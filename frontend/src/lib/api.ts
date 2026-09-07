// Typed client for the FastAPI backend. Requests go to /api/* which
// next.config.ts rewrites to the backend (BACKEND_URL, default :8000).

export type RunStatus = "active" | "sleeping" | "completed" | "terminated";

export type ActivityType =
  | "incoming_event"
  | "wake_decision"
  | "agent_action"
  | "manual_instruction"
  | "final_output";

export interface Supervisor {
  id: string;
  name: string;
  base_instruction: string;
  model_settings: Record<string, unknown>;
  created_at: string;
}

export interface Run {
  id: string;
  order_id: string;
  supervisor_id: string;
  status: RunStatus;
  memory_summary: string;
  workflow_id: string | null;
  next_wake_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivityLogRow {
  id: number;
  run_id: string;
  type: ActivityType;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunDetail {
  run: Run;
  timeline: ActivityLogRow[];
  live: {
    status: string;
    next_wake_at: string | null;
    queued_events: number;
    standing_instructions: string[];
    memory_summary: string;
    processed_wakes: number;
    terminating: boolean;
  } | null;
}

// Order lifecycle events the control panel can inject (mirrors backend
// models.EVENT_TYPES). A free-text type is also allowed - unknown types
// exercise the classifier's "escalate" path.
export const EVENT_TYPES = [
  "order_created",
  "payment_confirmed",
  "payment_failed",
  "shipment_created",
  "shipment_delayed",
  "delivered",
  "refund_requested",
  "customer_message_received",
  "no_update_for_n_hours",
] as const;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- supervisors ---
export const listSupervisors = () => http<Supervisor[]>("/supervisors");
export const createSupervisor = (body: {
  name: string;
  base_instruction: string;
  model_settings?: Record<string, unknown>;
}) => http<Supervisor>("/supervisors", { method: "POST", body: JSON.stringify(body) });

// --- runs ---
export const listRuns = (status?: RunStatus) =>
  http<Run[]>(`/runs${status ? `?status=${status}` : ""}`);
export const getRun = (id: string) => http<RunDetail>(`/runs/${id}`);
export const createRun = (body: {
  supervisor_id: string;
  order_id: string;
  order_context?: Record<string, unknown>;
  run_instructions?: string[];
}) => http<Run>("/runs", { method: "POST", body: JSON.stringify(body) });

// --- signals into a live run ---
export const injectEvent = (
  id: string,
  event: { type: string; payload?: Record<string, unknown> },
) => http<{ ok: boolean }>(`/runs/${id}/events`, { method: "POST", body: JSON.stringify(event) });

export const addInstruction = (id: string, text: string) =>
  http<{ ok: boolean }>(`/runs/${id}/instructions`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });

export const interruptRun = (id: string, reason = "manual interrupt") =>
  http<{ ok: boolean }>(`/runs/${id}/interrupt?reason=${encodeURIComponent(reason)}`, {
    method: "POST",
  });
