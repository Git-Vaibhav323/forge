from __future__ import annotations

from fastapi.testclient import TestClient


def test_upload_and_list_on_project(project_client: TestClient, file_client: TestClient) -> None:
    create_response = project_client.post(
        "/api/projects",
        json={"name": "Pump job", "goal": "bom_generation", "category": "Pumps"},
    )
    project_id = create_response.json()["id"]

    upload_response = file_client.post(
        f"/api/projects/{project_id}/files",
        files={"file": ("datasheet.pdf", b"%PDF-1.4 test content", "application/pdf")},
    )
    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["documentId"].startswith("doc-")
    assert body["filename"] == "datasheet.pdf"
    assert body["status"] == "processing"

    get_response = project_client.get(f"/api/projects/{project_id}")
    documents = get_response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["id"] == body["documentId"]


def test_duplicate_upload_returns_409_with_message(
    project_client: TestClient, file_client: TestClient
) -> None:
    create_response = project_client.post(
        "/api/projects",
        json={"name": "Dup test", "goal": "bom_generation", "category": "Pumps"},
    )
    project_id = create_response.json()["id"]
    payload = b"same-bytes"

    first = file_client.post(
        f"/api/projects/{project_id}/files",
        files={"file": ("a.pdf", payload, "application/pdf")},
    )
    assert first.status_code == 200

    duplicate = file_client.post(
        f"/api/projects/{project_id}/files",
        files={"file": ("b.pdf", payload, "application/pdf")},
    )
    assert duplicate.status_code == 409
    detail = duplicate.json()["detail"]
    assert detail["code"] == "duplicate_file"
    assert "What are you looking for differently" in detail["message"]

    reupload = file_client.post(
        f"/api/projects/{project_id}/files?intent=reupload",
        files={"file": ("c.pdf", payload, "application/pdf")},
    )
    assert reupload.status_code == 200

    get_response = project_client.get(f"/api/projects/{project_id}")
    assert len(get_response.json()["documents"]) == 2


def test_delete_project_drops_documents(
    project_client: TestClient, file_client: TestClient, monkeypatch
) -> None:
    removed: list[str] = []
    monkeypatch.setattr(
        "services.project_service.repository.remove_object",
        lambda key: removed.append(key),
    )
    created = project_client.post(
        "/api/projects",
        json={"name": "Wipe me", "goal": "product_configuration", "category": "valve"},
    )
    project_id = created.json()["id"]
    file_client.post(
        f"/api/projects/{project_id}/files",
        files={"file": ("sheet.pdf", b"%PDF-delete-me", "application/pdf")},
    )

    deleted = project_client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204
    assert len(removed) == 1
    assert removed[0].startswith(f"{project_id}/")
    assert project_client.get(f"/api/projects/{project_id}").status_code == 404
