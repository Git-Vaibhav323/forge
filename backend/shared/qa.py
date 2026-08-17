"""The QA gate (M8). Pure functions — no DB, no network.

The hard rule from context.md:

    The generator uses ONLY approved facts, approved answers, approved
    calculations, and cited evidence. No unsupported claims, no general model
    knowledge for technical values.

So this module answers two separate questions, and the distinction matters:

* **Blockers** — reasons nothing may be printed at all. Two sources still
  disagree, or a hold is still waiting on a person. Printing over either would
  publish a number nobody stands behind.
* **Warnings** — reasons the printed document is incomplete but honest. A field
  nothing established, a rule that abstained, a value resting on a single
  photo. These are *recorded on the artifact*, never silently dropped.

A gap that appears in the warnings is also written into the document itself, so
the reader of the PDF/markdown sees the same caveats the operator did.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

# Attribute statuses that may be stated as fact in an output.
PUBLISHABLE_STATUSES: frozenset[str] = frozenset({"known", "verified", "derived"})
# Statuses that must never be printed as a value.
WITHHELD_STATUSES: frozenset[str] = frozenset(
    {"missing", "conflicting", "needs_review", "unverified", "not_applicable"}
)


@dataclass
class QaResult:
    blockers: list[str] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when something may be printed at all."""
        return not self.blockers

    @property
    def clean(self) -> bool:
        """True when the printed document has no caveats."""
        return not self.blockers and not self.warnings

    @property
    def status(self) -> str:
        if self.blockers:
            return "qa_failed"
        return "qa_passed" if not self.warnings else "generated"

    @property
    def notes(self) -> list[str]:
        return [*self.blockers, *self.warnings]


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def evaluate(
    *,
    conflicting_fields: list[str],
    pending_holds: list[str],
    missing_fields: list[str],
    unverified_fields: list[str],
    abstained_rules: list[str],
    unresolved_bom_lines: int = 0,
) -> QaResult:
    """Decide whether this job may be printed, and with what caveats."""
    result = QaResult()

    # --- Blockers: publishing these would assert something unowned -----------
    if conflicting_fields:
        result.blockers.append(
            f"{_plural(len(conflicting_fields), 'field')} still have disagreeing "
            f"sources: {', '.join(sorted(conflicting_fields))}. Resolve them on "
            "the Review tab before printing."
        )
    if pending_holds:
        result.blockers.append(
            f"{_plural(len(pending_holds), 'hold')} awaiting a decision: "
            f"{', '.join(sorted(pending_holds))}. Every hold must be answered by "
            "a person before anything is published."
        )

    # --- Warnings: the document is incomplete, and says so -------------------
    if missing_fields:
        result.warnings.append(
            f"{_plural(len(missing_fields), 'field')} could not be established "
            f"and are listed as gaps: {', '.join(sorted(missing_fields))}."
        )
    if unverified_fields:
        result.warnings.append(
            f"{_plural(len(unverified_fields), 'field')} rest on a single "
            f"unconfirmed reading: {', '.join(sorted(unverified_fields))}."
        )
    if abstained_rules:
        result.warnings.append(
            f"{_plural(len(abstained_rules), 'compatibility rule')} could not be "
            f"decided from the sources: {', '.join(sorted(abstained_rules))}."
        )
    if unresolved_bom_lines:
        result.warnings.append(
            f"{_plural(unresolved_bom_lines, 'BOM line')} could not be resolved "
            "and are marked as gaps."
        )

    return result
