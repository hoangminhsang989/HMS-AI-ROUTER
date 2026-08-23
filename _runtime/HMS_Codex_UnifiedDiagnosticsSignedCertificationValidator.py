#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';s=importlib.util.spec_from_file_location('diag66',p);m=importlib.util.module_from_spec(s);sys.modules['diag66']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2566-diag-') as td:
  data=Path(td);d=data/'startup-recovery-v2565'/'v2566';d.mkdir(parents=True)
  fixtures=[('windows-attestation-signer-latest-v2566.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':8,'total':8},'windows_signing_executed':False,'private_key':'SECRET','account':'person@example.invalid','generated_utc':datetime.now(timezone.utc).isoformat()}),('target-cert-runbook-latest-v2566.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':8,'total':8},'real_codex_effects_executed':False,'auto_disarmed':True,'operator_phrase':'SECRET','generated_utc':datetime.now(timezone.utc).isoformat()}),('attestation-exchange-latest-v2566.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':6,'total':6},'token':'SECRET_TOKEN','generated_utc':datetime.now(timezone.utc).isoformat()})]
  for n,o in fixtures:(d/n).write_text(json.dumps(o),encoding='utf-8')
  r=m.build_report(data,max_events=600);raw=json.dumps(r,ensure_ascii=False)
  add('version_current',r.get('version') in {VERSION,'25.68','25.69','25.70','25.71','25.72','25.73','25.74'},r.get('version'));layers=r.get('layers') or {};add('signer_layer',layers.get('windows_attestation_signer')=='OK',layers);add('runbook_layer',layers.get('target_certification_runbook')=='OK',layers);add('exchange_layer',layers.get('attestation_exchange')=='OK',layers);add('no_secret','SECRET' not in raw and 'person@example.invalid' not in raw);add('metadata_only_no_execution','target_signing=False' in raw and 'auto_disarm=True' in raw)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_SIGNED_CERTIFICATION_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
