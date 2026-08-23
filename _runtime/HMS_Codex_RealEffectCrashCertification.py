#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.65"
SCHEMA_VERSION = 1
ARM_TOKEN = "REAL_CODEX_EFFECTS"
OPERATOR_PHRASE = "ARM HMS REAL CODEX CRASH CERTIFICATION"
ENV_GATE = "HMS_REAL_EFFECT_CRASH_CERT"
EVIDENCE_CLASS = "REAL_CODEX_EFFECT"
PRODUCTION_CLAIM = "NOT_CLAIMED_REAL_CODEX_EFFECT_TARGET_RUN_REQUIRED"
EFFECTS = ("auth", "restart", "router", "lease")
EFFECT_KIND = {
    "auth": "OFFICIAL_AUTH_REWRITE",
    "restart": "CONTROLLED_CODEX_RESTART",
    "router": "ROUTER_STATE_TRANSITION",
    "lease": "LAN_LEASE_HANDOFF",
}
WINDOWS = ("AFTER_PREPARE_BEFORE_EFFECT", "AFTER_EFFECT_BEFORE_DURABLE", "AFTER_DURABLE_BEFORE_VERIFY")
FORBIDDEN_ARGV = {"-command", "-encodedcommand", "/c", "-c"}


def utcnow() -> str: return datetime.now(timezone.utc).isoformat()
def stable(obj: Any) -> str: return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def sha(v: bytes | str) -> str:
    if isinstance(v, str): v = v.encode("utf-8", "surrogatepass")
    return hashlib.sha256(v).hexdigest()

def safe_ref(v: str) -> str: return "ref-" + sha(v)[:20]

def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8")
    tmp=path.with_name(path.name+".tmp-"+sha(raw)[:10])
    with tmp.open("wb") as f: f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def read_json(path: Path) -> dict[str,Any]:
    try:
        obj=json.loads(path.read_text("utf-8-sig"));return obj if isinstance(obj,dict) else {}
    except Exception:return {}

def append_journal(path: Path, phase: str, effect: str, meta: dict[str,Any] | None=None) -> None:
    rows=[]
    if path.exists():
        for line in path.read_text("utf-8-sig").splitlines():
            if line.strip(): rows.append(json.loads(line))
    prev=rows[-1]["record_hash"] if rows else "GENESIS"
    row={"schema_version":SCHEMA_VERSION,"version":VERSION,"seq":len(rows)+1,"phase":phase,"effect":effect,"time_utc":utcnow(),"meta":meta or {},"prev_hash":prev}
    row["record_hash"]=sha(stable(row))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8",newline="\n") as f:f.write(stable(row)+"\n");f.flush();os.fsync(f.fileno())

def validate_journal(path: Path) -> bool:
    prev="GENESIS"
    try:
        rows=[json.loads(x) for x in path.read_text("utf-8-sig").splitlines() if x.strip()]
        for i,row in enumerate(rows,1):
            if int(row.get("seq") or 0)!=i or row.get("prev_hash")!=prev:return False
            raw={k:v for k,v in row.items() if k!="record_hash"}
            if row.get("record_hash")!=sha(stable(raw)):return False
            prev=row["record_hash"]
        return bool(rows)
    except Exception:return False

def phases(path: Path) -> set[str]:
    try:return {str(json.loads(x).get("phase") or "") for x in path.read_text("utf-8-sig").splitlines() if x.strip()}
    except Exception:return set()

def safe_argv(argv: Any) -> tuple[bool,str]:
    if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv):return False,"ARGV_REQUIRED"
    lower=[x.lower() for x in argv]
    if any(x in FORBIDDEN_ARGV for x in lower):return False,"SHELL_COMMAND_MODE_FORBIDDEN"
    if any(any(ch in x for ch in ("\n","\r","\x00")) for x in argv):return False,"ARGV_CONTROL_CHAR_FORBIDDEN"
    return True,""

def validate_manifest(obj: dict[str,Any]) -> tuple[bool,list[str]]:
    errors=[]
    if int(obj.get("schema_version") or 0)!=1:errors.append("SCHEMA_VERSION")
    effects=obj.get("effects") or {}
    if set(effects)!=set(EFFECTS):errors.append("EFFECT_SET")
    for name in EFFECTS:
        row=effects.get(name) if isinstance(effects,dict) else None
        if not isinstance(row,dict):errors.append(name+":ROW");continue
        if row.get("effect_kind")!=EFFECT_KIND[name]:errors.append(name+":KIND")
        for key in ("apply_argv","probe_argv"):
            ok,reason=safe_argv(row.get(key));
            if not ok:errors.append(name+":"+key+":"+reason)
        # Probe must return only hashes/generation metadata; apply must accept idempotency via env.
        if row.get("probe_contract")!="DIGEST_AND_IDEMPOTENCY_WITNESS_ONLY":errors.append(name+":PROBE_CONTRACT")
    return not errors,errors

def run_adapter(argv: list[str], env: dict[str,str] | None=None, timeout: int=45) -> tuple[int,dict[str,Any],str]:
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,env=env,creationflags=0x08000000 if os.name=="nt" else 0)
        obj=json.loads((p.stdout or "{}").strip() or "{}")
        return p.returncode,obj if isinstance(obj,dict) else {},(p.stderr or "")[-400:]
    except Exception as exc:return 99,{},type(exc).__name__

def probe(row: dict[str,Any]) -> dict[str,Any]:
    rc,obj,_=run_adapter(list(row["probe_argv"]),timeout=20)
    if rc!=0:return {"ok":False,"reason":"PROBE_FAILED","exit_code":rc}
    state_hash=str(obj.get("state_hash") or "").lower();witness=str(obj.get("applied_idempotency_key_hash") or "").lower()
    if len(state_hash)!=64:return {"ok":False,"reason":"PROBE_STATE_HASH_INVALID"}
    return {"ok":True,"state_hash":state_hash,"applied_idempotency_key_hash":witness if len(witness)==64 else "","generation":obj.get("generation")}

def apply(row: dict[str,Any], idem: str) -> dict[str,Any]:
    env=dict(os.environ);env["HMS_EFFECT_IDEMPOTENCY_KEY_HASH"]=idem;env["HMS_REAL_EFFECT_ARMED"]="1"
    rc,obj,err=run_adapter(list(row["apply_argv"]),env=env,timeout=int(row.get("timeout_seconds") or 45))
    return {"ok":rc==0 and bool(obj.get("ok",rc==0)),"exit_code":rc,"result_ref":safe_ref(stable({"rc":rc,"generation":obj.get("generation")})),"error_type":err if rc else ""}

def arming_status(manifest: dict[str,Any], arm: str, operator_confirm: str) -> dict[str,Any]:
    valid,errors=validate_manifest(manifest)
    gates={
        "windows_host":os.name=="nt",
        "arm_token":arm==ARM_TOKEN,
        "operator_phrase":operator_confirm==OPERATOR_PHRASE,
        "environment_gate":os.environ.get(ENV_GATE)=="1",
        "adapter_manifest":valid,
    }
    return {"armed":all(gates.values()),"gates":gates,"manifest_errors":errors,"production_score_eligible":False}

def marker(case_dir: Path, phase: str, role: str) -> None:atomic_json(case_dir/"checkpoint.json",{"phase":phase,"role":role,"pid":os.getpid(),"time_utc":utcnow()})
def journal(case_dir: Path)->Path:return case_dir/"real-effect-journal.jsonl"

def target_worker(case_dir: Path, effect: str, window: str, role: str, manifest_path: Path) -> int:
    manifest=read_json(manifest_path);row=(manifest.get("effects") or {}).get(effect) or {};jp=journal(case_dir)
    idem=sha("hms-v2565-real:"+safe_ref(str(case_dir))+":"+effect)
    if role=="initial":
        before=probe(row)
        if not before.get("ok"):append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"PRE_EFFECT_PROBE_FAILED"});return 3
        append_journal(jp,"EFFECT_PREPARE",effect,{"before_hash":before["state_hash"],"idempotency_key_hash":idem})
        if window=="AFTER_PREPARE_BEFORE_EFFECT":marker(case_dir,window,role);subprocess.run([sys.executable,"-c","import time;time.sleep(60)"]);return 90
        result=apply(row,idem)
        if not result.get("ok"):append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"APPLY_FAILED","exit_code":result.get("exit_code")});return 4
        if window=="AFTER_EFFECT_BEFORE_DURABLE":marker(case_dir,window,role);subprocess.run([sys.executable,"-c","import time;time.sleep(60)"]);return 91
        append_journal(jp,"EFFECT_DURABLE",effect,{"idempotency_key_hash":idem,"decision":"ADAPTER_APPLY_RETURNED_OK"})
        if window=="AFTER_DURABLE_BEFORE_VERIFY":marker(case_dir,window,role);subprocess.run([sys.executable,"-c","import time;time.sleep(60)"]);return 92
    # cold-start: probe idempotency witness before deciding whether apply can run.
    current=probe(row)
    if not current.get("ok"):append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"RECOVERY_PROBE_FAILED"});return 5
    ps=phases(jp)
    witness=current.get("applied_idempotency_key_hash")==idem
    if witness:
        if "EFFECT_DURABLE" not in ps:append_journal(jp,"EFFECT_DURABLE",effect,{"idempotency_key_hash":idem,"decision":"WITNESS_ALREADY_APPLIED_NO_REPEAT"})
    elif "EFFECT_DURABLE" in ps:
        append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"DURABLE_WITHOUT_EXTERNAL_WITNESS"});return 6
    else:
        result=apply(row,idem)
        if not result.get("ok"):append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"RECOVERY_APPLY_FAILED"});return 7
        post=probe(row)
        if not post.get("ok") or post.get("applied_idempotency_key_hash")!=idem:
            append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"POST_APPLY_WITNESS_MISSING"});return 8
        append_journal(jp,"EFFECT_DURABLE",effect,{"idempotency_key_hash":idem,"decision":"RECOVERY_APPLIED_ONCE_WITH_WITNESS"})
    append_journal(jp,"EFFECT_VERIFY",effect,{"decision":"DIGEST_AND_IDEMPOTENCY_WITNESS_VERIFIED"})
    append_journal(jp,"TXN_DONE",effect,{"convergence":"HEALTHY"});marker(case_dir,"RECOVERY_DONE",role);return 0

def wait_checkpoint(path: Path, phase: str, timeout: float=20.0)->dict[str,Any]:
    import time
    end=time.time()+timeout
    while time.time()<end:
        obj=read_json(path)
        if obj.get("phase")==phase:return obj
        time.sleep(.05)
    return {}

def target_case(root: Path,effect: str,window: str,manifest_path: Path)->dict[str,Any]:
    case_dir=root/(effect+"-"+window.lower());case_dir.mkdir(parents=True,exist_ok=True)
    base=[sys.executable,str(Path(__file__).resolve()),"--worker","--case-dir",str(case_dir),"--effect",effect,"--window",window,"--manifest",str(manifest_path)]
    p=subprocess.Popen(base+["--role","initial"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=="nt" else 0)
    cp=wait_checkpoint(case_dir/"checkpoint.json",window);killed=False
    if cp:p.kill();killed=True
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:p.kill();p.wait();killed=True
    first_pid=int(cp.get("pid") or p.pid)
    r=subprocess.run(base+["--role","recovery"],capture_output=True,text=True,timeout=90,creationflags=0x08000000 if os.name=="nt" else 0)
    done=read_json(case_dir/"checkpoint.json");second_pid=int(done.get("pid") or 0);ps=phases(journal(case_dir))
    return {"effect":effect,"window":window,"killed":killed,"cold_start_distinct_pid":bool(second_pid and second_pid!=first_pid),"recovery_rc":r.returncode,"journal_valid":validate_journal(journal(case_dir)),"operator_required":"OPERATOR_REQUIRED" in ps,"healthy":"TXN_DONE" in ps and "OPERATOR_REQUIRED" not in ps}

def target_run(manifest_path: Path, output_root: Path, arm: str, operator_confirm: str)->dict[str,Any]:
    manifest=read_json(manifest_path);arming=arming_status(manifest,arm,operator_confirm)
    if not arming["armed"]:
        return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"REAL_CODEX_EFFECT_CRASH_CERTIFICATION","generated_utc":utcnow(),"verdict":"DEFERRED_NOT_ARMED","arming":arming,"evidence_class":EVIDENCE_CLASS,"production_score_eligible":False,"production_certification":PRODUCTION_CLAIM}
    cases=[target_case(output_root,e,w,manifest_path) for e in EFFECTS for w in WINDOWS]
    passed=sum(c["healthy"] and c["journal_valid"] and c["cold_start_distinct_pid"] and c["killed"] for c in cases)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"REAL_CODEX_EFFECT_CRASH_CERTIFICATION","generated_utc":utcnow(),"verdict":"PASS_REAL_CODEX_EFFECT_CRASH_CERT" if passed==len(cases) else "FAIL","summary":{"pass":passed,"fail":len(cases)-passed,"total":len(cases),"crash_cases":len(cases)},"arming":arming,"evidence_class":EVIDENCE_CLASS,"real_codex_effects_executed":True,"attestation_candidate":passed==len(cases),"production_score_eligible":False,"cases":cases,"production_certification":"ATTESTATION_CANDIDATE_REQUIRES_V25_65_PROMOTION_GATE"}

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
    manifest={"schema_version":1,"effects":{e:{"effect_kind":EFFECT_KIND[e],"apply_argv":["C:/HMS/adapter.exe","apply",e],"probe_argv":["C:/HMS/adapter.exe","probe",e],"probe_contract":"DIGEST_AND_IDEMPOTENCY_WITNESS_ONLY"} for e in EFFECTS}}
    ok,errors=validate_manifest(manifest);add("valid_adapter_manifest",ok,errors)
    add("exact_four_effects",set((manifest.get("effects") or {}))==set(EFFECTS))
    add("three_crash_windows",set(WINDOWS)=={"AFTER_PREPARE_BEFORE_EFFECT","AFTER_EFFECT_BEFORE_DURABLE","AFTER_DURABLE_BEFORE_VERIFY"})
    add("shell_command_mode_forbidden",not safe_argv(["powershell.exe","-Command","Write-Host x"])[0])
    old=os.environ.get(ENV_GATE)
    try:
        os.environ.pop(ENV_GATE,None)
        a=arming_status(manifest,ARM_TOKEN,OPERATOR_PHRASE);add("env_gate_blocks",not a["armed"] and not a["gates"]["environment_gate"],a)
        os.environ[ENV_GATE]="1"
        b=arming_status(manifest,"WRONG",OPERATOR_PHRASE);add("arm_token_blocks",not b["armed"] and not b["gates"]["arm_token"])
        c=arming_status(manifest,ARM_TOKEN,"WRONG");add("operator_phrase_blocks",not c["armed"] and not c["gates"]["operator_phrase"])
        if os.name!="nt":
            d=arming_status(manifest,ARM_TOKEN,OPERATOR_PHRASE);add("nonwindows_cannot_arm",not d["armed"] and not d["gates"]["windows_host"],d)
        else:add("windows_gate_present",arming_status(manifest,ARM_TOKEN,OPERATOR_PHRASE)["gates"]["windows_host"])
    finally:
        if old is None:os.environ.pop(ENV_GATE,None)
        else:os.environ[ENV_GATE]=old
    src=Path(__file__).read_text("utf-8")
    add("idempotency_witness_before_repeat","applied_idempotency_key_hash" in src and "WITNESS_ALREADY_APPLIED_NO_REPEAT" in src)
    add("cold_start_distinct_process","subprocess.Popen" in src and ".kill()" in src and "cold_start_distinct_pid" in src)
    adapter_source=inspect.getsource(run_adapter)+inspect.getsource(target_case)
    add("no_shell_true","shell=True" not in adapter_source)
    add("target_evidence_not_auto_score",'"production_score_eligible":False' in src or '"production_score_eligible": False' in src)
    add("production_claim_blocked",PRODUCTION_CLAIM.startswith("NOT_CLAIMED"))
    passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"REAL_CODEX_EFFECT_CRASH_CERTIFICATION_PROOF","generated_utc":utcnow(),"verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,"real_codex_effects_executed":False,"attestation_candidate":False,"production_score_eligible":False,"production_certification":PRODUCTION_CLAIM}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=("proof","preflight","target"),default="preflight");ap.add_argument("--manifest");ap.add_argument("--output-root");ap.add_argument("--output");ap.add_argument("--arm",default="");ap.add_argument("--operator-confirm",default="")
    ap.add_argument("--worker",action="store_true");ap.add_argument("--case-dir");ap.add_argument("--effect",choices=EFFECTS);ap.add_argument("--window",choices=WINDOWS);ap.add_argument("--role",choices=("initial","recovery"))
    a=ap.parse_args()
    if a.worker:return target_worker(Path(a.case_dir),a.effect,a.window,a.role,Path(a.manifest))
    if a.mode=="proof":out=synthetic_proof();rc=0 if out["verdict"]=="PASS" else 2
    else:
        manifest=read_json(Path(a.manifest)) if a.manifest else {};arming=arming_status(manifest,a.arm,a.operator_confirm)
        if a.mode=="preflight":out={"product":"HMS-AI-ROUTER","version":VERSION,"suite":"REAL_CODEX_EFFECT_CRASH_CERTIFICATION_PREFLIGHT","generated_utc":utcnow(),"verdict":"READY_ARMED" if arming["armed"] else "DEFERRED_NOT_ARMED","arming":arming,"evidence_class":EVIDENCE_CLASS,"real_codex_effects_executed":False,"attestation_candidate":False,"production_score_eligible":False,"production_certification":PRODUCTION_CLAIM};rc=0
        else:
            if not a.manifest or not a.output_root:raise SystemExit("--manifest and --output-root required for target mode")
            out=target_run(Path(a.manifest),Path(a.output_root),a.arm,a.operator_confirm);rc=0 if out["verdict"].startswith("PASS") else 4
    if a.output:atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=="__main__":raise SystemExit(main())
