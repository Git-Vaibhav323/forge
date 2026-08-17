from __future__ import annotations

import re
from pathlib import PurePath

# Document types that need OCR rather than a text parser (M7). Lives here,
# beside guess_doc_type, so pure modules can use it without importing config.
IMAGE_DOC_TYPES: frozenset[str] = frozenset({"image", "photo", "nameplate", "scan"})


def guess_doc_type(filename: str) -> str:
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext == "pdf":
        return "pdf"
    if ext in {"png", "jpg", "jpeg", "webp"}:
        return "image"
    if ext in {"csv", "xlsx", "xls"}:
        return "catalog"
    if ext in {"html", "htm"}:
        return "web"
    return "document"


def sanitize_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        return "upload.bin"
    name = PurePath(filename.strip()).name
    cleaned = re.sub(r"[^\w.\- ]+", "_", name)
    return cleaned[:255] or "upload.bin"
