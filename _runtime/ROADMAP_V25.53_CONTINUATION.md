# HMS AI Cockpit — Roadmap after v25.53

## Target-machine execution gate
v25.53 is the last software-side aggregation gate before a production-superset claim can be considered. On a real Windows target, the operator must complete:
1. PREFLIGHT: Windows PowerShell 5.1 + Codex CLI capability + >=2 isolated managed instances.
2. LIVE 1: one explicitly confirmed real Codex request.
3. Live quota refresh for at least two real accounts with valid 5h + weekly windows.
4. One bounded failover test with restore verified.
5. >=2 signed LAN nodes and a real SMB/NAS atomic roundtrip.
6. Completed non-synthetic 6h soak.
7. Completed non-synthetic 24h soak.

## v26.0 — Production Superset Gate
Only after v25.53 returns `PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED` on the intended production topology may v26.0 re-score production evidence and consider a Production Superset verdict. Until then the correct claim remains `FEATURE_PARITY_CANDIDATE`.

No synthetic fallback, shortened soak, stale quota, single-node LAN, failed account restore or unconfirmed model request can satisfy the production gate.
