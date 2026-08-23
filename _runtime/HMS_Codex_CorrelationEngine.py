#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

REQ_PATTERNS=[
    re.compile(r'(?i)(?:request[_ -]?id|req[_ -]?id|request-id)\s*[:=]\s*([A-Za-z0-9._:\-]+)'),
    re.compile(r'\b(req_[A-Za-z0-9_\-]{6,})\b')
]
RESP_PATTERNS=[re.compile(r'\b(resp_[A-Za-z0-9_\-]{6,})\b')]
LAT_RE=re.compile(r'(?i)(?:latency|duration|elapsed)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*ms\b')
STATUS_RE=re.compile(r'(?<!\d)([1-5]\d{2})(?!\d)')

def first(patterns,s):
    for p in patterns:
        m=p.search(s)
        if m:return m.group(1)
    return None

def correlate(events):
    rows=[]
    for idx,e in enumerate(events):
        msg=str(e.get("message") or "")
        req=first(REQ_PATTERNS,msg)
        resp=first(RESP_PATTERNS,msg)
        lm=LAT_RE.search(msg);sm=STATUS_RE.search(msg)
        rows.append({
            "seq":idx,"request_id":req,"response_id":resp,
            "account":e.get("account"),"confidence":e.get("confidence"),
            "kind":e.get("kind"),"status_code":int(sm.group(1)) if sm else None,
            "latency_ms":float(lm.group(1)) if lm else None,
            "source":e.get("source"),"message":msg
        })
    grouped={}
    singles=[]
    for r in rows:
        key=r["request_id"] or r["response_id"]
        if not key: singles.append(r);continue
        g=grouped.setdefault(key,{"correlation_id":key,"account":None,"confidence":"UNATTRIBUTED",
                                  "status_code":None,"latency_ms":None,"events":[]})
        g["events"].append(r)
        if r["account"]:
            g["account"]=r["account"]
            if r["confidence"]=="CONFIRMED" or g["confidence"]!="CONFIRMED":g["confidence"]=r["confidence"]
        if r["status_code"] is not None:g["status_code"]=r["status_code"]
        if r["latency_ms"] is not None:g["latency_ms"]=r["latency_ms"]
    result=list(grouped.values())
    return {"correlated":result[-300:],"uncorrelated":singles[-200:],
            "correlated_count":len(result),"uncorrelated_count":len(singles)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:
        d=json.loads(Path(a.input).read_text("utf-8"));o={"ok":True,"data":correlate(d.get("events",[]))}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
