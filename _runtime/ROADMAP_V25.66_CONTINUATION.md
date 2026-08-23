# HMS AI Cockpit — v25.66 Continuation Roadmap

Generated UTC: 2026-08-23T00:47:22.439877+00:00

## Frozen baseline
- Version: **25.66**
- Track: Codex-only
- Verdict candidate: `PASS_SYNTHETIC_CONTROL_PLANE_RELEASE_FREEZE`
- Feature evidence: **93.0%**
- Production evidence: **55.2%**
- Public BackendAction: **90**
- Real-effect target certification: **DISARMED by default**
- Windows runtime certified: **false**

## Next revision — v25.67
**Windows Attestation Trust Store & Resumable Target Certification Campaign**

### P0
1. Add a local Windows attestation trust-store abstraction with certificate pinning, explicit rotation/revocation state and deterministic trust-snapshot digest.
2. Add DPAPI signing-key lifecycle metadata (create/rotate/retire) without exporting raw key material.
3. Add an offline attestation verifier for package/run/nonce/signature/trust snapshot without account identity or credential access.
4. Add a resumable certification campaign journal for the 4-effect x 3-crash-window matrix. Each case remains one-shot and separately armed; resume must never silently repeat a durable effect.
5. Bind every case to the exact release manifest and trust-snapshot digest; mixed-version, revoked signer or reused nonce fails closed.
6. Keep real-effect execution DISARMED by default and require explicit target-machine operator arming per case.

### P1
- Vietnamese campaign dashboard: pending / running / recovered / operator-required / attested / rejected.
- Certificate-expiry and revocation warnings without leaking private material.
- Exportable offline verification report with pseudonymous machine/runtime refs.
- Promotion decision explains exactly which target evidence is missing or rejected.

### Production promotion rule
- Synthetic/control-plane evidence MUST NOT increase production score.
- A real Windows campaign may only become **promotion eligible** after cryptographic verification and complete 4x3 target evidence.
- Promotion eligibility is evidence for review, not automatic production certification.

### Target-machine gates that remain open
- Real Windows PowerShell 5.1 parser/runtime.
- Real Codex App Official Auth / controlled restart effects.
- Real Windows target observer + certificate/DPAPI signing.
- Complete 4x3 crash certification campaign.
- Real LAN/NAS failover evidence where applicable.
- 6h/24h soak.
