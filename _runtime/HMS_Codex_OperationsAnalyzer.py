#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, hashlib
from pathlib import Path
from datetime import datetime, timezone

EMAIL_RE=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
TOKEN_RE=re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}")
JWT_RE=re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}")
KEYVAL_RE=re.compile(r'(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|authorization)\s*[:=]\s*["\']?([^"\'\s,}]+)')

def redact(s:str)->str:
    s=TOKEN_RE.sub(r"\1[REDACTED]",s)
    s=JWT_RE.sub("[JWT_REDACTED]",s)
    s=KEYVAL_RE.sub(lambda m:m.group(1)+"=[REDACTED]",s)
    return s

def classify(line:str):
    l=line.lower()
    if "429" in l or "quota" in l or "cooldown" in l:return "COOLDOWN"
    if "failover" in l:return "FAILOVER"
    if "retry" in l:return "RETRY"
    if "error" in l or "fail" in l:return "ERROR"
    if "response" in l or "request" in l:return "REQUEST"
    if "auth" in l or "credential" in l:return "AUTH"
    return "INFO"

def analyze(logs:list[Path],accounts:list[str],max_lines:int):
    lines=[]
    for p in logs:
        if not p.exists():continue
        try:
            raw=p.read_text("utf-8",errors="replace").splitlines()[-max_lines:]
            lines.extend([(p.name,x) for x in raw])
        except Exception:pass
    events=[]
    latest_account=None
    latest_account_line=-999999
    for idx,(src,line) in enumerate(lines):
        found=None
        for a in accounts:
            if a and a.lower() in line.lower():found=a;break
        if not found:
            m=EMAIL_RE.search(line)
            if m and any(m.group(0).lower()==a.lower() for a in accounts):found=m.group(0)
        if found:
            latest_account=found;latest_account_line=idx
        kind=classify(line)
        if kind!="INFO" or found:
            if found:
                confidence="CONFIRMED"
                account=found
            elif latest_account and idx-latest_account_line<=12 and kind in ("REQUEST","RETRY","FAILOVER","ERROR","COOLDOWN"):
                confidence="PROBABLE";account=latest_account
            else:
                confidence="UNATTRIBUTED";account=None
            events.append({"source":src,"kind":kind,"account":account,"confidence":confidence,"message":redact(line)[:600]})
    # last request-ish account
    attr=None
    for e in reversed(events):
        if e["kind"] in ("REQUEST","AUTH","RETRY","FAILOVER") and e["account"]:
            attr={"account":e["account"],"confidence":e["confidence"],"evidence":e["message"],"source":e["source"]};break
    counts={}
    account_counts={a:{"attributed_events":0,"request_signals":0,"route_signals":0,"failover":0,"retry":0,"cooldown":0,"errors":0,"confirmed":0,"probable":0} for a in accounts}
    account_lookup={a.lower():a for a in accounts if a}
    for e in events:
        counts[e["kind"]]=counts.get(e["kind"],0)+1
        account=e.get("account")
        if not account:continue
        canonical=account_lookup.get(account.lower(),account)
        bucket=account_counts.setdefault(canonical,{"attributed_events":0,"request_signals":0,"route_signals":0,"failover":0,"retry":0,"cooldown":0,"errors":0,"confirmed":0,"probable":0})
        bucket["attributed_events"]+=1
        if e["kind"]=="REQUEST":bucket["request_signals"]+=1
        if e["kind"] in ("REQUEST","AUTH","RETRY","FAILOVER"):bucket["route_signals"]+=1
        if e["kind"]=="FAILOVER":bucket["failover"]+=1
        if e["kind"]=="RETRY":bucket["retry"]+=1
        if e["kind"]=="COOLDOWN":bucket["cooldown"]+=1
        if e["kind"]=="ERROR":bucket["errors"]+=1
        if e.get("confidence")=="CONFIRMED":bucket["confirmed"]+=1
        elif e.get("confidence")=="PROBABLE":bucket["probable"]+=1
    return {"events":events[-500:],"latest_attribution":attr,"counts":counts,"account_counts":account_counts,"scanned_lines":len(lines),"scanned_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--logs",action="append",default=[]);ap.add_argument("--accounts");ap.add_argument("--max-lines",type=int,default=2500);ap.add_argument("--output")
    a=ap.parse_args()
    accounts=json.loads(Path(a.accounts).read_text("utf-8")) if a.accounts else []
    try:o={"ok":True,"data":analyze([Path(x) for x in a.logs],accounts,a.max_lines)}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
