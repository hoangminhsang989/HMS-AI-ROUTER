# HMS AI Cockpit — Roadmap after v25.49

## NEXT: v25.50 — LIVE QUOTA INTELLIGENCE

Mục tiêu là đóng khoảng cách lớn tiếp theo với Cockpit ở quota thật và quyết định rotation dựa trên evidence đang còn tươi.

### Gate bắt buộc
1. Thu thập quota Hourly / Weekly / plan từ đường dữ liệu Codex/Router thật, có timestamp và provenance.
2. Freshness TTL + stale fail-closed: quota cũ không được dùng để quyết định tài khoản đủ điều kiện.
3. Reserve policy theo account/plan; không dùng một ngưỡng mù cho mọi loại tài khoản.
4. Normalize Free / Plus / Pro và trạng thái chưa biết; unknown phải fail-safe.
5. Rotation phải dùng snapshot live gần thời điểm request, không chỉ startup snapshot.
6. Project affinity vẫn được giữ nếu account còn đủ quota; chỉ failover khi policy cho phép.
7. Hysteresis/cooldown chống ping-pong account khi quota dao động gần ngưỡng.
8. Diagnostics giải thích được: account nào bị loại, quota evidence tuổi bao nhiêu, reserve nào được áp dụng.
9. Không lưu token/prompt/body trong quota evidence.
10. Regression + migration + LAN + reliability + performance + v25.49 contract phải tiếp tục PASS.

### Production boundary
v25.50 không được tự coi là production-certified nếu v25.49 target-machine LIVE 1 chưa PASS trên Windows/Codex thật.
