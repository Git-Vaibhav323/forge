from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import DocumentRow, ProjectRow
from shared.ocr import is_enabled, provider_name, read_image_text
from shared.schemas import ImageRead, VisionStatus
from shared.utils import IMAGE_DOC_TYPES


def _read_bytes(storage_key: str) -> bytes:
    # Imported lazily so vision-service does not pull object-storage config at
    # import time, and so tests can monkeypatch it. Same shape as
    # evidence_service.repository._read_pdf_bytes.
    from services.file_service.storage import get_object

    return get_object(storage_key)


def status() -> VisionStatus:
    return VisionStatus.model_validate(
        {
            "provider": provider_name(),
            "enabled": is_enabled(),
            "imageTypes": sorted(IMAGE_DOC_TYPES),
        }
    )


def list_image_documents(db: Session, project_id: str) -> list[DocumentRow]:
    return list(
        db.scalars(
            select(DocumentRow)
            .where(
                DocumentRow.project_id == project_id,
                DocumentRow.type.in_(tuple(IMAGE_DOC_TYPES)),
            )
            .order_by(DocumentRow.uploaded_at.asc())
        ).all()
    )


def read_document(db: Session, project: ProjectRow, document_id: str) -> ImageRead:
    """OCR one stored image and return what it says — without persisting facts.

    Attributes are only ever written by evidence-service, which runs the same
    label→field rules over this text. Keeping that one writer is what stops a
    photo from taking a different path onto the record than a datasheet does.
    """
    document = db.get(DocumentRow, document_id)
    if document is None or document.project_id != project.id:
        raise KeyError(document_id)
    if document.type not in IMAGE_DOC_TYPES:
        raise ValueError(f"Document {document_id} is not an image ({document.type})")

    if not is_enabled():
        return ImageRead.model_validate(
            {
                "documentId": document.id,
                "filename": document.filename,
                "provider": provider_name(),
                "pages": [],
                "note": (
                    "OCR is off (OCR_PROVIDER=off). The image is stored and "
                    "listed but nothing has read it — no facts are inferred."
                ),
            }
        )

    pages = read_image_text(_read_bytes(document.storage_key), filename=document.filename)
    return ImageRead.model_validate(
        {
            "documentId": document.id,
            "filename": document.filename,
            "provider": provider_name(),
            "pages": pages,
            "note": (
                "Read from the image. Values sourced only from a photo land as "
                "`unverified` until a second source agrees."
                if pages
                else "No text could be read from this image."
            ),
        }
    )
