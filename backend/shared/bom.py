"""BOM / configuration line resolution (M6). Pure functions — no DB.

A BOM line is only ever built from something the job can cite: an extracted
attribute or an answer the user typed. There is no parts catalog behind this,
so the resolver does exactly two things:

  * emit a line for each component it CAN identify, carrying its evidence, and
  * emit a `missing` line for each component the goal requires but nothing
    supports.

A missing line is the point. A BOM that quietly drops the component it could
not resolve is worse than one that names the gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

RESOLVED = "resolved"
MISSING = "missing"
UNVERIFIED = "unverified"

PRIMARY = "primary"
SPECIFICATION = "specification"

# Goals that produce a parts breakdown at all.
BOM_GOALS: frozenset[str] = frozenset({"bom_generation", "product_configuration"})

# Fields that describe the primary item's identity, in display order.
IDENTITY_FIELDS: tuple[str, ...] = ("manufacturer", "model")

# Fields that qualify the primary line and must appear on the BOM if known.
# Each is a real field from shared/completeness.py — none are invented here.
SPEC_FIELDS: tuple[str, ...] = (
    "connection_standard",
    "supply_voltage",
    "maximum_pressure",
    "max_temperature",
    "fail_safe_mode",
)


@dataclass(frozen=True)
class Component:
    """A resolved attribute the BOM can cite."""

    value: str
    unit: str | None = None
    status: str = RESOLVED
    evidence_ids: tuple[str, ...] = ()

    def display(self) -> str:
        return f"{self.value} {self.unit}".strip() if self.unit else self.value


@dataclass(frozen=True)
class BomLine:
    position: int
    role: str
    component: str
    quantity: str | None
    unit: str | None
    status: str
    source_field: str | None
    reason: str
    evidence_ids: tuple[str, ...] = dataclass_field(default_factory=tuple)


def _identity(known: dict[str, Component]) -> tuple[str, tuple[str, ...], str]:
    """Build the primary item's name from whatever identity fields are cited."""
    parts: list[str] = []
    evidence: list[str] = []
    missing: list[str] = []
    for field_name in IDENTITY_FIELDS:
        component = known.get(field_name)
        if component and component.value.strip():
            parts.append(component.display())
            evidence.extend(component.evidence_ids)
        else:
            missing.append(field_name)
    return " ".join(parts), tuple(evidence), ", ".join(missing)


def resolve_lines(
    goal: str,
    known: dict[str, Component],
    quantity: str | None = None,
) -> list[BomLine]:
    """Return the BOM for a job, gaps included."""
    if goal not in BOM_GOALS:
        return []

    lines: list[BomLine] = []
    position = 1

    name, evidence, missing_identity = _identity(known)
    if name:
        lines.append(
            BomLine(
                position=position,
                role=PRIMARY,
                component=name,
                quantity=quantity,
                unit=None,
                status=RESOLVED if not missing_identity else UNVERIFIED,
                source_field="model",
                reason=(
                    "Identified from cited sources."
                    if not missing_identity
                    else f"Partly identified — no {missing_identity} on the record."
                ),
                evidence_ids=evidence,
            )
        )
    else:
        lines.append(
            BomLine(
                position=position,
                role=PRIMARY,
                component="Unidentified item",
                quantity=quantity,
                unit=None,
                status=MISSING,
                source_field="model",
                reason=(
                    "No manufacturer or model on the record. The primary line "
                    "cannot be named without one."
                ),
                evidence_ids=(),
            )
        )
    position += 1

    for field_name in SPEC_FIELDS:
        component = known.get(field_name)
        label = field_name.replace("_", " ")
        if component and component.value.strip():
            lines.append(
                BomLine(
                    position=position,
                    role=SPECIFICATION,
                    component=f"{label}: {component.display()}",
                    quantity=None,
                    unit=component.unit,
                    status=component.status,
                    source_field=field_name,
                    reason="Cited on the record.",
                    evidence_ids=component.evidence_ids,
                )
            )
        else:
            lines.append(
                BomLine(
                    position=position,
                    role=SPECIFICATION,
                    component=f"{label}: not established",
                    quantity=None,
                    unit=None,
                    status=MISSING,
                    source_field=field_name,
                    reason=(
                        f"No source states the {label}. Left as a gap rather than "
                        "filled from a default."
                    ),
                    evidence_ids=(),
                )
            )
        position += 1

    return lines


def unresolved_count(lines: list[BomLine]) -> int:
    return sum(1 for line in lines if line.status == MISSING)
