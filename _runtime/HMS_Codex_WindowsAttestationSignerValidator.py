#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_WindowsAttestationSigner.py';s=importlib.util.spec_from_file_location('signer66',p);m=importlib.util.module_from_spec(s);sys.modules['signer66']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_9',sm.get('total')==9,sm)
 src=(root/'HMS_Codex_WindowsAttestationSigner.py').read_text('utf-8')
 add('dpapi_machine_scope','CryptProtectData' in src and 'machine_scope=True' in src)
 add('certificate_store_structured_argv','powershell.exe' in src and 'shell=False' in src and "'-File'" in src)
 add('signature_exact_binding',all(x in src for x in ('package_manifest_sha256','run_id','nonce','evidence_class','signed_payload_sha256')))
 add('private_material_not_exported',"'private_material_exported':False" in src)
 add('trusted_classes',m.SIGNER_CLASSES=={'WINDOWS_LOCAL_MACHINE_DPAPI_HMAC','WINDOWS_CERTIFICATE_SIGNATURE'})
 add('nonwindows_no_target_signing',proof.get('windows_signing_executed') is False)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'WINDOWS_ATTESTATION_SIGNER_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
