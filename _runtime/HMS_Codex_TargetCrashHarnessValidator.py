#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.63'

def load(root:Path):
    p=root/'HMS_Codex_TargetCrashHarness.py';spec=importlib.util.spec_from_file_location('ch63',p);m=importlib.util.module_from_spec(spec);sys.modules['ch63']=m;spec.loader.exec_module(m);return m

def run(root:Path):
    m=load(root);tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    proof=m.proof();sm=proof.get('summary') or {};cases=proof.get('cases') or []
    add('proof_pass',proof.get('verdict')=='PASS',sm)
    add('exact_12_crash_cases',int(sm.get('crash_cases',0))==12,sm)
    add('four_effects',set(m.EFFECTS)=={'auth','restart','router','lease'})
    add('three_crash_windows',set(m.WINDOWS)=={'AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY'})
    add('every_process_killed',all(c.get('killed') for c in cases))
    add('cold_start_distinct_pid',all(c.get('cold_start_distinct_pid') for c in cases))
    add('all_effects_exactly_once',all(c.get('exec_count')==1 and c.get('at_most_once') for c in cases))
    add('all_journals_valid',all(c.get('journal_valid') for c in cases))
    add('all_converge_healthy',all(c.get('healthy') for c in cases))
    add('all_recovery_rc_zero',all(c.get('recovery_rc')==0 for c in cases))
    add('all_cases_safe',all(c.get('safe') for c in cases))
    host=proof.get('host') or {}
    add('host_evidence_explicit','windows_target_evidence' in host,host)
    if sys.platform.startswith('win'):
        add('windows_host_marks_target_evidence',host.get('windows_target_evidence') is True,host)
    else:
        add('nonwindows_does_not_fake_windows',host.get('windows_target_evidence') is False,host)
    safety=proof.get('safety') or {}
    add('real_codex_not_executed',safety.get('real_codex_effects_executed') is False,safety)
    add('production_claim_blocked',str(safety.get('production_certification') or '').startswith('NOT_CLAIMED'))
    src=(root/'HMS_Codex_TargetCrashHarness.py').read_text('utf-8')
    add('actual_subprocess_kill','subprocess.Popen' in src and '.kill()' in src)
    add('durable_fsync','os.fsync' in src and 'os.replace' in src)
    add('danger_window_observe_no_repeat','OBSERVED_ALREADY_APPLIED_NO_REPEAT' in src)
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_CRASH_HARNESS_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests),'crash_cases':sm.get('crash_cases',0)},'host':host,'tests':tests,'production_certification':m.PRODUCTION_CLAIM}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
