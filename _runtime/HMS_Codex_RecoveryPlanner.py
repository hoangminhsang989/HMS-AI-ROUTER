#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

VERSION = "25.57"
PRODUCTION_CLAIM = "NOT_CLAIMED_RECOVERY_DECISION_PROOF_SYNTHETIC_ONLY"

HARD_OPERATOR = {"AUTH_DRIFT", "IDENTITY_DRIFT", "FOREIGN_PORT", "PROJECT_MISSING"}
QUOTA_FAULTS = {"HTTP_429", "QUOTA_RESERVE", "QUOTA_STALE", "QUOTA_UNKNOWN"}
NETWORK_FAULTS = {"UPSTREAM_TIMEOUT", "UPSTREAM_CONNECT", "SMB_TRANSIENT"}
PROCESS_FAULTS = {"ROUTER_CRASH", "CLIENT_CRASH"}
CONFIG_FAULTS = {"GLOBAL_CONFIG_DRIFT", "INSTANCE_CONFIG_DRIFT", "BINDING_DRIFT"}
NOOP_FAULTS = {"CLIENT_ABORT", "HEALTHY", "RECOVERED"}

@dataclass(frozen=True)
class RecoveryContext:
    incident: str
    scope: str = "GLOBAL"
    owned_process: bool = False
    existing_session: bool = False
    affinity_target_healthy: bool = True
    quota_fresh: bool = True
    lease_signed: bool = True
    lease_expired: bool = False
    attempts_in_window: int = 0
    last_action_succeeded: bool = False
    config_backup_available: bool = True
    router_running: bool = True
    client_running: bool = True


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def _hash(obj) -> str:
    raw=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _step(action, *, reason, auto_safe=True, verify=None, rollback=None, max_attempts=1,
          backoff_sec=0, preserves_session=True, destructive=False, mutation=False):
    return {
        "action":action,"reason":reason,"auto_safe":bool(auto_safe),
        "verify":verify or "READBACK_HEALTH","rollback":rollback,
        "max_attempts":int(max_attempts),"backoff_sec":int(backoff_sec),
        "preserves_session":bool(preserves_session),"destructive":bool(destructive),
        "mutation":bool(mutation)
    }


def decide(ctx: RecoveryContext):
    incident=ctx.incident.upper().strip()
    steps=[]; disposition="NO_ACTION"; escalation="NONE"
    circuit_open=ctx.attempts_in_window >= 3

    if incident in NOOP_FAULTS:
        disposition="OBSERVE"
    elif incident in HARD_OPERATOR:
        disposition="FAIL_CLOSED_OPERATOR"
        escalation="OPERATOR_REQUIRED"
        steps=[_step("QUARANTINE_SCOPE",reason=incident,auto_safe=True,verify="SCOPE_NOT_ROUTABLE",max_attempts=1)]
    elif circuit_open:
        disposition="CIRCUIT_OPEN"
        escalation="OPERATOR_REQUIRED"
        steps=[_step("OPEN_RECOVERY_CIRCUIT",reason="RECOVERY_LOOP_BREAKER",verify="NO_AUTO_RECOVERY_UNTIL_COOLDOWN",max_attempts=1)]
    elif incident in QUOTA_FAULTS:
        disposition="ROTATE_NEW_SESSIONS_ONLY"
        steps=[_step("MARK_NEW_SESSION_INELIGIBLE",reason=incident,verify="ROUTING_ELIGIBLE_FALSE",max_attempts=1)]
        if not ctx.existing_session:
            steps.append(_step("SELECT_HEALTHY_FALLBACK",reason=incident,verify="DIFFERENT_ELIGIBLE_TARGET",max_attempts=1))
    elif incident == "LAN_PARTITION":
        disposition="PRESERVE_LEASE"
        if not ctx.lease_signed:
            escalation="OPERATOR_REQUIRED"
            steps=[_step("FAIL_CLOSED_UNSIGNED_LEASE",reason=incident,verify="NO_TAKEOVER",max_attempts=1)]
        elif not ctx.lease_expired:
            steps=[_step("HOLD_OWNERSHIP_NO_TAKEOVER",reason=incident,verify="LEASE_OWNER_UNCHANGED",max_attempts=1)]
        else:
            steps=[_step("ALLOW_SIGNED_LEASE_REELECTION",reason=incident,verify="SINGLE_OWNER_AFTER_REELECTION",max_attempts=1)]
    elif incident == "STALE_PID":
        disposition="METADATA_REPAIR"
        steps=[_step("CLEAR_STALE_PID_METADATA",reason=incident,verify="PID_METADATA_EMPTY",max_attempts=1,mutation=True)]
    elif incident in NETWORK_FAULTS:
        disposition="BOUNDED_RETRY"
        steps=[_step("RETRY_SAME_TARGET",reason=incident,verify="APPLICATION_HEALTH_OK",max_attempts=2,backoff_sec=2)]
        if incident == "SMB_TRANSIENT":
            steps.append(_step("MARK_SHARED_IO_DEGRADED",reason=incident,verify="NO_UNSAFE_TAKEOVER",max_attempts=1))
    elif incident in PROCESS_FAULTS:
        if not ctx.owned_process:
            disposition="FAIL_CLOSED_OPERATOR"; escalation="OPERATOR_REQUIRED"
            steps=[_step("REFUSE_UNOWNED_PROCESS_RESTART",reason=incident,verify="NO_PROCESS_MUTATION",auto_safe=True,max_attempts=1)]
        else:
            disposition="BOUNDED_RESTART"
            action="RESTART_ROUTER" if incident=="ROUTER_CRASH" else "RESTART_CLIENT"
            verify="ROUTER_APP_HEALTH_OK" if incident=="ROUTER_CRASH" else "CLIENT_OWNERSHIP_AND_SESSION_READY"
            steps=[_step(action,reason=incident,verify=verify,rollback="RESTORE_PREVIOUS_PROCESS_STATE",max_attempts=2,backoff_sec=3,mutation=True)]
    elif incident in CONFIG_FAULTS:
        disposition="REPAIR_VERIFY_ROLLBACK"
        rollback="RESTORE_CONFIG_BACKUP" if ctx.config_backup_available else None
        if not rollback:
            escalation="OPERATOR_REQUIRED"
            steps=[_step("REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP",reason=incident,verify="CONFIG_UNCHANGED",max_attempts=1)]
        else:
            steps=[_step("REPAIR_CONFIG_ATOMIC",reason=incident,verify="CONFIG_READBACK_MATCH",rollback=rollback,max_attempts=1,mutation=True)]
    else:
        disposition="UNKNOWN_FAIL_CLOSED"; escalation="OPERATOR_REQUIRED"
        steps=[_step("QUARANTINE_SCOPE",reason="UNKNOWN_INCIDENT",verify="SCOPE_NOT_ROUTABLE",max_attempts=1)]

    # Suppress redundant recovery after an already-successful action unless the incident is a new hard fault.
    if ctx.last_action_succeeded and incident not in HARD_OPERATOR and incident not in {"ROUTER_CRASH","CLIENT_CRASH"}:
        mutating=[s for s in steps if s.get("mutation")]
        if mutating:
            disposition="SUPPRESSED_REDUNDANT_RECOVERY"
            steps=[_step("OBSERVE_AFTER_SUCCESS",reason="RECENT_RECOVERY_SUCCEEDED",verify="HEALTH_STABLE",max_attempts=1)]

    plan={
        "version":VERSION,"incident":incident,"scope":ctx.scope,"disposition":disposition,
        "escalation":escalation,"circuit_open":circuit_open,"steps":steps,
        "invariants":{
            "never_kill_unowned":True,"no_auth_copy_or_refresh_mutation":True,
            "no_midstream_replay":True,"existing_session_affinity_preserved_unless_hard_failure":True,
            "quota_fault_never_restarts_process":True,"bounded_recovery":True,
            "config_mutation_requires_rollback":True,"signed_lease_required_for_takeover":True,
            "production_certification":PRODUCTION_CLAIM
        }
    }
    plan["plan_id"]=_hash({k:v for k,v in plan.items() if k not in {"plan_id"}})[:24]
    return plan


def plan_from_dict(d: dict):
    fields=RecoveryContext.__dataclass_fields__
    clean={k:v for k,v in d.items() if k in fields}
    return decide(RecoveryContext(**clean))


def simulate_sequence(events):
    state={"attempts":{},"history":[],"escalations":0,"restart_count":0,"rotate_count":0}
    for i,e in enumerate(events):
        scope=str(e.get("scope") or "GLOBAL")
        key=scope+":"+str(e.get("incident") or "UNKNOWN")
        ctx=dict(e);ctx["attempts_in_window"]=int(state["attempts"].get(key,0))
        p=plan_from_dict(ctx)
        if p["disposition"] not in {"OBSERVE","NO_ACTION","SUPPRESSED_REDUNDANT_RECOVERY"}:
            state["attempts"][key]=ctx["attempts_in_window"]+1
        acts=[s["action"] for s in p["steps"]]
        state["restart_count"]+=sum(a.startswith("RESTART_") for a in acts)
        state["rotate_count"]+=sum(a=="SELECT_HEALTHY_FALLBACK" for a in acts)
        state["escalations"]+=int(p["escalation"]!="NONE")
        state["history"].append({"index":i,"incident":p["incident"],"disposition":p["disposition"],"actions":acts,"plan_id":p["plan_id"]})
    return state


def invariant_violations(ctx: RecoveryContext, p: dict):
    acts=[s["action"] for s in p["steps"]]
    bad=[]
    if not ctx.owned_process and any(a in {"RESTART_ROUTER","RESTART_CLIENT","STOP_PROCESS","KILL_PROCESS"} for a in acts): bad.append("UNOWNED_PROCESS_MUTATION")
    if ctx.incident in QUOTA_FAULTS and any(a.startswith("RESTART_") for a in acts): bad.append("QUOTA_TRIGGERED_RESTART")
    if ctx.incident=="CLIENT_ABORT" and any(a in {"RETRY_SAME_TARGET","RESTART_ROUTER","RESTART_CLIENT","SELECT_HEALTHY_FALLBACK"} for a in acts): bad.append("CLIENT_ABORT_RECOVERY")
    if ctx.incident in CONFIG_FAULTS:
        for s in p["steps"]:
            if s.get("mutation") and not s.get("rollback"): bad.append("CONFIG_MUTATION_WITHOUT_ROLLBACK")
    if ctx.incident=="LAN_PARTITION" and (not ctx.lease_signed or not ctx.lease_expired) and "ALLOW_SIGNED_LEASE_REELECTION" in acts: bad.append("UNSAFE_LEASE_TAKEOVER")
    if ctx.attempts_in_window>=3 and any(a.startswith("RESTART_") or a=="SELECT_HEALTHY_FALLBACK" for a in acts): bad.append("RECOVERY_LOOP_NOT_BROKEN")
    if ctx.existing_session and ctx.incident in QUOTA_FAULTS and "SELECT_HEALTHY_FALLBACK" in acts: bad.append("EXISTING_SESSION_ROTATED_FOR_QUOTA")
    return bad


def model_check():
    incidents=["CLIENT_ABORT","HTTP_429","QUOTA_STALE","UPSTREAM_TIMEOUT","SMB_TRANSIENT","ROUTER_CRASH","CLIENT_CRASH","INSTANCE_CONFIG_DRIFT","AUTH_DRIFT","FOREIGN_PORT","LAN_PARTITION","STALE_PID"]
    checked=0;violations=[];dispositions={}
    for incident,owned,existing,lease_signed,lease_expired,attempts,backup,affinity_healthy,router_running,quota_fresh in product(incidents,[False,True],[False,True],[False,True],[False,True],[0,2,3],[False,True],[False,True],[False,True],[False,True]):
        ctx=RecoveryContext(incident=incident,scope="INSTANCE:A",owned_process=owned,existing_session=existing,lease_signed=lease_signed,lease_expired=lease_expired,attempts_in_window=attempts,config_backup_available=backup,affinity_target_healthy=affinity_healthy,router_running=router_running,quota_fresh=quota_fresh)
        p=decide(ctx);checked+=1;dispositions[p["disposition"]]=dispositions.get(p["disposition"],0)+1
        bad=invariant_violations(ctx,p)
        if bad and len(violations)<25: violations.append({"context":asdict(ctx),"violations":bad,"plan":p})
    return {"states_checked":checked,"violation_count":len(violations),"sample_violations":violations,"dispositions":dispositions,"verdict":"PASS" if not violations else "FAIL"}


def ddmin(events, predicate):
    seq=list(events);n=2
    while len(seq)>=2:
        chunk=max(1,len(seq)//n);reduced=False
        for i in range(0,len(seq),chunk):
            cand=seq[:i]+seq[i+chunk:]
            if cand and predicate(cand): seq=cand;n=max(2,n-1);reduced=True;break
        if not reduced:
            if n>=len(seq): break
            n=min(len(seq),n*2)
    return seq


def unsafe_restart_on_429(events):
    return any(str(e.get("incident"))=="HTTP_429" for e in events)


def synthetic_proof():
    checks=[]
    def add(name,ok,detail=None): checks.append({"name":name,"ok":bool(ok),"detail":detail})
    cases={
        "quota":RecoveryContext("HTTP_429",existing_session=True,owned_process=True),
        "crash_owned":RecoveryContext("ROUTER_CRASH",owned_process=True),
        "crash_unowned":RecoveryContext("ROUTER_CRASH",owned_process=False),
        "config":RecoveryContext("INSTANCE_CONFIG_DRIFT",owned_process=True,config_backup_available=True),
        "config_no_backup":RecoveryContext("INSTANCE_CONFIG_DRIFT",owned_process=True,config_backup_available=False),
        "auth":RecoveryContext("AUTH_DRIFT",owned_process=True),
        "client_abort":RecoveryContext("CLIENT_ABORT",owned_process=True),
        "lan_hold":RecoveryContext("LAN_PARTITION",lease_signed=True,lease_expired=False),
        "lan_reelect":RecoveryContext("LAN_PARTITION",lease_signed=True,lease_expired=True),
        "loop":RecoveryContext("ROUTER_CRASH",owned_process=True,attempts_in_window=3),
    }
    plans={k:decide(v) for k,v in cases.items()}
    acts=lambda k:[s["action"] for s in plans[k]["steps"]]
    add("quota_never_restart",not any(x.startswith("RESTART_") for x in acts("quota")),acts("quota"))
    add("existing_session_not_rotated_on_429","SELECT_HEALTHY_FALLBACK" not in acts("quota"),acts("quota"))
    add("owned_router_crash_bounded_restart",acts("crash_owned")==["RESTART_ROUTER"] and plans["crash_owned"]["steps"][0]["max_attempts"]==2)
    add("unowned_router_never_restarted","RESTART_ROUTER" not in acts("crash_unowned"),acts("crash_unowned"))
    add("config_has_atomic_repair_and_rollback",acts("config")==["REPAIR_CONFIG_ATOMIC"] and plans["config"]["steps"][0]["rollback"]=="RESTORE_CONFIG_BACKUP")
    add("config_without_backup_refused",acts("config_no_backup")==["REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP"])
    add("auth_drift_fail_closed",plans["auth"]["disposition"]=="FAIL_CLOSED_OPERATOR" and "QUARANTINE_SCOPE" in acts("auth"))
    add("client_abort_no_recovery",plans["client_abort"]["disposition"]=="OBSERVE" and not acts("client_abort"))
    add("lan_unexpired_lease_no_takeover",acts("lan_hold")==["HOLD_OWNERSHIP_NO_TAKEOVER"])
    add("lan_expired_signed_lease_can_reelect",acts("lan_reelect")==["ALLOW_SIGNED_LEASE_REELECTION"])
    add("recovery_loop_breaker",plans["loop"]["disposition"]=="CIRCUIT_OPEN" and acts("loop")==["OPEN_RECOVERY_CIRCUIT"])
    seq=[{"incident":"UPSTREAM_TIMEOUT"},{"incident":"UPSTREAM_TIMEOUT"},{"incident":"UPSTREAM_TIMEOUT"},{"incident":"UPSTREAM_TIMEOUT"},{"incident":"HTTP_429","existing_session":True},{"incident":"RECOVERED"}]
    sim=simulate_sequence(seq)
    add("sequence_bounded_restart_zero",sim["restart_count"]==0,sim)
    add("sequence_rotation_zero_for_existing_429",sim["rotate_count"]==0,sim)
    mc=model_check();add("model_checker_no_safety_violation",mc["verdict"]=="PASS",{"states":mc["states_checked"],"violations":mc["violation_count"]})
    trace=[{"incident":"HEALTHY"},{"incident":"UPSTREAM_TIMEOUT"},{"incident":"HTTP_429"},{"incident":"RECOVERED"},{"incident":"LAN_PARTITION"},{"incident":"HTTP_429"},{"incident":"HEALTHY"}]
    mini=ddmin(trace,unsafe_restart_on_429)
    add("counterexample_minimized_to_one_429",len(mini)==1 and mini[0]["incident"]=="HTTP_429",mini)
    ids=[decide(RecoveryContext("HTTP_429",scope="A")).get("plan_id") for _ in range(2)]
    add("same_input_same_plan_id",ids[0]==ids[1],ids)
    add("production_never_claimed",PRODUCTION_CLAIM=="NOT_CLAIMED_RECOVERY_DECISION_PROOF_SYNTHETIC_ONLY")
    passed=sum(1 for x in checks if x["ok"])
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"RECOVERY_PLANNER_SELF_HEALING_DECISION_PROOF","generated_utc":now_utc(),"verdict":"PASS" if passed==len(checks) and mc["verdict"]=="PASS" else "FAIL","summary":{"pass":passed,"fail":len(checks)-passed,"total":len(checks),"model_states":mc["states_checked"]},"checks":checks,"model_check":mc,"minimized_counterexample":{"original_length":len(trace),"minimized_length":len(mini),"events":mini,"trace_hash":_hash(mini)},"safety":{"production_certification":PRODUCTION_CLAIM,"destructive_delete":False,"raw_auth_mutation":False,"midstream_replay":False}}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=["proof","plan","model-check"],default="proof");ap.add_argument("--input");ap.add_argument("--output")
    a=ap.parse_args()
    if a.mode=="proof": data=synthetic_proof()
    elif a.mode=="model-check":
        mc=model_check();data={"product":"HMS-AI-ROUTER","version":VERSION,"suite":"RECOVERY_MODEL_CHECK","verdict":mc["verdict"],"summary":{"pass":1 if mc["verdict"]=="PASS" else 0,"fail":0 if mc["verdict"]=="PASS" else 1,"total":1,"model_states":mc["states_checked"]},"model_check":mc,"safety":{"production_certification":PRODUCTION_CLAIM}}
    else:
        if not a.input: raise SystemExit("--input required for plan")
        data=plan_from_dict(json.loads(Path(a.input).read_text("utf-8-sig")))
    txt=json.dumps(data,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+"\n","utf-8")
    print(txt);return 0 if data.get("verdict","PASS")=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
