#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, ipaddress, json, os, socket, ssl, struct, time, urllib.parse
from pathlib import Path
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

def atomic(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),"utf-8")
    os.replace(tmp,p)

def load_state(path):
    p=Path(path)
    if not p.exists(): return {"version":23,"profiles":{}}
    try:d=json.loads(p.read_text("utf-8-sig"))
    except:d={"version":23,"profiles":{}}
    d.setdefault("version",23);d.setdefault("profiles",{})
    return d

def recv_until(sock,marker=b"\r\n\r\n",limit=262144):
    data=b""
    while marker not in data:
        c=sock.recv(4096)
        if not c:break
        data+=c
        if len(data)>limit:raise RuntimeError("HTTP headers too large")
    return data

def http_connect(proxy_host,proxy_port,dest_host,dest_port,username="",password="",tls_proxy=False,timeout=10):
    raw=socket.create_connection((proxy_host,proxy_port),timeout=timeout)
    sock=raw
    if tls_proxy:
        sock=ssl.create_default_context().wrap_socket(raw,server_hostname=proxy_host)
    auth=""
    if username:
        token=base64.b64encode(f"{username}:{password}".encode()).decode()
        auth=f"Proxy-Authorization: Basic {token}\r\n"
    req=(f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\n"
         f"Host: {dest_host}:{dest_port}\r\n"
         f"Proxy-Connection: Keep-Alive\r\n{auth}\r\n").encode("latin1")
    sock.sendall(req)
    head=recv_until(sock)
    first=head.split(b"\r\n",1)[0].decode("latin1","replace")
    try:code=int(first.split()[1])
    except:code=0
    if code!=200:
        sock.close();raise RuntimeError(f"proxy CONNECT status {code}")
    return sock

def socks5_connect(proxy_host,proxy_port,dest_host,dest_port,username="",password="",timeout=10):
    sock=socket.create_connection((proxy_host,proxy_port),timeout=timeout)
    methods=[0]
    if username:methods.append(2)
    sock.sendall(bytes([5,len(methods),*methods]))
    r=sock.recv(2)
    if len(r)!=2 or r[0]!=5 or r[1]==255:
        sock.close();raise RuntimeError("SOCKS5 method negotiation failed")
    if r[1]==2:
        ub=username.encode();pb=password.encode()
        if len(ub)>255 or len(pb)>255:raise RuntimeError("SOCKS5 credential too long")
        sock.sendall(bytes([1,len(ub)])+ub+bytes([len(pb)])+pb)
        a=sock.recv(2)
        if len(a)!=2 or a[1]!=0:
            sock.close();raise RuntimeError("SOCKS5 authentication failed")
    hb=dest_host.encode("idna")
    sock.sendall(bytes([5,1,0,3,len(hb)])+hb+struct.pack("!H",dest_port))
    h=sock.recv(4)
    if len(h)!=4 or h[0]!=5 or h[1]!=0:
        sock.close();raise RuntimeError(f"SOCKS5 connect failed code={h[1] if len(h)>1 else 'short'}")
    atyp=h[3]
    if atyp==1:sock.recv(4)
    elif atyp==3:
        n=sock.recv(1)
        if n:sock.recv(n[0])
    elif atyp==4:sock.recv(16)
    sock.recv(2)
    return sock

def parse_http_response(raw_head,body,sock):
    head=raw_head.decode("latin1","replace")
    lines=head.split("\r\n")
    first=lines[0]
    try:status=int(first.split()[1])
    except:status=0
    headers={}
    for line in lines[1:]:
        if ":" in line:
            k,v=line.split(":",1);headers[k.strip().lower()]=v.strip()
    if status!=200:raise RuntimeError(f"egress endpoint HTTP {status}")
    if headers.get("transfer-encoding","").lower()=="chunked":
        data=body
        out=b""
        while True:
            while b"\r\n" not in data:
                c=sock.recv(4096)
                if not c:break
                data+=c
            line,data=data.split(b"\r\n",1)
            n=int(line.split(b";",1)[0],16)
            if n==0:break
            while len(data)<n+2:
                data+=sock.recv(4096)
            out+=data[:n];data=data[n+2:]
        return out
    if "content-length" in headers:
        n=int(headers["content-length"])
        data=body
        while len(data)<n:
            c=sock.recv(min(65536,n-len(data)))
            if not c:break
            data+=c
        return data[:n]
    data=body
    while True:
        try:c=sock.recv(65536)
        except socket.timeout:break
        if not c:break
        data+=c
    return data

def fetch_via_proxy(proxy_scheme,proxy_host,proxy_port,username,password,url,timeout=10):
    u=urllib.parse.urlparse(url)
    if u.scheme not in ("http","https"):raise ValueError("egress URL must be http/https")
    host=u.hostname
    port=u.port or (443 if u.scheme=="https" else 80)
    path=u.path or "/"
    if u.query:path+="?"+u.query
    started=time.time()
    sock=None
    try:
        if u.scheme=="http" and proxy_scheme in ("http","https"):
            raw=socket.create_connection((proxy_host,proxy_port),timeout=timeout)
            sock=raw
            if proxy_scheme=="https":
                sock=ssl.create_default_context().wrap_socket(raw,server_hostname=proxy_host)
            auth=""
            if username:
                token=base64.b64encode(f"{username}:{password}".encode()).decode()
                auth=f"Proxy-Authorization: Basic {token}\r\n"
            absolute=url
            req=(f"GET {absolute} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n"
                 f"Accept: application/json,text/plain\r\nUser-Agent: HMS-Proxy-Egress/23\r\n{auth}\r\n").encode("latin1")
            sock.sendall(req)
        else:
            if proxy_scheme=="socks5":
                sock=socks5_connect(proxy_host,proxy_port,host,port,username,password,timeout)
            else:
                sock=http_connect(proxy_host,proxy_port,host,port,username,password,proxy_scheme=="https",timeout)
            if u.scheme=="https":
                sock=ssl.create_default_context().wrap_socket(sock,server_hostname=host)
            req=(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n"
                 f"Accept: application/json,text/plain\r\nUser-Agent: HMS-Proxy-Egress/23\r\n\r\n").encode("latin1")
            sock.sendall(req)
        sock.settimeout(timeout)
        raw=recv_until(sock)
        head,sep,body=raw.partition(b"\r\n\r\n")
        payload=parse_http_response(head+b"\r\n\r\n",body,sock)
        text=payload.decode("utf-8","replace").strip()
        ip=None
        try:
            obj=json.loads(text)
            if isinstance(obj,dict):ip=obj.get("ip")
        except:pass
        ip=str(ip or text).strip()
        addr=ipaddress.ip_address(ip)
        return {
            "status":"PASS","observed_ip":str(addr),"ip_version":addr.version,
            "latency_ms":round((time.time()-started)*1000,2),
            "probe_url":url,"checked_utc":now(),"error":None
        }
    except Exception as e:
        return {
            "status":"FAIL","observed_ip":None,"ip_version":None,
            "latency_ms":round((time.time()-started)*1000,2),
            "probe_url":url,"checked_utc":now(),"error":f"{type(e).__name__}: {e}"
        }
    finally:
        try:
            if sock:sock.close()
        except:pass

def update(path,profile_id,probe,auto_learn=True,require_stable=True):
    state=load_state(path)
    old=state["profiles"].get(profile_id,{})
    expected=old.get("expected_ip")
    drift_count=int(old.get("drift_count") or 0)
    baseline_learned=False
    result=dict(probe)
    if probe.get("status")!="PASS":
        result.update({
            "integrity_status":"FAIL","expected_ip":expected,
            "drift_count":drift_count,"strict_block":True,"baseline_learned":False
        })
    else:
        observed=probe.get("observed_ip")
        if not expected and auto_learn:
            expected=observed;baseline_learned=True
        if not expected:
            integrity="BASELINE_REQUIRED";strict=True
        elif require_stable and observed!=expected:
            integrity="DRIFT";strict=True;drift_count+=1
        else:
            integrity="PASS";strict=False
        result.update({
            "integrity_status":integrity,"expected_ip":expected,
            "drift_count":drift_count,"strict_block":strict,
            "baseline_learned":baseline_learned
        })
    result["updated_utc"]=now()
    state["profiles"][profile_id]=result
    atomic(path,state)
    return result

def set_baseline(path,profile_id,ip):
    addr=str(ipaddress.ip_address(ip))
    state=load_state(path)
    row=state["profiles"].get(profile_id,{})
    row["expected_ip"]=addr
    row["baseline_set_utc"]=now()
    if row.get("observed_ip")==addr and row.get("status")=="PASS":
        row["integrity_status"]="PASS";row["strict_block"]=False
    state["profiles"][profile_id]=row;atomic(path,state);return row

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile-id",required=True)
    ap.add_argument("--scheme",choices=["http","https","socks5"])
    ap.add_argument("--host");ap.add_argument("--port",type=int)
    ap.add_argument("--username",default="");ap.add_argument("--password-env",default="HMS_PROXY_PASSWORD")
    ap.add_argument("--url",default="https://api.ipify.org?format=json")
    ap.add_argument("--timeout",type=float,default=10)
    ap.add_argument("--state",required=True)
    ap.add_argument("--no-auto-learn",action="store_true")
    ap.add_argument("--allow-drift",action="store_true")
    ap.add_argument("--set-baseline")
    a=ap.parse_args()
    if a.set_baseline:
        row=set_baseline(a.state,a.profile_id,a.set_baseline)
        print(json.dumps({"ok":True,"data":row},ensure_ascii=False,indent=2));return 0
    if not a.scheme or not a.host or not a.port:
        raise SystemExit("scheme/host/port required for probe")
    password=os.environ.get(a.password_env,"")
    probe=fetch_via_proxy(a.scheme,a.host,a.port,a.username,password,a.url,a.timeout)
    row=update(a.state,a.profile_id,probe,not a.no_auto_learn,not a.allow_drift)
    ok=(row.get("integrity_status")=="PASS")
    print(json.dumps({"ok":ok,"data":row},ensure_ascii=False,indent=2))
    return 0 if ok else 2

if __name__=="__main__":
    raise SystemExit(main())
