# Third-party references — HMS v24

## Cockpit Tools

Used only as a public behavioral/product comparison baseline.

Reviewed 2026-08-19:
- release workflow showing v1.3.16;
- current README;
- current `docs/CODEX_API_SERVICE_HANDOFF.md`;
- public Codex API Service release history.

HMS does not copy Cockpit source code, assets, branding, secrets or private implementation details.

## CLIProxyAPI

HMS uses isolated CLIProxyAPI sidecars.

Current upstream documentation confirms support for:
- custom config path via `--config`;
- `auth-dir`;
- global `proxy-url`;
- HTTP / HTTPS / SOCKS5;
- routing session affinity and TTL;
- streaming keepalive/bootstrap retry configuration.

HMS v24 adds its own control-plane policy above CLIProxyAPI. It does not claim that every HMS
routing policy is implemented by upstream CLIProxyAPI itself.

## ipify

Default optional Proxy Fleet public egress probe:
  https://api.ipify.org?format=json

This URL is configurable. HMS Egress Guard does not use an unproxied/direct fallback.

## OpenAI / Codex

Real Codex client behavior, account quota fidelity, OAuth refresh, images and profile takeover
remain target-runtime gates. v24 synthetic validation does not replace those real-client checks.
