# HMS AI Cockpit — Continuation after v25.39

## Next tranche: v25.40 Security Hardening

Goal: harden Codex-only credential/config/runtime security without adding more provider breadth.

Target work:
- move local sensitive HMS secrets toward Windows-native protected storage where feasible;
- reduce plaintext secret lifetime in process/environment/log surfaces;
- tighten ACL checks for instance roots, auth snapshots, settings and evidence;
- add secret-leak regression scanner across diagnostics/evidence/update packages;
- signed update/release verification hardening and rollback evidence;
- tamper detection for instance binding/config/pool manifests;
- explicit security posture page in GUI;
- keep Self-Healing fail-closed when security invariants are violated.

Hard invariants:
- Codex-only scope;
- no destructive delete action;
- no cross-account/project mutation;
- no secret logging;
- no killing unowned processes;
- stable endpoint and session affinity preserved;
- every security repair produces evidence + readback + rollback path.

Acceptance levels remain IMPLEMENTED -> STATIC VERIFIED -> SYNTHETIC VERIFIED -> RUNTIME VERIFIED -> SOAK VERIFIED.
