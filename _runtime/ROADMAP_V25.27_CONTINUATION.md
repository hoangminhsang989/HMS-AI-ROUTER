# HMS AI Cockpit — after v25.27

## Delivered in v25.27
- Adaptive Router policy with hysteresis and guarded routing hints.
- Signed update staging pipeline with pinned RSA public key, SHA-256, manifest verification and operator activation.

## Recommended next tranche — v25.28
1. Runtime attribution feedback loop: compare adaptive recommendation vs actual selected account and learn only from confirmed routes.
2. Per-project / per-Codex-session affinity policy profiles.
3. Router event ledger for policy decision → route selected → result → quota impact.
4. Update publisher/channel tooling: stable/beta feed generator, key rotation policy, release notes preview and staged-diff view.
5. One-click self-repair: verify active release, provider config, Router ownership, Codex config backup and restore without exposing BAT files.
6. Optional system tray + notification center for quota/failover/update events.

## Runtime evidence still deferred
Real Windows Codex/Antigravity/failover/quota/hot-reload tests remain deferred by operator instruction. Fix real defects when observed.
