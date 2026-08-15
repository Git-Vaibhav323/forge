"""
Completeness + Question Service (placeholder).

Owns: detecting missing/blocking fields and asking the single highest-value
next question, then recording the answer.
Maps to: context.md → "Services" → Completeness Service + Question Service.

TODO(Phase 1, see context.md → Build order):
  - Load the goal- and category-specific required-field schema.
  - Classify each field (known / derived / missing / conflicting / …).
  - Score candidate questions by impact ÷ effort and return the top one.
  - On answer, validate it, update the project model, and re-run the check.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import AnswerInput, Question

router = APIRouter(prefix="/api/projects", tags=["questions"])


@router.get("/{project_id}/questions", response_model=list[Question])
def list_questions(project_id: str) -> list[Question]:
    # TODO: return the open question plus answered history for this project.
    return []


@router.post("/{project_id}/questions/{question_id}/answer", response_model=Question)
def answer_question(
    project_id: str, question_id: str, payload: AnswerInput
) -> Question:
    # TODO: persist the answer, validate it, and trigger a completeness re-check.
    raise HTTPException(
        status_code=501,
        detail="Question answering not implemented — see backend/app/routers/questions.py",
    )
