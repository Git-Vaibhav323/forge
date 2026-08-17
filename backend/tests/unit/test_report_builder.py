from __future__ import annotations

from datetime import datetime, timezone

from shared.output_render import RenderContext, RenderField, render
from shared.report_builder import build_report_narrative

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def test_replacement_narrative_cites_part_and_driver():
    ctx = RenderContext(
        project_id="prj-1",
        project_name="Gate valve swap",
        goal="replacement_recommendation",
        category="valve",
        generated_at=NOW,
        established=[
            RenderField(
                name="maximum_pressure",
                value="285",
                unit="PSI",
                status="verified",
                confidence=1.0,
                citations=("datasheet.pdf, p.3",),
            )
        ],
        withheld=[
            RenderField(
                name="model",
                value="",
                unit=None,
                status="missing",
                confidence=0.0,
            )
        ],
    )
    narrative = build_report_narrative(ctx)
    assert "Gate valve swap" in narrative.executive_summary
    assert any("Installed asset" in section.title for section in narrative.sections)
    assert any("Gaps blocking" in section.title for section in narrative.sections)


def test_render_includes_executive_summary_and_data_record():
    ctx = RenderContext(
        project_id="prj-1",
        project_name="Gate valve datasheet",
        goal="product_datasheet",
        category="valve",
        generated_at=NOW,
        established=[
            RenderField(
                name="maximum_pressure",
                value="285",
                unit="PSI",
                status="verified",
                confidence=1.0,
                citations=("datasheet.pdf, p.3",),
            )
        ],
    )
    body = render(ctx)
    assert "# Product datasheet" in body
    assert "## Executive summary" in body
    assert "## Data record" in body
    assert "### Established" in body
    assert "285" in body
