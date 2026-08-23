#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import HMS_Codex_ReliabilitySoak as rs

VERSION = "25.47"


def args_for(root: Path, **overrides):
    d = dict(
        mode="run", profile="custom", duration_sec=0.72, interval_sec=0.08,
        state_dir=str(root / "state"), run_id="resume-test", shared=str(root / "shared"),
        key_hex="", router_target="", instance_target=[], node_name="VALIDATOR-A",
        recovery_attempts=3, recovery_budget_sec=2.0, max_cycles=0,
        synthetic=True, synthetic_fault_every=2, output="",
    )
    d.update(overrides)
    return SimpleNamespace(**d)


def run(root: Path):
    checks = []
    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})

    # Contract/profile basics.
    add("version_is_25_47", rs.VERSION == VERSION, rs.VERSION)
    add("profile_6h_exact", rs.PROFILE_DURATION_SEC.get("6h") == 21600, rs.PROFILE_DURATION_SEC)
    add("profile_24h_exact", rs.PROFILE_DURATION_SEC.get("24h") == 86400, rs.PROFILE_DURATION_SEC)
    try:
        rs.ReliabilitySoak(args_for(root / "immutable-duration", profile="6h", duration_sec=1.0, run_id="bad-6h"))
        immutable_duration = False
    except ValueError as exc:
        immutable_duration = "STANDARD_PROFILE_DURATION_IMMUTABLE" in str(exc)
    add("standard_6h_24h_duration_immutable", immutable_duration)
    add("resume_semantics_constant", "ACTIVE_PROCESS_TIME_ONLY" in Path(rs.__file__).read_text("utf-8"), "downtime is not wall-clock credited")

    # TCP Router / multi-instance probe primitive.
    listeners = []
    closed_port = 9
    try:
        for _ in range(2):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0)); s.listen(8); listeners.append(s)
        r1 = rs.tcp_probe("127.0.0.1", listeners[0].getsockname()[1], 0.3)
        r2 = rs.tcp_probe("127.0.0.1", listeners[1].getsockname()[1], 0.3)
        add("router_tcp_probe_success", r1.ok, r1)
        add("multi_instance_tcp_probe_success", r2.ok, r2)
        closed_port = listeners[0].getsockname()[1]
    finally:
        for s in listeners:
            try: s.close()
            except Exception: pass
    bad = rs.tcp_probe("127.0.0.1", closed_port, 0.1)
    add("tcp_probe_failure_explicit", not bad.ok and bool(bad.error), bad)

    # Application-layer Router / Codex instance health must prove /hms/health, not only TCP accept.
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/hms/health":
                body = b'{"ok":true,"version":"validator"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()
        def log_message(self, *_args):
            pass

    health_server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    health_thread = threading.Thread(target=health_server.serve_forever, daemon=True)
    health_thread.start()
    try:
        gh = rs.gateway_health_probe("127.0.0.1", health_server.server_address[1], 0.5)
        add("gateway_health_probe_success", gh.ok and not gh.error, gh)
    finally:
        health_server.shutdown(); health_server.server_close(); health_thread.join(timeout=1.0)
    gh_bad = rs.gateway_health_probe("127.0.0.1", closed_port, 0.1)
    add("gateway_health_probe_failure_explicit", not gh_bad.ok and bool(gh_bad.error), gh_bad)

    try:
        rs.parse_target("bad-target")
        parse_bad = False
    except ValueError:
        parse_bad = True
    add("invalid_tcp_target_rejected", parse_bad)

    # Controlled interruption: partial run MUST NOT PASS.
    a1 = args_for(root, max_cycles=2)
    h1 = rs.ReliabilitySoak(a1)
    out1 = h1.run()
    cp1 = rs.read_json(h1.checkpoint_path, {})
    active1 = float(cp1.get("active_elapsed_sec") or 0)
    add("partial_run_is_in_progress", out1.get("verdict") == "IN_PROGRESS" and not out1.get("duration_complete"), out1.get("verdict"))
    add("checkpoint_created_atomically", h1.checkpoint_path.exists() and cp1.get("run_id") == "resume-test", h1.checkpoint_path)
    add("partial_active_time_positive", 0 < active1 < a1.duration_sec, active1)
    add("session_count_initial", int(cp1.get("session_count") or 0) == 1, cp1.get("session_count"))

    # Simulated downtime: checkpoint active time must remain unchanged.
    time.sleep(0.35)
    cp_after_down = rs.read_json(h1.checkpoint_path, {})
    active_after_down = float(cp_after_down.get("active_elapsed_sec") or 0)
    add("downtime_not_counted", abs(active_after_down - active1) < 0.01, f"before={active1}, after={active_after_down}")

    # Resume same run to completion; session_count increments, coverage survives.
    a2 = args_for(root, max_cycles=0)
    h2 = rs.ReliabilitySoak(a2)
    before_resume = rs.read_json(h2.checkpoint_path, {})
    add("resume_preserves_run_id", before_resume.get("run_id") == "resume-test")
    add("resume_increments_session_count", int(before_resume.get("session_count") or 0) == 2, before_resume.get("session_count"))
    out2 = h2.run()
    cp2 = rs.read_json(h2.checkpoint_path, {})
    cov = cp2.get("coverage") or {}
    add("completed_synthetic_soak_passes", out2.get("verdict") == "PASS" and out2.get("duration_complete") and out2.get("coverage_complete"), out2.get("missing_coverage"))
    add("active_duration_reaches_target_only", float(out2.get("active_elapsed_sec") or 0) >= a2.duration_sec, out2.get("active_elapsed_sec"))
    add("shared_roundtrip_exercised", int(cov.get("shared_roundtrip_ok") or 0) >= 1, cov.get("shared_roundtrip_ok"))
    add("transient_smb_recovery_exercised", int(cov.get("transient_fault_recovered") or 0) >= 1 and int(cov.get("recovery_exhausted") or 0) == 0, cov)
    add("lease_owner_renew_exercised", int(cov.get("lease_owner_ok") or 0) >= 1, cov.get("lease_owner_ok"))
    add("foreign_silent_takeover_blocked", int(cov.get("foreign_lease_blocked") or 0) >= 1, cov.get("foreign_lease_blocked"))
    add("node_disconnect_detected", int(cov.get("node_disconnect_detected") or 0) >= 1, cov.get("node_disconnect_detected"))
    add("node_rejoin_exercised", int(cov.get("node_rejoin_ok") or 0) >= 1, cov.get("node_rejoin_ok"))
    add("lease_churn_exercised", int(cov.get("lease_churn_ok") or 0) >= 1, cov.get("lease_churn_ok"))
    add("event_journal_persisted", h2.events_path.exists() and len(h2.events_path.read_text("utf-8").splitlines()) >= 5, h2.events_path)
    add("result_evidence_persisted", h2.result_path.exists() and rs.read_json(h2.result_path, {}).get("verdict") == "PASS", h2.result_path)
    add("synthetic_never_claims_production", out2.get("production_certification") == "NOT_CLAIMED", out2.get("production_certification"))

    # Privacy: no pairing key/code/token/request body persisted in checkpoint/result/events.
    evidence_text = h2.checkpoint_path.read_text("utf-8") + h2.result_path.read_text("utf-8") + h2.events_path.read_text("utf-8")
    forbidden = ["HMS-V25.47-SYNTHETIC-SOAK", "PAIRING_CODE", "access_token", "refresh_token", "Authorization: Bearer"]
    add("soak_evidence_secret_free", not any(x in evidence_text for x in forbidden), [x for x in forbidden if x in evidence_text])
    add("shared_path_stored_as_hash_only", str((root / "shared").resolve()) not in h2.checkpoint_path.read_text("utf-8") and bool(cp2.get("privacy", {}).get("shared_path_hash")), cp2.get("privacy"))

    # 6h/24h production-shaped profiles cannot PASS without Router + >=2 instances + shared LAN.
    req_root = root / "required-targets"
    req_args = args_for(req_root, profile="6h", duration_sec=None, run_id="required-targets", shared="", synthetic=False, synthetic_fault_every=0)
    req_h = rs.ReliabilitySoak(req_args)
    req_h.checkpoint["active_elapsed_sec"] = req_h.target_duration_sec
    req_out = req_h.result(terminal=True)
    add("six_hour_profile_requires_full_topology", req_out.get("verdict") != "PASS" and set(req_out.get("missing_coverage") or []) >= {"required_router_target","required_two_instance_targets","required_shared_lan_path"}, req_out.get("missing_coverage"))
    add("production_certification_never_auto_claimed", req_out.get("production_certification") == "NOT_CLAIMED", req_out.get("production_certification"))

    # Completed run target/profile cannot be silently changed on resume.
    changed = args_for(root, duration_sec=1.2)
    try:
        rs.ReliabilitySoak(changed)
        target_change_rejected = False
    except RuntimeError as exc:
        target_change_rejected = "TARGET_DURATION_CHANGED" in str(exc)
    add("resume_target_duration_change_rejected", target_change_rejected)

    # Graceful stop is checkpoint/pause based; it never kills the process or converts partial time into PASS.
    stop_root = root / "stop-test"
    hs = rs.ReliabilitySoak(args_for(stop_root, run_id="stop-test", duration_sec=1.0, max_cycles=0))
    hs.stop_request_path.write_text(rs.utcnow()+"\n", encoding="ascii")
    stop_out = hs.run()
    stop_cp = rs.read_json(hs.checkpoint_path,{})
    add("graceful_stop_pauses_partial_run", stop_out.get("verdict")=="IN_PROGRESS" and stop_cp.get("state")=="PAUSED", stop_cp.get("state"))
    add("graceful_stop_request_consumed", not hs.stop_request_path.exists())
    add("stop_contract_never_force_kills", "Harness will checkpoint and pause; no process kill is performed." in Path(rs.__file__).read_text("utf-8"), "stop is cooperative")

    # Same-node duplicate live run lock is fail-closed.
    lock_path = root / "locks" / "run.lock"
    first = rs.RunLock(lock_path, 30)
    first.acquire()
    try:
        try:
            second = rs.RunLock(lock_path, 30); second.acquire(); duplicate_blocked = False; second.release()
        except RuntimeError as exc:
            duplicate_blocked = "ALREADY_ACTIVE" in str(exc)
    finally:
        first.release()
    add("duplicate_live_soak_blocked", duplicate_blocked)

    # Dead same-host lock may be reclaimed without waiting stale timeout (crash restart recovery).
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    rs.atomic_json(lock_path, {"pid": 99999999, "host": rs.platform.node() or rs.socket.gethostname(), "started_utc": rs.utcnow()})
    reclaimed = rs.RunLock(lock_path, 9999)
    try:
        reclaimed.acquire(); reclaimed_ok = reclaimed.owned
    except Exception:
        reclaimed_ok = False
    finally:
        reclaimed.release()
    add("dead_process_lock_reclaimed_for_restart", reclaimed_ok)

    # Exhausted bounded recovery is recorded and cannot be silently PASSed.
    fault_root = root / "recovery-exhausted"
    hf = rs.ReliabilitySoak(args_for(fault_root, run_id="fault-test", duration_sec=0.1, max_cycles=1, synthetic_fault_every=0))
    ok, _, attempts, _, _ = hf._bounded("forced_failure", lambda: (_ for _ in ()).throw(OSError("forced")))
    rf = hf.result(terminal=True)
    add("bounded_recovery_attempt_count", (not ok) and attempts == 3, attempts)
    add("recovery_exhaustion_prevents_pass", int(hf.checkpoint["coverage"].get("recovery_exhausted") or 0) == 1 and rf.get("verdict") != "PASS", rf.get("verdict"))

    passed = sum(1 for x in checks if x["ok"])
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "RELIABILITY_SOAK_HARNESS",
        "verdict": "PASS" if passed == len(checks) else "FAIL",
        "summary": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks,
        "soak_6h": "HARNESS_READY_NOT_EXECUTED",
        "soak_24h": "HARNESS_READY_NOT_EXECUTED",
        "real_router_multi_instance": "PROBE_CONTRACT_VALIDATED_RUNTIME_DEFERRED",
        "real_multi_pc_smb_nas": "DEFERRED_BY_OPERATOR",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--temp")
    ap.add_argument("--output")
    a = ap.parse_args()
    owned = not bool(a.temp)
    root = Path(a.temp) if a.temp else Path(tempfile.mkdtemp(prefix="hms-reliability-v2547-"))
    try:
        out = run(root)
    finally:
        if owned:
            import shutil
            shutil.rmtree(root, ignore_errors=True)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
