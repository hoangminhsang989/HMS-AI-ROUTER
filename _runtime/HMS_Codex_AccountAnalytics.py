#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ENGINE_VERSION = "25.35"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


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
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def i(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(vals[lo])
    return float(vals[lo] * (hi - k) + vals[hi] * (k - lo))


def parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def norm_account(v: Any) -> str:
    return str(v or "").strip().lower()


def init_analytics_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS account_snapshots (
            snapshot_utc TEXT NOT NULL,
            account TEXT NOT NULL,
            quality_score REAL NOT NULL,
            confidence TEXT NOT NULL,
            requests_7d INTEGER NOT NULL,
            success_rate_7d REAL NOT NULL,
            latency_p95_7d REAL NOT NULL,
            retry_rate_7d REAL NOT NULL,
            http_429_7d INTEGER NOT NULL,
            auth_errors_7d INTEGER NOT NULL,
            server_errors_7d INTEGER NOT NULL,
            quota_floor_pct REAL,
            predictive_risk TEXT,
            circuit_state TEXT,
            PRIMARY KEY(snapshot_utc, account)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_aa_account_time ON account_snapshots(account,snapshot_utc)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)")
    conn.execute(
        "INSERT INTO meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def usage_rows(usage_db: Path, cutoff: datetime) -> list[sqlite3.Row]:
    if not usage_db.exists():
        return []
    c = sqlite3.connect(str(usage_db), timeout=15)
    c.row_factory = sqlite3.Row
    try:
        return c.execute(
            "SELECT * FROM requests WHERE time_utc>=? ORDER BY time_utc DESC",
            (cutoff.isoformat(),),
        ).fetchall()
    finally:
        c.close()


def summarize(rows: list[sqlite3.Row]) -> dict[str, Any]:
    total = len(rows)
    success = sum(1 for r in rows if 200 <= i(r["status"]) < 400)
    retry = sum(1 for r in rows if i(r["attempt_count"]) > 1)
    lat = [f(r["latency_ms"]) for r in rows if f(r["latency_ms"]) > 0]
    return {
        "requests": total,
        "success": success,
        "success_rate_pct": round(success * 100.0 / total, 2) if total else 0.0,
        "retry_requests": retry,
        "retry_rate_pct": round(retry * 100.0 / total, 2) if total else 0.0,
        "http_429": sum(1 for r in rows if i(r["status"]) == 429),
        "http_401_403": sum(1 for r in rows if i(r["status"]) in (401, 403)),
        "server_errors": sum(1 for r in rows if 500 <= i(r["status"]) < 600),
        "total_tokens": sum(max(0, i(r["total_tokens"])) for r in rows),
        "latency_p50_ms": round(percentile(lat, .50), 1),
        "latency_p95_ms": round(percentile(lat, .95), 1),
        "latency_p99_ms": round(percentile(lat, .99), 1),
    }


def grouped(rows: list[sqlite3.Row], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, ...], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = tuple(str(r[x] or "—").strip() or "—" for x in fields)
        buckets[key].append(r)
    out: list[dict[str, Any]] = []
    for key, grp in buckets.items():
        item = {fields[idx]: key[idx] for idx in range(len(fields))}
        item.update(summarize(grp))
        out.append(item)
    out.sort(key=lambda x: (-i(x.get("requests")), tuple(str(x.get(k) or "") for k in fields)))
    return out


def fleet_accounts(fleet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    candidates = fleet.get("accounts") or fleet.get("account_center") or []
    if isinstance(candidates, dict):
        candidates = candidates.get("records") or candidates.get("accounts") or []
    for row in candidates if isinstance(candidates, list) else []:
        if not isinstance(row, dict):
            continue
        key = norm_account(row.get("email") or row.get("account") or row.get("name"))
        if key:
            out[key] = row
    # v25.31+ fleet carries instance pools as a second source.
    for inst in fleet.get("instances") or []:
        for row in inst.get("pool") or inst.get("accounts") or []:
            if not isinstance(row, dict):
                continue
            key = norm_account(row.get("email") or row.get("account") or row.get("name"))
            if key and key not in out:
                out[key] = row
    return out


def plan_by_account(doc: dict[str, Any], keys: tuple[str, ...] = ("accounts", "rows", "candidates")) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(doc, dict):
        return out
    stack: list[Any] = [doc]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            account = norm_account(cur.get("account") or cur.get("email") or cur.get("name"))
            if account and any(k in cur for k in ("risk", "state", "desired_state", "score", "action", "breaker_state")):
                prior = out.get(account)
                if prior is None or len(cur) > len(prior):
                    out[account] = cur
            for k, v in cur.items():
                if k in {"token", "access_token", "refresh_token", "cookie", "authorization", "api_key", "client_secret", "password"}:
                    continue
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def quota_floor(account: dict[str, Any]) -> float | None:
    q = account.get("quota") or {}
    vals: list[float] = []
    for key in ("five_hour_remaining", "weekly_remaining"):
        v = q.get(key)
        if v is not None and v != "":
            try:
                vals.append(float(v))
            except Exception:
                pass
    return min(vals) if vals else None


def confidence(samples: int) -> str:
    if samples >= 100:
        return "VERY_HIGH"
    if samples >= 30:
        return "HIGH"
    if samples >= 10:
        return "MEDIUM"
    if samples >= 3:
        return "LOW"
    return "NONE"


def quality_score(metrics: dict[str, Any], live: dict[str, Any], predictive: dict[str, Any], breaker: dict[str, Any]) -> float:
    req = i(metrics.get("requests"))
    # Neutral baseline until enough evidence exists.
    c = min(1.0, req / 30.0)
    success = f(metrics.get("success_rate_pct"), 50.0 if not req else 0.0)
    rel = 50.0 + (success - 50.0) * c
    retry_penalty = min(18.0, f(metrics.get("retry_rate_pct")) * .22)
    error_penalty = min(28.0, i(metrics.get("http_429")) * 2.8 + i(metrics.get("http_401_403")) * 6.0 + i(metrics.get("server_errors")) * 1.2)
    p95 = f(metrics.get("latency_p95_ms"))
    latency = 50.0 if p95 <= 0 else clamp(105.0 - p95 / 180.0, 5.0, 100.0)
    health = clamp(f(live.get("health_score"), f(live.get("pool_score"), 50.0)))
    q = quota_floor(live)
    quota = 55.0 if q is None else clamp(q)
    score = rel * .38 + latency * .17 + health * .18 + quota * .17 + clamp(f(live.get("pool_score"), health)) * .10
    score -= retry_penalty + error_penalty
    risk = str(predictive.get("risk") or predictive.get("predictive_risk") or "UNKNOWN").upper()
    score -= {"MEDIUM": 5.0, "HIGH": 12.0, "EMERGENCY": 25.0}.get(risk, 0.0)
    state = str(breaker.get("desired_state") or breaker.get("state") or breaker.get("breaker_state") or "CLOSED").upper()
    score -= {"HALF_OPEN": 20.0, "OPEN": 55.0}.get(state, 0.0)
    status = str(live.get("status") or "READY").upper()
    if status and status != "READY":
        score -= 35.0
    return round(clamp(score), 1)


def grade(score: float, samples: int, breaker_state: str) -> str:
    if breaker_state == "OPEN":
        return "QUARANTINED"
    if samples < 3:
        return "LEARNING"
    if score >= 90:
        return "EXCELLENT"
    if score >= 78:
        return "GOOD"
    if score >= 62:
        return "FAIR"
    if score >= 45:
        return "WEAK"
    return "POOR"


def model_quality(row: dict[str, Any]) -> float:
    req = i(row.get("requests"))
    c = min(1.0, req / 20.0)
    success = f(row.get("success_rate_pct"))
    reliability = 50 + (success - 50) * c
    p95 = f(row.get("latency_p95_ms"))
    latency = 50 if p95 <= 0 else clamp(105 - p95 / 180, 5, 100)
    penalties = min(32.0, f(row.get("retry_rate_pct")) * .18 + i(row.get("http_429")) * 2.5 + i(row.get("http_401_403")) * 5 + i(row.get("server_errors")) * 1.2)
    return round(clamp(reliability * .72 + latency * .28 - penalties), 1)


def trend_for(conn: sqlite3.Connection, account: str, current_score: float) -> dict[str, Any]:
    cutoff = (utcnow() - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT snapshot_utc,quality_score FROM account_snapshots WHERE account=? AND snapshot_utc>=? ORDER BY snapshot_utc ASC",
        (account, cutoff),
    ).fetchall()
    if not rows:
        return {"direction": "NEW", "delta_score": 0.0}
    baseline = f(rows[0][1], current_score)
    delta = round(current_score - baseline, 1)
    return {"direction": "UP" if delta >= 3 else ("DOWN" if delta <= -3 else "STABLE"), "delta_score": delta}


def build_report(args: argparse.Namespace, conn: sqlite3.Connection) -> dict[str, Any]:
    now = utcnow()
    rows30 = usage_rows(Path(args.usage_db), now - timedelta(days=30))
    rows7 = [r for r in rows30 if (parse_time(r["time_utc"]) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(days=7)]
    rows1 = [r for r in rows30 if (parse_time(r["time_utc"]) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(hours=24)]
    by_acc_30 = {norm_account(x["account"]): x for x in grouped(rows30, ("account",)) if x["account"] != "—"}
    by_acc_7 = {norm_account(x["account"]): x for x in grouped(rows7, ("account",)) if x["account"] != "—"}
    by_acc_1 = {norm_account(x["account"]): x for x in grouped(rows1, ("account",)) if x["account"] != "—"}

    fleet = read_json(Path(args.fleet) if args.fleet else None, {}) or {}
    live = fleet_accounts(fleet)
    predictive = plan_by_account(read_json(Path(args.predictive) if args.predictive else None, {}) or {})
    breaker = plan_by_account(read_json(Path(args.breaker) if args.breaker else None, {}) or {})

    account_keys = set(live) | set(by_acc_30) | set(by_acc_7) | set(by_acc_1) | set(predictive) | set(breaker)
    accounts: list[dict[str, Any]] = []
    snap_time = iso(now)
    for account in sorted(account_keys):
        m30, m7, m1 = by_acc_30.get(account, {}), by_acc_7.get(account, {}), by_acc_1.get(account, {})
        l = live.get(account, {})
        p = predictive.get(account, {})
        b = breaker.get(account, {})
        score = quality_score(m7, l, p, b)
        state = str(b.get("desired_state") or b.get("state") or b.get("breaker_state") or "CLOSED").upper()
        samples = i(m7.get("requests"))
        q = quota_floor(l)
        row = {
            "account": str(l.get("email") or l.get("account") or account),
            "status": str(l.get("status") or ("UNKNOWN" if account not in live else "READY")).upper(),
            "plan": str(l.get("plan") or l.get("tier") or ""),
            "role": str(l.get("role") or l.get("pool_role") or "AUTO"),
            "quality_score": score,
            "grade": grade(score, samples, state),
            "confidence": confidence(samples),
            "requests_24h": i(m1.get("requests")),
            "requests_7d": samples,
            "requests_30d": i(m30.get("requests")),
            "success_rate_24h": f(m1.get("success_rate_pct")),
            "success_rate_7d": f(m7.get("success_rate_pct")),
            "success_rate_30d": f(m30.get("success_rate_pct")),
            "latency_p95_24h": f(m1.get("latency_p95_ms")),
            "latency_p95_7d": f(m7.get("latency_p95_ms")),
            "retry_rate_7d": f(m7.get("retry_rate_pct")),
            "http_429_7d": i(m7.get("http_429")),
            "auth_errors_7d": i(m7.get("http_401_403")),
            "server_errors_7d": i(m7.get("server_errors")),
            "tokens_7d": i(m7.get("total_tokens")),
            "quota_floor_pct": q,
            "predictive_risk": str(p.get("risk") or p.get("predictive_risk") or "UNKNOWN").upper(),
            "predictive_action": str(p.get("action") or ""),
            "circuit_state": state,
        }
        row["trend"] = trend_for(conn, account, score)
        accounts.append(row)
        conn.execute(
            "INSERT OR REPLACE INTO account_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snap_time, account, score, row["confidence"], samples, row["success_rate_7d"], row["latency_p95_7d"], row["retry_rate_7d"], row["http_429_7d"], row["auth_errors_7d"], row["server_errors_7d"], q, row["predictive_risk"], state),
        )

    accounts.sort(key=lambda x: (-f(x.get("quality_score")), -i(x.get("requests_7d")), norm_account(x.get("account"))))

    model_profiles: list[dict[str, Any]] = []
    for row in grouped(rows7, ("account", "model")):
        if row.get("account") == "—" or row.get("model") == "—":
            continue
        item = dict(row)
        item["quality_score"] = model_quality(item)
        item["confidence"] = confidence(i(item.get("requests")))
        model_profiles.append(item)
    model_profiles.sort(key=lambda x: (-f(x.get("quality_score")), -i(x.get("requests")), str(x.get("model"))))

    workload_profiles: list[dict[str, Any]] = []
    for row in grouped(rows7, ("account", "request_type")):
        if row.get("account") == "—":
            continue
        item = dict(row)
        item["quality_score"] = model_quality(item)
        item["confidence"] = confidence(i(item.get("requests")))
        workload_profiles.append(item)
    workload_profiles.sort(key=lambda x: (-f(x.get("quality_score")), -i(x.get("requests"))))

    model_recommendations: list[dict[str, Any]] = []
    models = defaultdict(list)
    for row in model_profiles:
        if i(row.get("requests")) >= max(3, i(args.min_samples)):
            models[str(row.get("model"))].append(row)
    for model, candidates in models.items():
        candidates.sort(key=lambda x: (-f(x.get("quality_score")), -i(x.get("requests"))))
        best = candidates[0]
        model_recommendations.append({
            "model": model,
            "recommended_account": best.get("account"),
            "quality_score": best.get("quality_score"),
            "requests": best.get("requests"),
            "confidence": best.get("confidence"),
            "mode": "ANALYTICS_ADVISORY",
        })
    model_recommendations.sort(key=lambda x: (-i(x.get("requests")), str(x.get("model"))))

    conn.commit()
    total = len(accounts)
    healthy = sum(1 for x in accounts if f(x.get("quality_score")) >= 78 and x.get("circuit_state") != "OPEN")
    attention = sum(1 for x in accounts if f(x.get("quality_score")) < 62 or x.get("circuit_state") == "OPEN")
    best = accounts[0] if accounts else None
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": snap_time,
        "summary": {
            "accounts": total,
            "healthy": healthy,
            "attention": attention,
            "best_account": best.get("account") if best else "",
            "best_score": best.get("quality_score") if best else 0.0,
            "requests_7d": sum(i(x.get("requests_7d")) for x in accounts),
            "model_profiles": len(model_profiles),
        },
        "accounts": accounts,
        "model_profiles": model_profiles[:100],
        "workload_profiles": workload_profiles[:100],
        "model_recommendations": model_recommendations[:50],
        "router_signal": {
            "mode": "ACCOUNT_QUALITY_SIGNAL",
            "accounts": [
                {
                    "account": x["account"],
                    "quality_score": x["quality_score"],
                    "confidence": x["confidence"],
                    "samples_7d": x["requests_7d"],
                    "circuit_state": x["circuit_state"],
                    "predictive_risk": x["predictive_risk"],
                }
                for x in accounts
            ],
            "note": "v25.35 signal is bounded inside Closed-loop Router; stable endpoint/session affinity remain authoritative.",
        },
        "privacy": {
            "prompt_stored": False,
            "request_body_stored": False,
            "oauth_token_stored": False,
            "api_key_stored": False,
            "cookie_stored": False,
            "note": "Account Analytics consumes normalized metadata only.",
        },
    }


def prune(conn: sqlite3.Connection, days: int) -> None:
    cutoff = (utcnow() - timedelta(days=max(7, days))).isoformat()
    conn.execute("DELETE FROM account_snapshots WHERE snapshot_utc<?", (cutoff,))
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("sync", "status"), default="sync")
    ap.add_argument("--db", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--usage-db", required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--predictive")
    ap.add_argument("--breaker")
    ap.add_argument("--retention-days", type=int, default=90)
    ap.add_argument("--min-samples", type=int, default=5)
    args = ap.parse_args()

    db, report = Path(args.db), Path(args.report)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=15)
    try:
        init_analytics_db(conn)
        if args.mode == "status" and report.exists():
            data = read_json(report, {}) or {}
        else:
            data = build_report(args, conn)
            prune(conn, args.retention_days)
            atomic_json(report, data)
        out = {"ok": True, "mode": args.mode, "data": data, "db": str(db), "report": str(report)}
    except Exception as exc:
        out = {"ok": False, "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
