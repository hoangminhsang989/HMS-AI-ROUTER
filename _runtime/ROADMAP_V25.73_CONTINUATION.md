# HMS AI Cockpit — Roadmap sau v25.73

Generated UTC: 2026-08-23T06:17:44.934804+00:00

## Mốc khóa tiếp theo

**v25.74 — External Windows Evidence Review Packet & Baseline Drift Reconciliation**

### P0 — Review packet cho evidence thật

1. Nhận bundle/report thật từ Windows Target Capture Kit v25.72 mà không thay đổi source tại máy target.
2. Tạo review packet privacy-safe cho đủ 7 runtime case: signature/trust/freshness/package/manifest/Codex-version/idempotency witness.
3. Giữ raw imported evidence immutable; mọi normalization chỉ tạo artifact dẫn xuất có digest/provenance.
4. Reviewer A/B dùng pseudonymous reviewer refs và append-only Promotion Decision Ledger; không overwrite quyết định cũ.
5. Chỉ khi 7/7 report thật pass + dual review + baseline current mới cho Production Evidence Promotion Auditor tạo đề xuất human review.
6. Auditor vẫn không tự sửa `windows_runtime_certified` hay production score.

### P0 — Baseline drift reconciliation

- Recheck Cockpit ở lúc mở review packet và ngay trước final human decision.
- Nếu Cockpit > 1.3.27: freeze packet, capture upstream version/digest, tạo Codex-only delta audit, invalidate eligibility bằng superseding ledger entry.
- Sau khi parity delta mới được review/freeze, evidence cũ chỉ được tái sử dụng nếu capability binding chứng minh vẫn hợp lệ; không silently grandfather.
- Không tự merge upstream code.

### P1 — UX review tiếng Việt

- Bảng 7-case: Đã nhận / Hợp lệ / Quarantine / Cần reviewer / Baseline stale.
- Hiển thị lý do reject theo mã ổn định và hướng xử lý.
- Export review packet metadata-only cho audit; không export raw credential/account identity.

## Claim boundary

Cho tới khi evidence thật từ Windows + Codex được import và dual-review:

- `windows_runtime_certified = false`
- `external_windows_target_evidence_imported = false`
- `production_score_promotion_eligible = false`
- production evidence giữ **55.2%**
- feature evidence giữ **93.0%**

Nếu chưa có evidence Windows thật, v25.74 chỉ được hoàn thiện review/reconciliation infrastructure; không được tự nâng production score bằng synthetic fixture.
