# Evaluation — measured, not claimed

All numbers below were produced on this machine on 2026-11-25 with the commands
shown. Anything not measured is marked **not measured**, not estimated.

## NLU intent evaluation

Command: `.venv/Scripts/python -m pytest tests/test_nlu.py -q` and the dataset in
`fixtures/utterances.json`.

| Metric | Result |
|---|---|
| Labelled utterances | 150 (10 intents × 15) |
| Overall intent accuracy | **150 / 150 = 100%** |
| `unsupported_transfer` recall | **1.00** (15/15) |
| Per-intent recall (all 10 intents) | **1.00** |
| Languages represented | Hindi (Devanagari), roman Hindi/Hinglish, English |

Per intent: `pay_bill`, `book_gas_cylinder`, `refill_medicine`, `message_child`,
`affirm`, `deny`, `repeat`, `help`, `unsupported_transfer`, `unclear` — 15/15 each.

**How to read this honestly:** the dataset was authored together with the
deterministic parser, so 100% measures *coverage of the intended command set*, not
open-world generalisation. It is a regression baseline (N-07), not a claim that the
system understands every speaker. There is no independent or dialect corpus yet.

## Adversarial checks

Covered by `tests/test_nlu.py::test_n03_adversarial_never_auto_executes`: prompt
injection phrases, “limit badha do”, and transfer requests never produced
`AUTO_EXECUTE`, created no transaction and charged nothing.

## ASR / dialect accuracy

**Not measured.** There is no 40-utterance audio benchmark, no WER table and no
Haryanvi corpus. The demo uses Chrome’s Hindi speech recognition; its error rate on
elderly, noisy, phone-quality or Haryanvi speech is unknown. Do not claim otherwise
in the pitch.

## Latency

Command: `python scripts/measure_latency.py` (50 calls, in-process, SQLite,
deterministic fakes; each sample includes understanding, policy, resolve, read-back,
confirmation, execution, notification and audit writes).

| Metric | Result |
|---|---|
| Full read-back + confirmation pair, p50 | **4.02 ms** |
| Same, p95 | **7.28 ms** |
| `make reset-demo` equivalent (`db.reset`), p50 | **0.39 ms** |
| Reset max | **0.63 ms** |
| Audit chain after run | valid |

**Scope caveat:** this is backend compute only. It excludes microphone capture,
browser ASR, network and speech synthesis. A real conversation’s perceived latency
depends on those, and has not been measured over a phone network.

## Cost per call

**Not measured / not applicable.** No paid adapter is enabled, so there is no
vendor token or audio cost to report. No price is invented.

## Test suite

Command: `.venv/Scripts/python -m pytest`.

| Metric | Result |
|---|---|
| Tests | **78 passed** |
| Policy engine | table-driven + Hypothesis properties (200/100 examples) |
| Money | integer paise, grouping, revalidation, concurrency |
| NLU | 150-utterance eval + adversarial + schema guard |
| Journeys | C-01…C-10 |
| Security | IDOR, limit-path abuse, rate limit, PII, audit tamper, fuzz |
| Ops | 200-call soak, latency, chaos, reset |
| Browser E2E | **passed** — J1–J7, DTMF, pause, axe WCAG 2A/2AA, 360px overflow |

Playwright + axe pass (`npm run e2e`); `npm audit --audit-level=high` reports 0
vulnerabilities and `pip check` is clean. Not run: visual regression snapshots,
Lighthouse budgets, `pip-audit`, mutation testing. See `TEST_MATRIX.md`.

## Measurements needed before a live pilot

- Witheld-speaker and dialect intent accuracy, and ASR WER on recorded audio.
- True end-to-end perceptual latency (mic → reply audio) on a mid-range Android.
- Cost per call once a real ASR/TTS/telephony adapter is selected, citing vendor
  pricing with a date.
- Completion rate and error rate for first-time elderly users in a moderated test.
