"use client";

import { usePathname } from "next/navigation";
import { useProject } from "@/hooks/useProjectData";
import { ProjectStatusBadge } from "@/components/shared/StatusBadge";
import { Tabs, TabItem } from "@/components/ui/Tabs";
import { PROJECT_GOAL_LABELS } from "@/lib/types";

export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: project, loading } = useProject(projectId);
  const pathname = usePathname();
  const base = `/projects/${projectId}`;

  const tabs: TabItem[] = [
    { href: base, label: "Overview" },
    { href: `${base}/evidence`, label: "Evidence" },
    { href: `${base}/questions`, label: "Questions" },
    {
      href: `${base}/review`,
      label: "Review",
      count: project?.pendingApprovalsCount,
      tone: project && project.conflictsCount > 0 ? "conflict" : "review",
    },
    { href: `${base}/outputs`, label: "Outputs" },
  ];

  return (
    <div className="px-6 py-5">
      {loading && (
        <p className="font-mono text-[11px] text-faint">Opening job…</p>
      )}

      {project && (
        <>
          <header className="mb-4 border-b border-line pb-3">
            <div className="flex items-baseline justify-between gap-4">
              <h1 className="min-w-0 truncate text-[17px] font-semibold">
                {project.name}
              </h1>
              <span className="num shrink-0 font-mono text-[12px] text-muted">
                {project.completionScore}% cited
              </span>
            </div>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-faint">
              <span>{project.id}</span>
              <span>·</span>
              <span>{PROJECT_GOAL_LABELS[project.goal]}</span>
              <span>·</span>
              <span>{project.category.replace(/_/g, " ")}</span>
              <ProjectStatusBadge status={project.status} />
            </p>
          </header>

          <div className="mb-5">
            <Tabs items={tabs} activeHref={pathname} />
          </div>
        </>
      )}

      {project && children}
    </div>
  );
}
