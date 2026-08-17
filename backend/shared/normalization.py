"""Unit normalization (M5). Pint-backed, defensive, never raises.

Purpose: tell a *representation* difference from a *value* difference.
"285 PSI" and "19.65 bar" are the same physical pressure written two ways —
that is not a conflict and must not waste a reviewer's decision. "285 PSI" and
"287 PSI" ARE different numbers from two sources and must stay `conflicting`.

Normalization is explicitly allowed to run without human approval
(context.md → governance rule). Deciding between two genuinely different
values is not — that always becomes a review item.

Every entry point returns None / False rather than raising, so a malformed
datasheet string can never break extraction or the review queue.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

# A conversion between units carries rounding from whoever published the
# catalog (10 bar printed as "145 psi" is really 145.038). Allow that much
# slack ONLY when the units differ.
CONVERSION_TOLERANCE = 0.005  # 0.5%

# Datasheet spellings → Pint unit names.
_UNIT_ALIASES: dict[str, str] = {
    "psi": "psi",
    "psig": "psi",
    "bar": "bar",
    "bars": "bar",
    "kpa": "kPa",
    "mpa": "MPa",
    "pa": "Pa",
    "v": "volt",
    "vac": "volt",
    "vdc": "volt",
    "volt": "volt",
    "volts": "volt",
    "kv": "kilovolt",
    "c": "degC",
    "°c": "degC",
    "degc": "degC",
    "f": "degF",
    "°f": "degF",
    "degf": "degF",
    "k": "kelvin",
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "in": "inch",
    "inch": "inch",
    "inches": "inch",
    '"': "inch",
}

_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")

# AC and DC at the same magnitude are DIFFERENT facts, not two spellings of
# one. Pint only sees volts, so current type is compared separately.
_AC = re.compile(r"\b(?:ac|vac|alternating)\b|(?<=\d)\s*vac\b", re.IGNORECASE)
_DC = re.compile(r"\b(?:dc|vdc|direct)\b|(?<=\d)\s*vdc\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _registry() -> Any | None:
    """Build the Pint registry once.

    Returns None if Pint is missing OR fails to import — some Pint/flexparser
    version pairs raise TypeError at import time. Degrading to string
    comparison is always safe here; crashing the review queue is not.
    """
    try:
        from pint import UnitRegistry

        return UnitRegistry()
    except Exception:  # pragma: no cover - depends on installed pint build
        return None


def _clean_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().lower().replace(" ", "")
    token = token.replace("degrees", "deg").replace("º", "°")
    return _UNIT_ALIASES.get(token)


def _split(raw_value: str, unit: str | None) -> tuple[float, str | None] | None:
    """Pull a magnitude and a Pint unit name out of a datasheet string."""
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None

    match = _NUMBER.search(text.replace(",", ""))
    if not match:
        return None
    try:
        magnitude = float(match.group(0))
    except ValueError:
        return None

    # Prefer a unit written inline with the value; fall back to the column unit.
    trailing = text.replace(",", "")[match.end():].strip()
    resolved = _clean_unit(trailing) or _clean_unit(unit)
    return magnitude, resolved


def parse_quantity(raw_value: str, unit: str | None = None) -> Any | None:
    """Return a Pint Quantity, or None when the text is not a measurement."""
    registry = _registry()
    if registry is None:
        return None
    parts = _split(raw_value, unit)
    if parts is None:
        return None
    magnitude, unit_name = parts
    if unit_name is None:
        return None
    try:
        return registry.Quantity(magnitude, unit_name)
    except Exception:
        return None


def canonical_value(raw_value: str, unit: str | None = None) -> str | None:
    """Human-readable normalized form, e.g. '285 psi' → '19.649 bar'. Display only."""
    quantity = parse_quantity(raw_value, unit)
    if quantity is None:
        return None
    try:
        base = quantity.to_base_units()
        return f"{base.magnitude:.6g} {base.units:~P}"
    except Exception:
        return None


def values_agree(
    a_value: str,
    a_unit: str | None,
    b_value: str,
    b_unit: str | None,
) -> bool:
    """True when two source values are the same fact written differently.

    Same unit  → requires the same number (285 psi != 287 psi).
    Diff unit  → converts, then allows published-rounding slack.
    Non-numeric → case/whitespace-insensitive string equality.
    """
    # 24 VDC vs 24 VAC must stay a conflict on a safety-critical field.
    left_type = _current_type(a_value, a_unit)
    right_type = _current_type(b_value, b_unit)
    if left_type and right_type and left_type != right_type:
        return False

    left = parse_quantity(a_value, a_unit)
    right = parse_quantity(b_value, b_unit)

    if left is None or right is None:
        return _text_equal(a_value, b_value)

    try:
        if left.units == right.units:
            return left.magnitude == right.magnitude
        converted = right.to(left.units)
    except Exception:
        # Different dimensions (psi vs volt) are a real disagreement, not an error.
        return False

    scale = max(abs(left.magnitude), abs(converted.magnitude))
    if scale == 0:
        return abs(left.magnitude - converted.magnitude) < 1e-9
    return abs(left.magnitude - converted.magnitude) / scale <= CONVERSION_TOLERANCE


def compare_values(
    a_value: str,
    a_unit: str | None,
    b_value: str,
    b_unit: str | None,
) -> int | None:
    """Order two measurements: -1 if a < b, 0 if equal, 1 if a > b.

    Returns None when they are not comparable (unparseable, different
    dimensions, or different current type) — the caller must then abstain
    rather than assume an order.
    """
    if _current_type(a_value, a_unit) and _current_type(b_value, b_unit):
        if _current_type(a_value, a_unit) != _current_type(b_value, b_unit):
            return None

    left = parse_quantity(a_value, a_unit)
    right = parse_quantity(b_value, b_unit)
    if left is None or right is None:
        return None

    try:
        converted = right.to(left.units)
    except Exception:
        return None

    if values_agree(a_value, a_unit, b_value, b_unit):
        return 0
    return -1 if left.magnitude < converted.magnitude else 1


def _current_type(raw_value: str, unit: str | None) -> str | None:
    """Return 'ac', 'dc', or None when the text does not say."""
    text = f"{raw_value or ''} {unit or ''}"
    has_dc = bool(_DC.search(text))
    has_ac = bool(_AC.search(text))
    if has_dc and not has_ac:
        return "dc"
    if has_ac and not has_dc:
        return "ac"
    return None


def _text_equal(a_value: str, b_value: str) -> bool:
    return " ".join(str(a_value).lower().split()) == " ".join(str(b_value).lower().split())
