import { FileOutput, Download, CheckCircle2, XCircle } from "lucide-react";
import type { OutputArtifact } from "@/lib/types";
import { Button } from "@/components/ui/Button";
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

export function OutputCard({ output }: { output: OutputArtifact }) {
  const cfg = statusConfig[output.status];
  return (
    <div className="flex items-start gap-3 rounded border border-line p-4">
      <FileOutput size={18} className="mt-0.5 shrink-0 text-faint" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-[13px] font-medium">{output.filename}</p>
          <span className={cn("font-mono text-[11px] uppercase", cfg.tone)}>
            {cfg.label}
          </span>
        </div>
        <p className="mt-0.5 font-mono text-[11px] text-faint">
          {output.type.replace(/_/g, " ")}
          {output.generatedAt && ` · generated ${new Date(output.generatedAt).toLocaleString()}`}
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
      </div>

      {(output.status === "generated" || output.status === "qa_passed") && (
        <Button size="sm" variant="secondary">
          <Download size={13} /> Download
        </Button>
      )}
    </div>
  );
}
