#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone

def first_json(path:Path):
    try:
        with path.open("r",encoding="utf-8",errors="replace") as f:
            line=f.readline().strip()
        return json.loads(line) if line else {}
    except Exception:return {}

def rec_find(o,keys):
    if isinstance(o,dict):
        for k in keys:
            v=o.get(k)
            if isinstance(v,str) and v:return v
        for v in o.values():
            r=rec_find(v,keys)
            if r:return r
    elif isinstance(o,list):
        for v in o:
            r=rec_find(v,keys)
            if r:return r
    return None

def iso_mtime(p):
    return datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()

def scan_home(home:Path,include_archived=True):
    dirs=["sessions"]+(["archived_sessions"] if include_archived else [])
    rows=[]
    for d in dirs:
        root=home/d
        if not root.exists():continue
        for p in root.rglob("*.jsonl"):
            o=first_json(p)
            sid=rec_find(o,("id","session_id","sessionId","thread_id","threadId")) or p.stem
            provider=rec_find(o,("model_provider","modelProvider","provider"))
            model=rec_find(o,("model","model_name","modelName"))
            cwd=rec_find(o,("cwd","working_directory","workingDirectory","project_path","projectPath"))
            rows.append({"home":str(home),"kind":d,"session_id":sid,"provider":provider,"model":model,
                         "project":cwd,"path":str(p),"mtime_utc":iso_mtime(p)})
    rows.sort(key=lambda x:x["mtime_utc"],reverse=True)
    return rows

def load_json(path):
    try:return json.loads(Path(path).read_text("utf-8-sig"))
    except Exception:return None

def route_events(path:Path):
    if not path.exists():return []
    out=[]
    for line in path.read_text("utf-8",errors="replace").splitlines()[-5000:]:
        try:
            j=json.loads(line)
            acc=j.get("account") or j.get("email")
            if acc:out.append({"account":acc,"time":j.get("time"),"type":j.get("type") or j.get("event"),"message":j.get("message")})
        except Exception:pass
    return out

def bind_visibility(rows,attribution,history):
    active=None
    if isinstance(attribution,dict):
        active=attribution.get("latest_attribution")
    for r in rows:
        r["account"]=None;r["confidence"]="UNATTRIBUTED";r["evidence"]=None
        # We intentionally do not infer a session/account from an unrelated global route unless there is direct session evidence.
        o=first_json(Path(r["path"]))
        s=json.dumps(o,ensure_ascii=False)
        m=re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',s)
        if m:
            r["account"]=m.group(0);r["confidence"]="CONFIRMED";r["evidence"]="session payload contains account email"
        elif active and r==rows[0] and active.get("account"):
            r["account"]=active.get("account");r["confidence"]="PROBABLE";r["evidence"]="latest session + latest global route only"
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--home",action="append",required=True);ap.add_argument("--attribution");ap.add_argument("--route-history")
    ap.add_argument("--include-archived",action="store_true");ap.add_argument("--max",type=int,default=500);ap.add_argument("--output")
    a=ap.parse_args()
    try:
        rows=[]
        for h in a.home:rows.extend(scan_home(Path(h),a.include_archived))
        rows.sort(key=lambda x:x["mtime_utc"],reverse=True)
        attr=load_json(a.attribution) if a.attribution else None
        hist=route_events(Path(a.route_history)) if a.route_history else []
        rows=bind_visibility(rows[:a.max],attr,hist)
        counts={"CONFIRMED":0,"PROBABLE":0,"UNATTRIBUTED":0}
        for r in rows:counts[r["confidence"]]=counts.get(r["confidence"],0)+1
        o={"ok":True,"data":{"sessions":rows,"counts":counts,"total":len(rows)}}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
