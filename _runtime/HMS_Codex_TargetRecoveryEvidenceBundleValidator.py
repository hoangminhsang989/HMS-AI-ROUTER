#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.65'
def load(root):
 p=root/'HMS_Codex_TargetRecoveryEvidenceBundle.py';spec=importlib.util.spec_from_file_location('bun64',p);m=importlib.util.module_from_spec(spec);sys.modules['bun64']=m;spec.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_8',sm.get('total')==8,sm)
 add('four_evidence_classes',m.ALLOWED_CLASSES=={'LAB_PROCESS_KILL','LAB_FIXTURE','WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'})
 src=(root/'HMS_Codex_TargetRecoveryEvidenceBundle.py').read_text('utf-8')
 add('host_runtime_hashed','host_fingerprint' in src and 'runtime_fingerprint' in src and 'safe_ref' in src)
 add('source_payload_not_embedded','source_payloads_embedded' in src and 'project_observer' in src and 'project_real' in src)
 add('score_requires_attestation_gate',"'production_score_eligible':False" in src and 'HMS_Codex_AttestedEvidencePromotionGate.py' in src)
 add('bundle_sha256','bundle_sha256' in src and 'sha(stable(bundle))' in src)
 add('production_boundary',m.PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
 passed=sum(t['status']=='PASS' for t in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_certification':m.PRODUCTION_CLAIM}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
