"use client";

import { useState } from "react";
import { FileOutput } from "lucide-react";
import * as api from "@/lib/api";
import { useOutputs, useProject } from "@/hooks/useProjectData";
import { OutputCard } from "@/components/outputs/OutputCard";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";

export default function OutputsPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: project, refresh: refreshProject } = useProject(projectId);
  const { data: outputs, loading, refresh } = useOutputs(projectId);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string>();

  const blocked =
    !!project && (project.conflictsCount > 0 || project.pendingApprovalsCount > 0);

  async function handleGenerate() {
    if (!project) return;
    setGenerating(true);
    setError(undefined);
    try {
      await api.generateOutput(projectId, project.goal);
      refresh();
      // The QA gate re-derives the record, so counts and status can move.
      refreshProject();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium">Print the package</p>
            <p className="mt-0.5 text-[12px] text-muted">
              Built only from approved facts, answers you typed, and cited
              evidence. Nothing else.
            </p>
          </div>
          <Button variant="primary" disabled={blocked || generating} onClick={handleGenerate}>
            <FileOutput size={15} />
            {generating ? "Printing…" : "Print"}
          </Button>
        </CardHeader>
        {blocked && (
          <CardBody>
            <p className="text-[13px] text-review">
              Generation is disabled while conflicts or approvals are pending.
              Resolve them in the Review tab first.
            </p>
          </CardBody>
        )}
        {error && (
          <CardBody>
            <p className="text-[13px] text-conflict">Could not print. {error}</p>
          </CardBody>
        )}
      </Card>

      <div>
        <p className="label-caps mb-2">Outputs</p>
        {loading && (
          <p className="font-mono text-[11px] text-faint">Loading outputs…</p>
        )}

        {!loading && outputs && outputs.length === 0 && (
          <Card>
            <EmptyState
              icon={FileOutput}
              title="Nothing printed yet"
              description="When the holds are cleared, print the package from this page."
            />
          </Card>
        )}

        {!loading && outputs && outputs.length > 0 && (
          <div className="space-y-2.5">
            {outputs.map((output) => (
              <OutputCard key={output.id} output={output} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
