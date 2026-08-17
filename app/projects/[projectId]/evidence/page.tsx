"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, Globe } from "lucide-react";
import * as api from "@/lib/api";
import { useAttributes, useProject } from "@/hooks/useProjectData";
import { AddWebSourceCard } from "@/components/evidence/AddWebSourceCard";
import { AttributeTable } from "@/components/evidence/AttributeTable";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function EvidencePage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: project, refresh: refreshProject } = useProject(projectId);
  const { data: attributes, loading, refresh } = useAttributes(projectId);
  const [selectedId, setSelectedId] = useState<string>();
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string>();
  const autoTried = useRef(false);

  const documents = project?.documents ?? [];
  const docCount = documents.length;
  const webDocs = documents.filter(
    (d) => d.type === "web" || Boolean(d.sourceUrl)
  );
  const fileDocs = documents.filter(
    (d) => d.type !== "web" && !d.sourceUrl
  );

  async function runScan() {
    setScanning(true);
    setScanError(undefined);
    try {
      await api.extractAttributes(projectId);
      refresh();
      refreshProject();
    } catch (err) {
      setScanError(err instanceof Error ? err.message : String(err));
    } finally {
      setScanning(false);
    }
  }

  async function handleWebAdded() {
    refreshProject();
    await runScan();
  }

  // First visit: if the job has documents but nothing has been extracted yet,
  // read sources once automatically so the tab is not empty.
  useEffect(() => {
    if (autoTried.current) return;
    if (loading || scanning) return;
    if (!attributes) return;
    if (attributes.length === 0 && docCount > 0) {
      autoTried.current = true;
      runScan();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attributes, loading, docCount]);

  useEffect(() => {
    if (attributes && attributes.length > 0 && !selectedId) {
      setSelectedId(attributes[0]!.id);
    }
  }, [attributes, selectedId]);

  const selected = attributes?.find((a) => a.id === selectedId);
  const busy = scanning || (loading && !attributes);

  return (
    <div className="space-y-4">
      <AddWebSourceCard
        projectId={projectId}
        onAdded={handleWebAdded}
        disabled={scanning}
      />

      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2 overflow-hidden">
          <CardHeader className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[13px] font-medium">Fields on the record</p>
              <p className="mt-0.5 text-[12px] text-muted">
                A value without a source is not shown as fact. PDF and web
                quotes both appear here — disagreements become conflicts for
                Review.
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={scanning || docCount === 0}
              onClick={runScan}
            >
              {scanning ? "Reading sources…" : "Re-scan documents"}
            </Button>
          </CardHeader>

          {docCount > 0 && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 border-b border-line px-4 py-2 text-[11px] text-muted">
              <span className="inline-flex items-center gap-1">
                <FileText size={11} /> {fileDocs.length} file
                {fileDocs.length === 1 ? "" : "s"}
              </span>
              <span className="inline-flex items-center gap-1">
                <Globe size={11} /> {webDocs.length} web
                {webDocs.length === 1 ? "" : " sources"}
              </span>
            </div>
          )}

          {scanError && (
            <p className="px-4 py-3 text-[13px] text-conflict">
              Could not read the documents. {scanError}
            </p>
          )}

          {busy && (
            <p className="px-4 py-6 font-mono text-[11px] text-faint">
              {scanning
                ? "Reading documents and web pages, citing fields…"
                : "Reading fields…"}
            </p>
          )}

          {!busy && attributes && attributes.length === 0 && (
            <p className="px-4 py-6 text-[13px] text-muted">
              {docCount === 0
                ? "No sources on this job yet. Upload a datasheet or add a web URL above, then re-scan."
                : "No fields could be read from the current sources."}
            </p>
          )}

          {!busy && attributes && attributes.length > 0 && (
            <AttributeTable
              attributes={attributes}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </Card>

        <Card className="h-fit">
          <CardBody>
            <EvidencePanel attribute={selected} />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
