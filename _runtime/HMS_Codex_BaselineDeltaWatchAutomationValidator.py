#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
VERSION='25.73'
def load(path):
 spec=importlib.util.spec_from_file_location('hms_delta73',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_BaselineDeltaWatchAutomation.py');p=m.synthetic_proof();add('proof_pass',p['verdict']=='PASS' and p['summary']['total']==9,p['summary']);add('baseline_exact',m.COCKPIT_BASELINE=='1.3.27')
 ok=m.evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27','source_digest_sha256':'a'*64},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.27','source_digest_sha256':'b'*64}])
 stale=m.evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27','source_digest_sha256':'a'*64},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.28','source_digest_sha256':'b'*64}])
 add('two_checkpoint_current_pass',not ok['promotion_frozen'])
 add('newer_freezes',stale['promotion_frozen'] and stale['verdict']=='PROMOTION_FROZEN_BASELINE_STALE')
 add('codex_only_delta_queue',len(stale['delta_audit_queue'])==1 and stale['delta_audit_queue'][0]['scope']=='CODEX_ONLY')
 add('no_auto_merge',stale['automatic_upstream_merge'] is False and stale['delta_audit_queue'][0]['automatic_merge'] is False)
 add('no_auto_promotion',stale['automatic_production_certification'] is False and stale['production_score_promotion_eligible'] is False)
 add('digest_bound',len(stale['watch_digest'])==64)
 add('antigravity_not_imported',stale['codex_only_scope'] and not stale['antigravity_scope_imported'])
 out={'version':VERSION,'suite':'BASELINE_DELTA_WATCH_AUTOMATION_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_promotion_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
