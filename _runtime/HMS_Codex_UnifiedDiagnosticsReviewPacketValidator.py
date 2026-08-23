#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,tempfile,importlib.util,sys
from pathlib import Path
VERSION='25.74'
def load(path):
 spec=importlib.util.spec_from_file_location('hms_diag74',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_UnifiedDiagnostics.py')
 with tempfile.TemporaryDirectory(prefix='hms-diag74-') as td:
  d=Path(td);p=d/'startup-recovery-v2565'/'v2574';p.mkdir(parents=True)
  (p/'external-windows-review-packet-latest-v2574.json').write_text(json.dumps({'version':VERSION,'packet_state':'READY_FOR_HUMAN_REVIEW','packet_seq':1,'case_count':7,'immutable_raw_evidence':True,'derived_metadata_only':True,'review_packet_export_safe':True,'review_ledger':{'dual_review_complete':True},'reviewer_email':'secret@example.invalid','access_token':'SECRET74','generated_utc':'2026-08-23T07:00:00+00:00'}),'utf-8')
  (p/'baseline-drift-reconciliation-latest-v2574.json').write_text(json.dumps({'version':VERSION,'packet_state_after':'FROZEN_BASELINE_DRIFT','required_baseline':'1.3.27','observed_version':'1.3.28','baseline_drift_detected':True,'eligibility_invalidated':True,'superseding_invalidation_entry_count':2,'delta_audit_valid_for_evidence_reuse':True,'evidence_reuse_allowed_after_new_review_epoch':True,'new_dual_review_epoch_required':True,'reviewer_identity':'SECRET_REVIEWER74','generated_utc':'2026-08-23T07:01:00+00:00'}),'utf-8')
  ev1=m.external_windows_review_packet_events(d);ev2=m.baseline_drift_reconciliation_events(d);raw=json.dumps({'a':ev1,'b':ev2},ensure_ascii=False).lower()
  add('packet_event_present',len(ev1)==1 and ev1[0]['details']['case_count']==7)
  add('immutability_visible',ev1[0]['details']['immutable_raw_evidence'] is True and ev1[0]['details']['derived_metadata_only'] is True)
  add('dual_review_visible',ev1[0]['details']['dual_review_complete'] is True)
  add('baseline_drift_visible',len(ev2)==1 and ev2[0]['details']['baseline_drift_detected'] is True)
  add('invalidation_count_visible',ev2[0]['details']['superseding_invalidation_entry_count']==2)
  add('new_review_epoch_visible',ev2[0]['details']['new_dual_review_epoch_required'] is True)
  add('aggregate_only_no_identity_or_secret','secret@example.invalid' not in raw and 'secret74' not in raw and 'secret_reviewer74' not in raw)
  add('no_account_project_instance',all(not e.get('account') and not e.get('project') and not e.get('instance_id') for e in ev1+ev2))
  add('no_score_promotion',all(e['details']['production_score_eligible'] is False for e in ev1+ev2))
 out={'version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_REVIEW_PACKET_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
