from __future__ import annotations

from services.evidence_service.extraction import merge_hits, parse_page

DATASHEET_A = """Meridian Flow Controls
Gate Valve Series — Product Datasheet
Model: MFC-GV-100
Nominal Size: 1"
Body Material: Ductile Iron
End Connection: Flanged (ANSI 125)
Max Working Pressure: 285 PSI
Max Temperature Rating: 200°C
Standard: API 600
Meridian Flow Controls — Page 1
"""

DATASHEET_B = """Meridian Flow Controls
Distributor Catalog Listing
Model: MFC-GV-100
Max Working Pressure: 300 PSI
Meridian Flow Controls — Page 1
"""


def _hits(text: str, doc_id: str, name: str):
    return parse_page(
        text=text, page=1, document_id=doc_id, document_name=name, document_type="pdf"
    )


def test_parse_page_reads_labelled_specs() -> None:
    hits = _hits(DATASHEET_A, "doc-a", "A.pdf")
    by_field = {h.field: h for h in hits}

    assert by_field["model"].raw_value == "MFC-GV-100"
    assert by_field["maximum_pressure"].normalized == "285"
    assert by_field["maximum_pressure"].unit == "PSI"
    assert by_field["max_temperature"].normalized == "200"
    assert "NPT" not in by_field["connection_standard"].raw_value  # Flanged, not NPT
    # every hit must carry the page + quote it came from
    assert by_field["maximum_pressure"].page == 1
    assert "285" in by_field["maximum_pressure"].quote


def test_never_invents_missing_field() -> None:
    hits = _hits(DATASHEET_A, "doc-a", "A.pdf")
    drafts = merge_hits(hits, required_fields=["supply_voltage"])
    voltage = next(d for d in drafts if d.name == "supply_voltage")
    assert voltage.status == "missing"
    assert voltage.raw_value == ""
    assert voltage.evidence == []


def test_agreeing_sources_raise_confidence() -> None:
    hits = _hits(DATASHEET_A, "doc-a", "A.pdf") + _hits(DATASHEET_A, "doc-b", "B.pdf")
    drafts = {d.name: d for d in merge_hits(hits, required_fields=[])}
    pressure = drafts["maximum_pressure"]
    assert pressure.status == "known"
    assert pressure.confidence >= 0.9
    assert len(pressure.evidence) == 2


def test_conflicting_sources_flagged_not_merged() -> None:
    hits = _hits(DATASHEET_A, "doc-a", "A.pdf") + _hits(DATASHEET_B, "doc-b", "B.pdf")
    drafts = {d.name: d for d in merge_hits(hits, required_fields=[])}
    pressure = drafts["maximum_pressure"]
    assert pressure.status == "conflicting"
    assert pressure.risk_level == "critical"
    assert pressure.normalized_value is None
    # both quotes are kept so a reviewer can see the disagreement
    assert len(pressure.evidence) == 2
    assert {"285", "300"} == {h.normalized for h in pressure.evidence}
