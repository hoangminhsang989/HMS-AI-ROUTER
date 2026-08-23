# HMS AI Cockpit — Continuation after v25.62

## Current frozen milestone
**v25.62 — Recovery Transaction Replay & Multi-Subsystem Crash Consistency**

Delivered and frozen:
- cross-subsystem transaction/effect identity;
- idempotency keys and at-most-once durable side-effect invariant;
- external-state verification before replay;
- compensation DAG with ownership proof;
- 30-case crash/concurrent-change matrix;
- Recovery Replay operator proof UI;
- metadata-only Unified Diagnostics / diagnostics bundle integration;
- public BackendAction set remains 90.

## Next milestone — v25.63
**Startup Recovery Reconciler & Target-Machine Crash Injection Harness**

### P0 — Startup reconciler
- Discover unresolved v25.60/v25.62 journals before any new mutating operator action.
- Correlate journal intent/effect fingerprints with observable auth/process/router/LAN state.
- Block new conflicting mutation while an unresolved transaction is OPERATOR_REQUIRED.

### P0 — Real effect observers
- Read-only observer adapters for auth store file/keyring/auto, Codex process identity/restart generation, router active generation and LAN lease owner/epoch.
- No observer may expose raw credentials to journal or diagnostics.

### P0 — Target-machine crash injection harness
- Windows subprocess kill/crash points around auth write, controlled restart, router transition and lease handoff.
- Cold-start replay after process termination, not merely in-process exceptions.
- Evidence must prove at-most-once side effects and safe convergence on the target PC.

### P1 — Operator recovery UX
- Startup banner for HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED.
- Vietnamese evidence timeline with effect fingerprint, observed state class and required action; no secret values.

## Production gate remains unchanged
Do not call HMS AI Cockpit production-certified or a production superset until real Windows/Codex, live quota fidelity, multi-account rotation, LAN/NAS failover and required 6h/24h soak evidence pass.
