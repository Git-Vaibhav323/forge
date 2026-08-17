"""Built-in work types — plain labels for any job, optional industrial depth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkCategory:
    id: str
    label: str
    description: str
    industrial: bool = False


# Alias kept for older imports.
ProductCategory = WorkCategory

WORK_CATEGORIES: tuple[WorkCategory, ...] = (
    WorkCategory(
        id="physical_product",
        label="Physical product",
        description="Hardware, equipment, or anything you can hold or ship.",
    ),
    WorkCategory(
        id="software_app",
        label="Software or app",
        description="Applications, platforms, integrations, or internal tools.",
    ),
    WorkCategory(
        id="service_process",
        label="Service or process",
        description="A workflow, offering, or repeatable way work gets done.",
    ),
    WorkCategory(
        id="content_documents",
        label="Content or documents",
        description="Reports, guides, marketing packs, or document bundles.",
    ),
    WorkCategory(
        id="customer_request",
        label="Customer request",
        description="Something a client or stakeholder asked for.",
    ),
    WorkCategory(
        id="upgrade_replacement",
        label="Upgrade or replacement",
        description="Swapping, modernizing, or retiring something that exists today.",
    ),
    WorkCategory(
        id="kit_bundle",
        label="Kit or bundle",
        description="Multiple items sold or delivered together.",
    ),
    WorkCategory(
        id="industrial_equipment",
        label="Industrial equipment",
        description="Plant gear — valves, pumps, sensors, motors, and similar.",
        industrial=True,
    ),
    WorkCategory(
        id="other",
        label="Other",
        description="Doesn't fit above — describe it in the job name.",
    ),
)

PRODUCT_CATEGORIES = WORK_CATEGORIES


def normalise_category(value: str) -> str:
    return (value or "").lower().replace("-", " ").replace("_", " ")


def is_industrial_category(category: str) -> bool:
    hay = normalise_category(category)
    for item in WORK_CATEGORIES:
        if item.id.replace("_", " ") in hay or item.label.lower() in hay:
            return item.industrial
    industrial_tokens = (
        "valve",
        "pump",
        "sensor",
        "motor",
        "solenoid",
        "actuator",
        "transmitter",
        "industrial equipment",
    )
    return any(token in hay for token in industrial_tokens)


def category_label(category_id: str) -> str:
    for item in WORK_CATEGORIES:
        if item.id == category_id:
            return item.label
    return category_id.replace("_", " ").title()
