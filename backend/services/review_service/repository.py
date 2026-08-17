from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import ProjectRow, ReviewDecisionRow, ReviewItemRow
from shared.review_sync import candidate_values, sibling_attributes, sync_reviews
from shared.schemas import ReviewDecision, ReviewItem

ACTION_STATUS = {
    "approve": "approved",
    "edit": "edited",
    "reject": "rejected",
    "unresolved": "unresolved",
}


def _decision_id() -> str:
    return f"dec-{uuid.uuid4().hex[:12]}"


def row_to_review_item(row: ReviewItemRow) -> ReviewItem:
    return ReviewItem.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "field": row.field,
            "productId": row.product_id,
            "issueType": row.issue_type,
            "severity": row.severity,
            "currentValue": row.current_value,
            "proposedValue": row.proposed_value,
            "values": json.loads(row.values_json) if row.values_json else None,
            "reason": row.reason,
            "evidenceIds": json.loads(row.evidence_ids_json)
            if row.evidence_ids_json
            else [],
            "affectedProducts": row.affected_products,
            "status": row.status,
            "createdAt": row.created_at,
        }
    )


def list_review_items(db: Session, project: ProjectRow) -> list[ReviewItem]:
    """Return the review queue, reconciled against the current record."""
    sync_reviews(db, project)
    rows = db.scalars(
        select(ReviewItemRow)
        .where(ReviewItemRow.project_id == project.id)
        .order_by(ReviewItemRow.created_at.asc())
    ).all()
    return [row_to_review_item(row) for row in rows]


def submit_decision(
    db: Session,
    project: ProjectRow,
    review_id: str,
    decision: ReviewDecision,
) -> ReviewItem:
    """Record a human decision, apply it, and optionally fix sibling jobs."""
    item = db.get(ReviewItemRow, review_id)
    if item is None or item.project_id != project.id:
        raise KeyError(review_id)

    action = (decision.action or "").strip().lower()
    if action not in ACTION_STATUS:
        raise ValueError(f"Unknown action: {decision.action}")

    typed = (decision.value or "").strip() or None
    if action == "edit" and not typed:
        raise ValueError("An edited value cannot be empty")

    # Approving takes the value the reviewer saw unless they typed another.
    # A high-risk item with nothing proposed is an explicit acknowledgement,
    # not a value — it clears the hold without inventing a fact.
    resolved: str | None = None
    if action == "approve":
        resolved = typed or item.proposed_value
    elif action == "edit":
        resolved = typed

    affected = 0
    if decision.propagate and resolved and action in {"approve", "edit"}:
        affected = _propagate(db, project, item, resolved)

    item.status = ACTION_STATUS[action]
    item.resolved_value = resolved
    item.updated_at = datetime.now(timezone.utc)

    db.add(
        ReviewDecisionRow(
            id=_decision_id(),
            review_item_id=item.id,
            project_id=project.id,
            field=item.field,
            action=action,
            value=resolved,
            propagate=bool(decision.propagate),
            affected_fields=affected,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.flush()

    # Replays the decision onto attributes and refreshes conflict/approval counts.
    sync_reviews(db, project)
    db.commit()

    refreshed = db.get(ReviewItemRow, review_id)
    assert refreshed is not None
    return row_to_review_item(refreshed)


def _propagate(
    db: Session, project: ProjectRow, item: ReviewItemRow, resolved: str
) -> int:
    """Apply the corrected value to sibling jobs carrying the same wrong value."""
    siblings = sibling_attributes(db, project, item.field, candidate_values(item))
    now = datetime.now(timezone.utc)
    for attr in siblings:
        attr.raw_value = resolved
        attr.normalized_value = resolved
        attr.status = "verified"
        attr.confidence = 1.0
        attr.updated_at = now
    db.flush()
    return len(siblings)


def list_decisions(db: Session, project_id: str) -> list[ReviewDecisionRow]:
    """Audit trail, oldest first."""
    return list(
        db.scalars(
            select(ReviewDecisionRow)
            .where(ReviewDecisionRow.project_id == project_id)
            .order_by(ReviewDecisionRow.created_at.asc())
        ).all()
    )
