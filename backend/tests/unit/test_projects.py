from __future__ import annotations

from datetime import datetime, timezone

from shared.db.models import ProjectRow
from services.project_service.repository import generate_project_id, row_to_project
from shared.schemas import ProjectGoal, ProjectStatus


def test_generate_project_id_format() -> None:
    project_id = generate_project_id()
    assert project_id.startswith("prj-")
    assert len(project_id) == len("prj-") + 8


def test_row_to_project_maps_all_fields() -> None:
    now = datetime.now(timezone.utc)
    row = ProjectRow(
        id="prj-deadbeef",
        name="Pump rebuild",
        goal=ProjectGoal.bom_generation.value,
        category="Centrifugal pumps",
        status=ProjectStatus.draft.value,
        completion_score=0,
        blocking_fields_count=0,
        conflicts_count=0,
        pending_approvals_count=0,
        created_at=now,
        updated_at=now,
    )

    project = row_to_project(row)

    assert project.id == "prj-deadbeef"
    assert project.name == "Pump rebuild"
    assert project.goal == ProjectGoal.bom_generation
    assert project.category == "Centrifugal pumps"
    assert project.status == ProjectStatus.draft
    assert project.completion_score == 0
    assert project.documents == []
    assert project.blocking_fields_count == 0
    assert project.conflicts_count == 0
    assert project.pending_approvals_count == 0
    assert project.created_at == now
    assert project.updated_at == now
