from __future__ import annotations

from datetime import datetime, timezone

from shared.output_render import (
    RenderBomLine,
    RenderContext,
    RenderField,
    RenderFinding,
    output_filename,
    render,
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
        "product_datasheet_prj-1042.md"
    )


def test_header_carries_the_job_identity():
    body = render(_context())
    assert "# Product datasheet" in body
    assert "Gate valve datasheet" in body
    assert "`prj-1042`" in body
    assert "2026-08-17 12:00 UTC" in body


def test_established_values_are_printed_with_their_source():
    body = render(
        _context(
            established=[
                RenderField(
                    name="maximum_pressure",
                    value="285",
                    unit="PSI",
                    status="known",
                    confidence=0.95,
                    citations=("datasheet.pdf, p.3",),
                )
            ]
        )
    )
    assert "maximum pressure" in body
    assert "285 PSI" in body
    assert "datasheet.pdf, p.3" in body
    assert "95%" in body


def test_withheld_fields_are_named_with_a_reason():
    """The section that stops an incomplete document reading as complete."""
    body = render(
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
    assert "## Not established" in body
    assert "supply voltage" in body
    assert "No source states this." in body
    assert "Absence here is deliberate." in body


def test_a_document_with_nothing_sourced_says_so_rather_than_looking_empty():
    body = render(_context())
    assert "Nothing on this job has a source yet" in body


def test_bom_section_appears_only_when_there_are_lines():
    assert "## Bill of materials" not in render(_context())

    body = render(
        _context(
            goal="bom_generation",
            bom_lines=[
                RenderBomLine(
                    position=1,
                    role="primary",
                    component="Meridian MFC-GV-100",
                    quantity="4",
                    status="resolved",
                    reason="Identified from cited sources.",
                )
            ],
        )
    )
    assert "## Bill of materials" in body
    assert "Meridian MFC-GV-100" in body


def test_unresolved_bom_lines_are_called_out_under_the_table():
    body = render(
        _context(
            goal="bom_generation",
            bom_lines=[
                RenderBomLine(
                    position=1,
                    role="specification",
                    component="supply voltage: not established",
                    quantity=None,
                    status="missing",
                    reason="No source states the supply voltage.",
                )
            ],
        )
    )
    assert "could not be resolved and are named above" in body


def test_abstained_compatibility_is_never_presented_as_a_pass():
    body = render(
        _context(
            findings=[
                RenderFinding(
                    rule="chemical_compatibility",
                    status="unknown",
                    required_value="Steam",
                    rated_value=None,
                    reason="Needs a materials statement.",
                )
            ]
        )
    )
    assert "## Compatibility" in body
    assert "`unknown`" in body
    assert "It is not a pass." in body


def test_qa_notes_are_reproduced_on_the_artifact():
    body = render(_context(qa_notes=["1 field could not be established: model."]))
    assert "## QA notes" in body
    assert "1 field could not be established: model." in body


def test_pipes_in_values_cannot_break_the_table():
    body = render(
        _context(
            established=[
                RenderField(
                    name="model",
                    value="A|B",
                    unit=None,
                    status="known",
                    confidence=0.8,
                    citations=("sheet.pdf",),
                )
            ]
        )
    )
    assert "A\\|B" in body


def test_newlines_in_values_cannot_break_the_table():
    body = render(
        _context(
            established=[
                RenderField(
                    name="model",
                    value="A\nB",
                    unit=None,
                    status="known",
                    confidence=0.8,
                    citations=("sheet.pdf",),
                )
            ]
        )
    )
    assert "| model | A B |" in body


def test_footer_states_the_sourcing_rule():
    body = render(_context())
    assert "Fields without a source are listed as gaps, never inferred." in body
