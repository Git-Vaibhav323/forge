from __future__ import annotations

import re
from pathlib import PurePath


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
