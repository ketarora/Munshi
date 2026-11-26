# Limitations

This file is intentionally blunt. Do not remove warnings from the UI or pitch.

## Money and integrations

- **No real money moves.** Bill payment runs on `MockLedger`, labelled SANDBOX in
  every surface. Cashfree is not integrated: access terms and the current MCP/wallet
  contract were not verified, and Cashfree is not a hackathon sponsor.
- **Gas and medicine are simulated.** Fixed synthetic prices, no LPG distributor, no
  pharmacy. They exist to show the capability-plugin pattern, not fulfilment.
- **No telephony.** There is no inbound phone number, no live call interception, and
  no promise of call blocking. The demo uses a browser call simulator.
- **No WhatsApp or Telegram.** Adapters are stubs; the child device is a simulator.
  WhatsApp Business API needs business verification and templates that were not done.

## Voice

- Browser speech recognition depends on Chrome and its network service. It is LIVE
  in the sense that no mock is used, but it is not a benchmarked ASR vendor.
- **Haryanvi / regional dialect accuracy is unmeasured.** The 150-utterance NLU set is
  authored and synthetic. It shows the intent layer is testable and that no transfer
  request slips on that set; it is not a dialect WER study.
- TTS voice quality depends on the operating system’s installed Hindi voice.
- There are no voice biometrics. Identity is the registered phone number hash.

## Security and auth

- The family console uses a **demo child token** supplied to the browser
  (`NEXT_PUBLIC_MUNSHI_TOKEN`). It is not production authentication and would need to
  be replaced by real sessions/OTP before any public deployment.
- Rate limiting for unknown callers is in-memory per process, not distributed.
- Webhook HMAC uses a demo secret from configuration. Rotate and store it properly
  before real use.
- No independent penetration test has been run. Tests cover IDOR, limit-path abuse,
  audit tampering, fuzzed JSON and PII scrubbing, but that is not a security audit.

## Verification gaps

- Automated visual-diff snapshots (`F-09`), Lighthouse audits (`F-10`), `pip-audit` and
  mutation testing were **not executed**. (Playwright E2E for J1–J7, `@axe-core/playwright`
  WCAG 2A/2AA checks, 360px responsive checks, and `npm audit --audit-level=high` pass.)
- Docker Compose configuration is provided but was **not built or run** in this
  environment; the documented local path is the verified one.
- The 10× demo rehearsal (D-01) and fresh-clone test (R-05) have not been performed
  by a second person.
- Latency is measured in-process (see EVAL.md), not over a real phone network.

## Legal / policy

- Call recording disclosure is configurable and on by default in the demo copy.
- No legal conclusion about Indian data-protection obligations is made here. Review
  consent, retention and disclosures before any real deployment.
- The product does not give medical advice; medicine refill means reordering an item
  the family already set up.

## Cost

- No vendor pricing is claimed or estimated. With zero paid adapters, cost per call is
  the local compute cost only, which is not a useful production number.
