// Typed client for the Problem 7 FastAPI routes (backend/main.py). No other backend.

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  created_at: string;
  notes: string[];
  pending_payment_requests: string[];
  draft_ids: string[];
  last_run_id: string | null;
}

export interface TicketList {
  today: string | null;
  tickets: Ticket[];
}

export interface Draft {
  id: string;
  kind: string;
  to: string;
  subject: string;
  body: string;
  created_by: string;
  status: string;
}

export interface TicketDetail {
  ok: boolean;
  today: string | null;
  ticket: Ticket & { notes: string | null };
  lease: Record<string, unknown> | null;
  invoice: Record<string, unknown> | null;
  payment_requests: PaymentRequest[];
  drafts: Draft[];
  last_run_id: string | null;
}

export interface BossDecision {
  ticket_id: number;
  assigned_to: AgentName[];
  decision: string;
  status_after: string;
  waiting_on: string[];
}

export interface BossReport {
  agent: "boss";
  summary: string;
  decisions: BossDecision[];
  human_actions_needed: string[];
}

export interface RunInfo {
  run_id: string;
  ticket_id: number;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  output: BossReport | null;
  error: string | null;
  events_url: string;
}

export interface ToolUse {
  tool: string;
  args: string | null;
  result: string | null;
}

export interface AgentReportDigest {
  summary?: string;
  actions_taken?: string[];
  needs_human_approval?: string[];
  blocked_by?: string[];
  facts?: string[];
  decisions?: BossDecision[];
  human_actions_needed?: string[];
}

export interface AgentEvent {
  ts: string;
  run_id: string;
  ticket_id: number | null;
  agent: AgentName;
  chain: string;
  depth: number;
  step: number | null;
  type: "agent_start" | "model_request" | "model_response" | "delegation" | "agent_stop";
  said: string | null;
  mcp_tools: ToolUse[];
  delegation: { to_agent: AgentName; task: string; allowed: boolean; error: string | null } | null;
  stop_reason: string | null;
  finish_reason: string | null;
  report: AgentReportDigest | null;
}

export interface Payment {
  id: number;
  kind: string;
  ref_id: number;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
}

export interface Cash {
  as_of: string | null;
  account: string;
  balance: number;
  balance_date: string;
  pending_requests_total: number;
  available_after_pending: number;
  unpaid_invoices_total: number;
  rent_due_total: number;
  cash_after_all_obligations: number;
  payments: Payment[];
}

export interface PaymentRequest {
  id: string;
  kind: "invoice" | "lease";
  ref_id: number;
  amount: number;
  account: string;
  due: string;
  ticket_id: number | null;
  reason: string;
  requested_by: string;
  requested_on: string;
  status: string;
}

export interface Health {
  ok: boolean;
  model: string;
  active_run: string | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the desk API at ${API_BASE}. Is the backend running?`);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : `Request failed (${res.status}).`);
  }
  return body as T;
}

export const api = {
  health: () => call<Health>("/api/health"),
  tickets: () => call<TicketList>("/api/tickets"),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => call<RunInfo>(`/api/tickets/${id}/run`, { method: "POST" }),
  runs: () => call<RunInfo[]>("/api/runs"),
  run: (runId: string) => call<RunInfo>(`/api/runs/${runId}`),
  events: (runId: string) => call<{ total: number; events: AgentEvent[] }>(`/api/events?run_id=${runId}&limit=1000`),
  cash: () => call<Cash>("/api/cash"),
  paymentRequests: () => call<{ pending: PaymentRequest[]; cash: Cash }>("/api/payment-requests"),
  approve: (id: string, approvedBy: string) =>
    call<{ ok: boolean; request: PaymentRequest; payment_id: number; cash: Cash }>(
      `/api/payment-requests/${id}/approve`,
      { method: "POST", body: JSON.stringify({ approved_by: approvedBy }) },
    ),
  reject: (id: string, rejectedBy: string, reason: string) =>
    call<{ ok: boolean; cash: Cash }>(`/api/payment-requests/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    }),
};
