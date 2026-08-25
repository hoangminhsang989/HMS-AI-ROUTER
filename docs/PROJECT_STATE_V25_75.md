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

The integrated wrapper-chain proof now additionally locks launcher → recovery wrapper → reviewer wrapper → guarded promotion entry → legacy core ordering and requires recovery/reviewer method patch sets to remain disjoint.

## Cockpit Tools v1.3.29 parity drift

Upstream v1.3.29 introduces material Codex deltas. Confirmed from upstream changelog/source:

- device-code authorization in addition to browser callback OAuth;
- OAuth scopes add `api.connectors.read` and `api.connectors.invoke`;
- ID-token refresh lead changes from 15 to 10 minutes;
- quota refresh may use a valid access token without rotating an official-client-owned refresh token; previous quota is retained while waiting for a newer access token instead of converting the condition into account failure;
- combined OAuth/API-Key profiles retain actual OAuth credential ownership and latest official-client-rotated tokens to avoid stale `refresh_token_reused` behavior;
- unified launch preview with explicit confirmation before client state change;
- expanded session repair/provider migration/catalog repair;
- expanded Codex API Service including Live/Realtime and additional request transports/features.

Priority before a new production evidence epoch:

1. quota/refresh-token ownership semantics;
2. combined-profile OAuth credential ownership and stale-token reuse prevention;
3. device-auth/OAuth-scope contract;
4. launch confirmation-before-mutation invariant;
5. remaining session/API-service parity work in dedicated tranches.

Do not simply change `COCKPIT_BASELINE` from `1.3.28` to `1.3.29`. Baseline adoption requires explicit delta reconciliation and a new proof/review epoch.

## Observed Windows CI proof graph

Historical complete source/synthetic walking-gate PASS remains valid only for the exact tested historical source:

- Run #67
- Run ID `32691345325`
- Job ID `97325459363`
- Tested head `3c78208d5f0a894e11ea2e2ec804137888c1b5a3`
- Microsoft Windows Server 2025 / Python 3.12.10
- all 36 configured steps PASS, including Windows PowerShell 5.1 guided UAC operator proof.

It does not certify the current PR #7 source or any real target.

Current integrated candidate PR #7 has repeatedly failed **before Checkout**. Latest known final-head checkpoint run:

- Run #149
- Run ID `32799771196`
- Job ID `97658208798`
- Tested head `d5dfcb39c9105502474705005ec7df05cb4698df`
- `steps = []`
- no Checkout/Setup/compile/proof step materialized.

Correct classification: **repository/account runner-start unavailable; exact cause unproven with available tooling**. This is neither a code PASS nor a code/test FAIL.

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

The historical v1.3.28 source proof also does not establish v1.3.29 parity.

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
- Final human decision records now retain source/package/reviewer-authority provenance through the append-only hash chain.
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
3. Reconcile the P0 v1.3.29 quota/refresh-token-ownership and combined OAuth/API-Key credential-ownership deltas in source/proofs.
4. Define the HMS device-code OAuth + connector-scope contract and add proof coverage before baseline adoption.
5. Reconcile launch/session/API-service deltas in dedicated tranches rather than mixing them into production evidence claims.
6. Only after a new frozen baseline is explicitly adopted should the authorized Windows/current-Codex canonical seven-case evidence be captured for a new review epoch.
7. Complete certificate-signed packet import, sealed reviewer authorities, dual human review and live baseline reconciliation on that new epoch.
8. Only then consider a human-authorized production evidence promotion; do not automatically mutate the current `55.2%` score.
