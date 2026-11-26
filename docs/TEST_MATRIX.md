# Test matrix

Status uses three words only: **covered** (automated and passing), **partial**
(some behaviours covered, not the whole ID), or **not run** (no automated check).

Last full run: `.venv/Scripts/python -m pytest` → **78 passed**; `apps/web` Playwright E2E + Axe (`npm run e2e`) → **passed** (`J1`–`J7`, `F-01`–`F-07`).

| ID | What it checks | Status | Where |
|---|---|---|---|
| P-01 | All checks pass → AUTO_EXECUTE | covered | `tests/test_policy.py` |
| P-02 | Per-txn cap boundary ±1 paisa | covered | `tests/test_policy.py` |
| P-03 | Hard ceiling boundary, +1 rejects | covered | `tests/test_policy.py` |
| P-04 | New payee at any amount → child | covered | `tests/test_policy.py` |
| P-05 | Daily cap boundary | covered | `tests/test_policy.py` |
| P-06 | Monthly cap boundary | covered | `tests/test_policy.py` |
| P-06b | Month rollover at 00:00 IST | covered | `tests/test_rollover.py` |
| P-07 | Paused rejects everything | covered | `tests/test_policy.py` |
| P-08 | Capability disabled | covered | `tests/test_policy.py` |
| P-09 | Unverified caller, no transaction | covered | `tests/test_policy.py`, `tests/test_api.py` |
| P-10 | Confidence below / at / above | covered | `tests/test_policy.py` |
| P-11 | Rule order and reason code | covered | `tests/test_policy.py` |
| P-12 | Property: no auto when a hard rule fails | covered | `tests/test_policy.py` (Hypothesis) |
| P-13 | Property: policy is pure | covered | `tests/test_policy.py` |
| M-01 | Integer paise only; floats/bools rejected | covered | `tests/test_money.py` |
| M-02 | Indian grouping + Hindi/English read-back edges | covered | `tests/test_money.py` |
| M-03 | Amount changes before execute voids confirmation | covered | `tests/test_money.py` |
| M-04 | Amount never sourced from speech | covered | `tests/test_money.py` |
| M-05 | Idempotent execution | covered | `tests/test_money.py` |
| M-06 | Concurrent duplicate charges once | covered | `tests/test_money.py` |
| S-01 | Legal transitions pass, illegal raise | covered | `tests/test_state_machine.py` |
| S-02 | Terminal immutable | covered | `tests/test_state_machine.py` |
| S-03 | Approval timeout expires, parent told | covered | `tests/test_state_machine.py` |
| S-04 | Late approval rejected | covered | `tests/test_state_machine.py` |
| S-05 | Child denies → cancelled | covered | `tests/test_state_machine.py` |
| S-06 | Pause cancels non-terminal atomically | covered | `tests/test_state_machine.py` |
| S-07 | Non-child identity rejected | covered | `tests/test_state_machine.py`, `tests/test_security.py` |
| N-01 | ≥15 labelled utterances per intent | covered | `tests/test_nlu.py` (150 total) |
| N-02 | Transfer recall | covered | `tests/test_nlu.py` (1.00) |
| N-03 | Adversarial never auto-executes | covered | `tests/test_nlu.py` |
| N-04 | Schema violation → unclear | covered | `tests/test_nlu.py` |
| N-05 | Unknown capability discarded | covered | `tests/test_nlu.py` |
| N-06 | Language switching recorded | covered | `tests/test_nlu.py` |
| N-07 | Golden baseline accuracy | covered | `tests/test_nlu.py` (100% authored set) |
| C-01 | J1 happy path, one txn/note | covered | `tests/test_conversation.py` |
| C-02 | J2 approve and deny | covered | `tests/test_conversation.py` |
| C-03 | J3 unsupported transfer | covered | `tests/test_conversation.py` |
| C-04 | J4 clarify twice then escalate | covered | `tests/test_conversation.py` |
| C-05 | Silence re-prompt then close | covered | `tests/test_conversation.py` |
| C-06 | Barge-in repeat safe | covered | `tests/test_conversation.py` |
| C-07 | Cancel at read-back | covered | `tests/test_conversation.py` |
| C-08 | Dropped call recoverable | covered | `tests/test_conversation.py` |
| C-09 | Max-turn close | covered | `tests/test_conversation.py` |
| C-10 | Overlapping calls, single execution | covered | `tests/test_conversation.py` |
| A-01 | Fake adapter contracts | covered | `tests/test_adapters.py` |
| A-02 | Timeout/5xx degradation | covered | `tests/test_adapters.py` |
| A-03 | Webhook signature + replay | covered | `tests/test_adapters.py` |
| A-04 | Provider failure after read-back | covered | `tests/test_adapters.py` |
| X-01 | Limits cannot change from call path | covered | `tests/test_security.py` |
| X-02 | IDOR across families | covered | `tests/test_security.py` |
| X-03 | Unknown-caller alert rate limit | covered | `tests/test_security.py` |
| X-04 | No PII/secrets in logs | covered | `tests/test_security.py` |
| X-05 | Audit tamper detection | covered | `tests/test_security.py` |
| X-06 | JSON endpoint fuzzing | covered | `tests/test_security.py` (Hypothesis) |
| X-07 | `npm audit` / `pip check` | **partial** | `npm audit --audit-level=high` (0 vulnerabilities) and `pip check` (no broken requirements) run; `pip-audit` not installed |
| O-01 | 5,000 vs 50,000 parsing | covered | `tests/test_onboarding.py` |
| O-02 | Read-back + explicit confirm required | covered | `tests/test_onboarding.py` |
| O-03 | Contradictory limits clarify | covered | `tests/test_onboarding.py` |
| O-04 | Increase needs second factor | covered | `tests/test_onboarding.py` |
| O-05 | Decrease needs no second factor | covered | `tests/test_onboarding.py` |
| R-01 | Stage latency recorded, p50/p95 | covered | `tests/test_nonfunctional.py`, `scripts/measure_latency.py` |
| R-02 | 200-call soak, no state leak | covered | `tests/test_nonfunctional.py` |
| R-03 | Chaos adapter failure + recovery | covered | `tests/test_nonfunctional.py` |
| R-04 | Reset idempotent, < 5s | covered | `tests/test_nonfunctional.py` |
| R-05 | Repo has a fresh-clone path | **partial** | files + README asserted; not run from a clean machine |
| F-01 | J1–J7 through the browser | **covered** | `apps/web/tests/e2e.mjs` (J1, J2, J3, J5, J6, J7 + DTMF + Reset) |
| F-02 | Child approval updates console live | **covered** | `apps/web/tests/e2e.mjs` + API tests |
| F-03 | Pause immediate everywhere | **covered** | `apps/web/tests/e2e.mjs` (switch blocks parent call immediately) |
| F-04 | LIVE/SANDBOX/SIMULATED badges | **covered** | `apps/web/tests/e2e.mjs` (footer + ledger mode stamps asserted) |
| F-05 | Trace shows the fired rule | **covered** | `apps/web/tests/e2e.mjs` (`P-NEW-PAYEE` + `audit valid` asserted) |
| F-06 | axe / keyboard-only / contrast | **partial** | `@axe-core/playwright` WCAG 2A+2AA + contrast passes across `/`, `/console`, `/trace`; full keyboard-only script manual |
| F-07 | 360px–desktop responsive | **covered** | `apps/web/tests/e2e.mjs` asserts zero horizontal overflow at `360px` and `1440px` across all 3 routes |
| F-08 | Empty/loading/error states | **partial** | implemented and reset flow tested; offline fallback visual state manual |
| F-09 | Visual regression snapshots | **not run** | manual screenshot inspection done; automated pixel-diff baseline not configured |
| F-10 | Lighthouse budgets | **not run** | — |
| D-01 | 10× demo rehearsal | **not run** | manual |
| D-02 | Real-device 5× | **not run** | no telephony |
| D-03 | Offline fallback video | **not run** | manual |
| D-04 | Stranger completes J1 from README | **not run** | manual |

## Known gaps

- Automated visual diff snapshots (`F-09`), Lighthouse budgets (`F-10`), and `pip-audit` (`X-07`).
- Mutation testing (`mutmut`) on the Policy Engine.
- Docker build/run execution and a genuinely fresh-clone verification on a second machine.
- Dialect ASR accuracy (`EVAL.md`) and real telephony / WhatsApp / Cashfree credentials.

These are gaps, not passes. The product surfaces the corresponding honesty labels.
