from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.project_service.config import settings
from services.project_service.repository import create_project as create_project_row
from services.project_service.repository import get_project as get_project_row
from services.project_service.repository import list_projects as list_project_rows
from shared.db.session import get_session_factory
from shared.schemas import Project, ProjectCreateInput

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[Project])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list_project_rows(db)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = get_project_row(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreateInput, db: Session = Depends(get_db)) -> Project:
    return create_project_row(db, payload)
