# HMS AI Cockpit — Roadmap after v25.70

## Locked next revision

**v25.71 — Cockpit v1.3.27 Windows Runtime Parity Certification & Production Evidence Promotion Auditor**

### P0 — Real Windows runtime parity campaign

1. Execute the v25.70 Cockpit-v1.3.27 delta gates on a real Windows target with current Codex.
2. Certify foreign-port conflict auto-rebind while proving the foreign PID remains untouched.
3. Certify launch-time account occupancy with two real isolated Codex instances and duplicate-account denial.
4. Certify client-auth/API-service split-state through login/logout, router/API-service stop/start and Codex restart transitions.
5. Certify official-account usage continuity across remove/re-add using only pseudonymous account references in HMS storage/evidence.
6. Certify WebSocket preference persistence across real credential refresh/switch and process restart.
7. Certify bounded credential backup retention and crash-safe rollback on NTFS/Windows semantics.

### P0 — Production Evidence Promotion Auditor (deferred from the pre-parity-reset roadmap)

1. Consume only evidence already accepted by the v25.69 ingest/dual-review ledger plus v25.70/v25.71 parity evidence.
2. Re-verify exact package, manifest, trust snapshot, signed reports, freshness, reviewer chain and current Cockpit baseline.
3. Produce a deterministic Vietnamese **promotion proposal** only; never mutate the score automatically.
4. Any proposed score change must map to exact signed Windows/Codex report digests and explicit reviewer ledger entries.
5. Revocation, package supersession, trust change, evidence staleness or a newer Cockpit baseline must invalidate/reconcile eligibility without replaying durable effects.

### P0 — Cockpit baseline watch

1. Record Cockpit v1.3.27 as the current frozen competitive baseline for this release.
2. If a newer public Cockpit version appears before v25.71 certification, perform a new Codex-only delta audit before score promotion.
3. Never silently inherit Antigravity/non-Codex features back into HMS scope.

### P1 — Operator evidence UX

1. Vietnamese parity-runtime checklist for each v1.3.27 delta.
2. Show PASS/FAIL/DEFERRED with evidence class and exact package/manifest digest.
3. Keep sensitive account IDs, tokens, credential payloads and raw reviewer identity out of exported diagnostics.

## Claim boundary

v25.71 may increase production evidence only from cryptographically bound, dual-reviewed, real Windows + Codex target evidence.
Synthetic/control-plane validation alone must leave the production evidence score unchanged.
