"""Rule-based question engine — evidence, conditional rules, built-in copy.

Layers:
  1. Goal/category field registry (+ conditional rules)
  2. Evidence pre-fill from M4 attributes (skip known fields)
  3. User answers from questions table (authoritative)
  4. Built-in field order + scenario copy (never LLM for question text)
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.completeness import RequiredField, is_satisfied, next_unsatisfied, score_answers
from shared.db.models import AttributeRow, DocumentRow, ProjectRow, QuestionRow
from shared.field_registry import active_required_fields
from shared.scenario_copy import ScenarioContext, enrich_question


# Attribute statuses that may pre-fill a question (never invent).
EVIDENCE_SATISFIES = frozenset({"known", "verified", "derived"})
EVIDENCE_BLOCKS = frozenset({"conflicting", "needs_review"})


@dataclass(frozen=True)
class JobContext:
    project_id: str
    name: str
    goal: str
    category: str
    document_names: tuple[str, ...]
    evidence_values: dict[str, str]
    conflicting_fields: tuple[str, ...]
    user_answers: dict[str, str]

    @property
    def merged_answers(self) -> dict[str, str]:
        """User answers win over evidence when both exist."""
        merged = dict(self.evidence_values)
        merged.update(self.user_answers)
        return merged


def list_question_rows(db: Session, project_id: str) -> list[QuestionRow]:
    return list(
        db.scalars(
            select(QuestionRow)
            .where(QuestionRow.project_id == project_id)
            .order_by(QuestionRow.created_at.asc())
        ).all()
    )


def list_attribute_rows(db: Session, project_id: str) -> list[AttributeRow]:
    return list(
        db.scalars(
            select(AttributeRow)
            .where(AttributeRow.project_id == project_id)
            .order_by(AttributeRow.name.asc())
        ).all()
    )


def evidence_answer_map(attributes: list[AttributeRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in attributes:
        if row.status in EVIDENCE_BLOCKS:
            continue
        if row.status not in EVIDENCE_SATISFIES:
            continue
        value = (row.normalized_value or row.raw_value or "").strip()
        if not value:
            continue
        if row.confidence < 0.5:
            continue
        out[row.name] = value
    return out


def conflicting_field_names(attributes: list[AttributeRow]) -> list[str]:
    return [row.name for row in attributes if row.status in EVIDENCE_BLOCKS]


def user_answers_map(rows: list[QuestionRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if row.answer:
            out[row.field] = row.answer
    return out


def build_job_context(
    db: Session,
    project: ProjectRow,
    question_rows: list[QuestionRow],
    attributes: list[AttributeRow] | None = None,
) -> JobContext:
    if attributes is None:
        attributes = list_attribute_rows(db, project.id)
    documents = list(
        db.scalars(
            select(DocumentRow)
            .where(DocumentRow.project_id == project.id)
            .order_by(DocumentRow.uploaded_at.asc())
        ).all()
    )
    return JobContext(
        project_id=project.id,
        name=project.name,
        goal=project.goal,
        category=project.category,
        document_names=tuple(d.filename for d in documents),
        evidence_values=evidence_answer_map(attributes),
        conflicting_fields=tuple(conflicting_field_names(attributes)),
        user_answers=user_answers_map(question_rows),
    )


def active_specs(ctx: JobContext) -> list[RequiredField]:
    return active_required_fields(ctx.goal, ctx.category, ctx.merged_answers)


def completeness_for_job(ctx: JobContext) -> tuple[int, int]:
    return score_answers(active_specs(ctx), ctx.merged_answers)


@dataclass(frozen=True)
class NextQuestion:
    spec: RequiredField
    text: str
    why_asked: str


def pick_next_question(ctx: JobContext) -> NextQuestion | None:
    """Pick the next built-in question from registry order and prior answers."""
    specs = active_specs(ctx)
    spec = next_unsatisfied(specs, ctx.merged_answers, goal=ctx.goal)
    if spec is None:
        return None
    scenario = ScenarioContext(
        name=ctx.name,
        goal=ctx.goal,
        category=ctx.category,
        document_names=ctx.document_names,
    )
    enriched = enrich_question(spec, scenario)
    return NextQuestion(spec=enriched.spec, text=enriched.text, why_asked=enriched.why_asked)
