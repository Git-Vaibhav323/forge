"""Rule-based brand evaluation for Unilog-style catalog rows."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shared.catalog_parser import CatalogPart

COMPLETE = "complete"
PARTIAL = "partial"
BRAND_GAP = "brand_gap"
CONFLICT = "conflict"
MANUFACTURER_ONLY = "manufacturer_only"
NEEDS_REVIEW = "needs_review"

# Leading tokens in Part_Desc that often indicate brand when columns are empty.
_DESC_BRAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b3M\b", re.I), "3M"),
    (re.compile(r"\bDiablo\b", re.I), "Diablo"),
    (re.compile(r"\bMilw(?:aukee)?\b", re.I), "Milwaukee"),
    (re.compile(r"\bTREX\b", re.I), "TREX"),
    (re.compile(r"\bTIMBERTECH\b", re.I), "TIMBERTECH"),
    (re.compile(r"\bJAMESHARDIE\b", re.I), "JAMES HARDIE"),
    (re.compile(r"\bLP SMARTSIDE\b", re.I), "LP SMARTSIDE"),
    (re.compile(r"\bDEWALT\b", re.I), "DEWALT"),
    (re.compile(r"\bMakita\b", re.I), "Makita"),
    (re.compile(r"\bKichler\b", re.I), "Kichler"),
    (re.compile(r"\bSatco\b", re.I), "Satco"),
    (re.compile(r"\bPhilips\b", re.I), "Philips"),
    (re.compile(r"\bFeit\b", re.I), "Feit Electric"),
    (re.compile(r"\bHunter\b", re.I), "Hunter"),
    (re.compile(r"\bGE\b", re.I), "GE"),
    (re.compile(r"\bKitchen Aid\b", re.I), "KitchenAid"),
    (re.compile(r"\bSpeed Queen\b", re.I), "Speed Queen"),
    (re.compile(r"\bVelux\b", re.I), "Velux"),
    (re.compile(r"\bPROVIA\b", re.I), "ProVia"),
    (re.compile(r"\bUnited Window\b", re.I), "United Window & Door"),
)


@dataclass(frozen=True)
class BrandFinding:
    rule: str
    severity: str  # info | warning | error
    field: str
    message: str


@dataclass
class PartEvaluation:
    part: CatalogPart
    status: str
    recommended_brand: str | None = None
    brand_source: str | None = None
    findings: list[BrandFinding] = field(default_factory=list)


@dataclass
class CatalogEvaluationSummary:
    total: int = 0
    complete: int = 0
    partial: int = 0
    brand_gap: int = 0
    conflict: int = 0
    manufacturer_only: int = 0
    needs_review: int = 0


@dataclass
class CatalogEvaluationResult:
    parts: list[PartEvaluation]
    summary: CatalogEvaluationSummary


def _brand_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = re.sub(r"[^a-z0-9]+", "", value.casefold())
    return key or None


def _populated_brands(part: CatalogPart) -> dict[str, str]:
    out: dict[str, str] = {}
    if part.e1_brand_norm:
        out["e1"] = part.e1_brand_norm
    if part.unilog_brand_norm:
        out["unilog"] = part.unilog_brand_norm
    if part.dib_brand_norm:
        out["dib"] = part.dib_brand_norm
    return out


def _brands_agree(brands: dict[str, str]) -> bool:
    keys = {_brand_key(v) for v in brands.values()}
    keys.discard(None)
    return len(keys) <= 1


def _hint_from_description(part: CatalogPart) -> str | None:
    desc = part.part_desc
    if not desc:
        return None
    for pattern, label in _DESC_BRAND_PATTERNS:
        if pattern.search(desc):
            return label
    return None


def evaluate_part(part: CatalogPart) -> PartEvaluation:
    findings: list[BrandFinding] = []
    brands = _populated_brands(part)
    desc_hint = _hint_from_description(part)

    if not part.part_manuf_norm:
        findings.append(
            BrandFinding(
                rule="manufacturer_missing",
                severity="warning",
                field="Part_Manuf",
                message="Manufacturer is missing or placeholder.",
            )
        )

    if not brands:
        if part.part_manuf_norm:
            findings.append(
                BrandFinding(
                    rule="all_brands_empty",
                    severity="warning",
                    field="E1_Brand",
                    message="All brand columns are empty; manufacturer is present.",
                )
            )
        else:
            findings.append(
                BrandFinding(
                    rule="all_brands_empty",
                    severity="error",
                    field="E1_Brand",
                    message="All brand columns are empty.",
                )
            )
        if desc_hint:
            findings.append(
                BrandFinding(
                    rule="desc_brand_hint",
                    severity="info",
                    field="Part_Desc",
                    message=f"Description suggests brand {desc_hint!r}.",
                )
            )
            return PartEvaluation(
                part=part,
                status=MANUFACTURER_ONLY if part.part_manuf_norm else BRAND_GAP,
                recommended_brand=desc_hint,
                brand_source="desc",
                findings=findings,
            )
        status = MANUFACTURER_ONLY if part.part_manuf_norm else BRAND_GAP
        return PartEvaluation(
            part=part,
            status=status,
            findings=findings,
        )

    if len(brands) < 3:
        missing = [name for name in ("e1", "unilog", "dib") if name not in brands]
        field_map = {"e1": "E1_Brand", "unilog": "Unilog_Brand", "dib": "DIB_Brand"}
        findings.append(
            BrandFinding(
                rule="partial_brand_coverage",
                severity="warning",
                field=field_map.get(missing[0], "E1_Brand"),
                message=(
                    f"Brand present in {', '.join(sorted(brands))} "
                    f"but missing in {', '.join(sorted(missing))}."
                ),
            )
        )

    if not _brands_agree(brands):
        values = ", ".join(f"{k}={v!r}" for k, v in brands.items())
        findings.append(
            BrandFinding(
                rule="cross_column_conflict",
                severity="error",
                field="E1_Brand",
                message=f"Brand columns disagree: {values}.",
            )
        )
        return PartEvaluation(
            part=part,
            status=CONFLICT,
            findings=findings,
        )

    # All populated brands agree.
    recommended = next(iter(brands.values()))
    source = next(iter(brands.keys()))

    if desc_hint and _brand_key(desc_hint) != _brand_key(recommended):
        findings.append(
            BrandFinding(
                rule="desc_brand_mismatch",
                severity="warning",
                field="Part_Desc",
                message=(
                    f"Description suggests {desc_hint!r} but catalog brand is {recommended!r}."
                ),
            )
        )
        return PartEvaluation(
            part=part,
            status=NEEDS_REVIEW,
            recommended_brand=recommended,
            brand_source=source,
            findings=findings,
        )

    if len(brands) == 3:
        findings.append(
            BrandFinding(
                rule="brands_complete",
                severity="info",
                field="E1_Brand",
                message=f"All brand columns agree on {recommended!r}.",
            )
        )
        return PartEvaluation(
            part=part,
            status=COMPLETE,
            recommended_brand=recommended,
            brand_source=source,
            findings=findings,
        )

    # One or two channels populated and aligned.
    if desc_hint and _brand_key(desc_hint) == _brand_key(recommended):
        findings.append(
            BrandFinding(
                rule="desc_brand_confirms",
                severity="info",
                field="Part_Desc",
                message=f"Description confirms brand {recommended!r}.",
            )
        )

    return PartEvaluation(
        part=part,
        status=PARTIAL,
        recommended_brand=recommended,
        brand_source=source,
        findings=findings,
    )


def evaluate_catalog(parts: list[CatalogPart]) -> CatalogEvaluationResult:
    evaluations = [evaluate_part(part) for part in parts]
    summary = CatalogEvaluationSummary(total=len(evaluations))
    for ev in evaluations:
        match ev.status:
            case "complete":
                summary.complete += 1
            case "partial":
                summary.partial += 1
            case "brand_gap":
                summary.brand_gap += 1
            case "conflict":
                summary.conflict += 1
            case "manufacturer_only":
                summary.manufacturer_only += 1
            case "needs_review":
                summary.needs_review += 1
    return CatalogEvaluationResult(parts=evaluations, summary=summary)
