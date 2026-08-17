"""Resolve relationships, compatibility and BOM for a job (M6).

Sits between the pure rule modules (`shared/compatibility.py`, `shared/bom.py`)
and the database, the same way `review_sync` sits under review-service.

The two sides of every compatibility check already exist on the record:

  * the **requirement** — the user's answer, which
    `record_sync.apply_user_answers_to_attributes` writes onto the attribute
    and marks with a `user-answer` evidence row; and
  * the **rating** — the document evidence rows, each carrying the value its
    own source stated (the `value` column added in M5).

When an attribute is still `conflicting` there is no trustworthy rating, so
every rule over that field abstains. You cannot check a number you have not
agreed on yet.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shared.bom import BOM_GOALS, Component, resolve_lines
from shared.compatibility import Side, evaluate_all
from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    BomLineRow,
    CompatibilityFindingRow,
    ProductRelationshipRow,
    ProjectRow,
)
from shared.record_sync import USER_ANSWER_DOC_ID
from shared.review_sync import REVIEW_DOC_ID

# Evidence rows that represent a human input rather than a source document.
HUMAN_DOC_IDS = frozenset({USER_ANSWER_DOC_ID, REVIEW_DOC_ID})

# Attribute statuses whose value is solid enough to put on a BOM line.
USABLE_STATUSES = frozenset({"known", "verified", "derived"})


def _rel_id() -> str:
    return f"rel-{uuid.uuid4().hex[:12]}"


def _find_id() -> str:
    return f"cmp-{uuid.uuid4().hex[:12]}"


def _bom_id() -> str:
    return f"bom-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Reading the record
# ---------------------------------------------------------------------------


def _load(db: Session, project_id: str) -> tuple[list[AttributeRow], dict[str, list[AttributeEvidenceRow]]]:
    attrs = list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project_id)
            .order_by(AttributeRow.name.asc())
        ).all()
    )
    if not attrs:
        return [], {}
    rows = db.scalars(
        select(AttributeEvidenceRow).where(
            AttributeEvidenceRow.attribute_id.in_([a.id for a in attrs])
        )
    ).all()
    grouped: dict[str, list[AttributeEvidenceRow]] = {}
    for row in rows:
        grouped.setdefault(row.attribute_id, []).append(row)
    return attrs, grouped


def split_sides(
    attrs: list[AttributeRow], ev_map: dict[str, list[AttributeEvidenceRow]]
) -> tuple[dict[str, Side], dict[str, Side]]:
    """Separate what the user requires from what the sources rate."""
    requirements: dict[str, Side] = {}
    ratings: dict[str, Side] = {}

    for attr in attrs:
        rows = ev_map.get(attr.id, [])
        human = [r for r in rows if r.document_id in HUMAN_DOC_IDS]
        documents = [r for r in rows if r.document_id not in HUMAN_DOC_IDS]

        # The user's answer is written onto the attribute itself; the evidence
        # row only records that a human supplied it.
        if human and (attr.raw_value or "").strip():
            requirements[attr.name] = Side(
                value=attr.raw_value.strip(),
                unit=attr.unit,
                evidence_ids=tuple(r.id for r in human),
            )

        # A field still in dispute has no rating anyone can rely on.
        if attr.status == "conflicting":
            continue

        stated = [r for r in documents if (r.value or "").strip()]
        if stated:
            ratings[attr.name] = Side(
                value=(stated[0].value or "").strip(),
                unit=stated[0].unit or attr.unit,
                evidence_ids=tuple(r.id for r in stated),
            )
        elif not human and (attr.raw_value or "").strip() and attr.status in USABLE_STATUSES:
            # Extracted before the per-source `value` column existed.
            ratings[attr.name] = Side(
                value=attr.raw_value.strip(),
                unit=attr.unit,
                evidence_ids=tuple(r.id for r in documents),
            )

    return requirements, ratings


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def model_family(model: str) -> str:
    """MFC-GV-100 → MFC-GV. A size suffix does not make a different product."""
    cleaned = (model or "").strip().upper()
    if not cleaned:
        return ""
    for separator in ("-", "/"):
        if separator in cleaned:
            head, _, tail = cleaned.rpartition(separator)
            # Only strip the last segment when it looks like a size/variant code.
            if head and any(ch.isdigit() for ch in tail):
                return head
    return cleaned


def _identity(db: Session, project_ids: list[str]) -> dict[str, tuple[str, str]]:
    """project_id → (manufacturer, model family), for jobs that state both."""
    if not project_ids:
        return {}
    rows = db.scalars(
        select(AttributeRow).where(
            AttributeRow.project_id.in_(project_ids),
            AttributeRow.name.in_(("manufacturer", "model")),
        )
    ).all()

    collected: dict[str, dict[str, str]] = {}
    for row in rows:
        value = (row.raw_value or "").strip()
        if not value or row.status not in USABLE_STATUSES:
            continue
        collected.setdefault(row.project_id, {})[row.name] = value

    out: dict[str, tuple[str, str]] = {}
    for project_id, values in collected.items():
        manufacturer = values.get("manufacturer", "").strip().upper()
        family = model_family(values.get("model", ""))
        if manufacturer and family:
            out[project_id] = (manufacturer, family)
    return out


def derive_variants(db: Session, project: ProjectRow) -> int:
    """Link jobs that share a manufacturer and model family. Returns the count."""
    db.execute(
        delete(ProductRelationshipRow).where(
            ProductRelationshipRow.project_id == project.id
        )
    )

    candidates = list(
        db.scalars(
            select(ProjectRow.id).where(ProjectRow.category == project.category)
        ).all()
    )
    identities = _identity(db, candidates)
    mine = identities.get(project.id)
    if mine is None:
        db.flush()
        return 0

    now = datetime.now(timezone.utc)
    linked = 0
    for other_id, theirs in identities.items():
        if other_id == project.id or theirs != mine:
            continue
        db.add(
            ProductRelationshipRow(
                id=_rel_id(),
                project_id=project.id,
                related_project_id=other_id,
                relation="variant",
                basis=f"Same manufacturer ({mine[0]}) and model family ({mine[1]})",
                confidence=0.9,
                created_at=now,
            )
        )
        linked += 1

    db.flush()
    return linked


# ---------------------------------------------------------------------------
# Compatibility + BOM persistence
# ---------------------------------------------------------------------------


def _persist_findings(db: Session, project: ProjectRow, findings) -> None:
    db.execute(
        delete(CompatibilityFindingRow).where(
            CompatibilityFindingRow.project_id == project.id
        )
    )
    now = datetime.now(timezone.utc)
    for finding in findings:
        db.add(
            CompatibilityFindingRow(
                id=_find_id(),
                project_id=project.id,
                rule=finding.rule,
                field=finding.field,
                status=finding.status,
                severity=finding.severity,
                required_value=finding.required_value,
                rated_value=finding.rated_value,
                reason=finding.reason,
                evidence_ids_json=json.dumps(list(finding.evidence_ids)),
                created_at=now,
            )
        )
    db.flush()


def _persist_bom(db: Session, project: ProjectRow, lines) -> None:
    db.execute(delete(BomLineRow).where(BomLineRow.project_id == project.id))
    now = datetime.now(timezone.utc)
    for line in lines:
        db.add(
            BomLineRow(
                id=_bom_id(),
                project_id=project.id,
                position=line.position,
                role=line.role,
                component=line.component,
                quantity=line.quantity,
                unit=line.unit,
                status=line.status,
                source_field=line.source_field,
                reason=line.reason,
                evidence_ids_json=json.dumps(list(line.evidence_ids)),
                created_at=now,
            )
        )
    db.flush()


def _bom_components(
    attrs: list[AttributeRow], ev_map: dict[str, list[AttributeEvidenceRow]]
) -> dict[str, Component]:
    known: dict[str, Component] = {}
    for attr in attrs:
        if attr.status not in USABLE_STATUSES:
            continue
        value = (attr.raw_value or "").strip()
        if not value:
            continue
        known[attr.name] = Component(
            value=value,
            unit=attr.unit,
            status="resolved",
            evidence_ids=tuple(r.id for r in ev_map.get(attr.id, [])),
        )
    return known


def resolve_relationships(db: Session, project: ProjectRow) -> None:
    """Full M6 pass. Safe to call repeatedly; each run replaces the last."""
    attrs, ev_map = _load(db, project.id)

    requirements, ratings = split_sides(attrs, ev_map)
    _persist_findings(db, project, evaluate_all(requirements, ratings))

    derive_variants(db, project)

    if project.goal in BOM_GOALS:
        known = _bom_components(attrs, ev_map)
        quantity = known.get("quantity")
        _persist_bom(
            db,
            project,
            resolve_lines(project.goal, known, quantity.value if quantity else None),
        )
    else:
        db.execute(delete(BomLineRow).where(BomLineRow.project_id == project.id))
        db.flush()
