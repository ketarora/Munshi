import type { Mode } from "@/lib/api";

export function ModeStamp({ mode }: { mode: Mode | string }) {
  const cls = mode === "LIVE" ? "live" : mode === "SANDBOX" ? "sandbox" : "sim";
  return <span className={`stamp ${cls}`}>{mode}</span>;
}

const STATE_MAP: Record<string, { cls: string; label: string }> = {
  SUCCEEDED: { cls: "ok", label: "settled" },
  AWAITING_APPROVAL: { cls: "pending", label: "approval" },
  AWAITING_READBACK: { cls: "pending", label: "readback" },
  NEEDS_CLARIFICATION: { cls: "pending", label: "clarify" },
  EXECUTING: { cls: "pending", label: "executing" },
  FAILED: { cls: "failed", label: "failed" },
  REJECTED: { cls: "failed", label: "blocked" },
  CANCELLED: { cls: "cancelled", label: "cancelled" },
  EXPIRED: { cls: "expired", label: "expired" },
  APPROVED: { cls: "ok", label: "approved" },
  PENDING: { cls: "pending", label: "needs you" },
  DENIED: { cls: "cancelled", label: "denied" },
  STALE: { cls: "cancelled", label: "stale" },
};

export function StateStamp({ state }: { state: string }) {
  const mapped = STATE_MAP[state] ?? { cls: "muted", label: state.toLowerCase() };
  return <span className={`stamp ${mapped.cls}`}>{mapped.label}</span>;
}

export function requireLabel(state: string): string {
  return STATE_MAP[state]?.label ?? state;
}
