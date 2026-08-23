# HMS AI Cockpit — v25.68 Continuation Roadmap

Generated UTC: 2026-08-23T01:26:03.672413+00:00

## Frozen baseline
- Version: **25.68**
- Track: Codex-only
- Verdict candidate: `PASS_SYNTHETIC_CONTROL_PLANE_RELEASE_FREEZE`
- Feature evidence: **93.0%**
- Production evidence: **55.2%**
- Public BackendAction: **90**
- Real-effect target execution: **DISARMED by default**
- Windows runtime certified: **false**

## Next revision — v25.69
**Windows Target Certification Evidence Ingest & Promotion Decision Ledger**

### P0
1. Add a read-only evidence-ingest pipeline for externally produced Windows target certification reports; ingest never executes target effects.
2. Require exact package version, release-manifest SHA-256, frozen trust-snapshot digest, run/campaign ID, case ID and cryptographically verified signer envelope for every imported report.
3. Reject duplicate/replayed nonce, mixed package/trust generation, stale/revoked signer, incomplete 4×3 matrix and conflicting case ownership.
4. Add an immutable promotion-decision ledger that records human review decisions, evidence digest, reviewer pseudonymous identity, reason code and prior-decision link; append-only, no silent overwrite.
5. Require explicit dual-review policy before a real campaign can become `PROMOTION_ELIGIBLE`; eligibility remains separate from automatic production-score mutation.
6. Re-evaluate prior decisions when a certificate is revoked, trust snapshot changes, package is superseded or evidence ages beyond policy; never delete historical evidence.
7. Keep `production_evidence_score_pct` unchanged unless real Windows/Codex evidence has been imported, cryptographically validated and explicitly approved under the promotion policy.

### P1
- Vietnamese Evidence Inbox showing 12-case completeness, signature/trust state, freshness and conflict reason.
- Offline-first import/export with deterministic bundle digest and no network requirement.
- Quarantine area for invalid/mixed/replayed evidence; no automatic repair or promotion.
- Decision timeline linking campaign → signed reports → trust snapshot → human reviews → promotion decision.
- Optional NAS archival adapter with append-only/object-version evidence and ownership/readback checks before archival mutation.

### Production promotion rule
- Synthetic/control-plane evidence MUST NOT increase production score.
- Importing real evidence does not itself certify production readiness.
- A promotion ledger decision must be explicit, traceable and reversible only by a new superseding ledger entry.
- Automatic production certification remains forbidden.

### Target-machine gates still open
- Real Windows PowerShell 5.1 parser/runtime evidence.
- Real Codex App Official Auth/restart/router/lease effects across the complete 4×3 campaign.
- Real Windows certificate/DPAPI signatures from the target.
- Real target evidence ingest and dual human review.
- LAN/NAS failover evidence where applicable.
- 6h/24h soak and production hardening.
