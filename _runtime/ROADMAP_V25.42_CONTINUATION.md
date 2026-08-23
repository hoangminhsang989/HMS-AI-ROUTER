# HMS AI Cockpit — Continuation after v25.42

## Current milestone
v25.42 establishes a one-click Codex Project Orchestrator on top of Project Affinity, Identity Isolation, Security Hardening, Model/Reasoning Manager and Seamless Router.

## Next recommended tranche: v25.43 Multi-Codex Team
- Assign multiple managed Codex instances to one project as roles: Coder / Reviewer / Tester.
- Preserve dedicated account + CODEX_HOME + app-data + router identity per role.
- Add project-level role topology and conflict/ownership guard.
- Allow parallel work only when project/worktree ownership rules do not conflict.
- Add explicit handoff/epoch semantics instead of silent takeover.
- Keep destructive operations blocked unless explicitly approved.

## Verification ladder
- IMPLEMENTED
- STATIC VERIFIED
- SYNTHETIC VERIFIED
- RUNTIME VERIFIED on real Windows Codex
- SOAK VERIFIED

v26.0 must not claim production readiness while core Codex multi-instance/orchestration features remain runtime-deferred.
