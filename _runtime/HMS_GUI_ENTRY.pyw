#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import threading
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"
APP_VERSION = "25.75"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))


def _load_legacy_gui():
    loader = importlib.machinery.SourceFileLoader("hms_gui_legacy", str(LEGACY_GUI))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Không thể tạo module spec cho HMS_GUI.pyw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.APP_VERSION = APP_VERSION
    return module


legacy = _load_legacy_gui()

from HMS_Codex_CockpitLiveBaselineProvider import CockpitLiveBaselineProvider, LiveBaselineError
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE
from HMS_Codex_WindowsPromotionDecisionLedger import read_ledger
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController

_ORIGINAL_BUILD_SHELL = legacy.HmsApp._build_shell
_ORIGINAL_BUILD_PAGES = legacy.HmsApp._build_pages
_ORIGINAL_SHOW_PAGE = legacy.HmsApp.show_page


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def _promotion_state_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return root / "HMS-AI-ROUTER" / "promotion-review"


def _safe_json(path: Path, default):
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError, TypeError):
        return default


def _patch_visible_branding(app):
    for widget in _walk_widgets(app.sidebar):
        try:
            if widget.cget("text") == "AI COCKPIT":
                widget.configure(text="AI ROUTER")
        except Exception:
            pass


def _extended_build_shell(self):
    _ORIGINAL_BUILD_SHELL(self)
    _patch_visible_branding(self)
    nav_parent = self.nav["settings"].master
    item = legacy.NavItem(
        nav_parent,
        "Promotion review",
        "security",
        lambda: self.show_page("promotion"),
        width=184,
        height=40,
    )
    item.pack(fill="x", pady=2)
    self.nav["promotion"] = item


def _gate_row(parent, name):
    tk = legacy.tk
    C = legacy.C
    row = tk.Frame(parent, bg=C["surface"], height=30)
    row.pack(fill="x", padx=14, pady=1)
    row.pack_propagate(False)
    tk.Label(row, text=name, width=18, anchor="w", bg=C["surface"], fg=C["text2"],
             font=("Segoe UI Semibold", 8)).pack(side="left")
    value = tk.Label(row, text="CHỜ", anchor="w", bg=C["surface"], fg=C["muted"],
                     font=("Segoe UI Semibold", 8))
    value.pack(side="left", fill="x", expand=True)
    return value


def _extended_build_pages(self):
    _ORIGINAL_BUILD_PAGES(self)
    tk = legacy.tk
    ttk = legacy.ttk
    C = legacy.C

    page = tk.Frame(self.content, bg=C["bg"])
    self.pages["promotion"] = page

    header = tk.Frame(page, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
    header.pack(fill="x", pady=(0, 8), ipady=8)
    tk.Label(header, text="Windows Promotion Review Workbench", bg=C["surface"], fg=C["text"],
             font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=16, pady=(2, 2))
    tk.Label(header,
             text="Review-only · không tự certify · không tự sửa production score · baseline drift = fail-closed",
             bg=C["surface"], fg=C["text2"], font=("Segoe UI", 8)).pack(anchor="w", padx=16)

    body = tk.Frame(page, bg=C["bg"])
    body.pack(fill="both", expand=True)

    top = tk.Frame(body, bg=C["bg"])
    top.pack(fill="x")

    gates = tk.Frame(top, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
    gates.pack(side="left", fill="both", expand=True, padx=(0, 5))
    tk.Label(gates, text="GATE AN TOÀN", bg=C["surface"], fg=C["text"],
             font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=14, pady=(9, 4))
    self.promotion_gate_rows = {
        "evidence": _gate_row(gates, "Evidence"),
        "signature": _gate_row(gates, "Signature"),
        "trust": _gate_row(gates, "Trust"),
        "freshness": _gate_row(gates, "Freshness"),
        "idempotency": _gate_row(gates, "Idempotency"),
        "reviewers": _gate_row(gates, "Reviewer A+B"),
        "baseline": _gate_row(gates, "Baseline"),
        "ledger": _gate_row(gates, "Ledger"),
    }

    review = tk.Frame(top, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1, width=330)
    review.pack(side="left", fill="y", padx=(5, 0))
    review.pack_propagate(False)
    tk.Label(review, text="REVIEWER ACTION", bg=C["surface"], fg=C["text"],
             font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=14, pady=(9, 5))

    form = tk.Frame(review, bg=C["surface"])
    form.pack(fill="x", padx=14)
    tk.Label(form, text="Reviewer identity (không lưu)", bg=C["surface"], fg=C["text2"],
             font=("Segoe UI", 7)).pack(anchor="w")
    self.promotion_reviewer_identity = tk.StringVar()
    tk.Entry(form, textvariable=self.promotion_reviewer_identity, bg="#172033", fg=C["text"],
             insertbackground=C["text"], relief="flat", font=("Segoe UI", 8)).pack(fill="x", ipady=4, pady=(2, 5))

    tk.Label(form, text="Reviewer salt ≥ 16 ký tự (không lưu)", bg=C["surface"], fg=C["text2"],
             font=("Segoe UI", 7)).pack(anchor="w")
    self.promotion_reviewer_salt = tk.StringVar()
    tk.Entry(form, textvariable=self.promotion_reviewer_salt, show="•", bg="#172033", fg=C["text"],
             insertbackground=C["text"], relief="flat", font=("Segoe UI", 8)).pack(fill="x", ipady=4, pady=(2, 5))

    tk.Label(form, text="Lane", bg=C["surface"], fg=C["text2"], font=("Segoe UI", 7)).pack(anchor="w")
    self.promotion_lane = tk.StringVar(value="TERMINAL_PTY")
    lane = ttk.Combobox(form, textvariable=self.promotion_lane, state="readonly",
                        values=["TERMINAL_PTY", "PROJECT_RESUME", "OPTIONAL_GPU"], font=("Segoe UI", 8))
    lane.pack(fill="x", pady=(2, 5))

    tk.Label(form, text="Ghi chú", bg=C["surface"], fg=C["text2"], font=("Segoe UI", 7)).pack(anchor="w")
    self.promotion_note = tk.StringVar()
    tk.Entry(form, textvariable=self.promotion_note, bg="#172033", fg=C["text"], insertbackground=C["text"],
             relief="flat", font=("Segoe UI", 8)).pack(fill="x", ipady=4, pady=(2, 8))

    action_row = tk.Frame(form, bg=C["surface"])
    action_row.pack(fill="x")
    self.promotion_approve_btn = legacy.HoverButton(action_row, "DUYỆT", lambda: self.submit_promotion_review("APPROVE"),
        width=84, height=30, bg="#245844", hover="#2f7157", font=("Segoe UI Semibold", 7))
    self.promotion_approve_btn.pack(side="left", padx=(0, 4))
    self.promotion_reject_btn = legacy.HoverButton(action_row, "TỪ CHỐI", lambda: self.submit_promotion_review("REJECT"),
        width=84, height=30, bg="#6b343b", hover="#814048", font=("Segoe UI Semibold", 7))
    self.promotion_reject_btn.pack(side="left", padx=4)
    self.promotion_invalidate_btn = legacy.HoverButton(action_row, "INVALIDATE", lambda: self.submit_promotion_review("INVALIDATE"),
        width=96, height=30, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7))
    self.promotion_invalidate_btn.pack(side="left", padx=(4, 0))
    for btn in (self.promotion_approve_btn, self.promotion_reject_btn, self.promotion_invalidate_btn):
        btn.set_enabled(False)

    status = tk.Frame(body, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
    status.pack(fill="x", pady=(10, 0), ipady=7)
    self.promotion_baseline_label = tk.Label(status, bg=C["surface"], fg=C["text"],
        font=("Segoe UI Semibold", 8), anchor="w")
    self.promotion_baseline_label.pack(fill="x", padx=14, pady=(4, 1))
    self.promotion_live_label = tk.Label(status, bg=C["surface"], fg=C["muted"],
        font=("Segoe UI Semibold", 8), anchor="w")
    self.promotion_live_label.pack(fill="x", padx=14, pady=1)
    self.promotion_packet_label = tk.Label(status, bg=C["surface"], fg=C["text2"],
        font=("Segoe UI", 8), anchor="w")
    self.promotion_packet_label.pack(fill="x", padx=14, pady=1)
    self.promotion_ledger_label = tk.Label(status, bg=C["surface"], fg=C["text2"],
        font=("Segoe UI", 8), anchor="w")
    self.promotion_ledger_label.pack(fill="x", padx=14, pady=1)
    self.promotion_gate_label = tk.Label(status, bg=C["surface"], fg=C["warning"],
        font=("Segoe UI Semibold", 8), anchor="w", wraplength=760, justify="left")
    self.promotion_gate_label.pack(fill="x", padx=14, pady=(1, 4))

    actions = tk.Frame(body, bg=C["bg"])
    actions.pack(fill="x", pady=(8, 0))
    legacy.HoverButton(actions, "LÀM MỚI REVIEW", self.refresh_promotion_review, width=138, height=32,
        bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 8)).pack(side="left")

    self._promotion_controller = PromotionWorkbenchController(_promotion_state_dir())
    self._promotion_live_provider = CockpitLiveBaselineProvider()
    self._promotion_live_observation = None
    self._promotion_live_check_busy = False
    self._promotion_action_busy = False
    self._promotion_report = {}
    self._promotion_ledger = []
    self.refresh_promotion_review()


def _set_gate(self, key, ok=None, text=None):
    label = getattr(self, "promotion_gate_rows", {}).get(key)
    if label is None:
        return
    C = legacy.C
    if ok is True:
        label.configure(text=text or "PASS", fg=C["success"])
    elif ok is False:
        label.configure(text=text or "BLOCK", fg=C["danger"])
    else:
        label.configure(text=text or "CHỜ", fg=C["muted"])


def _refresh_gate_matrix(self):
    report = getattr(self, "_promotion_report", {}) or {}
    reasons = set(str(x) for x in (report.get("reasons") or []))
    verified = report.get("real_packet_verified") is True
    self._set_promotion_gate("evidence", verified, "VERIFIED" if verified else "CHƯA CÓ PACKET THẬT")
    self._set_promotion_gate("signature", verified and "SIGNER_VALIDATION_REQUIRED" not in reasons and "SIGNATURE_DIGEST_INVALID" not in reasons,
                             "PASS" if verified and "SIGNER_VALIDATION_REQUIRED" not in reasons and "SIGNATURE_DIGEST_INVALID" not in reasons else "BLOCK")
    trust_bad = bool(reasons & {"TRUST_SNAPSHOT_NOT_CURRENT", "SIGNER_TRUST_REF_MISMATCH", "TRUST_SNAPSHOT_DIGEST_INVALID"})
    self._set_promotion_gate("trust", verified and not trust_bad, "PASS" if verified and not trust_bad else "BLOCK")
    fresh_bad = bool(reasons & {"EVIDENCE_STALE", "CAPTURE_UTC_INVALID", "CAPTURE_TIME_IN_FUTURE"})
    self._set_promotion_gate("freshness", verified and not fresh_bad, "PASS" if verified and not fresh_bad else "BLOCK")
    replay_bad = "DUPLICATE_PACKET_DIGEST" in reasons or any(x.endswith("_REPLAY") for x in reasons)
    self._set_promotion_gate("idempotency", verified and not replay_bad, "PASS" if verified and not replay_bad else "BLOCK")

    ledger = getattr(self, "_promotion_ledger", []) or []
    self._set_promotion_gate("ledger", True, f"{len(ledger)} RECORD(S)")
    live = getattr(self, "_promotion_live_observation", None)
    if live is None:
        self._set_promotion_gate("baseline", None, "ĐANG KIỂM TRA")
    else:
        match = str(live.get("baseline") or "") == COCKPIT_BASELINE
        self._set_promotion_gate("baseline", match, "MATCH" if match else f"DRIFT → {live.get('baseline') or '—'}")

    reviewers_ok = False
    if verified:
        provenance = report.get("provenance") or {}
        manifest = str(provenance.get("release_manifest_sha256") or "").lower()
        if HEX64.fullmatch(manifest):
            try:
                baseline_now = str((live or {}).get("baseline") or COCKPIT_BASELINE)
                state = self._promotion_controller.state(package_version=APP_VERSION, manifest_sha256=manifest,
                    baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=baseline_now)
                reviewers_ok = state.get("gates", {}).get("reviewer_a_b") is True
            except Exception:
                reviewers_ok = False
    self._set_promotion_gate("reviewers", reviewers_ok, "ĐỦ 2 REVIEWER/LANE" if reviewers_ok else "CHƯA ĐỦ")
    self._update_promotion_action_buttons()


def _update_promotion_action_buttons(self):
    if not hasattr(self, "promotion_approve_btn"):
        return
    busy = bool(getattr(self, "_promotion_action_busy", False) or getattr(self, "_promotion_live_check_busy", False))
    report = getattr(self, "_promotion_report", {}) or {}
    live = getattr(self, "_promotion_live_observation", None)
    evidence_ok = report.get("real_packet_verified") is True
    trusted_live = isinstance(live, dict) and live.get("source") == "GITHUB_RELEASES_LATEST" and bool(live.get("release_id"))
    match = trusted_live and str(live.get("baseline") or "") == COCKPIT_BASELINE
    self.promotion_approve_btn.set_enabled(not busy and evidence_ok and match)
    self.promotion_reject_btn.set_enabled(not busy and evidence_ok and match)
    self.promotion_invalidate_btn.set_enabled(not busy and evidence_ok and trusted_live)


def _apply_promotion_live_result(self, observation=None, error=None):
    C = legacy.C
    self._promotion_live_check_busy = False
    if error is not None:
        self._promotion_live_observation = None
        self.promotion_live_label.configure(text=f"Live baseline: ERROR · {error}", fg=C["danger"])
        self.promotion_gate_label.configure(text="LIVE BASELINE GATE: không xác minh được upstream → reviewer action bị khóa (fail-closed).", fg=C["danger"])
        self._refresh_promotion_gate_matrix()
        return
    self._promotion_live_observation = observation
    live = str((observation or {}).get("baseline") or "")
    checked = str((observation or {}).get("checked_utc") or "")
    matched = live == COCKPIT_BASELINE
    self.promotion_live_label.configure(text=f"Live baseline: {live or '—'} · {'MATCH' if matched else 'DRIFT'} · checked {checked}",
                                        fg=C["success"] if matched else C["danger"])
    self.promotion_gate_label.configure(
        text=("LIVE BASELINE GATE: MATCH. DUYỆT/TỪ CHỐI được phép nếu evidence hợp lệ; baseline sẽ được recheck lại ngay trước khi ghi ledger."
              if matched else f"LIVE BASELINE GATE: DRIFT {COCKPIT_BASELINE} → {live or 'unknown'} · chỉ INVALIDATE được mở."),
        fg=C["success"] if matched else C["danger"])
    self._refresh_promotion_gate_matrix()


def _start_promotion_live_check(self):
    if getattr(self, "_promotion_live_check_busy", False):
        return
    provider = getattr(self, "_promotion_live_provider", None)
    if provider is None:
        return
    self._promotion_live_check_busy = True
    self._promotion_live_observation = None
    self.promotion_live_label.configure(text="Live baseline: đang kiểm tra GitHub Releases…", fg=legacy.C["muted"])
    self._update_promotion_action_buttons()

    def worker():
        try:
            observation = provider.observe()
            self.root.after(0, lambda: self._apply_promotion_live_result(observation=observation))
        except LiveBaselineError as exc:
            self.root.after(0, lambda e=str(exc): self._apply_promotion_live_result(error=e))
        except Exception as exc:
            self.root.after(0, lambda e=f"unexpected provider error: {exc}": self._apply_promotion_live_result(error=e))

    threading.Thread(target=worker, daemon=True).start()


def _refresh_promotion_review(self):
    C = legacy.C
    ctl = getattr(self, "_promotion_controller", None)
    if ctl is None:
        return
    report = _safe_json(ctl.report_path, {})
    try:
        ledger = read_ledger(ctl.ledger_path)
    except Exception:
        ledger = []
    self._promotion_report = report
    self._promotion_ledger = ledger
    verified = report.get("real_packet_verified") is True
    self.promotion_baseline_label.configure(text=f"Frozen parity authority: Cockpit Tools {COCKPIT_BASELINE}")
    self.promotion_packet_label.configure(text=("External Windows packet: VERIFIED" if verified else "External Windows packet: chưa có verified packet"),
                                          fg=C["success"] if verified else C["text2"])
    self.promotion_ledger_label.configure(text=f"Decision ledger: {len(ledger)} record(s) · raw reviewer identity/salt không được lưu")
    self.promotion_gate_label.configure(text="LIVE BASELINE GATE: đang xác minh upstream; reviewer action khóa cho tới khi có kết quả.", fg=C["warning"])
    self._refresh_promotion_gate_matrix()
    self._start_promotion_live_check()


def _validate_promotion_form(self):
    identity = self.promotion_reviewer_identity.get().strip()
    salt = self.promotion_reviewer_salt.get()
    lane = self.promotion_lane.get().strip().upper()
    note = self.promotion_note.get().strip()
    if len(identity) < 2:
        return None, "Reviewer identity cần ít nhất 2 ký tự."
    if len(salt) < 16:
        return None, "Reviewer salt cần ít nhất 16 ký tự."
    if lane not in {"TERMINAL_PTY", "PROJECT_RESUME", "OPTIONAL_GPU"}:
        return None, "Lane không hợp lệ."
    return {"reviewer_identity": identity, "reviewer_salt": salt, "lane": lane, "note_vi": note}, None


def _submit_promotion_review(self, decision):
    if getattr(self, "_promotion_action_busy", False):
        return
    form, error = self._validate_promotion_form()
    if error:
        self.toast(error, "warning")
        return
    report = getattr(self, "_promotion_report", {}) or {}
    if report.get("real_packet_verified") is not True:
        self.toast("Chưa có verified Windows/Codex packet thật.", "warning")
        return
    live = getattr(self, "_promotion_live_observation", None)
    if not isinstance(live, dict):
        self.toast("Chưa có trusted live baseline.", "warning")
        return
    observed = str(live.get("baseline") or "")
    if decision in {"APPROVE", "REJECT"} and observed != COCKPIT_BASELINE:
        self.toast("Baseline đang drift; chỉ cho phép INVALIDATE.", "warning")
        return

    self._promotion_action_busy = True
    self._update_promotion_action_buttons()
    self.promotion_gate_label.configure(text="Đang recheck upstream baseline ngay trước khi ghi ledger…", fg=legacy.C["warning"])
    ctl = self._promotion_controller
    provider = self._promotion_live_provider

    def worker():
        try:
            result = ctl.record_review_action(decision=decision, reviewer_identity=form["reviewer_identity"],
                reviewer_salt=form["reviewer_salt"], lane=form["lane"], package_version=APP_VERSION,
                live_baseline_provider=provider.get_live_baseline, note_vi=form["note_vi"])
            self.root.after(0, lambda: self._finish_promotion_review(result=result))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self._finish_promotion_review(error=e))

    threading.Thread(target=worker, daemon=True).start()


def _finish_promotion_review(self, result=None, error=None):
    self._promotion_action_busy = False
    self.promotion_reviewer_salt.set("")
    if error is not None:
        self.toast(f"Reviewer action bị chặn: {error}", "danger")
        self.promotion_gate_label.configure(text=f"REVIEW ACTION: FAIL-CLOSED · {error}", fg=legacy.C["danger"])
        self._update_promotion_action_buttons()
        return
    result = result or {}
    effective = str(result.get("decision") or "")
    requested = str(result.get("requested_decision") or effective)
    if result.get("action_blocked_by_baseline_drift"):
        self.toast(f"Baseline drift: {requested} đã chuyển thành INVALIDATE.", "warning")
    else:
        self.toast(f"Đã ghi {effective} · lane {result.get('lane', '—')} · epoch {result.get('epoch', '—')}", "success")
    self.refresh_promotion_review()


def _extended_show_page(self, name, animate=True):
    if name != "promotion":
        return _ORIGINAL_SHOW_PAGE(self, name, animate=animate)
    if name not in self.pages:
        return
    old = self.pages.get(self.current_page)
    new = self.pages[name]
    if old is new and new.winfo_ismapped():
        self.refresh_promotion_review()
        return
    for key, item in self.nav.items():
        item.set_active(key == name)
    self.page_title.configure(text="Promotion review")
    self.page_subtitle.configure(text="Windows evidence · two-reviewer ledger · trusted live-baseline fail-closed gate")
    if old and old.winfo_ismapped():
        old.place_forget()
    self.current_page = name
    self.refresh_promotion_review()
    if not animate:
        new.place(x=0, y=0, relwidth=1, relheight=1)
        return
    new.place(x=18, y=0, relwidth=1, relheight=1)
    steps = 7

    def step(i=0):
        if i >= steps:
            new.place(x=0, y=0, relwidth=1, relheight=1)
            return
        x = int(18 * (1 - (i + 1) / steps))
        new.place(x=x, y=0, relwidth=1, relheight=1)
        self.root.after(18, lambda: step(i + 1))

    step()


legacy.HmsApp._build_shell = _extended_build_shell
legacy.HmsApp._build_pages = _extended_build_pages
legacy.HmsApp.show_page = _extended_show_page
legacy.HmsApp.refresh_promotion_review = _refresh_promotion_review
legacy.HmsApp._start_promotion_live_check = _start_promotion_live_check
legacy.HmsApp._apply_promotion_live_result = _apply_promotion_live_result
legacy.HmsApp._set_promotion_gate = _set_gate
legacy.HmsApp._refresh_promotion_gate_matrix = _refresh_gate_matrix
legacy.HmsApp._update_promotion_action_buttons = _update_promotion_action_buttons
legacy.HmsApp._validate_promotion_form = _validate_promotion_form
legacy.HmsApp.submit_promotion_review = _submit_promotion_review
legacy.HmsApp._finish_promotion_review = _finish_promotion_review


def extension_proof():
    checks = {
        "wrapper_version_25_75": legacy.APP_VERSION == APP_VERSION == "25.75",
        "promotion_page_hook_installed": legacy.HmsApp._build_pages is _extended_build_pages,
        "promotion_navigation_hook_installed": legacy.HmsApp.show_page is _extended_show_page,
        "controller_live_recheck_gate_available": hasattr(PromotionWorkbenchController, "record_review_action"),
        "trusted_live_provider_available": hasattr(CockpitLiveBaselineProvider, "get_live_baseline"),
        "reviewer_action_hook_installed": legacy.HmsApp.submit_promotion_review is _submit_promotion_review,
        "raw_reviewer_identity_not_persisted_by_gui": "write_text" not in _submit_promotion_review.__code__.co_names,
        "salt_cleared_after_action": "promotion_reviewer_salt" in _finish_promotion_review.__code__.co_names,
        "baseline_recheck_used_for_publication": "record_review_action" in _submit_promotion_review.__code__.co_names,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": APP_VERSION,
        "suite": "GUI_PROMOTION_REVIEW_EXTENSION_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def main():
    if "--proof" in sys.argv[1:]:
        result = extension_proof()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["verdict"] == "PASS" else 2
    legacy.HmsApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
