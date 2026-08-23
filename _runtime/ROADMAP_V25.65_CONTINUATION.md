# HMS AI Cockpit — v25.65 Continuation Roadmap

Generated UTC: 2026-08-22T20:14:51.844956+00:00

## Frozen baseline

- Version: **25.65**
- Track: Codex-only
- Verdict candidate: `PASS_SYNTHETIC_CONTROL_PLANE_RELEASE_FREEZE`
- Feature evidence: **93.0%**
- Production evidence: **55.2%**
- Public BackendAction: **90**
- Real-effect mode: **DISARMED by default**

## Next revision — v25.66

**Live Windows Attestation Signer & Controlled Target Certification Runbook**

### P0
1. Add a Windows-local attestation signer abstraction that can bind evidence to machine/package/run without exporting private signing material.
2. Support Windows certificate-backed or DPAPI-bound attestation verification with stable signer-class metadata.
3. Add one-shot controlled target certification runbook with explicit operator arming, dry-run, preflight, crash-window selection, recovery proof and automatic disarm.
4. Bind all target evidence to the exact release manifest digest and reject mixed-version/mixed-package evidence.
5. Keep production-score promotion impossible until the v25.65 promotion gate validates a real target pair.

### P1
- Vietnamese operator walkthrough for target certification.
- Evidence export/import verification without account identity, hostname, raw auth, command line or environment leakage.
- Recovery evidence chain viewer and promotion-decision explanation.

### Target-machine gates that remain open
- Real Windows PowerShell 5.1 parser/runtime.
- Real Codex App Official Auth / controlled restart effects.
- Real Windows target observer evidence.
- Real LAN/NAS failover evidence where applicable.
- 6h/24h soak.

Synthetic/control-plane work MUST NOT increase production evidence score by itself.
