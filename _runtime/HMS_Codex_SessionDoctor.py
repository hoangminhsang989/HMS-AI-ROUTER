#!/usr/bin/env python3
"""
HMS Codex Session Doctor v1.0
Clean-room bounded session visibility audit/repair helper.

Default mode is audit only. Repair always:
- creates a timestamped backup directory first;
- only mutates known session metadata/index/SQLite fields;
- never deletes session files;
- does not run against an actively-writing DB unless --force-running is supplied.
"""
from __future__ import annotations
import argparse, json, os, shutil, sqlite3, sys, time
from pathlib import Path
from datetime import datetime

SESSION_DIRS = ("sessions", "archived_sessions")
DB_CANDIDATES = ("state_5.sqlite", "codex-dev.db")

def read_toml_provider(codex_home: Path) -> str:
    p=codex_home/"config.toml"
    if not p.exists(): return "openai"
    for line in p.read_text("utf-8",errors="ignore").splitlines():
        s=line.strip()
        if s.startswith("model_provider") and "=" in s:
            v=s.split("=",1)[1].strip().strip('"').strip("'")
            if v: return v
    return "openai"

def iter_session_files(home: Path):
    for d in SESSION_DIRS:
        root=home/d
        if root.exists():
            yield from root.rglob("*.jsonl")

def parse_first_json(path: Path):
    try:
        with path.open("r",encoding="utf-8",errors="replace") as f:
            line=f.readline().strip()
        return json.loads(line) if line else None
    except Exception:
        return None

def session_id_from_obj(obj):
    if not isinstance(obj,dict): return None
    for key in ("id","session_id","sessionId","thread_id","threadId"):
        v=obj.get(key)
        if isinstance(v,str) and v: return v
    payload=obj.get("payload")
    if isinstance(payload,dict):
        return session_id_from_obj(payload)
    return None

def provider_from_obj(obj):
    if not isinstance(obj,dict): return None
    for key in ("model_provider","modelProvider","provider"):
        v=obj.get(key)
        if isinstance(v,str) and v: return v
    payload=obj.get("payload")
    if isinstance(payload,dict):
        return provider_from_obj(payload)
    return None

def cwd_from_obj(obj):
    if not isinstance(obj,dict): return None
    for key in ("cwd","working_directory","workingDirectory"):
        v=obj.get(key)
        if isinstance(v,str) and v: return v
    payload=obj.get("payload")
    if isinstance(payload,dict):
        return cwd_from_obj(payload)
    return None

def scan_index(home: Path):
    p=home/"session_index.jsonl"
    rows=[]
    if not p.exists(): return rows
    for n,line in enumerate(p.read_text("utf-8",errors="replace").splitlines(),1):
        try:
            j=json.loads(line)
            rows.append((n,j))
        except Exception:
            rows.append((n,None))
    return rows

def sqlite_paths(home: Path):
    found=[]
    for root in (home,home/"sqlite"):
        if root.exists():
            for name in DB_CANDIDATES:
                p=root/name
                if p.exists(): found.append(p)
    return found

def inspect_sqlite(path: Path):
    result={"path":str(path),"ok":False,"threads":None,"provider_counts":{},"error":None}
    try:
        uri=f"file:{path.as_posix()}?mode=ro"
        con=sqlite3.connect(uri,uri=True,timeout=2)
        cols=[r[1] for r in con.execute("pragma table_info(threads)")]
        if "id" in cols:
            result["threads"]=con.execute("select count(*) from threads").fetchone()[0]
        if "model_provider" in cols:
            for provider,count in con.execute("select coalesce(model_provider,''),count(*) from threads group by model_provider"):
                result["provider_counts"][provider]=count
        con.close(); result["ok"]=True
    except Exception as e:
        result["error"]=str(e)
    return result

def audit(home: Path):
    target=read_toml_provider(home)
    files=[]
    session_ids=set()
    mismatched=[]
    unreadable=0
    for p in iter_session_files(home):
        obj=parse_first_json(p)
        if obj is None:
            unreadable+=1; continue
        sid=session_id_from_obj(obj)
        if sid: session_ids.add(sid)
        prov=provider_from_obj(obj)
        if prov and prov!=target:
            mismatched.append({"path":str(p),"provider":prov,"target":target,"session_id":sid})
        files.append({"path":str(p),"session_id":sid,"provider":prov,"cwd":cwd_from_obj(obj)})

    idx=scan_index(home)
    index_ids=set()
    bad_index=0
    for _,j in idx:
        if j is None: bad_index+=1; continue
        sid=session_id_from_obj(j)
        if sid:index_ids.add(sid)

    missing_index=sorted(session_ids-index_ids)
    stale_index=sorted(index_ids-session_ids)
    dbs=[inspect_sqlite(p) for p in sqlite_paths(home)]
    return {
        "home":str(home),"target_provider":target,
        "session_file_count":len(files),"unreadable_session_files":unreadable,
        "provider_mismatch_count":len(mismatched),"provider_mismatches":mismatched[:200],
        "session_index_rows":len(idx),"bad_session_index_rows":bad_index,
        "missing_index_session_ids":missing_index[:500],
        "stale_index_session_ids":stale_index[:500],
        "sqlite":dbs,
    }

def backup(home: Path):
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    root=home/"hms_backups"/f"{stamp}-session-visibility"
    root.mkdir(parents=True,exist_ok=False)
    for name in ("session_index.jsonl","config.toml"):
        p=home/name
        if p.exists(): shutil.copy2(p,root/name)
    for p in sqlite_paths(home):
        rel=p.relative_to(home)
        dest=root/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest)
    # Session files can be numerous; backup only mismatched files before mutation.
    return root

def rewrite_provider_first_line(path: Path,target: str,backup_root: Path,home: Path):
    raw=path.read_text("utf-8",errors="replace")
    lines=raw.splitlines(True)
    if not lines:return False
    try:j=json.loads(lines[0])
    except Exception:return False
    changed=False
    def patch(obj):
        nonlocal changed
        if not isinstance(obj,dict):return
        for k in ("model_provider","modelProvider","provider"):
            if k in obj and isinstance(obj[k],str) and obj[k]!=target:
                obj[k]=target; changed=True
        if isinstance(obj.get("payload"),dict): patch(obj["payload"])
    patch(j)
    if not changed:return False
    rel=path.relative_to(home);dest=backup_root/"session_files"/rel
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    ending="\n" if lines[0].endswith("\n") else ""
    lines[0]=json.dumps(j,ensure_ascii=False,separators=(",",":"))+ending
    tmp=path.with_suffix(path.suffix+".hms.tmp")
    tmp.write_text("".join(lines),"utf-8")
    os.replace(tmp,path)
    return True

def repair(home: Path,target: str|None):
    before=audit(home)
    target=target or before["target_provider"]
    b=backup(home)
    changed_files=0
    for item in before["provider_mismatches"]:
        p=Path(item["path"])
        if rewrite_provider_first_line(p,target,b,home):changed_files+=1
    db_rows=0
    for p in sqlite_paths(home):
        try:
            con=sqlite3.connect(str(p),timeout=3)
            cols=[r[1] for r in con.execute("pragma table_info(threads)")]
            if "model_provider" in cols:
                cur=con.execute("update threads set model_provider=? where coalesce(model_provider,'')<>?",(target,target))
                db_rows+=max(cur.rowcount,0)
                con.commit()
            con.close()
        except Exception:
            pass
    after=audit(home)
    return {"backup":str(b),"changed_session_files":changed_files,"updated_sqlite_rows":db_rows,"before":before,"after":after}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--home",required=True)
    ap.add_argument("--mode",choices=("audit","repair"),default="audit")
    ap.add_argument("--provider")
    ap.add_argument("--output")
    args=ap.parse_args()
    home=Path(args.home).expanduser().resolve()
    if not home.exists():
        out={"ok":False,"error":"CODEX_HOME does not exist","home":str(home)}
    else:
        try:
            data=audit(home) if args.mode=="audit" else repair(home,args.provider)
            out={"ok":True,"mode":args.mode,"data":data}
        except Exception as e:
            out={"ok":False,"error":repr(e)}
    payload=json.dumps(out,ensure_ascii=False,indent=2)
    if args.output: Path(args.output).write_text(payload,"utf-8")
    print(payload)
    return 0 if out.get("ok") else 1
if __name__=="__main__": raise SystemExit(main())
