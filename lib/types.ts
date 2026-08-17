/**
 * Canonical types shared by the frontend and (eventually) the backend.
 *
 * These mirror the field-level JSON shape locked in `context.md`:
 * { attribute, value, unit, source, page, evidence, confidence, status }
 *
 * Keep this file in sync with backend/app/models/schemas.py — the two
 * should describe the same wire shape. If you change one, change both.
 */

export type FieldStatus =
  | "known"
  | "missing"
  | "conflicting"
  | "derived"
  | "unverified"
  | "needs_review"
  | "verified"
  | "not_applicable";

export type Severity = "low" | "medium" | "high" | "critical";

export interface Evidence {
  id: string;
  documentId: string;
  documentName: string;
  documentType?: string;
  page?: number;
  quote: string;
  boundingBox?: { x: number; y: number; width: number; height: number };
}

export interface Attribute {
  id: string;
  productId: string;
  name: string;
  rawValue: string;
  normalizedValue?: string | number;
  unit?: string;
  confidence: number; // 0–1
  status: FieldStatus;
  evidence: Evidence[];
  riskLevel: Severity;
  updatedAt: string;
}

export interface ConflictValue {
  value: string;
  source: string;
  sourceType: string;
  evidenceId?: string;
}

export type IssueType =
  | "conflict"
  | "high_risk"
  | "duplicate"
  | "bulk_propagation"
  /** Sources agree, but the value does not meet the stated requirement (M6). */
  | "incompatible";
export type ReviewStatus = "pending" | "approved" | "edited" | "rejected" | "unresolved";

export interface ReviewItem {
  id: string;
  projectId: string;
  field: string;
  productId?: string;
  issueType: IssueType;
  severity: Severity;
  currentValue?: string;
  proposedValue?: string;
  values?: ConflictValue[];
  reason: string;
  evidenceIds: string[];
  affectedProducts?: number;
  status: ReviewStatus;
  createdAt: string;
}

export type QuestionInputType =
  | "select"
  | "multi_select"
  | "number"
  | "text"
  | "file"
  | "confirmation";

export interface Question {
  id: string;
  projectId: string;
  field: string;
  text: string;
  inputType: QuestionInputType;
  options?: string[];
  whyAsked: string;
  priority: "critical" | "high" | "medium" | "low";
  status: "open" | "answered" | "skipped";
  answer?: string;
  answeredAt?: string;
}

export type ProjectGoal =
  | "product_configuration"
  | "bom_generation"
  | "technical_quotation"
  | "product_datasheet"
  | "installation_package"
  | "replacement_recommendation"
  | "rfq_response";

export const PROJECT_GOAL_LABELS: Record<ProjectGoal, string> = {
  product_configuration: "Product configuration",
  bom_generation: "Bill of materials",
  technical_quotation: "Technical quotation",
  product_datasheet: "Product datasheet",
  installation_package: "Installation package",
  replacement_recommendation: "Replacement recommendation",
  rfq_response: "RFQ response",
};

export type ProjectStatus =
  | "draft"
  | "collecting_information"
  | "waiting_for_user"
  | "validating"
  | "waiting_for_approval"
  | "ready_to_generate"
  | "generated"
  | "completed";

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "Draft",
  collecting_information: "Collecting information",
  waiting_for_user: "Waiting on you",
  validating: "Validating",
  waiting_for_approval: "Needs approval",
  ready_to_generate: "Ready to generate",
  generated: "Generated",
  completed: "Completed",
};

export interface ProjectDocument {
  id: string;
  filename: string;
  type: string;
  status: "pending" | "processing" | "processed" | "failed";
  uploadedAt: string;
  pages?: number;
  /** Set when the document was ingested from a pasted/fetched URL. */
  sourceUrl?: string;
}

export interface Project {
  id: string;
  name: string;
  goal: ProjectGoal;
  category: string;
  status: ProjectStatus;
  completionScore: number; // 0–100
  createdAt: string;
  updatedAt: string;
  documents: ProjectDocument[];
  blockingFieldsCount: number;
  conflictsCount: number;
  pendingApprovalsCount: number;
}

// ---------------------------------------------------------------------------
// Relationships / compatibility / BOM (M6)
// Mirrors backend/shared/schemas.py. Served by relationship-service :8006 and
// consumed by generation-service (M8) — no dedicated tab of its own.
// ---------------------------------------------------------------------------

export interface ProductRelationship {
  id: string;
  projectId: string;
  relatedProjectId: string;
  relation: "variant" | "accessory" | "duplicate";
  /** Why the link was drawn — never asserted without a reason. */
  basis: string;
  confidence: number;
}

/** `unknown` means the rule abstained rather than guessed. */
export type CompatibilityStatus = "pass" | "fail" | "unknown";

export interface CompatibilityFinding {
  id: string;
  projectId: string;
  rule: string;
  field: string;
  status: CompatibilityStatus;
  severity: Severity;
  requiredValue?: string;
  ratedValue?: string;
  reason: string;
  evidenceIds: string[];
}

export type BomLineStatus = "resolved" | "missing" | "unverified";

export interface BomLine {
  id: string;
  projectId: string;
  position: number;
  role: "primary" | "specification";
  component: string;
  quantity?: string;
  unit?: string;
  status: BomLineStatus;
  sourceField?: string;
  reason: string;
  evidenceIds: string[];
}

export interface RelationshipView {
  variants: ProductRelationship[];
  findings: CompatibilityFinding[];
  bomLines: BomLine[];
}

export type OutputStatus = "draft" | "generated" | "qa_passed" | "qa_failed";

export interface OutputArtifact {
  id: string;
  projectId: string;
  type: string;
  filename: string;
  status: OutputStatus;
  generatedAt?: string;
  qaNotes?: string[];
  /**
   * Gateway-relative download path. Absent when the QA gate blocked
   * generation — the row records why, but no file exists (M8).
   */
  downloadUrl?: string;
  sizeBytes?: number;
}
