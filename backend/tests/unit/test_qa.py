from __future__ import annotations

from shared.qa import evaluate


def _clean():
    return evaluate(
        conflicting_fields=[],
        pending_holds=[],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=[],
    )


def test_a_clean_job_passes_with_no_notes():
    result = _clean()
    assert result.passed is True
    assert result.clean is True
    assert result.status == "qa_passed"
    assert result.notes == []


# ---------------------------------------------------------------------------
# Blockers — nothing may be printed
# ---------------------------------------------------------------------------


def test_unresolved_conflicts_block_generation():
    result = evaluate(
        conflicting_fields=["maximum_pressure"],
        pending_holds=[],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=[],
    )
    assert result.passed is False
    assert result.status == "qa_failed"
    assert "maximum_pressure" in result.blockers[0]


def test_pending_holds_block_generation():
    result = evaluate(
        conflicting_fields=[],
        pending_holds=["supply_voltage"],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=[],
    )
    assert result.passed is False
    assert "must be answered by a person" in result.blockers[0]


def test_every_blocker_is_reported_not_just_the_first():
    result = evaluate(
        conflicting_fields=["maximum_pressure"],
        pending_holds=["supply_voltage"],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=[],
    )
    assert len(result.blockers) == 2


# ---------------------------------------------------------------------------
# Warnings — printable, but the document says what is missing
# ---------------------------------------------------------------------------


def test_gaps_warn_but_do_not_block():
    result = evaluate(
        conflicting_fields=[],
        pending_holds=[],
        missing_fields=["connection_standard"],
        unverified_fields=[],
        abstained_rules=[],
    )
    assert result.passed is True
    assert result.clean is False
    assert result.status == "generated"
    assert "connection_standard" in result.warnings[0]


def test_photo_only_values_are_flagged_on_the_artifact():
    result = evaluate(
        conflicting_fields=[],
        pending_holds=[],
        missing_fields=[],
        unverified_fields=["model"],
        abstained_rules=[],
    )
    assert result.passed is True
    assert "single unconfirmed reading" in result.warnings[0]


def test_abstained_compatibility_rules_are_carried_onto_the_output():
    result = evaluate(
        conflicting_fields=[],
        pending_holds=[],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=["chemical_compatibility"],
    )
    assert result.passed is True
    assert "could not be decided" in result.warnings[0]


def test_unresolved_bom_lines_warn():
    result = evaluate(
        conflicting_fields=[],
        pending_holds=[],
        missing_fields=[],
        unverified_fields=[],
        abstained_rules=[],
        unresolved_bom_lines=3,
    )
    assert result.passed is True
    assert "3 BOM lines" in result.warnings[0]


def test_blockers_come_before_warnings_in_the_notes():
    result = evaluate(
        conflicting_fields=["maximum_pressure"],
        pending_holds=[],
        missing_fields=["model"],
        unverified_fields=[],
        abstained_rules=[],
    )
    assert result.notes[0] == result.blockers[0]
    assert result.notes[-1] == result.warnings[-1]


def test_singular_and_plural_read_correctly():
    one = evaluate(
        conflicting_fields=["a"], pending_holds=[], missing_fields=[],
        unverified_fields=[], abstained_rules=[],
    )
    two = evaluate(
        conflicting_fields=["a", "b"], pending_holds=[], missing_fields=[],
        unverified_fields=[], abstained_rules=[],
    )
    assert "1 field still" in one.blockers[0]
    assert "2 fields still" in two.blockers[0]
