# HMS AI Cockpit — Continuation after v25.44

## Current milestone
v25.44 adds a bounded Smart Model Router above Project Orchestrator and Multi-Codex Team: new work can be evaluated by project, role and workload, then mapped to a compatible model/reasoning profile and a healthy account recommendation without breaking existing session affinity.

## Next recommended tranche: v25.45 Cross-PC / LAN Codex Pool
- Discover trusted HMS nodes on the LAN without exposing raw account secrets.
- Keep account credentials local to the owning workstation; exchange only capability/health/quota/routing metadata and explicit job ownership leases.
- Add project-to-node affinity, node heartbeat, capacity and circuit state.
- Support controlled handoff to another workstation only for new work; never silently steal an active sticky session.
- Fail closed on identity, certificate/trust, project-root or ownership mismatch.
- Preserve local-only mode as the default and keep the product Codex-only.

## Production path
- v25.46–v25.49: regression, Windows runtime certification, performance, failure injection and soak.
- v26.0 only after core Codex paths are RUNTIME VERIFIED and SOAK VERIFIED.
