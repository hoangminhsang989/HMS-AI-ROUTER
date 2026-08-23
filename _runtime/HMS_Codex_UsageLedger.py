#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 3


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: Any) -> str:
    if not value:
        return utcnow().isoformat()
    s = str(value).strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat()
    except Exception:
        return utcnow().isoformat()


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def official_account_ref(row: dict[str, Any]) -> str:
    """Return a pseudonymous stable ref; never persist the raw official account id."""
    raw = ""
    for key in ("official_account_id", "account_id", "chatgpt_account_id", "user_id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            raw = str(value).strip()
            break
    if not raw:
        return ""
    return "oaid-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(vals[lo])
    return float(vals[lo] * (hi - k) + vals[hi] * (k - lo))


def tail_lines(path: Path, max_lines: int) -> Iterable[str]:
    if not path.exists():
        return []
    # JSONL traces are typically small; deque keeps memory bounded even after long runs.
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        return list(deque(fh, maxlen=max_lines))


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            request_id TEXT PRIMARY KEY,
            time_utc TEXT NOT NULL,
            protocol TEXT,
            method TEXT,
            path TEXT,
            request_type TEXT,
            model TEXT,
            exposed_model TEXT,
            account TEXT,
            official_account_ref TEXT,
            client_key_id TEXT,
            client_key_name TEXT,
            target_id TEXT,
            selection TEXT,
            status INTEGER,
            result_class TEXT,
            header_ms REAL,
            ttft_ms REAL,
            latency_ms REAL,
            streaming INTEGER,
            attempt_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cached_input_tokens INTEGER,
            total_tokens INTEGER,
            usage_source TEXT,
            estimated_usd REAL,
            error_class TEXT,
            trace_hash TEXT,
            first_seen_utc TEXT,
            last_seen_utc TEXT
        )
        """
    )
    columns = {str(r[1]) for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
    if "official_account_ref" not in columns:
        conn.execute("ALTER TABLE requests ADD COLUMN official_account_ref TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_official_account_ref ON requests(official_account_ref)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_time ON requests(time_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_account ON requests(account)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_model ON requests(model)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO meta(key,value) VALUES('schema_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    request_id = str(row.get("request_id") or "").strip()
    path = str(row.get("path") or "").strip()
    if not request_id or not path:
        return None
    status = as_int(row.get("status"), 0)
    result_class = "SUCCESS" if 200 <= status < 400 else ("ERROR" if status else "UNKNOWN")
    request_type = str(row.get("request_type") or "").strip()
    if not request_type:
        p = path.lower()
        if p.endswith("/models"):
            request_type = "models"
        elif "responses" in p:
            request_type = "responses"
        elif "chat/completions" in p:
            request_type = "chat"
        else:
            request_type = "other"
    safe = {
        "request_id": request_id,
        "time_utc": iso_utc(row.get("time")),
        "protocol": str(row.get("protocol") or ""),
        "method": str(row.get("method") or ""),
        "path": path[:500],
        "request_type": request_type[:80],
        "model": str(row.get("model") or "")[:200],
        "exposed_model": str(row.get("exposed_model") or "")[:200],
        "account": str(row.get("account") or "")[:320],
        "official_account_ref": official_account_ref(row),
        "client_key_id": str(row.get("client_key_id") or "")[:160],
        "client_key_name": str(row.get("client_key_name") or "")[:200],
        "target_id": str(row.get("target_id") or "")[:200],
        "selection": str(row.get("selection") or "")[:200],
        "status": status,
        "result_class": result_class,
        "header_ms": as_float(row.get("header_ms")),
        "ttft_ms": as_float(row.get("ttft_ms")),
        "latency_ms": as_float(row.get("latency_ms")),
        "streaming": 1 if bool(row.get("streaming")) else 0,
        "attempt_count": max(0, as_int(row.get("attempt_count"))),
        "input_tokens": max(0, as_int(row.get("input_tokens"))),
        "output_tokens": max(0, as_int(row.get("output_tokens"))),
        "cached_input_tokens": max(0, as_int(row.get("cached_input_tokens"))),
        "total_tokens": max(0, as_int(row.get("total_tokens"))),
        "usage_source": str(row.get("usage_source") or "")[:120],
        "estimated_usd": max(0.0, as_float(row.get("estimated_usd"))),
        "error_class": str(row.get("error_class") or "")[:200],
    }
    digest_source = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe["trace_hash"] = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    return safe


def sync_trace(conn: sqlite3.Connection, trace: Path, max_lines: int) -> dict[str, Any]:
    added = updated = unchanged = invalid = 0
    now = utcnow().isoformat()
    sql = """
    INSERT INTO requests(
        request_id,time_utc,protocol,method,path,request_type,model,exposed_model,account,official_account_ref,
        client_key_id,client_key_name,target_id,selection,status,result_class,header_ms,ttft_ms,
        latency_ms,streaming,attempt_count,input_tokens,output_tokens,cached_input_tokens,total_tokens,
        usage_source,estimated_usd,error_class,trace_hash,first_seen_utc,last_seen_utc
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(request_id) DO UPDATE SET
        time_utc=excluded.time_utc, protocol=excluded.protocol, method=excluded.method,
        path=excluded.path, request_type=excluded.request_type, model=excluded.model,
        exposed_model=excluded.exposed_model, account=excluded.account,
        official_account_ref=excluded.official_account_ref, client_key_id=excluded.client_key_id, client_key_name=excluded.client_key_name,
        target_id=excluded.target_id, selection=excluded.selection, status=excluded.status,
        result_class=excluded.result_class, header_ms=excluded.header_ms, ttft_ms=excluded.ttft_ms,
        latency_ms=excluded.latency_ms, streaming=excluded.streaming,
        attempt_count=excluded.attempt_count, input_tokens=excluded.input_tokens,
        output_tokens=excluded.output_tokens, cached_input_tokens=excluded.cached_input_tokens,
        total_tokens=excluded.total_tokens, usage_source=excluded.usage_source,
        estimated_usd=excluded.estimated_usd, error_class=excluded.error_class,
        trace_hash=excluded.trace_hash, last_seen_utc=excluded.last_seen_utc
    """
    for line in tail_lines(trace, max_lines):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict):
                invalid += 1
                continue
            row = normalize_row(raw)
            if row is None:
                continue
        except Exception:
            invalid += 1
            continue
        prior = conn.execute("SELECT trace_hash FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
        if prior is None:
            added += 1
        elif prior[0] != row["trace_hash"]:
            updated += 1
        else:
            unchanged += 1
        vals = [
            row["request_id"], row["time_utc"], row["protocol"], row["method"], row["path"],
            row["request_type"], row["model"], row["exposed_model"], row["account"], row["official_account_ref"],
            row["client_key_id"], row["client_key_name"], row["target_id"], row["selection"],
            row["status"], row["result_class"], row["header_ms"], row["ttft_ms"], row["latency_ms"],
            row["streaming"], row["attempt_count"], row["input_tokens"], row["output_tokens"],
            row["cached_input_tokens"], row["total_tokens"], row["usage_source"], row["estimated_usd"],
            row["error_class"], row["trace_hash"], now, now,
        ]
        conn.execute(sql, vals)
    conn.execute(
        "INSERT INTO meta(key,value) VALUES('last_sync_utc',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (now,),
    )
    conn.execute(
        "INSERT INTO meta(key,value) VALUES('trace_path',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(trace),),
    )
    conn.commit()
    return {"added": added, "updated": updated, "unchanged": unchanged, "invalid": invalid, "trace_exists": trace.exists()}


def rows_for_window(conn: sqlite3.Connection, cutoff: str | None) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    if cutoff:
        return conn.execute("SELECT * FROM requests WHERE time_utc>=? ORDER BY time_utc DESC", (cutoff,)).fetchall()
    return conn.execute("SELECT * FROM requests ORDER BY time_utc DESC").fetchall()


def summarize(rows: list[sqlite3.Row]) -> dict[str, Any]:
    total = len(rows)
    success = sum(1 for r in rows if 200 <= as_int(r["status"]) < 400)
    failed = sum(1 for r in rows if as_int(r["status"]) >= 400)
    tokens = sum(as_int(r["total_tokens"]) for r in rows)
    token_rows = sum(1 for r in rows if as_int(r["total_tokens"]) > 0)
    cost = sum(as_float(r["estimated_usd"]) for r in rows)
    cost_rows = sum(1 for r in rows if as_float(r["estimated_usd"]) > 0)
    lat = [as_float(r["latency_ms"]) for r in rows if as_float(r["latency_ms"]) > 0]
    retry_requests = sum(1 for r in rows if as_int(r["attempt_count"]) > 1)
    http_429 = sum(1 for r in rows if as_int(r["status"]) == 429)
    http_401_403 = sum(1 for r in rows if as_int(r["status"]) in (401, 403))
    server_errors = sum(1 for r in rows if 500 <= as_int(r["status"]) < 600)
    return {
        "requests": total,
        "success": success,
        "failed": failed,
        "success_rate_pct": round(success * 100.0 / total, 2) if total else 0.0,
        "retry_requests": retry_requests,
        "retry_rate_pct": round(retry_requests * 100.0 / total, 2) if total else 0.0,
        "http_429": http_429,
        "http_401_403": http_401_403,
        "server_errors": server_errors,
        "total_tokens": tokens,
        "token_coverage_pct": round(token_rows * 100.0 / total, 2) if total else 0.0,
        "estimated_usd": round(cost, 6),
        "cost_coverage_pct": round(cost_rows * 100.0 / total, 2) if total else 0.0,
        "latency_p50_ms": round(percentile(lat, 0.50), 1),
        "latency_p95_ms": round(percentile(lat, 0.95), 1),
        "latency_p99_ms": round(percentile(lat, 0.99), 1),
    }


def group_stats(rows: list[sqlite3.Row], field: str, limit: int = 50) -> list[dict[str, Any]]:
    buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = str(r[field] or "").strip() or "—"
        buckets[key].append(r)
    result = []
    for key, group in buckets.items():
        item = {"name": key}
        item.update(summarize(group))
        result.append(item)
    result.sort(key=lambda x: (-x["requests"], x["name"].lower()))
    return result[:limit]


def group_account_stats(rows: list[sqlite3.Row], limit: int = 50) -> list[dict[str, Any]]:
    """Prefer stable official-account refs so delete/re-add does not split usage history."""
    buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
    labels: dict[str, str] = {}
    for r in rows:
        ref = str(r["official_account_ref"] or "").strip() if "official_account_ref" in r.keys() else ""
        label = str(r["account"] or "").strip() or "—"
        key = ref or label
        buckets[key].append(r)
        labels.setdefault(key, label)
    result: list[dict[str, Any]] = []
    for key, group in buckets.items():
        item = {"name": key, "display_account": labels.get(key, "—"), "identity_basis": "OFFICIAL_ACCOUNT_REF" if key.startswith("oaid-") else "LEGACY_ACCOUNT_LABEL"}
        item.update(summarize(group))
        result.append(item)
    result.sort(key=lambda x: (-x["requests"], x["name"].lower()))
    return result[:limit]


def adaptive_pool(account_stats: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for item in account_stats:
        if item["name"] == "—":
            continue
        req = int(item["requests"])
        success = float(item["success_rate_pct"])
        p95 = float(item["latency_p95_ms"])
        # Stable, conservative advisory score. Historical only; never mutates Router state.
        confidence = min(1.0, req / 20.0)
        latency_component = max(0.0, 20.0 - min(20.0, p95 / 500.0)) if p95 else 10.0
        score = (success * 0.70 + latency_component + 10.0 * confidence)
        score = max(0.0, min(100.0, score))
        candidates.append({
            "account": item["name"],
            "score": round(score, 1),
            "requests": req,
            "success_rate_pct": success,
            "latency_p95_ms": p95,
            "confidence": "HIGH" if req >= 20 else ("MEDIUM" if req >= 5 else "LOW"),
        })
    candidates.sort(key=lambda x: (-x["score"], -x["requests"], x["account"].lower()))
    best = candidates[0] if candidates else None
    return {
        "mode": "HISTORICAL_SIGNAL",
        "recommended_account": best["account"] if best else "",
        "recommended_score": best["score"] if best else 0.0,
        "candidates": candidates[:8],
        "note": "Tín hiệu lịch sử 7 ngày; v25.27 Adaptive Router kết hợp quota/health/role/hysteresis trước mọi apply.",
    }


def build_snapshot(conn: sqlite3.Connection, sync: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utcnow()
    windows = {
        "hour": now - timedelta(hours=1),
        "day": now - timedelta(hours=24),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "all": None,
    }
    output: dict[str, Any] = {}
    rows_cache: dict[str, list[sqlite3.Row]] = {}
    for name, cutoff_dt in windows.items():
        cutoff = cutoff_dt.isoformat() if cutoff_dt else None
        rows = rows_for_window(conn, cutoff)
        rows_cache[name] = rows
        output[name] = {"total": summarize(rows)}
    hour = rows_cache["hour"]
    day = rows_cache["day"]
    week = rows_cache["week"]
    by_account_hour = group_account_stats(hour)
    by_account_day = group_account_stats(day)
    by_account = group_account_stats(week)
    by_model = group_stats(week, "model")
    by_key = group_stats(week, "client_key_name")
    by_type = group_stats(week, "request_type")
    recent = []
    for r in rows_cache["all"][:50]:
        recent.append({
            "time": r["time_utc"], "request_id": r["request_id"], "account": r["account"],
            "official_account_ref": r["official_account_ref"] if "official_account_ref" in r.keys() else "",
            "model": r["model"], "status": r["status"], "latency_ms": r["latency_ms"],
            "total_tokens": r["total_tokens"], "estimated_usd": r["estimated_usd"],
            "request_type": r["request_type"], "selection": r["selection"],
            "attempt_count": r["attempt_count"], "error_class": r["error_class"],
            "target_id": r["target_id"], "client_key_name": r["client_key_name"],
        })
    meta = {r[0]: r[1] for r in conn.execute("SELECT key,value FROM meta").fetchall()}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": now.isoformat(),
        "sync": sync or {},
        "meta": meta,
        "windows": output,
        "by_account_hour": by_account_hour,
        "by_account_day": by_account_day,
        "by_account_week": by_account,
        "by_model_week": by_model,
        "by_client_key_week": by_key,
        "by_request_type_week": by_type,
        "adaptive_pool": adaptive_pool(by_account),
        "recent": recent,
        "privacy": {
            "request_body_stored": False,
            "oauth_token_stored": False,
            "api_key_stored": False,
            "cookie_stored": False,
            "official_account_id_raw_stored": False,
            "note": "Ledger chỉ lưu metadata Router; official account ID nếu có được SHA-256 thành pseudonymous ref trước khi lưu.",
        },
    }


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("sync", "status"), default="sync")
    ap.add_argument("--trace", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--latest", required=True)
    ap.add_argument("--max-lines", type=int, default=200000)
    ap.add_argument("--output")
    args = ap.parse_args()
    trace = Path(args.trace)
    db = Path(args.db)
    latest = Path(args.latest)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=15)
    try:
        init_db(conn)
        sync = sync_trace(conn, trace, max(1000, min(1_000_000, args.max_lines))) if args.mode == "sync" else None
        snap = build_snapshot(conn, sync)
        atomic_json(latest, snap)
        out = {"ok": True, "mode": args.mode, "data": snap, "db": str(db), "latest": str(latest)}
    except Exception as exc:
        out = {"ok": False, "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
