// Typed client for the FastAPI backend. Calls go to /api/* which next.config.ts
// rewrites to the backend. Every function is a scaffold stub.

export type RunStatus =
  | "starting"
  | "running"
  | "sleeping"
  | "paused"
  | "completed"
  | "terminated";

export interface Supervisor {
  id: string;
  name: string;
  base_instruction: string;
  available_actions: string[];
  default_wake_minutes: number;
  wake_aggressiveness: "passive" | "balanced" | "aggressive";
  created_at: string;
}

export interface Run {
  id: string;
  supervisor_id: string;
  order_id: string;
  workflow_id: string;
  status: RunStatus;
  sleep_state: "awake" | "sleeping";
  next_wake_at: string | null;
  memory_summary: string;
  wakeup_guidance: string;
  run_instructions: string[];
  final_output: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Activity {
  id: number;
  run_id: string;
  kind: string;
  title: string;
  payload: Record<string, unknown>;
  important: boolean;
  created_at: string;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}

// --- supervisors ---
export const listSupervisors = () => http<Supervisor[]>("/supervisors");
export const createSupervisor = (body: Partial<Supervisor>) =>
  http<Supervisor>("/supervisors", { method: "POST", body: JSON.stringify(body) });

// --- runs ---
export const listRuns = () => http<Run[]>("/runs");
export const getRun = (id: string) =>
  http<{ run: Run; timeline: Activity[] }>(`/runs/${id}`);
export const createRun = (body: { supervisor_id: string; order_id: string; order_context?: unknown; run_instructions?: string[] }) =>
  http<Run>("/runs", { method: "POST", body: JSON.stringify(body) });

// --- signals into a live run ---
export const injectEvent = (id: string, event: { type: string; payload?: unknown }) =>
  http<void>(`/runs/${id}/events`, { method: "POST", body: JSON.stringify(event) });
export const addInstruction = (id: string, text: string) =>
  http<void>(`/runs/${id}/instructions`, { method: "POST", body: JSON.stringify({ text }) });
export const interruptRun = (id: string) => http<void>(`/runs/${id}/interrupt`, { method: "POST" });
export const resumeRun = (id: string) => http<void>(`/runs/${id}/resume`, { method: "POST" });
export const terminateRun = (id: string) => http<void>(`/runs/${id}/terminate`, { method: "POST" });
