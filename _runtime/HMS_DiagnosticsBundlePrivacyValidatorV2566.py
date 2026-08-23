#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.67'
def run(root):
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2566-privacy-') as td:
  base=Path(td);data=base/'data';out=base/'out';state=data/'startup-recovery-v2565'/'v2566';state.mkdir(parents=True);out.mkdir()
  bad={'version':VERSION,'verdict':'PASS','access_token':'ACCESS_SECRET_66','message':'Bearer SUPER_SECRET_66','account':'raw@example.invalid','hostname':'PRIVATE-HOST','command_line':'codex --token SECRET','environment':'SECRET_ENV','private_key':'PRIVATE_SECRET'}
  for n in ('windows-attestation-signer-latest-v2566.json','target-cert-runbook-latest-v2566.json','attestation-exchange-latest-v2566.json'):(state/n).write_text(json.dumps(bad),encoding='utf-8')
  result=base/'result.json';p=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(root),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True,timeout=60)
  r=json.loads(result.read_text('utf-8')) if result.exists() else {};add('bundle_created',p.returncode==0 and r.get('ok'),r)
  zp=Path(r.get('path') or '')
  if zp.exists():
   with zipfile.ZipFile(zp) as z:
    names=z.namelist();alltext='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names)
    manifest=json.loads(z.read('DIAGNOSTICS_MANIFEST.json'));mv=manifest.get('version')
   add('manifest_version',mv in {VERSION,'25.68','25.69','25.70','25.71','25.72','25.73','25.74'},mv);add('v2566_artifacts_included',all(any(n.endswith(x) for n in names) for x in ('windows-attestation-signer-latest-v2566.json','target-cert-runbook-latest-v2566.json','attestation-exchange-latest-v2566.json')),names)
   for label,secret in [('access','ACCESS_SECRET_66'),('bearer','SUPER_SECRET_66'),('account','raw@example.invalid'),('hostname','PRIVATE-HOST'),('private','PRIVATE_SECRET')]:add(label+'_redacted',secret not in alltext)
  else:
   for n in ('manifest_version','v2566_artifacts_included','access_redacted','bearer_redacted','account_redacted','hostname_redacted','private_redacted'):add(n,False,'bundle missing')
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.66','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
