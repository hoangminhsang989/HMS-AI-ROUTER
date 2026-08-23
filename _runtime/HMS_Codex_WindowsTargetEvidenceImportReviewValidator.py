#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION='25.73'
def load(path:Path):
 spec=importlib.util.spec_from_file_location('hms_import73',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_WindowsTargetEvidenceImportReview.py');p=m.synthetic_proof()
 add('proof_pass',p.get('verdict')=='PASS' and p.get('summary',{}).get('total')==10,p.get('summary'))
 add('seven_runtime_cases_exact',len(m.CASE_IDS)==7 and len(set(m.CASE_IDS))==7,m.CASE_IDS)
 add('target_package_is_v2572',m.TARGET_PACKAGE_VERSION=='25.72')
 add('cockpit_baseline_exact',m.COCKPIT_BASELINE=='1.3.27')
 src=(root/'HMS_Codex_WindowsTargetEvidenceImportReview.py').read_text('utf-8')
 add('cryptographic_verification_required','verify_signed_attestation' in src and 'SYNTHETIC_SIGNATURE_FIXTURE_FORBIDDEN' in src)
 add('two_baseline_checkpoints_required',"('BEFORE_IMPORT',baseline_before_import)" in src and "('BEFORE_PROMOTION_REVIEW',baseline_before_review)" in src and any(t.get('name')=='second_baseline_checkpoint_can_freeze' and t.get('status')=='PASS' for t in p.get('tests',[])))
 add('replay_guards_present',all(x in src for x in ['RUN_ID_REPLAY_OR_MISSING','NONCE_REPLAY_OR_INVALID','REPORT_DIGEST_REPLAY']))
 add('dual_review_ledger_reused','HMS_Codex_PromotionDecisionLedger.py' in src and 'evaluate_dual_review' in src)
 add('runtime_certifier_reused','HMS_Codex_Cockpit1327WindowsRuntimeCertification.py' in src and 'evaluate_runtime_campaign' in src)
 add('read_only_import_no_effect',"'read_only_import':True" in src and "'target_effects_executed_during_import':False" in src)
 add('no_auto_score_or_cert',"'production_score_mutation_authorized':False" in src and "'automatic_production_certification':False" in src)
 add('codex_only_scope',"'codex_only_scope':True" in src and "'antigravity_scope_imported':False" in src)
 out={'version':VERSION,'suite':'WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_promotion_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
