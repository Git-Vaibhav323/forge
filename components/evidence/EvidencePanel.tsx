import { FileText, ImageIcon } from "lucide-react";
import type { Attribute } from "@/lib/types";
import { FieldStatusBadge } from "@/components/shared/StatusBadge";
import { ConfidenceMeter } from "@/components/shared/Meters";
import { EmptyState } from "@/components/shared/EmptyState";

export function EvidencePanel({ attribute }: { attribute: Attribute | undefined }) {
  if (!attribute) {
    return (
      <EmptyState
        icon={FileText}
        title="No field selected"
        description="Click any row to see exactly where its value came from."
      />
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold capitalize">
          {attribute.name.replace(/_/g, " ")}
        </h3>
        <FieldStatusBadge status={attribute.status} />
      </div>

      <dl className="mb-4 space-y-2 text-[13px]">
        <Row label="Raw value">{attribute.rawValue || "—"}</Row>
        {attribute.normalizedValue !== undefined && (
          <Row label="Normalized">
            {attribute.normalizedValue} {attribute.unit}
          </Row>
        )}
        <Row label="Confidence">
          <ConfidenceMeter value={attribute.confidence} />
        </Row>
        <Row label="Risk level">
          <span className="capitalize">{attribute.riskLevel}</span>
        </Row>
      </dl>

      <p className="label-caps mb-2">
        Evidence ({attribute.evidence.length})
      </p>

      {attribute.evidence.length === 0 && (
        <p className="rounded border border-dashed border-line-strong px-3 py-4 text-center text-[12px] text-muted">
          No source found for this field. It cannot be published until
          evidence exists or a reviewer confirms it manually.
        </p>
      )}

      <div className="space-y-2.5">
        {attribute.evidence.map((ev) => (
          <div
            key={ev.id}
            className="rounded border-l-2 border-l-accent bg-paper px-3 py-2.5"
          >
            <div className="mb-1 flex items-center gap-1.5 font-mono text-[11px] text-muted">
              {ev.documentType === "image" ? (
                <ImageIcon size={12} />
              ) : (
                <FileText size={12} />
              )}
              {ev.documentName}
              {ev.page && <span>· p.{ev.page}</span>}
            </div>
            <p className="text-[13px] italic leading-snug text-ink">
              &ldquo;{ev.quote}&rdquo;
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className="font-mono text-[12px]">{children}</dd>
    </div>
  );
}
