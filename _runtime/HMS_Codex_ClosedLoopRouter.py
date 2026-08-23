#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
POLICY_VERSION = "25.51"
SECRET_KEYS = {"token", "access_token", "refresh_token", "cookie", "authorization", "bearer", "api_key", "apikey", "client_secret", "password"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def atomic_json(path: Path, obj: Any) -> None:
    atomic_bytes(path, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def i(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def ek(value: Any) -> str:
    return str(value or "").strip().lower()


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


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def quota_floor(account: dict[str, Any]) -> float | None:
    q = account.get("quota") or {}
    vals: list[float] = []
    for key in ("five_hour_remaining", "weekly_remaining"):
        value = q.get(key)
        if value is None or value == "":
            continue
        try:
            vals.append(float(value))
        except Exception:
            pass
    return min(vals) if vals else None


def by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        key = ek(row.get("name"))
        if key and key != "—":
            out[key] = row
    return out


def confidence(samples: int, target: int = 20) -> float:
    return clamp(samples / max(1.0, float(target)), 0.0, 1.0)


def reliability_score(row: dict[str, Any] | None) -> tuple[float, int]:
    if not row:
        return 50.0, 0
    req = max(0, i(row.get("requests")))
    if not req:
        return 50.0, 0
    ok = clamp(f(row.get("success_rate_pct"), 0.0))
    retries = clamp(f(row.get("retry_rate_pct"), 0.0))
    throttles = max(0, i(row.get("http_429")))
    auth_errors = max(0, i(row.get("http_401_403")))
    server_errors = max(0, i(row.get("server_errors")))
    penalty = min(30.0, retries * 0.18 + throttles * 1.8 + auth_errors * 4.0 + server_errors * 1.0)
    raw = clamp(ok - penalty)
    c = confidence(req)
    return 50.0 + (raw - 50.0) * c, req


def latency_score(row: dict[str, Any] | None) -> float:
    if not row:
        return 50.0
    p95 = f(row.get("latency_p95_ms"), 0.0)
    if p95 <= 0:
        return 50.0
    # 2s p95 ~= 95; 8s ~= 65; 20s+ ~= 5. This is intentionally conservative.
    return clamp(105.0 - p95 / 200.0, 5.0, 100.0)


def safe_account_center(accounts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for a in accounts or []:
        email = ek(a.get("email"))
        if not email:
            continue
        out[email] = a
    return out


def score_account(account: dict[str, Any], role: str, week: dict[str, Any] | None,
                  day: dict[str, Any] | None, hour: dict[str, Any] | None,
                  cfg: dict[str, Any], breaker: dict[str, Any] | None = None,
                  predictive: dict[str, Any] | None = None, analytics: dict[str, Any] | None = None, smart_model: dict[str, Any] | None = None) -> dict[str, Any]:
    status = str(account.get("status") or "").upper()
    health = clamp(f(account.get("health_score"), f(account.get("pool_score"), 50.0)))
    pool = clamp(f(account.get("pool_score"), health))
    q = quota_floor(account)
    quota_score = 55.0 if q is None else clamp(q)
    qmeta = account.get("quota") or {}
    live_quota_flag = qmeta.get("routing_eligible")
    live_quota_freshness = str(qmeta.get("freshness_state") or "UNKNOWN").upper()
    live_quota_reasons = [str(x) for x in list(qmeta.get("reason_codes") or []) if str(x)]

    r7, n7 = reliability_score(week)
    r1d, n1d = reliability_score(day)
    r1h, n1h = reliability_score(hour)
    # Recent outcomes matter more once they exist; otherwise historical data stays authoritative.
    rel = r7 * 0.45 + r1d * 0.35 + r1h * 0.20
    lat = latency_score(day or week)

    score = pool * 0.18 + health * 0.17 + quota_score * 0.25 + rel * 0.30 + lat * 0.10
    if role == "PRIMARY":
        score += 2.0
    if bool(account.get("favorite")):
        score += 1.0

    reasons: list[str] = []
    eligible = status == "READY"
    critical = not eligible
    if not eligible:
        reasons.append("STATUS_" + (status or "UNKNOWN"))

    # v25.50 Live Quota Intelligence is authoritative for NEW-session eligibility.
    # Existing session affinity is handled outside this scoring path and remains untouched.
    if live_quota_flag is not None:
        if not bool(live_quota_flag):
            eligible = False
            critical = True
            score -= 50.0
            reasons.extend([x for x in live_quota_reasons if x not in reasons])
            if not live_quota_reasons:
                reasons.append("LIVE_QUOTA_FAIL_CLOSED")
    elif bool(cfg.get("live_quota_fail_closed", True)) and live_quota_freshness in ("UNKNOWN", "STALE"):
        eligible = False
        critical = True
        score -= 50.0
        reasons.append("QUOTA_" + live_quota_freshness)

    breaker = breaker or {}
    breaker_state = str(breaker.get("desired_state") or breaker.get("state") or "CLOSED").upper()
    breaker_reason = str(breaker.get("transition_reason") or breaker.get("reason") or "")
    probe_only = False
    if breaker_state == "OPEN":
        eligible = False
        critical = True
        score -= 60.0
        reasons.append("CIRCUIT_OPEN")
        if breaker_reason:
            reasons.append("CIRCUIT_" + breaker_reason.split(":", 1)[0].upper())
    elif breaker_state == "HALF_OPEN":
        probe_only = True
        score = min(score, 25.0)
        reasons.append("CIRCUIT_HALF_OPEN_PROBE")

    floor_pct = f(cfg.get("quota_floor_pct"), 10.0)
    emergency_pct = f(cfg.get("emergency_quota_pct"), 3.0)
    if q is not None:
        if q <= 0:
            eligible = False
            critical = True
            reasons.append("QUOTA_EMPTY")
        elif q <= emergency_pct:
            critical = True
            score -= 28.0
            reasons.append("QUOTA_EMERGENCY")
        elif q < floor_pct:
            score -= min(24.0, (floor_pct - q) * 1.4)
            reasons.append("QUOTA_BELOW_FLOOR")

    recent_429 = i((hour or {}).get("http_429"), 0)
    recent_auth = i((day or {}).get("http_401_403"), 0)
    if recent_429:
        score -= min(20.0, recent_429 * 4.0)
        reasons.append("RECENT_429")
    if recent_auth:
        score -= min(30.0, recent_auth * 8.0)
        reasons.append("RECENT_AUTH_ERROR")

    predictive = predictive or {}
    predictive_risk = str(predictive.get("risk") or "UNKNOWN").upper()
    predictive_penalty = clamp(f(predictive.get("score_penalty"), 0.0), 0.0, 60.0)
    predictive_load_factor = clamp(f(predictive.get("new_session_load_factor"), 1.0), 0.05, 1.0)
    score -= predictive_penalty
    if predictive_risk == "EMERGENCY":
        critical = True
        reasons.append("PREDICTIVE_QUOTA_EMERGENCY")
    elif predictive_risk == "HIGH":
        reasons.append("PREDICTIVE_QUOTA_HIGH")
    elif predictive_risk == "MEDIUM":
        reasons.append("PREDICTIVE_QUOTA_MEDIUM")

    analytics = analytics or {}
    analytics_score = clamp(f(analytics.get("quality_score"), 50.0))
    analytics_confidence = str(analytics.get("confidence") or "NONE").upper()
    analytics_factor = {"VERY_HIGH": 0.16, "HIGH": 0.14, "MEDIUM": 0.10, "LOW": 0.05}.get(analytics_confidence, 0.0)
    analytics_adjustment = max(-8.0, min(8.0, (analytics_score - 50.0) * analytics_factor))
    score += analytics_adjustment
    if analytics_adjustment >= 2.0:
        reasons.append("ACCOUNT_ANALYTICS_POSITIVE")
    elif analytics_adjustment <= -2.0:
        reasons.append("ACCOUNT_ANALYTICS_NEGATIVE")

    # v25.44 Smart Model Router is a bounded NEW-session signal only.
    # Circuit/quota eligibility above remains authoritative.
    smart_model = smart_model or {}
    smart_model_adjustment = max(-8.0, min(8.0, f(smart_model.get("score_adjustment"), 0.0)))
    score += smart_model_adjustment
    if smart_model_adjustment >= 1.0:
        reasons.append("SMART_MODEL_ACCOUNT_AFFINITY")
    elif smart_model_adjustment <= -1.0:
        reasons.append("SMART_MODEL_ACCOUNT_AVOID")

    total_samples = max(n7, n1d, n1h)
    return {
        "account": str(account.get("email") or ""),
        "role": role,
        "status": status,
        "eligible": eligible,
        "critical": critical,
        "score": round(clamp(score), 1),
        "pool_score": round(pool, 1),
        "health_score": round(health, 1),
        "quota_floor_pct": q,
        "quota_freshness": live_quota_freshness,
        "live_quota_eligible": bool(live_quota_flag) if live_quota_flag is not None else None,
        "reliability_score": round(rel, 1),
        "latency_score": round(lat, 1),
        "samples_7d": n7,
        "samples_24h": n1d,
        "samples_1h": n1h,
        "sample_confidence": "HIGH" if total_samples >= 20 else ("MEDIUM" if total_samples >= 5 else ("LOW" if total_samples else "NONE")),
        "breaker_state": breaker_state,
        "breaker_reason": breaker_reason,
        "breaker_open_until_utc": breaker.get("open_until_utc"),
        "probe_only": probe_only,
        "predictive_risk": predictive_risk,
        "predictive_penalty": round(predictive_penalty, 1),
        "predictive_load_factor": round(predictive_load_factor, 2),
        "predictive_action": str(predictive.get("action") or ""),
        "analytics_score": round(analytics_score, 1),
        "analytics_confidence": analytics_confidence,
        "analytics_adjustment": round(analytics_adjustment, 2),
        "analytics_grade": str(analytics.get("grade") or ""),
        "smart_model_adjustment": round(smart_model_adjustment, 2),
        "smart_model": str(smart_model.get("model") or ""),
        "smart_model_role": str(smart_model.get("role") or ""),
        "predictive_five_hour": predictive.get("five_hour") or {},
        "predictive_weekly": predictive.get("weekly") or {},
        "reason_codes": reasons,
    }


def breaker_index(breaker: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(breaker, dict):
        return out
    payload = breaker.get("plan") if isinstance(breaker.get("plan"), dict) else breaker
    instances = payload.get("instances") or [] if isinstance(payload, dict) else []
    if isinstance(instances, dict):
        for iid, irow in instances.items():
            accounts = (irow or {}).get("accounts") or {}
            if isinstance(accounts, dict):
                for email, row in accounts.items():
                    if ek(email):
                        out[(str(iid), ek(email))] = dict(row or {})
    else:
        for inst in list(instances or []):
            iid = str(inst.get("instance_id") or inst.get("id") or "")
            for row in list(inst.get("accounts") or []):
                email = ek(row.get("account") or row.get("email"))
                if iid and email:
                    out[(iid, email)] = dict(row)
    return out


def predictive_index(predictive: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(predictive, dict):
        return out
    payload = predictive.get("plan") if isinstance(predictive.get("plan"), dict) else predictive
    for row in list((payload or {}).get("accounts") or []):
        email = ek(row.get("account") or row.get("email"))
        if email:
            out[email] = dict(row or {})
    return out


def analytics_index(analytics: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(analytics, dict):
        return out
    rows = analytics.get("accounts") or ((analytics.get("data") or {}).get("accounts") if isinstance(analytics.get("data"), dict) else []) or []
    for row in list(rows):
        if not isinstance(row, dict):
            continue
        email = ek(row.get("account") or row.get("email"))
        if email:
            out[email] = dict(row)
    return out


def smart_model_index(payload: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return out
    plan = payload.get("last_plan") if isinstance(payload.get("last_plan"), dict) else payload.get("plan") if isinstance(payload.get("plan"), dict) else payload
    for rec in list((plan or {}).get("recommendations") or []):
        if not isinstance(rec, dict):
            continue
        iid = str(rec.get("instance_id") or "")
        for row in list(rec.get("account_adjustments") or []):
            email = ek(row.get("account") or row.get("email"))
            if iid and email:
                out[(iid, email)] = dict(row)
    return out


def evaluate(fleet: dict[str, Any], usage: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any], breaker: dict[str, Any] | None = None, predictive: dict[str, Any] | None = None, analytics: dict[str, Any] | None = None, smart_model: dict[str, Any] | None = None) -> dict[str, Any]:
    account_map = safe_account_center(list(fleet.get("accounts") or []))
    week_map = by_name(list(usage.get("by_account_week") or []))
    day_map = by_name(list(usage.get("by_account_day") or []))
    hour_map = by_name(list(usage.get("by_account_hour") or []))
    prior_instances = (state.get("instances") or {}) if isinstance(state, dict) else {}
    breaker_rows = breaker_index(breaker)
    predictive_rows = predictive_index(predictive)
    analytics_rows = analytics_index(analytics)
    smart_model_rows = smart_model_index(smart_model)
    now = utcnow()
    plans: list[dict[str, Any]] = []

    for inst in list(fleet.get("instances") or []):
        iid = str(inst.get("id") or "").strip()
        manifest = inst.get("manifest") or {}
        if not iid or not isinstance(manifest, dict):
            continue
        pool_rows = list(manifest.get("accounts") or [])
        scored: list[dict[str, Any]] = []
        for idx, pool_row in enumerate(pool_rows):
            email = ek(pool_row.get("email"))
            if not email:
                continue
            account = account_map.get(email) or {"email": pool_row.get("email"), "status": "MISSING", "health_score": 0, "pool_score": 0, "quota": {}}
            role = "PRIMARY" if idx == 0 else "FALLBACK"
            row = score_account(account, role, week_map.get(email), day_map.get(email), hour_map.get(email), cfg, breaker_rows.get((iid, email)), predictive_rows.get(email), analytics_rows.get(email), smart_model_rows.get((iid, email)))
            row["slot"] = idx
            row["file"] = str(pool_row.get("file") or "")
            scored.append(row)

        scored.sort(key=lambda x: (not x["eligible"], -x["score"], -x["samples_7d"], x["slot"], ek(x["account"])))
        eligible = [x for x in scored if x["eligible"]]
        best = eligible[0] if eligible else None
        prior = prior_instances.get(iid) or {}
        primary = next((x for x in scored if x["slot"] == 0), None)
        current_email = ek(prior.get("preferred_account")) or ek(primary.get("account") if primary else "")
        # v25.51: preserve the actual preferred/current account even when it is no longer
        # eligible for NEW sessions. Otherwise the planner can silently treat the fallback
        # candidate as already-current and suppress the required rotation.
        current = next((x for x in scored if ek(x["account"]) == current_email), None)
        if current is None:
            current = primary or (eligible[0] if eligible else (scored[0] if scored else None))
            current_email = ek(current.get("account") if current else "")
        candidate = best
        switch_needed = bool(candidate and current and ek(candidate["account"]) != ek(current["account"]))
        delta = round((candidate["score"] - current["score"]), 1) if candidate and current else 0.0
        current_critical = bool(current and current.get("critical"))
        reasons: list[str] = []
        can_switch = switch_needed

        min_delta = f(cfg.get("min_score_delta"), 8.0)
        min_samples = i(cfg.get("min_samples"), 5)
        hold_minutes = i(cfg.get("hold_minutes"), 20)
        cooldown_sec = i(cfg.get("cooldown_sec"), 120)
        last_applied = parse_time(prior.get("last_applied_utc"))
        hold_until = last_applied + timedelta(minutes=hold_minutes) if last_applied else None
        cooldown_until = last_applied + timedelta(seconds=cooldown_sec) if last_applied else None

        if not candidate:
            can_switch = False
            reasons.append("NO_ELIGIBLE_ACCOUNT")
        if switch_needed and delta < min_delta and not current_critical:
            can_switch = False
            reasons.append("HYSTERESIS_SCORE_DELTA")
        candidate_samples = i(candidate.get("samples_7d"), 0) if candidate else 0
        if switch_needed and candidate_samples < min_samples and not current_critical:
            can_switch = False
            reasons.append("MIN_SAMPLES")
        if hold_until and now < hold_until and not current_critical:
            can_switch = False
            reasons.append("MIN_HOLD")
        if cooldown_until and now < cooldown_until and not current_critical:
            can_switch = False
            reasons.append("SWITCH_COOLDOWN")
        if not switch_needed and candidate:
            reasons.append("KEEP_CURRENT")
        if current_critical and switch_needed:
            reasons.append("CURRENT_CRITICAL_OVERRIDE")

        # Hints affect only NEW routing decisions. Router session affinity remains the owner of existing sessions.
        hints: list[dict[str, Any]] = []
        for rank, row in enumerate(eligible):
            if row.get("probe_only"):
                priority, weight = max(1, i(cfg.get("half_open_probe_priority"), 5)), 1
            elif rank == 0:
                priority, weight = 100, max(1, i(cfg.get("preferred_weight"), 8))
            elif rank == 1:
                priority, weight = 65, max(1, i(cfg.get("secondary_weight"), 3))
            else:
                priority, weight = 35, max(1, i(cfg.get("tail_weight"), 1))
            load_factor = clamp(f(row.get("predictive_load_factor"), 1.0), 0.05, 1.0)
            weight = max(1, int(round(weight * load_factor)))
            hints.append({"account": row["account"], "file": row["file"], "rank": rank + 1, "priority": priority, "weight": weight, "probe_only": bool(row.get("probe_only")), "predictive_load_factor": round(load_factor, 2), "predictive_risk": row.get("predictive_risk")})

        mode = str(cfg.get("mode") or "OBSERVE").upper()
        enabled = bool(cfg.get("enabled", True))
        apply_allowed = bool(enabled and mode == "GUARDED_AUTO" and (can_switch or (candidate and not switch_needed)))
        plans.append({
            "instance_id": iid,
            "instance_name": str(inst.get("name") or iid),
            "project": str(inst.get("project") or ""),
            "router_dir": str(inst.get("router_dir") or ""),
            "manifest_path": str(inst.get("manifest_path") or ""),
            "stable_endpoint": str(manifest.get("stable_endpoint") or ""),
            "pool_count": len(pool_rows),
            "current_account": current.get("account") if current else "",
            "recommended_account": candidate.get("account") if candidate else "",
            "current_score": current.get("score") if current else 0.0,
            "recommended_score": candidate.get("score") if candidate else 0.0,
            "score_delta": delta,
            "switch_needed": switch_needed,
            "can_switch": can_switch,
            "current_critical": current_critical,
            "apply_allowed": apply_allowed,
            "reason_codes": reasons,
            "hold_until_utc": iso(hold_until) if hold_until else None,
            "cooldown_until_utc": iso(cooldown_until) if cooldown_until else None,
            "ranking": scored,
            "routing_hints": hints,
        })

    plans.sort(key=lambda p: (not p.get("switch_needed"), -f(p.get("score_delta")), p.get("instance_name", "").lower()))
    switchable = sum(1 for p in plans if p.get("can_switch"))
    critical = sum(1 for p in plans if p.get("current_critical"))
    mode = str(cfg.get("mode") or "OBSERVE").upper()
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_utc": iso(),
        "enabled": bool(cfg.get("enabled", True)),
        "mode": mode,
        "summary": {"instances": len(plans), "switchable": switchable, "critical": critical},
        "instances": plans,
        "safety": {
            "stable_endpoint_untouched": True,
            "session_affinity_untouched": True,
            "project_binding_untouched": True,
            "oauth_tokens_untouched": True,
            "request_body_consumed": False,
            "destructive_delete": False,
            "apply_scope": "priority_weight_only_in_instance_auth",
            "circuit_breaker_consumed": True,
            "predictive_quota_consumed": True,
            "account_analytics_consumed": True,
            "ineligible_current_rotates_new_sessions": True,
        },
        "feedback": {
            "usage_windows": ["1h", "24h", "7d"],
            "signals": ["success_rate", "latency_p95", "retry_rate", "http_429", "auth_errors", "quota", "health", "pool_score", "circuit_state", "predictive_quota_risk", "quota_velocity", "runway", "account_analytics_quality", "analytics_confidence", "smart_model_account_affinity"],
        },
        "note": "Closed-loop v25.44 consumes Circuit Breaker + Predictive Quota + bounded Account Analytics + Smart Model Router account-affinity signals. OPEN is excluded, HALF_OPEN is probe-priority only; sticky sessions remain owned by Seamless Router session affinity.",
    }


def _safe_auth_file(router_dir: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise RuntimeError("UNSAFE_AUTH_FILENAME")
    auth_dir = (router_dir / "auth").resolve()
    path = (auth_dir / filename).resolve()
    if path.parent != auth_dir:
        raise RuntimeError("AUTH_PATH_ESCAPE")
    if path.is_symlink():
        raise RuntimeError("AUTH_SYMLINK_REJECTED")
    if not path.exists():
        raise RuntimeError(f"AUTH_FILE_MISSING:{filename}")
    return path


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


def apply_plan(plan: dict[str, Any], state_path: Path) -> dict[str, Any]:
    if str(plan.get("mode") or "").upper() != "GUARDED_AUTO":
        return {"applied": False, "reason": "GUARDED_AUTO_REQUIRED"}
    originals: list[tuple[Path, bytes]] = []
    manifest_originals: list[tuple[Path, bytes]] = []
    snapshots: dict[str, Any] = {}
    changed: list[dict[str, Any]] = []
    try:
        for inst in list(plan.get("instances") or []):
            if not inst.get("apply_allowed"):
                continue
            iid = str(inst.get("instance_id") or "")
            router_dir = Path(str(inst.get("router_dir") or ""))
            manifest_path = Path(str(inst.get("manifest_path") or ""))
            manifest = read_json(manifest_path, None)
            if not isinstance(manifest, dict):
                raise RuntimeError(f"MANIFEST_INVALID:{iid}")
            if str(manifest.get("stable_endpoint") or "") != str(inst.get("stable_endpoint") or ""):
                raise RuntimeError(f"STABLE_ENDPOINT_DRIFT:{iid}")
            m_accounts = {ek(x.get("email")): x for x in list(manifest.get("accounts") or [])}
            old_manifest = manifest_path.read_bytes()
            manifest_originals.append((manifest_path, old_manifest))
            inst_snapshot: dict[str, Any] = {"preferred_account": inst.get("current_account") or "", "values": {}}
            for hint in list(inst.get("routing_hints") or []):
                email = ek(hint.get("account"))
                mrow = m_accounts.get(email)
                if not mrow:
                    raise RuntimeError(f"HINT_ACCOUNT_NOT_IN_MANIFEST:{iid}:{email}")
                filename = str(mrow.get("file") or hint.get("file") or "")
                path = _safe_auth_file(router_dir, filename)
                raw = path.read_bytes()
                originals.append((path, raw))
                data = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(data, dict):
                    raise RuntimeError(f"AUTH_JSON_INVALID:{filename}")
                old_p = i(data.get("priority"), 0)
                old_w = max(1, i(data.get("weight"), 1))
                new_p = i(hint.get("priority"), 0)
                new_w = max(1, i(hint.get("weight"), 1))
                inst_snapshot["values"][email] = {"file": filename, "priority": old_p, "weight": old_w}
                if old_p != new_p or old_w != new_w:
                    data["priority"] = new_p
                    data["weight"] = new_w
                    new_raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
                    atomic_bytes(path, new_raw)
                    verify = read_json(path, {}) or {}
                    if i(verify.get("priority"), -999) != new_p or i(verify.get("weight"), -999) != new_w:
                        raise RuntimeError(f"AUTH_READBACK_FAIL:{filename}")
                    changed.append({"instance_id": iid, "account": hint.get("account"), "priority": new_p, "weight": new_w})
                mrow["sha256"] = sha256_file(path)
            manifest["version"] = POLICY_VERSION
            manifest["closed_loop_policy"] = {
                "policy_version": POLICY_VERSION,
                "preferred_account": inst.get("recommended_account") or inst.get("current_account") or "",
                "applied_utc": iso(),
                "session_affinity_untouched": True,
                "stable_endpoint_untouched": True,
            }
            manifest["updated_utc"] = iso()
            atomic_json(manifest_path, manifest)
            check = read_json(manifest_path, {}) or {}
            if str(check.get("stable_endpoint") or "") != str(inst.get("stable_endpoint") or ""):
                raise RuntimeError(f"MANIFEST_READBACK_FAIL:{iid}")
            snapshots[iid] = inst_snapshot

        old_state = read_json(state_path, {}) or {}
        old_instances = old_state.get("instances") or {}
        history = list(old_state.get("history") or [])[-99:]
        applied_utc = iso()
        for inst in list(plan.get("instances") or []):
            iid = str(inst.get("instance_id") or "")
            if not inst.get("apply_allowed"):
                continue
            prior = old_instances.get(iid) or {}
            old_instances[iid] = {
                "preferred_account": inst.get("recommended_account") or inst.get("current_account") or "",
                "previous_preferred_account": inst.get("current_account") or prior.get("preferred_account") or "",
                "last_applied_utc": applied_utc,
                "previous_values": snapshots.get(iid, {}).get("values", {}),
            }
            history.append({
                "time_utc": applied_utc,
                "instance_id": iid,
                "from_account": inst.get("current_account") or "",
                "to_account": inst.get("recommended_account") or "",
                "score_delta": inst.get("score_delta", 0),
            })
        new_state = {
            "schema_version": SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "updated_utc": applied_utc,
            "instances": old_instances,
            "history": history[-100:],
            "last_plan": plan,
        }
        atomic_json(state_path, new_state)
        return {"applied": True, "changed": changed, "instances_touched": len(snapshots), "session_affinity_untouched": True, "stable_endpoint_untouched": True}
    except Exception:
        # Transactional best-effort restore. No deletes.
        for path, raw in reversed(originals):
            try:
                atomic_bytes(path, raw)
            except Exception:
                pass
        for path, raw in reversed(manifest_originals):
            try:
                atomic_bytes(path, raw)
            except Exception:
                pass
        raise


def rollback(state_path: Path, fleet: dict[str, Any]) -> dict[str, Any]:
    state = read_json(state_path, {}) or {}
    instances_state = state.get("instances") or {}
    fleet_instances = {str(x.get("id") or ""): x for x in list(fleet.get("instances") or [])}
    restored: list[dict[str, Any]] = []
    originals: list[tuple[Path, bytes]] = []
    manifest_originals: list[tuple[Path, bytes]] = []
    try:
        for iid, srow in list(instances_state.items()):
            prev = srow.get("previous_values") or {}
            if not prev:
                continue
            inst = fleet_instances.get(iid)
            if not inst:
                continue
            router_dir = Path(str(inst.get("router_dir") or ""))
            manifest_path = Path(str(inst.get("manifest_path") or ""))
            manifest = read_json(manifest_path, None)
            if not isinstance(manifest, dict):
                raise RuntimeError(f"ROLLBACK_MANIFEST_INVALID:{iid}")
            manifest_originals.append((manifest_path, manifest_path.read_bytes()))
            m_accounts = {ek(x.get("email")): x for x in list(manifest.get("accounts") or [])}
            for email, old in prev.items():
                filename = str(old.get("file") or "")
                path = _safe_auth_file(router_dir, filename)
                raw = path.read_bytes(); originals.append((path, raw))
                data = json.loads(raw.decode("utf-8-sig"))
                p = i(old.get("priority"), 0); w = max(1, i(old.get("weight"), 1))
                data["priority"] = p; data["weight"] = w
                atomic_json(path, data)
                if ek(email) in m_accounts:
                    m_accounts[ek(email)]["sha256"] = sha256_file(path)
                restored.append({"instance_id": iid, "account": email, "priority": p, "weight": w})
            manifest["version"] = POLICY_VERSION
            manifest["closed_loop_policy"] = {
                "policy_version": POLICY_VERSION,
                "preferred_account": srow.get("previous_preferred_account") or "",
                "rollback_utc": iso(),
                "session_affinity_untouched": True,
                "stable_endpoint_untouched": True,
            }
            manifest["updated_utc"] = iso()
            atomic_json(manifest_path, manifest)
            srow["preferred_account"] = srow.get("previous_preferred_account") or srow.get("preferred_account") or ""
            srow["previous_values"] = {}
            srow["last_rollback_utc"] = iso()
        if not restored:
            raise RuntimeError("NO_CLOSED_LOOP_SNAPSHOT")
        state["instances"] = instances_state
        state["updated_utc"] = iso()
        atomic_json(state_path, state)
        return {"rolled_back": True, "restored": restored, "files_deleted": False}
    except Exception:
        for path, raw in reversed(originals):
            try: atomic_bytes(path, raw)
            except Exception: pass
        for path, raw in reversed(manifest_originals):
            try: atomic_bytes(path, raw)
            except Exception: pass
        raise


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if plan.get("policy_version") != POLICY_VERSION:
        errors.append("policy_version mismatch")
    safety = plan.get("safety") or {}
    for key in ("stable_endpoint_untouched", "session_affinity_untouched", "project_binding_untouched", "oauth_tokens_untouched"):
        if safety.get(key) is not True:
            errors.append(f"safety invariant false: {key}")
    if _contains_secret_like(plan):
        errors.append("secret-like field present in plan")
    for inst in list(plan.get("instances") or []):
        ranks = [i(x.get("rank")) for x in list(inst.get("routing_hints") or [])]
        if ranks and ranks != list(range(1, len(ranks) + 1)):
            errors.append(f"rank sequence invalid: {inst.get('instance_id')}")
        if not str(inst.get("stable_endpoint") or "").startswith("http://127.0.0.1:"):
            errors.append(f"non-local stable endpoint: {inst.get('instance_id')}")
    return {"ok": not errors, "errors": errors, "instances": len(plan.get("instances") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "evaluate", "apply", "rollback", "validate"), required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--usage")
    ap.add_argument("--breaker")
    ap.add_argument("--predictive")
    ap.add_argument("--analytics")
    ap.add_argument("--smart-model")
    ap.add_argument("--state", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--config-json")
    args = ap.parse_args()
    state_path = Path(args.state); plan_path = Path(args.plan)
    cfg = json.loads(args.config_json) if args.config_json else {}
    try:
        if args.mode == "status":
            data = {"state": read_json(state_path, {}) or {}, "plan": read_json(plan_path, {}) or {}}
        elif args.mode == "validate":
            data = {"validation": validate_plan(read_json(plan_path, {}) or {})}
            if not data["validation"]["ok"]:
                raise RuntimeError("PLAN_VALIDATION_FAILED:" + ",".join(data["validation"]["errors"]))
        else:
            if not args.fleet:
                raise ValueError("--fleet required")
            fleet = read_json(Path(args.fleet), {}) or {}
            if args.mode == "rollback":
                data = {"rollback": rollback(state_path, fleet), "plan": read_json(plan_path, {}) or {}}
            else:
                usage = read_json(Path(args.usage), {}) if args.usage else {}
                breaker = read_json(Path(args.breaker), {}) if args.breaker else {}
                predictive = read_json(Path(args.predictive), {}) if args.predictive else {}
                analytics = read_json(Path(args.analytics), {}) if args.analytics else {}
                smart_model = read_json(Path(args.smart_model), {}) if args.smart_model else {}
                state = read_json(state_path, {}) or {}
                plan = evaluate(fleet, usage or {}, state, cfg, breaker or {}, predictive or {}, analytics or {}, smart_model or {})
                validation = validate_plan(plan)
                if not validation["ok"]:
                    raise RuntimeError("PLAN_VALIDATION_FAILED:" + ",".join(validation["errors"]))
                atomic_json(plan_path, plan)
                if args.mode == "apply":
                    data = {"plan": plan, "validation": validation, "apply": apply_plan(plan, state_path)}
                else:
                    data = {"plan": plan, "validation": validation}
        out = {"ok": True, "data": data}
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
