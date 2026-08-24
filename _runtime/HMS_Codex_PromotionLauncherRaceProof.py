#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS
from HMS_Codex_WindowsPromotionDecisionLedger import read_ledger
from HMS_Codex_WindowsPromotionWorkbenchController import (
    PromotionWorkbenchController, REPORT_SEAL_PURPOSE, _expected_import_digest, _verified_report_gate,
)

RUNTIME_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_DIR.parent


def _launcher_chain_checks():
    vbs = (REPO_ROOT / "HMS_AI_ROUTER.vbs").read_text("utf-8")
    recovery = (RUNTIME_DIR / "HMS_GUI_RECOVERY_ENTRY.pyw").read_text("utf-8")
    review = (RUNTIME_DIR / "HMS_GUI_REVIEW_ENTRY.pyw").read_text("utf-8")
    safe = (RUNTIME_DIR / "HMS_GUI_SAFE_FALLBACK.pyw").read_text("utf-8")
    guarded = (RUNTIME_DIR / "HMS_GUI_ENTRY.pyw").read_text("utf-8")
    recovery_impl = recovery[:recovery.find("def extension_proof")]
    safe_impl = safe[:safe.find("def source_proof")]

    recovery_pos = vbs.find('HMS_GUI_RECOVERY_ENTRY.pyw')
    review_pos = vbs.find('HMS_GUI_REVIEW_ENTRY.pyw')
    safe_pos = vbs.find('HMS_GUI_SAFE_FALLBACK.pyw')
    legacy_pos = vbs.find('HMS_GUI.pyw')

    recovery_assign = 'gui = base & "\\_runtime\\HMS_GUI_RECOVERY_ENTRY.pyw"'
    review_assign = 'reviewGui = base & "\\_runtime\\HMS_GUI_REVIEW_ENTRY.pyw"'
    safe_assign = 'safeGui = base & "\\_runtime\\HMS_GUI_SAFE_FALLBACK.pyw"'
    legacy_assign = 'legacyGui = base & "\\_runtime\\HMS_GUI.pyw"'
    fallback_review = 'If Not fso.FileExists(gui) Then gui = reviewGui'
    fallback_safe = 'If Not fso.FileExists(gui) Then gui = safeGui'
    fallback_legacy = 'If Not fso.FileExists(gui) Then gui = legacyGui'

    return {
        "principal_launcher_names_recovery_wrapper": recovery_pos >= 0 and recovery_assign in vbs,
        "fallback_order_recovery_review_safe_legacy": 0 <= recovery_pos < review_pos < safe_pos < legacy_pos,
        "fallback_is_three_stage_and_fail_closed": all(x in vbs for x in (fallback_review, fallback_safe, fallback_legacy))
            and vbs.find(fallback_review) < vbs.find(fallback_safe) < vbs.find(fallback_legacy),
        "launcher_does_not_fallback_to_guarded_promotion_entry": 'guardedGui' not in vbs and 'gui = base & "\\_runtime\\HMS_GUI_ENTRY.pyw"' not in vbs,
        "recovery_wrapper_chains_to_sealed_review_wrapper": 'REVIEW_ENTRY = RUNTIME_DIR / "HMS_GUI_REVIEW_ENTRY.pyw"' in recovery_impl
            and "review = _load_review_entry()" in recovery_impl and "legacy = review.legacy" in recovery_impl,
        "recovery_wrapper_bounds_retry": "_MAX_RECOVERY_RETRIES = 3" in recovery_impl and "RETRY_LIMIT_REACHED" in recovery_impl,
        "recovery_wrapper_keeps_background_quiet": "_BACKGROUND_TOKENS" in recovery_impl and "_is_interactive_backend_action" in recovery_impl,
        "recovery_wrapper_has_no_elevation_execution": "ShellExecute" not in recovery_impl and '"runas"' not in recovery_impl.lower(),
        "review_wrapper_loads_guarded_entry_when_principal_present": 'BASE_ENTRY = RUNTIME_DIR / "HMS_GUI_ENTRY.pyw"' in review,
        "review_wrapper_installs_confirmation": "askyesno" in review and "_confirmed_submit_promotion_review" in review,
        "review_wrapper_uses_contract": "evaluate_gui_action_contract" in review,
        "guarded_entry_click_uses_controller_recheck": "record_review_action" in guarded and "get_live_baseline" in guarded,
        "safe_fallback_loads_legacy_core_directly": 'LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"' in safe_impl,
        "safe_fallback_has_no_promotion_controller": "PromotionWorkbenchController" not in safe_impl and "submit_promotion_review" not in safe_impl,
        "legacy_only_final_fallback": review_assign in vbs and safe_assign in vbs and legacy_assign in vbs and vbs.count('gui = legacyGui') == 1,
    }


def _verified_fixture_report():
    trust="d"*64; cert="e"*64; sig="f"*64; signed="1"*64
    report={"real_packet_verified":True,"ingest_status":"VERIFIED_REAL_PACKET","case_matrix_complete":True,
        "case_matrix":{"valid":True,"missing":[],"unexpected":[],"duplicates":[]},"raw_evidence_rewritten":False,
        "cockpit_baseline":COCKPIT_BASELINE,"reasons":[],"trust_anchor_match":True,
        "signer_trust":{"valid":True,"trust_snapshot_sha256":trust,"certificate_sha256":cert,"signature_sha256":sig,
                        "signed_payload_sha256":signed,"signer_key_id_ref":"ref-"+("9"*24)},
        "reviewer_trust_authority":{"valid":True,"authority_sha256":"3"*64,"trust_snapshot_sha256":trust,
                                     "active_pin_count":1,"local_integrity_seal_valid":True,"packet_derived":False},
        "provenance":{"raw_packet_sha256":"a"*64,"package_zip_sha256":"2"*64,"release_manifest_sha256":"b"*64,
                      "trust_snapshot_sha256":trust,"expected_trust_snapshot_sha256":trust,"signature_sha256":sig,
                      "certificate_sha256":cert,"signed_payload_sha256":signed,"signer_key_id_ref":"ref-"+("9"*24),
                      "case_report_sha256":[str(i)*64 for i in range(2,9)],"required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS)}}
    report["import_digest"]=_expected_import_digest(report); return report


def _click_time_race_checks():
    with tempfile.TemporaryDirectory() as d:
        ctl=PromotionWorkbenchController(Path(d)/"state"); report=_verified_fixture_report()
        ctl._write_sealed_json(ctl.report_path,ctl.report_seal_path,report,REPORT_SEAL_PURPOSE)
        page_open_baseline=COCKPIT_BASELINE; calls=[]
        def click_time_provider(): calls.append("click"); return "1.3.29"
        result=ctl.record_review_action(decision="APPROVE",reviewer_identity="reviewer-a",reviewer_salt="race-proof-salt-0001",
            lane="TERMINAL_PTY",package_version=VERSION,live_baseline_provider=click_time_provider,
            note_vi="page opened at frozen baseline; upstream drifted before click")
        ledger=read_ledger(ctl.ledger_path)
        forged_ctl=PromotionWorkbenchController(Path(d)/"forged"); forged_ctl._atomic_json(forged_ctl.report_path,{"real_packet_verified":True})
        forged_blocked=False
        try:
            forged_ctl.record_review_action(decision="APPROVE",reviewer_identity="reviewer-z",reviewer_salt="race-proof-salt-0001",
                lane="TERMINAL_PTY",package_version=VERSION,live_baseline_provider=lambda:COCKPIT_BASELINE)
        except ValueError: forged_blocked=True
        return {
            "full_metadata_fixture_passes_controller_gate":_verified_report_gate(report)["valid"],
            "sealed_fixture_loads_through_controller":ctl.load_verified_report().get("real_packet_verified") is True,
            "page_open_was_match":page_open_baseline==COCKPIT_BASELINE,
            "provider_called_at_click":calls==["click"],
            "click_time_drift_blocks_approve":result["requested_decision"]=="APPROVE" and result["decision"]=="INVALIDATE",
            "click_time_drift_flagged":result["action_blocked_by_baseline_drift"] is True and result["baseline_recheck_passed"] is False,
            "observed_new_baseline_persisted":result["observed_cockpit_baseline"]=="1.3.29",
            "ledger_contains_only_invalidation":len(ledger)==1 and ledger[0]["decision"]=="INVALIDATE" and ledger[0]["cockpit_baseline"]=="1.3.29",
            "forged_minimal_ingest_metadata_blocked":forged_blocked and not forged_ctl.ledger_path.exists(),
            "no_auto_authority":result["automatic_production_certification"] is False and result["production_score_mutation_authorized"] is False,
        }


def synthetic_proof():
    checks={}; checks.update(_launcher_chain_checks()); checks.update(_click_time_race_checks())
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; passed=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PROMOTION_LAUNCHER_CHAIN_AND_CLICK_TIME_RACE_PROOF",
        "verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},
        "tests":tests,"synthetic_fixture_only":True,"windows_runtime_certified":False,
        "production_score_promotion_eligible":False,"automatic_production_certification":False}

if __name__=="__main__":
    out=synthetic_proof(); print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out["verdict"]=="PASS" else 2)
