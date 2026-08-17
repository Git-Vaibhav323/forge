"""Read citeable text from uploaded documents for solution generation.

Prefers evidence quotes already in the database (no S3 round-trip). Falls back
to PDF text extraction / OCR only when excerpts are thin.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.evidence_service.extraction import extract_pages_from_pdf
from shared.db.models import AttributeEvidenceRow, AttributeRow, DocumentRow
from shared.html_text import html_to_text
from shared.ocr import is_enabled as ocr_enabled, read_image_text
from shared.record_sync import USER_ANSWER_DOC_ID
from shared.utils import IMAGE_DOC_TYPES

TEXT_DOC_TYPES = {"pdf", "document", "web", "html", "webpage"}
READABLE_DOC_TYPES = TEXT_DOC_TYPES | set(IMAGE_DOC_TYPES)

MAX_TOTAL_CHARS = 12_000
MAX_PAGE_CHARS = 2_000
MIN_EVIDENCE_CHARS = 1500
MAX_S3_DOCS = 2


@dataclass(frozen=True)
class DocumentExcerpt:
    document_id: str
    document_name: str
    page: int
    text: str


def _read_object(storage_key: str) -> bytes:
    from services.file_service.storage import get_object

    return get_object(storage_key)


def _pages_from_bytes(data: bytes, doc_type: str, filename: str) -> list[str]:
    if doc_type in IMAGE_DOC_TYPES:
        return read_image_text(data, filename=filename)

    if doc_type in {"web", "html", "webpage"}:
        raw = data.decode("utf-8", errors="replace")
        text = html_to_text(raw) if "<" in raw[:200].lower() or "</" in raw else raw
        return [text] if text.strip() else []

    if doc_type == "pdf":
        pages = extract_pages_from_pdf(data)
        if any(page.strip() for page in pages):
            return pages
        if ocr_enabled():
            return read_image_text(data, filename=filename or "document.pdf")
        return pages

    text = data.decode("utf-8", errors="replace")
    return [text] if text.strip() else []


def _trim(text: str, limit: int = MAX_PAGE_CHARS) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _char_total(excerpts: list[DocumentExcerpt]) -> int:
    return sum(len(ex.text) for ex in excerpts)


def _append_excerpt(
    excerpts: list[DocumentExcerpt],
    *,
    document_id: str,
    document_name: str,
    page: int,
    text: str,
    total_chars: int,
) -> tuple[int, bool]:
    trimmed = _trim(text)
    if not trimmed:
        return total_chars, False
    if total_chars + len(trimmed) > MAX_TOTAL_CHARS:
        remaining = MAX_TOTAL_CHARS - total_chars
        if remaining <= 0:
            return total_chars, True
        trimmed = _trim(trimmed, remaining)
    excerpts.append(
        DocumentExcerpt(
            document_id=document_id,
            document_name=document_name,
            page=page,
            text=trimmed,
        )
    )
    total_chars += len(trimmed)
    return total_chars, total_chars >= MAX_TOTAL_CHARS


def _excerpts_from_evidence(db: Session, project_id: str) -> list[DocumentExcerpt]:
    rows = list(
        db.scalars(
            select(AttributeEvidenceRow)
            .join(AttributeRow, AttributeEvidenceRow.attribute_id == AttributeRow.id)
            .where(
                AttributeRow.project_id == project_id,
                AttributeEvidenceRow.document_id != USER_ANSWER_DOC_ID,
            )
            .order_by(AttributeEvidenceRow.document_name.asc())
        ).all()
    )
    excerpts: list[DocumentExcerpt] = []
    total_chars = 0
    seen: set[tuple[str, int, str]] = set()
    for row in rows:
        quote = (row.quote or "").strip()
        if not quote:
            continue
        key = (row.document_id, row.page or 0, quote[:120])
        if key in seen:
            continue
        seen.add(key)
        total_chars, done = _append_excerpt(
            excerpts,
            document_id=row.document_id,
            document_name=row.document_name,
            page=row.page or 1,
            text=quote,
            total_chars=total_chars,
        )
        if done:
            break
    return excerpts


def _excerpts_from_storage(
    db: Session, project_id: str, *, max_docs: int
) -> list[DocumentExcerpt]:
    documents = list(
        db.scalars(
            select(DocumentRow)
            .where(DocumentRow.project_id == project_id)
            .order_by(DocumentRow.uploaded_at.asc())
            .limit(max_docs)
        ).all()
    )

    excerpts: list[DocumentExcerpt] = []
    total_chars = 0

    for doc in documents:
        if doc.type not in READABLE_DOC_TYPES:
            continue
        if doc.type in IMAGE_DOC_TYPES and not ocr_enabled():
            continue
        try:
            data = _read_object(doc.storage_key)
            pages = _pages_from_bytes(data, doc.type, doc.filename)
        except Exception:
            continue

        display_name = doc.source_url or doc.filename
        for index, page_text in enumerate(pages, start=1):
            total_chars, done = _append_excerpt(
                excerpts,
                document_id=doc.id,
                document_name=display_name,
                page=index,
                text=page_text,
                total_chars=total_chars,
            )
            if done:
                return excerpts

    return excerpts


def collect_document_excerpts(db: Session, project_id: str) -> list[DocumentExcerpt]:
    """Return page-level excerpts, preferring cached evidence quotes over S3."""
    excerpts = _excerpts_from_evidence(db, project_id)
    if _char_total(excerpts) >= MIN_EVIDENCE_CHARS:
        return excerpts
    storage_excerpts = _excerpts_from_storage(db, project_id, max_docs=MAX_S3_DOCS)
    if not storage_excerpts:
        return excerpts

    seen = {(ex.document_id, ex.page, ex.text[:120]) for ex in excerpts}
    total_chars = _char_total(excerpts)
    for ex in storage_excerpts:
        key = (ex.document_id, ex.page, ex.text[:120])
        if key in seen:
            continue
        seen.add(key)
        if total_chars >= MAX_TOTAL_CHARS:
            break
        remaining = MAX_TOTAL_CHARS - total_chars
        text = ex.text if len(ex.text) <= remaining else _trim(ex.text, remaining)
        excerpts.append(
            DocumentExcerpt(
                document_id=ex.document_id,
                document_name=ex.document_name,
                page=ex.page,
                text=text,
            )
        )
        total_chars += len(text)
    return excerpts
