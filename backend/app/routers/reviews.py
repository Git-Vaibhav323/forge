"""
Review / Human-Approval Service (placeholder).

Owns: review tasks for conflicts and high-risk fields, reviewer decisions,
bulk-correction propagation, and the audit trail.
Maps to: context.md → "Services" → Review Service + Risk/Approval Policy.

Governance rule (see context.md → "Approval policy"):
    Conflicts, high-risk fields, safety-critical values, bulk corrections,
    and published-data changes ALWAYS pause here for human approval.
    Everything else proceeds automatically.

TODO(Phase 3, see context.md → Build order):
  - Persist review tasks and decisions.
  - On "approve & propagate", find sibling records via the similarity /
    error-fingerprint logic and stage a bulk correction (with rollback).
  - Emit HumanDecisionRecorded so the Workflow Service can resume.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ReviewDecision, ReviewItem

router = APIRouter(prefix="/api", tags=["reviews"])


@router.get("/projects/{project_id}/reviews", response_model=list[ReviewItem])
def list_reviews(project_id: str) -> list[ReviewItem]:
    # TODO: return pending + resolved review tasks for this project.
    return []


@router.post("/reviews/{review_id}/decision", response_model=ReviewItem)
def submit_decision(review_id: str, payload: ReviewDecision) -> ReviewItem:
    # TODO: apply the approved/edited value, record it in the audit log, and
    # if payload.propagate, stage the bulk correction across sibling SKUs.
    raise HTTPException(
        status_code=501,
        detail="Review decisions not implemented — see backend/app/routers/reviews.py",
    )
