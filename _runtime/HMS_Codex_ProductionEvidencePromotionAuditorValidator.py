#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION="25.73"
def load(path:Path):
    spec=importlib.util.spec_from_file_location("hms_v2571_promo_audit",path);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--output");a=ap.parse_args();root=Path(a.root).resolve();checks=[]
    def add(n,ok,d=None):checks.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
    m=load(root/"HMS_Codex_ProductionEvidencePromotionAuditor.py");p=m.synthetic_proof();src=(root/"HMS_Codex_ProductionEvidencePromotionAuditor.py").read_text("utf-8")
    add("proof_pass",p.get("verdict")=="PASS" and p.get("summary",{}).get("total")==9,p.get("summary"))
    add("baseline_1327",m.COCKPIT_BASELINE=="1.3.27")
    add("windows_certificate_required",'WINDOWS_RUNTIME_CERTIFICATE_REQUIRED' in src)
    add("external_evidence_required",'EXTERNAL_WINDOWS_EVIDENCE_REQUIRED' in src)
    add("dual_review_required",'DUAL_REVIEW_NOT_COMPLETE' in src)
    add("baseline_change_invalidates",'COCKPIT_BASELINE_CHANGED_OR_STALE' in src)
    add("human_proposal_only",'ELIGIBLE_FOR_HUMAN_PRODUCTION_SCORE_REVIEW' in src and '"proposed_score_mutation":None' in src.replace(' ',''))
    add("no_automatic_certification",'"automatic_production_certification":False' in src.replace(' ',''))
    add("no_score_mutation_authority",'"production_score_mutation_authorized":False' in src.replace(' ',''))
    add("digest_only_evidence_refs","evidence_report_digests" in src and "report_sha256" in src)
    out={"version":VERSION,"suite":"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR_VALIDATION","summary":{"pass":sum(x["status"]=="PASS" for x in checks),"fail":sum(x["status"]=="FAIL" for x in checks),"total":len(checks)},"checks":checks,"production_score_eligible":False,"automatic_production_certification":False};out["verdict"]="PASS" if out["summary"]["fail"]==0 else "FAIL";text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+"\n","utf-8")
    print(text);return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
