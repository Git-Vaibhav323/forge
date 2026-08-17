from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from services.question_service.config import settings
from shared.completeness import RequiredField, is_satisfied, status_for_score
from shared.db.models import ProjectRow, QuestionRow
from shared.llm_ranker import LlmSettings
from shared.question_engine import (
    NextQuestion,
    build_job_context,
    completeness_for_job,
    list_question_rows,
    pick_next_question,
)
from shared.record_sync import sync_record_from_questions
from shared.schemas import Question


def generate_question_id() -> str:
    return f"q-{uuid.uuid4().hex[:8]}"


def _llm_settings() -> LlmSettings:
    return LlmSettings(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )


def _options_list(row: QuestionRow) -> list[str] | None:
    if not row.options_json:
        return None
    parsed = json.loads(row.options_json)
    return list(parsed) if parsed else None


def row_to_question(row: QuestionRow) -> Question:
    return Question.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "field": row.field,
            "text": row.text,
            "inputType": row.input_type,
            "options": _options_list(row),
            "whyAsked": row.why_asked,
            "priority": row.priority,
            "status": row.status,
            "answer": row.answer,
            "answeredAt": row.answered_at,
        }
    )


def _insert_open(db: Session, project_id: str, nxt: NextQuestion) -> QuestionRow:
    spec = nxt.spec
    now = datetime.now(timezone.utc)
    row = QuestionRow(
        id=generate_question_id(),
        project_id=project_id,
        field=spec.field,
        text=nxt.text,
        input_type=spec.input_type,
        options_json=json.dumps(list(spec.options)) if spec.options else None,
        why_asked=nxt.why_asked,
        priority=spec.priority,
        status="open",
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row


def sync_completeness(db: Session, project: ProjectRow, rows: list[QuestionRow]) -> None:
    ctx = build_job_context(db, project, rows)
    completion, blocking = completeness_for_job(ctx)
    project.completion_score = completion
    project.blocking_fields_count = blocking
    project.status = status_for_score(completion, blocking)
    project.updated_at = datetime.now(timezone.utc)


def ensure_open_question(db: Session, project: ProjectRow) -> list[QuestionRow]:
    """Hybrid: evidence pre-fill + conditional rules + LLM wording + one open Q."""
    rows = list_question_rows(db, project.id)
    ctx = build_job_context(db, project, rows)
    merged = ctx.merged_answers
    open_rows = [row for row in rows if row.status == "open"]
    dirty = False

    # Drop open questions for fields already satisfied (e.g. new evidence extract).
    for row in open_rows:
        if is_satisfied(merged.get(row.field)):
            row.status = "skipped"
            dirty = True
    if dirty:
        open_rows = [row for row in rows if row.status == "open"]

    nxt = pick_next_question(ctx, _llm_settings())

    if nxt is None:
        if open_rows:
            for row in open_rows:
                row.status = "skipped"
            dirty = True
        if dirty:
            sync_completeness(db, project, rows)
            db.commit()
            return list_question_rows(db, project.id)
        return rows

    matching = [row for row in open_rows if row.field == nxt.spec.field]
    extras = [row for row in open_rows if row.field != nxt.spec.field]
    if extras:
        for row in extras:
            row.status = "skipped"
        dirty = True
    if not matching:
        rows.append(_insert_open(db, project.id, nxt))
        dirty = True
    elif matching:
        # Refresh wording when LLM returns scenario-specific copy for same field.
        row = matching[0]
        if row.text != nxt.text or row.why_asked != nxt.why_asked:
            row.text = nxt.text
            row.why_asked = nxt.why_asked
            dirty = True

    if dirty:
        sync_completeness(db, project, rows)
        db.commit()
        return list_question_rows(db, project.id)
    return rows


def answer_question_row(
    db: Session, project: ProjectRow, question_id: str, answer: str
) -> QuestionRow:
    row = db.get(QuestionRow, question_id)
    if row is None or row.project_id != project.id:
        raise KeyError(question_id)
    if row.status != "open":
        raise ValueError("Question is not open")

    now = datetime.now(timezone.utc)
    row.answer = answer.strip()
    row.status = "answered"
    row.answered_at = now
    db.flush()
    ensure_open_question(db, project)
    rows = list_question_rows(db, project.id)
    sync_completeness(db, project, rows)
    sync_record_from_questions(db, project)
    db.commit()
    refreshed = db.get(QuestionRow, question_id)
    assert refreshed is not None
    return refreshed
