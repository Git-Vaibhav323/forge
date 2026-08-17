from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from services.file_service.storage import remove_object
from shared.completeness import required_fields, score_answers
from shared.db.documents import list_documents_for_project, list_documents_grouped
from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    BomLineRow,
    CompatibilityFindingRow,
    DocumentRow,
    ProductRelationshipRow,
    ProjectRow,
    QuestionRow,
    ReviewDecisionRow,
    ReviewItemRow,
)
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
    specs = required_fields(payload.goal.value, payload.category)
    completion, blocking = score_answers(specs, {})
    row = ProjectRow(
        id=generate_project_id(),
        name=payload.name,
        goal=payload.goal.value,
        category=payload.category,
        status=ProjectStatus.draft.value,
        completion_score=completion,
        blocking_fields_count=blocking,
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


def delete_project(db: Session, project_id: str) -> bool:
    row = db.get(ProjectRow, project_id)
    if row is None:
        return False

    storage_keys = list(
        db.scalars(select(DocumentRow.storage_key).where(DocumentRow.project_id == project_id))
    )
    # Children are removed explicitly: SQLite (used by the test suite) does not
    # enforce ON DELETE CASCADE unless PRAGMA foreign_keys is on.
    review_ids = list(
        db.scalars(select(ReviewItemRow.id).where(ReviewItemRow.project_id == project_id))
    )
    if review_ids:
        db.execute(
            delete(ReviewDecisionRow).where(ReviewDecisionRow.review_item_id.in_(review_ids))
        )
    db.execute(delete(ReviewItemRow).where(ReviewItemRow.project_id == project_id))

    db.execute(
        delete(ProductRelationshipRow).where(
            ProductRelationshipRow.project_id == project_id
        )
    )
    # Links pointing AT this job would otherwise dangle — no FK covers them.
    db.execute(
        delete(ProductRelationshipRow).where(
            ProductRelationshipRow.related_project_id == project_id
        )
    )
    db.execute(
        delete(CompatibilityFindingRow).where(
            CompatibilityFindingRow.project_id == project_id
        )
    )
    db.execute(delete(BomLineRow).where(BomLineRow.project_id == project_id))

    attribute_ids = list(
        db.scalars(select(AttributeRow.id).where(AttributeRow.project_id == project_id))
    )
    if attribute_ids:
        db.execute(
            delete(AttributeEvidenceRow).where(
                AttributeEvidenceRow.attribute_id.in_(attribute_ids)
            )
        )
    db.execute(delete(AttributeRow).where(AttributeRow.project_id == project_id))

    db.execute(delete(QuestionRow).where(QuestionRow.project_id == project_id))
    db.execute(delete(DocumentRow).where(DocumentRow.project_id == project_id))
    db.delete(row)
    db.commit()

    for key in storage_keys:
        remove_object(key)
    return True
