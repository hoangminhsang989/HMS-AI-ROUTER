# HMS v19 — Windows Runtime Gate Guide

## Lần chạy đầu tiên khuyến nghị

Chạy:

```bat
HMS_Windows_Runtime_Gate.bat
```

Batch mặc định chỉ chạy `PREFLIGHT`.

Kết quả mong muốn trước khi làm bất kỳ runtime mutation test nào:

- `host.windows_powershell = PASS`
- `source.static_lint = PASS`
- `package.manifest = PASS`
- `source.powershell_parse = PASS`
- `source.python_compile = PASS`
- `launcher.setup = PASS`

Chỉ khi 6 gate này PASS mới chuyển sang `WEB_SMOKE`.

## Thứ tự closure

1. PREFLIGHT
2. WEB_SMOKE
3. UI_SMOKE
4. SAFE_RUNTIME
5. ROUTER_SMOKE
6. QUICK_1H soak
7. STANDARD_6H
8. PROD_24H

`ROUTER_SMOKE` có thể chạy trước SAFE_RUNTIME nếu operator muốn, nhưng phải bảo đảm
port router trống và Cockpit không sở hữu port đó.

## Operator gates

Trong HMS UI, các settings mặc định:

```text
WindowsRuntimeGateOperatorMode = false
WindowsRuntimeGateAllowUiSmoke = false
WindowsRuntimeGateAllowRouterSmoke = false
WindowsRuntimeGateAllowSafeRuntime = false
```

Không bật đồng loạt trước khi PREFLIGHT PASS.

## Ownership invariant

Router smoke không được phép:

- stop listener đang tồn tại;
- chiếm port của Cockpit;
- kill PID không phải child PID do gate tạo;
- coi port-open là PASS nếu PID owner khác child PID.

## Evidence rule

Không xóa evidence của run thất bại trước khi xác định root cause.
Mỗi run dùng thư mục evidence riêng để so sánh giữa revision.
