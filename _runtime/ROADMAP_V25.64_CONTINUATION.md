# HMS AI Cockpit — Continuation after v25.64

## Current frozen milestone
**v25.64 — Live Windows Recovery Observer Bridge & Real Codex Effect Crash Certification**

Delivered and frozen at control-plane/harness level:
- secret-safe Windows recovery observer bridge contract;
- fail-closed digest-only keyring observer boundary;
- five-gate, disarmed-by-default real-effect certification harness;
- external idempotency witness before effect replay;
- target recovery evidence classes and metadata-only evidence bundle;
- v25.64 startup mutation-gate integration, GUI preflight and privacy-safe diagnostics;
- public BackendAction set remains exactly 90.

No REAL_CODEX_EFFECT target execution is claimed by this milestone.

## Next milestone — v25.65
**Windows Target Adapter Pack & Attested Evidence Promotion Gate**

### P0 — Audited Windows target adapters
- Implement concrete target-Windows adapters for Official Auth file/keyring/auto fingerprinting, controlled Codex restart generation, router generation and LAN lease epoch/owner digest.
- Keyring adapter must expose digest/generation metadata only through an explicit helper contract; no raw token/secret/account identity may cross the boundary.
- Real-effect apply/probe adapters must support idempotency witness and exact readback verification.
- Distribution remains DISARMED by default; real effects require explicit target-machine operator arming.

### P0 — Target evidence attestation / anti-replay
- Add per-run nonce/run_id, package/source manifest digest, monotonic event sequence and evidence bundle hash-chain.
- Bind evidence to pseudonymous target-machine/runtime fingerprints without exposing hostname/user/account.
- Reject stale, replayed, mixed-version or partial target evidence.

### P0 — Production-score promotion gate
- Add a separate auditor that may promote only evidence with WINDOWS_TARGET_OBSERVER or REAL_CODEX_EFFECT class, current package hash, complete crash matrix and target-machine validity.
- Lab/synthetic/control-plane evidence must remain permanently ineligible for production-score promotion.
- A failed/partial target run must never lower safety gates to obtain a score.

### P1 — Vietnamese recovery operator timeline
- Show PREPARE / OBSERVE / EFFECT / DURABLE / VERIFY / DONE / OPERATOR_REQUIRED as a Vietnamese timeline.
- Include source/freshness, safe fingerprint prefix and exact remediation reason; never expose credential/account identity.
- Export the same metadata-only timeline to support diagnostics.

## Production gate remains unchanged
Do not call HMS AI Cockpit production-certified or a production superset until verified real Windows/Codex effects, live Free/Plus/Pro quota fidelity, real multi-account rotation, LAN/NAS failover and required 6h/24h soak evidence pass.
