#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, os, socketserver, http.server, threading, time, sys, shutil, http.client, sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

class Upstream(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a):return
    def do_GET(self):
        if self.path.startswith("/v1/models"):
            body=json.dumps({"object":"list","data":[{"id":"gpt-5.6"},{"id":"gpt-image-2"}]}).encode()
        else:
            body=json.dumps({"ok":True}).encode()
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        raw=self.rfile.read(n) if n else b"{}"
        try:j=json.loads(raw)
        except:j={}
        body=json.dumps({
            "id":"resp_test","model":j.get("model"),
            "usage":{"input_tokens":100,"output_tokens":25,"input_tokens_details":{"cached_tokens":20},"total_tokens":125},
            "ok":True
        }).encode()
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)

def serve():
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),Upstream);srv.daemon_threads=True
    threading.Thread(target=srv.serve_forever,daemon=True).start();return srv

def gateway(gw,cfg,keys,trace,cfgp):
    cfgp.write_text(json.dumps(cfg),"utf-8")
    srv=gw.ThreadingServer(("127.0.0.1",0),gw.Handler)
    srv.keys=keys;srv.configure_runtime(cfgp,cfg,str(trace))
    threading.Thread(target=srv.serve_forever,daemon=True).start()
    return srv

def req(port,method,path,key,body=None,headers=None):
    c=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
    h={"Authorization":"Bearer "+key}
    if headers:h.update(headers)
    payload=None
    if body is not None:
        payload=json.dumps(body).encode();h["Content-Type"]="application/json"
    c.request(method,path,body=payload,headers=h);r=c.getresponse();raw=r.read();hs=dict(r.getheaders());status=r.status;c.close()
    return status,hs,raw

def run(root:Path,temp:Path):
    shutil.rmtree(temp,ignore_errors=True);temp.mkdir(parents=True)
    gw=loadmod("hms_gateway_v24_validate",root/"HMS_Codex_SmartGateway.py")
    an=loadmod("hms_analytics_v24_validate",root/"HMS_Codex_ApiAnalytics.py")
    tests=[]
    def add(name,ok,detail):tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})

    now=datetime.now(timezone.utc).isoformat()
    targets=[
        {"id":"A","account":"a@example.com","base_url":"http://127.0.0.1:1","priority":10,"weight":1,"enabled":True,
         "model_allow":["gpt-*"],"model_deny":[],"quota_hourly_pct":90,"quota_weekly_pct":80,"quota_checked_utc":now,"plan_rank":2,
         "expiry_utc":(datetime.now(timezone.utc)+timedelta(days=20)).isoformat()},
        {"id":"B","account":"b@example.com","base_url":"http://127.0.0.1:2","priority":10,"weight":3,"enabled":True,
         "model_allow":["gpt-*"],"model_deny":[],"quota_hourly_pct":60,"quota_weekly_pct":55,"quota_checked_utc":now,"plan_rank":5,
         "expiry_utc":(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()},
        {"id":"C","account":"c@example.com","base_url":"http://127.0.0.1:3","priority":10,"weight":1,"enabled":True,
         "model_allow":["gpt-*"],"model_deny":[],"quota_hourly_pct":99,"quota_weekly_pct":99,
         "quota_checked_utc":(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),"plan_rank":1,
         "backup":True}
    ]
    base={"strategy":"stable-round-robin","session_affinity":True,"session_ttl_sec":3600,
          "quota_evidence_max_age_sec":900,"quota_reserve_fail_closed":True,"default_quota_reserve_pct":0,
          "targets":targets}
    r=gw.Router(base,temp/"trace0.jsonl")

    client={"id":"k1","target_allow":["A","B"],"target_deny":[],"routing_strategy":"single","single_target":"B",
            "model_allow":["gpt-*"],"model_deny":[]}
    t,why=r.choose("gpt-5.6","s1",client=client)
    add("key_pool.single",t and t["id"]=="B" and why=="SINGLE",f"target={t and t['id']} reason={why}")

    client2={"id":"k2","target_allow":["A","B"],"routing_strategy":"quota-first","model_allow":["gpt-*"],"quota_reserve_pct":0}
    t,why=r.choose("gpt-5.6",None,client=client2)
    add("routing.quota_first",t and t["id"]=="A" and why=="QUOTA_FIRST",f"target={t and t['id']}")

    client3={"id":"k3","target_allow":["A","B"],"routing_strategy":"plan-first","model_allow":["gpt-*"]}
    t,why=r.choose("gpt-5.6",None,client=client3)
    add("routing.plan_first",t and t["id"]=="B" and why=="PLAN_FIRST",f"target={t and t['id']}")

    client4={"id":"k4","target_allow":["A","B"],"routing_strategy":"expiry-soon","model_allow":["gpt-*"]}
    t,why=r.choose("gpt-5.6",None,client=client4)
    add("routing.expiry_soon",t and t["id"]=="B" and why=="EXPIRY_SOON",f"target={t and t['id']}")

    client5={"id":"k5","target_allow":["A","C"],"routing_strategy":"quota-first","quota_reserve_pct":85,"model_allow":["gpt-*"]}
    elig=r.available("gpt-5.6",client=client5)
    add("quota.reserve_fail_closed",len(elig)==0,"stale C excluded; A below reserve")

    # Client-key scoped affinity must not collide.
    c1={"id":"one","target_allow":["A"],"model_allow":["gpt-*"]}
    c2={"id":"two","target_allow":["B"],"model_allow":["gpt-*"]}
    a1,_=r.choose("gpt-5.6","same-session",client=c1);a2,_=r.choose("gpt-5.6","same-session",client=c2)
    add("affinity.client_key_scope",a1 and a2 and a1["id"]=="A" and a2["id"]=="B" and len(r.affinity)>=2,
        f"a1={a1 and a1['id']} a2={a2 and a2['id']} affinity={len(r.affinity)}")

    # Live HTTP: model prefix, CORS, usage capture, estimated cost.
    up=serve()
    trace=temp/"gateway-trace.jsonl";cfgp=temp/"gateway.json";keys=gw.KeyStore(temp/"keys.json")
    rec,key=keys.create("dev",["gpt-*"],["gpt-image-*"],["UP"],[],None,"corp-",None,0,{}, {})
    cfg={
        "host":"127.0.0.1","port":0,"strategy":"stable-round-robin","session_affinity":True,"session_ttl_sec":3600,
        "health_fail_threshold":3,"health_cooldown_sec":120,"require_client_key":True,
        "max_failover_attempts":2,"retry_statuses":[429,500,502,503,504],"require_idempotency_for_post_replay":True,
        "stream_chunk_bytes":1024,"upstream_timeout_sec":10,"websocket_enabled":True,"websocket_idle_timeout_sec":10,
        "websocket_require_model_hint":True,"expose_selected_target_headers":True,
        "cors_enabled":True,"cors_allowed_origins":["http://localhost:*","http://127.0.0.1:*"],
        "usage_capture_max_bytes":2097152,"quota_evidence_max_age_sec":900,"quota_reserve_fail_closed":True,
        "model_prices":{"gpt-5.6":{"input_per_million":10.0,"cached_input_per_million":2.0,"output_per_million":20.0}},
        "targets":[{"id":"UP","account":"up@example.com","base_url":f"http://127.0.0.1:{up.server_address[1]}","priority":10,"weight":1,
                    "enabled":True,"model_allow":["gpt-*"],"model_deny":[]}]
    }
    gs=gateway(gw,cfg,keys,trace,cfgp);port=gs.server_address[1]
    try:
        status,_,raw=req(port,"GET","/v1/models",key)
        mids=[x["id"] for x in json.loads(raw).get("data",[])]
        add("model.prefix_catalog",status==200 and "corp-gpt-5.6" in mids and "corp-gpt-image-2" not in mids,str(mids))

        status,hs,raw=req(port,"POST","/v1/responses",key,{"model":"corp-gpt-5.6","input":"secret-data"})
        body=json.loads(raw)
        add("model.prefix_rewrite",status==200 and body.get("model")=="gpt-5.6",json.dumps(body))

        c=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
        c.request("OPTIONS","/v1/responses",headers={"Origin":"http://localhost:3000","Access-Control-Request-Method":"POST"})
        rr=c.getresponse();rr.read();cors=dict(rr.getheaders());c.close()
        add("cors.loopback_preflight",rr.status==204 and cors.get("Access-Control-Allow-Origin")=="http://localhost:3000",
            f"status={rr.status} origin={cors.get('Access-Control-Allow-Origin')}")

        time.sleep(0.05)
        rows=[json.loads(x) for x in trace.read_text().splitlines() if x.strip()]
        last=next(x for x in reversed(rows) if x.get("protocol")=="http" and x.get("status")==200)
        expected=((80*10)+(20*2)+(25*20))/1_000_000
        cost=last.get("estimated_usd")
        add("usage.cost_capture",
            last.get("input_tokens")==100 and last.get("output_tokens")==25 and last.get("cached_input_tokens")==20 and abs(cost-expected)<1e-10,
            json.dumps({k:last.get(k) for k in ("input_tokens","output_tokens","cached_input_tokens","estimated_usd","usage_source")}))

        analytics=an.analyze(trace,1000)
        allstats=analytics["windows"]["all"]["total"]
        bykey=analytics["windows"]["all"]["by_client_key"]
        add("analytics.account_model_key",
            allstats.get("requests",0)>=1 and "dev" in bykey and bykey["dev"].get("total_tokens",0)>=125,
            json.dumps({"total":allstats,"keys":list(bykey)}))
    finally:
        gs.shutdown();gs.server_close();up.shutdown();up.server_close()

    # Trace privacy
    raw=trace.read_text("utf-8")
    add("trace.privacy","secret-data" not in raw and key not in raw,"request body/client key absent")

    # Session visibility repair parity: rollout/session metadata + state_5.sqlite threads.
    sd=loadmod("hms_sessiondoctor_v24_validate",root/"HMS_Codex_SessionDoctor.py")
    home=temp/"codex-home";(home/"sessions").mkdir(parents=True)
    (home/"config.toml").write_text('model_provider = "hms_api_router"\n',"utf-8")
    session_file=home/"sessions"/"s1.jsonl"
    session_file.write_text(json.dumps({"id":"s1","model_provider":"openai","cwd":"C:/work"})+"\n","utf-8")
    con=sqlite3.connect(str(home/"state_5.sqlite"))
    con.execute("create table threads(id text primary key, model_provider text)")
    con.execute("insert into threads(id,model_provider) values('s1','openai')")
    con.commit();con.close()
    rr=sd.repair(home,"hms_api_router")
    first=json.loads(session_file.read_text("utf-8").splitlines()[0])
    con=sqlite3.connect(str(home/"state_5.sqlite"));db_provider=con.execute("select model_provider from threads where id='s1'").fetchone()[0];con.close()
    backup_ok=Path(rr["backup"]).exists()
    add("session.visibility_repair",
        first.get("model_provider")=="hms_api_router" and db_provider=="hms_api_router" and rr.get("updated_sqlite_rows")==1 and backup_ok,
        json.dumps({"changed_session_files":rr.get("changed_session_files"),"updated_sqlite_rows":rr.get("updated_sqlite_rows"),"backup":backup_ok}))

    fail=sum(1 for x in tests if x["status"]=="FAIL")
    return {"version":"24.0","verdict":"PASS" if fail==0 else "FAIL",
            "summary":{"pass":len(tests)-fail,"fail":fail,"total":len(tests)},"tests":tests}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--temp",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:data=run(Path(a.root),Path(a.temp));o={"ok":data["verdict"]=="PASS","data":data}
    except Exception as e:o={"ok":False,"error":repr(e)}
    txt=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt);return 0 if o.get("ok") else 2

if __name__=="__main__":raise SystemExit(main())
