"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { speak, useRecognition } from "@/lib/voice";
import type { Approval, Bootstrap, Transaction } from "@/lib/api";
import { rupees, when } from "@/lib/api";
import { ModeStamp, StateStamp } from "@/components/Stamp";
import Waveform from "@/components/Waveform";
import SpatialTilt from "@/components/SpatialTilt";

interface Props {
  snapshot: Bootstrap | null;
  busy: boolean;
  voiceOn: boolean;
  onDecide: (approval: Approval, decision: "approve" | "deny") => void;
  onVoiceDecision: (approval: Approval, text: string) => void;
}

export default function ChildPhone({ snapshot, busy, voiceOn, onDecide, onVoiceDecision }: Props) {
  const pending = snapshot?.approvals.find((approval) => approval.state === "PENDING") ?? null;
  const [lastPlayed, setLastPlayed] = useState<string | null>(null);

  const { listening, supported, error, start, stop } = useRecognition((text) => {
    if (pending) onVoiceDecision(pending, text);
  });

  const notes = snapshot?.notifications.slice(0, 4) ?? [];
  const ledger: Transaction[] = (snapshot?.ledger ?? [])
    .filter((txn) => txn.state === "SUCCEEDED")
    .slice(0, 3);
  const paused = snapshot?.limits.paused ?? false;

  return (
    <SpatialTilt maxTilt={4.5}>
      <motion.div
        className="phone"
        aria-label="Rohit's phone (simulated)"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
      >
        <div className="phone-top">
          <span>Rohit · Bengaluru</span>
          <span>9:41 · WhatsApp Sim</span>
        </div>
        <div className="phone-screen">
          <div className="phone-screen-head">
            <div className="phone-owner">
              <img
                src="/images/rohit-portrait.jpg"
                alt="Rohit"
                className="avatar-ring avatar-sm"
                width={38}
                height={38}
              />
              <div>
                <div className="phone-title">Munshi</div>
                <div className="phone-sub">voice notes · limits · approvals</div>
              </div>
            </div>
            <span className="stamp sim">simulator</span>
          </div>

          <AnimatePresence>
            {paused ? (
              <motion.div
                className="phone-paused"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
              >
                Munshi ruka hua hai — sab kaam band
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {pending ? (
              <motion.div
                className="approval-card"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
              >
                <div className="phone-section-label">
                  <span>Manzoori chahiye</span>
                  <StateStamp state="PENDING" />
                </div>
                <p className="approval-summary">{pending.summary}</p>
                <div className="approval-actions">
                  <button
                    className="btn btn-accent btn-sm"
                    disabled={busy}
                    onClick={() => onDecide(pending, "approve")}
                  >
                    Haan, kar do
                  </button>
                  <button
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => onDecide(pending, "deny")}
                  >
                    Nahi
                  </button>
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => (listening ? stop() : start())}
                  disabled={busy || !supported}
                >
                  <Waveform active={listening} bars={5} />
                  {listening ? "Sun raha hoon…" : "Bolke jawab dein"}
                </button>
                {error ? <span className="alert-line">{error}</span> : null}
              </motion.div>
            ) : null}
          </AnimatePresence>

          <div className="phone-section-label">
            <span>Munshi ke voice notes</span>
            <span>{notes.length}</span>
          </div>

          {notes.length === 0 ? (
            <p className="phone-empty">
              Abhi koi note nahi. Call stage par Amma ka bill bhejiye — yahan voice note aa jayega.
            </p>
          ) : (
            notes.map((note) => (
            <motion.button
              key={note.id}
              className="voice-note"
              onClick={() => {
                speak(note.body, voiceOn, "hi-IN");
                setLastPlayed(note.id);
              }}
              title="Sunne ke liye dabaiye"
              initial={{ y: 4 }}
              animate={{ y: 0 }}
              transition={{ duration: 0.18 }}
            >
                <Waveform active={lastPlayed === note.id && voiceOn} bars={5} />
                <span className="note-body">
                  {note.body}
                  <span className="note-meta">
                    {when(note.created_at)} · {note.kind.replaceAll("_", " ")}
                  </span>
                </span>
              </motion.button>
            ))
          )}

          <div className="phone-ledger">
            <div className="phone-section-label">
              <span>Aaj ka khata · settled</span>
              <span className="mono">{snapshot ? rupees(snapshot.spend.today_paise) : "—"}</span>
            </div>
            {ledger.length === 0 ? (
              <p className="phone-empty">Koi entry nahi.</p>
            ) : (
              ledger.map((txn) => (
                <div className="phone-ledger-row" key={txn.id}>
                  <span>
                    {txn.description ?? txn.capability}
                    <br />
                    <ModeStamp mode={txn.mode} /> <StateStamp state={txn.state} />
                  </span>
                  <span className="amt">{rupees(txn.amount_paise)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </motion.div>
    </SpatialTilt>
  );
}
