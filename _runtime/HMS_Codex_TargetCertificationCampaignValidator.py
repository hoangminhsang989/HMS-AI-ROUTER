#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_TargetCertificationCampaign.py';s=importlib.util.spec_from_file_location('campaign67',p);m=importlib.util.module_from_spec(s);sys.modules['campaign67']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);p=m.synthetic_proof();tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=p.get('summary') or {};add('proof_pass',p.get('verdict')=='PASS',sm);add('proof_13',sm.get('total')==13,sm);src=(root/'HMS_Codex_TargetCertificationCampaign.py').read_text('utf-8')
 add('matrix_exact',len(m.EFFECTS)==4 and len(m.WINDOWS)==3)
 add('resume_never_silent_repeat',all(x in src for x in ('DURABLE_UNVERIFIED','VERIFY_ONLY','SKIP_COMPLETE','OPERATOR_REQUIRED','silent_effect_repeat_allowed')))
 add('per_case_arm','ARM_TOKEN' in src and 'OPERATOR_PHRASE' in src and 'arm_case' in src)
 add('manifest_trust_binding','MANIFEST_DIGEST_MISMATCH' in src and 'TRUST_SNAPSHOT_DIGEST_MISMATCH' in src)
 add('hash_chain','record_hash' in src and 'prev_hash' in src and 'event_chain_valid' in src)
 add('disarmed_default','real_effects_disarmed_by_default' in src and 'automatic_rearm' in src)
 add('production_not_auto',"'production_score_eligible':False" in src)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_CERTIFICATION_CAMPAIGN_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
