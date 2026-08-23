#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile,subprocess,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.65'
def load(root):
 p=root/'HMS_DiagnosticsBundle.py';s=importlib.util.spec_from_file_location('db65',p);m=importlib.util.module_from_spec(s);sys.modules['db65']=m;s.loader.exec_module(m);return m
def run(root):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 names=['windows-target-adapter-latest-v2565.json','attested-evidence-promotion-latest-v2565.json','recovery-operator-timeline-latest-v2565.json','real-effect-preflight-latest-v2565.json']
 for n in names:add('allow_'+n,m.allowed(Path('startup-recovery-v2565')/n))
 add('deny_auth_path',not m.allowed(Path('auth')/'windows-target-adapter-latest-v2565.json'))
 with tempfile.TemporaryDirectory(prefix='hms-v2565-bundle-') as td:
  b=Path(td);data=b/'data';runtime=b/'runtime';out=b/'out';state=data/'startup-recovery-v2565';state.mkdir(parents=True);runtime.mkdir()
  bad={'version':'25.65','verdict':'PASS','access_token':'ACCESS_SECRET_65','message':'Bearer SUPER_SECRET_65','prompt':'PROMPT_SECRET_65','account':'raw@example.invalid','hostname':'PRIVATE-HOST','nonce':'NONCE_SHOULD_NOT_LEAK'}
  for n in names:(state/n).write_text(json.dumps(bad),'utf-8')
  runtime_names=['WINDOWS_TARGET_ADAPTER_PACK_VALIDATION_V25.65.json','ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.65.json','RECOVERY_OPERATOR_TIMELINE_VALIDATION_V25.65.json']
  for n in runtime_names:(runtime/n).write_text(json.dumps(bad),'utf-8')
  result=b/'result.json';rc=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(runtime),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True).returncode;add('bundle_command_pass',rc==0,rc)
  r=json.loads(result.read_text('utf-8'));zp=Path(r['path']);add('bundle_exists',zp.exists(),str(zp))
  with zipfile.ZipFile(zp) as z:
   entries=z.namelist();blob='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in entries);mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json'))['version']
   add('four_state_files',all(any(e.endswith(n) for e in entries) for n in names),entries)
   add('runtime_validators',all(any(e.endswith(n) for e in entries) for n in runtime_names),entries)
   add('manifest_version',mv in {'25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},mv)
   add('access_redacted','ACCESS_SECRET_65' not in blob);add('bearer_redacted','SUPER_SECRET_65' not in blob);add('prompt_redacted','PROMPT_SECRET_65' not in blob);add('account_redacted','raw@example.invalid' not in blob);add('hostname_redacted','PRIVATE-HOST' not in blob)
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_ATTESTED_RECOVERY','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
