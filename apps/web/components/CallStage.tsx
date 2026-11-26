"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Volume2, VolumeX, Phone, PhoneOff, ShieldCheck, Hash, PauseCircle } from "lucide-react";
import {
  PARENT_NUMBER,
  api,
  type Approval,
  type Bootstrap,
  type TurnResponse,
  rupees,
} from "@/lib/api";
import { speak, stopSpeaking, useRecognition } from "@/lib/voice";
import ChildPhone from "@/components/ChildPhone";
import PipelineStrip from "@/components/PipelineStrip";
import VoiceCore3D, { type VoiceCoreMode } from "@/components/3d/VoiceCore3D";

type Message = { role: "munshi" | "amma" | "system"; text: string; decision?: string };

const QUICK_PHRASES = [
  { label: "बिजली का बिल (J1)", text: "बिजली का बिल भर दो" },
  { label: "पानी का बिल (J2 · Approval)", text: "पानी का बिल भर दो" },
  { label: "रामू को 5,000 भेज दे (J3)", text: "रामू को 5,000 भेज दे" },
  { label: "सिलेंडर खत्म (Sim)", text: "सिलेंडर खत्म हो गया" },
  { label: "दवाई मंगवा दो (Sim)", text: "दवाई मंगवा दो" },
  { label: "हाँ", text: "हाँ" },
  { label: "नहीं", text: "नहीं" },
];

const EASE = [0.4, 0, 0.2, 1] as const;

function MicIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3.5a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0v-5a3 3 0 0 1 3-3Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

const bubbleVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: EASE } },
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2 } },
};

export default function CallStage() {
  const [caller] = useState(PARENT_NUMBER);
  const [callId, setCallId] = useState<string | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(true);
  const [showDtmf, setShowDtmf] = useState(false);
  const [snapshot, setSnapshot] = useState<Bootstrap | null>(null);
  const [last, setLast] = useState<TurnResponse | null>(null);
  const [utterance, setUtterance] = useState("");
  const [ended, setEnded] = useState(false);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  const langFor = (lang?: string) => (lang === "en" ? "en-IN" : "hi-IN");

  const refresh = useCallback(async () => {
    try {
      const data = await api.bootstrap();
      setSnapshot(data);
    } catch {
      // Call continues even if snapshot fails
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onReset = () => {
      stopSpeaking();
      setCallId(null);
      setVerified(null);
      setMessages([]);
      setDraft("");
      setError(null);
      setLast(null);
      setUtterance("");
      setEnded(false);
      void refresh();
    };
    window.addEventListener("munshi:demo-reset", onReset);
    return () => window.removeEventListener("munshi:demo-reset", onReset);
  }, [refresh]);

  useEffect(() => {
    if (!callId) return;
    const timer = setInterval(() => void refresh(), 4000);
    return () => clearInterval(timer);
  }, [callId, refresh]);

  useEffect(() => {
    const node = transcriptRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, busy]);

  const send = useCallback(
    async (raw: string, silence = false) => {
      const text = raw.trim();
      if (!silence && !text) return;
      if (!callId) {
        setError("Pehle call shuru kijiye — upar 'Start call' dabaiye.");
        return;
      }
      setError(null);
      setBusy(true);
      if (!silence) setDraft("");
      setMessages((prev) => [
        ...prev,
        { role: silence ? "system" : "amma", text: silence ? "(Silence on the line)" : text },
      ]);
      try {
        const response = await api.turn(callId, silence ? "" : text, silence);
        setMessages((prev) => [
          ...prev,
          { role: "munshi", text: response.reply, decision: response.decision },
        ]);
        setLast(response);
        setUtterance(silence ? "(silence)" : text);
        speak(response.reply, voiceOn, langFor(response.lang));
        await refresh();
        if (response.done) {
          setEnded(true);
          setCallId(null);
          setMessages((prev) => [...prev, { role: "system", text: "Call band ho gayi." }]);
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Call fail ho gayi.");
      } finally {
        setBusy(false);
      }
    },
    [callId, refresh, voiceOn],
  );

  const sendDtmf = async (key: "1" | "2" | "*") => {
    if (!callId) return;
    setError(null);
    setBusy(true);
    setMessages((prev) => [...prev, { role: "system", text: `DTMF keypad pressed: [${key}]` }]);
    try {
      const response = await api.dtmf(callId, key);
      setMessages((prev) => [
        ...prev,
        { role: "munshi", text: response.reply, decision: response.decision },
      ]);
      setLast(response);
      setUtterance(`DTMF [${key}]`);
      speak(response.reply, voiceOn, langFor(response.lang));
      await refresh();
      if (response.done) {
        setEnded(true);
        setCallId(null);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "DTMF fail ho gaya.");
    } finally {
      setBusy(false);
    }
  };

  const { listening, supported, error: micError, start: startMic, stop: stopMic } = useRecognition(
    (text) => void send(text),
  );

  const startCall = async (number: string) => {
    setBusy(true);
    setError(null);
    setEnded(false);
    try {
      const response = await api.startCall(number);
      setCallId(response.call_id);
      setVerified(response.verified);
      setLast(null);
      setUtterance("");
      setMessages([{ role: "munshi", text: response.greeting }]);
      speak(response.greeting, voiceOn, "hi-IN");
      await refresh();
    } catch (exc) {
      setError(
        exc instanceof Error
          ? `${exc.message} — API chal rahi hai? (uvicorn apps/api/run.py)`
          : "API se baat nahi ho rahi.",
      );
      setCallId(null);
    } finally {
      setBusy(false);
    }
  };

  const endCall = async () => {
    if (!callId) return;
    setBusy(true);
    try {
      await api.endCall(callId);
      setMessages((prev) => [...prev, { role: "system", text: "Aapne call band kar di." }]);
    } catch {
      // ending is best-effort
    } finally {
      setCallId(null);
      setEnded(true);
      setBusy(false);
      stopSpeaking();
      void refresh();
    }
  };

  const decide = async (approval: Approval, decision: "approve" | "deny") => {
    setBusy(true);
    setError(null);
    try {
      await api.decide(approval.id, decision);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Approval fail ho gaya.");
    } finally {
      setBusy(false);
    }
  };

  const voiceDecide = async (approval: Approval, text: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.decideVoice(approval.id, text);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Awaaz samajh nahi aayi — 'haan' ya 'na' boliye.");
    } finally {
      setBusy(false);
    }
  };

  const unknownCall = () => void startCall("9000000000");

  const coreMode: VoiceCoreMode = useMemo(() => {
    if (listening) return "listening";
    if (snapshot?.limits.paused || last?.decision === "REJECT") return "blocked";
    if (last?.decision === "REQUIRE_CHILD_APPROVAL" || last?.decision === "ESCALATE_TO_CHILD") {
      return "approval";
    }
    if (last?.txn?.state === "AWAITING_READBACK") return "readback";
    if (callId) return "active";
    return "idle";
  }, [listening, snapshot?.limits.paused, last, callId]);

  return (
    <main className="page">
      {/* Editorial + 3D Spatial Hero Showcase */}
      <motion.section
        className="hero-showcase"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: EASE }}
      >
        <div
          className="hero-bg-photo"
          aria-hidden="true"
          style={{ backgroundImage: "url('/images/hero-bridge.jpg')" }}
        />
        <div className="hero-scrim" aria-hidden="true" />

        <div className="hero-content">
          <div className="hero-copy">
            <span className="eyebrow hero-eyebrow">Everyday access · sovereign voice bridge</span>
            <h1 className="display hero-display">
              Ek phone call. <em>Poora bharosa.</em>
            </h1>
            <p className="hero-lede">
              Amma gaon se apni bhasha mein phone karti hai. Munshi rakam biller se laata hai,
              zor se padhkar sunata hai, deterministic niyam check karta hai — aur Bengaluru mein
              Rohit ko turant voice note milta hai.
            </p>

            <div className="persona-bridge">
              <div className="persona-pill">
                <img
                  src="/images/amma-portrait.jpg"
                  alt="Kamla Devi (Amma)"
                  width={42}
                  height={42}
                  className="avatar-ring"
                />
                <div>
                  <strong>Kamla Devi · 68</strong>
                  <span>Feature phone · Zero app</span>
                </div>
              </div>
              <span className="bridge-arrow" aria-hidden="true">
                ← 800 km →
              </span>
              <div className="persona-pill">
                <img
                  src="/images/rohit-portrait.jpg"
                  alt="Rohit"
                  width={42}
                  height={42}
                  className="avatar-ring"
                />
                <div>
                  <strong>Rohit · Bengaluru</strong>
                  <span>Sets limits · Approves new payees</span>
                </div>
              </div>
            </div>

            <div className="hero-cta-row">
              {callId ? (
                <button className="btn btn-accent" onClick={endCall} disabled={busy}>
                  <PhoneOff size={16} aria-hidden="true" />
                  <span>End live call</span>
                </button>
              ) : (
                <button className="btn btn-accent" onClick={() => void startCall(caller)} disabled={busy}>
                  <Phone size={16} aria-hidden="true" />
                  <span>{ended ? "Nayi call shuru karein" : "Start Amma's call"}</span>
                </button>
              )}
              <Link className="btn hero-ghost-btn" href="/console">
                Open Family Console →
              </Link>
            </div>
          </div>

          <div className="hero-3d-slot">
            <VoiceCore3D mode={coreMode} />
          </div>
        </div>
      </motion.section>

      <motion.div
        className="stage-grid"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.55, ease: EASE }}
      >
        <section className="call-panel" aria-label="Live call">
          <div className="call-head">
            <div className="line-id">
              <img
                src="/images/amma-portrait.jpg"
                alt="Amma"
                width={32}
                height={32}
                className={`avatar-ring avatar-sm ${callId ? "avatar-live" : ""}`}
              />
              <span className={`dot ${callId ? "" : "off"}`} aria-hidden="true" />
              <span>Amma ki line</span>
              <span className="num">
                +91 ••••• 5678 {verified === false ? "· unverified" : ""}
              </span>
            </div>
            <div className="call-tools">
              <button
                type="button"
                className="btn"
                onClick={() => setShowDtmf((v) => !v)}
                aria-expanded={showDtmf}
                title="Feature phone DTMF keypad"
              >
                <Hash size={13} aria-hidden="true" />
                <span>Keypad</span>
              </button>
              <button
                type="button"
                className={`btn ${voiceOn ? "btn-accent" : ""}`}
                onClick={() => {
                  setVoiceOn((value) => !value);
                  if (voiceOn) stopSpeaking();
                }}
                aria-pressed={voiceOn}
                title="Browser ki awaaz on/off"
              >
                {voiceOn ? <Volume2 size={14} aria-hidden="true" /> : <VolumeX size={14} aria-hidden="true" />}
                <span>{voiceOn ? "Awaaz on" : "Awaaz off"}</span>
              </button>
              {callId ? (
                <button type="button" className="btn" onClick={endCall} disabled={busy}>
                  End call
                </button>
              ) : (
                <button type="button" className="btn btn-accent" onClick={() => void startCall(caller)} disabled={busy}>
                  {ended ? "Nayi call" : "Start call"}
                </button>
              )}
            </div>
          </div>

          <div className="transcript" ref={transcriptRef} aria-live="polite">
            {messages.length === 0 ? (
              <motion.div
                className="transcript-empty"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4 }}
              >
                <strong>Line khaali hai.</strong>
                &ldquo;Start call&rdquo; dabaiye. Amma ki jagah aap boliye ya likhiye — Munshi Hindi,
                Hinglish aur English samajhta hai.
              </motion.div>
            ) : (
              <AnimatePresence mode="popLayout">
                {messages.map((message, index) => (
                  <motion.div
                    key={`${message.role}-${index}`}
                    className={`bubble ${message.role}`}
                    variants={bubbleVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    layout
                  >
                    <span className="who">
                      {message.role === "munshi" ? "Munshi" : message.role === "amma" ? "Amma" : "System"}
                    </span>
                    {message.text}
                    {message.decision ? (
                      <span className="decision">niyam · {message.decision.replaceAll("_", " ")}</span>
                    ) : null}
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            {busy ? (
              <motion.div
                className="bubble system"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.25 }}
              >
                <span className="who">System</span>
                Munshi soch raha hai…
              </motion.div>
            ) : null}
          </div>

          <AnimatePresence>
            {showDtmf ? (
              <motion.div
                className="dtmf-bar"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <span className="mono">DTMF fallback:</span>
                <button type="button" className="chip" disabled={!callId || busy} onClick={() => void sendDtmf("1")}>
                  1 · Haan
                </button>
                <button type="button" className="chip" disabled={!callId || busy} onClick={() => void sendDtmf("2")}>
                  2 · Nahi
                </button>
                <button type="button" className="chip" disabled={!callId || busy} onClick={() => void sendDtmf("*")}>
                  * · Phir bolo
                </button>
                <button type="button" className="chip" disabled={!callId || busy} onClick={() => void send("", true)}>
                  <PauseCircle size={12} aria-hidden="true" /> Silence
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              void send(draft);
            }}
          >
            <label className="visually-hidden" htmlFor="utterance">
              Amma ki baat
            </label>
            <input
              id="utterance"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={callId ? "Amma ki baat likhiye…" : "Pehle call shuru kijiye"}
              autoComplete="off"
              disabled={!callId || busy}
            />
            <button
              type="button"
              className={`mic ${listening ? "listening" : ""}`}
              onClick={() => (listening ? stopMic() : startMic())}
              disabled={!callId || !supported || busy}
              aria-label={listening ? "Sunna band kijiye" : "Bolna shuru kijiye"}
              title={supported ? "Bolkar bhejiye (Chrome)" : "Speech recognition is browser mein nahi hai"}
            >
              <MicIcon />
            </button>
            <button className="send" type="submit" disabled={!callId || busy || !draft.trim()}>
              Bhejiye →
            </button>
          </form>

          <div className="chips" aria-label="Quick phrases">
            {QUICK_PHRASES.map((phrase) => (
              <button
                key={phrase.label}
                type="button"
                className="chip"
                disabled={!callId || busy}
                onClick={() => void send(phrase.text)}
              >
                {phrase.label}
              </button>
            ))}
            {!callId ? (
              <button type="button" className="chip" onClick={unknownCall} disabled={busy}>
                Anjaan number se call (J7)
              </button>
            ) : null}
          </div>

          {micError ? <p className="call-error">{micError}</p> : null}
          {error ? <p className="call-error">{error}</p> : null}

          <p className="trust-note">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>
              <b>Rakam hamesha biller se.</b> Amma sirf kaam bolti hai; 5,000 ko 50,000 sunne ka
              risk hi nahi. Har payment se pehle read-back, aur naya payee ho to Rohit ki haan.
            </span>
          </p>
        </section>

        <aside className="side">
          <ChildPhone
            snapshot={snapshot}
            busy={busy}
            voiceOn={voiceOn}
            onDecide={(approval, decision) => void decide(approval, decision)}
            onVoiceDecision={(approval, text) => void voiceDecide(approval, text)}
          />
          <p className="empty-note">
            Rohit ka phone simulator hai. Voice note sunne ke liye note dabaiye.{" "}
            <Link href="/console">Family console</Link> mein limits aur khata poora dikhta hai.
          </p>
        </aside>
      </motion.div>

      <PipelineStrip trace={last?.trace ?? null} utterance={utterance} decision={last?.decision} />

      <div className="stage-head" style={{ marginTop: "1.4rem" }}>
        <p className="lede">
          Pichhli call par agar confirmation adhoora reh gaya, agli call seedha usi read-back se
          shuru hoti hai — bina dobara poochhe, bina double payment.
        </p>
        <p className="mono muted" style={{ fontSize: "0.72rem" }}>
          {snapshot ? `Aaj ka kharcha ${rupees(snapshot.spend.today_paise)}` : "Khata load ho raha hai…"}{" "}
          · <Link href="/trace">Under the hood →</Link>
        </p>
      </div>
    </main>
  );
}
