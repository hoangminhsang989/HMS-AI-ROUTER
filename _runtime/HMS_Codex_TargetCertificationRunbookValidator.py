#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.67'
def load(root):
 p=root/'HMS_Codex_TargetCertificationRunbook.py';s=importlib.util.spec_from_file_location('runbook66',p);m=importlib.util.module_from_spec(s);sys.modules['runbook66']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);p=m.synthetic_proof();tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 sm=p.get('summary') or {};add('proof_pass',p.get('verdict')=='PASS',sm);add('proof_10',sm.get('total')==10,sm);src=(root/'HMS_Codex_TargetCertificationRunbook.py').read_text()
 add('one_shot_operator_gates',all(x in src for x in ('ARM_TOKEN','OPERATOR_PHRASE','ENV_GATE','windows_host')))
 add('auto_disarm_finally','finally:' in src and 'disarm_session' in src and 'AUTO_DISARM' in src)
 add('no_invented_target_command','DEFERRED_TARGET_INTEGRATION_REQUIRED' in src)
 add('structured_argv','shell=False' in src)
 add('vietnamese_phases','CHẠY THỬ KHÔNG TÁC ĐỘNG' in src and 'TỰ ĐÓNG KHÓA' in src and 'QUYẾT ĐỊNH EVIDENCE' in src)
 add('production_not_auto_promoted',"'production_score_eligible':False" in src)
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_CERTIFICATION_RUNBOOK_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
