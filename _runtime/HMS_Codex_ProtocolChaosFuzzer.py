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
import random
import socket
import socketserver
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

VERSION = "25.56"
SCHEMA_VERSION = 1
PRODUCTION_CLAIM = "NOT_CLAIMED_PROTOCOL_CHAOS_SYNTHETIC_ONLY"
SECRET_MARKERS = (
    "PROTOCHAOS_ACCESS_TOKEN_SECRET",
    "PROTOCHAOS_API_KEY_SECRET",
    "PROTOCHAOS_PROMPT_SECRET",
    "PROTOCHAOS_REQUEST_BODY_SECRET",
    "PROTOCHAOS_RESPONSE_BODY_SECRET",
)


def stable_hash(obj: Any) -> str:
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_gateway(root: Path):
    path=root/"HMS_Codex_SmartGateway.py"
    spec=importlib.util.spec_from_file_location("hms_gateway_v2556_chaos",path)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod


def read_jsonl(path: Path) -> list[dict[str,Any]]:
    rows=[]
    if not path.exists():return rows
    for line in path.read_text("utf-8",errors="replace").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict):rows.append(x)
        except Exception:pass
    return rows


def serve_gateway(gw,root:Path,targets:list[dict[str,Any]],trace:Path,**overrides):
    keyfile=trace.with_name(trace.stem+"-keys.json")
    keys=gw.KeyStore(keyfile);_,key=keys.create("protocol-chaos",["*"],[])
    cfg={
        "strategy":"stable-round-robin","session_affinity":True,"session_ttl_sec":3600,
        "health_fail_threshold":1,"health_cooldown_sec":60,"require_client_key":True,
        "max_failover_attempts":3,"retry_statuses":[408,429,500,502,503,504],
        "require_idempotency_for_post_replay":True,"stream_chunk_bytes":1024,
        "stream_integrity_capture_max_bytes":262144,"upstream_timeout_sec":3,
        "websocket_enabled":True,"websocket_idle_timeout_sec":3,
        "websocket_require_model_hint":True,"expose_selected_target_headers":True,
        "targets":targets,
    }
    cfg.update(overrides)
    srv=gw.ThreadingServer(("127.0.0.1",0),gw.Handler)
    srv.keys=keys;srv.configure_runtime("",cfg,str(trace))
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return srv,key


def http_req(port:int,key:str,method:str,path:str,body:bytes|dict|None=None,headers:dict[str,str]|None=None,timeout=5):
    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=timeout)
    h={"Authorization":"Bearer "+key}
    if headers:h.update(headers)
    raw=body
    if isinstance(body,dict):
        raw=json.dumps(body,separators=(",",":")).encode();h.setdefault("Content-Type","application/json")
    conn.request(method,path,body=raw,headers=h)
    resp=conn.getresponse();data=resp.read();hs=dict(resp.getheaders());status=resp.status
    conn.close();return status,hs,data


class ChaosHTTP(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a):return
    def _close_stream(self,parts:list[bytes],delay=0.003):
        self.send_response(200);self.send_header("Content-Type","text/event-stream")
        self.send_header("Cache-Control","no-cache");self.send_header("Connection","close");self.end_headers()
        for part in parts:
            self.wfile.write(part);self.wfile.flush();time.sleep(delay)
        self.close_connection=True
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0") or 0);_body=self.rfile.read(n) if n else b""
        case=getattr(self.server,"case","complete")
        if case=="complete":
            payload=(
                b'data: {"type":"response.created"}\n\n'
                b'data: {"type":"response.output_text.delta","delta":"H"}\n\n'
                b'data: {"type":"response.output_text.delta","delta":"i"}\n\n'
                b'data: {"type":"response.completed","response":{"usage":{"input_tokens":2,"output_tokens":2}}}\n\n'
            )
            cuts=[1,2,5,9,17,31,47,71,len(payload)]
            parts=[];last=0
            for c in cuts:
                if c>last:parts.append(payload[last:c]);last=c
            return self._close_stream(parts)
        if case=="done":
            return self._close_stream([b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n',b'data: [DONE]\n\n'])
        if case=="truncated":
            return self._close_stream([b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'])
        if case=="duplicate":
            ev=b'data: {"type":"response.output_text.delta","delta":"DUP"}\n\n'
            return self._close_stream([ev,ev,b'data: {"type":"response.completed"}\n\n'])
        if case=="malformed_sse_json":
            return self._close_stream([b'data: {this is not json}\n\n',b'data: {"type":"response.completed"}\n\n'])
        if case=="malformed_error":
            b=b'{"error":BROKEN_JSON'
            self.send_response(400);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if case=="early_eof_length":
            b=b'{"ok":true}'
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)+50));self.send_header("Connection","close");self.end_headers();self.wfile.write(b);self.wfile.flush();self.close_connection=True;return
        status=int(getattr(self.server,"status",200))
        b=json.dumps({"ok":status<400,"status":status}).encode()
        self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        return self.do_POST()


def serve_http(case="complete",status=200):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),ChaosHTTP);srv.daemon_threads=True;srv.case=case;srv.status=status
    threading.Thread(target=srv.serve_forever,daemon=True).start();return srv


def ws_accept(key:str)->str:
    return base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()


def read_head(sock:socket.socket,limit=131072)->bytes:
    data=b""
    while b"\r\n\r\n" not in data and len(data)<limit:
        c=sock.recv(4096)
        if not c:break
        data+=c
    return data


def ws_read_frame(sock:socket.socket):
    h=sock.recv(2)
    if len(h)<2:return None
    b1,b2=h;n=b2&0x7f;masked=bool(b2&0x80)
    if n==126:n=struct.unpack("!H",sock.recv(2))[0]
    elif n==127:n=struct.unpack("!Q",sock.recv(8))[0]
    mask=sock.recv(4) if masked else b"";data=b""
    while len(data)<n:
        c=sock.recv(n-len(data))
        if not c:break
        data+=c
    if masked:data=bytes(x^mask[i%4] for i,x in enumerate(data))
    return b1&0x0f,data


def ws_frame(payload:bytes|str,opcode=1,fin=True,masked=True)->bytes:
    if isinstance(payload,str):payload=payload.encode()
    b1=(0x80 if fin else 0)|opcode;n=len(payload);maskbit=0x80 if masked else 0
    if n<126:head=bytes([b1,maskbit|n])
    elif n<65536:head=bytes([b1,maskbit|126])+struct.pack("!H",n)
    else:head=bytes([b1,maskbit|127])+struct.pack("!Q",n)
    if not masked:return head+payload
    mask=b"HMS!";enc=bytes(x^mask[i%4] for i,x in enumerate(payload));return head+mask+enc


class ChaosWS(socketserver.BaseRequestHandler):
    def handle(self):
        data=read_head(self.request);text=data.decode("latin1","replace");key=""
        for line in text.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):key=line.split(":",1)[1].strip()
        mode=getattr(self.server,"mode","valid")
        if mode=="partial_head":
            self.request.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n");return
        accept=ws_accept(key)
        if mode=="wrong_accept":accept="WRONG-ACCEPT"
        lines=["HTTP/1.1 101 Switching Protocols","Upgrade: websocket","Connection: Upgrade"]
        if mode!="missing_accept":lines.append("Sec-WebSocket-Accept: "+accept)
        if mode=="missing_upgrade":lines=[x for x in lines if not x.lower().startswith("upgrade:")]
        self.request.sendall(("\r\n".join(lines)+"\r\n\r\n").encode())
        if mode!="valid":return
        frame=ws_read_frame(self.request)
        if frame:
            op,payload=frame
            # Echo as two fragments to prove the gateway tunnels frames without reinterpretation.
            split=max(1,len(payload)//2)
            self.request.sendall(ws_frame(payload[:split],opcode=op,fin=False,masked=False))
            self.request.sendall(ws_frame(payload[split:],opcode=0,fin=True,masked=False))


def serve_ws(mode="valid"):
    srv=socketserver.ThreadingTCPServer(("127.0.0.1",0),ChaosWS);srv.daemon_threads=True;srv.mode=mode
    threading.Thread(target=srv.serve_forever,daemon=True).start();return srv


def ws_client(port:int,key:str,model="gpt-5.6"):
    s=socket.create_connection(("127.0.0.1",port),timeout=5);s.settimeout(5)
    wkey=base64.b64encode(b"0123456789abcdef").decode()
    req=(
        f"GET /ws?model={model} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {wkey}\r\nSec-WebSocket-Version: 13\r\nAuthorization: Bearer {key}\r\n\r\n"
    ).encode();s.sendall(req);head=read_head(s)
    return s,head


def target(srv,id):
    return {"id":id,"account":id+"@synthetic.invalid","base_url":f"http://127.0.0.1:{srv.server_address[1]}","priority":10,"weight":1,"enabled":True,"model_allow":["*"],"model_deny":[]}


def structural_fuzz(gw,seed:int,cases:int):
    rng=random.Random(seed);counts={"sse":0,"ws":0,"json":0};fails=[];fingerprints=[]
    for i in range(cases):
        kind=i%3
        if kind==0:
            complete=(i%4)!=0;client_abort=(i%17)==0
            payload=(b'data: {"type":"response.output_text.delta","delta":"x"}\n\n'+(b'data: {"type":"response.completed"}\n\n' if complete else b''))
            probe=gw.SSEIntegrityProbe("/v1/responses?x=1","text/event-stream",8192)
            pos=0
            while pos<len(payload):
                n=rng.randint(1,11);probe.feed(payload[pos:pos+n]);pos+=n
            got=probe.finish(None,client_abort)
            expected="CLIENT_ABORT" if client_abort else ("COMPLETE" if complete else "TRUNCATED_EOF")
            if got.get("status")!=expected:fails.append(f"sse:{i}:{got.get('status')}!={expected}")
            counts["sse"]+=1;fingerprints.append(("sse",got.get("status"),got.get("chunks_seen")))
        elif kind==1:
            key=base64.b64encode(hashlib.sha256(f"{seed}:{i}".encode()).digest()[:16]).decode()
            accept=ws_accept(key)
            variants=[
                (f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode(),True),
                (b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n",False),
                (f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: WRONG\r\n\r\n".encode(),False),
                (f"HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode(),False),
                (b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n",False),
            ]
            raw,expected=variants[(i//3)%len(variants)];ok,reason=gw.validate_websocket_upgrade_head(raw,key)
            if bool(ok)!=expected:fails.append(f"ws:{i}:{reason}:{ok}!={expected}")
            counts["ws"]+=1;fingerprints.append(("ws",bool(ok),reason))
        else:
            variants=[b"{",b"[]",b'\xff\xfe',b'{"model":"gpt-5.6","stream":true}',b'{"tools":[{"type":"mcp"}]}',b'null']
            body=variants[(i//3)%len(variants)]
            try:
                model=gw.extract_model(body,"/v1/responses",{})
                features=gw.compatibility_features(body,"/v1/responses",{})
                rewritten=gw.rewrite_json_model(body,"gpt-5.6","gpt-5.6-sol")
                if not isinstance(model,str) or not isinstance(features,list) or not isinstance(rewritten,(bytes,bytearray)):
                    fails.append(f"json:{i}:type")
                fingerprints.append(("json",model,tuple(features),len(rewritten)));counts["json"]+=1
            except Exception as exc:fails.append(f"json:{i}:{type(exc).__name__}")
    return {"cases":cases,"counts":counts,"failures":fails,"trace_hash":stable_hash(fingerprints)}


def run(root:Path,seed:int=2556,cases:int=300)->dict[str,Any]:
    gw=load_gateway(root);tests=[];resources=[]
    def add(name,ok,detail="",extra=None):tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail,"extra":extra or {}})
    structural=structural_fuzz(gw,seed,cases)
    add("fuzz.structural_all_cases",not structural["failures"],f"cases={cases}; failures={len(structural['failures'])}",{"counts":structural["counts"],"trace_hash":structural["trace_hash"]})
    add("fuzz.sse_coverage",structural["counts"]["sse"]>=cases//4,str(structural["counts"]))
    add("fuzz.websocket_coverage",structural["counts"]["ws"]>=cases//4,str(structural["counts"]))
    add("fuzz.json_coverage",structural["counts"]["json"]>=cases//4,str(structural["counts"]))

    with tempfile.TemporaryDirectory(prefix="hms-v2556-chaos-") as td:
        temp=Path(td)
        # Complete split SSE and usage/terminal integrity.
        up=serve_http("complete");resources.append(up);trace=temp/"complete.jsonl"
        g,key=serve_gateway(gw,root,[target(up,"complete")],trace);resources.append(g)
        st,hs,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6","input":"PROTOCHAOS_PROMPT_SECRET","stream":True},{"Accept":"text/event-stream","Idempotency-Key":"complete"})
        rows=read_jsonl(trace);last=rows[-1] if rows else {}
        add("sse.split_partial_frames_preserved",st==200 and b"response.completed" in raw and b'\"delta\":\"H\"' in raw,f"status={st}; bytes={len(raw)}")
        add("sse.complete_integrity",last.get("stream_integrity")=="COMPLETE" and last.get("stream_terminal_seen") is True,str(last.get("stream_integrity")))
        add("sse.usage_capture_survives_splits",last.get("input_tokens")==2 and last.get("output_tokens")==2,f"usage={last.get('input_tokens')}/{last.get('output_tokens')}")
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # Truncated SSE must not be replayed but must penalize upstream for next request.
        up=serve_http("truncated");trace=temp/"truncated.jsonl";g,key=serve_gateway(gw,root,[target(up,"truncated")],trace)
        st,_,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6","stream":True},{"Accept":"text/event-stream","Idempotency-Key":"trunc"})
        rows=read_jsonl(trace);last=rows[-1] if rows else {};health=g.router.health.get("truncated")
        add("sse.truncated_partial_still_passthrough",st==200 and b"partial" in raw and b"response.completed" not in raw,f"status={st}; bytes={len(raw)}")
        add("sse.truncated_detected",last.get("stream_integrity")=="TRUNCATED_EOF" and last.get("stream_terminal_seen") is False,str(last.get("stream_integrity")))
        add("sse.truncated_health_penalty",bool(health and health.last_status==599 and health.cooldown_until>time.time()),f"last={getattr(health,'last_status',None)}")
        add("sse.no_midstream_replay",int(last.get("attempt_count") or 0)==1,f"attempts={last.get('attempt_count')}")
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # DONE terminator accepted (chat-style compatibility).
        up=serve_http("done");trace=temp/"done.jsonl";g,key=serve_gateway(gw,root,[target(up,"done")],trace)
        st,_,raw=http_req(g.server_address[1],key,"POST","/v1/chat/completions",{"model":"gpt-5.6","stream":True},{"Accept":"text/event-stream","Idempotency-Key":"done"})
        last=(read_jsonl(trace) or [{}])[-1]
        add("sse.done_terminal_accepted",st==200 and b"[DONE]" in raw and last.get("stream_integrity")=="COMPLETE",str(last.get("stream_integrity")))
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # Duplicate/malformed SSE is transparent; gateway never de-dupes or parses prompt content.
        up=serve_http("duplicate");trace=temp/"dup.jsonl";g,key=serve_gateway(gw,root,[target(up,"dup")],trace)
        st,_,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6","stream":True},{"Accept":"text/event-stream","Idempotency-Key":"dup"})
        add("sse.duplicate_event_preserved",st==200 and raw.count(b"DUP")==2,f"dup_count={raw.count(b'DUP')}")
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        up=serve_http("malformed_sse_json");trace=temp/"bad-sse.jsonl";g,key=serve_gateway(gw,root,[target(up,"bad-sse")],trace)
        st,_,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6","stream":True},{"Accept":"text/event-stream","Idempotency-Key":"bad-sse"})
        last=(read_jsonl(trace) or [{}])[-1]
        add("sse.malformed_data_passthrough",st==200 and b"this is not json" in raw and last.get("stream_integrity")=="COMPLETE",f"status={st}")
        add("sse.malformed_usage_no_crash",last.get("usage_source") in ("NO_DATA","SSE_CAPTURE"),str(last.get("usage_source")))
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # Malformed upstream JSON error stays transparent, not gateway-crashing/secret-logging.
        up=serve_http("malformed_error");trace=temp/"bad-error.jsonl";g,key=serve_gateway(gw,root,[target(up,"bad-error")],trace)
        st,_,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6","input":"PROTOCHAOS_REQUEST_BODY_SECRET"})
        add("json.malformed_upstream_error_passthrough",st==400 and raw==b'{"error":BROKEN_JSON',f"status={st}; bytes={len(raw)}")
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # Content-Length early EOF is an upstream read error and must affect health, not crash the server.
        up=serve_http("early_eof_length");trace=temp/"eof.jsonl";g,key=serve_gateway(gw,root,[target(up,"eof")],trace)
        client_failed=False
        try:_=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6"})
        except Exception:client_failed=True
        rows=read_jsonl(trace);last=rows[-1] if rows else {};health=g.router.health.get("eof")
        add("http.early_eof_contained",bool(last),f"client_exception={client_failed}; trace={bool(last)}")
        add("http.early_eof_health_penalty",bool(health and health.last_status==599),f"last={getattr(health,'last_status',None)}")
        add("http.early_eof_error_metadata_only",last.get("error_class") in ("IncompleteRead","RemoteDisconnected","ConnectionResetError","IncompleteBody"),str(last.get("error_class")))
        g.shutdown();g.server_close();up.shutdown();up.server_close()

        # Retry sequence budget and idempotency boundary.
        s1=serve_http("status",503);s2=serve_http("status",429);s3=serve_http("status",200)
        def ranked(srv,ident,priority):
            row=target(srv,ident);row["priority"]=priority;return row
        trace=temp/"retry3.jsonl";g,key=serve_gateway(gw,root,[ranked(s1,"r1",30),ranked(s2,"r2",20),ranked(s3,"r3",10)],trace,max_failover_attempts=3,health_fail_threshold=99)
        st,hs,raw=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6"},{"Idempotency-Key":"retry-3"})
        add("retry.sequence_503_429_200",st==200 and hs.get("X-HMS-Attempts")=="3",f"status={st}; attempts={hs.get('X-HMS-Attempts')}")
        for _ in range(20):
            rows=read_jsonl(trace)
            if rows:break
            time.sleep(0.01)
        last=(read_jsonl(trace) or [{}])[-1]
        add("retry.attempt_budget_exact",last.get("attempt_count")==3 and [x.get("status") for x in last.get("attempts",[])]==[503,429,200],str([x.get('status') for x in last.get('attempts',[])]))
        g.shutdown();g.server_close()
        trace=temp/"retry2.jsonl";g,key=serve_gateway(gw,root,[ranked(s1,"b1",30),ranked(s2,"b2",20),ranked(s3,"b3",10)],trace,max_failover_attempts=2,health_fail_threshold=99)
        st,hs,_=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6"},{"Idempotency-Key":"retry-2"})
        add("retry.budget_never_exceeded",st==429 and hs.get("X-HMS-Attempts")=="2",f"status={st}; attempts={hs.get('X-HMS-Attempts')}")
        g.shutdown();g.server_close()
        trace=temp/"no-replay.jsonl";g,key=serve_gateway(gw,root,[ranked(s1,"n1",30),ranked(s3,"n2",10)],trace,max_failover_attempts=3,health_fail_threshold=99)
        st,hs,_=http_req(g.server_address[1],key,"POST","/v1/responses",{"model":"gpt-5.6"})
        add("retry.post_without_idempotency_not_replayed",st==503 and hs.get("X-HMS-Attempts")=="1",f"status={st}; attempts={hs.get('X-HMS-Attempts')}")
        g.shutdown();g.server_close()
        for x in (s1,s2,s3):x.shutdown();x.server_close()

        # WebSocket malformed 101 must be rejected and fail over to a valid handshake.
        for mode in ("missing_accept","wrong_accept","missing_upgrade","partial_head"):
            bad=serve_ws(mode);good=serve_ws("valid");trace=temp/f"ws-{mode}.jsonl"
            g,key=serve_gateway(gw,root,[target(bad,"wsbad"),target(good,"wsgood")],trace,max_failover_attempts=2,health_fail_threshold=99)
            sock,head=ws_client(g.server_address[1],key)
            ok_head=b"101 Switching Protocols" in head and b"X-HMS-Attempts: 2" in head
            add(f"websocket.malformed_101_failover.{mode}",ok_head,f"head={head.splitlines()[0] if head else b''!r}")
            if ok_head:
                sock.sendall(ws_frame("fragment-me",opcode=1,fin=True,masked=True))
                f1=ws_read_frame(sock);f2=ws_read_frame(sock)
                ok_frag=bool(f1 and f2 and f1[1]+f2[1]==b"fragment-me")
                add(f"websocket.fragment_tunnel.{mode}",ok_frag,f"frames={bool(f1)}/{bool(f2)}")
            try:sock.close()
            except:pass
            for _ in range(20):
                time.sleep(0.01)
                if read_jsonl(trace):break
            rows=read_jsonl(trace);attempts=[]
            for row in rows:
                if row.get("protocol")=="websocket":attempts=row.get("attempts") or []
            add(f"websocket.malformed_attempt_metadata.{mode}",any(x.get("result")=="MALFORMED_UPGRADE" for x in attempts),str([x.get('result') for x in attempts]))
            g.shutdown();g.server_close();bad.shutdown();bad.server_close();good.shutdown();good.server_close()

        # Raw chunked request parser mutations.
        good=serve_http("status",200);trace=temp/"chunked.jsonl";g,key=serve_gateway(gw,root,[target(good,"chunk")],trace,max_request_bytes=32)
        def raw_chunked(chunks:bytes):
            s=socket.create_connection(("127.0.0.1",g.server_address[1]),timeout=3);s.settimeout(3)
            req=(f"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {key}\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n").encode()+chunks
            s.sendall(req)
            try:s.shutdown(socket.SHUT_WR)
            except:pass
            data=b""
            try:
                while True:
                    c=s.recv(4096)
                    if not c:break
                    data+=c
            except:pass
            s.close();return data
        resp=raw_chunked(b"ZZ\r\n");add("chunked.invalid_hex_400",b"400" in resp.split(b"\r\n",1)[0] and b"CHUNKED_BODY_INVALID_SIZE" in resp,f"bytes={len(resp)}")
        resp=raw_chunked(b"5\r\nabc");add("chunked.truncated_400",b"400" in resp.split(b"\r\n",1)[0] and b"CHUNKED_BODY_TRUNCATED" in resp,f"bytes={len(resp)}")
        resp=raw_chunked(b"3\r\nabcXX0\r\n\r\n");add("chunked.bad_terminator_400",b"400" in resp.split(b"\r\n",1)[0] and b"CHUNKED_BODY_INVALID_TERMINATOR" in resp,f"bytes={len(resp)}")
        resp=raw_chunked(b"21\r\n"+b"x"*33+b"\r\n0\r\n\r\n");add("chunked.over_limit_413",b"413" in resp.split(b"\r\n",1)[0] and b"REQUEST_BODY_TOO_LARGE" in resp,f"bytes={len(resp)}")
        g.shutdown();g.server_close();good.shutdown();good.server_close()

        # Trace privacy: no request/prompt/API key plaintext survives any network scenario.
        trace_bytes=b"".join(p.read_bytes() for p in temp.glob("*.jsonl"))
        add("privacy.no_secret_markers_in_trace",not any(x.encode() in trace_bytes for x in SECRET_MARKERS),f"trace_bytes={len(trace_bytes)}")
        add("privacy.no_authorization_header_in_trace",b"Authorization: Bearer" not in trace_bytes and b"hms_" not in trace_bytes,f"trace_bytes={len(trace_bytes)}")
        add("privacy.request_body_logged_false",b'"request_body_logged":true' not in trace_bytes,"all traces metadata-only")

    failed=[x for x in tests if x["status"]=="FAIL"]
    return {
        "product":"HMS-AI-ROUTER","version":VERSION,"schema_version":SCHEMA_VERSION,
        "suite":"PROTOCOL_CHAOS_API_COMPATIBILITY_FUZZER",
        "verdict":"PASS_PROTOCOL_CHAOS_API_COMPATIBILITY_FUZZER_V25_56" if not failed else "FAIL_PROTOCOL_CHAOS_API_COMPATIBILITY_FUZZER_V25_56",
        "summary":{"pass":len(tests)-len(failed),"fail":len(failed),"total":len(tests),"fuzz_cases":cases,"seed":seed,
                   "fuzz_trace_hash":structural["trace_hash"]},
        "tests":tests,
        "safety":{
            "real_codex_called":False,"real_quota_consumed":False,"real_auth_read_or_mutated":False,
            "request_or_prompt_persisted":False,"production_certification":PRODUCTION_CLAIM,
            "partial_stream_replay":"FORBIDDEN","malformed_ws_101":"FAILOVER_BEFORE_RELAY"
        },
        "claim_boundary":"Synthetic protocol-chaos evidence only; cannot emit PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED.",
    }


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--root",default=str(Path(__file__).resolve().parent));ap.add_argument("--seed",type=int,default=2556);ap.add_argument("--cases",type=int,default=300);ap.add_argument("--output")
    a=ap.parse_args();out=run(Path(a.root).resolve(),a.seed,a.cases);text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text);return 0 if str(out.get("verdict","")).startswith("PASS") else 2

if __name__=="__main__":raise SystemExit(main())
