"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, rupees, when, type TraceResponse } from "@/lib/api";
import AuditChain3D from "@/components/3d/AuditChain3D";

type CallList = Awaited<ReturnType<typeof api.calls>>["calls"];

const RULES = [
  "P-CALLER-UNVERIFIED",
  "P-SYSTEM-PAUSED",
  "P-DUPLICATE",
  "P-CAPABILITY-DISABLED",
  "P-AMOUNT-INVALID",
  "P-CONFIDENCE-LOW",
  "P-CONFIDENCE-EXHAUSTED",
  "P-HARD-CEILING",
  "P-NEW-PAYEE",
  "P-PER-TXN-CAP",
  "P-DAILY-CAP",
  "P-MONTHLY-CAP",
  "P-OK",
];

const EASE = [0.4, 0, 0.2, 1] as const;

function decisionClass(decision: string): string {
  if (decision === "AUTO_EXECUTE") return "done";
  if (decision === "REJECT" || decision === "ESCALATE_TO_CHILD") return "blocked";
  return "";
}

const turnVariant = {
  hidden: { opacity: 0, x: -12 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.05, duration: 0.35, ease: EASE },
  }),
};

export default function TraceView() {
  const [calls, setCalls] = useState<CallList>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.calls();
      setCalls(result.calls);
      setError(null);
      setSelected((prev) =>
        prev && result.calls.some((c) => c.id === prev) ? prev : result.calls[0]?.id ?? null,
      );
    } catch (exc) {
      setError(
        exc instanceof Error
          ? `${exc.message} — API chal rahi hai? (uvicorn apps/api/run.py)`
          : "Calls load nahi hui.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCalls();
    const onReset = () => {
      setSelected(null);
      setTrace(null);
      void loadCalls();
    };
    window.addEventListener("munshi:demo-reset", onReset);
    return () => window.removeEventListener("munshi:demo-reset", onReset);
  }, [loadCalls]);

  useEffect(() => {
    if (!selected) {
      setTrace(null);
      return;
    }
    let cancelled = false;
    void api
      .trace(selected)
      .then((result) => {
        if (!cancelled) setTrace(result);
      })
      .catch((exc: unknown) => {
        if (!cancelled) setError(exc instanceof Error ? exc.message : "Trace load nahi hui.");
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  return (
    <main className="page">
      <motion.section
        className="trace-hero-banner"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        <div
          className="trace-hero-bg"
          aria-hidden="true"
          style={{ backgroundImage: "url('/images/vault-seal.jpg')" }}
        />
        <div className="trace-hero-scrim" aria-hidden="true" />
        <div className="trace-hero-inner">
          <div>
            <span className="eyebrow hero-eyebrow">Judge mode · carbon copy</span>
            <h1 className="display hero-display">
              Under the <em>hood.</em>
            </h1>
            <p className="hero-lede">
              Har call ka poora sach: ASR text, intent JSON, kaunsa niyam chala, kitna time laga,
              aur SHA-256 hash-chained audit ledger valid hai ya nahi.
            </p>
          </div>
          <div className="trace-hero-actions">
            <button className="btn hero-ghost-btn btn-sm" onClick={() => void loadCalls()} disabled={loading}>
              Refresh trace
            </button>
          </div>
        </div>
      </motion.section>

      {error ? <p className="alert-line">{error}</p> : null}

      {calls.length === 0 && !loading ? (
        <motion.div
          className="card"
          style={{ marginTop: "1.5rem" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <h2>Abhi koi call nahi</h2>
          <p className="empty-note">
            <Link href="/">Call stage</Link> par jaakar ek call shuru kijiye, phir yahan uski
            pipeline aur 3D audit chain dikhegi.
          </p>
        </motion.div>
      ) : (
        <motion.div
          className="trace-layout"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.45, ease: EASE }}
        >
          <aside>
            <div className="card-label" style={{ marginBottom: "0.5rem" }}>
              Recent calls
            </div>
            <div className="call-list">
              {calls.map((call) => (
                <button
                  key={call.id}
                  aria-current={selected === call.id}
                  onClick={() => setSelected(call.id)}
                >
                  <div className="call-id">{call.id}</div>
                  <div className="call-meta">
                    {when(call.started_at)} · {call.status} · {call.turns.length} turns
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section>
            <AnimatePresence mode="wait">
              {trace ? (
                <motion.div
                  className="trace-sheet"
                  key={trace.call.id}
                  initial={{ opacity: 0, scale: 0.99 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.99 }}
                  transition={{ duration: 0.35 }}
                >
                  <div className="trace-head">
                    <div>
                      <div className="mono-label">Call</div>
                      <h2>{trace.call.id}</h2>
                      <div className="mono-label" style={{ marginTop: "0.25rem" }}>
                        {when(trace.call.started_at)} · {trace.call.status} · {trace.call.family_id}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <span className={`stamp ${trace.audit.ok ? "ok" : "failed"}`}>
                        audit {trace.audit.ok ? "valid" : `broken @ ${trace.audit.first_bad_seq}`}
                      </span>
                      <span className="stamp sim">{trace.audit.entries} entries</span>
                    </div>
                  </div>

                  <AuditChain3D
                    entries={trace.audit.entries}
                    ok={trace.audit.ok}
                    firstBadSeq={trace.audit.first_bad_seq}
                  />

                  {trace.turns.length === 0 ? (
                    <p className="turn-reply" style={{ marginTop: "1rem" }}>
                      Sirf greeting hua; koi turn nahi.
                    </p>
                  ) : (
                    trace.turns.map((turn, i) => {
                      const policy = turn.trace.policy;
                      const resolved = turn.trace.resolved;
                      const proposal = turn.proposal as {
                        intent?: string;
                        confidence?: number;
                        language_detected?: string;
                      };
                      const stages = turn.trace.stages ?? [];
                      return (
                        <motion.article
                          className={`turn-record ${decisionClass(turn.decision)}`}
                          key={turn.idx}
                          custom={i}
                          variants={turnVariant}
                          initial="hidden"
                          animate="visible"
                        >
                          <div className="turn-head">
                            <span>
                              TURN {String(turn.idx).padStart(2, "0")} · {turn.decision.replaceAll("_", " ")}
                            </span>
                            <span className="badge">
                              {proposal.intent ?? "unclear"} ·{" "}
                              {Math.round((proposal.confidence ?? 0) * 100)}% ·{" "}
                              {proposal.language_detected ?? "—"}
                            </span>
                          </div>
                          <div className="turn-heard">
                            <span className="q">heard</span>
                            {turn.asr_text || "(silence)"}
                          </div>
                          <div className="turn-reply">
                            <span className="q">munshi</span>
                            {turn.spoken_reply}
                          </div>

                          {policy ? (
                            <div className="rule-card">
                              <div className="rule">{policy.rule}</div>
                              <div>{policy.reason}</div>
                            </div>
                          ) : turn.trace.execution ? (
                            <div className="rule-card">
                              <div className="rule">
                                execution · {turn.trace.execution.state}
                              </div>
                              <div>
                                {turn.trace.execution.txn_id} · {rupees(turn.trace.execution.amount_paise)} ·
                                ref {turn.trace.execution.reference} · completed the read-back above; no
                                fresh policy evaluation.
                              </div>
                            </div>
                          ) : (
                            <div className="rule-card">
                              <div className="rule">no policy call</div>
                              <div>This turn did not request or move money.</div>
                            </div>
                          )}

                          {resolved ? (
                            <div className="rule-card">
                              <div>
                                resolved · {resolved.capability} · {rupees(resolved.amount_paise)} ·{" "}
                                {resolved.payee ?? "no payee"}
                              </div>
                              <div className="rule">amount source: biller adapter, not ASR</div>
                            </div>
                          ) : null}

                          <div className="mono-label" style={{ marginTop: "0.55rem" }}>
                            {stages.map((stage) => `${stage.stage} ${stage.ms}ms`).join(" · ") || "no stages"}
                            {turn.trace.degraded ? " · DEGRADED" : ""}
                          </div>

                          <pre className="json">{JSON.stringify(turn.proposal, null, 2)}</pre>
                        </motion.article>
                      );
                    })
                  )}

                  <div className="trace-grid">
                    <div>
                      <div className="mono-label">Audit chain · latest entries (whole family)</div>
                      <div style={{ marginTop: "0.4rem" }}>
                        {trace.audit_rows.slice(-8).reverse().map((row) => (
                          <div className="audit-line" key={row.seq}>
                            <span>
                              {String(row.seq).padStart(3, "0")} · {row.event}
                            </span>
                            <span className="h">{row.hash.slice(0, 12)}…</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="mono-label">Adapters this turn</div>
                      <pre className="json">
                        {JSON.stringify(trace.turns[trace.turns.length - 1]?.trace.mode ?? {}, null, 2)}
                      </pre>
                    </div>
                  </div>

                  <details className="rules">
                    <summary>Policy rule order — first match wins</summary>
                    <ol>
                      {RULES.map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ol>
                  </details>
                </motion.div>
              ) : (
                <p className="empty-note">Call chuniye.</p>
              )}
            </AnimatePresence>
          </section>
        </motion.div>
      )}
    </main>
  );
}
