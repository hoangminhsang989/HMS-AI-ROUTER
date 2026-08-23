#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import http.server
import importlib.util
import json
import os
import secrets
import socket
import socketserver
import struct
import sys
import threading
import time
from pathlib import Path

def load_gateway(root:Path):
    p=root/"HMS_Codex_SmartGateway.py"
    spec=importlib.util.spec_from_file_location("hms_gateway_v21_validate",p)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod

def read_head(sock):
    data=b""
    while b"\r\n\r\n" not in data:
        c=sock.recv(4096)
        if not c:break
        data+=c
        if len(data)>131072:raise RuntimeError("header too large")
    return data

def ws_accept(key):
    raw=hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    return base64.b64encode(raw).decode()

def ws_read_frame(sock):
    h=sock.recv(2)
    if len(h)<2:return None
    b1,b2=h
    masked=bool(b2&0x80);n=b2&0x7f
    if n==126:n=struct.unpack("!H",sock.recv(2))[0]
    elif n==127:n=struct.unpack("!Q",sock.recv(8))[0]
    mask=sock.recv(4) if masked else b""
    data=b""
    while len(data)<n:
        c=sock.recv(n-len(data))
        if not c:break
        data+=c
    if masked:data=bytes(x^mask[i%4] for i,x in enumerate(data))
    return b1&0x0f,data

def ws_frame(payload,opcode=1,masked=False):
    if isinstance(payload,str):payload=payload.encode()
    n=len(payload);b1=0x80|opcode
    if n<126:head=bytes([b1,(0x80 if masked else 0)|n])
    elif n<65536:head=bytes([b1,(0x80 if masked else 0)|126])+struct.pack("!H",n)
    else:head=bytes([b1,(0x80 if masked else 0)|127])+struct.pack("!Q",n)
    if not masked:return head+payload
    mask=os.urandom(4)
    enc=bytes(x^mask[i%4] for i,x in enumerate(payload))
    return head+mask+enc

class Upstream(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a):return
    def do_GET(self):
        if self.path.startswith("/v1/models"):
            b=json.dumps({"object":"list","data":[{"id":"gpt-5.6"},{"id":"gpt-image-2"}]}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if self.path.startswith("/sse"):
            self.send_response(200);self.send_header("Content-Type","text/event-stream");self.send_header("Cache-Control","no-cache");self.send_header("Connection","close");self.end_headers()
            for i in range(3):
                self.wfile.write(f"data: {i}\n\n".encode());self.wfile.flush();time.sleep(0.06)
            self.close_connection=True;return
        if self.path.startswith("/retry"):
            if getattr(self.server,"fail",False):
                b=b'{"error":"retry"}'
                self.send_response(503);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
            else:
                b=b'{"ok":true}'
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
            return
        self.send_response(404);self.send_header("Content-Length","0");self.end_headers()
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0") or 0);body=self.rfile.read(n) if n else b""
        if self.path.startswith("/retry"):
            if getattr(self.server,"fail",False):
                b=b'{"error":"retry"}';self.send_response(503)
            else:
                b=b'{"ok":true}';self.send_response(200)
            self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        try:model=json.loads(body).get("model")
        except:model=None
        b=json.dumps({"ok":True,"model":model}).encode()
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)

class WsHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data=read_head(self.request)
        txt=data.decode("latin1","replace")
        key=""
        for line in txt.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key=line.split(":",1)[1].strip()
        resp=(
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {ws_accept(key)}\r\n\r\n"
        ).encode()
        self.request.sendall(resp)
        frame=ws_read_frame(self.request)
        if frame:
            op,payload=frame
            self.request.sendall(ws_frame(payload,op,masked=False))

class WsRejectHandler(socketserver.BaseRequestHandler):
    def handle(self):
        _=read_head(self.request)
        body=b'{"error":"temporary"}'
        resp=(
            "HTTP/1.1 503 Service Unavailable\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode()+body
        self.request.sendall(resp)

def serve_http(fail=False):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),Upstream)
    srv.daemon_threads=True;srv.fail=fail
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return srv,th

def serve_ws(handler=WsHandler):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),handler)
    srv.daemon_threads=True
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return srv,th

def gateway_server(gw,cfg,keys,trace):
    srv=gw.ThreadingServer(("127.0.0.1",0),gw.Handler)
    srv.cfg=cfg;srv.keys=keys;srv.trace=str(trace);srv.router=gw.Router(cfg,str(trace))
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return srv,th

def http_req(port,method,path,key,body=None,headers=None):
    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
    h={"Authorization":"Bearer "+key}
    if headers:h.update(headers)
    if body is not None:
        if not isinstance(body,(bytes,bytearray)):body=json.dumps(body).encode()
        h["Content-Type"]="application/json"
    conn.request(method,path,body=body,headers=h)
    resp=conn.getresponse()
    raw=resp.read()
    hs=dict(resp.getheaders())
    status=resp.status
    conn.close()
    return status,hs,raw

def run(root:Path,temp:Path):
    gw=load_gateway(root)
    results=[]
    def add(name,status,detail,extra=None):
        results.append({"name":name,"status":status,"detail":detail,"extra":extra or {}})

    temp.mkdir(parents=True,exist_ok=True)
    trace=temp/"trace.jsonl"
    keys=gw.KeyStore(temp/"keys.json")
    _,key=keys.create("validator",["gpt-*"],["gpt-image-*"])

    up1,_=serve_http(False)
    cfg={
        "strategy":"stable-round-robin","session_affinity":True,"session_ttl_sec":3600,
        "health_fail_threshold":3,"health_cooldown_sec":120,"require_client_key":True,
        "max_failover_attempts":3,"retry_statuses":[429,500,502,503,504],
        "require_idempotency_for_post_replay":True,"stream_chunk_bytes":1024,
        "websocket_enabled":True,"websocket_idle_timeout_sec":10,
        "websocket_require_model_hint":True,
        "expose_selected_target_headers":True,
        "targets":[{"id":"main","account":"main@example.com","base_url":f"http://127.0.0.1:{up1.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]}]
    }
    g,_=gateway_server(gw,cfg,keys,trace)
    gp=g.server_address[1]

    try:
        status,hs,raw=http_req(gp,"POST","/v1/responses",key,{"model":"gpt-5.6","input":"SECRET_BODY"})
        ok=status==200 and json.loads(raw).get("model")=="gpt-5.6" and hs.get("X-HMS-Selected-Target")
        add("http.forwarding","PASS" if ok else "FAIL",f"status={status}; selected={hs.get('X-HMS-Selected-Target')}")

        status,_,raw=http_req(gp,"GET","/v1/models",key)
        ids=[x["id"] for x in json.loads(raw).get("data",[])]
        ok=status==200 and "gpt-5.6" in ids and "gpt-image-2" not in ids
        add("models.policy","PASS" if ok else "FAIL",f"models={ids}")

        conn=http.client.HTTPConnection("127.0.0.1",gp,timeout=5)
        conn.request("GET","/sse?model=gpt-5.6",headers={"Authorization":"Bearer "+key})
        resp=conn.getresponse();t0=time.time();chunks=[]
        while True:
            c=resp.read1(64)
            if not c:break
            chunks.append((time.time()-t0,c))
        conn.close()
        joined=b"".join(c for _,c in chunks)
        ok=resp.status==200 and joined.count(b"data:")==3 and len(chunks)>=2
        add("sse.streaming","PASS" if ok else "FAIL",f"status={resp.status}; chunks={len(chunks)}; bytes={len(joined)}",
            {"chunk_times":[round(x[0],3) for x in chunks]})

    finally:
        g.shutdown();g.server_close();up1.shutdown();up1.server_close()

    # Retry/failover safety: first target 503, second 200.
    bad,_=serve_http(True);good,_=serve_http(False)
    trace2=temp/"retry-trace.jsonl"
    cfg2=dict(cfg)
    cfg2["targets"]=[
        {"id":"bad","account":"bad@example.com","base_url":f"http://127.0.0.1:{bad.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]},
        {"id":"good","account":"good@example.com","base_url":f"http://127.0.0.1:{good.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]},
    ]
    g2,_=gateway_server(gw,cfg2,keys,trace2);gp2=g2.server_address[1]
    try:
        status,hs,_=http_req(gp2,"POST","/retry?model=gpt-5.6",key,{"model":"gpt-5.6"})
        ok=status==503 and hs.get("X-HMS-Attempts")=="1"
        add("post.no_idempotency_no_replay","PASS" if ok else "FAIL",f"status={status}; attempts={hs.get('X-HMS-Attempts')}")
        # Fresh gateway to guarantee first target is bad again.
    finally:
        g2.shutdown();g2.server_close()

    g3,_=gateway_server(gw,cfg2,keys,temp/"retry-idem-trace.jsonl");gp3=g3.server_address[1]
    try:
        status,hs,_=http_req(gp3,"POST","/retry?model=gpt-5.6",key,{"model":"gpt-5.6"},{"Idempotency-Key":"idem-1"})
        ok=status==200 and hs.get("X-HMS-Attempts")=="2"
        add("post.idempotent_failover","PASS" if ok else "FAIL",f"status={status}; attempts={hs.get('X-HMS-Attempts')}")
    finally:
        g3.shutdown();g3.server_close();bad.shutdown();bad.server_close();good.shutdown();good.server_close()

    # WebSocket tunnel.
    ws,_=serve_ws()
    cfgws=dict(cfg)
    cfgws["targets"]=[{"id":"ws","account":"ws@example.com","base_url":f"http://127.0.0.1:{ws.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]}]
    gwss,_=gateway_server(gw,cfgws,keys,temp/"ws-trace.jsonl");wp=gwss.server_address[1]
    try:
        sock=socket.create_connection(("127.0.0.1",wp),timeout=5)
        wkey=base64.b64encode(os.urandom(16)).decode()
        request=(
            f"GET /v1/realtime?model=gpt-5.6 HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{wp}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {wkey}\r\nSec-WebSocket-Version: 13\r\n"
            f"Authorization: Bearer {key}\r\nX-Session-ID: ws-session\r\n\r\n"
        ).encode()
        sock.sendall(request)
        head=read_head(sock)
        ok_head=b" 101 " in head.split(b"\r\n",1)[0] and b"X-HMS-Selected-Target:" in head
        sock.sendall(ws_frame("hello-v21",1,masked=True))
        frame=ws_read_frame(sock)
        ok_frame=frame and frame[1]==b"hello-v21"
        add("websocket.relay","PASS" if (ok_head and ok_frame) else "FAIL",
            f"handshake={ok_head}; echo={ok_frame}")
        try:sock.close()
        except:pass
    finally:
        gwss.shutdown();gwss.server_close();ws.shutdown();ws.server_close()

    # WebSocket model-hint safety.
    ws2,_=serve_ws()
    cfg_hint=dict(cfg)
    cfg_hint["targets"]=[{"id":"ws","account":"ws@example.com","base_url":f"http://127.0.0.1:{ws2.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]}]
    gh,_=gateway_server(gw,cfg_hint,keys,temp/"ws-hint-trace.jsonl");hp=gh.server_address[1]
    try:
        sock=socket.create_connection(("127.0.0.1",hp),timeout=5)
        wkey=base64.b64encode(os.urandom(16)).decode()
        req=(
            f"GET /v1/realtime HTTP/1.1\r\nHost: 127.0.0.1:{hp}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {wkey}\r\nSec-WebSocket-Version: 13\r\n"
            f"Authorization: Bearer {key}\r\n\r\n"
        ).encode()
        sock.sendall(req);head=read_head(sock)
        ok=b" 400 " in head.split(b"\r\n",1)[0]
        add("websocket.model_hint_policy","PASS" if ok else "FAIL",f"blocked_without_model={ok}")
        sock.close()
    finally:
        gh.shutdown();gh.server_close();ws2.shutdown();ws2.server_close()

    # WebSocket handshake failover: 503 target -> 101 target.
    reject,_=serve_ws(WsRejectHandler);accept,_=serve_ws(WsHandler)
    cfg_fo=dict(cfg)
    cfg_fo["targets"]=[
        {"id":"reject","account":"reject@example.com","base_url":f"http://127.0.0.1:{reject.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]},
        {"id":"accept","account":"accept@example.com","base_url":f"http://127.0.0.1:{accept.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["gpt-*"],"model_deny":[]},
    ]
    gf,_=gateway_server(gw,cfg_fo,keys,temp/"ws-failover-trace.jsonl");fp=gf.server_address[1]
    try:
        sock=socket.create_connection(("127.0.0.1",fp),timeout=5)
        wkey=base64.b64encode(os.urandom(16)).decode()
        req=(
            f"GET /v1/realtime?model=gpt-5.6 HTTP/1.1\r\nHost: 127.0.0.1:{fp}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {wkey}\r\nSec-WebSocket-Version: 13\r\n"
            f"Authorization: Bearer {key}\r\n\r\n"
        ).encode()
        sock.sendall(req);head=read_head(sock)
        ok_head=(b" 101 " in head.split(b"\r\n",1)[0] and b"X-HMS-Attempts: 2" in head)
        sock.sendall(ws_frame("failover-ok",1,masked=True))
        frame=ws_read_frame(sock)
        ok_frame=frame and frame[1]==b"failover-ok"
        add("websocket.handshake_failover","PASS" if (ok_head and ok_frame) else "FAIL",
            f"attempts_2={ok_head}; echo={ok_frame}")
        sock.close()
    finally:
        gf.shutdown();gf.server_close();reject.shutdown();reject.server_close();accept.shutdown();accept.server_close()

    # Trace privacy and protocol telemetry.
    alltrace="\n".join(p.read_text("utf-8",errors="replace") for p in temp.glob("*trace.jsonl") if p.exists())
    privacy=("SECRET_BODY" not in alltrace and key not in alltrace)
    telemetry=('"protocol":"sse"' in alltrace and '"protocol":"websocket"' in alltrace and '"ttft_ms"' in alltrace)
    add("trace.privacy","PASS" if privacy else "FAIL","body/key absent from trace")
    add("trace.protocol_telemetry","PASS" if telemetry else "FAIL","SSE/WS/TTFT trace markers present")

    fail=sum(1 for x in results if x["status"]=="FAIL")
    return {
        "version":"21.0","generated_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "verdict":"PASS" if fail==0 else "FAIL",
        "summary":{"pass":sum(1 for x in results if x["status"]=="PASS"),"fail":fail,"total":len(results)},
        "tests":results
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--temp",required=True)
    ap.add_argument("--output")
    a=ap.parse_args()
    try:
        data=run(Path(a.root),Path(a.temp))
        out={"ok":data["verdict"]=="PASS","data":data}
    except Exception as e:
        out={"ok":False,"error":repr(e)}
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt)
    return 0 if out.get("ok") else 2

if __name__=="__main__":
    raise SystemExit(main())
