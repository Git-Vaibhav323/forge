"use client";

import { useRouter } from "next/navigation";
import { useState, type MouseEvent } from "react";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";

export function RemoveJobButton({
  projectId,
  projectName,
  redirectTo,
  onRemoved,
  size = "sm",
}: {
  projectId: string;
  projectName: string;
  redirectTo?: string;
  onRemoved?: () => void;
  size?: "sm" | "md";
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onRemove(event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    const ok = window.confirm(
      `Remove “${projectName}”? This deletes the job, its questions, and stored PDFs. This cannot be undone.`
    );
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteProject(projectId);
      onRemoved?.();
      if (redirectTo) {
        router.push(redirectTo);
      }
    } catch (err) {
      setBusy(false);
      window.alert(
        err instanceof Error ? err.message : "Could not remove this job."
      );
    }
  }

  return (
    <Button
      type="button"
      variant="danger"
      size={size}
      disabled={busy}
      onClick={onRemove}
    >
      {busy ? "Removing…" : "Remove job"}
    </Button>
  );
}
