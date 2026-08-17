from __future__ import annotations

import pytest

from shared.normalization import canonical_value, parse_quantity, values_agree


@pytest.mark.parametrize(
    "a_value,a_unit,b_value,b_unit",
    [
        ("285", "PSI", "19.649", "bar"),  # same pressure, two units
        ("10", "bar", "145", "psi"),  # published rounding
        ("100", "degC", "212", "degF"),  # temperature conversion
        ("285 PSI", None, "19.649 bar", None),  # unit inline in the value
        ("NPT", None, "npt", None),  # non-numeric, case-insensitive
    ],
)
def test_representation_differences_are_not_conflicts(a_value, a_unit, b_value, b_unit):
    assert values_agree(a_value, a_unit, b_value, b_unit) is True


@pytest.mark.parametrize(
    "a_value,a_unit,b_value,b_unit",
    [
        ("285", "PSI", "287", "PSI"),  # genuinely different numbers
        ("285", "PSI", "24", "V"),  # different dimensions
        ("NPT", None, "BSPP", None),  # different text
    ],
)
def test_value_differences_stay_conflicts(a_value, a_unit, b_value, b_unit):
    assert values_agree(a_value, a_unit, b_value, b_unit) is False


def test_ac_and_dc_at_same_magnitude_are_not_the_same_fact():
    # Pint only sees volts. On a safety-critical field this must stay a hold.
    assert values_agree("24", "VDC", "24", "VAC") is False
    assert values_agree("24", "VDC", "24", "VDC") is True


def test_unspecified_current_type_compares_on_magnitude():
    assert values_agree("24 VDC", None, "24", "V") is True


def test_same_unit_requires_exact_match_not_tolerance():
    # 0.5% slack applies only across a unit conversion, never within one unit.
    assert values_agree("1000", "psi", "1001", "psi") is False


def test_garbage_never_raises():
    assert values_agree("", None, "", None) is True
    assert values_agree("n/a", None, "285", "PSI") is False
    assert parse_quantity("no digits here", None) is None
    assert canonical_value("no digits here", None) is None


def test_canonical_value_collapses_units_to_a_common_base():
    assert canonical_value("285", "PSI") == canonical_value("19.6501", "bar")
