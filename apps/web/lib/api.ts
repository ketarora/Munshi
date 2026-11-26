export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

function getApiBase(): string {
  if (typeof window !== "undefined") {
    const override = (window as unknown as { __MUNSHI_API_BASE__?: string }).__MUNSHI_API_BASE__;
    if (override) return override;
  }
  return API_BASE;
}
export const CHILD_TOKEN = process.env.NEXT_PUBLIC_MUNSHI_TOKEN ?? "demo-child-token";
export const PARENT_NUMBER = process.env.NEXT_PUBLIC_PARENT_NUMBER ?? "9812345678";

export type Mode = "LIVE" | "SANDBOX" | "SIMULATED";

export interface Limits {
  per_txn_cap_paise: number;
  daily_cap_paise: number;
  monthly_cap_paise: number;
  hard_ceiling_paise: number;
  capabilities_enabled: string[];
  allowlisted_payees: string[];
  paused: boolean;
  updated_at: string;
}

export interface Spend {
  today_paise: number;
  month_paise: number;
  monthly_remaining_paise: number;
  daily_remaining_paise: number;
}

export interface Transaction {
  id: string;
  capability: string;
  description: string | null;
  amount_paise: number | null;
  state: string;
  mode: Mode;
  reason: string;
  created_at: string;
  payee: string | null;
}

export interface Approval {
  id: string;
  txn_id: string;
  family_id: string;
  state: string;
  summary: string;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
  decided_by: string | null;
  channel: string | null;
}

export interface Notification {
  id: string;
  family_id: string;
  channel: string;
  kind: string;
  body: string;
  related_txn: string | null;
  created_at: string;
}

export interface Bootstrap {
  family: { id: string; name: string; timezone: string };
  parent: { name: string; masked: string };
  child: { name: string };
  limits: Limits;
  spend: Spend;
  approvals: Approval[];
  ledger: Transaction[];
  bills: { id: string; biller: string; account_no: string; amount_paise: number; due_date: string; paid: number }[];
  notifications: Notification[];
  callbacks: Notification[];
  calls: { id: string; started_at: string; status: string; family_id: string | null }[];
  audit: { ok: boolean; entries: number; first_bad_seq: number | null };
  modes: Record<string, string>;
}

export interface TurnResponse {
  call_id: string;
  reply: string;
  lang: string;
  decision: string;
  trace: {
    stages: { stage: string; ms: number }[];
    proposal?: { intent: string; slots: Record<string, unknown>; confidence: number; language_detected: string };
    policy?: { decision: string; rule: string; reason: string; input?: Record<string, unknown> } | null;
    resolved?: { capability: string; amount_paise: number | null; payee: string | null; description: string };
    execution?: { txn_id: string; state: string; amount_paise: number | null; reference: string };
    mode?: Record<string, string>;
    degraded?: boolean;
  };
  txn: Transaction | null;
  approval: Approval | null;
  done: boolean;
}

export interface StartCallResponse {
  call_id: string;
  verified: boolean;
  greeting: string;
  family: { id: string; name: string } | null;
  parent_name: string | null;
  resumed: boolean;
  pending: string | null;
}

export interface TraceResponse {
  call: { id: string; started_at: string; status: string; family_id: string | null; meta: Record<string, unknown> };
  turns: {
    idx: number;
    asr_text: string;
    asr_confidence: number;
    proposal: Record<string, unknown>;
    decision: string;
    spoken_reply: string;
    trace: TurnResponse["trace"];
    created_at: string;
  }[];
  audit: { ok: boolean; entries: number; first_bad_seq: number | null };
  audit_rows: { seq: number; ts: string; actor: string; event: string; payload_json: string; hash: string }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (payload as { detail?: string; error?: string }).detail;
    throw new Error(detail ?? `Request failed (${response.status})`);
  }
  return payload as T;
}

function authHeaders(): Record<string, string> {
  return { "X-Munshi-Token": CHILD_TOKEN };
}

export const api = {
  startCall: (callerNumber: string) =>
    request<StartCallResponse>("/api/calls/start", {
      method: "POST",
      body: JSON.stringify({ caller_number: callerNumber }),
    }),
  turn: (callId: string, text: string, silence = false) =>
    request<TurnResponse>(`/api/calls/${callId}/turn`, {
      method: "POST",
      body: JSON.stringify({ text, silence }),
    }),
  dtmf: (callId: string, key: string) =>
    request<TurnResponse>(`/api/calls/${callId}/dtmf`, {
      method: "POST",
      body: JSON.stringify({ key }),
    }),
  endCall: (callId: string) =>
    request<{ call_id: string; status: string }>(`/api/calls/${callId}/end`, { method: "POST" }),
  bootstrap: () => request<Bootstrap>("/api/console/bootstrap", { headers: authHeaders() }),
  decide: (approvalId: string, decision: "approve" | "deny") =>
    request<{ status: string; txn: Transaction | null }>(`/api/console/approvals/${approvalId}`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ decision }),
    }),
  decideVoice: (approvalId: string, text: string) =>
    request<{ status: string; txn: Transaction | null }>(`/api/console/approvals/${approvalId}/voice`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ text }),
    }),
  pause: (paused: boolean) =>
    request<{ paused: boolean; cancelled: string[] }>("/api/console/pause", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ paused }),
    }),
  pauseVoice: (text: string) =>
    request<{ action: string; paused?: boolean }>("/api/console/pause/voice", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ text }),
    }),
  parseLimits: (text: string) =>
    request<{
      saved: boolean;
      parsed: {
        capabilities: string[];
        monthly_rupees: number | null;
        per_txn_rupees: number | null;
        needs_clarification: boolean;
        clarification: string | null;
        readback: string;
      };
      token: string | null;
      requires_second_factor: boolean;
    }>("/api/console/limits/parse", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ text }),
    }),
  confirmLimits: (token: string, confirmed: boolean, secondFactor?: string) =>
    request<{ saved: boolean; limits?: Limits }>("/api/console/limits/confirm", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ token, confirmed, second_factor: secondFactor ?? null }),
    }),
  calls: () => request<{ calls: (TraceResponse["call"] & { turns: TraceResponse["turns"] })[] }>("/api/calls", { headers: authHeaders() }),
  trace: (callId: string) => request<TraceResponse>(`/api/calls/${callId}/trace`, { headers: authHeaders() }),
  resetDemo: () => request<{ ok: boolean; reset_ms: number }>("/api/demo/reset", { method: "POST" }),
};

export function rupees(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  return `₹${new Intl.NumberFormat("en-IN").format(Math.round(paise / 100))}`;
}

export function exactRupees(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  const whole = Math.floor(paise / 100);
  const rest = paise % 100;
  const formatted = new Intl.NumberFormat("en-IN").format(whole);
  return rest ? `₹${formatted}.${String(rest).padStart(2, "0")}` : `₹${formatted}`;
}

export function when(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export const CAPABILITY_LABELS: Record<string, string> = {
  pay_bill: "Bill payment",
  book_gas_cylinder: "Gas cylinder",
  refill_medicine: "Medicine refill",
  message_child: "Message to child",
};
