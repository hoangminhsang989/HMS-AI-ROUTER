#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "25.61"
SCHEMA_VERSION = 1
PRODUCTION_CLAIM = "NOT_CLAIMED_USAGE_TOKEN_CENTER_SYNTHETIC_ONLY"
SCENARIO_KIND = "HYPOTHETICAL_POST_RESET_SCENARIO"
SENSITIVE_KEYS = {
    "token", "access_token", "refresh_token", "id_token", "api_key", "apikey",
    "authorization", "cookie", "password", "secret", "client_secret", "auth_json",
    "prompt", "request", "response", "request_body", "response_body", "payload",
}
PLAN_ALIASES = {
    "FREE": "FREE", "BASIC": "FREE", "CHATGPT FREE": "FREE",
    "PLUS": "PLUS", "PERSONAL": "PLUS", "CHATGPT PLUS": "PLUS",
    "PRO": "PRO", "CHATGPT PRO": "PRO",
    "TEAM": "TEAM_BUSINESS", "BUSINESS": "TEAM_BUSINESS", "TEAM/BUSINESS": "TEAM_BUSINESS",
    "CHATGPT TEAM": "TEAM_BUSINESS", "CHATGPT BUSINESS": "TEAM_BUSINESS",
    "ENTERPRISE": "ENTERPRISE", "CHATGPT ENTERPRISE": "ENTERPRISE",
}
PLAN_ORDER = {"ENTERPRISE": 5, "TEAM_BUSINESS": 4, "PRO": 3, "PLUS": 2, "FREE": 1, "UNKNOWN": 0}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def finite_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def clamp_pct(value: Any) -> float | None:
    n = finite_num(value)
    if n is None:
        return None
    return round(max(0.0, min(100.0, n)), 2)


def plan_class(value: Any) -> str:
    raw = str(value or "").strip().upper()
    return PLAN_ALIASES.get(raw, "UNKNOWN")


def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8", "surrogatepass")
    return hashlib.sha256(value).hexdigest()


def contains_secret_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SENSITIVE_KEYS or kl.endswith(("_token", "_secret", "_password", "_api_key")):
                return True
            if contains_secret_like(v):
                return True
    elif isinstance(obj, list):
        return any(contains_secret_like(x) for x in obj)
    return False


def safe_identity_hash(value: Any) -> str:
    s = str(value or "").strip().lower()
    return "acct-" + sha256(s)[:16] if s else "acct-unknown"


def freshness_state(quota: dict[str, Any], now: datetime, fresh_seconds: int = 600, stale_seconds: int = 1200) -> tuple[str, float | None, str | None]:
    last = quota.get("last_success_utc") or quota.get("lastSuccessUtc") or quota.get("refreshed_utc") or quota.get("refreshedUtc")
    dt = parse_time(last)
    if not dt:
        return "UNKNOWN", None, None
    age = max(0.0, (now - dt).total_seconds())
    if age <= max(30, int(fresh_seconds)):
        st = "FRESH"
    elif age <= max(int(fresh_seconds), int(stale_seconds)):
        st = "AGING"
    else:
        st = "STALE"
    return st, round(age, 1), iso(dt)


def countdown(reset: datetime | None, now: datetime) -> dict[str, Any]:
    if reset is None:
        return {
            "reset_utc": None, "seconds_remaining": None, "countdown_text": "—",
            "absolute_utc_text": "—", "state": "UNKNOWN",
        }
    sec = (reset - now).total_seconds()
    absolute = reset.strftime("%Y-%m-%d %H:%M UTC")
    if sec <= 0:
        return {
            "reset_utc": iso(reset), "seconds_remaining": round(sec, 1),
            "countdown_text": "đã tới hạn", "absolute_utc_text": absolute, "state": "DUE",
        }
    mins = int(sec // 60)
    if mins < 60:
        txt = f"{mins}m"
    elif mins < 1440:
        txt = f"{mins // 60}h {mins % 60}m"
    else:
        days = mins // 1440
        rem = mins % 1440
        txt = f"{days}d {rem // 60}h"
    return {
        "reset_utc": iso(reset), "seconds_remaining": round(sec, 1),
        "countdown_text": txt, "absolute_utc_text": absolute, "state": "UPCOMING",
    }


def _window(*, kind: str, name: str, label: str, remaining: Any, reset: Any, minutes: Any,
            present: Any, source: str, freshness: str, now: datetime) -> dict[str, Any]:
    rem = clamp_pct(remaining)
    dt = parse_time(reset)
    cd = countdown(dt, now)
    nmin = finite_num(minutes)
    is_present = bool(present) if present is not None else (rem is not None or dt is not None)
    return {
        "kind": kind, "name": name, "label": label, "present": is_present,
        "remaining_pct": rem, "window_minutes": int(nmin) if nmin is not None and nmin >= 0 else None,
        "source": source or "UNKNOWN", "freshness_state": freshness, **cd,
    }


def primary_windows(quota: dict[str, Any], source: str, freshness: str, now: datetime) -> list[dict[str, Any]]:
    return [
        _window(
            kind="FIVE_HOUR", name="5 giờ", label="5h",
            remaining=quota.get("five_hour_remaining", quota.get("hourlyRemaining")),
            reset=quota.get("five_hour_reset", quota.get("hourlyReset")),
            minutes=quota.get("five_hour_window_minutes", quota.get("hourlyWindowMinutes", 300)),
            present=quota.get("five_hour_window_present", quota.get("hourlyWindowPresent")),
            source=source, freshness=freshness, now=now,
        ),
        _window(
            kind="WEEKLY", name="Hàng tuần", label="weekly",
            remaining=quota.get("weekly_remaining", quota.get("weeklyRemaining")),
            reset=quota.get("weekly_reset", quota.get("weeklyReset")),
            minutes=quota.get("weekly_window_minutes", quota.get("weeklyWindowMinutes")),
            present=quota.get("weekly_window_present", quota.get("weeklyWindowPresent")),
            source=source, freshness=freshness, now=now,
        ),
    ]


def model_specific_windows(quota: dict[str, Any], source: str, freshness: str, now: datetime) -> list[dict[str, Any]]:
    raw = quota.get("additional_windows") or quota.get("additionalWindows") or quota.get("model_windows") or []
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for i, row in enumerate(raw[:32]):
        if not isinstance(row, dict):
            continue
        model = str(row.get("model") or row.get("name") or row.get("label") or f"model-{i+1}")[:80]
        rem = row.get("remaining_pct", row.get("remaining", row.get("remainingPercent")))
        reset = row.get("reset_utc", row.get("reset", row.get("resetAt")))
        minutes = row.get("window_minutes", row.get("windowMinutes"))
        present = row.get("present")
        out.append(_window(
            kind="MODEL_SPECIFIC", name=model, label=model, remaining=rem, reset=reset,
            minutes=minutes, present=present, source=str(row.get("source") or source),
            freshness=freshness, now=now,
        ))
    return out


def lifecycle(account: dict[str, Any], quota: dict[str, Any], now: datetime) -> dict[str, Any]:
    # Package expiry is accepted ONLY from explicit quota/subscription metadata.
    pval = quota.get("package_expiry_utc") or quota.get("packageExpiry") or quota.get("subscription_expires_utc")
    psource = str(quota.get("package_expiry_source") or quota.get("packageExpirySource") or ("UPSTREAM_EXPLICIT" if pval else "NOT_EXPOSED"))
    pdt = parse_time(pval)
    if pval and not pdt:
        psource = "INVALID_METADATA"
    # OAuth token expiry is independent and may come from account credential metadata.
    tval = account.get("token_expiry_utc") or account.get("token_expiry") or account.get("expiry") or account.get("expires_at")
    tdt = parse_time(tval)
    return {
        "package": {
            "expiry_utc": iso(pdt) if pdt else None,
            "remaining": countdown(pdt, now)["countdown_text"] if pdt else "—",
            "source": psource if pdt else ("INVALID_METADATA" if pval else "NOT_EXPOSED"),
        },
        "oauth_token_lifecycle": {
            "expiry_utc": iso(tdt) if tdt else None,
            "remaining": countdown(tdt, now)["countdown_text"] if tdt else "—",
            "source": "AUTH_METADATA" if tdt else "NOT_EXPOSED",
        },
        "non_conflation": True,
    }


def _live_eligible(account: dict[str, Any], quota: dict[str, Any], freshness: str) -> bool:
    if "routing_eligible" in quota:
        return bool(quota.get("routing_eligible"))
    status = str(account.get("status") or "").upper()
    if status != "READY" or freshness in {"STALE", "UNKNOWN"}:
        return False
    vals = [clamp_pct(quota.get("five_hour_remaining", quota.get("hourlyRemaining"))),
            clamp_pct(quota.get("weekly_remaining", quota.get("weeklyRemaining")))]
    vals = [v for v in vals if v is not None]
    return bool(vals) and min(vals) > 0


def account_card(account: dict[str, Any], now: datetime, fresh_seconds: int = 600, stale_seconds: int = 1200) -> dict[str, Any]:
    quota = account.get("quota") or {}
    if not isinstance(quota, dict):
        quota = {}
    freshness, age, last_success = freshness_state(quota, now, fresh_seconds, stale_seconds)
    source = str(quota.get("source") or quota.get("source_name") or "WHAM_USAGE")[:80]
    windows = primary_windows(quota, source, freshness, now)
    windows.extend(model_specific_windows(quota, source, freshness, now))
    known = [w["remaining_pct"] for w in windows if w.get("present") and w.get("remaining_pct") is not None]
    floor = min(known) if known else None
    return {
        "account_ref": safe_identity_hash(account.get("email") or account.get("account") or account.get("id")),
        "plan_class": plan_class(account.get("plan") or quota.get("plan")),
        "status": str(account.get("status") or "UNKNOWN").upper(),
        "freshness_state": freshness,
        "source_age_seconds": age,
        "last_success_utc": last_success,
        "source": source,
        "quota_floor_pct": floor,
        "live_routing_eligible": _live_eligible(account, quota, freshness),
        "windows": windows,
        "lifecycle": lifecycle(account, quota, now),
    }


def router_preview(cards: list[dict[str, Any]]) -> dict[str, Any]:
    # NOW mirrors live eligibility. AFTER RESET is a visual scenario only; it cannot mutate live state.
    now_rows = []
    after_rows = []
    for c in cards:
        plan_score = PLAN_ORDER.get(c.get("plan_class", "UNKNOWN"), 0)
        floor = c.get("quota_floor_pct")
        now_score = (1000 if c.get("live_routing_eligible") else 0) + (floor if floor is not None else -1) + plan_score / 10
        reset_present = any(w.get("present") and w.get("reset_utc") for w in c.get("windows", []) if w.get("kind") in {"FIVE_HOUR", "WEEKLY"})
        # Scenario assumes observed primary windows replenish to 100 at their next reset; it NEVER changes card/live state.
        after_floor = 100.0 if reset_present and c.get("freshness_state") != "STALE" else floor
        after_eligible = bool(c.get("status") == "READY" and c.get("freshness_state") not in {"STALE", "UNKNOWN"} and after_floor is not None and after_floor > 0)
        after_score = (1000 if after_eligible else 0) + (after_floor if after_floor is not None else -1) + plan_score / 10
        now_rows.append({"account_ref": c["account_ref"], "eligible": bool(c.get("live_routing_eligible")), "score": round(now_score, 3)})
        after_rows.append({"account_ref": c["account_ref"], "eligible": after_eligible, "score": round(after_score, 3)})
    now_rows.sort(key=lambda x: (-x["score"], x["account_ref"]))
    after_rows.sort(key=lambda x: (-x["score"], x["account_ref"]))
    for i, row in enumerate(now_rows, 1):
        row["rank"] = i
    for i, row in enumerate(after_rows, 1):
        row["rank"] = i
    return {
        "mode": "READ_ONLY_PREVIEW",
        "now": now_rows,
        "after_next_reset": after_rows,
        "after_reset_kind": SCENARIO_KIND,
        "after_reset_label": "SCENARIO ONLY",
        "live_router_mutated": False,
        "quota_mutated": False,
    }


def build(accounts_obj: dict[str, Any], *, now: datetime | None = None, fresh_seconds: int = 600, stale_seconds: int = 1200) -> dict[str, Any]:
    t = now or utcnow()
    accounts = accounts_obj.get("accounts") or []
    cards = [account_card(a, t, fresh_seconds, stale_seconds) for a in accounts if isinstance(a, dict)]
    preview = router_preview(cards)
    counts: dict[str, int] = {k: 0 for k in ("FREE", "PLUS", "PRO", "TEAM_BUSINESS", "ENTERPRISE", "UNKNOWN")}
    for c in cards:
        counts[c["plan_class"]] = counts.get(c["plan_class"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "generated_utc": iso(t),
        "cards": cards,
        "summary": {
            "cards": len(cards), "plans": counts,
            "fresh": sum(c["freshness_state"] == "FRESH" for c in cards),
            "stale": sum(c["freshness_state"] == "STALE" for c in cards),
            "package_expiry_exposed": sum(bool(c["lifecycle"]["package"]["expiry_utc"]) for c in cards),
        },
        "router_preview": preview,
        "safety": {
            "live_quota_authoritative": True,
            "history_metadata_only": True,
            "package_token_quota_lifecycles_separate": True,
            "after_reset_scenario_only": True,
            "public_mutation_backend_action_added": False,
            "production_certification": PRODUCTION_CLAIM,
        },
    }


def history_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    cards = []
    for c in report.get("cards") or []:
        cards.append({
            "account_ref": c.get("account_ref"), "plan_class": c.get("plan_class"),
            "freshness_state": c.get("freshness_state"), "source": c.get("source"),
            "windows": [{k: w.get(k) for k in ("kind", "name", "remaining_pct", "reset_utc", "freshness_state", "source")}
                        for w in c.get("windows") or []],
            "package_expiry_utc": ((c.get("lifecycle") or {}).get("package") or {}).get("expiry_utc"),
        })
    snap = {
        "schema_version": SCHEMA_VERSION, "version": VERSION,
        "captured_utc": report.get("generated_utc") or iso(), "cards": cards,
    }
    if contains_secret_like(snap):
        raise ValueError("HISTORY_SECRET_SHAPE_REJECTED")
    snap["snapshot_hash"] = sha256(stable_json(snap))
    return snap


def append_history(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    snap = history_snapshot(report)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = stable_json(snap) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    return snap


def read_history(path: Path, max_lines: int = 5000) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8-sig") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict) and not contains_secret_like(row):
                out.append(row)
            if len(out) >= max_lines:
                break
    return out


def _card_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(c.get("account_ref")): c for c in snapshot.get("cards") or [] if isinstance(c, dict) and c.get("account_ref")}


def replay_events(snapshots: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(snapshots)
    events: list[dict[str, Any]] = []
    for prev, cur in zip(rows, rows[1:]):
        pmap, cmap = _card_map(prev), _card_map(cur)
        for acct in sorted(set(pmap) & set(cmap)):
            p, c = pmap[acct], cmap[acct]
            pw = {str(w.get("kind"))+":"+str(w.get("name")): w for w in p.get("windows") or []}
            cw = {str(w.get("kind"))+":"+str(w.get("name")): w for w in c.get("windows") or []}
            for key in sorted(set(pw) & set(cw)):
                a, b = pw[key], cw[key]
                if a.get("reset_utc") != b.get("reset_utc"):
                    events.append({"event": "RESET_TIMESTAMP_CHANGED", "account_ref": acct, "window": key,
                                   "from": a.get("reset_utc"), "to": b.get("reset_utc"), "at": cur.get("captured_utc")})
                ar, br = finite_num(a.get("remaining_pct")), finite_num(b.get("remaining_pct"))
                if ar is not None and br is not None and br >= ar + 20:
                    events.append({"event": "RESET_REPLENISHMENT_OBSERVED", "account_ref": acct, "window": key,
                                   "from_pct": ar, "to_pct": br, "at": cur.get("captured_utc")})
            if p.get("package_expiry_utc") != c.get("package_expiry_utc"):
                events.append({"event": "PACKAGE_EXPIRY_METADATA_CHANGED", "account_ref": acct,
                               "from": p.get("package_expiry_utc"), "to": c.get("package_expiry_utc"),
                               "at": cur.get("captured_utc")})
    if contains_secret_like(events):
        raise ValueError("REPLAY_SECRET_SHAPE_REJECTED")
    return events


def cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", required=True)
    ap.add_argument("--history")
    ap.add_argument("--output")
    ap.add_argument("--mode", choices=["build", "snapshot", "replay"], default="build")
    args = ap.parse_args()
    obj = json.loads(Path(args.accounts).read_text("utf-8-sig"))
    report = build(obj)
    if args.mode == "snapshot":
        if not args.history:
            raise SystemExit("--history required")
        data = {"ok": True, "version": VERSION, "snapshot": append_history(Path(args.history), report)}
    elif args.mode == "replay":
        if not args.history:
            raise SystemExit("--history required")
        data = {"ok": True, "version": VERSION, "events": replay_events(read_history(Path(args.history)))}
    else:
        data = {"ok": True, "version": VERSION, "usage_token_center": report}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", "utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
