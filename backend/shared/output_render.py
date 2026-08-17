"""Render the final artifact (M8). Pure functions — no DB, no network.

CSV output in Unilog format (252 columns). Maps ForgeData attributes to
Unilog's standard wide-format schema. All established values are populated;
withheld fields are left blank.
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
    return f"{goal}_{project_id}.csv"


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


def render_csv(context: RenderContext) -> str:
    """Build CSV in Unilog format (252 columns). Maps ForgeData attributes."""
    output = StringIO()

    # Unilog header row (252 columns)
    headers = [
        "MFR URL", "Ref URL 1", "Ref URL 2", "Ref URL 3", "Ref URL 4", "Ref URL 5",
        "PART_NUMBER", "Dept", "Class", "Fine", "SKU - MY_PART_NUMBER",
        "Mfg_Part_Num", "Part_Desc", "E1_Brand", "Unilog_Brand", "DIB_Brand",
        "Part_Manuf", "MANUFACTURER_NAME", "BRAND_NAME", "TRADE_NAME",
        "MANUFACTURER_PART_NUMBER", "ALTERNATE_PART_NUMBER", "Classpath",
        "MOBILE_DESC", "INVOICE_DESC", "SHORT_DESC", "LONG_DESC1", "RETAIL_DESC",
        "MARKETING_DESCRIPTION",
        # Features
        *[f"ITEM_FEATURES_{i}" for i in range(1, 21)],
        # Approvals
        "With", "Standard/Approvals", "Prop 65", "Application", "Includes",
        "Product Name",
        # Attributes: 50 slots of (LABEL, VALUE, UOM)
        *[col for i in range(1, 51) for col in [
            f"ATTRIBUTE_LABEL {i}", f"ATTRIBUTE_VALUE {i}", f"ATTRIBUTE_UOM {i}"
        ]],
        # Codes
        "UPC", "EAN", "GTIN", "UNSPSC",
        # Pricing & packaging
        "Warranty", "List Price", "Selling Qty", "Selling UOM",
        "Standard Packaging Information",
        # Dimensions
        "LENGTH", "LENGTH_UOM", "HEIGHT", "HEIGHT_UOM", "WIDTH", "WIDTH_UOM",
        "WEIGHT", "WEIGHT_UOM", "VOLUME", "VOLUME_UOM",
        # Images & documents
        "Product Image", "Alternate Image 1", "Alternate Image 2",
        "Alternate Image 3", "Alternate Image 4",
        "SDS", "SDS_1", "Warranty Information", "Catalog",
        "Specification Sheet", "Instruction/Installation Manual", "Service Manual",
        "Owners/User Manual", "Line Drawing", "MTR", "RoHS",
        "Full Engineering Drawing", "Energy Star Guide", "Technical Bulletin",
        "Submittal", "Compatibility Chart", "Size Chart", "Product Label/Insert",
        "Video Link", "Video Link 1",
        # Metadata
        "Country Of Origin", "Discontinued", "Actual Image (Yes/No)",
    ]

    # Build value map from established fields (keyed by normalized name)
    value_map = {}
    for field in context.established:
        # Store with both original name and normalized versions
        key = field.name.lower().replace(" ", "_")
        value_map[key] = field.value
        value_map[field.name.lower()] = field.value
        # Also store unit separately
        if field.unit:
            value_map[f"{key}_uom"] = field.unit

    # Build row with smart column mapping
    row = {}

    # Reference columns — try to extract from attributes
    row["PART_NUMBER"] = value_map.get("part_number", value_map.get("mfr_part_number", ""))
    row["MANUFACTURER_NAME"] = value_map.get("manufacturer_name", value_map.get("manufacturer", ""))
    row["BRAND_NAME"] = value_map.get("brand_name", value_map.get("brand", ""))
    row["Dept"] = value_map.get("dept", value_map.get("department", ""))
    row["Class"] = value_map.get("class", "")

    # Descriptions (try to extract or use first available)
    descriptions = [value_map.get(f"{desc}_desc", "") for desc in
                   ["mobile", "invoice", "short", "long", "retail", "marketing"]]
    row["MOBILE_DESC"] = descriptions[0] or value_map.get("description", "")
    row["INVOICE_DESC"] = descriptions[1] or ""
    row["SHORT_DESC"] = descriptions[2] or ""
    row["LONG_DESC1"] = descriptions[3] or ""
    row["RETAIL_DESC"] = descriptions[4] or ""
    row["MARKETING_DESCRIPTION"] = descriptions[5] or ""

    # Electrical ratings (first slots)
    slot = 1
    if "voltage" in value_map:
        row["ATTRIBUTE_LABEL 1"] = "Voltage"
        row["ATTRIBUTE_VALUE 1"] = value_map.get("voltage", "")
        row["ATTRIBUTE_UOM 1"] = value_map.get("voltage_uom", "V")
        slot = 2
    if "amperage" in value_map:
        row[f"ATTRIBUTE_LABEL {slot}"] = "Amperage"
        row[f"ATTRIBUTE_VALUE {slot}"] = value_map.get("amperage", "")
        row[f"ATTRIBUTE_UOM {slot}"] = value_map.get("amperage_uom", "A")
        slot += 1

    # Attributes (slot N with LABEL/VALUE/UOM triplets)
    attr_count = 0
    for field in context.established:
        if slot + attr_count > 50:
            break
        # Skip if this is a known column header, only store extras as attributes
        if not _is_standard_column(field.name):
            current_slot = slot + attr_count
            row[f"ATTRIBUTE_LABEL {current_slot}"] = _label(field.name)
            row[f"ATTRIBUTE_VALUE {current_slot}"] = field.value
            row[f"ATTRIBUTE_UOM {current_slot}"] = field.unit or ""
            attr_count += 1

    # Dimensions
    for dim in ["length", "height", "width", "weight", "volume"]:
        if f"{dim}_uom" in value_map:
            row[f"{dim.upper()}"] = value_map.get(dim, "")
            row[f"{dim.upper()}_UOM"] = value_map.get(f"{dim}_uom", "")

    # Safety & compliance
    if "certification" in value_map:
        row["Standard/Approvals"] = value_map.get("certification", "")

    # Country of origin
    row["Country Of Origin"] = value_map.get("country_of_origin", "")
    row["Discontinued"] = "Yes" if value_map.get("discontinued", "").lower() in ["yes", "true"] else ""

    # Write CSV header
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()

    # Write single data row (ForgeData produces one output per job)
    writer.writerow({h: row.get(h, "") for h in headers})

    return output.getvalue()


def _is_standard_column(field_name: str) -> bool:
    """Check if a field name is a standard Unilog column (not an extra attribute)."""
    standard_cols = {
        "part_number", "manufacturer_name", "brand_name", "dept", "class",
        "mobile_desc", "invoice_desc", "short_desc", "long_desc", "retail_desc",
        "marketing_description", "voltage", "amperage", "certification",
        "country_of_origin", "discontinued", "weight", "height", "width",
        "length", "volume",
    }
    return field_name.lower().replace(" ", "_") in standard_cols
