"""Deterministic, key-free extraction for M4.

Reads datasheet text and maps labelled specs to canonical attributes, each
carrying the page + quoted line it came from. No LLM, no embeddings, no API
key. The wire shape (Attribute + Evidence) is identical to what a semantic
RAG pipeline would emit, so that can replace `parse_page` later without
touching the frontend or the database.

Rule: never invent. A field with no supporting quote is reported `missing`.
Two sources that disagree become `conflicting`, not a silent merge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field

from shared.utils import IMAGE_DOC_TYPES


@dataclass(frozen=True)
class FieldSpec:
    name: str
    # Regex (case-insensitive) with a named group `val`, optional `unit`.
    pattern: str
    unit: str | None = None
    risk: str = "low"


# Order matters only for display. Each pattern is anchored on the datasheet
# label so a bare number elsewhere on the page is never captured.
FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name="manufacturer",
        pattern=r"(?P<val>[A-Za-z][\w .,&/-]+?)\s*[—\-]\s*Page\s*\d+",
        risk="low",
    ),
    FieldSpec(
        name="model",
        pattern=r"Model\s*[:#]?\s*(?P<val>[A-Za-z0-9][A-Za-z0-9\-\/\.]+)",
        risk="medium",
    ),
    FieldSpec(
        name="nominal_size",
        pattern=r"Nominal\s*Size\s*[:]?\s*(?P<val>[0-9][0-9./\"\s-]*(?:mm|in|inch|\")?)",
        risk="low",
    ),
    FieldSpec(
        name="body_material",
        pattern=r"Body\s*Material\s*[:]?\s*(?P<val>[A-Za-z0-9][A-Za-z0-9 .\-]+)",
        risk="low",
    ),
    FieldSpec(
        name="connection_standard",
        pattern=r"End\s*Connection\s*[:]?\s*(?P<val>[A-Za-z0-9][A-Za-z0-9 ()\-\.]+)",
        risk="high",
    ),
    FieldSpec(
        name="maximum_pressure",
        pattern=(
            r"(?:Max(?:imum)?\s*(?:Working\s*)?Pressure)\s*(?:Rating)?\s*[:]?\s*"
            r"(?P<val>[0-9][0-9.,]*)\s*(?P<unit>PSI|psi|bar|kPa|MPa)?"
        ),
        unit="PSI",
        risk="critical",
    ),
    FieldSpec(
        name="max_temperature",
        pattern=(
            r"(?:Max(?:imum)?\s*Temperature(?:\s*Rating)?)\s*[:]?\s*"
            r"(?P<val>-?[0-9][0-9.,]*)\s*(?P<unit>°?\s*[CF])?"
        ),
        unit="°C",
        risk="high",
    ),
    FieldSpec(
        name="supply_voltage",
        pattern=(
            r"(?:Supply\s*Voltage|Coil\s*Voltage|Voltage)\s*[:]?\s*"
            r"(?P<val>[0-9][0-9.,]*)\s*(?P<unit>V(?:AC|DC)?|volts?)?"
        ),
        unit="V",
        risk="critical",
    ),
    FieldSpec(
        name="standard",
        pattern=r"Standard\s*[:]?\s*(?P<val>(?:API|ASME|ANSI|ISO|EN|DIN)\s*[A-Za-z0-9.\-]+)",
        risk="low",
    ),
)

_COMPILED = [(spec, re.compile(spec.pattern, re.IGNORECASE)) for spec in FIELD_SPECS]

from shared.risk import HIGH_RISK_FIELDS as HIGH_RISK


@dataclass
class Hit:
    field: str
    raw_value: str
    normalized: str
    unit: str | None
    page: int
    quote: str
    document_id: str
    document_name: str
    document_type: str | None


@dataclass
class AttributeDraft:
    name: str
    raw_value: str
    normalized_value: str | None
    unit: str | None
    confidence: float
    status: str
    risk_level: str
    evidence: list[Hit] = dataclass_field(default_factory=list)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().strip(".,;")


def _normalize(field: str, raw: str) -> str:
    text = _clean(raw).lower()
    number = re.search(r"-?[0-9][0-9.,]*", text)
    if number:
        return number.group(0).replace(",", "")
    return text


def parse_page(
    *,
    text: str,
    page: int,
    document_id: str,
    document_name: str,
    document_type: str | None,
) -> list[Hit]:
    """Pull every recognised spec from one page of text."""
    hits: list[Hit] = []
    for spec, regex in _COMPILED:
        match = regex.search(text)
        if not match:
            continue
        raw = _clean(match.group("val"))
        if not raw:
            continue
        unit = None
        if "unit" in match.groupdict() and match.group("unit"):
            unit = _clean(match.group("unit"))
        unit = unit or spec.unit
        quote = _clean(match.group(0))
        hits.append(
            Hit(
                field=spec.name,
                raw_value=raw,
                normalized=_normalize(spec.name, raw),
                unit=unit,
                page=page,
                quote=quote,
                document_id=document_id,
                document_name=document_name,
                document_type=document_type,
            )
        )
    return hits


def merge_hits(hits: list[Hit], required_fields: list[str]) -> list[AttributeDraft]:
    """Group hits per field, resolve agreement vs conflict, add missing fields."""
    by_field: dict[str, list[Hit]] = {}
    for hit in hits:
        by_field.setdefault(hit.field, []).append(hit)

    drafts: list[AttributeDraft] = []
    seen: set[str] = set()

    for field_name, field_hits in by_field.items():
        seen.add(field_name)
        distinct = {h.normalized for h in field_hits}
        base_risk = next(
            (s.risk for s in FIELD_SPECS if s.name == field_name),
            "high" if field_name in HIGH_RISK else "low",
        )
        first = field_hits[0]

        if len(distinct) > 1:
            drafts.append(
                AttributeDraft(
                    name=field_name,
                    raw_value=" / ".join(sorted({h.raw_value for h in field_hits})),
                    normalized_value=None,
                    unit=first.unit,
                    confidence=0.5,
                    status="conflicting",
                    risk_level="critical" if base_risk == "critical" else "high",
                    evidence=field_hits,
                )
            )
        else:
            # A nameplate photo on its own is a reading, not an established
            # fact — OCR misreads characters and nobody has confirmed it. It
            # lands as `unverified`, which makes safety-critical fields a
            # review hold. A photo that AGREES with a datasheet is a second
            # source and lifts the field to `known` like any other agreement.
            image_only = all(
                (hit.document_type or "") in IMAGE_DOC_TYPES for hit in field_hits
            )
            if image_only:
                confidence, status = 0.6, "unverified"
            else:
                confidence = 0.95 if len(field_hits) > 1 else 0.82
                status = "known"
            drafts.append(
                AttributeDraft(
                    name=field_name,
                    raw_value=first.raw_value,
                    normalized_value=first.normalized,
                    unit=first.unit,
                    confidence=confidence,
                    status=status,
                    risk_level=base_risk,
                    evidence=field_hits,
                )
            )

    for field_name in required_fields:
        if field_name in seen:
            continue
        drafts.append(
            AttributeDraft(
                name=field_name,
                raw_value="",
                normalized_value=None,
                unit=None,
                confidence=0.0,
                status="missing",
                risk_level="high" if field_name in HIGH_RISK else "low",
                evidence=[],
            )
        )

    return drafts


def extract_pages_from_pdf(data: bytes) -> list[str]:
    """Return page texts. pypdf is imported lazily so the service and tests
    boot even before the dependency is installed."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf is not installed. Run: python -m pip install pypdf"
        ) from exc

    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    return [(page.extract_text() or "") for page in reader.pages]
