from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import (
    AttributeEvidenceRow,
    AttributeRow,
    DocumentRow,
    ProjectRow,
)

NOW = datetime.now(timezone.utc)


def _project(db: Session, project_id: str, *, category: str = "valve") -> ProjectRow:
    row = ProjectRow(
        id=project_id,
        name=f"Job {project_id}",
        goal="product_datasheet",
        category=category,
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


def _attribute(
    db: Session,
    project_id: str,
    attr_id: str,
    name: str,
    *,
    raw_value: str = "",
    status: str = "known",
    risk: str = "low",
    unit: str | None = None,
) -> AttributeRow:
    row = AttributeRow(
        id=attr_id,
        project_id=project_id,
        name=name,
        raw_value=raw_value,
        normalized_value=raw_value or None,
        unit=unit,
        confidence=0.8,
        status=status,
        risk_level=risk,
        updated_at=NOW,
    )
    db.add(row)
    return row


def _evidence(
    db: Session,
    attr_id: str,
    ev_id: str,
    *,
    doc_name: str,
    value: str,
    unit: str | None,
    page: int = 1,
    doc_type: str = "pdf",
) -> None:
    db.add(
        AttributeEvidenceRow(
            id=ev_id,
            attribute_id=attr_id,
            document_id=f"doc-{ev_id}",
            document_name=doc_name,
            document_type=doc_type,
            page=page,
            quote=f"Max Working Pressure: {value} {unit or ''}".strip(),
            value=value,
            unit=unit,
        )
    )


def _seed_conflict(db: Session, project_id: str = "prj-rv01") -> str:
    """A pressure conflict: datasheet says 285 PSI, catalog says 300 PSI."""
    _project(db, project_id)
    _attribute(
        db,
        project_id,
        "attr-p1",
        "maximum_pressure",
        raw_value="285 / 300",
        status="conflicting",
        risk="critical",
        unit="PSI",
    )
    _evidence(db, "attr-p1", "ev-a", doc_name="datasheet.pdf", value="285", unit="PSI")
    _evidence(db, "attr-p1", "ev-b", doc_name="catalog.html", value="300", unit="PSI", doc_type="web")
    db.commit()
    return project_id


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def test_conflicting_attribute_becomes_a_review_item(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)

    response = review_client.get(f"/api/projects/{project_id}/reviews")
    assert response.status_code == 200
    items = response.json()

    assert len(items) == 1
    item = items[0]
    assert item["field"] == "maximum_pressure"
    assert item["issueType"] == "conflict"
    assert item["severity"] == "critical"
    assert item["status"] == "pending"

    # Both sources are shown with their own value — this is what the card renders.
    values = {v["value"] for v in item["values"]}
    assert values == {"285 PSI", "300 PSI"}
    assert {v["sourceType"] for v in item["values"]} == {"pdf", "web"}


def test_derivation_updates_the_job_counters(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_client.get(f"/api/projects/{project_id}/reviews")

    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 1
    assert project.conflicts_count == 1


def test_missing_safety_critical_field_becomes_a_high_risk_hold(
    review_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rv02")
    _attribute(
        db_session,
        "prj-rv02",
        "attr-v1",
        "supply_voltage",
        status="missing",
        risk="critical",
    )
    # A low-risk missing field must NOT create a hold.
    _attribute(db_session, "prj-rv02", "attr-m1", "model", status="missing", risk="low")
    db_session.commit()

    items = review_client.get("/api/projects/prj-rv02/reviews").json()
    assert len(items) == 1
    assert items[0]["field"] == "supply_voltage"
    assert items[0]["issueType"] == "high_risk"


def test_unit_only_disagreement_is_normalized_not_escalated(
    review_client: TestClient, db_session: Session
) -> None:
    """285 PSI and 19.6501 bar are one fact written twice — not a reviewer's problem."""
    _project(db_session, "prj-rv03")
    _attribute(
        db_session,
        "prj-rv03",
        "attr-p3",
        "maximum_pressure",
        raw_value="285 / 19.6501",
        status="conflicting",
        risk="critical",
        unit="PSI",
    )
    _evidence(db_session, "attr-p3", "ev-c", doc_name="datasheet.pdf", value="285", unit="PSI")
    _evidence(db_session, "attr-p3", "ev-d", doc_name="catalog.html", value="19.6501", unit="bar")
    db_session.commit()

    items = review_client.get("/api/projects/prj-rv03/reviews").json()
    assert items == []

    attr = db_session.get(AttributeRow, "attr-p3")
    assert attr is not None
    db_session.refresh(attr)
    assert attr.status == "known"

    project = db_session.get(ProjectRow, "prj-rv03")
    assert project is not None
    db_session.refresh(project)
    assert project.conflicts_count == 0


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def _first_item_id(client: TestClient, project_id: str) -> str:
    items = client.get(f"/api/projects/{project_id}/reviews").json()
    return items[0]["id"]


def test_approve_writes_the_value_and_clears_the_hold(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    response = review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "approve", "value": "285 PSI"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    attr = db_session.get(AttributeRow, "attr-p1")
    assert attr is not None
    db_session.refresh(attr)
    assert attr.status == "verified"
    assert attr.raw_value == "285 PSI"

    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 0
    assert project.conflicts_count == 0


def test_edit_records_the_typed_value(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    response = review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "edit", "value": "290 PSI"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "edited"

    attr = db_session.get(AttributeRow, "attr-p1")
    assert attr is not None
    db_session.refresh(attr)
    assert attr.raw_value == "290 PSI"
    assert attr.status == "verified"


def test_edit_without_a_value_is_rejected(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    response = review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "edit", "value": "   "},
    )
    assert response.status_code == 422


def test_reject_abstains_rather_than_keeping_a_disputed_value(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "reject"},
    )

    attr = db_session.get(AttributeRow, "attr-p1")
    assert attr is not None
    db_session.refresh(attr)
    # Nothing invented, nothing kept that nobody stands behind.
    assert attr.raw_value == ""
    assert attr.status == "missing"


def test_rejecting_a_critical_field_reopens_it_as_a_missing_evidence_hold(
    review_client: TestClient, db_session: Session
) -> None:
    """Intentional, not a bug.

    Rejecting both candidate pressures leaves a safety-critical field with no
    value. Per the governance rule that is still a hold — it just changes from
    "sources disagree" to "no evidence". The reviewer clears it by approving an
    explicit override or by adding a source.
    """
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "reject"},
    )

    items = review_client.get(f"/api/projects/{project_id}/reviews").json()
    assert len(items) == 1
    assert items[0]["issueType"] == "high_risk"
    assert items[0]["status"] == "pending"

    # An explicit override then clears it without inventing a value.
    review_client.post(
        f"/api/reviews/{items[0]['id']}/decision",
        json={"projectId": project_id, "action": "approve"},
    )
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 0


def test_unknown_action_is_rejected(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)

    response = review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "obliterate"},
    )
    assert response.status_code == 422


def test_decision_on_another_projects_item_is_refused(
    review_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_conflict(db_session)
    _project(db_session, "prj-other")
    db_session.commit()
    review_id = _first_item_id(review_client, project_id)

    response = review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": "prj-other", "action": "approve"},
    )
    assert response.status_code == 400


def test_decision_is_recorded_in_the_audit_trail(
    review_client: TestClient, db_session: Session
) -> None:
    from services.review_service.repository import list_decisions

    project_id = _seed_conflict(db_session)
    review_id = _first_item_id(review_client, project_id)
    review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_id, "action": "approve", "value": "285 PSI"},
    )

    decisions = list_decisions(db_session, project_id)
    assert len(decisions) == 1
    assert decisions[0].action == "approve"
    assert decisions[0].value == "285 PSI"
    assert decisions[0].field == "maximum_pressure"


# ---------------------------------------------------------------------------
# Survival across an evidence re-scan — the reason items are keyed on (job, field)
# ---------------------------------------------------------------------------

DATASHEET = """Meridian Flow Controls
Gate Valve Series - Product Datasheet
Model: MFC-GV-100
Max Working Pressure: 285 PSI
Meridian Flow Controls - Page 1
"""

CATALOG = """Meridian Flow Controls
Distributor Catalog Listing
Model: MFC-GV-100
Max Working Pressure: 300 PSI
Meridian Flow Controls - Page 1
"""


@pytest.fixture
def _stub_pdf_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    # Same stubbing as tests/module/test_evidence_api.py: the storage_key holds
    # the page text, so neither object storage nor pypdf is needed.
    monkeypatch.setattr(
        "services.evidence_service.repository._read_pdf_bytes",
        lambda storage_key: storage_key.encode("utf-8"),
    )
    monkeypatch.setattr(
        "services.evidence_service.repository.extract_pages_from_pdf",
        lambda data: [data.decode("utf-8")],
    )


def test_approved_decision_survives_a_document_rescan(
    review_client: TestClient,
    evidence_client: TestClient,
    db_session: Session,
    _stub_pdf_reader: None,
) -> None:
    """evidence-service deletes and recreates every attribute row on re-scan.

    Because review items are keyed on (project_id, field) rather than the
    attribute id, the decision is replayed instead of being silently undone.
    """
    project_id = "prj-rv04"
    _project(db_session, project_id)
    for idx, text in ((1, DATASHEET), (2, CATALOG)):
        db_session.add(
            DocumentRow(
                id=f"doc-rv{idx}",
                project_id=project_id,
                filename=f"sheet_{idx}.pdf",
                type="pdf",
                status="pending",
                storage_key=text,
                content_hash=f"hash-rv{idx}",
                uploaded_at=NOW,
            )
        )
    db_session.commit()

    # Extract → the two sheets disagree on pressure.
    evidence_client.post(f"/api/projects/{project_id}/attributes/extract")

    items = review_client.get(f"/api/projects/{project_id}/reviews").json()
    pressure = [i for i in items if i["field"] == "maximum_pressure"]
    assert len(pressure) == 1

    review_client.post(
        f"/api/reviews/{pressure[0]['id']}/decision",
        json={"projectId": project_id, "action": "approve", "value": "285 PSI"},
    )

    # Re-scan the same documents. The conflict is still in the PDFs.
    rescanned = evidence_client.post(
        f"/api/projects/{project_id}/attributes/extract"
    ).json()

    after = {a["name"]: a for a in rescanned}
    assert after["maximum_pressure"]["status"] == "verified"
    assert after["maximum_pressure"]["rawValue"] == "285 PSI"

    # And the hold does not come back.
    items_after = review_client.get(f"/api/projects/{project_id}/reviews").json()
    pressure_after = [i for i in items_after if i["field"] == "maximum_pressure"]
    assert pressure_after[0]["status"] == "approved"

    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 0


# ---------------------------------------------------------------------------
# Bulk propagation
# ---------------------------------------------------------------------------


def _seed_sibling_pair(db: Session) -> tuple[str, str]:
    """Two valve jobs whose connection_standard carries the same wrong value."""
    _project(db, "prj-bulk-a")
    _attribute(
        db,
        "prj-bulk-a",
        "attr-c1",
        "connection_standard",
        raw_value="NPT / BSPP",
        status="conflicting",
        risk="high",
    )
    _evidence(db, "attr-c1", "ev-e", doc_name="datasheet.pdf", value="NPT", unit=None)
    _evidence(db, "attr-c1", "ev-f", doc_name="catalog.html", value="BSPP", unit=None, doc_type="web")

    _project(db, "prj-bulk-b")
    _attribute(
        db,
        "prj-bulk-b",
        "attr-c2",
        "connection_standard",
        raw_value="NPT",
        status="known",
        risk="high",
    )
    db.commit()
    return "prj-bulk-a", "prj-bulk-b"


def test_sibling_jobs_are_counted_on_the_item(
    review_client: TestClient, db_session: Session
) -> None:
    project_a, _ = _seed_sibling_pair(db_session)

    items = review_client.get(f"/api/projects/{project_a}/reviews").json()
    assert items[0]["affectedProducts"] == 2  # this job + one sibling


def test_propagate_applies_the_correction_to_siblings(
    review_client: TestClient, db_session: Session
) -> None:
    project_a, _ = _seed_sibling_pair(db_session)
    review_id = _first_item_id(review_client, project_a)

    review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={
            "projectId": project_a,
            "action": "approve",
            "value": "BSPP",
            "propagate": True,
        },
    )

    sibling = db_session.get(AttributeRow, "attr-c2")
    assert sibling is not None
    db_session.refresh(sibling)
    assert sibling.raw_value == "BSPP"
    assert sibling.status == "verified"


def test_sibling_is_untouched_without_propagate(
    review_client: TestClient, db_session: Session
) -> None:
    project_a, _ = _seed_sibling_pair(db_session)
    review_id = _first_item_id(review_client, project_a)

    review_client.post(
        f"/api/reviews/{review_id}/decision",
        json={"projectId": project_a, "action": "approve", "value": "BSPP"},
    )

    sibling = db_session.get(AttributeRow, "attr-c2")
    assert sibling is not None
    db_session.refresh(sibling)
    assert sibling.raw_value == "NPT"
    assert sibling.status == "known"
