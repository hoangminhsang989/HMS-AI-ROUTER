#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone

EMAIL_RE=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""):h.update(c)
    return h.hexdigest()

def deep(o,keys):
    if isinstance(o,dict):
        for k in keys:
            if k in o and o[k] not in (None,""):return o[k]
        for v in o.values():
            r=deep(v,keys)
            if r not in (None,""):return r
    if isinstance(o,list):
        for v in o:
            r=deep(v,keys)
            if r not in (None,""):return r
    return None

def parse_dt(v):
    if v in (None,""):return None
    try:
        if isinstance(v,(int,float)):
            # seconds or milliseconds
            x=float(v);x=x/1000 if x>10_000_000_000 else x
            return datetime.fromtimestamp(x,timezone.utc)
        s=str(v).strip()
        if s.isdigit():
            x=float(s);x=x/1000 if x>10_000_000_000 else x
            return datetime.fromtimestamp(x,timezone.utc)
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except:return None

def auth_info(p:Path):
    row={"path":str(p),"name":p.name,"exists":p.exists()}
    if not p.exists():return row
    row["mtime_utc"]=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()
    row["sha256"]=sha256(p)
    try:
        raw=p.read_text("utf-8-sig",errors="replace");j=json.loads(raw)
        row["json_ok"]=True
    except Exception as e:
        row["json_ok"]=False;row["error"]=str(e)[:180];return row
    email=deep(j,("email","account_email","user_email"))
    if not email:
        m=EMAIL_RE.search(raw);email=m.group(0) if m else None
    row["email"]=str(email) if email else None
    aid=deep(j,("account_id","accountId","chatgpt_account_id","user_id","userId"))
    row["account_id"]=str(aid) if aid else None
    exp=deep(j,("expires_at","expiresAt","expiry","expiration","expire_at"))
    expdt=parse_dt(exp);row["expiry_utc"]=expdt.isoformat() if expdt else None
    # Find cooldown-like metadata without exposing token contents.
    cd=deep(j,("cooldown_until","cooldownUntil","unavailable_until","unavailableUntil"))
    cdt=parse_dt(cd);row["cooldown_until_utc"]=cdt.isoformat() if cdt else None
    row["identity_key"]=(row["account_id"] or row["email"] or p.stem).lower()
    return row

def shared_inventory(auth_dir:Path):
    rows=[auth_info(p) for p in sorted(auth_dir.glob("codex-*.json"))] if auth_dir.exists() else []
    return rows

def load_previous(path):
    if not path or not Path(path).exists():return None
    try:return json.loads(Path(path).read_text("utf-8-sig"))
    except:return None

def by_email(rows):
    d={}
    for r in rows:
        if r.get("email"):d[r["email"].lower()]=r
    return d

def compare_instance(inst,shared_by_email,skew=2):
    router=Path(str(inst.get("routerDir") or inst.get("router_dir") or ""))
    authdir=router/"auth"
    files=[p for p in authdir.glob("codex-*.json")] if authdir.exists() else []
    infos=[auth_info(p) for p in sorted(files)]
    bound=str(inst.get("accountEmail") or inst.get("account") or "")
    src=shared_by_email.get(bound.lower()) if bound else None
    out={"id":inst.get("id"),"name":inst.get("name"),"bound_account":bound,
         "router_dir":str(router),"auth_dir":str(authdir),"child_files":infos,
         "client_pid":inst.get("clientPid") or 0,"router_pid":inst.get("routerPid") or 0,
         "status":"OK","recommendation":"NONE","reason":"consistent"}
    if not src:
        out.update(status="MISSING_SHARED_ACCOUNT",recommendation="REVIEW",reason="bound account is absent from shared pool");return out
    out["shared"]=src
    if len(infos)==0:
        out.update(status="CHILD_AUTH_MISSING",recommendation="COPY_FROM_SHARED",reason="child auth is missing");return out
    if len(infos)>1:
        out.update(status="MULTIPLE_CHILD_AUTH",recommendation="REVIEW",reason="child router has multiple active codex auth files");return out
    child=infos[0];out["child"]=child
    if not child.get("json_ok",False):
        out.update(status="CHILD_JSON_INVALID",recommendation="SYNC_FROM_SHARED",reason="child auth JSON invalid");return out
    if child.get("email") and child.get("email","").lower()!=bound.lower():
        out.update(status="IDENTITY_MISMATCH",recommendation="SYNC_FROM_SHARED",reason="child identity differs from instance binding");return out
    if child.get("sha256")==src.get("sha256"):
        out.update(status="OK",recommendation="NONE",reason="exact credential copy");return out
    sm=parse_dt(src.get("mtime_utc"));cm=parse_dt(child.get("mtime_utc"))
    se=parse_dt(src.get("expiry_utc"));ce=parse_dt(child.get("expiry_utc"))
    # Prefer clearly newer expiry over mtime when available.
    if se and ce and se>ce:
        out.update(status="DRIFT_SHARED_NEWER",recommendation="SYNC_FROM_SHARED",reason="shared credential expiry is newer");return out
    if se and ce and ce>se:
        out.update(status="CONFLICT_CHILD_NEWER",recommendation="REVIEW",reason="child credential expiry is newer than shared");return out
    if sm and cm:
        delta=(sm-cm).total_seconds()
        if delta>skew:
            out.update(status="DRIFT_SHARED_NEWER",recommendation="SYNC_FROM_SHARED",reason="shared auth modified later");return out
        if delta<-skew:
            out.update(status="CONFLICT_CHILD_NEWER",recommendation="REVIEW",reason="child auth modified later");return out
    out.update(status="DRIFT_AMBIGUOUS",recommendation="REVIEW",reason="credential content differs but freshness is ambiguous")
    return out

def build(data):
    shared=shared_inventory(Path(data["shared_auth_dir"]))
    smap=by_email(shared)
    prev=load_previous(data.get("previous_snapshot"))
    prev_emails=set()
    if isinstance(prev,dict):
        prev_emails={str(x.get("email")).lower() for x in prev.get("shared_accounts",[]) if x.get("email")}
    cur_emails={str(x.get("email")).lower() for x in shared if x.get("email")}
    changes={"new_accounts":sorted(cur_emails-prev_emails) if prev is not None else [],
             "removed_accounts":sorted(prev_emails-cur_emails) if prev is not None else []}
    inst=[compare_instance(i,smap,int(data.get("clock_skew_seconds",2))) for i in data.get("instances",[])]
    problems=[x for x in inst if x["status"]!="OK"]
    now=datetime.now(timezone.utc)
    cooldowns=[]
    for r in shared:
        c=parse_dt(r.get("cooldown_until_utc"))
        if c:
            cooldowns.append({"email":r.get("email"),"until_utc":c.isoformat(),
                              "state":"ACTIVE" if c>now else "EXPIRED_METADATA"})
    return {"shared_accounts":shared,"changes":changes,"instances":inst,"problems":problems,
            "cooldowns":cooldowns,
            "summary":{"shared_accounts":len(shared),"instances":len(inst),"problems":len(problems),
                       "new_accounts":len(changes["new_accounts"]),"removed_accounts":len(changes["removed_accounts"])}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:o={"ok":True,"data":build(json.loads(Path(a.input).read_text("utf-8")))}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
