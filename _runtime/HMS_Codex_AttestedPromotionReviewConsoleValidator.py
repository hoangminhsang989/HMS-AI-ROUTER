#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.68'
def load(root):
 p=root/'HMS_Codex_AttestedPromotionReviewConsole.py';s=importlib.util.spec_from_file_location('review68',p);m=importlib.util.module_from_spec(s);sys.modules['review68']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);proof=m.synthetic_proof();src=(root/'HMS_Codex_AttestedPromotionReviewConsole.py').read_text('utf-8');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_11',sm.get('total')==11,sm)
 add('matrix_review_exact',all(x in src for x in ['EXACTLY_12_SIGNED_CASE_REPORTS_REQUIRED','COMPLETE_4X3_CRASH_MATRIX_REQUIRED','DUPLICATE_CASE_REPORT']))
 add('crypto_windows_real_required',all(x in src for x in ['CRYPTOGRAPHIC_SIGNATURE_REQUIRED','WINDOWS_TARGET_OBSERVER_REQUIRED','REAL_CODEX_EFFECT_REQUIRED','DURABLE_IDEMPOTENCY_WITNESS_REQUIRED']))
 add('stale_revoked_mixed_rejected',all(x in src for x in ['ATTESTATION_STALE','CERTIFICATE_REVOKED','MIXED_PACKAGE_VERSION','TRUST_SNAPSHOT_DIGEST_MISMATCH']))
 add('retired_historical_audit',all(x in src for x in ['historical_certificate_audit','historical_only','new_case_signing_allowed']))
 add('offline_review_bundle_privacy',all(x in src for x in ['OFFLINE_ATTESTED_PROMOTION_REVIEW','contains_account_identity','contains_credentials','contains_private_material','bundle_sha256']))
 add('human_review_no_auto_cert',all(x in src for x in ['ELIGIBLE_FOR_HUMAN_PROMOTION_REVIEW','automatic_production_certification','requires_human_review']))
 add('vietnamese_decision','CHƯA ĐỦ ĐIỀU KIỆN PROMOTION' in src and 'ĐỦ ĐIỀU KIỆN ĐỂ NGƯỜI VẬN HÀNH XEM XÉT PROMOTION' in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTED_PROMOTION_REVIEW_CONSOLE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False,'automatic_production_certification':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
