# HMS AI Cockpit v25.36 continuation

Current tranche: `CODEX_IDENTITY_ISOLATION_HARDENING`

Status:
- IMPLEMENTED: PASS
- STATIC VERIFIED: PASS
- SYNTHETIC VERIFIED: PASS
- RUNTIME VERIFIED: DEFERRED_BY_OPERATOR
- SOAK VERIFIED: NOT_YET

## Next tranche — v25.37 Codex Model & Reasoning Manager
- Discover current Codex model catalog through the stable HMS endpoint.
- Persist project-scoped model + reasoning defaults without changing account identity.
- Capability matrix for Responses API / tools / reasoning / image / web-search where observable.
- Fail closed on unsupported model aliases; never silently substitute a different paid model.
- Keep identity fingerprint, Project Affinity, session affinity, Circuit Breaker and quota policies authoritative.
- Native GUI only for normal operation.
