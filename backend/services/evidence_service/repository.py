from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from services.evidence_service.extraction import (
    AttributeDraft,
    Hit,
    extract_pages_from_pdf,
    merge_hits,
    parse_page,
)
from shared.catalog_sync import sync_catalog_evaluation
from shared.catalog_parser import CatalogPart, parse_catalog_csv
from shared.evidence_fields import extraction_targets
from shared.question_engine import build_job_context, list_question_rows as list_q_rows
from shared.record_sync import apply_user_answers_to_attributes
from shared.relationship_sync import resolve_relationships
from shared.review_sync import sync_reviews
from shared.html_text import html_to_text
from shared.ocr import is_enabled as ocr_enabled, read_image_text
from shared.utils import IMAGE_DOC_TYPES
from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    DocumentRow,
    ProjectRow,
)
from shared.schemas import Attribute

TEXT_DOC_TYPES = {"pdf", "document", "web", "html", "webpage"}
# Images join the same pipeline via OCR (M7); everything downstream — conflict
# detection, review holds, compatibility — is unchanged.
READABLE_DOC_TYPES = TEXT_DOC_TYPES | set(IMAGE_DOC_TYPES)


def _attr_id() -> str:
    return f"attr-{uuid.uuid4().hex[:12]}"


def _ev_id() -> str:
    return f"ev-{uuid.uuid4().hex[:12]}"


def row_to_attribute(row: AttributeRow, evidence: list[AttributeEvidenceRow]) -> Attribute:
    return Attribute.model_validate(
        {
            "id": row.id,
            "productId": row.project_id,
            "name": row.name,
            "rawValue": row.raw_value,
            "normalizedValue": row.normalized_value,
            "unit": row.unit,
            "confidence": row.confidence,
            "status": row.status,
            "riskLevel": row.risk_level,
            "updatedAt": row.updated_at,
            "evidence": [
                {
                    "id": ev.id,
                    "documentId": ev.document_id,
                    "documentName": ev.document_name,
                    "documentType": ev.document_type,
                    "page": ev.page,
                    "quote": ev.quote,
                }
                for ev in evidence
            ],
        }
    )


def _read_attributes(db: Session, project_id: str) -> list[Attribute]:
    rows = list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project_id)
            .options(selectinload(AttributeRow.evidence_rows))
            .order_by(AttributeRow.name.asc())
        ).all()
    )
    return [row_to_attribute(row, list(row.evidence_rows)) for row in rows]


def list_attributes(db: Session, project_id: str) -> list[Attribute]:
    """Return persisted attributes for a job.

    This is a read-only view. Question answers are promoted to verified
    attributes on write paths such as answer submission and extraction
    (``apply_user_answers_to_attributes``), not during this GET.
    """
    if db.get(ProjectRow, project_id) is None:
        return []
    return _read_attributes(db, project_id)


def _read_pdf_bytes(storage_key: str) -> bytes:
    # Imported lazily so evidence-service does not pull object-storage config
    # (or boto3) at import time, and so tests can monkeypatch it.
    from services.file_service.storage import get_object

    return get_object(storage_key)


def _pages_from_bytes(data: bytes, doc_type: str, filename: str = "") -> list[str]:
    if doc_type in IMAGE_DOC_TYPES:
        return read_image_text(data, filename=filename)
    if doc_type in {"web", "html", "webpage"}:
        raw = data.decode("utf-8", errors="replace")
        text = html_to_text(raw) if "<" in raw[:200].lower() or "</" in raw else raw
        return [text]
    return extract_pages_from_pdf(data)


def _collect_hits(db: Session, project_id: str) -> list[Hit]:
    documents = list(
        db.scalars(
            select(DocumentRow)
            .where(DocumentRow.project_id == project_id)
            .order_by(DocumentRow.uploaded_at.asc())
        )
    )
    hits: list[Hit] = []
    for doc in documents:
        if doc.type not in READABLE_DOC_TYPES:
            continue
        if doc.type in IMAGE_DOC_TYPES and not ocr_enabled():
            # Stored, listed, and honestly marked as not yet read. Running
            # without OCR is a supported configuration, not a failure.
            doc.status = "pending"
            continue
        try:
            data = _read_pdf_bytes(doc.storage_key)
            pages = _pages_from_bytes(data, doc.type, doc.filename)
        except Exception:
            # A single unreadable document must not fail the whole extraction.
            doc.status = "failed"
            continue
        display_name = doc.source_url or doc.filename
        for index, text in enumerate(pages, start=1):
            hits.extend(
                parse_page(
                    text=text,
                    page=index,
                    document_id=doc.id,
                    document_name=display_name,
                    document_type=doc.type,
                )
            )
        doc.status = "processed"
        if doc.pages is None:
            doc.pages = len(pages)
    return hits


def _collect_catalog_batches(
    db: Session, project_id: str
) -> list[tuple[DocumentRow, list[CatalogPart]]]:
    documents = list(
        db.scalars(
            select(DocumentRow)
            .where(DocumentRow.project_id == project_id, DocumentRow.type == "catalog")
            .order_by(DocumentRow.uploaded_at.asc())
        )
    )
    batches: list[tuple[DocumentRow, list]] = []
    for doc in documents:
        try:
            data = _read_pdf_bytes(doc.storage_key)
            parts = parse_catalog_csv(data, filename=doc.filename)
        except Exception:
            doc.status = "failed"
            continue
        batches.append((doc, parts))
    return batches


def _persist(db: Session, project: ProjectRow, drafts: list[AttributeDraft]) -> None:
    existing = list(
        db.scalars(select(AttributeRow).where(AttributeRow.project_id == project.id))
    )
    if existing:
        db.execute(
            delete(AttributeEvidenceRow).where(
                AttributeEvidenceRow.attribute_id.in_([r.id for r in existing])
            )
        )
        db.execute(delete(AttributeRow).where(AttributeRow.project_id == project.id))

    now = datetime.now(timezone.utc)
    conflicts = 0
    pending_evidence: list[tuple[str, list[Hit]]] = []
    for draft in drafts:
        if draft.status == "conflicting":
            conflicts += 1
        attr_id = _attr_id()
        db.add(
            AttributeRow(
                id=attr_id,
                project_id=project.id,
                name=draft.name,
                raw_value=draft.raw_value,
                normalized_value=draft.normalized_value,
                unit=draft.unit,
                confidence=draft.confidence,
                status=draft.status,
                risk_level=draft.risk_level,
                updated_at=now,
            )
        )
        pending_evidence.append((attr_id, draft.evidence))

    # Postgres enforces the evidence FK; insert parents first.
    db.flush()

    for attr_id, hits in pending_evidence:
        for hit in hits:
            db.add(
                AttributeEvidenceRow(
                    id=_ev_id(),
                    attribute_id=attr_id,
                    document_id=hit.document_id,
                    document_name=hit.document_name,
                    document_type=hit.document_type,
                    page=hit.page,
                    quote=hit.quote,
                    # Kept per-source so review-service can show who said what.
                    value=hit.raw_value,
                    unit=hit.unit,
                )
            )

    project.conflicts_count = conflicts
    project.updated_at = now


def run_extraction(db: Session, project: ProjectRow) -> list[Attribute]:
    hits = _collect_hits(db, project.id)
    catalog_batches = _collect_catalog_batches(db, project.id)
    q_rows = list_q_rows(db, project.id)
    ctx = build_job_context(db, project, q_rows)
    if hits:
        targets = extraction_targets(ctx, hits)
        drafts = merge_hits(hits, targets)
        _persist(db, project, drafts)
    elif not catalog_batches:
        _persist(db, project, [])

    for doc, parts in catalog_batches:
        sync_catalog_evaluation(db, project, doc, parts)

    apply_user_answers_to_attributes(db, project, q_rows)
    # Variants, compatibility findings and BOM lines all read the record we
    # just rebuilt, so they are re-derived here (M6). Must run BEFORE
    # sync_reviews, which turns failed compatibility rules into holds.
    resolve_relationships(db, project)
    # `_persist` rebuilds every attribute row, which would otherwise wipe out
    # decisions a reviewer already made. Replaying them here (and recomputing
    # conflict/approval counts) is what makes "Re-scan documents" safe. (M5)
    sync_reviews(db, project)
    db.commit()
    return _read_attributes(db, project.id)
