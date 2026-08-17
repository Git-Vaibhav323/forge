from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import AttributeEvidenceRow, AttributeRow, ProjectRow
from shared.record_sync import USER_ANSWER_DOC_ID

NOW = datetime.now(timezone.utc)


def _project(
    db: Session,
    project_id: str,
    *,
    goal: str = "product_configuration",
    category: str = "valve",
) -> ProjectRow:
    row = ProjectRow(
        id=project_id,
        name=f"Job {project_id}",
        goal=goal,
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


def _field(
    db: Session,
    project_id: str,
    attr_id: str,
    name: str,
    *,
    required: str | None = None,
    rated: str | None = None,
    unit: str | None = None,
    status: str = "known",
) -> None:
    """Seed one attribute with a requirement side and/or a rating side.

    Mirrors what the running system produces: the user's answer is written onto
    the attribute and marked with a `user-answer` evidence row, while the
    datasheet keeps its own evidence row carrying the value it stated.
    """
    value = required if required is not None else (rated or "")
    db.add(
        AttributeRow(
            id=attr_id,
            project_id=project_id,
            name=name,
            raw_value=value,
            normalized_value=value or None,
            unit=unit,
            confidence=1.0 if required else 0.8,
            status="verified" if required else status,
            risk_level="low",
            updated_at=NOW,
        )
    )
    if required is not None:
        db.add(
            AttributeEvidenceRow(
                id=f"ev-req-{attr_id}",
                attribute_id=attr_id,
                document_id=USER_ANSWER_DOC_ID,
                document_name="User answer (Questions tab)",
                document_type="user",
                page=None,
                quote=f"Q: {name}\nA: {required}",
                value=required,
                unit=unit,
            )
        )
    if rated is not None:
        db.add(
            AttributeEvidenceRow(
                id=f"ev-doc-{attr_id}",
                attribute_id=attr_id,
                document_id=f"doc-{attr_id}",
                document_name="datasheet.pdf",
                document_type="pdf",
                page=1,
                quote=f"{name}: {rated} {unit or ''}".strip(),
                value=rated,
                unit=unit,
            )
        )


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


def test_under_rated_product_produces_a_failing_finding(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel01")
    _field(
        db_session,
        "prj-rel01",
        "attr-p",
        "maximum_pressure",
        required="300",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-rel01/relationships/resolve"
    ).json()

    pressure = next(f for f in view["findings"] if f["rule"] == "pressure_rating")
    assert pressure["status"] == "fail"
    assert pressure["requiredValue"] == "300 PSI"
    assert pressure["ratedValue"] == "285 PSI"
    assert pressure["severity"] == "critical"


def test_adequately_rated_product_passes(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel02")
    _field(
        db_session,
        "prj-rel02",
        "attr-p2",
        "maximum_pressure",
        required="200",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-rel02/relationships/resolve"
    ).json()
    pressure = next(f for f in view["findings"] if f["rule"] == "pressure_rating")
    assert pressure["status"] == "pass"


def test_a_field_still_in_conflict_abstains_rather_than_judging(
    relationship_client: TestClient, db_session: Session
) -> None:
    """You cannot check a rating nobody has agreed on yet."""
    _project(db_session, "prj-rel03")
    _field(
        db_session,
        "prj-rel03",
        "attr-p3",
        "maximum_pressure",
        required="300",
        rated="285",
        unit="PSI",
        status="conflicting",
    )
    # Force the disputed state the extractor would have produced.
    db_session.flush()
    attr = db_session.get(AttributeRow, "attr-p3")
    assert attr is not None
    attr.status = "conflicting"
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-rel03/relationships/resolve"
    ).json()
    pressure = next(f for f in view["findings"] if f["rule"] == "pressure_rating")
    assert pressure["status"] == "unknown"


def test_resolve_is_idempotent(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel04")
    _field(
        db_session,
        "prj-rel04",
        "attr-p4",
        "maximum_pressure",
        required="300",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    first = relationship_client.post(
        "/api/projects/prj-rel04/relationships/resolve"
    ).json()
    second = relationship_client.post(
        "/api/projects/prj-rel04/relationships/resolve"
    ).json()

    assert len(first["findings"]) == len(second["findings"])
    assert {f["rule"] for f in first["findings"]} == {
        f["rule"] for f in second["findings"]
    }


def test_get_returns_stored_state_without_recomputing(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel05")
    db_session.commit()

    assert relationship_client.get("/api/projects/prj-rel05/relationships").json() == {
        "variants": [],
        "findings": [],
        "bomLines": [],
    }


def test_unknown_project_is_404(relationship_client: TestClient) -> None:
    assert (
        relationship_client.get("/api/projects/prj-nope/relationships").status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def _identified(db: Session, project_id: str, model: str) -> None:
    _field(db, project_id, f"attr-mfr-{project_id}", "manufacturer", rated="Meridian")
    _field(db, project_id, f"attr-mdl-{project_id}", "model", rated=model)


def test_same_model_family_is_linked_as_a_variant(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-var-a")
    _identified(db_session, "prj-var-a", "MFC-GV-100")
    _project(db_session, "prj-var-b")
    _identified(db_session, "prj-var-b", "MFC-GV-150")
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-var-a/relationships/resolve"
    ).json()

    assert len(view["variants"]) == 1
    variant = view["variants"][0]
    assert variant["relatedProjectId"] == "prj-var-b"
    assert variant["relation"] == "variant"
    # The link must explain itself, not just assert itself.
    assert "MFC-GV" in variant["basis"]


def test_a_different_model_family_is_not_linked(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-var-c")
    _identified(db_session, "prj-var-c", "MFC-GV-100")
    _project(db_session, "prj-var-d")
    _identified(db_session, "prj-var-d", "ACME-BV-100")
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-var-c/relationships/resolve"
    ).json()
    assert view["variants"] == []


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------


def test_bom_lines_are_built_for_configuration_goals(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-bom01", goal="bom_generation")
    _identified(db_session, "prj-bom01", "MFC-GV-100")
    _field(
        db_session,
        "prj-bom01",
        "attr-conn",
        "connection_standard",
        rated="NPT",
    )
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-bom01/relationships/resolve"
    ).json()
    lines = view["bomLines"]

    primary = lines[0]
    assert primary["role"] == "primary"
    assert primary["component"] == "Meridian MFC-GV-100"
    assert primary["status"] == "resolved"

    by_field = {line["sourceField"]: line for line in lines}
    assert by_field["connection_standard"]["status"] == "resolved"
    # Everything the goal wants but nothing supports is named as a gap.
    assert by_field["supply_voltage"]["status"] == "missing"


def test_no_bom_for_goals_that_do_not_produce_one(
    relationship_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-bom02", goal="product_datasheet")
    _identified(db_session, "prj-bom02", "MFC-GV-100")
    db_session.commit()

    view = relationship_client.post(
        "/api/projects/prj-bom02/relationships/resolve"
    ).json()
    assert view["bomLines"] == []


# ---------------------------------------------------------------------------
# Integration with the review queue (M5)
# ---------------------------------------------------------------------------


def test_a_failing_rule_becomes_a_review_hold(
    relationship_client: TestClient, review_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel06")
    _field(
        db_session,
        "prj-rel06",
        "attr-p6",
        "maximum_pressure",
        required="300",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    relationship_client.post("/api/projects/prj-rel06/relationships/resolve")
    items = review_client.get("/api/projects/prj-rel06/reviews").json()

    incompatible = [i for i in items if i["issueType"] == "incompatible"]
    assert len(incompatible) == 1
    assert incompatible[0]["field"] == "maximum_pressure"
    assert incompatible[0]["severity"] == "critical"
    assert incompatible[0]["status"] == "pending"

    project = db_session.get(ProjectRow, "prj-rel06")
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 1


def test_a_passing_rule_creates_no_hold(
    relationship_client: TestClient, review_client: TestClient, db_session: Session
) -> None:
    _project(db_session, "prj-rel07")
    _field(
        db_session,
        "prj-rel07",
        "attr-p7",
        "maximum_pressure",
        required="200",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    relationship_client.post("/api/projects/prj-rel07/relationships/resolve")
    items = review_client.get("/api/projects/prj-rel07/reviews").json()
    assert [i for i in items if i["issueType"] == "incompatible"] == []


def test_accepting_a_mismatch_clears_the_hold_without_changing_the_value(
    relationship_client: TestClient, review_client: TestClient, db_session: Session
) -> None:
    """Approving an incompatibility is an explicit override, not a new fact."""
    _project(db_session, "prj-rel08")
    _field(
        db_session,
        "prj-rel08",
        "attr-p8",
        "maximum_pressure",
        required="300",
        rated="285",
        unit="PSI",
    )
    db_session.commit()

    relationship_client.post("/api/projects/prj-rel08/relationships/resolve")
    items = review_client.get("/api/projects/prj-rel08/reviews").json()
    hold = next(i for i in items if i["issueType"] == "incompatible")

    review_client.post(
        f"/api/reviews/{hold['id']}/decision",
        json={"projectId": "prj-rel08", "action": "approve"},
    )

    project = db_session.get(ProjectRow, "prj-rel08")
    assert project is not None
    db_session.refresh(project)
    assert project.pending_approvals_count == 0

    attr = db_session.get(AttributeRow, "attr-p8")
    assert attr is not None
    db_session.refresh(attr)
    assert attr.raw_value == "300"  # unchanged — nothing was invented
