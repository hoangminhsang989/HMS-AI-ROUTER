#!/usr/bin/env python3
from __future__ import annotations
import json
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE as INGEST_BASELINE, synthetic_proof as ingest_proof
from HMS_Codex_WindowsPromotionDecisionLedger import COCKPIT_BASELINE as LEDGER_BASELINE, synthetic_proof as ledger_proof
from HMS_Codex_WindowsPromotionReviewWorkbench import synthetic_proof as workbench_proof
from HMS_Codex_ProductionEvidencePromotionAuditor import COCKPIT_BASELINE as AUDITOR_BASELINE, synthetic_proof as auditor_proof

VERSION="25.75"; EXPECTED_BASELINE="1.3.28"

def validate():
    proofs={"ingest":ingest_proof(),"ledger":ledger_proof(),"workbench":workbench_proof(),"auditor":auditor_proof()}
    checks={}
    checks["baseline_authority_1_3_28"]=INGEST_BASELINE==LEDGER_BASELINE==AUDITOR_BASELINE==EXPECTED_BASELINE
    checks["all_component_proofs_pass"]=all(x.get("verdict")=="PASS" for x in proofs.values())
    checks["synthetic_never_certifies"]=proofs["ingest"].get("windows_runtime_certified") is False and proofs["auditor"].get("windows_runtime_certified") is False
    checks["synthetic_never_promotes_score"]=all(x.get("production_score_promotion_eligible") is False for x in proofs.values())
    checks["auditor_only_proposes"]=proofs["auditor"].get("production_score_promotion_eligible") is False
    checks["codex_only_scope"]="ANTIGRAVITY" not in json.dumps(proofs,ensure_ascii=False).upper()
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]
    n=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"CLAIM_BOUNDARY_VALIDATOR",
            "cockpit_baseline":EXPECTED_BASELINE,"verdict":"PASS" if n==len(tests) else "FAIL",
            "summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},"tests":tests,
            "windows_runtime_certified":False,"external_windows_target_evidence_imported":False,
            "production_score_promotion_eligible":False,"feature_evidence_pct":93.0,"production_evidence_pct":55.2}
if __name__=="__main__":
    out=validate(); print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out["verdict"]=="PASS" else 2)
