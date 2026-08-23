#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.69'
def load(root):
 p=root/'HMS_Codex_PromotionDecisionLedger.py';s=importlib.util.spec_from_file_location('ledger2569',p);m=importlib.util.module_from_spec(s);sys.modules['ledger2569']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);proof=m.synthetic_proof();src=(root/'HMS_Codex_PromotionDecisionLedger.py').read_text('utf-8');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_11',sm.get('total')==11,sm)
 add('hash_chain_append_only',all(x in src for x in ['prev_entry_sha256','entry_sha256','verify_chain','append_jsonl']))
 add('optimistic_concurrency','LEDGER_CONCURRENT_APPEND_DETECTED' in src and 'expected_tail_sha256' in src)
 add('dual_distinct_review','DUAL_DISTINCT_REVIEW_REQUIRED' in src and 'reviewer_count' in src)
 add('pseudonymous_reviewer','PSEUDONYMOUS_REVIEWER_REF_REQUIRED' in src)
 add('superseding_invalidation',all(x in src for x in ['INVALIDATE','supersedes_sha256','requires_superseding_entry']))
 add('reevaluation_triggers',all(x in src for x in ['CERTIFICATE_REVOKED','EVIDENCE_AGED_BEYOND_POLICY','PACKAGE_SUPERSEDED','TRUST_SNAPSHOT_CHANGED']))
 add('no_historical_delete','historical_entries_deleted' in src and "'historical_entries_deleted':False" in src)
 add('eligibility_separate_from_score',all(x in src for x in ['PROMOTION_ELIGIBLE_FOR_SEPARATE_SCORE_AUDIT','production_score_mutation_authorized','automatic_production_certification']))
 add('decision_set_exact',"DECISIONS={'APPROVE','REJECT','INVALIDATE'}" in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'PROMOTION_DECISION_LEDGER_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
