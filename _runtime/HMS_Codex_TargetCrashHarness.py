#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.63"
SCHEMA_VERSION = 1
EFFECTS = ("auth", "restart", "router", "lease")
WINDOWS = ("AFTER_PREPARE_BEFORE_EFFECT", "AFTER_EFFECT_BEFORE_DURABLE", "AFTER_DURABLE_BEFORE_VERIFY")
PRODUCTION_CLAIM = "NOT_CLAIMED_OS_PROCESS_KILL_LAB_REAL_CODEX_EFFECTS_NOT_EXECUTED"


def utcnow() -> str: return datetime.now(timezone.utc).isoformat()
def stable(o: Any) -> str: return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def sha(v: bytes | str) -> str:
    if isinstance(v, str): v = v.encode("utf-8")
    return hashlib.sha256(v).hexdigest()

def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def read_json(path: Path, default: Any = None) -> Any:
    try: return json.loads(path.read_text("utf-8-sig"))
    except Exception: return default

def append_journal(path: Path, phase: str, effect: str, meta: dict[str, Any] | None = None) -> None:
    rows = []
    if path.exists():
        for line in path.read_text("utf-8-sig").splitlines():
            if line.strip(): rows.append(json.loads(line))
    prev = rows[-1]["record_hash"] if rows else "GENESIS"
    row = {"schema_version": SCHEMA_VERSION, "version": VERSION, "seq": len(rows)+1, "phase": phase,
           "effect": effect, "time_utc": utcnow(), "meta": meta or {}, "prev_hash": prev}
    row["record_hash"] = sha(stable(row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(stable(row)+"\n"); f.flush(); os.fsync(f.fileno())

def validate_journal(path: Path) -> bool:
    if not path.exists(): return False
    prev = "GENESIS"
    try:
        for i, line in enumerate(path.read_text("utf-8-sig").splitlines(), 1):
            if not line.strip(): continue
            r = json.loads(line)
            if r.get("prev_hash") != prev: return False
            raw = {k:v for k,v in r.items() if k != "record_hash"}
            if r.get("record_hash") != sha(stable(raw)): return False
            if int(r.get("seq") or 0) != i: return False
            prev = r["record_hash"]
        return True
    except Exception:
        return False

def phase_set(path: Path) -> set[str]:
    if not path.exists(): return set()
    out=set()
    for line in path.read_text("utf-8-sig").splitlines():
        if line.strip(): out.add(str(json.loads(line).get("phase") or ""))
    return out

def desired(effect: str) -> str: return sha("v25.63-desired:"+effect)
def before(effect: str) -> str: return sha("v25.63-before:"+effect)

def world_path(case_dir: Path) -> Path: return case_dir / "world.json"
def count_path(case_dir: Path) -> Path: return case_dir / "exec-count.json"
def journal_path(case_dir: Path) -> Path: return case_dir / "journal.jsonl"

def initialize(case_dir: Path, effect: str) -> None:
    if not world_path(case_dir).exists(): atomic_json(world_path(case_dir), {"effect":effect,"hash":before(effect)})
    if not count_path(case_dir).exists(): atomic_json(count_path(case_dir), {"effect":effect,"count":0})

def apply_effect(case_dir: Path, effect: str) -> None:
    w = read_json(world_path(case_dir), {})
    c = read_json(count_path(case_dir), {"count":0})
    if w.get("hash") == desired(effect): return
    c["count"] = int(c.get("count") or 0) + 1
    atomic_json(count_path(case_dir), c)
    atomic_json(world_path(case_dir), {"effect":effect,"hash":desired(effect)})

def marker(case_dir: Path, phase: str, role: str) -> None:
    atomic_json(case_dir / "checkpoint.json", {"phase":phase,"role":role,"pid":os.getpid(),"time_utc":utcnow()})

def worker(case_dir: Path, effect: str, crash_window: str, role: str) -> int:
    initialize(case_dir,effect)
    jp=journal_path(case_dir); phases=phase_set(jp); w=read_json(world_path(case_dir),{})
    if role == "initial":
        if "EFFECT_PREPARE" not in phases: append_journal(jp,"EFFECT_PREPARE",effect,{"before_hash":before(effect),"desired_hash":desired(effect)})
        if crash_window == "AFTER_PREPARE_BEFORE_EFFECT":
            marker(case_dir,crash_window,role); time.sleep(60); return 90
        apply_effect(case_dir,effect)
        if crash_window == "AFTER_EFFECT_BEFORE_DURABLE":
            marker(case_dir,crash_window,role); time.sleep(60); return 91
        if "EFFECT_DURABLE" not in phase_set(jp): append_journal(jp,"EFFECT_DURABLE",effect,{"decision":"APPLIED_WITH_IDEMPOTENCY_KEY_HASH_ONLY"})
        if crash_window == "AFTER_DURABLE_BEFORE_VERIFY":
            marker(case_dir,crash_window,role); time.sleep(60); return 92
    # cold-start recovery: observe first, never blindly repeat.
    phases=phase_set(jp); w=read_json(world_path(case_dir),{})
    if "EFFECT_VERIFY" in phases:
        return 0
    if w.get("hash") == desired(effect):
        if "EFFECT_DURABLE" not in phases: append_journal(jp,"EFFECT_DURABLE",effect,{"decision":"OBSERVED_ALREADY_APPLIED_NO_REPEAT"})
    elif w.get("hash") == before(effect):
        if "EFFECT_DURABLE" in phases:
            append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"DURABLE_EFFECT_EXTERNAL_MISMATCH"}); return 3
        apply_effect(case_dir,effect); append_journal(jp,"EFFECT_DURABLE",effect,{"decision":"RECOVERY_APPLIED_ONCE"})
    else:
        append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"OWNERSHIP_UNPROVEN"}); return 4
    w=read_json(world_path(case_dir),{})
    if w.get("hash") != desired(effect):
        append_journal(jp,"OPERATOR_REQUIRED",effect,{"reason":"POST_EFFECT_VERIFY_MISMATCH"}); return 5
    append_journal(jp,"EFFECT_VERIFY",effect,{"decision":"EXTERNAL_EFFECT_VERIFIED"})
    append_journal(jp,"TXN_DONE",effect,{"convergence":"HEALTHY"})
    marker(case_dir,"RECOVERY_DONE",role)
    return 0

def wait_checkpoint(path: Path, expected: str, timeout: float = 8.0) -> dict[str,Any]:
    end=time.time()+timeout
    while time.time()<end:
        obj=read_json(path,{})
        if obj.get("phase")==expected: return obj
        time.sleep(.02)
    return {}

def run_case(root: Path, effect: str, window: str) -> dict[str,Any]:
    case_dir=root/f"{effect}-{window.lower()}"; case_dir.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(Path(__file__).resolve()),"--worker","--case-dir",str(case_dir),"--effect",effect,"--window",window,"--role","initial"]
    flags=0x08000000 if os.name=="nt" else 0
    p=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    cp=wait_checkpoint(case_dir/"checkpoint.json",window)
    killed=False
    if cp:
        p.kill(); killed=True
    try:p.wait(timeout=8)
    except subprocess.TimeoutExpired:
        p.kill();p.wait();killed=True
    initial_pid=int(cp.get("pid") or p.pid)
    # Cold start recovery in a distinct process.
    recover_cmd=[sys.executable,str(Path(__file__).resolve()),"--worker","--case-dir",str(case_dir),"--effect",effect,"--window",window,"--role","recovery"]
    r=subprocess.run(recover_cmd,capture_output=True,text=True,timeout=15,creationflags=flags)
    done=read_json(case_dir/"checkpoint.json",{})
    recovery_pid=int(done.get("pid") or 0)
    count=int((read_json(count_path(case_dir),{}) or {}).get("count") or 0)
    phases=phase_set(journal_path(case_dir))
    return {"effect":effect,"window":window,"killed":killed,"initial_pid":initial_pid,"recovery_pid":recovery_pid,
            "cold_start_distinct_pid":bool(recovery_pid and recovery_pid!=initial_pid),"recovery_rc":r.returncode,
            "exec_count":count,"at_most_once":count==1,"journal_valid":validate_journal(journal_path(case_dir)),
            "healthy":"TXN_DONE" in phases and "OPERATOR_REQUIRED" not in phases,
            "safe":killed and r.returncode==0 and count==1 and validate_journal(journal_path(case_dir)) and "TXN_DONE" in phases and recovery_pid!=initial_pid}

def proof() -> dict[str,Any]:
    with tempfile.TemporaryDirectory(prefix="hms-v2563-os-crash-") as td:
        root=Path(td);cases=[run_case(root,e,w) for e in EFFECTS for w in WINDOWS]
    passed=sum(c["safe"] for c in cases)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"TARGET_MACHINE_CRASH_INJECTION_HARNESS",
            "generated_utc":utcnow(),"verdict":"PASS" if passed==len(cases) else "FAIL",
            "summary":{"pass":passed,"fail":len(cases)-passed,"total":len(cases),"crash_cases":len(cases),"effects":len(EFFECTS),"windows":len(WINDOWS)},
            "host":{"os_name":os.name,"platform":sys.platform,"windows_target_evidence":os.name=="nt"},
            "cases":cases,"safety":{"subprocess_termination":True,"cold_start_new_process":True,"at_most_once_required":True,
            "real_codex_effects_executed":False,"production_certification":PRODUCTION_CLAIM}}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--proof",action="store_true");ap.add_argument("--output")
    ap.add_argument("--worker",action="store_true");ap.add_argument("--case-dir");ap.add_argument("--effect",choices=EFFECTS);ap.add_argument("--window",choices=WINDOWS);ap.add_argument("--role",choices=("initial","recovery"))
    a=ap.parse_args()
    if a.worker:
        return worker(Path(a.case_dir),a.effect,a.window,a.role)
    d=proof();txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output: atomic_json(Path(a.output),d)
    print(txt);return 0 if d["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
