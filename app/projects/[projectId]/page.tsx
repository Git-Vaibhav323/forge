"use client";

import Link from "next/link";
import { FileText } from "lucide-react";
import { useAttributes, useOutputs, useProject, useQuestions, useReviewItems } from "@/hooks/useProjectData";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { formatDate } from "@/lib/utils";

export default function ProjectOverviewPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: project } = useProject(projectId);
  const { data: attributes } = useAttributes(projectId);
  const { data: questions } = useQuestions(projectId);
  const { data: reviewItems } = useReviewItems(projectId);
  const { data: outputs } = useOutputs(projectId);

  if (!project) return null;

  const verifiedCount = attributes?.filter((a) => a.status === "verified" || a.status === "known").length ?? 0;
  const openQuestion = questions?.find((q) => q.status === "open");
  const pendingReviews = reviewItems?.filter((r) => r.status === "pending" || r.status === "unresolved") ?? [];

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 space-y-4">
        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">What to do next</p>
          </CardHeader>
          <CardBody>
            {openQuestion ? (
              <Link
                href={`/projects/${projectId}/questions`}
                className="block border border-review/40 bg-review-soft/40 p-3 hover:border-review"
              >
                <p className="label-caps mb-1 text-review">Asked of you</p>
                <p className="text-[13px] font-medium text-ink">
                  {openQuestion.text}
                </p>
                <p className="mt-0.5 text-[12px] text-muted">
                  {openQuestion.whyAsked}
                </p>
              </Link>
            ) : pendingReviews.length > 0 ? (
              <Link
                href={`/projects/${projectId}/review`}
                className="block border border-conflict/40 bg-conflict-soft/40 p-3 hover:border-conflict"
              >
                <p className="label-caps mb-1 text-conflict">Held for you</p>
                <p className="text-[13px] font-medium text-ink">
                  {pendingReviews.length} field
                  {pendingReviews.length > 1 ? "s" : ""} will not publish until
                  you decide
                </p>
                <p className="mt-0.5 text-[12px] text-muted">
                  Conflicts and high-risk values sit here. The desk will not
                  guess.
                </p>
              </Link>
            ) : (
              <Link
                href={`/projects/${projectId}/outputs`}
                className="block border border-verified/40 bg-verified-soft/40 p-3 hover:border-verified"
              >
                <p className="label-caps mb-1 text-verified">Clear to generate</p>
                <p className="text-[13px] font-medium text-ink">
                  Nothing is blocking this job
                </p>
                <p className="mt-0.5 text-[12px] text-muted">
                  Print the package when you are ready. It will only use
                  approved facts.
                </p>
              </Link>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">Files on the job</p>
          </CardHeader>
          <CardBody className="p-0">
            <ul className="divide-y divide-line">
              {project.documents.map((doc) => (
                <li
                  key={doc.id}
                  className="flex items-center gap-3 px-4 py-2.5 text-[13px]"
                >
                  <FileText size={14} className="shrink-0 text-faint" />
                  <span className="min-w-0 flex-1 truncate">{doc.filename}</span>
                  <span className="font-mono text-[11px] uppercase text-faint">
                    {doc.type.replace(/_/g, " ")}
                  </span>
                  <span
                    className={
                      doc.status === "processed"
                        ? "font-mono text-[11px] text-verified"
                        : doc.status === "failed"
                        ? "font-mono text-[11px] text-conflict"
                        : "font-mono text-[11px] text-review"
                    }
                  >
                    {doc.status}
                  </span>
                </li>
              ))}
              {project.documents.length === 0 && (
                <li className="px-4 py-4 text-[13px] text-muted">
                  No files on this job yet.
                </li>
              )}
            </ul>
          </CardBody>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">Counts</p>
          </CardHeader>
          <CardBody className="space-y-2.5">
            <Stat label="Attributes verified" value={`${verifiedCount} / ${attributes?.length ?? 0}`} />
            <Stat label="Open questions" value={String(questions?.filter((q) => q.status === "open").length ?? 0)} />
            <Stat label="Conflicts" value={String(project.conflictsCount)} tone={project.conflictsCount > 0 ? "conflict" : undefined} />
            <Stat label="Pending approvals" value={String(project.pendingApprovalsCount)} tone={project.pendingApprovalsCount > 0 ? "review" : undefined} />
            <Stat label="Outputs generated" value={String(outputs?.filter((o) => o.status !== "draft").length ?? 0)} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-[13px] font-medium">Opened / last write</p>
          </CardHeader>
          <CardBody className="space-y-1.5 text-[12px] text-muted">
            <p>Created {formatDate(project.createdAt)}</p>
            <p>Last updated {formatDate(project.updatedAt)}</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "conflict" | "review";
}) {
  return (
    <div className="flex items-center justify-between text-[13px]">
      <span className="text-muted">{label}</span>
      <span
        className={
          "num font-mono font-medium " +
          (tone === "conflict" ? "text-conflict" : tone === "review" ? "text-review" : "text-ink")
        }
      >
        {value}
      </span>
    </div>
  );
}
