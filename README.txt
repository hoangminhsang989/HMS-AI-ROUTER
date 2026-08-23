HMS-AI-ROUTER v25.74 — External Windows Evidence Review Packet & Baseline Drift Reconciliation
HMS-AI-ROUTER v25.74 — CODEX-ONLY / IMMUTABLE REVIEW PACKET / NO SILENT GRANDFATHERING

MỤC TIÊU v25.74
- Review packet cho 7 report Windows/Codex thật chỉ tham chiếu raw evidence bằng SHA-256; không normalize/overwrite raw report và không nhúng raw credential/identity.
- Packet có packet_id/sequence/prev-hash/hash-chain, exact target ZIP + release-manifest + trust-snapshot + Cockpit v1.3.27 provenance và capability-binding digest.
- Reviewer chỉ tồn tại dưới pseudonymous reviewer_ref; dual-review ledger append-only vẫn là authority review duy nhất.
- Baseline được recheck khi mở packet và trước quyết định cuối. Cockpit >1.3.27 => packet FROZEN_BASELINE_DRIFT và eligibility bị invalidated.
- Reconciliation tạo superseding INVALIDATE entries cho approval đang sống; không xóa lịch sử.
- Evidence cũ chỉ có thể tái sử dụng nếu Codex-only delta audit chứng minh đủ 7 capability binding còn hợp lệ; dù vậy vẫn bắt buộc new dual-review epoch, không silently grandfather.
- Không auto-merge upstream, không auto-certification và không production-score mutation.
- GUI chỉ có PACKET / RECONCILE / DIAGNOSTICS proof controls; không backend mutation/target arm/credential export binding.

CLAIM BOUNDARY v25.74
Build hiện tại chỉ chứng minh immutable review-packet/reconciliation contract bằng synthetic/control-plane proof. Chưa import evidence Windows/Codex thật trong build này; windows_runtime_certified=false và production score giữ nguyên 55.2%.

=== PRIOR MILESTONE v25.73 ===
HMS-AI-ROUTER v25.73 — Windows Target Evidence Import Review & Baseline Delta Watch Automation
- Read-only 7-case signed import, replay/quarantine, dual-review append-only ledger và two-checkpoint Cockpit baseline watch.
- Full regression 86/86 · 2.006/2.006; synthetic/control-plane only, production score không tự tăng.

=== PRIOR MILESTONE v25.70 ===
HMS-AI-ROUTER v25.70 — Cockpit Tools v1.3.27 Codex Parity Reset
- Baseline Cockpit nâng từ v1.3.24 lên v1.3.27.
- Port auto-rebind, launch-time occupancy, auth/API split, official-account-ref usage continuity, stream identity isolation, WebSocket preservation, bounded backups, manual auth.json export gate và live-only model metadata.
- Full regression 72/72 · 1.856/1.856; synthetic/control-plane only, production score không tự tăng.

=== PRIOR MILESTONE v25.69 ===
HMS-AI-ROUTER v25.69 — Windows Target Certification Evidence Ingest & Promotion Decision Ledger
HMS-AI-ROUTER v25.69 — CODEX-ONLY / READ-ONLY EVIDENCE INBOX + APPEND-ONLY DUAL-REVIEW LEDGER

MỤC TIÊU v25.69
- Read-only ingest cho externally produced Windows target certification reports; ingest tuyệt đối không execute target effect.
- Mỗi report bind exact package version + release manifest SHA-256 + frozen trust snapshot SHA-256 + campaign/run/case/nonce + cryptographic signer envelope.
- Reject/quarantine nonce replay, run replay, report-digest replay, mixed package/trust/campaign, stale/untrusted signature và raw private/identity fields; không auto-repair.
- Evidence Inbox hiển thị accepted/quarantine + completeness đúng ma trận 4 effect × 3 crash window.
- Promotion Decision Ledger append-only JSONL/hash-chain; optimistic tail guard chặn concurrent silent overwrite.
- Promotion cần ít nhất hai reviewer pseudonymous khác nhau; APPROVE/REJECT/INVALIDATE đều là ledger entry bất biến.
- Certificate revocation, trust snapshot drift, package supersede hoặc evidence aging chỉ được xử lý bằng superseding ledger entry; không xóa lịch sử.
- `PROMOTION_ELIGIBLE_FOR_SEPARATE_SCORE_AUDIT` không đồng nghĩa production score mutation; `automatic_production_certification=false` và `production_score_mutation_authorized=false`.
- GUI chỉ có INGEST / LEDGER / INBOX proof controls; không có target arm binding.
- Synthetic/control-plane proof không tăng production score.

CLAIM BOUNDARY v25.69
Build hiện tại chỉ chứng minh ingest/anti-replay/quarantine/dual-review-ledger contract bằng cryptographic fixture an toàn. Không có external Windows target evidence thật được import trong release proof; real Codex effects, Windows signing và production score promotion vẫn chưa được thực thi/chứng nhận.

=== PRIOR MILESTONE v25.68 ===
HMS-AI-ROUTER v25.68 — Target Campaign Executor & Attested Promotion Review Console
HMS-AI-ROUTER v25.68 — CODEX-ONLY / ONE-CASE TARGET EXECUTOR + HUMAN PROMOTION REVIEW BOUNDARY

MỤC TIÊU v25.68
- Windows-only target campaign executor chỉ nhận một case đã ARM riêng; không auto-run case kế tiếp và không automatic re-arm.
- Mỗi case bind exact package version + release manifest SHA-256 + frozen trust-snapshot SHA-256.
- Preflight bắt buộc Windows host + PowerShell 5.1 parser/runtime + Codex process ownership + Official Auth observer + idempotency witness.
- Durable effect phải có observed idempotency witness khớp; mismatch => OPERATOR_REQUIRED; executor AUTO-DISARM sau mọi attempt.
- LAN/NAS lease vẫn có ownership/readback gate riêng và không đi qua generic mutation shortcut.
- Attested Promotion Review Console yêu cầu đúng 12 signed reports, đủ 4 effect × 3 crash window; reject stale/revoked/retired-current/mixed-version/mixed-trust/invalid-signature evidence.
- Certificate RETIRED vẫn có thể audit lịch sử nếu chữ ký có trước thời điểm retire, nhưng không được dùng ký case mới/current promotion.
- Offline review bundle chỉ chứa pseudonymous case summaries/signature envelopes/trust snapshot/decision; không account identity, credential hay private material.
- GUI chỉ có EXECUTOR / REVIEW / OFFLINE proof controls; không có nút arm real target effect.
- `promotion_score_eligible=true` nếu xuất hiện từ review thật chỉ là input cho HUMAN REVIEW; `automatic_production_certification=false` luôn giữ nguyên.
- Synthetic/control-plane proof không tăng production score.

CLAIM BOUNDARY v25.68
Build hiện tại chứng minh executor/review/offline-bundle contract bằng fixture an toàn. Không có real target campaign case, Windows signing hay real Codex effect nào được chạy trong build này; windows_runtime_certified=false và production score không tự tăng.

=== PRIOR MILESTONE v25.67 ===
HMS-AI-ROUTER v25.67 — Windows Attestation Trust Store & Resumable Target Certification Campaign
HMS-AI-ROUTER v25.67 — CODEX-ONLY / TRUST-SNAPSHOT + RESUMABLE CERTIFICATION BOUNDARY

MỤC TIÊU v25.67
- Local attestation trust store với certificate pinning, rotation, revocation và deterministic trust-snapshot SHA-256.
- DPAPI signing-key lifecycle chỉ xuất metadata: generation, state, pseudonymous key ref và sealed-blob digest; không export raw key/private material.
- Offline attestation verifier xác minh package/run/nonce/signature/trust snapshot mà không cần account identity, credential hay network.
- Resumable target certification campaign bao phủ đúng 4 effect × 3 crash window = 12 case.
- Mỗi case phải arm riêng; PENDING => REARM_REQUIRED, RUNNING/UNKNOWN => OPERATOR_REQUIRED, DURABLE_UNVERIFIED => VERIFY_ONLY, RECOVERED => ATTEST_ONLY, ATTESTED => SKIP_COMPLETE.
- Resume tuyệt đối không silently repeat durable effect và không automatic re-arm.
- Mỗi campaign/case bind exact package version + release manifest digest + trust snapshot digest; mixed-version/revoked signer/trust drift fail closed.
- GUI chỉ có TRUST / OFFLINE / CAMPAIGN proof controls; không có nút arm real target effect.
- Synthetic/control-plane proof không tăng production score.

CLAIM BOUNDARY v25.67
Build hiện tại chứng minh trust-store/offline-verifier/resumable-campaign contract bằng fixture an toàn. Real Windows certificate/DPAPI lifecycle, real Codex effects và complete 4×3 target campaign chưa chạy trong build này; windows_runtime_certified=false và production score không tự tăng.

=== PRIOR MILESTONE v25.66 ===
- Windows-local cryptographic attestation signer: DPAPI machine-bound HMAC / Windows Certificate Store.
- One-shot target certification runbook với auto-disarm trong finally.
- Privacy-safe attestation exchange + Vietnamese promotion explanation.
- Cryptographic promotion gate; eligibility không đồng nghĩa automatic production certification.

=== PRIOR MILESTONE v25.65 ===
HMS-AI-ROUTER v25.65 — Windows Target Adapter Pack & Attested Evidence Promotion Gate
- Adapter pack / anti-replay / promotion / recovery timeline foundation.
- Real-effect mode DISARMED mặc định; public BackendAction giữ nguyên.

=== PRIOR MILESTONE v25.62 ===
HMS-AI-ROUTER v25.62 — Recovery Transaction Replay & Multi-Subsystem Crash Consistency
HMS-AI-ROUTER v25.62 — CODEX-ONLY / SYNTHETIC CONTROL-PLANE GATE

MỤC TIÊU v25.62
- Một transaction identity/effect fingerprint xuyên Official Auth rewrite, controlled Codex restart, router transition và LAN lease handoff.
- Mỗi durable side effect có idempotency key; replay luôn kiểm tra external observable state trước quyết định, không lặp mutation chỉ vì process cũ biến mất.
- Compensation chạy theo dependency DAG ngược và chỉ rollback khi ownership được chứng minh.
- Concurrent external change / ownership không chứng minh được => OPERATOR_REQUIRED, fail closed.
- Convergence vocabulary: HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED.
- Synthetic crash matrix bao phủ trước/sau phase, unjournaled-effect window và repeated replay; production certification vẫn tách riêng.

=== PRIOR MILESTONE v25.61 ===
HMS-AI-ROUTER v25.61 — Native Usage & Token Center Parity+
HMS-AI-ROUTER v25.61 — CODEX-ONLY / FEATURE PARITY CANDIDATE

MỤC TIÊU v25.61
- Native Usage & Token Center đọc metadata quota/account hiện có; không thêm public mutation BackendAction.
- 5 giờ / Weekly / model-specific quota hiển thị countdown + absolute reset timestamp + source + freshness.
- Tách ba lifecycle độc lập: package/subscription expiry, OAuth/token expiry, quota reset.
- NOW vs AFTER NEXT RESET là read-only scenario preview; AFTER RESET luôn gắn SCENARIO ONLY và không ghi ngược live quota/router.
- Metadata-only history/replay cho reset timestamp change, replenishment observed và package-expiry metadata change.
- Unified Diagnostics + Diagnostics Bundle chỉ nhận aggregate metadata; không account identity/raw auth/prompt/request/response body.
- Generic Bearer redaction được harden thêm trong Diagnostics Bundle.
- Production certification vẫn yêu cầu evidence thật trên Windows/Codex/live quota/LAN-NAS/soak.


=== PRIOR MILESTONE v25.60 ===
HMS-AI-ROUTER v25.60 — Recovery Transaction Journal & Usage Reset UX
HMS-AI-ROUTER v25.60 — CODEX-ONLY / NO REAL MACHINE REQUIRED FOR DEVELOPMENT GATES

MỤC TIÊU v25.60
- Durable hash-chain Recovery Transaction Journal: PREPARE → COMMIT → VERIFY → DONE/ROLLBACK.
- Crash-consistent resume: COMMIT đã durable thì chỉ VERIFY, tuyệt đối không lặp auth rewrite/restart/lease reelection.
- Journal metadata/hash only; không lưu raw auth token/API key/prompt/request/response body.
- Official Auth switch v25.59 được bọc transaction journal trước/giữa/sau atomic rewrite.
- Account Center hiển thị cả countdown + giờ đặt lại tuyệt đối cho 5h/Weekly.
- Package/subscription expiry chỉ hiển thị khi upstream thực sự cung cấp; không đánh đồng với token expiry.
- Synthetic crash-injection có thể PASS không cần máy thật nhưng không tạo production certificate.


MỤC TIÊU v25.59
- Parity target: Cockpit Tools v1.3.24 Codex auth switching behavior.
- Support Codex cli_auth_credentials_store = file / keyring / auto; ephemeral fails closed for persisted switching.
- Snapshot current auth BEFORE switch; serialize switches; atomic write + readback + rollback.
- Preserve unrelated/custom auth.json fields while replacing credential-bearing fields and cleaning stale credentials.
- Preserve/repair auth_mode for ChatGPT OAuth and avoid mixed stale API-key + OAuth credentials.
- Match official Codex direct-keyring naming model: service Codex Auth, account cli|sha256(CODEX_HOME)[:16]; detect secret_auth_storage and fail closed for the encrypted Secrets backend until the official Codex helper path is available.
- Track Codex OAuth identity profiles: Cockpit v1.3.24 originator codex_vscode; User-Agent derives from the installed Codex version with a compatibility fallback.
- Controlled Codex App restart only after commit/readback verification in native PowerShell path.

CLAIM BOUNDARY
Synthetic file/direct-keyring fixtures validate semantics without using real credentials. Codex encrypted Secrets keyring is detected and blocked from raw mutation; real Windows Codex App/Secrets-keyring/live OAuth remains target-machine certification evidence and is not claimed by this build.


=== v25.59 · OFFICIAL AUTH COMPATIBILITY LAYER · P0 ===
Parity baseline: Cockpit Tools v1.3.24 (2026-08-20).
- File / keyring / auto auth-store abstraction; CODEX_HOME-aware.
- Snapshot the current official auth state before account switch.
- Serialized switch lock; atomic field-preserving rewrite; stale credential/account-identity cleanup.
- OAuth compatibility identity: Cockpit v1.3.24 originator=codex_vscode; User-Agent is version-derived (0.146.0 only as fallback fixture). Official CLI profile codex_cli_rs is kept separate.
- Readback fingerprint verification and rollback before any controlled Codex App restart.
- Audit/evidence is metadata-only; no raw token/API key/prompt/request/response body.
- Synthetic fixtures may PASS without a real machine, but cannot issue a production certificate.

=== PRIOR MILESTONE v25.63 · STARTUP RECOVERY RECONCILER / TARGET CRASH HARNESS ===
- Startup audits unresolved v25.60/v25.62 journals before conflicting mutation.
- Read-only auth/process/router/LAN observers expose digests/metadata only; no raw credential/account identity.
- Direct backend mutation and private Official Auth switch run the same recovery preflight.
- GUI shows HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED and an OS subprocess cold-start crash lab.
- Public BackendAction contract remains exactly 90.
- Real Windows PowerShell 5.1, real Codex effects, LAN/NAS and soak remain production gates.
Runtime historical: v25.63
