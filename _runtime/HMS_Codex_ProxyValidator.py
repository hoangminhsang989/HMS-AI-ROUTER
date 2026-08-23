#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, socket, socketserver, struct, threading, time, sys, shutil
from pathlib import Path

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

class HttpConnect(socketserver.BaseRequestHandler):
    def handle(self):
        data=b""
        while b"\r\n\r\n" not in data:
            c=self.request.recv(4096)
            if not c:return
            data+=c
        if b"CONNECT " not in data.split(b"\r\n",1)[0]:
            self.request.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length:0\r\n\r\n");return
        self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        # synthetic tunnel closes after success

class Socks5(socketserver.BaseRequestHandler):
    def handle(self):
        h=self.request.recv(2)
        if len(h)<2:return
        methods=self.request.recv(h[1])
        self.request.sendall(b"\x05\x00")
        req=self.request.recv(4)
        if len(req)<4:return
        atyp=req[3]
        if atyp==1:self.request.recv(4)
        elif atyp==3:
            n=self.request.recv(1)
            if not n:return
            self.request.recv(n[0])
        elif atyp==4:self.request.recv(16)
        self.request.recv(2)
        self.request.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")

def serve(handler):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),handler);srv.daemon_threads=True
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start();return srv,th

def run(root:Path,temp:Path):
    mgr=loadmod("hms_proxy_manager_v22",root/"HMS_Codex_ProxyManager.py")
    health=loadmod("hms_proxy_health_v22",root/"HMS_Codex_ProxyHealth.py")
    shutil.rmtree(temp,ignore_errors=True);temp.mkdir(parents=True)
    profiles=temp/"profiles.json";bindings=temp/"bindings.json";healthp=temp/"health.json";audit=temp/"audit.jsonl"

    for i in range(3):
        mgr.upsert_profile(profiles,audit,{
            "id":f"p{i+1}","name":f"VN-{i+1:02}","scheme":"http","host":"127.0.0.1","port":9000+i,
            "mode":"STRICT","max_accounts":5,"enabled":True,"country":"VN"
        })

    accounts=[{"email":f"user{i:02}@example.com","filename":f"codex-user{i:02}.json"} for i in range(1,13)]
    assigned=mgr.assign(profiles,bindings,audit,accounts,5,True)
    rows=assigned["bindings"]
    counts={}
    for x in rows:counts[x["proxy_profile_id"]]=counts.get(x["proxy_profile_id"],0)+1
    t=[];add=lambda n,ok,d:t.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})

    add("assignment.capacity",max(counts.values())<=5 and sum(counts.values())==12,str(counts))
    first={x["email"]:x["proxy_profile_id"] for x in rows}
    assigned2=mgr.assign(profiles,bindings,audit,accounts+[{"email":"new@example.com","filename":"codex-new.json"}],5,True)
    second={x["email"]:x["proxy_profile_id"] for x in assigned2["bindings"]}
    preserved=all(second[k]==v for k,v in first.items())
    add("assignment.stable_preserve",preserved,"existing bindings preserved")

    # Strict fail-closed.
    mgr.atomic(healthp,{"version":22,"profiles":{"p1":{"status":"FAIL"},"p2":{"status":"PASS"},"p3":{"status":"PASS"}}})
    email=next(x["email"] for x in rows if x["proxy_profile_id"]=="p1")
    pol=mgr.account_policy(email,profiles,bindings,healthp,False)
    add("policy.strict_fail_closed",pol["decision"]=="BLOCKED" and pol["reason"]=="STRICT_PROXY_UNHEALTHY",json.dumps(pol))

    plan=mgr.plan(profiles,bindings,healthp,8420,False)
    p1=next(x for x in plan["groups"] if x["profile_id"]=="p1")
    add("plan.strict_blocks_unhealthy",p1["start_allowed"] is False,f"start_allowed={p1['start_allowed']}")
    ports=[x["sidecar_port"] for x in plan["groups"]]
    add("plan.unique_ports",len(ports)==len(set(ports)),str(ports))

    safe=mgr.safe_export(profiles,bindings,healthp)
    raw=json.dumps(safe)
    add("export.no_proxy_passwords","secret_ref" not in raw and safe["contains_proxy_passwords"] is False,"safe export redacts secret refs")

    # HTTP CONNECT synthetic without TLS probe.
    hs,_=serve(HttpConnect)
    try:
        r=health.check("http","127.0.0.1",hs.server_address[1],"example.com",443,timeout=2,tls_probe=False)
        add("health.http_connect",r["status"]=="PASS",json.dumps(r))
    finally:hs.shutdown();hs.server_close()

    ss,_=serve(Socks5)
    try:
        r=health.check("socks5","127.0.0.1",ss.server_address[1],"example.com",443,timeout=2,tls_probe=False)
        add("health.socks5",r["status"]=="PASS",json.dumps(r))
    finally:ss.shutdown();ss.server_close()

    fail=sum(1 for x in t if x["status"]=="FAIL")
    return {"version":"22.0","verdict":"PASS" if fail==0 else "FAIL",
            "summary":{"pass":len(t)-fail,"fail":fail,"total":len(t)},"tests":t}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--temp",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:data=run(Path(a.root),Path(a.temp));o={"ok":data["verdict"]=="PASS","data":data}
    except Exception as e:o={"ok":False,"error":repr(e)}
    txt=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt);return 0 if o.get("ok") else 2

if __name__=="__main__":raise SystemExit(main())
