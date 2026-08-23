# HMS v20.0 Smart Gateway

## Gap closed
Cockpit's current Codex API Service has deep request routing and per-client/account controls.
v20 establishes an HMS-owned gateway layer rather than relying only on the shared CLIProxyAPI selector.

## Delivered
- named client keys;
- per-key model policies;
- account/target priority and weight;
- model eligibility;
- session affinity;
- reset-aware optional selection;
- selected-target request trace;
- aggregated model catalog;
- target cooldown health;
- request-body privacy.

## HMS-specific extension
`reset-aware` can prioritize the eligible target whose configured quota/reset time is earliest.
This is intentionally optional; stable round-robin remains the default.

## Next closure
1. Windows v19/v20 PREFLIGHT.
2. Real CLIProxy target integration.
3. Two-account live routing test.
4. Session-affinity failover test.
5. Client-key model policy test from real Codex.
6. Streaming/SSE long response soak.
7. WebSocket compatibility layer.
8. Automatic isolated target projection with explicit operator opt-in and backup/ACL.
