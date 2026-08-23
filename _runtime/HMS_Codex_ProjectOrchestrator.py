# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_VERSION = "25.42"
SCHEMA_VERSION = 1
SECRET_KEY_TOKENS = (
    "token", "secret", "password", "cookie", "authorization", "api_key",
    "apikey", "access_key", "refresh_token", "access_token", "client_secret",
    "localapikey", "router_key", "credential_blob",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(v: Any) -> str:
    return str(v or "").strip()


def path_key(v: Any) -> str:
    s = norm(v)
    if not s:
        return ""
    try:
        s = os.path.abspath(os.path.normpath(s))
    except Exception:
        pass
    return os.path.normcase(s).replace("/", "\\").rstrip("\\").lower()


def read_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def secret_scan(obj: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            low = ks.lower().replace("-", "_")
            p = f"{prefix}.{ks}" if prefix else ks
            if any(tok in low for tok in SECRET_KEY_TOKENS):
                hits.append(p)
            hits.extend(secret_scan(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(secret_scan(v, f"{prefix}[{i}]"))
    return hits


def plan_hash(plan: dict[str, Any]) -> str:
    raw = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def classify_project(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    if not bool(row.get("project_exists")):
        blockers.append("PROJECT_MISSING")
    if not bool(row.get("affinity_mapped", True)):
        blockers.append("PROJECT_UNMAPPED")
    if not norm(row.get("instance_id")):
        blockers.append("INSTANCE_MISSING")
    if not bool(row.get("identity_ok")):
        blockers.append("IDENTITY_ISOLATION_BLOCKED")
    if not bool(row.get("security_ok")):
        blockers.append("SECURITY_HARD_GATE_BLOCKED")
    if bool(row.get("port_conflict_foreign")):
        blockers.append("FOREIGN_PORT_OWNER")

    affinity_state = norm(row.get("affinity_state")).upper()
    if affinity_state not in {"RUNNING", "READY", "SEAMLESS_FALLBACK_READY"}:
        blockers.append("AFFINITY_" + (affinity_state or "UNKNOWN"))

    if bool(row.get("binding_drift")):
        blockers.append("BINDING_DRIFT")
    if bool(row.get("model_policy_drift")):
        warnings.append("MODEL_POLICY_DRIFT_WILL_BE_REAPPLIED")
    if not bool(row.get("model_configured")):
        warnings.append("MODEL_POLICY_NOT_CONFIGURED_USING_EXISTING_CONFIG")
    if not bool(row.get("router_online")) and bool(row.get("client_running")):
        blockers.append("CLIENT_RUNNING_ROUTER_OFFLINE")
    elif not bool(row.get("router_online")):
        warnings.append("ROUTER_WILL_START_WITH_INSTANCE")

    hourly = row.get("hourly_remaining")
    weekly = row.get("weekly_remaining")
    try:
        if hourly is not None and float(hourly) <= 3:
            warnings.append("PRIMARY_5H_QUOTA_CRITICAL")
    except Exception:
        pass
    try:
        if weekly is not None and float(weekly) <= 3:
            warnings.append("PRIMARY_7D_QUOTA_CRITICAL")
    except Exception:
        pass

    running = bool(row.get("client_running"))
    steps: list[dict[str, Any]] = []
    if not blockers:
        if running:
            steps.append({"step": "FOCUS_INSTANCE", "mutation": False, "description": "Đưa managed Codex instance đang chạy lên trước."})
        else:
            steps.extend([
                {"step": "VERIFY_PROJECT_AFFINITY", "mutation": False, "description": "Xác nhận Project ↔ Instance ↔ Account binding."},
                {"step": "VERIFY_IDENTITY_ISOLATION", "mutation": False, "description": "Xác minh identity fingerprint và path isolation."},
                {"step": "VERIFY_SECURITY_HARD_GATE", "mutation": False, "description": "Xác minh protected secret refs, reparse guard và integrity seals."},
                {"step": "SYNC_SEAMLESS_ROUTER", "mutation": True, "description": "Đồng bộ primary/fallback pool phía sau stable endpoint."},
            ])
            if bool(row.get("model_configured")):
                steps.append({"step": "APPLY_MODEL_POLICY", "mutation": True, "description": "Áp dụng model/reasoning policy vào isolated config.toml và readback."})
            steps.extend([
                {"step": "START_MANAGED_CODEX", "mutation": True, "description": "Khởi động Router + Codex bằng ownership guard."},
                {"step": "VERIFY_PROCESS_OWNERSHIP", "mutation": False, "description": "Xác nhận client/router PID thuộc managed instance."},
            ])

    readiness = "BLOCKED" if blockers else ("RUNNING" if running else ("ATTENTION" if warnings else "READY"))
    out = {
        "name": norm(row.get("name")) or Path(norm(row.get("project_dir")) or "project").name,
        "project_dir": norm(row.get("project_dir")),
        "instance_id": norm(row.get("instance_id")),
        "instance_name": norm(row.get("instance_name")),
        "account": norm(row.get("account")),
        "fallback_account": norm(row.get("fallback_account")),
        "affinity_state": affinity_state,
        "readiness": readiness,
        "one_click_ready": not blockers,
        "client_running": running,
        "router_online": bool(row.get("router_online")),
        "router_endpoint": norm(row.get("router_endpoint")),
        "identity_ok": bool(row.get("identity_ok")),
        "identity_fingerprint": norm(row.get("identity_fingerprint")),
        "security_ok": bool(row.get("security_ok")),
        "model": norm(row.get("model")),
        "reasoning": norm(row.get("reasoning")) or "—",
        "profile": norm(row.get("profile")) or "BALANCED",
        "model_configured": bool(row.get("model_configured")),
        "account_health": row.get("account_health"),
        "hourly_remaining": hourly,
        "weekly_remaining": weekly,
        "blockers": blockers,
        "warnings": warnings,
        "plan": steps,
        "source_reason": norm(row.get("reason")),
    }
    out["plan_hash"] = plan_hash({
        "project_dir": out["project_dir"], "instance_id": out["instance_id"],
        "account": out["account"], "router_endpoint": out["router_endpoint"],
        "model": out["model"], "reasoning": out["reasoning"],
        "steps": [s["step"] for s in steps], "blockers": blockers,
    })
    return out


def build_state(fleet: dict[str, Any]) -> dict[str, Any]:
    hits = secret_scan(fleet)
    if hits:
        raise ValueError("PROJECT_ORCHESTRATOR_SECRET_FIELD_REJECTED: " + ",".join(hits[:8]))
    projects = [classify_project(x) for x in (fleet.get("projects") or []) if isinstance(x, dict)]
    projects.sort(key=lambda x: (x["readiness"] == "BLOCKED", not x["client_running"], x["name"].lower()))
    summary = {
        "projects": len(projects),
        "running": sum(1 for x in projects if x["client_running"]),
        "ready": sum(1 for x in projects if x["one_click_ready"] and not x["client_running"]),
        "blocked": sum(1 for x in projects if not x["one_click_ready"]),
        "attention": sum(1 for x in projects if x["warnings"] and x["one_click_ready"]),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": utcnow(),
        "summary": summary,
        "projects": projects,
        "privacy": "NO_PROMPT_NO_REQUEST_BODY_NO_OAUTH_NO_API_KEY_NO_COOKIE",
        "invariants": [
            "Project Orchestrator does not change project affinity automatically.",
            "Identity Isolation and Security Hardening are hard gates before one-click launch.",
            "Stable endpoint and session affinity are preserved.",
            "Unowned processes are never killed by Project Orchestrator.",
            "Model policy is applied only when explicitly configured for the project.",
        ],
    }


def select_project(state: dict[str, Any], project_dir: str) -> dict[str, Any]:
    key = path_key(project_dir)
    if not key:
        raise ValueError("PROJECT_ORCHESTRATOR_PROJECT_REQUIRED")
    for row in state.get("projects") or []:
        if path_key(row.get("project_dir")) == key:
            return row
    raise ValueError("PROJECT_ORCHESTRATOR_PROJECT_NOT_FOUND")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "preflight"), required=True)
    ap.add_argument("--fleet", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--input")
    args = ap.parse_args()
    try:
        fleet = read_json(Path(args.fleet), {}) or {}
        state = build_state(fleet)
        if args.mode == "preflight":
            inp = read_json(Path(args.input) if args.input else None, {}) or {}
            hits = secret_scan(inp)
            if hits:
                raise ValueError("PROJECT_ORCHESTRATOR_INPUT_SECRET_REJECTED: " + ",".join(hits[:8]))
            selected = select_project(state, norm(inp.get("project_dir")))
            state["selected"] = selected
            state["preflight"] = {
                "ok": bool(selected.get("one_click_ready")),
                "project_dir": selected.get("project_dir"),
                "plan_hash": selected.get("plan_hash"),
                "blockers": selected.get("blockers") or [],
                "warnings": selected.get("warnings") or [],
            }
        atomic_json(Path(args.state), state)
        print(json.dumps({"ok": True, "mode": args.mode, "data": state}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "mode": args.mode, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
