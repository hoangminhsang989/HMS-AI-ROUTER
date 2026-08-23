# HMS AI Cockpit — Continuation after v25.60

## v25.61 — Native Usage & Token Center Parity+

Primary next track, still developable without a real machine:

- Dedicated native Usage & Token Center card model for 5-hour / Weekly / model-specific windows.
- Reset countdown + absolute reset timestamp + source/freshness indicator in one row.
- Subscription/package lifecycle intelligence only from trustworthy explicit upstream fields.
- Distinguish package expiry, OAuth/token expiry and quota-reset time as three separate concepts.
- Plan-aware presentation for Free / Plus / Pro / Team-Business / Enterprise without inventing unavailable metadata.
- Reset-aware router preview: show why an account is preferred now versus after the next reset.
- History/replay for quota reset boundaries and package-expiry metadata changes.
- Synthetic fixtures for missing, malformed, stale and contradictory expiry/reset metadata.

## v25.62 — Recovery Transaction Replay & Multi-Subsystem Crash Consistency

- Apply the v25.60 journal contract to router restart, client restart, config repair and lease reelection execution paths.
- External-state verification for PREPARE records after unjournalled side effects.
- Transaction ownership/epoch fencing and torn-tail recovery.
- Cross-subsystem recovery replay and global idempotency proof.
- Crash injection across chained transactions and deterministic replay/minimization.

## Claim boundary

Development may continue with deterministic simulation/model checking. `PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED` remains reserved for real Windows/Codex/quota/LAN/SMB/soak evidence.
