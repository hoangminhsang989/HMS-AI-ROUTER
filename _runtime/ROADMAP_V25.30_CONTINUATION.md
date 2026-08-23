# HMS AI Cockpit — after v25.30

## Completed in v25.30
- Stable local endpoint per managed Codex instance.
- Primary + Project Affinity fallback credentials behind the same instance Router.
- Metadata-only router pool manifest with SHA-256 evidence.
- Session affinity + retry credential policy.
- GUI pool visibility and explicit sync action.
- No Codex config rewrite required when fallback pool changes.

## Next hard gate: v25.31 Closed-loop Adaptive Routing
- Feed real route outcomes from Usage Ledger back into per-account scores.
- Combine quota, success/failure, latency, cooldown and project role.
- Keep session affinity; do not ping-pong an active session.
- Introduce guarded policy transitions with reason/evidence for every change.

Evidence state: IMPLEMENTED + STATIC VERIFIED. Real Windows failover/no-Codex-restart behavior and soak are deferred by operator.
