#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.73'
def run(root:Path):
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2573-privacy-') as td:
  b=Path(td);data=b/'data';state=data/'startup-recovery-v2565'/'v2573';state.mkdir(parents=True);out=b/'out';out.mkdir()
  bad={'version':VERSION,'verdict':'PASS','access_token':'ACCESS73','message':'Bearer SUPERSECRET73','reviewer_email':'reviewer73@example.invalid','account':'raw73@example.invalid','hostname':'HOST73','private_material':'PRIVATE73','prompt':'PROMPT73','response':'RESPONSE73','command_line':'CMD73','environment':'ENV73','summary':{'pass':10,'total':10}}
  for n in ('windows-target-import-review-latest-v2573.json','baseline-delta-watch-latest-v2573.json'):(state/n).write_text(json.dumps(bad),'utf-8')
  result=b/'r.json';p=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(root),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True,timeout=60);r=json.loads(result.read_text('utf-8')) if result.exists() else {};add('bundle_created',p.returncode==0 and r.get('ok'),r);zp=Path(r.get('path') or '')
  if zp.exists():
   with zipfile.ZipFile(zp) as z:
    names=z.namelist();alltext='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names);mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json')).get('version')
   add('manifest_version',mv in {VERSION,'25.74'},mv);add('v2573_artifacts_included',all(any(n.endswith(x) for n in names) for x in ('windows-target-import-review-latest-v2573.json','baseline-delta-watch-latest-v2573.json')),names)
   for lab,sec in [('access','ACCESS73'),('bearer','SUPERSECRET73'),('reviewer','reviewer73@example.invalid'),('account','raw73@example.invalid'),('hostname','HOST73'),('private','PRIVATE73'),('prompt','PROMPT73'),('response','RESPONSE73'),('command','CMD73'),('environment','ENV73')]:add(lab+'_redacted',sec not in alltext)
  else:
   for n in ('manifest_version','v2573_artifacts_included','access_redacted','bearer_redacted','reviewer_redacted','account_redacted','hostname_redacted','private_redacted','prompt_redacted','response_redacted','command_redacted','environment_redacted'):add(n,False,'bundle missing')
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.73','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
