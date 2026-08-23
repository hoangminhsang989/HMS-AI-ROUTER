#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import json
import math
import os
import queue
import statistics
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.48"
SCHEMA_VERSION = 1
DEFAULT_CONCURRENCY = [1, 4, 8, 16, 32]
DEFAULT_REQUESTS_PER_LEVEL = 24
DEFAULT_TIMEOUT_SEC = 2.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], q: float) -> float | None:
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def stats(values: list[float]) -> dict[str, Any]:
    vals = [float(v) for v in values]
    if not vals:
        return {"count": 0, "min": None, "max": None, "avg": None, "p50": None, "p95": None, "p99": None}
    return {
        "count": len(vals),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
        "avg": round(statistics.fmean(vals), 3),
        "p50": round(percentile(vals, .50) or 0.0, 3),
        "p95": round(percentile(vals, .95) or 0.0, 3),
        "p99": round(percentile(vals, .99) or 0.0, 3),
    }


def safe_run_id(value: str | None) -> str:
    raw = str(value or "").strip() or f"perf-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    keep = "".join(c for c in raw if c.isalnum() or c in "-_")[:80]
    if not keep:
        raise ValueError("INVALID_RUN_ID")
    return keep


def parse_target(value: str) -> tuple[str, int]:
    host, sep, port = str(value or "").strip().rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ValueError(f"INVALID_TARGET:{value}")
    p = int(port)
    if not 1 <= p <= 65535:
        raise ValueError(f"INVALID_PORT:{value}")
    return host, p


@dataclass
class Probe:
    ok: bool
    status: int
    latency_ms: float
    ttfb_ms: float
    bytes_read: int
    error: str = ""


def health_probe(target: tuple[str, int], timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> Probe:
    host, port = target
    conn = None
    start = time.perf_counter()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=max(.05, float(timeout_sec)))
        conn.request("GET", "/hms/health", headers={"Accept": "application/json", "Connection": "close"})
        resp = conn.getresponse()
        first = time.perf_counter()
        raw = resp.read(65536)
        end = time.perf_counter()
        ok = False
        err = ""
        if resp.status != 200:
            err = f"HTTP_{resp.status}"
        else:
            try:
                body = json.loads(raw.decode("utf-8", errors="replace"))
                ok = isinstance(body, dict) and body.get("ok") is True
                if not ok:
                    err = "HEALTH_NOT_OK"
            except Exception:
                err = "INVALID_HEALTH_JSON"
        return Probe(ok, int(resp.status), round((end-start)*1000,3), round((first-start)*1000,3), len(raw), err)
    except Exception as exc:
        end = time.perf_counter()
        return Probe(False, 0, round((end-start)*1000,3), round((end-start)*1000,3), 0, type(exc).__name__)
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


class BoundedQueueGate:
    """Small deterministic admission gate used to prove bounded queue/backpressure behavior."""
    def __init__(self, workers: int, queue_capacity: int):
        self.workers = max(1, int(workers))
        self.queue_capacity = max(0, int(queue_capacity))
        self.q: queue.Queue[Any] = queue.Queue(maxsize=self.queue_capacity)
        self.stop = object()
        self.accepted = 0
        self.rejected = 0
        self.completed = 0
        self.max_depth = 0
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def start(self, work_delay_sec: float) -> None:
        def worker():
            while True:
                item = self.q.get()
                try:
                    if item is self.stop:
                        return
                    time.sleep(work_delay_sec)
                    with self._lock:
                        self.completed += 1
                finally:
                    self.q.task_done()
        for _ in range(self.workers):
            t = threading.Thread(target=worker, daemon=True)
            t.start(); self._threads.append(t)

    def submit_nowait(self, item: Any) -> bool:
        try:
            self.q.put_nowait(item)
            with self._lock:
                self.accepted += 1
                self.max_depth = max(self.max_depth, self.q.qsize())
            return True
        except queue.Full:
            with self._lock:
                self.rejected += 1
            return False

    def close(self) -> None:
        self.q.join()
        for _ in self._threads:
            self.q.put(self.stop)
        self.q.join()
        for t in self._threads:
            t.join(timeout=1.0)


def run_backpressure(workers: int = 2, queue_capacity: int = 4, burst: int = 48, work_delay_sec: float = .01) -> dict[str, Any]:
    gate = BoundedQueueGate(workers, queue_capacity)
    gate.start(work_delay_sec)
    for i in range(max(1, int(burst))):
        gate.submit_nowait(i)
    gate.close()
    return {
        "workers": gate.workers,
        "queue_capacity": gate.queue_capacity,
        "burst": burst,
        "accepted": gate.accepted,
        "rejected": gate.rejected,
        "completed": gate.completed,
        "max_queue_depth": gate.max_depth,
        "bounded": gate.max_depth <= gate.queue_capacity,
        "no_silent_drop": gate.completed == gate.accepted,
        "backpressure_observed": gate.rejected > 0,
    }


def run_http_level(targets: list[tuple[str, int]], concurrency: int, request_count: int, timeout_sec: float) -> dict[str, Any]:
    concurrency = max(1, int(concurrency)); request_count = max(1, int(request_count))
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()

    def one(i: int):
        target = targets[i % len(targets)]
        p = health_probe(target, timeout_sec)
        row = {
            "target_index": i % len(targets), "ok": p.ok, "status": p.status,
            "latency_ms": p.latency_ms, "control_plane_ttfb_ms": p.ttfb_ms,
            "bytes_read": p.bytes_read, "error": p.error,
        }
        with lock:
            rows.append(row)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="hms-perf") as ex:
        futures = [ex.submit(one, i) for i in range(request_count)]
        for f in futures:
            f.result(timeout=max(2.0, timeout_sec * 4))
    elapsed = max(.000001, time.perf_counter() - started)
    oks = [r for r in rows if r["ok"]]
    lat = [r["latency_ms"] for r in rows]
    ttfb = [r["control_plane_ttfb_ms"] for r in rows]
    per_target: dict[str, Any] = {}
    for idx in range(len(targets)):
        sub = [r for r in rows if r["target_index"] == idx]
        per_target[str(idx)] = {
            "requests": len(sub), "success": sum(1 for r in sub if r["ok"]),
            "latency_ms": stats([r["latency_ms"] for r in sub]),
            "control_plane_ttfb_ms": stats([r["control_plane_ttfb_ms"] for r in sub]),
        }
    return {
        "concurrency": concurrency,
        "requests": request_count,
        "success": len(oks),
        "fail": request_count - len(oks),
        "error_rate": round((request_count-len(oks))/request_count, 6),
        "elapsed_sec": round(elapsed, 4),
        "throughput_rps": round(request_count/elapsed, 3),
        "latency_ms": stats(lat),
        "control_plane_ttfb_ms": stats(ttfb),
        "per_target": per_target,
    }


def shared_contention(shared: Path, run_id: str, workers: int = 8, ops_per_worker: int = 12) -> dict[str, Any]:
    root = Path(shared) / ".hms_perf" / run_id
    root.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock(); latencies: list[float] = []; failures: list[str] = []

    def worker(worker_id: int):
        for i in range(ops_per_worker):
            start = time.perf_counter()
            p = root / f"w{worker_id:03d}-{i:04d}.json"
            tmp = p.with_suffix(".tmp")
            payload = {"schema": 1, "worker": worker_id, "op": i, "nonce": uuid.uuid4().hex, "time_utc": utcnow()}
            try:
                raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
                with tmp.open("wb") as fh:
                    fh.write(raw); fh.flush(); os.fsync(fh.fileno())
                os.replace(tmp, p)
                got = json.loads(p.read_text("utf-8"))
                if got.get("worker") != worker_id or got.get("op") != i:
                    raise RuntimeError("ROUNDTRIP_MISMATCH")
                p.unlink(missing_ok=True)
                with lock:
                    latencies.append((time.perf_counter()-start)*1000)
            except Exception as exc:
                with lock:
                    failures.append(type(exc).__name__)
                try: tmp.unlink(missing_ok=True)
                except Exception: pass
                try: p.unlink(missing_ok=True)
                except Exception: pass

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,workers), thread_name_prefix="hms-smb") as ex:
        fs = [ex.submit(worker, w) for w in range(max(1,workers))]
        for f in fs: f.result(timeout=30)
    elapsed = max(.000001, time.perf_counter()-started)
    try:
        root.rmdir(); root.parent.rmdir()
    except Exception:
        pass
    total = max(1, workers*ops_per_worker)
    return {
        "workers": workers, "ops_per_worker": ops_per_worker, "ops": workers*ops_per_worker,
        "success": len(latencies), "fail": len(failures), "error_rate": round(len(failures)/total,6),
        "throughput_ops_sec": round(len(latencies)/elapsed,3), "latency_ms": stats(latencies),
        "namespace": ".hms_perf/<run_id>", "errors": sorted(set(failures))[:10],
    }


def reconnect_storm(targets: list[tuple[str,int]], attempts: int = 64, concurrency: int = 16, timeout_sec: float = .8) -> dict[str, Any]:
    return run_http_level(targets, concurrency=concurrency, request_count=attempts, timeout_sec=timeout_sec)


def run(args: argparse.Namespace) -> dict[str, Any]:
    run_id = safe_run_id(args.run_id)
    router = parse_target(args.router_target) if getattr(args, "router_target", "") else None
    instances = [parse_target(x) for x in getattr(args, "instance_target", [])]
    generic = [parse_target(x) for x in args.target]
    if router or instances:
        targets = ([router] if router else []) + instances
        target_roles = (["router"] if router else []) + [f"instance-{i+1}" for i in range(len(instances))]
        multi_instance_exercised = len(instances) >= 2
    else:
        targets = generic
        target_roles = [f"target-{i+1}" for i in range(len(generic))]
        multi_instance_exercised = len(targets) >= 2
    if not targets:
        raise ValueError("AT_LEAST_ONE_TARGET_REQUIRED")
    levels = [int(x) for x in args.concurrency.split(",") if str(x).strip()]
    if not levels or any(x < 1 or x > 256 for x in levels):
        raise ValueError("INVALID_CONCURRENCY_LEVELS")
    profile_rows = [run_http_level(targets, c, args.requests_per_level, args.timeout_sec) for c in levels]
    bp = run_backpressure(args.queue_workers, args.queue_capacity, args.queue_burst, args.queue_work_delay_sec)
    storm = reconnect_storm(targets, args.reconnect_attempts, args.reconnect_concurrency, args.timeout_sec)
    shared = shared_contention(Path(args.shared), run_id, args.shared_workers, args.shared_ops_per_worker) if args.shared else None

    all_requests = sum(r["requests"] for r in profile_rows)
    all_success = sum(r["success"] for r in profile_rows)
    p95s = [r["latency_ms"]["p95"] for r in profile_rows if r["latency_ms"]["p95"] is not None]
    ttfb95s = [r["control_plane_ttfb_ms"]["p95"] for r in profile_rows if r["control_plane_ttfb_ms"]["p95"] is not None]
    throughput = [r["throughput_rps"] for r in profile_rows]
    baseline_rps = profile_rows[0]["throughput_rps"] if profile_rows else None
    peak_row = max(profile_rows, key=lambda r: r["throughput_rps"]) if profile_rows else None
    peak_rps = peak_row["throughput_rps"] if peak_row else None
    peak_concurrency = peak_row["concurrency"] if peak_row else None
    scale_rows = []
    for r in profile_rows:
        c = max(1, int(r["concurrency"]))
        rps = float(r["throughput_rps"])
        ideal = (float(baseline_rps) * c) if baseline_rps else 0.0
        efficiency = (rps / ideal) if ideal > 0 else None
        scale_rows.append({
            "concurrency": c,
            "throughput_rps": round(rps, 3),
            "vs_single_x": round(rps / float(baseline_rps), 3) if baseline_rps else None,
            "parallel_efficiency": round(efficiency, 4) if efficiency is not None else None,
            "latency_p95_ms": r["latency_ms"]["p95"],
            "control_plane_ttfb_p95_ms": r["control_plane_ttfb_ms"]["p95"],
            "error_rate": r["error_rate"],
        })
    last_rps = profile_rows[-1]["throughput_rps"] if profile_rows else None
    high_concurrency_retention = (float(last_rps) / float(peak_rps)) if peak_rps else None
    failures: list[str] = []
    warnings: list[str] = []
    if all_success != all_requests:
        failures.append("CONTROL_PLANE_REQUEST_FAILURE")
    if not bp["bounded"] or not bp["no_silent_drop"] or not bp["backpressure_observed"]:
        failures.append("BACKPRESSURE_CONTRACT_FAILURE")
    if storm["success"] != storm["requests"]:
        failures.append("RECONNECT_STORM_FAILURE")
    if shared and shared["fail"]:
        failures.append("SHARED_CONTENTION_DATA_INTEGRITY_FAILURE")
    if p95s and max(p95s) > args.warn_latency_p95_ms:
        warnings.append("CONTROL_PLANE_P95_ABOVE_WARNING_THRESHOLD")
    if ttfb95s and max(ttfb95s) > args.warn_ttfb_p95_ms:
        warnings.append("CONTROL_PLANE_TTFB_P95_ABOVE_WARNING_THRESHOLD")
    if not multi_instance_exercised:
        warnings.append("MULTI_INSTANCE_SCALE_NOT_EXERCISED")
    if not shared:
        warnings.append("LAN_CONTENTION_NOT_EXERCISED")

    result = {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "suite": "PERFORMANCE_SCALE",
        "generated_utc": utcnow(),
        "run_id": run_id,
        "verdict": "FAIL" if failures else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "production_certification": "NOT_CLAIMED",
        "metric_scope": {
            "control_plane_ttfb": "GET /hms/health response-header latency; NOT model token TTFT",
            "model_ttft": "NOT_MEASURED_NO_QUOTA_CONSUMPTION",
            "payload_capture": False,
            "authorization_capture": False,
        },
        "topology": {
            "target_count": len(targets),
            "router_configured": bool(router),
            "instance_target_count": len(instances) if (router or instances) else (len(targets) if len(targets) >= 2 else 0),
            "target_roles": target_roles,
            "target_hashes": [hashlib.sha256(f"{h}:{p}".encode()).hexdigest()[:16] for h,p in targets],
            "shared_path_hash": hashlib.sha256(str(Path(args.shared)).encode()).hexdigest() if args.shared else "",
        },
        "summary": {
            "request_success": all_success, "request_total": all_requests,
            "max_latency_p95_ms": round(max(p95s),3) if p95s else None,
            "max_control_plane_ttfb_p95_ms": round(max(ttfb95s),3) if ttfb95s else None,
            "max_throughput_rps": round(max(throughput),3) if throughput else None,
            "baseline_single_rps": round(float(baseline_rps),3) if baseline_rps is not None else None,
            "peak_concurrency": peak_concurrency,
            "high_concurrency_retention": round(high_concurrency_retention,4) if high_concurrency_retention is not None else None,
            "multi_instance_exercised": multi_instance_exercised,
            "shared_contention_exercised": bool(shared),
            "backpressure_observed": bool(bp["backpressure_observed"]),
            "reconnect_storm_requests": storm["requests"],
        },
        "concurrency_profiles": profile_rows,
        "scaling_analysis": {
            "rows": scale_rows,
            "baseline_single_rps": round(float(baseline_rps),3) if baseline_rps is not None else None,
            "peak_rps": round(float(peak_rps),3) if peak_rps is not None else None,
            "peak_concurrency": peak_concurrency,
            "high_concurrency_retention": round(high_concurrency_retention,4) if high_concurrency_retention is not None else None,
            "interpretation": "Synthetic/control-plane scaling evidence only; real Codex model throughput and token TTFT are deferred.",
        },
        "backpressure": bp,
        "reconnect_storm": storm,
        "shared_contention": shared,
        "failures": failures,
        "warnings": warnings,
        "next_certification": "v25.49 real Windows/Codex model TTFT and quota-backed request path",
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", default=[], help="Generic health target host:port (compatibility mode)")
    ap.add_argument("--router-target", default="", help="Router health target host:port")
    ap.add_argument("--instance-target", action="append", default=[], help="Managed Codex instance health target host:port")
    ap.add_argument("--shared", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--concurrency", default=",".join(str(x) for x in DEFAULT_CONCURRENCY))
    ap.add_argument("--requests-per-level", type=int, default=DEFAULT_REQUESTS_PER_LEVEL)
    ap.add_argument("--timeout-sec", type=float, default=DEFAULT_TIMEOUT_SEC)
    ap.add_argument("--queue-workers", type=int, default=2)
    ap.add_argument("--queue-capacity", type=int, default=4)
    ap.add_argument("--queue-burst", type=int, default=48)
    ap.add_argument("--queue-work-delay-sec", type=float, default=.01)
    ap.add_argument("--reconnect-attempts", type=int, default=64)
    ap.add_argument("--reconnect-concurrency", type=int, default=16)
    ap.add_argument("--shared-workers", type=int, default=8)
    ap.add_argument("--shared-ops-per-worker", type=int, default=12)
    ap.add_argument("--warn-latency-p95-ms", type=float, default=500.0)
    ap.add_argument("--warn-ttfb-p95-ms", type=float, default=300.0)
    ap.add_argument("--output")
    a = ap.parse_args()
    try:
        out = run(a)
    except Exception as exc:
        out = {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PERFORMANCE_SCALE","generated_utc":utcnow(),"verdict":"FAIL","production_certification":"NOT_CLAIMED","error":f"{type(exc).__name__}:{exc}"}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text+"\n", encoding="utf-8")
    print(text)
    return 0 if out.get("verdict") in {"PASS","PASS_WITH_WARNINGS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
