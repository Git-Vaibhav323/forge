"""Keep Evidence attributes aligned with Questions for any job type."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.completeness import COMMON, is_satisfied
from shared.db.models import AttributeEvidenceRow, AttributeRow, ProjectRow, QuestionRow
from shared.evidence_fields import DOCUMENT_EXTRACT_GOALS, allowed_evidence_fields, question_field_names
from shared.question_engine import active_specs, build_job_context, list_question_rows
from shared.risk import HIGH_RISK_FIELDS  # noqa: F401  (re-exported for callers)

USER_ANSWER_DOC_ID = "user-answer"
USER_ANSWER_DOC_NAME = "User answer (Questions tab)"


def _attr_id() -> str:
    return f"attr-{uuid.uuid4().hex[:12]}"


def _ev_id() -> str:
    return f"ev-{uuid.uuid4().hex[:12]}"


def _risk_for_field(field: str) -> str:
    from shared.risk import risk_for_field

    return risk_for_field(field)


def _attribute_map(db: Session, project_id: str) -> dict[str, AttributeRow]:
    rows = list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project_id)
            .order_by(AttributeRow.name.asc())
        ).all()
    )
    return {row.name: row for row in rows}


def prune_stale_attributes(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow] | None = None
) -> None:
    """Drop attribute rows that no longer belong to this job's evidence field set."""
    rows = question_rows if question_rows is not None else list_question_rows(db, project.id)
    ctx = build_job_context(db, project, rows)
    allowed = allowed_evidence_fields(ctx)
    stale = list(
        db.scalars(
            select(AttributeRow).where(AttributeRow.project_id == project.id)
        ).all()
    )
    for attr in stale:
        if attr.name in allowed:
            continue
        has_doc_evidence = any(
            ev.document_id != USER_ANSWER_DOC_ID for ev in attr.evidence_rows
        )
        if has_doc_evidence:
            continue
        db.delete(attr)
    db.flush()


def ensure_attribute_schema(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow] | None = None
) -> None:
    """Create missing attribute rows for every field shown on Evidence for this job."""
    rows = question_rows if question_rows is not None else list_question_rows(db, project.id)
    ctx = build_job_context(db, project, rows)
    specs_map = {spec.field: spec for spec in active_specs(ctx)}
    if ctx.goal in DOCUMENT_EXTRACT_GOALS:
        for spec in COMMON:
            specs_map.setdefault(spec.field, spec)
    existing = _attribute_map(db, project.id)
    now = datetime.now(timezone.utc)

    for spec in specs_map.values():
        if spec.field in existing:
            continue
        db.add(
            AttributeRow(
                id=_attr_id(),
                project_id=project.id,
                name=spec.field,
                raw_value="",
                normalized_value=None,
                unit=None,
                confidence=0.0,
                status="missing",
                risk_level=_risk_for_field(spec.field),
                updated_at=now,
            )
        )
    db.flush()


def _upsert_user_evidence(
    db: Session,
    attr: AttributeRow,
    *,
    question_text: str,
    answer: str,
) -> None:
    quote = f"Q: {question_text}\nA: {answer}"
    existing = list(
        db.scalars(
            select(AttributeEvidenceRow).where(
                AttributeEvidenceRow.attribute_id == attr.id,
                AttributeEvidenceRow.document_id == USER_ANSWER_DOC_ID,
            )
        ).all()
    )
    if existing:
        existing[0].quote = quote
        existing[0].value = answer
        existing[0].unit = attr.unit
        return
    db.add(
        AttributeEvidenceRow(
            id=_ev_id(),
            attribute_id=attr.id,
            document_id=USER_ANSWER_DOC_ID,
            document_name=USER_ANSWER_DOC_NAME,
            document_type="user",
            page=None,
            quote=quote,
            # Mirrors the per-source value on document evidence (M5), so the
            # requirement side of a compatibility check is self-describing (M6).
            value=answer,
            unit=attr.unit,
        )
    )


def apply_user_answers_to_attributes(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow] | None = None
) -> None:
    """Promote satisfied question answers onto the Evidence record."""
    rows = question_rows if question_rows is not None else list_question_rows(db, project.id)
    ensure_attribute_schema(db, project, rows)
    by_name = _attribute_map(db, project.id)
    now = datetime.now(timezone.utc)
    allowed = question_field_names(build_job_context(db, project, rows))

    for question in rows:
        if question.status not in {"answered"} or not question.answer:
            continue
        if question.field not in allowed:
            continue
        if not is_satisfied(question.answer):
            continue
        attr = by_name.get(question.field)
        if attr is None:
            attr = AttributeRow(
                id=_attr_id(),
                project_id=project.id,
                name=question.field,
                raw_value="",
                normalized_value=None,
                unit=None,
                confidence=0.0,
                status="missing",
                risk_level=_risk_for_field(question.field),
                updated_at=now,
            )
            db.add(attr)
            db.flush()
            by_name[question.field] = attr

        answer = question.answer.strip()
        attr.raw_value = answer
        attr.normalized_value = answer
        attr.confidence = 1.0
        attr.status = "verified"
        attr.risk_level = _risk_for_field(question.field)
        attr.updated_at = now
        _upsert_user_evidence(
            db,
            attr,
            question_text=question.text,
            answer=answer,
        )

    db.flush()


def sync_record_from_questions(db: Session, project: ProjectRow) -> None:
    """Full sync: schema rows + user answers. Safe to call from GET or POST handlers."""
    rows = list_question_rows(db, project.id)
    prune_stale_attributes(db, project, rows)
    ensure_attribute_schema(db, project, rows)
    apply_user_answers_to_attributes(db, project, rows)
