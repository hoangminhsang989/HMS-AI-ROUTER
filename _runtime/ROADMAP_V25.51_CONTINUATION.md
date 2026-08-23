# HMS AI Cockpit — Roadmap after v25.51

## v25.52 — UX / Cockpit Parity+
- Consolidate Account Center, Live Quota, Adaptive/Closed-loop Router, Rotation status, LAN Pool and Diagnostics into an operator-first dark dashboard.
- One-glance reason codes: selected / held / reserve / stale / cooldown / circuit-open / affinity / failover.
- Add account-level drilldown showing why NEW sessions route elsewhere while existing sticky sessions remain bound.
- Keep Codex-only scope and frozen public BackendAction compatibility.

## v26.0 — Production Superset Gate
Requires:
- Windows PowerShell 5.1 target gate.
- Real Codex CLI/Desktop capability + v25.49 LIVE 1 evidence.
- Real Free/Plus/Pro quota fidelity + reserve/TTL evidence.
- Multi-instance real Codex rotation torture with 429/recovery.
- Multi-PC LAN/SMB/NAS lease/rejoin evidence.
- 6h and 24h reliability soak.
- No auth bleed, no session ping-pong, no destructive auth mutation.
