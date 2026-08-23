#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION='25.72'
def load(path:Path):
 spec=importlib.util.spec_from_file_location('hms_capture72',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_WindowsTargetEvidenceCaptureKit.py');p=m.synthetic_proof(root)
 add('proof_pass',p.get('verdict')=='PASS' and p.get('summary',{}).get('total')==10,p.get('summary'))
 add('seven_cases_exact',len(m.CASE_IDS)==7 and len(set(m.CASE_IDS))==7,m.CASE_IDS)
 add('cockpit_1327_bound',m.COCKPIT_BASELINE=='1.3.27')
 idx=m.build_kit_index(package_zip_sha256='a'*64,manifest_sha256='b'*64,codex_version='codex-fixture',trust_snapshot_sha256='c'*64)
 add('disarmed_one_case_only',idx['default_state']=='DISARMED' and not idx['automatic_next_case'] and not idx['automatic_rearm'] and all(x['one_case_only'] for x in idx['cases']))
 add('exact_zip_manifest_binding',idx['binding_valid'] and idx['package_zip_sha256']=='a'*64 and idx['release_manifest_sha256']=='b'*64)
 add('codex_version_bound',bool(idx['codex_version']) and str(idx['codex_version_ref']).startswith('ref-'))
 add('privacy_contract',all(v is False for v in idx['privacy'].values()))
 src=(root/'HMS_Codex_WindowsTargetEvidenceCaptureKit.py').read_text('utf-8')
 add('reuses_target_executor','HMS_Codex_TargetCampaignExecutor.py' in src and 'capture_only_orchestration' in src)
 add('requires_observer_real_effect',all(x in src for x in ['WINDOWS_TARGET_OBSERVER_REQUIRED','REAL_CODEX_EFFECT_REQUIRED','DURABLE_IDEMPOTENCY_WITNESS_REQUIRED']))
 kit=root/'windows_target_capture_kit_v25_72';add('portable_kit_files',all((kit/x).exists() for x in ['README_VI.md','00_BASELINE_WATCH.ps1','01_PREFLIGHT.ps1','02_ONE_CASE_ONLY.txt','03_PRIVACY_CHECK.ps1']))
 ps=(kit/'00_BASELINE_WATCH.ps1').read_text('utf-8');add('public_baseline_watch_script','api.github.com/repos/jlcodes99/cockpit-tools/releases/latest' in ps and 'STALE_BASELINE' in ps)
 add('no_auto_score_or_cert',idx['production_score_eligible'] is False and idx['automatic_production_certification'] is False)
 out={'version':VERSION,'suite':'WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
