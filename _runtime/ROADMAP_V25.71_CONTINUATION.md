# HMS AI Cockpit — Roadmap after v25.71

## Locked next revision

**v25.72 — Windows Target Evidence Capture Kit & Cockpit Baseline Watch Gate**

### P0 — Windows target evidence capture kit
1. Produce a portable Windows-only capture package for the seven Cockpit v1.3.27 parity runtime cases.
2. Every case must bind exact HMS ZIP SHA-256, release manifest SHA-256, Cockpit baseline and Codex version.
3. Capture only pseudonymous IDs/digests; never export raw auth tokens, account IDs, prompts, responses, command-line secrets or environment secrets.
4. Generate one signed report per case with idempotency witness, observer evidence class, timestamps and operator-visible PASS/FAIL/DEFERRED.
5. Keep real-effect execution one-case-at-a-time and DISARMED by default.

### P0 — Baseline watch gate
1. Re-check the public Cockpit Tools version before any Windows target campaign starts and again before promotion review.
2. If baseline > 1.3.27, freeze promotion and perform a Codex-only delta audit first.
3. Never silently import Antigravity/non-Codex scope.

### P0 — Production promotion path
1. Import signed Windows target reports through the v25.69 read-only ingest.
2. Require dual review through the append-only ledger.
3. Run v25.71 Production Evidence Promotion Auditor.
4. Human operator decides whether production-evidence score should change; no automatic mutation.

### P1 — Operator UX
- Vietnamese checklist for each of seven parity cases with package/manifest/Codex version/evidence class.
- Export a privacy-safe evidence index and recovery timeline.

## Claim boundary
Until external signed Windows + current Codex evidence is imported and reviewed, `windows_runtime_certified=false` and production evidence remains 55.2%.
