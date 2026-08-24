# HMS-AI-ROUTER — Project State v25.75

Date: 2026-08-24
Status: ACTIVE DEVELOPMENT — REAL WINDOWS/CURRENT-CODEX EVIDENCE GATE
Authority: `main` on `hoangminhsang989/HMS-AI-ROUTER`

## Baseline

- Migration baseline: v25.74
- Frozen Cockpit Tools parity authority for current v25.75 P0: v1.3.28
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

## Current v25.75 P0 state

The source-side external Windows evidence path now includes:

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

Latest detailed authority checkpoint:

`docs/V25.75_P0_AUTHORITY_DIAGNOSTICS_CHECKPOINT.md`

## Reviewer authority operational rules

- Reviewer authority default freshness window remains 24 hours.
- Renewal must recapture from the approved reviewer trust store; never edit timestamps or reseal an old body merely to extend validity.
- Certificate rotation/revocation must update the approved trust authority through the independent approval path before new packets are accepted.
- Reviewer local integrity keys are bound to Windows DPAPI CurrentUser and must not be copied to another Windows user or machine to bypass reviewer identity/context.
- `reviewer-authority-status` is read-only and never recaptures authority, imports a packet, mutates trust state, signs evidence, executes live Codex or changes production score.

## Verification boundary

- Source/synthetic proof infrastructure is not real Windows/current-Codex production evidence.
- The orchestrator source contract is now function-scoped to avoid its previous self-matching false negative.
- The current GitHub connector still exposes no combined status entries or workflow runs for the latest push; an unobserved Windows Actions run is therefore not claimed PASS.

## Change policy

- Do not rewrite frozen v25.74 manifests merely to rename historical product strings.
- Do not claim Windows certification from synthetic/Linux/CI-only evidence.
- Do not auto-promote production scores.
- Do not force-push `main`.
- Raw runtime evidence remains immutable, digest-bound and append-only.
- Dual review and live Cockpit baseline-drift reconciliation remain mandatory before production evidence promotion.
- Source and development checkpoints live in GitHub; ChatGPT File Library is not a development source authority.

## Immediate next action

1. Observe/remediate the Windows promotion-safety workflow when GitHub exposes a run for the current main graph.
2. Execute the actual authorized Windows/current-Codex seven-case target evidence only on the target Windows machine.
3. Import the resulting certificate-signed packet through sealed reviewer authority.
4. Complete required dual human review and baseline reconciliation.
5. Only then evaluate a human-authorized production-evidence promotion proposal; do not mutate the current `55.2%` production evidence score automatically.
