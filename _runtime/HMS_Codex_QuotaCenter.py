#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
POLICY_VERSION = "25.34"
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization",
    "bearer", "api_key", "apikey", "client_secret", "password", "auth_json",
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


def read_json(path: Path | None, default: Any = None) -> Any:
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))
    os.replace(tmp, path)


def contains_secret_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS or kl.endswith(("_access_token", "_refresh_token", "_api_key", "_client_secret", "_password")):
                return True
            if contains_secret_like(v):
                return True
    elif isinstance(obj, list):
        return any(contains_secret_like(v) for v in obj)
    return False


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quota_snapshots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_utc TEXT NOT NULL,
            account TEXT NOT NULL,
            plan TEXT,
            status TEXT,
            five_remaining REAL,
            weekly_remaining REAL,
            five_reset_utc TEXT,
            weekly_reset_utc TEXT,
            refreshed_utc TEXT,
            source TEXT,
            source_age_seconds REAL,
            source_state TEXT,
            extra_windows_json TEXT,
            imported_legacy INTEGER NOT NULL DEFAULT 0,
            UNIQUE(account, captured_utc)
        );
        CREATE INDEX IF NOT EXISTS ix_quota_snapshots_account_time
          ON quota_snapshots(account, captured_utc);
        CREATE TABLE IF NOT EXISTS forecast_predictions(
            pred_key TEXT PRIMARY KEY,
            created_utc TEXT NOT NULL,
            target_utc TEXT NOT NULL,
            account TEXT NOT NULL,
            window_name TEXT NOT NULL,
            predicted_remaining REAL NOT NULL,
            baseline_remaining REAL,
            burn_pct_per_hour REAL,
            source_generated_utc TEXT,
            resolved_utc TEXT,
            actual_remaining REAL,
            observation_lag_seconds REAL,
            abs_error_pct REAL,
            signed_error_pct REAL
        );
        CREATE INDEX IF NOT EXISTS ix_forecast_due
          ON forecast_predictions(resolved_utc, target_utc);
        CREATE INDEX IF NOT EXISTS ix_forecast_account
          ON forecast_predictions(account, window_name, created_utc);
        """
    )
    cols={str(r[1]) for r in con.execute("PRAGMA table_info(quota_snapshots)").fetchall()}
    if "extra_windows_json" not in cols:
        con.execute("ALTER TABLE quota_snapshots ADD COLUMN extra_windows_json TEXT")
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    con.commit()
    return con


def freshness(refreshed: Any, now: datetime, cfg: dict[str, Any]) -> tuple[str, float | None]:
    dt = parse_time(refreshed)
    if not dt:
        return "UNKNOWN", None
    age = max(0.0, (now - dt).total_seconds())
    fresh_s = max(60.0, float(cfg.get("fresh_minutes", 10.0)) * 60.0)
    stale_s = max(fresh_s, float(cfg.get("stale_minutes", 30.0)) * 60.0)
    if age <= fresh_s:
        return "FRESH", age
    if age <= stale_s:
        return "AGING", age
    return "STALE", age


def safe_additional_windows(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in list(value or [])[:20]:
        if not isinstance(w, dict):
            continue
        remaining = num(w.get("remaining"))
        reset = parse_time(w.get("reset") or w.get("reset_utc") or w.get("resetAt"))
        out.append({
            "name": str(w.get("limit_name") or w.get("metered_feature") or w.get("name") or "Quota bổ sung")[:80],
            "label": str(w.get("label") or w.get("window") or "Window")[:60],
            "remaining_pct": None if remaining is None else round(clamp(remaining), 2),
            "reset_utc": iso(reset) if reset else None,
            "reset_text": str(w.get("reset_text") or "")[:80],
        })
    return out


def normalized_account_rows(fleet: dict[str, Any], cfg: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for a in list(fleet.get("accounts") or []):
        email = ek(a.get("email"))
        if not email:
            continue
        q = a.get("quota") or {}
        refreshed = q.get("refreshed_utc") or q.get("updated_utc") or q.get("source_updated_utc")
        fs, age = freshness(refreshed, now, cfg)
        source = str(q.get("source") or q.get("source_name") or "Codex quota")[:80]
        rows.append({
            "account": email,
            "plan": str(a.get("plan") or q.get("plan") or "")[:60],
            "status": str(a.get("status") or "")[:40],
            "five_remaining": num(q.get("five_hour_remaining")),
            "weekly_remaining": num(q.get("weekly_remaining")),
            "five_reset_utc": iso(parse_time(q.get("five_hour_reset"))) if parse_time(q.get("five_hour_reset")) else None,
            "weekly_reset_utc": iso(parse_time(q.get("weekly_reset"))) if parse_time(q.get("weekly_reset")) else None,
            "refreshed_utc": iso(parse_time(refreshed)) if parse_time(refreshed) else None,
            "source": source,
            "source_age_seconds": age,
            "source_state": fs,
            "extra_windows": safe_additional_windows(q.get("additional_windows")),
        })
    return rows


def _last_snapshot(con: sqlite3.Connection, account: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM quota_snapshots WHERE account=? ORDER BY captured_utc DESC LIMIT 1", (account,)
    ).fetchone()


def insert_current(con: sqlite3.Connection, rows: list[dict[str, Any]], now: datetime, cfg: dict[str, Any]) -> dict[str, int]:
    added = skipped = 0
    min_interval = max(15.0, float(cfg.get("min_snapshot_interval_seconds", 300.0)))
    captured = iso(now)
    for r in rows:
        last = _last_snapshot(con, r["account"])
        if last:
            last_t = parse_time(last["captured_utc"])
            if last_t and (now - last_t).total_seconds() < min_interval:
                same = (
                    num(last["five_remaining"]) == r["five_remaining"] and
                    num(last["weekly_remaining"]) == r["weekly_remaining"] and
                    (last["five_reset_utc"] or None) == r["five_reset_utc"] and
                    (last["weekly_reset_utc"] or None) == r["weekly_reset_utc"]
                )
                if same:
                    skipped += 1
                    continue
        before = con.total_changes
        con.execute(
            """INSERT OR IGNORE INTO quota_snapshots(
                captured_utc,account,plan,status,five_remaining,weekly_remaining,
                five_reset_utc,weekly_reset_utc,refreshed_utc,source,source_age_seconds,source_state,extra_windows_json,imported_legacy
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (captured, r["account"], r["plan"], r["status"], r["five_remaining"], r["weekly_remaining"],
             r["five_reset_utc"], r["weekly_reset_utc"], r["refreshed_utc"], r["source"],
             r["source_age_seconds"], r["source_state"], json.dumps(r.get("extra_windows") or [], ensure_ascii=False))
        )
        if con.total_changes > before:
            added += 1
    con.commit()
    return {"added": added, "skipped": skipped}


def import_legacy_history(con: sqlite3.Connection, path: Path | None, cfg: dict[str, Any]) -> int:
    if not path or not path.exists():
        return 0
    max_lines = max(100, int(cfg.get("legacy_import_max_lines", 10000)))
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return 0
    added = 0
    for line in lines:
        try:
            snap = json.loads(line)
        except Exception:
            continue
        captured = parse_time(snap.get("time") or snap.get("time_utc"))
        if not captured:
            continue
        for a in list(snap.get("accounts") or []):
            email = ek(a.get("email"))
            if not email:
                continue
            q5 = num(a.get("hourly"))
            qw = num(a.get("weekly"))
            before = con.total_changes
            con.execute(
                """INSERT OR IGNORE INTO quota_snapshots(
                    captured_utc,account,five_remaining,weekly_remaining,source,source_state,imported_legacy
                ) VALUES(?,?,?,?,?,?,1)""",
                (iso(captured), email, q5, qw, "legacy-jsonl", "LEGACY")
            )
            if con.total_changes > before:
                added += 1
    con.commit()
    return added


def predictive_rows(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ek(r.get("account")): r for r in list(plan.get("accounts") or []) if ek(r.get("account"))}


def add_predictions(con: sqlite3.Connection, plan: dict[str, Any], now: datetime, cfg: dict[str, Any]) -> int:
    if not plan:
        return 0
    horizon_min = max(15.0, float(cfg.get("accuracy_horizon_minutes", 60.0)))
    min_interval_min = max(5.0, float(cfg.get("prediction_min_interval_minutes", 15.0)))
    generated = parse_time(plan.get("generated_utc")) or now
    target = now + timedelta(minutes=horizon_min)
    added = 0
    for account, row in predictive_rows(plan).items():
        for window_name, field in (("5h", "five_hour"), ("7d", "weekly")):
            w = row.get(field) or {}
            remain = num(w.get("remaining_pct"))
            burn = num(w.get("burn_pct_per_hour"))
            if remain is None or burn is None or burn < 0:
                continue
            reset_dt = parse_time(w.get("reset_utc"))
            effective_target = target
            if reset_dt and reset_dt <= effective_target:
                # Do not evaluate a pre-reset burn model after the reset boundary.
                continue
            predicted = clamp(remain - burn * (horizon_min / 60.0))
            bucket = int(now.timestamp() // (min_interval_min * 60.0))
            key = f"{account}|{window_name}|{bucket}"
            before = con.total_changes
            con.execute(
                """INSERT OR IGNORE INTO forecast_predictions(
                    pred_key,created_utc,target_utc,account,window_name,predicted_remaining,
                    baseline_remaining,burn_pct_per_hour,source_generated_utc
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (key, iso(now), iso(effective_target), account, window_name, predicted, remain, burn, iso(generated))
            )
            if con.total_changes > before:
                added += 1
    con.commit()
    return added


def resolve_predictions(con: sqlite3.Connection, now: datetime, tolerance_min: float = 30.0) -> int:
    due = con.execute(
        "SELECT * FROM forecast_predictions WHERE resolved_utc IS NULL AND target_utc<=? ORDER BY target_utc LIMIT 500",
        (iso(now),)
    ).fetchall()
    resolved = 0
    tolerance_s = max(300.0, tolerance_min * 60.0)
    for p in due:
        field = "five_remaining" if p["window_name"] == "5h" else "weekly_remaining"
        target = parse_time(p["target_utc"])
        if not target:
            continue
        # Prefer the first observation at/after target; otherwise a close observation before target.
        obs = con.execute(
            f"SELECT captured_utc,{field} AS actual FROM quota_snapshots WHERE account=? AND {field} IS NOT NULL AND captured_utc>=? ORDER BY captured_utc ASC LIMIT 1",
            (p["account"], iso(target))
        ).fetchone()
        if not obs:
            obs = con.execute(
                f"SELECT captured_utc,{field} AS actual FROM quota_snapshots WHERE account=? AND {field} IS NOT NULL AND captured_utc<? ORDER BY captured_utc DESC LIMIT 1",
                (p["account"], iso(target))
            ).fetchone()
        if not obs:
            continue
        ot = parse_time(obs["captured_utc"])
        if not ot or abs((ot - target).total_seconds()) > tolerance_s:
            continue
        actual = num(obs["actual"])
        if actual is None:
            continue
        signed = float(p["predicted_remaining"]) - actual
        con.execute(
            """UPDATE forecast_predictions SET resolved_utc=?,actual_remaining=?,observation_lag_seconds=?,
               abs_error_pct=?,signed_error_pct=? WHERE pred_key=?""",
            (iso(now), actual, (ot - target).total_seconds(), abs(signed), signed, p["pred_key"])
        )
        resolved += 1
    con.commit()
    return resolved


def prune(con: sqlite3.Connection, now: datetime, cfg: dict[str, Any]) -> dict[str, int]:
    quota_days = max(7, int(cfg.get("retention_days", 45)))
    forecast_days = max(quota_days, int(cfg.get("forecast_retention_days", 90)))
    qcut = iso(now - timedelta(days=quota_days))
    pcut = iso(now - timedelta(days=forecast_days))
    before = con.total_changes
    con.execute("DELETE FROM quota_snapshots WHERE captured_utc<?", (qcut,))
    qdel = con.total_changes - before
    before = con.total_changes
    con.execute("DELETE FROM forecast_predictions WHERE created_utc<?", (pcut,))
    pdel = con.total_changes - before
    con.commit()
    return {"quota_deleted": qdel, "forecast_deleted": pdel}


def downsample(rows: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if len(rows) <= max_points:
        return rows
    step = (len(rows) - 1) / float(max_points - 1)
    idxs = sorted({round(i * step) for i in range(max_points)})
    return [rows[min(len(rows) - 1, i)] for i in idxs]


def history_series(con: sqlite3.Connection, account: str, since: datetime, max_points: int) -> dict[str, list[dict[str, Any]]]:
    rows = con.execute(
        "SELECT captured_utc,five_remaining,weekly_remaining FROM quota_snapshots WHERE account=? AND captured_utc>=? ORDER BY captured_utc",
        (account, iso(since))
    ).fetchall()
    five = [{"t": r["captured_utc"], "v": round(float(r["five_remaining"]), 2)} for r in rows if r["five_remaining"] is not None]
    week = [{"t": r["captured_utc"], "v": round(float(r["weekly_remaining"]), 2)} for r in rows if r["weekly_remaining"] is not None]
    return {"five_hour": downsample(five, max_points), "weekly": downsample(week, max_points)}


def accuracy(con: sqlite3.Connection, account: str, window_name: str) -> dict[str, Any]:
    rows = con.execute(
        """SELECT abs_error_pct,signed_error_pct,observation_lag_seconds,resolved_utc
           FROM forecast_predictions WHERE account=? AND window_name=? AND resolved_utc IS NOT NULL
           ORDER BY resolved_utc DESC LIMIT 100""",
        (account, window_name)
    ).fetchall()
    if not rows:
        return {"samples": 0, "mae_pct": None, "bias_pct": None, "last_error_pct": None}
    abses = [float(r["abs_error_pct"]) for r in rows if r["abs_error_pct"] is not None]
    signed = [float(r["signed_error_pct"]) for r in rows if r["signed_error_pct"] is not None]
    return {
        "samples": len(abses),
        "mae_pct": round(sum(abses) / len(abses), 2) if abses else None,
        "bias_pct": round(sum(signed) / len(signed), 2) if signed else None,
        "last_error_pct": round(abses[0], 2) if abses else None,
        "median_error_pct": round(statistics.median(abses), 2) if abses else None,
    }


def reset_info(reset_value: Any, now: datetime) -> dict[str, Any]:
    dt = parse_time(reset_value)
    if not dt:
        return {"reset_utc": None, "reset_in_hours": None, "state": "UNKNOWN"}
    hours = (dt - now).total_seconds() / 3600.0
    state = "UPCOMING" if hours >= 0 else "OVERDUE"
    return {"reset_utc": iso(dt), "reset_in_hours": round(hours, 2), "state": state}


def report(con: sqlite3.Connection, plan: dict[str, Any], cfg: dict[str, Any], now: datetime) -> dict[str, Any]:
    latest_rows = con.execute(
        """SELECT q.* FROM quota_snapshots q JOIN (
             SELECT account,MAX(captured_utc) mt FROM quota_snapshots GROUP BY account
           ) x ON q.account=x.account AND q.captured_utc=x.mt ORDER BY q.account"""
    ).fetchall()
    pred = predictive_rows(plan)
    max_points = max(12, min(240, int(cfg.get("chart_max_points", 72))))
    chart_hours = max(6.0, float(cfg.get("chart_history_hours", 168.0)))
    low_pct = float(cfg.get("alert_low_pct", 15.0))
    critical_pct = float(cfg.get("alert_critical_pct", 5.0))
    accounts: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    freshness_counts = {"FRESH": 0, "AGING": 0, "STALE": 0, "UNKNOWN": 0, "LEGACY": 0}
    risk_counts = {"EMERGENCY": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}

    for r in latest_rows:
        account = r["account"]
        p = pred.get(account) or {}
        risk = str(p.get("risk") or "UNKNOWN").upper()
        if risk not in risk_counts:
            risk = "UNKNOWN"
        risk_counts[risk] += 1
        fs = str(r["source_state"] or "UNKNOWN").upper()
        freshness_counts[fs if fs in freshness_counts else "UNKNOWN"] += 1
        five = num(r["five_remaining"])
        week = num(r["weekly_remaining"])
        a5 = accuracy(con, account, "5h")
        aw = accuracy(con, account, "7d")
        try:
            extras = json.loads(r["extra_windows_json"] or "[]") if "extra_windows_json" in r.keys() else []
            if not isinstance(extras, list): extras = []
        except Exception:
            extras = []
        row_alerts: list[str] = []
        if fs == "STALE":
            row_alerts.append("QUOTA_SOURCE_STALE")
        elif fs == "UNKNOWN":
            row_alerts.append("QUOTA_SOURCE_UNKNOWN")
        if five is not None and five <= critical_pct:
            row_alerts.append("FIVE_HOUR_CRITICAL")
        elif five is not None and five <= low_pct:
            row_alerts.append("FIVE_HOUR_LOW")
        if week is not None and week <= critical_pct:
            row_alerts.append("WEEKLY_CRITICAL")
        elif week is not None and week <= low_pct:
            row_alerts.append("WEEKLY_LOW")
        if risk in {"HIGH", "EMERGENCY"}:
            row_alerts.append("PREDICTIVE_" + risk)
        for code in row_alerts:
            sev = "CRITICAL" if code.endswith("CRITICAL") or code.endswith("EMERGENCY") else ("WARN" if "LOW" in code or "STALE" in code or "HIGH" in code else "INFO")
            alerts.append({"account": account, "severity": sev, "code": code})
        accounts.append({
            "account": account,
            "plan": r["plan"] or "",
            "status": r["status"] or "",
            "captured_utc": r["captured_utc"],
            "five_hour_remaining": five,
            "weekly_remaining": week,
            "five_hour_reset": reset_info(r["five_reset_utc"], now),
            "weekly_reset": reset_info(r["weekly_reset_utc"], now),
            "freshness": {"state": fs, "age_seconds": r["source_age_seconds"], "refreshed_utc": r["refreshed_utc"], "source": r["source"]},
            "predictive": {
                "risk": risk,
                "score_penalty": p.get("score_penalty"),
                "action": p.get("action"),
                "five_hour": p.get("five_hour") or {},
                "weekly": p.get("weekly") or {},
            },
            "accuracy": {"five_hour": a5, "weekly": aw},
            "additional_windows": extras,
            "history": history_series(con, account, now - timedelta(hours=chart_hours), max_points),
            "alerts": row_alerts,
        })

    forecasts = con.execute("SELECT COUNT(*) n FROM forecast_predictions").fetchone()["n"]
    resolved = con.execute("SELECT COUNT(*) n FROM forecast_predictions WHERE resolved_utc IS NOT NULL").fetchone()["n"]
    snapshots = con.execute("SELECT COUNT(*) n FROM quota_snapshots").fetchone()["n"]
    alerts.sort(key=lambda x: ({"CRITICAL": 0, "WARN": 1, "INFO": 2}.get(x["severity"], 3), x["account"], x["code"]))
    out = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_utc": iso(now),
        "summary": {
            "accounts": len(accounts),
            "snapshots": snapshots,
            "forecasts": forecasts,
            "resolved_forecasts": resolved,
            "freshness": freshness_counts,
            "risk": risk_counts,
            "alerts": len(alerts),
        },
        "alerts": alerts[:100],
        "accounts": accounts,
        "safety": {
            "quota_live_is_authoritative": True,
            "forecast_is_labeled_forecast": True,
            "no_prompt_or_request_body": True,
            "no_oauth_token_or_cookie": True,
            "stable_endpoint_untouched": True,
            "session_affinity_untouched": True,
            "project_binding_untouched": True,
            "destructive_delete": False,
        },
        "note": "Advanced Quota Center v25.34 stores quota metadata/history only. Forecast accuracy is measured against later observed quota and never overwrites live quota.",
    }
    if contains_secret_like(out):
        raise RuntimeError("SECRET_LIKE_FIELD_IN_REPORT")
    return out


def validate_report(obj: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if str(obj.get("policy_version") or "") != POLICY_VERSION:
        errors.append("policy_version mismatch")
    safety = obj.get("safety") or {}
    for key in (
        "quota_live_is_authoritative", "forecast_is_labeled_forecast", "no_prompt_or_request_body",
        "no_oauth_token_or_cookie", "stable_endpoint_untouched", "session_affinity_untouched",
        "project_binding_untouched",
    ):
        if safety.get(key) is not True:
            errors.append("safety invariant false: " + key)
    if contains_secret_like(obj):
        errors.append("secret-like field present")
    return {"ok": not errors, "errors": errors, "accounts": len(obj.get("accounts") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "sync", "validate"), required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--predictive")
    ap.add_argument("--legacy-history")
    ap.add_argument("--config-json")
    args = ap.parse_args()
    db = Path(args.db)
    state_path = Path(args.state)
    report_path = Path(args.report)
    cfg = json.loads(args.config_json) if args.config_json else {}
    now = utcnow()
    con: sqlite3.Connection | None = None
    try:
        if args.mode == "status":
            data = {"state": read_json(state_path, {}) or {}, "report": read_json(report_path, {}) or {}}
        elif args.mode == "validate":
            obj = read_json(report_path, {}) or {}
            val = validate_report(obj)
            if not val["ok"]:
                raise RuntimeError("REPORT_VALIDATION_FAILED:" + ",".join(val["errors"]))
            data = {"validation": val, "report": obj}
        else:
            if not args.fleet:
                raise ValueError("--fleet required for sync")
            fleet = read_json(Path(args.fleet), {}) or {}
            predictive = read_json(Path(args.predictive), {}) or {} if args.predictive else {}
            con = connect(db)
            imported = import_legacy_history(con, Path(args.legacy_history) if args.legacy_history else None, cfg)
            rows = normalized_account_rows(fleet, cfg, now)
            sync_result = insert_current(con, rows, now, cfg)
            pred_added = add_predictions(con, predictive, now, cfg)
            pred_resolved = resolve_predictions(con, now, float(cfg.get("accuracy_tolerance_minutes", 35.0)))
            pruned = prune(con, now, cfg)
            rep = report(con, predictive, cfg, now)
            val = validate_report(rep)
            if not val["ok"]:
                raise RuntimeError("REPORT_VALIDATION_FAILED:" + ",".join(val["errors"]))
            atomic_json(report_path, rep)
            state = {
                "schema_version": SCHEMA_VERSION,
                "policy_version": POLICY_VERSION,
                "updated_utc": iso(now),
                "sync": sync_result,
                "legacy_imported": imported,
                "predictions_added": pred_added,
                "predictions_resolved": pred_resolved,
                "pruned": pruned,
                "summary": rep.get("summary") or {},
            }
            atomic_json(state_path, state)
            data = {"state": state, "report": rep, "validation": val}
        out = {"ok": True, "data": data}
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if con is not None:
            con.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
