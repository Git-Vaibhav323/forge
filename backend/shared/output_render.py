"""Render the final artifact (M8). Pure functions — no DB, no network.

Markdown reports carry a goal-specific narrative plus sourced data tables.
CSV helpers remain for structured export and tests.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from io import StringIO

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


@dataclass(frozen=True)
class RenderRecommendation:
    area: str
    current_state: str
    suggested_change: str
    priority: str
    rationale: str


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
    recommendation_summary: str | None = None
    recommendations: list[RenderRecommendation] = dataclass_field(default_factory=list)


def _cell(text: str | None) -> str:
    """Escape a value so it cannot break out of a markdown table cell."""
    if text is None or text == "":
        return "—"
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _label(field_name: str) -> str:
    return field_name.replace("_", " ")


def goal_title(goal: str) -> str:
    return GOAL_TITLES.get(goal, goal.replace("_", " ").capitalize())


def report_filename(goal: str, project_id: str) -> str:
    """Primary download filename for a goal (PDF report or CSV export)."""
    from shared.output_format import output_filename as artifact_filename

    return artifact_filename(goal, project_id)


def output_filename(goal: str, project_id: str) -> str:
    """Alias for artifact filename selection."""
    return report_filename(goal, project_id)


def _render_narrative(narrative) -> list[str]:
    lines: list[str] = []
    lines.append("## Executive summary")
    lines.append("")
    lines.append(narrative.executive_summary)
    lines.append("")

    for section in narrative.sections:
        lines.append(f"## {section.title}")
        lines.append("")
        for paragraph in section.paragraphs:
            lines.append(paragraph)
            lines.append("")
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        if section.bullets:
            lines.append("")

    return lines


def render(context: RenderContext) -> str:
    """Build a detailed markdown report. Every stated value carries its source."""
    from shared.report_builder import build_report_narrative

    lines: list[str] = []
    narrative = build_report_narrative(context)

    lines.append(f"# {goal_title(context.goal)}")
    lines.append("")
    lines.append(f"**{context.project_name}**")
    lines.append("")
    lines.append("| | |")
    lines.append("| --- | --- |")
    lines.append(f"| Job | `{context.project_id}` |")
    lines.append(f"| Category | {_cell(context.category)} |")
    lines.append(f"| Goal | {_cell(goal_title(context.goal))} |")
    lines.append(
        f"| Generated | {context.generated_at.strftime('%Y-%m-%d %H:%M UTC')} |"
    )
    lines.append("")

    lines.extend(_render_narrative(narrative))

    if context.recommendation_summary or context.recommendations:
        lines.append("## Engineering analysis")
        lines.append("")
        if context.recommendation_summary:
            lines.append(context.recommendation_summary)
            lines.append("")
        if context.recommendations:
            lines.append("| Area | Current state | Recommended action | Priority | Basis |")
            lines.append("| --- | --- | --- | --- | --- |")
            for item in context.recommendations:
                lines.append(
                    f"| {_cell(item.area)} | {_cell(item.current_state)} "
                    f"| {_cell(item.suggested_change)} | `{item.priority}` "
                    f"| {_cell(item.rationale)} |"
                )
            lines.append("")

    lines.append("## Data record")
    lines.append("")
    lines.append(
        "_Structured tables below mirror the sourced record. Values without a "
        "citation appear only under **Not established**._"
    )
    lines.append("")

    # --- Established --------------------------------------------------------
    lines.append("### Established")
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
    lines.append("### Not established")
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


def render_csv(context: RenderContext) -> str:
    """Build a lean CSV tailored to the job goal."""
    renderers = {
        "replacement_recommendation": _render_replacement_csv,
        "bom_generation": _render_bom_csv,
        "technical_quotation": _render_quotation_csv,
        "rfq_response": _render_quotation_csv,
        "installation_package": _render_installation_csv,
    }
    renderer = renderers.get(context.goal, _render_spec_csv)
    return renderer(context)


_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def _csv_cell(value: str | None) -> str:
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_LEAD):
        return "'" + text
    return text


def _csv_string(headers: list[str], rows: list[dict[str, str]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: _csv_cell(row.get(header, "")) for header in headers})
    return output.getvalue()


def _meta(context: RenderContext) -> dict[str, str]:
    return {
        "job_id": context.project_id,
        "job_name": context.project_name,
        "category": context.category or "",
        "goal": goal_title(context.goal),
        "generated_at": context.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
    }


def _value_map(context: RenderContext) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for field in context.established:
        key = field.name.lower().replace(" ", "_")
        mapping[key] = field.value
        mapping[field.name.lower()] = field.value
        if field.unit:
            mapping[f"{key}_uom"] = field.unit
    return mapping


def _citations(field: RenderField) -> str:
    return "; ".join(field.citations) if field.citations else ""


def _render_spec_csv(context: RenderContext) -> str:
    """Product datasheet / configuration — one row per sourced or missing field."""
    headers = [
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
    meta = _meta(context)
    rows: list[dict[str, str]] = []

    for field in context.established:
        rows.append(
            {
                **meta,
                "field": _label(field.name),
                "value": field.value,
                "unit": field.unit or "",
                "required": "",
                "rated": "",
                "confidence": f"{field.confidence:.0%}",
                "source": _citations(field),
                "status": field.status,
            }
        )

    for field in context.withheld:
        why = STATUS_EXPLANATIONS.get(field.status, "Not available.")
        rows.append(
            {
                **meta,
                "field": _label(field.name),
                "value": "",
                "unit": field.unit or "",
                "required": "",
                "rated": "",
                "confidence": "",
                "source": why,
                "status": field.status,
            }
        )

    for finding in context.findings:
        rows.append(
            {
                **meta,
                "field": f"compatibility — {_label(finding.rule)}",
                "value": "",
                "unit": "",
                "required": finding.required_value or "",
                "rated": finding.rated_value or "",
                "confidence": "",
                "source": finding.reason,
                "status": finding.status,
            }
        )

    if not rows:
        rows.append(
            {
                **meta,
                "field": "",
                "value": "",
                "unit": "",
                "required": "",
                "rated": "",
                "confidence": "",
                "source": "",
                "status": "",
            }
        )

    return _csv_string(headers, rows)


def _render_replacement_csv(context: RenderContext) -> str:
    """Replacement / upgrade jobs — one row per recommendation."""
    headers = [
        "job_id",
        "job_name",
        "category",
        "goal",
        "generated_at",
        "existing_part",
        "reason_for_change",
        "summary",
        "area",
        "current_state",
        "suggested_change",
        "priority",
        "rationale",
    ]
    values = _value_map(context)
    existing = (
        values.get("existing_part_number")
        or values.get("part_number")
        or values.get("model")
        or ""
    )
    reason = (
        values.get("reason_for_replacement")
        or values.get("customer_requirement")
        or values.get("description")
        or ""
    )
    summary = context.recommendation_summary or (
        f"{context.project_name} — {goal_title(context.goal)}"
    )
    meta = {
        **_meta(context),
        "existing_part": existing,
        "reason_for_change": reason,
        "summary": summary,
    }

    if context.recommendations:
        rows = [
            {
                **meta,
                "area": rec.area,
                "current_state": rec.current_state,
                "suggested_change": rec.suggested_change,
                "priority": rec.priority,
                "rationale": rec.rationale,
            }
            for rec in context.recommendations
        ]
    else:
        rows = [
            {
                **meta,
                "area": "",
                "current_state": existing,
                "suggested_change": "",
                "priority": "",
                "rationale": reason,
            }
        ]

    return _csv_string(headers, rows)


def _render_bom_csv(context: RenderContext) -> str:
    """BOM jobs — one row per line item."""
    headers = [
        "job_id",
        "job_name",
        "category",
        "goal",
        "generated_at",
        "line",
        "role",
        "component",
        "quantity",
        "status",
        "notes",
    ]
    meta = _meta(context)
    values = _value_map(context)

    rows: list[dict[str, str]] = []
    for line in context.bom_lines:
        rows.append(
            {
                **meta,
                "line": str(line.position),
                "role": line.role,
                "component": line.component,
                "quantity": line.quantity or "",
                "status": line.status,
                "notes": line.reason,
            }
        )

    if not rows:
        rows.append(
            {
                **meta,
                "line": "1",
                "role": "assembly",
                "component": values.get("model") or values.get("part_number") or context.project_name,
                "quantity": "",
                "status": "resolved" if values else "missing",
                "notes": "",
            }
        )

    return _csv_string(headers, rows)


def _render_quotation_csv(context: RenderContext) -> str:
    """Quotation / RFQ — identity plus sourced specs."""
    headers = [
        "job_id",
        "job_name",
        "category",
        "goal",
        "generated_at",
        "part_number",
        "manufacturer",
        "model",
        "description",
        "field",
        "value",
        "unit",
        "source",
    ]
    values = _value_map(context)
    meta = _meta(context)
    identity = {
        **meta,
        "part_number": values.get("part_number") or values.get("existing_part_number") or values.get("model") or "",
        "manufacturer": values.get("manufacturer") or values.get("manufacturer_name") or "",
        "model": values.get("model") or "",
        "description": values.get("description") or values.get("customer_requirement") or context.project_name,
    }

    quote_fields = [
        f for f in context.established
        if f.name.lower().replace(" ", "_")
        not in {
            "part_number",
            "existing_part_number",
            "manufacturer",
            "manufacturer_name",
            "model",
            "description",
            "customer_requirement",
        }
    ]

    rows: list[dict[str, str]] = []
    for field in quote_fields:
        rows.append(
            {
                **identity,
                "field": _label(field.name),
                "value": field.value,
                "unit": field.unit or "",
                "source": _citations(field),
            }
        )

    if not rows:
        rows.append({**identity, "field": "", "value": "", "unit": "", "source": ""})

    return _csv_string(headers, rows)


def _render_installation_csv(context: RenderContext) -> str:
    """Installation package — install-relevant fields only."""
    install_hints = (
        "install",
        "mount",
        "wiring",
        "voltage",
        "pressure",
        "connection",
        "pipe",
        "torque",
        "clearance",
        "orientation",
        "environment",
        "temperature",
        "flow",
        "dimension",
        "weight",
        "certification",
        "approval",
        "manual",
    )
    headers = [
        "job_id",
        "job_name",
        "category",
        "goal",
        "generated_at",
        "field",
        "value",
        "unit",
        "source",
        "status",
    ]
    meta = _meta(context)
    rows: list[dict[str, str]] = []

    def _is_install_field(name: str) -> bool:
        hay = name.lower().replace("_", " ")
        return any(hint in hay for hint in install_hints)

    for field in context.established:
        if not _is_install_field(field.name):
            continue
        rows.append(
            {
                **meta,
                "field": _label(field.name),
                "value": field.value,
                "unit": field.unit or "",
                "source": _citations(field),
                "status": field.status,
            }
        )

    for field in context.withheld:
        if not _is_install_field(field.name):
            continue
        rows.append(
            {
                **meta,
                "field": _label(field.name),
                "value": "",
                "unit": field.unit or "",
                "source": STATUS_EXPLANATIONS.get(field.status, "Not available."),
                "status": field.status,
            }
        )

    if not rows:
        return _render_spec_csv(context)

    return _csv_string(headers, rows)
