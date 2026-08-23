#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import HMS_Codex_PerformanceScale as ps

VERSION = "25.48"


class HealthHandler(BaseHTTPRequestHandler):
    delay_sec = 0.0
    mode = "ok"
    def do_GET(self):
        if self.path != "/hms/health":
            self.send_response(404); self.end_headers(); return
        if self.delay_sec:
            time.sleep(self.delay_sec)
        if self.mode == "invalid_json":
            body = b"not-json"
        elif self.mode == "not_ok":
            body = b'{"ok":false}'
        else:
            body = b'{"ok":true,"service":"validator"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *_args):
        pass


def make_server(delay: float = 0.0, mode: str = "ok"):
    handler = type(f"Handler_{mode}_{int(delay*1000)}", (HealthHandler,), {"delay_sec": delay, "mode": mode})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    return srv, th


def ns(**overrides):
    d = dict(
        target=[], router_target="", instance_target=[], shared="", run_id="validator", concurrency="1,4,8,16,32", requests_per_level=10,
        timeout_sec=1.0, queue_workers=1, queue_capacity=2, queue_burst=32, queue_work_delay_sec=.02,
        reconnect_attempts=20, reconnect_concurrency=8, shared_workers=4, shared_ops_per_worker=5,
        warn_latency_p95_ms=500.0, warn_ttfb_p95_ms=300.0, output="",
    )
    d.update(overrides); return SimpleNamespace(**d)


def run(root: Path):
    checks = []
    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})

    add("version_is_25_48", ps.VERSION == VERSION, ps.VERSION)
    add("default_concurrency_levels", ps.DEFAULT_CONCURRENCY == [1,4,8,16,32], ps.DEFAULT_CONCURRENCY)
    add("model_ttft_not_faked_by_health_probe", "NOT model token TTFT" in Path(ps.__file__).read_text("utf-8"))

    try:
        ps.parse_target("bad")
        bad_rejected = False
    except ValueError:
        bad_rejected = True
    add("invalid_target_rejected", bad_rejected)

    # Basic statistics contract.
    s = ps.stats([1,2,3,4,100])
    add("percentile_statistics_present", s["count"] == 5 and s["p50"] == 3.0 and s["p95"] is not None and s["p99"] is not None, s)

    # Backpressure must remain bounded and never silently lose an admitted job.
    bp = ps.run_backpressure(workers=1, queue_capacity=2, burst=40, work_delay_sec=.02)
    add("bounded_queue_never_exceeds_capacity", bp["bounded"] and bp["max_queue_depth"] <= 2, bp)
    add("backpressure_rejects_overload", bp["backpressure_observed"] and bp["rejected"] > 0, bp)
    add("accepted_work_has_no_silent_drop", bp["no_silent_drop"] and bp["completed"] == bp["accepted"], bp)

    servers = []; threads = []
    try:
        for _ in range(2):
            srv, th = make_server(); servers.append(srv); threads.append(th)
        targets = [f"127.0.0.1:{s.server_address[1]}" for s in servers]
        p = ps.health_probe(ps.parse_target(targets[0]), .5)
        add("health_probe_application_success", p.ok and p.status == 200 and p.bytes_read > 0, p)
        add("health_probe_has_control_plane_ttfb", p.ttfb_ms >= 0 and p.ttfb_ms <= p.latency_ms + 1.0, p)

        shared = root / "shared"; shared.mkdir(parents=True, exist_ok=True)
        out = ps.run(ns(router_target=targets[0], instance_target=targets, shared=str(shared), run_id="full-matrix"))
        add("full_matrix_passes", out["verdict"] in {"PASS","PASS_WITH_WARNINGS"} and not out["failures"], out["verdict"])
        add("concurrency_profiles_exercised", [x["concurrency"] for x in out["concurrency_profiles"]] == [1,4,8,16,32], out["concurrency_profiles"])
        add("scaling_analysis_has_all_levels", [x["concurrency"] for x in out["scaling_analysis"]["rows"]] == [1,4,8,16,32], out["scaling_analysis"])
        add("scaling_baseline_is_single_concurrency", out["scaling_analysis"]["baseline_single_rps"] == out["concurrency_profiles"][0]["throughput_rps"], out["scaling_analysis"])
        add("scaling_peak_concurrency_is_observed_level", out["scaling_analysis"]["peak_concurrency"] in [1,4,8,16,32], out["scaling_analysis"])
        add("high_concurrency_retention_is_bounded", out["scaling_analysis"]["high_concurrency_retention"] is not None and 0 <= out["scaling_analysis"]["high_concurrency_retention"] <= 1.0001, out["scaling_analysis"])
        add("scale_efficiency_metric_present", all(x["parallel_efficiency"] is not None and x["parallel_efficiency"] >= 0 for x in out["scaling_analysis"]["rows"]), out["scaling_analysis"])
        add("all_control_plane_requests_succeed", out["summary"]["request_success"] == out["summary"]["request_total"], out["summary"])
        add("router_and_multi_instance_roles_explicit", out["topology"]["router_configured"] and out["topology"]["instance_target_count"] == 2 and out["topology"]["target_roles"] == ["router","instance-1","instance-2"], out["topology"])
        add("multi_instance_throughput_exercised", out["summary"]["multi_instance_exercised"] and out["topology"]["target_count"] == 3, out["summary"])
        add("per_target_distribution_present", all(len(x["per_target"]) == 3 for x in out["concurrency_profiles"]), "router + 2 instances per level")
        add("reconnect_storm_exercised", out["reconnect_storm"]["requests"] == 20 and out["reconnect_storm"]["success"] == 20, out["reconnect_storm"])
        add("shared_contention_exercised", out["shared_contention"]["success"] == 20 and out["shared_contention"]["fail"] == 0, out["shared_contention"])
        add("shared_contention_namespace_isolated", out["shared_contention"]["namespace"] == ".hms_perf/<run_id>", out["shared_contention"]["namespace"])
        add("production_certification_not_claimed", out["production_certification"] == "NOT_CLAIMED")
        add("model_ttft_explicitly_not_measured", out["metric_scope"]["model_ttft"] == "NOT_MEASURED_NO_QUOTA_CONSUMPTION", out["metric_scope"])
        add("privacy_no_payload_or_auth_capture", not out["metric_scope"]["payload_capture"] and not out["metric_scope"]["authorization_capture"], out["metric_scope"])
        serialized = json.dumps(out, ensure_ascii=False)
        add("raw_targets_not_persisted", all(t not in serialized for t in targets), "targets stored as hashes/indexes only")
        add("raw_shared_path_not_persisted", str(shared) not in serialized and bool(out["topology"]["shared_path_hash"]), out["topology"])

        # One target may run a benchmark but may not claim multi-instance coverage.
        one = ps.run(ns(target=[targets[0]], shared="", run_id="single-target", concurrency="1", requests_per_level=3, reconnect_attempts=3, reconnect_concurrency=1))
        add("single_target_marks_multi_instance_gap", "MULTI_INSTANCE_SCALE_NOT_EXERCISED" in one["warnings"] and not one["summary"]["multi_instance_exercised"], one["warnings"])
        add("missing_shared_marks_lan_gap", "LAN_CONTENTION_NOT_EXERCISED" in one["warnings"] and not one["summary"]["shared_contention_exercised"], one["warnings"])
    finally:
        for srv in servers:
            try: srv.shutdown(); srv.server_close()
            except Exception: pass
        for th in threads:
            th.join(timeout=1.0)

    # Invalid application response must fail even though TCP/HTTP works.
    bad_srv, bad_th = make_server(mode="not_ok")
    try:
        p = ps.health_probe(("127.0.0.1", bad_srv.server_address[1]), .5)
        add("health_not_ok_rejected", not p.ok and p.error == "HEALTH_NOT_OK", p)
    finally:
        bad_srv.shutdown(); bad_srv.server_close(); bad_th.join(timeout=1.0)

    invalid_srv, invalid_th = make_server(mode="invalid_json")
    try:
        p = ps.health_probe(("127.0.0.1", invalid_srv.server_address[1]), .5)
        add("invalid_health_json_rejected", not p.ok and p.error == "INVALID_HEALTH_JSON", p)
    finally:
        invalid_srv.shutdown(); invalid_srv.server_close(); invalid_th.join(timeout=1.0)

    # Closed port is explicit failure and full benchmark fails closed.
    sock = socket.socket(); sock.bind(("127.0.0.1",0)); closed_port=sock.getsockname()[1]; sock.close()
    p = ps.health_probe(("127.0.0.1", closed_port), .1)
    add("unreachable_target_failure_explicit", not p.ok and bool(p.error), p)
    failed = ps.run(ns(target=[f"127.0.0.1:{closed_port}"], concurrency="1", requests_per_level=2, reconnect_attempts=2, reconnect_concurrency=1, timeout_sec=.1))
    add("unreachable_benchmark_fails_closed", failed["verdict"] == "FAIL" and "CONTROL_PLANE_REQUEST_FAILURE" in failed["failures"], failed.get("failures"))

    passed = sum(1 for x in checks if x["ok"])
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION, "suite": "PERFORMANCE_SCALE_VALIDATION",
        "verdict": "PASS" if passed == len(checks) else "FAIL",
        "summary": {"pass": passed, "fail": len(checks)-passed, "total": len(checks)},
        "checks": checks,
        "real_codex_model_ttft": "DEFERRED_TO_V25.49",
        "real_windows_multi_instance": "DEFERRED_BY_OPERATOR",
        "real_multi_pc_smb_nas": "DEFERRED_BY_OPERATOR",
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--temp"); ap.add_argument("--output"); a=ap.parse_args()
    owned = not bool(a.temp)
    root = Path(a.temp) if a.temp else Path(tempfile.mkdtemp(prefix="hms-performance-v2548-"))
    try:
        out=run(root)
    finally:
        if owned:
            import shutil; shutil.rmtree(root, ignore_errors=True)
    text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text); return 0 if out["verdict"]=="PASS" else 2


if __name__=="__main__": raise SystemExit(main())
