// API client for the FastAPI backend

import type { RunSummary, StepSummary, StepDetail, TraceData, JobStatus, AdminStatus, AudioInfo } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path}: ${res.status} ${res.statusText}`);
  return res.json();
}

async function postJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!res.ok) throw new Error(`API ${path}: ${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  listRuns: () => fetchJson<RunSummary[]>("/api/runs"),

  getTrace: (runId: string) => fetchJson<TraceData>(`/api/runs/${runId}/trace`),

  getSteps: (runId: string) => fetchJson<StepSummary[]>(`/api/runs/${runId}/steps`),

  getStep: (runId: string, index: number) =>
    fetchJson<StepDetail>(`/api/runs/${runId}/step/${index}`),

  uploadAudio: async (file: File): Promise<{ job_id: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },

  getJobStatus: (jobId: string) => fetchJson<JobStatus>(`/api/jobs/${jobId}`),

  // Re-run pipeline
  rerunPipeline: (runId: string) => postJson<{ job_id: string; message: string }>(`/api/rerun/${runId}`),

  // Audio
  getAudioUrl: (runId: string) => `${API_BASE}/api/runs/${runId}/audio`,
  checkAudio: (runId: string) => fetchJson<AudioInfo>(`/api/runs/${runId}/has-audio`),

  // Admin
  adminStatus: () => fetchJson<AdminStatus>("/api/admin/status"),
  restartBackend: () => postJson<{ status: string }>("/api/admin/restart-backend"),
  restartFrontend: () => postJson<{ status: string }>("/api/admin/restart-frontend"),
};
