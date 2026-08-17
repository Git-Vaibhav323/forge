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

// Lightweight request layer: dedupe concurrent identical GETs and serve a
// very short-lived cache so switching tabs (Overview ↔ Questions ↔ Evidence)
// feels instant instead of re-hitting a remote DB each time.
const inflight = new Map<string, Promise<unknown>>();
const cache = new Map<string, { value: unknown; ts: number }>();
const requestGen = new Map<string, number>();
const DEFAULT_TTL = 15000;
const HEAVY_READ_TTL = 30000;

function cachedGet<T>(key: string, fn: () => Promise<T>, ttl = DEFAULT_TTL): Promise<T> {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.ts < ttl) {
    return Promise.resolve(hit.value as T);
  }
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;

  const gen = (requestGen.get(key) ?? 0) + 1;
  requestGen.set(key, gen);

  const pending = fn()
    .then((value) => {
      if (requestGen.get(key) === gen) {
        cache.set(key, { value, ts: Date.now() });
      }
      return value;
    })
    .finally(() => {
      if (requestGen.get(key) === gen) {
        inflight.delete(key);
      }
    });
  inflight.set(key, pending);
  return pending;
}

function dedupe<T>(key: string, fn: () => Promise<T>, ttl = DEFAULT_TTL): Promise<T> {
  return cachedGet(key, fn, ttl);
}

function invalidateApi(prefix: string) {
  for (const key of [...cache.keys()]) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
  for (const key of [...inflight.keys(), ...requestGen.keys()]) {
    if (key.startsWith(prefix)) {
      inflight.delete(key);
      requestGen.set(key, (requestGen.get(key) ?? 0) + 1);
    }
  }
}

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
  return cachedGet("GET:/api/projects", () => http<Project[]>("/api/projects"));
}

export async function getProject(id: string): Promise<Project | undefined> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.projects.find((p) => p.id === id);
  }
  return dedupe(`GET:/api/projects/${id}`, () =>
    http<Project>(`/api/projects/${id}`)
  );
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
  const created = await http<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
  invalidateApi("GET:/api/projects");
  return created;
}

export async function deleteProject(id: string): Promise<void> {
  if (USE_MOCK) {
    await simulateLatency(300);
    state.projects = state.projects.filter((p) => p.id !== id);
    delete state.attributes[id];
    delete state.reviewItems[id];
    delete state.questions[id];
    delete state.outputs[id];
    return;
  }
  invalidateApi("GET:/api/projects");
  const res = await fetch(`${API_BASE}/api/projects/${id}`, { method: "DELETE" });
  if (res.status === 404) {
    throw new Error("Job not found");
  }
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
}

export type UploadIntent = "reupload" | "replace";

export interface DuplicateDocumentDetail {
  code: "duplicate_file";
  message: string;
  existingDocumentId: string;
  existingFilename: string;
  contentHash: string;
}

export class DuplicateDocumentError extends Error {
  detail: DuplicateDocumentDetail;

  constructor(detail: DuplicateDocumentDetail) {
    super(detail.message);
    this.name = "DuplicateDocumentError";
    this.detail = detail;
  }
}

export async function uploadDocument(
  projectId: string,
  file: File,
  intent?: UploadIntent
): Promise<{ documentId: string; status: string; filename?: string }> {
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
  const query = intent ? `?intent=${intent}` : "";
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/files${query}`, {
    method: "POST",
    body: form,
  });
  if (res.status === 409) {
    const body = (await res.json()) as { detail: DuplicateDocumentDetail };
    throw new DuplicateDocumentError(body.detail);
  }
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  invalidateApi(`GET:/api/projects/${projectId}`);
  invalidateApi("GET:/api/projects");
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
  return cachedGet(`GET:/api/projects/${projectId}/attributes`, () =>
    http<Attribute[]>(`/api/projects/${projectId}/attributes`)
  , HEAVY_READ_TTL);
}

/** Re-read every PDF/web source on the job and rebuild cited attributes (M4). */
export async function extractAttributes(projectId: string): Promise<Attribute[]> {
  if (USE_MOCK) {
    await simulateLatency(600);
    return state.attributes[projectId] ?? [];
  }
  invalidateApi(`GET:/api/projects/${projectId}`);
  invalidateApi(`GET:/api/projects/${projectId}/questions`);
  return http<Attribute[]>(`/api/projects/${projectId}/attributes/extract`, {
    method: "POST",
  });
}

/** Add a web page as a citeable document (fetch URL or paste HTML). */
export async function addWebSource(
  projectId: string,
  input: { url: string; html?: string },
  intent?: UploadIntent
): Promise<{
  documentId: string;
  status: string;
  filename?: string;
  type?: string;
  sourceUrl?: string;
}> {
  if (USE_MOCK) {
    await simulateLatency(500);
    const project = state.projects.find((p) => p.id === projectId);
    const documentId = `doc-${Math.floor(Math.random() * 9000 + 1000)}`;
    project?.documents.push({
      id: documentId,
      filename: input.url,
      type: "web",
      status: "processing",
      uploadedAt: new Date().toISOString(),
      sourceUrl: input.url,
    });
    return { documentId, status: "processing", type: "web", sourceUrl: input.url };
  }
  const query = intent ? `?intent=${intent}` : "";
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/sources${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: input.url, html: input.html || undefined }),
  });
  if (res.status === 409) {
    const body = (await res.json()) as { detail: DuplicateDocumentDetail };
    throw new DuplicateDocumentError(body.detail);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Could not add web source (${res.status}): ${text}`);
  }
  invalidateApi(`GET:/api/projects/${projectId}`);
  invalidateApi("GET:/api/projects");
  return res.json();
}

// ---------------------------------------------------------------------------
// Questions (completeness loop)
// ---------------------------------------------------------------------------

export async function listQuestions(projectId: string): Promise<Question[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.questions[projectId] ?? [];
  }
  return dedupe(`GET:/api/projects/${projectId}/questions`, () =>
    http<Question[]>(`/api/projects/${projectId}/questions`)
  , HEAVY_READ_TTL);
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
  invalidateApi(`GET:/api/projects/${projectId}`);
  try {
    return await http<Question>(
      `/api/projects/${projectId}/questions/${questionId}/answer`,
      { method: "POST", body: JSON.stringify({ answer }) }
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "";
    if (message.includes("409") && message.includes("not open")) {
      const questions = await listQuestions(projectId);
      const answered = questions.find((item) => item.id === questionId);
      if (answered) return answered;
    }
    // Gateway timeout / network error — the backend may already have saved the answer.
    if (
      message.includes("Failed to fetch") ||
      message.includes("504") ||
      message.includes("502")
    ) {
      invalidateApi(`GET:/api/projects/${projectId}/questions`);
      const questions = await listQuestions(projectId);
      const answered = questions.find((item) => item.id === questionId);
      if (answered?.status === "answered") return answered;
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Review / human approval
// ---------------------------------------------------------------------------

export async function listReviewItems(projectId: string): Promise<ReviewItem[]> {
  if (USE_MOCK) {
    await simulateLatency();
    return state.reviewItems[projectId] ?? [];
  }
  return cachedGet(`GET:/api/projects/${projectId}/reviews`, () =>
    http<ReviewItem[]>(`/api/projects/${projectId}/reviews`)
  , HEAVY_READ_TTL);
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
  // A decision changes attribute status, conflict/approval counts, and can
  // touch sibling jobs — drop every cached view of this project and the list.
  invalidateApi(`GET:/api/projects/${projectId}`);
  invalidateApi("GET:/api/projects");
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
  return cachedGet(`GET:/api/projects/${projectId}/outputs`, () =>
    http<OutputArtifact[]>(`/api/projects/${projectId}/outputs`)
  , HEAVY_READ_TTL);
}

/**
 * Absolute URL for an artifact's bytes, or undefined when the QA gate blocked
 * generation and no file exists.
 */
export function outputDownloadUrl(output: OutputArtifact): string | undefined {
  if (!output.downloadUrl) return undefined;
  return USE_MOCK ? undefined : `${API_BASE}${output.downloadUrl}`;
}

export function outputPreviewUrl(output: OutputArtifact): string | undefined {
  if (!output.downloadUrl) return undefined;
  return USE_MOCK ? undefined : `${API_BASE}${output.downloadUrl.replace("/download", "/preview")}`;
}

export async function fetchOutputPreview(
  output: OutputArtifact
): Promise<{ content: string; filename: string }> {
  if (USE_MOCK || !output.downloadUrl) {
    return { content: "", filename: output.filename };
  }
  return http<{ content: string; filename: string }>(
    output.downloadUrl.replace("/download", "/preview")
  );
}

export async function downloadOutput(output: OutputArtifact): Promise<void> {
  if (USE_MOCK || !output.downloadUrl) return;

  const res = await fetch(`${API_BASE}${output.downloadUrl}`);
  if (!res.ok) {
    let detail =
      res.status === 404
        ? "This output is no longer available. Click Print again to regenerate it."
        : `Download failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (typeof body.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body — keep the default message.
    }
    throw new Error(detail);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = output.filename;
  anchor.click();
  URL.revokeObjectURL(url);
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
  // Generating re-derives the record and can flip the job's status, so drop
  // every cached view of it.
  invalidateApi(`GET:/api/projects/${projectId}`);
  invalidateApi(`GET:/api/projects/${projectId}/outputs`);
  invalidateApi("GET:/api/projects");
  return http<OutputArtifact>(`/api/projects/${projectId}/outputs`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}

export const apiMode = USE_MOCK ? "mock" : "live";
