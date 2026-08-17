"""Build evidence-grounded report narrative for output artifacts.

Reports are synthesized from sourced fields, explicit gaps, compatibility
results, and user answers — not generic keyword templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from shared.output_render import (
    RenderContext,
    RenderField,
    RenderFinding,
    STATUS_EXPLANATIONS,
    goal_title,
)


@dataclass(frozen=True)
class ReportSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportNarrative:
    executive_summary: str
    sections: tuple[ReportSection, ...] = ()


def _label(name: str) -> str:
    return name.replace("_", " ")


def _field_line(field: RenderField) -> str:
    value = field.display_value()
    source = "; ".join(field.citations) if field.citations else "user answer"
    return f"**{_label(field.name)}**: {value} ({source}, {field.confidence:.0%} confidence)"


def _gap_line(field: RenderField) -> str:
    why = STATUS_EXPLANATIONS.get(field.status, "Not available.")
    return f"**{_label(field.name)}** — `{field.status}`: {why}"


def _finding_line(finding: RenderFinding) -> str:
    required = finding.required_value or "not specified"
    rated = finding.rated_value or "not on record"
    return (
        f"**{_label(finding.rule)}**: required {required}, "
        f"on record {rated} → `{finding.status}` ({finding.reason})"
    )


def _pick(fields: list[RenderField], *names: str) -> list[RenderField]:
    wanted = {name.lower() for name in names}
    return [field for field in fields if field.name.lower() in wanted]


def _identity_summary(ctx: RenderContext) -> str:
    hits = _pick(
        ctx.established,
        "manufacturer",
        "manufacturer_name",
        "model",
        "part_number",
        "existing_part_number",
        "description",
    )
    if not hits:
        return "No product identity fields are fully sourced on this job."
    parts = [field.display_value() for field in hits]
    return " / ".join(parts)


def _replacement_narrative(ctx: RenderContext) -> ReportNarrative:
    existing = next(
        (field for field in ctx.established + ctx.withheld if field.name == "existing_part_number"),
        None,
    )
    reason = next(
        (field for field in ctx.established + ctx.withheld if field.name == "reason_for_replacement"),
        None,
    )
    existing_text = existing.display_value() if existing and existing.value else "not recorded"
    reason_text = reason.value if reason and reason.value else "not recorded"

    sourced = len(ctx.established)
    gaps = len(ctx.withheld)
    failed_checks = [finding for finding in ctx.findings if finding.status not in {"pass", "unknown"}]

    executive = (
        f"This replacement assessment covers **{ctx.project_name}** ({ctx.category}). "
        f"The installed item is recorded as **{existing_text}**. "
        f"Stated driver: {reason_text}. "
        f"{sourced} field(s) are sourced on the record; {gaps} remain unresolved."
    )
    if failed_checks:
        executive += f" {len(failed_checks)} compatibility check(s) did not pass."

    sections: list[ReportSection] = []

    if ctx.established:
        sections.append(
            ReportSection(
                title="Installed asset — verified record",
                paragraphs=(
                    "The following values are quoted from sources on this job and form "
                    "the baseline for any substitute selection.",
                ),
                bullets=tuple(_field_line(field) for field in ctx.established),
            )
        )

    sections.append(
        ReportSection(
            title="Replacement scope",
            paragraphs=(
                f"**Part targeted:** {existing_text}",
                f"**Why replacement is needed:** {reason_text}",
                (
                    "A catalog substitute must match or exceed every sourced rating "
                    "below and close every gap before the package can be quoted."
                ),
            ),
        )
    )

    if ctx.withheld:
        sections.append(
            ReportSection(
                title="Gaps blocking substitute selection",
                paragraphs=(
                    "These fields were not stated because no acceptable source exists. "
                    "They must be resolved before naming a replacement part number.",
                ),
                bullets=tuple(_gap_line(field) for field in ctx.withheld),
            )
        )

    if ctx.findings:
        sections.append(
            ReportSection(
                title="Compatibility assessment",
                paragraphs=("Deterministic rules evaluated against the sourced record.",),
                bullets=tuple(_finding_line(finding) for finding in ctx.findings),
            )
        )

    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def _datasheet_narrative(ctx: RenderContext) -> ReportNarrative:
    identity = _identity_summary(ctx)
    executive = (
        f"Product datasheet for **{ctx.project_name}** ({ctx.category}). "
        f"Identity on record: {identity}. "
        f"{len(ctx.established)} specification(s) sourced; {len(ctx.withheld)} gap(s) documented."
    )
    sections: list[ReportSection] = []

    if ctx.established:
        sections.append(
            ReportSection(
                title="Verified specifications",
                paragraphs=("Each value below is tied to a document page or user-confirmed answer.",),
                bullets=tuple(_field_line(field) for field in ctx.established),
            )
        )

    if ctx.withheld:
        sections.append(
            ReportSection(
                title="Specification gaps",
                paragraphs=(
                    "Fields listed here were deliberately omitted from the established "
                    "specification because they could not be sourced.",
                ),
                bullets=tuple(_gap_line(field) for field in ctx.withheld),
            )
        )

    if ctx.findings:
        sections.append(
            ReportSection(
                title="Rating checks",
                bullets=tuple(_finding_line(finding) for finding in ctx.findings),
            )
        )

    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def _bom_narrative(ctx: RenderContext) -> ReportNarrative:
    resolved = sum(1 for line in ctx.bom_lines if line.status != "missing")
    missing = len(ctx.bom_lines) - resolved
    executive = (
        f"Bill of materials for **{ctx.project_name}** ({ctx.category}). "
        f"{resolved} line(s) resolved from sourced evidence; {missing} could not be named."
    )
    sections: list[ReportSection] = []

    if ctx.bom_lines:
        bullets = tuple(
            f"Line {line.position} — **{line.component}** ({line.role}), "
            f"qty {line.quantity or '—'}, status `{line.status}`"
            + (f": {line.reason}" if line.reason else "")
            for line in ctx.bom_lines
        )
        sections.append(ReportSection(title="Line items", bullets=bullets))

    if ctx.established:
        sections.append(
            ReportSection(
                title="Assembly identity",
                bullets=tuple(_field_line(field) for field in ctx.established[:8]),
            )
        )

    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def _rfq_narrative(ctx: RenderContext) -> ReportNarrative:
    requirement = next(
        (field for field in ctx.established + ctx.withheld if field.name == "customer_requirement"),
        None,
    )
    quantity = next(
        (field for field in ctx.established + ctx.withheld if field.name == "quantity"),
        None,
    )
    req_text = requirement.value if requirement and requirement.value else "not recorded"
    qty_text = quantity.display_value() if quantity and quantity.value else "not stated"

    executive = (
        f"RFQ response package for **{ctx.project_name}**. "
        f"Customer requirement: {req_text}. Quantity: {qty_text}. "
        f"{len(ctx.established)} line item(s) can be quoted from sourced data."
    )
    sections: list[ReportSection] = [
        ReportSection(
            title="Commercial scope",
            paragraphs=(
                f"**Requirement:** {req_text}",
                f"**Quantity:** {qty_text}",
            ),
        )
    ]
    if ctx.established:
        sections.append(
            ReportSection(
                title="Quotable specifications",
                bullets=tuple(_field_line(field) for field in ctx.established),
            )
        )
    if ctx.withheld:
        sections.append(
            ReportSection(
                title="Lines that cannot be quoted yet",
                bullets=tuple(_gap_line(field) for field in ctx.withheld),
            )
        )
    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def _installation_narrative(ctx: RenderContext) -> ReportNarrative:
    executive = (
        f"Installation package for **{ctx.project_name}** ({ctx.category}). "
        f"{len(ctx.established)} install-relevant field(s) sourced; "
        f"{len(ctx.withheld)} install parameter(s) still missing."
    )
    sections: list[ReportSection] = []
    if ctx.established:
        sections.append(
            ReportSection(
                title="Install parameters on record",
                bullets=tuple(_field_line(field) for field in ctx.established),
            )
        )
    if ctx.withheld:
        sections.append(
            ReportSection(
                title="Install parameters not yet sourced",
                bullets=tuple(_gap_line(field) for field in ctx.withheld),
            )
        )
    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def _generic_narrative(ctx: RenderContext) -> ReportNarrative:
    executive = (
        f"{goal_title(ctx.goal)} for **{ctx.project_name}** ({ctx.category}). "
        f"{len(ctx.established)} sourced field(s); {len(ctx.withheld)} documented gap(s)."
    )
    sections: list[ReportSection] = []
    if ctx.established:
        sections.append(
            ReportSection(
                title="Sourced record",
                bullets=tuple(_field_line(field) for field in ctx.established),
            )
        )
    if ctx.withheld:
        sections.append(
            ReportSection(
                title="Documented gaps",
                bullets=tuple(_gap_line(field) for field in ctx.withheld),
            )
        )
    return ReportNarrative(executive_summary=executive, sections=tuple(sections))


def build_report_narrative(ctx: RenderContext) -> ReportNarrative:
    builders = {
        "replacement_recommendation": _replacement_narrative,
        "product_datasheet": _datasheet_narrative,
        "product_configuration": _datasheet_narrative,
        "bom_generation": _bom_narrative,
        "rfq_response": _rfq_narrative,
        "technical_quotation": _rfq_narrative,
        "installation_package": _installation_narrative,
    }
    builder = builders.get(ctx.goal, _generic_narrative)
    return builder(ctx)
