#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def check_manifest(root:Path):
    path=root/"RELEASE_MANIFEST_V25_23_1.json"
    if not path.exists():return {"ok":False,"error":"missing RELEASE_MANIFEST_V25_23_1.json","files":[]}
    try:m=json.loads(path.read_text("utf-8"))
    except Exception as e:return {"ok":False,"error":f"manifest parse: {e}","files":[]}
    rows=[];ok=True
    for item in m.get("files",[]):
        p=root/item["path"];exists=p.exists();match=False
        if exists:
            try:match=sha256(p)==item["sha256"]
            except Exception:match=False
        rows.append({"path":item["path"],"exists":exists,"hash_ok":match})
        ok=ok and exists and match
    return {"ok":ok,"files":rows,"version":m.get("version")}

def json_health(data:Path):
    rows=[];bad=0
    if not data.exists():return {"rows":[],"bad":0}
    for p in sorted(data.glob("*.json")):
        try:
            json.loads(p.read_text("utf-8-sig"))
            rows.append({"file":p.name,"ok":True})
        except Exception as e:
            rows.append({"file":p.name,"ok":False,"error":str(e)[:240]});bad+=1
    return {"rows":rows,"bad":bad}

def sqlite_health(data:Path):
    p=data/"codex-ha-v6.sqlite"
    if not p.exists():return {"exists":False,"ok":True,"result":"not-created-yet"}
    try:
        c=sqlite3.connect(f"file:{p.as_posix()}?mode=ro",uri=True,timeout=2)
        row=c.execute("pragma quick_check").fetchone();c.close()
        result=row[0] if row else "unknown"
        return {"exists":True,"ok":result=="ok","result":result}
    except Exception as e:return {"exists":True,"ok":False,"result":str(e)}

def write_test(data:Path):
    try:
        data.mkdir(parents=True,exist_ok=True)
        p=data/".hms-write-test.tmp";p.write_text("ok","utf-8");p.unlink()
        return {"ok":True}
    except Exception as e:return {"ok":False,"error":str(e)}

def static_lint(ps:Path):
    suspicious=[
        "Get-Date-Format","Get-Process-Id","Stop-Process-Id","Test-Path$","Ensure-Dir$",
        "Save-JsonAtomic$","Save-Json$","Add-Content$","Get-Content$","Copy-Item$",
        "Move-Item$","Remove-Item$","Join-Path$","Get-ChildItem$","ListenerPid$","PortOpen$","IsOurProxy$"
    ]
    if not ps.exists():return {"ok":False,"hits":[{"pattern":"missing ps1","count":1}]}
    t=ps.read_text("utf-8-sig",errors="replace")
    hits=[{"pattern":x,"count":t.count(x)} for x in suspicious if t.count(x)]
    return {"ok":not hits,"hits":hits}

def audit(root:Path,data:Path):
    man=check_manifest(root);jh=json_health(data);sq=sqlite_health(data);wt=write_test(data)
    ps=next(iter(sorted(root.glob("HMS_AI_ROUTER_v25.23.1.ps1"))),None)
    lint=static_lint(ps) if ps else {"ok":False,"hits":[{"pattern":"main ps1 missing","count":1}]}
    score=100
    if not man["ok"]:score-=35
    score-=min(25,jh["bad"]*5)
    if not sq["ok"]:score-=20
    if not wt["ok"]:score-=20
    if not lint["ok"]:score-=20
    score=max(0,score)
    grade="PASS" if score>=90 else ("WARN" if score>=70 else "FAIL")
    return {"score":score,"grade":grade,"manifest":man,"json":jh,"sqlite":sq,"write_test":wt,"static_lint":lint}

def archive_logs(logdir:Path,archive_dir:Path,min_age_days:int,keep_latest:int):
    archive_dir.mkdir(parents=True,exist_ok=True)
    files=[p for p in logdir.glob("*") if p.is_file() and p.suffix.lower() in (".log",".txt")]
    files.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    protect=set(files[:max(0,keep_latest)])
    cutoff=datetime.now().timestamp()-max(0,min_age_days)*86400
    eligible=[p for p in files if p not in protect and p.stat().st_mtime<cutoff]
    if not eligible:return {"archived":0,"zip":None,"files":[]}
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    zpath=archive_dir/f"logs-{stamp}.zip"
    names=[]
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
        for p in eligible:
            z.write(p,p.name);names.append(p.name)
    # Remove originals only after archive has been fully closed.
    with zipfile.ZipFile(zpath,"r") as z:
        if z.testzip() is not None:raise RuntimeError("archive integrity failed")
    for p in eligible:p.unlink()
    return {"archived":len(eligible),"zip":str(zpath),"files":names}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("audit","archive"),default="audit")
    ap.add_argument("--root",required=True);ap.add_argument("--data",required=True);ap.add_argument("--output")
    ap.add_argument("--log-dir");ap.add_argument("--archive-dir");ap.add_argument("--min-age-days",type=int,default=2);ap.add_argument("--keep-latest",type=int,default=3)
    a=ap.parse_args();root=Path(a.root);data=Path(a.data)
    try:
        if a.mode=="audit":result=audit(root,data)
        else:result=archive_logs(Path(a.log_dir),Path(a.archive_dir),a.min_age_days,a.keep_latest)
        out={"ok":True,"mode":a.mode,"data":result}
    except Exception as e:out={"ok":False,"error":repr(e)}
    s=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if out.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
