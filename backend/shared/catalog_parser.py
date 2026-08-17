"""Parse distributor catalog CSV rows into normalized part attributes."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

# Canonical column names (case-insensitive match).
INPUT_COLUMNS = (
    "Mfg_Part_Num",
    "Part_Desc",
    "E1_Brand",
    "Unilog_Brand",
    "DIB_Brand",
    "Part_Manuf",
)

# Values that mean "no brand / no manufacturer" in Unilog-style feeds.
BRAND_SENTINELS = frozenset(
    {
        "",
        "-",
        "-- unbranded --",
        "-- no unilog brand --",
        "-- no dib brand --",
        "commodity - unbranded",
    }
)

_MANUF_CODE_RE = re.compile(r"\s*\([^)]+\)\s*$")


@dataclass(frozen=True)
class CatalogPart:
    """Normalized attributes for one catalog row."""

    row_index: int
    mfg_part_num: str
    part_desc: str
    e1_brand: str
    unilog_brand: str
    dib_brand: str
    part_manuf: str
    e1_brand_norm: str | None
    unilog_brand_norm: str | None
    dib_brand_norm: str | None
    part_manuf_norm: str | None


def normalize_brand(raw: str | None) -> str | None:
    """Return a display brand or None when the source value is a placeholder."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.casefold() in BRAND_SENTINELS:
        return None
    return text


def normalize_manufacturer(raw: str | None) -> str | None:
    """Strip vendor codes like ``Freud Inc (2435)`` → ``Freud Inc``."""
    text = (raw or "").strip()
    if not text or text == "-":
        return None
    cleaned = _MANUF_CODE_RE.sub("", text).strip()
    return cleaned or None


def _normalize_header(name: str) -> str:
    return (name or "").strip()


def _row_dict(raw: dict[str, str]) -> dict[str, str]:
    keyed: dict[str, str] = {}
    for key, value in raw.items():
        norm = _normalize_header(key)
        if norm:
            keyed[norm] = (value or "").strip()
    return keyed


def normalize_catalog_row(row_index: int, raw: dict[str, str]) -> CatalogPart | None:
    """Map one CSV dict row to ``CatalogPart``. Returns None when part number missing."""
    data = _row_dict(raw)
    part_num = data.get("Mfg_Part_Num", "").strip()
    if not part_num:
        return None
    return CatalogPart(
        row_index=row_index,
        mfg_part_num=part_num,
        part_desc=data.get("Part_Desc", "").strip(),
        e1_brand=data.get("E1_Brand", "").strip(),
        unilog_brand=data.get("Unilog_Brand", "").strip(),
        dib_brand=data.get("DIB_Brand", "").strip(),
        part_manuf=data.get("Part_Manuf", "").strip(),
        e1_brand_norm=normalize_brand(data.get("E1_Brand")),
        unilog_brand_norm=normalize_brand(data.get("Unilog_Brand")),
        dib_brand_norm=normalize_brand(data.get("DIB_Brand")),
        part_manuf_norm=normalize_manufacturer(data.get("Part_Manuf")),
    )


def parse_catalog_csv(data: bytes, *, filename: str = "") -> list[CatalogPart]:
    """Parse catalog CSV bytes into normalized part rows."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    headers = {_normalize_header(h) for h in reader.fieldnames if h}
    missing = [col for col in INPUT_COLUMNS if col not in headers]
    if missing:
        raise ValueError(
            f"Catalog CSV {filename or 'upload'} is missing required columns: "
            + ", ".join(missing)
        )

    parts: list[CatalogPart] = []
    for row_index, raw in enumerate(reader, start=2):
        part = normalize_catalog_row(row_index, raw)
        if part is not None:
            parts.append(part)
    return parts
