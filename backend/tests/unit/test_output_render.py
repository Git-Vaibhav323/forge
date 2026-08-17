from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from shared.output_render import (
    RenderBomLine,
    RenderContext,
    RenderField,
    RenderFinding,
    RenderRecommendation,
    goal_title,
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


def _parse_csv(body: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(body))
    return list(reader)


def test_filename_is_derived_from_goal_and_job():
    assert output_filename("product_datasheet", "prj-1042") == (
        "product_datasheet_prj-1042.pdf"
    )
    assert output_filename("bom_generation", "prj-1042") == (
        "bom_generation_prj-1042.csv"
    )


def test_datasheet_csv_uses_lean_spec_columns():
    body = render_csv(_context())
    headers = csv.DictReader(StringIO(body)).fieldnames or []
    assert headers == [
        "job_id",
        "job_name",
        "category",
        "goal",
        "generated_at",
        "field",
        "value",
        "unit",
        "required",
        "rated",
        "confidence",
        "source",
        "status",
    ]
    assert "MFR URL" not in headers
    assert len(headers) <= 14


def test_datasheet_csv_lists_established_fields():
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
    rows = _parse_csv(body)
    fields = {row["field"]: row for row in rows}
    assert fields["maximum pressure"]["value"] == "285"
    assert fields["maximum pressure"]["unit"] == "PSI"
    assert fields["manufacturer name"]["value"] == "Meridian"


def test_datasheet_csv_lists_withheld_fields():
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
    rows = _parse_csv(body)
    assert len(rows) == 1
    assert rows[0]["field"] == "supply voltage"
    assert rows[0]["value"] == ""
    assert rows[0]["status"] == "missing"


def test_datasheet_csv_handles_commas_and_quotes_in_values():
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
    rows = _parse_csv(body)
    assert rows[0]["value"] == 'Steel, 1/4" NPT'


def test_replacement_csv_is_one_row_per_recommendation():
    body = render_csv(
        _context(
            project_name="NEW TECH STACK",
            goal="replacement_recommendation",
            category="TECHSTACK",
            recommendation_summary=(
                'For "NEW TECH STACK", keep "frontend" as the baseline and apply '
                "2 recommended change(s) driven by: to make frontend more interactive."
            ),
            recommendations=[
                RenderRecommendation(
                    area="User experience",
                    current_state="frontend",
                    suggested_change="Adopt a component-based UI layer with client-side interactivity.",
                    priority="high",
                    rationale="User stated: to make frontend more interactive",
                ),
                RenderRecommendation(
                    area="Frontend delivery",
                    current_state="frontend",
                    suggested_change="Split static markup from dynamic views.",
                    priority="medium",
                    rationale="Incremental rollout",
                ),
            ],
            established=[
                RenderField(
                    name="existing_part_number",
                    value="frontend",
                    unit=None,
                    status="verified",
                    confidence=1.0,
                    citations=("User answer (Questions tab)",),
                ),
                RenderField(
                    name="reason_for_replacement",
                    value="to make frontend more interactive",
                    unit=None,
                    status="verified",
                    confidence=1.0,
                    citations=("User answer (Questions tab)",),
                ),
            ],
        )
    )
    rows = _parse_csv(body)
    assert len(rows) == 2
    assert rows[0]["existing_part"] == "frontend"
    assert rows[0]["job_name"] == "NEW TECH STACK"
    assert "component-based" in rows[0]["suggested_change"]
    assert rows[0]["priority"] == "high"
    assert rows[1]["area"] == "Frontend delivery"


def test_bom_csv_lists_line_items():
    body = render_csv(
        _context(
            goal="bom_generation",
            established=[
                RenderField(
                    name="manufacturer",
                    value="Meridian",
                    unit=None,
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                ),
                RenderField(
                    name="model",
                    value="MFC-GV-100",
                    unit=None,
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                ),
            ],
            bom_lines=[
                RenderBomLine(
                    position=1,
                    role="body",
                    component="Gate valve",
                    quantity="1",
                    status="resolved",
                    reason="",
                )
            ],
        )
    )
    rows = _parse_csv(body)
    assert rows[0]["component"] == "Gate valve"
    assert rows[0]["line"] == "1"


def test_compatibility_findings_appear_in_datasheet_csv():
    body = render_csv(
        _context(
            findings=[
                RenderFinding(
                    rule="pressure_rating",
                    status="pass",
                    required_value="300 PSI",
                    rated_value="285 PSI",
                    reason="Within tolerance",
                )
            ]
        )
    )
    rows = _parse_csv(body)
    assert any("compatibility" in row["field"] for row in rows)
    compatibility = next(row for row in rows if "compatibility" in row["field"])
    assert compatibility["required"] == "300 PSI"
    assert compatibility["rated"] == "285 PSI"
    assert compatibility["value"] == ""
    assert compatibility["unit"] == ""


def test_csv_neutralizes_formula_prefixes():
    body = render_csv(
        _context(
            established=[
                RenderField(
                    name="description",
                    value="=SUM(A1:A2)",
                    unit=None,
                    status="known",
                    confidence=1.0,
                    citations=("datasheet.pdf",),
                )
            ]
        )
    )
    assert "'=SUM(A1:A2)" in body


def test_goal_title_is_human_readable():
    assert goal_title("replacement_recommendation") == "Replacement recommendation"
