from __future__ import annotations

from collections.abc import Generator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from services.generation_service.repository import (
    generate_output,
    list_outputs,
    read_output_bytes,
)
from shared.db.models import ProjectRow
from shared.db.session import get_session_factory
from shared.schemas import OutputArtifact, OutputGenerateInput

router = APIRouter(prefix="/api", tags=["outputs"])


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def _project(db: Session, project_id: str) -> ProjectRow:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/outputs", response_model=list[OutputArtifact])
def get_outputs(project_id: str, db: Session = Depends(get_db)) -> list[OutputArtifact]:
    _project(db, project_id)
    return list_outputs(db, project_id)


@router.post("/projects/{project_id}/outputs", response_model=OutputArtifact)
def post_output(
    project_id: str,
    payload: OutputGenerateInput,
    db: Session = Depends(get_db),
) -> OutputArtifact:
    project = _project(db, project_id)
    output_type = (payload.type or "").strip() or project.goal
    return generate_output(db, project, output_type)


@router.get("/outputs/{output_id}/download")
def download_output(output_id: str, db: Session = Depends(get_db)) -> Response:
    try:
        row, body = read_output_bytes(db, output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Output not found") from None
    except ValueError as exc:
        # Blocked by QA — there is no file, and inventing one is the whole
        # thing this system refuses to do.
        raise HTTPException(status_code=409, detail=str(exc)) from None

    return Response(
        content=body,
        media_type=row.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(row.filename)}"
            )
        },
    )
