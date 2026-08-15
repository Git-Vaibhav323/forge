from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from services.file_service.storage import put_object, remove_object
from shared.db.documents import find_document_by_project_and_hash
from shared.db.models import DocumentRow
from shared.utils import guess_doc_type, sanitize_filename

UploadIntent = Literal["reupload", "replace"]


def generate_document_id() -> str:
    return f"doc-{uuid.uuid4().hex[:8]}"


def build_storage_key(project_id: str, document_id: str, filename: str) -> str:
    return f"{project_id}/{document_id}/{filename}"


def store_upload(
    db: Session,
    *,
    project_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    intent: UploadIntent | None,
) -> tuple[DocumentRow, bool]:
    """Returns (document_row, was_duplicate_resolved)."""
    content_hash = hashlib.sha256(content).hexdigest()
    safe_name = sanitize_filename(filename)
    doc_type = guess_doc_type(safe_name)
    existing = find_document_by_project_and_hash(db, project_id, content_hash)

    if existing and intent is None:
        raise DuplicateFileError(existing)

    if existing and intent == "replace":
        remove_object(existing.storage_key)
        existing.filename = safe_name
        existing.type = doc_type
        existing.status = "processing"
        existing.storage_key = build_storage_key(project_id, existing.id, safe_name)
        existing.uploaded_at = datetime.now(timezone.utc)
        put_object(
            existing.storage_key,
            content,
            content_type or "application/octet-stream",
        )
        db.commit()
        db.refresh(existing)
        return existing, True

    document_id = generate_document_id()
    storage_key = build_storage_key(project_id, document_id, safe_name)
    put_object(storage_key, content, content_type or "application/octet-stream")

    row = DocumentRow(
        id=document_id,
        project_id=project_id,
        filename=safe_name,
        type=doc_type,
        status="processing",
        content_hash=content_hash,
        storage_key=storage_key,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, existing is not None


class DuplicateFileError(Exception):
    def __init__(self, existing: DocumentRow) -> None:
        self.existing = existing
