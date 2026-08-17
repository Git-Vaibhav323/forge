"""Render evidence-grounded reports as PDF bytes."""

from __future__ import annotations

from io import BytesIO

from fpdf import FPDF

from shared.output_render import (
    RenderContext,
    STATUS_EXPLANATIONS,
    _label,
    goal_title,
)
from shared.report_builder import build_report_narrative


def _pdf_text(text: str) -> str:
    """Keep PDF output compatible with built-in Latin fonts."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _plain_text(text: str) -> str:
    """Strip lightweight markdown markers used in narrative bullets."""
    return _pdf_text(text.replace("**", "").replace("`", ""))


class _ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)

    def _write_block(self, text: str, *, h: float = 5) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, _pdf_text(text))

    def heading(self, text: str, *, size: int = 14) -> None:
        self.set_font("Helvetica", "B", size)
        self._write_block(text, h=8)
        self.ln(2)

    def paragraph(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self._write_block(text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self._write_block(f"  -  {text}")

    def meta_row(self, label: str, value: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.cell(42, 6, _pdf_text(f"{label}:"))
        self.set_font("Helvetica", "", 10)
        self.cell(self.epw - 42, 6, _pdf_text(value), ln=1)

    def data_table(self, headers: list[str], rows: list[list[str]]) -> None:
        if not rows:
            self.paragraph("-")
            return
        col_count = len(headers)
        col_w = self.epw / col_count
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 9)
        for header in headers:
            self.cell(col_w, 7, _pdf_text(header), border=1)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for row in rows:
            self.set_x(self.l_margin)
            for value in row:
                text = _pdf_text((value or "-").replace("\n", " "))
                if len(text) > 72:
                    text = text[:69] + "..."
                self.cell(col_w, 6, text, border=1)
            self.ln()
        self.ln(3)


def render_pdf(context: RenderContext) -> bytes:
    narrative = build_report_narrative(context)
    pdf = _ReportPDF()
    pdf.add_page()

    pdf.heading(goal_title(context.goal), size=18)
    pdf.set_font("Helvetica", "B", 12)
    pdf._write_block(context.project_name, h=7)
    pdf.ln(4)

    pdf.meta_row("Job", context.project_id)
    pdf.meta_row("Category", context.category or "-")
    pdf.meta_row("Goal", goal_title(context.goal))
    pdf.meta_row("Generated", context.generated_at.strftime("%Y-%m-%d %H:%M UTC"))
    pdf.ln(4)

    pdf.heading("Executive summary", size=13)
    pdf.paragraph(narrative.executive_summary)

    for section in narrative.sections:
        pdf.heading(section.title, size=13)
        for paragraph in section.paragraphs:
            pdf.paragraph(paragraph)
        for item in section.bullets:
            pdf.bullet(_plain_text(item))
        pdf.ln(2)

    if context.recommendation_summary or context.recommendations:
        pdf.heading("Engineering analysis", size=13)
        if context.recommendation_summary:
            pdf.paragraph(context.recommendation_summary)
        if context.recommendations:
            pdf.data_table(
                ["Area", "Current state", "Recommended action", "Priority", "Basis"],
                [
                    [
                        item.area,
                        item.current_state,
                        item.suggested_change,
                        item.priority,
                        item.rationale,
                    ]
                    for item in context.recommendations
                ],
            )

    pdf.heading("Data record", size=13)
    pdf.paragraph(
        "Structured tables below mirror the sourced record. Values without a "
        "citation appear only under Not established."
    )

    pdf.heading("Established", size=11)
    if context.established:
        pdf.data_table(
            ["Field", "Value", "Confidence", "Source"],
            [
                [
                    _label(item.name),
                    item.display_value(),
                    f"{item.confidence:.0%}",
                    "; ".join(item.citations) if item.citations else "-",
                ]
                for item in context.established
            ],
        )
    else:
        pdf.paragraph("Nothing on this job has a source yet.")

    pdf.heading("Not established", size=11)
    if context.withheld:
        pdf.paragraph(
            "These fields were left out rather than filled in. "
            "Absence here is deliberate."
        )
        pdf.data_table(
            ["Field", "Status", "Why"],
            [
                [
                    _label(item.name),
                    item.status,
                    STATUS_EXPLANATIONS.get(item.status, "Not available."),
                ]
                for item in context.withheld
            ],
        )
    else:
        pdf.paragraph("Every required field on this job is sourced.")

    if context.bom_lines:
        pdf.heading("Bill of materials", size=13)
        pdf.data_table(
            ["#", "Item", "Qty", "Status"],
            [
                [
                    str(line.position),
                    line.component,
                    line.quantity or "-",
                    line.status,
                ]
                for line in context.bom_lines
            ],
        )

    if context.findings:
        pdf.heading("Compatibility", size=13)
        pdf.data_table(
            ["Check", "Required", "Rated", "Result"],
            [
                [
                    _label(finding.rule),
                    finding.required_value or "-",
                    finding.rated_value or "-",
                    finding.status,
                ]
                for finding in context.findings
            ],
        )

    if context.qa_notes:
        pdf.heading("QA notes", size=13)
        for note in context.qa_notes:
            pdf.bullet(note)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf._write_block(
        "Every value above is quoted from a source on this job. Fields without a "
        "source are listed as gaps, never inferred.",
        h=5,
    )

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
