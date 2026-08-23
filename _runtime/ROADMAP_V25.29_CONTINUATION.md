# HMS AI Cockpit — after v25.29

## Completed in v25.29
- Project Affinity control plane and native GUI.
- Project remembers its isolated Codex instance and bound primary account.
- Validated fallback metadata + health-aware recommendation.
- One-click focus/start of the correct mapped instance.

## Next hard gate: v25.30 Seamless Codex Router
- Stable local endpoint per project/session.
- Preferred + fallback account pool behind the endpoint.
- Rotate/failover account without restarting Codex.
- Preserve session affinity and avoid credential file mutation during a live session.

Evidence state: IMPLEMENTED + STATIC VERIFIED; real Windows runtime/soak deferred by operator.
