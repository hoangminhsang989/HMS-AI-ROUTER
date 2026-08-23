# HMS AI Cockpit — Continuation after v25.61

## Current frozen milestone
**v25.61 — Native Usage & Token Center Parity+**

Delivered and frozen:
- native 5-hour / Weekly / model-specific quota card model;
- plan-aware Free / Plus / Pro / Team-Business / Enterprise presentation;
- countdown + absolute reset timestamp + source + freshness;
- strict package-expiry / OAuth-token-expiry / quota-reset separation;
- scenario-only NOW vs AFTER NEXT RESET router preview;
- metadata-only reset/package history and replay;
- Unified Diagnostics + Diagnostics Bundle privacy integration;
- frozen public BackendAction set remains 90.

## Next milestone — v25.62
**Recovery Transaction Replay & Multi-Subsystem Crash Consistency**

### P0 — Cross-subsystem transaction identity
- One transaction ID / effect fingerprint across Official Auth switch, controlled Codex restart, router state transition and LAN lease handoff when they belong to one operator intent.
- Explicit idempotency keys for every side-effecting recovery step.
- Reject duplicate durable effects after crash/restart.

### P0 — Durable replay engine
- Reconstruct unresolved recovery transaction from journal at startup.
- Verify externally observable effect before deciding COMMIT, VERIFY, ROLLBACK or OPERATOR_REQUIRED.
- Never repeat an auth rewrite/restart/lease takeover solely because the prior process disappeared.

### P0 — Multi-subsystem compensation DAG
- Model dependencies and compensations across auth, process restart, router and LAN lease state.
- Roll back only effects proven to belong to the unresolved transaction.
- Preserve concurrent external changes and fail closed when ownership cannot be proven.

### P0 — Crash matrix expansion
- Deterministic crash points before/after every durable phase and every cross-subsystem effect.
- Compound crash/restart cases, repeated recovery process crash, stale journal, partial rollback and concurrent operator change.
- Invariant: at-most-once durable side effect + eventual HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED convergence.

### P1 — Recovery replay operator UX
- One timeline showing transaction, effect fingerprints, current recovery decision and proof.
- Clear Vietnamese states: ĐÃ XÁC MINH, CẦN PHỤC HỒI, CẦN NGƯỜI VẬN HÀNH.
- Export metadata-only evidence to Unified Diagnostics.

### P1 — Target-machine evidence hooks
- Prepare Windows/Codex hooks for later real crash injection around file/keyring/auto auth storage and controlled restart.
- Keep real target-machine certification separate from synthetic PASS.

## Production gate remains unchanged
Do not call HMS AI Cockpit production-certified or a production superset until real Windows/Codex, live quota fidelity, multi-account rotation, LAN/NAS failover and required soak evidence pass.
