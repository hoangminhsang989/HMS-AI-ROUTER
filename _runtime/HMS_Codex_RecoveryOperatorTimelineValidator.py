#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.65'
def load(root):
 p=root/'HMS_Codex_RecoveryOperatorTimeline.py';s=importlib.util.spec_from_file_location('tl65',p);m=importlib.util.module_from_spec(s);sys.modules['tl65']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_8',sm.get('total')==8,sm)
 add('seven_phases',m.PHASES==('PREPARE','OBSERVE','EFFECT','DURABLE','VERIFY','DONE','OPERATOR_REQUIRED'))
 add('vietnamese_operator_required',m.VI['OPERATOR_REQUIRED']=='CẦN NGƯỜI VẬN HÀNH')
 src=(root/'HMS_Codex_RecoveryOperatorTimeline.py').read_text('utf-8');add('metadata_fields',all(x in src for x in ['source','freshness','safe_fingerprint_prefix','remediation_reason']))
 add('no_identity_projection','account' not in str(m.project_event({'account':'secret@example.invalid'},1)))
 add('bearer_redaction','REDACTED' in m.sanitize_reason('Bearer abcdef123456'))
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_OPERATOR_TIMELINE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
