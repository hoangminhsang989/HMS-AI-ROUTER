#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, os, socketserver, threading, time, sys, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def now():return datetime.now(timezone.utc).isoformat()

class IpProxy(socketserver.BaseRequestHandler):
    def handle(self):
        data=b""
        while b"\r\n\r\n" not in data:
            c=self.request.recv(4096)
            if not c:return
            data+=c
        body=json.dumps({"ip":self.server.public_ip}).encode()
        resp=(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+
              str(len(body)).encode()+b"\r\nConnection: close\r\n\r\n"+body)
        self.request.sendall(resp)

def serve_ip(ip):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),IpProxy);srv.daemon_threads=True;srv.public_ip=ip
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return srv,th

def run(root:Path,temp:Path):
    shutil.rmtree(temp,ignore_errors=True);temp.mkdir(parents=True)
    eg=loadmod("hms_egress_v23",root/"HMS_Codex_EgressGuard.py")
    fl=loadmod("hms_fleet_v23",root/"HMS_Codex_ProxyFleet.py")
    gw=loadmod("hms_gateway_v23",root/"HMS_Codex_SmartGateway.py")
    tests=[]
    def add(name,ok,detail):tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})

    # Egress baseline -> stable -> drift.
    proxy,_=serve_ip("203.0.113.10")
    state=temp/"egress.json"
    try:
        p1=eg.fetch_via_proxy("http","127.0.0.1",proxy.server_address[1],"","",
                              "http://probe.invalid/ip",2)
        r1=eg.update(state,"p1",p1,True,True)
        add("egress.baseline_learn",r1["integrity_status"]=="PASS" and r1["expected_ip"]=="203.0.113.10",
            json.dumps(r1))
        p2=eg.fetch_via_proxy("http","127.0.0.1",proxy.server_address[1],"","",
                              "http://probe.invalid/ip",2)
        r2=eg.update(state,"p1",p2,True,True)
        add("egress.stable",r2["integrity_status"]=="PASS" and not r2["strict_block"],json.dumps(r2))
        proxy.public_ip="203.0.113.11"
        p3=eg.fetch_via_proxy("http","127.0.0.1",proxy.server_address[1],"","",
                              "http://probe.invalid/ip",2)
        r3=eg.update(state,"p1",p3,True,True)
        add("egress.drift_block",r3["integrity_status"]=="DRIFT" and r3["strict_block"] and r3["drift_count"]==1,
            json.dumps(r3))
    finally:
        proxy.shutdown();proxy.server_close()

    # Fleet critical recommendation and quarantine.
    profiles=temp/"profiles.json";bindings=temp/"bindings.json";health=temp/"health.json"
    sidecars=temp/"sidecars.json";fleetstate=temp/"fleetstate.json";history=temp/"history.jsonl";actions=temp/"actions.jsonl"
    profiles.write_text(json.dumps({"profiles":[{"id":"p1","name":"VN-01","enabled":True,"max_accounts":5}]}),"utf-8")
    bindings.write_text(json.dumps({"bindings":[{"email":"a@example.com","proxy_profile_id":"p1"}]}),"utf-8")
    health.write_text(json.dumps({"profiles":{"p1":{"status":"PASS","checked_utc":now()}}}),"utf-8")
    sidecars.write_text(json.dumps({"sidecars":[{"profile_id":"p1","status":"RUNNING","pid":123,"port":8420}]}),"utf-8")
    audit=fl.audit(profiles,bindings,health,state,sidecars,fleetstate,actions,True,True,2,300,300,300)
    row=audit["profiles"][0]
    add("fleet.drift_recommends_quarantine",
        row["severity"]=="CRITICAL" and row["recommendation"]=="QUARANTINE_EGRESS_DRIFT" and row["auto_action"]=="QUARANTINE",
        json.dumps(row))
    fl.set_state(fleetstate,actions,"p1","QUARANTINED","TEST_DRIFT")
    audit2=fl.audit(profiles,bindings,health,state,sidecars,fleetstate,actions,True,True,2,300,300,300)
    add("fleet.quarantined_state",
        audit2["profiles"][0]["ops_state"]=="QUARANTINED" and audit2["profiles"][0]["severity"]=="QUARANTINED",
        json.dumps(audit2["profiles"][0]))

    # Stale evidence must not be healthy.
    stale=(datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
    health.write_text(json.dumps({"profiles":{"p1":{"status":"PASS","checked_utc":stale}}}),"utf-8")
    fl.set_state(fleetstate,actions,"p1","ACTIVE","TEST_ACTIVE")
    # Put stable egress back but stale egress timestamp.
    egs=eg.load_state(state);egs["profiles"]["p1"].update({"observed_ip":"203.0.113.10","expected_ip":"203.0.113.10",
        "integrity_status":"PASS","strict_block":False,"checked_utc":stale})
    eg.atomic(state,egs)
    audit3=fl.audit(profiles,bindings,health,state,sidecars,fleetstate,actions,True,True,2,300,300,300)
    row3=audit3["profiles"][0]
    add("fleet.stale_evidence_not_healthy",
        row3["health_status"]=="STALE" and row3["egress_status"]=="STALE" and row3["severity"]=="DEGRADED",
        json.dumps(row3))

    # Smart Gateway hot config reload removes quarantined target without process restart.
    cfgp=temp/"gateway.json";trace=temp/"gateway-trace.jsonl"
    cfg1={"host":"127.0.0.1","port":0,"strategy":"stable-round-robin","session_affinity":True,
          "targets":[{"id":"A","enabled":True,"base_url":"http://127.0.0.1:1","priority":10,"model_allow":["*"]},
                     {"id":"B","enabled":True,"base_url":"http://127.0.0.1:2","priority":10,"model_allow":["*"]}]}
    cfgp.write_text(json.dumps(cfg1),"utf-8")
    srv=gw.ThreadingServer(("127.0.0.1",0),gw.Handler)
    try:
        srv.keys=gw.KeyStore(temp/"keys.json")
        srv.configure_runtime(cfgp,cfg1,str(trace))
        srv.router.affinity["session"]=("A",time.time()+3600)
        time.sleep(0.01)
        cfg2=dict(cfg1);cfg2["targets"]=[cfg1["targets"][1]]
        cfgp.write_text(json.dumps(cfg2),"utf-8")
        # Ensure mtime monotonic on coarse filesystems.
        os.utime(cfgp,None);time.sleep(0.02)
        changed=srv.refresh_config()
        ids=[x["id"] for x in srv.router.cfg.get("targets",[])]
        add("gateway.hot_reload_quarantine",
            changed and ids==["B"] and "session" not in srv.router.affinity,
            f"changed={changed}; ids={ids}; affinity={srv.router.affinity}")
    finally:
        srv.server_close()

    # Safe fleet export excludes secret refs.
    safe=fl.safe_export(profiles,bindings,health,state,fleetstate)
    raw=json.dumps(safe)
    add("fleet.safe_export","secret_ref" not in raw and safe["contains_proxy_passwords"] is False,
        "no secret_ref/password fields")

    fail=sum(1 for x in tests if x["status"]=="FAIL")
    return {"version":"23.0","verdict":"PASS" if fail==0 else "FAIL",
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
