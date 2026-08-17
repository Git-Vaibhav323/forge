from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import DocumentRow, ProjectRow

DATASHEET_A = """Meridian Flow Controls
Gate Valve Series — Product Datasheet
Model: MFC-GV-100
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


def _seed(db_session: Session) -> str:
    now = datetime.now(timezone.utc)
    db_session.add(
        ProjectRow(
            id="prj-ev01",
            name="Gate valve datasheet",
            goal="product_datasheet",
            category="valve",
            status="draft",
            completion_score=0,
            blocking_fields_count=0,
            conflicts_count=0,
            pending_approvals_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    # storage_key carries the page text so the stubbed reader can route it.
    for idx, text in ((1, DATASHEET_A), (2, DATASHEET_B)):
        db_session.add(
            DocumentRow(
                id=f"doc-ev{idx}",
                project_id="prj-ev01",
                filename=f"sheet_{idx}.pdf",
                type="pdf",
                status="pending",
                storage_key=text,
                content_hash=f"hash-{idx}",
                uploaded_at=now,
            )
        )
    db_session.commit()
    return "prj-ev01"


@pytest.fixture(autouse=True)
def _stub_pdf_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid needing pypdf or object storage: treat the storage_key as raw
    # bytes and the "PDF" as a single page of that text.
    monkeypatch.setattr(
        "services.evidence_service.repository._read_pdf_bytes",
        lambda storage_key: storage_key.encode("utf-8"),
    )
    monkeypatch.setattr(
        "services.evidence_service.repository.extract_pages_from_pdf",
        lambda data: [data.decode("utf-8")],
    )


def test_attributes_empty_before_extract(
    evidence_client: TestClient, db_session: Session
) -> None:
    project_id = _seed(db_session)
    body = evidence_client.get(f"/api/projects/{project_id}/attributes").json()
    assert body == []


def test_extract_cites_fields_and_flags_conflict(
    evidence_client: TestClient, db_session: Session
) -> None:
    project_id = _seed(db_session)
    resp = evidence_client.post(f"/api/projects/{project_id}/attributes/extract")
    assert resp.status_code == 200
    attrs = {a["name"]: a for a in resp.json()}

    model = attrs["model"]
    assert model["rawValue"] == "MFC-GV-100"
    assert model["status"] == "known"
    assert len(model["evidence"]) == 2
    assert model["evidence"][0]["page"] == 1
    assert model["evidence"][0]["quote"]

    pressure = attrs["maximum_pressure"]
    assert pressure["status"] == "conflicting"
    assert pressure["riskLevel"] == "critical"
    assert len(pressure["evidence"]) == 2

    db_session.expire_all()
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    assert project.conflicts_count == 1


def test_extract_is_idempotent(
    evidence_client: TestClient, db_session: Session
) -> None:
    project_id = _seed(db_session)
    first = evidence_client.post(f"/api/projects/{project_id}/attributes/extract").json()
    second = evidence_client.post(f"/api/projects/{project_id}/attributes/extract").json()
    assert len(first) == len(second)
    # a re-scan replaces rows, it does not accumulate duplicates
    stored = evidence_client.get(f"/api/projects/{project_id}/attributes").json()
    assert len(stored) == len(second)


def test_extract_from_web_document(
    evidence_client: TestClient, db_session: Session
) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        ProjectRow(
            id="prj-evweb",
            name="Web extract",
            goal="product_datasheet",
            category="valve",
            status="draft",
            completion_score=0,
            blocking_fields_count=0,
            conflicts_count=0,
            pending_approvals_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    html = """<html><body>
      <p>Model: WEB-99</p>
      <p>Max Working Pressure: 150 PSI</p>
    </body></html>"""
    db_session.add(
        DocumentRow(
            id="doc-web1",
            project_id="prj-evweb",
            filename="catalog.example.com_valve.html",
            type="web",
            status="pending",
            storage_key=html,
            content_hash="hash-web",
            source_url="https://catalog.example.com/valve",
            uploaded_at=now,
        )
    )
    db_session.commit()

    resp = evidence_client.post("/api/projects/prj-evweb/attributes/extract")
    assert resp.status_code == 200
    attrs = {a["name"]: a for a in resp.json()}
    assert attrs["model"]["rawValue"] == "WEB-99"
    assert attrs["model"]["status"] == "known"
    assert attrs["model"]["evidence"][0]["documentType"] == "web"
    assert attrs["model"]["evidence"][0]["documentName"] == "https://catalog.example.com/valve"
    assert attrs["maximum_pressure"]["rawValue"] == "150"
