"""Required-field catalog and completeness scoring (M3).

A job is complete when every required field for its goal (+ category extras)
has a real answer. "Not applicable" counts. "I don't know" does not — that
field stays blocking.
"""

from __future__ import annotations

from dataclasses import dataclass


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
UNSATISFIED = {"", "i don't know", "i dont know", "unknown", "idk"}


@dataclass(frozen=True)
class RequiredField:
    field: str
    text: str
    why_asked: str
    priority: str
    input_type: str = "text"
    options: tuple[str, ...] | None = None
    blocking: bool = True


def _select(field: str, text: str, why: str, priority: str, *options: str) -> RequiredField:
    return RequiredField(
        field=field,
        text=text,
        why_asked=why,
        priority=priority,
        input_type="select",
        options=options,
    )


COMMON: tuple[RequiredField, ...] = (
    RequiredField(
        field="manufacturer",
        text="Who manufactured this product?",
        why_asked="Identifies the catalog family before any rating can be trusted.",
        priority="high",
    ),
    RequiredField(
        field="model",
        text="What is the model or SKU?",
        why_asked="Without a model, sibling parts and datasheets cannot be matched.",
        priority="critical",
    ),
    _select(
        "operating_medium",
        "What medium will this see in service?",
        "Drives seals, body material, and chemical-compatibility checks.",
        "critical",
        "Water",
        "Compressed air",
        "Oil",
        "Steam",
        "Chemical",
        "Other",
    ),
    _select(
        "installation_environment",
        "Where will it be installed?",
        "Sets enclosure (IP) and coating requirements.",
        "high",
        "Indoor",
        "Outdoor",
        "Both",
        "Hazardous area",
    ),
)

GOAL_FIELDS: dict[str, tuple[RequiredField, ...]] = {
    "product_configuration": (
        _select(
            "fail_safe_mode",
            "Should it close on power loss, or stay open?",
            "Selects the actuator variant before a configuration can be issued.",
            "critical",
            "Close on power loss (normally closed)",
            "Stay open (normally open)",
        ),
        RequiredField(
            field="supply_voltage",
            text="What coil / supply voltage is required?",
            why_asked="Voltage is high-risk — a wrong coil is a safety and fit issue.",
            priority="critical",
        ),
        _select(
            "connection_standard",
            "What connection standard should the ports use?",
            "NPT vs BSPP is a common datasheet mix-up and a leak waiting to happen.",
            "high",
            "NPT",
            "BSPP",
            "BSPT",
            "SAE",
            "Flanged",
            "Unknown",
        ),
        RequiredField(
            field="maximum_pressure",
            text="What maximum working pressure must it hold?",
            why_asked="Pressure rating is safety-critical and cannot be guessed.",
            priority="critical",
        ),
    ),
    "bom_generation": (
        RequiredField(
            field="application",
            text="What application is this BOM for?",
            why_asked="The parts list follows the application, not a generic catalog dump.",
            priority="critical",
        ),
        RequiredField(
            field="quantity",
            text="How many complete assemblies are needed?",
            why_asked="Quantities scale every BOM line.",
            priority="high",
            input_type="number",
        ),
        _select(
            "connection_standard",
            "What connection standard should mating parts use?",
            "Mismatched threads make the whole BOM unusable in the field.",
            "high",
            "NPT",
            "BSPP",
            "BSPT",
            "SAE",
            "Flanged",
            "Unknown",
        ),
    ),
    "technical_quotation": (
        RequiredField(
            field="quantity",
            text="What quantity is being quoted?",
            why_asked="Price and lead time are meaningless without quantity.",
            priority="high",
            input_type="number",
        ),
        RequiredField(
            field="delivery_requirement",
            text="Any delivery or site constraint the quote must honour?",
            why_asked="Lead time and packing depend on this, not on the datasheet.",
            priority="medium",
        ),
    ),
    "product_datasheet": (
        RequiredField(
            field="key_rating",
            text="What is the headline rating that must appear on the sheet?",
            why_asked="A datasheet that omits the governing rating is not publishable.",
            priority="critical",
        ),
    ),
    "installation_package": (
        _select(
            "mounting_orientation",
            "What mounting orientation is required?",
            "Coil and drain orientation are installation-fatal if wrong.",
            "high",
            "Vertical coil-up",
            "Vertical coil-down",
            "Horizontal",
            "Any",
        ),
        RequiredField(
            field="power_supply",
            text="What power supply is available at the install site?",
            why_asked="Wiring instructions cannot be written without the supply.",
            priority="critical",
        ),
    ),
    "replacement_recommendation": (
        RequiredField(
            field="existing_part_number",
            text="What part is being replaced?",
            why_asked="A substitute is defined against the installed part, not a guess.",
            priority="critical",
        ),
        RequiredField(
            field="reason_for_replacement",
            text="Why is it being replaced?",
            why_asked="Obsolete vs failed vs upsized changes which substitutes are legal.",
            priority="high",
        ),
    ),
    "rfq_response": (
        RequiredField(
            field="customer_requirement",
            text="What is the customer actually asking for, in one sentence?",
            why_asked="The RFQ response has to map their list onto the catalog, field by field.",
            priority="critical",
        ),
        RequiredField(
            field="quantity",
            text="What quantity did they request?",
            why_asked="An RFQ with no quantity is not answerable.",
            priority="high",
            input_type="number",
        ),
    ),
}

# Goals that ask only goal-specific (+ category) fields — not the COMMON catalog block.
# Product configuration / BOM jobs still merge manufacturer, model, medium, etc.
GOAL_ONLY: frozenset[str] = frozenset(
    {
        "replacement_recommendation",
        "rfq_response",
        "technical_quotation",
        "product_datasheet",
        "installation_package",
    }
)

CATEGORY_FIELDS: tuple[tuple[str, RequiredField], ...] = (
    (
        "valve",
        _select(
            "fail_safe_mode",
            "Should the valve close on power loss, or stay open?",
            "Actuator variant depends on fail-safe. This cannot be inferred from a photo.",
            "critical",
            "Close on power loss (normally closed)",
            "Stay open (normally open)",
        ),
    ),
    (
        "sensor",
        RequiredField(
            field="measurement_range",
            text="What measurement range must the sensor cover?",
            why_asked="A sensor outside the process range is a wrong part.",
            priority="critical",
        ),
    ),
)


def required_fields(goal: str, category: str = "") -> list[RequiredField]:
    """Merge goal (+ optional COMMON) + category extras."""
    merged: dict[str, RequiredField] = {}
    if goal not in GOAL_ONLY:
        for spec in COMMON:
            merged[spec.field] = spec
    for spec in GOAL_FIELDS.get(goal, ()):
        merged[spec.field] = spec
    haystack = (category or "").lower().replace("-", " ").replace("_", " ")
    for needle, spec in CATEGORY_FIELDS:
        if needle in haystack:
            merged.setdefault(spec.field, spec)
    return list(merged.values())


def is_satisfied(answer: str | None) -> bool:
    if answer is None:
        return False
    return answer.strip().lower() not in UNSATISFIED


def is_not_applicable(answer: str | None) -> bool:
    return (answer or "").strip().lower() in {"not applicable", "n/a", "na"}


def score_answers(
    specs: list[RequiredField], answers: dict[str, str]
) -> tuple[int, int]:
    """Return (completion_score 0–100, blocking_fields_count)."""
    if not specs:
        return 100, 0
    completed = 0
    blocking = 0
    for spec in specs:
        raw = answers.get(spec.field)
        if is_satisfied(raw):
            completed += 1
        elif spec.blocking:
            blocking += 1
    return round(100 * completed / len(specs)), blocking


def goal_field_names(goal: str) -> frozenset[str]:
    return frozenset(spec.field for spec in GOAL_FIELDS.get(goal, ()))


def next_unsatisfied(
    specs: list[RequiredField],
    answers: dict[str, str],
    *,
    goal: str = "",
) -> RequiredField | None:
    missing = [spec for spec in specs if not is_satisfied(answers.get(spec.field))]
    goal_first = goal_field_names(goal)
    missing.sort(
        key=lambda spec: (
            0 if spec.field in goal_first else 1,
            PRIORITY_ORDER.get(spec.priority, 9),
        )
    )
    return missing[0] if missing else None


def status_for_score(completion_score: int, blocking: int) -> str:
    if completion_score >= 100 and blocking == 0:
        return "ready_to_generate"
    if blocking > 0:
        return "waiting_for_user"
    return "collecting_information"
