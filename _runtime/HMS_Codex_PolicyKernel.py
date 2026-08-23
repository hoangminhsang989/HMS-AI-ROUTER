#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from datetime import datetime,timezone,timedelta

SAFE_AUTO_ALLOWLIST={
    "START_OWNED_MAIN_ROUTER",
    "RUN_POOL_AUDIT",
    "REFRESH_ROUTER_INTELLIGENCE",
    "REFRESH_PERFORMANCE",
    "PUBLISH_HEALTH_CERTIFICATE",
}
NEVER_AUTO={
    "DELETE_CREDENTIAL","DISABLE_CREDENTIAL","SYNC_CREDENTIAL","REBIND_INSTANCE",
    "KILL_PROCESS","STOP_FOREIGN_PROCESS","ROLLBACK_RELEASE","CRASH_TEST",
}

def now():return datetime.now(timezone.utc).isoformat()

def load(path):
    if not path:return None
    p=Path(path)
    if not p.exists():return None
    try:return json.loads(p.read_text("utf-8-sig"))
    except:return None

def recent_actions(path,hours=1):
    p=Path(path) if path else None
    if not p or not p.exists():return []
    cut=datetime.now(timezone.utc)-timedelta(hours=hours)
    out=[]
    for line in p.read_text("utf-8",errors="replace").splitlines()[-5000:]:
        try:j=json.loads(line)
        except:continue
        try:t=datetime.fromisoformat(str(j.get("time")).replace("Z","+00:00"))
        except:continue
        if t>=cut:out.append(j)
    return out

def action(kind,priority,reason,auto_safe=False,scope="system"):
    return {"kind":kind,"priority":priority,"reason":reason,"auto_safe":bool(auto_safe),
            "scope":scope,"status":"RECOMMENDED"}

def evaluate(inp):
    mode=str(inp.get("mode","OBSERVE")).upper()
    previous=inp.get("kernel_state") or {}
    sla=inp.get("sla") or {}
    pool=inp.get("pool") or {}
    perf=inp.get("performance") or {}
    rec=inp.get("pool_reconcile") or {}
    soak=inp.get("soak") or {}
    router=inp.get("router") or {}
    cfg=inp.get("config") or {}
    actions=[]
    signals=[]
    score=100

    online=bool(router.get("online"))
    owned=bool(router.get("owned"))
    hms_mode=bool(router.get("hms_mode"))
    ready=int(pool.get("ready") or 0);total=int(pool.get("total") or 0)
    sla_score=int(sla.get("Score") or sla.get("score") or 0)
    rec_problems=int(((rec.get("summary") or {}).get("problems") or 0))
    perf_verdict=str(perf.get("verdict") or "UNKNOWN").upper()
    soak_verdict=str(soak.get("verdict") or "UNKNOWN").upper()

    if not online and hms_mode:
        score-=35;signals.append({"severity":"CRITICAL","code":"MAIN_ROUTER_OFFLINE","value":True})
        if owned or not router.get("listener_pid"):
            actions.append(action("START_OWNED_MAIN_ROUTER",100,"HMS mode active and main router port is not served by a foreign listener.",True))
        else:
            actions.append(action("OPERATOR_REVIEW_FOREIGN_PORT",100,"Router port has a foreign owner; HMS will not start/kill over it.",False))
    if total>0 and ready<=int(cfg.get("ready_critical",0)):
        score-=30;signals.append({"severity":"CRITICAL","code":"POOL_READY_CRITICAL","value":ready})
        actions.append(action("RUN_POOL_AUDIT",90,"Pool has no READY account; refresh reconciliation evidence.",True))
        actions.append(action("REFRESH_ROUTER_INTELLIGENCE",85,"Refresh eligible-pool explanation.",True))
    elif total>0 and ready<total:
        score-=10;signals.append({"severity":"WARN","code":"POOL_DEGRADED","value":f"{ready}/{total}"})
    if sla_score<int(cfg.get("sla_critical",50)):
        score-=25;signals.append({"severity":"CRITICAL","code":"SLA_CRITICAL","value":sla_score})
        actions.append(action("PUBLISH_HEALTH_CERTIFICATE",80,"SLA is critical; publish a fresh health snapshot.",True))
    elif sla_score<int(cfg.get("sla_degraded",75)):
        score-=10;signals.append({"severity":"WARN","code":"SLA_DEGRADED","value":sla_score})
    if rec_problems>0:
        score-=min(20,rec_problems*5)
        signals.append({"severity":"WARN","code":"POOL_RECONCILE_PROBLEMS","value":rec_problems})
        actions.append(action("RUN_POOL_AUDIT",75,f"{rec_problems} pool reconciliation issue(s) need fresh evidence.",True))
        # Credential sync stays recommendation-only, never auto.
        actions.append(action("REVIEW_POOL_RECONCILIATION",70,"Credential drift/conflicts require stopped-instance/operator review.",False))
    if perf_verdict=="WARN":
        score-=8;signals.append({"severity":"WARN","code":"PERFORMANCE_WARN","value":perf_verdict})
        actions.append(action("REFRESH_PERFORMANCE",60,"Refresh performance evidence before any operational change.",True))
    elif perf_verdict=="FAIL":
        score-=18;signals.append({"severity":"CRITICAL","code":"PERFORMANCE_FAIL","value":perf_verdict})
        actions.append(action("REFRESH_PERFORMANCE",80,"Refresh performance evidence; no destructive remediation is allowed.",True))
    if soak_verdict=="FAIL":
        score-=20;signals.append({"severity":"CRITICAL","code":"SOAK_FAIL","value":soak_verdict})
        actions.append(action("OPERATOR_REVIEW_SOAK",80,"Completed soak failed. Automated mutation is suppressed.",False))

    # Dedupe highest priority per action kind.
    ded={}
    for a in actions:
        if a["kind"] not in ded or a["priority"]>ded[a["kind"]]["priority"]:ded[a["kind"]]=a
    actions=sorted(ded.values(),key=lambda x:-x["priority"])

    history=recent_actions(inp.get("action_history"))
    max_actions=int(cfg.get("max_actions_per_hour",4))
    max_router=int(cfg.get("max_router_starts_per_hour",2))
    used=len([x for x in history if x.get("result")=="EXECUTED"])
    router_used=len([x for x in history if x.get("kind")=="START_OWNED_MAIN_ROUTER" and x.get("result")=="EXECUTED"])
    budget={"used":used,"max":max_actions,"remaining":max(0,max_actions-used),
            "routerStartsUsed":router_used,"routerStartsMax":max_router,
            "routerStartsRemaining":max(0,max_router-router_used)}

    prev_streaks=previous.get("streaks") or {}
    prev_last=previous.get("lastActionUtc") or {}
    kinds={a["kind"] for a in actions}
    streaks={k:(int(prev_streaks.get(k,0))+1 if k in kinds else 0) for k in set(prev_streaks)|kinds}
    hysteresis=max(1,int(cfg.get("hysteresis_cycles",2)))
    cooldown=max(0,int(cfg.get("cooldown_sec",180)))
    nowdt=datetime.now(timezone.utc)

    def cooldown_ok(kind):
        v=prev_last.get(kind)
        if not v:return True
        try:last=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        except:return True
        return (nowdt-last).total_seconds()>=cooldown

    # Mode/allowlist/budget/hysteresis/cooldown gating. This engine never executes.
    for a in actions:
        kind=a["kind"]
        a["streak"]=int(streaks.get(kind,0))
        a["hysteresis_required"]=hysteresis
        a["cooldown_ok"]=cooldown_ok(kind)
        a["auto_allowed"]=False
        if mode=="SAFE_AUTO" and a["auto_safe"] and kind in SAFE_AUTO_ALLOWLIST and kind not in NEVER_AUTO:
            if (a["streak"]>=hysteresis and a["cooldown_ok"] and budget["remaining"]>0
                and (kind!="START_OWNED_MAIN_ROUTER" or budget["routerStartsRemaining"]>0)):
                a["auto_allowed"]=True
        if mode=="OBSERVE":a["status"]="OBSERVED"
        elif mode=="RECOMMEND":a["status"]="RECOMMENDED"
        elif a["auto_allowed"]:a["status"]="AUTO_ELIGIBLE"
        else:a["status"]="OPERATOR_ONLY"

    score=max(0,min(100,score))
    state="HEALTHY" if score>=90 else ("DEGRADED" if score>=70 else ("CRITICAL" if score>=40 else "PROTECT"))
    return {"generatedUtc":now(),"mode":mode,"score":score,"state":state,"signals":signals,
            "actions":actions,"budget":budget,
            "kernel_state":{"streaks":streaks,"lastActionUtc":prev_last,"lastCycleUtc":now()},
            "safety":{"allowlist":sorted(SAFE_AUTO_ALLOWLIST),"neverAuto":sorted(NEVER_AUTO),
                      "credentialSyncAuto":False,"rebindAuto":False,"processKillAuto":False,"destructiveAuto":False}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:o={"ok":True,"data":evaluate(json.loads(Path(a.input).read_text("utf-8-sig")))}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
