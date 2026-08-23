#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, secrets
from pathlib import Path
from datetime import datetime, timezone

MODES={"STRICT","STICKY_FAILOVER","DIRECT_FALLBACK"}
SCHEMES={"http","https","socks5"}

def now(): return datetime.now(timezone.utc).isoformat()

def loadj(path,default):
    p=Path(path)
    if not p.exists(): return default
    try:return json.loads(p.read_text("utf-8-sig"))
    except:return default

def atomic(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),"utf-8")
    os.replace(tmp,p)

def audit(path,event,**kw):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    row={"time":now(),"event":event,**kw}
    with p.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")

def normalize_profile(p):
    q=dict(p)
    q["id"]=str(q.get("id") or secrets.token_hex(6))
    q["name"]=str(q.get("name") or q["id"])
    q["scheme"]=str(q.get("scheme") or "http").lower()
    if q["scheme"] not in SCHEMES: raise ValueError("unsupported proxy scheme")
    q["host"]=str(q.get("host") or "").strip()
    q["port"]=int(q.get("port") or 0)
    if not q["host"] or not (1<=q["port"]<=65535): raise ValueError("invalid proxy host/port")
    q["username"]=str(q.get("username") or "")
    q["secret_ref"]=str(q.get("secret_ref") or "")
    q["mode"]=str(q.get("mode") or "STRICT").upper()
    if q["mode"] not in MODES: raise ValueError("invalid proxy mode")
    q["max_accounts"]=max(1,int(q.get("max_accounts") or 5))
    q["enabled"]=bool(q.get("enabled",True))
    q["country"]=str(q.get("country") or "VN")
    q["isp"]=str(q.get("isp") or "")
    q["notes"]=str(q.get("notes") or "")
    q["fallback_profile_ids"]=[str(x) for x in (q.get("fallback_profile_ids") or []) if str(x)]
    q["sidecar_port"]=int(q.get("sidecar_port") or 0)
    q["updated_utc"]=now()
    return q

def profile_store(path):
    d=loadj(path,{"version":22,"profiles":[]})
    d.setdefault("version",22);d.setdefault("profiles",[])
    return d

def binding_store(path):
    d=loadj(path,{"version":22,"bindings":[]})
    d.setdefault("version",22);d.setdefault("bindings",[])
    return d

def upsert_profile(path,audit_path,profile):
    d=profile_store(path);q=normalize_profile(profile)
    rows=d["profiles"];found=False
    for i,x in enumerate(rows):
        if str(x.get("id"))==q["id"]:
            created=x.get("created_utc") or now()
            q["created_utc"]=created;rows[i]=q;found=True;break
    if not found:
        q["created_utc"]=now();rows.append(q)
    atomic(path,d);audit(audit_path,"PROFILE_UPSERT",profile_id=q["id"],name=q["name"],mode=q["mode"])
    return q

def remove_profile(path,bindings_path,audit_path,profile_id):
    d=profile_store(path);before=len(d["profiles"])
    d["profiles"]=[x for x in d["profiles"] if str(x.get("id"))!=profile_id]
    if len(d["profiles"])==before:return False
    atomic(path,d)
    b=binding_store(bindings_path)
    for x in b["bindings"]:
        if x.get("proxy_profile_id")==profile_id:
            x["proxy_profile_id"]=None;x["status"]="UNASSIGNED";x["updated_utc"]=now()
    atomic(bindings_path,b)
    audit(audit_path,"PROFILE_REMOVED",profile_id=profile_id)
    return True

def normalize_accounts(accounts):
    out=[];seen=set()
    for x in accounts:
        if isinstance(x,str):
            email=x;filename=""
        else:
            email=str(x.get("email") or x.get("Email") or "").strip()
            filename=str(x.get("filename") or x.get("FileName") or x.get("file") or "").strip()
        key=email.lower()
        if not email or key in seen:continue
        seen.add(key);out.append({"email":email,"filename":filename})
    return out

def stable_assign(profiles,accounts,existing,max_per_default=5,preserve=True):
    enabled=[p for p in profiles if p.get("enabled",True)]
    byid={p["id"]:p for p in enabled}
    capacities={p["id"]:max(1,int(p.get("max_accounts") or max_per_default)) for p in enabled}
    used={k:0 for k in byid}
    result={}
    existing_map={str(x.get("email","")).lower():x for x in existing}
    account_map={a["email"].lower():a for a in accounts}

    # Preserve valid prior binding first.
    if preserve:
        for key,a in account_map.items():
            old=existing_map.get(key);pid=str(old.get("proxy_profile_id") or "") if old else ""
            if pid in byid and used[pid]<capacities[pid]:
                result[key]=pid;used[pid]+=1

    # Deterministic fill by profile id/name.
    order=sorted(enabled,key=lambda p:(int(p.get("sidecar_port") or 99999),p.get("name",""),p["id"]))
    for key,a in account_map.items():
        if key in result:continue
        candidate=None
        for p in order:
            if used[p["id"]]<capacities[p["id"]]:
                candidate=p;break
        if candidate:
            result[key]=candidate["id"];used[candidate["id"]]+=1
        else:
            result[key]=None

    rows=[]
    for a in accounts:
        pid=result[a["email"].lower()]
        rows.append({
            "email":a["email"],"filename":a["filename"],"proxy_profile_id":pid,
            "status":"ASSIGNED" if pid else "UNASSIGNED","updated_utc":now()
        })
    return rows,used

def assign(profiles_path,bindings_path,audit_path,accounts,max_per_default=5,preserve=True):
    p=profile_store(profiles_path)
    b=binding_store(bindings_path)
    accounts=normalize_accounts(accounts)
    rows,used=stable_assign(p["profiles"],accounts,b["bindings"],max_per_default,preserve)
    b["bindings"]=rows;b["updated_utc"]=now()
    atomic(bindings_path,b)
    audit(audit_path,"AUTO_ASSIGN",accounts=len(accounts),assigned=sum(1 for x in rows if x["proxy_profile_id"]),usage=used)
    return b

def health_map(path):
    h=loadj(path,{"version":22,"profiles":{}})
    h.setdefault("profiles",{})
    return h

def account_policy(email,profiles_path,bindings_path,health_path,direct_fallback_allowed=False):
    profiles={p["id"]:p for p in profile_store(profiles_path)["profiles"]}
    bindings=binding_store(bindings_path)["bindings"]
    health=health_map(health_path).get("profiles",{})
    b=next((x for x in bindings if str(x.get("email","")).lower()==email.lower()),None)
    if not b or not b.get("proxy_profile_id"):
        return {"email":email,"decision":"BLOCKED","reason":"NO_PROXY_BINDING","proxy_profile_id":None}
    pid=b["proxy_profile_id"];p=profiles.get(pid)
    if not p or not p.get("enabled",True):
        return {"email":email,"decision":"BLOCKED","reason":"PROFILE_DISABLED_OR_MISSING","proxy_profile_id":pid}
    ph=health.get(pid) or {}
    healthy=(str(ph.get("status") or "").upper()=="PASS")
    mode=str(p.get("mode") or "STRICT").upper()
    if healthy:
        return {"email":email,"decision":"PROXY","reason":"HEALTHY_STICKY","proxy_profile_id":pid}
    if mode=="STRICT":
        return {"email":email,"decision":"BLOCKED","reason":"STRICT_PROXY_UNHEALTHY","proxy_profile_id":pid}
    if mode=="STICKY_FAILOVER":
        for fid in p.get("fallback_profile_ids") or []:
            fp=profiles.get(fid);fh=health.get(fid) or {}
            if fp and fp.get("enabled",True) and str(fh.get("status") or "").upper()=="PASS":
                return {"email":email,"decision":"PROXY","reason":"STICKY_FAILOVER","proxy_profile_id":fid,"primary_profile_id":pid}
        return {"email":email,"decision":"BLOCKED","reason":"NO_HEALTHY_FALLBACK","proxy_profile_id":pid}
    if mode=="DIRECT_FALLBACK" and direct_fallback_allowed:
        return {"email":email,"decision":"DIRECT","reason":"EXPLICIT_DIRECT_FALLBACK","proxy_profile_id":pid}
    return {"email":email,"decision":"BLOCKED","reason":"DIRECT_FALLBACK_DISABLED","proxy_profile_id":pid}

def plan(profiles_path,bindings_path,health_path,base_port=8420,direct_fallback_allowed=False):
    profiles=profile_store(profiles_path)["profiles"]
    bindings=binding_store(bindings_path)["bindings"]
    health=health_map(health_path).get("profiles",{})
    groups=[]
    used_ports=set()
    for idx,p in enumerate(sorted([x for x in profiles if x.get("enabled",True)],key=lambda x:(x.get("name",""),x["id"]))):
        port=int(p.get("sidecar_port") or (base_port+idx))
        while port in used_ports:port+=1
        used_ports.add(port)
        members=[b for b in bindings if b.get("proxy_profile_id")==p["id"]]
        ph=health.get(p["id"]) or {}
        status=str(ph.get("status") or "UNKNOWN").upper()
        start_allowed=(status=="PASS") or (str(p.get("mode","STRICT")).upper()!="STRICT")
        if str(p.get("mode","STRICT")).upper()=="STRICT" and status!="PASS":
            start_allowed=False
        groups.append({
            "profile_id":p["id"],"profile_name":p["name"],"mode":p.get("mode","STRICT"),
            "scheme":p["scheme"],"host":p["host"],"port":p["port"],"username":p.get("username",""),
            "secret_ref":p.get("secret_ref",""),"sidecar_port":port,
            "accounts":members,"account_count":len(members),"capacity":int(p.get("max_accounts") or 5),
            "health_status":status,"start_allowed":start_allowed,
            "direct_fallback_allowed":bool(direct_fallback_allowed and p.get("mode")=="DIRECT_FALLBACK")
        })
    return {"version":22,"generated_utc":now(),"groups":groups}

def safe_export(profiles_path,bindings_path,health_path):
    p=profile_store(profiles_path)
    for x in p["profiles"]:
        x.pop("secret_ref",None)
    return {"version":22,"profiles":p["profiles"],"bindings":binding_store(bindings_path)["bindings"],
            "health":health_map(health_path).get("profiles",{}),"contains_proxy_passwords":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profiles",required=True);ap.add_argument("--bindings",required=True);ap.add_argument("--health",required=True);ap.add_argument("--audit",required=True)
    sp=ap.add_subparsers(dest="cmd",required=True)
    sp.add_parser("init")
    u=sp.add_parser("upsert-profile")
    for k in ("id","name","scheme","host","username","secret-ref","mode","country","isp","notes"):
        u.add_argument("--"+k)
    u.add_argument("--port",type=int);u.add_argument("--max-accounts",type=int,default=5);u.add_argument("--sidecar-port",type=int,default=0);u.add_argument("--disabled",action="store_true")
    rm=sp.add_parser("remove-profile");rm.add_argument("--id",required=True)
    a=sp.add_parser("assign");a.add_argument("--accounts-json",required=True);a.add_argument("--max-per-proxy",type=int,default=5);a.add_argument("--no-preserve",action="store_true")
    pl=sp.add_parser("plan");pl.add_argument("--base-port",type=int,default=8420);pl.add_argument("--direct-fallback-allowed",action="store_true")
    pol=sp.add_parser("policy");pol.add_argument("--email",required=True);pol.add_argument("--direct-fallback-allowed",action="store_true")
    sp.add_parser("safe-export")
    args=ap.parse_args()
    if args.cmd=="init":
        atomic(args.profiles,profile_store(args.profiles));atomic(args.bindings,binding_store(args.bindings));atomic(args.health,health_map(args.health))
        print(json.dumps({"ok":True}))
    elif args.cmd=="upsert-profile":
        q=upsert_profile(args.profiles,args.audit,{
            "id":args.id,"name":args.name,"scheme":args.scheme,"host":args.host,"port":args.port,
            "username":args.username,"secret_ref":args.secret_ref,"mode":args.mode,
            "country":args.country,"isp":args.isp,"notes":args.notes,"max_accounts":args.max_accounts,
            "sidecar_port":args.sidecar_port,"enabled":not args.disabled
        });print(json.dumps({"ok":True,"profile":q},ensure_ascii=False))
    elif args.cmd=="remove-profile":
        print(json.dumps({"ok":remove_profile(args.profiles,args.bindings,args.audit,args.id)}))
    elif args.cmd=="assign":
        accounts=json.loads(Path(args.accounts_json).read_text("utf-8-sig"))
        print(json.dumps({"ok":True,"data":assign(args.profiles,args.bindings,args.audit,accounts,args.max_per_proxy,not args.no_preserve)},ensure_ascii=False))
    elif args.cmd=="plan":
        print(json.dumps({"ok":True,"data":plan(args.profiles,args.bindings,args.health,args.base_port,args.direct_fallback_allowed)},ensure_ascii=False))
    elif args.cmd=="policy":
        print(json.dumps({"ok":True,"data":account_policy(args.email,args.profiles,args.bindings,args.health,args.direct_fallback_allowed)},ensure_ascii=False))
    elif args.cmd=="safe-export":
        print(json.dumps({"ok":True,"data":safe_export(args.profiles,args.bindings,args.health)},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
