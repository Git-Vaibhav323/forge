from __future__ import annotations

from pathlib import Path

import pytest

from shared.brand_evaluator import (
    BRAND_GAP,
    COMPLETE,
    CONFLICT,
    MANUFACTURER_ONLY,
    PARTIAL,
    evaluate_catalog,
    evaluate_part,
)
from shared.catalog_parser import normalize_brand, normalize_manufacturer, parse_catalog_csv

SEED = Path(__file__).resolve().parents[3] / "seed_data" / "Unihack_ Sample Dataset - Input.csv"


def test_normalize_brand_treats_sentinels_as_missing() -> None:
    assert normalize_brand("-- Unbranded --") is None
    assert normalize_brand("-- No Unilog Brand --") is None
    assert normalize_brand("TREX") == "TREX"


def test_normalize_manufacturer_strips_vendor_code() -> None:
    assert normalize_manufacturer("Freud Inc (2435)") == "Freud Inc"
    assert normalize_manufacturer("-") is None


def test_parse_catalog_csv_reads_seed_file() -> None:
    parts = parse_catalog_csv(SEED.read_bytes(), filename="Unihack.csv")
    assert len(parts) == 1000
    first = parts[0]
    assert first.mfg_part_num == "DCB518ASTS06G"
    assert first.part_manuf_norm == "Freud Inc"
    assert first.e1_brand_norm is None


def test_evaluate_part_detects_brand_gap_with_desc_hint() -> None:
    parts = parse_catalog_csv(SEED.read_bytes())
    row = next(p for p in parts if p.mfg_part_num == "3MABR-7100075678")
    ev = evaluate_part(row)
    assert ev.status in {BRAND_GAP, MANUFACTURER_ONLY}
    assert ev.recommended_brand == "3M"
    assert any(f.rule == "desc_brand_hint" for f in ev.findings)


def test_evaluate_part_detects_complete_trex_row() -> None:
    parts = parse_catalog_csv(SEED.read_bytes())
    row = next(p for p in parts if p.mfg_part_num == "543302126")
    ev = evaluate_part(row)
    assert ev.status == PARTIAL
    assert ev.recommended_brand == "TREX"


def test_evaluate_part_detects_dib_only_partial() -> None:
    parts = parse_catalog_csv(SEED.read_bytes())
    row = next(p for p in parts if p.mfg_part_num == "1700-1PK-BB40")
    ev = evaluate_part(row)
    assert ev.status == PARTIAL
    assert ev.recommended_brand == "3M"
    assert ev.brand_source == "dib"


def test_evaluate_catalog_summarizes_seed_file() -> None:
    parts = parse_catalog_csv(SEED.read_bytes())
    result = evaluate_catalog(parts)
    assert result.summary.total == 1000
    assert result.summary.brand_gap + result.summary.manufacturer_only > 500
    assert result.summary.complete >= 0
    assert result.summary.conflict >= 0


def test_parse_catalog_csv_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        parse_catalog_csv(b"foo,bar\n1,2\n")
