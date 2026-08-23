# HMS AI Cockpit — continuation after v25.58

## v25.59 — Recovery Transaction Journal & Crash-Consistent Resume
Goal: make multi-step recovery plans crash-consistent across process restarts without replaying already-committed mutations.

Planned gates:
- append-only recovery transaction journal with hash chain;
- prepare/commit/verify/rollback state per DAG node;
- idempotent resume after crash between mutation and verification;
- no duplicate restart/config repair/lease reelection after resume;
- corrupted journal fail-closed + operator recovery;
- deterministic crash-point injection across every transition;
- synthetic-only claim boundary preserved.
