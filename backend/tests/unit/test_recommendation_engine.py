from __future__ import annotations

from shared.recommendation_engine import RecommendationContext, build_recommendations


def test_techstack_replacement_is_grounded_in_answers():
    result = build_recommendations(
        RecommendationContext(
            project_name="NEW TECH STACK",
            goal="replacement_recommendation",
            category="TECHSTACK",
            answers={
                "existing_part_number": "frontend",
                "reason_for_replacement": "to make frontend more interactive",
            },
        )
    )
    assert result is not None
    assert "NEW TECH STACK" in result.summary
    assert any(item.area == "Scope" for item in result.items)


def test_industrial_obsolete_produces_catalog_guidance():
    result = build_recommendations(
        RecommendationContext(
            project_name="Gate valve swap",
            goal="replacement_recommendation",
            category="valve",
            answers={
                "existing_part_number": "MFC-GV-100",
                "reason_for_replacement": "obsolete — no longer stocked",
            },
            established_fields=("maximum_pressure: 285 PSI",),
            withheld_fields=("model",),
        )
    )
    assert result is not None
    assert any("supersession" in item.suggested_change.lower() for item in result.items)
    assert any(item.area == "Record completeness" for item in result.items)


def test_datasheet_goal_returns_analysis():
    result = build_recommendations(
        RecommendationContext(
            project_name="Valve datasheet",
            goal="product_datasheet",
            category="valve",
            answers={},
            established_fields=("maximum_pressure: 285 PSI",),
            withheld_fields=("model",),
        )
    )
    assert result is not None
    assert any(item.area == "Incomplete specification" for item in result.items)


def test_unknown_goal_returns_none():
    assert (
        build_recommendations(
            RecommendationContext(
                project_name="x",
                goal="unknown_goal",
                category="valve",
                answers={},
            )
        )
        is None
    )
