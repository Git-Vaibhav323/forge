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
        text="Who provides or owns this?",
        why_asked="Identifies the source before anything can be verified.",
        priority="high",
    ),
    RequiredField(
        field="model",
        text="What is the name, version, or identifier?",
        why_asked="A stable identifier is needed to match documents and outputs.",
        priority="critical",
    ),
    _select(
        "operating_medium",
        "What does this interact with or depend on?",
        "Context drives compatibility checks and what gets asked next.",
        "critical",
        "People / users",
        "Data or content",
        "Physical environment",
        "Another system",
        "Other",
    ),
    _select(
        "installation_environment",
        "Where is this used or deployed?",
        "Environment shapes requirements and constraints.",
        "high",
        "Office / remote",
        "Customer site",
        "Cloud",
        "Field / on-site",
        "Regulated / restricted",
        "Other",
    ),
)

GOAL_FIELDS: dict[str, tuple[RequiredField, ...]] = {
    "product_configuration": (
        _select(
            "fail_safe_mode",
            "What should happen if power or service is interrupted?",
            "Defines the safe default before a configuration can be issued.",
            "critical",
            "Return to safe / off state",
            "Keep last state",
            "Not applicable",
        ),
        RequiredField(
            field="supply_voltage",
            text="What power or input level is required?",
            why_asked="Wrong power or input breaks fit and safety assumptions.",
            priority="critical",
        ),
        _select(
            "connection_standard",
            "What interface or connection standard applies?",
            "Mismatched interfaces are a common source of rework.",
            "high",
            "Standard A",
            "Standard B",
            "Custom",
            "Unknown",
        ),
        RequiredField(
            field="maximum_pressure",
            text="What is the key limit or rating it must meet?",
            why_asked="The governing limit cannot be guessed from a name alone.",
            priority="critical",
        ),
    ),
    "bom_generation": (
        RequiredField(
            field="application",
            text="What is this list for?",
            why_asked="The list follows the use case — not a generic dump.",
            priority="critical",
        ),
        RequiredField(
            field="quantity",
            text="How many are needed?",
            why_asked="Quantities scale every line item.",
            priority="high",
            input_type="number",
        ),
        _select(
            "connection_standard",
            "What interface or format should line items follow?",
            "Keeps the list consistent end to end.",
            "high",
            "Standard A",
            "Standard B",
            "Custom",
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
            text="What is the headline fact or spec that must appear?",
            why_asked="A summary without its main point is not publishable.",
            priority="critical",
        ),
    ),
    "installation_package": (
        _select(
            "mounting_orientation",
            "How should this be set up or deployed?",
            "Setup steps depend on orientation and access.",
            "high",
            "Standard setup",
            "Custom setup",
            "Remote / hands-off",
            "Any",
        ),
        RequiredField(
            field="power_supply",
            text="What power, access, or prerequisites are available on site?",
            why_asked="Setup instructions need the real environment.",
            priority="critical",
        ),
    ),
    "replacement_recommendation": (
        RequiredField(
            field="existing_part_number",
            text="What exists today that needs to change?",
            why_asked="Upgrades are defined against what is installed now — not a guess.",
            priority="critical",
        ),
        RequiredField(
            field="reason_for_replacement",
            text="Why does it need to change?",
            why_asked="Broken, obsolete, and upsized changes follow different paths.",
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
        "physical product",
        RequiredField(
            field="key_specification",
            text="What is the most important specification?",
            why_asked="Every product has one fact that everything else hangs on.",
            priority="critical",
        ),
    ),
    (
        "software",
        RequiredField(
            field="platform",
            text="What platform or environment does this run on?",
            why_asked="Stack and deployment shape every downstream question.",
            priority="critical",
        ),
    ),
    (
        "service",
        RequiredField(
            field="scope",
            text="What is in scope for this service or process?",
            why_asked="Boundaries keep the record honest about what is covered.",
            priority="critical",
        ),
    ),
    (
        "content",
        RequiredField(
            field="audience",
            text="Who is the intended audience?",
            why_asked="Tone, depth, and format all follow the reader.",
            priority="high",
        ),
    ),
    (
        "kit",
        RequiredField(
            field="bundle_contents",
            text="What items belong in this kit or bundle?",
            why_asked="A bundle is only complete when every piece is named.",
            priority="critical",
        ),
    ),
    (
        "industrial",
        _select(
            "fail_safe_mode",
            "What should happen on power or signal loss?",
            "Fail position is safety-critical on plant equipment.",
            "critical",
            "Fail safe / off",
            "Fail open",
            "Hold last position",
            "Not applicable",
        ),
    ),
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
        "pump",
        RequiredField(
            field="design_flow_rate",
            text="What design flow rate must the pump deliver?",
            why_asked="BOM and curve selection start from the duty point.",
            priority="critical",
        ),
    ),
    (
        "pump",
        RequiredField(
            field="design_head",
            text="What total dynamic head (TDH) is required?",
            why_asked="Head and flow together define the pump operating point.",
            priority="critical",
        ),
    ),
    (
        "sensor",
        RequiredField(
            field="measurement_range",
            text="What measurement range must the instrument cover?",
            why_asked="A sensor outside the process range is a wrong part.",
            priority="critical",
        ),
    ),
    (
        "transmitter",
        RequiredField(
            field="measurement_range",
            text="What measurement range must the transmitter cover?",
            why_asked="Range and accuracy class must match the process.",
            priority="critical",
        ),
    ),
    (
        "meter",
        RequiredField(
            field="flow_range",
            text="What flow range must the meter cover?",
            why_asked="Sizing errors show up as poor accuracy or straight-run violations.",
            priority="critical",
        ),
    ),
    (
        "motor",
        RequiredField(
            field="motor_power",
            text="What motor power (HP or kW) is required?",
            why_asked="Drive sizing depends on nameplate power and service factor.",
            priority="critical",
        ),
    ),
    (
        "actuator",
        _select(
            "fail_safe_mode",
            "Should the actuator fail closed, fail open, or hold last position?",
            "Fail position is safety-critical and must be confirmed.",
            "critical",
            "Fail closed",
            "Fail open",
            "Hold last position",
        ),
    ),
    (
        "compressor",
        RequiredField(
            field="air_demand_cfm",
            text="What compressed-air demand (CFM) is required?",
            why_asked="Compressor sizing starts from peak demand and duty cycle.",
            priority="critical",
        ),
    ),
    (
        "exchanger",
        RequiredField(
            field="heat_duty",
            text="What heat duty (BTU/hr or kW) must the exchanger transfer?",
            why_asked="Thermal sizing cannot be inferred from a model name alone.",
            priority="critical",
        ),
    ),
    (
        "filter",
        RequiredField(
            field="filtration_rating",
            text="What filtration rating (micron) is required?",
            why_asked="Mesh or element rating defines what passes downstream.",
            priority="high",
        ),
    ),
    (
        "strainer",
        RequiredField(
            field="filtration_rating",
            text="What strainer mesh size is required?",
            why_asked="Protects downstream equipment from debris.",
            priority="high",
        ),
    ),
    (
        "panel",
        RequiredField(
            field="supply_voltage",
            text="What supply voltage feeds this panel?",
            why_asked="Power distribution and breaker sizing depend on it.",
            priority="critical",
        ),
    ),
    (
        "plc",
        RequiredField(
            field="io_count",
            text="How many I/O points are required?",
            why_asked="PLC and rack sizing follow from I/O count.",
            priority="high",
            input_type="number",
        ),
    ),
    (
        "customer",
        RequiredField(
            field="request_summary",
            text="What is the customer asking for, in one sentence?",
            why_asked="Every request needs a clear ask before work can be scoped.",
            priority="critical",
        ),
    ),
    (
        "upgrade",
        RequiredField(
            field="existing_part_number",
            text="What exists today that will be changed?",
            why_asked="Upgrades are defined against what is installed now — not a guess.",
            priority="critical",
        ),
    ),
    (
        "document",
        RequiredField(
            field="deliverable_format",
            text="What format or channel is this content for?",
            why_asked="Structure and tone follow how the audience will consume it.",
            priority="critical",
        ),
    ),
)


def all_critical_field_names() -> frozenset[str]:
    """Every field marked critical anywhere in the built-in schema."""
    names: set[str] = set()
    for spec in COMMON:
        if spec.priority == "critical":
            names.add(spec.field)
    for specs in GOAL_FIELDS.values():
        for spec in specs:
            if spec.priority == "critical":
                names.add(spec.field)
    for _, spec in CATEGORY_FIELDS:
        if spec.priority == "critical":
            names.add(spec.field)
    from shared.field_registry import EXTRA_FIELDS

    for spec in EXTRA_FIELDS.values():
        if spec.priority == "critical":
            names.add(spec.field)
    return frozenset(names)


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
    field_order = {spec.field: index for index, spec in enumerate(specs)}
    goal_first = goal_field_names(goal)
    missing.sort(
        key=lambda spec: (
            0 if spec.field in goal_first else 1,
            PRIORITY_ORDER.get(spec.priority, 9),
            field_order.get(spec.field, 999),
        )
    )
    return missing[0] if missing else None


def status_for_score(completion_score: int, blocking: int) -> str:
    if completion_score >= 100 and blocking == 0:
        return "ready_to_generate"
    if blocking > 0:
        return "waiting_for_user"
    return "collecting_information"
