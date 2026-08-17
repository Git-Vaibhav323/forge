"""Choose the primary artifact format per deliverable goal."""

from __future__ import annotations

from typing import Literal

from shared.output_render import RenderContext, render_csv

OutputFormat = Literal["pdf", "csv"]

# Tabular exports — one row per field or BOM line.
CSV_GOALS: frozenset[str] = frozenset(
    {
        "bom_generation",
        "technical_quotation",
    }
)

# Narrative reports — PDF for sharing and archival.
PDF_GOALS: frozenset[str] = frozenset(
    {
        "product_configuration",
        "product_datasheet",
        "installation_package",
        "replacement_recommendation",
        "rfq_response",
    }
)


def format_for_goal(goal: str) -> OutputFormat:
    if goal in CSV_GOALS:
        return "csv"
    return "pdf"


def output_extension(goal: str) -> str:
    return format_for_goal(goal)


def content_type_for_goal(goal: str) -> str:
    if format_for_goal(goal) == "csv":
        return "text/csv; charset=utf-8"
    return "application/pdf"


def output_filename(goal: str, project_id: str) -> str:
    return f"{goal}_{project_id}.{output_extension(goal)}"


def render_artifact(context: RenderContext) -> tuple[bytes, str, str]:
    """Return (body bytes, filename, content type) for the job goal."""
    filename = output_filename(context.goal, context.project_id)
    if format_for_goal(context.goal) == "csv":
        body = render_csv(context).encode("utf-8")
        return body, filename, content_type_for_goal(context.goal)

    from shared.output_pdf import render_pdf

    return render_pdf(context), filename, content_type_for_goal(context.goal)
