# HMS AI Cockpit — Continuation after v25.63

## Current frozen milestone
**v25.63 — Startup Recovery Reconciler & Target-Machine Crash Injection Harness**

Delivered and frozen:
- cold-start recovery journal discovery and hash-chain validation;
- read-only/digest-only auth/process/router/LAN observers;
- fail-closed startup mutation gate for direct backend and private Official Auth switch paths;
- real subprocess kill + cold-start lab recovery harness;
- 12 crash scenarios with at-most-once lab side effects;
- startup recovery operator UI and aggregate-only diagnostics;
- public BackendAction set remains exactly 90.

## Next milestone — v25.64
**Live Windows Recovery Observer Bridge & Real Codex Effect Crash Certification**

### P0 — Windows observer bridge
- Add target-Windows adapters that obtain safe state fingerprints for Codex file/keyring/auto auth storage without exposing credential material.
- Capture Codex process identity/restart generation from Windows process APIs with secret-safe filtering.
- Observe live router generation and LAN lease owner/epoch from the actual runtime stores.
- Every observer must declare evidence class, freshness and failure reason; unavailable proof fails closed.

### P0 — Armed real-effect crash harness
- Extend the crash harness with a separately armed target-machine mode for real Official Auth switch, controlled Codex restart, router transition and LAN lease handoff.
- Never arm this mode by default; require explicit operator action on the target Windows machine.
- Inject termination around PREPARE/EFFECT/DURABLE/VERIFY boundaries and cold-start the real Cockpit recovery path.
- Prove no duplicate auth rewrite/restart/router transition/lease handoff and preserve operator changes.

### P0 — Evidence ingestion / certification boundary
- Produce signed-or-hashed target-machine evidence bundles with host/runtime identity redacted to non-sensitive fingerprints.
- Distinguish LAB_PROCESS_KILL, WINDOWS_TARGET_OBSERVER and REAL_CODEX_EFFECT evidence classes.
- Production score may change only from verified target-machine evidence, never from synthetic fixtures.

### P1 — Recovery operator timeline
- Add Vietnamese recovery timeline with state class, safe fingerprint, observed source/freshness and exact remediation reason.
- Provide exportable metadata-only recovery evidence for support/diagnostics.

## Production gate remains unchanged
Do not call HMS AI Cockpit production-certified or a production superset until real Windows/Codex, live Free/Plus/Pro quota fidelity, multi-account rotation, LAN/NAS failover and required 6h/24h soak evidence pass.
