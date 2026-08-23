# HMS AI Cockpit v25.56 — continuation roadmap (Codex-only)

## Current decision
Real hardware remains optional for development. v25.56 hardens the Smart Gateway against malformed/partial protocol behavior and fuzzes compatibility deterministically.

## v25.57 — Recovery Planner & Self-Healing Decision Proof
- Simulate remediation candidates before execution.
- Bounded action budget, blast-radius score, rollback proof and explicit destructive-action denial.
- Prove recovery does not violate project/session affinity or quota fail-closed rules.

## v25.58 — Large Pool / Project Graph Scale Lab
- 10/25/50/100 accounts and 2/8/16/32 instances.
- Graph affinity, queue fairness, starvation, recovery storm and shard rebalance checks.

## v25.59 — Release Candidate Superset Audit
- Re-run Cockpit parity matrix plus all HMS-only extensions.
- No production-superset claim without v25.53 real target evidence.

## v26.0
Production Superset label remains conditional on real target evidence; development continues without a real machine.
