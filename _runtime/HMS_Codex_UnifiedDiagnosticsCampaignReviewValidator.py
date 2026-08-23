#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.68'
def run(root:Path):
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2568-unified-') as td:
  base=Path(td);data=base/'data';state=data/'startup-recovery-v2565'/'v2568';state.mkdir(parents=True)
  ex=json.loads(subprocess.check_output([sys.executable,str(root/'HMS_Codex_TargetCampaignExecutorValidator.py'),'--root',str(root)],text=True));rv=json.loads(subprocess.check_output([sys.executable,str(root/'HMS_Codex_AttestedPromotionReviewConsoleValidator.py'),'--root',str(root)],text=True))
  # Add hostile fields to prove the diagnostics projection ignores them.
  ex.update({'access_token':'EXEC_SECRET','account':'raw@example.invalid','message':'Bearer EXEC_SECRET_BEARER','private_material':'NOPE'});rv.update({'refresh_token':'REVIEW_SECRET','hostname':'PRIVATE-HOST','certificate_private_material':'CERT_SECRET'})
  (state/'target-campaign-executor-latest-v2568.json').write_text(json.dumps(ex),encoding='utf-8');(state/'attested-promotion-review-latest-v2568.json').write_text(json.dumps(rv),encoding='utf-8')
  latest=base/'unified.json';proc=subprocess.run([sys.executable,str(root/'HMS_Codex_UnifiedDiagnostics.py'),'--data-dir',str(data),'--latest',str(latest),'--mode','refresh'],capture_output=True,text=True,timeout=60)
  report=(json.loads(proc.stdout).get('unified_diagnostics') if proc.returncode==0 else {}) or {};raw=json.dumps(report,ensure_ascii=False)
  add('unified_exit',proc.returncode==0,proc.stderr[-300:]);add('report_version',report.get('version') in {VERSION,'25.69','25.70','25.71','25.72','25.73','25.74'},report.get('version'))
  layers=report.get('layers') or {};add('executor_layer',layers.get('target_campaign_executor')=='OK',layers.get('target_campaign_executor'));add('review_layer',layers.get('attested_promotion_review')=='OK',layers.get('attested_promotion_review'))
  by=report.get('by_source') or {};add('aggregate_sources',by.get('target-campaign-executor')==1 and by.get('attested-promotion-review')==1,by)
  add('no_identity_or_secret',all(x not in raw for x in ('EXEC_SECRET','REVIEW_SECRET','raw@example.invalid','PRIVATE-HOST','CERT_SECRET','EXEC_SECRET_BEARER')))
  add('metadata_only',((report.get('privacy') or {}).get('metadata_only') is True) and ((report.get('privacy') or {}).get('contains_raw_secret') is False))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_CAMPAIGN_REVIEW_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
