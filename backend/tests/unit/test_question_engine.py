from __future__ import annotations

from datetime import datetime, timezone

from shared.completeness import RequiredField, is_satisfied
from shared.db.models import AttributeRow
from shared.field_registry import active_required_fields
from shared.question_engine import (
    JobContext,
    evidence_answer_map,
    pick_next_question,
    user_answers_map,
)
from shared.llm_ranker import LlmSettings


def _attr(
    name: str,
    raw: str,
    *,
    status: str = "known",
    confidence: float = 0.9,
) -> AttributeRow:
    return AttributeRow(
        id=f"attr-{name}",
        project_id="prj-test",
        name=name,
        raw_value=raw,
        normalized_value=raw,
        unit=None,
        confidence=confidence,
        status=status,
        risk_level="low",
        updated_at=datetime.now(timezone.utc),
    )


def test_evidence_prefill_skips_known_fields() -> None:
    attributes = [_attr("manufacturer", "Meridian"), _attr("model", "MFC-GV-200")]
    evidence = evidence_answer_map(attributes)
    assert evidence["manufacturer"] == "Meridian"
    assert evidence["model"] == "MFC-GV-200"

    ctx = JobContext(
        project_id="prj-test",
        name="Test job",
        goal="product_configuration",
        category="valve",
        document_names=("datasheet.pdf",),
        evidence_values=evidence,
        conflicting_fields=(),
        user_answers={},
    )
    specs = active_required_fields(ctx.goal, ctx.category, ctx.merged_answers)
    nxt = pick_next_question(ctx, LlmSettings(provider="off", api_key=None))
    assert nxt is not None
    assert nxt.spec.field not in {"manufacturer", "model"}


def test_conflicting_evidence_does_not_prefill() -> None:
    attributes = [_attr("supply_voltage", "24V / 110V", status="conflicting")]
    evidence = evidence_answer_map(attributes)
    assert "supply_voltage" not in evidence


def test_conditional_rule_adds_hazardous_class() -> None:
    answers = {"installation_environment": "Hazardous area"}
    specs = active_required_fields("product_configuration", "valve", answers)
    fields = {s.field for s in specs}
    assert "hazardous_area_class" in fields


def test_conditional_rule_steam_adds_max_temperature() -> None:
    answers = {"operating_medium": "Steam"}
    specs = active_required_fields("product_configuration", "valve", answers)
    assert "max_temperature" in {s.field for s in specs}


def test_user_answer_overrides_evidence() -> None:
    ctx = JobContext(
        project_id="prj-test",
        name="Test",
        goal="product_configuration",
        category="valve",
        document_names=(),
        evidence_values={"model": "From-PDF"},
        conflicting_fields=(),
        user_answers={"model": "User-Override"},
    )
    assert ctx.merged_answers["model"] == "User-Override"


def test_idk_is_unsatisfied() -> None:
    assert is_satisfied("idk") is False


def test_goal_fields_asked_before_common() -> None:
    ctx = JobContext(
        project_id="prj-test",
        name="Replace legacy pump",
        goal="replacement_recommendation",
        category="pump",
        document_names=("datasheet.pdf",),
        evidence_values={},
        conflicting_fields=(),
        user_answers={},
    )
    nxt = pick_next_question(ctx, LlmSettings(provider="off", api_key=None))
    assert nxt is not None
    assert nxt.spec.field in {"existing_part_number", "reason_for_replacement"}


def test_pick_next_without_llm_uses_priority() -> None:
    ctx = JobContext(
        project_id="prj-test",
        name="Test",
        goal="product_configuration",
        category="valve",
        document_names=(),
        evidence_values={},
        conflicting_fields=(),
        user_answers={},
    )
    nxt = pick_next_question(ctx, LlmSettings(provider="off", api_key=None))
    assert nxt is not None
    assert nxt.spec.priority == "critical"
