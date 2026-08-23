# HMS v22.0 Proxy Affinity & Egress Control

## Delivered

- proxy profile registry;
- HTTP / HTTPS / SOCKS5 profiles;
- DPAPI CurrentUser secret store;
- stable N-account -> 1-proxy assignment;
- default 5 accounts/proxy;
- STRICT / STICKY_FAILOVER / DIRECT_FALLBACK policy model;
- system-wide direct fallback disabled by default;
- HTTP CONNECT / SOCKS5 health checker;
- isolated CLIProxyAPI sidecar generation;
- versioned projected auth directories;
- global proxy-url per sidecar;
- sidecar PID/port ownership verification;
- Smart Gateway proxy-group target projection;
- Unified UX safe proxy-group status;
- Windows Runtime Gate PROXY_SMOKE;
- synthetic proxy validator.

## Why sidecars

A proxy placed only between HMS Smart Gateway and a local CLIProxyAPI process does not change
the network path of CLIProxyAPI -> upstream. v22 therefore makes the proxy enforcement point
the isolated CLIProxyAPI sidecar itself.

Each proxy group gets:
- its own local port;
- its own auth projection;
- its own global proxy-url;
- its own session-affinity pool.

## Default policy

```text
ProxyAffinityMode = STRICT
ProxyAccountsPerProxy = 5
ProxyDirectFallbackAllowed = false
ProxyHealthRequiredBeforeStart = true
```

## Next runtime closure

1. Windows PowerShell parser.
2. Add one real paid/static VN proxy.
3. Health PASS.
4. Assign 2 test accounts.
5. Start one sidecar.
6. Verify sidecar public outbound IP manually/provider-side.
7. Run Codex request through Smart Gateway.
8. Verify selected group/account trace.
9. Stop proxy service and confirm STRICT block/no direct fallback.
10. Expand to 4-5 accounts per proxy.
