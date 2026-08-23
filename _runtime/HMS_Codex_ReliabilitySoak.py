#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import platform
import secrets
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import HMS_Codex_LanPool as lp

VERSION = "25.47"
SCHEMA_VERSION = 1
DEFAULT_INTERVAL_SEC = 5.0
DEFAULT_RECOVERY_ATTEMPTS = 3
DEFAULT_RECOVERY_BUDGET_SEC = 60.0
PROFILE_DURATION_SEC = {"smoke": 30, "6h": 6 * 60 * 60, "24h": 24 * 60 * 60}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def epoch_now() -> float:
    return time.time()


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def safe_run_id(value: str) -> str:
    raw = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(value or "").strip())
    return (raw.strip("-._") or uuid.uuid4().hex)[:80]


def default_state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile_dir()
    return Path(base) / "HMS_AI_MultiRouter" / "reliability-soak-v2547"


def tempfile_dir() -> str:
    import tempfile
    return tempfile.gettempdir()


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class RunLock:
    def __init__(self, path: Path, stale_sec: float):
        self.path = path
        self.stale_sec = max(30.0, float(stale_sec))
        self.owned = False

    def _existing_is_live(self) -> bool:
        row = read_json(self.path, {}) or {}
        host = str(row.get("host") or "")
        pid = int(row.get("pid") or 0)
        same_host = not host or host.lower() == (platform.node() or socket.gethostname()).lower()
        if same_host and process_alive(pid):
            return True
        try:
            age = max(0.0, epoch_now() - self.path.stat().st_mtime)
        except OSError:
            return False
        return age <= self.stale_sec and not same_host

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                row = {"pid": os.getpid(), "host": platform.node() or socket.gethostname(), "started_utc": utcnow(), "version": VERSION}
                os.write(fd, json.dumps(row, ensure_ascii=False).encode("utf-8"))
                os.close(fd)
                self.owned = True
                return
            except FileExistsError:
                if self._existing_is_live():
                    raise RuntimeError("SOAK_RUN_ALREADY_ACTIVE")
                try:
                    self.path.unlink(missing_ok=True)
                except OSError:
                    raise RuntimeError("SOAK_RUN_LOCK_STALE_BUT_UNREMOVABLE")
        raise RuntimeError("SOAK_RUN_LOCK_ACQUIRE_FAILED")

    def refresh(self) -> None:
        if self.owned:
            try:
                self.path.touch()
            except OSError:
                pass

    def release(self) -> None:
        if self.owned:
            try:
                self.path.unlink(missing_ok=True)
            finally:
                self.owned = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: float
    error: str = ""


def tcp_probe(host: str, port: int, timeout_sec: float = 2.0) -> ProbeResult:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=max(0.1, float(timeout_sec))):
            pass
        return ProbeResult(True, round((time.perf_counter() - started) * 1000.0, 3))
    except Exception as exc:
        return ProbeResult(False, round((time.perf_counter() - started) * 1000.0, 3), type(exc).__name__)


def gateway_health_probe(host: str, port: int, timeout_sec: float = 2.0) -> ProbeResult:
    started = time.perf_counter()
    conn = None
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=max(0.1, float(timeout_sec)))
        conn.request("GET", "/hms/health", headers={"Accept": "application/json", "Connection": "close"})
        resp = conn.getresponse()
        raw = resp.read(65536)
        if resp.status != 200:
            return ProbeResult(False, round((time.perf_counter() - started) * 1000.0, 3), f"HTTP_{resp.status}")
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return ProbeResult(False, round((time.perf_counter() - started) * 1000.0, 3), "INVALID_HEALTH_JSON")
        if not isinstance(body, dict) or body.get("ok") is not True:
            return ProbeResult(False, round((time.perf_counter() - started) * 1000.0, 3), "HEALTH_NOT_OK")
        return ProbeResult(True, round((time.perf_counter() - started) * 1000.0, 3))
    except Exception as exc:
        return ProbeResult(False, round((time.perf_counter() - started) * 1000.0, 3), type(exc).__name__)
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def parse_target(value: str) -> tuple[str, int]:
    value = str(value or "").strip()
    host, sep, port = value.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ValueError(f"INVALID_TCP_TARGET:{value}")
    p = int(port)
    if p < 1 or p > 65535:
        raise ValueError(f"INVALID_TCP_PORT:{value}")
    return host, p


class ReliabilitySoak:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.state_dir = Path(args.state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = safe_run_id(args.run_id)
        self.checkpoint_path = self.state_dir / f"soak-checkpoint-v2547-{self.run_id}.json"
        self.result_path = self.state_dir / f"soak-result-v2547-{self.run_id}.json"
        self.events_path = self.state_dir / f"soak-events-v2547-{self.run_id}.jsonl"
        self.lock_path = self.state_dir / f"soak-run-v2547-{self.run_id}.lock"
        self.stop_request_path = self.state_dir / f"soak-stop-v2547-{self.run_id}.request"
        self.interval_sec = max(0.05, float(args.interval_sec))
        self.recovery_attempts = max(1, min(10, int(args.recovery_attempts)))
        self.recovery_budget_sec = max(1.0, float(args.recovery_budget_sec))
        self.target_duration_sec = self._resolve_duration()
        self.synthetic = bool(args.synthetic)
        self.shared = Path(args.shared) if args.shared else None
        self.router_target = parse_target(args.router_target) if args.router_target else None
        self.instance_targets = [parse_target(x) for x in (args.instance_target or [])]
        self.max_cycles = int(args.max_cycles or 0)
        self.fault_every = max(0, int(args.synthetic_fault_every or 0))
        self.node_name = str(args.node_name or platform.node() or socket.gethostname() or "HMS-SOAK-NODE")
        self.key, self.key_mode = self._load_key()
        self.checkpoint = self._load_or_create_checkpoint()
        self._last_mono = time.monotonic()

    def _resolve_duration(self) -> float:
        profile = str(self.args.profile)
        if profile in ("6h", "24h"):
            fixed = float(PROFILE_DURATION_SEC[profile])
            if self.args.duration_sec is not None and abs(float(self.args.duration_sec) - fixed) > 0.001:
                raise ValueError("SOAK_STANDARD_PROFILE_DURATION_IMMUTABLE")
            return fixed
        if self.args.duration_sec is not None:
            return max(0.1, float(self.args.duration_sec))
        if profile in PROFILE_DURATION_SEC:
            return float(PROFILE_DURATION_SEC[profile])
        raise ValueError("SOAK_DURATION_MISSING")

    def _load_key(self) -> tuple[bytes, str]:
        if self.synthetic:
            return lp.derive_pairing_key("HMS-V25.47-SYNTHETIC-SOAK"), "SYNTHETIC_TEST_NAMESPACE"
        raw = str(self.args.key_hex or os.environ.get("HMS_LAN_POOL_KEY_HEX", "")).strip()
        if raw:
            return lp.key_from_hex(raw), "PROTECTED_LAN_POOL_KEY_IN_MEMORY_ONLY"
        if self.shared:
            # Reliability namespace only: deterministic probe key lets GUI/CLI resume without persisting a secret.
            # It never authenticates or mutates the production LAN registry because all writes are under .hms_soak/<run_id>.
            basis = f"HMS-AI-SoakProbe-v25.47|{self.run_id}".encode("utf-8")
            return hashlib.sha256(basis).digest(), "DERIVED_SOAK_NAMESPACE_ONLY"
        return b"", "NONE"

    def _new_checkpoint(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "version": VERSION,
            "run_id": self.run_id,
            "profile": self.args.profile,
            "target_duration_sec": self.target_duration_sec,
            "active_elapsed_sec": 0.0,
            "created_utc": utcnow(),
            "last_resume_utc": utcnow(),
            "last_checkpoint_utc": utcnow(),
            "completed_utc": None,
            "cycle_count": 0,
            "session_count": 1,
            "state": "IN_PROGRESS",
            "synthetic": self.synthetic,
            "coverage": {
                "router_probe_ok": 0,
                "router_probe_fail": 0,
                "instance_probe_ok": 0,
                "instance_probe_fail": 0,
                "distinct_instance_targets": len(self.instance_targets),
                "shared_roundtrip_ok": 0,
                "shared_roundtrip_fail": 0,
                "lan_heartbeat_ok": 0,
                "lease_owner_ok": 0,
                "foreign_lease_blocked": 0,
                "node_disconnect_detected": 0,
                "node_rejoin_ok": 0,
                "transient_fault_recovered": 0,
                "recovery_exhausted": 0,
                "lease_churn_ok": 0,
            },
            "health": {
                "consecutive_failures": 0,
                "max_consecutive_failures": 0,
                "unresolved_outage_since_utc": None,
                "last_error": "",
                "fatal_error_count": 0,
                "current_outage_active_sec": 0.0,
                "max_outage_active_sec": 0.0,
                "recovery_budget_violation_count": 0,
            },
            "privacy": {
                "pairing_key_persisted": False,
                "pairing_code_persisted": False,
                "oauth_persisted": False,
                "api_key_persisted": False,
                "request_body_persisted": False,
                "shared_path_hash": sha256_text(str(self.shared)) if self.shared else "",
                "lan_key_mode": self.key_mode,
            },
        }

    def _load_or_create_checkpoint(self) -> dict[str, Any]:
        old = read_json(self.checkpoint_path, None)
        if isinstance(old, dict):
            if int(old.get("schema_version") or 0) != SCHEMA_VERSION or str(old.get("run_id")) != self.run_id:
                raise RuntimeError("SOAK_CHECKPOINT_SCHEMA_OR_RUN_ID_MISMATCH")
            if abs(float(old.get("target_duration_sec") or 0) - self.target_duration_sec) > 0.001:
                raise RuntimeError("SOAK_TARGET_DURATION_CHANGED")
            if bool(old.get("synthetic")) != self.synthetic:
                raise RuntimeError("SOAK_MODE_CHANGED")
            old["session_count"] = int(old.get("session_count") or 0) + 1
            old["last_resume_utc"] = utcnow()
            old["state"] = "IN_PROGRESS" if float(old.get("active_elapsed_sec") or 0) < self.target_duration_sec else old.get("state", "IN_PROGRESS")
            self._event("RESUME", {"active_elapsed_sec": old.get("active_elapsed_sec", 0), "session_count": old["session_count"]})
            atomic_json(self.checkpoint_path, old)
            return old
        cp = self._new_checkpoint()
        atomic_json(self.checkpoint_path, cp)
        self._event("START", {"target_duration_sec": self.target_duration_sec, "profile": self.args.profile, "synthetic": self.synthetic})
        return cp

    def _event(self, kind: str, detail: dict[str, Any] | None = None) -> None:
        row = {"time_utc": utcnow(), "version": VERSION, "run_id": self.run_id, "event": kind, "detail": detail or {}}
        append_jsonl(self.events_path, row)

    def _save_checkpoint(self) -> None:
        self.checkpoint["last_checkpoint_utc"] = utcnow()
        atomic_json(self.checkpoint_path, self.checkpoint)

    def _count(self, key: str, amount: int = 1) -> None:
        cov = self.checkpoint["coverage"]
        cov[key] = int(cov.get(key) or 0) + int(amount)

    def _mark_success(self) -> None:
        health = self.checkpoint["health"]
        if int(health.get("consecutive_failures") or 0) > 0:
            self._event("RECOVERED", {"consecutive_failures": health.get("consecutive_failures")})
        health["consecutive_failures"] = 0
        health["unresolved_outage_since_utc"] = None
        health["current_outage_active_sec"] = 0.0
        health["last_error"] = ""

    def _mark_failure(self, error: str) -> None:
        health = self.checkpoint["health"]
        n = int(health.get("consecutive_failures") or 0) + 1
        health["consecutive_failures"] = n
        health["max_consecutive_failures"] = max(int(health.get("max_consecutive_failures") or 0), n)
        health["last_error"] = str(error)[:200]
        if not health.get("unresolved_outage_since_utc"):
            health["unresolved_outage_since_utc"] = utcnow()
        self._event("CYCLE_FAILURE", {"error": str(error)[:200], "consecutive_failures": n})

    def _bounded(self, name: str, fn: Callable[[], Any], inject_first_failure: bool = False) -> tuple[bool, Any, int, float, str]:
        started = time.monotonic()
        last_error = ""
        for attempt in range(1, self.recovery_attempts + 1):
            try:
                if inject_first_failure and attempt == 1:
                    raise OSError("SYNTHETIC_TRANSIENT_SMB_DISCONNECT")
                value = fn()
                elapsed = time.monotonic() - started
                if attempt > 1:
                    self._count("transient_fault_recovered")
                    self._event("RECOVERY_SUCCESS", {"operation": name, "attempt": attempt, "elapsed_sec": round(elapsed, 6)})
                return True, value, attempt, elapsed, ""
            except Exception as exc:
                last_error = f"{type(exc).__name__}:{exc}"
                if attempt < self.recovery_attempts:
                    time.sleep(min(0.25, 0.03 * attempt))
        elapsed = time.monotonic() - started
        self._count("recovery_exhausted")
        self._event("RECOVERY_EXHAUSTED", {"operation": name, "attempts": self.recovery_attempts, "elapsed_sec": round(elapsed, 6), "error": last_error[:200]})
        return False, None, self.recovery_attempts, elapsed, last_error

    def _synthetic_shared(self) -> Path:
        assert self.shared is not None
        return self.shared / "_hms_soak" / self.run_id

    def _shared_roundtrip(self, cycle: int) -> None:
        if not self.shared:
            return
        base = self._synthetic_shared() if self.synthetic else self.shared / ".hms_soak" / self.run_id
        probe = base / "io-probe" / f"{self.node_name}-{os.getpid()}.json"
        inject = bool(self.synthetic and self.fault_every and cycle % self.fault_every == 0)

        def op():
            payload = {"schema_version": 1, "run_id": self.run_id, "node_name_hash": sha256_text(self.node_name), "cycle": cycle, "time_utc": utcnow()}
            lp.atomic_json(probe, payload)
            got = read_json(probe, {}) or {}
            if got.get("run_id") != self.run_id or int(got.get("cycle") or -1) != cycle:
                raise OSError("SHARED_ROUNDTRIP_READBACK_MISMATCH")
            probe.unlink(missing_ok=True)
            return True

        ok, _, attempts, elapsed, err = self._bounded("shared_roundtrip", op, inject_first_failure=inject)
        if ok:
            self._count("shared_roundtrip_ok")
            if elapsed > self.recovery_budget_sec:
                self._mark_failure(f"SHARED_RECOVERY_BUDGET_EXCEEDED:{elapsed:.3f}")
            self._event("SHARED_ROUNDTRIP_OK", {"cycle": cycle, "attempts": attempts, "latency_ms": round(elapsed * 1000, 3)})
        else:
            self._count("shared_roundtrip_fail")
            self._mark_failure(err)

    def _network_probes(self) -> None:
        any_failure = False
        if self.router_target:
            r = gateway_health_probe(*self.router_target, timeout_sec=min(2.0, max(0.2, self.interval_sec)))
            self._count("router_probe_ok" if r.ok else "router_probe_fail")
            self._event("ROUTER_PROBE", {"ok": r.ok, "latency_ms": r.latency_ms, "error": r.error})
            any_failure |= not r.ok
        for host, port in self.instance_targets:
            r = gateway_health_probe(host, port, timeout_sec=min(2.0, max(0.2, self.interval_sec)))
            self._count("instance_probe_ok" if r.ok else "instance_probe_fail")
            self._event("INSTANCE_PROBE", {"target_hash": sha256_text(f"{host}:{port}"), "ok": r.ok, "latency_ms": r.latency_ms, "error": r.error})
            any_failure |= not r.ok
        if any_failure:
            self._mark_failure("ROUTER_OR_INSTANCE_PROBE_FAILED")

    def _lan_cycle(self, cycle: int) -> None:
        if not self.shared or not self.key:
            return
        base = self._synthetic_shared() if self.synthetic else self.shared / ".hms_soak" / self.run_id / "lan-registry"
        local = self.state_dir / f"node-v2547-{self.run_id}.json"
        node_a = lp.ensure_node(local, self.node_name)
        # Synthetic mode uses a second logical node on the same host to exercise ownership collisions.
        peer_state = self.state_dir / f"peer-v2547-{self.run_id}.json"
        node_b = lp.ensure_node(peer_state, self.node_name + "-PEER") if self.synthetic else None
        project = {"project_dir": str(self.state_dir / "synthetic-project"), "logical_id": "hms-soak:" + self.run_id, "project_label": "HMS Reliability Soak"}
        try:
            lp.heartbeat(base, self.key, node_a, {"health": "READY", "capacity": 2, "running_instances": len(self.instance_targets)}, 15)
            self._count("lan_heartbeat_ok")
            if node_b:
                lp.heartbeat(base, self.key, node_b, {"health": "READY", "capacity": 1, "running_instances": 0}, 15)
            owner = lp.acquire_lease(base, self.key, node_a, project, 15)
            if not owner.get("ok"):
                raise RuntimeError("SOAK_OWNER_LEASE_FAILED:" + str(owner.get("status")))
            self._count("lease_owner_ok")
            if node_b:
                blocked = lp.acquire_lease(base, self.key, node_b, project, 15)
                if blocked.get("ok") or blocked.get("status") != "BLOCKED_OWNED_BY_OTHER_NODE":
                    raise RuntimeError("SOAK_FOREIGN_SILENT_TAKEOVER")
                self._count("foreign_lease_blocked")
                # Accelerated logical time verifies disconnect->stale->rejoin without waiting 15 seconds.
                if cycle % 3 == 0:
                    now = lp.epoch_now()
                    rows = lp.read_nodes(base, self.key, now_epoch=now + 16)
                    peer = next((x for x in rows if x.get("node_id") == node_b["node_id"]), None)
                    if not peer or peer.get("state") != "STALE":
                        raise RuntimeError("SOAK_NODE_DISCONNECT_NOT_DETECTED")
                    self._count("node_disconnect_detected")
                    lp.heartbeat(base, self.key, node_b, {"health": "READY", "capacity": 1, "running_instances": 0}, 15)
                    rows = lp.read_nodes(base, self.key)
                    peer = next((x for x in rows if x.get("node_id") == node_b["node_id"]), None)
                    if not peer or peer.get("state") != "ONLINE":
                        raise RuntimeError("SOAK_NODE_REJOIN_FAILED")
                    self._count("node_rejoin_ok")
            if node_b and cycle % 4 == 0:
                # Lease churn: explicit release -> peer acquire -> old owner blocked -> peer release -> owner reacquire.
                rel_a = lp.release_lease(base, self.key, node_a, project)
                acq_b = lp.acquire_lease(base, self.key, node_b, project, 15)
                blocked_a = lp.acquire_lease(base, self.key, node_a, project, 15)
                rel_b = lp.release_lease(base, self.key, node_b, project)
                acq_a = lp.acquire_lease(base, self.key, node_a, project, 15)
                churn_ok = (rel_a.get("ok") and acq_b.get("ok") and not blocked_a.get("ok")
                            and blocked_a.get("status") == "BLOCKED_OWNED_BY_OTHER_NODE"
                            and rel_b.get("ok") and acq_a.get("ok"))
                if not churn_ok:
                    raise RuntimeError("SOAK_LEASE_CHURN_FAILED")
                self._count("lease_churn_ok")
            self._event("LAN_CYCLE_OK", {"cycle": cycle, "lease_epoch": int(owner.get("lease", {}).get("epoch") or 0), "foreign_takeover_blocked": bool(node_b)})
        except Exception as exc:
            self._mark_failure(f"LAN_CYCLE:{type(exc).__name__}:{exc}")

    def _coverage_ready(self) -> tuple[bool, list[str]]:
        cov = self.checkpoint["coverage"]
        missing: list[str] = []
        # A real 6h/24h soak is meaningful only with the full target topology.
        if not self.synthetic and self.args.profile in ("6h", "24h"):
            if not self.router_target:
                missing.append("required_router_target")
            if len(self.instance_targets) < 2:
                missing.append("required_two_instance_targets")
            if not self.shared:
                missing.append("required_shared_lan_path")
        if self.shared:
            if int(cov.get("shared_roundtrip_ok") or 0) < 1:
                missing.append("shared_roundtrip")
            if self.key and int(cov.get("lan_heartbeat_ok") or 0) < 1:
                missing.append("lan_heartbeat")
            if self.key and int(cov.get("lease_owner_ok") or 0) < 1:
                missing.append("lease_owner")
        if self.router_target and int(cov.get("router_probe_ok") or 0) < 1:
            missing.append("router_probe")
        if self.instance_targets and int(cov.get("instance_probe_ok") or 0) < len(self.instance_targets):
            missing.append("instance_probe")
        if self.synthetic:
            for key in ("foreign_lease_blocked", "node_disconnect_detected", "node_rejoin_ok", "transient_fault_recovered", "lease_churn_ok"):
                if key == "transient_fault_recovered":
                    if self.fault_every and int(cov.get(key) or 0) < 1:
                        missing.append(key)
                elif int(cov.get(key) or 0) < 1:
                    missing.append(key)
        return not missing, missing

    def result(self, terminal: bool = False) -> dict[str, Any]:
        cp = self.checkpoint
        active = float(cp.get("active_elapsed_sec") or 0.0)
        duration_done = active + 1e-9 >= self.target_duration_sec
        coverage_ok, missing = self._coverage_ready()
        fatal = int(cp.get("health", {}).get("fatal_error_count") or 0)
        exhausted = int(cp.get("coverage", {}).get("recovery_exhausted") or 0)
        unresolved = bool(cp.get("health", {}).get("unresolved_outage_since_utc"))
        budget_violations = int(cp.get("health", {}).get("recovery_budget_violation_count") or 0)
        # A completed synthetic self-test may pass with injected/recovered failures; exhausted/unbounded recovery never passes.
        passable = duration_done and coverage_ok and fatal == 0 and exhausted == 0 and budget_violations == 0 and not unresolved
        if passable:
            verdict = "PASS"
        elif terminal and duration_done:
            verdict = "FAIL"
        else:
            verdict = "IN_PROGRESS"
        evidence = {
            "product": "HMS-AI-ROUTER",
            "version": VERSION,
            "suite": "RELIABILITY_SOAK",
            "run_id": self.run_id,
            "generated_utc": utcnow(),
            "profile": self.args.profile,
            "target_duration_sec": self.target_duration_sec,
            "active_elapsed_sec": round(active, 6),
            "progress_pct": round(min(100.0, active / self.target_duration_sec * 100.0), 4),
            "session_count": int(cp.get("session_count") or 0),
            "cycle_count": int(cp.get("cycle_count") or 0),
            "verdict": verdict,
            "duration_complete": duration_done,
            "coverage_complete": coverage_ok,
            "missing_coverage": missing,
            "coverage": cp.get("coverage", {}),
            "health": cp.get("health", {}),
            "privacy": cp.get("privacy", {}),
            "resume_semantics": "ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED",
            "production_certification": "NOT_CLAIMED",
            "soak_certificate_scope": "SYNTHETIC_HARNESS_ONLY" if self.synthetic else ("SINGLE_NODE_DURATION_AND_TARGET_PROBES" if verdict == "PASS" else "NOT_YET"),
            "real_multi_pc_smb_nas": "NOT_PROVEN_BY_SINGLE_NODE_HARNESS",
            "checkpoint": str(self.checkpoint_path),
            "events": str(self.events_path),
        }
        return evidence

    def _stop_requested(self) -> bool:
        return self.stop_request_path.exists()

    def _pause_for_stop_request(self) -> dict[str, Any]:
        try:
            self.stop_request_path.unlink(missing_ok=True)
        except OSError:
            pass
        self.checkpoint["state"] = "PAUSED"
        self._save_checkpoint()
        self._event("STOP_REQUESTED", {"active_elapsed_sec": self.checkpoint.get("active_elapsed_sec", 0), "cycle_count": self.checkpoint.get("cycle_count", 0)})
        out = self.result(terminal=False)
        atomic_json(self.result_path, out)
        return out

    def run(self) -> dict[str, Any]:
        lock_stale = max(120.0, self.interval_sec * 6.0)
        with RunLock(self.lock_path, lock_stale) as lock:
            if self.checkpoint.get("state") == "PASS" and float(self.checkpoint.get("active_elapsed_sec") or 0) >= self.target_duration_sec:
                return self.result(terminal=True)
            cycles_this_session = 0
            self._last_mono = time.monotonic()
            while float(self.checkpoint.get("active_elapsed_sec") or 0) < self.target_duration_sec:
                if self._stop_requested():
                    return self._pause_for_stop_request()
                cycle_start = time.monotonic()
                cycle = int(self.checkpoint.get("cycle_count") or 0) + 1
                failures_before = int(self.checkpoint.get("health", {}).get("consecutive_failures") or 0)
                self._network_probes()
                self._shared_roundtrip(cycle)
                self._lan_cycle(cycle)
                # A cycle with no new failure clears prior transient outage state.
                failures_after = int(self.checkpoint.get("health", {}).get("consecutive_failures") or 0)
                if failures_after == failures_before:
                    self._mark_success()
                self.checkpoint["cycle_count"] = cycle
                cycles_this_session += 1

                # Only monotonic time while this process is alive is credited. Downtime between sessions is never added.
                now_mono = time.monotonic()
                active_delta = max(0.0, now_mono - self._last_mono)
                self.checkpoint["active_elapsed_sec"] = min(self.target_duration_sec, float(self.checkpoint.get("active_elapsed_sec") or 0.0) + active_delta)
                health = self.checkpoint["health"]
                if health.get("unresolved_outage_since_utc"):
                    health["current_outage_active_sec"] = float(health.get("current_outage_active_sec") or 0.0) + active_delta
                    health["max_outage_active_sec"] = max(float(health.get("max_outage_active_sec") or 0.0), float(health["current_outage_active_sec"]))
                    if float(health["current_outage_active_sec"]) > self.recovery_budget_sec and int(health.get("recovery_budget_violation_count") or 0) == 0:
                        health["recovery_budget_violation_count"] = 1
                        self._event("RECOVERY_BUDGET_EXCEEDED", {"active_outage_sec": round(float(health["current_outage_active_sec"]), 6), "budget_sec": self.recovery_budget_sec})
                self._last_mono = now_mono
                self._save_checkpoint()
                lock.refresh()
                if self._stop_requested():
                    return self._pause_for_stop_request()

                if self.max_cycles and cycles_this_session >= self.max_cycles:
                    self._event("SESSION_STOP_MAX_CYCLES", {"cycles_this_session": cycles_this_session, "active_elapsed_sec": self.checkpoint["active_elapsed_sec"]})
                    out = self.result(terminal=False)
                    atomic_json(self.result_path, out)
                    return out

                if float(self.checkpoint.get("active_elapsed_sec") or 0) >= self.target_duration_sec:
                    break
                spent = time.monotonic() - cycle_start
                sleep_for = max(0.0, self.interval_sec - spent)
                if sleep_for:
                    time.sleep(sleep_for)
                    # credit the sleep because the harness is alive during this interval
                    now_mono = time.monotonic()
                    sleep_delta = max(0.0, now_mono - self._last_mono)
                    self.checkpoint["active_elapsed_sec"] = min(self.target_duration_sec, float(self.checkpoint.get("active_elapsed_sec") or 0.0) + sleep_delta)
                    health = self.checkpoint["health"]
                    if health.get("unresolved_outage_since_utc"):
                        health["current_outage_active_sec"] = float(health.get("current_outage_active_sec") or 0.0) + sleep_delta
                        health["max_outage_active_sec"] = max(float(health.get("max_outage_active_sec") or 0.0), float(health["current_outage_active_sec"]))
                        if float(health["current_outage_active_sec"]) > self.recovery_budget_sec and int(health.get("recovery_budget_violation_count") or 0) == 0:
                            health["recovery_budget_violation_count"] = 1
                            self._event("RECOVERY_BUDGET_EXCEEDED", {"active_outage_sec": round(float(health["current_outage_active_sec"]), 6), "budget_sec": self.recovery_budget_sec})
                    self._last_mono = now_mono
                    self._save_checkpoint()
                    lock.refresh()

            out = self.result(terminal=True)
            self.checkpoint["state"] = out["verdict"]
            self.checkpoint["completed_utc"] = utcnow()
            self._save_checkpoint()
            self._event("COMPLETE", {"verdict": out["verdict"], "active_elapsed_sec": out["active_elapsed_sec"]})
            out = self.result(terminal=True)
            atomic_json(self.result_path, out)
            return out


def status_for(state_dir: Path, run_id: str) -> dict[str, Any]:
    rid = safe_run_id(run_id)
    cp = read_json(state_dir / f"soak-checkpoint-v2547-{rid}.json", None)
    result = read_json(state_dir / f"soak-result-v2547-{rid}.json", None)
    if not isinstance(cp, dict):
        return {"ok": False, "version": VERSION, "run_id": rid, "error": "SOAK_CHECKPOINT_NOT_FOUND"}
    return {"ok": True, "version": VERSION, "run_id": rid, "checkpoint": cp, "result": result,
            "stop_requested": (state_dir / f"soak-stop-v2547-{rid}.request").exists()}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="HMS-AI-ROUTER v25.47 resumable reliability/soak harness")
    ap.add_argument("--mode", choices=("run", "status", "stop"), default="run")
    ap.add_argument("--profile", choices=("smoke", "6h", "24h", "custom"), default="smoke")
    ap.add_argument("--duration-sec", type=float)
    ap.add_argument("--interval-sec", type=float, default=DEFAULT_INTERVAL_SEC)
    ap.add_argument("--state-dir", default=str(default_state_dir()))
    ap.add_argument("--run-id", default="default")
    ap.add_argument("--shared", default="")
    ap.add_argument("--key-hex", default="")
    ap.add_argument("--router-target", default="", help="TCP target host:port for the global Router")
    ap.add_argument("--instance-target", action="append", default=[], help="repeatable TCP host:port for isolated instance routers")
    ap.add_argument("--node-name", default="")
    ap.add_argument("--recovery-attempts", type=int, default=DEFAULT_RECOVERY_ATTEMPTS)
    ap.add_argument("--recovery-budget-sec", type=float, default=DEFAULT_RECOVERY_BUDGET_SEC)
    ap.add_argument("--max-cycles", type=int, default=0, help="test/controlled interruption; leaves verdict IN_PROGRESS")
    ap.add_argument("--synthetic", action="store_true", help="isolated deterministic fault-injection mode; never production certification")
    ap.add_argument("--synthetic-fault-every", type=int, default=3)
    ap.add_argument("--output", default="")
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    try:
        if args.mode == "status":
            out = status_for(Path(args.state_dir), args.run_id)
            code = 0 if out.get("ok") else 2
        elif args.mode == "stop":
            state_dir = Path(args.state_dir)
            rid = safe_run_id(args.run_id)
            cp = read_json(state_dir / f"soak-checkpoint-v2547-{rid}.json", None)
            if not isinstance(cp, dict):
                out = {"ok": False, "version": VERSION, "run_id": rid, "error": "SOAK_CHECKPOINT_NOT_FOUND"}; code = 2
            else:
                stop_path = state_dir / f"soak-stop-v2547-{rid}.request"
                stop_path.parent.mkdir(parents=True, exist_ok=True)
                stop_path.write_text(utcnow() + "\n", encoding="ascii")
                out = {"ok": True, "version": VERSION, "run_id": rid, "status": "STOP_REQUESTED", "note": "Harness will checkpoint and pause; no process kill is performed."}; code = 0
        else:
            harness = ReliabilitySoak(args)
            out = harness.run()
            code = 0 if out.get("verdict") in ("PASS", "IN_PROGRESS") else 2
    except Exception as exc:
        out = {"ok": False, "version": VERSION, "error": f"{type(exc).__name__}:{exc}"}
        code = 2
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        atomic_json(Path(args.output), out)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
