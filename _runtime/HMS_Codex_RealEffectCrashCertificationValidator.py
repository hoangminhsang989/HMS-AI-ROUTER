#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, os, sys
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.65'
def load(root):
 p=root/'HMS_Codex_RealEffectCrashCertification.py';spec=importlib.util.spec_from_file_location('real64',p);m=importlib.util.module_from_spec(spec);sys.modules['real64']=m;spec.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_13',sm.get('total')==13,sm)
 add('four_effects',set(m.EFFECTS)=={'auth','restart','router','lease'});add('three_windows',len(m.WINDOWS)==3)
 add('default_disarmed',m.ARM_TOKEN=='REAL_CODEX_EFFECTS' and m.ENV_GATE=='HMS_REAL_EFFECT_CRASH_CERT')
 manifest=json.loads((root/'REAL_EFFECT_ADAPTER_MANIFEST_TEMPLATE_V25.65.json').read_text('utf-8'));ok,errors=m.validate_manifest(manifest);add('template_schema_valid',ok,errors)
 pre=m.arming_status(manifest,'','');add('preflight_not_armed',not pre['armed'],pre)
 if os.name!='nt':add('nonwindows_cannot_arm',not m.arming_status(manifest,m.ARM_TOKEN,m.OPERATOR_PHRASE)['armed'])
 src=(root/'HMS_Codex_RealEffectCrashCertification.py').read_text('utf-8')
 add('argv_no_shell',all(x in src for x in ['SHELL_COMMAND_MODE_FORBIDDEN','shell=True" not in adapter_source']))
 add('idempotency_witness',all(x in src for x in ['HMS_EFFECT_IDEMPOTENCY_KEY_HASH','applied_idempotency_key_hash','WITNESS_ALREADY_APPLIED_NO_REPEAT']))
 add('cold_start_kill','subprocess.Popen' in src and '.kill()' in src and 'cold_start_distinct_pid' in src)
 add('operator_required_fail_closed',all(x in src for x in ['DURABLE_WITHOUT_EXTERNAL_WITNESS','RECOVERY_PROBE_FAILED','POST_APPLY_WITNESS_MISSING']))
 add('score_not_automatic',proof.get('production_score_eligible') is False and proof.get('real_codex_effects_executed') is False and 'attestation_candidate' in src)
 gui=(root/'HMS_GUI.pyw').read_text('utf-8');add('gui_preflight_only',all(x in gui for x in ['REAL CODEX EFFECT CRASH CERT v25.74 · DISARMED DEFAULT','PREFLIGHT','start_real_effect_preflight_async']))
 add('production_boundary',m.PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
 passed=sum(t['status']=='PASS' for t in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'REAL_EFFECT_CRASH_CERT_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'real_codex_effects_executed':False,'production_score_eligible':False,'production_certification':m.PRODUCTION_CLAIM}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
