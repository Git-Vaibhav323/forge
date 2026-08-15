import { Badge } from "@/components/ui/Badge";
import type { FieldStatus, ProjectStatus, ReviewStatus } from "@/lib/types";
import { PROJECT_STATUS_LABELS } from "@/lib/types";

const fieldStatusMap: Record<
  FieldStatus,
  { label: string; tone: "verified" | "review" | "conflict" | "missing" | "accent" }
> = {
  verified: { label: "Verified", tone: "verified" },
  known: { label: "Known", tone: "verified" },
  derived: { label: "Derived", tone: "accent" },
  needs_review: { label: "Needs review", tone: "review" },
  conflicting: { label: "Conflicting", tone: "conflict" },
  missing: { label: "Missing", tone: "missing" },
  unverified: { label: "Unverified", tone: "review" },
  not_applicable: { label: "N/A", tone: "missing" },
};

export function FieldStatusBadge({ status }: { status: FieldStatus }) {
  const cfg = fieldStatusMap[status];
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

const projectStatusTone: Record<ProjectStatus, "verified" | "review" | "conflict" | "missing" | "accent"> = {
  draft: "missing",
  collecting_information: "accent",
  waiting_for_user: "review",
  validating: "accent",
  waiting_for_approval: "review",
  ready_to_generate: "verified",
  generated: "verified",
  completed: "verified",
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge tone={projectStatusTone[status]}>
      {PROJECT_STATUS_LABELS[status]}
    </Badge>
  );
}

const reviewStatusTone: Record<ReviewStatus, "verified" | "review" | "conflict" | "missing"> = {
  pending: "review",
  approved: "verified",
  edited: "verified",
  rejected: "conflict",
  unresolved: "missing",
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  const labels: Record<ReviewStatus, string> = {
    pending: "Pending",
    approved: "Approved",
    edited: "Edited & approved",
    rejected: "Rejected",
    unresolved: "Unresolved",
  };
  return <Badge tone={reviewStatusTone[status]}>{labels[status]}</Badge>;
}
