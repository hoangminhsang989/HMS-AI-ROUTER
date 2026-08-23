# HMS AI Cockpit — continuation after v25.48

## v25.49 — Real Codex Certification

Goal: convert the strongest remaining IMPLEMENTED_PENDING_RUNTIME items into real target-machine evidence without weakening the frozen public contract.

- Windows PowerShell 5.1 parse/runtime gate on the target PC.
- Detect and certify the currently installed Codex CLI/Desktop versions without a brittle hard-coded version allowlist.
- Verify latest Codex authentication/profile behavior and account switching against real Codex, including protected auth state and restart-generation guard.
- Real Router + >=2 managed Codex instances with project affinity and no cross-project ownership conflict.
- Real quota-backed request-path exercise with explicit operator budget/cap.
- Measure real model token TTFT separately from v25.48 control-plane TTFB; never infer one from the other.
- Verify Responses/streaming/WebSocket compatibility on the real client path.
- Real account lifecycle: healthy -> quota/cooldown -> alternate account -> recovery, with no silent takeover.
- Keep public BackendAction exact 90 unless a separately versioned compatibility decision explicitly changes it.

## v25.50 — Live Quota Intelligence

- Cross-check hourly/weekly quota freshness against live account state.
- Reserve thresholds, stale-quota fail-closed behavior and per-plan normalization.
- Rotation decisions must use current quota evidence, not service-start snapshots.
- Free/Plus/Pro account eligibility and project/account affinity policies.

## v25.51 — Seamless Rotation Torture Test

- Long sticky sessions while accounts approach quota/cooldown thresholds.
- Rotation under concurrency, stream retry and reconnect storms.
- No client restart unless the real Codex client contract requires it.
- Prove no lost project affinity, duplicate ownership or request replay amplification.

## v25.52 — UX / Cockpit Parity+

- High-density Codex-only dashboard polish.
- Account/quota/instance/project/router/health surfaces unified.
- Guided remediation and one-click diagnostics/evidence export.
- Reduce operator settings to advanced popovers while retaining full observability.

## v26.0 — Production Superset Candidate

Release only after real Windows/Codex evidence, multi-PC LAN/SMB evidence and standard soak gates pass. Feature evidence or synthetic benchmark results alone are insufficient.
