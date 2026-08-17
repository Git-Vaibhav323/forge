from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import (
    BomLineRow,
    CompatibilityFindingRow,
    ProductRelationshipRow,
    ProjectRow,
)
from shared.relationship_sync import resolve_relationships
from shared.schemas import (
    BomLine,
    CompatibilityFinding,
    ProductRelationship,
    RelationshipView,
)


def _ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return list(json.loads(raw))
    except ValueError:
        return []


def row_to_relationship(row: ProductRelationshipRow) -> ProductRelationship:
    return ProductRelationship.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "relatedProjectId": row.related_project_id,
            "relation": row.relation,
            "basis": row.basis,
            "confidence": row.confidence,
        }
    )


def row_to_finding(row: CompatibilityFindingRow) -> CompatibilityFinding:
    return CompatibilityFinding.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "rule": row.rule,
            "field": row.field,
            "status": row.status,
            "severity": row.severity,
            "requiredValue": row.required_value,
            "ratedValue": row.rated_value,
            "reason": row.reason,
            "evidenceIds": _ids(row.evidence_ids_json),
        }
    )


def row_to_bom_line(row: BomLineRow) -> BomLine:
    return BomLine.model_validate(
        {
            "id": row.id,
            "projectId": row.project_id,
            "position": row.position,
            "role": row.role,
            "component": row.component,
            "quantity": row.quantity,
            "unit": row.unit,
            "status": row.status,
            "sourceField": row.source_field,
            "reason": row.reason,
            "evidenceIds": _ids(row.evidence_ids_json),
        }
    )


def read_view(db: Session, project_id: str) -> RelationshipView:
    """Return whatever is currently stored, without recomputing."""
    variants = db.scalars(
        select(ProductRelationshipRow)
        .where(ProductRelationshipRow.project_id == project_id)
        .order_by(ProductRelationshipRow.related_project_id.asc())
    ).all()
    findings = db.scalars(
        select(CompatibilityFindingRow)
        .where(CompatibilityFindingRow.project_id == project_id)
        .order_by(CompatibilityFindingRow.rule.asc())
    ).all()
    lines = db.scalars(
        select(BomLineRow)
        .where(BomLineRow.project_id == project_id)
        .order_by(BomLineRow.position.asc())
    ).all()

    return RelationshipView.model_validate(
        {
            "variants": [row_to_relationship(r) for r in variants],
            "findings": [row_to_finding(r) for r in findings],
            "bomLines": [row_to_bom_line(r) for r in lines],
        }
    )


def resolve(db: Session, project: ProjectRow) -> RelationshipView:
    """Re-derive variants, compatibility findings and BOM lines, then return them."""
    resolve_relationships(db, project)
    db.commit()
    return read_view(db, project.id)
