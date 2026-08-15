"""
File Service (placeholder).

Owns: uploads, file hashes, storage keys, processing status.
Maps to: context.md → "Services" → File Service.

TODO(Phase 1, see context.md → Build order):
  - Persist the uploaded bytes to object storage (MinIO / S3-compatible).
  - Compute a SHA-256 hash and short-circuit re-processing of duplicates.
  - Publish a FileUploaded event so the Document Intelligence Service can
    pick it up (Phase 2 wires the extraction pipeline).

Right now this only acknowledges the upload so the frontend's create-and-
upload flow completes against a live backend.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/api/projects", tags=["files"])


@router.post("/{project_id}/files")
async def upload_file(project_id: str, file: UploadFile) -> dict:
    # TODO: stream `file` to object storage instead of discarding it.
    document_id = f"doc-{uuid.uuid4().hex[:8]}"
    return {
        "documentId": document_id,
        "status": "processing",
        "filename": file.filename,
    }
