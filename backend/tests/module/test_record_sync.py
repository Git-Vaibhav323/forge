from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import ProjectRow


def _seed_replacement(db_session: Session) -> str:
    now = datetime.now(timezone.utc)
    row = ProjectRow(
        id="prj-sync01",
        name="new techstack",
        goal="replacement_recommendation",
        category="TECHSTACK",
        status="draft",
        completion_score=0,
        blocking_fields_count=2,
        conflicts_count=0,
        pending_approvals_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.commit()
    return row.id


def test_question_answers_appear_on_evidence_tab(
    question_client: TestClient,
    evidence_client: TestClient,
    db_session: Session,
) -> None:
    project_id = _seed_replacement(db_session)

    first = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q = next(q for q in first if q["status"] == "open")
    question_client.post(
        f"/api/projects/{project_id}/questions/{open_q['id']}/answer",
        json={"answer": "legacy frontend stack"},
    )
    second = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q2 = next(q for q in second if q["status"] == "open")
    question_client.post(
        f"/api/projects/{project_id}/questions/{open_q2['id']}/answer",
        json={"answer": "needs better UX"},
    )

    attrs = evidence_client.get(f"/api/projects/{project_id}/attributes").json()
    by_name = {a["name"]: a for a in attrs}
    assert set(by_name) == {"existing_part_number", "reason_for_replacement"}
    assert by_name["existing_part_number"]["rawValue"] == "legacy frontend stack"
    assert by_name["existing_part_number"]["status"] == "verified"
    assert by_name["reason_for_replacement"]["rawValue"] == "needs better UX"
    assert by_name["existing_part_number"]["confidence"] == 1.0
    assert len(by_name["existing_part_number"]["evidence"]) >= 1


def test_rescan_preserves_user_answers(
    question_client: TestClient,
    evidence_client: TestClient,
    db_session: Session,
) -> None:
    project_id = _seed_replacement(db_session)
    first = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q = next(q for q in first if q["status"] == "open")
    question_client.post(
        f"/api/projects/{project_id}/questions/{open_q['id']}/answer",
        json={"answer": "frontend module"},
    )

    evidence_client.post(f"/api/projects/{project_id}/attributes/extract")
    attrs = evidence_client.get(f"/api/projects/{project_id}/attributes").json()
    part = next(a for a in attrs if a["name"] == "existing_part_number")
    assert part["rawValue"] == "frontend module"
    assert part["status"] == "verified"


def test_stale_attributes_pruned_on_sync(
    evidence_client: TestClient,
    db_session: Session,
) -> None:
    from datetime import datetime, timezone

    from shared.db.models import AttributeRow, ProjectRow

    now = datetime.now(timezone.utc)
    project_id = "prj-stale01"
    db_session.add(
        ProjectRow(
            id=project_id,
            name="new techstack",
            goal="replacement_recommendation",
            category="TECHSTACK",
            status="draft",
            completion_score=0,
            blocking_fields_count=2,
            conflicts_count=0,
            pending_approvals_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        AttributeRow(
            id="attr-stale-man",
            project_id=project_id,
            name="manufacturer",
            raw_value="Acme",
            normalized_value="acme",
            unit=None,
            confidence=0.9,
            status="known",
            risk_level="low",
            updated_at=now,
        )
    )
    db_session.commit()

    attrs = evidence_client.get(f"/api/projects/{project_id}/attributes").json()
    names = {a["name"] for a in attrs}
    assert "manufacturer" not in names
    assert names == {"existing_part_number", "reason_for_replacement"}
