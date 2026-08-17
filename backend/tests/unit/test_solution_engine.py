from __future__ import annotations

from unittest.mock import patch

from shared.document_text import DocumentExcerpt
from shared.llm_ranker import LlmSettings
from shared.solution_engine import EvidenceFact, SolutionContext, build_solution


def test_rule_fallback_when_llm_off():
    result = build_solution(
        SolutionContext(
            project_name="NEW TECH STACK",
            goal="replacement_recommendation",
            category="TECHSTACK",
            answers={
                "existing_part_number": "frontend",
                "reason_for_replacement": "to make frontend more interactive",
            },
        ),
        llm=LlmSettings(provider="off", api_key=None),
    )
    assert result is not None
    assert any(item.area == "Scope" for item in result.items)


def test_llm_solution_parsed_when_enabled():
    payload = """
    {
      "summary": "Upgrade frontend for interactivity based on user need and doc review.",
      "recommendations": [
        {
          "area": "UI layer",
          "current_state": "static frontend",
          "suggested_change": "Introduce React with client-side routing.",
          "priority": "high",
          "rationale": "User answer: make frontend more interactive; doc mentions legacy jQuery."
        }
      ]
    }
    """
    ctx = SolutionContext(
        project_name="NEW TECH STACK",
        goal="replacement_recommendation",
        category="TECHSTACK",
        answers={
            "existing_part_number": "frontend",
            "reason_for_replacement": "make frontend more interactive",
        },
        evidence=[
            EvidenceFact(
                name="framework",
                value="jQuery 1.x",
                unit=None,
                status="known",
                source="stack.pdf, p.2",
            )
        ],
        document_excerpts=[
            DocumentExcerpt(
                document_id="doc-1",
                document_name="stack.pdf",
                page=2,
                text="Current stack uses jQuery 1.x on all pages.",
            )
        ],
        document_names=("stack.pdf",),
    )
    with patch("shared.solution_engine.complete_json", return_value=payload):
        result = build_solution(ctx, llm=LlmSettings(provider="gemini", api_key="test-key"))

    assert result is not None
    assert "interactivity" in result.summary.lower()
    assert result.items[0].suggested_change.startswith("Introduce React")
    assert "jQuery" in result.items[0].rationale


def test_llm_failure_falls_back_to_rules():
    ctx = SolutionContext(
        project_name="Gate valve swap",
        goal="replacement_recommendation",
        category="valve",
        answers={
            "existing_part_number": "MFC-GV-100",
            "reason_for_replacement": "obsolete — no longer stocked",
        },
    )
    with patch("shared.solution_engine.complete_json", return_value=None):
        result = build_solution(ctx, llm=LlmSettings(provider="gemini", api_key="test-key"))

    assert result is not None
    assert any("supersession" in item.suggested_change.lower() for item in result.items)


def test_non_solution_goal_returns_none():
    assert (
        build_solution(
            SolutionContext(
                project_name="x",
                goal="unknown_goal",
                category="valve",
                answers={},
            )
        )
        is None
    )
