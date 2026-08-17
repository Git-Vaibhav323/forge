from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from services.evidence_service.repository import run_extraction
from shared.db.models import CatalogLineRow, DocumentRow, ProjectRow

SEED = Path(__file__).resolve().parents[3] / "seed_data" / "Unihack_ Sample Dataset - Input.csv"


def test_extract_ingests_catalog_csv(db_session, monkeypatch) -> None:
    project = ProjectRow(
        id="prj-cat02",
        name="Unihack catalog",
        goal="technical_quotation",
        category="physical_product",
        status="draft",
    )
    doc = DocumentRow(
        id="doc-cat02",
        project_id=project.id,
        filename="Unihack_ Sample Dataset - Input.csv",
        type="catalog",
        status="processing",
        content_hash="seed",
        storage_key="seed-key",
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    db_session.add(doc)
    db_session.commit()

    monkeypatch.setattr(
        "services.evidence_service.repository._read_pdf_bytes",
        lambda _key: SEED.read_bytes(),
    )

    run_extraction(db_session, project)

    lines = db_session.query(CatalogLineRow).filter_by(project_id=project.id).all()
    assert len(lines) == 1000
    assert doc.status == "processed"
