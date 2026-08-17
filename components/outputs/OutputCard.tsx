import { useState } from "react";
import { ChevronDown, ChevronUp, FileOutput, Download, CheckCircle2, XCircle } from "lucide-react";
import type { OutputArtifact } from "@/lib/types";
import * as api from "@/lib/api";
import { cn } from "@/lib/utils";

const statusConfig: Record<
  OutputArtifact["status"],
  { label: string; tone: string }
> = {
  draft: { label: "Draft", tone: "text-muted" },
  generated: { label: "Generated", tone: "text-accent" },
  qa_passed: { label: "QA passed", tone: "text-verified" },
  qa_failed: { label: "QA failed", tone: "text-conflict" },
};

function formatLabel(filename: string): string {
  if (filename.endsWith(".pdf")) return "PDF report";
  if (filename.endsWith(".csv")) return "CSV export";
  if (filename.endsWith(".md")) return "Markdown report";
  return "Report";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function OutputCard({ output }: { output: OutputArtifact }) {
  const cfg = statusConfig[output.status];
  const canDownload = !!output.downloadUrl;
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string>();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string>();
  const [previewContent, setPreviewContent] = useState<string>();

  async function handleDownload() {
    setDownloading(true);
    setDownloadError(undefined);
    try {
      await api.downloadOutput(output);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : String(err));
    } finally {
      setDownloading(false);
    }
  }

  async function handlePreviewToggle() {
    if (previewOpen) {
      setPreviewOpen(false);
      return;
    }
    setPreviewOpen(true);
    if (previewContent || previewLoading) return;

    setPreviewLoading(true);
    setPreviewError(undefined);
    try {
      const body = await api.fetchOutputPreview(output);
      setPreviewContent(body.content);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <div className="rounded border border-line p-4">
      <div className="flex items-start gap-3">
        <FileOutput size={18} className="mt-0.5 shrink-0 text-faint" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-[13px] font-medium">{output.filename}</p>
            <span className={cn("font-mono text-[11px] uppercase", cfg.tone)}>
              {cfg.label}
            </span>
          </div>
          <p className="mt-0.5 font-mono text-[11px] text-faint">
            {formatLabel(output.filename)}
            {" · "}
            {output.type.replace(/_/g, " ")}
            {output.generatedAt && ` · generated ${new Date(output.generatedAt).toLocaleString()}`}
            {typeof output.sizeBytes === "number" && ` · ${formatSize(output.sizeBytes)}`}
          </p>

          {output.qaNotes && output.qaNotes.length > 0 && (
            <ul className="mt-2 space-y-1">
              {output.qaNotes.map((note, i) => (
                <li key={i} className="flex items-center gap-1.5 text-[12px] text-muted">
                  {output.status === "qa_passed" ? (
                    <CheckCircle2 size={12} className="text-verified" />
                  ) : (
                    <XCircle size={12} className="text-conflict" />
                  )}
                  {note}
                </li>
              ))}
            </ul>
          )}

          {downloadError && (
            <p className="mt-2 text-[12px] text-conflict">{downloadError}</p>
          )}
        </div>

        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          {canDownload && (
            <button
              type="button"
              onClick={handlePreviewToggle}
              className={cn(
                "inline-flex items-center justify-center gap-1.5 font-medium",
                "h-7 px-2.5 text-[13px]",
                "border border-line bg-panel text-ink hover:border-line-strong"
              )}
            >
              {previewOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {previewOpen ? "Hide report" : "View report"}
            </button>
          )}
          {canDownload && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              aria-label={`Download ${output.filename}`}
              className={cn(
                "inline-flex items-center justify-center gap-1.5 font-medium",
                "h-7 px-2.5 text-[13px]",
                "border border-line bg-panel text-ink hover:border-line-strong",
                "disabled:cursor-not-allowed disabled:opacity-60"
              )}
            >
              <Download size={13} /> {downloading ? "Downloading…" : "Download"}
            </button>
          )}
        </div>
      </div>

      {previewOpen && (
        <div className="mt-4 border-t border-line pt-4">
          {previewLoading && (
            <p className="font-mono text-[11px] text-faint">Loading report…</p>
          )}
          {previewError && (
            <p className="text-[12px] text-conflict">{previewError}</p>
          )}
          {previewContent && (
            <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded border border-line bg-canvas p-4 font-mono text-[12px] leading-relaxed text-ink">
              {previewContent}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
