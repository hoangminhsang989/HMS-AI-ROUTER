#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION='25.74'
def load(path:Path):
 spec=importlib.util.spec_from_file_location('hms_reconcile74',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_BaselineDriftReconciliation.py');p=m.synthetic_proof();src=(root/'HMS_Codex_BaselineDriftReconciliation.py').read_text('utf-8')
 add('proof_pass',p.get('verdict')=='PASS' and p.get('summary',{}).get('total')==10,p.get('summary'))
 add('version_current',m.VERSION==VERSION)
 add('baseline_exact',m.COCKPIT_BASELINE=='1.3.27')
 add('newer_baseline_freezes',"'FROZEN_BASELINE_DRIFT'" in src and "'UPSTREAM_BASELINE_NEWER'" in src)
 add('superseding_invalidation_entries','decision=\'INVALIDATE\'' in src and 'supersedes_sha256' in src)
 add('append_only_ledger_reused','HMS_Codex_PromotionDecisionLedger.py' in src and 'verify_chain' in src)
 add('delta_audit_codex_only',"delta.get('scope')=='CODEX_ONLY'" in src and "delta.get('automatic_merge') is False" in src)
 add('capability_binding_required','prior_capability_binding_sha256' in src and 'unchanged_capability_ids' in src)
 add('no_silent_grandfathering',"'silent_grandfathering':False" in src and "'new_dual_review_epoch_required':newer" in src)
 add('no_auto_merge','automatic_upstream_merge' in src and "'automatic_upstream_merge':False" in src)
 add('no_score_mutation',all(x in src for x in ["'automatic_production_certification':False","'production_score_mutation_authorized':False","'production_score_promotion_eligible':False"]))
 add('codex_only_scope',"'codex_only_scope':True" in src and "'antigravity_scope_imported':False" in src)
 out={'version':VERSION,'suite':'BASELINE_DRIFT_RECONCILIATION_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_promotion_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
