#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from HMS_Codex_WindowsPromotionDecisionLedger import COCKPIT_BASELINE, VERSION, evaluate, read_ledger

SENSITIVE={"access_token","refresh_token","authorization","cookie","cookies","credential","credentials",
           "password","raw_identity","reviewer_identity","secret","token"}

def metadata_only(v):
    if isinstance(v,dict): return {str(k):metadata_only(x) for k,x in v.items() if str(k).lower() not in SENSITIVE}
    if isinstance(v,list): return [metadata_only(x) for x in v]
    return v

def build_state(*,ingest_report,ledger_records,package_version,manifest_sha256,baseline_at_open,
                baseline_before_final_review,optional_gpu_required=False):
    reasons=[]
    if ingest_report.get("real_packet_verified") is not True: reasons.append("QUARANTINE")
    if ingest_report.get("case_matrix_complete") is not True: reasons.append("RUNTIME_CASE_MATRIX_INCOMPLETE")
    if ingest_report.get("raw_evidence_rewritten") is not False: reasons.append("RAW_EVIDENCE_IMMUTABILITY_VIOLATION")
    provenance=ingest_report.get("provenance") if isinstance(ingest_report.get("provenance"),dict) else {}
    signer_trust=ingest_report.get("signer_trust") if isinstance(ingest_report.get("signer_trust"),dict) else {}
    crypto_ok=signer_trust.get("valid") is True
    anchor_ok=ingest_report.get("trust_anchor_match") is True
    if ingest_report.get("real_packet_verified") is True and not crypto_ok: reasons.append("CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED")
    if ingest_report.get("real_packet_verified") is True and not anchor_ok: reasons.append("INDEPENDENT_TRUST_ANCHOR_REQUIRED")
    evidence=str(provenance.get("raw_packet_sha256") or "").lower()
    baseline_ok=baseline_at_open==COCKPIT_BASELINE and baseline_before_final_review==COCKPIT_BASELINE and ingest_report.get("cockpit_baseline")==COCKPIT_BASELINE
    if not baseline_ok: reasons.append("FROZEN_BASELINE_DRIFT")
    review=evaluate(ledger_records,evidence_sha256=evidence,manifest_sha256=manifest_sha256,
                    package_version=package_version,current_cockpit_baseline=baseline_before_final_review,
                    optional_gpu_required=optional_gpu_required)
    if not review["promotion_eligible"]: reasons.extend(review["reasons"])
    eligible=not reasons
    if "FROZEN_BASELINE_DRIFT" in reasons:
        status="FROZEN_BASELINE_DRIFT"; text="Baseline Cockpit đã thay đổi. Phải append INVALIDATE, chạy Codex-only delta audit và mở epoch review mới."
    elif "QUARANTINE" in reasons:
        status="QUARANTINE"; text="Packet chưa được xác minh là evidence Windows/Codex thật; không được dùng để xét promotion."
    elif not eligible:
        status="REVIEW_REQUIRED"; text="Evidence hợp lệ nhưng chưa đủ hai reviewer độc lập cho tất cả lane bắt buộc."
    else:
        status="ELIGIBLE_FOR_HUMAN_PROMOTION_PROPOSAL"; text="Đủ gate để auditor tạo đề xuất cho con người; hệ thống không tự tăng điểm hay tự chứng nhận."
    ingest_reasons=ingest_report.get("reasons") or []
    gates={"evidence":ingest_report.get("real_packet_verified") is True,
           "signature":crypto_ok,
           "trust":crypto_ok and anchor_ok,
           "freshness":not any(x in ingest_reasons for x in ("EVIDENCE_STALE","CAPTURE_UTC_INVALID","CAPTURE_TIME_IN_FUTURE")),
           "idempotency":not any(str(x).endswith("_REPLAY") or x=="DUPLICATE_PACKET_DIGEST" for x in ingest_reasons),
           "reviewer_a_b":review["dual_review_complete"] is True,"baseline":baseline_ok}
    return metadata_only({"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_REVIEW_WORKBENCH",
        "status":status,"summary_vi":text,"gates":gates,"reasons":sorted(set(reasons)),
        "cockpit_baseline_required":COCKPIT_BASELINE,"baseline_at_open":baseline_at_open,
        "baseline_before_final_review":baseline_before_final_review,"evidence_provenance":provenance,
        "ingest_import_digest":ingest_report.get("import_digest"),"ledger_tail_sha256":review["ledger_tail_sha256"],
        "current_review_epoch":review["current_epoch"],"lane_summary":review["lane_summary"],
        "package_version":package_version,"manifest_sha256":manifest_sha256,
        "production_score_promotion_eligible":eligible,"requires_new_review_epoch":"FROZEN_BASELINE_DRIFT" in reasons,
        "automatic_production_certification":False,"production_score_mutation_authorized":False,
        "automatic_upstream_merge_authorized":False,"automatic_real_effect_rearm_authorized":False,
        "raw_evidence_included":False})

def sensitive_paths(v):
    out=[]
    def walk(x,p=""):
        if isinstance(x,dict):
            for k,y in x.items():
                q=f"{p}.{k}" if p else str(k)
                if str(k).lower() in SENSITIVE: out.append(q)
                walk(y,q)
        elif isinstance(x,list):
            for i,y in enumerate(x): walk(y,f"{p}[{i}]")
    walk(v); return out

def synthetic_proof():
    ing={"real_packet_verified":True,"case_matrix_complete":True,"raw_evidence_rewritten":False,
         "cockpit_baseline":COCKPIT_BASELINE,"reasons":[],"trust_anchor_match":True,"signer_trust":{"valid":True},
         "provenance":{"raw_packet_sha256":"a"*64,"package_zip_sha256":"c"*64,"release_manifest_sha256":"b"*64,
         "reviewer_identity":"secret-name"},"import_digest":"d"*64}
    state=build_state(ingest_report=ing,ledger_records=[],package_version=VERSION,manifest_sha256="b"*64,
                      baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review=COCKPIT_BASELINE)
    drift=build_state(ingest_report=ing,ledger_records=[],package_version=VERSION,manifest_sha256="b"*64,
                      baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review="1.3.29")
    no_anchor=json.loads(json.dumps(ing)); no_anchor["trust_anchor_match"]=False
    anchor_state=build_state(ingest_report=no_anchor,ledger_records=[],package_version=VERSION,manifest_sha256="b"*64,
                             baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review=COCKPIT_BASELINE)
    checks={"zero_reviewer_never_promotes":not state["production_score_promotion_eligible"],
            "baseline_drift_freezes":drift["status"]=="FROZEN_BASELINE_DRIFT" and drift["requires_new_review_epoch"],
            "metadata_only_export":not sensitive_paths(state),
            "crypto_signature_gate_authoritative":state["gates"]["signature"] is True,
            "independent_trust_anchor_gate":state["gates"]["trust"] is True and anchor_state["gates"]["trust"] is False,
            "anchor_missing_never_promotes":not anchor_state["production_score_promotion_eligible"],
            "no_auto_authority":not state["automatic_production_certification"] and not state["production_score_mutation_authorized"],
            "vietnamese_guidance":any(x in state["summary_vi"].lower() for x in ("chưa","không","đủ"))}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_REVIEW_WORKBENCH_PROOF",
            "verdict":"PASS" if n==len(tests) else "FAIL","summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},
            "tests":tests,"production_score_promotion_eligible":False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--proof",action="store_true"); ap.add_argument("--ingest-report")
    ap.add_argument("--ledger"); ap.add_argument("--package-version"); ap.add_argument("--manifest-sha256")
    ap.add_argument("--baseline-at-open",default=COCKPIT_BASELINE); ap.add_argument("--baseline-before-final-review",default=COCKPIT_BASELINE)
    ap.add_argument("--optional-gpu-required",action="store_true"); ap.add_argument("--output"); a=ap.parse_args()
    if a.proof: out=synthetic_proof(); code=0 if out["verdict"]=="PASS" else 2
    else:
        if not(a.ingest_report and a.ledger and a.package_version and a.manifest_sha256): ap.error("workbench inputs required")
        ing=json.loads(Path(a.ingest_report).read_text("utf-8")); out=build_state(ingest_report=ing,
            ledger_records=read_ledger(Path(a.ledger)),package_version=a.package_version,manifest_sha256=a.manifest_sha256,
            baseline_at_open=a.baseline_at_open,baseline_before_final_review=a.baseline_before_final_review,
            optional_gpu_required=a.optional_gpu_required); code=0 if out["production_score_promotion_eligible"] else 4
    text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text); return code
if __name__=="__main__": raise SystemExit(main())
