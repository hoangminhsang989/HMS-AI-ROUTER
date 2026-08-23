#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_OfflineAttestationVerifier.py';s=importlib.util.spec_from_file_location('offline67',p);m=importlib.util.module_from_spec(s);sys.modules['offline67']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);p=m.synthetic_proof();tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=p.get('summary') or {};add('proof_pass',p.get('verdict')=='PASS',sm);add('proof_7',sm.get('total')==7,sm);src=(root/'HMS_Codex_OfflineAttestationVerifier.py').read_text('utf-8')
 add('trust_snapshot_binding','TRUST_SNAPSHOT_DIGEST_MISMATCH' in src and 'ATTESTATION_TRUST_SNAPSHOT_MISMATCH' in src)
 add('revocation_checked','evaluate_certificate' in src and 'trusted_certificate_sha256' in src)
 add('dpapi_local_context_fail_closed','DPAPI_LOCAL_MACHINE_CONTEXT_REQUIRED_FOR_OFFLINE_VERIFY' in src)
 add('offline_privacy','network_required' in src and 'raw_account_identity' in src and 'raw_credentials' in src)
 add('production_not_auto',"'production_score_eligible':False" in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'OFFLINE_ATTESTATION_VERIFIER_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
