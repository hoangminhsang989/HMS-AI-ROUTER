# HMS AI Cockpit — Roadmap after v25.52

## v25.53 — Target-Machine Certification Runner
- Provide one operator-first Windows certification flow that checks PowerShell 5.1, Codex CLI/Desktop capability, login/auth metadata, Router health, at least two managed Codex instances, project affinity and isolated CODEX_HOME/app-data.
- Reuse v25.49 LIVE 1 for one explicit real model request; never spend quota without explicit operator confirmation.
- Capture real Free/Plus/Pro quota freshness/reserve evidence without storing OAuth/API keys/prompt/body.
- Run real rotation/failover checks while preserving v25.51 sticky-session and anti-ping-pong invariants.
- Validate SMB/NAS lease/rejoin on multiple Windows nodes when available.
- Launch/resume 6h and 24h soak checkpoints without counting downtime.
- Produce a signed/redacted certification report that clearly separates PASS / DEFERRED / NOT CONFIGURED.
- No destructive auth mutation; no silent takeover; no production claim from synthetic fallback.

## v26.0 — Production Superset Gate
Requires all target-machine authority gates to PASS:
- Windows PowerShell 5.1.
- Real Codex CLI/Desktop capability + explicit LIVE 1 evidence.
- Real Free/Plus/Pro quota fidelity + reserve/TTL evidence.
- Multi-instance real Codex rotation with 429/recovery and no session ping-pong.
- Multi-PC LAN/SMB/NAS lease/rejoin evidence.
- Completed 6h and 24h reliability soak.
- No auth bleed, no prompt/body leakage, no destructive auth mutation.

Until then the correct verdict remains FEATURE_PARITY_CANDIDATE, not production superset.
