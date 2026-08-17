"""The human-approval queue (M5): derive it, replay it, keep counts honest.

Three jobs, in this order (see `sync_reviews`):

1. **Replay** decisions a reviewer already made onto the attribute record.
   evidence-service rebuilds every AttributeRow from scratch on each re-scan
   (`_persist` deletes and re-inserts with fresh ids), so without this step a
   re-scan would silently undo human decisions. Review items are keyed on
   (project_id, field) precisely so they survive that.

2. **Derive** open items from the current attribute record. A field is a hold
   when two sources disagree, or when a safety-critical field has no evidence.

3. **Recompute** `conflicts_count` and `pending_approvals_count` on the job.
   These are the numbers the dashboard, the Review tab badge, and the Outputs
   print gate all read, so exactly one function owns them.

Governance (context.md): normalization runs automatically; choosing between
two genuinely different values never does.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    CompatibilityFindingRow,
    ProductRelationshipRow,
    ProjectRow,
    ReviewItemRow,
)
from shared.normalization import values_agree
from shared.risk import escalate, is_high_risk

REVIEW_DOC_ID = "review-decision"
REVIEW_DOC_NAME = "Reviewer decision (Review tab)"

# Items still awaiting a person. These are what `pendingApprovalsCount` counts.
OPEN_STATUSES = frozenset({"pending", "unresolved"})
# Decisions that put a value onto the record.
APPLIED_STATUSES = frozenset({"approved", "edited"})

# Attribute statuses that mean a human already settled the field.
SETTLED_STATUSES = frozenset({"verified", "not_applicable"})
# Statuses that make an absent safety-critical field a hold.
ABSENT_STATUSES = frozenset({"missing", "needs_review", "unverified"})


def _rev_id() -> str:
    return f"rev-{uuid.uuid4().hex[:12]}"


def _ev_id() -> str:
    return f"ev-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Reading the current record
# ---------------------------------------------------------------------------


def _attributes(db: Session, project_id: str) -> list[AttributeRow]:
    return list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project_id)
            .order_by(AttributeRow.name.asc())
        ).all()
    )


def _evidence_by_attribute(
    db: Session, attribute_ids: list[str]
) -> dict[str, list[AttributeEvidenceRow]]:
    if not attribute_ids:
        return {}
    rows = db.scalars(
        select(AttributeEvidenceRow).where(
            AttributeEvidenceRow.attribute_id.in_(attribute_ids)
        )
    ).all()
    grouped: dict[str, list[AttributeEvidenceRow]] = {}
    for row in rows:
        grouped.setdefault(row.attribute_id, []).append(row)
    return grouped


def _source_label(row: AttributeEvidenceRow) -> str:
    if row.page:
        return f"{row.document_name}, p.{row.page}"
    return row.document_name


def _conflict_values(rows: list[AttributeEvidenceRow]) -> list[dict]:
    """One entry per distinct value, in the ConflictValue wire shape."""
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        value = (row.value or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "value": f"{value} {row.unit}".strip() if row.unit else value,
                "source": _source_label(row),
                "sourceType": row.document_type or "document",
                "evidenceId": row.id,
            }
        )
    return out


def _all_agree(rows: list[AttributeEvidenceRow]) -> bool:
    """True when every source is stating the same fact in different words."""
    stated = [r for r in rows if (r.value or "").strip()]
    if len(stated) < 2:
        return False
    first = stated[0]
    return all(
        values_agree(first.value or "", first.unit, other.value or "", other.unit)
        for other in stated[1:]
    )


def _signature(issue_type: str, values: list[dict]) -> str:
    """Fingerprint of the disagreement, so a re-scan does not re-ask a settled question."""
    joined = "|".join(sorted(v["value"].lower() for v in values))
    return f"{issue_type}:{joined}"[:255]


# ---------------------------------------------------------------------------
# 1. Replay decisions onto the attribute record
# ---------------------------------------------------------------------------


def _upsert_review_evidence(db: Session, attr: AttributeRow, quote: str) -> None:
    existing = list(
        db.scalars(
            select(AttributeEvidenceRow).where(
                AttributeEvidenceRow.attribute_id == attr.id,
                AttributeEvidenceRow.document_id == REVIEW_DOC_ID,
            )
        ).all()
    )
    if existing:
        existing[0].quote = quote
        existing[0].value = attr.raw_value
        existing[0].unit = attr.unit
        return
    db.add(
        AttributeEvidenceRow(
            id=_ev_id(),
            attribute_id=attr.id,
            document_id=REVIEW_DOC_ID,
            document_name=REVIEW_DOC_NAME,
            document_type="review",
            page=None,
            quote=quote,
            value=attr.raw_value,
            unit=attr.unit,
        )
    )


def apply_review_decisions_to_attributes(db: Session, project: ProjectRow) -> None:
    """Re-apply settled decisions. Safe to call repeatedly and after a re-scan."""
    items = list(
        db.scalars(
            select(ReviewItemRow).where(ReviewItemRow.project_id == project.id)
        ).all()
    )
    if not items:
        return

    by_field = {attr.name: attr for attr in _attributes(db, project.id)}
    now = datetime.now(timezone.utc)

    for item in items:
        attr = by_field.get(item.field)
        if attr is None:
            continue

        if item.status in APPLIED_STATUSES and item.resolved_value:
            attr.raw_value = item.resolved_value
            attr.normalized_value = item.resolved_value
            attr.status = "verified"
            attr.confidence = 1.0
            attr.updated_at = now
            verb = "approved" if item.status == "approved" else "corrected to"
            _upsert_review_evidence(
                db,
                attr,
                f"Reviewer {verb}: {item.resolved_value}\nField: {item.field}",
            )
        elif item.status == "rejected":
            # Rejecting says the extracted value is wrong — abstain rather than
            # keep a value nobody stands behind. The field returns as a gap.
            attr.raw_value = ""
            attr.normalized_value = None
            attr.status = "missing"
            attr.confidence = 0.0
            attr.updated_at = now

    db.flush()


# ---------------------------------------------------------------------------
# 2. Derive open items from the record
# ---------------------------------------------------------------------------


def _field_label(name: str) -> str:
    return name.replace("_", " ")


def _classify(
    attr: AttributeRow, rows: list[AttributeEvidenceRow]
) -> dict | None:
    """Return the review item spec for this attribute, or None when it is fine."""
    if attr.status in SETTLED_STATUSES:
        return None

    if attr.status == "conflicting":
        values = _conflict_values(rows)
        return {
            "issue_type": "conflict",
            "severity": escalate(attr.risk_level, "high"),
            "values": values,
            "current_value": attr.raw_value or None,
            "proposed_value": values[0]["value"] if values else None,
            "reason": (
                f"{len(values)} sources disagree on {_field_label(attr.name)}. "
                "The desk will not pick one for you — approve a value or type "
                "the correct one."
            )
            if values
            else "Sources disagree on this field.",
            "evidence_ids": [r.id for r in rows],
        }

    if is_high_risk(attr.name) and attr.status in ABSENT_STATUSES:
        return {
            "issue_type": "high_risk",
            "severity": escalate(attr.risk_level, "high"),
            "values": [],
            "current_value": attr.raw_value or None,
            "proposed_value": None,
            "reason": (
                "No evidence found for a safety-critical field. This cannot be "
                "inferred from general knowledge — supply a source or record an "
                "explicit override."
            ),
            "evidence_ids": [r.id for r in rows],
        }

    return None


def derive_review_items(db: Session, project: ProjectRow) -> None:
    """Reconcile review_items against the current attribute record."""
    attrs = _attributes(db, project.id)
    ev_map = _evidence_by_attribute(db, [a.id for a in attrs])
    existing = {
        row.field: row
        for row in db.scalars(
            select(ReviewItemRow).where(ReviewItemRow.project_id == project.id)
        ).all()
    }
    now = datetime.now(timezone.utc)
    seen: set[str] = set()

    for attr in attrs:
        rows = ev_map.get(attr.id, [])

        # Unit-only disagreement is a representation artifact, not a hold.
        if attr.status == "conflicting" and _all_agree(rows):
            stated = [r for r in rows if (r.value or "").strip()]
            attr.status = "known"
            attr.raw_value = stated[0].value or attr.raw_value
            attr.unit = stated[0].unit or attr.unit
            attr.normalized_value = attr.raw_value
            attr.confidence = 0.9
            attr.updated_at = now

        spec = _classify(attr, rows)
        if spec is None:
            continue

        seen.add(attr.name)
        item = existing.get(attr.name)
        signature = _signature(spec["issue_type"], spec["values"])

        # How many jobs one correction would fix, including this one.
        candidates = [v["value"] for v in spec["values"]]
        if spec["current_value"]:
            candidates.append(spec["current_value"])
        siblings = sibling_attributes(db, project, attr.name, candidates)
        affected = 1 + len(siblings) if siblings else None

        if item is None:
            db.add(
                ReviewItemRow(
                    id=_rev_id(),
                    project_id=project.id,
                    field=attr.name,
                    product_id=None,
                    issue_type=spec["issue_type"],
                    severity=spec["severity"],
                    current_value=spec["current_value"],
                    proposed_value=spec["proposed_value"],
                    values_json=json.dumps(spec["values"]) if spec["values"] else None,
                    reason=spec["reason"],
                    evidence_ids_json=json.dumps(spec["evidence_ids"]),
                    affected_products=affected,
                    status="pending",
                    signature=signature,
                    created_at=now,
                    updated_at=now,
                )
            )
            continue

        # An already-decided item is only re-opened when the underlying
        # disagreement actually changed — otherwise a re-scan would nag.
        if item.signature != signature and item.status not in OPEN_STATUSES:
            item.status = "pending"
            item.resolved_value = None

        item.issue_type = spec["issue_type"]
        item.severity = spec["severity"]
        item.current_value = spec["current_value"]
        item.proposed_value = spec["proposed_value"]
        item.values_json = json.dumps(spec["values"]) if spec["values"] else None
        item.reason = spec["reason"]
        item.evidence_ids_json = json.dumps(spec["evidence_ids"])
        item.affected_products = affected
        item.signature = signature
        item.updated_at = now

    # A failed compatibility rule (M6) is also a hold — the sources agree, the
    # value is just wrong for this duty. An unresolved disagreement on the same
    # field takes precedence: you cannot check a rating nobody has agreed on,
    # so those fields are skipped here and picked up once the conflict clears.
    for finding in db.scalars(
        select(CompatibilityFindingRow).where(
            CompatibilityFindingRow.project_id == project.id,
            CompatibilityFindingRow.status == "fail",
        )
    ).all():
        if finding.field in seen:
            continue
        seen.add(finding.field)
        signature = f"incompatible:{finding.required_value}|{finding.rated_value}"[:255]
        item = existing.get(finding.field)

        if item is None:
            db.add(
                ReviewItemRow(
                    id=_rev_id(),
                    project_id=project.id,
                    field=finding.field,
                    product_id=None,
                    issue_type="incompatible",
                    severity=finding.severity,
                    current_value=finding.rated_value,
                    proposed_value=None,
                    values_json=None,
                    reason=finding.reason,
                    evidence_ids_json=finding.evidence_ids_json,
                    affected_products=None,
                    status="pending",
                    signature=signature,
                    created_at=now,
                    updated_at=now,
                )
            )
            continue

        if item.signature != signature and item.status not in OPEN_STATUSES:
            item.status = "pending"
            item.resolved_value = None

        item.issue_type = "incompatible"
        item.severity = finding.severity
        item.current_value = finding.rated_value
        item.proposed_value = None
        item.values_json = None
        item.reason = finding.reason
        item.evidence_ids_json = finding.evidence_ids_json
        item.signature = signature
        item.updated_at = now

    # Issues that resolved themselves (user answered the question, source
    # removed) drop out. Decided items are kept as the audit trail.
    for field, item in existing.items():
        if field in seen:
            continue
        if item.status in OPEN_STATUSES:
            db.delete(item)

    db.flush()


# ---------------------------------------------------------------------------
# Bulk propagation — the same extraction error on sibling jobs
# ---------------------------------------------------------------------------


def sibling_attributes(
    db: Session, project: ProjectRow, field: str, candidates: list[str]
) -> list[AttributeRow]:
    """Attributes on OTHER jobs in the same category showing the same wrong value.

    Preferred source is the M6 relationship graph: jobs explicitly derived as
    variants of this one (same manufacturer + model family). When no
    relationships have been resolved yet, this falls back to the M5 heuristic
    of "same category", which is broader and less certain.

    Either way it is only ever applied when the reviewer asks to propagate.
    """
    wanted = [c for c in candidates if c and c.strip()]
    if not wanted:
        return []

    related_ids = list(
        db.scalars(
            select(ProductRelationshipRow.related_project_id).where(
                ProductRelationshipRow.project_id == project.id
            )
        ).all()
    )

    query = select(AttributeRow).where(
        AttributeRow.name == field,
        AttributeRow.project_id != project.id,
        AttributeRow.status.not_in(tuple(SETTLED_STATUSES)),
    )
    if related_ids:
        query = query.where(AttributeRow.project_id.in_(related_ids))
    else:
        query = query.join(
            ProjectRow, AttributeRow.project_id == ProjectRow.id
        ).where(ProjectRow.category == project.category)

    rows = db.scalars(query).all()

    return [
        row
        for row in rows
        if any(values_agree(row.raw_value or "", row.unit, value, None) for value in wanted)
    ]


def candidate_values(item: ReviewItemRow) -> list[str]:
    """Every value this item might be replacing, for sibling matching."""
    values: list[str] = []
    if item.values_json:
        try:
            values = [v["value"] for v in json.loads(item.values_json) if v.get("value")]
        except (ValueError, KeyError, TypeError):
            values = []
    if item.current_value:
        values.append(item.current_value)
    return values


# ---------------------------------------------------------------------------
# 3. Counts — the single writer
# ---------------------------------------------------------------------------


def recompute_counts(db: Session, project: ProjectRow) -> None:
    conflicts = sum(
        1 for attr in _attributes(db, project.id) if attr.status == "conflicting"
    )
    pending = sum(
        1
        for item in db.scalars(
            select(ReviewItemRow).where(ReviewItemRow.project_id == project.id)
        ).all()
        if item.status in OPEN_STATUSES
    )
    project.conflicts_count = conflicts
    project.pending_approvals_count = pending
    project.updated_at = datetime.now(timezone.utc)
    db.flush()


def sync_reviews(db: Session, project: ProjectRow) -> None:
    """Full reconcile. Call from review GETs and after an evidence re-scan."""
    apply_review_decisions_to_attributes(db, project)
    derive_review_items(db, project)
    recompute_counts(db, project)
