"""
Canonical schemas shared by the backend and (eventually) the frontend.

These must describe the same wire shape as `lib/types.ts` in the frontend.
If you change a field here, change it there too — the review console,
evidence panel, and question loop all render directly off this shape.

Locked field-level JSON shape (see context.md → "Data contract"):
    { attribute, value, unit, source, page, evidence, confidence, status }
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    known = "known"
    missing = "missing"
    conflicting = "conflicting"
    derived = "derived"
    unverified = "unverified"
    needs_review = "needs_review"
    verified = "verified"
    not_applicable = "not_applicable"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectGoal(str, Enum):
    product_configuration = "product_configuration"
    bom_generation = "bom_generation"
    technical_quotation = "technical_quotation"
    product_datasheet = "product_datasheet"
    installation_package = "installation_package"
    replacement_recommendation = "replacement_recommendation"
    rfq_response = "rfq_response"


class ProjectStatus(str, Enum):
    draft = "draft"
    collecting_information = "collecting_information"
    waiting_for_user = "waiting_for_user"
    validating = "validating"
    waiting_for_approval = "waiting_for_approval"
    ready_to_generate = "ready_to_generate"
    generated = "generated"
    completed = "completed"


class Evidence(BaseModel):
    id: str
    document_id: str = Field(alias="documentId")
    document_name: str = Field(alias="documentName")
    document_type: Optional[str] = Field(default=None, alias="documentType")
    page: Optional[int] = None
    quote: str
    bounding_box: Optional[dict] = Field(default=None, alias="boundingBox")

    class Config:
        populate_by_name = True


class Attribute(BaseModel):
    id: str
    product_id: str = Field(alias="productId")
    name: str
    raw_value: str = Field(alias="rawValue")
    normalized_value: Optional[str | float] = Field(default=None, alias="normalizedValue")
    unit: Optional[str] = None
    confidence: float
    status: FieldStatus
    evidence: list[Evidence] = []
    risk_level: Severity = Field(alias="riskLevel")
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


class ConflictValue(BaseModel):
    """One side of a disagreement, as rendered by ReviewItemCard."""

    value: str
    source: str
    source_type: str = Field(alias="sourceType")
    evidence_id: Optional[str] = Field(default=None, alias="evidenceId")

    class Config:
        populate_by_name = True


class ReviewItem(BaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    field: str
    product_id: Optional[str] = Field(default=None, alias="productId")
    issue_type: str = Field(alias="issueType")  # conflict | high_risk | duplicate | bulk_propagation
    severity: Severity
    current_value: Optional[str] = Field(default=None, alias="currentValue")
    proposed_value: Optional[str] = Field(default=None, alias="proposedValue")
    # Populated for `conflict` items — each disagreeing source with its quote.
    values: Optional[list[ConflictValue]] = None
    reason: str
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    affected_products: Optional[int] = Field(default=None, alias="affectedProducts")
    status: str = "pending"  # pending | approved | edited | rejected | unresolved
    created_at: datetime = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class ReviewDecision(BaseModel):
    action: str  # approve | edit | reject | unresolved
    value: Optional[str] = None
    propagate: bool = False
    # The frontend posts projectId alongside the decision (lib/api.ts).
    project_id: Optional[str] = Field(default=None, alias="projectId")

    class Config:
        populate_by_name = True


class ProductRelationship(BaseModel):
    """A derived link to a sibling job, with the reason it was drawn (M6)."""

    id: str
    project_id: str = Field(alias="projectId")
    related_project_id: str = Field(alias="relatedProjectId")
    relation: str  # variant | accessory | duplicate
    basis: str
    confidence: float

    class Config:
        populate_by_name = True


class CompatibilityFinding(BaseModel):
    """One deterministic rule result. `unknown` means the rule abstained (M6)."""

    id: str
    project_id: str = Field(alias="projectId")
    rule: str
    field: str
    status: str  # pass | fail | unknown
    severity: Severity
    required_value: Optional[str] = Field(default=None, alias="requiredValue")
    rated_value: Optional[str] = Field(default=None, alias="ratedValue")
    reason: str
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")

    class Config:
        populate_by_name = True


class BomLine(BaseModel):
    """One line of a resolved BOM. `missing` lines are named, not dropped (M6)."""

    id: str
    project_id: str = Field(alias="projectId")
    position: int
    role: str  # primary | specification
    component: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    status: str  # resolved | missing | unverified
    source_field: Optional[str] = Field(default=None, alias="sourceField")
    reason: str
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")

    class Config:
        populate_by_name = True


class RelationshipView(BaseModel):
    """What relationship-service returns for a job (M6, consumed by M8)."""

    variants: list[ProductRelationship] = []
    findings: list[CompatibilityFinding] = []
    bom_lines: list[BomLine] = Field(default_factory=list, alias="bomLines")

    class Config:
        populate_by_name = True


class VisionStatus(BaseModel):
    """Whether OCR is available at all, and under which provider (M7)."""

    provider: str  # off | tesseract | custom
    enabled: bool
    image_types: list[str] = Field(default_factory=list, alias="imageTypes")

    class Config:
        populate_by_name = True


class ImageRead(BaseModel):
    """Raw text read off one stored image. Facts are never written from here (M7)."""

    document_id: str = Field(alias="documentId")
    filename: str
    provider: str
    pages: list[str] = []
    note: str = ""

    class Config:
        populate_by_name = True


class Question(BaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    field: str
    text: str
    input_type: str = Field(alias="inputType")
    options: Optional[list[str]] = None
    why_asked: str = Field(alias="whyAsked")
    priority: str
    status: str = "open"
    answer: Optional[str] = None
    answered_at: Optional[datetime] = Field(default=None, alias="answeredAt")

    class Config:
        populate_by_name = True


class AnswerInput(BaseModel):
    answer: str


class ProjectDocument(BaseModel):
    id: str
    filename: str
    type: str
    status: str = "pending"
    uploaded_at: datetime = Field(alias="uploadedAt")
    pages: Optional[int] = None
    # Present when this document was ingested from a pasted/fetched URL.
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")

    class Config:
        populate_by_name = True


class Project(BaseModel):
    id: str
    name: str
    goal: ProjectGoal
    category: str
    status: ProjectStatus = ProjectStatus.draft
    completion_score: int = Field(default=0, alias="completionScore")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    documents: list[ProjectDocument] = []
    blocking_fields_count: int = Field(default=0, alias="blockingFieldsCount")
    conflicts_count: int = Field(default=0, alias="conflictsCount")
    pending_approvals_count: int = Field(default=0, alias="pendingApprovalsCount")

    class Config:
        populate_by_name = True


class ProjectCreateInput(BaseModel):
    name: str
    goal: ProjectGoal
    category: str


class OutputArtifact(BaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    type: str
    filename: str
    status: str = "draft"  # draft | generated | qa_passed | qa_failed
    generated_at: Optional[datetime] = Field(default=None, alias="generatedAt")
    qa_notes: Optional[list[str]] = Field(default=None, alias="qaNotes")
    # Gateway-relative path; null when the QA gate blocked generation and no
    # file was written (M8). The frontend prefixes NEXT_PUBLIC_API_BASE_URL.
    download_url: Optional[str] = Field(default=None, alias="downloadUrl")
    size_bytes: Optional[int] = Field(default=None, alias="sizeBytes")

    class Config:
        populate_by_name = True


class OutputGenerateInput(BaseModel):
    type: str
