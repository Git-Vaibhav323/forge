from shared.completeness import (
    is_satisfied,
    next_unsatisfied,
    required_fields,
    score_answers,
)


def test_product_configuration_asks_fail_safe_and_voltage() -> None:
    fields = {spec.field for spec in required_fields("product_configuration", "solenoid_valve")}
    assert "model" in fields
    assert "fail_safe_mode" in fields
    assert "supply_voltage" in fields
    assert "operating_medium" in fields


def test_sensor_category_adds_range() -> None:
    fields = {spec.field for spec in required_fields("rfq_response", "temperature_sensor")}
    assert "measurement_range" in fields
    assert "customer_requirement" in fields


def test_i_dont_know_is_not_satisfied() -> None:
    assert is_satisfied("Water") is True
    assert is_satisfied("Not applicable") is True
    assert is_satisfied("I don't know") is False
    assert is_satisfied("") is False
    assert is_satisfied(None) is False


def test_score_and_next_question_order() -> None:
    specs = required_fields("product_configuration", "solenoid valve")
    score, blocking = score_answers(specs, {})
    assert score == 0
    assert blocking == len(specs)

    nxt = next_unsatisfied(specs, {})
    assert nxt is not None
    assert nxt.priority == "critical"

    answers = {nxt.field: "SV-24"}
    score_after, blocking_after = score_answers(specs, answers)
    assert score_after > 0
    assert blocking_after == blocking - 1
    assert next_unsatisfied(specs, answers) is not None
    assert next_unsatisfied(specs, answers).field != nxt.field


def test_all_answered_is_complete() -> None:
    specs = required_fields("product_datasheet", "")
    answers = {spec.field: "ok" for spec in specs}
    score, blocking = score_answers(specs, answers)
    assert score == 100
    assert blocking == 0
    assert next_unsatisfied(specs, answers) is None
