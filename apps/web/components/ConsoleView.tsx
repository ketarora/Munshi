"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  api,
  rupees,
  exactRupees,
  when,
  type Approval,
  type Bootstrap,
} from "@/lib/api";
import { ModeStamp, StateStamp } from "@/components/Stamp";
import { useRecognition } from "@/lib/voice";
import BudgetVault3D from "@/components/3d/BudgetVault3D";

type ParsedLimits = Awaited<ReturnType<typeof api.parseLimits>>;

const BILLER_LABELS: Record<string, string> = {
  bijli: "Bijli",
  paani: "Paani",
  mobile: "Mobile",
};

const CAPABILITY_LABELS: Record<string, string> = {
  pay_bill: "Bill",
  book_gas_cylinder: "Gas cylinder",
  refill_medicine: "Dawai",
  message_child: "Message",
};

const EASE = [0.4, 0, 0.2, 1] as const;

const cardVariant = {
  hidden: { opacity: 0, y: 18 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: 0.08 + i * 0.07, duration: 0.45, ease: EASE },
  }),
};

export default function ConsoleView() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(
    "Amma ke liye bijli, gas aur dawai, mahine mein 5,000 tak.",
  );
  const [parsed, setParsed] = useState<ParsedLimits | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [second, setSecond] = useState("");
  const [requiresSecond, setRequiresSecond] = useState(false);
  const [onboardMsg, setOnboardMsg] = useState<string | null>(null);
  const [pauseMsg, setPauseMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const snapshot = await api.bootstrap();
      setData(snapshot);
      setError(null);
    } catch (exc) {
      setError(
        exc instanceof Error
          ? `${exc.message} — API chal rahi hai? (uvicorn apps/api/run.py)`
          : "API se baat nahi ho rahi.",
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onReset = () => {
      setParsed(null);
      setToken(null);
      setSecond("");
      setRequiresSecond(false);
      setOnboardMsg(null);
      setPauseMsg(null);
      void refresh();
    };
    window.addEventListener("munshi:demo-reset", onReset);
    return () => window.removeEventListener("munshi:demo-reset", onReset);
  }, [refresh]);

  useEffect(() => {
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const { listening, supported, error: micError, start, stop } = useRecognition(async (text) => {
    try {
      const result = await api.pauseVoice(text);
      setPauseMsg(
        result.action === "pause"
          ? "Awaaz se pause: Munshi ruk gaya."
          : result.action === "resume"
            ? "Awaaz se resume: Munshi chalu ho gaya."
            : "Sirf 'Munshi ruk jao' ya 'Munshi chalu karo' samajh aaya.",
      );
      await refresh();
    } catch (exc) {
      setPauseMsg(exc instanceof Error ? exc.message : "Awaaz se pause fail ho gaya.");
    }
  });

  const togglePause = async () => {
    if (!data) return;
    setBusy(true);
    try {
      const result = await api.pause(!data.limits.paused);
      setPauseMsg(
        result.paused
          ? `Munshi ruk gaya. ${result.cancelled.length} adhoore kaam cancel hue — koi paisa nahi kata.`
          : "Munshi chalu hai.",
      );
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Pause fail ho gaya.");
    } finally {
      setBusy(false);
    }
  };

  const decide = async (approval: Approval, decision: "approve" | "deny") => {
    setBusy(true);
    try {
      await api.decide(approval.id, decision);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Approval fail ho gaya.");
    } finally {
      setBusy(false);
    }
  };

  const parseNote = async () => {
    setBusy(true);
    setOnboardMsg(null);
    setParsed(null);
    setToken(null);
    try {
      const result = await api.parseLimits(note);
      setParsed(result);
      setToken(result.token);
      setRequiresSecond(result.requires_second_factor);
      if (result.parsed.needs_clarification) {
        setOnboardMsg(result.parsed.clarification);
      }
    } catch (exc) {
      setOnboardMsg(exc instanceof Error ? exc.message : "Note samajh nahi aaya.");
    } finally {
      setBusy(false);
    }
  };

  const confirmLimits = async (confirmed: boolean) => {
    if (!token) return;
    setBusy(true);
    try {
      const result = await api.confirmLimits(token, confirmed, requiresSecond ? second : undefined);
      if (result.saved) {
        setOnboardMsg("Lag gaya. Nayi limits ab se laagu hain.");
        setToken(null);
        setParsed(null);
        setSecond("");
        setRequiresSecond(false);
        await refresh();
      } else {
        setOnboardMsg("Theek hai, kuch nahi badla.");
        setToken(null);
        setParsed(null);
      }
    } catch (exc) {
      setOnboardMsg(
        exc instanceof Error ? `${exc.message} — demo second step: 246810` : "Save nahi hua.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return (
      <main className="page">
        <span className="eyebrow">Family console</span>
        <h1 className="display">Ghar ka khata.</h1>
        <p className="lede">{error ?? "Khata load ho raha hai…"}</p>
        {error ? (
          <button className="btn btn-primary" style={{ marginTop: "1rem" }} onClick={() => void refresh()}>
            Dobara koshish
          </button>
        ) : null}
      </main>
    );
  }

  const { limits, spend } = data;
  const paidPercent = Math.min(100, Math.round((spend.month_paise / Math.max(1, limits.monthly_cap_paise)) * 100));
  const remainingRatio = spend.monthly_remaining_paise / Math.max(1, limits.monthly_cap_paise);
  const pending = data.approvals.filter((approval) => approval.state === "PENDING");
  const recentDecided = data.approvals.filter((approval) => approval.state !== "PENDING").slice(0, 3);

  return (
    <main className="page">
      <motion.div
        className="console-head"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        <div className="console-title-group">
          <img
            src="/images/rohit-portrait.jpg"
            alt="Rohit"
            width={56}
            height={56}
            className="avatar-ring avatar-lg"
          />
          <div>
            <span className="eyebrow">Family console · {data.child.name}</span>
            <h1 className="display">
              Ghar ka <em>khata.</em>
            </h1>
            <p className="lede">
              {data.family.name} — {data.parent.name} ki line. Limits, ijazat aur har payment ka
              hisaab, ek jagah.
            </p>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
          <span className={`stamp ${data.audit.ok ? "ok" : "failed"}`}>
            Audit chain {data.audit.ok ? "valid" : "broken"}
          </span>
          <span className="stamp sim">{data.audit.entries} entries</span>
          <Link className="btn btn-sm" href="/trace">
            Under the hood →
          </Link>
        </div>
      </motion.div>

      {error ? <p className="alert-line">{error}</p> : null}

      <motion.section
        className="budget-band budget-band-3d"
        aria-label="Budget"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.5, ease: EASE }}
      >
        <div className="budget-main">
          <span className="card-label">Is mahine bacha</span>
          <div className="big-amount">
            <span className="cur">₹</span>
            {new Intl.NumberFormat("en-IN").format(Math.round(spend.monthly_remaining_paise / 100))}
          </div>
          <p className="budget-sub">
            {rupees(spend.month_paise)} kharch ho chuka, {rupees(limits.monthly_cap_paise)} ki
            chhat ke andar. Aaj {rupees(spend.daily_remaining_paise)} bacha hai.
          </p>
          <div className="ruler" aria-hidden="true">
            <motion.div
              className="ruler-fill"
              initial={{ width: 0 }}
              animate={{ width: `${paidPercent}%` }}
              transition={{ delay: 0.35, duration: 0.7, ease: EASE }}
            />
            <span className="ruler-label">{paidPercent}% kharch</span>
          </div>
        </div>

        <div className="budget-vault-col">
          <BudgetVault3D remainingRatio={remainingRatio} paused={limits.paused} />
        </div>

        <div className="budget-side">
          <div className="budget-line">
            <span>Aaj ka kharcha</span>
            <span className="val">{exactRupees(spend.today_paise)}</span>
          </div>
          <div className="budget-line">
            <span>Is mahine</span>
            <span className="val">{exactRupees(spend.month_paise)}</span>
          </div>
          <div className="budget-line">
            <span>Pending approvals</span>
            <span className="val">{pending.length}</span>
          </div>
          <div className="pause-box">
            <div className="pause-copy">
              <strong>{limits.paused ? "Munshi ruka hua hai" : "Munshi chalu hai"}</strong>
              <span>Pause sab kuch rok deta hai — turant.</span>
            </div>
            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <button
                className="btn btn-sm"
                onClick={() => (listening ? stop() : start())}
                disabled={!supported || busy}
                title="Bolkar pause/resume"
              >
                {listening ? "Sun raha…" : "Bolke"}
              </button>
              <button
                className="switch"
                role="switch"
                aria-checked={limits.paused}
                aria-label={limits.paused ? "Munshi chalu kijiye" : "Munshi rok dijiye"}
                onClick={() => void togglePause()}
                disabled={busy}
              />
            </div>
          </div>
          {pauseMsg ? <p className="saved-line">{pauseMsg}</p> : null}
          {micError ? <p className="alert-line">{micError}</p> : null}
        </div>
      </motion.section>

      <div className="console-grid">
        <motion.section
          className="card col-4"
          aria-label="Limits"
          custom={0}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Limits</h2>
          <p className="card-sub">Sirf Rohit badal sakta hai. Amma ki call se kabhi nahi.</p>
          <div className="limit-row">
            <span>Ek payment</span>
            <span className="leader" />
            <span className="val">{rupees(limits.per_txn_cap_paise)}</span>
          </div>
          <div className="limit-row">
            <span>Ek din</span>
            <span className="leader" />
            <span className="val">{rupees(limits.daily_cap_paise)}</span>
          </div>
          <div className="limit-row">
            <span>Ek mahina</span>
            <span className="leader" />
            <span className="val">{rupees(limits.monthly_cap_paise)}</span>
          </div>
          <div className="limit-row">
            <span>Hard ceiling</span>
            <span className="leader" />
            <span className="val">{rupees(limits.hard_ceiling_paise)}</span>
          </div>
          <div className="stamp-row">
            {limits.allowlisted_payees.map((payee) => (
              <span className="stamp ok" key={payee}>
                {BILLER_LABELS[payee] ?? payee} ✓
              </span>
            ))}
          </div>
          <div className="stamp-row">
            {limits.capabilities_enabled.map((capability) => (
              <span className="stamp muted" key={capability}>
                {CAPABILITY_LABELS[capability] ?? capability}
              </span>
            ))}
          </div>
        </motion.section>

        <motion.section
          className="card col-4"
          aria-label="Pending approvals"
          custom={1}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Manzoori</h2>
          <p className="card-sub">Naya payee ya limit se upar — Rohit ki haan zaroori.</p>
          {pending.length === 0 ? (
            <p className="empty-note">Kuch pending nahi. Call stage se naya payee try kijiye.</p>
          ) : (
            <div className="approval-list">
              {pending.map((approval) => (
                <div className="approval-item" key={approval.id}>
                  <div className="summary">{approval.summary}</div>
                  <div className="meta">
                    {when(approval.requested_at)} · expires {when(approval.expires_at)}
                  </div>
                  <div className="approval-actions">
                    <button
                      className="btn btn-accent btn-sm"
                      disabled={busy}
                      onClick={() => void decide(approval, "approve")}
                    >
                      Haan
                    </button>
                    <button
                      className="btn btn-sm"
                      disabled={busy}
                      onClick={() => void decide(approval, "deny")}
                    >
                      Nahi
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {recentDecided.length > 0 ? (
            <div className="note-list" style={{ marginTop: "0.8rem" }}>
              {recentDecided.map((approval) => (
                <div className="note-item" key={approval.id}>
                  <div className="note-text">{approval.summary}</div>
                  <div className="note-meta">
                    {approval.state} · {approval.decided_by ?? "system"}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </motion.section>

        <motion.section
          className="card col-4"
          aria-label="Bills and modes"
          custom={2}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Bills due</h2>
          <p className="card-sub">Rakam yahin se aati hai — Amma ki awaaz se nahi.</p>
          {data.bills.length === 0 ? (
            <p className="empty-note">Koi bill baaki nahi.</p>
          ) : (
            <div>
              {data.bills.map((bill) => (
                <div className="limit-row" key={bill.id}>
                  <span>
                    {BILLER_LABELS[bill.biller] ?? bill.biller} · {bill.account_no}
                    <br />
                    <span className="mono muted" style={{ fontSize: "0.62rem" }}>
                      due {bill.due_date}
                    </span>
                  </span>
                  <span className="leader" />
                  <span className="val">{rupees(bill.amount_paise)}</span>
                </div>
              ))}
            </div>
          )}
          <hr className="rule" />
          <div className="stamp-row">
            <ModeStamp mode={data.modes.payments.toUpperCase()} />
            <span className="stamp live">Browser voice</span>
            <span className="stamp muted">{data.modes.understanding}</span>
          </div>
          <p className="empty-note" style={{ marginTop: "0.5rem" }}>
            Gas aur dawai simulated hain. Bill payment bhi mock ledger par chalta hai — koi asli
            paisa nahi.
          </p>
        </motion.section>

        <motion.section
          className="card col-7"
          aria-label="Onboarding by voice note"
          custom={3}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Limits voice note se</h2>
          <p className="card-sub">
            Rohit ka note. Munshi padhkar sunata hai; aapki haan ke bina kuch save nahi hota.
          </p>
          <div className="field">
            <label htmlFor="limits-note">Voice note (transcript)</label>
            <textarea
              id="limits-note"
              className="input"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
            />
          </div>
          <div className="onboarding-actions">
            <button className="btn btn-primary btn-sm" onClick={() => void parseNote()} disabled={busy}>
              Samjho
            </button>
            {parsed ? (
              <button
                className="btn btn-sm"
                onClick={() => {
                  setParsed(null);
                  setToken(null);
                  setOnboardMsg(null);
                }}
              >
                Clear
              </button>
            ) : null}
          </div>

          <AnimatePresence>
            {parsed && token ? (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <p className="readback">{parsed.parsed.readback}</p>
                {requiresSecond ? (
                  <div className="inline-field">
                    <div className="field">
                      <label htmlFor="second-factor">Doosra step (demo code)</label>
                      <input
                        id="second-factor"
                        className="input"
                        value={second}
                        onChange={(event) => setSecond(event.target.value)}
                        placeholder="246810"
                        inputMode="numeric"
                      />
                    </div>
                  </div>
                ) : null}
                <div className="onboarding-actions">
                  <button
                    className="btn btn-accent btn-sm"
                    onClick={() => void confirmLimits(true)}
                    disabled={busy || (requiresSecond && !second)}
                  >
                    Haan, save karo
                  </button>
                  <button className="btn btn-sm" onClick={() => void confirmLimits(false)} disabled={busy}>
                    Nahi
                  </button>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
          {onboardMsg ? <p className={token ? "alert-line" : "saved-line"}>{onboardMsg}</p> : null}
        </motion.section>

        <motion.section
          className="card col-5"
          aria-label="Voice notes"
          custom={4}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Beta ke voice notes</h2>
          <p className="card-sub">Har payment ke baad ek note. Sunne ke liye dabaiye.</p>
          <div className="note-list">
            {data.notifications.length === 0 ? (
              <p className="empty-note">Abhi koi note nahi.</p>
            ) : (
              data.notifications.map((notification) => (
                <div className="note-item" key={notification.id}>
                  <div className="note-text">{notification.body}</div>
                  <div className="note-meta">
                    {when(notification.created_at)} · {notification.kind.replaceAll("_", " ")}
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.section>

        <motion.section
          className="card col-12"
          aria-label="Ledger"
          custom={5}
          variants={cardVariant}
          initial="hidden"
          animate="visible"
        >
          <h2>Khata</h2>
          <p className="card-sub">
            Har entry ke saath uska mode. LIVE kabhi nahi dikhega jab tak asli adapter na lage.
          </p>
          <div className="ledger-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Kaam</th>
                  <th>Rakam</th>
                  <th>Mode</th>
                  <th>Halat</th>
                  <th>Waqt</th>
                </tr>
              </thead>
              <tbody>
                {data.ledger.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="ledger-empty">
                      Khata khaali hai. Call stage se pehla bill bhejiye.
                    </td>
                  </tr>
                ) : (
                  data.ledger.map((txn) => (
                    <tr key={txn.id}>
                      <td className="what">
                        {txn.description ?? txn.capability}
                        <br />
                        <span className="mono muted" style={{ fontSize: "0.62rem" }}>
                          {txn.reason}
                        </span>
                      </td>
                      <td className="amt">{rupees(txn.amount_paise)}</td>
                      <td>
                        <ModeStamp mode={txn.mode} />
                      </td>
                      <td>
                        <StateStamp state={txn.state} />
                      </td>
                      <td className="when">{when(txn.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </motion.section>
      </div>
    </main>
  );
}
