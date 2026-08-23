# HMS AI Cockpit — Continuation after v25.43

## Current milestone
v25.43 adds Multi-Codex Team topology above isolated managed instances: Coder / Reviewer / Tester can run in parallel only with distinct workspaces and explicit role ownership.

## Next recommended tranche: v25.44 Smart Model Router
- Route new project/team work to the best model + account using Model/Workload Analytics, quota runway, circuit state and reasoning policy.
- Preserve existing conversation/session affinity; never hot-switch an active sticky session merely because another model scores higher.
- Add model capability hard gates and per-role defaults (Coder / Reviewer / Tester).
- Add bounded policy influence and explicit rationale/evidence for every recommendation/application.
- Keep stable endpoint, identity isolation and security hard gates unchanged.

## Later
- v25.45 cross-PC/LAN Codex pool.
- v25.46–v25.49 regression, Windows runtime certification, performance and soak.
- v26.0 only after core Codex paths are RUNTIME VERIFIED + SOAK VERIFIED.
