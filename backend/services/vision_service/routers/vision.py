from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.vision_service.repository import (
    list_image_documents,
    read_document,
    status,
)
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory
from shared.ocr import OcrError
from shared.schemas import ImageRead, ProjectDocument, VisionStatus

# Internal API (M7). Not proxied through the gateway — evidence-service reads
# images directly via shared/ocr.py during extraction. These routes exist to
# inspect what OCR sees, which is the only way to debug a bad nameplate read.
router = APIRouter(prefix="/api", tags=["vision"])


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


@router.get("/vision/status", response_model=VisionStatus)
def get_status() -> VisionStatus:
    return status()


@router.get("/projects/{project_id}/images", response_model=list[ProjectDocument])
def get_images(
    project_id: str, db: Session = Depends(get_db)
) -> list[ProjectDocument]:
    _project(db, project_id)
    return [
        ProjectDocument.model_validate(
            {
                "id": doc.id,
                "filename": doc.filename,
                "type": doc.type,
                "status": doc.status,
                "uploadedAt": doc.uploaded_at,
                "pages": doc.pages,
                "sourceUrl": doc.source_url,
            }
        )
        for doc in list_image_documents(db, project_id)
    ]


@router.post(
    "/projects/{project_id}/images/{document_id}/read", response_model=ImageRead
)
def post_read(
    project_id: str, document_id: str, db: Session = Depends(get_db)
) -> ImageRead:
    project = _project(db, project_id)
    try:
        return read_document(db, project, document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Image not found on this job") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except OcrError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
