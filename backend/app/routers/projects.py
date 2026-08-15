"""
Project Service (placeholder).

Owns: project lifecycle, goal, category, status, completion score.
Maps to: context.md → "Services" → Project Service.

This router keeps a real in-memory store (not persisted) so the frontend
can be pointed at a running backend and exercise the create → list → view
flow end to end. Everything else in this file is a TODO:

  TODO: replace `_projects` dict with PostgreSQL (SQLAlchemy/SQLModel).
  TODO: compute completion_score from the Completeness Service instead
        of leaving it static.
  TODO: emit ProjectCreated / ProjectStateUpdated events once an event
        bus (Redis Streams) is introduced — see context.md → Phase 3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.schemas import Project, ProjectCreateInput, ProjectStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])

_projects: dict[str, Project] = {}


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    return list(_projects.values())


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreateInput) -> Project:
    now = datetime.now(timezone.utc)
    project_id = f"prj-{uuid.uuid4().hex[:8]}"
    project = Project(
        id=project_id,
        name=payload.name,
        goal=payload.goal,
        category=payload.category,
        status=ProjectStatus.draft,
        completionScore=0,
        createdAt=now,
        updatedAt=now,
        documents=[],
        blockingFieldsCount=0,
        conflictsCount=0,
        pendingApprovalsCount=0,
    )
    _projects[project_id] = project
    return project
