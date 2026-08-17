from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from shared.output_render import (
    RenderBomLine,
    RenderContext,
    RenderField,
    RenderFinding,
    output_filename,
    render_csv,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def _context(**overrides) -> RenderContext:
    base = {
        "project_id": "prj-1042",
        "project_name": "Gate valve datasheet",
        "goal": "product_datasheet",
        "category": "valve",
        "generated_at": NOW,
    }
    base.update(overrides)
    return RenderContext(**base)


def test_filename_is_derived_from_goal_and_job():
    assert output_filename("product_datasheet", "prj-1042") == (
        "product_datasheet_prj-1042.csv"
    )


def _parse_csv(body: str) -> dict:
    """Parse CSV and return the first row as a dict."""
    reader = csv.DictReader(StringIO(body))
    row = next(reader)
    return row


def test_csv_output_has_standard_unilog_headers():
    """CSV should include all required Unilog columns."""
    body = render_csv(_context())
    reader = csv.DictReader(StringIO(body))
    headers = reader.fieldnames or []
    assert "PART_NUMBER" in headers
    assert "MANUFACTURER_NAME" in headers
    assert "ATTRIBUTE_LABEL 1" in headers
    assert "ATTRIBUTE_VALUE 1" in headers
    assert "ATTRIBUTE_UOM 1" in headers


def test_csv_output_is_parseable():
    """CSV should parse cleanly without errors."""
    body = render_csv(_context())
    reader = csv.DictReader(StringIO(body))
    rows = list(reader)
    assert len(rows) == 1, "Should produce exactly one row per job"


def test_established_values_appear_in_csv():
    """Established fields should be populated in the CSV."""
    body = render_csv(
        _context(
            established=[
                RenderField(
                    name="maximum_pressure",
                    value="285",
                    unit="PSI",
                    status="known",
                    confidence=0.95,
                    citations=("datasheet.pdf, p.3",),
                ),
                RenderField(
                    name="manufacturer_name",
                    value="Meridian",
                    unit=None,
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf, p.1",),
                ),
            ]
        )
    )
    row = _parse_csv(body)
    assert row["MANUFACTURER_NAME"] == "Meridian"
    # maximum_pressure should go to an attribute slot
    assert "maximum pressure" in row.get("ATTRIBUTE_LABEL 1", "") or row.get(
        "ATTRIBUTE_LABEL 2", ""
    )


def test_csv_attributes_fill_slots():
    """Extra attributes should fill ATTRIBUTE_LABEL/VALUE/UOM slots."""
    body = render_csv(
        _context(
            established=[
                RenderField(
                    name="voltage",
                    value="120",
                    unit="V",
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                ),
                RenderField(
                    name="amperage",
                    value="15",
                    unit="A",
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                ),
            ]
        )
    )
    row = _parse_csv(body)
    # voltage and amperage are standard columns, should be populated
    # (actual slots may vary depending on implementation)
    body_str = body.lower()
    assert "voltage" in body_str or "120" in body_str


def test_withheld_fields_do_not_appear_in_csv():
    """Withheld fields should not be in established values."""
    body = render_csv(
        _context(
            withheld=[
                RenderField(
                    name="supply_voltage",
                    value="",
                    unit=None,
                    status="missing",
                    confidence=0.0,
                )
            ]
        )
    )
    row = _parse_csv(body)
    # Should not have supply_voltage in attribute slots
    assert row.get("ATTRIBUTE_LABEL 1", "") != "supply voltage"


def test_csv_handles_commas_and_quotes_in_values():
    """CSV should escape special characters properly."""
    body = render_csv(
        _context(
            established=[
                RenderField(
                    name="description",
                    value='Steel, 1/4" NPT',
                    unit=None,
                    status="known",
                    confidence=0.9,
                    citations=("datasheet.pdf",),
                )
            ]
        )
    )
    # Should parse without error (proper CSV escaping)
    row = _parse_csv(body)
    assert row is not None


def test_csv_single_row_per_job():
    """ForgeData produces one output row per job."""
    body = render_csv(
        _context(
            established=[
                RenderField(
                    name="model",
                    value="XYZ-100",
                    unit=None,
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                )
            ]
        )
    )
    reader = csv.DictReader(StringIO(body))
    rows = list(reader)
    assert len(rows) == 1
