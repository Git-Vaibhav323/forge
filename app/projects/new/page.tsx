"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { ProjectGoal } from "@/lib/types";
import { GoalSelector } from "@/components/projects/GoalSelector";
import { CategorySelector } from "@/components/projects/CategorySelector";
import { UploadDropzone } from "@/components/projects/UploadDropzone";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { categoryLabel } from "@/lib/categories";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [goal, setGoal] = useState<ProjectGoal | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = name.trim().length > 0 && category && goal;

  const missing: string[] = [];
  if (!goal) missing.push("deliverable type");
  if (!name.trim()) missing.push("job name");
  if (!category) missing.push("work type");

  async function handleSubmit() {
    if (!canSubmit || !goal) return;
    setSubmitting(true);
    try {
      const project = await api.createProject({
        name,
        goal,
        category: categoryLabel(category),
      });
      await Promise.all(files.map((file) => api.uploadDocument(project.id, file)));
      router.push(`/projects/${project.id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-6">
      <h1 className="text-[17px] font-semibold">Open a job</h1>
      <p className="mt-1 mb-5 max-w-lg text-[12px] leading-relaxed text-muted">
        Choose what you need to produce, name the job, and add any files you
        already have. Questions come one at a time from built-in templates.
      </p>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">
              Job name <span className="text-conflict">*</span>
            </p>
          </CardHeader>
          <CardBody>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q4 website refresh — client Acme"
              autoFocus
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">
              What type of work is this? <span className="text-conflict">*</span>
            </p>
            <p className="mt-0.5 text-[12px] text-muted">
              Built-in questions adapt to this — no AI, one question at a time.
            </p>
          </CardHeader>
          <CardBody>
            <CategorySelector value={category} onChange={setCategory} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">
              What should leave the desk? <span className="text-conflict">*</span>
            </p>
          </CardHeader>
          <CardBody>
            <GoalSelector value={goal} onChange={setGoal} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">What you already have</p>
            <p className="mt-0.5 text-[12px] text-muted">
              Optional. PDFs, spreadsheets, screenshots — anything you already have.
            </p>
          </CardHeader>
          <CardBody>
            <UploadDropzone files={files} onFilesChange={setFiles} />
          </CardBody>
        </Card>

        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            {missing.length > 0 ? (
              <p className="text-[12px] text-review">
                Still needed: {missing.join(", ")}
              </p>
            ) : (
              <p className="text-[11px] text-faint">
                High-risk fields still stop for a person. Nothing publishes itself.
              </p>
            )}
          </div>
          <Button
            variant="primary"
            disabled={!canSubmit || submitting}
            onClick={handleSubmit}
          >
            {submitting ? "Opening…" : "Open job"}
          </Button>
        </div>
      </div>
    </div>
  );
}
