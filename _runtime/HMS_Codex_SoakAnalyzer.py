#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from datetime import datetime,timezone,timedelta

def parse_dt(v):
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except:return None

def load_samples(path):
    p=Path(path)
    if not p.exists():return []
    rows=[]
    for line in p.read_text("utf-8",errors="replace").splitlines():
        try:
            j=json.loads(line)
            if j.get("time"):rows.append(j)
        except:pass
    rows.sort(key=lambda x:x.get("time",""))
    return rows

def longest_run(rows,pred):
    best=cur=0
    for r in rows:
        if pred(r):cur+=1;best=max(best,cur)
        else:cur=0
    return best

def slope_per_hour(rows,key):
    pts=[]
    for r in rows:
        t=parse_dt(r.get("time"))
        v=r.get(key)
        if t is not None and isinstance(v,(int,float)):pts.append((t,float(v)))
    if len(pts)<2:return None
    dt=(pts[-1][0]-pts[0][0]).total_seconds()/3600
    if dt<=0:return None
    return (pts[-1][1]-pts[0][1])/dt

def recent_events(rows,minutes,types):
    if not rows:return 0
    end=parse_dt(rows[-1].get("time")) or datetime.now(timezone.utc)
    cutoff=end-timedelta(minutes=minutes)
    window=[]
    for r in rows:
        t=parse_dt(r.get("time"))
        if t and t>=cutoff:window.append(r)
    if not window:return 0
    first=window[0].get("event_totals") or {}
    last=window[-1].get("event_totals") or {}
    n=0
    for k in types:
        n+=max(0,int(last.get(k,0) or 0)-int(first.get(k,0) or 0))
    return n

def analyze(samples,state,cfg):
    if not samples:
        return {"verdict":"BLOCKED","reason":"no samples","metrics":{},"findings":[{"severity":"BLOCKED","code":"NO_SAMPLES","message":"Chưa có mẫu soak."}]}
    start=parse_dt(state.get("startedUtc")) or parse_dt(samples[0]["time"])
    end=parse_dt(samples[-1]["time"]) or datetime.now(timezone.utc)
    elapsed=max(0,(end-start).total_seconds())
    target=int(state.get("targetSeconds") or 3600)
    expected=max(1,elapsed/max(1,int(cfg.get("sample_interval_sec",60))))
    coverage=len(samples)/expected
    router_off=longest_run(samples,lambda r:not bool(r.get("router_online")))
    ready_zero=longest_run(samples,lambda r:int(r.get("pool_ready") or 0)<=0 and int(r.get("pool_total") or 0)>0)
    ram_slope=slope_per_hour(samples,"total_ram_mb")
    state_slope=slope_per_hour(samples,"state_size_mb")
    recovery_count=recent_events(samples,int(cfg.get("recovery_loop_window_minutes",15)),("RECOVERY","FAILOVER","RETRY"))
    pools=[(r.get("pool_total"),r.get("pool_ready")) for r in samples]
    pool_changes=sum(1 for a,b in zip(pools,pools[1:]) if a!=b)
    sla=[int(r.get("sla_score") or 0) for r in samples if r.get("sla_score") is not None]
    findings=[]
    def add(sev,code,msg):findings.append({"severity":sev,"code":code,"message":msg})
    if router_off>=int(cfg.get("router_offline_critical_samples",3)):
        add("FAIL","ROUTER_OFFLINE_RUN",f"Router offline liên tiếp {router_off} mẫu.")
    if ready_zero>=int(cfg.get("pool_ready_zero_critical_samples",3)):
        add("FAIL","POOL_READY_ZERO_RUN",f"Pool Ready=0 liên tiếp {ready_zero} mẫu.")
    if recovery_count>=int(cfg.get("recovery_loop_critical_count",8)):
        add("FAIL","RECOVERY_LOOP",f"{recovery_count} recovery/failover/retry event trong cửa sổ gần.")
    if ram_slope is not None and ram_slope>float(cfg.get("ram_growth_warn_mb_per_hour",250)):
        add("WARN","RAM_GROWTH",f"RAM tăng xấp xỉ {ram_slope:.1f} MB/giờ.")
    if state_slope is not None and state_slope>float(cfg.get("state_growth_warn_mb_per_hour",50)):
        add("WARN","STATE_GROWTH",f"State/log tăng xấp xỉ {state_slope:.1f} MB/giờ.")
    if coverage<0.70 and elapsed>=1800:
        add("WARN","LOW_SAMPLE_COVERAGE",f"Sample coverage chỉ {coverage*100:.1f}%.")
    if sla and min(sla)<50:add("WARN","LOW_SLA",f"Fleet SLA thấp nhất {min(sla)}.")
    complete=elapsed>=target
    has_fail=any(x["severity"]=="FAIL" for x in findings)
    has_warn=any(x["severity"]=="WARN" for x in findings)
    if not complete:verdict="IN_PROGRESS"
    elif has_fail:verdict="FAIL"
    elif has_warn:verdict="WARN"
    else:verdict="PASS"
    return {
        "verdict":verdict,"complete":complete,"elapsedSeconds":round(elapsed,1),"targetSeconds":target,
        "progressPct":round(min(100,elapsed/max(1,target)*100),2),
        "metrics":{
            "samples":len(samples),"coverage":round(coverage,3),"routerOfflineLongestRun":router_off,
            "poolReadyZeroLongestRun":ready_zero,"recoveryEventsRecent":recovery_count,
            "ramGrowthMbPerHour":None if ram_slope is None else round(ram_slope,2),
            "stateGrowthMbPerHour":None if state_slope is None else round(state_slope,2),
            "poolStateChanges":pool_changes,"slaMin":min(sla) if sla else None,
            "slaMedian":statistics.median(sla) if sla else None
        },"findings":findings
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--samples",required=True);ap.add_argument("--state",required=True);ap.add_argument("--config",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:
        state=json.loads(Path(a.state).read_text("utf-8-sig"))
        cfg=json.loads(Path(a.config).read_text("utf-8-sig"))
        o={"ok":True,"data":analyze(load_samples(a.samples),state,cfg)}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
