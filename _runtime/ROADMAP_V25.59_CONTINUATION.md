# HMS AI Cockpit — Continuation after v25.59

## v25.60 — Recovery Transaction Journal & Crash-Consistent Resume

Priority after the v25.59 P0 auth-compatibility freeze.

- Hash-chained recovery transaction journal.
- PREPARE → COMMIT → VERIFY → ROLLBACK state machine.
- Crash injection at every transaction boundary.
- Idempotent resume: no duplicated restart, auth mutation, config repair or lease reelection.
- Recovery ownership/epoch fencing and bounded retry budget.
- Journal corruption/torn-write detection and fail-closed recovery.
- Deterministic simulation/model-check evidence; no real machine required for development gates.

## Following UX track

Continue Native Usage & Token Center work after the recovery-journal gate, including prominent 5-hour/weekly reset countdowns, absolute reset timestamps, reserve/freshness/route eligibility and subscription/package-expiry display where trustworthy upstream metadata exists.
