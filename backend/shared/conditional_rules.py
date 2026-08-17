"""Conditional field requirements (layer 2 of the hybrid question engine).

Fields activate when prior answers match — e.g. hazardous install → area class.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConditionalRule:
    when_field: str
    when_values: frozenset[str]
    require_fields: tuple[str, ...]


# Normalised to lowercase for comparison against user answers.
CONDITIONAL_RULES: tuple[ConditionalRule, ...] = (
    ConditionalRule(
        when_field="installation_environment",
        when_values=frozenset({"regulated / restricted", "hazardous area"}),
        require_fields=("hazardous_area_class",),
    ),
    ConditionalRule(
        when_field="operating_medium",
        when_values=frozenset({"physical environment", "steam", "chemical"}),
        require_fields=("max_temperature",),
    ),
    ConditionalRule(
        when_field="operating_medium",
        when_values=frozenset({"chemical"}),
        require_fields=("chemical_compatibility",),
    ),
    ConditionalRule(
        when_field="fail_safe_mode",
        when_values=frozenset(
            {"stay open (normally open)", "fail open", "keep last state"}
        ),
        require_fields=("return_spring_required",),
    ),
)
