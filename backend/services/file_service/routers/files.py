"""
File Service — uploads, SHA-256 dedup, S3-compatible storage (M2).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from services.file_service.repository import DuplicateFileError, store_upload
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory

router = APIRouter(prefix="/api/projects", tags=["files"])

UploadIntent = Literal["reupload", "replace"]


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@router.post("/{project_id}/files")
async def upload_file(
    project_id: str,
    file: UploadFile,
    intent: UploadIntent | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(ProjectRow, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        row, _ = store_upload(
            db,
            project_id=project_id,
            filename=file.filename or "upload.bin",
            content=content,
            content_type=file.content_type,
            intent=intent,
        )
    except DuplicateFileError as exc:
        existing = exc.existing
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_file",
                "message": (
                    f'"{existing.filename}" is already on this job (identical content). '
                    "What are you looking for differently this time? "
                    "Use intent=reupload to keep another copy, or intent=replace to swap the stored file."
                ),
                "existingDocumentId": existing.id,
                "existingFilename": existing.filename,
                "contentHash": existing.content_hash,
            },
        ) from exc

    return {
        "documentId": row.id,
        "status": row.status,
        "filename": row.filename,
    }
