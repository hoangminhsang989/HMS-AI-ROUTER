#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION="25.73"
def load(path:Path):
    spec=importlib.util.spec_from_file_location("hms_v2571_runtime_cert",path);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--output");a=ap.parse_args();root=Path(a.root).resolve();checks=[]
    def add(n,ok,d=None):checks.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
    m=load(root/"HMS_Codex_Cockpit1327WindowsRuntimeCertification.py");p=m.synthetic_proof()
    add("proof_pass",p.get("verdict")=="PASS" and p.get("summary",{}).get("total")==10,p.get("summary"))
    add("seven_runtime_cases",len(m.CASE_IDS)==7 and len(set(m.CASE_IDS))==7,m.CASE_IDS)
    add("baseline_1327",m.COCKPIT_BASELINE=="1.3.27")
    add("lab_never_certified",p.get("windows_runtime_certified") is False and p.get("production_score_eligible") is False)
    src=(root/"HMS_Codex_Cockpit1327WindowsRuntimeCertification.py").read_text("utf-8")
    add("requires_real_source_mode",'REAL_SOURCE_MODE = "REAL_WINDOWS_TARGET"' in src)
    add("requires_observer_and_real_effect",'REQUIRED_EVIDENCE_CLASSES = {"WINDOWS_TARGET_OBSERVER", "REAL_CODEX_EFFECT"}' in src)
    add("requires_exact_manifest",'MANIFEST_DIGEST_MISMATCH' in src)
    add("requires_current_cockpit_baseline",'COCKPIT_BASELINE_MISMATCH' in src)
    add("privacy_guards",all(x in src for x in ("RAW_ACCOUNT_ID_EXPORTED","CREDENTIAL_PAYLOAD_EXPORTED")))
    add("no_score_mutation_authority",'"production_score_mutation_authorized": False' in src and '"automatic_production_certification": False' in src)
    out={"version":VERSION,"suite":"COCKPIT_1327_WINDOWS_RUNTIME_CERTIFICATION_VALIDATION","summary":{"pass":sum(x["status"]=="PASS" for x in checks),"fail":sum(x["status"]=="FAIL" for x in checks),"total":len(checks)},"checks":checks,"windows_runtime_certified":False,"production_score_eligible":False}
    out["verdict"]="PASS" if out["summary"]["fail"]==0 else "FAIL";text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+"\n","utf-8")
    print(text);return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
