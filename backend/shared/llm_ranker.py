"""Optional LLM planning for the next question (layer 4).

Returns which field to ask AND scenario-specific wording when the API key works.
Falls back to rule-based field order + template text from completeness.py.

Recommended FREE provider: Google Gemini — https://aistudio.google.com/apikey
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from shared.completeness import RequiredField

if TYPE_CHECKING:
    from shared.question_engine import JobContext

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
LLM_TIMEOUT = 12.0


@dataclass(frozen=True)
class LlmSettings:
    provider: str  # off | gemini | groq
    api_key: str | None
    model: str | None = None

    @property
    def enabled(self) -> bool:
        return self.provider not in ("", "off", "none") and bool(self.api_key)


@dataclass(frozen=True)
class QuestionPlan:
    """LLM output — field is required; text/whyAsked override templates when set."""

    field: str
    text: str | None = None
    why_asked: str | None = None


def _build_prompt(
    ctx: JobContext,
    missing: list[RequiredField],
    conflicting: tuple[str, ...],
) -> str:
    missing_lines = []
    for spec in missing:
        line = f"- {spec.field} ({spec.priority}): default=\"{spec.text}\""
        if spec.field in ctx.evidence_values:
            line += f" [evidence: {ctx.evidence_values[spec.field]!r}]"
        missing_lines.append(line)

    answered = [
        f"  {field}: {value!r}"
        for field, value in sorted(ctx.user_answers.items())
        if value
    ]
    evidence = [
        f"  {field}: {value!r}"
        for field, value in sorted(ctx.evidence_values.items())
        if field not in ctx.user_answers
    ]

    goal_label = ctx.goal.replace("_", " ")

    return (
        "You help complete an industrial product record by asking ONE question at a time.\n"
        "Given this specific job scenario, pick the most important missing field and write\n"
        "a clear question tailored to the job name, goal, category, and uploaded documents.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "field": "<exact field name from ALLOWED list>",\n'
        '  "text": "<question shown to the user, 1 sentence>",\n'
        '  "whyAsked": "<short reason this matters for THIS job, 1 sentence>"\n'
        "}\n\n"
        "Rules:\n"
        "- field MUST be copied exactly from ALLOWED missing fields.\n"
        "- Prefer fields that match the job GOAL before generic catalog fields.\n"
        "- For replacement/RFQ jobs, ask about the installed part or customer need first.\n"
        "- Reference document filenames when relevant (e.g. profile PDF, datasheet).\n"
        "- Do not invent field names. Do not ask about fields already answered or evidenced.\n"
        "- Keep text professional and specific — not generic boilerplate.\n\n"
        f"Job name: {ctx.name!r}\n"
        f"Goal: {goal_label} ({ctx.goal})\n"
        f"Category: {ctx.category}\n"
        f"Documents: {', '.join(ctx.document_names) or 'none uploaded'}\n"
        f"Conflicting evidence: {', '.join(conflicting) or 'none'}\n\n"
        "User answers so far:\n"
        + ("\n".join(answered) if answered else "  (none)\n")
        + "\nFrom documents (not yet confirmed by user):\n"
        + ("\n".join(evidence) if evidence else "  (none)\n")
        + "\nALLOWED missing fields:\n"
        + "\n".join(missing_lines)
    )


def _parse_plan(raw: str, allowed: set[str]) -> QuestionPlan | None:
    text = raw.strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'"field"\s*:\s*"([^"]+)"', text)
        if not match:
            return None
        field = match.group(1)
        if field not in allowed:
            return None
        return QuestionPlan(field=field)

    field = str(payload.get("field", "")).strip()
    if not field or field not in allowed:
        return None
    qtext = payload.get("text")
    why = payload.get("whyAsked") or payload.get("why_asked")
    return QuestionPlan(
        field=field,
        text=str(qtext).strip() if qtext else None,
        why_asked=str(why).strip() if why else None,
    )


def _call_gemini(settings: LlmSettings, prompt: str) -> str | None:
    model = settings.model or DEFAULT_GEMINI_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    response = httpx.post(
        url,
        params={"key": settings.api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.3,
                "maxOutputTokens": 256,
            },
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts") or []
    if not parts:
        return None
    return parts[0].get("text")


def _call_groq(settings: LlmSettings, prompt: str) -> str | None:
    model = settings.model or DEFAULT_GROQ_MODEL
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        'Respond with JSON: {"field":"...","text":"...","whyAsked":"..."}'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        return None
    return choices[0].get("message", {}).get("content")


def plan_next_question(
    settings: LlmSettings,
    *,
    context: JobContext,
    missing: list[RequiredField],
    conflicting: tuple[str, ...],
) -> QuestionPlan | None:
    """Return field + optional contextual wording, or None for rule fallback."""
    if not settings.enabled or not missing:
        return None

    allowed = {spec.field for spec in missing}
    prompt = _build_prompt(context, missing, conflicting)
    try:
        if settings.provider == "gemini":
            raw = _call_gemini(settings, prompt)
        elif settings.provider == "groq":
            raw = _call_groq(settings, prompt)
        else:
            return None
        if not raw:
            return None
        plan = _parse_plan(raw, allowed)
        if plan is not None:
            return plan
        logger.warning("LLM returned unparseable plan; using rule fallback")
    except Exception as exc:
        logger.warning("LLM planner failed (%s); using rule fallback", exc)
    return None


# Backward-compatible alias used in tests
def rank_next_field(
    settings: LlmSettings,
    *,
    context: JobContext,
    missing: list[RequiredField],
    conflicting: tuple[str, ...],
) -> str | None:
    plan = plan_next_question(
        settings, context=context, missing=missing, conflicting=conflicting
    )
    return plan.field if plan else None
