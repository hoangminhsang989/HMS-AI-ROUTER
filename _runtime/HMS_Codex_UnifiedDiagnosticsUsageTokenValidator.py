#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, tempfile, sys
from pathlib import Path
from datetime import datetime, timezone

VERSION='25.61'

def load(root:Path):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';spec=importlib.util.spec_from_file_location('ud2561',p);m=importlib.util.module_from_spec(spec);sys.modules['ud2561']=m;spec.loader.exec_module(m);return m

def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'ok':bool(ok),'detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2561-ud-') as td:
  data=Path(td);p=data/'usage-token-v2561';p.mkdir(parents=True)
  payload={'version':'25.61','generated_utc':'2026-08-22T09:00:00+00:00','summary':{'cards':2},'cards':[
   {'account_ref':'acct-safehash1','email':'raw@example.invalid','freshness_state':'FRESH','windows':[{'reset_utc':'2026-08-22T10:00:00+00:00'}],'lifecycle':{'package':{'expiry_utc':'2026-09-01T00:00:00+00:00'}},'access_token':'SECRET_ACCESS_TOKEN','prompt':'SECRET_PROMPT'},
   {'account_ref':'acct-safehash2','freshness_state':'STALE','windows':[{'reset_utc':None}],'lifecycle':{'package':{'expiry_utc':None}},'authorization':'Bearer VERY_SECRET'}],
   'safety':{'production_certification':'NOT_CLAIMED_USAGE_TOKEN_CENTER_SYNTHETIC_ONLY'}}
  (p/'usage-token-latest-v2561.json').write_text(json.dumps(payload),'utf-8')
  ev=m.usage_token_events(data)
  add('collector_one_aggregate_event',len(ev)==1,len(ev))
  e=ev[0] if ev else {}
  add('collector_source',e.get('source')=='usage-token-center',e.get('source'))
  add('collector_kind',e.get('kind')=='USAGE_TOKEN_METADATA',e.get('kind'))
  add('account_identity_not_projected',not e.get('account') and 'raw@example.invalid' not in json.dumps(e))
  raw=json.dumps(e,ensure_ascii=False)
  add('access_token_not_projected','SECRET_ACCESS_TOKEN' not in raw)
  add('bearer_not_projected','VERY_SECRET' not in raw)
  add('prompt_not_projected','SECRET_PROMPT' not in raw)
  add('aggregate_counts_present','accounts=2' in e.get('message','') and 'resets=1' in e.get('message','') and 'package=1' in e.get('message','') and 'stale=1' in e.get('message',''),e.get('message'))
  report=m.build_report(data)
  add('report_version_25_61_or_newer',tuple(map(int,str(report.get('version') or '0.0').split('.')[:2])) >= (25,61),report.get('version'))
  add('usage_layer_ok',(report.get('layers') or {}).get('usage_token_center')=='OK',(report.get('layers') or {}).get('usage_token_center'))
  add('report_privacy_metadata_only',(report.get('privacy') or {}).get('metadata_only') is True and (report.get('privacy') or {}).get('contains_raw_secret') is False,report.get('privacy'))
  add('report_has_no_injected_secrets',all(x not in json.dumps(report,ensure_ascii=False) for x in ('SECRET_ACCESS_TOKEN','VERY_SECRET','SECRET_PROMPT','raw@example.invalid')))
 passed=sum(x['ok'] for x in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_USAGE_TOKEN_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
