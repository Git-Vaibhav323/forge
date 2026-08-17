from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import AttributeRow, ProjectRow


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


def test_final_answer_persists_and_completes_job(
    question_client: TestClient, db_session: Session
) -> None:
    """Answering the last required field must commit — not roll back on session close."""
    project_id = _seed_project(db_session)
    seen_open: set[str] = set()
    for _ in range(20):
        body = question_client.get(f"/api/projects/{project_id}/questions").json()
        open_q = next((q for q in body if q["status"] == "open"), None)
        if open_q is None:
            break
        seen_open.add(open_q["field"])
        answer = (
            "Not applicable"
            if open_q["inputType"] == "select"
            else f"test-{open_q['field']}"
        )
        response = question_client.post(
            f"/api/projects/{project_id}/questions/{open_q['id']}/answer",
            json={"answer": answer},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "answered"

    final = question_client.get(f"/api/projects/{project_id}/questions").json()
    assert not any(q["status"] == "open" for q in final)
    assert len(seen_open) >= 1

    db_session.expire_all()
    project = db_session.get(ProjectRow, project_id)
    assert project is not None
    assert project.completion_score == 100
    assert project.blocking_fields_count == 0
    assert project.status == "ready_to_generate"


def test_evidence_prefill_skips_cited_fields(
    question_client: TestClient, db_session: Session
) -> None:
    project_id = _seed_project(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(
        AttributeRow(
            id="attr-mfg",
            project_id=project_id,
            name="manufacturer",
            raw_value="Meridian",
            normalized_value="Meridian",
            unit=None,
            confidence=0.9,
            status="known",
            risk_level="low",
            updated_at=now,
        )
    )
    db_session.add(
        AttributeRow(
            id="attr-model",
            project_id=project_id,
            name="model",
            raw_value="MFC-GV-200",
            normalized_value="MFC-GV-200",
            unit=None,
            confidence=0.9,
            status="known",
            risk_level="medium",
            updated_at=now,
        )
    )
    db_session.commit()

    body = question_client.get(f"/api/projects/{project_id}/questions").json()
    open_q = next(q for q in body if q["status"] == "open")
    assert open_q["field"] not in {"manufacturer", "model"}


def test_replacement_job_completes_after_goal_fields_only(
    question_client: TestClient, db_session: Session
) -> None:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    row = ProjectRow(
        id="prj-repl01",
        name="Swap frontend stack",
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

    for _ in range(5):
        body = question_client.get("/api/projects/prj-repl01/questions").json()
        open_q = next((q for q in body if q["status"] == "open"), None)
        if open_q is None:
            break
        assert open_q["field"] in {"existing_part_number", "reason_for_replacement"}
        question_client.post(
            f"/api/projects/prj-repl01/questions/{open_q['id']}/answer",
            json={"answer": f"answer-{open_q['field']}"},
        )

    final = question_client.get("/api/projects/prj-repl01/questions").json()
    assert not any(q["status"] == "open" for q in final)
    fields = {q["field"] for q in final}
    assert fields == {"existing_part_number", "reason_for_replacement"}
    assert "model" not in fields

    db_session.expire_all()
    project = db_session.get(ProjectRow, "prj-repl01")
    assert project is not None
    assert project.completion_score == 100
    assert project.status == "ready_to_generate"


def test_missing_project_404(question_client: TestClient) -> None:
    response = question_client.get("/api/projects/prj-nope/questions")
    assert response.status_code == 404
