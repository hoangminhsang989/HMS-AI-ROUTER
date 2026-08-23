# HMS AI Cockpit — after v25.31

## Completed in v25.31
- Closed feedback loop from Router Usage Ledger into per-instance account ranking.
- 1h / 24h / 7d reliability, latency, retry and HTTP error signals.
- Quota/health/pool-score fusion per account.
- Session-safe hysteresis + hold/cooldown + minimum sample gates.
- Guarded per-instance priority/weight apply with SHA-256 manifest update.
- Transactional rollback path and no-destructive-delete invariant.
- Seamless credential refresh preserves instance-local routing metadata.

## Next hard gate: v25.32 Circuit Breaker + Failover State Machine
- Track consecutive/recent failures per account and per instance.
- CLOSED / OPEN / HALF_OPEN circuit state with bounded probe traffic.
- Quarantine 401/403 and repeated 429 separately from transient 5xx/timeouts.
- Feed circuit state into Closed-loop ranking without breaking existing sessions.
- Add operator-visible reason/timer for every quarantined account.

Evidence state: IMPLEMENTED + STATIC VERIFIED + SYNTHETIC APPLY/ROLLBACK VERIFIED. Real Windows Codex runtime/soak remains deferred by operator.
