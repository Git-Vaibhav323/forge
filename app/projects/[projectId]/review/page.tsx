"use client";

import { ShieldCheck } from "lucide-react";
import * as api from "@/lib/api";
import { useReviewItems } from "@/hooks/useProjectData";
import { ReviewItemCard } from "@/components/review/ReviewItemCard";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";

export default function ReviewPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: items, loading, refresh } = useReviewItems(projectId);

  const pending = items?.filter((r) => r.status === "pending" || r.status === "unresolved") ?? [];
  const resolved = items?.filter((r) => r.status !== "pending" && r.status !== "unresolved") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <p className="label-caps mb-2">
          Needs your decision ({pending.length})
        </p>

        {loading && (
          <p className="font-mono text-[11px] text-faint">Loading holds…</p>
        )}

        {!loading && pending.length === 0 && (
          <Card>
            <EmptyState
              icon={ShieldCheck}
              title="No holds"
              description="When two sources disagree, or a voltage / pressure / cert is in play, it stops here. The desk will not fill it in."
            />
          </Card>
        )}

        {!loading && pending.length > 0 && (
          <div className="space-y-3">
            {pending.map((item) => (
              <ReviewItemCard
                key={item.id}
                item={item}
                onDecide={async (decision) => {
                  await api.submitReviewDecision(projectId, item.id, decision);
                  refresh();
                }}
              />
            ))}
          </div>
        )}
      </div>

      {resolved.length > 0 && (
        <div>
          <p className="label-caps mb-2">Resolved ({resolved.length})</p>
          <div className="space-y-3 opacity-70">
            {resolved.map((item) => (
              <ReviewItemCard key={item.id} item={item} onDecide={() => {}} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
