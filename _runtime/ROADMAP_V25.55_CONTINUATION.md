# HMS AI Cockpit v25.55 — continuation roadmap (Codex-only)

## Current decision
Real hardware remains optional for development. v25.55 establishes a large-pool autonomous-router digital twin plus bounded state-machine checking. Real target evidence is still required only for the final production label.

## v25.56 — Protocol Chaos / API Compatibility Fuzzer
- Structured malformed SSE/WebSocket/JSON/error/retry streams.
- Partial frame, duplicate event, reordered metadata, early EOF, timeout and reconnect sequences.
- Fuzz API compatibility without ever persisting prompt/tool arguments/request bodies.
- Preserve session affinity, retry budgets and OpenAI-compatible error surfaces.

## v25.57 — Recovery Planner & Self-Healing Decision Proof
- Simulate candidate remediation before applying it.
- Action budgets, blast-radius score, rollback proof and explicit destructive-action denial.

## v25.58 — Large Pool / Project Graph Scale Lab
- 10/25/50/100 accounts and 2/8/16/32 instances.
- Graph-level project affinity, queue fairness, starvation, recovery-storm and shard rebalance checks.

## v25.59 — Release Candidate Superset Audit
- Re-run Cockpit parity matrix and all HMS-only extensions.
- No production-superset claim without v25.53 real target evidence.

## v26.0
Production Superset label remains conditional on real target evidence. Development does not require a real machine.
