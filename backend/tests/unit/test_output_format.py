from __future__ import annotations

from datetime import datetime, timezone

from shared.output_format import (
    content_type_for_goal,
    format_for_goal,
    output_filename,
    render_artifact,
)
from shared.output_render import RenderContext, RenderField


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def test_format_for_goal_picks_pdf_or_csv():
    assert format_for_goal("product_datasheet") == "pdf"
    assert format_for_goal("replacement_recommendation") == "pdf"
    assert format_for_goal("bom_generation") == "csv"
    assert format_for_goal("technical_quotation") == "csv"


def test_content_type_matches_format():
    assert content_type_for_goal("product_datasheet") == "application/pdf"
    assert content_type_for_goal("bom_generation") == "text/csv; charset=utf-8"


def test_render_artifact_pdf_magic():
    context = RenderContext(
        project_id="prj-1",
        project_name="Sample job",
        goal="product_datasheet",
        category="other",
        generated_at=NOW,
        established=[
            RenderField(
                name="model",
                value="ABC-100",
                unit=None,
                status="verified",
                confidence=0.95,
                citations=("datasheet.pdf",),
            )
        ],
    )
    body, filename, content_type = render_artifact(context)
    assert filename == "product_datasheet_prj-1.pdf"
    assert content_type == "application/pdf"
    assert body.startswith(b"%PDF")


def test_render_artifact_csv_for_bom_goal():
    context = RenderContext(
        project_id="prj-2",
        project_name="BOM job",
        goal="bom_generation",
        category="kit",
        generated_at=NOW,
    )
    body, filename, content_type = render_artifact(context)
    assert filename == "bom_generation_prj-2.csv"
    assert content_type == "text/csv; charset=utf-8"
    assert b"job_id" in body
