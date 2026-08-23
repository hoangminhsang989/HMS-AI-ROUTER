# HMS AI Cockpit — v25.26 continuation

## Delivered tranche
`DURABLE_USAGE_LEDGER_AND_SAFE_LOCAL_RELEASE_MANAGER`

- Durable SQLite request ledger beyond rolling log windows.
- Native usage dashboard by account/model with token coverage and latency.
- Adaptive Pool is visible but intentionally `ADVISORY_ONLY`.
- One-click redacted diagnostics bundle is available from GUI.
- Local releases can be hash-verified, activated, and rolled back without deleting old versions.

## Next recommended tranche — v25.27
`ADAPTIVE_ROUTER_POLICY_AND_SIGNED_UPDATE_CHANNEL`

1. Router-native adaptive weighting with hard safety bounds, hysteresis and explicit opt-in.
2. Combine durable usage score + live quota/reset/health + preferred/reserve role into one policy decision.
3. Signed online release metadata/feed, download to staging, verify SHA/signature, then local activation.
4. Release retention policy that only proposes cleanup first; destructive deletion remains confirmation-gated.
5. Usage export/report and longer-term SLA/latency trends.
6. Unified health badge that explains why an account is selected or excluded in real time.

## Runtime test policy
Real Codex/Antigravity runtime tests remain deferred by operator direction. Any defect discovered during real use becomes a focused remediation revision without reverting GUI-only operation.
