# HMS AI Cockpit — Roadmap after v25.45

## v25.46 — Regression & Compatibility Freeze
- Freeze the Codex-only public GUI/backend action contract.
- Exhaustive backward regression for v25.28–v25.45 features.
- Windows PowerShell 5.1 parser/runtime verification when operator testing is available.
- Codex CLI/Desktop compatibility matrix and config migration checks.
- LAN Pool failure matrix: share unavailable, SMB reconnect, stale lock, clock skew, duplicated node state, invalid signature, expired lease takeover.

## v25.47 — Reliability / Soak Harness
- 6h / 24h sustained Router + multi-instance + LAN heartbeat soak.
- Crash/restart/reconnect loops with evidence and bounded recovery.
- Lease churn and node disconnect tests without silent takeover.

## v25.48 — Performance & Scale
- Measure GUI refresh, Router latency overhead, SQLite/log IO and LAN registry contention.
- Test higher instance/account/project counts while preserving sticky-session behavior.

## v25.49 — Production Release Candidate
- Final security review, redaction review, migration/rollback rehearsal and clean-machine install verification.

## v26.0 — Production
- Ship only after the real Windows/Codex runtime gates and soak are completed.
