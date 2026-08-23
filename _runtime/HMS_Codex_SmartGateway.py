#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import hmac
import http.client
import http.server
import json
import os
import secrets
import random
import select
import socket
import socketserver
import ssl
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HOP = {
    "connection","keep-alive","proxy-authenticate","proxy-authorization",
    "te","trailers","transfer-encoding","upgrade"
}
RETRY_DEFAULT={429,500,502,503,504}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def loadj(path,default):
    p=Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except Exception:
        return default

def append_jsonl(path,obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:
        f.write(json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n")

def safe_id(v):
    return hashlib.sha256(str(v).encode()).hexdigest()[:12]

def key_digest(salt,key):
    return hashlib.sha256((salt+":"+key).encode()).hexdigest()

def model_ok(rec,model):
    allow=rec.get("model_allow") or ["*"]
    deny=rec.get("model_deny") or []
    return any(fnmatch.fnmatch(model,x) for x in allow) and not any(fnmatch.fnmatch(model,x) for x in deny)

def canonical_model_for_client(client,model):
    model=str(model or "*")
    prefix=str((client or {}).get("model_prefix") or "")
    if prefix and model.startswith(prefix):
        stripped=model[len(prefix):]
        return stripped or model
    return model

def exposed_model_for_client(client,model):
    prefix=str((client or {}).get("model_prefix") or "")
    return prefix+str(model) if prefix else str(model)

def target_client_ok(client,target):
    client=client or {}
    tid=str(target.get("id") or "")
    allow=client.get("target_allow") or ["*"]
    deny=client.get("target_deny") or []
    return any(fnmatch.fnmatch(tid,x) for x in allow) and not any(fnmatch.fnmatch(tid,x) for x in deny)

def parse_utc_ts(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp()
    except:return None

def quota_remaining(target):
    vals=[]
    for k in ("quota_hourly_pct","quota_weekly_pct","quota_remaining_pct"):
        try:
            if target.get(k) is not None:vals.append(float(target.get(k)))
        except:pass
    return min(vals) if vals else None

def quota_evidence_fresh(target,max_age):
    ts=parse_utc_ts(target.get("quota_checked_utc"))
    return bool(ts and 0 <= time.time()-ts <= max(1,int(max_age)))

def effective_priority(target,client):
    ov=(client or {}).get("target_priority") or {}
    try:return int(ov.get(str(target.get("id")),target.get("priority",0)))
    except:return int(target.get("priority",0) or 0)

def effective_weight(target,client):
    ov=(client or {}).get("target_weight") or {}
    try:return max(1,int(ov.get(str(target.get("id")),target.get("weight",1))))
    except:return max(1,int(target.get("weight",1) or 1))

def rewrite_json_model(body,old_model,new_model):
    if not body or old_model==new_model:return body
    try:
        obj=json.loads(body)
        if isinstance(obj,dict) and str(obj.get("model") or "")==str(old_model):
            obj["model"]=new_model
            return json.dumps(obj,separators=(",",":"),ensure_ascii=False).encode()
    except:pass
    return body

def rewrite_path_model(path,old_model,new_model):
    if old_model==new_model:return path
    try:
        u=urllib.parse.urlsplit(path)
        q=urllib.parse.parse_qs(u.query,keep_blank_values=True)
        if q.get("model") and q["model"][0]==old_model:
            q["model"]=[new_model]
            return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(q,doseq=True),u.fragment))
    except:pass
    return path


class SSEIntegrityProbe:
    """Bounded metadata-only integrity probe for OpenAI-compatible SSE streams.

    It never stores request/prompt data. It only keeps a small rolling slice of the
    upstream response to detect a terminal event on known OpenAI streaming paths.
    """
    OPENAI_STREAM_PATHS={"/v1/responses","/v1/chat/completions"}
    def __init__(self,path,content_type,max_bytes=262144):
        self.path=str(path or "").split("?",1)[0]
        self.content_type=str(content_type or "").lower()
        self.max_bytes=max(4096,int(max_bytes))
        self.tail=bytearray()
        self.bytes_seen=0
        self.chunks_seen=0
        self.enforced=("text/event-stream" in self.content_type and self.path in self.OPENAI_STREAM_PATHS)
    def feed(self,chunk):
        if not chunk:return
        self.bytes_seen+=len(chunk);self.chunks_seen+=1
        if not self.enforced:return
        self.tail.extend(chunk)
        if len(self.tail)>self.max_bytes:
            del self.tail[:-self.max_bytes]
    def terminal_seen(self):
        if not self.enforced:return False
        raw=bytes(self.tail).lower()
        return b"response.completed" in raw or b"data: [done]" in raw
    def finish(self,upstream_error=None,client_aborted=False):
        if not self.enforced:
            status="NOT_APPLICABLE"
        elif client_aborted:
            status="CLIENT_ABORT"
        elif upstream_error:
            status="UPSTREAM_READ_ERROR"
        elif self.terminal_seen():
            status="COMPLETE"
        else:
            status="TRUNCATED_EOF"
        return {
            "enforced":self.enforced,"status":status,"terminal_seen":self.terminal_seen(),
            "bytes_seen":self.bytes_seen,"chunks_seen":self.chunks_seen
        }

def validate_websocket_upgrade_head(head,client_key=""):
    """Validate a server WebSocket 101 response before exposing it to the client."""
    try:
        raw=bytes(head or b"")
        if b"\r\n\r\n" not in raw:
            return False,"INCOMPLETE_HTTP_HEAD"
        text=raw.decode("latin1","replace")
        lines=text.split("\r\n")
        first=lines[0].split()
        if len(first)<2 or int(first[1])!=101:
            return False,"STATUS_NOT_101"
        headers={}
        for line in lines[1:]:
            if not line or ":" not in line:continue
            k,v=line.split(":",1)
            headers.setdefault(k.strip().lower(),[]).append(v.strip())
        upgrade=",".join(headers.get("upgrade",[])).lower()
        connection=",".join(headers.get("connection",[])).lower()
        accept=(headers.get("sec-websocket-accept") or [""])[-1].strip()
        if "websocket" not in [x.strip() for x in upgrade.split(",") if x.strip()]:
            return False,"MISSING_UPGRADE_WEBSOCKET"
        if "upgrade" not in [x.strip() for x in connection.split(",") if x.strip()]:
            return False,"MISSING_CONNECTION_UPGRADE"
        if not accept:
            return False,"MISSING_SEC_WEBSOCKET_ACCEPT"
        if client_key:
            import base64 as _b64
            expected=_b64.b64encode(hashlib.sha1((str(client_key)+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            if not hmac.compare_digest(accept,expected):
                return False,"SEC_WEBSOCKET_ACCEPT_MISMATCH"
        return True,"OK"
    except Exception as exc:
        return False,"MALFORMED_UPGRADE_"+type(exc).__name__.upper()

class UsageCapture:
    def __init__(self,max_bytes=2097152):
        self.max_bytes=max(0,int(max_bytes))
        self.buf=bytearray()
    def feed(self,chunk):
        if self.max_bytes<=0 or len(self.buf)>=self.max_bytes:return
        self.buf.extend(chunk[:max(0,self.max_bytes-len(self.buf))])
    def _usage_from_obj(self,obj):
        if not isinstance(obj,dict):return None
        u=obj.get("usage")
        if not isinstance(u,dict):
            response=obj.get("response")
            if isinstance(response,dict):u=response.get("usage")
        if not isinstance(u,dict):return None
        def num(*keys):
            for k in keys:
                try:
                    if u.get(k) is not None:return int(u.get(k))
                except:pass
            return 0
        inp=num("input_tokens","prompt_tokens")
        out=num("output_tokens","completion_tokens")
        cached=0
        details=u.get("input_tokens_details") or u.get("prompt_tokens_details") or {}
        if isinstance(details,dict):
            try:cached=int(details.get("cached_tokens") or 0)
            except:cached=0
        total=num("total_tokens") or inp+out
        return {"input_tokens":inp,"output_tokens":out,"cached_input_tokens":cached,"total_tokens":total}
    def finish(self,content_type):
        raw=bytes(self.buf)
        if not raw:return {"input_tokens":None,"output_tokens":None,"cached_input_tokens":None,"total_tokens":None,"usage_source":"NO_DATA"}
        best=None
        ctype=(content_type or "").lower()
        if "text/event-stream" in ctype:
            text=raw.decode("utf-8","replace")
            for line in text.splitlines():
                if not line.startswith("data:"):continue
                payload=line[5:].strip()
                if not payload or payload=="[DONE]":continue
                try:u=self._usage_from_obj(json.loads(payload))
                except:u=None
                if u:best=u
            source="SSE_CAPTURE"
        else:
            try:best=self._usage_from_obj(json.loads(raw.decode("utf-8","replace")))
            except:best=None
            source="JSON_CAPTURE"
        if not best:return {"input_tokens":None,"output_tokens":None,"cached_input_tokens":None,"total_tokens":None,"usage_source":"NO_DATA"}
        best["usage_source"]=source
        return best

def estimate_cost(model,usage,cfg):
    prices=(cfg or {}).get("model_prices") or {}
    p=prices.get(str(model))
    if not isinstance(p,dict):return None
    try:
        inp=float(usage.get("input_tokens") or 0)
        out=float(usage.get("output_tokens") or 0)
        cached=float(usage.get("cached_input_tokens") or 0)
        noncached=max(0.0,inp-cached)
        return round((noncached*float(p.get("input_per_million",0))+
                      cached*float(p.get("cached_input_per_million",p.get("input_per_million",0)))+
                      out*float(p.get("output_per_million",0)))/1_000_000,10)
    except:return None

def extract_model(body,path="",headers=None):
    headers=headers or {}
    for hk in ("X-Model","OpenAI-Model"):
        if headers.get(hk):
            return str(headers.get(hk))
    try:
        q=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        if q.get("model"):
            return str(q["model"][0])
    except Exception:
        pass
    try:
        j=json.loads(body or b"{}")
        return str(j.get("model") or "*")
    except Exception:
        return "*"

def compatibility_features(body=b"",path="",headers=None):
    """Return feature labels only; never returns prompt/tool arguments or request content."""
    headers=headers or {}
    features=set()
    p=str(path or "").split("?",1)[0].lower()
    if p=="/v1/models": features.add("models")
    if p=="/v1/responses": features.add("responses")
    if p=="/v1/chat/completions": features.add("chat_completions")
    if "mcp" in p: features.add("mcp")
    if "search" in p: features.add("web_search")
    if headers.get("Upgrade","").lower()=="websocket": features.add("websocket")
    if "text/event-stream" in str(headers.get("Accept","")).lower(): features.add("streaming")
    try:
        obj=json.loads(body or b"{}")
    except Exception:
        obj={}
    if not isinstance(obj,dict): obj={}
    if obj.get("stream") is True: features.add("streaming")
    if obj.get("reasoning") is not None or obj.get("reasoning_effort") is not None: features.add("reasoning")
    if obj.get("response_format") is not None: features.add("structured_output")
    text_cfg=obj.get("text")
    if isinstance(text_cfg,dict) and text_cfg.get("format") is not None: features.add("structured_output")
    tools=obj.get("tools") or obj.get("functions") or []
    if isinstance(tools,dict): tools=[tools]
    if isinstance(tools,list) and tools:
        features.add("tool_calls")
        for t in tools:
            if not isinstance(t,dict): continue
            typ=str(t.get("type") or "").lower()
            if typ=="mcp" or "mcp" in typ: features.add("mcp")
            if "web_search" in typ or typ in ("search","web_search_preview"): features.add("web_search")
    def walk(v,depth=0):
        if depth>8:return
        if isinstance(v,dict):
            typ=str(v.get("type") or "").lower()
            if typ in ("input_image","image_url") or "image_url" in v: features.add("image_input")
            if typ in ("input_file","file") or "file_id" in v: features.add("attachments")
            if "json_schema" in v: features.add("structured_output")
            for x in v.values(): walk(x,depth+1)
        elif isinstance(v,list):
            for x in v[:200]: walk(x,depth+1)
    walk(obj)
    return sorted(features)

def compatibility_contract(cfg=None):
    cfg=cfg or {}
    return {
        "version":"25.72",
        "mode":"TRANSPARENT_PASS_THROUGH",
        "surfaces":{
            "/v1/models":"NATIVE_AGGREGATED",
            "/v1/responses":"PASS_THROUGH",
            "/v1/chat/completions":"PASS_THROUGH",
            "streaming_sse":"PASS_THROUGH_STREAM",
            "websocket":"PASS_THROUGH" if cfg.get("websocket_enabled",True) else "DISABLED",
            "tool_calls":"BODY_PRESERVING_PASS_THROUGH",
            "mcp_tools":"BODY_PRESERVING_PASS_THROUGH",
            "web_search_tools":"BODY_PRESERVING_PASS_THROUGH",
            "image_input":"BODY_PRESERVING_PASS_THROUGH",
            "attachments":"BODY_PRESERVING_PASS_THROUGH",
            "structured_output":"BODY_PRESERVING_PASS_THROUGH",
            "reasoning":"BODY_PRESERVING_PASS_THROUGH"
        },
        "transport":{
            "chunked_request_decode":True,
            "sse_flush":True,
            "cors_loopback":bool(cfg.get("cors_enabled",True)),
            "methods":["GET","POST","PUT","PATCH","DELETE","HEAD","OPTIONS"]
        },
        "routing_invariants":{
            "stable_endpoint":True,"session_affinity":bool(cfg.get("session_affinity",True)),
            "stream_identity_isolation":"CLIENT_PLUS_COMPOSITE_CONVERSATION_ID",
            "body_logging":False,"upstream_error_body_passthrough":True
        }
    }

def compat_error_payload(code,message=None,err_type="hms_gateway_error",param=None,request_id=None,extra=None):
    e={"message":message or str(code).replace("_"," ").title(),"type":err_type,"code":code}
    if param is not None:e["param"]=param
    out={"error":e,"hms_error":code}
    if request_id:out["request_id"]=request_id
    if isinstance(extra,dict):out.update(extra)
    return out

def session_id(headers,body,path=""):
    # v25.70 / Cockpit 1.3.25 parity: never let a broad user/account identity
    # collapse distinct streaming conversations onto the same affinity identity.
    # Preserve legacy single-key behavior, but hash the tuple when multiple
    # conversation/thread/request identifiers are available.
    parts=[]
    def add(kind,value):
        v=safe_id(value) if value is not None else None
        if v and (kind,v) not in parts:
            parts.append((kind,v))
    for k in ("X-Session-ID","Session_id","X-Client-Request-Id","Idempotency-Key"):
        if headers.get(k): add(k.lower(),headers.get(k))
    try:
        q=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        for k in ("session_id","conversation_id","thread_id"):
            if q.get(k): add(k,q[k][0])
    except Exception:
        pass
    try:
        j=json.loads(body or b"{}")
        for p in (("conversation_id",),("session_id",),("thread_id",),("metadata","user_id")):
            v=j
            for x in p:
                v=v.get(x) if isinstance(v,dict) else None
            if v: add(".".join(p),v)
    except Exception:
        pass
    if not parts:return None
    if len(parts)==1:return parts[0][1]
    basis="|".join(f"{k}={v}" for k,v in parts)
    return "sid-"+hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

class KeyStore:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()
        self.data=loadj(path,{"version":1,"salt":secrets.token_hex(16),"keys":[]})

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),"utf-8")
        os.replace(tmp,self.path)

    def create(self,name,allow=None,deny=None,target_allow=None,target_deny=None,routing_strategy=None,
               model_prefix="",single_target=None,quota_reserve_pct=0,target_priority=None,target_weight=None):
        key="hms_"+secrets.token_urlsafe(32)
        rec={
            "id":secrets.token_hex(8),"name":name,
            "digest":key_digest(self.data["salt"],key),
            "enabled":True,"created_utc":now_iso(),
            "model_allow":allow or ["*"],"model_deny":deny or [],
            "target_allow":target_allow or ["*"],"target_deny":target_deny or [],
            "routing_strategy":routing_strategy or None,"model_prefix":model_prefix or "",
            "single_target":single_target or None,"quota_reserve_pct":float(quota_reserve_pct or 0),
            "target_priority":target_priority or {},"target_weight":target_weight or {}
        }
        with self.lock:
            self.data["keys"].append(rec)
            self.save()
        return rec,key

    def verify(self,key):
        if not key:
            return None
        d=key_digest(self.data["salt"],key)
        for rec in self.data.get("keys",[]):
            if rec.get("enabled") and hmac.compare_digest(rec.get("digest",""),d):
                return rec
        return None

@dataclass
class Health:
    failures:int=0
    cooldown_until:float=0.0
    last_status:int|None=None
    last_latency_ms:float|None=None

class Router:
    def __init__(self,cfg,trace):
        self.cfg=cfg
        self.trace=trace
        self.lock=threading.RLock()
        self.rr=0
        self.health={x["id"]:Health() for x in cfg.get("targets",[])}
        self.affinity={}

    def update_cfg(self,cfg):
        with self.lock:
            self.cfg=cfg
            valid={str(x.get("id")) for x in cfg.get("targets",[]) if x.get("enabled",True)}
            for t in cfg.get("targets",[]):
                self.health.setdefault(t["id"],Health())
            self.affinity={k:v for k,v in self.affinity.items() if v and v[0] in valid}

    def _candidate_rows(self,model,exclude=None,client=None):
        exclude=set(exclude or [])
        now=time.time()
        rows=[]
        reserve=float((client or {}).get("quota_reserve_pct") or self.cfg.get("default_quota_reserve_pct") or 0)
        quota_max_age=int(self.cfg.get("quota_evidence_max_age_sec",900))
        quota_fail_closed=bool(self.cfg.get("quota_reserve_fail_closed",True))
        backup_ids=set((client or {}).get("backup_targets") or [])
        for t in self.cfg.get("targets",[]):
            h=self.health.setdefault(t["id"],Health())
            if t["id"] in exclude or not t.get("enabled",True) or h.cooldown_until>now:
                continue
            if not target_client_ok(client,t):
                continue
            if model!="*" and not model_ok(t,model):
                continue
            expiry=parse_utc_ts(t.get("expiry_utc"))
            if expiry is not None and expiry<=now:
                continue
            if reserve>0:
                q=quota_remaining(t);fresh=quota_evidence_fresh(t,quota_max_age)
                if (q is None or not fresh):
                    if quota_fail_closed:continue
                elif q<reserve:
                    continue
            q=dict(t)
            q["_effective_priority"]=effective_priority(t,client)
            q["_effective_weight"]=effective_weight(t,client)
            q["_backup"]=bool(t.get("backup",False) or str(t.get("id")) in backup_ids)
            rows.append(q)
        return rows

    def all_eligible(self,model="*",exclude=None,client=None):
        return self._candidate_rows(model,exclude,client)

    def available(self,model,exclude=None,client=None):
        rows=self._candidate_rows(model,exclude,client)
        if not rows:return []
        primaries=[x for x in rows if not x.get("_backup")]
        if primaries:rows=primaries
        top=max(int(x.get("_effective_priority",0)) for x in rows)
        return [x for x in rows if int(x.get("_effective_priority",0))==top]

    def _select_from(self,rows,client=None):
        strategy=str((client or {}).get("routing_strategy") or self.cfg.get("strategy","stable-round-robin"))
        if strategy=="single":
            wanted=str((client or {}).get("single_target") or "")
            for t in rows:
                if str(t.get("id"))==wanted:return t,"SINGLE"
            return None,"SINGLE_TARGET_UNAVAILABLE"
        if strategy=="fill-first":
            return rows[0],strategy.upper()
        if strategy=="random":
            return random.choice(rows),"RANDOM"
        if strategy=="weighted":
            expanded=[]
            for t in rows:expanded += [t]*max(1,int(t.get("_effective_weight",1)))
            with self.lock:
                idx=self.rr % len(expanded);self.rr+=1
            return expanded[idx],"WEIGHTED"
        if strategy=="reset-aware":
            def key(x):
                ts=parse_utc_ts(x.get("reset_utc"))
                return (ts if ts is not None else float("inf"),str(x.get("id","")))
            return sorted(rows,key=key)[0],"RESET_AWARE"
        if strategy=="expiry-soon":
            def key(x):
                ts=parse_utc_ts(x.get("expiry_utc"))
                return (ts if ts is not None else float("inf"),str(x.get("id","")))
            return sorted(rows,key=key)[0],"EXPIRY_SOON"
        if strategy=="quota-first":
            known=[x for x in rows if quota_remaining(x) is not None]
            if known:
                best=max(quota_remaining(x) for x in known)
                tied=[x for x in known if quota_remaining(x)==best]
                with self.lock:
                    idx=self.rr % len(tied);self.rr+=1
                return tied[idx],"QUOTA_FIRST"
        if strategy=="plan-first":
            best=max(int(x.get("plan_rank",0) or 0) for x in rows)
            tied=[x for x in rows if int(x.get("plan_rank",0) or 0)==best]
            with self.lock:
                idx=self.rr % len(tied);self.rr+=1
            return tied[idx],"PLAN_FIRST"
        if strategy=="auto":
            # Prefer fresh known quota, then plan rank, then earlier subscription expiry.
            def score(x):
                q=quota_remaining(x)
                known=1 if q is not None else 0
                exp=parse_utc_ts(x.get("expiry_utc"))
                expiry_score=-(exp if exp is not None else 9e18)
                return (known,q if q is not None else -1,int(x.get("plan_rank",0) or 0),expiry_score)
            best=max(score(x) for x in rows)
            tied=[x for x in rows if score(x)==best]
            with self.lock:
                idx=self.rr % len(tied);self.rr+=1
            return tied[idx],"AUTO"
        with self.lock:
            idx=self.rr % len(rows);self.rr+=1
        return rows[idx],"STABLE_ROUND_ROBIN"

    def _affinity_key(self,session,client):
        if not session:return None
        return (str((client or {}).get("id") or "anonymous"),str(session))

    def choose(self,model,session=None,exclude=None,client=None):
        # v25.51: session affinity is authoritative across ALL currently eligible targets,
        # not only the highest-priority slice. If a session failed over to a lower-priority
        # target during 429/cooldown, recovery of the former primary must not pull that
        # existing session back and create ping-pong. New sessions still use normal ranking.
        all_rows=self.all_eligible(model,exclude,client)
        if not all_rows:return None,"NO_ELIGIBLE"
        now=time.time();excluded=set(exclude or [])
        akey=self._affinity_key(session,client)
        if akey and self.cfg.get("session_affinity",True):
            a=self.affinity.get(akey)
            if a and a[1]>now and a[0] not in excluded:
                for t in all_rows:
                    if t["id"]==a[0]:return t,"AFFINITY"
        rows=self.available(model,exclude,client)
        if not rows:return None,"NO_ELIGIBLE"
        t,reason=self._select_from(rows,client)
        if t is None:return None,reason
        if akey and self.cfg.get("session_affinity",True):
            self.affinity[akey]=(t["id"],now+int(self.cfg.get("session_ttl_sec",3600)))
        return t,reason

    def rebind(self,session,target,client=None):
        akey=self._affinity_key(session,client)
        if akey and self.cfg.get("session_affinity",True):
            self.affinity[akey]=(target["id"],time.time()+int(self.cfg.get("session_ttl_sec",3600)))

    def mark(self,target,status,latency):
        h=self.health.setdefault(target["id"],Health())
        h.last_status=status
        h.last_latency_ms=latency
        if status in (401,403,408,409,429,500,502,503,504,599):
            h.failures+=1
            if h.failures>=int(self.cfg.get("health_fail_threshold",3)):
                h.cooldown_until=time.time()+int(self.cfg.get("health_cooldown_sec",120))
                h.failures=0
        elif 200<=status<400:
            h.failures=0
            h.cooldown_until=0.0

class ThreadingServer(socketserver.ThreadingMixIn,http.server.HTTPServer):
    daemon_threads=True
    allow_reuse_address=True

    def configure_runtime(self,config_path,cfg,trace):
        self.config_path=str(config_path) if config_path else ""
        self.config_lock=threading.RLock()
        self.config_mtime_ns=0
        self.cfg=cfg
        self.trace=trace
        self.router=Router(cfg,trace)
        try:self.config_mtime_ns=Path(self.config_path).stat().st_mtime_ns if self.config_path else 0
        except:self.config_mtime_ns=0

    def refresh_config(self):
        path=getattr(self,"config_path","")
        if not path:return False
        try:mtime=Path(path).stat().st_mtime_ns
        except:return False
        if mtime<=getattr(self,"config_mtime_ns",0):return False
        with self.config_lock:
            try:mtime=Path(path).stat().st_mtime_ns
            except:return False
            if mtime<=self.config_mtime_ns:return False
            new_cfg=loadj(path,{})
            if not isinstance(new_cfg,dict):return False
            # Listen host/port cannot be changed without restart; preserve actual bind authority.
            new_cfg["host"]=self.cfg.get("host","127.0.0.1")
            new_cfg["port"]=self.cfg.get("port",self.server_address[1])
            self.cfg=new_cfg
            self.router.update_cfg(new_cfg)
            self.config_mtime_ns=mtime
            append_jsonl(self.trace,{
                "time":now_iso(),"protocol":"control","event":"CONFIG_RELOAD",
                "target_count":len(new_cfg.get("targets",[])),
                "strategy":new_cfg.get("strategy")
            })
            return True

class Handler(http.server.BaseHTTPRequestHandler):
    server_version="HMS-SmartGateway/25.38"
    protocol_version="HTTP/1.1"

    def log_message(self,*a):
        return

    def _json(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Connection","close")
        self._emit_cors()
        self.end_headers()
        self.wfile.write(b)
        self.close_connection=True

    def _error(self,code,http_code,message=None,err_type="hms_gateway_error",param=None,request_id=None,extra=None):
        return self._json(http_code,compat_error_payload(code,message,err_type,param,request_id,extra))

    def _read_body(self):
        te=(self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" not in te:
            n=int(self.headers.get("Content-Length","0") or 0)
            return self.rfile.read(n) if n else b""
        chunks=[];total=0;limit=max(1,int(self.server.cfg.get("max_request_bytes",64*1024*1024)))
        while True:
            line=self.rfile.readline(128)
            if not line: raise ValueError("CHUNKED_BODY_EOF")
            size_text=line.split(b";",1)[0].strip()
            try:size=int(size_text,16)
            except Exception:raise ValueError("CHUNKED_BODY_INVALID_SIZE")
            if size==0:
                while True:
                    trailer=self.rfile.readline(8192)
                    if trailer in (b"\r\n",b"\n",b""): break
                break
            total+=size
            if total>limit: raise ValueError("REQUEST_BODY_TOO_LARGE")
            chunk=self.rfile.read(size)
            if len(chunk)!=size: raise ValueError("CHUNKED_BODY_TRUNCATED")
            chunks.append(chunk)
            ending=self.rfile.read(2)
            if ending!=b"\r\n": raise ValueError("CHUNKED_BODY_INVALID_TERMINATOR")
        return b"".join(chunks)

    def _client_auth(self,model):
        if not self.server.cfg.get("require_client_key",True):
            return {"id":None,"name":"anonymous","model_allow":["*"],"model_deny":[]}
        raw=self.headers.get("Authorization","")
        key=raw[7:] if raw.lower().startswith("bearer ") else ""
        rec=self.server.keys.verify(key)
        if rec is None:
            return None
        canonical=canonical_model_for_client(rec,model)
        if canonical!="*" and not model_ok(rec,canonical):
            return False
        return rec

    def _upstream_headers(self,target,websocket=False):
        headers={}
        for k,v in self.headers.items():
            kl=k.lower()
            if kl in ("host","authorization","content-length"):
                continue
            if not websocket and kl in HOP:
                continue
            headers[k]=v
        key_env=target.get("api_key_env","")
        upstream_key=os.environ.get(key_env,"") if key_env else ""
        if upstream_key:
            headers["Authorization"]="Bearer "+upstream_key
        return headers

    def _cors_origin_allowed(self,origin):
        if not origin:return False
        patterns=self.server.cfg.get("cors_allowed_origins") or ["http://localhost:*","http://127.0.0.1:*","https://localhost:*","https://127.0.0.1:*"]
        return any(fnmatch.fnmatch(origin,p) for p in patterns)

    def _emit_cors(self):
        origin=self.headers.get("Origin","")
        if self.server.cfg.get("cors_enabled",True) and self._cors_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Vary","Origin")
            self.send_header("Access-Control-Expose-Headers","X-HMS-Request-Id,X-HMS-Selected-Target,X-HMS-Selection-Reason,X-HMS-Attempts,X-HMS-Compatibility-Version")

    def _cors_preflight(self):
        origin=self.headers.get("Origin","")
        if not self._cors_origin_allowed(origin):
            return self._json(403,{"error":"CORS_ORIGIN_NOT_ALLOWED"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",origin)
        self.send_header("Vary","Origin")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Authorization,Content-Type,X-Session-ID,Session_id,X-Client-Request-Id,Idempotency-Key,X-Model,OpenAI-Model")
        self.send_header("Access-Control-Max-Age","600")
        self.send_header("Content-Length","0")
        self.end_headers()

    def do_HEAD(self): self._proxy()
    def do_OPTIONS(self):
        if self.server.cfg.get("cors_enabled",True):return self._cors_preflight()
        self._proxy()
    def do_GET(self):
        path=self.path.split("?",1)[0]
        if path=="/v1/models":
            return self._models()
        if path=="/hms/compatibility":
            client=self._client_auth("*")
            if client is None:return self._error("INVALID_CLIENT_KEY",401,"Invalid HMS client key.","authentication_error")
            return self._json(200,compatibility_contract(self.server.cfg))
        if self.headers.get("Upgrade","").lower()=="websocket":
            return self._websocket()
        self._proxy()
    def do_POST(self): self._proxy()
    def do_DELETE(self): self._proxy()
    def do_PUT(self): self._proxy()
    def do_PATCH(self): self._proxy()

    def _models(self):
        self.server.refresh_config()
        if not self.server.cfg.get("require_client_key",True):
            client={"id":None,"name":"anonymous","model_allow":["*"],"model_deny":[]}
        else:
            raw=self.headers.get("Authorization","")
            key=raw[7:] if raw.lower().startswith("bearer ") else ""
            client=self.server.keys.verify(key)
            if client is None:
                return self._error("INVALID_CLIENT_KEY",401,"Invalid HMS client key.","authentication_error")
        models={}
        sources={}
        now=time.time()
        for target in self.server.router.all_eligible("*",client=client):
            u=urllib.parse.urlparse(target["base_url"])
            try:
                conn=(http.client.HTTPSConnection if u.scheme=="https" else http.client.HTTPConnection)(
                    u.hostname,u.port,timeout=10
                )
                headers={}
                key_env=target.get("api_key_env","")
                upstream_key=os.environ.get(key_env,"") if key_env else ""
                if upstream_key:
                    headers["Authorization"]="Bearer "+upstream_key
                conn.request("GET",u.path.rstrip("/")+"/v1/models",headers=headers)
                resp=conn.getresponse()
                raw=resp.read()
                conn.close()
                if resp.status!=200:
                    continue
                obj=json.loads(raw.decode("utf-8","replace"))
                for m in obj.get("data",[]) if isinstance(obj,dict) else []:
                    mid=str(m.get("id") or "")
                    if not mid or not model_ok(client,mid) or not model_ok(target,mid):
                        continue
                    exposed=exposed_model_for_client(client,mid)
                    mm=dict(m);mm["id"]=exposed
                    models.setdefault(exposed,mm)
                    sources.setdefault(exposed,[]).append(safe_id(target["id"]))
            except Exception:
                continue
        self._json(200,{
            "object":"list","data":list(models.values()),
            "hms":{"eligible_targets":sources,"gateway_version":"25.38"}
        })

    def _can_replay(self):
        if self.command in ("GET","HEAD","OPTIONS"):
            return True
        if self.command in ("PUT","DELETE"):
            return True
        if self.command=="POST":
            if not self.server.cfg.get("require_idempotency_for_post_replay",True):
                return True
            return bool(self.headers.get("Idempotency-Key"))
        return False

    def _retry_statuses(self):
        raw=self.server.cfg.get("retry_statuses")
        if isinstance(raw,list):
            return {int(x) for x in raw}
        if isinstance(raw,str):
            try:return {int(x.strip()) for x in raw.split(",") if x.strip()}
            except:return RETRY_DEFAULT
        return RETRY_DEFAULT

    def _proxy(self):
        self.server.refresh_config()
        if self.path=="/hms/health":
            return self._json(200,{
                "ok":True,"version":"25.38",
                "strategy":self.server.router.cfg.get("strategy"),
                "websocket":bool(self.server.cfg.get("websocket_enabled",True)),
                "compatibility":"25.38",
                "time":now_iso()
            })

        try:
            body=self._read_body()
        except ValueError as e:
            code=str(e)
            return self._error(code,413 if code=="REQUEST_BODY_TOO_LARGE" else 400,code.replace("_"," ").title(),"invalid_request_error")
        exposed_model=extract_model(body,self.path,self.headers)
        compat_features=compatibility_features(body,self.path,self.headers)
        client=self._client_auth(exposed_model)
        if client is None:
            return self._error("INVALID_CLIENT_KEY",401,"Invalid HMS client key.","authentication_error")
        if client is False:
            return self._error("MODEL_NOT_ALLOWED_FOR_CLIENT_KEY",403,"Model is not allowed for this HMS client key.","permission_error","model",extra={"model":exposed_model})
        model=canonical_model_for_client(client,exposed_model)
        body=rewrite_json_model(body,exposed_model,model)
        upstream_path=rewrite_path_model(self.path,exposed_model,model)

        sid=session_id(self.headers,body,upstream_path)
        replay=self._can_replay()
        max_attempts=max(1,int(self.server.cfg.get("max_failover_attempts",3)))
        retry_statuses=self._retry_statuses()
        excluded=[]
        attempt_rows=[]
        reqid=secrets.token_hex(8)
        final=None

        for attempt in range(1,max_attempts+1):
            target,reason=self.server.router.choose(model,sid,excluded,client)
            if not target:
                break
            started=time.time()
            status=599
            err=None
            conn=None
            resp=None
            try:
                u=urllib.parse.urlparse(target["base_url"])
                conn=(http.client.HTTPSConnection if u.scheme=="https" else http.client.HTTPConnection)(
                    u.hostname,u.port,timeout=float(self.server.cfg.get("upstream_timeout_sec",300))
                )
                headers=self._upstream_headers(target,False)
                headers["Host"]=u.netloc
                headers["X-HMS-Route-Id"]=safe_id(target["id"])
                path=u.path.rstrip("/")+upstream_path
                conn.request(self.command,path,body=body,headers=headers)
                resp=conn.getresponse()
                status=resp.status
                header_ms=round((time.time()-started)*1000,2)

                if status in retry_statuses and replay and attempt<max_attempts:
                    # Do not expose retry response to client. Drain a bounded body and move on.
                    try:resp.read(1024*1024)
                    except:pass
                    try:conn.close()
                    except:pass
                    self.server.router.mark(target,status,header_ms)
                    excluded.append(target["id"])
                    attempt_rows.append({
                        "attempt":attempt,"target_id":target["id"],"status":status,
                        "reason":reason,"result":"RETRY_STATUS","header_ms":header_ms
                    })
                    continue

                final=(target,reason,conn,resp,started,header_ms,attempt)
                break

            except Exception as e:
                err=type(e).__name__
                latency=round((time.time()-started)*1000,2)
                self.server.router.mark(target,599,latency)
                excluded.append(target["id"])
                attempt_rows.append({
                    "attempt":attempt,"target_id":target["id"],"status":599,
                    "reason":reason,"result":"TRANSPORT_ERROR","error_class":err,"header_ms":latency
                })
                try:
                    if conn:conn.close()
                except:pass
                if not replay or attempt>=max_attempts:
                    break

        if final is None:
            append_jsonl(self.server.trace,{
                "time":now_iso(),"request_id":reqid,"protocol":"http",
                "method":self.command,"path":self.path.split("?")[0],"model":model,"exposed_model":exposed_model,
                "client_key_id":client.get("id"),"client_key_name":client.get("name"),
                "attempts":attempt_rows,"status":502,"error_class":"NO_SUCCESSFUL_UPSTREAM",
                "compat_features":compat_features,"request_body_logged":False
            })
            return self._error("UPSTREAM_FAILURE",502,"No eligible upstream completed the request.","upstream_error",request_id=reqid,extra={"attempts":len(attempt_rows)})

        target,reason,conn,resp,started,header_ms,attempt=final
        self.server.router.rebind(sid,target,client)
        status=resp.status
        content_type=(resp.getheader("Content-Type") or "").lower()
        content_len=resp.getheader("Content-Length")
        streaming=("text/event-stream" in content_type or content_len is None)
        expected_content_length=None
        try:
            if content_len is not None and self.command!="HEAD" and status not in (204,304):
                expected_content_length=max(0,int(content_len))
        except Exception:
            expected_content_length=None
        bytes_down=0
        ttft_ms=None
        error_class=None
        error_source=None
        usage_capture=UsageCapture(self.server.cfg.get("usage_capture_max_bytes",2097152))
        stream_probe=SSEIntegrityProbe(upstream_path,content_type,self.server.cfg.get("stream_integrity_capture_max_bytes",262144))

        try:
            self.send_response(resp.status,resp.reason)
            for k,v in resp.getheaders():
                kl=k.lower()
                if kl in HOP:
                    continue
                if streaming and kl=="content-length":
                    continue
                self.send_header(k,v)
            if self.server.cfg.get("expose_selected_target_headers",True):
                self.send_header("X-HMS-Request-Id",reqid)
                self.send_header("X-HMS-Selected-Target",safe_id(target["id"]))
                self.send_header("X-HMS-Selection-Reason",reason)
                self.send_header("X-HMS-Attempts",str(attempt))
                self.send_header("X-HMS-Compatibility-Version","25.38")
            if streaming:
                self.send_header("Connection","close")
                self.close_connection=True
            self._emit_cors()
            self.end_headers()

            chunk_size=max(1024,int(self.server.cfg.get("stream_chunk_bytes",65536)))
            while True:
                try:
                    chunk=resp.read1(chunk_size) if streaming and hasattr(resp,"read1") else resp.read(chunk_size)
                except Exception as e:
                    error_class=type(e).__name__;error_source="UPSTREAM_READ"
                    break
                if not chunk:
                    break
                if ttft_ms is None:
                    ttft_ms=round((time.time()-started)*1000,2)
                bytes_down+=len(chunk)
                usage_capture.feed(chunk);stream_probe.feed(chunk)
                try:
                    self.wfile.write(chunk);self.wfile.flush()
                except Exception as e:
                    error_class=type(e).__name__;error_source="CLIENT_WRITE"
                    break
        except Exception as e:
            error_class=type(e).__name__;error_source=error_source or "CLIENT_HEADER_WRITE"
        finally:
            try:conn.close()
            except:pass

        total_ms=round((time.time()-started)*1000,2)
        client_aborted=error_source in ("CLIENT_WRITE","CLIENT_HEADER_WRITE")
        integrity=stream_probe.finish(error_class if error_source=="UPSTREAM_READ" else None,client_aborted)
        if expected_content_length is None:
            body_integrity="NOT_APPLICABLE"
        elif client_aborted:
            body_integrity="CLIENT_ABORT"
        elif bytes_down==expected_content_length:
            body_integrity="COMPLETE"
        else:
            body_integrity="CONTENT_LENGTH_MISMATCH"
            if error_class is None:
                error_class="IncompleteBody";error_source="UPSTREAM_EOF"
        health_status=status
        if error_source in ("UPSTREAM_READ","UPSTREAM_EOF") or integrity.get("status")=="TRUNCATED_EOF" or body_integrity=="CONTENT_LENGTH_MISMATCH":
            health_status=599
        # A client disconnect is not an upstream health failure. A truncated OpenAI SSE
        # stream is: mark it unhealthy for the NEXT request, but never replay a partial stream.
        self.server.router.mark(target,health_status,total_ms)
        usage=usage_capture.finish(content_type)
        estimated_usd=estimate_cost(model,usage,self.server.cfg)
        attempt_rows.append({
            "attempt":attempt,"target_id":target["id"],"status":status,
            "reason":reason,"result":"FINAL","header_ms":header_ms
        })
        append_jsonl(self.server.trace,{
            "time":now_iso(),"request_id":reqid,"protocol":"sse" if "text/event-stream" in content_type else "http",
            "method":self.command,"path":self.path.split("?")[0],"model":model,"exposed_model":exposed_model,
            "client_key_id":client.get("id"),"client_key_name":client.get("name"),
            "target_id":target["id"],"account":target.get("account"),"selection":reason,
            "session_present":bool(sid),"status":status,"header_ms":header_ms,
            "ttft_ms":ttft_ms,"latency_ms":total_ms,"bytes_down":bytes_down,
            "streaming":streaming,"attempt_count":len(attempt_rows),"attempts":attempt_rows,
            "stream_integrity":integrity.get("status"),"stream_terminal_seen":integrity.get("terminal_seen"),
            "stream_integrity_enforced":integrity.get("enforced"),"stream_error_source":error_source,
            "body_integrity":body_integrity,"expected_content_length":expected_content_length,
            "input_tokens":usage.get("input_tokens"),"output_tokens":usage.get("output_tokens"),
            "cached_input_tokens":usage.get("cached_input_tokens"),"total_tokens":usage.get("total_tokens"),
            "usage_source":usage.get("usage_source"),"estimated_usd":estimated_usd,
            "compat_features":compat_features,
            "error_class":error_class,"request_body_logged":False
        })

    def _read_http_head(self,sock,limit=131072):
        data=b""
        while b"\r\n\r\n" not in data:
            chunk=sock.recv(4096)
            if not chunk:
                break
            data+=chunk
            if len(data)>limit:
                raise RuntimeError("upstream websocket headers too large")
        head,sep,rest=data.partition(b"\r\n\r\n")
        return head+sep,rest

    def _websocket(self):
        self.server.refresh_config()
        if not self.server.cfg.get("websocket_enabled",True):
            return self._error("WEBSOCKET_DISABLED",501,"WebSocket compatibility is disabled.","unsupported_error")

        exposed_model=extract_model(b"",self.path,self.headers)
        if exposed_model=="*" and self.server.cfg.get("websocket_require_model_hint",True):
            return self._error("WEBSOCKET_MODEL_HINT_REQUIRED",400,"Provide model query parameter or X-Model/OpenAI-Model header.","invalid_request_error","model")

        client=self._client_auth(exposed_model)
        if client is None:
            return self._error("INVALID_CLIENT_KEY",401,"Invalid HMS client key.","authentication_error")
        if client is False:
            return self._error("MODEL_NOT_ALLOWED_FOR_CLIENT_KEY",403,"Model is not allowed for this HMS client key.","permission_error","model",extra={"model":exposed_model})
        model=canonical_model_for_client(client,exposed_model)
        upstream_path=rewrite_path_model(self.path,exposed_model,model)

        sid=session_id(self.headers,b"",upstream_path)
        reqid=secrets.token_hex(8)
        max_attempts=max(1,int(self.server.cfg.get("max_failover_attempts",3)))
        retry_statuses=self._retry_statuses()
        excluded=[]
        attempt_rows=[]
        selected=None

        for attempt in range(1,max_attempts+1):
            target,reason=self.server.router.choose(model,sid,excluded,client)
            if not target:
                break

            started=time.time()
            upstream=None
            status=599
            head=b""
            rest=b""
            try:
                u=urllib.parse.urlparse(target["base_url"])
                raw=socket.create_connection(
                    (u.hostname,u.port or (443 if u.scheme=="https" else 80)),
                    timeout=15
                )
                if u.scheme=="https":
                    ctx=ssl.create_default_context()
                    upstream=ctx.wrap_socket(raw,server_hostname=u.hostname)
                else:
                    upstream=raw
                upstream.settimeout(float(self.server.cfg.get("websocket_idle_timeout_sec",300)))

                path=u.path.rstrip("/")+upstream_path
                lines=[f"{self.command} {path} HTTP/1.1",f"Host: {u.netloc}"]
                headers=self._upstream_headers(target,True)
                headers["Connection"]="Upgrade"
                headers["Upgrade"]="websocket"
                headers["X-HMS-Route-Id"]=safe_id(target["id"])
                for k,v in headers.items():
                    if k.lower()=="host":
                        continue
                    lines.append(f"{k}: {v}")
                upstream.sendall(("\r\n".join(lines)+"\r\n\r\n").encode("latin1","replace"))

                head,rest=self._read_http_head(upstream)
                first=head.split(b"\r\n",1)[0].decode("latin1","replace")
                try:status=int(first.split()[1])
                except:status=599
                handshake_ms=round((time.time()-started)*1000,2)
                self.server.router.mark(target,status,handshake_ms)

                if status==101:
                    ws_ok,ws_reason=validate_websocket_upgrade_head(head,self.headers.get("Sec-WebSocket-Key", ""))
                    if ws_ok:
                        selected=(target,reason,upstream,head,rest,started,attempt)
                        attempt_rows.append({
                            "attempt":attempt,"target_id":target["id"],"status":101,
                            "reason":reason,"result":"UPGRADE","handshake_ms":handshake_ms
                        })
                        break
                    attempt_rows.append({
                        "attempt":attempt,"target_id":target["id"],"status":599,
                        "reason":reason,"result":"MALFORMED_UPGRADE","handshake_ms":handshake_ms,
                        "error_class":ws_reason
                    })
                    self.server.router.mark(target,599,handshake_ms)
                    try:upstream.close()
                    except:pass
                    upstream=None
                    excluded.append(target["id"])
                    if attempt<max_attempts:
                        continue
                    break

                attempt_rows.append({
                    "attempt":attempt,"target_id":target["id"],"status":status,
                    "reason":reason,"result":"HANDSHAKE_REJECT","handshake_ms":handshake_ms
                })
                try:upstream.close()
                except:pass
                upstream=None
                if status in retry_statuses and attempt<max_attempts:
                    excluded.append(target["id"])
                    continue

                # Non-retryable handshake response: forward it as final.
                self.connection.sendall(head)
                if rest:self.connection.sendall(rest)
                self.close_connection=True
                append_jsonl(self.server.trace,{
                    "time":now_iso(),"request_id":reqid,"protocol":"websocket",
                    "method":self.command,"path":self.path.split("?")[0],"model":model,
                    "client_key_id":client.get("id"),"client_key_name":client.get("name"),
                    "target_id":target["id"],"account":target.get("account"),"selection":reason,
                    "session_present":bool(sid),"status":status,
                    "latency_ms":handshake_ms,"bytes_up":0,"bytes_down":len(rest),
                    "attempt_count":len(attempt_rows),"attempts":attempt_rows,
                    "error_class":None,"request_body_logged":False
                })
                return

            except Exception as e:
                latency=round((time.time()-started)*1000,2)
                self.server.router.mark(target,599,latency)
                attempt_rows.append({
                    "attempt":attempt,"target_id":target["id"],"status":599,
                    "reason":reason,"result":"TRANSPORT_ERROR",
                    "handshake_ms":latency,"error_class":type(e).__name__
                })
                try:
                    if upstream:upstream.close()
                except:pass
                excluded.append(target["id"])
                if attempt>=max_attempts:
                    break

        if selected is None:
            append_jsonl(self.server.trace,{
                "time":now_iso(),"request_id":reqid,"protocol":"websocket",
                "method":self.command,"path":self.path.split("?")[0],"model":model,
                "client_key_id":client.get("id"),"client_key_name":client.get("name"),
                "session_present":bool(sid),"status":502,
                "attempt_count":len(attempt_rows),"attempts":attempt_rows,
                "error_class":"NO_SUCCESSFUL_WEBSOCKET_UPSTREAM",
                "request_body_logged":False
            })
            return self._error("WEBSOCKET_UPSTREAM_FAILURE",502,"No eligible upstream completed the WebSocket handshake.","upstream_error",request_id=reqid,extra={"attempts":len(attempt_rows)})

        target,reason,upstream,head,rest,started,attempt=selected
        status=101
        bytes_up=0
        bytes_down=0
        error_class=None

        try:
            htxt=head.decode("latin1","replace")
            base=htxt.split("\r\n\r\n",1)[0]
            hdr=(
                base+
                f"\r\nX-HMS-Request-Id: {reqid}"
                f"\r\nX-HMS-Selected-Target: {safe_id(target['id'])}"
                f"\r\nX-HMS-Selection-Reason: {reason}"
                f"\r\nX-HMS-Attempts: {attempt}\r\n\r\n"
            )
            self.connection.sendall(hdr.encode("latin1","replace"))
            if rest:
                self.connection.sendall(rest)
                bytes_down+=len(rest)

            self.server.router.rebind(sid,target,client)
            self.connection.setblocking(False)
            upstream.setblocking(False)
            idle=float(self.server.cfg.get("websocket_idle_timeout_sec",300))
            last=time.time()

            while True:
                r,_,_=select.select([self.connection,upstream],[],[],1.0)
                if not r:
                    if time.time()-last>idle:
                        break
                    continue
                for src in r:
                    try:
                        data=src.recv(65536)
                    except (BlockingIOError,ssl.SSLWantReadError):
                        continue
                    if not data:
                        return
                    last=time.time()
                    if src is self.connection:
                        try:upstream.sendall(data)
                        except ssl.SSLWantWriteError:continue
                        bytes_up+=len(data)
                    else:
                        self.connection.sendall(data)
                        bytes_down+=len(data)

        except Exception as e:
            error_class=type(e).__name__
        finally:
            try:upstream.close()
            except:pass
            append_jsonl(self.server.trace,{
                "time":now_iso(),"request_id":reqid,"protocol":"websocket",
                "method":self.command,"path":self.path.split("?")[0],"model":model,
                "client_key_id":client.get("id"),"client_key_name":client.get("name"),
                "target_id":target["id"],"account":target.get("account"),"selection":reason,
                "session_present":bool(sid),"status":status,
                "latency_ms":round((time.time()-started)*1000,2),
                "bytes_up":bytes_up,"bytes_down":bytes_down,
                "attempt_count":len(attempt_rows),"attempts":attempt_rows,
                "error_class":error_class,"request_body_logged":False
            })

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",required=True)
    ap.add_argument("--keys",required=True)
    ap.add_argument("--trace",required=True)
    a=ap.parse_args()
    cfg=loadj(a.config,{})
    keys=KeyStore(a.keys)
    srv=ThreadingServer((cfg.get("host","127.0.0.1"),int(cfg.get("port",8320))),Handler)
    srv.keys=keys
    srv.configure_runtime(a.config,cfg,a.trace)
    print(
        f"HMS Smart Gateway v25.38 http://{cfg.get('host','127.0.0.1')}:{cfg.get('port',8320)} "
        f"strategy={cfg.get('strategy')} websocket={cfg.get('websocket_enabled',True)}",
        flush=True
    )
    srv.serve_forever()

if __name__=="__main__":
    main()
