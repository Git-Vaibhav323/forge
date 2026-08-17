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


class ReviewItem(BaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    field: str
    product_id: Optional[str] = Field(default=None, alias="productId")
    issue_type: str = Field(alias="issueType")  # conflict | high_risk | duplicate | bulk_propagation
    severity: Severity
    current_value: Optional[str] = Field(default=None, alias="currentValue")
    proposed_value: Optional[str] = Field(default=None, alias="proposedValue")
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

    class Config:
        populate_by_name = True


class OutputGenerateInput(BaseModel):
    type: str
