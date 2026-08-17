from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.relationship_service.repository import read_view, resolve
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory
from shared.schemas import RelationshipView

# Internal API (M6). Not proxied through the gateway yet — generation-service
# (M8) is the intended caller. See plan.md → "M6 — relationship-service".
router = APIRouter(prefix="/api/projects", tags=["relationships"])


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


@router.get("/{project_id}/relationships", response_model=RelationshipView)
def get_relationships(
    project_id: str, db: Session = Depends(get_db)
) -> RelationshipView:
    _project(db, project_id)
    return read_view(db, project_id)


@router.post("/{project_id}/relationships/resolve", response_model=RelationshipView)
def post_resolve(project_id: str, db: Session = Depends(get_db)) -> RelationshipView:
    project = _project(db, project_id)
    return resolve(db, project)
