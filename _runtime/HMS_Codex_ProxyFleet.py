#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from datetime import datetime, timezone

OPS={"ACTIVE","DRAINING","QUARANTINED","DISABLED"}

def now():return datetime.now(timezone.utc).isoformat()

def loadj(path,default):
    p=Path(path)
    if not p.exists():return default
    try:return json.loads(p.read_text("utf-8-sig"))
    except:return default

def atomic(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2),"utf-8")
    os.replace(t,p)

def append(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n")

def state(path):
    d=loadj(path,{"version":23,"profiles":{}})
    d.setdefault("version",23);d.setdefault("profiles",{})
    return d

def set_state(path,history,profile_id,ops_state,reason=""):
    ops_state=ops_state.upper()
    if ops_state not in OPS:raise ValueError("invalid ops state")
    d=state(path);old=d["profiles"].get(profile_id,{})
    row={
        "ops_state":ops_state,"reason":reason,
        "updated_utc":now(),"previous_state":old.get("ops_state","ACTIVE")
    }
    d["profiles"][profile_id]=row;atomic(path,d)
    append(history,{"time":now(),"event":"OPS_STATE","profile_id":profile_id,
                    "from":row["previous_state"],"to":ops_state,"reason":reason})
    return row

def _profiles(path):
    d=loadj(path,{"profiles":[]});return d.get("profiles",[])

def _bindings(path):
    d=loadj(path,{"bindings":[]});return d.get("bindings",[])

def _map(path):
    d=loadj(path,{"profiles":{}});return d.get("profiles",{})

def _sidecars(path):
    d=loadj(path,{"sidecars":[]});return d.get("sidecars",[])

def _fresh(ts,max_age):
    if not ts:return False
    try:
        when=datetime.fromisoformat(str(ts).replace("Z","+00:00")).timestamp()
        age=time.time()-when
        return age>=0 and age<=max(1,max_age)
    except:return False

def _recent_actions(path,profile_id,seconds=3600):
    p=Path(path)
    if not p.exists():return []
    cutoff=time.time()-seconds;rows=[]
    for line in p.read_text("utf-8",errors="replace").splitlines()[-5000:]:
        try:r=json.loads(line)
        except:continue
        if r.get("profile_id")!=profile_id:continue
        try:ts=datetime.fromisoformat(str(r.get("time")).replace("Z","+00:00")).timestamp()
        except:continue
        if ts>=cutoff:rows.append(r)
    return rows

def audit(profiles_path,bindings_path,health_path,egress_path,sidecar_path,fleet_state_path,action_history,
          quarantine_health=True,quarantine_drift=True,max_restarts_per_hour=2,recovery_cooldown=300,
          health_max_age=300,egress_max_age=300):
    profiles=_profiles(profiles_path);bindings=_bindings(bindings_path);health=_map(health_path);egress=_map(egress_path)
    sidecars=_sidecars(sidecar_path);ops=state(fleet_state_path).get("profiles",{})
    by_sidecar={str(x.get("profile_id")):x for x in sidecars}
    rows=[]
    for p in profiles:
        pid=str(p.get("id"));assigned=sum(1 for b in bindings if b.get("proxy_profile_id")==pid)
        h=health.get(pid,{})
        e=egress.get(pid,{})
        sc=by_sidecar.get(pid)
        op=ops.get(pid,{}).get("ops_state","ACTIVE")
        reason=ops.get(pid,{}).get("reason","")
        hstat=str(h.get("status") or "UNKNOWN").upper()
        estat=str(e.get("integrity_status") or "UNKNOWN").upper()
        health_fresh=_fresh(h.get("checked_utc"),health_max_age)
        egress_fresh=_fresh(e.get("checked_utc"),egress_max_age)
        if hstat=="PASS" and not health_fresh:hstat="STALE"
        if estat=="PASS" and not egress_fresh:estat="STALE"
        running=bool(sc and str(sc.get("status","")).upper()=="RUNNING")
        capacity=max(1,int(p.get("max_accounts") or 5))
        cap_ok=assigned<=capacity
        severity="HEALTHY"
        recommendation="NONE"
        auto_action=None

        if op=="DISABLED":
            severity="DISABLED";recommendation="STOP_IF_RUNNING"
        elif op=="QUARANTINED":
            severity="QUARANTINED";recommendation="STOP_AND_REVIEW"
        elif op=="DRAINING":
            severity="DRAINING";recommendation="EXCLUDE_NEW_ROUTES"
        elif not cap_ok:
            severity="CRITICAL";recommendation="REBALANCE_CAPACITY"
        elif quarantine_drift and estat=="DRIFT":
            severity="CRITICAL";recommendation="QUARANTINE_EGRESS_DRIFT"
        elif quarantine_health and hstat=="FAIL":
            severity="CRITICAL";recommendation="QUARANTINE_HEALTH_FAIL"
        elif estat in ("FAIL","BASELINE_REQUIRED","UNKNOWN"):
            severity="DEGRADED";recommendation="CHECK_EGRESS"
        elif hstat!="PASS":
            severity="DEGRADED";recommendation="CHECK_HEALTH"
        elif assigned==0:
            severity="IDLE";recommendation="NONE"
        elif not running:
            severity="RECOVERABLE";recommendation="START_SIDECAR"
            actions=_recent_actions(action_history,pid,3600)
            restarts=[x for x in actions if x.get("action")=="START_SIDECAR"]
            last=max([datetime.fromisoformat(x["time"].replace("Z","+00:00")).timestamp() for x in restarts],default=0)
            if len(restarts)<max_restarts_per_hour and time.time()-last>=recovery_cooldown:
                auto_action="START_SIDECAR"

        if severity=="CRITICAL" and recommendation.startswith("QUARANTINE"):
            auto_action="QUARANTINE"
        rows.append({
            "profile_id":pid,"profile_name":p.get("name"),"ops_state":op,"ops_reason":reason,
            "assigned":assigned,"capacity":capacity,"capacity_ok":cap_ok,
            "health_status":hstat,"egress_status":estat,
            "expected_ip":e.get("expected_ip"),"observed_ip":e.get("observed_ip"),
            "sidecar_running":running,"sidecar_pid":sc.get("pid") if sc else None,
            "sidecar_port":sc.get("port") if sc else None,
            "severity":severity,"recommendation":recommendation,"auto_action":auto_action
        })
    summary={
        "total":len(rows),
        "healthy":sum(1 for x in rows if x["severity"]=="HEALTHY"),
        "critical":sum(1 for x in rows if x["severity"]=="CRITICAL"),
        "quarantined":sum(1 for x in rows if x["ops_state"]=="QUARANTINED"),
        "draining":sum(1 for x in rows if x["ops_state"]=="DRAINING"),
        "recoverable":sum(1 for x in rows if x["severity"]=="RECOVERABLE")
    }
    verdict="CRITICAL" if summary["critical"] else ("DEGRADED" if any(x["severity"] in ("DEGRADED","RECOVERABLE","DRAINING") for x in rows) else "HEALTHY")
    return {"version":23,"generated_utc":now(),"verdict":verdict,"summary":summary,"profiles":rows}

def record_action(path,profile_id,action,result,detail=""):
    row={"time":now(),"profile_id":profile_id,"action":action,"result":result,"detail":detail}
    append(path,row);return row

def safe_export(profiles_path,bindings_path,health_path,egress_path,fleet_state_path):
    ps=_profiles(profiles_path)
    safe=[]
    for p in ps:
        q={k:v for k,v in p.items() if k not in ("secret_ref",)}
        safe.append(q)
    return {
        "version":23,"generated_utc":now(),"profiles":safe,
        "bindings":_bindings(bindings_path),
        "health":_map(health_path),"egress":_map(egress_path),
        "fleet_state":state(fleet_state_path).get("profiles",{}),
        "contains_proxy_passwords":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profiles",required=True);ap.add_argument("--bindings",required=True)
    ap.add_argument("--health",required=True);ap.add_argument("--egress",required=True)
    ap.add_argument("--sidecars",required=True);ap.add_argument("--fleet-state",required=True)
    ap.add_argument("--history",required=True);ap.add_argument("--actions",required=True)
    sp=ap.add_subparsers(dest="cmd",required=True)
    au=sp.add_parser("audit")
    au.add_argument("--no-health-quarantine",action="store_true")
    au.add_argument("--no-drift-quarantine",action="store_true")
    au.add_argument("--max-restarts-hour",type=int,default=2)
    au.add_argument("--recovery-cooldown",type=int,default=300)
    au.add_argument("--health-max-age",type=int,default=300)
    au.add_argument("--egress-max-age",type=int,default=300)
    st=sp.add_parser("set-state");st.add_argument("--profile-id",required=True);st.add_argument("--state",required=True);st.add_argument("--reason",default="")
    ra=sp.add_parser("record-action");ra.add_argument("--profile-id",required=True);ra.add_argument("--action",required=True);ra.add_argument("--result",required=True);ra.add_argument("--detail",default="")
    sp.add_parser("safe-export")
    a=ap.parse_args()
    if a.cmd=="audit":
        r=audit(a.profiles,a.bindings,a.health,a.egress,a.sidecars,a.fleet_state,a.actions,
                not a.no_health_quarantine,not a.no_drift_quarantine,a.max_restarts_hour,a.recovery_cooldown,
                a.health_max_age,a.egress_max_age)
        atomic(a.history.replace(".jsonl","-latest.json"),r)
        append(a.history,{"time":now(),"event":"AUDIT","verdict":r["verdict"],"summary":r["summary"]})
        print(json.dumps({"ok":True,"data":r},ensure_ascii=False,indent=2))
    elif a.cmd=="set-state":
        r=set_state(a.fleet_state,a.actions,a.profile_id,a.state,a.reason)
        print(json.dumps({"ok":True,"data":r},ensure_ascii=False,indent=2))
    elif a.cmd=="record-action":
        print(json.dumps({"ok":True,"data":record_action(a.actions,a.profile_id,a.action,a.result,a.detail)},ensure_ascii=False))
    elif a.cmd=="safe-export":
        print(json.dumps({"ok":True,"data":safe_export(a.profiles,a.bindings,a.health,a.egress,a.fleet_state)},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
