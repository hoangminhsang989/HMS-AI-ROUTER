#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile,zipfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.69'
def run(root:Path):
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2569-privacy-') as td:
  b=Path(td);data=b/'data';state=data/'startup-recovery-v2565'/'v2569';state.mkdir(parents=True);out=b/'out';out.mkdir()
  bad={'version':VERSION,'verdict':'PASS','access_token':'ACCESS69','message':'Bearer SUPERSECRET69','reviewer_identity':'Reviewer Real Name','reviewer_email':'review69@example.invalid','hostname':'HOST69','private_material':'PRIVATE69','summary':{'accepted':12,'entries':2}}
  for n in ('target-cert-evidence-ingest-latest-v2569.json','promotion-decision-ledger-latest-v2569.json'):(state/n).write_text(json.dumps(bad),'utf-8')
  result=b/'r.json';p=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(root),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True,timeout=60);r=json.loads(result.read_text('utf-8')) if result.exists() else {};add('bundle_created',p.returncode==0 and r.get('ok'),r);zp=Path(r.get('path') or '')
  if zp.exists():
   with zipfile.ZipFile(zp) as z:
    names=z.namelist();alltext='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names);mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json')).get('version')
   add('manifest_version',mv in {VERSION,'25.70','25.71','25.72','25.73','25.74'},mv);add('v2569_artifacts_included',all(any(n.endswith(x) for n in names) for x in ('target-cert-evidence-ingest-latest-v2569.json','promotion-decision-ledger-latest-v2569.json')),names)
   for lab,sec in [('access','ACCESS69'),('bearer','SUPERSECRET69'),('reviewer','Reviewer Real Name'),('reviewer_email','review69@example.invalid'),('hostname','HOST69'),('private','PRIVATE69')]:add(lab+'_redacted',sec not in alltext)
  else:
   for n in ('manifest_version','v2569_artifacts_included','access_redacted','bearer_redacted','reviewer_redacted','reviewer_email_redacted','hostname_redacted','private_redacted'):add(n,False,'bundle missing')
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.69','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
