# HMS AI Cockpit — Continuation after v25.38

## Next tranche: v25.39 Codex Self-Healing

Goal: detect and repair common Codex/HMS runtime drift without asking the normal user to run BAT/PowerShell.

Target checks:
- Codex/ChatGPT executable discovery and version visibility
- Router process/port ownership and stale PID repair
- stable endpoint/provider drift
- client key/config mismatch
- isolated instance identity drift
- project/account binding drift
- stale credential snapshot / missing auth pool member
- model policy drift
- Circuit Breaker/Closed-loop state consistency
- safe restart/reload recommendation or guarded action

Hard invariants:
- Codex-only scope
- no destructive delete action
- no secret logging
- every repair has pre-state evidence and readback
- do not kill a PID not proven to be HMS-owned
- restore/rollback on failed repair

Acceptance levels remain IMPLEMENTED -> STATIC VERIFIED -> SYNTHETIC VERIFIED -> RUNTIME VERIFIED -> SOAK VERIFIED.
