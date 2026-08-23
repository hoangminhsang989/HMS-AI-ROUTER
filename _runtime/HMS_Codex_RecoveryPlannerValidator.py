#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
VERSION="25.57"

def version_tuple(s):
    try:return tuple(int(x) for x in str(s).split('.')[:3])
    except:return (0,)

def main_version(ps):
    import re
    m=re.search(r'\$script:Version\s*=\s*"([0-9.]+)"',ps)
    return m.group(1) if m else "0"

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root)
    tool=root/'HMS_Codex_RecoveryPlanner.py';out_path=root/'RECOVERY_PLANNER_VALIDATION_V25.57.runtime.json'
    p=subprocess.run([sys.executable,str(tool),'--mode','proof','--output',str(out_path)],cwd=str(root),text=True,capture_output=True,timeout=120)
    proof=json.loads(out_path.read_text('utf-8-sig')) if out_path.exists() else {}
    try: out_path.unlink()
    except: pass
    ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig',errors='replace')
    gui=(root/'HMS_GUI.pyw').read_text('utf-8-sig',errors='replace')
    runtime=(root/'HMS_Runtime_KitValidator.py').read_text('utf-8-sig',errors='replace')
    checks=[]
    def add(n,ok,d=None):checks.append({'name':n,'ok':bool(ok),'detail':d})
    add('proof_process_exit',p.returncode==0,p.stderr[-300:] if p.returncode else None)
    add('proof_verdict_pass',proof.get('verdict')=='PASS')
    s=proof.get('summary') or {};add('proof_assertions_at_least_17',int(s.get('pass') or 0)>=17 and s.get('fail')==0,s)
    add('model_checker_at_least_6000_states',int(s.get('model_states') or 0)>=6000,s.get('model_states'))
    names={x.get('name') for x in proof.get('checks') or [] if x.get('ok')}
    required={'quota_never_restart','existing_session_not_rotated_on_429','owned_router_crash_bounded_restart','unowned_router_never_restarted','config_has_atomic_repair_and_rollback','config_without_backup_refused','auth_drift_fail_closed','client_abort_no_recovery','lan_unexpired_lease_no_takeover','recovery_loop_breaker','model_checker_no_safety_violation','counterexample_minimized_to_one_429','same_input_same_plan_id','production_never_claimed'}
    add('critical_decision_contract',required.issubset(names),sorted(required-names))
    mc=proof.get('model_check') or {};add('zero_model_safety_violations',mc.get('violation_count')==0,mc.get('violation_count'))
    mini=proof.get('minimized_counterexample') or {};add('minimal_bad_policy_trace',mini.get('minimized_length')==1 and (mini.get('events') or [{}])[0].get('incident')=='HTTP_429',mini)
    add('production_never_claimed',(proof.get('safety') or {}).get('production_certification')=='NOT_CLAIMED_RECOVERY_DECISION_PROOF_SYNTHETIC_ONLY')
    add('runtime_contract_present',all(x in runtime for x in ['v25_57.recovery_planner','v25_57.loop_breaker','v25_57.rollback_proof','v25_57.model_checker']))
    add('native_gui_surface',all(x in gui for x in ['RECOVERY PLANNER / SELF-HEALING PROOF v25.57','PROOF','MODEL CHECK','start_recovery_planner_async']))
    add('powershell_surface',all(x in ps for x in ['RECOVERY PLANNER / SELF-HEALING PROOF v25.57','Show-HmsRecoveryPlannerCenter','Invoke-HmsRecoveryPlannerProof']))
    add('main_version_at_least_25_57',version_tuple(main_version(ps))>=version_tuple('25.57'),main_version(ps))
    passed=sum(1 for x in checks if x['ok'])
    result={'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_PLANNER_SELF_HEALING_DECISION_PROOF_VALIDATOR','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(checks) else 'FAIL','summary':{'pass':passed,'fail':len(checks)-passed,'total':len(checks)},'checks':checks,'production_certification':'NOT_CLAIMED_RECOVERY_DECISION_PROOF_SYNTHETIC_ONLY'}
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if result['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
