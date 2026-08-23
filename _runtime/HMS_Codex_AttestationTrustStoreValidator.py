#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_AttestationTrustStore.py';s=importlib.util.spec_from_file_location('trust67',p);m=importlib.util.module_from_spec(s);sys.modules['trust67']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);p=m.synthetic_proof();tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=p.get('summary') or {};add('proof_pass',p.get('verdict')=='PASS',sm);add('proof_9',sm.get('total')==9,sm);src=(root/'HMS_Codex_AttestationTrustStore.py').read_text('utf-8')
 add('certificate_states',m.CERT_STATES=={'ACTIVE','RETIRED','REVOKED'})
 add('snapshot_deterministic','trust_snapshot_sha256' in src and 'sort_keys=True' in src)
 add('rotation_revocation','rotate_certificate' in src and 'revoke_certificate' in src and 'CERTIFICATE_REVOKED' in src)
 add('dpapi_lifecycle_metadata','register_dpapi_key' in src and 'sealed_blob_sha256' in src and p.get('trust_snapshot',{}).get('private_material_exported') is False)
 add('expiry_warning','CERTIFICATE_EXPIRING_SOON' in src and 'CERTIFICATE_EXPIRED' in src)
 add('production_not_auto',"'production_score_eligible':False" in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTATION_TRUST_STORE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
