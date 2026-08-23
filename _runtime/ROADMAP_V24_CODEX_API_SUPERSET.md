# HMS v24.0 — Codex API Superset & Parity Auditor

## Baseline reviewed

Public Cockpit evidence reviewed on 2026-08-19:
- release workflow shows v1.3.16;
- current `CODEX_API_SERVICE_HANDOFF.md`;
- current README and Codex API Service release history.

## v24 closure

- Per-client-key target/account scope.
- Per-client-key routing strategy.
- Per-client-key priority/weight/backup.
- Client-key scoped session affinity.
- Quota reserve fail-closed semantics.
- Auto/random/single/quota/plan/expiry routing.
- Model prefix catalog + request rewrite.
- Local loopback CORS.
- Usage/token/cost ledger.
- Daily/weekly/monthly/all-time analytics.
- Session visibility repair synthetic proof.
- Parity Auditor.

## Evidence

Feature evidence score: **93.0%**
Production evidence score: **55.2%**

The two scores are deliberately separate.

Feature score answers:
> Is the capability present with static/synthetic evidence?

Production score answers:
> Has it been proven under real Windows/Codex/network runtime?

## HMS design advantages over current Cockpit baseline

- Per-key target pool is a first-class HMS policy.
- Proxy Fleet public-IP baseline/drift/quarantine.
- Health + egress freshness gates.
- HA / Soak / Policy Kernel.
- Explicit foreign-PID ownership invariant.
- Source-integrity + Windows runtime evidence gates.

## Cockpit still ahead

- Public production maturity.
- Real cross-platform release lifecycle.
- Richer mature UI.
- Proven quota/plan/subscription feed.
- Dedicated image scheduling/concurrency behavior.
- Broader provider/platform ecosystem.
- Real multi-instance usage and account/profile lifecycle.
- More mature timeout/retry presets and operational tuning.

## Next recommended major stage

**v25 Windows Runtime Certification & Cockpit Gap Closure**

Order:
1. target-PC PowerShell parse/PREFLIGHT;
2. live CLIProxy sidecar;
3. two-account real routing;
4. quota feed validation;
5. real SSE/WebSocket Codex;
6. proxy egress fail-closed;
7. multi-instance launch/session repair;
8. image endpoint/concurrency gate;
9. 1h soak;
10. then 6h/24h certification.

No new large control-plane subsystem should outrank real runtime certification now.
