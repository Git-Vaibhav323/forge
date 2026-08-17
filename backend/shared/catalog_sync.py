"""Persist catalog ingest and brand evaluation results."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shared.brand_evaluator import CatalogEvaluationResult, evaluate_catalog
from shared.catalog_parser import CatalogPart
from shared.db.models import CatalogLineRow, DocumentRow, ProjectRow


def _line_id() -> str:
    return f"cat-{uuid.uuid4().hex[:12]}"


def sync_catalog_evaluation(
    db: Session,
    project: ProjectRow,
    document: DocumentRow,
    parts: list[CatalogPart],
) -> CatalogEvaluationResult:
    """Evaluate catalog rows and replace persisted lines for this document."""
    result = evaluate_catalog(parts)
    now = datetime.now(timezone.utc)

    db.execute(
        delete(CatalogLineRow).where(
            CatalogLineRow.project_id == project.id,
            CatalogLineRow.document_id == document.id,
        )
    )

    for ev in result.parts:
        part = ev.part
        db.add(
            CatalogLineRow(
                id=_line_id(),
                project_id=project.id,
                document_id=document.id,
                row_index=part.row_index,
                mfg_part_num=part.mfg_part_num,
                part_desc=part.part_desc,
                e1_brand=part.e1_brand,
                unilog_brand=part.unilog_brand,
                dib_brand=part.dib_brand,
                part_manuf=part.part_manuf,
                e1_brand_norm=part.e1_brand_norm,
                unilog_brand_norm=part.unilog_brand_norm,
                dib_brand_norm=part.dib_brand_norm,
                part_manuf_norm=part.part_manuf_norm,
                evaluation_status=ev.status,
                recommended_brand=ev.recommended_brand,
                brand_source=ev.brand_source,
                findings_json=json.dumps(
                    [
                        {
                            "rule": f.rule,
                            "severity": f.severity,
                            "field": f.field,
                            "message": f.message,
                        }
                        for f in ev.findings
                    ]
                ),
                created_at=now,
                updated_at=now,
            )
        )

    db.flush()

    # Surface conflict volume on the project for existing dashboards.
    project.conflicts_count = result.summary.conflict + result.summary.needs_review
    project.updated_at = now
    document.status = "processed"
    if document.pages is None:
        document.pages = len(parts)

    return result


def list_catalog_lines(db: Session, project_id: str) -> list[CatalogLineRow]:
    return list(
        db.scalars(
            select(CatalogLineRow)
            .where(CatalogLineRow.project_id == project_id)
            .order_by(CatalogLineRow.row_index.asc())
        ).all()
    )
