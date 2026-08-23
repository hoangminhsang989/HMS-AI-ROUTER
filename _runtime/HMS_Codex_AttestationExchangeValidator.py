#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_AttestationExchange.py';s=importlib.util.spec_from_file_location('exchange66',p);m=importlib.util.module_from_spec(s);sys.modules['exchange66']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);p=m.synthetic_proof();tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=p.get('summary') or {};add('proof_pass',p.get('verdict')=='PASS',sm);add('proof_6',sm.get('total')==6,sm);src=(root/'HMS_Codex_AttestationExchange.py').read_text()
 add('privacy_forbidden_keys','command_line' in src and 'private_key' in src and 'raw_hostname' in src)
 add('bundle_integrity','bundle_sha256' in src and 'BUNDLE_HASH_MISMATCH' in src)
 add('vietnamese_explanation','CHƯA ĐỦ ĐIỀU KIỆN' in src and 'automatic_production_certification' in src)
 add('production_not_auto',"'production_score_eligible':False" in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTATION_EXCHANGE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
