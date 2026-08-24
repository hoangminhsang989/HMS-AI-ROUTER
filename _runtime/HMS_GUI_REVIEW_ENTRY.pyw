#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
BASE_ENTRY = RUNTIME_DIR / "HMS_GUI_ENTRY.pyw"
APP_VERSION = "25.75"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))


def _load_base_entry():
    loader = importlib.machinery.SourceFileLoader("hms_gui_entry_v2575", str(BASE_ENTRY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Không thể tạo module spec cho HMS_GUI_ENTRY.pyw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


base = _load_base_entry()
legacy = base.legacy

from HMS_Codex_PromotionGUIActionContract import confirmation_text, evaluate_gui_action_contract
from HMS_Codex_WindowsPromotionDecisionLedger import read_ledger

_ORIGINAL_UPDATE_BUTTONS = legacy.HmsApp._update_promotion_action_buttons
_ORIGINAL_SUBMIT = legacy.HmsApp.submit_promotion_review
_ORIGINAL_APPLY_LIVE = legacy.HmsApp._apply_promotion_live_result
_ORIGINAL_REFRESH_GATES = legacy.HmsApp._refresh_promotion_gate_matrix
_ORIGINAL_REFRESH_REVIEW = legacy.HmsApp.refresh_promotion_review


def _current_contract(self):
    report = getattr(self, "_promotion_report", {}) or {}
    live = getattr(self, "_promotion_live_observation", None)
    identity = self.promotion_reviewer_identity.get() if hasattr(self, "promotion_reviewer_identity") else ""
    salt = self.promotion_reviewer_salt.get() if hasattr(self, "promotion_reviewer_salt") else ""
    lane = self.promotion_lane.get() if hasattr(self, "promotion_lane") else ""
    busy = bool(getattr(self, "_promotion_action_busy", False) or getattr(self, "_promotion_live_check_busy", False))
    return evaluate_gui_action_contract(report, live, reviewer_identity=identity, reviewer_salt=salt, lane=lane, busy=busy)


def _crypto_refresh_promotion_gate_matrix(self):
    _ORIGINAL_REFRESH_GATES(self)
    report = getattr(self, "_promotion_report", {}) or {}
    signer_trust = report.get("signer_trust") if isinstance(report.get("signer_trust"), dict) else {}
    authority = report.get("reviewer_trust_authority") if isinstance(report.get("reviewer_trust_authority"), dict) else {}
    crypto_ok = report.get("real_packet_verified") is True and signer_trust.get("valid") is True
    authority_ok = (
        crypto_ok
        and report.get("trust_anchor_match") is True
        and authority.get("valid") is True
        and authority.get("local_integrity_seal_valid") is True
        and authority.get("packet_derived") is False
    )
    self._set_promotion_gate("signature", crypto_ok, "CRYPTO PASS" if crypto_ok else "CRYPTO BLOCK")
    self._set_promotion_gate("trust", authority_ok, "AUTHORITY SEALED" if authority_ok else "AUTHORITY BLOCK")


def _sealed_refresh_promotion_review(self):
    C = legacy.C
    ctl = getattr(self, "_promotion_controller", None)
    if ctl is None:
        return
    integrity_error = ""
    try:
        report = ctl.load_verified_report()
    except Exception as exc:
        integrity_error = str(exc)
        report = {"real_packet_verified": False, "reasons": ["LOCAL_VERIFIED_METADATA_INVALID"],
                  "local_integrity_error": integrity_error}
    try:
        ledger = read_ledger(ctl.ledger_path)
    except Exception:
        ledger = []
    self._promotion_report = report
    self._promotion_ledger = ledger
    verified = report.get("real_packet_verified") is True
    self.promotion_baseline_label.configure(text=f"Frozen parity authority: Cockpit Tools {base.COCKPIT_BASELINE}")
    if integrity_error:
        self.promotion_packet_label.configure(text="External Windows packet: BLOCKED · local metadata seal invalid",
                                              fg=C["danger"])
    else:
        self.promotion_packet_label.configure(
            text=("External Windows packet: VERIFIED + SEALED" if verified else "External Windows packet: chưa có verified packet"),
            fg=C["success"] if verified else C["text2"])
    self.promotion_ledger_label.configure(
        text=f"Decision ledger: {len(ledger)} record(s) · raw reviewer identity/salt không được lưu")
    self.promotion_gate_label.configure(
        text=(f"LOCAL INTEGRITY GATE: BLOCK · {integrity_error}" if integrity_error
              else "LIVE BASELINE GATE: đang xác minh upstream; reviewer action khóa cho tới khi có kết quả."),
        fg=C["danger"] if integrity_error else C["warning"])
    self._refresh_promotion_gate_matrix()
    if not integrity_error:
        self._start_promotion_live_check()
    else:
        self._promotion_live_observation = None
        self._promotion_live_check_busy = False
        self._update_promotion_action_buttons()


def _policy_update_promotion_action_buttons(self):
    if not hasattr(self, "promotion_approve_btn"):
        return
    contract = self._promotion_gui_contract = _current_contract(self)
    buttons = contract["buttons"]
    self.promotion_approve_btn.set_enabled(buttons["APPROVE"])
    self.promotion_reject_btn.set_enabled(buttons["REJECT"])
    self.promotion_invalidate_btn.set_enabled(buttons["INVALIDATE"])


def _confirmed_submit_promotion_review(self, decision):
    decision = str(decision or "").upper()
    try:
        contract = _current_contract(self)
        if not contract["buttons"].get(decision, False):
            reasons = ", ".join(contract["policy"].get("reasons") or []) or "form/gate chưa hợp lệ"
            self.toast(f"Reviewer action đang bị khóa: {reasons}", "warning")
            return
        observed = contract["policy"].get("observed_baseline") or "—"
        lane = self.promotion_lane.get().strip().upper()
        if not legacy.messagebox.askyesno("Xác nhận Promotion Review", confirmation_text(decision, lane, observed), parent=self.root):
            self.toast("Đã hủy reviewer action; chưa ghi ledger.", "warning")
            return
        _ORIGINAL_SUBMIT(self, decision)
    finally:
        try:
            self.promotion_reviewer_salt.set("")
        except Exception:
            pass
        try:
            self._update_promotion_action_buttons()
        except Exception:
            pass


def _policy_apply_promotion_live_result(self, observation=None, error=None):
    _ORIGINAL_APPLY_LIVE(self, observation=observation, error=error)
    self._update_promotion_action_buttons()


legacy.HmsApp.refresh_promotion_review = _sealed_refresh_promotion_review
legacy.HmsApp._refresh_promotion_gate_matrix = _crypto_refresh_promotion_gate_matrix
legacy.HmsApp._update_promotion_action_buttons = _policy_update_promotion_action_buttons
legacy.HmsApp.submit_promotion_review = _confirmed_submit_promotion_review
legacy.HmsApp._apply_promotion_live_result = _policy_apply_promotion_live_result


def extension_proof():
    authority = {"valid": True, "local_integrity_seal_valid": True, "packet_derived": False,
                 "authority_sha256": "d" * 64, "trust_snapshot_sha256": "c" * 64}
    report = {"real_packet_verified": True, "reasons": [], "signer_trust": {"valid": True},
        "trust_anchor_match": True, "reviewer_trust_authority": authority,
        "provenance": {"raw_packet_sha256": "a" * 64, "release_manifest_sha256": "b" * 64,
                       "trust_snapshot_sha256": "c" * 64, "expected_trust_snapshot_sha256": "c" * 64}}
    match = {"source": "GITHUB_RELEASES_LATEST", "upstream_repository": "jlcodes99/cockpit-tools", "release_id": 1328,
        "checked_utc": "2026-08-23T00:00:00+00:00", "baseline": "1.3.28"}
    form = dict(reviewer_identity="reviewer-a", reviewer_salt="0123456789abcdef", lane="TERMINAL_PTY")
    good = evaluate_gui_action_contract(report, match, **form)
    drift = evaluate_gui_action_contract(report, dict(match, baseline="1.3.29", release_id=1329), **form)
    provider_error = evaluate_gui_action_contract(report, None, **form)
    bad_salt = evaluate_gui_action_contract(report, match, reviewer_identity="reviewer-a", reviewer_salt="short", lane="TERMINAL_PTY")
    no_crypto = evaluate_gui_action_contract(dict(report, signer_trust={"valid": False}), match, **form)
    no_anchor = evaluate_gui_action_contract(dict(report, trust_anchor_match=False), match, **form)
    no_authority = evaluate_gui_action_contract(dict(report, reviewer_trust_authority={}), match, **form)
    gate_consts = set(_crypto_refresh_promotion_gate_matrix.__code__.co_consts)
    checks = {
        "base_entry_loaded": getattr(base, "APP_VERSION", None) == APP_VERSION,
        "sealed_refresh_installed": legacy.HmsApp.refresh_promotion_review is _sealed_refresh_promotion_review,
        "sealed_refresh_uses_controller_loader": "load_verified_report" in _sealed_refresh_promotion_review.__code__.co_names,
        "visual_crypto_gate_override_installed": legacy.HmsApp._refresh_promotion_gate_matrix is _crypto_refresh_promotion_gate_matrix,
        "visual_gate_reads_crypto_result": "signer_trust" in gate_consts,
        "visual_gate_reads_reviewer_authority": "reviewer_trust_authority" in gate_consts,
        "policy_is_button_authority": legacy.HmsApp._update_promotion_action_buttons is _policy_update_promotion_action_buttons,
        "confirmation_wrapper_installed": legacy.HmsApp.submit_promotion_review is _confirmed_submit_promotion_review,
        "match_contract": all(good["buttons"].values()),
        "drift_contract": drift["buttons"] == {"APPROVE": False, "REJECT": False, "INVALIDATE": True},
        "provider_error_contract": not any(provider_error["buttons"].values()),
        "salt_invalid_contract": not any(bad_salt["buttons"].values()),
        "crypto_failure_contract": not any(no_crypto["buttons"].values()),
        "trust_anchor_failure_contract": not any(no_anchor["buttons"].values()),
        "reviewer_authority_failure_contract": not any(no_authority["buttons"].values()),
        "confirmation_required": good["confirmation_required"] is True,
        "salt_clear_required": good["salt_clear_required_after_attempt"] is True and "promotion_reviewer_salt" in _confirmed_submit_promotion_review.__code__.co_names,
        "no_auto_authority": not good["automatic_production_certification"] and not good["production_score_mutation_authorized"],
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {"product": "HMS-AI-ROUTER", "version": APP_VERSION, "suite": "GUI_REVIEW_POLICY_WRAPPER_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
        "tests": tests, "automatic_production_certification": False, "production_score_mutation_authorized": False}


def main():
    if "--proof" in sys.argv[1:]:
        out = extension_proof(); print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if out["verdict"] == "PASS" else 2
    legacy.HmsApp().run(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
