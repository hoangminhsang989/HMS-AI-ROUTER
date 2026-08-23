#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_AdaptiveRouterPolicy as adaptive
import HMS_Codex_ClosedLoopRouter as closed_loop
import HMS_Codex_LanPool as lan
import HMS_Codex_LiveQuotaIntelligence as live_quota
import HMS_Codex_SmartGateway as gateway

VERSION = "25.51"
SCHEMA_VERSION = 1
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization", "bearer",
    "api_key", "apikey", "client_secret", "password", "prompt", "request_body",
    "response_body", "body", "auth_json",
}


def iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def contains_secret_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS or kl.endswith(("_token", "_secret", "_password", "_api_key")):
                return True
            if contains_secret_like(v):
                return True
    elif isinstance(obj, list):
        return any(contains_secret_like(v) for v in obj)
    return False


def immutable_auth_fingerprint(data: dict[str, Any]) -> str:
    """Hash auth identity/secret payload while ignoring routing-only knobs.

    The hash is evidence only; raw auth values are never returned in reports.
    """
    clean = {k: v for k, v in data.items() if k not in {"priority", "weight"}}
    raw = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def quota_account(email: str, plan: str, remaining: float, now: datetime, *, status: str = "READY", pool: float = 80.0,
                  freshness_minutes: int = 1, source_state: str = "FRESH") -> dict[str, Any]:
    stamp = now - timedelta(minutes=freshness_minutes)
    return {
        "email": email,
        "plan": plan,
        "status": status,
        "pool_score": pool,
        "health_score": pool,
        "quota": {
            "five_hour_remaining": remaining,
            "weekly_remaining": remaining,
            "five_hour_window_present": True,
            "weekly_window_present": True,
            "last_success_utc": iso(stamp),
            "last_attempt_utc": iso(stamp),
            "source_state": source_state,
        },
    }


def enrich_live_quota(accounts: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    result = live_quota.evaluate({"accounts": accounts}, now=now)
    by_email = {str(r.get("account") or "").lower(): r for r in result.get("accounts") or []}
    out: list[dict[str, Any]] = []
    for src in accounts:
        row = json.loads(json.dumps(src))
        ev = by_email.get(str(src.get("email") or "").lower()) or {}
        q = row.setdefault("quota", {})
        q["freshness_state"] = ev.get("freshness_state")
        q["routing_eligible"] = ev.get("routing_eligible")
        q["reserve_pct"] = ev.get("reserve_pct")
        q["usable_remaining_pct"] = ev.get("usable_remaining_pct")
        q["reason_codes"] = list(ev.get("reason_codes") or [])
        out.append(row)
    return out


def adaptive_plan(accounts: list[dict[str, Any]], state: dict[str, Any], *, min_delta: float = 8.0,
                  hold_minutes: int = 30, cooldown_sec: int = 180) -> dict[str, Any]:
    return adaptive.evaluate(
        {"accounts": accounts},
        {"by_account_week": []},
        state,
        {
            "enabled": True,
            "mode": "GUARDED_AUTO",
            "min_samples": 0,
            "min_score_delta": min_delta,
            "hold_minutes": hold_minutes,
            "cooldown_sec": cooldown_sec,
            "live_quota_fail_closed": True,
            "quota_floor_pct": 10,
            "emergency_quota_pct": 3,
        },
    )


def scenario_active_becomes_ineligible(now: datetime) -> dict[str, Any]:
    a = quota_account("alpha@example.test", "Plus", 14, now, pool=96)
    b = quota_account("beta@example.test", "Pro", 72, now, pool=73)
    rows = enrich_live_quota([a, b], now)
    state = {"active_account": "alpha@example.test", "last_applied_utc": iso(now)}
    plan = adaptive_plan(rows, state)
    return {
        "current": plan.get("current_account"),
        "recommended": plan.get("recommended_account"),
        "switch_needed": bool(plan.get("switch_needed")),
        "can_switch": bool(plan.get("can_switch")),
        "critical": bool(plan.get("current_critical")),
        "reasons": list(plan.get("reason_codes") or []),
        "session_affinity_untouched": bool((plan.get("safety") or {}).get("session_affinity_untouched")),
    }


def scenario_hysteresis_no_ping_pong(now: datetime, cycles: int = 160) -> dict[str, Any]:
    # beta is current after alpha hit reserve. Alpha then oscillates just above/below release margin.
    # Existing beta selection must not flap on every quota sample.
    state = {"active_account": "beta@example.test", "last_applied_utc": iso(now)}
    switchable = 0
    recommended_alpha = 0
    held = 0
    for idx in range(cycles):
        alpha_remaining = 19 if idx % 2 == 0 else 21
        alpha = quota_account("alpha@example.test", "Plus", alpha_remaining, now, pool=92)
        beta = quota_account("beta@example.test", "Pro", 65, now, pool=80)
        rows = enrich_live_quota([alpha, beta], now)
        plan = adaptive_plan(rows, state, min_delta=3, hold_minutes=30, cooldown_sec=180)
        if plan.get("recommended_account") == "alpha@example.test":
            recommended_alpha += 1
        if plan.get("can_switch"):
            switchable += 1
        if any(x in ("MIN_HOLD", "SWITCH_COOLDOWN", "HYSTERESIS_SCORE_DELTA") for x in plan.get("reason_codes") or []):
            held += 1
    return {"cycles": cycles, "switchable": switchable, "recommended_alpha": recommended_alpha, "held": held}


def scenario_stale_recovery(now: datetime) -> dict[str, Any]:
    alpha_stale = quota_account("alpha@example.test", "Plus", 95, now, pool=99, freshness_minutes=30)
    beta = quota_account("beta@example.test", "Pro", 60, now, pool=76)
    stale_rows = enrich_live_quota([alpha_stale, beta], now)
    stale_plan = adaptive_plan(stale_rows, {"active_account": "beta@example.test"}, min_delta=1, hold_minutes=0, cooldown_sec=0)

    alpha_fresh = quota_account("alpha@example.test", "Plus", 95, now, pool=99, freshness_minutes=1)
    fresh_rows = enrich_live_quota([alpha_fresh, beta], now)
    fresh_plan = adaptive_plan(fresh_rows, {"active_account": "beta@example.test", "last_applied_utc": iso(now)}, min_delta=1, hold_minutes=30, cooldown_sec=180)
    return {
        "stale_recommended": stale_plan.get("recommended_account"),
        "stale_alpha_eligible": next(x for x in stale_plan.get("ranking") or [] if x.get("account") == "alpha@example.test").get("eligible"),
        "recovery_recommended": fresh_plan.get("recommended_account"),
        "recovery_can_switch_immediately": bool(fresh_plan.get("can_switch")),
        "recovery_reasons": list(fresh_plan.get("reason_codes") or []),
    }


def scenario_gateway_429_affinity(tmp: Path) -> dict[str, Any]:
    cfg = {
        "strategy": "fill-first",
        "session_affinity": True,
        "session_ttl_sec": 3600,
        "health_fail_threshold": 3,
        "health_cooldown_sec": 120,
        "quota_reserve_fail_closed": False,
        "targets": [
            {"id": "B", "account": "beta@example.test", "base_url": "http://127.0.0.1:19001", "priority": 100, "weight": 1, "enabled": True, "model_allow": ["gpt-*"]},
            {"id": "C", "account": "gamma@example.test", "base_url": "http://127.0.0.1:19002", "priority": 60, "weight": 1, "enabled": True, "model_allow": ["gpt-*"]},
        ],
    }
    router = gateway.Router(cfg, tmp / "rotation-gateway-trace.jsonl")
    client = {"id": "rotation-test", "target_allow": ["B", "C"], "model_allow": ["gpt-*"]}
    first, first_reason = router.choose("gpt-5.6", "sticky-session", client=client)
    first_id = first.get("id") if first else None
    for _ in range(3):
        router.mark(first, 429, 25.0)
    after_429, after_reason = router.choose("gpt-5.6", "sticky-session", client=client)
    after_id = after_429.get("id") if after_429 else None
    # A later success clears B health cooldown, but the existing session must stay rebound to C.
    router.mark(first, 200, 20.0)
    recovered_existing, recovered_existing_reason = router.choose("gpt-5.6", "sticky-session", client=client)
    recovered_new, recovered_new_reason = router.choose("gpt-5.6", "new-session", client=client)
    return {
        "first": first_id,
        "first_reason": first_reason,
        "after_429": after_id,
        "after_429_reason": after_reason,
        "existing_after_recovery": recovered_existing.get("id") if recovered_existing else None,
        "existing_after_recovery_reason": recovered_existing_reason,
        "new_after_recovery": recovered_new.get("id") if recovered_new else None,
        "new_after_recovery_reason": recovered_new_reason,
        "affinity_entries": len(router.affinity),
    }


def scenario_auth_isolation(tmp: Path, now: datetime) -> dict[str, Any]:
    auth = tmp / "auth"
    auth.mkdir(parents=True, exist_ok=True)
    originals = {
        "alpha@example.test": {"email": "alpha@example.test", "access_token": "synthetic-alpha-secret", "refresh_token": "synthetic-alpha-refresh", "priority": 10, "weight": 1},
        "beta@example.test": {"email": "beta@example.test", "access_token": "synthetic-beta-secret", "refresh_token": "synthetic-beta-refresh", "priority": 20, "weight": 2},
    }
    paths: dict[str, Path] = {}
    before: dict[str, str] = {}
    for idx, (email, data) in enumerate(originals.items(), 1):
        p = auth / f"codex-{idx}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        paths[email] = p
        before[email] = immutable_auth_fingerprint(data)

    rows = enrich_live_quota([
        quota_account("alpha@example.test", "Plus", 14, now, pool=95),
        quota_account("beta@example.test", "Pro", 80, now, pool=75),
    ], now)
    plan = adaptive_plan(rows, {"active_account": "alpha@example.test", "last_applied_utc": iso(now)})
    state_path = tmp / "adaptive-state.json"
    applied = adaptive.apply_plan(plan, state_path, auth)
    after = {email: immutable_auth_fingerprint(json.loads(path.read_text(encoding="utf-8"))) for email, path in paths.items()}
    raw_joined = "\n".join(path.read_text(encoding="utf-8") for path in paths.values())
    return {
        "applied": bool(applied.get("applied")),
        "active_account": applied.get("active_account"),
        "immutable_fingerprints_preserved": before == after,
        "account_files_distinct": paths["alpha@example.test"] != paths["beta@example.test"],
        "synthetic_alpha_still_in_alpha_file": "synthetic-alpha-secret" in paths["alpha@example.test"].read_text(encoding="utf-8"),
        "synthetic_beta_still_in_beta_file": "synthetic-beta-secret" in paths["beta@example.test"].read_text(encoding="utf-8"),
        "cross_bleed_absent": "synthetic-beta-secret" not in paths["alpha@example.test"].read_text(encoding="utf-8") and "synthetic-alpha-secret" not in paths["beta@example.test"].read_text(encoding="utf-8"),
        "report_contains_raw_credential": any(x in json.dumps(applied) for x in ("synthetic-alpha-secret", "synthetic-beta-secret", "synthetic-alpha-refresh", "synthetic-beta-refresh")),
        "auth_file_count": len(paths),
        "raw_fixture_bytes": len(raw_joined.encode("utf-8")),
    }


def scenario_two_instance_rotation(now: datetime) -> dict[str, Any]:
    rows = enrich_live_quota([
        quota_account("alpha@example.test", "Plus", 14, now, pool=96),
        quota_account("beta@example.test", "Pro", 75, now, pool=77),
        quota_account("gamma@example.test", "Free", 70, now, pool=72),
    ], now)
    fleet = {
        "accounts": rows,
        "instances": [
            {"id": "I1", "name": "Codex-A", "project": "P1", "router_dir": "/synthetic/i1", "manifest": {"stable_endpoint": "http://127.0.0.1:18101", "accounts": [
                {"email": "alpha@example.test", "file": "codex-a.json"}, {"email": "beta@example.test", "file": "codex-b.json"}, {"email": "gamma@example.test", "file": "codex-c.json"}]}},
            {"id": "I2", "name": "Codex-B", "project": "P2", "router_dir": "/synthetic/i2", "manifest": {"stable_endpoint": "http://127.0.0.1:18102", "accounts": [
                {"email": "alpha@example.test", "file": "codex-a.json"}, {"email": "beta@example.test", "file": "codex-b.json"}, {"email": "gamma@example.test", "file": "codex-c.json"}]}},
        ],
    }
    state = {"instances": {
        "I1": {"preferred_account": "alpha@example.test", "last_applied_utc": iso(now)},
        "I2": {"preferred_account": "alpha@example.test", "last_applied_utc": iso(now)},
    }}
    plan = closed_loop.evaluate(fleet, {"by_account_week": [], "by_account_day": [], "by_account_hour": []}, state,
                                {"enabled": True, "mode": "GUARDED_AUTO", "min_samples": 0, "min_score_delta": 8,
                                 "hold_minutes": 30, "cooldown_sec": 180, "live_quota_fail_closed": True})
    return {
        "instances": len(plan.get("instances") or []),
        "switchable": (plan.get("summary") or {}).get("switchable"),
        "critical": (plan.get("summary") or {}).get("critical"),
        "rows": [{"instance_id": x.get("instance_id"), "current": x.get("current_account"), "recommended": x.get("recommended_account"),
                  "switch_needed": x.get("switch_needed"), "can_switch": x.get("can_switch"), "critical": x.get("current_critical"),
                  "stable_endpoint": x.get("stable_endpoint")} for x in plan.get("instances") or []],
        "session_affinity_untouched": bool((plan.get("safety") or {}).get("session_affinity_untouched")),
        "stable_endpoint_untouched": bool((plan.get("safety") or {}).get("stable_endpoint_untouched")),
    }


def scenario_lan_rejoin(tmp: Path) -> dict[str, Any]:
    shared = tmp / "shared-lan"
    key = lan.derive_pairing_key("HMS-ROTATION-PAIR-2026")
    node1 = lan.default_node("NODE-A", "NODE-A")
    node2 = lan.default_node("NODE-B", "NODE-B")
    lan.heartbeat(shared, key, node1, {"health": "READY", "capacity": 2, "running_instances": 1})
    lan.heartbeat(shared, key, node2, {"health": "READY", "capacity": 2, "running_instances": 1})
    project = {"logical_id": "rotation-project", "project_label": "Rotation Project"}
    first = lan.acquire_lease(shared, key, node1, project, 15)
    blocked = lan.acquire_lease(shared, key, node2, project, 15)

    # Deterministically expire NODE-A's signed lease without sleeping 15 seconds.
    fp = first["fingerprint"]
    p = lan.lease_file(shared, fp)
    wrapper = lan.read_json(p, {})
    payload = dict(wrapper["payload"])
    t = lan.epoch_now() - 40
    payload["acquired_epoch"] = t - 5
    payload["renewed_epoch"] = t
    payload["expires_epoch"] = t + 15
    lan.atomic_json(p, lan.signed(payload, key))

    takeover = lan.acquire_lease(shared, key, node2, project, 15)
    lan.heartbeat(shared, key, node1, {"health": "READY", "capacity": 2, "running_instances": 1})
    stale_owner_rejoin_attempt = lan.acquire_lease(shared, key, node1, project, 15)
    status = lan.status(shared, key, node1, [project])
    return {
        "first_status": first.get("status"),
        "blocked_status": blocked.get("status"),
        "takeover_status": takeover.get("status"),
        "takeover_epoch": (takeover.get("lease") or {}).get("epoch"),
        "rejoin_attempt_status": stale_owner_rejoin_attempt.get("status"),
        "online_nodes": (status.get("summary") or {}).get("online"),
        "invalid_signatures": (status.get("summary") or {}).get("invalid_signatures"),
        "lease_owner": ((status.get("projects") or [{}])[0].get("lease") or {}).get("node_id"),
        "secret_fields_in_shared_status": bool(lan.secret_scan(status)),
    }


def run(root: Path | None = None, cycles: int = 160) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="hms-v2551-rotation-") as td:
        tmp = Path(td)
        scenarios = {
            "active_ineligible": scenario_active_becomes_ineligible(now),
            "hysteresis": scenario_hysteresis_no_ping_pong(now, cycles),
            "stale_recovery": scenario_stale_recovery(now),
            "gateway_429": scenario_gateway_429_affinity(tmp),
            "auth_isolation": scenario_auth_isolation(tmp, now),
            "multi_instance": scenario_two_instance_rotation(now),
            "lan_rejoin": scenario_lan_rejoin(tmp),
        }

    checks = {
        "active_real_current_preserved": scenarios["active_ineligible"]["current"] == "alpha@example.test",
        "active_rotates_to_eligible": scenarios["active_ineligible"]["recommended"] == "beta@example.test",
        "active_switch_required": scenarios["active_ineligible"]["switch_needed"],
        "active_switch_bypasses_hold_when_critical": scenarios["active_ineligible"]["can_switch"] and scenarios["active_ineligible"]["critical"],
        "active_affinity_not_mutated": scenarios["active_ineligible"]["session_affinity_untouched"],
        "hysteresis_zero_switches": scenarios["hysteresis"]["switchable"] == 0,
        "hysteresis_cycles_exercised": scenarios["hysteresis"]["cycles"] >= 100,
        "stale_high_quota_not_promoted": scenarios["stale_recovery"]["stale_recommended"] == "beta@example.test" and not scenarios["stale_recovery"]["stale_alpha_eligible"],
        "recovered_account_does_not_immediate_pingpong": scenarios["stale_recovery"]["recovery_recommended"] == "alpha@example.test" and not scenarios["stale_recovery"]["recovery_can_switch_immediately"],
        "gateway_initial_affinity_beta": scenarios["gateway_429"]["first"] == "B",
        "gateway_429_rotates_to_gamma": scenarios["gateway_429"]["after_429"] == "C",
        "gateway_existing_session_stays_gamma_after_beta_recovery": scenarios["gateway_429"]["existing_after_recovery"] == "C",
        "gateway_new_session_can_use_recovered_beta": scenarios["gateway_429"]["new_after_recovery"] == "B",
        "gateway_affinity_scoped": scenarios["gateway_429"]["affinity_entries"] >= 2,
        "auth_routing_apply_succeeds": scenarios["auth_isolation"]["applied"],
        "auth_identity_payload_preserved": scenarios["auth_isolation"]["immutable_fingerprints_preserved"],
        "auth_files_distinct": scenarios["auth_isolation"]["account_files_distinct"],
        "auth_cross_bleed_absent": scenarios["auth_isolation"]["cross_bleed_absent"],
        "auth_apply_report_redacted": not scenarios["auth_isolation"]["report_contains_raw_credential"],
        "multi_instance_two_exercised": scenarios["multi_instance"]["instances"] >= 2,
        "multi_instance_both_switchable": scenarios["multi_instance"]["switchable"] == 2,
        "multi_instance_both_critical": scenarios["multi_instance"]["critical"] == 2,
        "multi_instance_affinity_preserved": scenarios["multi_instance"]["session_affinity_untouched"],
        "multi_instance_stable_endpoints_preserved": scenarios["multi_instance"]["stable_endpoint_untouched"],
        "lan_first_acquired": scenarios["lan_rejoin"]["first_status"] == "ACQUIRED",
        "lan_second_blocked_while_owner_active": scenarios["lan_rejoin"]["blocked_status"] == "BLOCKED_OWNED_BY_OTHER_NODE",
        "lan_expired_takeover": scenarios["lan_rejoin"]["takeover_status"] == "TAKEOVER_EXPIRED",
        "lan_epoch_increased": int(scenarios["lan_rejoin"]["takeover_epoch"] or 0) >= 2,
        "lan_old_node_rejoin_cannot_steal": scenarios["lan_rejoin"]["rejoin_attempt_status"] == "BLOCKED_OWNED_BY_OTHER_NODE",
        "lan_owner_is_new_node": scenarios["lan_rejoin"]["lease_owner"] == "NODE-B",
        "lan_two_nodes_online": int(scenarios["lan_rejoin"]["online_nodes"] or 0) == 2,
        "lan_no_invalid_signature": int(scenarios["lan_rejoin"]["invalid_signatures"] or 0) == 0,
        "lan_shared_metadata_no_secret_fields": not scenarios["lan_rejoin"]["secret_fields_in_shared_status"],
    }
    failed = [k for k, ok in checks.items() if not ok]
    report = {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "suite": "SEAMLESS_ROTATION_TORTURE",
        "generated_utc": iso(),
        "verdict": "PASS_SEAMLESS_ROTATION_TORTURE_V25_51" if not failed else "FAIL_SEAMLESS_ROTATION_TORTURE_V25_51",
        "summary": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "cycles": cycles},
        "checks": [{"name": k, "ok": bool(v)} for k, v in checks.items()],
        "scenarios": scenarios,
        "safety": {
            "synthetic_only": True,
            "real_quota_consumed": False,
            "oauth_tokens_mutated": False,
            "session_affinity_authoritative": True,
            "new_session_rotation_only": True,
            "auth_cross_bleed_guard": True,
            "lan_lease_epoch_guard": True,
            "raw_secret_evidence": False,
        },
        "claim_boundary": "Synthetic torture validates control-plane invariants only; target Windows + real Codex + real quota + multi-PC LAN remain required for production certification.",
    }
    # Defensive guarantee: report itself must never contain a secret-shaped field.
    if contains_secret_like(report):
        report["verdict"] = "FAIL_SEAMLESS_ROTATION_TORTURE_V25_51"
        report["summary"]["fail"] += 1
        report["summary"]["total"] += 1
        report["checks"].append({"name": "report_secret_shape_absent", "ok": False})
    else:
        report["summary"]["pass"] += 1
        report["summary"]["total"] += 1
        report["checks"].append({"name": "report_secret_shape_absent", "ok": True})
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.51 Seamless Rotation Torture Test")
    ap.add_argument("--root")
    ap.add_argument("--cycles", type=int, default=160)
    ap.add_argument("--output")
    a = ap.parse_args()
    report = run(Path(a.root) if a.root else None, max(100, min(5000, a.cycles)))
    if a.output:
        Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
