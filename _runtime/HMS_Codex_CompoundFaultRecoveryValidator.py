#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "25.58"

def version_tuple(s):
    try: return tuple(int(x) for x in str(s).split('.')[:3])
    except Exception: return (0,)

def main_version(ps):
    m=re.search(r'\$script:Version\s*=\s*"([0-9.]+)"',ps)
    return m.group(1) if m else "0"

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root)
    tool=root/'HMS_Codex_CompoundFaultRecovery.py'
    out_path=root/'COMPOUND_FAULT_RECOVERY_VALIDATION_V25.58.runtime.json'
    proc=subprocess.run([sys.executable,str(tool),'--mode','proof','--output',str(out_path)],cwd=str(root),text=True,capture_output=True,timeout=120)
    try: proof=json.loads(out_path.read_text('utf-8-sig'))
    except Exception:
        try: proof=json.loads(proc.stdout)
        except Exception: proof={}
    checks=[]
    def add(name,ok,detail=None):checks.append({'name':name,'ok':bool(ok),'detail':detail})
    add('proof_process_exit_zero',proc.returncode==0,(proc.stderr or '')[-300:])
    add('proof_verdict_pass',proof.get('verdict')=='PASS')
    sm=proof.get('summary') or {}
    add('proof_assertions_at_least_23',int(sm.get('pass') or 0)>=23 and sm.get('fail')==0,sm)
    add('model_checker_at_least_70000_states',int(sm.get('model_states') or 0)>=70000,sm.get('model_states'))
    mc=proof.get('model_check') or {}
    add('zero_model_safety_violations',mc.get('violation_count')==0,mc.get('violation_count'))
    add('terminal_states_all_covered',all(int((mc.get('terminal_distribution') or {}).get(x,0))>0 for x in ['HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED']),mc.get('terminal_distribution'))
    names={x.get('name') for x in proof.get('checks') or [] if x.get('ok')}
    required={'quota_plus_crash_restart_only_for_crash','quota_plus_crash_existing_session_no_fallback','quota_plus_crash_converges_degraded_safe','smb_partition_expired_converges_healthy','config_plus_client_crash_converges_healthy','hard_auth_dominates_auto_mutation','global_budget_blocks_recovery_storm','unexpired_partition_no_takeover','all_scenario_dags_acyclic','all_scenarios_bounded_rounds','production_never_claimed'}
    add('critical_compound_contract',required.issubset(names),sorted(required-names))
    plans=proof.get('scenario_plans') or {}; sims=proof.get('scenario_convergence') or {}
    add('recovery_dag_contract',all((p.get('dag') or {}).get('acyclic') and len((p.get('dag') or {}).get('nodes') or [])==len(set((p.get('dag') or {}).get('nodes') or [])) for p in plans.values()))
    add('global_budget_contract',all(int((p.get('global_budget') or {}).get('spent',0))<=int((p.get('global_budget') or {}).get('limit',0)) for p in plans.values()))
    add('convergence_contract',all((s or {}).get('terminal_state') in {'HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED'} and int((s or {}).get('round_count',99))<=4 for s in sims.values()))
    safety=proof.get('safety') or {}
    add('production_never_claimed',safety.get('production_certification')=='NOT_CLAIMED_COMPOUND_FAULT_CONVERGENCE_SYNTHETIC_ONLY' and safety.get('real_codex_called') is False)
    runtime=(root/'HMS_Runtime_KitValidator.py').read_text('utf-8',errors='replace')
    gui=(root/'HMS_GUI.pyw').read_text('utf-8',errors='replace')
    ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig',errors='replace')
    add('runtime_contract_present',all(x in runtime for x in ['v25_58.compound_fault_dag','v25_58.global_recovery_budget','v25_58.convergence_model','v25_58.operator_dominance']))
    add('native_gui_surface',all(x in gui for x in ['COMPOUND-FAULT CONVERGENCE v25.58','CONVERGENCE','MODEL 72K','start_compound_fault_recovery_async']))
    add('powershell_surface',all(x in ps for x in ['COMPOUND-FAULT CONVERGENCE v25.58','Show-HmsCompoundFaultRecoveryCenter','Invoke-HmsCompoundFaultRecovery']))
    add('main_version_at_least_25_58',version_tuple(main_version(ps))>=version_tuple('25.58'),main_version(ps))
    passed=sum(1 for x in checks if x['ok'])
    result={'product':'HMS-AI-ROUTER','version':VERSION,'suite':'COMPOUND_FAULT_RECOVERY_CONVERGENCE_VALIDATOR','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(checks) else 'FAIL','summary':{'pass':passed,'fail':len(checks)-passed,'total':len(checks),'model_states':sm.get('model_states')},'checks':checks,'production_certification':'NOT_CLAIMED_COMPOUND_FAULT_CONVERGENCE_SYNTHETIC_ONLY'}
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if result['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
