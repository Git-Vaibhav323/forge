from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.evidence_service.repository import list_attributes, run_extraction
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory
from shared.schemas import Attribute

router = APIRouter(prefix="/api/projects", tags=["attributes"])


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


@router.get("/{project_id}/attributes", response_model=list[Attribute])
def get_attributes(project_id: str, db: Session = Depends(get_db)) -> list[Attribute]:
    _project(db, project_id)
    return list_attributes(db, project_id)


@router.post("/{project_id}/attributes/extract", response_model=list[Attribute])
def extract_attributes(project_id: str, db: Session = Depends(get_db)) -> list[Attribute]:
    project = _project(db, project_id)
    return run_extraction(db, project)
