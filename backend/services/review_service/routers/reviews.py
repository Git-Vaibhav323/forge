from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.review_service.repository import list_review_items, submit_decision
from shared.db.models import ProjectRow, ReviewItemRow
from shared.db.session import get_session_factory
from shared.schemas import ReviewDecision, ReviewItem

router = APIRouter(prefix="/api", tags=["reviews"])


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


@router.get("/projects/{project_id}/reviews", response_model=list[ReviewItem])
def get_reviews(project_id: str, db: Session = Depends(get_db)) -> list[ReviewItem]:
    project = _project(db, project_id)
    return list_review_items(db, project)


@router.post("/reviews/{review_id}/decision", response_model=ReviewItem)
def post_decision(
    review_id: str,
    payload: ReviewDecision,
    db: Session = Depends(get_db),
) -> ReviewItem:
    # The frontend posts projectId in the body; fall back to the item's own
    # project so the route also works for a direct API caller.
    item = db.get(ReviewItemRow, review_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if payload.project_id and payload.project_id != item.project_id:
        raise HTTPException(status_code=400, detail="projectId does not match review item")

    project = _project(db, item.project_id)
    try:
        return submit_decision(db, project, review_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
