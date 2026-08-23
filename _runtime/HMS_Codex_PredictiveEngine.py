#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
from datetime import datetime

def n(v):
    return float(v) if isinstance(v,(int,float)) else None

def forecast(history, horizon_hours=6):
    by={}
    for snap in history:
        t=snap.get("time")
        try: ts=datetime.fromisoformat(t.replace("Z","+00:00")).timestamp()
        except Exception: continue
        for a in snap.get("accounts",[]):
            e=str(a.get("email") or "")
            if not e: continue
            by.setdefault(e,[]).append((ts,n(a.get("hourly")),n(a.get("weekly"))))
    rows=[]
    for email,pts in by.items():
        pts=sorted(pts,key=lambda x:x[0])
        def calc(ix):
            valid=[(t,p[ix]) for t,*p in pts if p[ix] is not None]
            if len(valid)<2:return (None,None,None)
            t0,v0=valid[0]; t1,v1=valid[-1]
            hours=max((t1-t0)/3600.0,1/60)
            burn=max(0.0,(v0-v1)/hours)
            eta=(v1/burn) if burn>0.001 else None
            projected=max(0.0,v1-burn*horizon_hours)
            return round(burn,3), (round(eta,2) if eta is not None else None), round(projected,2)
        hb,heta,hproj=calc(0); wb,weta,wproj=calc(1)
        latest=pts[-1]
        rows.append({"email":email,"hourly_now":latest[1],"weekly_now":latest[2],
                     "hourly_burn_per_hour":hb,"hourly_eta_zero_hours":heta,"hourly_projected":hproj,
                     "weekly_burn_per_hour":wb,"weekly_eta_zero_hours":weta,"weekly_projected":wproj})
    return rows

def metrics(events):
    by={}
    for e in events:
        a=e.get("account") or "UNATTRIBUTED"
        r=by.setdefault(a,{"requests":0,"errors":0,"cooldowns":0,"failovers":0})
        k=e.get("kind")
        if k=="REQUEST":r["requests"]+=1
        elif k=="ERROR":r["errors"]+=1
        elif k=="COOLDOWN":r["cooldowns"]+=1
        elif k=="FAILOVER":r["failovers"]+=1
    out=[]
    for a,r in by.items():
        denom=max(1,r["requests"]+r["errors"])
        r["error_rate_pct"]=round(100*r["errors"]/denom,2)
        r["account"]=a;out.append(r)
    return out

def decide(forecasts, mets, quota_trigger, error_trigger, min_samples):
    actions=[]
    mm={x["account"]:x for x in mets}
    for f in forecasts:
        e=f["email"]; m=mm.get(e,{})
        samples=int(m.get("requests",0))+int(m.get("errors",0))
        reasons=[]
        if f.get("hourly_now") is not None and f["hourly_now"]<=quota_trigger: reasons.append("hourly_quota_low")
        if f.get("hourly_projected") is not None and f["hourly_projected"]<=quota_trigger: reasons.append("hourly_quota_forecast_low")
        if samples>=min_samples and float(m.get("error_rate_pct",0))>=error_trigger: reasons.append("error_rate_high")
        if reasons: actions.append({"account":e,"action":"ACTIVATE_RESERVE_CANDIDATE","reasons":reasons,"samples":samples})
    return actions

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:
        d=json.loads(Path(a.input).read_text("utf-8"))
        f=forecast(d.get("quota_history",[]),int(d.get("forecast_hours",6)))
        m=metrics(d.get("events",[]))
        actions=decide(f,m,float(d.get("quota_trigger",15)),float(d.get("error_trigger",25)),int(d.get("min_samples",5)))
        o={"ok":True,"data":{"forecast":f,"metrics":m,"recommendations":actions}}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
