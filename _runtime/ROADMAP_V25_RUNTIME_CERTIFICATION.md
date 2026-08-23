# HMS v25.23.1 — Windows Runtime Certification

## Freeze

Không thêm subsystem lớn trước khi hoàn thành runtime closure.

## Phase A — First-run gates

1. ALL_READY
2. PORT_PROFILE
3. UI_SMOKE
4. ROUTER_SMOKE
5. SAFE_RUNTIME

Kết quả mong muốn: `RUNTIME_READY=true`.

## Phase B — Real Codex minimum

Sau RUNTIME_READY:

1. mở HMS;
2. kiểm pool auth thật;
3. start router/Smart Gateway có chủ đích;
4. gửi 1 request Codex thật;
5. xác minh selected account/target;
6. xác minh session affinity;
7. ép một upstream unavailable và kiểm failover;
8. kiểm SSE/Responses WebSocket với client thật.

## Phase C — Quota and profile

- đọc quota hourly/weekly thật;
- plan recognition thật;
- refresh/auth lifecycle;
- profile backup/takeover/restore;
- session visibility repair thật.

## Phase D — Proxy

Chỉ khi có proxy thật:

- add 1 static/sticky proxy;
- health PASS;
- egress IP baseline PASS;
- 2 accounts first;
- proxy offline/drift -> fail-closed;
- sau đó 4–5 accounts/proxy.

## Phase E — Multi-instance

- 2 isolated instances;
- separate project roots;
- separate account/group routing;
- no cross-project contamination;
- session/history visibility.

## Phase F — Soak

- 1h
- 6h
- 24h

Chỉ sau đó mới cân nhắc `PRODUCTION_PARITY_CANDIDATE`.
