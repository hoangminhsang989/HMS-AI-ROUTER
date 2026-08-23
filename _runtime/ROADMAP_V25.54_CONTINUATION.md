# HMS AI Cockpit v25.54 — continuation roadmap (Codex-only)

## Current decision
Real hardware is no longer a blocker for continued product development. HMS continues through progressively stronger deterministic simulation, model checking, security hardening and compatibility gates. The v25.53 target-machine runner remains available only as the final real-production evidence gate.

## v25.55 — State-Machine Model Checking & Trace Minimization
- Explore bounded state combinations for quota freshness/reserve, account health, session affinity, cooldown, lease epoch and process generation.
- Assert safety properties across transitions, not just random scenarios.
- Automatically minimize a failing event trace to the shortest reproducible sequence.
- Persist replay seed + minimized trace hash only; never credentials/request bodies.

## v25.56 — Protocol Chaos / API Compatibility Fuzzer
- Structured malformed SSE/WebSocket/JSON/error/retry sequences.
- Partial frame, duplicate event, reordered metadata, early EOF, timeout and reconnect cases.
- Preserve frozen API compatibility and session-affinity invariants.

## v25.57 — Recovery Planner & Self-Healing Decision Proof
- Simulate remediation choices before applying them.
- Add action budgets, blast-radius scoring and rollback proof.
- Fail closed for destructive or credential-affecting actions.

## v25.58 — Large Pool / Project Graph Scale Lab
- 10/25/50/100 account synthetic pool.
- 2/8/16/32 instance synthetic topology.
- project affinity graph, queue fairness, starvation and recovery-storm checks.

## v25.59 — Release Candidate Superset Audit
- Re-run Cockpit parity matrix and all HMS-only extensions.
- No production-superset claim without v25.53 real target evidence.

## v26.0
Production Superset label remains conditional on real target evidence. Development of v25.55+ does not require it.
