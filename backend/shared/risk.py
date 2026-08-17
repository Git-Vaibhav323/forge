"""Canonical risk classification — one list, used by every service.

Hold triggers follow the job schema (goal + work type + answers), not a fixed
industrial field list. Voltage and pressure still matter on plant jobs; platform
and scope matter on software and service jobs.
"""

from __future__ import annotations

from shared.completeness import all_critical_field_names

# Extraction-time fallback when full job context is unavailable.
HIGH_RISK_FIELDS: frozenset[str] = all_critical_field_names()

# Ranked worst-first so `max` comparisons read naturally.
SEVERITY_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")


def critical_fields_for_job(
    goal: str,
    category: str,
    answers: dict[str, str] | None = None,
) -> frozenset[str]:
    """Fields that must be sourced or explicitly decided before printing."""
    from shared.field_registry import active_required_fields

    specs = active_required_fields(goal, category, answers or {})
    return frozenset(spec.field for spec in specs if spec.priority == "critical")


def requires_review_hold(
    field: str,
    goal: str,
    category: str,
    answers: dict[str, str] | None = None,
) -> bool:
    return field in critical_fields_for_job(goal, category, answers)


def is_high_risk(field: str) -> bool:
    """True when a field can be critical on some job type (extraction fallback)."""
    return field in HIGH_RISK_FIELDS


def risk_for_field(
    field: str,
    *,
    goal: str = "",
    category: str = "",
    answers: dict[str, str] | None = None,
) -> str:
    """Baseline risk when we have no extraction-time signal (e.g. user answers)."""
    if goal and requires_review_hold(field, goal, category, answers):
        return "critical"
    return "critical" if is_high_risk(field) else "low"


def escalate(*severities: str) -> str:
    """Return the worst severity given. Unknown values are treated as `low`."""
    worst = 0
    for severity in severities:
        if severity in SEVERITY_ORDER:
            worst = max(worst, SEVERITY_ORDER.index(severity))
    return SEVERITY_ORDER[worst]
