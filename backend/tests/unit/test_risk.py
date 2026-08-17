from __future__ import annotations

from shared.risk import (
    critical_fields_for_job,
    requires_review_hold,
)


def test_software_job_treats_platform_as_critical():
    fields = critical_fields_for_job("installation_package", "Software or app")
    assert "platform" in fields
    assert "power_supply" in fields
    assert "supply_voltage" not in fields


def test_industrial_configuration_keeps_plant_fields_critical():
    fields = critical_fields_for_job("product_configuration", "Industrial equipment valve")
    assert "supply_voltage" in fields
    assert "maximum_pressure" in fields


def test_datasheet_job_only_goal_critical_fields():
    fields = critical_fields_for_job("product_datasheet", "Software or app")
    assert fields == frozenset({"key_rating", "platform"})


def test_customer_request_category_adds_request_summary():
    assert requires_review_hold(
        "request_summary",
        "rfq_response",
        "Customer request",
    )


def test_model_is_not_critical_on_goal_only_jobs():
    assert not requires_review_hold(
        "model",
        "installation_package",
        "Software or app",
    )
