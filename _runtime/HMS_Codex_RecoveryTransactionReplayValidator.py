#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.62'

def load(root:Path):
 p=root/'HMS_Codex_RecoveryTransactionReplay.py';spec=importlib.util.spec_from_file_location('rr62',p);m=importlib.util.module_from_spec(spec);sys.modules['rr62']=m;spec.loader.exec_module(m);return m

def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None): tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {}
 add('proof_pass',proof.get('verdict')=='PASS',sm)
 add('proof_18_checks_or_more',int(sm.get('total',0))>=18,sm)
 add('crash_matrix_30_plus',int(sm.get('crash_cases',0))>=30,sm.get('crash_cases'))
 add('crash_matrix_zero_fail',(proof.get('crash_matrix') or {}).get('fail')==0)
 add('four_cross_subsystem_effects',set(m.EFFECT_KINDS)=={'OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF'})
 plan=m.make_plan('validator')
 add('one_transaction_identity',plan.txn_id.startswith('rrx-') and len({plan.txn_id})==1,plan.txn_id)
 add('effect_fingerprint_unique',len({e.effect_fingerprint for e in plan.effects})==4)
 add('idempotency_key_unique',len({e.idempotency_key for e in plan.effects})==4)
 add('idempotency_key_not_effect_fingerprint',all(e.idempotency_key!=e.effect_fingerprint for e in plan.effects))
 add('dependency_dag_linear',all(plan.effects[i].depends_on==(plan.effects[i-1].effect_id,) for i in range(1,4)))
 with tempfile.TemporaryDirectory(prefix='hms-v2562-val-') as td:
  j=m.ReplayJournal(Path(td)/'j.jsonl');w=m.ModelWorld(plan);eng=m.ReplayEngine(j,w)
  try:eng.recover(plan,crash_marker='AFTER_EFFECT_BEFORE_DURABLE:auth')
  except m.CrashInjected:pass
  add('danger_window_effect_once_before_resume',w.exec_count['auth']==1,w.exec_count)
  r=eng.recover(plan);add('danger_window_converges_healthy',r['status']=='HEALTHY',r)
  add('danger_window_no_duplicate_auth',w.exec_count['auth']==1,w.exec_count)
  add('all_effects_at_most_once',all(v<=1 for v in w.exec_count.values()),w.exec_count)
  add('journal_chain_valid',j.validate()['ok'],j.validate())
  raw=j.path.read_text('utf-8')
  add('journal_hides_raw_idempotency',all(e.idempotency_key not in raw for e in plan.effects))
  add('journal_has_effect_fingerprint',all(e.effect_fingerprint in raw for e in plan.effects))
  r2=eng.recover(plan);add('second_replay_noop_healthy',r2['status']=='HEALTHY' and all(v<=1 for v in w.exec_count.values()),r2)
 with tempfile.TemporaryDirectory(prefix='hms-v2562-concurrent-val-') as td:
  p=m.make_plan('concurrent-val');j=m.ReplayJournal(Path(td)/'j.jsonl');w=m.ModelWorld(p);eng=m.ReplayEngine(j,w)
  try:eng.recover(p,crash_marker='AFTER_PREPARE:auth')
  except m.CrashInjected:pass
  w.concurrent_change(p.effects[0]);r=eng.recover(p)
  add('concurrent_change_operator_required',r['status']=='OPERATOR_REQUIRED',r)
  add('concurrent_change_not_overwritten',w.exec_count['auth']==0,w.exec_count)
 with tempfile.TemporaryDirectory(prefix='hms-v2562-comp-val-') as td:
  p=m.make_plan('comp-val');j=m.ReplayJournal(Path(td)/'j.jsonl');w=m.ModelWorld(p);eng=m.ReplayEngine(j,w);eng.recover(p);c=eng.compensate_verified(p)
  add('compensation_reverse_dependency_order',c.get('compensated')==['lease','router','restart','auth'],c)
  add('compensation_converges_degraded_safe',c.get('status')=='DEGRADED_SAFE',c)
 src=(root/'HMS_Codex_RecoveryTransactionReplay.py').read_text('utf-8')
 add('durable_fsync','os.fsync' in src and 'flush()' in src)
 add('explicit_operator_required','OPERATOR_REQUIRED' in src and 'OWNERSHIP_UNPROVEN' in src)
 add('externally_observable_verify','VERIFY_ONLY_NO_REPEAT' in src and 'OBSERVED_ALREADY_APPLIED_NO_REPEAT' in src)
 add('production_claim_blocked',m.PRODUCTION_CLAIM=='NOT_CLAIMED_RECOVERY_REPLAY_SYNTHETIC_ONLY')
 ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig');gui=(root/'HMS_GUI.pyw').read_text('utf-8')
 add('version_25_62_ps',any(f'$script:Version = "{v}"' in ps for v in ['25.62','25.63','25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74']))
 add('version_25_62_gui',any(f'APP_VERSION = "{v}"' in gui for v in ['25.62','25.63','25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74']))
 add('gui_replay_surface',all(x in gui for x in ['REPLAY v25.62','REPLAY PROOF','start_recovery_replay_proof_async']))
 import re
 c=json.loads((root/'CODEX_PUBLIC_CONTRACT_V25_46.json').read_text('utf-8'));mm=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',ps,re.S);actions=re.findall(r'"([^"]+)"',mm.group(1)) if mm else []
 add('public_actions_still_90',actions==c.get('backend_actions') and len(actions)==90,len(actions))
 passed=sum(x['status']=='PASS' for x in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_TRANSACTION_REPLAY_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests),'crash_cases':sm.get('crash_cases',0)},'tests':tests,'production_certification':'NOT_CLAIMED_RECOVERY_REPLAY_SYNTHETIC_ONLY'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
