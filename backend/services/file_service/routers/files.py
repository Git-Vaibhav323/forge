"""
File Service — uploads, SHA-256 dedup, MinIO storage (M2).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from services.file_service.config import settings
from services.file_service.repository import DuplicateFileError, store_upload
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
    async with httpx.AsyncClient(timeout=10.0) as client:
        project_response = await client.get(
            f"{settings.project_service_url}/api/projects/{project_id}"
        )
    if project_response.status_code == 404:
        raise HTTPException(status_code=404, detail="Project not found")
    if project_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Project service unavailable")

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
