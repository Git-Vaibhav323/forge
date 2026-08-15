"use client";

import { useState } from "react";
import { AlertTriangle, GitMerge, ShieldAlert, Copy } from "lucide-react";
import type { IssueType, ReviewItem, Severity } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ReviewStatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@/lib/utils";

const issueIcon: Record<IssueType, typeof AlertTriangle> = {
  conflict: GitMerge,
  high_risk: ShieldAlert,
  duplicate: Copy,
  bulk_propagation: AlertTriangle,
};

const issueLabel: Record<IssueType, string> = {
  conflict: "Conflicting sources",
  high_risk: "High-risk field",
  duplicate: "Possible duplicate",
  bulk_propagation: "Bulk correction",
};

const severityTone: Record<Severity, string> = {
  low: "text-muted",
  medium: "text-accent",
  high: "text-review",
  critical: "text-conflict",
};

export function ReviewItemCard({
  item,
  onDecide,
}: {
  item: ReviewItem;
  onDecide: (decision: {
    action: "approve" | "edit" | "reject" | "unresolved";
    value?: string;
    propagate?: boolean;
  }) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.proposedValue ?? "");
  const [submitting, setSubmitting] = useState(false);
  const Icon = issueIcon[item.issueType];
  const isBulk = item.issueType === "bulk_propagation";
  const decided = item.status !== "pending";

  async function decide(
    action: "approve" | "edit" | "reject" | "unresolved",
    value?: string
  ) {
    setSubmitting(true);
    try {
      await onDecide({ action, value, propagate: isBulk });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded border p-4",
        item.severity === "critical" ? "border-conflict/30" : "border-line"
      )}
    >
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon size={15} className={severityTone[item.severity]} />
          <span className="text-[13px] font-medium">{issueLabel[item.issueType]}</span>
          <span className={cn("font-mono text-[10px] uppercase", severityTone[item.severity])}>
            {item.severity}
          </span>
        </div>
        <ReviewStatusBadge status={item.status} />
      </div>

      <p className="mb-1 font-mono text-[12px] text-faint">
        field: {item.field}
        {item.productId && ` · ${item.productId}`}
      </p>

      {item.values && item.values.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {item.values.map((v, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded bg-paper px-2.5 py-1.5 text-[13px]"
            >
              <span className="font-mono">{v.value}</span>
              <span className="text-[12px] text-muted">{v.source}</span>
            </div>
          ))}
        </div>
      )}

      {!item.values && (item.currentValue || item.proposedValue) && (
        <div className="mb-3 flex items-center gap-2 text-[13px]">
          <span className="font-mono text-faint line-through">
            {item.currentValue ?? "—"}
          </span>
          <span className="text-faint">→</span>
          <span className="font-mono font-medium">{item.proposedValue}</span>
        </div>
      )}

      <p className="mb-3 text-[13px] leading-snug text-muted">{item.reason}</p>

      {isBulk && item.affectedProducts && (
        <div className="mb-3 rounded border border-review/30 bg-review-soft/40 px-3 py-2 text-[12px] text-review">
          This correction may apply to <strong>{item.affectedProducts}</strong>{" "}
          similar products. Approving reviews a representative sample before
          applying it to the rest.
        </div>
      )}

      {!decided && (
        <>
          {editing ? (
            <div className="flex items-center gap-2">
              <Input
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="flex-1"
              />
              <Button size="sm" variant="primary" disabled={submitting} onClick={() => decide("edit", editValue)}>
                Save value
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="primary"
                disabled={submitting}
                onClick={() => decide("approve", item.proposedValue)}
              >
                {isBulk ? "Approve & propagate" : "Approve"}
              </Button>
              <Button size="sm" variant="secondary" disabled={submitting} onClick={() => setEditing(true)}>
                Edit value
              </Button>
              <Button size="sm" variant="secondary" disabled={submitting} onClick={() => decide("reject")}>
                Reject
              </Button>
              <Button size="sm" variant="ghost" disabled={submitting} onClick={() => decide("unresolved")}>
                Mark unresolved
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
