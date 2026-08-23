#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
VERSION="25.73";COCKPIT_BASELINE="1.3.27";HEX64=re.compile(r"^[0-9a-f]{64}$")
def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def sha(v:bytes|str):
    if isinstance(v,str):v=v.encode("utf-8","surrogatepass")
    return hashlib.sha256(v).hexdigest()

def audit(*,runtime_certificate:dict[str,Any],dual_review:dict[str,Any],current_package_version:str,current_manifest_sha256:str,current_cockpit_baseline:str=COCKPIT_BASELINE,current_feature_score:float=93.0,current_production_score:float=55.2)->dict[str,Any]:
    reasons=[]
    if runtime_certificate.get("windows_runtime_certified") is not True:reasons.append("WINDOWS_RUNTIME_CERTIFICATE_REQUIRED")
    if runtime_certificate.get("external_windows_target_evidence_imported") is not True:reasons.append("EXTERNAL_WINDOWS_EVIDENCE_REQUIRED")
    if runtime_certificate.get("case_matrix_complete") is not True:reasons.append("PARITY_RUNTIME_CASE_MATRIX_INCOMPLETE")
    if runtime_certificate.get("cockpit_baseline")!=current_cockpit_baseline:reasons.append("COCKPIT_BASELINE_CHANGED_OR_STALE")
    if dual_review.get("promotion_eligible") is not True or dual_review.get("dual_review_complete") is not True:reasons.append("DUAL_REVIEW_NOT_COMPLETE")
    if dual_review.get("automatic_production_certification") is not False or dual_review.get("production_score_mutation_authorized") is not False:reasons.append("UNSAFE_LEDGER_AUTHORITY")
    if not HEX64.fullmatch(str(current_manifest_sha256).lower()):reasons.append("CURRENT_MANIFEST_DIGEST_INVALID")
    if dual_review.get("package_version") not in (None,current_package_version):reasons.append("REVIEW_PACKAGE_MISMATCH")
    if dual_review.get("manifest_sha256") not in (None,current_manifest_sha256):reasons.append("REVIEW_MANIFEST_MISMATCH")
    eligible=not reasons
    report_refs=[x.get("report_sha256") for x in runtime_certificate.get("case_results") or [] if HEX64.fullmatch(str(x.get("report_sha256") or "").lower())]
    proposal={
        "decision":"ELIGIBLE_FOR_HUMAN_PRODUCTION_SCORE_REVIEW" if eligible else "KHONG_DU_DIEU_KIEN_DE_XET_NANG_PRODUCTION_SCORE",
        "summary_vi":"Đủ bằng chứng Windows/Codex thật và dual-review để con người xem xét thay đổi điểm production; auditor không tự sửa điểm." if eligible else "Chưa đủ bằng chứng để xét nâng điểm production; giữ nguyên điểm hiện tại.",
        "current_feature_score_pct":float(current_feature_score),"current_production_score_pct":float(current_production_score),
        "proposed_score_mutation":None,
        "requires_human_score_decision":eligible,
    }
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR","generated_utc":utcnow(),"cockpit_baseline":current_cockpit_baseline,"promotion_proposal_eligible":eligible,"reasons":sorted(set(reasons)),"proposal":proposal,"evidence_report_digests":sorted(report_refs),"runtime_campaign_digest":runtime_certificate.get("campaign_digest"),"ledger_tail_sha256":dual_review.get("ledger_tail_sha256"),"audit_digest":sha(stable({"runtime_campaign_digest":runtime_certificate.get("campaign_digest"),"ledger_tail_sha256":dual_review.get("ledger_tail_sha256"),"report_refs":sorted(report_refs),"reasons":sorted(set(reasons))})),"automatic_production_certification":False,"production_score_mutation_authorized":False}

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
    cert={"windows_runtime_certified":False,"external_windows_target_evidence_imported":False,"case_matrix_complete":False,"cockpit_baseline":COCKPIT_BASELINE,"campaign_digest":"a"*64,"case_results":[]}
    review={"promotion_eligible":False,"dual_review_complete":False,"automatic_production_certification":False,"production_score_mutation_authorized":False,"ledger_tail_sha256":"b"*64,"package_version":VERSION,"manifest_sha256":"c"*64}
    r0=audit(runtime_certificate=cert,dual_review=review,current_package_version=VERSION,current_manifest_sha256="c"*64)
    add("synthetic_or_missing_target_rejected",not r0["promotion_proposal_eligible"] and "WINDOWS_RUNTIME_CERTIFICATE_REQUIRED" in r0["reasons"])
    real=dict(cert);real.update({"windows_runtime_certified":True,"external_windows_target_evidence_imported":True,"case_matrix_complete":True,"case_results":[{"case_id":str(i),"report_sha256":sha(str(i))} for i in range(7)]})
    dual=dict(review);dual.update({"promotion_eligible":True,"dual_review_complete":True})
    r1=audit(runtime_certificate=real,dual_review=dual,current_package_version=VERSION,current_manifest_sha256="c"*64)
    add("complete_real_evidence_can_propose_human_review",r1["promotion_proposal_eligible"] and r1["proposal"]["requires_human_score_decision"] is True)
    add("auditor_never_mutates_score",r1["proposal"]["proposed_score_mutation"] is None and r1["production_score_mutation_authorized"] is False and r1["automatic_production_certification"] is False)
    stale=dict(real);stale["cockpit_baseline"]="1.3.28";r2=audit(runtime_certificate=stale,dual_review=dual,current_package_version=VERSION,current_manifest_sha256="c"*64)
    add("baseline_change_invalidates_proposal",not r2["promotion_proposal_eligible"] and "COCKPIT_BASELINE_CHANGED_OR_STALE" in r2["reasons"])
    bad_review=dict(dual);bad_review["dual_review_complete"]=False;r3=audit(runtime_certificate=real,dual_review=bad_review,current_package_version=VERSION,current_manifest_sha256="c"*64)
    add("dual_review_required",not r3["promotion_proposal_eligible"])
    unsafe=dict(dual);unsafe["production_score_mutation_authorized"]=True;r4=audit(runtime_certificate=real,dual_review=unsafe,current_package_version=VERSION,current_manifest_sha256="c"*64)
    add("unsafe_ledger_authority_rejected",not r4["promotion_proposal_eligible"] and "UNSAFE_LEDGER_AUTHORITY" in r4["reasons"])
    add("report_refs_digest_only",len(r1["evidence_report_digests"])==7 and all(HEX64.fullmatch(x) for x in r1["evidence_report_digests"]))
    add("vietnamese_explanation_present","điểm production" in r1["proposal"]["summary_vi"].lower())
    add("audit_digest_deterministic_shape",HEX64.fullmatch(r1["audit_digest"]) is not None)
    passed=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR_PROOF","generated_utc":utcnow(),"verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,"production_score_eligible":False,"automatic_production_certification":False,"production_score_mutation_authorized":False}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--proof",action="store_true");ap.add_argument("--output");a=ap.parse_args();out=synthetic_proof();text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+"\n","utf-8")
    print(text);return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
