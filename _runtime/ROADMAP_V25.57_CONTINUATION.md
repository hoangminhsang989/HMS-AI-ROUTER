# HMS AI Cockpit — continuation after v25.57

## Locked next stage: v25.58 — Compound-Fault Recovery Convergence Lab

Goal: prove that the v25.57 cause-aware planner converges under overlapping failures rather than handling only one incident at a time.

Planned gates:
- Compound incidents: quota+429+router crash, SMB partition+lease expiry, config drift+client crash, stale quota+account recovery.
- Recovery DAG dependency ordering and conflict elimination (e.g. never restart while config rollback is pending).
- Global recovery budget across accounts/instances/projects.
- Escalation arbitration: one operator incident instead of duplicated alerts.
- Recovery convergence proof: bounded steps to HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED.
- Recovery storm simulation with adversarial event ordering and deterministic replay.
- Rollback-of-rollback guard and generation/epoch monotonicity.
- Privacy-safe decision timeline integrated into diagnostics.

Claim boundary remains unchanged: synthetic/model-check evidence can improve feature safety but cannot issue target-machine production certification.
