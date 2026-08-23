#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).astimezone(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


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


def email_key(value: Any) -> str:
    return str(value or "").strip().lower()


def quota_floor(account: dict[str, Any]) -> float | None:
    q = account.get("quota") or {}
    vals = []
    for key in ("five_hour_remaining", "weekly_remaining"):
        val = q.get(key)
        if val is None or val == "":
            continue
        try:
            vals.append(float(val))
        except Exception:
            pass
    return min(vals) if vals else None


def live_quota_gate(account: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, list[str], float | None, str]:
    q = account.get("quota") or {}
    freshness = str(q.get("freshness_state") or "UNKNOWN").upper()
    routing_flag = q.get("routing_eligible")
    reserve = q.get("reserve_pct")
    reasons = [str(x) for x in list(q.get("reason_codes") or []) if str(x)]
    fail_closed = bool(cfg.get("live_quota_fail_closed", True))
    # v25.50: when native account center publishes an explicit routing gate, trust it.
    if routing_flag is not None:
        return bool(routing_flag), reasons, as_float(reserve, 0.0), freshness
    if fail_closed and freshness in ("UNKNOWN", "STALE"):
        reasons.append("QUOTA_" + freshness)
        return False, reasons, as_float(reserve, 0.0), freshness
    return True, reasons, as_float(reserve, 0.0) if reserve is not None else None, freshness


def usage_map(usage: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in usage.get("by_account_week") or []:
        key = email_key(row.get("name"))
        if key and key != "—":
            out[key] = row
    return out


def historical_score(row: dict[str, Any] | None) -> tuple[float, int, str]:
    if not row:
        return 50.0, 0, "NO_HISTORY"
    requests = as_int(row.get("requests"))
    success = as_float(row.get("success_rate_pct"), 0.0)
    p95 = as_float(row.get("latency_p95_ms"), 0.0)
    latency = 50.0 if p95 <= 0 else max(0.0, 100.0 - min(100.0, p95 / 40.0))
    confidence = min(1.0, requests / 20.0)
    # Low history confidence stays near neutral so a few lucky requests cannot dominate quota/health.
    raw = success * 0.72 + latency * 0.18 + confidence * 10.0
    score = 50.0 + (raw - 50.0) * confidence
    grade = "HIGH" if requests >= 20 else ("MEDIUM" if requests >= 5 else ("LOW" if requests else "NONE"))
    return max(0.0, min(100.0, score)), requests, grade


def evaluate(accounts_obj: dict[str, Any], usage: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    accounts = list(accounts_obj.get("accounts") or [])
    u_map = usage_map(usage)
    rows: list[dict[str, Any]] = []

    for account in accounts:
        email = str(account.get("email") or "").strip()
        if not email:
            continue
        hist, samples, confidence = historical_score(u_map.get(email_key(email)))
        pool = as_float(account.get("pool_score"), as_float(account.get("health_score"), 50.0))
        effective = pool * 0.72 + hist * 0.28
        role = str(account.get("role") or account.get("pool_role") or "auto").strip().lower()
        status = str(account.get("status") or "").strip().upper()
        qfloor = quota_floor(account)
        eligible = status == "READY"
        blocks: list[str] = []
        if not eligible:
            blocks.append("STATUS_" + (status or "UNKNOWN"))
        live_ok, live_reasons, live_reserve, live_freshness = live_quota_gate(account, cfg)
        if not live_ok:
            eligible = False
            blocks.extend([x for x in live_reasons if x not in blocks])
            if not live_reasons:
                blocks.append("LIVE_QUOTA_FAIL_CLOSED")
        floor_setting = as_float(cfg.get("quota_floor_pct"), 10.0)
        if qfloor is not None and qfloor <= 0:
            eligible = False
            blocks.append("QUOTA_EMPTY")
        elif qfloor is not None and qfloor < floor_setting:
            effective -= min(25.0, (floor_setting - qfloor) * 1.2)
            blocks.append("QUOTA_BELOW_FLOOR")
        if role == "preferred":
            effective += 5.0
        elif role == "reserve":
            effective -= 12.0
        if bool(account.get("favorite")):
            effective += 2.0
        effective = max(0.0, min(100.0, effective))
        rows.append({
            "account": email,
            "alias": str(account.get("alias") or ""),
            "role": role,
            "status": status,
            "quota_floor_pct": qfloor,
            "quota_reserve_pct": live_reserve,
            "quota_freshness": live_freshness,
            "live_quota_eligible": live_ok,
            "pool_score": round(pool, 1),
            "history_score": round(hist, 1),
            "effective_score": round(effective, 1),
            "samples_7d": samples,
            "confidence": confidence,
            "eligible": eligible,
            "blocks": blocks,
            "recent_route": bool(account.get("is_recent_route")),
            "current_priority": as_int(account.get("priority"), 0),
            "current_weight": max(1, as_int(account.get("weight"), 1)),
        })

    non_reserve_ready = [r for r in rows if r["eligible"] and r["role"] != "reserve" and not (r["quota_floor_pct"] is not None and r["quota_floor_pct"] < as_float(cfg.get("quota_floor_pct"), 10.0))]
    if non_reserve_ready:
        # Reserve accounts remain eligible for emergency failover but are not promoted in normal ranking.
        for r in rows:
            if r["role"] == "reserve":
                r["effective_score"] = round(max(0.0, r["effective_score"] - 8.0), 1)

    rows.sort(key=lambda r: (not r["eligible"], -r["effective_score"], -r["samples_7d"], r["account"].lower()))
    eligible = [r for r in rows if r["eligible"]]
    best = eligible[0] if eligible else None

    active_account = email_key(state.get("active_account"))
    if not active_account:
        recent = next((r for r in rows if r["recent_route"] and r["eligible"]), None)
        active_account = email_key(recent.get("account")) if recent else ""
    # v25.51: keep the REAL active account distinct from the eligible candidate pool.
    # If the active account becomes reserve-held/stale/disabled, existing sticky sessions
    # stay owned by the gateway, but NEW sessions must be allowed to rotate away.
    current = next((r for r in rows if email_key(r["account"]) == active_account), None)
    if current is None:
        recent_any = next((r for r in rows if r["recent_route"]), None)
        current = recent_any or (eligible[0] if eligible else (rows[0] if rows else None))
        active_account = email_key(current["account"]) if current else ""

    candidate = best
    delta = round((candidate["effective_score"] - current["effective_score"]), 1) if candidate and current else 0.0
    reason_codes: list[str] = []
    switch_needed = bool(candidate and current and email_key(candidate["account"]) != email_key(current["account"]))

    min_delta = as_float(cfg.get("min_score_delta"), 10.0)
    min_samples = as_int(cfg.get("min_samples"), 5)
    hold_minutes = as_int(cfg.get("hold_minutes"), 30)
    cooldown_sec = as_int(cfg.get("cooldown_sec"), 180)
    last_applied = parse_time(state.get("last_applied_utc"))
    hold_until = last_applied + timedelta(minutes=hold_minutes) if last_applied else None
    cooldown_until = last_applied + timedelta(seconds=cooldown_sec) if last_applied else None
    t = now()

    current_critical = False
    if current:
        if current["status"] != "READY" or not bool(current.get("eligible")) or not bool(current.get("live_quota_eligible", True)):
            current_critical = True
        q = current.get("quota_floor_pct")
        if q is not None and q <= as_float(cfg.get("emergency_quota_pct"), 3.0):
            current_critical = True

    can_switch = switch_needed
    if not candidate:
        can_switch = False
        reason_codes.append("NO_ELIGIBLE_ACCOUNT")
    if switch_needed and delta < min_delta and not current_critical:
        can_switch = False
        reason_codes.append("HYSTERESIS_SCORE_DELTA")
    if candidate and candidate["samples_7d"] < min_samples and not current_critical:
        can_switch = False
        reason_codes.append("MIN_SAMPLES")
    if hold_until and t < hold_until and not current_critical:
        can_switch = False
        reason_codes.append("MIN_HOLD")
    if cooldown_until and t < cooldown_until and not current_critical:
        can_switch = False
        reason_codes.append("SWITCH_COOLDOWN")
    if not switch_needed and candidate:
        reason_codes.append("KEEP_CURRENT")
    if current_critical and switch_needed:
        reason_codes.append("CURRENT_CRITICAL_OVERRIDE")

    mode = str(cfg.get("mode") or "OBSERVE").upper()
    enabled = bool(cfg.get("enabled", True))
    apply_allowed = enabled and mode == "GUARDED_AUTO" and can_switch

    # Translate ranking to conservative routing hints. Existing session affinity remains untouched.
    routing_hints: list[dict[str, Any]] = []
    for idx, row in enumerate(eligible):
        if row["role"] == "reserve":
            priority, weight = 10, max(1, as_int(cfg.get("reserve_weight"), 1))
        elif idx == 0:
            priority, weight = 100, max(1, as_int(cfg.get("preferred_weight"), 8))
        elif idx == 1:
            priority, weight = 60, max(1, as_int(cfg.get("secondary_weight"), 3))
        else:
            priority, weight = 30, 1
        routing_hints.append({"account": row["account"], "priority": priority, "weight": weight, "rank": idx + 1})

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": iso(),
        "enabled": enabled,
        "mode": mode,
        "current_account": current["account"] if current else "",
        "recommended_account": candidate["account"] if candidate else "",
        "recommended_score": candidate["effective_score"] if candidate else 0.0,
        "current_score": current["effective_score"] if current else 0.0,
        "score_delta": delta,
        "switch_needed": switch_needed,
        "can_switch": can_switch,
        "apply_allowed": apply_allowed,
        "reason_codes": reason_codes,
        "current_critical": current_critical,
        "hold_until_utc": iso(hold_until) if hold_until else None,
        "cooldown_until_utc": iso(cooldown_until) if cooldown_until else None,
        "ranking": rows[:12],
        "routing_hints": routing_hints,
        "safety": {
            "session_affinity_untouched": True,
            "oauth_tokens_untouched": True,
            "auth_files_deleted": False,
            "auto_requires_mode": "GUARDED_AUTO",
            "hysteresis": True,
            "live_quota_fail_closed": bool(cfg.get("live_quota_fail_closed", True)),
            "stale_quota_never_promotes_new_session": True,
            "ineligible_active_account_rotates_new_sessions": True,
        },
        "note": "Adaptive Router chỉ đổi routing priority/weight khi GUARDED_AUTO đủ gate; session affinity hiện có vẫn giữ session đang chạy.",
    }


def recursive_email(obj: Any) -> str:
    if isinstance(obj, dict):
        for key in ("email", "account_email", "user_email"):
            if key in obj and obj[key]:
                return str(obj[key]).strip()
        for value in obj.values():
            found = recursive_email(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = recursive_email(value)
            if found:
                return found
    return ""


def auth_map(auth_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    out: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not auth_dir.exists():
        return out
    for path in sorted(auth_dir.glob("codex-*.json")):
        data = read_json(path, None)
        if not isinstance(data, dict):
            continue
        email = email_key(recursive_email(data))
        if email:
            out[email] = (path, data)
    return out


def apply_plan(plan: dict[str, Any], state_path: Path, auth_dir: Path) -> dict[str, Any]:
    if not plan.get("apply_allowed"):
        return {"applied": False, "reason": "PLAN_NOT_ALLOWED", "plan": plan}
    mapping = auth_map(auth_dir)
    hints = plan.get("routing_hints") or []
    previous: dict[str, Any] = {}
    changed: list[dict[str, Any]] = []
    for hint in hints:
        key = email_key(hint.get("account"))
        if key not in mapping:
            continue
        path, data = mapping[key]
        previous[key] = {
            "priority": as_int(data.get("priority"), 0),
            "weight": max(1, as_int(data.get("weight"), 1)),
            "path": str(path),
        }
        new_priority = as_int(hint.get("priority"), 0)
        new_weight = max(1, as_int(hint.get("weight"), 1))
        if previous[key]["priority"] == new_priority and previous[key]["weight"] == new_weight:
            continue
        data["priority"] = new_priority
        data["weight"] = new_weight
        atomic_json(path, data)
        verify = read_json(path, {})
        if as_int(verify.get("priority"), -999) != new_priority or as_int(verify.get("weight"), -999) != new_weight:
            raise RuntimeError(f"READBACK_FAIL:{key}")
        changed.append({"account": hint.get("account"), "priority": new_priority, "weight": new_weight})

    old_state = read_json(state_path, {}) or {}
    history = list(old_state.get("history") or [])[-49:]
    record = {
        "time_utc": iso(),
        "from_account": plan.get("current_account") or "",
        "to_account": plan.get("recommended_account") or "",
        "score_delta": plan.get("score_delta"),
        "changed_accounts": changed,
    }
    history.append(record)
    new_state = {
        "schema_version": SCHEMA_VERSION,
        "active_account": plan.get("recommended_account") or plan.get("current_account") or "",
        "last_applied_utc": record["time_utc"],
        "previous_values": previous,
        "last_plan": plan,
        "history": history,
    }
    atomic_json(state_path, new_state)
    return {
        "applied": True,
        "changed": changed,
        "active_account": new_state["active_account"],
        "state_path": str(state_path),
        "oauth_tokens_untouched": True,
        "files_deleted": False,
    }


def rollback(state_path: Path, auth_dir: Path) -> dict[str, Any]:
    state = read_json(state_path, {}) or {}
    previous = state.get("previous_values") or {}
    if not previous:
        raise RuntimeError("NO_ADAPTIVE_ROUTING_SNAPSHOT")
    mapping = auth_map(auth_dir)
    restored = []
    for key, old in previous.items():
        if key not in mapping:
            continue
        path, data = mapping[key]
        p = as_int(old.get("priority"), 0)
        w = max(1, as_int(old.get("weight"), 1))
        data["priority"] = p
        data["weight"] = w
        atomic_json(path, data)
        verify = read_json(path, {})
        if as_int(verify.get("priority"), -999) != p or as_int(verify.get("weight"), -999) != w:
            raise RuntimeError(f"ROLLBACK_READBACK_FAIL:{key}")
        restored.append({"account": key, "priority": p, "weight": w})
    state["last_rollback_utc"] = iso()
    state["active_account"] = state.get("last_plan", {}).get("current_account") or ""
    state["previous_values"] = {}
    atomic_json(state_path, state)
    return {"rolled_back": True, "restored": restored, "files_deleted": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "evaluate", "apply", "rollback"), required=True)
    ap.add_argument("--accounts")
    ap.add_argument("--usage")
    ap.add_argument("--state", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--auth-dir")
    ap.add_argument("--config-json")
    args = ap.parse_args()
    state_path = Path(args.state)
    plan_path = Path(args.plan)
    cfg = json.loads(args.config_json) if args.config_json else {}
    try:
        if args.mode == "status":
            data = {"state": read_json(state_path, {}) or {}, "plan": read_json(plan_path, {}) or {}}
        elif args.mode in ("evaluate", "apply"):
            if not args.accounts:
                raise ValueError("--accounts required")
            accounts_obj = read_json(Path(args.accounts), {}) or {}
            usage = read_json(Path(args.usage), {}) if args.usage else {}
            state = read_json(state_path, {}) or {}
            plan = evaluate(accounts_obj, usage or {}, state, cfg)
            atomic_json(plan_path, plan)
            if args.mode == "apply":
                if not args.auth_dir:
                    raise ValueError("--auth-dir required")
                applied = apply_plan(plan, state_path, Path(args.auth_dir))
                data = {"plan": plan, "apply": applied}
            else:
                data = {"plan": plan}
        else:
            if not args.auth_dir:
                raise ValueError("--auth-dir required")
            data = {"rollback": rollback(state_path, Path(args.auth_dir)), "plan": read_json(plan_path, {}) or {}}
        out = {"ok": True, "mode": args.mode, "data": data}
    except Exception as exc:
        out = {"ok": False, "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
