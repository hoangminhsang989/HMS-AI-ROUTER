# HMS AI Cockpit — v25.24 continuation

## Current tranche
`LIVE_AUTOMATION_AND_ROUTE_VISIBILITY`

The user-facing path is GUI-only. BAT/PowerShell gate files are retained for diagnostics/recovery, not normal operation.

## Implemented in v25.24
- Native GUI drives core automation while open.
- Live route/account attribution is surfaced in Overview and Logs.
- Auto quota switch now has an execution path.
- HA/Operations controls are surfaced under Advanced.

## Next recommended tranche
`ACCOUNT_POOL_INTELLIGENCE_AND_ANTIGRAVITY_CONTROL`

1. Per-account usage counters / request count.
2. Better reset-aware account ranking and reserve visualization.
3. Account aliases/groups/favorite in native GUI.
4. Antigravity 2.0 panel integrated into the same native GUI.
5. Silent-vs-restart switch semantics shown clearly per client.
6. Package updater + rollback UI.

## Runtime test policy
Real Codex/failover/quota checks are temporarily treated as deferred, per operator direction. Failures encountered later become remediation revisions instead of blocking this feature tranche.
