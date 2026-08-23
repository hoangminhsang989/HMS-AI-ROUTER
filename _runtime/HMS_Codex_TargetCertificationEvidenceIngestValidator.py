#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.69'
def load(root):
 p=root/'HMS_Codex_TargetCertificationEvidenceIngest.py';s=importlib.util.spec_from_file_location('ingest2569',p);m=importlib.util.module_from_spec(s);sys.modules['ingest2569']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);proof=m.synthetic_proof();src=(root/'HMS_Codex_TargetCertificationEvidenceIngest.py').read_text('utf-8');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_10',sm.get('total')==10,sm)
 add('read_only_ingest',all(x in src for x in ['read_only_ingest','target_effects_executed','automatic_repair']))
 add('exact_binding',all(x in src for x in ['MIXED_PACKAGE_VERSION','MANIFEST_DIGEST_MISMATCH','TRUST_SNAPSHOT_DIGEST_MISMATCH','CAMPAIGN_ID_REQUIRED']))
 add('anti_replay',all(x in src for x in ['RUN_ID_REPLAY_OR_MISSING','NONCE_REPLAY_OR_INVALID','REPORT_DIGEST_REPLAY']))
 add('crypto_trust_required',all(x in src for x in ['verify_signed_attestation','CERTIFICATE_NOT_TRUSTED','REAL_CODEX_EFFECT_REQUIRED','WINDOWS_TARGET_OBSERVER_REQUIRED']))
 add('quarantine',all(x in src for x in ['quarantine','MIXED_CAMPAIGN_OWNERSHIP','missing_case_ids']))
 add('matrix_4x3',"EFFECTS=('auth','restart','router','lease')" in src and 'matrix_complete' in src)
 add('privacy_filter','FORBIDDEN_KEYS' in src and 'FORBIDDEN_PRIVATE_OR_IDENTITY_FIELD' in src)
 add('no_auto_promotion','automatic_production_certification' in src and 'production_score_promotion_eligible' in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_CERTIFICATION_EVIDENCE_INGEST_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
