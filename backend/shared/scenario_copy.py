"""Rule-based scenario wording when LLM is off or unavailable."""

from __future__ import annotations

from dataclasses import dataclass

from shared.completeness import RequiredField


@dataclass(frozen=True)
class ScenarioContext:
    name: str
    goal: str
    category: str
    document_names: tuple[str, ...]


@dataclass(frozen=True)
class EnrichedQuestion:
    spec: RequiredField
    text: str
    why_asked: str


def _doc_hint(ctx: ScenarioContext) -> str:
    if not ctx.document_names:
        return ""
    if len(ctx.document_names) == 1:
        return f" (see {ctx.document_names[0]})"
    return f" (see {ctx.document_names[0]} and {len(ctx.document_names) - 1} other file(s))"


def _is_non_industrial_category(category: str) -> bool:
    hay = (category or "").lower().replace("-", " ").replace("_", " ")
    industrial = (
        "valve",
        "pump",
        "sensor",
        "motor",
        "pipe",
        "solenoid",
        "gauge",
        "actuator",
        "fitting",
        "flange",
    )
    return not any(token in hay for token in industrial)


def enrich_question(spec: RequiredField, ctx: ScenarioContext) -> EnrichedQuestion:
    """Tailor template copy to the job goal, name, and uploaded sources."""
    goal = ctx.goal
    doc = _doc_hint(ctx)
    text = spec.text
    why = spec.why_asked

    if goal == "replacement_recommendation":
        if spec.field == "existing_part_number":
            text = f"What part or product is being replaced for “{ctx.name}”?{doc}"
            why = "Replacement jobs start from the installed part — not a generic catalog SKU."
        elif spec.field == "reason_for_replacement":
            text = f"Why is “{ctx.name}” being replaced?{doc}"
            why = "Obsolete, failed, and upsized swaps follow different approval rules."

    elif goal == "rfq_response":
        if spec.field == "customer_requirement":
            text = f"What is the customer asking for on job “{ctx.name}”?{doc}"
            why = "The RFQ response must map their wording to your catalog field by field."
        elif spec.field == "quantity":
            text = f"What quantity did the customer request for “{ctx.name}”?{doc}"

    elif goal == "bom_generation":
        if spec.field == "application":
            text = f"What application is this BOM for (“{ctx.name}”, {ctx.category})?{doc}"
            why = "BOM lines follow the application — not a generic parts dump."

    elif goal == "product_configuration":
        if spec.field == "fail_safe_mode" and ctx.category:
            text = f"For {ctx.category}, should it close on power loss or stay open?{doc}"

    elif goal == "product_datasheet":
        if spec.field == "key_rating":
            text = f"What headline rating must appear on the datasheet for “{ctx.name}”?{doc}"

    elif doc and text == spec.text:
        text = f"{spec.text}{doc}"

    if _is_non_industrial_category(ctx.category):
        if spec.field == "manufacturer":
            text = f"Who is the vendor, team, or provider for “{ctx.name}”?{doc}"
            why = "Identifies who owns the product or service — industrial or not."
        elif spec.field == "model":
            text = f"What is the product, service, or version name for “{ctx.name}”?{doc}"
            why = "A stable name or SKU is needed to match docs and downstream outputs."
        elif spec.field == "operating_medium":
            text = f"What does this interact with in practice (medium, platform, or environment)?{doc}"
            why = "Compatibility checks apply even outside classic plant equipment."
        elif spec.field == "installation_environment":
            text = f"Where will “{ctx.name}” be used or deployed?{doc}"
            why = "Install context drives packaging, access, and compliance needs."

    return EnrichedQuestion(spec=spec, text=text, why_asked=why)
