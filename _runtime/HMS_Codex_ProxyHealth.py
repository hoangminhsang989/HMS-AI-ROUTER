#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, json, os, socket, ssl, struct, time
from pathlib import Path
from datetime import datetime, timezone

def now():return datetime.now(timezone.utc).isoformat()

def recv_until(sock,marker=b"\r\n\r\n",limit=65536):
    data=b""
    while marker not in data:
        c=sock.recv(4096)
        if not c:break
        data+=c
        if len(data)>limit:raise RuntimeError("proxy response too large")
    return data

def http_connect(proxy_host,proxy_port,probe_host,probe_port,username="",password="",tls_proxy=False,timeout=8):
    raw=socket.create_connection((proxy_host,proxy_port),timeout=timeout)
    sock=raw
    if tls_proxy:
        ctx=ssl.create_default_context()
        sock=ctx.wrap_socket(raw,server_hostname=proxy_host)
    auth=""
    if username:
        token=base64.b64encode(f"{username}:{password}".encode()).decode()
        auth=f"Proxy-Authorization: Basic {token}\r\n"
    req=(f"CONNECT {probe_host}:{probe_port} HTTP/1.1\r\n"
         f"Host: {probe_host}:{probe_port}\r\n"
         f"Proxy-Connection: Keep-Alive\r\n{auth}\r\n").encode("latin1")
    sock.sendall(req)
    head=recv_until(sock)
    first=head.split(b"\r\n",1)[0].decode("latin1","replace")
    try:code=int(first.split()[1])
    except:code=0
    if code!=200:
        sock.close();raise RuntimeError(f"HTTP proxy CONNECT status {code}")
    return sock

def socks5_connect(proxy_host,proxy_port,probe_host,probe_port,username="",password="",timeout=8):
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
    hostb=probe_host.encode("idna")
    if len(hostb)>255:raise RuntimeError("probe host too long")
    sock.sendall(bytes([5,1,0,3,len(hostb)])+hostb+struct.pack("!H",probe_port))
    h=sock.recv(4)
    if len(h)!=4 or h[0]!=5 or h[1]!=0:
        sock.close();raise RuntimeError(f"SOCKS5 connect failed code={h[1] if len(h)>1 else 'short'}")
    atyp=h[3]
    if atyp==1:sock.recv(4)
    elif atyp==3:
        n=sock.recv(1)[0];sock.recv(n)
    elif atyp==4:sock.recv(16)
    sock.recv(2)
    return sock

def check(scheme,host,port,probe_host,probe_port,username="",password="",timeout=8,tls_probe=True):
    started=time.time()
    sock=None
    try:
        if scheme=="http":
            sock=http_connect(host,port,probe_host,probe_port,username,password,False,timeout)
        elif scheme=="https":
            sock=http_connect(host,port,probe_host,probe_port,username,password,True,timeout)
        elif scheme=="socks5":
            sock=socks5_connect(host,port,probe_host,probe_port,username,password,timeout)
        else:
            raise ValueError("unsupported proxy scheme")
        tunnel_ms=round((time.time()-started)*1000,2)
        tls_ms=None
        if tls_probe:
            t=time.time()
            ctx=ssl.create_default_context()
            ss=ctx.wrap_socket(sock,server_hostname=probe_host)
            tls_ms=round((time.time()-t)*1000,2)
            ss.close();sock=None
        return {"status":"PASS","checked_utc":now(),"latency_ms":tunnel_ms,"tls_ms":tls_ms,
                "probe_host":probe_host,"probe_port":probe_port,"error":None}
    except Exception as e:
        return {"status":"FAIL","checked_utc":now(),"latency_ms":round((time.time()-started)*1000,2),
                "tls_ms":None,"probe_host":probe_host,"probe_port":probe_port,
                "error":f"{type(e).__name__}: {e}"}
    finally:
        try:
            if sock:sock.close()
        except:pass

def update_health(path,profile_id,result):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    try:d=json.loads(p.read_text("utf-8-sig")) if p.exists() else {"version":22,"profiles":{}}
    except:d={"version":22,"profiles":{}}
    d.setdefault("profiles",{})[profile_id]=result
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),"utf-8")
    os.replace(tmp,p)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile-id",required=True)
    ap.add_argument("--scheme",choices=["http","https","socks5"],required=True)
    ap.add_argument("--host",required=True);ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--username",default="")
    ap.add_argument("--password-env",default="HMS_PROXY_PASSWORD")
    ap.add_argument("--probe-host",default="api.openai.com");ap.add_argument("--probe-port",type=int,default=443)
    ap.add_argument("--timeout",type=float,default=8)
    ap.add_argument("--no-tls-probe",action="store_true")
    ap.add_argument("--health",required=True)
    a=ap.parse_args()
    password=os.environ.get(a.password_env,"")
    r=check(a.scheme,a.host,a.port,a.probe_host,a.probe_port,a.username,password,a.timeout,not a.no_tls_probe)
    update_health(a.health,a.profile_id,r)
    print(json.dumps({"ok":r["status"]=="PASS","data":r},ensure_ascii=False,indent=2))
    return 0 if r["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
