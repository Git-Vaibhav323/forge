from __future__ import annotations

from datetime import datetime, timezone

from shared.brand_evaluator import CONFLICT, evaluate_part
from shared.catalog_parser import normalize_catalog_row
from shared.catalog_sync import sync_catalog_evaluation
from shared.db.models import CatalogLineRow, DocumentRow, ProjectRow


def test_sync_catalog_evaluation_persists_lines(db_session) -> None:
    project = ProjectRow(
        id="prj-cat01",
        name="Catalog eval",
        goal="technical_quotation",
        category="physical_product",
        status="draft",
    )
    doc = DocumentRow(
        id="doc-cat01",
        project_id=project.id,
        filename="catalog.csv",
        type="catalog",
        status="processing",
        content_hash="abc",
        storage_key="key",
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    db_session.add(doc)
    db_session.flush()

    part = normalize_catalog_row(
        2,
        {
            "Mfg_Part_Num": "543302126",
            "Part_Desc": "6' Wh Select T-Rail Kit",
            "E1_Brand": "TREX",
            "Unilog_Brand": "-- No Unilog Brand --",
            "DIB_Brand": "-- No DIB Brand --",
            "Part_Manuf": "U S Lumber (3073)",
        },
    )
    assert part is not None

    result = sync_catalog_evaluation(db_session, project, doc, [part])
    assert result.summary.total == 1

    rows = db_session.query(CatalogLineRow).filter_by(project_id=project.id).all()
    assert len(rows) == 1
    line = rows[0]
    assert line.mfg_part_num == "543302126"
    assert line.evaluation_status == "partial"
    assert line.recommended_brand == "TREX"
    assert doc.status == "processed"


def test_evaluate_part_flags_cross_column_conflict() -> None:
    part = normalize_catalog_row(
        2,
        {
            "Mfg_Part_Num": "X-1",
            "Part_Desc": "Sample part",
            "E1_Brand": "TREX",
            "Unilog_Brand": "TIMBERTECH",
            "DIB_Brand": "-- No DIB Brand --",
            "Part_Manuf": "Vendor (123)",
        },
    )
    assert part is not None
    ev = evaluate_part(part)
    assert ev.status == CONFLICT
    assert any(f.rule == "cross_column_conflict" for f in ev.findings)
