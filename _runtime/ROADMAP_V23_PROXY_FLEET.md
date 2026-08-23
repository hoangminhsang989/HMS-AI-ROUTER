# HMS v23.0 — Proxy Fleet Supervisor & Egress Integrity

## Delivered

- `HMS_Codex_EgressGuard.py`
- `HMS_Codex_ProxyFleet.py`
- `HMS_Codex_ProxyFleetValidator.py`
- Proxy Fleet Center
- public-IP baseline and drift detection
- evidence staleness gates
- ACTIVE / DRAINING / QUARANTINED / DISABLED
- fleet recommendations/action budget
- restrictive auto-quarantine
- optional owned-sidecar auto-recovery
- CSV/JSON/TXT import
- Smart Gateway config hot reload
- session-affinity pruning on removed target
- Unified UX egress/quarantine visibility
- Windows Runtime Gate `PROXY_FLEET_SMOKE`

## Invariants

1. Proxy group is not route-eligible unless ops state is ACTIVE.
2. STRICT routing requires current health PASS.
3. STRICT routing requires current egress PASS.
4. Stale PASS evidence is not treated as healthy.
5. Egress drift cannot silently fall back to DIRECT.
6. Quarantine removes target from new routing without killing foreign processes.
7. Smart Gateway hot reload removes affinity to targets no longer present.
8. Auto recovery is OFF by default.

## Real-network closure

1. Add one static/sticky VN proxy.
2. Run Health and Egress probe.
3. Record baseline IP.
4. Start one sidecar with 2 accounts.
5. Verify provider-side/public egress IP.
6. Route Codex through Smart Gateway.
7. Force proxy IP change/offline.
8. Confirm DRIFT/FAIL -> target removed from route.
9. Confirm no direct fallback.
10. Repeat with 4–5 accounts/proxy.
