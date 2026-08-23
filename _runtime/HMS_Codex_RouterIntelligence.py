#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta

def dt(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except:return None

def parse_history(path):
    if not path or not Path(path).exists():return []
    out=[]
    for line in Path(path).read_text("utf-8",errors="replace").splitlines()[-10000:]:
        try:
            j=json.loads(line)
            out.append({"time":j.get("time"),"type":j.get("type") or j.get("event") or "INFO",
                        "account":j.get("account") or j.get("email"),"message":j.get("message") or ""})
        except:pass
    return out

def recent_counts(events,minutes):
    cutoff=datetime.now(timezone.utc)-timedelta(minutes=minutes)
    c={}
    for e in events:
        t=dt(e.get("time"))
        if t and t.tzinfo is None:t=t.replace(tzinfo=timezone.utc)
        if t and t<cutoff:continue
        a=e.get("account")
        if not a:continue
        r=c.setdefault(a,{"route":0,"failover":0,"cooldown":0,"error":0,"last_seen":None})
        typ=str(e.get("type") or "").upper()
        if "ROUTE" in typ or "ATTRIBUT" in typ:r["route"]+=1
        if "FAIL" in typ or "RETRY" in typ:r["failover"]+=1
        if "COOLDOWN" in typ or "429" in typ:r["cooldown"]+=1
        if "ERROR" in typ:r["error"]+=1
        if e.get("time"):r["last_seen"]=e.get("time")
    return c

def eligible_reason(a):
    rs=str(a.get("router_status") or "").upper()
    ops=str(a.get("ops_state") or "ACTIVE").upper()
    circuit=str(a.get("circuit") or "CLOSED").upper()
    reasons=[]
    if rs!="READY":reasons.append("router_status="+rs)
    if ops=="MAINTENANCE":reasons.append("maintenance")
    if ops=="QUARANTINED":reasons.append("quarantined")
    if circuit in ("OPEN","LOCKED_OPEN"):reasons.append("circuit="+circuit)
    eligible=not reasons
    return eligible,("eligible" if eligible else "; ".join(reasons))

def strategy_description(profile,affinity_ttl):
    p=(profile or "stable").lower()
    if p=="balanced":
        return {"strategy":"round-robin","session_affinity":False,"ttl":affinity_ttl,
                "explanation":"Request/session mới được chia qua pool; không cố giữ sticky session."}
    if p=="fill-first":
        return {"strategy":"fill-first","session_affinity":True,"ttl":affinity_ttl,
                "explanation":"Ưu tiên dùng credential theo fill-first; không phải chế độ chia pool mặc định."}
    return {"strategy":"round-robin","session_affinity":True,"ttl":affinity_ttl,
            "explanation":"Round-robin giữa pool, nhưng session đã bind thường giữ account cũ; failover khi credential không khả dụng."}

def build(data):
    events=parse_history(data.get("history"))
    for e in data.get("log_events",[]):
        if not isinstance(e,dict):continue
        events.append({"time":e.get("time"),"type":e.get("type") or e.get("Type") or "INFO",
                       "account":e.get("account") or e.get("Account"),
                       "message":e.get("message") or e.get("Message") or ""})
    counts=recent_counts(events,int(data.get("window_minutes",60)))
    rows=[]
    for a in data.get("accounts",[]):
        e,reason=eligible_reason(a)
        c=counts.get(a.get("email"),{})
        rows.append({**a,"eligible":e,"eligibility_reason":reason,
                     "recent_confirmed_routes":c.get("route",0),"recent_failovers":c.get("failover",0),
                     "recent_cooldowns":c.get("cooldown",0),"recent_errors":c.get("error",0),
                     "last_seen":c.get("last_seen")})
    strat=strategy_description(data.get("profile"),data.get("affinity_ttl"))
    attr=data.get("active_attribution")
    actual={"account":None,"confidence":"UNATTRIBUTED","evidence":None}
    if isinstance(attr,dict) and attr.get("account"):
        actual={"account":attr.get("account"),"confidence":attr.get("confidence") or "PROBABLE",
                "evidence":attr.get("evidence") or attr.get("source")}
    eligible=[r["email"] for r in rows if r["eligible"]]
    if actual["account"]:
        decision=f"Active route evidence: {actual['account']} [{actual['confidence']}]. "
    else:
        decision="Active route: UNATTRIBUTED. "
    decision+=f"Eligible pool: {len(eligible)}/{len(rows)}. "
    if strat["session_affinity"]:
        decision+="Next request cannot be predicted reliably because an existing session may stay bound to its current account."
    else:
        decision+="Next account is still router-owned; HMS shows eligible pool/distribution but does not claim exact next choice."
    timeline=events[-int(data.get("max_events",500)):]
    return {"strategy":strat,"accounts":rows,"eligible_accounts":eligible,"active_route":actual,
            "decision_explanation":decision,"timeline":timeline,
            "totals":{"accounts":len(rows),"eligible":len(eligible),
                      "confirmed_routes":sum(r["recent_confirmed_routes"] for r in rows),
                      "failovers":sum(r["recent_failovers"] for r in rows),
                      "cooldowns":sum(r["recent_cooldowns"] for r in rows)}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:o={"ok":True,"data":build(json.loads(Path(a.input).read_text("utf-8")))}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
