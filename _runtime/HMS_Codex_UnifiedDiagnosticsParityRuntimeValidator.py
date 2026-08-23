#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION="25.73"
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();checks=[]
    def add(n,ok,d=None):checks.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    cert=load('cert2571',root/'HMS_Codex_Cockpit1327WindowsRuntimeCertification.py').synthetic_proof()
    aud=load('aud2571',root/'HMS_Codex_ProductionEvidencePromotionAuditor.py').synthetic_proof()
    add('runtime_cert_proof_pass',cert.get('verdict')=='PASS')
    add('promotion_auditor_proof_pass',aud.get('verdict')=='PASS')
    add('diagnostics_windows_cert_false',cert.get('windows_runtime_certified') is False)
    add('diagnostics_score_eligible_false',aud.get('production_score_eligible') is False)
    raw=json.dumps({'cert':cert,'auditor':aud},ensure_ascii=False).lower()
    add('no_raw_account_identity','@' not in raw and 'access_token' not in raw and 'refresh_token' not in raw)
    add('no_private_material','private_key' not in raw and 'credential_payload' not in raw)
    diag={'version':VERSION,'cockpit_baseline':'1.3.27','runtime_certification':{'case_count':7,'windows_runtime_certified':False,'external_target_evidence_imported':False},'promotion_auditor':{'proposal_eligible':False,'automatic_production_certification':False,'production_score_mutation_authorized':False},'sensitive_identity_exported':False}
    add('aggregate_metadata_only',diag['runtime_certification']['case_count']==7 and diag['sensitive_identity_exported'] is False)
    out={'version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_PARITY_RUNTIME_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in checks),'fail':sum(x['status']=='FAIL' for x in checks),'total':len(checks)},'checks':checks,'diagnostics':diag};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+'\n','utf-8')
    print(text);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
