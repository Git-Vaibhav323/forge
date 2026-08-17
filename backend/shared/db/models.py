from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    completion_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocking_fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_approvals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AttributeRow(Base):
    __tablename__ = "attributes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="missing")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    evidence_rows: Mapped[list["AttributeEvidenceRow"]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan"
    )


class AttributeEvidenceRow(Base):
    __tablename__ = "attribute_evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    attribute_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(String(32), nullable=False)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    # What THIS source said for the field. Needed to render a conflict as
    # "source A says X / source B says Y" (M5). Not part of the locked
    # Evidence wire shape — review-service reads these rows directly.
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attribute: Mapped["AttributeRow"] = relationship(back_populates="evidence_rows")


class ReviewItemRow(Base):
    """One open decision for one field on one job.

    Identity is (project_id, field) — deliberately NOT the attribute id, which
    evidence-service regenerates on every re-scan (see evidence_service
    repository `_persist`). Keying on the field name lets a review item and its
    recorded decision survive "Re-scan documents".
    """

    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint("project_id", "field", name="uq_review_items_project_field"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Serialized list[ConflictValue] — the disagreeing sources with their quotes.
    values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_products: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # Fingerprint of the underlying disagreement. When a re-scan produces the
    # same signature we keep an existing decision instead of re-asking.
    signature: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Value the reviewer approved/typed; replayed onto attributes after re-scan.
    resolved_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReviewDecisionRow(Base):
    """Append-only audit trail. Never updated, never deleted by the service."""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    review_item_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("review_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    propagate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    affected_fields: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductRelationshipRow(Base):
    """A derived link between two jobs — never asserted, always justified.

    `basis` records WHY the link exists (e.g. "same manufacturer and model
    family"), so a propagated correction can be explained rather than trusted.
    """

    __tablename__ = "product_relationships"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "related_project_id", "relation", name="uq_relationship_pair"
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    related_project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="variant")
    basis: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompatibilityFindingRow(Base):
    """Result of one deterministic rule for one job. `unknown` means abstained."""

    __tablename__ = "compatibility_findings"
    __table_args__ = (
        UniqueConstraint("project_id", "rule", name="uq_compat_project_rule"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    required_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rated_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BomLineRow(Base):
    """One line of a resolved BOM/configuration. `missing` lines are the point."""

    __tablename__ = "bom_lines"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_bom_project_position"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="specification")
    component: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="missing")
    source_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutputRow(Base):
    """A generated artifact. One per (job, type) — regenerating replaces it.

    `storage_key` is null when the QA gate blocked generation: the row records
    why, but no file was written, because there was nothing legitimate to write.
    """

    __tablename__ = "outputs"
    __table_args__ = (
        UniqueConstraint("project_id", "type", name="uq_outputs_project_type"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False, default="text/markdown"
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qa_notes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuestionRow(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(String(512), nullable=False)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_asked: Mapped[str] = mapped_column(String(1024), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
