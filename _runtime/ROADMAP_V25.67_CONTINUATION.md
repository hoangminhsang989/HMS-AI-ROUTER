# HMS AI Cockpit — v25.67 Continuation Roadmap

Generated UTC: 2026-08-23T01:04:35.177040+00:00

## Frozen baseline
- Version: **25.67**
- Track: Codex-only
- Verdict candidate: `PASS_SYNTHETIC_CONTROL_PLANE_RELEASE_FREEZE`
- Feature evidence: **93.0%**
- Production evidence: **55.2%**
- Public BackendAction: **90**
- Real-effect target certification: **DISARMED by default**
- Windows runtime certified: **false**

## Next revision — v25.68
**Target Campaign Executor & Attested Promotion Review Console**

### P0
1. Add a Windows-only campaign executor that consumes the v25.67 12-case journal but can execute only one explicitly armed case at a time.
2. Require the exact v25.67+ release manifest digest and frozen trust-snapshot digest before every target case.
3. Before any case effect, run Windows PowerShell 5.1 parser/runtime preflight, Codex process ownership verification, Official Auth observer and idempotency witness checks.
4. Auto-disarm after every case regardless of PASS/failure/crash recovery; resume uses v25.67 `VERIFY_ONLY / ATTEST_ONLY / OPERATOR_REQUIRED / SKIP_COMPLETE` semantics.
5. Build an attested promotion-review console that imports 12 signed case reports and shows exactly why evidence is eligible, stale, revoked, mixed-version or incomplete.
6. Keep production score unchanged unless evidence was actually produced on a real Windows target and passes cryptographic promotion review.

### P1
- Vietnamese 12-case campaign grid with status and last attestation timestamp.
- Trust rotation drill: old certificate retired/revoked while completed evidence remains auditable and new cases require the new pinned signer.
- Export one offline review bundle containing trust snapshot, 12 pseudonymous case summaries, signature envelopes and promotion decision; no account identity/credential/private material.
- Real LAN/NAS lease case adapter remains separately gated and must prove ownership/readback before mutation.

### Production promotion rule
- Synthetic/control-plane evidence MUST NOT increase production score.
- `promotion_score_eligible=true` is only a review input, never automatic production certification.
- Complete real Windows 4×3 campaign + cryptographic verification + trust snapshot + target runtime evidence is required before any production-score change.

### Target-machine gates still open
- Real Windows PowerShell 5.1 parser/runtime.
- Real Codex App Official Auth and controlled restart effects.
- Real certificate/DPAPI signing and trust rotation.
- Complete real 4×3 campaign.
- LAN/NAS failover evidence where applicable.
- 6h/24h soak.
