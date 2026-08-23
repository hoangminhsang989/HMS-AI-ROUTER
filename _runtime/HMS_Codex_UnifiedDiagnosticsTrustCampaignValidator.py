#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';s=importlib.util.spec_from_file_location('diag67',p);m=importlib.util.module_from_spec(s);sys.modules['diag67']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2567-diag-') as td:
  data=Path(td);d=data/'startup-recovery-v2565'/'v2567';d.mkdir(parents=True)
  fixtures=[
   ('attestation-trust-store-latest-v2567.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':8,'total':8},'trust_snapshot':{'trust_snapshot_sha256':'a'*64},'private_key':'SECRET','account':'person@example.invalid','generated_utc':datetime.now(timezone.utc).isoformat()}),
   ('offline-attestation-verifier-latest-v2567.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':7,'total':7},'network_required':False,'token':'SECRET_TOKEN','generated_utc':datetime.now(timezone.utc).isoformat()}),
   ('target-cert-campaign-latest-v2567.json',{'version':VERSION,'verdict':'PASS','summary':{'pass':9,'total':9},'campaign':{'total_cases':12,'complete':False},'hostname':'PRIVATE-HOST','generated_utc':datetime.now(timezone.utc).isoformat()})]
  for n,o in fixtures:(d/n).write_text(json.dumps(o),encoding='utf-8')
  r=m.build_report(data,max_events=600);raw=json.dumps(r,ensure_ascii=False);layers=r.get('layers') or {}
  add('version_current',r.get('version') in {VERSION,'25.68','25.69','25.70','25.71','25.72','25.73','25.74'},r.get('version'));add('trust_layer',layers.get('attestation_trust_store')=='OK',layers);add('offline_layer',layers.get('offline_attestation_verifier')=='OK',layers);add('campaign_layer',layers.get('target_certification_campaign')=='OK',layers)
  add('no_identity_or_secret','SECRET' not in raw and 'person@example.invalid' not in raw and 'PRIVATE-HOST' not in raw)
  add('metadata_only','network_required=False' in raw and 'cases=12' in raw)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_TRUST_CAMPAIGN_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
