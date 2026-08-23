#!/usr/bin/env python3
from __future__ import annotations
import json
from HMS_Codex_WindowsPromotionReviewWorkbench import COCKPIT_BASELINE, VERSION, build_state, sensitive_paths

REQUIRED_GATES={"evidence","signature","trust","freshness","idempotency","reviewer_a_b","baseline"}

def validate():
    ingest={"real_packet_verified":True,"case_matrix_complete":True,"raw_evidence_rewritten":False,
            "cockpit_baseline":COCKPIT_BASELINE,"reasons":[],"provenance":{"raw_packet_sha256":"a"*64,
            "package_zip_sha256":"b"*64,"release_manifest_sha256":"c"*64,"token":"must-not-export"},"import_digest":"d"*64}
    state=build_state(ingest_report=ingest,ledger_records=[],package_version=VERSION,manifest_sha256="c"*64,
                      baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review=COCKPIT_BASELINE)
    drift=build_state(ingest_report=ingest,ledger_records=[],package_version=VERSION,manifest_sha256="c"*64,
                      baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review="1.3.29")
    checks={"seven_operator_gates_present":set(state.get("gates") or {})==REQUIRED_GATES,
            "status_review_required_without_dual_review":state.get("status")=="REVIEW_REQUIRED",
            "baseline_drift_visible":drift.get("status")=="FROZEN_BASELINE_DRIFT" and drift.get("requires_new_review_epoch") is True,
            "vietnamese_operator_message":any(x in state.get("summary_vi","").lower() for x in ("chưa","không","đủ")),
            "metadata_only_no_sensitive_fields":not sensitive_paths(state),
            "raw_evidence_not_embedded":state.get("raw_evidence_included") is False,
            "no_auto_score_or_certification":state.get("production_score_mutation_authorized") is False and state.get("automatic_production_certification") is False}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]
    n=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_REVIEW_PACKET_GUI_VALIDATOR",
            "cockpit_baseline":COCKPIT_BASELINE,"verdict":"PASS" if n==len(tests) else "FAIL",
            "summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},"tests":tests,
            "production_score_promotion_eligible":False}
if __name__=="__main__":
    out=validate(); print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out["verdict"]=="PASS" else 2)
