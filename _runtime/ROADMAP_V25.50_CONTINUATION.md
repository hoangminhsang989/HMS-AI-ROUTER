# HMS AI Cockpit — Roadmap after v25.50

## v25.51 — Seamless Rotation Torture Test
- Repeated account rotation under quota depletion, 429 bursts, stale refresh and account recovery.
- Prove no cross-account auth bleed and no session-affinity break.
- Prove reserve hysteresis prevents switch ping-pong.
- Exercise 2+ Codex instances and LAN node rejoin during rotation.

## v25.52 — UX / Cockpit Parity+
- Consolidate Account Center, Quota, Router and Diagnostics into an operator-first dark dashboard.
- One-glance reason codes for why an account is selected, held, reserve, stale or blocked.

## v26.0 — Production Superset Gate
Requires Windows PowerShell 5.1, real Codex CLI/Desktop, Free/Plus/Pro quota fidelity, multi-instance, multi-PC LAN/SMB/NAS, 6h/24h soak and v25.49 LIVE 1 evidence.
