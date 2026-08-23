# HMS AI Cockpit — Continuation after v25.37

## Next tranche: v25.38 Full Codex API Compatibility

Goal: make the stable HMS endpoint behave as a robust Codex-facing compatibility layer, not only an account router.

Target surfaces:
- `/v1/models`
- `/v1/responses`
- streaming / SSE continuity
- tool calls
- MCP-related request paths used by Codex
- web/search request compatibility where supported by the upstream runtime
- image input where supported
- structured output / JSON-schema paths where supported
- consistent error mapping and redaction

Hard invariants carried forward:
- Codex-only scope
- stable per-instance endpoint
- Project Affinity and session affinity
- Identity Isolation fail-closed
- Circuit Breaker / Predictive Quota / Account Analytics / Closed-loop policy
- no secret logging
- no destructive delete action

Acceptance levels:
1. IMPLEMENTED
2. STATIC VERIFIED
3. SYNTHETIC VERIFIED
4. RUNTIME VERIFIED on Windows Codex
5. SOAK VERIFIED

Until real Windows validation is run, compatibility claims must remain IMPLEMENTED/STATIC/SYNTHETIC only.
