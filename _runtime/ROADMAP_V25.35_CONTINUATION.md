# HMS AI Cockpit v25.35 continuation

## Current tranche
ACCOUNT_ANALYTICS

Status:
- IMPLEMENTED: PASS
- STATIC VERIFIED: PASS
- SYNTHETIC VERIFIED: PASS
- RUNTIME VERIFIED: DEFERRED_BY_OPERATOR
- SOAK VERIFIED: NOT_YET

## Delivered contract
1. Per-account quality profile uses normalized request telemetry, quota pressure, circuit state and predictive risk.
2. Quality score is confidence-aware and remains neutral/LEARNING when evidence is insufficient.
3. Account × Model and Account × Workload matrices are generated without reading prompt bodies.
4. Model recommendation is advisory and minimum-sample gated.
5. Closed-loop consumes analytics only as a bounded ±8 adjustment; hard eligibility, Circuit Breaker and sticky-session invariants remain authoritative.
6. Stable endpoint, project binding, credentials and existing session affinity are untouched.

## Next tranche — v25.36 Codex Identity Isolation Hardening
- Strengthen per-instance CODEX_HOME / profile / app-data / config / auth snapshot boundaries.
- Add deterministic identity fingerprint per instance/account/project without exposing OAuth secrets.
- Detect accidental cross-instance state reuse before launch.
- Track process ancestry and environment proof for each managed Codex instance.
- Add one-click isolation audit and repair-safe guidance; no destructive auto-delete.
- Prepare stronger multi-instance runtime evidence for later Windows certification.

## Runtime gates deferred by operator
- Real Windows account quality telemetry under live Codex traffic.
- Real model-aware account matrix across multiple paid/free accounts.
- 24h/72h trend stability and false-positive analysis.
- Closed-loop live switching while existing sessions remain sticky.
