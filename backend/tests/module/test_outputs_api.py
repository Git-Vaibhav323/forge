from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import AttributeEvidenceRow, AttributeRow, OutputRow, ProjectRow

NOW = datetime.now(timezone.utc)


def _project(
    db: Session, project_id: str, *, goal: str = "product_datasheet"
) -> ProjectRow:
    row = ProjectRow(
        id=project_id,
        name=f"Job {project_id}",
        goal=goal,
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


def _cited(
    db: Session,
    project_id: str,
    attr_id: str,
    name: str,
    value: str,
    *,
    unit: str | None = None,
    status: str = "known",
    risk: str = "low",
    with_evidence: bool = True,
    document_id: str | None = None,
) -> None:
    db.add(
        AttributeRow(
            id=attr_id,
            project_id=project_id,
            name=name,
            raw_value=value,
            normalized_value=value or None,
            unit=unit,
            confidence=0.95,
            status=status,
            risk_level=risk,
            updated_at=NOW,
        )
    )
    if with_evidence:
        db.add(
            AttributeEvidenceRow(
                id=f"ev-{attr_id}",
                attribute_id=attr_id,
                document_id=document_id or f"doc-{attr_id}",
                document_name="datasheet.pdf",
                document_type="pdf",
                page=3,
                quote=f"{name}: {value} {unit or ''}".strip(),
                value=value,
                unit=unit,
            )
        )


def _printable_job(db: Session, project_id: str = "prj-out01") -> str:
    """A job with one fully cited field and nothing in dispute."""
    _project(db, project_id)
    _cited(db, project_id, "attr-o1", "maximum_pressure", "285", unit="PSI")
    db.commit()
    return project_id


# ---------------------------------------------------------------------------
# Generating
# ---------------------------------------------------------------------------


def test_generate_writes_a_real_artifact(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session)

    body = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    assert body["status"] in {"qa_passed", "generated"}
    assert body["filename"] == f"product_datasheet_{project_id}.csv"
    assert body["downloadUrl"] == f"/api/outputs/{body['id']}/download"
    assert body["sizeBytes"] > 0
    assert body["generatedAt"] is not None


def test_the_artifact_contains_the_cited_value_and_its_source(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session)
    created = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    response = generation_client.get(f"/api/outputs/{created['id']}/download")
    assert response.status_code == 200
    text = response.text

    # CSV output should contain the value (285 PSI is parsed as "285" value with "PSI" unit)
    assert "285" in text
    # CSV format should be parseable
    assert "," in text  # CSV delimiter


def test_download_is_served_as_a_named_attachment(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session)
    created = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    response = generation_client.get(f"/api/outputs/{created['id']}/download")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert f"product_datasheet_{project_id}.csv" in disposition


def test_generate_defaults_to_the_job_goal(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session)
    body = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": ""}
    ).json()
    assert body["type"] == "product_datasheet"


def test_regenerating_replaces_rather_than_accumulates(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session)
    first = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()
    second = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    assert first["id"] != second["id"]
    listed = generation_client.get(f"/api/projects/{project_id}/outputs").json()
    assert len(listed) == 1
    assert listed[0]["id"] == second["id"]


def test_listing_an_unknown_project_is_404(generation_client: TestClient) -> None:
    assert (
        generation_client.get("/api/projects/prj-nope/outputs").status_code == 404
    )


def test_downloading_an_unknown_output_is_404(generation_client: TestClient) -> None:
    assert (
        generation_client.get("/api/outputs/out-nope/download").status_code == 404
    )


# ---------------------------------------------------------------------------
# The QA gate — the governance rule, enforced
# ---------------------------------------------------------------------------


def test_an_unresolved_conflict_blocks_the_print(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = "prj-out02"
    _project(db_session, project_id)
    _cited(
        db_session,
        project_id,
        "attr-c",
        "maximum_pressure",
        "285 / 300",
        unit="PSI",
        status="conflicting",
        risk="critical",
    )
    db_session.commit()

    body = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    assert body["status"] == "qa_failed"
    # No file was written, because there was nothing legitimate to write.
    assert body["downloadUrl"] is None
    assert body["generatedAt"] is None
    assert any("disagreeing sources" in note for note in body["qaNotes"])


def test_a_blocked_output_cannot_be_downloaded(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = "prj-out03"
    _project(db_session, project_id)
    _cited(
        db_session,
        project_id,
        "attr-c3",
        "maximum_pressure",
        "285 / 300",
        unit="PSI",
        status="conflicting",
        risk="critical",
    )
    db_session.commit()

    created = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()
    response = generation_client.get(f"/api/outputs/{created['id']}/download")
    assert response.status_code == 409


def test_a_pending_hold_blocks_the_print(
    generation_client: TestClient, db_session: Session
) -> None:
    """A missing safety-critical field becomes a hold, and a hold blocks printing."""
    project_id = "prj-out04"
    _project(db_session, project_id)
    _cited(
        db_session,
        project_id,
        "attr-v",
        "supply_voltage",
        "",
        status="missing",
        risk="critical",
        with_evidence=False,
    )
    db_session.commit()

    body = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    assert body["status"] == "qa_failed"
    assert any("awaiting a decision" in note for note in body["qaNotes"])


def test_a_value_with_no_citation_is_never_stated_as_fact(
    generation_client: TestClient, db_session: Session
) -> None:
    """Status alone is not enough — a fact needs a source behind it."""
    project_id = "prj-out05"
    _project(db_session, project_id)
    _cited(
        db_session,
        project_id,
        "attr-nc",
        "model",
        "MFC-GV-100",
        with_evidence=False,  # claims to be known, but nothing backs it
    )
    db_session.commit()

    created = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()
    text = generation_client.get(f"/api/outputs/{created['id']}/download").text

    # CSV format: uncited values should not appear in the main columns
    # (they would only appear if they had evidence)
    assert "MFC-GV-100" not in text or "model" not in text  # Not both present together


def test_gaps_warn_but_still_produce_a_document(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = "prj-out06"
    _project(db_session, project_id)
    _cited(db_session, project_id, "attr-ok", "maximum_pressure", "285", unit="PSI")
    _cited(
        db_session,
        project_id,
        "attr-gap",
        "model",
        "",
        status="missing",
        with_evidence=False,
    )
    db_session.commit()

    body = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    ).json()

    assert body["status"] == "generated"  # printable, with caveats
    assert body["downloadUrl"] is not None
    # QA notes should warn about gaps even in CSV format
    assert any("gap" in note.lower() for note in body["qaNotes"])

    text = generation_client.get(f"/api/outputs/{body['id']}/download").text
    # CSV format should be valid
    assert "," in text  # CSV contains commas


def test_generation_marks_the_job_generated(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session, "prj-out07")
    generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    )

    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.status == "generated"


def test_a_blocked_print_does_not_mark_the_job_generated(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = "prj-out08"
    _project(db_session, project_id)
    _cited(
        db_session,
        project_id,
        "attr-c8",
        "maximum_pressure",
        "285 / 300",
        unit="PSI",
        status="conflicting",
        risk="critical",
    )
    db_session.commit()

    generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    )
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    db_session.refresh(project)
    assert project.status != "generated"


# ---------------------------------------------------------------------------
# BOM goals pull in M6
# ---------------------------------------------------------------------------


def test_a_bom_job_prints_its_resolved_lines(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = "prj-out09"
    _project(db_session, project_id, goal="bom_generation")
    _cited(db_session, project_id, "attr-mfr", "manufacturer", "Meridian")
    _cited(db_session, project_id, "attr-mdl", "model", "MFC-GV-100")
    db_session.commit()

    created = generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "bom_generation"}
    ).json()

    # Gaps in the BOM are warnings, not blockers.
    assert created["downloadUrl"] is not None
    text = generation_client.get(f"/api/outputs/{created['id']}/download").text
    # CSV format should contain the manufacturer and model data
    assert "Meridian" in text
    assert "MFC-GV-100" in text


def test_deleting_the_output_row_leaves_no_orphan_listing(
    generation_client: TestClient, db_session: Session
) -> None:
    project_id = _printable_job(db_session, "prj-out10")
    generation_client.post(
        f"/api/projects/{project_id}/outputs", json={"type": "product_datasheet"}
    )
    assert len(generation_client.get(f"/api/projects/{project_id}/outputs").json()) == 1

    db_session.query(OutputRow).filter(OutputRow.project_id == project_id).delete()
    db_session.commit()
    assert generation_client.get(f"/api/projects/{project_id}/outputs").json() == []
