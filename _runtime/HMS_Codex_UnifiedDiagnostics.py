#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "25.74"
SCHEMA = 1
MAX_EVENTS_DEFAULT = 600

SECRET_KEY = re.compile(r"(?i)(token|secret|password|api[_-]?key|authorization|cookie|credential|oauth|refresh[_-]?token|access[_-]?token|id[_-]?token|client[_-]?secret)")
PROMPT_KEY = re.compile(r"(?i)(prompt|request_body|response_body|body|content|tool_arguments|arguments|input_text|output_text|messages?)")
BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+\-/=]+")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
KEYLIKE = re.compile(r"\b(?:sk[-_]|hms[-_])[A-Za-z0-9._\-]{10,}\b", re.I)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return s[:64]


def redact_text(value: Any, limit: int = 260) -> str:
    s = str(value or "")
    s = BEARER.sub("Bearer <REDACTED>", s)
    s = JWT.sub("<REDACTED_JWT>", s)
    s = KEYLIKE.sub("<REDACTED_KEY>", s)
    return s[:limit]


def safe_scalar_map(row: dict[str, Any], extra: Iterable[str] = ()) -> dict[str, Any]:
    allow = {
        "request_id", "trace_id", "session_id", "thread_id", "turn_id",
        "instance_id", "instance", "project", "project_dir", "project_key",
        "account", "email", "model", "exposed_model", "protocol", "method", "path",
        "request_type", "status", "status_code", "http_status", "result_class", "reason",
        "latency_ms", "ttft_ms", "header_ms", "attempt_count", "retry_count",
        "streaming", "circuit_state", "state", "desired_state", "risk", "score",
        "quality_score", "confidence", "role", "priority", "weight", "action", "code",
        "severity", "verdict", "source_age_minutes", "remaining", "remaining_pct",
        "five_hour_remaining", "weekly_remaining", "quota_remaining", "generated_utc",
        "updated_utc", "time_utc", "time", "timestamp", "created_utc", "transition",
        "from_account", "to_account", "recommended_account", "current_account",
        "node_id", "node_name", "epoch", "fingerprint", "fingerprint_scope",
        "capacity", "running_instances", "signature_ok", "age_sec", "active",
        "profile", "active_elapsed_sec", "progress_pct", "cycle_count", "session_count",
        "duration_complete", "coverage_complete", "recovery_budget_violation_count",
        "target_count", "instance_target_count", "request_success", "request_total",
        "max_latency_p95_ms", "max_control_plane_ttfb_p95_ms", "max_throughput_rps",
        "seeds", "total_cycles", "accounts", "instances", "projects", "model_states_checked", "trace_minimized_to", "replay_pass", "replay_total",
        "multi_instance_exercised", "shared_contention_exercised", "backpressure_observed",
        "reconnect_storm_requests", "stages_pass", "stages_total", "production_certified",
        "model_states", "model_violations", "healthy_states", "degraded_safe_states",
        "operator_required_states", "production_certification", "evidence_hash",
        "cockpit_parity_baseline", "originator", "user_agent", "claim_boundary",
        "crash_cases", "duplicate_commit_allowed", "usage_reset_rows", "package_expiry_rows", "stale_rows", "at_most_once", "ownership_proof_required",
        "pass", "total", "case_count", "default_disarmed", "real_codex_effects_executed", "windows_signing_executed", "production_score_eligible",
        "required_baseline", "observed_version", "promotion_frozen", "delta_audit_required", "codex_only_scope",
        "accepted_count", "quarantined_count", "accepted_case_count", "review_ready_for_promotion_auditor", "dual_review_complete", "reviewer_count", "ledger_entry_count_after",
        "external_windows_target_evidence_imported", "checkpoint_count", "delta_queue_count", "automatic_upstream_merge",
        "packet_state", "packet_seq", "packet_count", "immutable_raw_evidence", "derived_metadata_only", "review_packet_export_safe",
        "baseline_drift_detected", "eligibility_invalidated", "superseding_invalidation_entry_count", "delta_audit_valid_for_evidence_reuse",
        "evidence_reuse_allowed_after_new_review_epoch", "new_dual_review_epoch_required",
    } | set(extra)
    out: dict[str, Any] = {}
    for k, v in row.items():
        ks = str(k)
        if SECRET_KEY.search(ks) or PROMPT_KEY.search(ks) or ks not in allow:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[ks] = redact_text(v) if isinstance(v, str) else v
    return out


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return None


def read_jsonl(path: Path, max_lines: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def time_from(row: dict[str, Any], fallback: str = "") -> str:
    for k in ("time_utc", "time", "timestamp", "updated_utc", "generated_utc", "created_utc", "last_transition_utc"):
        if row.get(k):
            return parse_time(row.get(k))
    return fallback


def event(source: str, kind: str, row: dict[str, Any] | None = None, *, severity: str = "INFO", message: str = "", fallback_time: str = "") -> dict[str, Any]:
    row = row or {}
    safe = safe_scalar_map(row)
    ev = {
        "time_utc": time_from(row, fallback_time),
        "source": source,
        "kind": kind,
        "severity": severity,
        "request_id": str(row.get("request_id") or row.get("trace_id") or "")[:160],
        "instance_id": str(row.get("instance_id") or row.get("instance") or "")[:160],
        "project": redact_text(row.get("project") or row.get("project_dir") or "", 320),
        "account": redact_text(row.get("account") or row.get("email") or "", 320),
        "model": redact_text(row.get("model") or row.get("exposed_model") or "", 160),
        "status": redact_text(row.get("status") or row.get("status_code") or row.get("http_status") or row.get("verdict") or "", 80),
        "latency_ms": row.get("latency_ms"),
        "message": redact_text(message or row.get("reason") or row.get("message") or row.get("detail") or "", 420),
        "details": safe,
    }
    return ev


def usage_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "usage-ledger" / "usage-ledger-latest-v2526.json"
    d = read_json(p) or {}
    rows = d.get("recent_requests") or d.get("recent") or d.get("requests") or []
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        status = str(r.get("status") or "")
        sev = "ERROR" if status and not (status.startswith("2") or status.upper() in {"OK", "SUCCESS"}) else "INFO"
        out.append(event("usage-ledger", "REQUEST", r, severity=sev, message=f"Request {r.get('request_type') or r.get('path') or ''}"))
    return out


def jsonl_events(data_dir: Path) -> list[dict[str, Any]]:
    specs = [
        ("codex-route-history.jsonl", "router", "ROUTE"),
        ("codex-seamless-router-history-v2530.jsonl", "seamless-router", "ROUTE_DECISION"),
        ("request-trace-v20.jsonl", "request-trace", "REQUEST_TRACE"),
        ("codex-ops-events.jsonl", "operations", "OPS_EVENT"),
        ("codex-incidents.jsonl", "incidents", "INCIDENT"),
        ("codex-config-doctor.jsonl", "config-doctor", "CONFIG"),
    ]
    out: list[dict[str, Any]] = []
    for name, source, kind in specs:
        for r in read_jsonl(data_dir / name):
            sev = str(r.get("severity") or ("ERROR" if r.get("error") else "INFO")).upper()
            out.append(event(source, kind, r, severity=sev, message=str(r.get("event") or r.get("action") or r.get("reason") or "")))
    return out


def closed_loop_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "closed-loop-router" / "closed-loop-router-plan-v2532.json"
    d = read_json(p) or {}
    out: list[dict[str, Any]] = []
    generated = parse_time(d.get("generated_utc") or d.get("updated_utc"))
    instances = d.get("instances") or []
    if isinstance(instances, dict):
        instances = [{"instance_id": k, **(v if isinstance(v, dict) else {})} for k, v in instances.items()]
    for inst in instances if isinstance(instances, list) else []:
        if not isinstance(inst, dict):
            continue
        cur = inst.get("current_account") or ""
        rec = inst.get("recommended_account") or ""
        row = dict(inst)
        row["from_account"] = cur
        row["to_account"] = rec
        msg = f"Router policy: {cur or '—'} → {rec or '—'}"
        sev = "WARNING" if cur and rec and str(cur).lower() != str(rec).lower() else "INFO"
        out.append(event("closed-loop", "ROUTER_DECISION", row, severity=sev, message=msg, fallback_time=generated))
    return out


def smart_model_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "smart-model-router" / "smart-model-router-plan-v2544.json"
    d = read_json(p) or {}
    generated = parse_time(d.get("generated_utc") or d.get("updated_utc"))
    out: list[dict[str, Any]] = []
    for r in d.get("recommendations") or []:
        if not isinstance(r, dict):
            continue
        row = dict(r)
        row["account"] = r.get("recommended_account") or ""
        row["model"] = r.get("recommended_model") or ""
        status = str(r.get("status") or "")
        sev = "WARNING" if status in {"BLOCKED", "STICKY_GUARD"} else "INFO"
        msg = f"Smart model {r.get('team_role') or 'SOLO'}: {r.get('current_model') or '—'} → {r.get('recommended_model') or '—'} / {r.get('recommended_reasoning') or '—'}"
        out.append(event("smart-model", "MODEL_ROUTER_DECISION", row, severity=sev, message=msg, fallback_time=generated))
    return out


def lan_pool_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "lan-pool" / "lan-pool-latest-v2545.json"
    d = read_json(p) or {}
    generated = parse_time(d.get("generated_utc"))
    out: list[dict[str, Any]] = []
    for r in d.get("nodes") or []:
        if not isinstance(r, dict):
            continue
        sev = "ERROR" if (not r.get("signature_ok", True) or not r.get("payload_ok", True)) else ("WARNING" if str(r.get("state") or "").upper() == "STALE" else "INFO")
        msg = f"LAN node {r.get('node_name') or r.get('node_id')}: {r.get('state') or 'UNKNOWN'}"
        out.append(event("lan-pool", "LAN_NODE", r, severity=sev, message=msg, fallback_time=generated))
    for r in d.get("leases") or []:
        if not isinstance(r, dict):
            continue
        sev = "ERROR" if (not r.get("signature_ok", True) or not r.get("payload_ok", True)) else ("INFO" if r.get("active") else "WARNING")
        msg = f"Project lease node={r.get('node_name') or r.get('node_id') or '—'} epoch={r.get('epoch') or '—'} state={r.get('state') or '—'}"
        out.append(event("lan-pool", "LAN_PROJECT_LEASE", r, severity=sev, message=msg, fallback_time=generated))
    return out


def reliability_soak_events(data_dir: Path) -> list[dict[str, Any]]:
    d = data_dir / "reliability-soak-v2547"
    if not d.exists():
        return []
    out: list[dict[str, Any]] = []
    paths = sorted(d.glob("soak-result-v2547-*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:12]
    if not paths:
        paths = sorted(d.glob("soak-checkpoint-v2547-*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:12]
    for p in paths:
        r = read_json(p) or {}
        if not isinstance(r, dict):
            continue
        verdict = str(r.get("verdict") or r.get("state") or "IN_PROGRESS").upper()
        health = r.get("health") or {}
        row = {
            "status": verdict,
            "profile": r.get("profile") or "",
            "active_elapsed_sec": r.get("active_elapsed_sec") or 0,
            "progress_pct": r.get("progress_pct") or 0,
            "cycle_count": r.get("cycle_count") or 0,
            "session_count": r.get("session_count") or 0,
            "duration_complete": bool(r.get("duration_complete")),
            "coverage_complete": bool(r.get("coverage_complete")),
            "recovery_budget_violation_count": int(health.get("recovery_budget_violation_count") or 0),
            "time_utc": r.get("generated_utc") or r.get("last_checkpoint_utc") or "",
        }
        sev = "ERROR" if verdict == "FAIL" or row["recovery_budget_violation_count"] else ("INFO" if verdict == "PASS" else "WARNING")
        msg = f"Reliability soak {row['profile'] or '—'}: {verdict} · active={float(row['active_elapsed_sec'] or 0)/3600:.2f}h · sessions={row['session_count']}"
        out.append(event("reliability-soak", "SOAK_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"]))
    return out


def performance_scale_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "performance-scale-v2548" / "performance-scale-latest-v2548.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    topo = r.get("topology") or {}
    row = {
        "status": verdict,
        "target_count": topo.get("target_count") or 0,
        "instance_target_count": topo.get("instance_target_count") or 0,
        "request_success": sm.get("request_success") or 0,
        "request_total": sm.get("request_total") or 0,
        "max_latency_p95_ms": sm.get("max_latency_p95_ms"),
        "max_control_plane_ttfb_p95_ms": sm.get("max_control_plane_ttfb_p95_ms"),
        "max_throughput_rps": sm.get("max_throughput_rps"),
        "multi_instance_exercised": bool(sm.get("multi_instance_exercised")),
        "shared_contention_exercised": bool(sm.get("shared_contention_exercised")),
        "backpressure_observed": bool(sm.get("backpressure_observed")),
        "reconnect_storm_requests": sm.get("reconnect_storm_requests") or 0,
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "ERROR" if verdict == "FAIL" else ("WARNING" if "WARNING" in verdict or r.get("warnings") else "INFO")
    msg = f"Performance scale {verdict}: targets={row['target_count']} p95={row['max_latency_p95_ms']}ms throughput={row['max_throughput_rps']}rps"
    return [event("performance-scale", "PERFORMANCE_SCALE_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def real_codex_cert_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "real-codex-cert-v2549" / "real-codex-cert-latest-v2549.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    cli = r.get("codex_cli") or {}
    ps = r.get("powershell_5_1") or {}
    row = {
        "status": verdict,
        "codex_version": cli.get("version") or "",
        "powershell_5_1": bool(ps.get("is_windows_powershell_5_1") and ps.get("parser_ok")),
        "managed_instances": sm.get("managed_instances") or 0,
        "healthy_instance_endpoints": sm.get("healthy_instance_endpoints") or 0,
        "generation_guard_pass": sm.get("generation_guard_pass") or 0,
        "live_requests_executed": sm.get("live_requests_executed") or 0,
        "live_requests_pass": sm.get("live_requests_pass") or 0,
        "exact_output_text_delta_ttft_observed": sm.get("exact_output_text_delta_ttft_observed") or 0,
        "real_codex_certified": bool(sm.get("real_codex_certified")),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict == "PASS_REAL_CODEX_CERTIFIED" else ("ERROR" if verdict == "FAIL" else "WARNING")
    msg = f"Real Codex certification {verdict}: Codex={row['codex_version'] or '—'} instances={row['healthy_instance_endpoints']}/{row['managed_instances']} live={row['live_requests_pass']}/{row['live_requests_executed']}"
    return [event("real-codex-cert", "REAL_CODEX_CERT_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]



def production_simulation_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "production-simulation-v2554" / "production-simulation-latest-v2554.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    row = {
        "status": verdict,
        "seeds": int(sm.get("seeds") or 0),
        "total_cycles": int(sm.get("total_cycles") or 0),
        "invariant_failures": int(sm.get("invariant_failures") or 0),
        "events_exercised": int(sm.get("events_exercised") or 0),
        "quota_matrix_pass": int(sm.get("quota_matrix_pass") or 0),
        "quota_matrix_total": int(sm.get("quota_matrix_total") or 0),
        "replay_pass": int(sm.get("replay_pass") or 0),
        "replay_total": int(sm.get("replay_total") or 0),
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_SIMULATION_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") and row["invariant_failures"] == 0 else "ERROR"
    msg = f"Production simulation {verdict}: seeds={row['seeds']} cycles={row['total_cycles']} invariant_fail={row['invariant_failures']} replay={row['replay_pass']}/{row['replay_total']}"
    return [event("production-simulation", "PRODUCTION_SIMULATION_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def autonomous_router_twin_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "autonomous-router-twin-v2555" / "autonomous-router-twin-latest-v2555.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    row = {
        "status": verdict,
        "seeds": int(sm.get("seeds") or 0),
        "total_cycles": int(sm.get("total_cycles") or 0),
        "accounts": int(sm.get("accounts") or 0),
        "instances": int(sm.get("instances") or 0),
        "projects": int(sm.get("projects") or 0),
        "model_states_checked": int(sm.get("model_states_checked") or 0),
        "trace_minimized_to": int(sm.get("trace_minimized_to") or 0),
        "replay_pass": int(sm.get("replay_pass") or 0),
        "replay_total": int(sm.get("replay_total") or 0),
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_DIGITAL_TWIN_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") else "ERROR"
    msg = f"Autonomous Router Twin {verdict}: pool={row['accounts']}/{row['instances']}/{row['projects']} cycles={row['total_cycles']} states={row['model_states_checked']} trace_min={row['trace_minimized_to']}"
    return [event("autonomous-router-twin", "AUTONOMOUS_ROUTER_TWIN_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def protocol_chaos_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "protocol-chaos-v2556" / "protocol-chaos-latest-v2556.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    row = {
        "status": verdict,
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "fuzz_cases": int(sm.get("fuzz_cases") or 0),
        "seed": int(sm.get("seed") or 0),
        "fuzz_trace_hash": str(sm.get("fuzz_trace_hash") or "")[:64],
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_PROTOCOL_CHAOS_SYNTHETIC_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") else "ERROR"
    msg = f"Protocol Chaos {verdict}: {row['pass']}/{row['total']} fuzz={row['fuzz_cases']} seed={row['seed']}"
    return [event("protocol-chaos", "PROTOCOL_CHAOS_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def recovery_planner_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "recovery-planner-v2557" / "recovery-planner-latest-v2557.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    mc = r.get("model_check") or {}
    row = {
        "status": verdict,
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "model_states": int(sm.get("model_states") or mc.get("states_checked") or 0),
        "model_violations": int(mc.get("violation_count") or 0),
        "counterexample_minimized_to": int((r.get("minimized_counterexample") or {}).get("minimized_length") or 0),
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_RECOVERY_DECISION_PROOF_SYNTHETIC_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") and row["model_violations"] == 0 else "ERROR"
    msg = f"Recovery Planner {verdict}: {row['pass']}/{row['total']} states={row['model_states']} violations={row['model_violations']}"
    return [event("recovery-planner", "SELF_HEALING_DECISION_PROOF", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def compound_fault_recovery_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "compound-fault-recovery-v2558" / "compound-fault-recovery-latest-v2558.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    mc = r.get("model_check") or {}
    terminals = mc.get("terminal_distribution") or {}
    row = {
        "status": verdict,
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "model_states": int(sm.get("model_states") or mc.get("states_checked") or 0),
        "model_violations": int(mc.get("violation_count") or 0),
        "healthy_states": int(terminals.get("HEALTHY") or 0),
        "degraded_safe_states": int(terminals.get("DEGRADED_SAFE") or 0),
        "operator_required_states": int(terminals.get("OPERATOR_REQUIRED") or 0),
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_COMPOUND_FAULT_CONVERGENCE_SYNTHETIC_ONLY"),
        "evidence_hash": str(r.get("evidence_hash") or "")[:64],
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") and row["model_violations"] == 0 else "ERROR"
    msg = f"Compound Fault Recovery {verdict}: {row['pass']}/{row['total']} states={row['model_states']} violations={row['model_violations']}"
    return [event("compound-fault-recovery", "RECOVERY_CONVERGENCE_PROOF", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def official_auth_compat_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "official-auth-compat-v2559" / "official-auth-compat-latest-v2559.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    identity = r.get("oauth_identity") or {}
    row = {
        "status": verdict,
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "cockpit_parity_baseline": str(r.get("cockpit_parity_baseline") or "v1.3.24")[:32],
        "originator": str(identity.get("originator") or "")[:64],
        "user_agent": str(identity.get("User-Agent") or "")[:96],
        "claim_boundary": str(r.get("claim_boundary") or "")[:160],
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") else "ERROR"
    msg = f"Official Auth Compatibility {verdict}: {row['pass']}/{row['total']} baseline={row['cockpit_parity_baseline']}"
    return [event("official-auth-compat", "CODEX_AUTH_COMPATIBILITY", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def recovery_journal_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "recovery-journal-v2560" / "recovery-journal-latest-v2560.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or ("PASS" if r.get("ok") else "UNKNOWN")).upper()
    sm = r.get("summary") or {}
    row = {
        "status": verdict,
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "crash_cases": int(sm.get("crash_cases") or 0),
        "duplicate_commit_allowed": bool((r.get("safety") or {}).get("duplicate_commit_allowed", False)),
        "production_certification": str((r.get("safety") or {}).get("production_certification") or "NOT_CLAIMED_RECOVERY_JOURNAL_SYNTHETIC_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") and not row["duplicate_commit_allowed"] else "ERROR"
    msg = f"Recovery Journal {verdict}: {row['pass']}/{row['total']} crash_cases={row['crash_cases']} duplicate_commit={row['duplicate_commit_allowed']}"
    return [event("recovery-journal", "CRASH_CONSISTENT_RECOVERY_PROOF", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def usage_token_events(data_dir: Path) -> list[dict[str, Any]]:
    # v25.61 deliberately exports aggregate metadata only. Account refs/emails are not projected.
    p = data_dir / "usage-token-v2561" / "usage-token-latest-v2561.json"
    r = read_json(p) or {}
    if isinstance(r, dict) and isinstance(r.get("usage_token_center"), dict):
        r = r.get("usage_token_center") or {}
    if not isinstance(r, dict) or not r:
        return []
    sm = r.get("summary") or {}
    cards = r.get("cards") or []
    resets = 0
    package = 0
    stale = 0
    for c in cards if isinstance(cards, list) else []:
        if not isinstance(c, dict):
            continue
        stale += int(str(c.get("freshness_state") or "").upper() == "STALE")
        life = c.get("lifecycle") or {}
        package += int(bool(((life.get("package") or {}).get("expiry_utc"))))
        for w in c.get("windows") or []:
            if isinstance(w, dict) and w.get("reset_utc"):
                resets += 1
    row = {
        "status": "PASS", "accounts": int(sm.get("cards") or len(cards) if isinstance(cards, list) else 0),
        "usage_reset_rows": resets, "package_expiry_rows": package, "stale_rows": stale,
        "production_certification": str(((r.get("safety") or {}).get("production_certification")) or "NOT_CLAIMED_USAGE_TOKEN_CENTER_SYNTHETIC_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    # only fields in safe_scalar_map are retained; message contains aggregate counts only.
    ev = event("usage-token-center", "USAGE_TOKEN_METADATA", row, severity="INFO",
               message=f"Usage/Token metadata accounts={row['accounts']} resets={resets} package={package} stale={stale}",
               fallback_time=row["time_utc"])
    ev["account"] = ""
    ev["project"] = ""
    return [ev]


def recovery_replay_events(data_dir: Path) -> list[dict[str, Any]]:
    # v25.62 projects proof aggregates only; no transaction/effect/account identity is exported.
    p = data_dir / "recovery-replay-v2562" / "recovery-replay-latest-v2562.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    sm = r.get("summary") or {}
    safety = r.get("safety") or {}
    row = {
        "status": str(r.get("verdict") or "UNKNOWN"),
        "pass": int(sm.get("pass") or 0),
        "total": int(sm.get("total") or 0),
        "crash_cases": int(sm.get("crash_cases") or 0),
        "at_most_once": bool(safety.get("at_most_once_durable_side_effect")),
        "ownership_proof_required": bool(safety.get("ownership_proof_required_for_compensation")),
        "production_certification": str(safety.get("production_certification") or "NOT_CLAIMED_RECOVERY_REPLAY_SYNTHETIC_ONLY"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if row["status"] == "PASS" else "ERROR"
    msg = f"Recovery Replay {row['status']}: {row['pass']}/{row['total']} crash_cases={row['crash_cases']} at_most_once={row['at_most_once']} ownership_proof={row['ownership_proof_required']}"
    ev = event("recovery-replay", "MULTI_SUBSYSTEM_REPLAY_PROOF", row, severity=sev, message=msg, fallback_time=row["time_utc"])
    ev["account"] = ""
    ev["project"] = ""
    ev["instance_id"] = ""
    return [ev]


def startup_recovery_events(data_dir: Path) -> list[dict[str, Any]]:
    # v25.63 exports aggregate startup gate state only; timeline/effect refs stay local.
    p = data_dir / "startup-recovery-v2565" / "startup-recovery-latest-v2565.json"
    if not p.exists():
        p = data_dir / "startup-recovery-v2564" / "startup-recovery-latest-v2564.json"
    if not p.exists():
        p = data_dir / "startup-recovery-v2563" / "startup-recovery-latest-v2563.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    sm = r.get("summary") or {}
    row = {
        "status": str(r.get("status") or "UNKNOWN"),
        "journals_discovered": int(sm.get("journals_discovered") or 0),
        "unresolved_transactions": int(sm.get("unresolved_transactions") or 0),
        "operator_required": int(sm.get("operator_required") or 0),
        "degraded_safe": int(sm.get("degraded_safe") or 0),
        "blocked_conflicting_actions": int(sm.get("blocked_conflicting_actions") or 0),
        "production_certification": str(r.get("production_certification") or "NOT_CLAIMED_STARTUP_RECONCILER_TARGET_MACHINE_LIVE_REQUIRED"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "ERROR" if row["status"] == "OPERATOR_REQUIRED" else ("WARNING" if row["status"] == "DEGRADED_SAFE" else "INFO")
    msg = f"Startup Recovery {row['status']}: unresolved={row['unresolved_transactions']} operator={row['operator_required']} blocked={row['blocked_conflicting_actions']}"
    ev = event("startup-recovery", "STARTUP_RECOVERY_GATE", row, severity=sev, message=msg, fallback_time=row["time_utc"])
    ev["account"] = ""; ev["project"] = ""; ev["instance_id"] = ""
    return [ev]



def external_windows_review_packet_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2574" / "external-windows-review-packet-latest-v2574.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    row={"status":str(r.get("packet_state") or "UNKNOWN"),"packet_state":str(r.get("packet_state") or "UNKNOWN"),
         "packet_seq":int(r.get("packet_seq") or 0),"case_count":int(r.get("case_count") or 0),
         "immutable_raw_evidence":bool(r.get("immutable_raw_evidence")),"derived_metadata_only":bool(r.get("derived_metadata_only")),
         "review_packet_export_safe":bool(r.get("review_packet_export_safe")),"dual_review_complete":bool((r.get("review_ledger") or {}).get("dual_review_complete")),
         "production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["packet_state"]=="READY_FOR_HUMAN_REVIEW" else "WARNING"
    ev=event("external-windows-review-packet","EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET",row,severity=sev,message=f"Windows evidence review packet {row['packet_state']}: cases={row['case_count']} immutable={row['immutable_raw_evidence']} dual_review={row['dual_review_complete']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def baseline_drift_reconciliation_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2574" / "baseline-drift-reconciliation-latest-v2574.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    row={"status":str(r.get("packet_state_after") or "UNKNOWN"),"observed_version":str(r.get("observed_version") or ""),
         "required_baseline":str(r.get("required_baseline") or "1.3.27"),"baseline_drift_detected":bool(r.get("baseline_drift_detected")),
         "eligibility_invalidated":bool(r.get("eligibility_invalidated")),"superseding_invalidation_entry_count":int(r.get("superseding_invalidation_entry_count") or 0),
         "delta_audit_valid_for_evidence_reuse":bool(r.get("delta_audit_valid_for_evidence_reuse")),
         "evidence_reuse_allowed_after_new_review_epoch":bool(r.get("evidence_reuse_allowed_after_new_review_epoch")),
         "new_dual_review_epoch_required":bool(r.get("new_dual_review_epoch_required")),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    sev="WARNING" if row["baseline_drift_detected"] else "INFO"
    ev=event("baseline-drift-reconciliation","BASELINE_DRIFT_RECONCILIATION",row,severity=sev,message=f"Baseline reconcile {row['status']}: observed={row['observed_version']} drift={row['baseline_drift_detected']} invalidations={row['superseding_invalidation_entry_count']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_crash_harness_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "startup-recovery-v2564" / "target-crash-harness-latest-v2563.json"
    if not p.exists():
        p = data_dir / "startup-recovery-v2563" / "target-crash-harness-latest-v2563.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    sm = r.get("summary") or {}; host = r.get("host") or {}; safety = r.get("safety") or {}
    row = {
        "status": str(r.get("verdict") or "UNKNOWN"), "pass": int(sm.get("pass") or 0), "total": int(sm.get("total") or 0),
        "crash_cases": int(sm.get("crash_cases") or 0), "windows_target_evidence": bool(host.get("windows_target_evidence")),
        "real_codex_effects_executed": bool(safety.get("real_codex_effects_executed")),
        "production_certification": str(safety.get("production_certification") or "NOT_CLAIMED_OS_PROCESS_KILL_LAB_REAL_CODEX_EFFECTS_NOT_EXECUTED"),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if row["status"] == "PASS" else "ERROR"
    msg = f"Crash Harness {row['status']}: {row['pass']}/{row['total']} crash_cases={row['crash_cases']} windows_target={row['windows_target_evidence']}"
    ev = event("target-crash-harness", "COLD_START_PROCESS_KILL_PROOF", row, severity=sev, message=msg, fallback_time=row["time_utc"])
    ev["account"] = ""; ev["project"] = ""; ev["instance_id"] = ""
    return [ev]



def windows_recovery_observer_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "startup-recovery-v2564" / "windows-recovery-observer-latest-v2564.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    sm = r.get("summary") or {}; evd = r.get("evidence") or {}
    row = {"status": str(r.get("verdict") or "UNKNOWN"), "available": int(sm.get("available") or 0), "total": int(sm.get("total") or 0), "evidence_class": str(evd.get("class") or "UNKNOWN"), "production_score_eligible": bool(evd.get("production_score_eligible")), "time_utc": r.get("generated_utc") or ""}
    sev = "INFO" if row["status"] == "PASS" else "WARNING"
    ev = event("windows-recovery-observer", "WINDOWS_TARGET_OBSERVER_BRIDGE", row, severity=sev, message=f"Windows observer {row['status']}: {row['available']}/{row['total']} class={row['evidence_class']} score_eligible={row['production_score_eligible']}", fallback_time=row["time_utc"])
    ev["account"]="";ev["project"]="";ev["instance_id"]=""
    return [ev]

def real_effect_crash_cert_events(data_dir: Path) -> list[dict[str, Any]]:
    base=data_dir / "startup-recovery-v2564"
    p=base / "real-effect-crash-cert-latest-v2564.json"
    if not p.exists(): p=base / "real-effect-preflight-latest-v2564.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};arming=r.get("arming") or {};g=arming.get("gates") or {}
    row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"crash_cases":int(sm.get("crash_cases") or 0),"arming_gates_pass":sum(bool(v) for v in g.values()),"arming_gates_total":len(g),"real_codex_effects_executed":bool(r.get("real_codex_effects_executed")),"production_score_eligible":bool(r.get("production_score_eligible")),"evidence_class":str(r.get("evidence_class") or "REAL_CODEX_EFFECT"),"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["status"].startswith("PASS") else "WARNING"
    ev=event("real-effect-crash-cert","REAL_CODEX_EFFECT_CRASH_CERT",row,severity=sev,message=f"Real-effect cert {row['status']}: armed={row['arming_gates_pass']}/{row['arming_gates_total']} executed={row['real_codex_effects_executed']} score_eligible={row['production_score_eligible']}",fallback_time=row["time_utc"])
    ev["account"]="";ev["project"]="";ev["instance_id"]=""
    return [ev]

def target_recovery_evidence_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2564" / "target-recovery-evidence-latest-v2564.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    row={"status":"PASS","evidence_classes_count":len(r.get("evidence_classes") or []),"production_score_eligible":bool(r.get("production_score_eligible")),"bundle_sha256_present":len(str(r.get("bundle_sha256") or ""))==64,"time_utc":r.get("generated_utc") or ""}
    ev=event("target-recovery-evidence","TARGET_RECOVERY_EVIDENCE_BUNDLE",row,severity="INFO",message=f"Target recovery evidence classes={row['evidence_classes_count']} score_eligible={row['production_score_eligible']} hash={row['bundle_sha256_present']}",fallback_time=row["time_utc"])
    ev["account"]="";ev["project"]="";ev["instance_id"]=""
    return [ev]

def windows_target_adapter_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "windows-target-adapter-latest-v2565.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {}
    row={"status":str(r.get("verdict") or "UNKNOWN"),"available":int(sm.get("available") or 0),"total":int(sm.get("total") or 0),"evidence_class":str(r.get("evidence_class") or "WINDOWS_TARGET_OBSERVER"),"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["status"]=="PASS" else "WARNING"
    ev=event("windows-target-adapter","WINDOWS_TARGET_ADAPTER_PACK",row,severity=sev,message=f"Windows target adapter {row['status']}: {row['available']}/{row['total']} score_eligible={row['production_score_eligible']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def attested_evidence_promotion_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "attested-evidence-promotion-latest-v2565.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {}
    row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"production_score_promotion_eligible":bool(r.get("production_score_promotion_eligible")),"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["status"] in {"PASS","PASS_PROMOTION_ELIGIBLE"} else "WARNING"
    ev=event("attested-evidence-promotion","ATTESTED_EVIDENCE_PROMOTION_GATE",row,severity=sev,message=f"Attested promotion {row['status']}: promotion_eligible={row['production_score_promotion_eligible']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def recovery_operator_timeline_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "recovery-operator-timeline-latest-v2565.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    out=[]
    for x in (r.get("timeline") or [])[:80]:
        if not isinstance(x,dict):continue
        row={"status":str(x.get("status") or ""),"phase":str(x.get("phase") or "OBSERVE"),"label_vi":str(x.get("nhan") or ""),"source":str(x.get("source") or "recovery"),"freshness":str(x.get("freshness") or "UNKNOWN"),"safe_fingerprint_prefix":str(x.get("safe_fingerprint_prefix") or "")[:12],"remediation_reason":str(x.get("remediation_reason") or "")[:180],"time_utc":x.get("time_utc") or r.get("generated_utc") or ""}
        sev="WARNING" if row["phase"]=="OPERATOR_REQUIRED" else "INFO"
        ev=event("recovery-operator-timeline","RECOVERY_OPERATOR_TIMELINE",row,severity=sev,message=f"{row['label_vi']} · {row['source']} · {row['freshness']} · {row['remediation_reason']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";out.append(ev)
    return out

def windows_attestation_signer_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2566" / "windows-attestation-signer-latest-v2566.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"windows_signing_executed":bool(r.get("windows_signing_executed")),"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    ev=event("windows-attestation-signer","WINDOWS_ATTESTATION_SIGNER",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Windows attestation signer {row['status']}: {row['pass']}/{row['total']} target_signing={row['windows_signing_executed']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_certification_runbook_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2566" / "target-cert-runbook-latest-v2566.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"real_codex_effects_executed":bool(r.get("real_codex_effects_executed")),"auto_disarmed":bool(r.get("auto_disarmed",True)),"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    ev=event("target-certification-runbook","TARGET_CERTIFICATION_RUNBOOK",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Target certification runbook {row['status']}: proof={row['pass']}/{row['total']} auto_disarm={row['auto_disarmed']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def attestation_exchange_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2566" / "attestation-exchange-latest-v2566.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    ev=event("attestation-exchange","ATTESTATION_EXCHANGE",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Attestation exchange {row['status']}: {row['pass']}/{row['total']} privacy/integrity",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def attestation_trust_store_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2567" / "attestation-trust-store-latest-v2567.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};snap=r.get("trust_snapshot") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"trust_snapshot_sha256":str(snap.get("trust_snapshot_sha256") or "")[:16],"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    ev=event("attestation-trust-store","ATTESTATION_TRUST_STORE",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Attestation trust store {row['status']}: {row['pass']}/{row['total']} snapshot={row['trust_snapshot_sha256']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def offline_attestation_verifier_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2567" / "offline-attestation-verifier-latest-v2567.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"network_required":False,"production_score_eligible":bool(r.get("production_score_eligible")),"time_utc":r.get("generated_utc") or ""}
    ev=event("offline-attestation-verifier","OFFLINE_ATTESTATION_VERIFIER",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Offline verifier {row['status']}: {row['pass']}/{row['total']} network_required=False",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_certification_campaign_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2567" / "target-cert-campaign-latest-v2567.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};camp=r.get("campaign") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"total_cases":int(camp.get("total_cases") or 0),"complete":bool(camp.get("complete")),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    ev=event("target-certification-campaign","TARGET_CERTIFICATION_CAMPAIGN",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Target campaign {row['status']}: proof={row['pass']}/{row['total']} cases={row['total_cases']} complete={row['complete']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_campaign_executor_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2568" / "target-campaign-executor-latest-v2568.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"real_codex_effects_executed":bool(r.get("real_codex_effects_executed")),"windows_target_execution":bool(r.get("windows_target_execution")),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    ev=event("target-campaign-executor","TARGET_CAMPAIGN_EXECUTOR",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Target campaign executor {row['status']}: proof={row['pass']}/{row['total']} real_effect={row['real_codex_effects_executed']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def attested_promotion_review_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2568" / "attested-promotion-review-latest-v2568.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"production_score_eligible":False,"automatic_production_certification":False,"time_utc":r.get("generated_utc") or ""}
    ev=event("attested-promotion-review","ATTESTED_PROMOTION_REVIEW",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Attested promotion review {row['status']}: proof={row['pass']}/{row['total']} auto_cert=False",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_certification_evidence_ingest_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2569" / "target-cert-evidence-ingest-latest-v2569.json"
    r=read_json(p) or {}
    if not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "PASS"),"accepted":int(sm.get("accepted") or 0),"quarantined":int(sm.get("quarantined") or 0),"present_cases":int(sm.get("present_cases") or 0),"matrix_complete":bool(sm.get("matrix_complete")),"read_only_ingest":bool(r.get("read_only_ingest",True)),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["quarantined"]==0 else "WARNING"
    ev=event("target-cert-evidence-ingest","TARGET_CERT_EVIDENCE_INGEST",row,severity=sev,message=f"Evidence inbox: accepted={row['accepted']} quarantine={row['quarantined']} matrix={row['present_cases']}/12",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def promotion_decision_ledger_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2569" / "promotion-decision-ledger-latest-v2569.json"
    r=read_json(p) or {}
    if not r:return []
    sm=r.get("summary") or {};row={"status":str(r.get("verdict") or "PASS"),"entries":int(sm.get("entries") or sm.get("total") or 0),"dual_review_complete":bool(r.get("dual_review_complete")),"promotion_eligible":bool(r.get("promotion_eligible")),"production_score_mutation_authorized":False,"time_utc":r.get("generated_utc") or ""}
    ev=event("promotion-decision-ledger","PROMOTION_DECISION_LEDGER",row,severity="INFO",message=f"Promotion ledger: entries={row['entries']} dual_review={row['dual_review_complete']} score_mutation=False",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]


def windows_target_capture_kit_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2572" / "windows-target-capture-kit-latest-v2572.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    sm=r.get("summary") or {}
    row={"status":str(r.get("verdict") or "UNKNOWN"),"pass":int(sm.get("pass") or 0),"total":int(sm.get("total") or 0),"case_count":7,"default_disarmed":True,"real_codex_effects_executed":bool(r.get("real_codex_effects_executed")),"windows_signing_executed":bool(r.get("windows_signing_executed")),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    ev=event("windows-target-capture-kit","WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT",row,severity="INFO" if row["status"]=="PASS" else "WARNING",message=f"Windows target capture kit {row['status']}: {row['pass']}/{row['total']} cases={row['case_count']} disarmed=True",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def cockpit_baseline_watch_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2572" / "cockpit-baseline-watch-latest-v2572.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    row={"status":str(r.get("status") or r.get("verdict") or "UNKNOWN"),"required_baseline":str(r.get("required_baseline") or r.get("cockpit_baseline") or "1.3.27"),"observed_version":str(r.get("observed_version") or ""),"promotion_frozen":bool(r.get("promotion_frozen")),"delta_audit_required":bool(r.get("delta_audit_required")),"codex_only_scope":bool(r.get("codex_only_scope",True)),"time_utc":r.get("generated_utc") or ""}
    sev="WARNING" if row["promotion_frozen"] else "INFO"
    ev=event("cockpit-baseline-watch","COCKPIT_BASELINE_WATCH_GATE",row,severity=sev,message=f"Cockpit baseline watch {row['status']}: required={row['required_baseline']} observed={row['observed_version']} frozen={row['promotion_frozen']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]



def windows_target_import_review_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2573" / "windows-target-import-review-latest-v2573.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    dual=r.get("dual_review") or {}
    row={"status":"READY" if r.get("review_ready_for_promotion_auditor") else "HOLD","accepted_count":int(r.get("accepted_count") or 0),
         "quarantined_count":int(r.get("quarantined_count") or 0),"accepted_case_count":int(r.get("accepted_case_count") or 0),
         "review_ready_for_promotion_auditor":bool(r.get("review_ready_for_promotion_auditor")),"dual_review_complete":bool(dual.get("dual_review_complete")),
         "reviewer_count":int(dual.get("reviewer_count") or 0),"ledger_entry_count_after":int(r.get("ledger_entry_count_after") or 0),
         "external_windows_target_evidence_imported":bool(r.get("external_windows_target_evidence_imported")),"production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    sev="INFO" if row["status"]=="READY" else "WARNING"
    ev=event("windows-target-import-review","WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW",row,severity=sev,message=f"Windows evidence import {row['status']}: accepted={row['accepted_case_count']}/7 quarantine={row['quarantined_count']} dual_review={row['dual_review_complete']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def baseline_delta_watch_events(data_dir: Path) -> list[dict[str, Any]]:
    p=data_dir / "startup-recovery-v2565" / "v2573" / "baseline-delta-watch-latest-v2573.json"
    r=read_json(p) or {}
    if not isinstance(r,dict) or not r:return []
    obs=r.get("observations") or []
    row={"status":str(r.get("verdict") or "UNKNOWN"),"required_baseline":str(r.get("required_baseline") or "1.3.27"),
         "promotion_frozen":bool(r.get("promotion_frozen")),"checkpoint_count":len(obs),"delta_queue_count":len(r.get("delta_audit_queue") or []),
         "codex_only_scope":bool(r.get("codex_only_scope",True)),"automatic_upstream_merge":bool(r.get("automatic_upstream_merge")),
         "production_score_eligible":False,"time_utc":r.get("generated_utc") or ""}
    sev="WARNING" if row["promotion_frozen"] else "INFO"
    ev=event("baseline-delta-watch","BASELINE_DELTA_WATCH_AUTOMATION",row,severity=sev,message=f"Baseline delta watch {row['status']}: checkpoints={row['checkpoint_count']} delta_queue={row['delta_queue_count']} frozen={row['promotion_frozen']}",fallback_time=row["time_utc"]);ev["account"]="";ev["project"]="";ev["instance_id"]="";return [ev]

def target_machine_cert_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "target-machine-cert-v2553" / "target-machine-cert-latest-v2553.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    stages = r.get("stages") or {}
    row = {
        "status": verdict,
        "stages_pass": int(sm.get("stages_pass") or 0),
        "stages_total": int(sm.get("stages_total") or 0),
        "production_certified": bool(sm.get("production_certified")),
        "windows": bool(((stages.get("host") or {}).get("pass"))),
        "codex": bool(((stages.get("codex") or {}).get("pass"))),
        "quota": bool(((stages.get("quota") or {}).get("pass"))),
        "failover": bool(((stages.get("failover") or {}).get("pass"))),
        "lan": bool(((stages.get("lan") or {}).get("pass"))),
        "soak_6h": bool(((stages.get("soak_6h") or {}).get("pass"))),
        "soak_24h": bool(((stages.get("soak_24h") or {}).get("pass"))),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict == "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" else ("ERROR" if verdict == "FAIL" else "WARNING")
    msg = f"Target-machine certification {verdict}: {row['stages_pass']}/{row['stages_total']} stages"
    return [event("target-machine-cert", "TARGET_MACHINE_CERT_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]

def rotation_torture_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "seamless-rotation-torture-v2551-latest.json"
    r = read_json(p) or {}
    if not isinstance(r, dict) or not r:
        return []
    verdict = str(r.get("verdict") or "UNKNOWN").upper()
    sm = r.get("summary") or {}
    scenarios = r.get("scenarios") or {}
    row = {
        "status": verdict,
        "pass_count": sm.get("pass") or 0,
        "fail_count": sm.get("fail") or 0,
        "total_count": sm.get("total") or 0,
        "cycles": sm.get("cycles") or 0,
        "gateway_affinity_entries": ((scenarios.get("gateway_429") or {}).get("affinity_entries") or 0),
        "multi_instance_count": ((scenarios.get("multi_instance") or {}).get("instances") or 0),
        "lan_takeover_epoch": ((scenarios.get("lan_rejoin") or {}).get("takeover_epoch") or 0),
        "time_utc": r.get("generated_utc") or "",
    }
    sev = "INFO" if verdict.startswith("PASS") else "ERROR"
    msg = f"Rotation torture {verdict}: {row['pass_count']}/{row['total_count']} · cycles={row['cycles']} · instances={row['multi_instance_count']}"
    return [event("rotation-torture", "ROTATION_TORTURE_RUN", row, severity=sev, message=msg, fallback_time=row["time_utc"])]


def circuit_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "circuit-breaker" / "circuit-breaker-plan-v2532.json"
    d = read_json(p) or {}
    generated = parse_time(d.get("generated_utc") or d.get("updated_utc"))
    out: list[dict[str, Any]] = []
    instances = d.get("instances") or []
    if isinstance(instances, dict):
        instances = [{"instance_id": k, **(v if isinstance(v, dict) else {})} for k, v in instances.items()]
    for inst in instances if isinstance(instances, list) else []:
        if not isinstance(inst, dict):
            continue
        iid = inst.get("instance_id") or ""
        for r in inst.get("accounts") or []:
            if not isinstance(r, dict):
                continue
            row = dict(r); row["instance_id"] = iid
            state = str(r.get("desired_state") or r.get("state") or "CLOSED").upper()
            sev = "ERROR" if state == "OPEN" else ("WARNING" if state == "HALF_OPEN" else "INFO")
            out.append(event("circuit-breaker", "CIRCUIT_STATE", row, severity=sev, message=f"Circuit {state}", fallback_time=generated))
    return out


def predictive_events(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "predictive-quota" / "predictive-quota-plan-v2533.json"
    d = read_json(p) or {}
    generated = parse_time(d.get("generated_utc") or d.get("updated_utc"))
    out = []
    for r in d.get("accounts") or []:
        if not isinstance(r, dict):
            continue
        risk = str(r.get("risk") or "UNKNOWN").upper()
        sev = "ERROR" if risk == "EMERGENCY" else ("WARNING" if risk in {"HIGH", "MEDIUM"} else "INFO")
        out.append(event("predictive-quota", "QUOTA_RISK", r, severity=sev, message=f"Predictive quota risk {risk}", fallback_time=generated))
    return out


def issue_events(data_dir: Path) -> list[dict[str, Any]]:
    specs = [
        (data_dir / "self-healing" / "self-healing-latest-v2539.json", "self-healing", "SELF_HEALING"),
        (data_dir / "security" / "security-latest-v2540.json", "security", "SECURITY"),
    ]
    out = []
    for p, source, kind in specs:
        d = read_json(p) or {}
        generated = parse_time(d.get("generated_utc") or d.get("updated_utc"))
        for r in d.get("issues") or []:
            if not isinstance(r, dict):
                continue
            sev = str(r.get("severity") or "WARNING").upper()
            out.append(event(source, kind, r, severity=sev, message=str(r.get("detail") or r.get("code") or ""), fallback_time=generated))
        for r in d.get("actions") or []:
            if not isinstance(r, dict):
                continue
            sev = "INFO" if r.get("ok", True) else "ERROR"
            out.append(event(source, kind + "_ACTION", r, severity=sev, message=str(r.get("message") or r.get("error") or r.get("action") or ""), fallback_time=generated))
    return out


def stable_hash(ev: dict[str, Any]) -> str:
    base = "|".join(str(ev.get(k) or "") for k in ("time_utc", "source", "kind", "request_id", "instance_id", "account", "status", "message"))
    return hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:24]


def sort_key(ev: dict[str, Any]) -> tuple[str, str]:
    t = ev.get("time_utc") or ""
    return (str(t), str(ev.get("event_id") or ""))


def build_report(data_dir: Path, max_events: int = MAX_EVENTS_DEFAULT) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for fn in (usage_events, jsonl_events, closed_loop_events, smart_model_events, lan_pool_events, reliability_soak_events, performance_scale_events, real_codex_cert_events, usage_token_events, recovery_replay_events, startup_recovery_events, windows_recovery_observer_events, real_effect_crash_cert_events, target_recovery_evidence_events, windows_target_adapter_events, attested_evidence_promotion_events, recovery_operator_timeline_events, windows_attestation_signer_events, target_certification_runbook_events, attestation_exchange_events, attestation_trust_store_events, offline_attestation_verifier_events, target_certification_campaign_events, target_campaign_executor_events, attested_promotion_review_events, target_certification_evidence_ingest_events, promotion_decision_ledger_events, windows_target_capture_kit_events, cockpit_baseline_watch_events, windows_target_import_review_events, baseline_delta_watch_events, external_windows_review_packet_events, baseline_drift_reconciliation_events, target_crash_harness_events, target_machine_cert_events, rotation_torture_events, production_simulation_events, autonomous_router_twin_events, protocol_chaos_events, recovery_planner_events, compound_fault_recovery_events, official_auth_compat_events, recovery_journal_events, circuit_events, predictive_events, issue_events):
        try:
            events.extend(fn(data_dir))
        except Exception as exc:
            events.append(event("unified-diagnostics", "COLLECTOR_ERROR", {"status": type(exc).__name__}, severity="WARNING", message=f"{fn.__name__}: {type(exc).__name__}"))
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ev in events:
        ev["event_id"] = stable_hash(ev)
        if ev["event_id"] in seen:
            continue
        seen.add(ev["event_id"])
        clean.append(ev)
    clean.sort(key=sort_key, reverse=True)
    clean = clean[:max(50, min(max_events, 5000))]

    counts: dict[str, int] = {"total": len(clean), "errors": 0, "warnings": 0, "requests": 0, "route_decisions": 0, "smart_model_decisions": 0, "failovers": 0, "circuit_open": 0, "self_healing": 0}
    by_source: dict[str, int] = {}
    by_account: dict[str, dict[str, Any]] = {}
    request_map: dict[str, list[dict[str, Any]]] = {}
    for ev in clean:
        sev = str(ev.get("severity") or "INFO").upper()
        if sev in {"ERROR", "CRITICAL", "HIGH"}: counts["errors"] += 1
        elif sev in {"WARNING", "WARN", "MEDIUM"}: counts["warnings"] += 1
        if ev.get("kind") == "REQUEST": counts["requests"] += 1
        if ev.get("kind") == "ROUTER_DECISION": counts["route_decisions"] += 1
        if ev.get("kind") == "MODEL_ROUTER_DECISION": counts["smart_model_decisions"] += 1
        if ev.get("kind") in {"ROUTE", "ROUTE_DECISION", "ROUTER_DECISION"} and ev.get("details", {}).get("from_account") and ev.get("details", {}).get("to_account") and str(ev["details"]["from_account"]).lower() != str(ev["details"]["to_account"]).lower():
            counts["failovers"] += 1
        if ev.get("kind") == "CIRCUIT_STATE" and str(ev.get("message") or "").endswith("OPEN"):
            counts["circuit_open"] += 1
        if str(ev.get("kind") or "").startswith("SELF_HEALING"):
            counts["self_healing"] += 1
        src = str(ev.get("source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        acct = str(ev.get("account") or "").strip()
        if acct:
            row = by_account.setdefault(acct, {"account": acct, "events": 0, "errors": 0, "warnings": 0, "requests": 0, "last_seen_utc": ""})
            row["events"] += 1
            row["errors"] += int(sev in {"ERROR", "CRITICAL", "HIGH"})
            row["warnings"] += int(sev in {"WARNING", "WARN", "MEDIUM"})
            row["requests"] += int(ev.get("kind") == "REQUEST")
            if str(ev.get("time_utc") or "") > row["last_seen_utc"]:
                row["last_seen_utc"] = ev.get("time_utc") or ""
        rid = str(ev.get("request_id") or "").strip()
        if rid:
            request_map.setdefault(rid, []).append(ev)

    request_timelines = []
    for rid, rows in request_map.items():
        rows_sorted = sorted(rows, key=sort_key)
        first = rows_sorted[0]
        last = rows_sorted[-1]
        request_timelines.append({
            "request_id": rid,
            "events": len(rows_sorted),
            "account": next((x.get("account") for x in reversed(rows_sorted) if x.get("account")), ""),
            "model": next((x.get("model") for x in reversed(rows_sorted) if x.get("model")), ""),
            "instance_id": next((x.get("instance_id") for x in reversed(rows_sorted) if x.get("instance_id")), ""),
            "start_utc": first.get("time_utc") or "",
            "end_utc": last.get("time_utc") or "",
            "status": next((x.get("status") for x in reversed(rows_sorted) if x.get("status")), ""),
            "latency_ms": next((x.get("latency_ms") for x in reversed(rows_sorted) if x.get("latency_ms") is not None), None),
            "has_error": any(str(x.get("severity") or "").upper() in {"ERROR", "CRITICAL", "HIGH"} for x in rows_sorted),
            "timeline": rows_sorted[-30:],
        })
    request_timelines.sort(key=lambda x: (x.get("end_utc") or "", x.get("request_id") or ""), reverse=True)

    layer_status = {
        "request": "ERROR" if counts["errors"] and counts["requests"] else ("OK" if counts["requests"] else "NO_DATA"),
        "routing": "WARNING" if counts["failovers"] else ("OK" if counts["route_decisions"] else "NO_DATA"),
        "circuit": "WARNING" if counts["circuit_open"] else ("OK" if by_source.get("circuit-breaker") else "NO_DATA"),
        "self_healing": "WARNING" if counts["self_healing"] else ("OK" if by_source.get("self-healing") else "NO_DATA"),
        "security": "WARNING" if any(e.get("source") == "security" and str(e.get("severity") or "").upper() not in {"INFO", "LOW"} for e in clean) else ("OK" if by_source.get("security") else "NO_DATA"),
        "lan_pool": "WARNING" if any(e.get("source") == "lan-pool" and str(e.get("severity") or "").upper() in {"WARNING", "ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("lan-pool") else "NO_DATA"),
        "reliability_soak": "ERROR" if any(e.get("source") == "reliability-soak" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("WARNING" if any(e.get("source") == "reliability-soak" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("reliability-soak") else "NO_DATA")),
        "performance_scale": "ERROR" if any(e.get("source") == "performance-scale" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("WARNING" if any(e.get("source") == "performance-scale" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("performance-scale") else "NO_DATA")),
        "real_codex_cert": "ERROR" if any(e.get("source") == "real-codex-cert" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("WARNING" if any(e.get("source") == "real-codex-cert" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("real-codex-cert") else "NO_DATA")),
        "target_machine_cert": "ERROR" if any(e.get("source") == "target-machine-cert" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("WARNING" if any(e.get("source") == "target-machine-cert" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("target-machine-cert") else "NO_DATA")),
        "rotation_torture": "ERROR" if any(e.get("source") == "rotation-torture" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("rotation-torture") else "NO_DATA"),
        "production_simulation": "ERROR" if any(e.get("source") == "production-simulation" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("production-simulation") else "NO_DATA"),
        "autonomous_router_twin": "ERROR" if any(e.get("source") == "autonomous-router-twin" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("autonomous-router-twin") else "NO_DATA"),
        "protocol_chaos": "ERROR" if any(e.get("source") == "protocol-chaos" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("protocol-chaos") else "NO_DATA"),
        "recovery_planner": "ERROR" if any(e.get("source") == "recovery-planner" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("recovery-planner") else "NO_DATA"),
        "compound_fault_recovery": "ERROR" if any(e.get("source") == "compound-fault-recovery" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("compound-fault-recovery") else "NO_DATA"),
        "official_auth_compat": "ERROR" if any(e.get("source") == "official-auth-compat" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("official-auth-compat") else "NO_DATA"),
        "recovery_journal": "ERROR" if any(e.get("source") == "recovery-journal" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("recovery-journal") else "NO_DATA"),
        "usage_token_center": "ERROR" if any(e.get("source") == "usage-token-center" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("usage-token-center") else "NO_DATA"),
        "recovery_replay": "ERROR" if any(e.get("source") == "recovery-replay" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("recovery-replay") else "NO_DATA"),
        "startup_recovery": "ERROR" if any(e.get("source") == "startup-recovery" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("WARNING" if any(e.get("source") == "startup-recovery" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("startup-recovery") else "NO_DATA")),
        "windows_recovery_observer": "WARNING" if any(e.get("source") == "windows-recovery-observer" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("windows-recovery-observer") else "NO_DATA"),
        "real_effect_crash_cert": "WARNING" if any(e.get("source") == "real-effect-crash-cert" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("real-effect-crash-cert") else "NO_DATA"),
        "target_recovery_evidence": "OK" if by_source.get("target-recovery-evidence") else "NO_DATA",
        "windows_target_adapter": "WARNING" if any(e.get("source") == "windows-target-adapter" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("windows-target-adapter") else "NO_DATA"),
        "attested_evidence_promotion": "OK" if by_source.get("attested-evidence-promotion") else "NO_DATA",
        "recovery_operator_timeline": "WARNING" if any(e.get("source") == "recovery-operator-timeline" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("recovery-operator-timeline") else "NO_DATA"),
        "windows_attestation_signer": "WARNING" if any(e.get("source") == "windows-attestation-signer" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("windows-attestation-signer") else "NO_DATA"),
        "target_certification_runbook": "WARNING" if any(e.get("source") == "target-certification-runbook" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("target-certification-runbook") else "NO_DATA"),
        "attestation_exchange": "WARNING" if any(e.get("source") == "attestation-exchange" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("attestation-exchange") else "NO_DATA"),
        "attestation_trust_store": "WARNING" if any(e.get("source") == "attestation-trust-store" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("attestation-trust-store") else "NO_DATA"),
        "offline_attestation_verifier": "WARNING" if any(e.get("source") == "offline-attestation-verifier" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("offline-attestation-verifier") else "NO_DATA"),
        "target_certification_campaign": "WARNING" if any(e.get("source") == "target-certification-campaign" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("target-certification-campaign") else "NO_DATA"),
        "target_campaign_executor": "WARNING" if any(e.get("source") == "target-campaign-executor" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("target-campaign-executor") else "NO_DATA"),
        "attested_promotion_review": "WARNING" if any(e.get("source") == "attested-promotion-review" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("attested-promotion-review") else "NO_DATA"),
        "target_certification_evidence_ingest": "WARNING" if any(e.get("source") == "target-cert-evidence-ingest" and str(e.get("severity") or "").upper() == "WARNING" for e in clean) else ("OK" if by_source.get("target-cert-evidence-ingest") else "NO_DATA"),
        "promotion_decision_ledger": "OK" if by_source.get("promotion-decision-ledger") else "NO_DATA",
        "target_crash_harness": "ERROR" if any(e.get("source") == "target-crash-harness" and str(e.get("severity") or "").upper() in {"ERROR", "CRITICAL"} for e in clean) else ("OK" if by_source.get("target-crash-harness") else "NO_DATA"),
    }
    return {
        "schema": SCHEMA,
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "generated_utc": iso_now(),
        "privacy": {"contains_prompt": False, "contains_request_body": False, "contains_raw_secret": False, "metadata_only": True},
        "summary": counts,
        "layers": layer_status,
        "by_source": dict(sorted(by_source.items())),
        "accounts": sorted(by_account.values(), key=lambda x: (-x["errors"], -x["warnings"], -x["events"], x["account"].lower())),
        "requests": request_timelines[:120],
        "timeline": clean,
    }


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history")
    ap.add_argument("--max-events", type=int, default=MAX_EVENTS_DEFAULT)
    ap.add_argument("--mode", choices=["get", "refresh"], default="refresh")
    ap.add_argument("--output")
    args = ap.parse_args()
    latest = Path(args.latest)
    if args.mode == "get" and latest.exists():
        report = read_json(latest) or {}
    else:
        report = build_report(Path(args.data_dir), args.max_events)
        atomic_json(latest, report)
        if args.history:
            hp = Path(args.history); hp.parent.mkdir(parents=True, exist_ok=True)
            compact = {"generated_utc": report.get("generated_utc"), "summary": report.get("summary"), "layers": report.get("layers"), "privacy": report.get("privacy")}
            with hp.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(compact, ensure_ascii=False) + "\n")
    out = {"ok": True, "version": VERSION, "unified_diagnostics": report}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
