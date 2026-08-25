# HMS-AI-ROUTER — Project State v25.75

Date: 2026-08-25
Status: ACTIVE DEVELOPMENT — COCKPIT v1.3.29 PARITY DRIFT + WINDOWS RUNNER-START BLOCKER + REAL-WINDOWS GATE
Authority: `main` on `hoangminhsang989/HMS-AI-ROUTER`; current integration candidate PR #7 remains unmerged

## Baseline

- Migration baseline: v25.74
- Frozen Cockpit Tools parity authority for the **existing v25.75 evidence epoch**: v1.3.28
- Current upstream Cockpit Tools stable release: **v1.3.29**
- Upstream v1.3.29 release commit: `83ce2d192cc954cc910ce89edf2d1f710c218798`
- Previous v1.3.28 release commit: `82576b9634bad0a365abc51eba8f022fb0a50d97`
- Product scope: Codex-only
- Product branding: HMS-AI-ROUTER
- Historical v25.74 evidence is immutable and may retain former product branding where it is part of frozen evidence.

v1.3.29 was released on 2026-08-24 after the v1.3.28 evidence epoch was frozen. It is **not yet adopted** as HMS's new frozen baseline. The existing reviewer live-baseline provider reads GitHub Releases latest on each observation, so current v1.3.28 promotion attempts must fail closed as baseline drift until the v1.3.29 delta is reconciled and a new review epoch is opened.

Detailed parity-drift audit:

`docs/V25.75_COCKPIT_V1_3_29_DELTA_AUDIT.md`

## Evidence boundary carried forward

- Feature evidence score: 93.0%
- Production evidence score: 55.2%
- Windows runtime certified: false
- External Windows target evidence imported: false
- Real Codex effects executed for the current source-hardening increment: false
- Windows signing executed for production evidence: false
- Automatic production certification: false
- Production score promotion eligible: false

These values MUST NOT be promoted from the discovery of v1.3.29, source/synthetic proof, or GitHub-hosted CI alone.

## Current v25.75 integrated evidence-safety state

The source-side external Windows evidence/review path now includes:

1. Exact canonical seven-case contract: `host`, `codex`, `quota`, `failover`, `lan`, `soak_6h`, `soak_24h`.
2. Certificate-only packet signing and real certificate preflight/enrollment binding.
3. Independent reviewer-side signer trust authority that is not packet-derived.
4. Independent reviewer release-identity authority bound to explicit reviewed package/manifest/source identity.
5. CurrentUser-DPAPI-backed reviewer local integrity sealing.
6. Sealed verified-ingest metadata and sealed replay registry.
7. Serialized ingest transactions with stale-lock fail-closed behavior.
8. Reviewer packet-import entrypoint and principal review GUI bound to sealed metadata.
9. Promotion-disabled fail-closed GUI fallback if the principal reviewer wrapper is unavailable.
10. Bounded Windows evidence orchestrator for read-only operator preflight and reviewer import.
11. Read-only reviewer-authority freshness/integrity diagnostics.
12. Full final decision provenance binding: every append-only decision record binds raw packet, release manifest, package ZIP, source-certification report, reviewer trust authority and reviewer release authority SHA-256 references.
13. Dual-review approval reuse is rejected if any of those provenance references differs from the current sealed ingest authority.
14. Reviewer action policy and GUI buttons require the same decision-provenance contract as the final ledger.
15. AST caller audit rejects production direct ledger callers that omit full explicit provenance.
16. Controller adversarial proof covers replay-registry seal tamper, sealed report authority tamper, same-reviewer-key rogue authorities, forged unsealed metadata and stale locks.
17. Exact-source Cockpit v1.3.29 P0 proof pins release blobs and fail-closes quota refresh-token ownership plus combined OAuth/API-Key credential ownership/stale-token-revival invariants.
18. Exact-source device-auth delta proof distinguishes Tauri-runtime deltas from `cockpit-core` synchronization and keeps device-auth adoption authority explicitly open.
19. Both v1.3.29 proofs are transitively required by the canonical external-Windows source-binding proof and are included in workflow path triggers and Python compilation.

Integrated candidate checkpoint:

`docs/V25.75_INTEGRATED_WINDOWS_SAFETY_CANDIDATE.md`

## Current v25.75 Windows recovery state

The source-side Windows recovery tranche aligned to the frozen v1.3.28 evidence epoch includes:

- Access Denied / error 5 and WSAEACCES 10013, file-in-use / error 32, program-missing / error 2 and `CODEX_RESTART_REQUIRED` classification;
- retry and operator-handled-then-retry paths;
- open-location and copy-sanitized-error actions;
- sensitive-detail redaction;
- quiet background probe/health/quota/refresh behavior;
- recovery-first fail-closed launcher preserving sealed reviewer wrapper and safe fallback;
- Codex-only one-shot UAC helper restricted to validated `Codex.exe` / `ChatGPT.exe` process identity;
- fixed `%SystemRoot%\System32\taskkill.exe` with numeric PID arguments only;
- one-shot token consumption before UAC so cancellation/failure cannot replay the same prompt epoch;
- UAC eligibility only at the stable client-close barrier for the allowed Codex lifecycle;
- retry of the original backend transaction after successful elevated close;
- structured official-auth lifecycle recovery derived from settings and before/after supported-client process identity;
- exact surviving-original-PID targeting so replacement processes are not killed;
- successful auth remains committed if post-commit UAC close is cancelled/fails;
- bounded UAC validation harness, session-bound Cancel→Close pair verifier and guided PowerShell 5.1 operator runner;
- no launcher `runas`, no `ExecutionPolicy Bypass`, no keyboard automation or generic arbitrary-elevation CLI.

The integrated wrapper-chain proof additionally locks launcher → recovery wrapper → reviewer wrapper → guarded promotion entry → legacy core ordering and requires recovery/reviewer method patch sets to remain disjoint.

## Cockpit Tools v1.3.29 parity drift

### Credential-safety P0 status

The two adoption-critical credential-safety deltas are now **SOURCE-CLOSED / PROOF-WIRED / CI EXECUTION PENDING**:

1. quota/background refresh uses a valid access token without rotating an official-client-owned refresh-token chain, with source-proven caller flow through `prepare_account_for_quota_query` and post-authority-sync access-token recheck;
2. combined OAuth/API-Key profiles separate runtime/provider owner from actual OAuth credential owner and use generation-aware authority so a stale refresh token cannot be revived after official-client rotation/unbind/legacy upgrade transitions.

HMS source authority:

- `_runtime/HMS_Codex_CockpitV1329P0ParityProof.py`;
- fail-closed transitively through `_runtime/HMS_Codex_ExternalWindowsSourceBindingProof.py`.

These source proofs do not authorize Windows runtime certification, target-evidence import, production score mutation, or v1.3.29 baseline adoption.

### OAuth scopes / refresh lead correction

Exact release comparison shows that v1.3.28 **Tauri runtime** already used connector scopes `api.connectors.read` / `api.connectors.invoke` and a 10-minute ID-token refresh lead. Therefore those values are not newly introduced Tauri behavior in v1.3.29.

The actual release delta is that `crates/cockpit-core/src/modules/codex_oauth.rs` synchronizes from base scopes + 15-minute lead in v1.3.28 to the already-present Tauri connector scopes + 10-minute lead in v1.3.29.

This distinction is now source-proofed and must remain explicit; core-library source synchronization must not be mislabeled as a new canonical Tauri runtime behavior.

### Device-code OAuth status

Device-code authorization is a real new v1.3.29 Tauri runtime capability. Source-proven behavior includes official device endpoints/exchange redirect, 15-minute bounded lifetime, single-active OAuth state, login/device identity-bound polling, timeout clearing, restart non-revival and login-ID-scoped cancellation.

Runtime reachability is proven across frontend service → Tauri invoke → command → OAuth module, and the command is registered in the Tauri invoke handler.

HMS proof authority:

- `_runtime/HMS_Codex_CockpitV1329DeviceAuthDeltaProof.py`;
- fail-closed through `_runtime/HMS_Codex_ExternalWindowsSourceBindingProof.py`;
- workflow path-trigger and `py_compile` coverage included.

Current classification: **SOURCE-CHARACTERIZED / PROOF-WIRED / ADOPTION DECISION OPEN**.

HMS must make an explicit source/reconciliation decision before baseline adoption: either device auth is required parity and must be implemented with the proven lifecycle invariants, or it is an explicitly accepted/documented capability gap. A bare `COCKPIT_BASELINE` constant edit is not sufficient authority for that decision.

### Remaining v1.3.29 work

P1:

- device-auth parity decision;
- launch confirmation-before-mutation invariant;
- session repair/provider discovery;
- provider migration rollback/stopped-target safety.

P2:

- unified launch-preview feature breadth;
- full session migration/catalog-repair breadth;
- expanded API Service Live/Realtime/transports/features.

Do not simply change `COCKPIT_BASELINE` from `1.3.28` to `1.3.29`. Baseline adoption still requires explicit delta reconciliation, a materialized proof graph and a new proof/review epoch.

## Observed Windows CI proof graph

Historical complete source/synthetic walking-gate PASS remains valid only for the exact tested historical source:

- Run #67
- Run ID `32691345325`
- Job ID `97325459363`
- Tested head `3c78208d5f0a894e11ea2e2ec804137888c1b5a3`
- Microsoft Windows Server 2025 / Python 3.12.10
- all 36 configured steps PASS, including Windows PowerShell 5.1 guided UAC operator proof.

It does not certify the current PR #7 source or any real target.

Current PR #7 continues to hit the runner-start blocker before Checkout. A representative proof-only trigger after the v1.3.29 proof path-filter hardening is:

- Run #159
- Run ID `32812084285`
- Job ID `97693216475`
- Tested head `098e3e4384891e3ecbb972ce860582e438d3eb16`
- `steps = []`
- no Checkout/Setup/compile/proof step materialized.

The proof-only commit did enqueue the canonical workflow, confirming the new proof file is under workflow trigger authority. It does not constitute compile/proof execution.

Correct failure classification: **repository/account runner-start unavailable; exact cause unproven with available tooling**. This is neither a code PASS nor a code/test FAIL.

PR #7 must remain unmerged until an exact-final-head Windows Promotion Safety run materializes and passes its complete graph.

## Meaning of source / CI proof

Source/synthetic or GitHub-hosted Windows proof never means:

- authorized target Windows workstation tested;
- real target UAC accepted/cancelled;
- real target Codex/ChatGPT process closed;
- current-Codex canonical seven-case evidence captured;
- production evidence packet signed/imported;
- Windows runtime certified;
- production score may be promoted.

The historical v1.3.28 source proof also does not establish v1.3.29 parity, and the new v1.3.29 source proofs remain non-production-authoritative until their canonical graph actually executes.

## Real-Windows operational gate

The bounded UAC recovery target flow remains prepared, but **new production-evidence capture is deferred until the v1.3.29 parity baseline decision is complete**.

When an authorized Windows target is eventually used for the bounded recovery check:

1. Keep a supported Codex/ChatGPT client running.
2. Double-click `HMS_VALIDATE_UAC_RECOVERY.cmd`.
3. Type exact `CANCEL`, then cancel the first real UAC dialog; require `PASS_CANCEL_AND_REPLAY_BLOCK`.
4. Type exact `CLOSE`, accept the second real UAC dialog; require `PASS_CLOSE_AND_REPLAY_BLOCK` with positive supported-client close count.
5. Require final `PASS_BOUNDED_UAC_RECOVERY_PAIR`.
6. Keep the four bounded-recovery JSON outputs outside production evidence storage.

These checks remain separate from canonical seven-case production certification and do not resolve v1.3.29 parity.

## Reviewer authority operational rules

- Reviewer trust authority default freshness remains bounded and must be recaptured from approved source, never timestamp-edited/resealed to extend validity.
- Reviewer release authority must be separately captured from explicit reviewed package/manifest/source identity and must not self-derive those reviewed digests from the local artifact at import time.
- Certificate rotation/revocation must update approved reviewer trust authority before new packets are accepted.
- Reviewer local integrity keys are bound to Windows DPAPI CurrentUser and must not be copied to another user/machine to bypass reviewer context.
- Reviewer diagnostics are read-only and never import packets, mutate trust state, sign evidence, execute live Codex or change production score.

## Verification boundary

- Source/synthetic proof infrastructure is not real Windows/current-Codex production evidence.
- Raw runtime evidence remains immutable, digest-bound and append-only.
- Final human decision records retain source/package/reviewer-authority provenance through the append-only hash chain.
- Live Cockpit baseline reconciliation remains a click-time authority; current upstream v1.3.29 therefore invalidates the old v1.3.28 review epoch rather than silently upgrading it.
- No recovery/UAC proof, parity audit, GitHub-hosted CI proof or upstream release discovery authorizes Windows production certification, target-evidence import or score mutation.

## Change policy

- Do not rewrite frozen v25.74 manifests merely to rename historical product strings.
- Do not claim Windows certification from synthetic/Linux/CI-only evidence.
- Do not auto-promote production scores.
- Do not force-push `main`.
- Raw runtime evidence remains immutable, digest-bound and append-only.
- Dual review and live Cockpit baseline-drift reconciliation remain mandatory.
- Source and development checkpoints live in GitHub; ChatGPT File Library is not a development source authority.

## Immediate next action

1. Keep PR #7 open/unmerged until a materialized exact-head Windows proof graph passes.
2. Treat Cockpit v1.3.29 as active upstream drift and keep the v1.3.28 production review epoch invalidated for new promotion decisions.
3. Require the P0 parity proof and device-auth source-characterization proof to execute successfully in the canonical graph; current runner-start failures are not proof results.
4. Make and record the explicit device-auth parity/capability-gap decision before baseline adoption.
5. Reconcile launch confirmation-before-mutation and session/migration safety in dedicated P1 tranches; keep larger API-service breadth in P2.
6. Only after a new frozen baseline is explicitly adopted should the authorized Windows/current-Codex canonical seven-case evidence be captured for a new review epoch.
7. Complete certificate-signed packet import, sealed reviewer authorities, dual human review and live baseline reconciliation on that new epoch.
8. Only then consider a human-authorized production evidence promotion; do not automatically mutate the current `55.2%` score.
