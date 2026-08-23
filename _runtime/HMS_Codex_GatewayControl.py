#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
from HMS_Codex_SmartGateway import KeyStore,loadj

STRATEGIES=["stable-round-robin","random","single","auto","quota-first","plan-first","expiry-soon","weighted","reset-aware","fill-first"]

def atomic(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2),"utf-8");os.replace(t,p)

def default_config():
    return {
        "version":24,"host":"127.0.0.1","port":8320,"strategy":"stable-round-robin",
        "session_affinity":True,"session_ttl_sec":3600,"health_fail_threshold":3,
        "health_cooldown_sec":120,"upstream_timeout_sec":300,"require_client_key":True,
        "max_failover_attempts":3,"retry_statuses":[429,500,502,503,504],
        "require_idempotency_for_post_replay":True,"stream_chunk_bytes":65536,
        "websocket_enabled":True,"websocket_idle_timeout_sec":300,"websocket_require_model_hint":True,
        "expose_selected_target_headers":True,
        "cors_enabled":True,
        "cors_allowed_origins":["http://localhost:*","http://127.0.0.1:*","https://localhost:*","https://127.0.0.1:*"],
        "quota_evidence_max_age_sec":900,"quota_reserve_fail_closed":True,"default_quota_reserve_pct":0,
        "usage_capture_max_bytes":2097152,"model_prices":{},"targets":[]
    }

def find_key(db,key_id):
    for x in db.data.get("keys",[]):
        if str(x.get("id"))==str(key_id):return x
    raise SystemExit("client key id not found")

def parse_map(items,cast=int):
    out={}
    for item in items or []:
        if "=" not in item:raise SystemExit(f"expected TARGET=VALUE: {item}")
        k,v=item.split("=",1);out[k]=cast(v)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",required=True);ap.add_argument("--keys",required=True)
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init")

    ck=sub.add_parser("create-key")
    ck.add_argument("--name",required=True);ck.add_argument("--allow",action="append");ck.add_argument("--deny",action="append")
    ck.add_argument("--target-allow",action="append");ck.add_argument("--target-deny",action="append")
    ck.add_argument("--strategy",choices=STRATEGIES);ck.add_argument("--single-target")
    ck.add_argument("--model-prefix",default="");ck.add_argument("--quota-reserve-pct",type=float,default=0)
    ck.add_argument("--priority",action="append",help="target=value");ck.add_argument("--weight",action="append",help="target=value")
    ck.add_argument("--backup-target",action="append")

    uk=sub.add_parser("update-key-policy")
    uk.add_argument("--id",required=True);uk.add_argument("--strategy",choices=STRATEGIES)
    uk.add_argument("--single-target");uk.add_argument("--model-prefix")
    uk.add_argument("--quota-reserve-pct",type=float)
    uk.add_argument("--target-allow",action="append");uk.add_argument("--target-deny",action="append")
    uk.add_argument("--priority",action="append");uk.add_argument("--weight",action="append");uk.add_argument("--backup-target",action="append")
    uk.add_argument("--clear-target-policy",action="store_true")

    lt=sub.add_parser("add-target")
    lt.add_argument("--id",required=True);lt.add_argument("--account",required=True);lt.add_argument("--base-url",required=True)
    lt.add_argument("--api-key-env",default="");lt.add_argument("--priority",type=int,default=0);lt.add_argument("--weight",type=int,default=1)
    lt.add_argument("--allow",action="append");lt.add_argument("--deny",action="append");lt.add_argument("--reset-utc")
    lt.add_argument("--expiry-utc");lt.add_argument("--plan-rank",type=int,default=0);lt.add_argument("--backup",action="store_true")
    lt.add_argument("--quota-hourly-pct",type=float);lt.add_argument("--quota-weekly-pct",type=float);lt.add_argument("--quota-checked-utc")

    ut=sub.add_parser("update-target-metadata")
    ut.add_argument("--id",required=True);ut.add_argument("--quota-hourly-pct",type=float);ut.add_argument("--quota-weekly-pct",type=float)
    ut.add_argument("--quota-checked-utc");ut.add_argument("--expiry-utc");ut.add_argument("--plan-rank",type=int);ut.add_argument("--backup",choices=["true","false"])

    st=sub.add_parser("set-strategy");st.add_argument("strategy",choices=STRATEGIES)

    pr=sub.add_parser("set-price")
    pr.add_argument("--model",required=True);pr.add_argument("--input",type=float,required=True);pr.add_argument("--output",type=float,required=True)
    pr.add_argument("--cached-input",type=float)

    sub.add_parser("show")

    a=ap.parse_args();cfg=loadj(a.config,default_config());db=KeyStore(a.keys)

    if a.cmd=="init":
        for k,v in default_config().items():cfg.setdefault(k,v)
        atomic(a.config,cfg);db.save()
        print(json.dumps({"ok":True,"config":a.config,"keys":a.keys}))
    elif a.cmd=="create-key":
        rec,key=db.create(
            a.name,a.allow,a.deny,a.target_allow,a.target_deny,a.strategy,a.model_prefix,a.single_target,
            a.quota_reserve_pct,parse_map(a.priority,int),parse_map(a.weight,int)
        )
        rec["backup_targets"]=a.backup_target or []
        db.save()
        print(json.dumps({"ok":True,"id":rec["id"],"name":rec["name"],"client_key":key,
                          "warning":"Displayed once; store securely."}))
    elif a.cmd=="update-key-policy":
        rec=find_key(db,a.id)
        if a.clear_target_policy:
            rec["target_allow"]=["*"];rec["target_deny"]=[];rec["target_priority"]={};rec["target_weight"]={};rec["backup_targets"]=[]
        if a.strategy is not None:rec["routing_strategy"]=a.strategy
        if a.single_target is not None:rec["single_target"]=a.single_target or None
        if a.model_prefix is not None:rec["model_prefix"]=a.model_prefix
        if a.quota_reserve_pct is not None:rec["quota_reserve_pct"]=a.quota_reserve_pct
        if a.target_allow is not None:rec["target_allow"]=a.target_allow
        if a.target_deny is not None:rec["target_deny"]=a.target_deny
        if a.priority is not None:rec["target_priority"]=parse_map(a.priority,int)
        if a.weight is not None:rec["target_weight"]=parse_map(a.weight,int)
        if a.backup_target is not None:rec["backup_targets"]=a.backup_target
        rec["updated_utc"]=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        db.save();print(json.dumps({"ok":True,"policy":{k:v for k,v in rec.items() if k!="digest"}},ensure_ascii=False))
    elif a.cmd=="add-target":
        cfg.setdefault("targets",[])
        if any(x.get("id")==a.id for x in cfg["targets"]):raise SystemExit("duplicate target id")
        cfg["targets"].append({
            "id":a.id,"account":a.account,"base_url":a.base_url,"api_key_env":a.api_key_env,
            "priority":a.priority,"weight":max(1,a.weight),"enabled":True,
            "model_allow":a.allow or ["*"],"model_deny":a.deny or [],
            "reset_utc":a.reset_utc,"expiry_utc":a.expiry_utc,"plan_rank":a.plan_rank,"backup":bool(a.backup),
            "quota_hourly_pct":a.quota_hourly_pct,"quota_weekly_pct":a.quota_weekly_pct,"quota_checked_utc":a.quota_checked_utc
        })
        atomic(a.config,cfg);print(json.dumps({"ok":True,"target_id":a.id}))
    elif a.cmd=="update-target-metadata":
        target=next((x for x in cfg.get("targets",[]) if str(x.get("id"))==a.id),None)
        if target is None:raise SystemExit("target not found")
        for attr,key in [("quota_hourly_pct","quota_hourly_pct"),("quota_weekly_pct","quota_weekly_pct"),
                         ("quota_checked_utc","quota_checked_utc"),("expiry_utc","expiry_utc"),("plan_rank","plan_rank")]:
            val=getattr(a,attr)
            if val is not None:target[key]=val
        if a.backup is not None:target["backup"]=(a.backup=="true")
        atomic(a.config,cfg);print(json.dumps({"ok":True,"target":target},ensure_ascii=False))
    elif a.cmd=="set-strategy":
        cfg["strategy"]=a.strategy;atomic(a.config,cfg);print(json.dumps({"ok":True,"strategy":a.strategy}))
    elif a.cmd=="set-price":
        cfg.setdefault("model_prices",{})[a.model]={
            "input_per_million":a.input,"output_per_million":a.output,
            "cached_input_per_million":a.cached_input if a.cached_input is not None else a.input
        }
        atomic(a.config,cfg);print(json.dumps({"ok":True,"model":a.model,"price":cfg["model_prices"][a.model]}))
    elif a.cmd=="show":
        safe=dict(cfg);safe["targets"]=[{k:v for k,v in x.items() if k!="api_key"} for x in cfg.get("targets",[])]
        print(json.dumps({"config":safe,"client_keys":[{k:v for k,v in x.items() if k!="digest"} for x in db.data.get("keys",[])]},
                         ensure_ascii=False,indent=2))

if __name__=="__main__":main()
