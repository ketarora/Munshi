# Decisions

Every entry records what was chosen, why, and what it costs. Where a claim could
not be verified, the build stays behind an adapter instead of guessing.

## D-01 — Deterministic rule NLU is the default; the LLM is optional

**Decision:** `RuleUnderstanding` is the live path. `AnthropicUnderstanding` exists
but raises `NotConfigured` without a key and model id.
**Why:** the demo must run with zero accounts; intent extraction must be testable;
no model ids or pricing are invented. The schema guard accepts either adapter.
**Cost:** the rule parser is narrower than an LLM. The 150-utterance eval measures
the authored set, not open-world generalisation.

## D-02 — Payments use MockLedger; no Cashfree integration

**Decision:** `MockLedger` with idempotency and failure injection; `CashfreePayments`
is a stub.
**Why:** public reporting says agent wallets currently support bill payments only and
does not establish hackathon access; Cashfree is not a sponsor. The core must not
depend on an unverified contract.
**Cost:** no real money demo. Every surface says SANDBOX/SIMULATED.

## D-03 — Browser speech is the voice layer

**Decision:** Web Speech API for ASR and `speechSynthesis` for TTS in Chrome; server
ASR/TTS adapters are stubs.
**Why:** genuinely live voice with no credentials, and the demo runs on the machine.
**Cost:** Chrome-dependent; no measured Haryanvi accuracy; no telephony. Dialect
accuracy must be measured before any claim.

## D-04 — SQLite, not Postgres

**Decision:** one SQLite connection behind a lock, repository methods on `Database`.
**Why:** zero setup, fast tests, deterministic fixtures; well inside demo load.
**Cost:** not a multi-tenant production datastore. Repository boundaries keep a
Postgres swap contained.

## D-05 — Next.js App Router, Tailwind v4 tokens, Three.js 3D & Framer Motion

**Decision:** Next 16 + React 19, custom design tokens in `globals.css` with Tailwind v4,
interactive React Three Fiber 3D scenes (`VoiceCore3D`, `BudgetVault3D`, `AuditChain3D`,
`SpatialAtmosphere3D`), Framer Motion transitions, and bespoke editorial imagery.
**Why:** the brief asks for a distinctive, current, classy surface with spatial 3D depth
and editorial craft rather than a default component-library template. All 3D scenes use
self-contained procedural lighting behind a `WebGLGuard` boundary and respect
`prefers-reduced-motion`.
**Cost:** requires WebGL for 3D enhancement (falls back cleanly to static accessible UI).

## D-06 — Money amounts are never taken from speech

**Decision:** `pay_bill` resolves the amount from the biller; its slots schema has
only `biller`. The same rule applies to gas and medicine (catalog price).
**Why:** “5,000 heard as 50,000” is the obvious judge attack. Removing the numeric
slot removes the class of bug.
**Cost:** the parent cannot pay an arbitrary amount. That is intended for this product.

## D-07 — Duplicate guard is scoped to one call, 60 seconds

**Decision:** `_recent_duplicate` checks successful transactions in the same call
within a short window.
**Why:** replaying a confirmation must not double-pay, but a second medicine order
next week (or a second call today) is legitimate. Cross-call duplicate suppression
broke real usage.
**Cost:** the same request repeated in separate calls is allowed; caps and approvals
still apply.

## D-08 — Approvals expire, never auto-approve

**Decision:** default TTL 900s, configurable. Expiry writes EXPIRED, notifies the
parent truthfully, never executes.
**Why:** silence is not consent. A late approval after expiry is rejected with a
clear message.

## D-09 — Identity = registered phone hash, not voice biometrics

**Decision:** caller verification by hashed number; no voiceprint claim. Unknown
callers get a refusal and a rate-limited audit event.
**Why:** voice anti-spoofing is not something to hand-wave in a hackathon.
**Cost:** SIM-swap or shared handsets are out of scope; documented.

## D-10 — Simulated capabilities use fixed synthetic prices

**Decision:** gas ₹1,100; medicine catalog ₹380–₹640.
**Why:** deterministic tests and honest demos. No market price is presented as real.
**Cost:** not a live LPG/pharmacy flow.

## D-11 — Demo child auth is a fixed token

**Decision:** `X-Munshi-Token` maps to a seeded family; the browser reads
`NEXT_PUBLIC_MUNSHI_TOKEN`.
**Why:** the console must be testable without an identity provider.
**Cost:** NOT production auth. A public build would leak the token; documented in
LIMITATIONS and in the code.

## D-12 — Browser E2E and Axe accessibility run via Playwright + Edge

**Decision:** ship `apps/web/tests/e2e.mjs` covering J1–J7, DTMF, Reset Demo,
`@axe-core/playwright` WCAG 2A/2AA contrast checks across `/`, `/console`, and `/trace`,
and 360px/1440px responsive overflow assertions.
**Why:** catches real CSS contrast, focus, and end-to-end integration bugs across
backend and frontend before demo day.
**Cost:** visual pixel-diff snapshots (`F-09`) and Lighthouse budgets (`F-10`) remain
manual/unrun in this pass; listed in `TEST_MATRIX.md`.

## D-13 — No claim of Cashfree access, invite status, or ASR accuracy

**Decision:** all three are marked unverified; the demo does not build on them.
**Why:** the team’s critique was correct; unverified claims are a judging risk.
