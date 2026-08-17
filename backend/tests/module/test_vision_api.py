from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import DocumentRow, ProjectRow

NOW = datetime.now(timezone.utc)

# What OCR would return from a photo of the valve's nameplate.
NAMEPLATE = """Meridian Flow Controls
Model: MFC-GV-100
Max Working Pressure: 285 PSI
Supply Voltage: 24 VDC
Meridian Flow Controls - Page 1
"""

# The same plate, misread as a higher pressure than the datasheet states.
NAMEPLATE_DISAGREEING = """Meridian Flow Controls
Model: MFC-GV-100
Max Working Pressure: 300 PSI
Meridian Flow Controls - Page 1
"""

DATASHEET = """Meridian Flow Controls
Gate Valve Series - Product Datasheet
Model: MFC-GV-100
Max Working Pressure: 285 PSI
Meridian Flow Controls - Page 1
"""


def _project(db: Session, project_id: str) -> ProjectRow:
    row = ProjectRow(
        id=project_id,
        name=f"Job {project_id}",
        goal="product_datasheet",
        category="valve",
        status="draft",
        completion_score=0,
        blocking_fields_count=0,
        conflicts_count=0,
        pending_approvals_count=0,
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(row)
    return row


def _document(
    db: Session,
    project_id: str,
    doc_id: str,
    *,
    text: str,
    doc_type: str,
    filename: str,
) -> None:
    # storage_key carries the content, as in tests/module/test_evidence_api.py.
    db.add(
        DocumentRow(
            id=doc_id,
            project_id=project_id,
            filename=filename,
            type=doc_type,
            status="pending",
            storage_key=text,
            content_hash=f"hash-{doc_id}",
            uploaded_at=NOW,
        )
    )


@pytest.fixture
def _ocr_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn OCR on and treat the stored bytes as the text a reader would return."""
    monkeypatch.setattr("services.evidence_service.repository.ocr_enabled", lambda: True)
    monkeypatch.setattr(
        "services.evidence_service.repository.read_image_text",
        lambda data, filename="": [data.decode("utf-8")],
    )
    monkeypatch.setattr(
        "services.evidence_service.repository._read_pdf_bytes",
        lambda storage_key: storage_key.encode("utf-8"),
    )
    monkeypatch.setattr(
        "services.evidence_service.repository.extract_pages_from_pdf",
        lambda data: [data.decode("utf-8")],
    )


# ---------------------------------------------------------------------------
# The service surface
# ---------------------------------------------------------------------------


def test_status_reports_ocr_off_by_default(vision_client: TestClient) -> None:
    body = vision_client.get("/api/vision/status").json()
    assert body["provider"] == "off"
    assert body["enabled"] is False
    assert "image" in body["imageTypes"]


def test_images_endpoint_lists_only_images(
    vision_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-vis01")
    _document(
        db_session, "prj-vis01", "doc-img", text=NAMEPLATE, doc_type="image",
        filename="plate.jpg",
    )
    _document(
        db_session, "prj-vis01", "doc-pdf", text=DATASHEET, doc_type="pdf",
        filename="sheet.pdf",
    )
    db_session.commit()

    body = vision_client.get("/api/projects/prj-vis01/images").json()
    assert [d["id"] for d in body] == ["doc-img"]


def test_reading_an_image_with_ocr_off_says_so_instead_of_failing(
    vision_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-vis02")
    _document(
        db_session, "prj-vis02", "doc-img2", text=NAMEPLATE, doc_type="image",
        filename="plate.jpg",
    )
    db_session.commit()

    body = vision_client.post(
        "/api/projects/prj-vis02/images/doc-img2/read"
    ).json()
    assert body["pages"] == []
    assert body["provider"] == "off"
    assert "no facts are inferred" in body["note"]


def test_reading_a_non_image_is_refused(
    vision_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-vis03")
    _document(
        db_session, "prj-vis03", "doc-pdf3", text=DATASHEET, doc_type="pdf",
        filename="sheet.pdf",
    )
    db_session.commit()

    response = vision_client.post("/api/projects/prj-vis03/images/doc-pdf3/read")
    assert response.status_code == 422


def test_reading_an_unknown_image_is_404(
    vision_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-vis04")
    db_session.commit()
    assert (
        vision_client.post("/api/projects/prj-vis04/images/doc-nope/read").status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Done when: "a nameplate photo can fill or conflict with datasheet fields,
# citing the image"
# ---------------------------------------------------------------------------


def test_a_photo_alone_produces_unverified_facts_citing_the_image(
    evidence_client: TestClient, db_session: Session, _ocr_on: None
) -> None:
    _project(db_session, "prj-vis05")
    _document(
        db_session, "prj-vis05", "doc-plate", text=NAMEPLATE, doc_type="image",
        filename="nameplate.jpg",
    )
    db_session.commit()

    body = evidence_client.post(
        "/api/projects/prj-vis05/attributes/extract"
    ).json()
    by_name = {a["name"]: a for a in body}

    pressure = by_name["maximum_pressure"]
    # A single OCR read is a reading, not an established fact.
    assert pressure["status"] == "unverified"
    assert pressure["confidence"] == 0.6
    # ...and it cites the photo it came from.
    assert pressure["evidence"][0]["documentName"] == "nameplate.jpg"
    assert pressure["evidence"][0]["documentType"] == "image"
    assert "285" in pressure["evidence"][0]["quote"]


def test_a_photo_agreeing_with_the_datasheet_confirms_the_field(
    evidence_client: TestClient, db_session: Session, _ocr_on: None
) -> None:
    _project(db_session, "prj-vis06")
    _document(
        db_session, "prj-vis06", "doc-sheet6", text=DATASHEET, doc_type="pdf",
        filename="sheet.pdf",
    )
    _document(
        db_session, "prj-vis06", "doc-plate6", text=NAMEPLATE, doc_type="image",
        filename="nameplate.jpg",
    )
    db_session.commit()

    body = evidence_client.post(
        "/api/projects/prj-vis06/attributes/extract"
    ).json()
    pressure = next(a for a in body if a["name"] == "maximum_pressure")

    # Two independent sources agreeing is exactly the case that raises trust.
    assert pressure["status"] == "known"
    assert pressure["confidence"] == 0.95
    assert {e["documentType"] for e in pressure["evidence"]} == {"pdf", "image"}


def test_a_photo_disagreeing_with_the_datasheet_becomes_a_conflict(
    evidence_client: TestClient, review_client: TestClient, db_session: Session,
    _ocr_on: None,
) -> None:
    _project(db_session, "prj-vis07")
    _document(
        db_session, "prj-vis07", "doc-sheet7", text=DATASHEET, doc_type="pdf",
        filename="sheet.pdf",
    )
    _document(
        db_session, "prj-vis07", "doc-plate7", text=NAMEPLATE_DISAGREEING,
        doc_type="image", filename="nameplate.jpg",
    )
    db_session.commit()

    body = evidence_client.post(
        "/api/projects/prj-vis07/attributes/extract"
    ).json()
    pressure = next(a for a in body if a["name"] == "maximum_pressure")
    assert pressure["status"] == "conflicting"

    # And it reaches the reviewer as a hold naming both sources.
    items = review_client.get("/api/projects/prj-vis07/reviews").json()
    hold = next(i for i in items if i["field"] == "maximum_pressure")
    assert hold["issueType"] == "conflict"
    assert {v["sourceType"] for v in hold["values"]} == {"pdf", "image"}


def test_a_photo_only_reading_of_a_critical_field_becomes_a_hold(
    evidence_client: TestClient, review_client: TestClient, db_session: Session,
    _ocr_on: None,
) -> None:
    """You should not trust a photo alone for a coil voltage."""
    _project(db_session, "prj-vis08")
    _document(
        db_session, "prj-vis08", "doc-plate8", text=NAMEPLATE, doc_type="image",
        filename="nameplate.jpg",
    )
    db_session.commit()

    evidence_client.post("/api/projects/prj-vis08/attributes/extract")
    items = review_client.get("/api/projects/prj-vis08/reviews").json()

    voltage = [i for i in items if i["field"] == "supply_voltage"]
    assert len(voltage) == 1
    assert voltage[0]["issueType"] == "high_risk"


def test_with_ocr_off_an_image_contributes_nothing_and_is_marked_unread(
    evidence_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running with no OCR is a supported configuration, not a failure."""
    monkeypatch.setattr(
        "services.evidence_service.repository._read_pdf_bytes",
        lambda storage_key: storage_key.encode("utf-8"),
    )
    _project(db_session, "prj-vis09")
    _document(
        db_session, "prj-vis09", "doc-plate9", text=NAMEPLATE, doc_type="image",
        filename="nameplate.jpg",
    )
    db_session.commit()

    body = evidence_client.post(
        "/api/projects/prj-vis09/attributes/extract"
    ).json()
    # No value was invented from an image nobody read.
    assert all(a["rawValue"] == "" for a in body)

    document = db_session.get(DocumentRow, "doc-plate9")
    assert document is not None
    db_session.refresh(document)
    assert document.status == "pending"
