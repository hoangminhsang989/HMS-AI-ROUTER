#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.69'
def run(root:Path):
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2569-unified-') as td:
  b=Path(td);data=b/'data';state=data/'startup-recovery-v2565'/'v2569';state.mkdir(parents=True)
  ingest={'version':VERSION,'verdict':'PASS','generated_utc':datetime.now(timezone.utc).isoformat(),'summary':{'accepted':12,'quarantined':0,'present_cases':12,'matrix_complete':True},'read_only_ingest':True,'reviewer_identity':'RAW REVIEWER','access_token':'SECRET69'}
  ledger={'version':VERSION,'verdict':'PASS','generated_utc':datetime.now(timezone.utc).isoformat(),'summary':{'entries':2},'dual_review_complete':True,'promotion_eligible':True,'production_score_mutation_authorized':False,'reviewer_email':'raw@example.invalid','private_material':'NOPE'}
  (state/'target-cert-evidence-ingest-latest-v2569.json').write_text(json.dumps(ingest),'utf-8');(state/'promotion-decision-ledger-latest-v2569.json').write_text(json.dumps(ledger),'utf-8')
  latest=b/'u.json';p=subprocess.run([sys.executable,str(root/'HMS_Codex_UnifiedDiagnostics.py'),'--data-dir',str(data),'--latest',str(latest),'--mode','refresh'],capture_output=True,text=True,timeout=60)
  r=(json.loads(p.stdout).get('unified_diagnostics') if p.returncode==0 else {}) or {};raw=json.dumps(r,ensure_ascii=False)
  add('unified_exit',p.returncode==0,p.stderr[-200:]);add('report_version',r.get('version') in {VERSION,'25.70','25.71','25.72','25.73','25.74'},r.get('version'));layers=r.get('layers') or {};add('ingest_layer',layers.get('target_certification_evidence_ingest')=='OK',layers.get('target_certification_evidence_ingest'));add('ledger_layer',layers.get('promotion_decision_ledger')=='OK',layers.get('promotion_decision_ledger'));by=r.get('by_source') or {};add('aggregate_sources',by.get('target-cert-evidence-ingest')==1 and by.get('promotion-decision-ledger')==1,by);add('no_raw_reviewer_or_secret',all(x not in raw for x in ('RAW REVIEWER','SECRET69','raw@example.invalid','NOPE')));add('metadata_only',((r.get('privacy') or {}).get('metadata_only') is True))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_EVIDENCE_LEDGER_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
