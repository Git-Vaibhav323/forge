from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.question_service.repository import (
    answer_question_row,
    ensure_open_question,
    row_to_question,
)
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory
from shared.schemas import AnswerInput, Question

router = APIRouter(prefix="/api/projects", tags=["questions"])


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def _project(db: Session, project_id: str) -> ProjectRow:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/questions", response_model=list[Question])
def list_questions(project_id: str, db: Session = Depends(get_db)) -> list[Question]:
    project = _project(db, project_id)
    rows = ensure_open_question(db, project)
    return [row_to_question(row) for row in rows]


@router.post("/{project_id}/questions/{question_id}/answer", response_model=Question)
def answer_question(
    project_id: str,
    question_id: str,
    payload: AnswerInput,
    db: Session = Depends(get_db),
) -> Question:
    project = _project(db, project_id)
    if not payload.answer or not payload.answer.strip():
        raise HTTPException(status_code=400, detail="Answer is required")
    try:
        row = answer_question_row(db, project, question_id, payload.answer)
    except KeyError:
        raise HTTPException(status_code=404, detail="Question not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return row_to_question(row)
