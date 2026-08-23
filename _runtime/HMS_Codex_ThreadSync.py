#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil
from pathlib import Path
from datetime import datetime
SESSION_DIRS=("sessions","archived_sessions")
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""): h.update(c)
    return h.hexdigest()
def first_json(p):
    try:
        with p.open("r",encoding="utf-8",errors="replace") as f: line=f.readline().strip()
        return json.loads(line) if line else {}
    except Exception:return {}
def sid(o):
    if not isinstance(o,dict):return None
    for k in ("id","session_id","sessionId","thread_id","threadId"):
        v=o.get(k)
        if isinstance(v,str) and v:return v
    return sid(o.get("payload")) if isinstance(o.get("payload"),dict) else None
def session_map(home):
    out={}
    for d in SESSION_DIRS:
        root=home/d
        if not root.exists():continue
        for p in root.rglob("*.jsonl"):out.setdefault(sid(first_json(p)) or p.stem,[]).append((d,p))
    return out
def load_index(home):
    p=home/"session_index.jsonl";rows=[];ids=set()
    if not p.exists():return rows,ids
    for line in p.read_text("utf-8",errors="replace").splitlines():
        if not line.strip():continue
        try:j=json.loads(line);rows.append(j);x=sid(j);ids.add(x) if x else None
        except Exception:rows.append({"_hms_unparsed":line})
    return rows,ids
def backup_index(home):
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    b=home/"hms_backups"/f"{stamp}-thread-sync";b.mkdir(parents=True,exist_ok=False)
    p=home/"session_index.jsonl"
    if p.exists():shutil.copy2(p,b/"session_index.jsonl")
    return b
def audit(homes):
    maps={str(h):session_map(h) for h in homes};all_ids=set()
    for m in maps.values():all_ids.update(m)
    return {"homes":len(homes),"global_sessions":len(all_ids),
            "targets":[{"home":str(h),"session_count":len(maps[str(h)]),"missing_from_global":len(all_ids-set(maps[str(h)]))} for h in homes]}
def sync(homes):
    maps={str(h):session_map(h) for h in homes};all_ids=set()
    for m in maps.values():all_ids.update(m)
    summaries=[]
    for target in homes:
        tmap=maps[str(target)];rows,index_ids=load_index(target);b=None;copied=0;added=0;conf=[]
        for x in sorted(all_ids):
            if x in tmap:continue
            source=None
            for sh in homes:
                if sh==target:continue
                vals=maps[str(sh)].get(x)
                if vals:source=(sh,vals[0]);break
            if not source:continue
            sh,(d,sp)=source
            root=next((q for q in sp.parents if q.name==d),None)
            rel=sp.relative_to(root) if root else Path(sp.name)
            dp=target/d/rel
            if dp.exists():
                if sha256(dp)!=sha256(sp):conf.append({"session_id":x,"source":str(sp),"target":str(dp)})
                continue
            if b is None:b=backup_index(target)
            dp.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(sp,dp);copied+=1
            if x not in index_ids:
                for hh in homes:
                    rr,_=load_index(hh)
                    found=next((r for r in rr if isinstance(r,dict) and sid(r)==x),None)
                    if found:rows.append(found);index_ids.add(x);added+=1;break
        if added:
            if b is None:b=backup_index(target)
            idx=target/"session_index.jsonl";tmp=idx.with_suffix(".jsonl.hms.tmp")
            with tmp.open("w",encoding="utf-8",newline="\n") as f:
                for r in rows:f.write((r["_hms_unparsed"] if "_hms_unparsed" in r else json.dumps(r,ensure_ascii=False,separators=(",",":")))+"\n")
            os.replace(tmp,idx)
        summaries.append({"home":str(target),"copied_sessions":copied,"index_added":added,"backup":str(b) if b else None,"conflicts":conf})
    return {"homes":len(homes),"session_ids":len(all_ids),"targets":summaries}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--home",action="append",required=True);ap.add_argument("--mode",choices=("audit","sync"),default="audit");ap.add_argument("--output")
    a=ap.parse_args();homes=[Path(x).expanduser().resolve() for x in a.home]
    try:o={"ok":True,"mode":a.mode,"data":audit(homes) if a.mode=="audit" else sync(homes)}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
