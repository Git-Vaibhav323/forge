"""Render the final artifact (M8). Pure functions — no DB, no network.

Markdown, deliberately. A datasheet built from cited evidence should be
readable as plain text and diffable, and it needs no rendering dependency
(reportlab / python-docx) to exist. Swapping the writer for PDF later touches
this module only — everything above it works in `RenderContext`.

The document always carries two tables:

  * **Established** — values that may be stated, each with the document and
    page it came from; and
  * **Not established** — every field that was withheld, and why.

The second table is the point. A generated datasheet that silently omits the
field it could not source reads as complete when it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime

# Mirrors PROJECT_GOAL_LABELS in lib/types.ts.
GOAL_TITLES: dict[str, str] = {
    "product_configuration": "Product configuration",
    "bom_generation": "Bill of materials",
    "technical_quotation": "Technical quotation",
    "product_datasheet": "Product datasheet",
    "installation_package": "Installation package",
    "replacement_recommendation": "Replacement recommendation",
    "rfq_response": "RFQ response",
}

STATUS_EXPLANATIONS: dict[str, str] = {
    "missing": "No source states this.",
    "conflicting": "Sources disagree; not resolved.",
    "needs_review": "Awaiting a decision.",
    "unverified": "Read from a single source and not confirmed.",
    "not_applicable": "Marked not applicable for this job.",
}


@dataclass(frozen=True)
class RenderField:
    name: str
    value: str
    unit: str | None
    status: str
    confidence: float
    citations: tuple[str, ...] = ()

    def display_value(self) -> str:
        return f"{self.value} {self.unit}".strip() if self.unit else self.value


@dataclass(frozen=True)
class RenderBomLine:
    position: int
    role: str
    component: str
    quantity: str | None
    status: str
    reason: str


@dataclass(frozen=True)
class RenderFinding:
    rule: str
    status: str
    required_value: str | None
    rated_value: str | None
    reason: str


@dataclass
class RenderContext:
    project_id: str
    project_name: str
    goal: str
    category: str
    generated_at: datetime
    established: list[RenderField] = dataclass_field(default_factory=list)
    withheld: list[RenderField] = dataclass_field(default_factory=list)
    bom_lines: list[RenderBomLine] = dataclass_field(default_factory=list)
    findings: list[RenderFinding] = dataclass_field(default_factory=list)
    qa_notes: list[str] = dataclass_field(default_factory=list)


def _cell(text: str | None) -> str:
    """Escape a value so it cannot break out of a markdown table cell."""
    if text is None or text == "":
        return "—"
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _label(field_name: str) -> str:
    return field_name.replace("_", " ")


def goal_title(goal: str) -> str:
    return GOAL_TITLES.get(goal, goal.replace("_", " ").capitalize())


def output_filename(goal: str, project_id: str) -> str:
    return f"{goal}_{project_id}.md"


def render(context: RenderContext) -> str:
    """Build the artifact. Every stated value carries its source."""
    lines: list[str] = []

    lines.append(f"# {goal_title(context.goal)}")
    lines.append("")
    lines.append(f"**{context.project_name}**")
    lines.append("")
    lines.append(f"| | |")
    lines.append("| --- | --- |")
    lines.append(f"| Job | `{context.project_id}` |")
    lines.append(f"| Category | {_cell(context.category)} |")
    lines.append(
        f"| Generated | {context.generated_at.strftime('%Y-%m-%d %H:%M UTC')} |"
    )
    lines.append("")

    # --- Established --------------------------------------------------------
    lines.append("## Established")
    lines.append("")
    if context.established:
        lines.append("| Field | Value | Confidence | Source |")
        lines.append("| --- | --- | --- | --- |")
        for item in context.established:
            citation = "; ".join(item.citations) if item.citations else "—"
            lines.append(
                f"| {_cell(_label(item.name))} | {_cell(item.display_value())} "
                f"| {item.confidence:.0%} | {_cell(citation)} |"
            )
    else:
        lines.append(
            "_Nothing on this job has a source yet, so nothing is stated here._"
        )
    lines.append("")

    # --- Not established ----------------------------------------------------
    lines.append("## Not established")
    lines.append("")
    if context.withheld:
        lines.append(
            "These fields were left out rather than filled in. "
            "Absence here is deliberate."
        )
        lines.append("")
        lines.append("| Field | Status | Why |")
        lines.append("| --- | --- | --- |")
        for item in context.withheld:
            why = STATUS_EXPLANATIONS.get(item.status, "Not available.")
            lines.append(
                f"| {_cell(_label(item.name))} | `{item.status}` | {_cell(why)} |"
            )
    else:
        lines.append("_Every required field on this job is sourced._")
    lines.append("")

    # --- BOM ----------------------------------------------------------------
    if context.bom_lines:
        lines.append("## Bill of materials")
        lines.append("")
        lines.append("| # | Item | Qty | Status |")
        lines.append("| --- | --- | --- | --- |")
        for line in context.bom_lines:
            lines.append(
                f"| {line.position} | {_cell(line.component)} "
                f"| {_cell(line.quantity)} | `{line.status}` |"
            )
        lines.append("")
        gaps = [line for line in context.bom_lines if line.status == "missing"]
        if gaps:
            lines.append(
                f"> {len(gaps)} line(s) could not be resolved and are named above "
                "rather than dropped."
            )
            lines.append("")

    # --- Compatibility ------------------------------------------------------
    if context.findings:
        lines.append("## Compatibility")
        lines.append("")
        lines.append("| Check | Required | Rated | Result |")
        lines.append("| --- | --- | --- | --- |")
        for finding in context.findings:
            lines.append(
                f"| {_cell(_label(finding.rule))} | {_cell(finding.required_value)} "
                f"| {_cell(finding.rated_value)} | `{finding.status}` |"
            )
        lines.append("")
        abstained = [f for f in context.findings if f.status == "unknown"]
        if abstained:
            lines.append(
                "> `unknown` means the check could not be decided from the sources "
                "on this job. It is not a pass."
            )
            lines.append("")

    # --- QA -----------------------------------------------------------------
    if context.qa_notes:
        lines.append("## QA notes")
        lines.append("")
        for note in context.qa_notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Every value above is quoted from a source on this job. Fields without a "
        "source are listed as gaps, never inferred."
    )
    lines.append("")

    return "\n".join(lines)
