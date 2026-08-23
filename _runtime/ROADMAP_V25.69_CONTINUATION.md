# HMS AI Cockpit — Roadmap after v25.69

## Locked next revision

**v25.70 — Production Evidence Promotion Auditor & Revocation Reconciliation Ledger**

### P0 — Promotion Score Auditor

1. Add a separate, read-only `ProductionEvidencePromotionAuditor` authority.
2. Consume only evidence already accepted by v25.69 ingest plus an intact v25.69 dual-review ledger.
3. Re-verify exact package/manifest/trust snapshot/campaign matrix/signatures/freshness at audit time.
4. Produce a deterministic **promotion proposal**, never mutate the score automatically.
5. The proposal must explain in Vietnamese which evidence classes are production-eligible, which remain synthetic, and why.
6. Any proposed production-score change must be traceable to exact signed report digests and dual-review ledger entries.
7. Keep feature score and production score unchanged when real Windows/Codex evidence is absent.

### P0 — Revocation / supersession reconciliation

1. Re-evaluate previously eligible campaigns when certificate is revoked/retired, trust snapshot changes, package or manifest is superseded, or evidence becomes stale.
2. Never delete historical evidence or prior decisions.
3. Append a new reconciliation/superseding record with reason code and prior-entry digest.
4. Previously durable real effects must never be replayed merely because promotion eligibility is revoked.
5. Reconciliation must be offline/deterministic and safe under concurrent ledger append.

### P0 — Explicit human promotion authority boundary

1. `PROMOTION_PROPOSED` is not `PRODUCTION_CERTIFIED`.
2. No automatic score mutation is allowed from ingest, campaign executor, review console, ledger or auditor.
3. A future explicit signed human promotion record is required before the product state may reflect a production-score change.
4. Public `BackendAction` remains frozen unless a separately reviewed compatibility change is authorized.

### P1 — Evidence archive / portability

1. Deterministic export package containing only accepted evidence, trust snapshot, ledger chain and auditor proposal.
2. Optional append-only NAS archival adapter with checksum verification and no overwrite semantics.
3. Offline verification must work without account credentials, private keys or network access.
4. Diagnostics surface should show archive digest, reconciliation state and proposal reason without reviewer/account identity.

## Claim boundary

v25.70 remains synthetic/control-plane until actual Windows + Codex evidence is imported and passes all cryptographic, replay, trust, dual-review and separate promotion-auditor gates.
Synthetic tests must not increase the production evidence score.
