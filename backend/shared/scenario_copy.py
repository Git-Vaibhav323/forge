"""Rule-based scenario wording — built-in copy tailored to goal and work type."""

from __future__ import annotations

from dataclasses import dataclass

from shared.category_catalog import is_industrial_category, normalise_category
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


def enrich_question(spec: RequiredField, ctx: ScenarioContext) -> EnrichedQuestion:
    """Tailor built-in question copy to the job goal, name, and work type."""
    goal = ctx.goal
    doc = _doc_hint(ctx)
    hay = normalise_category(ctx.category)
    text = spec.text
    why = spec.why_asked
    industrial = is_industrial_category(ctx.category)

    if goal == "replacement_recommendation":
        if spec.field == "existing_part_number":
            text = f"What exists today for “{ctx.name}”?{doc}"
            why = "Changes start from what is actually in place — not assumptions."
        elif spec.field == "reason_for_replacement":
            text = f"Why does “{ctx.name}” need to change?{doc}"
            why = "The reason drives what options are acceptable."

    elif goal == "rfq_response":
        if spec.field == "customer_requirement":
            text = f"What was requested for “{ctx.name}”?{doc}"
            why = "The response must track back to their ask, line by line."
        elif spec.field == "quantity":
            text = f"What quantity was requested for “{ctx.name}”?{doc}"

    elif goal == "bom_generation":
        if spec.field == "application":
            text = f"What is this list for (“{ctx.name}”)?{doc}"
            why = "Line items follow the use case — not a generic dump."
        elif spec.field == "quantity":
            text = f"How many of “{ctx.name}” are needed?{doc}"

    elif goal == "technical_quotation":
        if spec.field == "quantity":
            text = f"What quantity should be quoted for “{ctx.name}”?{doc}"
        elif spec.field == "delivery_requirement":
            text = f"Any timing or delivery constraints for “{ctx.name}”?{doc}"

    elif goal == "product_datasheet":
        if spec.field == "key_rating":
            text = f"What headline fact must appear for “{ctx.name}”?{doc}"

    elif goal == "installation_package":
        if spec.field == "mounting_orientation":
            text = f"How should “{ctx.name}” be set up?{doc}"
        elif spec.field == "power_supply":
            text = f"What is available on site to support “{ctx.name}”?{doc}"

    elif goal == "product_configuration":
        if spec.field == "maximum_pressure" and not industrial:
            text = f"What is the key limit or requirement for “{ctx.name}”?{doc}"

    # Work-type extras
    if "software" in hay:
        if spec.field == "platform":
            text = f"What platform or stack does “{ctx.name}” use?{doc}"
    elif "physical product" in hay or hay == "physical product":
        if spec.field == "key_specification":
            text = f"What is the single most important spec for “{ctx.name}”?{doc}"
    elif "service" in hay:
        if spec.field == "scope":
            text = f"What is in scope for “{ctx.name}”?{doc}"
    elif "content" in hay:
        if spec.field == "audience":
            text = f"Who will read or use “{ctx.name}”?{doc}"
    elif "kit" in hay or "bundle" in hay:
        if spec.field == "bundle_contents":
            text = f"What belongs in the “{ctx.name}” bundle?{doc}"

    # Industrial-only wording
    if industrial:
        if goal == "product_configuration" and spec.field == "fail_safe_mode":
            text = f"For this equipment, what happens on power or signal loss?{doc}"
        elif spec.field == "supply_voltage":
            text = f"What supply voltage or power level does “{ctx.name}” need?{doc}"
        elif spec.field == "maximum_pressure":
            text = f"What maximum working pressure must “{ctx.name}” hold?{doc}"
        elif "pump" in hay and spec.field == "design_flow_rate":
            text = f"What flow rate must this pump deliver for “{ctx.name}”?{doc}"
        elif "pump" in hay and spec.field == "design_head":
            text = f"What total head must this pump overcome?{doc}"

    # Generic defaults (most work types)
    if not industrial:
        if spec.field == "manufacturer":
            text = f"Who provides or owns “{ctx.name}”?{doc}"
        elif spec.field == "model":
            text = f"What name or version identifies “{ctx.name}”?{doc}"
        elif spec.field == "operating_medium":
            text = f"What does “{ctx.name}” interact with or depend on?{doc}"
        elif spec.field == "installation_environment":
            text = f"Where is “{ctx.name}” used or deployed?{doc}"
        elif spec.field == "existing_part_number":
            text = f"What is being replaced or upgraded for “{ctx.name}”?{doc}"
    elif doc and text == spec.text:
        text = f"{spec.text}{doc}"

    return EnrichedQuestion(spec=spec, text=text, why_asked=why)
