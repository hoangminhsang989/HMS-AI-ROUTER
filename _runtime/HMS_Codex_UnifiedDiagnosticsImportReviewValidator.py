#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,tempfile,importlib.util,sys
from pathlib import Path
VERSION='25.73'
def load(path):
 spec=importlib.util.spec_from_file_location('hms_diag73',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_UnifiedDiagnostics.py')
 with tempfile.TemporaryDirectory(prefix='hms-diag73-') as td:
  d=Path(td);p=d/'startup-recovery-v2565'/'v2573';p.mkdir(parents=True)
  (p/'windows-target-import-review-latest-v2573.json').write_text(json.dumps({'version':VERSION,'review_ready_for_promotion_auditor':True,'accepted_count':7,'accepted_case_count':7,'quarantined_count':0,'ledger_entry_count_after':2,'external_windows_target_evidence_imported':True,'dual_review':{'dual_review_complete':True,'reviewer_count':2},'reviewer_email':'secret@example.invalid','access_token':'SECRET73','generated_utc':'2026-08-23T06:00:00+00:00'}),'utf-8')
  (p/'baseline-delta-watch-latest-v2573.json').write_text(json.dumps({'version':VERSION,'verdict':'BASELINE_CURRENT_TWO_CHECKPOINTS_PASS','required_baseline':'1.3.27','promotion_frozen':False,'observations':[{'checkpoint':'BEFORE_TARGET_IMPORT'},{'checkpoint':'BEFORE_PROMOTION_REVIEW'}],'delta_audit_queue':[],'codex_only_scope':True,'automatic_upstream_merge':False,'source_locator':'https://secret.example','generated_utc':'2026-08-23T06:01:00+00:00'}),'utf-8')
  ev1=m.windows_target_import_review_events(d);ev2=m.baseline_delta_watch_events(d);raw=json.dumps({'a':ev1,'b':ev2},ensure_ascii=False).lower()
  add('import_event_present',len(ev1)==1 and ev1[0]['details']['accepted_case_count']==7)
  add('dual_review_visible',ev1[0]['details']['dual_review_complete'] is True and ev1[0]['details']['reviewer_count']==2)
  add('baseline_two_checkpoints_visible',len(ev2)==1 and ev2[0]['details']['checkpoint_count']==2)
  add('baseline_freeze_visible_false',ev2[0]['details']['promotion_frozen'] is False)
  add('aggregate_only_no_identity_or_secret','secret@example.invalid' not in raw and 'secret73' not in raw and 'secret.example' not in raw)
  add('no_account_project_instance',all(not e.get('account') and not e.get('project') and not e.get('instance_id') for e in ev1+ev2))
  add('no_score_promotion',ev1[0]['details']['production_score_eligible'] is False and ev2[0]['details']['production_score_eligible'] is False)
 out={'version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_IMPORT_REVIEW_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
