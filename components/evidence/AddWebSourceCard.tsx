"use client";

import { useState } from "react";
import { Globe } from "lucide-react";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Field";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

export function AddWebSourceCard({
  projectId,
  onAdded,
  disabled,
}: {
  projectId: string;
  onAdded: () => void;
  disabled?: boolean;
}) {
  const [url, setUrl] = useState("");
  const [html, setHtml] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function submit() {
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Paste a catalog or datasheet URL first.");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      await api.addWebSource(projectId, {
        url: trimmed,
        html: showPaste && html.trim() ? html : undefined,
      });
      setUrl("");
      setHtml("");
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Globe size={14} className="text-muted" />
          <div>
            <p className="text-[13px] font-medium">Add a web source</p>
            <p className="mt-0.5 text-[12px] text-muted">
              Paste a manufacturer or catalog URL. ForgeData stores the page and
              only cites labelled facts — it does not invent from the open web.
            </p>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <div>
          <Label>Page URL</Label>
          <Input
            type="url"
            placeholder="https://example.com/product/datasheet"
            value={url}
            disabled={busy || disabled}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
          />
        </div>

        <button
          type="button"
          className="text-[12px] text-muted underline-offset-2 hover:text-ink hover:underline"
          onClick={() => setShowPaste((v) => !v)}
        >
          {showPaste
            ? "Hide pasted HTML"
            : "Or paste HTML instead (for JS-heavy pages)"}
        </button>

        {showPaste && (
          <div>
            <Label>HTML snapshot</Label>
            <textarea
              value={html}
              disabled={busy || disabled}
              onChange={(e) => setHtml(e.target.value)}
              rows={5}
              placeholder="Paste the page HTML. The URL above is kept as the citation source."
              className="w-full rounded border border-line bg-panel px-3 py-2 font-mono text-[12px] text-ink placeholder:text-faint focus:border-accent focus:outline-none"
            />
          </div>
        )}

        {error && <p className="text-[12px] text-conflict">{error}</p>}

        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] text-faint">
            After add, re-scan so quotes land on the field table (helps M5
            review when a PDF and a web page disagree).
          </p>
          <Button
            size="sm"
            variant="secondary"
            disabled={busy || disabled || !url.trim()}
            onClick={submit}
          >
            {busy ? "Saving…" : "Add source"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
