# HMS AI Cockpit v25.72 — Windows Target Evidence Capture Kit

Gói này dùng để **thu evidence** trên máy Windows + Codex thật cho 7 case parity Cockpit Tools v1.3.27. Gói **không tự chạy hàng loạt** và **không tự arm real effect**.

Thứ tự bắt buộc:
1. Chạy `00_BASELINE_WATCH.ps1` khi máy có Internet. Baseline phải đúng `1.3.27`.
2. Chạy `01_PREFLIGHT.ps1` để xác nhận Windows / PowerShell / Codex và hash package.
3. Chọn đúng **một** case. Arm/execute bằng Target Campaign Executor hiện có, theo exact operator phrase; không dùng script này để bypass arm gate.
4. Thu observer output, executor output và ký report bằng Windows Attestation Signer.
5. Chạy verifier offline, sau đó export `EVIDENCE_INDEX.json` + report signed. Không export credential/prompt/response/command line/environment.
6. Sau mỗi case phải ở trạng thái DISARMED. Không tự chuyển case tiếp theo.

Nếu Cockpit Tools public version > 1.3.27: **DỪNG campaign** và thực hiện Codex-only delta audit trước.
