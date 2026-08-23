# Cockpit baseline reviewed 2026-08-19

Sources reviewed:
- GitHub release workflow: v1.3.16 release run visible.
- current README.
- current docs/CODEX_API_SERVICE_HANDOFF.md.
- release history for Codex API Service.

Observed current Codex baseline includes:
- bundled CLIProxyAPI sidecar;
- managed profile projection/restore;
- `/v1/models`, chat completions, Responses/compact;
- `/backend-api/codex/*` and Responses WebSocket;
- image generations/edits;
- named client keys and model policies;
- auto/random/single/quota/plan/expiry/custom priority/weight/backup routing;
- session affinity, health/cooldown and bounded retry;
- quota reserve fail-closed;
- account/model/key usage logs and statistics;
- pricing / estimated value;
- image concurrency controls;
- session visibility repair including `state_5.sqlite`;
- Codex multi-instance.

This file records only the comparison baseline. It does not copy Cockpit source code or assets.
