from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import ProjectRow


def _seed_project(db_session: Session, category: str = "solenoid_valve") -> str:
    now = datetime.now(timezone.utc)
    row = ProjectRow(
        id="prj-qtest01",
        name="SV-24 desk job",
        goal="product_configuration",
        category=category,
        status="draft",
        completion_score=0,
        blocking_fields_count=8,
        conflicts_count=0,
        pending_approvals_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.commit()
    return row.id


def test_list_seeds_one_open_question(
    question_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_project(db_session)
    response = question_client.get(f"/api/projects/{project_id}/questions")
    assert response.status_code == 200
    body = response.json()
    open_qs = [q for q in body if q["status"] == "open"]
    assert len(open_qs) == 1
    assert open_qs[0]["priority"] == "critical"
    assert "projectId" in open_qs[0]
    assert open_qs[0]["text"]


def test_answer_advances_and_updates_score(
    question_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_project(db_session)
    first = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q = next(q for q in first if q["status"] == "open")

    answered = question_client.post(
        f"/api/projects/{project_id}/questions/{open_q['id']}/answer",
        json={"answer": "Acme"},
    )
    assert answered.status_code == 200
    assert answered.json()["status"] == "answered"
    assert answered.json()["answer"] == "Acme"

    second = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_qs = [q for q in second if q["status"] == "open"]
    answered_qs = [q for q in second if q["status"] == "answered"]
    assert len(open_qs) == 1
    assert len(answered_qs) == 1
    assert open_qs[0]["id"] != open_q["id"]

    db_session.expire_all()
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    assert project.completion_score > 0
    assert project.blocking_fields_count >= 1
    assert project.status == "waiting_for_user"


def test_i_dont_know_does_not_complete_field(
    question_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_project(db_session)
    first = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q = next(q for q in first if q["status"] == "open")
    question_client.post(
        f"/api/projects/{project_id}/questions/{open_q['id']}/answer",
        json={"answer": "I don't know"},
    )
    again = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_qs = [q for q in again if q["status"] == "open"]
    # same field should be asked again (new open question)
    assert len(open_qs) == 1
    assert open_qs[0]["field"] == open_q["field"]

    db_session.expire_all()
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    assert project.completion_score == 0


def test_missing_project_404(question_client: TestClient) -> None:
    response = question_client.get("/api/projects/prj-nope/questions")
    assert response.status_code == 404
