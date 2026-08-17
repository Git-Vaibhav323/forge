"""Deterministic compatibility rules (M6). Pure functions — no DB, no network.

A job carries two things for the same field:

  * the **requirement** — what the user answered on the Questions tab
    (stored as the `user-answer` evidence row), and
  * the **rating** — what the datasheet actually says
    (the document evidence rows, each with its own cited value).

A rule compares the two and returns `pass`, `fail`, or `unknown`. It never
invents the missing side and never guesses an order it cannot derive:
if either value is absent or not comparable, the rule **abstains**.

`fail` findings become review holds (see `shared/review_sync.py`). `unknown`
findings are recorded but never block — they are visible gaps, not verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from shared.normalization import compare_values, values_agree

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"

# How the rated value must relate to the required value.
AT_LEAST = "at_least"  # rating must meet or exceed the requirement
EXACT = "exact"  # rating must match the requirement
ABSTAIN = "abstain"  # not derivable from the data we hold


@dataclass(frozen=True)
class Rule:
    name: str
    field: str
    comparison: str
    severity: str
    requirement_label: str
    rating_label: str


# Only rules that can be decided from cited values live here. Anything needing
# a knowledge base we do not have (chemical resistance, certification scope) is
# declared ABSTAIN so the gap is recorded rather than silently assumed safe.
RULES: tuple[Rule, ...] = (
    Rule(
        name="pressure_rating",
        field="maximum_pressure",
        comparison=AT_LEAST,
        severity="critical",
        requirement_label="required working pressure",
        rating_label="rated pressure",
    ),
    Rule(
        name="temperature_rating",
        field="max_temperature",
        comparison=AT_LEAST,
        severity="high",
        requirement_label="required temperature",
        rating_label="rated temperature",
    ),
    Rule(
        name="supply_voltage_match",
        field="supply_voltage",
        comparison=EXACT,
        severity="critical",
        requirement_label="required supply voltage",
        rating_label="rated coil voltage",
    ),
    Rule(
        name="connection_match",
        field="connection_standard",
        comparison=EXACT,
        severity="high",
        requirement_label="required connection standard",
        rating_label="datasheet connection standard",
    ),
    Rule(
        name="chemical_compatibility",
        field="operating_medium",
        comparison=ABSTAIN,
        severity="critical",
        requirement_label="operating medium",
        rating_label="wetted materials",
    ),
)

RULES_BY_FIELD: dict[str, Rule] = {rule.field: rule for rule in RULES}


@dataclass(frozen=True)
class Side:
    """One half of a comparison, with the evidence that supports it."""

    value: str
    unit: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def display(self) -> str:
        return f"{self.value} {self.unit}".strip() if self.unit else self.value


@dataclass(frozen=True)
class Finding:
    rule: str
    field: str
    status: str
    severity: str
    required_value: str | None
    rated_value: str | None
    reason: str
    evidence_ids: tuple[str, ...] = dataclass_field(default_factory=tuple)


def _abstained(rule: Rule, required: Side | None, rated: Side | None, reason: str) -> Finding:
    return Finding(
        rule=rule.name,
        field=rule.field,
        status=UNKNOWN,
        severity=rule.severity,
        required_value=required.display() if required else None,
        rated_value=rated.display() if rated else None,
        reason=reason,
        evidence_ids=tuple(
            (required.evidence_ids if required else ()) + (rated.evidence_ids if rated else ())
        ),
    )


def evaluate(rule: Rule, required: Side | None, rated: Side | None) -> Finding:
    """Compare one requirement against one rating."""
    if rule.comparison == ABSTAIN:
        return _abstained(
            rule,
            required,
            rated,
            f"{rule.name.replace('_', ' ').capitalize()} cannot be decided from the "
            "sources on this job. It needs a materials statement, not an assumption.",
        )

    if required is None or not required.value.strip():
        return _abstained(
            rule, required, rated, f"No {rule.requirement_label} recorded yet."
        )
    if rated is None or not rated.value.strip():
        return _abstained(
            rule, required, rated, f"No {rule.rating_label} found in the sources."
        )

    evidence = tuple(required.evidence_ids + rated.evidence_ids)

    if rule.comparison == EXACT:
        if values_agree(required.value, required.unit, rated.value, rated.unit):
            return Finding(
                rule=rule.name,
                field=rule.field,
                status=PASS,
                severity=rule.severity,
                required_value=required.display(),
                rated_value=rated.display(),
                reason=f"{rule.rating_label.capitalize()} matches the requirement.",
                evidence_ids=evidence,
            )
        return Finding(
            rule=rule.name,
            field=rule.field,
            status=FAIL,
            severity=rule.severity,
            required_value=required.display(),
            rated_value=rated.display(),
            reason=(
                f"You asked for {required.display()} but the sources state "
                f"{rated.display()}. These are different parts, not two ways of "
                "writing one."
            ),
            evidence_ids=evidence,
        )

    # AT_LEAST — the rating must meet or exceed the requirement.
    order = compare_values(rated.value, rated.unit, required.value, required.unit)
    if order is None:
        return _abstained(
            rule,
            required,
            rated,
            f"Cannot compare {rated.display()} against {required.display()} — "
            "different quantities, so no order can be derived.",
        )
    if order >= 0:
        return Finding(
            rule=rule.name,
            field=rule.field,
            status=PASS,
            severity=rule.severity,
            required_value=required.display(),
            rated_value=rated.display(),
            reason=(
                f"{rule.rating_label.capitalize()} {rated.display()} meets the "
                f"required {required.display()}."
            ),
            evidence_ids=evidence,
        )
    return Finding(
        rule=rule.name,
        field=rule.field,
        status=FAIL,
        severity=rule.severity,
        required_value=required.display(),
        rated_value=rated.display(),
        reason=(
            f"{rule.rating_label.capitalize()} is {rated.display()}, below the "
            f"required {required.display()}. The selected item is under-rated for "
            "this duty."
        ),
        evidence_ids=evidence,
    )


def evaluate_all(
    requirements: dict[str, Side], ratings: dict[str, Side]
) -> list[Finding]:
    """Run every rule whose field is present on either side.

    Abstain-only rules (chemical compatibility) still need an operating medium
    on the job — they must not fire on techstack / software replacements.
    """
    findings: list[Finding] = []
    for rule in RULES:
        required = requirements.get(rule.field)
        rated = ratings.get(rule.field)
        if required is None and rated is None:
            continue
        findings.append(evaluate(rule, required, rated))
    return findings
