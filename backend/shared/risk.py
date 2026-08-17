"""Canonical risk classification — one list, used by every service.

The governance rule in context.md is non-negotiable: conflicts, high-risk
fields (voltage, pressure, temperature, chemical compatibility, safety certs),
bulk corrections, and published-data changes ALWAYS pause for a human.

Before this module the high-risk set was duplicated in
`services/evidence_service/extraction.py` (extraction-time, tied to
FIELD_SPECS) and `shared/record_sync.py`. `record_sync` and review-service now
share the list below; `extraction.HIGH_RISK` stays separate because it is
scoped to the regex specs it sits next to.
"""

from __future__ import annotations

# Fields that always require a human decision when they conflict or are absent.
HIGH_RISK_FIELDS: frozenset[str] = frozenset(
    {
        "maximum_pressure",
        "supply_voltage",
        "max_temperature",
        "connection_standard",
        "hazardous_area_class",
        "chemical_compatibility",
    }
)

# Ranked worst-first so `max` comparisons read naturally.
SEVERITY_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")


def is_high_risk(field: str) -> bool:
    return field in HIGH_RISK_FIELDS


def risk_for_field(field: str) -> str:
    """Baseline risk when we have no extraction-time signal (e.g. user answers)."""
    return "critical" if is_high_risk(field) else "low"


def escalate(*severities: str) -> str:
    """Return the worst severity given. Unknown values are treated as `low`."""
    worst = 0
    for severity in severities:
        if severity in SEVERITY_ORDER:
            worst = max(worst, SEVERITY_ORDER.index(severity))
    return SEVERITY_ORDER[worst]
