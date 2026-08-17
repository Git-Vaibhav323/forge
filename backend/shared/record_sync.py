"""Keep Evidence attributes aligned with Questions for any job type."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from shared.completeness import COMMON, is_satisfied
from shared.db.models import AttributeEvidenceRow, AttributeRow, ProjectRow, QuestionRow
from shared.evidence_fields import DOCUMENT_EXTRACT_GOALS, allowed_evidence_fields, question_field_names
from shared.question_engine import JobContext, active_specs, build_job_context, list_question_rows
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


@dataclass
class _Record:
    """Everything the sync needs, read once.

    This runs when question answers are synced onto attributes. Keep it cheap:
    the pass is built to cost three queries and to write nothing when nothing moved.
    """

    ctx: JobContext
    attrs: dict[str, AttributeRow] = dataclass_field(default_factory=dict)
    user_evidence: dict[str, AttributeEvidenceRow] = dataclass_field(default_factory=dict)


def _load_record(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow]
) -> _Record:
    attributes = list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project.id)
            .options(selectinload(AttributeRow.evidence_rows))
            .order_by(AttributeRow.name.asc())
        ).all()
    )
    user_evidence: dict[str, AttributeEvidenceRow] = {}
    for attr in attributes:
        for evidence in attr.evidence_rows:
            if evidence.document_id == USER_ANSWER_DOC_ID:
                user_evidence[attr.id] = evidence
                break

    return _Record(
        ctx=build_job_context(db, project, question_rows, attributes=attributes),
        attrs={attr.name: attr for attr in attributes},
        user_evidence=user_evidence,
    )


def _new_attribute(project_id: str, field: str, now: datetime) -> AttributeRow:
    return AttributeRow(
        id=_attr_id(),
        project_id=project_id,
        name=field,
        raw_value="",
        normalized_value=None,
        unit=None,
        confidence=0.0,
        status="missing",
        risk_level=_risk_for_field(field),
        updated_at=now,
    )


def _prune(db: Session, record: _Record) -> bool:
    """Drop attribute rows that no longer belong to this job's evidence field set."""
    allowed = allowed_evidence_fields(record.ctx)
    changed = False
    for name, attr in list(record.attrs.items()):
        if name in allowed:
            continue
        # Anything a document actually stated stays on the record, even when the
        # scenario stopped asking for it.
        if any(ev.document_id != USER_ANSWER_DOC_ID for ev in attr.evidence_rows):
            continue
        db.delete(attr)
        record.attrs.pop(name)
        record.user_evidence.pop(attr.id, None)
        changed = True
    return changed


def _ensure_schema(db: Session, project: ProjectRow, record: _Record, now: datetime) -> bool:
    """Create attribute rows for every field shown on Evidence for this job."""
    wanted = {spec.field for spec in active_specs(record.ctx)}
    if record.ctx.goal in DOCUMENT_EXTRACT_GOALS:
        wanted |= {spec.field for spec in COMMON}

    changed = False
    for field in sorted(wanted - set(record.attrs)):
        attr = _new_attribute(project.id, field, now)
        db.add(attr)
        record.attrs[field] = attr
        changed = True
    return changed


def _apply_answers(
    db: Session,
    project: ProjectRow,
    question_rows: list[QuestionRow],
    record: _Record,
    now: datetime,
) -> bool:
    """Promote satisfied question answers onto the Evidence record."""
    allowed = question_field_names(record.ctx)
    changed = False

    for question in question_rows:
        if question.status != "answered" or not question.answer:
            continue
        if question.field not in allowed or not is_satisfied(question.answer):
            continue

        attr = record.attrs.get(question.field)
        if attr is None:
            attr = _new_attribute(project.id, question.field, now)
            db.add(attr)
            record.attrs[question.field] = attr
            changed = True

        answer = question.answer.strip()
        if (attr.raw_value, attr.status, attr.confidence) != (answer, "verified", 1.0):
            attr.raw_value = answer
            attr.normalized_value = answer
            attr.confidence = 1.0
            attr.status = "verified"
            attr.risk_level = _risk_for_field(question.field)
            attr.updated_at = now
            changed = True

        quote = f"Q: {question.text}\nA: {answer}"
        evidence = record.user_evidence.get(attr.id)
        if evidence is None:
            # Postgres enforces the evidence FK, so the attribute must exist first.
            db.flush()
            evidence = AttributeEvidenceRow(
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
            db.add(evidence)
            record.user_evidence[attr.id] = evidence
            changed = True
        elif (evidence.quote, evidence.value, evidence.unit) != (quote, answer, attr.unit):
            evidence.quote = quote
            evidence.value = answer
            evidence.unit = attr.unit
            changed = True

    return changed


def sync_record_from_questions(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow] | None = None
) -> bool:
    """Full sync: prune, schema rows, user answers. Returns True if anything moved."""
    rows = question_rows if question_rows is not None else list_question_rows(db, project.id)
    record = _load_record(db, project, rows)
    now = datetime.now(timezone.utc)

    changed = _prune(db, record)
    changed = _ensure_schema(db, project, record, now) or changed
    changed = _apply_answers(db, project, rows, record, now) or changed

    if changed:
        db.flush()
    return changed


def apply_user_answers_to_attributes(
    db: Session, project: ProjectRow, question_rows: list[QuestionRow] | None = None
) -> bool:
    """Promote answers onto the record without pruning (used after a re-scan)."""
    rows = question_rows if question_rows is not None else list_question_rows(db, project.id)
    record = _load_record(db, project, rows)
    now = datetime.now(timezone.utc)

    changed = _ensure_schema(db, project, record, now)
    changed = _apply_answers(db, project, rows, record, now) or changed

    if changed:
        db.flush()
    return changed
