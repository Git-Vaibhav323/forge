from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.completeness import is_satisfied, status_for_score
from shared.db.models import AttributeRow, ProjectRow, QuestionRow
from shared.qa import PUBLISHABLE_STATUSES
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
    """Evidence pre-fill + conditional rules + one built-in question at a time."""
    rows = list_question_rows(db, project.id)
    open_rows = [row for row in rows if row.status == "open"]
    dirty = False

    # Fast path: one open question already answered by publishable evidence.
    if len(open_rows) == 1:
        field = open_rows[0].field
        attr = db.scalar(
            select(AttributeRow).where(
                AttributeRow.project_id == project.id,
                AttributeRow.name == field,
            )
        )
        if (
            attr is not None
            and attr.status in PUBLISHABLE_STATUSES
            and (attr.raw_value or "").strip()
        ):
            open_rows[0].status = "skipped"
            dirty = True
            open_rows = []

    ctx = build_job_context(db, project, rows)
    merged = ctx.merged_answers

    for row in open_rows:
        if is_satisfied(merged.get(row.field)):
            row.status = "skipped"
            dirty = True
    if dirty:
        open_rows = [row for row in rows if row.status == "open"]

    if open_rows:
        for row in open_rows[1:]:
            row.status = "skipped"
            dirty = True
        if dirty:
            sync_completeness(db, project, rows)
            db.commit()
            return list_question_rows(db, project.id)
        return rows

    nxt = pick_next_question(ctx)
    if nxt is not None:
        rows.append(_insert_open(db, project.id, nxt))
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
