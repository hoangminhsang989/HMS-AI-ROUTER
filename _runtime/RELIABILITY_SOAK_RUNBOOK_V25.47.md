# HMS AI Cockpit v25.47 — Reliability / Soak Runbook

## Mục tiêu
Chứng minh Router + multi-instance + shared LAN hoạt động bền trong thời gian dài, có checkpoint/resume và không PASS giả khi tiến trình bị dừng.

## Cách chạy khuyến nghị
Dùng trang **LAN Pool** trong Native GUI:
- `SMOKE`: kiểm tra nhanh harness.
- `6H`: profile cố định 21,600 giây active.
- `24H`: profile cố định 86,400 giây active.
- `DỪNG`: tạo stop request, checkpoint và PAUSE; không force-kill.
- `TIẾP TỤC`: chạy lại đúng run hiện tại từ active time đã tích lũy.

## Gate bắt buộc cho 6H / 24H
Một run 6H/24H không thể PASS nếu thiếu bất kỳ điều kiện nào:
1. Global Router target trả lời đúng `GET /hms/health` với HTTP 200 + JSON `ok=true`.
2. Ít nhất 2 managed Codex instance target khác nhau, mỗi target cũng phải PASS `/hms/health`.
3. Shared SMB/NAS path.
4. Active elapsed time đạt đúng profile; `--duration-sec` không được phép rút ngắn profile 6H/24H.
5. Coverage tối thiểu của Router, instances, shared roundtrip, LAN heartbeat và lease.
6. Không có recovery exhausted / recovery-budget violation còn hiệu lực.

## Resume semantics
`active_elapsed_sec` chỉ tăng khi harness process đang sống. Khoảng thời gian máy tắt, app bị crash hoặc harness không chạy không được cộng vào soak. Một partial checkpoint luôn là `IN_PROGRESS`/`PAUSED`, không bao giờ được xem là PASS.

## Fault / recovery coverage
Synthetic validation đi kèm kiểm tra:
- transient SMB disconnect + bounded retry;
- signed heartbeat;
- lease owner renew;
- foreign-node silent takeover bị block;
- lease churn qua explicit release/acquire;
- node disconnect -> STALE;
- node rejoin -> ONLINE;
- duplicate live soak lock bị block;
- dead-process lock được reclaim để resume;
- cooperative stop + resume.

## Evidence
Mặc định nằm tại `%LOCALAPPDATA%\HMS_AI_MultiRouter\reliability-soak-v2547`:
- `soak-checkpoint-v2547-<run>.json`
- `soak-result-v2547-<run>.json`
- `soak-events-v2547-<run>.jsonl`
- `soak-process-v2547-<run>.log`

Evidence không lưu raw OAuth token, API key, cookie, prompt/request body, pairing code hoặc pairing key. Shared path chỉ được lưu dạng SHA-256 trong checkpoint/result.

## Giới hạn chứng nhận
PASS của harness một máy chỉ chứng minh **single-node duration + target probes**. Nó không tự động chứng nhận production, không thay thế Windows PowerShell 5.1/Codex runtime thật và không thay thế real multi-PC SMB/NAS contention/failover gate.
