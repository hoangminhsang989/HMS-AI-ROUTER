# HMS AI Cockpit — Roadmap sau v25.74

Generated UTC: 2026-08-23T07:27:07.763369+00:00

## Mốc khóa tiếp theo

**v25.75 — Real Windows Review Packet Ingest & Human Promotion Decision Workbench**

### P0 — Ingest evidence Windows thật

1. Nhận review packet/report thật sinh từ Windows Target Capture Kit v25.72 và chuỗi import/review v25.73–v25.74.
2. Verify exact HMS package ZIP SHA-256, release-manifest SHA-256, trust snapshot, signer, freshness, nonce/run/report replay guards và đủ 7 runtime cases.
3. Raw evidence tiếp tục immutable; Workbench chỉ tham chiếu digest/provenance, không rewrite raw report.
4. Recheck Cockpit public baseline ở lúc mở workbench và ngay trước quyết định reviewer cuối.
5. Nếu baseline drift: tự freeze eligibility, append superseding INVALIDATE epoch và yêu cầu Codex-only delta audit trước khi evidence có thể được xét lại.

### P0 — Human Promotion Decision Workbench

- Reviewer A/B phải là hai pseudonymous reviewer refs khác nhau.
- APPROVE / REJECT / INVALIDATE đều append-only, hash-chained; không sửa/xóa quyết định cũ.
- Chỉ khi evidence thật 7/7 pass + trust/freshness current + baseline current + dual review mới cho Production Evidence Promotion Auditor tạo **đề xuất** thay đổi production evidence.
- Auditor không tự sửa score; thay đổi score/certification vẫn là human-controlled publication step riêng.
- Không auto-certification, không auto-upstream merge, không auto-rearm real effects.

### P1 — Baseline watch / release watch

- Recheck Cockpit baseline trước import, trước review cuối và trước publication.
- Nếu upstream > 1.3.27, đóng băng promotion và tạo delta-audit queue ngay.
- Giữ scope Codex-only; không kéo Antigravity trở lại roadmap.

### P1 — UX tiếng Việt

- Workbench 7-case: Evidence / Signature / Trust / Freshness / Idempotency / Reviewer A / Reviewer B / Baseline.
- Giải thích rõ lý do `QUARANTINE`, `FROZEN_BASELINE_DRIFT`, `NEW_REVIEW_EPOCH_REQUIRED` và cách xử lý.
- Export audit packet metadata-only; không xuất raw credential/account identity/private material.

## Claim boundary

Cho tới khi có evidence Windows + Codex thật và hoàn thành dual-review:

- `windows_runtime_certified = false`
- `external_windows_target_evidence_imported = false`
- `production_score_promotion_eligible = false`
- production evidence giữ **55.2%**
- feature evidence giữ **93.0%**

Nếu chưa có evidence Windows thật, v25.75 chỉ hoàn thiện ingest/workbench infrastructure; tuyệt đối không tự nâng production score bằng synthetic fixture.
