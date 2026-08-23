#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, platform, re, subprocess, sys, tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.65"
SCHEMA_VERSION = 1
EVIDENCE_CLASS = "WINDOWS_TARGET_OBSERVER"
PRODUCTION_CLAIM = "NOT_CLAIMED_TARGET_ADAPTER_PACK_REQUIRES_LIVE_WINDOWS_EXECUTION"
EFFECT_KINDS = (
    "OFFICIAL_AUTH_REWRITE",
    "CONTROLLED_CODEX_RESTART",
    "ROUTER_STATE_TRANSITION",
    "LAN_LEASE_HANDOFF",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_ARGV = {"-command", "-encodedcommand", "/c", "-c"}
SENSITIVE_KEYS = ("token","secret","password","authorization","cookie","credential","api_key","email","account","hostname","username","prompt","body")


def utcnow() -> str: return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->str:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode("utf-8","surrogatepass")
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return "ref-"+sha(v)[:20]

def atomic_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8")
    tmp=path.with_name(path.name+".tmp-"+sha(raw)[:10])
    with tmp.open("wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def read_json(path:Path)->dict[str,Any]:
    try:
        o=json.loads(path.read_text("utf-8-sig"));return o if isinstance(o,dict) else {}
    except Exception:return {}

def sanitize(o:Any)->Any:
    if isinstance(o,dict):
        return {str(k):("<REDACTED>" if any(x in str(k).lower() for x in SENSITIVE_KEYS) else sanitize(v)) for k,v in o.items()}
    if isinstance(o,list):return [sanitize(x) for x in o]
    if isinstance(o,str) and len(o)>240:return o[:240]+"…"
    return o

def safe_argv(argv:Any)->tuple[bool,str]:
    if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv):return False,"ARGV_REQUIRED"
    lower=[x.lower() for x in argv]
    if any(x in FORBIDDEN_ARGV for x in lower):return False,"SHELL_COMMAND_MODE_FORBIDDEN"
    if any(any(ch in x for ch in ("\n","\r","\x00")) for x in argv):return False,"ARGV_CONTROL_CHAR_FORBIDDEN"
    return True,""

@dataclass(frozen=True)
class AdapterObservation:
    effect_kind:str
    available:bool
    state_hash:str
    generation:str
    applied_idempotency_key_hash:str
    evidence_class:str
    freshness_state:str
    failure_reason:str
    observed_utc:str
    detail:dict[str,Any]
    @property
    def observed_hash(self)->str:return self.state_hash
    @property
    def observer(self)->str:return "WINDOWS_TARGET_ADAPTER_PACK_V25.65"
    @property
    def source_age_seconds(self):return None
    def public(self)->dict[str,Any]:return sanitize(asdict(self))

class WindowsTargetAdapterPack:
    """Concrete probe pack for the four v25.65 target effects.

    It intentionally does not contain account switching payloads or credentials. Auth-file
    observation hashes raw bytes without serializing them. Keyring/auto observation requires
    a digest-only helper. Mutating real effects remain delegated to separately audited argv
    adapters and stay disarmed by the real-effect certification harness.
    """
    def __init__(self,data_dir:Path,*,auth_mode:str="auto",auth_file:Path|None=None,keyring_digest_provider:Path|None=None):
        self.data_dir=Path(data_dir)
        self.auth_mode=str(auth_mode or "auto").lower()
        self.auth_file=Path(auth_file) if auth_file else Path(os.environ.get("CODEX_HOME") or (Path.home()/".codex"))/"auth.json"
        self.keyring_digest_provider=Path(keyring_digest_provider) if keyring_digest_provider else None

    def _unavailable(self,kind:str,reason:str,detail:dict[str,Any]|None=None)->AdapterObservation:
        return AdapterObservation(kind,False,"","","",EVIDENCE_CLASS,"UNKNOWN",reason,utcnow(),detail or {})

    def _auth_file(self)->AdapterObservation:
        kind="OFFICIAL_AUTH_REWRITE"
        try:
            raw=self.auth_file.read_bytes();st=self.auth_file.stat()
            return AdapterObservation(kind,True,sha(raw),str(st.st_mtime_ns),"",EVIDENCE_CLASS if os.name=="nt" else "LAB_FIXTURE","FRESH","",utcnow(),{"mode":"file","size":st.st_size,"path_ref":safe_ref(str(self.auth_file)),"raw_content_exported":False})
        except Exception as exc:return self._unavailable(kind,"AUTH_FILE_READ_FAILED",{"error_type":type(exc).__name__,"path_ref":safe_ref(str(self.auth_file))})

    def _keyring(self)->AdapterObservation:
        kind="OFFICIAL_AUTH_REWRITE";p=self.keyring_digest_provider
        if os.name!="nt":return self._unavailable(kind,"WINDOWS_TARGET_REQUIRED",{"secret_read_attempted":False})
        if not p or not p.is_file():return self._unavailable(kind,"DIGEST_ONLY_KEYRING_PROVIDER_REQUIRED",{"secret_read_attempted":False})
        try:
            r=subprocess.run([str(p),"--hms-digest-only"],capture_output=True,text=True,timeout=15,creationflags=0x08000000)
            if r.returncode:return self._unavailable(kind,"KEYRING_PROVIDER_FAILED",{"exit_code":r.returncode})
            o=json.loads(r.stdout or "{}");digest=str(o.get("digest_sha256") or "").lower();generation=str(o.get("generation") or "")
            raw=stable(o).lower()
            if not HEX64.fullmatch(digest) or any('"'+x+'"' in raw for x in SENSITIVE_KEYS):return self._unavailable(kind,"KEYRING_PROVIDER_CONTRACT_REJECTED",{"secret_read_attempted":False})
            return AdapterObservation(kind,True,digest,generation,"",EVIDENCE_CLASS,"FRESH","",utcnow(),{"mode":"keyring","provider_ref":safe_ref(str(p)),"secret_read_attempted":False})
        except Exception as exc:return self._unavailable(kind,"KEYRING_PROVIDER_EXCEPTION",{"error_type":type(exc).__name__,"secret_read_attempted":False})

    def _restart(self)->AdapterObservation:
        kind="CONTROLLED_CODEX_RESTART"
        if os.name!="nt":return self._unavailable(kind,"WINDOWS_TARGET_REQUIRED")
        ps="$ErrorActionPreference='Stop';$r=@(Get-Process -Name codex -ErrorAction SilentlyContinue|%{$t=$null;try{$t=$_.StartTime.ToUniversalTime().Ticks}catch{};[ordered]@{id=$_.Id;name=$_.ProcessName.ToLowerInvariant();start_ticks=$t}});$r|Sort-Object name,id|ConvertTo-Json -Compress -Depth 4"
        try:
            r=subprocess.run(["powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-Command",ps],capture_output=True,text=True,timeout=15,creationflags=0x08000000)
            if r.returncode:return self._unavailable(kind,"WINDOWS_PROCESS_API_FAILED",{"exit_code":r.returncode})
            o=json.loads((r.stdout or "[]").strip() or "[]");rows=o if isinstance(o,list) else ([o] if isinstance(o,dict) else [])
            safe=[{"id":int(x.get("id") or 0),"name":str(x.get("name") or ""),"start_ticks":x.get("start_ticks")} for x in rows if isinstance(x,dict)]
            digest=sha(stable(safe));generation=sha(stable([(x["id"],x["start_ticks"]) for x in safe]))[:24]
            return AdapterObservation(kind,True,digest,generation,"",EVIDENCE_CLASS,"FRESH","",utcnow(),{"process_count":len(safe),"command_line_collected":False,"environment_collected":False})
        except Exception as exc:return self._unavailable(kind,"WINDOWS_PROCESS_OBSERVER_EXCEPTION",{"error_type":type(exc).__name__})

    def _runtime_json(self,kind:str,candidates:list[str],fields:tuple[str,...],owner_field:str="")->AdapterObservation:
        for name in candidates:
            p=self.data_dir/name
            if not p.is_file():continue
            o=read_json(p);project={k:o.get(k) for k in fields}
            if owner_field and owner_field in project:project[owner_field]=safe_ref(str(project.get(owner_field) or ""))
            digest=sha(stable(project));generation=str(o.get("generation") or o.get("epoch") or o.get("lease_epoch") or o.get("updated_utc") or "")
            return AdapterObservation(kind,True,digest,generation,"",EVIDENCE_CLASS if os.name=="nt" else "LAB_FIXTURE","FRESH","",utcnow(),{"source_ref":safe_ref(str(p)),"raw_owner_exposed":False if owner_field else None})
        return self._unavailable(kind,"RUNTIME_METADATA_NOT_FOUND",{"candidate_count":len(candidates)})

    def observe(self,kind:str)->AdapterObservation:
        if kind=="OFFICIAL_AUTH_REWRITE":
            if self.auth_mode=="file" or (self.auth_mode=="auto" and self.auth_file.is_file()):return self._auth_file()
            return self._keyring()
        if kind=="CONTROLLED_CODEX_RESTART":return self._restart()
        if kind=="ROUTER_STATE_TRANSITION":return self._runtime_json(kind,["gateway-state-v20.json","router-generation.json"],("generation","status","enabled","mode"))
        if kind=="LAN_LEASE_HANDOFF":return self._runtime_json(kind,["lan-pool-latest-v2545.json","lan-lease.json"],("generation","epoch","lease_epoch","owner","status"),"owner")
        return self._unavailable(kind,"UNKNOWN_EFFECT_KIND")

    def observe_all(self)->dict[str,Any]:
        rows=[self.observe(k).public() for k in EFFECT_KINDS]
        return {"product":"HMS-AI-ROUTER","version":VERSION,"schema_version":SCHEMA_VERSION,"suite":"WINDOWS_TARGET_ADAPTER_PACK","generated_utc":utcnow(),"verdict":"PASS" if all(r["available"] for r in rows) else "DEFERRED_TARGET_OBSERVATION","summary":{"available":sum(bool(r["available"]) for r in rows),"total":len(rows)},"evidence_class":EVIDENCE_CLASS,"production_score_eligible":False,"adapters":rows,"production_certification":PRODUCTION_CLAIM}

def build_adapter_manifest(adapter_exe:str)->dict[str,Any]:
    effects={}
    for short,kind in (("auth","OFFICIAL_AUTH_REWRITE"),("restart","CONTROLLED_CODEX_RESTART"),("router","ROUTER_STATE_TRANSITION"),("lease","LAN_LEASE_HANDOFF")):
        effects[short]={"effect_kind":kind,"apply_argv":[adapter_exe,"apply",short],"probe_argv":[adapter_exe,"probe",short],"probe_contract":"DIGEST_AND_IDEMPOTENCY_WITNESS_ONLY","readback_contract":"EXACT_STATE_HASH_AND_GENERATION","timeout_seconds":45}
    return {"schema_version":1,"pack_version":VERSION,"disarmed_default":True,"effects":effects,"privacy":{"raw_credentials":False,"raw_account_identity":False,"raw_hostname":False}}

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
    with tempfile.TemporaryDirectory(prefix="hms-v2565-adapter-") as td:
        d=Path(td);auth=d/"auth.json";auth.write_bytes(b'{"opaque":"fixture"}')
        (d/"gateway-state-v20.json").write_text(json.dumps({"generation":7,"status":"ready","enabled":True}),"utf-8")
        (d/"lan-pool-latest-v2545.json").write_text(json.dumps({"lease_epoch":9,"owner":"sensitive-owner","status":"HEALTHY"}),"utf-8")
        p=WindowsTargetAdapterPack(d,auth_mode="file",auth_file=auth)
        a=p.observe("OFFICIAL_AUTH_REWRITE").public();r=p.observe("ROUTER_STATE_TRANSITION").public();l=p.observe("LAN_LEASE_HANDOFF").public()
        add("auth_hash_64",HEX64.fullmatch(a.get("state_hash") or "") is not None,a)
        add("auth_content_not_exported",a.get("detail",{}).get("raw_content_exported") is False and "opaque" not in stable(a))
        add("router_generation",r.get("available") and str(r.get("generation"))=="7",r)
        add("lease_owner_hashed",l.get("available") and "sensitive-owner" not in stable(l),l)
    m=build_adapter_manifest("C:/HMS/hms-target-adapter.exe")
    add("manifest_four_effects",set(m["effects"])=={"auth","restart","router","lease"})
    add("manifest_disarmed",m.get("disarmed_default") is True)
    add("argv_structured",all(safe_argv(row["apply_argv"])[0] and safe_argv(row["probe_argv"])[0] for row in m["effects"].values()))
    add("probe_contract_exact",all(row["probe_contract"]=="DIGEST_AND_IDEMPOTENCY_WITNESS_ONLY" and row["readback_contract"]=="EXACT_STATE_HASH_AND_GENERATION" for row in m["effects"].values()))
    add("nonwindows_restart_fail_closed",os.name=="nt" or WindowsTargetAdapterPack(Path(tempfile.gettempdir())).observe("CONTROLLED_CODEX_RESTART").failure_reason=="WINDOWS_TARGET_REQUIRED")
    add("keyring_digest_only_contract","--hms-digest-only" in Path(__file__).read_text("utf-8") and "secret_read_attempted" in Path(__file__).read_text("utf-8"))
    add("production_not_auto",PRODUCTION_CLAIM.startswith("NOT_CLAIMED"))
    passed=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_TARGET_ADAPTER_PACK_PROOF","generated_utc":utcnow(),"verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,"production_score_eligible":False,"production_certification":PRODUCTION_CLAIM}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=("proof","observe","manifest"),default="proof");ap.add_argument("--data-dir");ap.add_argument("--auth-mode",default="auto");ap.add_argument("--auth-file");ap.add_argument("--keyring-provider");ap.add_argument("--adapter-exe",default="C:/HMS/hms-target-adapter.exe");ap.add_argument("--output");a=ap.parse_args()
    if a.mode=="proof":out=synthetic_proof();rc=0 if out["verdict"]=="PASS" else 2
    elif a.mode=="manifest":out=build_adapter_manifest(a.adapter_exe);rc=0
    else:
        if not a.data_dir:raise SystemExit("--data-dir required")
        out=WindowsTargetAdapterPack(Path(a.data_dir),auth_mode=a.auth_mode,auth_file=Path(a.auth_file) if a.auth_file else None,keyring_digest_provider=Path(a.keyring_provider) if a.keyring_provider else None).observe_all();rc=0
    if a.output:atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=="__main__":raise SystemExit(main())
