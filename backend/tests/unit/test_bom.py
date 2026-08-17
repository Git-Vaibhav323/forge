from __future__ import annotations

from shared.bom import (
    MISSING,
    RESOLVED,
    UNVERIFIED,
    Component,
    resolve_lines,
    unresolved_count,
)


def _known(**values: str) -> dict[str, Component]:
    return {name: Component(value=value) for name, value in values.items()}


def test_non_bom_goals_produce_no_lines():
    assert resolve_lines("product_datasheet", _known(model="MFC-GV-100")) == []
    assert resolve_lines("rfq_response", _known(model="MFC-GV-100")) == []


def test_primary_line_is_named_from_cited_identity():
    lines = resolve_lines(
        "bom_generation",
        _known(manufacturer="Meridian", model="MFC-GV-100"),
        quantity="4",
    )
    primary = lines[0]
    assert primary.role == "primary"
    assert primary.component == "Meridian MFC-GV-100"
    assert primary.status == RESOLVED
    assert primary.quantity == "4"


def test_partial_identity_is_flagged_not_invented():
    lines = resolve_lines("bom_generation", _known(model="MFC-GV-100"))
    primary = lines[0]
    assert primary.status == UNVERIFIED
    assert "manufacturer" in primary.reason
    # The known half is still used — abstaining does not mean discarding.
    assert primary.component == "MFC-GV-100"


def test_no_identity_yields_a_named_gap_not_a_dropped_line():
    lines = resolve_lines("bom_generation", {})
    primary = lines[0]
    assert primary.status == MISSING
    assert primary.component == "Unidentified item"


def test_unestablished_specs_appear_as_missing_lines():
    lines = resolve_lines(
        "bom_generation", _known(manufacturer="Meridian", model="MFC-GV-100")
    )
    specs = [line for line in lines if line.role == "specification"]
    assert specs, "spec lines must be emitted even when nothing is known"
    assert all(line.status == MISSING for line in specs)
    # A BOM that silently omits what it could not resolve is worse than one
    # that names the gap.
    assert all("not established" in line.component for line in specs)


def test_known_specs_are_cited():
    lines = resolve_lines(
        "bom_generation",
        {
            "manufacturer": Component("Meridian"),
            "model": Component("MFC-GV-100"),
            "connection_standard": Component("NPT", evidence_ids=("ev-1",)),
            "maximum_pressure": Component("285", unit="PSI", evidence_ids=("ev-2",)),
        },
    )
    by_field = {line.source_field: line for line in lines}
    assert by_field["connection_standard"].status == RESOLVED
    assert by_field["connection_standard"].component == "connection standard: NPT"
    assert by_field["maximum_pressure"].component == "maximum pressure: 285 PSI"
    assert by_field["maximum_pressure"].evidence_ids == ("ev-2",)


def test_positions_are_unique_and_sequential():
    lines = resolve_lines(
        "product_configuration", _known(manufacturer="Meridian", model="MFC-GV-100")
    )
    positions = [line.position for line in lines]
    assert positions == list(range(1, len(lines) + 1))


def test_unresolved_count_reports_the_gaps():
    lines = resolve_lines("bom_generation", {})
    assert unresolved_count(lines) == sum(1 for a in lines if a.status == MISSING)
    assert unresolved_count(lines) > 0
