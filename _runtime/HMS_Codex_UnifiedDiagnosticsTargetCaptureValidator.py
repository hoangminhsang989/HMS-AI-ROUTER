#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,tempfile,importlib.util,sys
from pathlib import Path
VERSION='25.72'
def load(path):
 spec=importlib.util.spec_from_file_location('hms_diag72',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_UnifiedDiagnostics.py')
 with tempfile.TemporaryDirectory(prefix='hms-diag72-') as td:
  d=Path(td);p=d/'startup-recovery-v2565'/'v2572';p.mkdir(parents=True)
  (p/'windows-target-capture-kit-latest-v2572.json').write_text(json.dumps({'version':VERSION,'verdict':'PASS','summary':{'pass':10,'total':10},'real_codex_effects_executed':False,'windows_signing_executed':False,'account':'secret@example.invalid','access_token':'SECRET72','generated_utc':'2026-08-23T05:00:00+00:00'}),'utf-8')
  (p/'cockpit-baseline-watch-latest-v2572.json').write_text(json.dumps({'version':VERSION,'status':'CURRENT','required_baseline':'1.3.27','observed_version':'1.3.27','promotion_frozen':False,'delta_audit_required':False,'codex_only_scope':True,'source_locator':'https://secret.example','generated_utc':'2026-08-23T05:01:00+00:00'}),'utf-8')
  ev1=m.windows_target_capture_kit_events(d);ev2=m.cockpit_baseline_watch_events(d);raw=json.dumps({'a':ev1,'b':ev2},ensure_ascii=False).lower()
  add('capture_event_present',len(ev1)==1 and ev1[0]['details']['case_count']==7)
  add('baseline_event_present',len(ev2)==1 and ev2[0]['details']['status']=='CURRENT')
  add('aggregate_only','secret@example.invalid' not in raw and 'secret72' not in raw and 'secret.example' not in raw)
  add('no_identity_fields',all(not x[0].get('account') and not x[0].get('project') and not x[0].get('instance_id') for x in (ev1,ev2)))
  add('no_score_promotion',ev1[0]['details']['production_score_eligible'] is False and ev2[0]['details']['promotion_frozen'] is False)
  add('codex_baseline_visible',ev2[0]['details']['required_baseline']=='1.3.27' and ev2[0]['details']['observed_version']=='1.3.27')
  add('real_effect_execution_visible_false',ev1[0]['details']['real_codex_effects_executed'] is False)
 out={'version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_TARGET_CAPTURE_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
