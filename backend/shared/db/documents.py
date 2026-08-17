from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import DocumentRow
from shared.schemas import ProjectDocument


def row_to_document(row: DocumentRow) -> ProjectDocument:
    return ProjectDocument(
        id=row.id,
        filename=row.filename,
        type=row.type,
        status=row.status,
        uploadedAt=row.uploaded_at,
        pages=row.pages,
        sourceUrl=row.source_url,
    )


def list_documents_for_project(db: Session, project_id: str) -> list[ProjectDocument]:
    rows = db.scalars(
        select(DocumentRow)
        .where(DocumentRow.project_id == project_id)
        .order_by(DocumentRow.uploaded_at.desc())
    ).all()
    return [row_to_document(row) for row in rows]


def list_documents_grouped(db: Session, project_ids: list[str]) -> dict[str, list[ProjectDocument]]:
    if not project_ids:
        return {}
    rows = db.scalars(
        select(DocumentRow)
        .where(DocumentRow.project_id.in_(project_ids))
        .order_by(DocumentRow.uploaded_at.desc())
    ).all()
    grouped: dict[str, list[ProjectDocument]] = {pid: [] for pid in project_ids}
    for row in rows:
        grouped.setdefault(row.project_id, []).append(row_to_document(row))
    return grouped


def find_document_by_project_and_hash(
    db: Session, project_id: str, content_hash: str
) -> DocumentRow | None:
    return db.scalar(
        select(DocumentRow).where(
            DocumentRow.project_id == project_id,
            DocumentRow.content_hash == content_hash,
        )
    )
