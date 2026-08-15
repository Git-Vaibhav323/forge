from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.documents import list_documents_for_project, list_documents_grouped
from shared.db.models import ProjectRow
from shared.schemas import Project, ProjectCreateInput, ProjectGoal, ProjectStatus


def generate_project_id() -> str:
    return f"prj-{uuid.uuid4().hex[:8]}"


def row_to_project(row: ProjectRow, documents=None) -> Project:
    return Project(
        id=row.id,
        name=row.name,
        goal=ProjectGoal(row.goal),
        category=row.category,
        status=ProjectStatus(row.status),
        completionScore=row.completion_score,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
        documents=documents or [],
        blockingFieldsCount=row.blocking_fields_count,
        conflictsCount=row.conflicts_count,
        pendingApprovalsCount=row.pending_approvals_count,
    )


def list_projects(db: Session) -> list[Project]:
    rows = db.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
    if not rows:
        return []
    doc_map = list_documents_grouped(db, [row.id for row in rows])
    return [row_to_project(row, doc_map.get(row.id, [])) for row in rows]


def get_project(db: Session, project_id: str) -> Project | None:
    row = db.get(ProjectRow, project_id)
    if row is None:
        return None
    return row_to_project(row, list_documents_for_project(db, project_id))


def create_project(db: Session, payload: ProjectCreateInput) -> Project:
    now = datetime.now(timezone.utc)
    row = ProjectRow(
        id=generate_project_id(),
        name=payload.name,
        goal=payload.goal.value,
        category=payload.category,
        status=ProjectStatus.draft.value,
        completion_score=0,
        blocking_fields_count=0,
        conflicts_count=0,
        pending_approvals_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row_to_project(row, [])


def project_exists(db: Session, project_id: str) -> bool:
    return db.get(ProjectRow, project_id) is not None
