#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path

def score_account(a, policy, quota_floor, prefer_favorite):
    status=str(a.get("status") or "").upper()
    if status!="READY":
        return -10000
    q=a.get("hourly")
    w=a.get("weekly")
    h=a.get("health")
    fav=bool(a.get("favorite"))
    score=float(h if isinstance(h,(int,float)) else 60)
    if isinstance(q,(int,float)):
        if q < quota_floor: score -= 500
        else: score += q*0.35
    if isinstance(w,(int,float)): score += w*0.12
    if prefer_favorite and fav: score += 8
    if policy=="reserve":
        score += (q if isinstance(q,(int,float)) else 50)*0.2
    elif policy=="quota-first":
        score += (q if isinstance(q,(int,float)) else 40)*0.9
    elif policy=="weekly-first":
        score += (w if isinstance(w,(int,float)) else 40)*0.8
    return score

def plan(accounts, instances, policy, quota_floor, reserve_count, max_per_account, prefer_favorite):
    ranked=[]
    for a in accounts:
        s=score_account(a,policy,quota_floor,prefer_favorite)
        ranked.append((s,a))
    ranked.sort(key=lambda x:(x[0],str(x[1].get("email",""))),reverse=True)
    healthy=[a for s,a in ranked if s>-1000]
    reserves=[]
    if reserve_count>0 and len(healthy)>reserve_count:
        reserves=healthy[-reserve_count:]
        alloc=healthy[:-reserve_count]
    else:
        alloc=healthy
    if not alloc: alloc=healthy
    counts={str(a.get("email")):0 for a in healthy}
    assignments=[]
    for inst in instances:
        current=str(inst.get("account") or "")
        candidates=[]
        for a in alloc:
            e=str(a.get("email"))
            if max_per_account>0 and counts.get(e,0)>=max_per_account: continue
            candidates.append(a)
        if not candidates:
            candidates=alloc or healthy
        chosen=None
        if policy=="sticky" and current:
            chosen=next((a for a in candidates if str(a.get("email"))==current),None)
        if chosen is None and candidates:
            chosen=max(candidates,key=lambda a:score_account(a,policy,quota_floor,prefer_favorite)-counts.get(str(a.get("email")),0)*18)
        if chosen:
            e=str(chosen.get("email")); counts[e]=counts.get(e,0)+1
            assignments.append({"instance_id":inst.get("id"),"instance_name":inst.get("name"),"from":current,"to":e,
                                "changed":e!=current,"score":round(score_account(chosen,policy,quota_floor,prefer_favorite),2)})
        else:
            assignments.append({"instance_id":inst.get("id"),"instance_name":inst.get("name"),"from":current,"to":None,"changed":False,"score":None})
    return {"policy":policy,"healthy_accounts":len(healthy),"reserve_accounts":[a.get("email") for a in reserves],
            "assignments":assignments,"ranked_accounts":[{"email":a.get("email"),"score":round(s,2)} for s,a in ranked]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    data=json.loads(Path(a.input).read_text("utf-8"))
    try:
        result=plan(data["accounts"],data["instances"],data.get("policy","balanced"),
                    int(data.get("quota_floor",15)),int(data.get("reserve_count",1)),
                    int(data.get("max_per_account",1)),bool(data.get("prefer_favorite",True)))
        out={"ok":True,"data":result}
    except Exception as e: out={"ok":False,"error":repr(e)}
    s=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(s,"utf-8")
    print(s)
    return 0 if out.get("ok") else 1
if __name__=="__main__": raise SystemExit(main())
