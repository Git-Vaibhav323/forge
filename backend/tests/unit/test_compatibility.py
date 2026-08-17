from __future__ import annotations

from shared.compatibility import (
    FAIL,
    PASS,
    RULES_BY_FIELD,
    UNKNOWN,
    Side,
    evaluate,
    evaluate_all,
)

PRESSURE = RULES_BY_FIELD["maximum_pressure"]
VOLTAGE = RULES_BY_FIELD["supply_voltage"]
CONNECTION = RULES_BY_FIELD["connection_standard"]
MEDIUM = RULES_BY_FIELD["operating_medium"]


# ---------------------------------------------------------------------------
# at_least rules
# ---------------------------------------------------------------------------


def test_rating_below_requirement_fails():
    finding = evaluate(
        PRESSURE, Side("300", "PSI"), Side("285", "PSI")
    )
    assert finding.status == FAIL
    assert finding.severity == "critical"
    assert "285 PSI" in finding.reason and "300 PSI" in finding.reason


def test_rating_above_requirement_passes():
    assert evaluate(PRESSURE, Side("200", "PSI"), Side("285", "PSI")).status == PASS


def test_rating_exactly_meeting_requirement_passes():
    assert evaluate(PRESSURE, Side("285", "PSI"), Side("285", "PSI")).status == PASS


def test_comparison_works_across_units():
    # 285 psi is about 19.65 bar, comfortably above a 10 bar duty.
    assert evaluate(PRESSURE, Side("10", "bar"), Side("285", "PSI")).status == PASS
    # ...and below a 30 bar duty.
    assert evaluate(PRESSURE, Side("30", "bar"), Side("285", "PSI")).status == FAIL


def test_incomparable_quantities_abstain_rather_than_fail():
    finding = evaluate(PRESSURE, Side("300", "PSI"), Side("24", "V"))
    assert finding.status == UNKNOWN
    assert "no order can be derived" in finding.reason


# ---------------------------------------------------------------------------
# exact rules
# ---------------------------------------------------------------------------


def test_matching_connection_standard_passes():
    assert evaluate(CONNECTION, Side("NPT"), Side("npt")).status == PASS


def test_mismatched_connection_standard_fails():
    finding = evaluate(CONNECTION, Side("NPT"), Side("BSPP"))
    assert finding.status == FAIL
    assert finding.severity == "high"


def test_ac_dc_mismatch_fails_even_at_the_same_magnitude():
    finding = evaluate(VOLTAGE, Side("24", "VDC"), Side("24", "VAC"))
    assert finding.status == FAIL
    assert finding.severity == "critical"


def test_matching_voltage_passes():
    assert evaluate(VOLTAGE, Side("24", "VDC"), Side("24", "VDC")).status == PASS


# ---------------------------------------------------------------------------
# Abstention — the rules that must never guess
# ---------------------------------------------------------------------------


def test_missing_rating_abstains():
    finding = evaluate(PRESSURE, Side("300", "PSI"), None)
    assert finding.status == UNKNOWN
    assert finding.rated_value is None


def test_missing_requirement_abstains():
    finding = evaluate(PRESSURE, None, Side("285", "PSI"))
    assert finding.status == UNKNOWN
    assert finding.required_value is None


def test_blank_values_abstain():
    assert evaluate(PRESSURE, Side("   "), Side("285", "PSI")).status == UNKNOWN


def test_chemical_compatibility_always_abstains():
    """There is no materials knowledge base behind this, so it must not verdict."""
    finding = evaluate(MEDIUM, Side("Steam"), Side("Brass"))
    assert finding.status == UNKNOWN
    assert finding.severity == "critical"


# ---------------------------------------------------------------------------
# evaluate_all
# ---------------------------------------------------------------------------


def test_evaluate_all_skips_rules_with_no_data_on_either_side():
    findings = evaluate_all(
        {"maximum_pressure": Side("300", "PSI")},
        {"maximum_pressure": Side("285", "PSI")},
    )
    rules = {f.rule for f in findings}
    # chemical_compatibility always reports (as an abstention); the rest only
    # appear when the job has something to say about them.
    assert rules == {"pressure_rating", "chemical_compatibility"}


def test_evaluate_all_carries_evidence_from_both_sides():
    findings = evaluate_all(
        {"maximum_pressure": Side("300", "PSI", ("ev-req",))},
        {"maximum_pressure": Side("285", "PSI", ("ev-doc",))},
    )
    pressure = next(f for f in findings if f.rule == "pressure_rating")
    assert set(pressure.evidence_ids) == {"ev-req", "ev-doc"}
