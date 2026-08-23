#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,statistics,html,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta

def pdt(v):
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except:return None

def jlines(path,limit=None):
    p=Path(path)
    if not p.exists():return []
    lines=p.read_text("utf-8",errors="replace").splitlines()
    if limit:lines=lines[-limit:]
    out=[]
    for line in lines:
        try:out.append(json.loads(line))
        except:pass
    return out

def percentile(vals,q):
    a=sorted(float(x) for x in vals if isinstance(x,(int,float)))
    if not a:return None
    if len(a)==1:return a[0]
    pos=(len(a)-1)*q
    lo=math.floor(pos);hi=math.ceil(pos)
    if lo==hi:return a[lo]
    return a[lo]*(hi-pos)+a[hi]*(pos-lo)

def stats(vals):
    a=[float(x) for x in vals if isinstance(x,(int,float))]
    if not a:return {"count":0,"min":None,"max":None,"avg":None,"p50":None,"p95":None,"p99":None}
    return {"count":len(a),"min":min(a),"max":max(a),"avg":sum(a)/len(a),
            "p50":percentile(a,.50),"p95":percentile(a,.95),"p99":percentile(a,.99)}

def slope_hour(rows,key):
    pts=[]
    for r in rows:
        t=pdt(r.get("time"));v=r.get(key)
        if t and isinstance(v,(int,float)):pts.append((t,float(v)))
    if len(pts)<2:return None
    hrs=(pts[-1][0]-pts[0][0]).total_seconds()/3600
    return None if hrs<=0 else (pts[-1][1]-pts[0][1])/hrs

def filter_window(rows,hours):
    if not rows:return []
    end=max((pdt(r.get("time")) for r in rows if pdt(r.get("time"))),default=datetime.now(timezone.utc))
    cut=end-timedelta(hours=hours)
    return [r for r in rows if (pdt(r.get("time")) or end)>=cut]

def ha_events(db_path,hours):
    p=Path(db_path) if db_path else None
    if not p or not p.exists():return []
    try:
        since=datetime.now(timezone.utc).timestamp()-hours*3600
        c=sqlite3.connect(f"file:{p.as_posix()}?mode=ro",uri=True,timeout=2)
        rows=c.execute("select observed_at,account,kind,confidence,request_id,status_code,latency_ms,message from events where observed_at>=? order by observed_at",(since,)).fetchall()
        c.close()
        out=[]
        for ts,a,k,conf,rid,status,lat,msg in rows:
            out.append({"time":datetime.fromtimestamp(ts,timezone.utc).isoformat(),"account":a,"type":k,
                        "confidence":conf,"request_id":rid,"status_code":status,"latency_ms":lat,"message":msg})
        return out
    except Exception:return []

def extract_latency(events):
    vals=[];byacct={}
    for e in events:
        v=e.get("latency_ms") or e.get("latencyMs") or e.get("latency")
        try:v=float(v)
        except:continue
        vals.append(v)
        a=e.get("account") or e.get("email")
        if a:byacct.setdefault(a,[]).append(v)
    return vals,byacct

def robust_anomalies(series,label,z=4.0):
    pts=[(pdt(r.get("time")),r.get("value")) for r in series if isinstance(r.get("value"),(int,float)) and pdt(r.get("time"))]
    vals=[float(v) for _,v in pts]
    if len(vals)<8:return []
    med=statistics.median(vals)
    dev=[abs(v-med) for v in vals];mad=statistics.median(dev)
    if mad<=0:return []
    scale=1.4826*mad
    out=[]
    for (t,v) in pts:
        score=abs(float(v)-med)/scale
        if score>=z:out.append({"time":t.isoformat(),"metric":label,"value":v,"robust_z":round(score,2)})
    return out[-50:]

def quota_accounts(rows):
    acc={}
    for r in rows:
        # history formats varied across versions: accept rows/account maps.
        if isinstance(r,dict) and "accounts" in r and isinstance(r["accounts"],list):
            seq=r["accounts"]
            ts=r.get("time") or r.get("capturedUtc") or r.get("generatedUtc")
        elif isinstance(r,dict) and r.get("email"):
            seq=[r];ts=r.get("time")
        else:continue
        for x in seq:
            e=x.get("email") or x.get("account")
            if not e:continue
            h=x.get("hourlyRemaining") if x.get("hourlyRemaining") is not None else x.get("hourly")
            w=x.get("weeklyRemaining") if x.get("weeklyRemaining") is not None else x.get("weekly")
            acc.setdefault(e,[]).append({"time":ts,"hourly":h,"weekly":w})
    return acc

def downsample(rows,maxpts):
    if len(rows)<=maxpts:return rows
    step=len(rows)/maxpts
    return [rows[min(len(rows)-1,int(i*step))] for i in range(maxpts)]

def analyze(inp):
    hours=int(inp.get("window_hours",24));maxpts=int(inp.get("max_points",720));z=float(inp.get("anomaly_z",4.0))
    soak=filter_window(jlines(inp.get("soak_samples","")),hours)
    ops=filter_window(jlines(inp.get("ops_events",""),10000),hours)
    ops+=ha_events(inp.get("ha_db",""),hours)
    ops=sorted(ops,key=lambda x:str(x.get("time") or ""))
    quota=filter_window(jlines(inp.get("quota_history",""),10000),hours)
    ram=[{"time":r.get("time"),"value":r.get("total_ram_mb")} for r in soak]
    sla=[{"time":r.get("time"),"value":r.get("sla_score")} for r in soak]
    state=[{"time":r.get("time"),"value":r.get("state_size_mb")} for r in soak]
    lat,latacct=extract_latency(ops)
    event_counts={"ERROR":0,"FAILOVER":0,"COOLDOWN":0,"RECOVERY":0,"RETRY":0}
    timeline=[]
    for e in ops:
        typ=str(e.get("type") or e.get("event") or "").upper()
        for k in event_counts:
            if k in typ:event_counts[k]+=1
        if any(k in typ for k in ("ERROR","FAILOVER","COOLDOWN","RECOVERY","RETRY")):
            timeline.append({"time":e.get("time"),"type":typ,"account":e.get("account") or e.get("email"),"message":e.get("message")})
    anomalies=[]
    anomalies+=robust_anomalies(ram,"RAM_MB",z)
    anomalies+=robust_anomalies([x for x in sla if x.get("value") is not None],"SLA",z)
    anomalies+=robust_anomalies(state,"STATE_MB",z)
    lstat=stats(lat)
    findings=[]
    p95warn=float(inp.get("latency_p95_warn_ms",5000))
    if lstat["p95"] is not None and lstat["p95"]>p95warn:
        findings.append({"severity":"WARN","code":"LATENCY_P95_HIGH","message":f"Latency P95 {lstat['p95']:.1f} ms > {p95warn:.0f} ms"})
    rg=slope_hour(soak,"total_ram_mb")
    if rg is not None and rg>float(inp.get("ram_growth_warn_mb_per_hour",250)):
        findings.append({"severity":"WARN","code":"RAM_GROWTH","message":f"RAM trend +{rg:.1f} MB/h"})
    slast=[x["value"] for x in sla if isinstance(x.get("value"),(int,float))]
    if slast and max(slast)-min(slast)>=float(inp.get("sla_drop_warn",20)):
        findings.append({"severity":"WARN","code":"SLA_SWING","message":f"SLA spread {max(slast)-min(slast):.1f}"})
    for a in anomalies[-20:]:
        findings.append({"severity":"INFO","code":"ANOMALY_"+a["metric"],"message":f"{a['metric']} anomaly z={a['robust_z']} value={a['value']}"})
    qacc=quota_accounts(quota)
    qsummary={}
    for e,rows in qacc.items():
        hv=[x["hourly"] for x in rows if isinstance(x.get("hourly"),(int,float))]
        wv=[x["weekly"] for x in rows if isinstance(x.get("weekly"),(int,float))]
        qsummary[e]={"samples":len(rows),"hourly":stats(hv),"weekly":stats(wv),
                     "latest_hourly":hv[-1] if hv else None,"latest_weekly":wv[-1] if wv else None}
    perlat={a:stats(v) for a,v in latacct.items()}
    verdict="WARN" if any(x["severity"]=="WARN" for x in findings) else "PASS"
    return {
      "generatedUtc":datetime.now(timezone.utc).isoformat(),"windowHours":hours,"verdict":verdict,
      "summary":{"soakSamples":len(soak),"opsEvents":len(ops),"quotaSamples":len(quota),"anomalies":len(anomalies)},
      "metrics":{"ram":stats([x["value"] for x in ram]),"sla":stats([x["value"] for x in sla]),
                 "state":stats([x["value"] for x in state]),"latency_ms":lstat,
                 "ramGrowthMbPerHour":rg,"stateGrowthMbPerHour":slope_hour(soak,"state_size_mb"),
                 "events":event_counts},
      "perAccountLatency":perlat,"quota":qsummary,"findings":findings,
      "timeline":timeline[-300:],
      "series":{"ram":downsample(ram,maxpts),"sla":downsample(sla,maxpts),"state":downsample(state,maxpts)}
    }

def svg(series,w=900,h=180,label=""):
    pts=[x for x in series if isinstance(x.get("value"),(int,float))]
    if len(pts)<2:return f'<div class="empty">No {html.escape(label)} series yet</div>'
    vals=[float(x["value"]) for x in pts];lo=min(vals);hi=max(vals)
    if hi==lo:hi=lo+1
    coords=[]
    for i,x in enumerate(vals):
        px=10+i*(w-20)/max(1,len(vals)-1);py=10+(hi-x)*(h-20)/(hi-lo)
        coords.append(f"{px:.1f},{py:.1f}")
    return f'<svg viewBox="0 0 {w} {h}" role="img"><polyline points="{" ".join(coords)}" fill="none" stroke="currentColor" stroke-width="2"/><text x="12" y="22">{html.escape(label)} min={lo:.1f} max={max(vals):.1f}</text></svg>'

def html_report(d):
    def f(v):
        return "—" if v is None else (f"{v:.1f}" if isinstance(v,float) else str(v))
    m=d["metrics"]
    findings="".join(f"<tr><td>{html.escape(x['severity'])}</td><td>{html.escape(x['code'])}</td><td>{html.escape(x['message'])}</td></tr>" for x in d["findings"]) or "<tr><td colspan=3>No findings</td></tr>"
    latrows="".join(f"<tr><td>{html.escape(a)}</td><td>{f(s['count'])}</td><td>{f(s['p50'])}</td><td>{f(s['p95'])}</td><td>{f(s['p99'])}</td></tr>" for a,s in d["perAccountLatency"].items()) or "<tr><td colspan=5>No latency attribution</td></tr>"
    qrows="".join(f"<tr><td>{html.escape(a)}</td><td>{f(q['latest_hourly'])}</td><td>{f(q['latest_weekly'])}</td><td>{q['samples']}</td></tr>" for a,q in d["quota"].items()) or "<tr><td colspan=4>No quota history</td></tr>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>HMS Performance Report</title>
<style>body{{background:#0d1014;color:#edf2f7;font-family:Segoe UI,Arial;margin:0}}main{{max-width:1500px;margin:auto;padding:22px}}.cards{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}}.c,.p{{background:#171b21;border:1px solid #2e3640;border-radius:10px;padding:13px}}.k{{color:#8d98a7;font-size:11px}}.v{{font-size:22px;margin-top:5px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}}svg{{width:100%;height:180px;background:#11151a;color:#69b0db;border-radius:8px}}table{{width:100%;border-collapse:collapse;font-size:12px}}td,th{{padding:7px;border-bottom:1px solid #29313a;text-align:left}}.empty{{color:#8d98a7;padding:30px}}</style></head><body><main>
<h1>HMS Performance Analytics v15.0</h1><p>Window {d['windowHours']}h · Verdict <b>{d['verdict']}</b> · Generated {html.escape(d['generatedUtc'])}</p>
<div class="cards"><div class="c"><div class=k>RAM P95 MB</div><div class=v>{f(m['ram']['p95'])}</div></div><div class="c"><div class=k>Latency P95 ms</div><div class=v>{f(m['latency_ms']['p95'])}</div></div><div class="c"><div class=k>Latency P99 ms</div><div class=v>{f(m['latency_ms']['p99'])}</div></div><div class="c"><div class=k>SLA P50</div><div class=v>{f(m['sla']['p50'])}</div></div><div class="c"><div class=k>Failovers</div><div class=v>{m['events']['FAILOVER']}</div></div><div class="c"><div class=k>Anomalies</div><div class=v>{d['summary']['anomalies']}</div></div></div>
<div class=grid><div class=p><h3>RAM trend</h3>{svg(d['series']['ram'],label='RAM MB')}</div><div class=p><h3>SLA trend</h3>{svg(d['series']['sla'],label='SLA')}</div></div>
<div class=grid><div class=p><h3>State growth</h3>{svg(d['series']['state'],label='State MB')}</div><div class=p><h3>Findings</h3><table><tr><th>Severity</th><th>Code</th><th>Message</th></tr>{findings}</table></div></div>
<div class=grid><div class=p><h3>Per-account latency</h3><table><tr><th>Account</th><th>N</th><th>P50</th><th>P95</th><th>P99</th></tr>{latrows}</table></div><div class=p><h3>Quota history</h3><table><tr><th>Account</th><th>5h latest</th><th>Weekly latest</th><th>Samples</th></tr>{qrows}</table></div></div>
</main></body></html>"""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output");ap.add_argument("--html")
    a=ap.parse_args()
    try:
        inp=json.loads(Path(a.input).read_text("utf-8-sig"));d=analyze(inp);o={"ok":True,"data":d}
        if a.html:Path(a.html).write_text(html_report(d),"utf-8")
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
