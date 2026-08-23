# HMS AI Cockpit — continuation after v25.32

## Current baseline
- Product scope: CODEX ONLY.
- v25.28: multi-instance/account/project isolation.
- v25.29: Project Affinity.
- v25.30: Seamless stable endpoint + account pool.
- v25.31: Closed-loop feedback routing.
- v25.32: per-instance/account Circuit Breaker + guarded quarantine + HALF_OPEN recovery.

## Next tranche — v25.33 Predictive Quota
1. Build durable quota history per account/window/model where source data is available.
2. Estimate consumption velocity with explicit confidence and never present estimates as authoritative quota.
3. Predict time-to-floor / time-to-exhaustion for 5h and weekly windows.
4. Feed predictive pressure into Closed-loop score before actual exhaustion.
5. Add reserve preservation: avoid spending the final healthy account too early.
6. Keep project/session affinity and circuit state authoritative over prediction.
7. Add conservative confidence gates, stale-data detection and fail-closed handling.
8. Runtime verification remains separate from implementation/static/synthetic evidence.

## Non-goals
- No Antigravity work.
- No provider expansion.
- No destructive cleanup of older releases.
