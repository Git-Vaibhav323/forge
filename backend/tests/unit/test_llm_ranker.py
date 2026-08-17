from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from shared.completeness import RequiredField
from shared.llm_ranker import LlmSettings, rank_next_field
from shared.question_engine import JobContext


def _missing() -> list[RequiredField]:
    return [
        RequiredField(
            field="model",
            text="Model?",
            why_asked="Need model",
            priority="critical",
        ),
        RequiredField(
            field="manufacturer",
            text="Maker?",
            why_asked="Need maker",
            priority="high",
        ),
    ]


def _ctx() -> JobContext:
    return JobContext(
        project_id="prj-x",
        name="Job",
        goal="product_configuration",
        category="valve",
        document_names=("a.pdf",),
        evidence_values={},
        conflicting_fields=(),
        user_answers={},
    )


def test_llm_disabled_returns_none() -> None:
    assert rank_next_field(
        LlmSettings(provider="off", api_key=None),
        context=_ctx(),
        missing=_missing(),
        conflicting=(),
    ) is None


def test_gemini_valid_response() -> None:
    def fake_post(url, **kwargs):
        request = httpx.Request("POST", str(url))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "field": "manufacturer",
                                            "text": "Who made the valve on job ABC?",
                                            "whyAsked": "Need the OEM for this replacement.",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
            request=request,
        )

    with patch("shared.llm_ranker.httpx.post", side_effect=fake_post):
        from shared.llm_ranker import plan_next_question

        plan = plan_next_question(
            LlmSettings(provider="gemini", api_key="test-key"),
            context=_ctx(),
            missing=_missing(),
            conflicting=(),
        )
    assert plan is not None
    assert plan.field == "manufacturer"
    assert plan.text is not None
    assert "valve" in plan.text.lower() or "made" in plan.text.lower()


def test_invalid_llm_field_falls_back() -> None:
    def fake_post(url, **kwargs):
        request = httpx.Request("POST", str(url))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps({"field": "not_a_field"})}]}}
                ]
            },
            request=request,
        )

    with patch("shared.llm_ranker.httpx.post", side_effect=fake_post):
        field = rank_next_field(
            LlmSettings(provider="gemini", api_key="test-key"),
            context=_ctx(),
            missing=_missing(),
            conflicting=(),
        )
    assert field is None


def test_llm_http_error_falls_back() -> None:
    def fake_post(url, **kwargs):
        raise httpx.TimeoutException("timeout")

    with patch("shared.llm_ranker.httpx.post", side_effect=fake_post):
        field = rank_next_field(
            LlmSettings(provider="gemini", api_key="test-key"),
            context=_ctx(),
            missing=_missing(),
            conflicting=(),
        )
    assert field is None
