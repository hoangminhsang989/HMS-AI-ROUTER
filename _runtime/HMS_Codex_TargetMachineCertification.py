#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_LiveQuotaIntelligence as lq
import HMS_Codex_RealCertification as rc

VERSION = "25.53"
SCHEMA_VERSION = 1
SAFE_STAGES = ("host", "codex", "quota", "failover", "lan", "soak_6h", "soak_24h")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def read_json(path: Path | None, default: Any = None) -> Any:
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def safe_hash(value: Any, n: int = 16) -> str:
    s = str(value or "").strip()
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:n] if s else ""


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def age_seconds(value: Any) -> float | None:
    d = parse_iso(value)
    if not d:
        return None
    return max(0.0, (datetime.now(timezone.utc) - d).total_seconds())


def discover_latest_json(root: Path, pattern: str) -> Path | None:
    rows = [p for p in root.glob(pattern) if p.is_file()]
    if not rows:
        return None
    rows.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0]


def real_cert_preflight(args: argparse.Namespace) -> dict[str, Any]:
    ns = argparse.Namespace(
        root=str(args.root), instance_store=str(args.instance_store or ""), codex=str(args.codex or ""),
        powershell=str(args.powershell or ""), timeout_sec=float(args.timeout_sec), allow_live_request=False,
        max_live_requests=0, model="", api_key_env_prefix="HMS_CERT_KEY_", live_timeout_sec=90.0,
        output="",
    )
    return rc.run(ns)


def summarize_real(evidence: dict[str, Any]) -> dict[str, Any]:
    s = evidence.get("summary") or {}
    host = evidence.get("host") or {}
    ps = evidence.get("powershell_5_1") or {}
    cli = evidence.get("codex_cli") or {}
    topo = evidence.get("topology") or {}
    verdict = str(evidence.get("verdict") or "")
    passed = verdict == "PASS_REAL_CODEX_CERTIFIED"
    return {
        "pass": passed,
        "verdict": verdict or "MISSING",
        "windows": bool(host.get("windows")),
        "powershell_5_1": bool(ps.get("is_windows_powershell_5_1") and ps.get("parser_ok")),
        "codex_cli": bool(cli.get("version_ok")),
        "codex_version": str(cli.get("version") or ""),
        "managed_instances": int(s.get("managed_instances") or 0),
        "healthy_instances": int(s.get("healthy_instance_endpoints") or 0),
        "live_requests_pass": int(s.get("live_requests_pass") or 0),
        "exact_ttft": int(s.get("exact_output_text_delta_ttft_observed") or 0),
        "isolated_topology": bool(topo.get("at_least_two_instances") and topo.get("unique_projects") and topo.get("unique_codex_homes") and topo.get("dedicated_accounts") and topo.get("unique_ports")),
        "blockers": list(evidence.get("blockers") or []),
    }


def quota_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    evaluated = lq.evaluate(snapshot or {})
    public_rows: list[dict[str, Any]] = []
    real_sources = 0
    fresh_or_aging = 0
    both_windows = 0
    plans: set[str] = set()
    for row, raw in zip(evaluated.get("accounts") or [], snapshot.get("accounts") or []):
        source = str(((raw.get("quota") or {}).get("source") or "")).upper()
        source_real = bool(source and not any(x in source for x in ("SYNTHETIC", "MOCK", "TEST", "FIXTURE")))
        if source_real:
            real_sources += 1
        if row.get("freshness_state") in {"FRESH", "AGING"}:
            fresh_or_aging += 1
        if (row.get("five_hour") or {}).get("present") and (row.get("weekly") or {}).get("present"):
            both_windows += 1
        plan = str(row.get("plan") or "DEFAULT")
        plans.add(plan)
        public_rows.append({
            "account_hash": safe_hash(row.get("account")), "plan": plan,
            "freshness_state": row.get("freshness_state"), "quota_floor_pct": row.get("quota_floor_pct"),
            "reserve_pct": row.get("reserve_pct"), "routing_eligible": bool(row.get("routing_eligible")),
            "source_real": source_real, "reason_codes": list(row.get("reason_codes") or []),
        })
    total = len(public_rows)
    pass_gate = total >= 2 and real_sources >= 2 and fresh_or_aging >= 2 and both_windows >= 2
    return {
        "pass": pass_gate, "accounts": total, "real_source_accounts": real_sources,
        "fresh_or_aging_accounts": fresh_or_aging, "both_primary_windows_accounts": both_windows,
        "routing_eligible": int((evaluated.get("summary") or {}).get("routing_eligible") or 0),
        "plans_observed": sorted(plans), "accounts_public": public_rows,
        "policy": evaluated.get("policy") or {},
        "claim": "REAL_QUOTA_METADATA_ONLY_NO_SECRET_NO_BODY",
    }


def failover_gate(path: Path | None, max_age_hours: float) -> dict[str, Any]:
    obj = read_json(path, {}) if path else {}
    verdict = str(obj.get("verdict") or "MISSING")
    completed = obj.get("completed_local") or obj.get("completed_utc") or obj.get("generated_utc")
    age = age_seconds(completed)
    restored = bool(obj.get("restored"))
    http_ok = int(obj.get("probe_http") or 0) == 200
    target = str(obj.get("target_email") or obj.get("target_file") or "")
    selected = str(obj.get("selected_label") or "")
    different = bool(target and selected and target.strip().lower() != selected.strip().lower())
    fresh = age is not None and age <= max(1.0, max_age_hours) * 3600.0
    return {
        "pass": verdict == "PASS" and restored and http_ok and different and fresh,
        "verdict": verdict, "restored": restored, "probe_http": int(obj.get("probe_http") or 0),
        "different_account_proven": different, "evidence_age_sec": None if age is None else round(age, 1),
        "target_hash": safe_hash(target), "selected_hash": safe_hash(selected),
        "evidence_file_hash": safe_hash(str(path.resolve())) if path else "",
    }


def shared_roundtrip(shared: Path | None) -> dict[str, Any]:
    if not shared:
        return {"pass": False, "available": False, "error": "SHARED_PATH_NOT_CONFIGURED", "shared_path_hash": ""}
    started = time.perf_counter()
    probe_dir = shared / ".hms_target_cert_v2553"
    probe = probe_dir / ("probe-" + secrets.token_hex(8) + ".tmp")
    payload = secrets.token_bytes(48)
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        with probe.open("wb") as fh:
            fh.write(payload); fh.flush()
            try: os.fsync(fh.fileno())
            except OSError: pass
        got = probe.read_bytes()
        ok = got == payload
        return {"pass": ok, "available": True, "roundtrip_ms": round((time.perf_counter()-started)*1000.0, 3), "shared_path_hash": safe_hash(str(shared.resolve()))}
    except Exception as exc:
        return {"pass": False, "available": False, "error": type(exc).__name__, "shared_path_hash": safe_hash(str(shared))}
    finally:
        try: probe.unlink(missing_ok=True)
        except OSError: pass
        try: probe_dir.rmdir()
        except OSError: pass


def lan_gate(snapshot: dict[str, Any], shared: Path | None) -> dict[str, Any]:
    lan = snapshot.get("lan_pool") if isinstance(snapshot.get("lan_pool"), dict) else snapshot
    summary = lan.get("summary") or {}
    sec = lan.get("security") or {}
    online = int(summary.get("online") or 0)
    nodes = int(summary.get("nodes") or 0)
    invalid = int(summary.get("invalid_signatures") or sec.get("invalid_signatures") or 0)
    roundtrip = shared_roundtrip(shared)
    no_credentials = sec.get("credential_sharing") is False and sec.get("raw_token_sharing") is False and sec.get("secret_values_excluded") is True
    return {
        "pass": online >= 2 and nodes >= 2 and invalid == 0 and bool(roundtrip.get("pass")) and no_credentials,
        "nodes": nodes, "online": online, "invalid_signatures": invalid,
        "metadata_only_security": no_credentials, "shared_roundtrip": roundtrip,
    }


def soak_gate(path: Path | None, profile: str) -> dict[str, Any]:
    obj = read_json(path, {}) if path else {}
    synthetic = bool(obj.get("synthetic") or (obj.get("privacy") or {}).get("lan_key_mode") == "SYNTHETIC_TEST_NAMESPACE")
    actual_profile = str(obj.get("profile") or "")
    target = float(obj.get("target_duration_sec") or 0.0)
    active = float(obj.get("active_elapsed_sec") or 0.0)
    expected = 6*3600 if profile == "6h" else 24*3600
    coverage = obj.get("coverage") or {}
    pass_gate = (
        str(obj.get("verdict") or "") == "PASS" and not synthetic and actual_profile == profile and
        target >= expected and active + 1e-6 >= expected and bool(obj.get("coverage_complete")) and
        int(coverage.get("router_probe_ok") or 0) >= 1 and int(coverage.get("instance_probe_ok") or 0) >= 2 and
        int(coverage.get("shared_roundtrip_ok") or 0) >= 1 and
        str(obj.get("resume_semantics") or "") == "ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED"
    )
    return {
        "pass": pass_gate, "verdict": str(obj.get("verdict") or "MISSING"), "profile": actual_profile,
        "active_elapsed_sec": round(active, 3), "target_duration_sec": round(target, 3),
        "coverage_complete": bool(obj.get("coverage_complete")), "synthetic": synthetic,
        "session_count": int(obj.get("session_count") or 0), "cycle_count": int(obj.get("cycle_count") or 0),
        "resume_semantics": str(obj.get("resume_semantics") or ""),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    data_dir = Path(args.data_dir).resolve()
    instance_store = Path(args.instance_store).resolve() if args.instance_store else data_dir / "codex-instances-v1.json"
    quota_snapshot = read_json(Path(args.quota_snapshot), {}) if args.quota_snapshot else {}
    lan_snapshot = read_json(Path(args.lan_snapshot), {}) if args.lan_snapshot else {}

    preflight = real_cert_preflight(argparse.Namespace(**{**vars(args), "root": root, "instance_store": instance_store}))
    real_evidence = read_json(Path(args.real_cert_evidence), None) if args.real_cert_evidence else None
    real = summarize_real(real_evidence if isinstance(real_evidence, dict) else preflight)
    preflight_public = summarize_real(preflight)
    quota = quota_gate(quota_snapshot) if quota_snapshot else {"pass": False, "accounts": 0, "error": "QUOTA_SNAPSHOT_MISSING"}

    failover_path = Path(args.failover_evidence) if args.failover_evidence else discover_latest_json(data_dir / "live-failover-v25_23_1", "*/result.json")
    failover = failover_gate(failover_path, float(args.failover_max_age_hours))
    lan = lan_gate(lan_snapshot, Path(args.shared).resolve() if args.shared else None) if lan_snapshot else {"pass": False, "nodes": 0, "online": 0, "error": "LAN_SNAPSHOT_MISSING", "shared_roundtrip": shared_roundtrip(Path(args.shared).resolve() if args.shared else None)}

    soak_dir = Path(args.soak_state_dir).resolve() if args.soak_state_dir else data_dir / "reliability-soak-v2547"
    soak6_path = Path(args.soak6_evidence) if args.soak6_evidence else discover_latest_json(soak_dir, "soak-result-v2547-*.json")
    soak24_path = Path(args.soak24_evidence) if args.soak24_evidence else discover_latest_json(soak_dir, "soak-result-v2547-*.json")
    # Auto-discovery can only safely claim a profile after reading it.
    if not args.soak6_evidence and soak6_path and str((read_json(soak6_path, {}) or {}).get("profile")) != "6h": soak6_path = next((p for p in sorted(soak_dir.glob("soak-result-v2547-*.json"), key=lambda x:x.stat().st_mtime, reverse=True) if str((read_json(p,{}) or {}).get("profile"))=="6h"), None)
    if not args.soak24_evidence and soak24_path and str((read_json(soak24_path, {}) or {}).get("profile")) != "24h": soak24_path = next((p for p in sorted(soak_dir.glob("soak-result-v2547-*.json"), key=lambda x:x.stat().st_mtime, reverse=True) if str((read_json(p,{}) or {}).get("profile"))=="24h"), None)
    soak6 = soak_gate(soak6_path, "6h")
    soak24 = soak_gate(soak24_path, "24h")

    stages = {
        "host": {"pass": bool(preflight_public.get("windows") and preflight_public.get("powershell_5_1") and preflight_public.get("codex_cli")), "detail": preflight_public},
        "codex": {"pass": bool(real.get("pass") and real.get("isolated_topology") and real.get("managed_instances",0)>=2 and real.get("healthy_instances",0)>=2), "detail": real},
        "quota": {"pass": bool(quota.get("pass")), "detail": quota},
        "failover": {"pass": bool(failover.get("pass")), "detail": failover},
        "lan": {"pass": bool(lan.get("pass")), "detail": lan},
        "soak_6h": {"pass": bool(soak6.get("pass")), "detail": soak6},
        "soak_24h": {"pass": bool(soak24.get("pass")), "detail": soak24},
    }
    passed = sum(1 for x in stages.values() if x["pass"])
    production_pass = passed == len(SAFE_STAGES)
    if production_pass:
        verdict = "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"
    elif stages["host"]["pass"] and stages["codex"]["pass"]:
        verdict = "TARGET_MACHINE_PARTIAL_EVIDENCE"
    elif stages["host"]["pass"]:
        verdict = "TARGET_MACHINE_READY_FOR_LIVE_CERTIFICATION"
    else:
        verdict = "HARNESS_READY_TARGET_RUNTIME_DEFERRED"

    blockers = [name.upper() for name, row in stages.items() if not row["pass"]]
    report = {
        "product": "HMS-AI-ROUTER", "edition": "CODEX_ONLY", "version": VERSION,
        "schema_version": SCHEMA_VERSION, "suite": "TARGET_MACHINE_CERTIFICATION",
        "generated_utc": utcnow(), "verdict": verdict,
        "production_certification": "TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK" if production_pass else "NOT_CLAIMED",
        "summary": {"stages_pass": passed, "stages_total": len(SAFE_STAGES), "production_certified": production_pass},
        "stages": stages, "blockers": blockers,
        "safety": {
            "preflight_consumes_quota": False, "runner_mutates_auth": False, "runner_disables_account": False,
            "live_request_requires_separate_explicit_bridge_confirmation": True,
            "failover_requires_explicit_bounded_operator_test": True,
            "soak_downtime_counted": False, "raw_auth_or_token_persisted": False,
            "prompt_or_response_body_persisted": False, "shared_registry_credentials": False,
        },
        "claim_boundary": "Production PASS requires real Windows PowerShell 5.1 + real Codex live request + >=2 isolated instances + real fresh quota + bounded restored failover + >=2 signed LAN nodes + real 6h and 24h soak. Synthetic evidence never satisfies a production stage.",
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.53 Target-Machine Certification Runner")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--data-dir", default=str(Path(os.environ.get("LOCALAPPDATA") or ".") / "HMS_AI_MultiRouter"))
    ap.add_argument("--instance-store", default="")
    ap.add_argument("--codex", default="")
    ap.add_argument("--powershell", default="")
    ap.add_argument("--timeout-sec", type=float, default=2.0)
    ap.add_argument("--quota-snapshot", default="")
    ap.add_argument("--lan-snapshot", default="")
    ap.add_argument("--shared", default="")
    ap.add_argument("--real-cert-evidence", default="")
    ap.add_argument("--failover-evidence", default="")
    ap.add_argument("--failover-max-age-hours", type=float, default=168.0)
    ap.add_argument("--soak-state-dir", default="")
    ap.add_argument("--soak6-evidence", default="")
    ap.add_argument("--soak24-evidence", default="")
    ap.add_argument("--output", default="")
    a = ap.parse_args()
    try:
        out = run(a)
        code = 0 if out.get("verdict") in {"PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED", "TARGET_MACHINE_PARTIAL_EVIDENCE", "TARGET_MACHINE_READY_FOR_LIVE_CERTIFICATION", "HARNESS_READY_TARGET_RUNTIME_DEFERRED"} else 2
    except Exception as exc:
        out = {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"TARGET_MACHINE_CERTIFICATION","generated_utc":utcnow(),"verdict":"FAIL","production_certification":"NOT_CLAIMED","error":f"{type(exc).__name__}:{exc}"}
        code = 2
    if a.output:
        atomic_json(Path(a.output), out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
