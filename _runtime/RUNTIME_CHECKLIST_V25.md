# HMS v25.23.1 Runtime Checklist

| Stage | Required | Mutation level | PASS condition |
|---|---:|---|---|
| ALL_READY | Yes | Read-only + private snapshot | inventory/parse/synthetic/coexistence PASS |
| PORT_PROFILE | Yes | HMS settings only | safe free ports saved |
| UI_SMOKE | Yes | UI lifecycle only | UI opens/closes cleanly |
| ROUTER_SMOKE | Yes | HMS-owned start/stop | ownership verified |
| SAFE_RUNTIME | Yes | safe validator | no FAIL/BLOCKED |
| Real Codex request | Next | controlled | selected target confirmed |
| Real proxy egress | If proxy used | network | expected IP PASS |
| 1h soak | Next | observation | no critical findings |
| 6h/24h soak | Final | observation | production certificate candidate |
