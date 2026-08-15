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


def test_delete_project_removes_it(project_client: TestClient) -> None:
    created = project_client.post(
        "/api/projects",
        json={
            "name": "Throwaway valve",
            "goal": "product_configuration",
            "category": "gate_valve",
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    deleted = project_client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204

    missing = project_client.get(f"/api/projects/{project_id}")
    assert missing.status_code == 404
    listed = project_client.get("/api/projects")
    assert all(p["id"] != project_id for p in listed.json())


def test_delete_missing_project_returns_404(project_client: TestClient) -> None:
    response = project_client.delete("/api/projects/prj-notfound")
    assert response.status_code == 404
