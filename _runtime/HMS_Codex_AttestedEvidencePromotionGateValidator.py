#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_AttestedEvidencePromotionGate.py';s=importlib.util.spec_from_file_location('gate65',p);m=importlib.util.module_from_spec(s);sys.modules['gate65']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_9',sm.get('total')==9,sm)
 src=(root/'HMS_Codex_AttestedEvidencePromotionGate.py').read_text('utf-8')
 add('nonce_run_id','nonce' in src and 'run_id' in src and 'RUN_ID_REPLAY_OR_MISSING' in src and 'NONCE_REPLAY_OR_INVALID' in src)
 add('manifest_binding','package_manifest_sha256' in src and 'PACKAGE_MANIFEST_DIGEST_MISMATCH' in src)
 add('event_hash_chain','prev_hash' in src and 'EVENT_HASH_MISMATCH' in src and 'EVENT_SEQUENCE_OR_PREV_HASH' in src)
 add('mixed_version_reject','MIXED_PACKAGE_VERSION' in src)
 add('cryptographic_signer_required','verify_signed_attestation' in src and 'SIGNATURE_' in src)
 add('only_target_classes',m.ELIGIBLE_CLASSES=={'WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'})
 add('complete_4x3_matrix',m.REQUIRED_EFFECTS=={'auth','restart','router','lease'} and len(m.REQUIRED_WINDOWS)==3)
 add('separate_promotion_gate','production_score_promotion_eligible' in src and 'EVIDENCE_ELIGIBLE_FOR_SEPARATE_PRODUCTION_SCORE_AUDITOR_NOT_AUTOMATIC_CERTIFICATION' in src)
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_promotion_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
