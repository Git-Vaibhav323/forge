"""Which fields appear on Evidence vs Questions — same job, different breadth."""

from __future__ import annotations

from shared.completeness import COMMON, GOAL_ONLY
from shared.question_engine import JobContext, active_specs

# Goals that upload datasheets/catalogs: Evidence shows catalog specs too.
DOCUMENT_EXTRACT_GOALS: frozenset[str] = frozenset(
    {
        "product_datasheet",
        "installation_package",
        "product_configuration",
        "bom_generation",
    }
)


def question_field_names(ctx: JobContext) -> set[str]:
    """Fields driven by Questions tab and completeness scoring."""
    return {spec.field for spec in active_specs(ctx)}


def allowed_evidence_fields(ctx: JobContext) -> set[str]:
    """Fields that may exist on the Evidence record for this job."""
    names = question_field_names(ctx)
    if ctx.goal in DOCUMENT_EXTRACT_GOALS:
        names |= {spec.field for spec in COMMON}
    return names


def extraction_targets(ctx: JobContext, hits: list) -> list[str]:
    """Fields to persist after a document re-scan."""
    names = allowed_evidence_fields(ctx)
    if ctx.goal in DOCUMENT_EXTRACT_GOALS:
        for hit in hits:
            names.add(hit.field)
    else:
        # Replacement / RFQ: only scenario fields, not regex noise from unrelated PDFs.
        pass
    return sorted(names)
