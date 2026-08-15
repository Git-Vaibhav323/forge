"""
Extraction / Evidence Service (placeholder).

Owns: structured product observations, each linked to source evidence
(document, page, quote, confidence, status).
Maps to: context.md → "Services" → Extraction Service + Evidence store.

TODO(Phase 2, see context.md → Build order):
  - Read evidence chunks produced by the Document Intelligence Service.
  - Run structured extraction (small LLM + Pydantic schema) to fill the
    canonical Attribute shape.
  - Normalize units (Pint) while preserving the raw value.
  - Never overwrite a value silently — conflicting sources become a
    ReviewItem, not a merged attribute.

Returns an empty list until the pipeline exists.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import Attribute

router = APIRouter(prefix="/api/projects", tags=["attributes"])


@router.get("/{project_id}/attributes", response_model=list[Attribute])
def list_attributes(project_id: str) -> list[Attribute]:
    # TODO: query the evidence DB for this project's observations.
    return []
