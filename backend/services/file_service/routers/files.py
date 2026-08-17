"""
File Service — uploads, SHA-256 dedup, S3-compatible storage (M2),
and web-page ingest as citeable documents.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.file_service.repository import DuplicateFileError, store_upload, store_web_source
from services.file_service.web_fetch import WebFetchError, fetch_web_page, validate_public_http_url
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


class WebSourceInput(BaseModel):
    """Ingest a manufacturer/catalog page as a document.

    Provide `url` alone to fetch (provider from WEB_FETCH_PROVIDER), or also
    pass `html` to skip the network and store a pasted page. Facts still only
    come from quoted extraction — never invented from the URL alone.
    """

    url: str = Field(..., min_length=8, max_length=2048)
    html: Optional[str] = Field(default=None, max_length=2_000_000)


def _duplicate_http(exc: DuplicateFileError) -> HTTPException:
    existing = exc.existing
    return HTTPException(
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
    )


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
        raise _duplicate_http(exc) from exc

    return {
        "documentId": row.id,
        "status": row.status,
        "filename": row.filename,
        "type": row.type,
    }


@router.post("/{project_id}/sources")
def add_web_source(
    project_id: str,
    body: WebSourceInput,
    intent: UploadIntent | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(ProjectRow, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        if body.html and body.html.strip():
            # Pasted HTML: cite the URL the user gave; do not resolve/fetch.
            source_url = validate_public_http_url(body.url, resolve_host=False)
            html = body.html
            canonical = source_url
        else:
            source_url = validate_public_http_url(body.url, resolve_host=True)
            html, canonical = fetch_web_page(source_url)
        row, _ = store_web_source(
            db,
            project_id=project_id,
            source_url=canonical,
            html=html,
            intent=intent,
        )
    except WebFetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except DuplicateFileError as exc:
        raise _duplicate_http(exc) from exc

    return {
        "documentId": row.id,
        "status": row.status,
        "filename": row.filename,
        "type": row.type,
        "sourceUrl": row.source_url,
    }
