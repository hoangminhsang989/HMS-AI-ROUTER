# HMS AI Cockpit v25.49 — Real Codex Certification Runbook

## Điều kiện trước khi chạy
- Windows có Windows PowerShell 5.1.
- Codex CLI/Desktop đang cài và `codex --version` hoạt động.
- Đã tạo tối thiểu 2 managed Codex instances trong HMS.
- Hai instance có project, CODEX_HOME, account identity và port tách biệt.
- API key của instance được lưu bằng cơ chế credential hiện có của HMS.

## Cách chứng nhận
1. Mở HMS → LAN Pool → `REAL CODEX CERTIFICATION v25.49`.
2. Nhấn `KIỂM TRA`.
   - Không gửi request model.
   - Không tiêu quota.
   - Kỳ vọng khi mọi preflight đều đạt: `READY_LIVE_REQUEST_REQUIRED`.
3. Nhập đúng model muốn kiểm tra.
4. Nhấn `LIVE 1` và xác nhận hộp thoại.
   - HMS chỉ cho phép đúng 1 live request từ GUI.
   - Request dùng fixed minimal prompt và response body không được persist.
5. PASS cuối phải là `PASS_REAL_CODEX_CERTIFIED`.
6. Evidence local nằm dưới `%LOCALAPPDATA%\HMS_AI_MultiRouter\real-codex-cert-v2549`.

## Tiêu chí PASS live
- Windows PowerShell 5.1 parser/runtime gate PASS.
- Codex capability/login status PASS.
- >=2 managed instance topology PASS.
- `/hms/health` của instance PASS.
- Process generation guard PASS.
- Live `/v1/responses` request PASS.
- Có exact `response.output_text.delta`; đây mới là model token TTFT.
- Không có raw API key/token/prompt/response body trong evidence.

## Fail-safe
Nếu thiếu bất kỳ điều kiện authoritative nào, verdict không được là `PASS_REAL_CODEX_CERTIFIED`.
