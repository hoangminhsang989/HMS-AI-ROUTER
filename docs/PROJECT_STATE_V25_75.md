# HMS-AI-ROUTER — Project State v25.75

Date: 2026-08-24
Status: ACTIVE DEVELOPMENT — WINDOWS RECOVERY/UAC P1 + REAL WINDOWS/CURRENT-CODEX EVIDENCE GATE
Authority: `main` on `hoangminhsang989/HMS-AI-ROUTER`

## Baseline

- Migration baseline: v25.74
- Frozen Cockpit Tools parity authority for current v25.75: v1.3.28
- Product scope: Codex-only
- Product branding: HMS-AI-ROUTER
- Historical v25.74 evidence is immutable and may retain former product branding where it is part of frozen evidence.

## Evidence boundary carried forward

- Feature evidence score: 93.0%
- Production evidence score: 55.2%
- Windows runtime certified: false
- External Windows target evidence imported: false
- Real Codex effects executed for the current source-hardening increment: false
- Windows signing executed for production evidence: false
- Automatic production certification: false
- Production score promotion eligible: false

These values MUST NOT be promoted without new real Windows/current-Codex evidence plus the required review gates.

## Current v25.75 P0 evidence-safety state

The source-side external Windows evidence path includes:

1. Exact canonical seven-case contract: `host`, `codex`, `quota`, `failover`, `lan`, `soak_6h`, `soak_24h`.
2. Certificate-only packet signing and real certificate preflight/enrollment binding.
3. Independent reviewer-side trust authority that is not packet-derived.
4. CurrentUser-DPAPI-backed reviewer local integrity sealing.
5. Sealed verified-ingest metadata and sealed replay registry.
6. Serialized ingest transactions with stale-lock fail-closed behavior.
7. Reviewer packet-import entrypoint and principal review GUI bound to sealed metadata.
8. Promotion-disabled fail-closed GUI fallback if the principal reviewer wrapper is unavailable.
9. Bounded Windows evidence orchestrator for read-only operator preflight and reviewer import.
10. Read-only `reviewer-authority-status` freshness/integrity diagnostics with `FRESH`, `RENEW_SOON` and fail-closed stale/invalid states.

Detailed P0 authority checkpoint:

`docs/V25.75_P0_AUTHORITY_DIAGNOSTICS_CHECKPOINT.md`

## Current v25.75 P1 Windows recovery state

The source-side Windows recovery tranche aligned to Cockpit Tools v1.3.28 now includes:

- classification for Access Denied / error 5 and WSAEACCES 10013, file-in-use / error 32, program-missing / error 2, `CODEX_RESTART_REQUIRED` client-close barrier, and other failures;
- retry and operator-handled-then-retry paths;
- open-location and copy-sanitized-error actions;
- sensitive-detail redaction before recovery display/copy;
- quiet background probe/health/quota/refresh behavior;
- bounded interactive backend recovery, including the normal `open_codex` backend path;
- recovery-first fail-closed launcher path preserving the sealed reviewer wrapper and promotion-disabled safe fallback;
- Codex-only one-shot UAC helper restricted to validated `Codex.exe` / `ChatGPT.exe` PIDs;
- fixed `%SystemRoot%\System32\taskkill.exe` elevation with numeric PID arguments only;
- one-shot token consumption before UAC so cancellation/failure cannot replay the same prompt epoch;
- UAC eligibility only at the stable pre-mutation `CODEX_RESTART_REQUIRED` close barrier for backend `enable` / `disable` operations;
- retry of the original backend transaction after successful elevated close so existing mutation/verifier logic remains authoritative;
- structured official-auth client lifecycle recovery derived from `CodexLaunchAfterAuthSwitch`, `RestartCodexOnSwitch` and before/after supported-client PID identity;
- read-only `get_settings` fallback when the GUI Settings page has not yet been loaded;
- official-auth UAC eligibility only when restart is requested/enabled and one or more original supported-client PIDs survive the successful auth transaction;
- exact surviving-original-PID targeting so newly launched replacement client PIDs are not killed merely because they are running;
- preservation of successful auth semantics when a post-commit UAC attempt is cancelled or fails;
- bounded real-Windows UAC recovery validation harness with separate `proof`, read-only `preflight` and explicit-acknowledgement `interactive` modes;
- same-process token replay validation after both UAC Cancel and successful supported-client close;
- guard against falsely counting a client that exited before UAC as a successful close validation;
- Windows CI compile/proof coverage for recovery contract, dialog, elevation helper, runtime validation harness, wrapper and launcher chain.

Detailed P1 checkpoints:

- `docs/V25.75_P1_WINDOWS_RECOVERY_CHECKPOINT.md`
- `docs/V25.75_P1_UAC_RECOVERY_CHECKPOINT.md`
- `docs/V25.75_P1_OFFICIAL_AUTH_LIFECYCLE_CHECKPOINT.md`
- `docs/V25.75_P1_UAC_RUNTIME_VALIDATION_HARNESS_CHECKPOINT.md`

### Remaining P1 operational gate

The source-side one-shot recovery paths and the bounded runtime validation harness are now present.

What remains is **execution on an authorized real Windows target**, not another source-only parity claim:

- run read-only `preflight`;
- observe a real UAC Cancel and same-token replay block;
- observe one real supported-client close and same-token replay block;
- verify restart-disabled/not-requested policies never offer UAC;
- verify unrelated processes remain non-elevatable;
- verify official-auth post-commit UAC failure preserves the fact that auth already committed.

These bounded recovery checks remain separate from the canonical seven-case production certification.

## Reviewer authority operational rules

- Reviewer authority default freshness window remains 24 hours.
- Renewal must recapture from the approved reviewer trust store; never edit timestamps or reseal an old body merely to extend validity.
- Certificate rotation/revocation must update the approved trust authority through the independent approval path before new packets are accepted.
- Reviewer local integrity keys are bound to Windows DPAPI CurrentUser and must not be copied to another Windows user or machine to bypass reviewer identity/context.
- `reviewer-authority-status` is read-only and never recaptures authority, imports a packet, mutates trust state, signs evidence, executes live Codex or changes production score.

## Verification boundary

- Source/synthetic proof infrastructure is not real Windows/current-Codex production evidence.
- Recovery forbidden-operation checks are scoped to implementation source so their proof expressions cannot self-match forbidden literals.
- The one-shot elevation source proof validates the Codex/ChatGPT allowlist, generic-process rejection, fixed system taskkill resolution, numeric PID-only argument construction, token replay block, UAC cancel/timeout codes and absence of generic shell elevation.
- The GUI recovery proof validates structured official-auth policy authority, backend read-only settings fallback, original-PID survival detection, new-PID success detection, restart-disabled/not-requested fail-closed behavior and preservation of committed-auth semantics after UAC failure.
- The runtime validation harness proof validates that preflight cannot call the elevated helper, interactive mode requires the exact acknowledgement before the helper call, same-token replay is checked, and a successful close requires a real UAC start plus a positive closed-PID count.
- GitHub Actions executes only the harness `proof`; CI never runs its `preflight` or `interactive` modes.
- The Windows Actions graph must still be observed independently after integration; an unavailable status record is not claimed PASS or FAIL.
- No recovery/UAC proof or bounded runtime validation authorizes Windows production certification, external target-evidence import or production-score mutation.

## Change policy

- Do not rewrite frozen v25.74 manifests merely to rename historical product strings.
- Do not claim Windows certification from synthetic/Linux/CI-only evidence.
- Do not auto-promote production scores.
- Do not force-push `main`.
- Raw runtime evidence remains immutable, digest-bound and append-only.
- Dual review and live Cockpit baseline-drift reconciliation remain mandatory before production evidence promotion.
- Source and development checkpoints live in GitHub; ChatGPT File Library is not a development source authority.

## Immediate next action

1. Integrate the bounded UAC runtime validation harness to `main` by fast-forward only if branch ancestry remains linear.
2. Observe/remediate the Windows promotion-safety workflow when GitHub exposes the integrated push run.
3. Execute the harness `preflight` and the two bounded interactive UAC validation outcomes on the authorized Windows target; keep their reports separate from production evidence.
4. Verify restart-disabled/not-requested and unrelated-process rejection behavior on the target.
5. Execute the actual authorized Windows/current-Codex canonical seven-case target evidence only after the bounded recovery gate is understood.
6. Import the resulting certificate-signed packet through sealed reviewer authority, complete dual human review and baseline reconciliation, then and only then evaluate any human-authorized production-evidence promotion proposal.
