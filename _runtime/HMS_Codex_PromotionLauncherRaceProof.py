#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION
from HMS_Codex_WindowsPromotionDecisionLedger import read_ledger
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController

RUNTIME_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_DIR.parent


def _launcher_chain_checks():
    vbs = (REPO_ROOT / "HMS_AI_ROUTER.vbs").read_text("utf-8")
    review = (RUNTIME_DIR / "HMS_GUI_REVIEW_ENTRY.pyw").read_text("utf-8")
    guarded = (RUNTIME_DIR / "HMS_GUI_ENTRY.pyw").read_text("utf-8")

    review_pos = vbs.find('HMS_GUI_REVIEW_ENTRY.pyw')
    guarded_pos = vbs.find('HMS_GUI_ENTRY.pyw')
    legacy_pos = vbs.find('HMS_GUI.pyw')
    return {
        "principal_launcher_names_reviewer_wrapper": review_pos >= 0,
        "fallback_order_review_guarded_legacy": 0 <= review_pos < guarded_pos < legacy_pos,
        "review_wrapper_loads_guarded_entry": 'BASE_ENTRY = RUNTIME_DIR / "HMS_GUI_ENTRY.pyw"' in review,
        "review_wrapper_installs_confirmation": "askyesno" in review and "_confirmed_submit_promotion_review" in review,
        "review_wrapper_uses_contract": "evaluate_gui_action_contract" in review,
        "guarded_entry_click_uses_controller_recheck": "record_review_action" in guarded and "get_live_baseline" in guarded,
        "launcher_never_prefers_legacy_while_review_exists": 'If Not fso.FileExists(gui) Then' in vbs and 'reviewGui' in vbs,
    }


def _click_time_race_checks():
    with tempfile.TemporaryDirectory() as d:
        ctl = PromotionWorkbenchController(Path(d) / "state")
        report = {
            "real_packet_verified": True,
            "case_matrix_complete": True,
            "raw_evidence_rewritten": False,
            "cockpit_baseline": COCKPIT_BASELINE,
            "reasons": [],
            "provenance": {
                "raw_packet_sha256": "a" * 64,
                "release_manifest_sha256": "b" * 64,
            },
            "import_digest": "c" * 64,
        }
        ctl._atomic_json(ctl.report_path, report)

        page_open_baseline = COCKPIT_BASELINE
        calls = []

        def click_time_provider():
            calls.append("click")
            return "1.3.29"

        result = ctl.record_review_action(
            decision="APPROVE",
            reviewer_identity="reviewer-a",
            reviewer_salt="race-proof-salt-0001",
            lane="TERMINAL_PTY",
            package_version=VERSION,
            live_baseline_provider=click_time_provider,
            note_vi="page opened at frozen baseline; upstream drifted before click",
        )
        ledger = read_ledger(ctl.ledger_path)
        return {
            "page_open_was_match": page_open_baseline == COCKPIT_BASELINE,
            "provider_called_at_click": calls == ["click"],
            "click_time_drift_blocks_approve": result["requested_decision"] == "APPROVE" and result["decision"] == "INVALIDATE",
            "click_time_drift_flagged": result["action_blocked_by_baseline_drift"] is True and result["baseline_recheck_passed"] is False,
            "observed_new_baseline_persisted": result["observed_cockpit_baseline"] == "1.3.29",
            "ledger_contains_only_invalidation": len(ledger) == 1 and ledger[0]["decision"] == "INVALIDATE" and ledger[0]["cockpit_baseline"] == "1.3.29",
            "no_auto_authority": result["automatic_production_certification"] is False and result["production_score_mutation_authorized"] is False,
        }


def synthetic_proof():
    checks = {}
    checks.update(_launcher_chain_checks())
    checks.update(_click_time_race_checks())
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(x["status"] == "PASS" for x in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "PROMOTION_LAUNCHER_CHAIN_AND_CLICK_TIME_RACE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
        "automatic_production_certification": False,
    }


if __name__ == "__main__":
    out = synthetic_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 2)
