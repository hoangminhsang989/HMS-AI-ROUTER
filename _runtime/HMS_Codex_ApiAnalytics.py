#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,statistics,time
from pathlib import Path
from datetime import datetime,timezone,timedelta

def parse_ts(v):
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except:return None

def load_rows(path,max_lines=100000):
    p=Path(path)
    if not p.exists():return []
    lines=p.read_text("utf-8",errors="replace").splitlines()
    rows=[]
    for line in lines[-max(1,int(max_lines)):]:
        try:r=json.loads(line)
        except:continue
        if isinstance(r,dict):rows.append(r)
    return rows

def pct(vals,p):
    vals=sorted(float(x) for x in vals if x is not None)
    if not vals:return None
    if len(vals)==1:return vals[0]
    k=(len(vals)-1)*(p/100);lo=math.floor(k);hi=math.ceil(k)
    if lo==hi:return vals[int(k)]
    return vals[lo]*(hi-k)+vals[hi]*(k-lo)

def request_type(path,protocol):
    p=str(path or "")
    if "images" in p:return "image"
    if "chat/completions" in p:return "chat"
    if "responses" in p:return "responses"
    if protocol=="websocket":return "websocket"
    if p.endswith("/models"):return "models"
    return "other"

def result_class(r):
    status=int(r.get("status") or 0)
    err=str(r.get("error_class") or "")
    if "cancel" in err.lower():return "canceled"
    if r.get("streaming") and err:return "stream_incomplete"
    if 200<=status<400:return "success"
    return "failed"

def group_stats(rows,keyfn):
    groups={}
    for r in rows:
        key=str(keyfn(r) or "UNKNOWN")
        g=groups.setdefault(key,{"requests":0,"success":0,"failed":0,"canceled":0,"stream_incomplete":0,
                                 "input_tokens":0,"output_tokens":0,"cached_input_tokens":0,"total_tokens":0,
                                 "token_samples":0,"estimated_usd":0.0,"cost_samples":0,"latencies":[],"ttfts":[]})
        g["requests"]+=1;g[result_class(r)]+=1
        has_tokens=False
        for field in ("input_tokens","output_tokens","cached_input_tokens","total_tokens"):
            v=r.get(field)
            if v is not None:
                try:g[field]+=int(v);has_tokens=True
                except:pass
        if has_tokens:g["token_samples"]+=1
        if r.get("estimated_usd") is not None:
            try:g["estimated_usd"]+=float(r["estimated_usd"]);g["cost_samples"]+=1
            except:pass
        try:
            if r.get("latency_ms") is not None:g["latencies"].append(float(r["latency_ms"]))
        except:pass
        try:
            if r.get("ttft_ms") is not None:g["ttfts"].append(float(r["ttft_ms"]))
        except:pass
    out={}
    for key,g in groups.items():
        req=g["requests"]
        out[key]={
            "requests":req,"success":g["success"],"failed":g["failed"],"canceled":g["canceled"],
            "stream_incomplete":g["stream_incomplete"],
            "success_rate_pct":round(g["success"]*100/req,2) if req else None,
            "input_tokens":g["input_tokens"],"output_tokens":g["output_tokens"],
            "cached_input_tokens":g["cached_input_tokens"],"total_tokens":g["total_tokens"],
            "token_coverage_pct":round(g["token_samples"]*100/req,2) if req else 0,
            "estimated_usd":round(g["estimated_usd"],8) if g["cost_samples"] else None,
            "cost_coverage_pct":round(g["cost_samples"]*100/req,2) if req else 0,
            "latency_ms":{"p50":pct(g["latencies"],50),"p95":pct(g["latencies"],95),"p99":pct(g["latencies"],99)},
            "ttft_ms":{"p50":pct(g["ttfts"],50),"p95":pct(g["ttfts"],95),"p99":pct(g["ttfts"],99)}
        }
    return out

def analyze(path,max_lines=100000,nowdt=None):
    rows=load_rows(path,max_lines)
    nowdt=nowdt or datetime.now(timezone.utc)
    parsed=[]
    for r in rows:
        ts=parse_ts(r.get("time"))
        if ts:r=dict(r);r["_ts"]=ts;parsed.append(r)
    windows={
        "day":nowdt-timedelta(days=1),
        "week":nowdt-timedelta(days=7),
        "month":nowdt-timedelta(days=30),
        "all":None
    }
    out={"version":"24.0","generated_utc":nowdt.isoformat(),"source_rows":len(rows),"timestamped_rows":len(parsed),"windows":{}}
    for name,cut in windows.items():
        rs=[r for r in parsed if cut is None or r["_ts"]>=cut]
        out["windows"][name]={
            "total":group_stats(rs,lambda r:"ALL").get("ALL",{}),
            "by_account":group_stats(rs,lambda r:r.get("account")),
            "by_model":group_stats(rs,lambda r:r.get("exposed_model") or r.get("model")),
            "by_client_key":group_stats(rs,lambda r:r.get("client_key_name") or r.get("client_key_id")),
            "by_request_type":group_stats(rs,lambda r:request_type(r.get("path"),r.get("protocol")))
        }
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--trace",required=True);ap.add_argument("--max-lines",type=int,default=100000);ap.add_argument("--output")
    a=ap.parse_args();data=analyze(a.trace,a.max_lines)
    txt=json.dumps({"ok":True,"data":data},ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt)

if __name__=="__main__":main()
