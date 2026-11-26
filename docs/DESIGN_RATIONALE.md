# Design rationale — Munshi

*Updated after upgrading the UI to the Sovereign Acoustic Ledger spatial system.*

## The concept: a family khata in spatial space

Munshi is a phone call between a parent and a trusted clerk, with a ledger the child can
audit. The interface pairs **Indian bahi-khata editorial craft** (ruled parchment,
vermilion stamp ink, dotted leader rows, monospace rupees, museum-grade still-life
imagery) with **live 3D WebGL instrumentation** (Three.js / React Three Fiber) that makes
the safety boundary tangible rather than decorative:

1. **Spatial Voice Bridge (`VoiceCore3D`)** — links Amma's village node and Rohit's
   Bengaluru node across a reactive acoustic wave ribbon. Locks a golden halo during
   read-back and contracts in crimson when blocked or paused.
2. **Editorial Photography (`public/images/`)** — bespoke art-directed scenes
   (`hero-bridge.jpg`, `amma-portrait.jpg`, `rohit-portrait.jpg`, `vault-seal.jpg`)
   anchoring real human stakes with zero cheesy stock clichés.
3. **3D Khata Vault Dial (`BudgetVault3D`)** — tactile brass dial on the Family Console
   showing remaining monthly budget and locking when paused.
4. **3D SHA-256 Audit Helix (`AuditChain3D`)** — interactive chain of ledger blocks in
   Judge Mode reflecting real database verification state.

**Point of view:** dignity, not cuteness. Warm paper, obsidian dark rooms, high-contrast
typography, and honest mode stamps on every surface.

## Type

- **Fraunces** (display serif): headings, hero rupee amounts, editorial warmth.
- **Noto Serif Devanagari**: "मुंशी" wordmark with crisp Devanagari shaping.
- **Inter**: crisp UI labels and controls.
- **IBM Plex Mono**: rupee amounts, rule codes, SHA hashes, stage latencies.

## Colour system (semantic tokens)

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--color-parchment` | `#f5efe2` | `#0f1218` | canvas |
| `--color-panel` | `#fbf7ec` | `#171b24` | ledger surface |
| `--color-ink` | `#15171c` | `#f1e9d9` | primary text |
| `--color-vermilion` | `#c8452b` | `#e2603f` | stamp ink, active line, alert |
| `--color-gold` | `#a97f35` | `#d3a75a` | brass hardware, sandbox caution |
| `--color-green` | `#3f6b4f` | `#84b596` | verified, settled |
| `--color-indigo` | `#26344f` | `#a5b6d9` | structural secondary / simulated |

## Three things deliberately avoided

1. **No generic purple/cyan AI SaaS gradients or meaningless floating blobs.**
2. **No fake metrics, sparkle icons, or unverified claims.**
3. **No WebGL dependencies on external HDR CDNs or fragile GPU assumptions** —
   everything uses self-contained procedural lighting inside a `WebGLGuard` boundary
   with `prefers-reduced-motion` support and accessible fallbacks.
