"""Central field registry (layer 1) — single source for completeness + evidence."""

from __future__ import annotations

from shared.completeness import GOAL_FIELDS, RequiredField, _select
from shared.conditional_rules import CONDITIONAL_RULES

# Fields only required when conditional rules fire (not in base goal/common lists).
EXTRA_FIELDS: dict[str, RequiredField] = {
    "hazardous_area_class": _select(
        "hazardous_area_class",
        "What hazardous-area classification applies (e.g. Zone 1, Div 2)?",
        "Enclosure and cert selection depend on the area class.",
        "critical",
        "Zone 0",
        "Zone 1",
        "Zone 2",
        "Div 1",
        "Div 2",
        "Not classified",
    ),
    "max_temperature": RequiredField(
        field="max_temperature",
        text="What maximum fluid or ambient temperature must the product handle?",
        why_asked="Steam and chemical service need explicit temperature limits.",
        priority="critical",
    ),
    "chemical_compatibility": RequiredField(
        field="chemical_compatibility",
        text="Which chemical(s) will contact wetted parts?",
        why_asked="Seal and body material must be checked against the chemical.",
        priority="critical",
    ),
    "return_spring_required": _select(
        "return_spring_required",
        "Is a return spring required for fail-open operation?",
        "Normally-open actuators need a defined return mechanism.",
        "high",
        "Yes — spring return",
        "No — external force",
        "Not applicable",
    ),
}


def _normalise_answer(value: str | None) -> str:
    return (value or "").strip().lower()


def active_required_fields(
    goal: str, category: str, answers: dict[str, str]
) -> list[RequiredField]:
    """Merge base schema + category extras + conditionally activated fields."""
    from shared.completeness import required_fields

    merged: dict[str, RequiredField] = {
        spec.field: spec for spec in required_fields(goal, category)
    }

    for rule in CONDITIONAL_RULES:
        raw = answers.get(rule.when_field)
        if raw is None:
            continue
        if _normalise_answer(raw) not in rule.when_values:
            continue
        for field_name in rule.require_fields:
            extra = EXTRA_FIELDS.get(field_name)
            if extra is not None:
                merged.setdefault(field_name, extra)

    return list(merged.values())
