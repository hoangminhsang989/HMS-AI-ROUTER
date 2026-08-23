#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, hashlib, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCHEMA="""
create table if not exists events(
 id text primary key,
 observed_at real not null,
 account text,
 kind text,
 confidence text,
 request_id text,
 status_code integer,
 latency_ms real,
 message text
);
create index if not exists ix_events_account_time on events(account,observed_at);
create table if not exists circuits(
 account text primary key,
 state text not null,
 opened_at real,
 open_until real,
 last_transition real,
 transitions_hour integer not null default 0,
 transition_window_start real,
 last_reason text,
 updated_at real not null
);
"""

def conn(db):
    c=sqlite3.connect(db);c.executescript(SCHEMA);return c

def event_hash(e,bucket):
    payload=json.dumps([bucket,e.get("source"),e.get("kind"),e.get("account"),e.get("confidence"),e.get("message")],
                       ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(payload.encode()).hexdigest()

def ingest(c,events):
    now=time.time();bucket=int(now//60)
    added=0
    for e in events:
        h=event_hash(e,bucket)
        try:
            c.execute("insert into events values(?,?,?,?,?,?,?,?,?)",
                      (h,now,e.get("account"),e.get("kind"),e.get("confidence"),e.get("request_id"),
                       e.get("status_code"),e.get("latency_ms"),str(e.get("message") or "")[:1000]))
            added+=1
        except sqlite3.IntegrityError:pass
    c.commit();return added

def metrics(c,accounts,window_min):
    since=time.time()-window_min*60
    out=[]
    for a in accounts:
        rows=c.execute("select kind,status_code,latency_ms from events where account=? and observed_at>=?",
                       (a,since)).fetchall()
        counts={"REQUEST":0,"ERROR":0,"COOLDOWN":0,"FAILOVER":0,"RETRY":0}
        lat=[]
        for kind,status,l in rows:
            if kind in counts:counts[kind]+=1
            if status and status>=400:counts["ERROR"]+=1
            if l is not None:lat.append(float(l))
        samples=counts["REQUEST"]+counts["ERROR"]
        er=100*counts["ERROR"]/max(1,samples)
        lat.sort()
        p50=lat[int((len(lat)-1)*0.50)] if lat else None
        p95=lat[int((len(lat)-1)*0.95)] if lat else None
        out.append({"account":a,"samples":samples,**counts,"error_rate_pct":round(er,2),
                    "latency_p50_ms":p50,"latency_p95_ms":p95})
    return out

def circuit_row(c,a):
    r=c.execute("select state,opened_at,open_until,last_transition,transitions_hour,transition_window_start,last_reason,updated_at from circuits where account=?",(a,)).fetchone()
    if not r:return {"account":a,"state":"CLOSED","opened_at":None,"open_until":None,"transitions_hour":0,"last_reason":None}
    return {"account":a,"state":r[0],"opened_at":r[1],"open_until":r[2],"last_transition":r[3],
            "transitions_hour":r[4],"transition_window_start":r[5],"last_reason":r[6],"updated_at":r[7]}

def transition(c,a,new_state,reason,open_seconds,max_transitions):
    now=time.time();cur=circuit_row(c,a)
    if cur["state"]==new_state:return cur
    ws=cur.get("transition_window_start") or now
    cnt=int(cur.get("transitions_hour") or 0)
    if now-ws>=3600:ws=now;cnt=0
    cnt+=1
    if cnt>max_transitions:new_state="LOCKED_OPEN";reason="anti_flap_lock: "+reason
    opened=now if new_state in ("OPEN","LOCKED_OPEN") else cur.get("opened_at")
    until=(now+open_seconds) if new_state=="OPEN" else (None if new_state!="LOCKED_OPEN" else cur.get("open_until"))
    c.execute("""insert into circuits(account,state,opened_at,open_until,last_transition,transitions_hour,transition_window_start,last_reason,updated_at)
                 values(?,?,?,?,?,?,?,?,?)
                 on conflict(account) do update set state=excluded.state,opened_at=excluded.opened_at,open_until=excluded.open_until,
                 last_transition=excluded.last_transition,transitions_hour=excluded.transitions_hour,transition_window_start=excluded.transition_window_start,
                 last_reason=excluded.last_reason,updated_at=excluded.updated_at""",
              (a,new_state,opened,until,now,cnt,ws,reason,now));c.commit()
    return circuit_row(c,a)

def evaluate(c,accounts,window_min,error_rate,min_samples,open_seconds,max_transitions,half_success):
    mets=metrics(c,accounts,window_min);mm={m["account"]:m for m in mets};out=[]
    now=time.time()
    for a in accounts:
        m=mm[a];cur=circuit_row(c,a);state=cur["state"]
        cooldown=m["COOLDOWN"]>0
        unhealthy=(m["samples"]>=min_samples and m["error_rate_pct"]>=error_rate)
        if state=="CLOSED" and (cooldown or unhealthy):
            reason="cooldown" if cooldown else f"error_rate={m['error_rate_pct']}%"
            cur=transition(c,a,"OPEN",reason,open_seconds,max_transitions)
        elif state=="OPEN" and cur.get("open_until") and now>=cur["open_until"]:
            cur=transition(c,a,"HALF_OPEN","open timeout elapsed",open_seconds,max_transitions)
        elif state=="HALF_OPEN":
            if cooldown or unhealthy:
                cur=transition(c,a,"OPEN","half-open failed",open_seconds,max_transitions)
            elif m["samples"]>=half_success and m["ERROR"]==0 and m["COOLDOWN"]==0:
                cur=transition(c,a,"CLOSED","half-open healthy",open_seconds,max_transitions)
        out.append({**m,**cur})
    return out

def reset(c,account):
    now=time.time()
    c.execute("""insert into circuits(account,state,opened_at,open_until,last_transition,transitions_hour,transition_window_start,last_reason,updated_at)
                 values(?,?,?,?,?,?,?,?,?)
                 on conflict(account) do update set state='CLOSED',opened_at=null,open_until=null,last_transition=excluded.last_transition,
                 transitions_hour=0,transition_window_start=excluded.transition_window_start,last_reason='manual reset',updated_at=excluded.updated_at""",
              (account,"CLOSED",None,None,now,0,now,"manual reset",now));c.commit()
    return circuit_row(c,account)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",required=True);ap.add_argument("--mode",choices=("ingest","evaluate","snapshot","reset"),required=True)
    ap.add_argument("--events");ap.add_argument("--accounts");ap.add_argument("--account");ap.add_argument("--output")
    ap.add_argument("--window-min",type=int,default=30);ap.add_argument("--error-rate",type=float,default=40)
    ap.add_argument("--min-samples",type=int,default=5);ap.add_argument("--open-seconds",type=int,default=300)
    ap.add_argument("--max-transitions",type=int,default=6);ap.add_argument("--half-success",type=int,default=3)
    a=ap.parse_args();c=conn(a.db)
    try:
        accounts=json.loads(Path(a.accounts).read_text("utf-8")) if a.accounts else []
        if a.mode=="ingest":
            events=json.loads(Path(a.events).read_text("utf-8")) if a.events else []
            data={"added":ingest(c,events)}
        elif a.mode=="evaluate":
            data={"accounts":evaluate(c,accounts,a.window_min,a.error_rate,a.min_samples,a.open_seconds,a.max_transitions,a.half_success)}
        elif a.mode=="snapshot":
            mm=metrics(c,accounts,a.window_min)
            data={"accounts":[{**m,**circuit_row(c,m["account"])} for m in mm]}
        else:data=reset(c,a.account)
        out={"ok":True,"data":data}
    except Exception as e:out={"ok":False,"error":repr(e)}
    finally:c.close()
    s=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if out.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
