"""Rule-based engineering analysis — no LLM, no external API.

Turns sourced record data and user answers into report-grade analysis rows.
Generic stack/UX templates are avoided unless the job is clearly non-industrial.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field


@dataclass(frozen=True)
class RecommendationItem:
    area: str
    current_state: str
    suggested_change: str
    priority: str  # critical | high | medium
    rationale: str


@dataclass
class RecommendationResult:
    summary: str
    items: list[RecommendationItem] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class RecommendationContext:
    project_name: str
    goal: str
    category: str
    answers: dict[str, str]
    document_names: tuple[str, ...] = ()
    established_fields: tuple[str, ...] = ()
    withheld_fields: tuple[str, ...] = ()


def _is_non_industrial(category: str) -> bool:
    hay = (category or "").lower().replace("-", " ").replace("_", " ")
    industrial = (
        "valve",
        "pump",
        "sensor",
        "motor",
        "pipe",
        "solenoid",
        "gauge",
        "actuator",
        "fitting",
        "flange",
        "pressure",
        "flow",
    )
    return not any(token in hay for token in industrial)


def _answer(ctx: RecommendationContext, field: str) -> str:
    return (ctx.answers.get(field) or "").strip()


def _contains(text: str, *needles: str) -> bool:
    hay = text.lower()
    return any(n in hay for n in needles)


def _field_summary(ctx: RecommendationContext) -> str:
    if ctx.established_fields:
        return ", ".join(ctx.established_fields[:6])
    return "no sourced fields on record"


def _gap_summary(ctx: RecommendationContext) -> str:
    if not ctx.withheld_fields:
        return "none"
    return ", ".join(ctx.withheld_fields[:6])


def _replacement_analysis(ctx: RecommendationContext) -> RecommendationResult:
    current = _answer(ctx, "existing_part_number") or "installed part not recorded"
    need = _answer(ctx, "reason_for_replacement") or "replacement driver not recorded"
    items: list[RecommendationItem] = []

    items.append(
        RecommendationItem(
            area="Baseline asset",
            current_state=f"Part on record: {current}",
            suggested_change=(
                "Confirm manufacturer, connection, and duty ratings for this exact "
                "installed item before shortlisting substitutes."
            ),
            priority="critical",
            rationale=f"Sourced fields: {_field_summary(ctx)}",
        )
    )

    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Record completeness",
                current_state=f"Unresolved: {_gap_summary(ctx)}",
                suggested_change=(
                    "Close each gap from datasheet or site survey — substitutes "
                    "cannot be validated while these fields are missing."
                ),
                priority="critical",
                rationale="Gaps are listed explicitly in the report narrative.",
            )
        )

    if _contains(need, "obsolete", "discontinued", "superseded"):
        items.append(
            RecommendationItem(
                area="Supersession lookup",
                current_state=f"Driver: {need}",
                suggested_change=(
                    "Pull the manufacturer supersession table for "
                    f"{current}; verify form/fit/function on pressure, "
                    "material, and electrical ratings."
                ),
                priority="critical",
                rationale="Obsolete-driven replacement requires catalog cross-reference.",
            )
        )
    elif _contains(need, "fail", "failed", "broken", "leak", "trip"):
        items.append(
            RecommendationItem(
                area="Failure mode review",
                current_state=f"Driver: {need}",
                suggested_change=(
                    "Match duty to failure mode before selecting a substitute — "
                    "confirm medium, pressure/temperature, and cycle count against "
                    "sourced ratings."
                ),
                priority="critical",
                rationale="Failure-driven swaps need root-cause alignment, not upsizing alone.",
            )
        )
    elif _contains(need, "upsiz", "capacity", "expand", "higher"):
        items.append(
            RecommendationItem(
                area="Upsizing check",
                current_state=f"Driver: {need}",
                suggested_change=(
                    "List every adjacent rating that must increase (pressure, flow, "
                    "power, enclosure) and re-check piping/power/clearance limits."
                ),
                priority="high",
                rationale="Upsizing affects more than the primary component.",
            )
        )
    else:
        items.append(
            RecommendationItem(
                area="Substitute validation",
                current_state=f"Driver: {need}",
                suggested_change=(
                    f"Identify catalog options for {current} that satisfy: {need}. "
                    "Validate wetted materials, connections, and cert scope."
                ),
                priority="high",
                rationale="Standard replacement workflow grounded in stated need.",
            )
        )

    summary = (
        f"Replacement assessment for {current}: {len(items)} engineering action(s) "
        f"based on {_len_sourced(ctx)} sourced field(s) and {len(ctx.withheld_fields)} gap(s)."
    )
    return RecommendationResult(summary=summary, items=items)


def _len_sourced(ctx: RecommendationContext) -> int:
    return len(ctx.established_fields)


def _techstack_analysis(ctx: RecommendationContext) -> RecommendationResult:
    """Only for clearly non-industrial categories — still tied to stated answers."""
    current = _answer(ctx, "existing_part_number") or "unspecified component"
    need = _answer(ctx, "reason_for_replacement") or "unspecified need"
    items: list[RecommendationItem] = [
        RecommendationItem(
            area="Scope",
            current_state=f"Component: {current}; need: {need}",
            suggested_change=(
                f"Define acceptance criteria for replacing/refactoring “{current}” "
                f"to address: {need}. Phase into discovery, pilot, and rollout."
            ),
            priority="high",
            rationale="Derived from Questions tab answers.",
        )
    ]
    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Information gaps",
                current_state=_gap_summary(ctx),
                suggested_change="Resolve missing inputs before committing to a technical approach.",
                priority="critical",
                rationale="Report lists gaps that block a complete assessment.",
            )
        )
    summary = (
        f"Change assessment for “{ctx.project_name}”: {len(items)} action(s) "
        f"grounded in the recorded answers."
    )
    return RecommendationResult(summary=summary, items=items)


def _rfq_analysis(ctx: RecommendationContext) -> RecommendationResult:
    requirement = _answer(ctx, "customer_requirement") or "requirement not recorded"
    quantity = _answer(ctx, "quantity") or "quantity not stated"
    items = [
        RecommendationItem(
            area="Requirement traceability",
            current_state=requirement,
            suggested_change=(
                "Map each customer phrase to a catalog field; every quoted line "
                "must cite a datasheet page or verified answer."
            ),
            priority="critical",
            rationale="RFQ responses must be traceable field by field.",
        ),
        RecommendationItem(
            area="Commercial readiness",
            current_state=f"Quantity requested: {quantity}",
            suggested_change=(
                f"Confirm price and lead time at quantity {quantity}; flag MOQ "
                "or alternates if stock cannot meet the request."
            ),
            priority="high",
            rationale="Quote is incomplete without quantity and lead time.",
        ),
    ]
    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Non-quotable lines",
                current_state=_gap_summary(ctx),
                suggested_change=(
                    "Do not quote values for these fields until a source is attached."
                ),
                priority="critical",
                rationale="Gaps are documented in the report tables.",
            )
        )
    summary = f"RFQ response plan for “{ctx.project_name}”: {requirement} (qty {quantity})."
    return RecommendationResult(summary=summary, items=items)


def _datasheet_analysis(ctx: RecommendationContext) -> RecommendationResult:
    items: list[RecommendationItem] = []
    if ctx.established_fields:
        items.append(
            RecommendationItem(
                area="Published specification",
                current_state=_field_summary(ctx),
                suggested_change=(
                    "Use the Established table as the quotable specification; "
                    "do not add values not listed there."
                ),
                priority="high",
                rationale=f"{_len_sourced(ctx)} field(s) carry citations.",
            )
        )
    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Incomplete specification",
                current_state=_gap_summary(ctx),
                suggested_change=(
                    "Attach datasheet pages or confirm N/A before issuing externally."
                ),
                priority="critical",
                rationale="Withheld fields are intentionally omitted from established values.",
            )
        )
    if not items:
        items.append(
            RecommendationItem(
                area="Data collection",
                current_state="No sourced fields yet",
                suggested_change="Upload and extract documents, then resolve Review holds.",
                priority="critical",
                rationale="Datasheet cannot be issued without sourced values.",
            )
        )
    summary = (
        f"Datasheet package for “{ctx.project_name}”: "
        f"{_len_sourced(ctx)} sourced field(s), {len(ctx.withheld_fields)} gap(s)."
    )
    return RecommendationResult(summary=summary, items=items)


def _bom_analysis(ctx: RecommendationContext) -> RecommendationResult:
    items: list[RecommendationItem] = [
        RecommendationItem(
            area="Assembly record",
            current_state=_field_summary(ctx),
            suggested_change=(
                "Resolve every BOM line marked missing before procurement release."
            ),
            priority="high",
            rationale="BOM lines are derived from the sourced assembly record.",
        )
    ]
    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Missing assembly data",
                current_state=_gap_summary(ctx),
                suggested_change="Source identity and rating fields to name unresolved BOM lines.",
                priority="critical",
                rationale="Unresolved lines are listed in the BOM section.",
            )
        )
    summary = f"BOM review for “{ctx.project_name}” based on the sourced assembly record."
    return RecommendationResult(summary=summary, items=items)


def _installation_analysis(ctx: RecommendationContext) -> RecommendationResult:
    items: list[RecommendationItem] = []
    if ctx.established_fields:
        items.append(
            RecommendationItem(
                area="Install parameters on record",
                current_state=_field_summary(ctx),
                suggested_change=(
                    "Base mounting, wiring, and torque instructions only on these sourced values."
                ),
                priority="high",
                rationale="Install package must not invent parameters.",
            )
        )
    if ctx.withheld_fields:
        items.append(
            RecommendationItem(
                area="Missing install parameters",
                current_state=_gap_summary(ctx),
                suggested_change=(
                    "Collect site power, mounting, and connection details before field work."
                ),
                priority="critical",
                rationale="Missing install fields are listed in the report.",
            )
        )
    if not items:
        items.append(
            RecommendationItem(
                area="Site survey required",
                current_state="No install parameters sourced",
                suggested_change="Record voltage, mounting, and connection data from site or manual.",
                priority="critical",
                rationale="Installation instructions require sourced parameters.",
            )
        )
    summary = (
        f"Installation package for “{ctx.project_name}”: "
        f"{_len_sourced(ctx)} parameter(s) sourced."
    )
    return RecommendationResult(summary=summary, items=items)


def build_recommendations(ctx: RecommendationContext) -> RecommendationResult | None:
    """Return evidence-grounded analysis for advisory goals."""
    handlers = {
        "replacement_recommendation": (
            _techstack_analysis if _is_non_industrial(ctx.category) else _replacement_analysis
        ),
        "rfq_response": _rfq_analysis,
        "technical_quotation": _rfq_analysis,
        "product_datasheet": _datasheet_analysis,
        "product_configuration": _datasheet_analysis,
        "bom_generation": _bom_analysis,
        "installation_package": _installation_analysis,
    }
    handler = handlers.get(ctx.goal)
    if handler is None:
        return None
    return handler(ctx)
