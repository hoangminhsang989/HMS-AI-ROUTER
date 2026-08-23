HMS-AI-ROUTER COCKPIT v25.12 — UCC + LIVE FAILOVER HOTFIX

Sửa lỗi Unified Command Center New-StatCardROUTER20 và thêm live failover certification có rollback.

Sau khi runtime certification PASS:
  UNIFIED COMMAND CENTER -> Advanced -> FAILOVER TEST

Test không xóa credential. Nó tạm disable đúng 1 account, gửi 1 request nhỏ, xác minh account khác qua Request Log, rồi restore trong finally.

Entry:
  01_BAT_DAU_CHAY_HMS_V25_12.bat


=== v25.24 ===
Native GUI là luồng sử dụng chính. Automation nền cốt lõi được chạy từ GUI; các BAT chỉ còn là diagnostic/recovery. Xem CHANGELOG_V25.24.txt.

=== v25.30 ===
Codex-only Seamless Router: mỗi managed instance giữ endpoint cố định, Project Affinity primary/fallback nằm phía sau Router, có session affinity, SHA-256 pool manifest và SYNC ROUTER ngay trong GUI. Real Windows failover/no-restart vẫn deferred theo operator.

=== v25.31 ===
Codex-only Closed-loop Router: Usage Ledger 1h/24h/7d + quota/health feedback được dùng để xếp hạng account theo từng managed instance. OBSERVE là mặc định; GUARDED_AUTO mới ghi priority/weight. Stable endpoint, project binding và session affinity không đổi. Real Windows closed-loop/failover vẫn deferred theo operator.

=== v25.34 ===
Advanced Quota Center Codex-only: SQLite history 5h/7d, reset timeline, source freshness FRESH/AGING/STALE/UNKNOWN, additional quota windows khi upstream cung cấp và forecast accuracy MAE/bias. Live quota luôn authoritative; Quota Center không lưu prompt/OAuth/API key và không sửa credential/session/project/endpoint.

=== v25.35 ===
Account Analytics Codex-only: quality score có confidence/trend theo account, ma trận Account × Model / Workload, SQLite snapshot dài hạn và bounded signal ±8 điểm cho Closed-loop Router. Không lưu prompt/body/OAuth/API key/cookie; Circuit Breaker và session affinity vẫn authoritative.

=== v25.36 ===
Codex Identity Isolation Hardening: fingerprint SHA-256 riêng cho từng managed instance; prelaunch audit fail-closed cho CODEX_HOME/app-data/Router/config/binding/project/account/port; phát hiện cross-instance path/project/port collision; native GUI có AUDIT ISOLATION. Fingerprint không chứa OAuth/API key/cookie. Real Windows Codex runtime vẫn deferred theo operator.

=== v25.37 ===
Codex Model & Reasoning Manager: policy theo Project → Model → Reasoning → Profile; live /v1/models discovery từ Router/managed instance; apply chỉ vào isolated config.toml và giữ nguyên hms_instance_router + stable endpoint. Có backup/readback, secret-free policy, Account Analytics advisory theo model và prelaunch apply khi policy đã cấu hình. Identity Isolation v25.36 vẫn là hard gate. Real Windows Codex model/reasoning runtime vẫn deferred theo operator.

=== v25.38 ===
Full Codex API Compatibility: Smart Gateway hỗ trợ compatibility contract, /v1/models, /v1/responses, /v1/chat/completions, streaming/SSE, tool calls, MCP/web_search, image/file input, structured output/reasoning, chunked request và PATCH. Gateway error chuẩn hóa theo OpenAI-shaped object; upstream error/body giữ nguyên; telemetry chỉ lưu capability labels, không lưu prompt/body. Native GUI có API Compat + AUDIT API. Real Windows Codex compatibility vẫn deferred theo operator.

=== v25.39 ===
- Thêm Codex Self-Healing: audit + sửa an toàn ngay trong GUI.
- Evidence trước/sau sửa, readback và rollback.
- Không kill process nếu chưa chứng minh ownership.
- Auto audit ON, auto repair safe OFF mặc định.
- Windows Codex runtime thật vẫn DEFERRED_BY_OPERATOR.

=== v25.43 ===
Multi-Codex Team Codex-only: thêm topology Coder / Reviewer / Tester bằng các managed instance riêng. Mỗi role phải có account + CODEX_HOME + app-data + Router + workspace riêng; shared/nested workspace bị block. Topology change dùng explicit epoch, running role không bị silent rebind, launch lỗi rollback chỉ instance HMS vừa khởi động. Windows Codex runtime thật vẫn DEFERRED_BY_OPERATOR.


V25.45 CROSS-PC / LAN CODEX POOL
- Pair nhiều máy Windows qua shared SMB/NAS chỉ bằng metadata ký HMAC.
- Project ownership dùng lease + epoch + nonce; Git remote origin là fingerprint cross-PC khi có.
- Không chia sẻ raw OAuth/API key/Codex credential giữa các máy.
- Prelaunch fail-closed nếu project đang thuộc node khác; lease hết hạn mới cho takeover.


V25.46 REGRESSION & COMPATIBILITY FREEZE
- Khóa exact public BackendAction contract của v25.45 và kiểm tra GUI action không vượt contract.
- Giữ nguyên provider/endpoint, settings/state path, Credential Manager target và LAN KDF salt để migration an toàn.
- LAN signed payload malformed / future clock skew / duplicate node ID đều fail-closed.
- Atomic publish có bounded SMB retry; TTL heartbeat/lease có hard cap.
- Thêm failure matrix và regression suite cho v25.28–v25.45.
- Windows PowerShell 5.1 + real Codex + multi-PC SMB/NAS vẫn là runtime authority cuối cùng.


V25.47 RELIABILITY / SOAK HARNESS
- Thêm soak SMOKE / 6H / 24H với checkpoint/resume; downtime không được cộng vào active elapsed time.
- 6H/24H chỉ đủ điều kiện PASS khi có global Router + ít nhất 2 managed instance + shared LAN path.
- Probe Router/instance ở tầng ứng dụng bằng `GET /hms/health` (HTTP 200 + JSON `ok=true`) + shared IO + signed LAN heartbeat/lease trên namespace soak riêng; không đụng production registry.
- Synthetic fault injection kiểm tra transient SMB reconnect, lease churn, foreign ownership block, node disconnect/rejoin.
- STOP là cooperative checkpoint + PAUSE, không kill process; GUI LAN Pool có nút TIẾP TỤC.
- Real Windows/Codex, real multi-PC SMB/NAS và soak 6h/24h thật vẫn phải chạy trước production release.


V25.52 UX / COCKPIT PARITY+
- Account Center được nâng thành Operator UX: 6 summary cards, filter ROUTE OK / HOLD / STALE / FAVORITE, tìm kiếm và active-route banner.
- Account card giải thích WHY HOLD và phân biệt NEW-session eligibility với sticky session affinity.
- Unified UX loopback-only/read-only hiển thị Route eligible / Hold / Stale quota và operator attention; mọi mutation vẫn dùng native HMS console.
- Không thêm BackendAction public: contract giữ nguyên 90 actions.
- v25.51 rotation/affinity invariants được giữ nguyên và khóa bởi regression.
- Đây là UX/regression evidence, không thay thế Windows/Codex/live-quota/LAN/6h+24h production certification.

=== v25.55 ===
Autonomous Router Digital Twin + bounded state-machine model checking: 32 account / 12 instance / 24 project mặc định; dynamic weights, quota/429/recovery/crash/burst/LAN adversarial events; 3.072 trạng thái rút gọn được duyệt; counterexample ping-pong được ddmin từ 7 event xuống FAIL -> RECOVER. Synthetic-only, không đọc auth thật/không tiêu quota/không cấp production certificate.


V25.63 STARTUP RECOVERY RECONCILER / TARGET CRASH HARNESS
- Startup tự audit journal v25.60/v25.62 trước mutation xung đột; HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED.
- Observer read-only cho auth file/keyring-auto digest provider, Codex process identity, router generation và LAN lease owner/epoch; không xuất raw credential/account identity.
- Direct backend và private Official Auth switch đều chạy recovery preflight, không phụ thuộc việc operator mở GUI.
- Crash harness dùng subprocess thật bị kill rồi cold-start PID mới tại 3 crash window × 4 effect; lab side effect at-most-once, không giả nhận real Codex effect.
- Public BackendAction vẫn chính xác 90. Windows PowerShell 5.1 + real Codex effect crash + live LAN/NAS + soak vẫn là production gate.

Runtime current: v25.63
