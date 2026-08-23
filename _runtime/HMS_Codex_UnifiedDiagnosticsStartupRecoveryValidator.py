#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.64'
def load(root:Path):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';spec=importlib.util.spec_from_file_location('ud63',p);m=importlib.util.module_from_spec(spec);sys.modules['ud63']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2563-ud-') as td:
  data=Path(td);p=data/'startup-recovery-v2563';p.mkdir(parents=True)
  startup={'version':'25.63','generated_utc':'2026-08-22T14:00:00+00:00','status':'OPERATOR_REQUIRED','summary':{'journals_discovered':2,'unresolved_transactions':1,'operator_required':1,'degraded_safe':0,'blocked_conflicting_actions':23},'timeline':[{'transaction_ref':'SECRET_TXN','effect_fingerprint':'SECRET_EFF','account':'raw@example.invalid','access_token':'SECRET_TOKEN'}],'production_certification':'NOT_CLAIMED_STARTUP_RECONCILER_TARGET_MACHINE_LIVE_REQUIRED'}
  crash={'version':'25.63','generated_utc':'2026-08-22T14:01:00+00:00','verdict':'PASS','summary':{'pass':12,'total':12,'crash_cases':12},'host':{'windows_target_evidence':False},'cases':[{'pid':123,'secret':'SECRET_CASE'}],'safety':{'real_codex_effects_executed':False,'production_certification':'NOT_CLAIMED_OS_PROCESS_KILL_LAB_REAL_CODEX_EFFECTS_NOT_EXECUTED'}}
  (p/'startup-recovery-latest-v2563.json').write_text(json.dumps(startup),'utf-8');(p/'target-crash-harness-latest-v2563.json').write_text(json.dumps(crash),'utf-8')
  ev=m.startup_recovery_events(data);add('startup_one_aggregate_event',len(ev)==1,len(ev));e=ev[0] if ev else {};raw=json.dumps(e,ensure_ascii=False)
  add('startup_source',e.get('source')=='startup-recovery',e.get('source'));add('startup_kind',e.get('kind')=='STARTUP_RECOVERY_GATE',e.get('kind'))
  add('startup_counts_projected','unresolved=1' in e.get('message','') and 'blocked=23' in e.get('message',''),e.get('message'))
  add('startup_identity_not_projected',all(x not in raw for x in ['SECRET_TXN','SECRET_EFF','raw@example.invalid','SECRET_TOKEN']))
  ce=m.target_crash_harness_events(data);add('crash_one_aggregate_event',len(ce)==1,len(ce));c=ce[0] if ce else {};craw=json.dumps(c,ensure_ascii=False)
  add('crash_source',c.get('source')=='target-crash-harness',c.get('source'));add('crash_cases_aggregate','crash_cases=12' in c.get('message',''),c.get('message'))
  add('crash_case_details_not_projected','SECRET_CASE' not in craw and '123' not in craw)
  report=m.build_report(data);rr=json.dumps(report,ensure_ascii=False)
  add('report_version_current',report.get('version') in {'25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},report.get('version'));add('startup_layer_error',(report.get('layers') or {}).get('startup_recovery')=='ERROR',(report.get('layers') or {}).get('startup_recovery'));add('crash_layer_ok',(report.get('layers') or {}).get('target_crash_harness')=='OK',(report.get('layers') or {}).get('target_crash_harness'))
  add('report_privacy',all(x not in rr for x in ['SECRET_TXN','SECRET_EFF','raw@example.invalid','SECRET_TOKEN','SECRET_CASE']))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_STARTUP_RECOVERY_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
