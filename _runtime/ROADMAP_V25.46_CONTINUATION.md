# HMS AI Cockpit — Roadmap after v25.46

## v25.47 — Reliability / Soak Harness
- Add resumable 6h / 24h sustained Router + multi-instance + LAN heartbeat/lease soak harness.
- Record crash/restart/reconnect loops with bounded recovery, evidence checkpoints and no silent takeover.
- Exercise lease churn, temporary SMB loss, node disconnect/rejoin and concurrent project ownership attempts.
- Produce machine-readable soak evidence that can resume after interruption without treating partial time as PASS.

## v25.48 — Performance & Scale
- Measure Router latency overhead, TTFT impact, GUI refresh cost, SQLite/log IO and LAN registry contention.
- Test higher account/instance/project counts while preserving session affinity, project ownership and quota-aware routing.
- Add bounded backpressure and queue observability where load tests show contention.

## v25.49 — Production Release Candidate
- Execute final security/redaction review, migration/rollback rehearsal and clean-machine install/upgrade verification.
- Require target Windows PowerShell 5.1 + real Codex CLI/Desktop compatibility evidence.
- Require real multi-PC SMB/NAS ownership/failover evidence.
- Freeze release candidate only when all mandatory runtime gates are green.

## v26.0 — Production
- Ship only after real Windows/Codex runtime, real LAN and soak certification are complete.
- Production-superset wording remains prohibited unless the parity/production evidence supports it.
