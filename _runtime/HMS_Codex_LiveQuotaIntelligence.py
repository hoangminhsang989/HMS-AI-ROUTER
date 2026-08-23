#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.50"
SCHEMA_VERSION = 1
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization", "bearer",
    "api_key", "apikey", "client_secret", "password", "auth_json", "prompt",
    "request_body", "response_body", "body",
}
DEFAULT_POLICY: dict[str, Any] = {
    "fresh_seconds": 600,
    "stale_seconds": 1200,
    "fail_closed": True,
    "require_both_primary_windows": True,
    "reserves": {
        "FREE": 25.0,
        "PLUS": 15.0,
        "PRO": 10.0,
        "TEAM": 10.0,
        "BUSINESS": 10.0,
        "ENTERPRISE": 8.0,
        "DEFAULT": 15.0,
    },
    "emergency_pct": 3.0,
    "switch_release_margin_pct": 5.0,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def ek(value: Any) -> str:
    return str(value or "").strip().lower()


def plan_key(value: Any) -> str:
    p = str(value or "").strip().upper()
    aliases = {
        "CHATGPT FREE": "FREE", "BASIC": "FREE",
        "CHATGPT PLUS": "PLUS", "PERSONAL": "PLUS",
        "CHATGPT PRO": "PRO",
        "CHATGPT TEAM": "TEAM",
        "CHATGPT BUSINESS": "BUSINESS",
        "CHATGPT ENTERPRISE": "ENTERPRISE",
    }
    return aliases.get(p, p or "DEFAULT")


def deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


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


def freshness(quota: dict[str, Any], policy: dict[str, Any], now: datetime) -> tuple[str, float | None, str | None]:
    # last_success is authoritative. A failed refresh attempt MUST NOT make old quota fresh.
    last_success = (
        quota.get("last_success_utc") or quota.get("lastSuccessUtc") or
        quota.get("refreshed_utc") or quota.get("refreshedUtc")
    )
    dt = parse_time(last_success)
    if not dt:
        return "UNKNOWN", None, None
    age = max(0.0, (now - dt).total_seconds())
    fresh_s = max(30.0, float(policy.get("fresh_seconds", 600)))
    stale_s = max(fresh_s, float(policy.get("stale_seconds", 1200)))
    if age <= fresh_s:
        state = "FRESH"
    elif age <= stale_s:
        state = "AGING"
    else:
        state = "STALE"
    return state, age, iso(dt)


def quota_window(quota: dict[str, Any], prefix: str) -> dict[str, Any]:
    if prefix == "five_hour":
        remaining = num(quota.get("five_hour_remaining", quota.get("hourlyRemaining")))
        reset = quota.get("five_hour_reset", quota.get("hourlyReset"))
        present = quota.get("five_hour_window_present", quota.get("hourlyWindowPresent"))
        minutes = quota.get("five_hour_window_minutes", quota.get("hourlyWindowMinutes"))
        label = "5h"
    else:
        remaining = num(quota.get("weekly_remaining", quota.get("weeklyRemaining")))
        reset = quota.get("weekly_reset", quota.get("weeklyReset"))
        present = quota.get("weekly_window_present", quota.get("weeklyWindowPresent"))
        minutes = quota.get("weekly_window_minutes", quota.get("weeklyWindowMinutes"))
        label = "weekly"
    return {
        "name": label,
        "remaining_pct": None if remaining is None else round(clamp(remaining), 2),
        "reset_utc": iso(parse_time(reset)) if parse_time(reset) else None,
        "window_minutes": int(minutes) if num(minutes) is not None else None,
        "present": bool(present) if present is not None else remaining is not None,
    }


def reserve_for(plan: Any, policy: dict[str, Any]) -> float:
    reserves = policy.get("reserves") or {}
    key = plan_key(plan)
    value = num(reserves.get(key))
    if value is None:
        value = num(reserves.get("DEFAULT"))
    return clamp(value if value is not None else 15.0)


def evaluate_account(account: dict[str, Any], policy: dict[str, Any], now: datetime) -> dict[str, Any]:
    quota = account.get("quota") or {}
    plan = plan_key(account.get("plan") or quota.get("plan"))
    reserve = reserve_for(plan, policy)
    fs, age, last_success = freshness(quota, policy, now)
    five = quota_window(quota, "five_hour")
    week = quota_window(quota, "weekly")
    windows = [five, week]
    known = [w["remaining_pct"] for w in windows if w["remaining_pct"] is not None]
    floor = min(known) if known else None
    usable = None if floor is None else max(0.0, floor - reserve)
    fail_closed = bool(policy.get("fail_closed", True))
    require_both = bool(policy.get("require_both_primary_windows", True))
    status = str(account.get("status") or "").upper()
    reasons: list[str] = []
    routing_eligible = status == "READY"
    if not routing_eligible:
        reasons.append("STATUS_" + (status or "UNKNOWN"))

    if fs == "UNKNOWN":
        reasons.append("QUOTA_FRESHNESS_UNKNOWN")
        if fail_closed:
            routing_eligible = False
    elif fs == "STALE":
        reasons.append("QUOTA_STALE")
        if fail_closed:
            routing_eligible = False
    elif fs == "AGING":
        reasons.append("QUOTA_AGING")

    missing = [w["name"] for w in windows if not w["present"] or w["remaining_pct"] is None]
    if missing:
        reasons.append("QUOTA_WINDOW_MISSING:" + ",".join(missing))
        if fail_closed and require_both:
            routing_eligible = False

    emergency = float(policy.get("emergency_pct", 3.0))
    if floor is not None:
        if floor <= 0:
            routing_eligible = False
            reasons.append("QUOTA_EMPTY")
        elif floor <= emergency:
            routing_eligible = False
            reasons.append("QUOTA_EMERGENCY")
        elif floor <= reserve:
            routing_eligible = False
            reasons.append("PLAN_RESERVE_HELD")
        elif floor <= reserve + float(policy.get("switch_release_margin_pct", 5.0)):
            reasons.append("NEAR_PLAN_RESERVE")

    source_state = str(quota.get("source_state") or quota.get("sourceState") or "").upper()
    last_attempt = quota.get("last_attempt_utc") or quota.get("lastAttemptUtc")
    error_code = quota.get("error_code") or quota.get("errorCode")
    if source_state == "ERROR" or error_code:
        reasons.append("LAST_REFRESH_FAILED")

    return {
        "account": str(account.get("email") or ""),
        "plan": plan,
        "status": status,
        "freshness_state": fs,
        "age_seconds": None if age is None else round(age, 1),
        "last_success_utc": last_success,
        "last_attempt_utc": iso(parse_time(last_attempt)) if parse_time(last_attempt) else None,
        "source_state": source_state or ("FRESH" if fs == "FRESH" else fs),
        "five_hour": five,
        "weekly": week,
        "quota_floor_pct": None if floor is None else round(floor, 2),
        "reserve_pct": round(reserve, 2),
        "usable_remaining_pct": None if usable is None else round(usable, 2),
        "routing_eligible": bool(routing_eligible),
        "reason_codes": reasons,
        "session_affinity_action": "KEEP_EXISTING_SESSION",
        "new_session_action": "ALLOW" if routing_eligible else "BLOCK_OR_ROUTE_ELSEWHERE",
    }


def evaluate(accounts_obj: dict[str, Any], policy_override: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    policy = deep_merge(DEFAULT_POLICY, policy_override or {})
    t = now or utcnow()
    rows = [evaluate_account(a, policy, t) for a in list(accounts_obj.get("accounts") or []) if isinstance(a, dict)]
    rows.sort(key=lambda r: (not r["routing_eligible"], -(r["usable_remaining_pct"] if r["usable_remaining_pct"] is not None else -1), ek(r["account"])))
    ready = [r for r in rows if r["routing_eligible"]]
    stale = [r for r in rows if r["freshness_state"] == "STALE"]
    unknown = [r for r in rows if r["freshness_state"] == "UNKNOWN"]
    output = {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "generated_utc": iso(t),
        "policy": {
            "fresh_seconds": int(policy["fresh_seconds"]),
            "stale_seconds": int(policy["stale_seconds"]),
            "fail_closed": bool(policy["fail_closed"]),
            "require_both_primary_windows": bool(policy["require_both_primary_windows"]),
            "reserves": policy["reserves"],
            "emergency_pct": float(policy["emergency_pct"]),
            "switch_release_margin_pct": float(policy["switch_release_margin_pct"]),
        },
        "summary": {
            "accounts": len(rows),
            "routing_eligible": len(ready),
            "stale": len(stale),
            "unknown": len(unknown),
            "all_fail_closed": bool(rows) and not ready,
        },
        "accounts": rows,
        "safety": {
            "last_good_preservation_required": True,
            "failed_refresh_must_not_advance_last_success": True,
            "stale_fail_closed_new_sessions": bool(policy["fail_closed"]),
            "existing_session_affinity_untouched": True,
            "oauth_tokens_untouched": True,
            "raw_quota_response_not_emitted": True,
        },
    }
    if contains_secret_like(output):
        raise RuntimeError("SECRET_LIKE_OUTPUT")
    return output


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.50 Live Quota Intelligence")
    ap.add_argument("--accounts", required=True)
    ap.add_argument("--output")
    ap.add_argument("--policy-json")
    args = ap.parse_args()
    try:
        accounts = read_json(Path(args.accounts))
        policy = json.loads(args.policy_json) if args.policy_json else {}
        result = evaluate(accounts, policy)
        if args.output:
            atomic_json(Path(args.output), result)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
