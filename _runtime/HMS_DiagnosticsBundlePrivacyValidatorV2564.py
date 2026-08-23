#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile,subprocess,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.64'
def load(root:Path):
 p=root/'HMS_DiagnosticsBundle.py';spec=importlib.util.spec_from_file_location('db64',p);m=importlib.util.module_from_spec(spec);sys.modules['db64']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 for name in ['startup-recovery-latest-v2564.json','windows-recovery-observer-latest-v2564.json','real-effect-preflight-latest-v2564.json','real-effect-crash-cert-latest-v2564.json','target-recovery-evidence-latest-v2564.json']:
  add('allow_'+name,m.allowed(Path('startup-recovery-v2564')/name))
 add('deny_auth_path',not m.allowed(Path('auth')/'windows-recovery-observer-latest-v2564.json'))
 with tempfile.TemporaryDirectory(prefix='hms-v2564-bundle-') as td:
  base=Path(td);data=base/'data';runtime=base/'runtime';out=base/'out';state=data/'startup-recovery-v2564';state.mkdir(parents=True);runtime.mkdir()
  bad={'version':'25.64','verdict':'PASS','summary':{'available':4,'total':4},'evidence':{'class':'WINDOWS_TARGET_OBSERVER','production_score_eligible':False},'access_token':'ACCESS_SECRET_64','message':'Bearer SUPER_SECRET_64','prompt':'PROMPT_SECRET_64','account':'raw@example.invalid','hostname':'PRIVATE-HOST'}
  for name in ['windows-recovery-observer-latest-v2564.json','real-effect-preflight-latest-v2564.json','target-recovery-evidence-latest-v2564.json']:(state/name).write_text(json.dumps(bad),'utf-8')
  for name in ['WINDOWS_RECOVERY_OBSERVER_BRIDGE_VALIDATION_V25.64.json','REAL_EFFECT_CRASH_CERT_VALIDATION_V25.64.json','TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.64.json']:(runtime/name).write_text(json.dumps(bad),'utf-8')
  result=base/'result.json';rc=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(runtime),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True).returncode;add('bundle_command_pass',rc==0,rc)
  r=json.loads(result.read_text('utf-8'));zp=Path(r['path']);add('bundle_exists',zp.exists(),str(zp))
  with zipfile.ZipFile(zp) as z:
   names=z.namelist();blob='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names);mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json'))['version']
   add('observer_latest_included',any(n.endswith('windows-recovery-observer-latest-v2564.json') for n in names),names)
   add('real_preflight_included',any(n.endswith('real-effect-preflight-latest-v2564.json') for n in names),names)
   add('target_evidence_included',any(n.endswith('target-recovery-evidence-latest-v2564.json') for n in names),names)
   add('runtime_validators_included',all(any(n.endswith(x) for n in names) for x in ['WINDOWS_RECOVERY_OBSERVER_BRIDGE_VALIDATION_V25.64.json','REAL_EFFECT_CRASH_CERT_VALIDATION_V25.64.json','TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.64.json']),names)
   add('manifest_version_current',mv in {'25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},mv)
   add('access_token_redacted','ACCESS_SECRET_64' not in blob);add('bearer_redacted','SUPER_SECRET_64' not in blob);add('prompt_redacted','PROMPT_SECRET_64' not in blob);add('account_redacted','raw@example.invalid' not in blob);add('hostname_redacted','PRIVATE-HOST' not in blob)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_WINDOWS_RECOVERY','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
