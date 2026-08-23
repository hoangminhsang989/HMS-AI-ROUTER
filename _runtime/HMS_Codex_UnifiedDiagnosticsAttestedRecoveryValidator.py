#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.65'
def load(root:Path):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';s=importlib.util.spec_from_file_location('ud65',p);m=importlib.util.module_from_spec(s);sys.modules['ud65']=m;s.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2565-ud-') as td:
  data=Path(td);state=data/'startup-recovery-v2565';state.mkdir(parents=True)
  adapter={'version':'25.65','verdict':'DEFERRED_TARGET_OBSERVATION','summary':{'available':3,'total':4},'evidence_class':'WINDOWS_TARGET_OBSERVER','production_score_eligible':False,'adapters':[{'account':'secret@example.invalid','token':'SECRET'}],'generated_utc':'2026-08-22T20:00:00+00:00'}
  promotion={'version':'25.65','verdict':'NO_PROMOTION','summary':{'pass':10,'total':10},'production_score_promotion_eligible':False,'reasons':['REAL_TRUSTED_TARGET_SIGNER_REQUIRED'],'nonce':'SECRET_NONCE','generated_utc':'2026-08-22T20:01:00+00:00'}
  timeline={'version':'25.65','verdict':'PASS','timeline':[{'seq':1,'phase':'OBSERVE','nhan':'QUAN SÁT TRẠNG THÁI','status':'PASS','source':'adapter','freshness':'FRESH','safe_fingerprint_prefix':'abcdef123456','remediation_reason':'OK','time_utc':'2026-08-22T20:02:00+00:00','account':'secret@example.invalid'},{'seq':2,'phase':'OPERATOR_REQUIRED','nhan':'CẦN NGƯỜI VẬN HÀNH','status':'BLOCKED','source':'promotion','freshness':'FRESH','safe_fingerprint_prefix':'123456abcdef','remediation_reason':'TRUSTED_TARGET_SIGNER_REQUIRED','time_utc':'2026-08-22T20:03:00+00:00'}],'generated_utc':'2026-08-22T20:03:00+00:00'}
  (state/'windows-target-adapter-latest-v2565.json').write_text(json.dumps(adapter),'utf-8');(state/'attested-evidence-promotion-latest-v2565.json').write_text(json.dumps(promotion),'utf-8');(state/'recovery-operator-timeline-latest-v2565.json').write_text(json.dumps(timeline),'utf-8')
  r=m.build_report(data,300);raw=json.dumps(r,ensure_ascii=False)
  add('report_version',r.get('version') in {'25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},r.get('version'))
  src=r.get('by_source') or {};add('three_sources',all(x in src for x in ['windows-target-adapter','attested-evidence-promotion','recovery-operator-timeline']),src)
  layers=r.get('layers') or {};add('adapter_layer',layers.get('windows_target_adapter')=='WARNING',layers.get('windows_target_adapter'));add('promotion_layer',layers.get('attested_evidence_promotion')=='OK',layers.get('attested_evidence_promotion'));add('timeline_layer',layers.get('recovery_operator_timeline')=='WARNING',layers.get('recovery_operator_timeline'))
  add('identity_not_projected','secret@example.invalid' not in raw and 'SECRET' not in raw)
  selected=[e for e in r.get('timeline',[]) if e.get('source') in {'windows-target-adapter','attested-evidence-promotion','recovery-operator-timeline'}]
  add('metadata_identity_blank',all(not e.get('account') and not e.get('project') and not e.get('instance_id') for e in selected))
  add('vi_timeline_exported',any('CẦN NGƯỜI VẬN HÀNH' in str(e.get('message') or '') for e in selected))
  add('safe_prefix_only',all(len(str((e.get('details') or {}).get('safe_fingerprint_prefix') or ''))<=12 for e in selected if e.get('source')=='recovery-operator-timeline'))
  add('no_auto_promotion',all(not bool((e.get('details') or {}).get('production_score_promotion_eligible')) for e in selected))
  add('privacy_contract',r.get('privacy',{}).get('metadata_only') is True and r.get('privacy',{}).get('contains_raw_secret') is False)
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_ATTESTED_RECOVERY_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
