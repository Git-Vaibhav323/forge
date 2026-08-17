from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.db.models import ProjectRow

SAMPLE_HTML = """
<html><body>
  <h1>Meridian Flow Controls — Catalog</h1>
  <p>Model: MFC-GV-100</p>
  <p>Max Working Pressure: 300 PSI</p>
  <p>Standard: API 600</p>
</body></html>
"""


def _seed_project(db_session: Session) -> str:
    now = datetime.now(timezone.utc)
    db_session.add(
        ProjectRow(
            id="prj-web01",
            name="Web source job",
            goal="product_datasheet",
            category="valve",
            status="draft",
            completion_score=0,
            blocking_fields_count=0,
            conflicts_count=0,
            pending_approvals_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()
    return "prj-web01"


def test_add_pasted_html_source(file_client: TestClient, db_session: Session) -> None:
    project_id = _seed_project(db_session)
    resp = file_client.post(
        f"/api/projects/{project_id}/sources",
        json={
            "url": "https://catalog.example.com/meridian/mfc-gv-100",
            "html": SAMPLE_HTML,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "web"
    assert body["sourceUrl"] == "https://catalog.example.com/meridian/mfc-gv-100"
    assert body["documentId"].startswith("doc-")


def test_add_source_missing_project_404(file_client: TestClient) -> None:
    resp = file_client.post(
        "/api/projects/prj-nope/sources",
        json={"url": "https://example.com/x", "html": "<p>Model: X</p>"},
    )
    assert resp.status_code == 404
