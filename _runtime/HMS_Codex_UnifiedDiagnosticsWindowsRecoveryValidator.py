#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.64'
def load(root:Path):
 p=root/'HMS_Codex_UnifiedDiagnostics.py';spec=importlib.util.spec_from_file_location('ud64',p);m=importlib.util.module_from_spec(spec);sys.modules['ud64']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 with tempfile.TemporaryDirectory(prefix='hms-v2564-unified-') as td:
  data=Path(td);state=data/'startup-recovery-v2564';state.mkdir(parents=True)
  observer={'version':'25.64','verdict':'PASS','summary':{'available':4,'total':4},'evidence':{'class':'WINDOWS_TARGET_OBSERVER','production_score_eligible':False},'observations':[{'account':'secret@example.invalid','access_token':'SECRET_TOKEN'}],'generated_utc':'2026-08-22T14:00:00+00:00'}
  real={'version':'25.64','verdict':'DEFERRED_NOT_ARMED','arming':{'gates':{'windows_host':True,'arm_token':False,'operator_phrase':False,'environment_gate':False,'adapter_manifest':True}},'evidence_class':'REAL_CODEX_EFFECT','real_codex_effects_executed':False,'production_score_eligible':False,'cases':[{'secret':'SECRET_CASE'}],'generated_utc':'2026-08-22T14:01:00+00:00'}
  bundle={'version':'25.64','evidence_classes':['WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'],'production_score_eligible':False,'bundle_sha256':'a'*64,'host_fingerprint':'ref-secret-host','raw_account':'secret@example.invalid','generated_utc':'2026-08-22T14:02:00+00:00'}
  (state/'windows-recovery-observer-latest-v2564.json').write_text(json.dumps(observer),'utf-8')
  (state/'real-effect-preflight-latest-v2564.json').write_text(json.dumps(real),'utf-8')
  (state/'target-recovery-evidence-latest-v2564.json').write_text(json.dumps(bundle),'utf-8')
  report=m.build_report(data,200);raw=json.dumps(report,ensure_ascii=False)
  add('report_version_current',report.get('version') in {'25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74'},report.get('version'))
  layers=report.get('layers') or {};add('observer_layer_ok',layers.get('windows_recovery_observer')=='OK',layers.get('windows_recovery_observer'));add('real_effect_layer_warning',layers.get('real_effect_crash_cert')=='WARNING',layers.get('real_effect_crash_cert'));add('evidence_layer_ok',layers.get('target_recovery_evidence')=='OK',layers.get('target_recovery_evidence'))
  add('observer_identity_not_projected','secret@example.invalid' not in raw and 'SECRET_TOKEN' not in raw)
  add('real_case_not_projected','SECRET_CASE' not in raw)
  add('host_fingerprint_not_projected','ref-secret-host' not in raw)
  sources=report.get('by_source') or {};add('three_sources_present',all(x in sources for x in ['windows-recovery-observer','real-effect-crash-cert','target-recovery-evidence']),sources)
  timeline=report.get('timeline') or [];selected=[e for e in timeline if e.get('source') in {'windows-recovery-observer','real-effect-crash-cert','target-recovery-evidence'}]
  add('three_aggregate_events',len(selected)==3,len(selected));add('identity_fields_blank',all(not e.get('account') and not e.get('project') and not e.get('instance_id') for e in selected))
  add('report_privacy',report.get('privacy',{}).get('metadata_only') is True and report.get('privacy',{}).get('contains_raw_secret') is False)
  add('production_not_promoted',all(not bool((e.get('details') or {}).get('production_score_eligible')) for e in selected))
 passed=sum(t['status']=='PASS' for t in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'UNIFIED_DIAGNOSTICS_WINDOWS_RECOVERY_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
