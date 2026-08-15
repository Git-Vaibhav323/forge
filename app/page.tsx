"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Project } from "@/lib/types";
import { PROJECT_GOAL_LABELS } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ProjectStatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { FolderOpen } from "lucide-react";
import { timeAgo } from "@/lib/utils";
import { RemoveJobButton } from "@/components/projects/RemoveJobButton";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>();

  useEffect(() => {
    api.listProjects().then(setProjects);
  }, []);

  const openCount =
    projects?.filter((p) => p.status !== "completed" && p.status !== "generated")
      .length ?? 0;

  return (
    <div className="px-6 py-6">
      <header className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold">Jobs on this desk</h1>
          <p className="mt-1 max-w-xl text-[12px] leading-relaxed text-muted">
            {projects
              ? `${openCount} still open. Completeness is how much of the record is cited — not how pretty the extract looks.`
              : "Reading the local drawer…"}
          </p>
        </div>
        <Link href="/projects/new">
          <Button variant="primary">Open a job</Button>
        </Link>
      </header>

      {!projects && (
        <p className="font-mono text-[11px] text-faint">Loading jobs…</p>
      )}

      {projects && projects.length === 0 && (
        <div className="border border-line bg-panel">
          <EmptyState
            icon={FolderOpen}
            title="Drawer is empty"
            description="Open a job, name the product, and drop whatever you already have — a datasheet, a photo of the nameplate, a half-finished CSV."
            action={
              <Link href="/projects/new">
                <Button variant="primary">Open a job</Button>
              </Link>
            }
          />
        </div>
      )}

      {projects && projects.length > 0 && (
        <div className="overflow-x-auto border border-line bg-panel">
          <table className="w-full min-w-[720px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line bg-paper/80">
                <th className="label-caps px-3 py-2 font-normal">Job</th>
                <th className="label-caps px-3 py-2 font-normal">Produces</th>
                <th className="label-caps px-3 py-2 font-normal">Status</th>
                <th className="label-caps px-3 py-2 text-right font-normal">
                  Cited
                </th>
                <th className="label-caps px-3 py-2 text-right font-normal">
                  Issues
                </th>
                <th className="label-caps px-3 py-2 text-right font-normal">
                  Files
                </th>
                <th className="label-caps px-3 py-2 text-right font-normal">
                  Touched
                </th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => {
                const issues =
                  project.conflictsCount + project.pendingApprovalsCount;
                return (
                  <tr
                    key={project.id}
                    className="border-b border-line last:border-b-0 hover:bg-paper/70"
                  >
                    <td className="px-3 py-2.5">
                      <Link
                        href={`/projects/${project.id}`}
                        className="font-medium text-ink hover:underline"
                      >
                        {project.name}
                      </Link>
                      <p className="font-mono text-[10px] text-faint">
                        {project.id} · {project.category.replace(/_/g, " ")}
                      </p>
                    </td>
                    <td className="px-3 py-2.5 text-muted">
                      {PROJECT_GOAL_LABELS[project.goal]}
                    </td>
                    <td className="px-3 py-2.5">
                      <ProjectStatusBadge status={project.status} />
                    </td>
                    <td className="num px-3 py-2.5 text-right font-mono text-[12px]">
                      {project.completionScore}%
                    </td>
                    <td
                      className={
                        "num px-3 py-2.5 text-right font-mono text-[12px] " +
                        (issues > 0 ? "text-conflict" : "text-faint")
                      }
                    >
                      {issues > 0 ? issues : "—"}
                    </td>
                    <td className="num px-3 py-2.5 text-right font-mono text-[12px] text-muted">
                      {project.documents.length}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-[11px] text-faint">
                      {timeAgo(project.updatedAt)}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <RemoveJobButton
                        projectId={project.id}
                        projectName={project.name}
                        onRemoved={() =>
                          setProjects((current) =>
                            current?.filter((p) => p.id !== project.id)
                          )
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
