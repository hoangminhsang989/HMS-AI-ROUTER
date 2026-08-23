#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile,subprocess,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.64'
def load(root:Path):
 p=root/'HMS_DiagnosticsBundle.py';spec=importlib.util.spec_from_file_location('db63',p);m=importlib.util.module_from_spec(spec);sys.modules['db63']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('allow_startup_latest',m.allowed(Path('startup-recovery-v2563')/'startup-recovery-latest-v2563.json'))
 add('allow_crash_latest',m.allowed(Path('startup-recovery-v2563')/'target-crash-harness-latest-v2563.json'))
 add('deny_auth_path',not m.allowed(Path('auth')/'startup-recovery-latest-v2563.json'))
 with tempfile.TemporaryDirectory(prefix='hms-v2563-bundle-') as td:
  base=Path(td);data=base/'data';runtime=base/'runtime';out=base/'out';p=data/'startup-recovery-v2563';p.mkdir(parents=True);runtime.mkdir()
  secrets=['ACCESS_SECRET_63','Bearer SUPER_SECRET_63','PROMPT_SECRET_63','raw@example.invalid']
  obj={'version':'25.63','status':'OPERATOR_REQUIRED','summary':{'unresolved_transactions':1},'access_token':secrets[0],'message':secrets[1],'prompt':secrets[2],'account':secrets[3]}
  crash={'version':'25.63','verdict':'PASS','summary':{'pass':12,'total':12},'message':'Bearer CRASH_SECRET_63','account':secrets[3]}
  (p/'startup-recovery-latest-v2563.json').write_text(json.dumps(obj),'utf-8');(p/'target-crash-harness-latest-v2563.json').write_text(json.dumps(crash),'utf-8')
  (runtime/'STARTUP_RECOVERY_RECONCILER_VALIDATION_V25.63.json').write_text(json.dumps(obj),'utf-8');(runtime/'TARGET_CRASH_HARNESS_VALIDATION_V25.63.json').write_text(json.dumps(crash),'utf-8')
  result=base/'result.json';rc=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(runtime),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True).returncode;add('bundle_command_pass',rc==0,rc)
  r=json.loads(result.read_text('utf-8'));zp=Path(r['path']);add('bundle_exists',zp.exists(),str(zp))
  with zipfile.ZipFile(zp) as z:
   names=z.namelist();blob='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names);mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json'))['version']
   add('startup_latest_included',any(n.endswith('startup-recovery-latest-v2563.json') for n in names),names);add('crash_latest_included',any(n.endswith('target-crash-harness-latest-v2563.json') for n in names),names);add('runtime_validators_included',any(n.endswith('STARTUP_RECOVERY_RECONCILER_VALIDATION_V25.63.json') for n in names) and any(n.endswith('TARGET_CRASH_HARNESS_VALIDATION_V25.63.json') for n in names),names);add('manifest_version_current',mv in {'25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},mv)
   add('access_token_redacted',secrets[0] not in blob);add('bearer_redacted','SUPER_SECRET_63' not in blob and 'CRASH_SECRET_63' not in blob);add('prompt_redacted',secrets[2] not in blob)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_STARTUP_RECOVERY','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
