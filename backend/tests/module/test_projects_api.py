from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_list_and_get_project(project_client: TestClient) -> None:
    create_response = project_client.post(
        "/api/projects",
        json={
            "name": "Valve quote",
            "goal": "technical_quotation",
            "category": "Ball valves",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"].startswith("prj-")
    assert created["name"] == "Valve quote"
    assert created["documents"] == []

    list_response = project_client.get("/api/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]

    get_response = project_client.get(f"/api/projects/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Valve quote"


def test_get_missing_project_returns_404(project_client: TestClient) -> None:
    response = project_client.get("/api/projects/prj-notfound")
    assert response.status_code == 404
