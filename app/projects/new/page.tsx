"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { ProjectGoal } from "@/lib/types";
import { GoalSelector } from "@/components/projects/GoalSelector";
import { UploadDropzone } from "@/components/projects/UploadDropzone";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Field";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [goal, setGoal] = useState<ProjectGoal | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = name.trim().length > 0 && category.trim().length > 0 && goal;

  async function handleSubmit() {
    if (!canSubmit || !goal) return;
    setSubmitting(true);
    try {
      const project = await api.createProject({ name, goal, category });
      for (const file of files) {
        await api.uploadDocument(project.id, file);
      }
      router.push(`/projects/${project.id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-6">
      <h1 className="text-[17px] font-semibold">Open a job</h1>
      <p className="mt-1 mb-5 max-w-lg text-[12px] leading-relaxed text-muted">
        Say what this has to produce, name the product, then drop the messy
        files you already have. You can add more later.
      </p>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">What should leave the desk?</p>
          </CardHeader>
          <CardBody>
            <GoalSelector value={goal} onChange={setGoal} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">Identify it</p>
          </CardHeader>
          <CardBody className="grid grid-cols-2 gap-4">
            <div>
              <Label>Product / job name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="SV-24 outdoor water inlet valve"
              />
            </div>
            <div>
              <Label>Family</Label>
              <Input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="solenoid valve"
              />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">What you already have</p>
            <p className="mt-0.5 text-[12px] text-muted">
              Optional. A PDF datasheet, a nameplate photo, a CSV with holes —
              all of it is usable.
            </p>
          </CardHeader>
          <CardBody>
            <UploadDropzone files={files} onFilesChange={setFiles} />
          </CardBody>
        </Card>

        <div className="flex items-center justify-between">
          <p className="text-[11px] text-faint">
            High-risk fields still stop for a person. Nothing publishes itself.
          </p>
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
