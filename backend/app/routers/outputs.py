"""
Generation + QA Service (placeholder).

Owns: producing the final artifact (config, BOM, quote, datasheet, …) from
approved facts only, then running a QA pass before delivery.
Maps to: context.md → "Services" → Generation Service + QA Service.

Hard rule (see context.md → "Generation"):
    The generator uses ONLY approved facts, approved answers, approved
    calculations, and cited evidence. No unsupported claims, no general
    model knowledge for technical values.

TODO(Phase 5+, see context.md → Build order):
  - Render the goal-specific template (Jinja2 + ReportLab / python-docx).
  - Run QA: every field evidence-backed, no unresolved conflicts, units
    consistent, high-risk fields approved.
  - Store the artifact and return a download URL.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import OutputArtifact, OutputGenerateInput

router = APIRouter(prefix="/api/projects", tags=["outputs"])


@router.get("/{project_id}/outputs", response_model=list[OutputArtifact])
def list_outputs(project_id: str) -> list[OutputArtifact]:
    # TODO: return generated artifacts for this project.
    return []


@router.post("/{project_id}/outputs", response_model=OutputArtifact)
def generate_output(project_id: str, payload: OutputGenerateInput) -> OutputArtifact:
    # TODO: gate on completeness + zero pending approvals, then generate.
    raise HTTPException(
        status_code=501,
        detail="Output generation not implemented — see backend/app/routers/outputs.py",
    )
