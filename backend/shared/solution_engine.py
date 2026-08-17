"""Generate output solutions from questions, evidence, and document text.

When LLM_PROVIDER is enabled, calls Gemini/Groq with the full job context.
Otherwise — or on failure — falls back to the rule-based recommendation_engine.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field as dataclass_field

from shared.document_text import DocumentExcerpt
from shared.llm_ranker import LlmSettings, complete_json
from shared.recommendation_engine import (
    RecommendationContext,
    RecommendationResult,
    build_recommendations,
)

logger = logging.getLogger(__name__)

SOLUTION_GOALS = frozenset(
    {
        "replacement_recommendation",
        "rfq_response",
        "product_configuration",
        "product_datasheet",
        "installation_package",
        "bom_generation",
        "technical_quotation",
    }
)


@dataclass(frozen=True)
class EvidenceFact:
    name: str
    value: str
    unit: str | None
    status: str
    source: str


@dataclass
class SolutionContext:
    project_name: str
    goal: str
    category: str
    answers: dict[str, str]
    evidence: list[EvidenceFact] = dataclass_field(default_factory=list)
    document_excerpts: list[DocumentExcerpt] = dataclass_field(default_factory=list)
    document_names: tuple[str, ...] = ()


def _build_prompt(ctx: SolutionContext) -> str:
    answered = [
        f"  {field}: {value!r}"
        for field, value in sorted(ctx.answers.items())
        if value
    ]
    evidence_lines = [
        f"  {fact.name}: {fact.value!r}"
        + (f" {fact.unit}" if fact.unit else "")
        + f" [{fact.status}] — {fact.source}"
        for fact in ctx.evidence
        if fact.value
    ]
    doc_blocks: list[str] = []
    for excerpt in ctx.document_excerpts:
        doc_blocks.append(
            f"--- {excerpt.document_name} (page {excerpt.page}) ---\n{excerpt.text}"
        )

    goal_label = ctx.goal.replace("_", " ")

    return (
        "You are a senior engineering analyst writing a detailed technical report. "
        "Use ONLY the user answers, verified evidence, and document excerpts below.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "summary": "<2-3 sentences: what this job is, what is sourced, what blocks completion>",\n'
        '  "recommendations": [\n'
        "    {\n"
        '      "area": "<specific engineering topic tied to this job>",\n'
        '      "current_state": "<cite exact field names/values from the record>",\n'
        '      "suggested_change": "<concrete next engineering step — not generic stack advice>",\n'
        '      "priority": "critical|high|medium",\n'
        '      "rationale": "<quote document page, field name, or user answer>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Write like a technical report appendix, not a blog post.\n"
        "- Name specific fields (pressure, model, voltage) and their sourced values.\n"
        "- For gaps, say exactly which field is missing and why that blocks the deliverable.\n"
        "- Do NOT suggest software frameworks unless category is clearly software AND documents support it.\n"
        "- Do NOT restate values for fields listed as gaps or without citations.\n"
        "- Prefer 2-4 focused items that reference this job's evidence.\n"
        f"- Deliverable type: {goal_label}.\n\n"
        f"Job name: {ctx.project_name!r}\n"
        f"Goal: {goal_label} ({ctx.goal})\n"
        f"Category: {ctx.category}\n"
        f"Uploaded documents: {', '.join(ctx.document_names) or 'none'}\n\n"
        "User answers (Questions tab):\n"
        + ("\n".join(answered) if answered else "  (none)\n")
        + "\nEvidence record (sourced fields):\n"
        + ("\n".join(evidence_lines) if evidence_lines else "  (none)\n")
        + "\nDocument excerpts:\n"
        + ("\n\n".join(doc_blocks) if doc_blocks else "  (no readable text — OCR may be off or files not uploaded)\n")
    )


def _parse_solution(raw: str) -> RecommendationResult | None:
    text = raw.strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    summary = str(payload.get("summary", "")).strip()
    items_raw = payload.get("recommendations") or payload.get("items") or []
    if not summary or not isinstance(items_raw, list):
        return None

    from shared.recommendation_engine import RecommendationItem

    items: list[RecommendationItem] = []
    for entry in items_raw:
        if not isinstance(entry, dict):
            continue
        area = str(entry.get("area", "")).strip()
        change = str(entry.get("suggested_change", "")).strip()
        if not area or not change:
            continue
        items.append(
            RecommendationItem(
                area=area,
                current_state=str(entry.get("current_state", "")).strip(),
                suggested_change=change,
                priority=str(entry.get("priority", "medium")).strip() or "medium",
                rationale=str(entry.get("rationale", "")).strip(),
            )
        )

    if not items:
        return None
    return RecommendationResult(summary=summary, items=items)


def _rule_fallback(ctx: SolutionContext) -> RecommendationResult | None:
    established = tuple(
        f"{fact.name}: {fact.value}" + (f" {fact.unit}" if fact.unit else "")
        for fact in ctx.evidence
        if fact.value and fact.status in {"known", "verified", "derived"}
    )
    withheld = tuple(
        fact.name for fact in ctx.evidence if fact.status not in {"known", "verified", "derived"}
    )
    return build_recommendations(
        RecommendationContext(
            project_name=ctx.project_name,
            goal=ctx.goal,
            category=ctx.category,
            answers=ctx.answers,
            document_names=ctx.document_names,
            established_fields=established,
            withheld_fields=withheld,
        )
    )


def _generic_fallback(ctx: SolutionContext) -> RecommendationResult:
    """Minimal output when neither LLM nor rule engine applies."""
    need = (
        ctx.answers.get("reason_for_replacement")
        or ctx.answers.get("customer_requirement")
        or ctx.answers.get("description")
        or "requirements captured on this job"
    )
    from shared.recommendation_engine import RecommendationItem

    doc_note = (
        f"{len(ctx.document_excerpts)} document page(s) reviewed"
        if ctx.document_excerpts
        else "no document text available — enable OCR or upload text-based PDFs"
    )
    return RecommendationResult(
        summary=(
            f"Analysis for “{ctx.project_name}” based on {len(ctx.answers)} answer(s), "
            f"{len(ctx.evidence)} evidence field(s), and {doc_note}."
        ),
        items=[
            RecommendationItem(
                area="Next steps",
                current_state=need,
                suggested_change=(
                    "Review sourced evidence and document excerpts; confirm gaps "
                    "on the Review tab before quoting or replacing."
                ),
                priority="high",
                rationale=f"Derived from job context ({doc_note}).",
            )
        ],
    )


def build_solution(
    ctx: SolutionContext,
    llm: LlmSettings | None = None,
) -> RecommendationResult | None:
    """Return recommendations for goals that produce advisory outputs."""
    if ctx.goal not in SOLUTION_GOALS:
        return None

    if llm and llm.enabled:
        prompt = _build_prompt(ctx)
        raw = complete_json(llm, prompt, timeout=25.0, max_tokens=2048)
        if raw:
            parsed = _parse_solution(raw)
            if parsed:
                logger.info(
                    "LLM solution for %s: %d recommendation(s)",
                    ctx.goal,
                    len(parsed.items),
                )
                return parsed
            logger.warning("LLM solution JSON unparseable; using rule fallback")

    ruled = _rule_fallback(ctx)
    if ruled is not None:
        return ruled

    return _generic_fallback(ctx)
