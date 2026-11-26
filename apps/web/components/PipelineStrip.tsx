"use client";

import { motion } from "framer-motion";
import type { TurnResponse } from "@/lib/api";
import { rupees } from "@/lib/api";

const INTENT_LABEL: Record<string, string> = {
  pay_bill: "bill payment",
  book_gas_cylinder: "gas cylinder",
  refill_medicine: "medicine",
  message_child: "message",
  affirm: "haan",
  deny: "nahi",
  repeat: "repeat",
  help: "help",
  pause: "pause",
  unsupported_transfer: "transfer (refused)",
  unclear: "unclear",
};

const EASE = [0.4, 0, 0.2, 1] as const;

const nodeVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: EASE },
  }),
};

export default function PipelineStrip({
  trace,
  utterance,
  decision,
}: {
  trace: TurnResponse["trace"] | null;
  utterance: string;
  decision?: string;
}) {
  const proposal = trace?.proposal;
  const policy = trace?.policy;
  const resolved = trace?.resolved;
  const execution = trace?.execution;
  const stageMs = trace?.stages?.find((stage) => stage.stage === "understand")?.ms;
  const amountPaise = resolved?.amount_paise ?? execution?.amount_paise;
  const amount = amountPaise != null ? rupees(amountPaise) : "—";
  const mode = trace?.mode?.payments ?? "—";
  const doneSomething = Boolean(resolved || execution);

  const nodes = [
    {
      num: "01",
      title: "Awaaz",
      status: utterance ? "live" : "idle",
      value: utterance || "Bol kar ya likh kar bhejiye",
      meta: "browser ASR",
      on: Boolean(utterance),
    },
    {
      num: "02",
      title: "Samajh",
      status: stageMs != null ? `${stageMs}ms` : "—",
      value: proposal
        ? `${INTENT_LABEL[proposal.intent] ?? proposal.intent} · ${Math.round(proposal.confidence * 100)}%`
        : "Intaazaar",
      meta: "JSON schema locked",
      on: Boolean(proposal),
    },
    {
      num: "03",
      title: "Niyam",
      status: decision ?? "—",
      value: policy ? policy.rule : execution ? "Read-back confirmed" : "Policy engine baad mein",
      meta: "deterministic",
      on: Boolean(policy || execution),
    },
    {
      num: "04",
      title: "Kaam",
      status: mode,
      value: amount,
      meta: execution
        ? `executed · ${execution.state.toLowerCase()}`
        : resolved
          ? "amount from biller"
          : "no amount spoken",
      on: doneSomething,
    },
    {
      num: "05",
      title: "Beta",
      status: "voice note",
      value: doneSomething ? "Rohit ko soochna" : "Kuch bheja nahi",
      meta: trace?.degraded ? "degraded" : "simulator",
      on: doneSomething,
    },
  ];

  return (
    <section className="pipeline" aria-label="How this turn was handled">
      {nodes.map((node, i) => (
        <motion.div
          key={node.num}
          className={`pipe-node ${node.on ? "on" : ""}`}
          custom={i}
          variants={nodeVariants}
          initial="hidden"
          animate="visible"
        >
          <div className="k">
            <span>
              {node.num} · {node.title}
            </span>
            <span>{node.status}</span>
          </div>
          <div className="v">{node.value}</div>
          <div className="m">{node.meta}</div>
        </motion.div>
      ))}
    </section>
  );
}
