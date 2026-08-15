import type {
  Attribute,
  OutputArtifact,
  Project,
  Question,
  ReviewItem,
} from "./types";

/**
 * Seed data for local development and demos without a backend.
 *
 * Deliberately includes a conflicting value (pressure), a missing
 * high-risk field (chemical compatibility), and a repeated connection-
 * standard error across sibling SKUs — so the review + bulk-propagation
 * screens have something real to show. See docs/demo-data-notes.md.
 */

const now = new Date().toISOString();
const hoursAgo = (h: number) =>
  new Date(Date.now() - h * 3600 * 1000).toISOString();

export const mockProjects: Project[] = [
  {
    id: "prj-1042",
    name: "SV-24 Outdoor Water Inlet Valve",
    goal: "product_configuration",
    category: "solenoid_valve",
    status: "waiting_for_approval",
    completionScore: 78,
    createdAt: hoursAgo(30),
    updatedAt: hoursAgo(1),
    documents: [
      { id: "doc-1", filename: "sv24_datasheet_rev_b.pdf", type: "datasheet", status: "processed", uploadedAt: hoursAgo(30), pages: 8 },
      { id: "doc-2", filename: "sv24_product_page.html", type: "web_page", status: "processed", uploadedAt: hoursAgo(30) },
      { id: "doc-3", filename: "nameplate_sv24.jpg", type: "image", status: "processed", uploadedAt: hoursAgo(29) },
      { id: "doc-4", filename: "pump_datasheet.pdf", type: "datasheet", status: "processed", uploadedAt: hoursAgo(6), pages: 4 },
    ],
    blockingFieldsCount: 1,
    conflictsCount: 1,
    pendingApprovalsCount: 2,
  },
  {
    id: "prj-1041",
    name: "Series X Ball Valve — Catalog Cleanup",
    goal: "bom_generation",
    category: "ball_valve",
    status: "collecting_information",
    completionScore: 41,
    createdAt: hoursAgo(80),
    updatedAt: hoursAgo(12),
    documents: [
      { id: "doc-5", filename: "series_x_catalog.csv", type: "catalog", status: "processed", uploadedAt: hoursAgo(80) },
      { id: "doc-6", filename: "series_x_manual.pdf", type: "manual", status: "processing", uploadedAt: hoursAgo(12), pages: 22 },
    ],
    blockingFieldsCount: 6,
    conflictsCount: 0,
    pendingApprovalsCount: 0,
  },
  {
    id: "prj-1039",
    name: "Sensor Replacement RFQ — Acme Foods",
    goal: "rfq_response",
    category: "temperature_sensor",
    status: "completed",
    completionScore: 100,
    createdAt: hoursAgo(240),
    updatedAt: hoursAgo(190),
    documents: [
      { id: "doc-7", filename: "acme_rfq.pdf", type: "rfq", status: "processed", uploadedAt: hoursAgo(240), pages: 2 },
    ],
    blockingFieldsCount: 0,
    conflictsCount: 0,
    pendingApprovalsCount: 0,
  },
];

export const mockAttributes: Record<string, Attribute[]> = {
  "prj-1042": [
    {
      id: "attr-1",
      productId: "SV-24-15",
      name: "voltage",
      rawValue: "24 VDC",
      normalizedValue: 24,
      unit: "VDC",
      confidence: 0.98,
      status: "verified",
      riskLevel: "high",
      updatedAt: hoursAgo(28),
      evidence: [
        {
          id: "ev-1",
          documentId: "doc-1",
          documentName: "sv24_datasheet_rev_b.pdf",
          documentType: "datasheet",
          page: 3,
          quote: "Operating voltage: 24 VDC ±10%",
        },
      ],
    },
    {
      id: "attr-2",
      productId: "SV-24-15",
      name: "connection_size",
      rawValue: "1/2 inch",
      normalizedValue: 12.7,
      unit: "mm",
      confidence: 0.94,
      status: "verified",
      riskLevel: "medium",
      updatedAt: hoursAgo(28),
      evidence: [
        {
          id: "ev-2",
          documentId: "doc-1",
          documentName: "sv24_datasheet_rev_b.pdf",
          documentType: "datasheet",
          page: 2,
          quote: "Port size: 1/2\" BSPP",
        },
      ],
    },
    {
      id: "attr-3",
      productId: "SV-24-15",
      name: "maximum_pressure",
      rawValue: "16 bar",
      normalizedValue: 16,
      unit: "bar",
      confidence: 0.71,
      status: "conflicting",
      riskLevel: "critical",
      updatedAt: hoursAgo(2),
      evidence: [
        {
          id: "ev-3",
          documentId: "doc-1",
          documentName: "sv24_datasheet_rev_b.pdf",
          documentType: "datasheet",
          page: 3,
          quote: "Maximum operating pressure: 16 bar",
        },
        {
          id: "ev-4",
          documentId: "doc-2",
          documentName: "sv24_product_page.html",
          documentType: "web_page",
          quote: "Max pressure: 10 bar",
        },
      ],
    },
    {
      id: "attr-4",
      productId: "SV-24-15",
      name: "body_material",
      rawValue: "Stainless steel 304",
      normalizedValue: "AISI 304 stainless steel",
      confidence: 0.96,
      status: "verified",
      riskLevel: "medium",
      updatedAt: hoursAgo(28),
      evidence: [
        {
          id: "ev-5",
          documentId: "doc-3",
          documentName: "nameplate_sv24.jpg",
          documentType: "image",
          quote: "Body: SS304 — visible on product nameplate",
        },
      ],
    },
    {
      id: "attr-5",
      productId: "SV-24-15",
      name: "ingress_protection",
      rawValue: "IP67",
      normalizedValue: "IP67",
      confidence: 0.9,
      status: "verified",
      riskLevel: "high",
      updatedAt: hoursAgo(28),
      evidence: [
        {
          id: "ev-6",
          documentId: "doc-1",
          documentName: "sv24_datasheet_rev_b.pdf",
          documentType: "datasheet",
          page: 4,
          quote: "Enclosure rating: IP67",
        },
      ],
    },
    {
      id: "attr-6",
      productId: "SV-24-15",
      name: "chemical_compatibility",
      rawValue: "",
      confidence: 0,
      status: "missing",
      riskLevel: "critical",
      updatedAt: hoursAgo(28),
      evidence: [],
    },
    {
      id: "attr-7",
      productId: "SV-24-15",
      name: "required_flow_rate",
      rawValue: "45 L/min",
      normalizedValue: 45,
      unit: "L/min",
      confidence: 0.88,
      status: "derived",
      riskLevel: "medium",
      updatedAt: hoursAgo(6),
      evidence: [
        {
          id: "ev-7",
          documentId: "doc-4",
          documentName: "pump_datasheet.pdf",
          documentType: "datasheet",
          page: 1,
          quote: "Rated output: 45 L/min at 8 bar inlet",
        },
      ],
    },
  ],
};

export const mockReviewItems: Record<string, ReviewItem[]> = {
  "prj-1042": [
    {
      id: "rev-1",
      projectId: "prj-1042",
      field: "maximum_pressure",
      productId: "SV-24-15",
      issueType: "conflict",
      severity: "critical",
      currentValue: "10 bar",
      proposedValue: "16 bar",
      values: [
        { value: "16 bar", source: "sv24_datasheet_rev_b.pdf, p.3", sourceType: "manufacturer_datasheet", evidenceId: "ev-3" },
        { value: "10 bar", source: "sv24_product_page.html", sourceType: "product_page", evidenceId: "ev-4" },
      ],
      reason:
        "Current manufacturer datasheet (rev B) has higher source authority and a newer revision than the product page.",
      evidenceIds: ["ev-3", "ev-4"],
      affectedProducts: 1,
      status: "pending",
      createdAt: hoursAgo(2),
    },
    {
      id: "rev-2",
      projectId: "prj-1042",
      field: "connection_standard",
      issueType: "bulk_propagation",
      severity: "high",
      currentValue: "NPT",
      proposedValue: "BSPP",
      reason:
        "Reviewer correction on SV-24-15 (NPT → BSPP) matches a known extraction error for Acme datasheets using this table template. 62 sibling SKUs share the same template and manufacturer.",
      evidenceIds: ["ev-2"],
      affectedProducts: 62,
      status: "pending",
      createdAt: hoursAgo(1),
    },
    {
      id: "rev-3",
      projectId: "prj-1042",
      field: "chemical_compatibility",
      productId: "SV-24-15",
      issueType: "high_risk",
      severity: "critical",
      reason:
        "No chemical-compatibility evidence found for the stated operating medium. This field cannot be inferred from general knowledge — safety-critical, requires a source or explicit override.",
      evidenceIds: [],
      status: "unresolved",
      createdAt: hoursAgo(20),
    },
  ],
};

export const mockQuestions: Record<string, Question[]> = {
  "prj-1042": [
    {
      id: "q-1",
      projectId: "prj-1042",
      field: "operating_medium",
      text: "What medium will pass through the valve?",
      inputType: "select",
      options: ["Water", "Compressed air", "Oil", "Steam", "Chemical", "Other"],
      whyAsked: "Determines seal material and chemical-compatibility requirements.",
      priority: "critical",
      status: "answered",
      answer: "Water",
      answeredAt: hoursAgo(24),
    },
    {
      id: "q-2",
      projectId: "prj-1042",
      field: "installation_environment",
      text: "Is the valve installed indoors or outdoors?",
      inputType: "select",
      options: ["Indoor", "Outdoor", "Both"],
      whyAsked: "Sets the minimum required enclosure (IP) rating.",
      priority: "high",
      status: "answered",
      answer: "Outdoor",
      answeredAt: hoursAgo(23),
    },
    {
      id: "q-3",
      projectId: "prj-1042",
      field: "fail_safe_mode",
      text: "Should the valve close when power is removed, or stay open?",
      inputType: "select",
      options: ["Close on power loss (normally closed)", "Stay open (normally open)"],
      whyAsked: "Required to select the correct actuator variant before the BOM can be finalized.",
      priority: "critical",
      status: "open",
    },
  ],
};

export const mockOutputs: Record<string, OutputArtifact[]> = {
  "prj-1042": [
    {
      id: "out-1",
      projectId: "prj-1042",
      type: "configured_product",
      filename: "sv-24-15_configured.json",
      status: "draft",
    },
  ],
  "prj-1039": [
    {
      id: "out-2",
      projectId: "prj-1039",
      type: "rfq_response",
      filename: "acme_foods_rfq_response.pdf",
      status: "qa_passed",
      generatedAt: hoursAgo(191),
      qaNotes: ["All fields evidence-backed.", "No unresolved conflicts."],
    },
  ],
};
