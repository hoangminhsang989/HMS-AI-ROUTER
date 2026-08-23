# HMS AI Cockpit — Roadmap sau v25.72

Generated UTC: 2026-08-23T05:48:47.149440+00:00

## Mốc khóa tiếp theo

**v25.73 — Windows Target Evidence Import Review & Baseline Delta Watch Automation**

### P0 — External Windows evidence review path

1. Nhận các report đã ký từ Windows Target Capture Kit v25.72 qua read-only ingest v25.69.
2. Xác minh exact v25.72 ZIP SHA-256 + RELEASE_MANIFEST_V25_72 digest + Cockpit baseline + Codex version.
3. Re-run Cockpit baseline watch trước import và trước human promotion review.
4. Nếu Cockpit > 1.3.27: freeze toàn bộ promotion, thực hiện Codex-only delta audit trước; không tự nhập scope Antigravity.
5. Đưa evidence hợp lệ vào dual-review append-only Promotion Decision Ledger.
6. Production Evidence Promotion Auditor chỉ đưa ra đề xuất review; không tự sửa score.
7. Chỉ khi evidence thật đủ cho 7 runtime case, đúng chữ ký/trust/freshness/idempotency, mới cho phép human review cân nhắc thay đổi `windows_runtime_certified` hoặc production evidence score.

### P0 — Baseline Delta Watch Automation

- Tạo baseline-watch artifact có timestamp/source/version/digest.
- Chạy ở hai checkpoint: trước target campaign và trước promotion review.
- Newer baseline => `PROMOTION_FROZEN_BASELINE_STALE`.
- Không tự merge/copy upstream code; chỉ tạo Codex-only delta audit queue.

### P1 — Operator UX tiếng Việt

- Import checklist từng bước.
- Hiển thị 7-case completeness, signature/trust/freshness và lý do quarantine.
- Hiển thị baseline current/stale rõ ràng.
- Cho export review bundle privacy-safe; không export raw credential/account identity.

## Claim boundary

Cho tới khi report từ Windows + Codex thật được import, xác minh và dual-review:

- `windows_runtime_certified = false`
- `external_windows_target_evidence_imported = false`
- `production_score_promotion_eligible = false`
- production evidence giữ **55.2%**
- feature evidence giữ **93.0%**

Không synthetic proof nào được dùng để tự nâng production score.
