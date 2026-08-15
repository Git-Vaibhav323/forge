from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.completeness import (
    RequiredField,
    next_unsatisfied,
    required_fields,
    score_answers,
    status_for_score,
)
from shared.db.models import ProjectRow, QuestionRow
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


def answers_map(rows: list[QuestionRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if row.answer:
            out[row.field] = row.answer
    return out


def list_question_rows(db: Session, project_id: str) -> list[QuestionRow]:
    return list(
        db.scalars(
            select(QuestionRow)
            .where(QuestionRow.project_id == project_id)
            .order_by(QuestionRow.created_at.asc())
        ).all()
    )


def _insert_open(db: Session, project_id: str, spec: RequiredField) -> QuestionRow:
    now = datetime.now(timezone.utc)
    row = QuestionRow(
        id=generate_question_id(),
        project_id=project_id,
        field=spec.field,
        text=spec.text,
        input_type=spec.input_type,
        options_json=json.dumps(list(spec.options)) if spec.options else None,
        why_asked=spec.why_asked,
        priority=spec.priority,
        status="open",
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row


def sync_completeness(db: Session, project: ProjectRow, rows: list[QuestionRow]) -> None:
    specs = required_fields(project.goal, project.category)
    completion, blocking = score_answers(specs, answers_map(rows))
    project.completion_score = completion
    project.blocking_fields_count = blocking
    project.status = status_for_score(completion, blocking)
    project.updated_at = datetime.now(timezone.utc)


def ensure_open_question(db: Session, project: ProjectRow) -> list[QuestionRow]:
    """Keep exactly one open question for the next unsatisfied required field."""
    rows = list_question_rows(db, project.id)
    specs = required_fields(project.goal, project.category)
    nxt = next_unsatisfied(specs, answers_map(rows))
    open_rows = [row for row in rows if row.status == "open"]
    dirty = False

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

    matching = [row for row in open_rows if row.field == nxt.field]
    extras = [row for row in open_rows if row.field != nxt.field]
    if extras:
        for row in extras:
            row.status = "skipped"
        dirty = True
    if not matching:
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
    refreshed = db.get(QuestionRow, question_id)
    assert refreshed is not None
    return refreshed
