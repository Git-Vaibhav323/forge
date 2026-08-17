from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shared.bom import BOM_GOALS
from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    BomLineRow,
    CompatibilityFindingRow,
    OutputRow,
    ProjectRow,
    ReviewItemRow,
)
from shared.output_render import (
    RenderBomLine,
    RenderContext,
    RenderField,
    RenderFinding,
    output_filename,
    render,
)
from shared.qa import PUBLISHABLE_STATUSES, QaResult, evaluate
from shared.relationship_sync import resolve_relationships
from shared.review_sync import OPEN_STATUSES, sync_reviews
from shared.schemas import OutputArtifact


def _output_id() -> str:
    return f"out-{uuid.uuid4().hex[:12]}"


def _storage_key(project_id: str, output_id: str, filename: str) -> str:
    return f"{project_id}/outputs/{output_id}/{filename}"


def _put(storage_key: str, data: bytes, content_type: str) -> None:
    # Lazy import so this module does not pull object-storage config at import
    # time, and so tests can monkeypatch it. Same pattern as evidence-service.
    from services.file_service.storage import put_object

    put_object(storage_key, data, content_type)


def _get(storage_key: str) -> bytes:
    from services.file_service.storage import get_object

    return get_object(storage_key)


def _remove(storage_key: str) -> None:
    from services.file_service.storage import remove_object

    remove_object(storage_key)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def row_to_output(row: OutputRow) -> OutputArtifact:
    return OutputArtifact.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "type": row.type,
            "filename": row.filename,
            "status": row.status,
            "generatedAt": row.generated_at,
            "qaNotes": json.loads(row.qa_notes_json) if row.qa_notes_json else None,
            # Only offered when bytes actually exist.
            "downloadUrl": f"/api/outputs/{row.id}/download" if row.storage_key else None,
            "sizeBytes": row.size_bytes,
        }
    )


def list_outputs(db: Session, project_id: str) -> list[OutputArtifact]:
    rows = db.scalars(
        select(OutputRow)
        .where(OutputRow.project_id == project_id)
        .order_by(OutputRow.created_at.desc())
    ).all()
    return [row_to_output(row) for row in rows]


# ---------------------------------------------------------------------------
# Gathering the record
# ---------------------------------------------------------------------------


def _citations(rows: list[AttributeEvidenceRow]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        label = f"{row.document_name}, p.{row.page}" if row.page else row.document_name
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
    return tuple(out)


def _collect(db: Session, project: ProjectRow) -> tuple[list[RenderField], list[RenderField]]:
    attrs = list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project.id)
            .order_by(AttributeRow.name.asc())
        ).all()
    )
    ev_map: dict[str, list[AttributeEvidenceRow]] = {}
    if attrs:
        for row in db.scalars(
            select(AttributeEvidenceRow).where(
                AttributeEvidenceRow.attribute_id.in_([a.id for a in attrs])
            )
        ).all():
            ev_map.setdefault(row.attribute_id, []).append(row)

    established: list[RenderField] = []
    withheld: list[RenderField] = []

    for attr in attrs:
        citations = _citations(ev_map.get(attr.id, []))
        item = RenderField(
            name=attr.name,
            value=attr.raw_value or "",
            unit=attr.unit,
            status=attr.status,
            confidence=attr.confidence,
            citations=citations,
        )
        # A value with no citation is never stated as fact, whatever its status.
        if attr.status in PUBLISHABLE_STATUSES and (attr.raw_value or "").strip() and citations:
            established.append(item)
        else:
            withheld.append(item)

    return established, withheld


def run_qa(db: Session, project: ProjectRow) -> QaResult:
    """Re-derive the record, then decide whether it may be printed."""
    resolve_relationships(db, project)
    sync_reviews(db, project)
    db.flush()

    established, withheld = _collect(db, project)

    conflicting = [f.name for f in withheld if f.status == "conflicting"]
    unverified = [f.name for f in withheld if f.status == "unverified"]
    missing = [f.name for f in withheld if f.status in {"missing", "needs_review"}]

    holds = [
        row.field
        for row in db.scalars(
            select(ReviewItemRow).where(ReviewItemRow.project_id == project.id)
        ).all()
        if row.status in OPEN_STATUSES
    ]

    abstained = [
        row.rule
        for row in db.scalars(
            select(CompatibilityFindingRow).where(
                CompatibilityFindingRow.project_id == project.id,
                CompatibilityFindingRow.status == "unknown",
            )
        ).all()
    ]

    unresolved_bom = 0
    if project.goal in BOM_GOALS:
        unresolved_bom = sum(
            1
            for row in db.scalars(
                select(BomLineRow).where(BomLineRow.project_id == project.id)
            ).all()
            if row.status == "missing"
        )

    return evaluate(
        conflicting_fields=conflicting,
        pending_holds=holds,
        missing_fields=missing,
        unverified_fields=unverified,
        abstained_rules=abstained,
        unresolved_bom_lines=unresolved_bom,
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _build_context(
    db: Session, project: ProjectRow, qa: QaResult, now: datetime
) -> RenderContext:
    established, withheld = _collect(db, project)

    bom_lines = [
        RenderBomLine(
            position=row.position,
            role=row.role,
            component=row.component,
            quantity=row.quantity,
            status=row.status,
            reason=row.reason,
        )
        for row in db.scalars(
            select(BomLineRow)
            .where(BomLineRow.project_id == project.id)
            .order_by(BomLineRow.position.asc())
        ).all()
    ]

    findings = [
        RenderFinding(
            rule=row.rule,
            status=row.status,
            required_value=row.required_value,
            rated_value=row.rated_value,
            reason=row.reason,
        )
        for row in db.scalars(
            select(CompatibilityFindingRow)
            .where(CompatibilityFindingRow.project_id == project.id)
            .order_by(CompatibilityFindingRow.rule.asc())
        ).all()
    ]

    return RenderContext(
        project_id=project.id,
        project_name=project.name,
        goal=project.goal,
        category=project.category,
        generated_at=now,
        established=established,
        withheld=withheld,
        bom_lines=bom_lines,
        findings=findings,
        qa_notes=qa.notes,
    )


def _replace_existing(db: Session, project_id: str, output_type: str) -> None:
    """Regenerating replaces the previous artifact rather than piling up copies."""
    for row in db.scalars(
        select(OutputRow).where(
            OutputRow.project_id == project_id, OutputRow.type == output_type
        )
    ).all():
        if row.storage_key:
            _remove(row.storage_key)
    db.execute(
        delete(OutputRow).where(
            OutputRow.project_id == project_id, OutputRow.type == output_type
        )
    )
    db.flush()


def generate_output(
    db: Session, project: ProjectRow, output_type: str
) -> OutputArtifact:
    """Print the package — or record why it could not be printed."""
    qa = run_qa(db, project)
    now = datetime.now(timezone.utc)
    output_id = _output_id()
    filename = output_filename(output_type, project.id)

    _replace_existing(db, project.id, output_type)

    if not qa.passed:
        # Nothing legitimate to write, so no file is written. The row exists so
        # the Outputs tab can say exactly what is blocking it.
        row = OutputRow(
            id=output_id,
            project_id=project.id,
            type=output_type,
            filename=filename,
            status="qa_failed",
            storage_key=None,
            content_type="text/markdown",
            size_bytes=None,
            qa_notes_json=json.dumps(qa.notes),
            generated_at=None,
            created_at=now,
        )
        db.add(row)
        db.commit()
        return row_to_output(row)

    body = render(_build_context(db, project, qa, now)).encode("utf-8")
    storage_key = _storage_key(project.id, output_id, filename)
    _put(storage_key, body, "text/markdown; charset=utf-8")

    row = OutputRow(
        id=output_id,
        project_id=project.id,
        type=output_type,
        filename=filename,
        status=qa.status,
        storage_key=storage_key,
        content_type="text/markdown; charset=utf-8",
        size_bytes=len(body),
        qa_notes_json=json.dumps(qa.notes) if qa.notes else None,
        generated_at=now,
        created_at=now,
    )
    db.add(row)

    project.status = "generated"
    project.updated_at = now
    db.commit()
    return row_to_output(row)


def read_output_bytes(db: Session, output_id: str) -> tuple[OutputRow, bytes]:
    row = db.get(OutputRow, output_id)
    if row is None:
        raise KeyError(output_id)
    if not row.storage_key:
        raise ValueError("This output was blocked by QA and has no file")
    return row, _get(row.storage_key)
