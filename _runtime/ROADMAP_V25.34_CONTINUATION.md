# HMS AI Cockpit v25.34 continuation

## Current tranche
ADVANCED_QUOTA_CENTER

Status:
- IMPLEMENTED: PASS
- STATIC VERIFIED: PASS
- SYNTHETIC VERIFIED: PASS
- RUNTIME VERIFIED: DEFERRED_BY_OPERATOR
- SOAK VERIFIED: NOT_YET

## Delivered contract
1. Durable quota metadata/history in SQLite, with legacy JSONL import and bounded retention.
2. 5h/7d history, fixed-scale chart data and reset timeline per account.
3. Explicit quota source freshness: FRESH / AGING / STALE / UNKNOWN.
4. Forecast calibration by resolving stored predictions against later observed quota and reporting MAE/bias.
5. Additional/model-specific quota windows are surfaced when upstream exposes them; UNKNOWN remains explicit otherwise.
6. Live quota remains authoritative. Quota Center is telemetry only and cannot mutate account credentials, project binding, endpoint or sticky sessions.

## Next tranche — v25.35 Account Analytics
- Per-account long-term reliability score from request success, latency, retry, 429, circuit state and quota pressure.
- Model-aware account performance matrix where request metadata identifies model.
- Session/project load attribution without storing prompt bodies.
- Detect noisy/unreliable accounts and distinguish transient server failures from account-specific degradation.
- Use evidence windows with confidence and minimum-sample gates; no black-box score without reasons.
- GUI drill-down per account and exportable redacted evidence.

## Runtime gates deferred by operator
- Real Windows quota source freshness against Codex production responses.
- Accuracy calibration across real reset cycles.
- Real model-specific quota window evidence.
- Multi-account 24h/72h soak.
