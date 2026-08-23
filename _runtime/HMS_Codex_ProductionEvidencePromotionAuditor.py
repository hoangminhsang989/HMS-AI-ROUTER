#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

VERSION="25.75"; COCKPIT_BASELINE="1.3.28"; HEX64=re.compile(r"^[0-9a-f]{64}$")
def _hex(v): return HEX64.fullmatch(str(v or "").lower()) is not None
def _stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _sha(v): return hashlib.sha256(v if isinstance(v,bytes) else str(v).encode("utf-8","surrogatepass")).hexdigest()

def audit(*,dual_review,current_package_version,current_manifest_sha256,ingest_report=None,runtime_certificate=None,
          current_cockpit_baseline=COCKPIT_BASELINE,baseline_rechecked_before_publication=False,
          current_feature_score=93.0,current_production_score=55.2):
    ingest=ingest_report if isinstance(ingest_report,dict) else (runtime_certificate if isinstance(runtime_certificate,dict) else {})
    reasons=[]; provenance=ingest.get("provenance") if isinstance(ingest.get("provenance"),dict) else {}
    if ingest.get("real_packet_verified") is not True: reasons.append("REAL_EXTERNAL_WINDOWS_PACKET_REQUIRED")
    if ingest.get("case_matrix_complete") is not True or int(ingest.get("case_count") or 0)!=7: reasons.append("PARITY_RUNTIME_CASE_MATRIX_INCOMPLETE")
    if ingest.get("raw_evidence_rewritten") is not False: reasons.append("RAW_EVIDENCE_IMMUTABILITY_REQUIRED")
    if ingest.get("cockpit_baseline")!=current_cockpit_baseline or current_cockpit_baseline!=COCKPIT_BASELINE:
        reasons.append("COCKPIT_BASELINE_CHANGED_OR_STALE")
    if baseline_rechecked_before_publication is not True: reasons.append("BASELINE_RECHECK_BEFORE_PUBLICATION_REQUIRED")
    if not _hex(provenance.get("raw_packet_sha256")): reasons.append("RAW_PACKET_DIGEST_REQUIRED")
    if not _hex(provenance.get("trust_snapshot_sha256")): reasons.append("TRUST_SNAPSHOT_DIGEST_REQUIRED")
    if not _hex(provenance.get("signature_sha256")) or not provenance.get("signer_ref"): reasons.append("SIGNER_TRUST_EVIDENCE_REQUIRED")
    reports=provenance.get("case_report_sha256") if isinstance(provenance.get("case_report_sha256"),list) else []
    if len(reports)!=7 or any(not _hex(x) for x in reports) or len(set(reports))!=7: reasons.append("SEVEN_UNIQUE_CASE_DIGESTS_REQUIRED")
    if dual_review.get("promotion_eligible") is not True or dual_review.get("dual_review_complete") is not True:
        reasons.append("DUAL_REVIEW_NOT_COMPLETE")
    if int(dual_review.get("distinct_reviewer_count") or 0)<2: reasons.append("TWO_INDEPENDENT_REVIEWERS_REQUIRED")
    unsafe=("automatic_production_certification","production_score_mutation_authorized",
            "automatic_upstream_merge_authorized","automatic_real_effect_rearm_authorized")
    if any(dual_review.get(k) is not False for k in unsafe): reasons.append("UNSAFE_LEDGER_AUTHORITY")
    manifest=str(current_manifest_sha256 or "").lower()
    if not _hex(manifest): reasons.append("CURRENT_MANIFEST_DIGEST_INVALID")
    if dual_review.get("package_version") not in (None,current_package_version): reasons.append("REVIEW_PACKAGE_MISMATCH")
    if dual_review.get("manifest_sha256") not in (None,manifest): reasons.append("REVIEW_MANIFEST_MISMATCH")
    if dual_review.get("evidence_sha256") not in (None,str(provenance.get("raw_packet_sha256") or "").lower()):
        reasons.append("REVIEW_EVIDENCE_MISMATCH")
    eligible=not reasons
    proposal={"decision":"ELIGIBLE_FOR_HUMAN_PRODUCTION_SCORE_REVIEW" if eligible else "KHONG_DU_DIEU_KIEN_DE_XET_NANG_PRODUCTION_SCORE",
              "summary_vi":"Đủ evidence Windows/Codex thật và dual-review để con người xem xét; auditor không tự sửa điểm hay chứng nhận." if eligible
                           else "Chưa đủ gate để xét nâng production evidence; giữ nguyên điểm và trạng thái certification.",
              "current_feature_score_pct":float(current_feature_score),"current_production_score_pct":float(current_production_score),
              "proposed_score_mutation":None,"requires_human_score_decision":eligible}
    refs=sorted(str(x).lower() for x in reports if _hex(x))
    digest=_sha(_stable({"raw":provenance.get("raw_packet_sha256"),"ledger":dual_review.get("ledger_tail_sha256"),
                         "manifest":manifest,"baseline":current_cockpit_baseline,"refs":refs,"reasons":sorted(set(reasons))}))
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR",
            "cockpit_baseline":current_cockpit_baseline,"promotion_proposal_eligible":eligible,"reasons":sorted(set(reasons)),
            "proposal":proposal,"evidence_report_digests":refs,"raw_packet_sha256":provenance.get("raw_packet_sha256"),
            "ledger_tail_sha256":dual_review.get("ledger_tail_sha256"),"audit_digest":digest,
            "windows_runtime_certified":False,"external_windows_target_evidence_imported":False,
            "production_score_promotion_eligible":False,"automatic_production_certification":False,
            "production_score_mutation_authorized":False,"automatic_upstream_merge_authorized":False,
            "automatic_real_effect_rearm_authorized":False}

def synthetic_proof():
    h=lambda s:hashlib.sha256(s.encode()).hexdigest(); reports=[h(f"case-{i}") for i in range(7)]
    ing={"real_packet_verified":True,"case_matrix_complete":True,"case_count":7,"raw_evidence_rewritten":False,
         "cockpit_baseline":COCKPIT_BASELINE,"provenance":{"raw_packet_sha256":"a"*64,"trust_snapshot_sha256":"b"*64,
         "signature_sha256":"c"*64,"signer_ref":"signer-pseudo-001","case_report_sha256":reports}}
    review={"promotion_eligible":True,"dual_review_complete":True,"distinct_reviewer_count":2,"package_version":VERSION,
            "manifest_sha256":"d"*64,"evidence_sha256":"a"*64,"ledger_tail_sha256":"e"*64,
            "automatic_production_certification":False,"production_score_mutation_authorized":False,
            "automatic_upstream_merge_authorized":False,"automatic_real_effect_rearm_authorized":False}
    good=audit(ingest_report=ing,dual_review=review,current_package_version=VERSION,current_manifest_sha256="d"*64,
               baseline_rechecked_before_publication=True)
    no_recheck=audit(ingest_report=ing,dual_review=review,current_package_version=VERSION,current_manifest_sha256="d"*64)
    fake=dict(ing); fake["real_packet_verified"]=False
    rejected=audit(ingest_report=fake,dual_review=review,current_package_version=VERSION,current_manifest_sha256="d"*64,
                   baseline_rechecked_before_publication=True)
    unsafe=dict(review); unsafe["production_score_mutation_authorized"]=True
    unsafe_r=audit(ingest_report=ing,dual_review=unsafe,current_package_version=VERSION,current_manifest_sha256="d"*64,
                   baseline_rechecked_before_publication=True)
    checks={"real_dual_review_can_only_propose":good["promotion_proposal_eligible"] and good["proposal"]["proposed_score_mutation"] is None,
            "publication_baseline_recheck_required":"BASELINE_RECHECK_BEFORE_PUBLICATION_REQUIRED" in no_recheck["reasons"],
            "unverified_packet_rejected":"REAL_EXTERNAL_WINDOWS_PACKET_REQUIRED" in rejected["reasons"],
            "unsafe_ledger_rejected":"UNSAFE_LEDGER_AUTHORITY" in unsafe_r["reasons"],
            "scores_and_certification_never_auto_mutated":not good["windows_runtime_certified"] and not good["production_score_promotion_eligible"]
                and not good["production_score_mutation_authorized"],
            "seven_digest_refs_only":len(good["evidence_report_digests"])==7 and all(_hex(x) for x in good["evidence_report_digests"])}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR_PROOF",
            "verdict":"PASS" if n==len(tests) else "FAIL","summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},
            "tests":tests,"production_score_promotion_eligible":False,"windows_runtime_certified":False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--proof",action="store_true"); ap.add_argument("--output"); a=ap.parse_args()
    if not a.proof: ap.error("v25.75 CLI currently exposes --proof only; runtime callers use audit()")
    out=synthetic_proof(); text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text); return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
