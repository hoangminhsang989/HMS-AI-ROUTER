# HMS AI Cockpit — continuation after v25.47

## v25.48 — Performance & Scale

Goal: quantify the cost and saturation limits of the Codex-only control plane without weakening v25.47 reliability gates.

- Router latency/TTFT overhead under concurrency.
- Per-instance throughput, queue depth and backpressure observability.
- SQLite/event-log I/O cost and bounded retention behavior.
- LAN registry/lease contention with multiple nodes and projects.
- Reconnect storm / retry amplification protection.
- GUI polling/render overhead while multiple instances and soak telemetry are active.
- Stress profiles with deterministic machine-readable evidence and no production claim from synthetic-only results.
- Preserve exact v25.46 public BackendAction contract unless a separately versioned compatibility decision explicitly changes it.

## v25.49 — Release Candidate Hardening

- Real Windows PowerShell 5.1 certification.
- Real Codex CLI/Desktop compatibility matrix.
- Real multi-account / multi-instance / profile takeover checks.
- Real SMB/NAS multi-PC lease/failover exercises.
- Execute standard 6H soak; investigate every unresolved outage/recovery-budget violation.
- Execute standard 24H soak only after 6H gate passes.
- Installer/upgrade/rollback, diagnostics, redaction and clean-machine verification.

## v26.0 — Production Candidate

Release only if all critical runtime evidence gates are PASS. A feature-evidence score alone is insufficient. Production/superset language remains prohibited until Windows/Codex, multi-PC LAN and standard soak evidence are all certified.
