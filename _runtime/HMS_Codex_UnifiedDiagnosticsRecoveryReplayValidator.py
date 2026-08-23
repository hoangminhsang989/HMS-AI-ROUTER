#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.62'
def load(root:Path):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';spec=importlib.util.spec_from_file_location('ud62',p);m=importlib.util.module_from_spec(spec);sys.modules['ud62']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2562-ud-') as td:
  data=Path(td);p=data/'recovery-replay-v2562';p.mkdir(parents=True)
  payload={'version':'25.62','generated_utc':'2026-08-22T11:00:00+00:00','verdict':'PASS','summary':{'pass':18,'fail':0,'total':18,'crash_cases':30},'safety':{'at_most_once_durable_side_effect':True,'ownership_proof_required_for_compensation':True,'production_certification':'NOT_CLAIMED_RECOVERY_REPLAY_SYNTHETIC_ONLY'},'txn_id':'SECRET_TXN','effects':[{'account':'raw@example.invalid','access_token':'SECRET_TOKEN','prompt':'SECRET_PROMPT'}]}
  (p/'recovery-replay-latest-v2562.json').write_text(json.dumps(payload),'utf-8')
  ev=m.recovery_replay_events(data);add('one_aggregate_event',len(ev)==1,len(ev));e=ev[0] if ev else {}
  add('source_recovery_replay',e.get('source')=='recovery-replay',e.get('source'));add('kind_replay_proof',e.get('kind')=='MULTI_SUBSYSTEM_REPLAY_PROOF',e.get('kind'))
  raw=json.dumps(e,ensure_ascii=False);add('raw_txn_not_projected','SECRET_TXN' not in raw);add('account_not_projected','raw@example.invalid' not in raw and not e.get('account'));add('token_not_projected','SECRET_TOKEN' not in raw);add('prompt_not_projected','SECRET_PROMPT' not in raw)
  add('aggregate_crash_count','crash_cases=30' in e.get('message',''),e.get('message'));add('at_most_once_aggregate','at_most_once=True' in e.get('message',''),e.get('message'));add('ownership_aggregate','ownership_proof=True' in e.get('message',''),e.get('message'))
  report=m.build_report(data);add('report_version_25_62',str(report.get('version') or '')>='25.62',report.get('version'));add('layer_ok',(report.get('layers') or {}).get('recovery_replay')=='OK',(report.get('layers') or {}).get('recovery_replay'));add('report_metadata_only',(report.get('privacy') or {}).get('metadata_only') is True and all(x not in json.dumps(report,ensure_ascii=False) for x in ('SECRET_TXN','SECRET_TOKEN','SECRET_PROMPT','raw@example.invalid')))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_RECOVERY_REPLAY_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
