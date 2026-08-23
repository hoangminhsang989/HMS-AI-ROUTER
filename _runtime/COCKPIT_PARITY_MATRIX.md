# Cockpit current main / v1.3.16-era vs HMS v25.47

Internal engineering self-assessment based on the public Cockpit evidence recorded by the parity auditor and HMS v25.47 build evidence.

> Important: this is an engineering evidence rubric, not an independent benchmark and not a production-superset claim.

| Area | Cockpit current | HMS v25.47 | Engineering verdict |
|---|---|---|---|
| Codex account management | Production mature | Implemented, runtime pending | Cockpit runtime edge |
| Multi-instance | Production mature | Deep architecture, runtime pending | Cockpit runtime edge |
| Hourly/weekly quota + plan | Mature | Layer exists, live fidelity pending | Cockpit runtime edge |
| Named client keys | Yes | Synthetic PASS | Near parity |
| Per-key model policy | Yes | Synthetic PASS + prefix rewrite | HMS design edge |
| Per-key target/account pool | Not core reference | Synthetic PASS | HMS design edge |
| Routing modes | Auto/random/single/quota/plan/expiry/custom | Same major families + reset-aware | Near parity |
| Priority/weight/backup | Yes | Synthetic PASS + per-key override | HMS design edge |
| Quota reserve fail-closed | Yes | Synthetic PASS | Near parity |
| Session affinity | Yes | Synthetic PASS, client-key scoped | HMS design edge |
| HTTP/SSE/WebSocket | Production | Synthetic PASS | Cockpit runtime edge |
| Image endpoints | Dedicated behavior/concurrency | Generic relay, runtime pending | Cockpit |
| CORS | Yes | Loopback allowlist, synthetic PASS | Near parity |
| Usage stats | Mature searchable UI | Day/week/month/all analytics | Near parity |
| Pricing/estimated value | Mature | Operator-managed prices + captured usage | Near parity |
| Request diagnostics | Mature | Request/target/retry/TTFT/bytes | HMS telemetry edge |
| Session visibility repair | Yes incl. state_5.sqlite | Synthetic PASS | Near parity |
| Proxy fail-closed | Yes | Strict Proxy Fleet | HMS design edge |
| Public IP drift/quarantine | Not core reference | Implemented | HMS design edge |
| HA/Soak/Policy Kernel | Not core focus | Resumable 6h/24h harness + synthetic validation + single-node live-shaped smoke; real long soak pending | HMS design edge pending proof |
| Source/runtime evidence gates | Not core focus | Implemented | HMS design edge |
| LAN cross-PC project lease | Not core comparison item | Signed heartbeat + fail-closed lease/epoch/nonce | HMS design edge pending real SMB proof |
| Production certification | Public released | Not yet | Cockpit clearly |

## v25.47 auditor result

- Feature evidence: **93.0%**
- Production evidence: **55.2%**
- HMS verdict: **FEATURE_PARITY_CANDIDATE**
- Windows runtime certified: **False**
- Runtime-pending benchmark areas: `multi_account`, `multi_instance`, `quota_plan`, `images`, `profile_takeover`

## Bottom line

HMS v25.47 is a **feature-parity candidate for the Codex control plane** with additional safety/reliability architecture. The v25.47 soak harness is validated, but the standard real 6h/24h runs have not been executed. Cockpit remains the stronger finished product until HMS passes real Windows/Codex, live quota/profile behavior, real SMB multi-PC, and those soak gates.
