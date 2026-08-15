import type {
  Attribute,
  OutputArtifact,
  Project,
  ProjectGoal,
  Question,
  ReviewItem,
  ReviewStatus,
} from "./types";
import {
  mockAttributes,
  mockOutputs,
  mockProjects,
  mockQuestions,
  mockReviewItems,
} from "./mock-data";
import { simulateLatency } from "./utils";

/**
 * Thin API client.
 *
 * If NEXT_PUBLIC_API_BASE_URL is set, every function below calls the real
 * backend at the documented REST path (see backend/README.md and
 * context.md → "API contract"). If it's unset, functions read/write an
 * in-memory copy of lib/mock-data.ts so the UI is fully clickable without
 * a backend running.
 *
 * Swap-over plan: once the backend implements a route, nothing in the
 * components needs to change — only the fetch call inside the matching
 * function here.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;
const USE_MOCK = !API_BASE;

// In-memory mutable copies so mock-mode actions (answer, approve, etc.)
// visibly persist across navigation within a session.
const state = {
  projects: [...mockProjects],
  attributes: structuredClone(mockAttributes),
  reviewItems: structuredClone(mockReviewItems),
  questions: structuredClone(mockQuestions),
  outputs: structuredClone(mockOutputs),
};

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export async function listProjects(): Promise<Project[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.projects;
  }
  return http<Project[]>("/api/projects");
}

export async function getProject(id: string): Promise<Project | undefined> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.projects.find((p) => p.id === id);
  }
  return http<Project>(`/api/projects/${id}`);
}

export async function createProject(input: {
  name: string;
  goal: ProjectGoal;
  category: string;
}): Promise<Project> {
  if (USE_MOCK) {
    await simulateLatency(500);
    const project: Project = {
      id: `prj-${Math.floor(Math.random() * 9000 + 1000)}`,
      name: input.name,
      goal: input.goal,
      category: input.category,
      status: "draft",
      completionScore: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      documents: [],
      blockingFieldsCount: 0,
      conflictsCount: 0,
      pendingApprovalsCount: 0,
    };
    state.projects.unshift(project);
    state.attributes[project.id] = [];
    state.reviewItems[project.id] = [];
    state.questions[project.id] = [];
    state.outputs[project.id] = [];
    return project;
  }
  return http<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function uploadDocument(
  projectId: string,
  file: File
): Promise<{ documentId: string; status: string }> {
  if (USE_MOCK) {
    await simulateLatency(600);
    const project = state.projects.find((p) => p.id === projectId);
    const documentId = `doc-${Math.floor(Math.random() * 9000 + 1000)}`;
    project?.documents.push({
      id: documentId,
      filename: file.name,
      type: guessDocType(file.name),
      status: "processing",
      uploadedAt: new Date().toISOString(),
    });
    return { documentId, status: "processing" };
  }
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/files`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

function guessDocType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "webp"].includes(ext ?? "")) return "image";
  if (["csv", "xlsx", "xls"].includes(ext ?? "")) return "catalog";
  return "document";
}

// ---------------------------------------------------------------------------
// Attributes / evidence
// ---------------------------------------------------------------------------

export async function listAttributes(projectId: string): Promise<Attribute[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.attributes[projectId] ?? [];
  }
  return http<Attribute[]>(`/api/projects/${projectId}/attributes`);
}

// ---------------------------------------------------------------------------
// Questions (completeness loop)
// ---------------------------------------------------------------------------

export async function listQuestions(projectId: string): Promise<Question[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.questions[projectId] ?? [];
  }
  return http<Question[]>(`/api/projects/${projectId}/questions`);
}

export async function answerQuestion(
  projectId: string,
  questionId: string,
  answer: string
): Promise<Question> {
  if (USE_MOCK) {
    await simulateLatency(400);
    const q = (state.questions[projectId] ?? []).find(
      (item) => item.id === questionId
    );
    if (!q) throw new Error("Question not found");
    q.status = "answered";
    q.answer = answer;
    q.answeredAt = new Date().toISOString();
    return q;
  }
  return http<Question>(
    `/api/projects/${projectId}/questions/${questionId}/answer`,
    { method: "POST", body: JSON.stringify({ answer }) }
  );
}

// ---------------------------------------------------------------------------
// Review / human approval
// ---------------------------------------------------------------------------

export async function listReviewItems(projectId: string): Promise<ReviewItem[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.reviewItems[projectId] ?? [];
  }
  return http<ReviewItem[]>(`/api/projects/${projectId}/reviews`);
}

export async function submitReviewDecision(
  projectId: string,
  reviewId: string,
  decision: {
    action: "approve" | "edit" | "reject" | "unresolved";
    value?: string;
    propagate?: boolean;
  }
): Promise<ReviewItem> {
  if (USE_MOCK) {
    await simulateLatency(450);
    const item = (state.reviewItems[projectId] ?? []).find(
      (r) => r.id === reviewId
    );
    if (!item) throw new Error("Review item not found");
    const statusMap: Record<typeof decision.action, ReviewStatus> = {
      approve: "approved",
      edit: "edited",
      reject: "rejected",
      unresolved: "unresolved",
    };
    item.status = statusMap[decision.action];
    if (decision.action === "edit" && decision.value) {
      item.proposedValue = decision.value;
    }
    return item;
  }
  return http<ReviewItem>(`/api/reviews/${reviewId}/decision`, {
    method: "POST",
    body: JSON.stringify({ projectId, ...decision }),
  });
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

export async function listOutputs(projectId: string): Promise<OutputArtifact[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.outputs[projectId] ?? [];
  }
  return http<OutputArtifact[]>(`/api/projects/${projectId}/outputs`);
}

export async function generateOutput(
  projectId: string,
  type: string
): Promise<OutputArtifact> {
  if (USE_MOCK) {
    await simulateLatency(900);
    const output: OutputArtifact = {
      id: `out-${Math.floor(Math.random() * 9000 + 1000)}`,
      projectId,
      type,
      filename: `${type}_${projectId}.json`,
      status: "generated",
      generatedAt: new Date().toISOString(),
    };
    state.outputs[projectId] = [...(state.outputs[projectId] ?? []), output];
    return output;
  }
  return http<OutputArtifact>(`/api/projects/${projectId}/outputs`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}

export const apiMode = USE_MOCK ? "mock" : "live";
