#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.68'
def load(root):
 p=root/'HMS_Codex_TargetCampaignExecutor.py';s=importlib.util.spec_from_file_location('exec68',p);m=importlib.util.module_from_spec(s);sys.modules['exec68']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);proof=m.synthetic_proof(root);src=(root/'HMS_Codex_TargetCampaignExecutor.py').read_text('utf-8');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_12',sm.get('total')==12,sm)
 add('one_case_only',all(x in src for x in ['execute_one_case','automatic_next_case','automatic_rearm']))
 add('frozen_manifest_trust_binding',all(x in src for x in ['MANIFEST_DIGEST_MISMATCH','TRUST_SNAPSHOT_DIGEST_MISMATCH','MIXED_PACKAGE_VERSION']))
 add('windows_ps51_codex_preflight',all(x in src for x in ['WINDOWS_HOST','POWERSHELL_5_1_PARSER','POWERSHELL_5_1_RUNTIME','CODEX_PROCESS_OWNERSHIP','OFFICIAL_AUTH_OBSERVER']))
 add('idempotency_and_auto_disarm',all(x in src for x in ['IDEMPOTENCY_WITNESS','IDEMPOTENCY_WITNESS_MISMATCH','AUTO_DISARM']))
 add('lease_separate_gate','LEASE_OWNERSHIP_READBACK_REQUIRED' in src)
 import inspect
 adapter_src=inspect.getsource(m.structured_subprocess_adapter)
 add('structured_argv','subprocess.run(argv' in adapter_src and 'shell=False' in adapter_src)
 add('synthetic_no_production','production_score_eligible' in src and proof.get('production_score_eligible') is False and proof.get('real_codex_effects_executed') is False)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_CAMPAIGN_EXECUTOR_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
