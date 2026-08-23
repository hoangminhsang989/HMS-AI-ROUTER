#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, tempfile, sys, subprocess, zipfile
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.61'

def load(root):
 p=root/'HMS_DiagnosticsBundle.py';spec=importlib.util.spec_from_file_location('db2561',p);m=importlib.util.module_from_spec(spec);sys.modules['db2561']=m;spec.loader.exec_module(m);return m

def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'ok':bool(ok),'detail':d})
 add('allow_usage_latest',m.allowed(Path('usage-token-v2561')/'usage-token-latest-v2561.json'))
 add('allow_usage_history',m.allowed(Path('usage-token-v2561')/'usage-token-history-v2561.jsonl'))
 add('deny_auth_path',not m.allowed(Path('auth')/'usage-token-latest-v2561.json'))
 with tempfile.TemporaryDirectory(prefix='hms-v2561-bundle-') as td:
  base=Path(td);data=base/'data';runtime=base/'runtime';out=base/'out';u=data/'usage-token-v2561';u.mkdir(parents=True);runtime.mkdir()
  secret_values=['ACCESS_SECRET_ABC','REFRESH_SECRET_DEF','API_SECRET_GHI','PROMPT_SECRET_JKL','REQUEST_SECRET_MNO','RESPONSE_SECRET_PQR','Bearer SUPER_SECRET_TOKEN']
  obj={'version':'25.61','generated_utc':'2026-08-22T09:00:00+00:00','access_token':secret_values[0],'refresh_token':secret_values[1],'api_key':secret_values[2],'prompt':secret_values[3],'request_body':secret_values[4],'response_body':secret_values[5],'message':secret_values[6],'cards':2}
  (u/'usage-token-latest-v2561.json').write_text(json.dumps(obj),'utf-8')
  (u/'usage-token-history-v2561.jsonl').write_text(json.dumps(obj)+'\n','utf-8')
  (runtime/'BUILD_VALIDATION_V25.61.txt').write_text('PASS\n','utf-8')
  result=base/'result.json'
  rc=subprocess.run([sys.executable,str(root/'HMS_DiagnosticsBundle.py'),'--data-dir',str(data),'--runtime-dir',str(runtime),'--output-dir',str(out),'--output',str(result)],capture_output=True,text=True).returncode
  add('bundle_command_pass',rc==0,rc)
  r=json.loads(result.read_text('utf-8'));zp=Path(r['path']);add('bundle_exists',zp.exists(),str(zp))
  with zipfile.ZipFile(zp) as z:
   names=z.namelist();blob='\n'.join(z.read(n).decode('utf-8',errors='replace') for n in names)
   add('latest_included',any(n.endswith('usage-token-latest-v2561.json') for n in names),names)
   add('history_included',any(n.endswith('usage-token-history-v2561.jsonl') for n in names),names)
   mv=json.loads(z.read('DIAGNOSTICS_MANIFEST.json'))['version'];add('manifest_version_25_61_or_newer',tuple(map(int,str(mv).split('.')[:2])) >= (25,61),mv)
   for label,val in [('access_token_redacted',secret_values[0]),('refresh_token_redacted',secret_values[1]),('api_key_redacted',secret_values[2]),('prompt_redacted',secret_values[3]),('request_response_redacted',secret_values[4]),('bearer_redacted','SUPER_SECRET_TOKEN')]:
    add(label,val not in blob)
 passed=sum(x['ok'] for x in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'DIAGNOSTICS_BUNDLE_PRIVACY_USAGE_TOKEN','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
