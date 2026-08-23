# HMS v25.23.1 — Runtime Certification Runbook

## Mục tiêu

Đưa HMS từ `FEATURE_PARITY_CANDIDATE` sang trạng thái có bằng chứng chạy thực tế trên Windows, nhưng không phá cấu hình Codex/Cockpit đang hoạt động.

## Trình tự bắt buộc

### Gate 1 — ALL_READY

Chạy `01_BAT_DAU_CHAY_HMS_V25_23_1.bat` → **KIỂM TRA ALL READY**.

Nó thực hiện:

1. private local snapshot;
2. Windows/Python/CLIProxy inventory;
3. release manifest/hash;
4. PowerShell 5.1 parser gate;
5. web smoke;
6. SSE/WebSocket protocol smoke;
7. Proxy Affinity synthetic;
8. Proxy Fleet synthetic;
9. API Superset synthetic;
10. Cockpit/port coexistence scan.

Không start router.

### Gate 2 — PORT_PROFILE

Wizard → **ÁP DỤNG PORT AN TOÀN**.

Chỉ cập nhật `%LOCALAPPDATA%\HMS_AI_MultiRouter\settings-v250.json`.

Safe defaults vẫn được giữ:

- `AutoEnable=false`
- `SmartGatewayAutoStart=false`
- `ProxyFleetAutoRecovery=false`
- `PolicyKernelMode=OBSERVE`

Nếu `8317` có listener, HMS không chiếm port đó và chọn port trống khác.

### Gate 3 — UI_SMOKE

Mở/đóng UI có kiểm soát để phát hiện lỗi WinForms/runtime binding.

### Gate 4 — ROUTER_SMOKE

Có operator confirmation.

Gate này có thể start/stop **router do HMS sở hữu**. Ownership mismatch/foreign PID phải BLOCK.

### Gate 5 — SAFE_RUNTIME

Chạy runtime validator an toàn sau khi router smoke PASS.

Khi cả năm checkpoint đều PASS:

```text
ALL_READY     PASS
PORT_PROFILE  PASS
UI_SMOKE      PASS
ROUTER_SMOKE  PASS
SAFE_RUNTIME  PASS

RUNTIME_READY = TRUE
```

sau đó dùng `04_MO_HMS_KHI_RUNTIME_READY.bat`.

## Snapshot

Lưu tại:

```text
%LOCALAPPDATA%\HMS_AI_MultiRouter\runtime-certification-v25_23_1\snapshots
```

Snapshot có thể chứa backup riêng tư của:

- `.codex/config.toml`
- `.codex/.env`
- `CLIProxyAPI/config.yaml`
- HMS settings

Do các file này có thể chứa secret, snapshot folder được áp ACL CurrentUser + SYSTEM theo best-effort. Không gửi nguyên snapshot cho người khác.

OAuth auth JSON không được copy vào snapshot; chỉ filename/size/mtime/SHA-256 metadata.

## Coexistence với Cockpit

HMS quét:

- `8317`
- `8318`
- `8320`
- `8420–8439`

và process owner.

Không có hành vi:

- kill Cockpit;
- stop foreign CLIProxy;
- chiếm foreign listener;
- tự chuyển Codex sang HMS ở gate đầu.

## Evidence

Mỗi run:

```text
%LOCALAPPDATA%\HMS_AI_MultiRouter\runtime-certification-v25_23_1\runs\<run-id>
```

Checkpoint:

```text
checkpoint-v25_23_1.json
```

Latest:

```text
latest-v25_23_1.json
```

## Sau Runtime Ready

Thứ tự kiểm thực tế tiếp theo trong HMS UI:

1. xác nhận Codex account pool;
2. xác nhận main router/Smart Gateway;
3. gửi một request Codex thật;
4. xác nhận selected target/account;
5. chạy SSE/WebSocket client path;
6. nếu dùng proxy: add một proxy tĩnh, health + egress PASS trước;
7. chạy 2 account;
8. sau đó mới tăng 4–5 account/proxy;
9. chạy soak 1h trước 6h/24h.

## Không coi là Production Certified nếu chưa có

- request Codex thật;
- OAuth refresh thật;
- quota feed thật;
- multi-instance thật;
- proxy egress thật nếu bật proxy;
- soak thực tế.
