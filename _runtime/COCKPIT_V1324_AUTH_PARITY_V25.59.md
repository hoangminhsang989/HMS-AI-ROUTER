# HMS v25.59 — Cockpit Tools v1.3.24 Auth Parity

P0 compatibility scope: `CODEX_HOME/auth.json`, file/keyring/auto store resolution, pre-switch current-auth snapshot, serialized switching, stale credential/account identity cleanup, field-preserving rewrite, readback verification/rollback, Cockpit v1.3.24 OAuth originator `codex_vscode` plus version-derived Codex User-Agent, and controlled Codex App restart after verified commit.

This release uses deterministic fixtures and does **not** claim live Codex/Windows production certification.

- Encrypted `secret_auth_storage` / Secrets backend is detected and fails closed for mutation until an official Codex helper is available.
- Native Account Center exposes confirmed `CHUYỂN AUTH` without extending the frozen public BackendAction contract.
