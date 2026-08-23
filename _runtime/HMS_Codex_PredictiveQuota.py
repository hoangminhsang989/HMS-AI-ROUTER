#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
POLICY_VERSION = "25.33"
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization",
    "bearer", "api_key", "apikey", "client_secret", "password",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


def ek(value: Any) -> str:
    return str(value or "").strip().lower()


def num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def intval(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def read_history(path: Path, max_lines: int = 4000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    # Quota history is intentionally append-only JSONL. Tail semantics keep runtime bounded.
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return []
    for line in lines:
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def _contains_secret_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS or kl.endswith(("_access_token", "_refresh_token", "_client_secret", "_api_key")):
                return True
            if _contains_secret_like(v):
                return True
    elif isinstance(obj, list):
        return any(_contains_secret_like(v) for v in obj)
    return False


def fleet_accounts(fleet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in list(fleet.get("accounts") or []):
        email = ek(row.get("email"))
        if email:
            out[email] = row
    return out


def collect_points(history: list[dict[str, Any]], email: str, field: str,
                   lookback_hours: float, reset_jump_pct: float) -> list[tuple[datetime, float]]:
    now = utcnow()
    points: list[tuple[datetime, float]] = []
    for snap in history:
        ts = parse_time(snap.get("time") or snap.get("time_utc"))
        if not ts or (now - ts).total_seconds() > lookback_hours * 3600:
            continue
        for row in list(snap.get("accounts") or []):
            if ek(row.get("email")) != email:
                continue
            val = num(row.get(field))
            if val is not None:
                points.append((ts, clamp(val)))
            break
    points.sort(key=lambda x: x[0])
    if len(points) < 2:
        return points

    # A material increase in remaining quota means a reset/replenishment boundary.
    # Forecast only the newest quota epoch so resets cannot create a negative burn rate.
    epoch_start = 0
    for idx in range(1, len(points)):
        if points[idx][1] - points[idx - 1][1] >= reset_jump_pct:
            epoch_start = idx
    return points[epoch_start:]


def robust_burn(points: list[tuple[datetime, float]], min_span_minutes: float) -> dict[str, Any]:
    if not points:
        return {"points": 0, "span_minutes": 0.0, "burn_pct_per_hour": None, "confidence": "NONE"}
    if len(points) == 1:
        return {"points": 1, "span_minutes": 0.0, "burn_pct_per_hour": None, "confidence": "LOW"}

    span_h = max(0.0, (points[-1][0] - points[0][0]).total_seconds() / 3600.0)
    rates: list[float] = []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        hours = (t1 - t0).total_seconds() / 3600.0
        if hours <= 0.0:
            continue
        consumed = v0 - v1
        # Ignore replenishment/noise as consumption. A tiny negative drift is not a reset signal.
        if consumed > 0.0:
            rates.append(consumed / hours)
    total_burn = max(0.0, points[0][1] - points[-1][1]) / span_h if span_h > 0 else 0.0
    if rates:
        med = statistics.median(rates)
        # Cap outliers relative to the median before averaging recent deltas.
        cap = max(1.0, med * 4.0)
        clipped = [min(x, cap) for x in rates]
        recent = clipped[-min(8, len(clipped)):]
        recent_avg = sum(recent) / len(recent)
        burn = med * 0.55 + recent_avg * 0.30 + total_burn * 0.15
    else:
        burn = 0.0

    span_minutes = span_h * 60.0
    if len(points) >= 6 and span_minutes >= min_span_minutes * 3:
        conf = "HIGH"
    elif len(points) >= 3 and span_minutes >= min_span_minutes:
        conf = "MEDIUM"
    else:
        conf = "LOW"
    return {
        "points": len(points),
        "span_minutes": round(span_minutes, 1),
        "burn_pct_per_hour": round(max(0.0, burn), 4),
        "confidence": conf,
    }


def window_forecast(name: str, remaining: float | None, reset_value: Any,
                    history: list[dict[str, Any]], email: str, history_field: str,
                    cfg: dict[str, Any], lookback_hours: float) -> dict[str, Any]:
    reset_jump = float(cfg.get("reset_jump_pct", 8.0))
    min_span = float(cfg.get("min_span_minutes", 20.0))
    points = collect_points(history, email, history_field, lookback_hours, reset_jump)
    burn = robust_burn(points, min_span)
    now = utcnow()
    reset_dt = parse_time(reset_value)
    reset_hours = None
    if reset_dt:
        reset_hours = max(0.0, (reset_dt - now).total_seconds() / 3600.0)

    eta = None
    projected_at_reset = None
    exhaust_before_reset = False
    rate = num(burn.get("burn_pct_per_hour"))
    if remaining is not None and rate is not None and rate > 1e-6:
        eta = max(0.0, remaining / rate)
        if reset_hours is not None:
            projected_at_reset = max(0.0, remaining - rate * reset_hours)
            guard_h = max(0.0, float(cfg.get("reset_guard_minutes", 10.0)) / 60.0)
            exhaust_before_reset = eta + guard_h < reset_hours
    elif remaining is not None and reset_hours is not None:
        projected_at_reset = remaining

    return {
        "window": name,
        "remaining_pct": None if remaining is None else round(remaining, 2),
        "reset_utc": iso(reset_dt) if reset_dt else None,
        "reset_in_hours": None if reset_hours is None else round(reset_hours, 2),
        "points": burn["points"],
        "history_span_minutes": burn["span_minutes"],
        "burn_pct_per_hour": burn["burn_pct_per_hour"],
        "eta_zero_hours": None if eta is None else round(eta, 2),
        "projected_at_reset_pct": None if projected_at_reset is None else round(projected_at_reset, 2),
        "exhaust_before_reset": bool(exhaust_before_reset),
        "confidence": burn["confidence"],
    }


def risk_for_window(row: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, float, list[str]]:
    remaining = num(row.get("remaining_pct"))
    eta = num(row.get("eta_zero_hours"))
    projected = num(row.get("projected_at_reset_pct"))
    emergency = float(cfg.get("emergency_pct", 3.0))
    trigger = float(cfg.get("reserve_trigger_pct", 15.0))
    proactive_h = float(cfg.get("proactive_runway_minutes", 90.0)) / 60.0
    warning_h = float(cfg.get("warning_runway_minutes", 240.0)) / 60.0
    reasons: list[str] = []
    risk = "LOW"
    penalty = 0.0

    if remaining is None:
        return "UNKNOWN", 4.0, ["QUOTA_UNKNOWN"]
    if remaining <= emergency:
        risk, penalty = "EMERGENCY", 40.0
        reasons.append("REMAINING_EMERGENCY")
    elif row.get("exhaust_before_reset") and eta is not None and eta <= proactive_h:
        risk, penalty = "EMERGENCY", 36.0
        reasons.append("EXHAUST_SOON_BEFORE_RESET")
    elif remaining <= trigger or row.get("exhaust_before_reset"):
        risk, penalty = "HIGH", 25.0
        reasons.append("FORECAST_HIGH_PRESSURE")
    elif eta is not None and eta <= warning_h:
        risk, penalty = "MEDIUM", 14.0
        reasons.append("LOW_RUNWAY")
    elif projected is not None and projected <= trigger:
        risk, penalty = "MEDIUM", 12.0
        reasons.append("PROJECTED_LOW_AT_RESET")

    conf = str(row.get("confidence") or "NONE").upper()
    # Keep current hard quota authoritative. Forecast-only penalties are confidence weighted.
    if risk in {"HIGH", "MEDIUM"} and remaining > trigger:
        factor = {"HIGH": 1.0, "MEDIUM": 0.65, "LOW": 0.35, "NONE": 0.2}.get(conf, 0.35)
        penalty *= factor
    return risk, penalty, reasons


def evaluate(fleet: dict[str, Any], history: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    risk_rank = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "EMERGENCY": 4}
    for email, account in sorted(fleet_accounts(fleet).items()):
        quota = account.get("quota") or {}
        h_remaining = num(quota.get("five_hour_remaining"))
        w_remaining = num(quota.get("weekly_remaining"))
        hourly = window_forecast(
            "5h", h_remaining, quota.get("five_hour_reset"), history, email, "hourly", cfg,
            float(cfg.get("hourly_lookback_hours", 8.0)),
        )
        weekly = window_forecast(
            "7d", w_remaining, quota.get("weekly_reset"), history, email, "weekly", cfg,
            float(cfg.get("weekly_lookback_hours", 72.0)),
        )
        hrisk, hpen, hreasons = risk_for_window(hourly, cfg)
        wrisk, wpen, wreasons = risk_for_window(weekly, cfg)
        risk = hrisk if risk_rank.get(hrisk, 0) >= risk_rank.get(wrisk, 0) else wrisk
        penalty = max(hpen, wpen)
        max_penalty = float(cfg.get("max_score_penalty", 42.0))
        penalty = min(max_penalty, penalty)
        if risk == "EMERGENCY":
            load_factor = 0.10
            action = "DRAIN_NEW_SESSIONS"
        elif risk == "HIGH":
            load_factor = 0.30
            action = "REDUCE_NEW_SESSION_LOAD"
        elif risk == "MEDIUM":
            load_factor = 0.60
            action = "SOFT_REBALANCE"
        elif risk == "UNKNOWN":
            load_factor = 0.80
            action = "KEEP_WITH_UNCERTAINTY"
        else:
            load_factor = 1.0
            action = "NORMAL"
        min_factor = clamp(float(cfg.get("min_load_factor_pct", 10.0)), 1.0, 100.0) / 100.0
        load_factor = max(min_factor, load_factor)
        critical = risk == "EMERGENCY"
        rows.append({
            "account": account.get("email") or email,
            "status": str(account.get("status") or ""),
            "risk": risk,
            "critical": critical,
            "score_penalty": round(penalty, 1),
            "new_session_load_factor": round(load_factor, 2),
            "action": action,
            "reason_codes": hreasons + wreasons,
            "five_hour": hourly,
            "weekly": weekly,
        })

    rows.sort(key=lambda x: (-risk_rank.get(x.get("risk"), 0), -float(x.get("score_penalty") or 0), ek(x.get("account"))))
    summary = {
        "accounts": len(rows),
        "emergency": sum(1 for r in rows if r["risk"] == "EMERGENCY"),
        "high": sum(1 for r in rows if r["risk"] == "HIGH"),
        "medium": sum(1 for r in rows if r["risk"] == "MEDIUM"),
        "unknown": sum(1 for r in rows if r["risk"] == "UNKNOWN"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_utc": iso(),
        "enabled": bool(cfg.get("enabled", True)),
        "summary": summary,
        "accounts": rows,
        "safety": {
            "forecast_is_not_reported_as_actual_quota": True,
            "stable_endpoint_untouched": True,
            "session_affinity_untouched": True,
            "project_binding_untouched": True,
            "oauth_tokens_untouched": True,
            "credentials_untouched": True,
            "destructive_delete": False,
            "effect": "advisory_signal_for_closed_loop_new_session_routing",
        },
        "note": "Predictive Quota v25.33 forecasts remaining-percent velocity inside the newest quota epoch. It never replaces the live quota reading; Closed-loop may only use its risk/penalty/load-factor for NEW session routing.",
    }


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if str(plan.get("policy_version") or "") != POLICY_VERSION:
        errors.append("policy_version mismatch")
    safety = plan.get("safety") or {}
    for key in (
        "forecast_is_not_reported_as_actual_quota", "stable_endpoint_untouched",
        "session_affinity_untouched", "project_binding_untouched", "oauth_tokens_untouched",
        "credentials_untouched",
    ):
        if safety.get(key) is not True:
            errors.append(f"safety invariant false: {key}")
    if _contains_secret_like(plan):
        errors.append("secret-like field present in plan")
    for row in list(plan.get("accounts") or []):
        if row.get("risk") not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "EMERGENCY"}:
            errors.append(f"invalid risk: {row.get('account')}")
        lf = num(row.get("new_session_load_factor"))
        if lf is None or not (0.0 < lf <= 1.0):
            errors.append(f"invalid load factor: {row.get('account')}")
    return {"ok": not errors, "errors": errors, "accounts": len(plan.get("accounts") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "evaluate", "validate"), required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--history")
    ap.add_argument("--state", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--config-json")
    args = ap.parse_args()
    state_path = Path(args.state)
    plan_path = Path(args.plan)
    cfg = json.loads(args.config_json) if args.config_json else {}
    try:
        if args.mode == "status":
            data = {"state": read_json(state_path, {}) or {}, "plan": read_json(plan_path, {}) or {}}
        elif args.mode == "validate":
            plan = read_json(plan_path, {}) or {}
            val = validate_plan(plan)
            if not val["ok"]:
                raise RuntimeError("PLAN_VALIDATION_FAILED:" + ",".join(val["errors"]))
            data = {"validation": val, "plan": plan}
        else:
            if not args.fleet:
                raise ValueError("--fleet required")
            fleet = read_json(Path(args.fleet), {}) or {}
            history = read_history(Path(args.history)) if args.history else []
            plan = evaluate(fleet, history, cfg)
            val = validate_plan(plan)
            if not val["ok"]:
                raise RuntimeError("PLAN_VALIDATION_FAILED:" + ",".join(val["errors"]))
            atomic_json(plan_path, plan)
            state = {
                "schema_version": SCHEMA_VERSION,
                "policy_version": POLICY_VERSION,
                "updated_utc": iso(),
                "last_plan_summary": plan.get("summary") or {},
                "history_points_consumed": len(history),
                "last_plan": plan,
            }
            atomic_json(state_path, state)
            data = {"plan": plan, "validation": val, "state": state}
        out = {"ok": True, "data": data}
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
