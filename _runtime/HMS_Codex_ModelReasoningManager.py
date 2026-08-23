#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_VERSION = "25.74"
SCHEMA_VERSION = 2
SECRET_KEYS = {"token", "access_token", "refresh_token", "api_key", "cookie", "authorization", "password", "client_secret"}
EFFORTS = ("auto", "none", "low", "medium", "high", "xhigh", "max")
PROFILES = ("BALANCED", "FAST", "DEEP", "REVIEW", "TEST")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def norm(v: Any) -> str:
    return str(v or "").strip()


def path_key(v: Any) -> str:
    try:
        return os.path.normcase(os.path.abspath(os.path.normpath(norm(v))))
    except Exception:
        return norm(v).lower()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def secret_scan(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in SECRET_KEYS or any(x in lk for x in ("access_token", "refresh_token", "api_key", "client_secret", "password", "cookie")):
                hits.append(f"{path}.{k}")
            else:
                hits.extend(secret_scan(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(secret_scan(v, f"{path}[{i}]"))
    return hits


def efforts_for(model: str) -> list[str]:
    m = model.lower()
    if "gpt-5.6" in m:
        return ["auto", "none", "low", "medium", "high", "xhigh", "max"]
    if "gpt-5.3-codex" in m or "gpt-5.2-codex" in m:
        return ["auto", "low", "medium", "high", "xhigh"]
    if "gpt-5.2" in m or "gpt-5.1" in m:
        return ["auto", "none", "low", "medium", "high", "xhigh"]
    if "gpt-5" in m or "codex" in m:
        return ["auto", "low", "medium", "high"]
    return ["auto", "low", "medium", "high"]


def model_caps(model: str) -> dict[str, Any]:
    m = model.lower()
    return {
        "coding_likely": bool("codex" in m or m.startswith("gpt-5")),
        "reasoning_configurable": bool("gpt-5" in m or "codex" in m),
        "reasoning_efforts": efforts_for(model),
        "capability_source": "CONSERVATIVE_NAME_MATRIX",
    }


def fleet_maps(fleet: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    instances: dict[str, dict[str, Any]] = {}
    projects: dict[str, dict[str, Any]] = {}
    for x in fleet.get("instances") or []:
        if not isinstance(x, dict):
            continue
        iid = norm(x.get("id") or x.get("instance_id"))
        if iid:
            instances[iid] = x
    for p in fleet.get("projects") or []:
        if not isinstance(p, dict):
            continue
        pd = norm(p.get("project_dir") or p.get("projectDir"))
        if pd:
            projects[path_key(pd)] = p
    # Instance store itself is authoritative if project affinity did not emit a row.
    for iid, x in instances.items():
        pd = norm(x.get("project_dir") or x.get("projectDir"))
        if pd and path_key(pd) not in projects:
            projects[path_key(pd)] = {
                "name": norm(x.get("name")) or Path(pd).name,
                "project_dir": pd,
                "instance_id": iid,
                "preferred_account": norm(x.get("account_email") or x.get("accountEmail")),
            }
    return instances, projects


def analytics_model_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in report.get("model_recommendations") or []:
        if isinstance(row, dict) and norm(row.get("model")):
            out[norm(row.get("model"))] = row
    return out


def normalize_catalog(catalog: dict[str, Any], analytics: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    recs = analytics_model_map(analytics)
    rows = catalog.get("models") or catalog.get("data") or []
    for row in rows:
        if isinstance(row, str):
            mid, source, owner = row, "UNKNOWN", ""
        elif isinstance(row, dict):
            mid = norm(row.get("id") or row.get("model"))
            source = norm(row.get("source")) or "LIVE_ROUTER"
            owner = norm(row.get("owned_by") or row.get("owner"))
            context_window = row.get("context_window") or row.get("context_window_tokens")
            compact_limit = row.get("auto_compact_token_limit") or row.get("compaction_threshold_tokens")
        else:
            continue
        if not mid:
            continue
        cur = seen.setdefault(mid, {"id": mid, "sources": [], "owned_by": owner, "context_window_tokens": None, "auto_compact_token_limit": None})
        if isinstance(row, dict):
            try:
                cw = int(context_window) if context_window is not None else None
                ac = int(compact_limit) if compact_limit is not None else None
            except Exception:
                cw = ac = None
            if cw is not None and cw > 0:
                cur["context_window_tokens"] = cw
            if ac is not None and ac > 0:
                cur["auto_compact_token_limit"] = ac
        if source and source not in cur["sources"]:
            cur["sources"].append(source)
        if not cur.get("owned_by") and owner:
            cur["owned_by"] = owner
    out: list[dict[str, Any]] = []
    for mid in sorted(seen, key=str.lower):
        row = seen[mid]
        row.update(model_caps(mid))
        cw = row.get("context_window_tokens")
        ac = row.get("auto_compact_token_limit")
        if cw and ac and int(ac) >= int(cw):
            # Fail soft on malformed upstream metadata; never invent a compaction threshold.
            row["auto_compact_token_limit"] = None
            row["runtime_metadata_state"] = "INVALID_COMPACTION_THRESHOLD_IGNORED"
        elif cw or ac:
            row["runtime_metadata_state"] = "LIVE_METADATA_PRESENT"
        else:
            row["runtime_metadata_state"] = "NOT_EXPOSED"
        rec = recs.get(mid) or {}
        row["recommended_account"] = norm(rec.get("recommended_account"))
        row["analytics_quality_score"] = rec.get("quality_score")
        row["analytics_samples"] = rec.get("requests")
        row["analytics_confidence"] = norm(rec.get("confidence")) or "NONE"
        out.append(row)
    return out


def load_policy(path: Path) -> dict[str, Any]:
    p = read_json(path, {}) or {}
    if not isinstance(p, dict):
        p = {}
    p.setdefault("schema_version", SCHEMA_VERSION)
    p.setdefault("engine_version", ENGINE_VERSION)
    p.setdefault("projects", [])
    return p


def policy_map(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for p in policy.get("projects") or []:
        if isinstance(p, dict) and norm(p.get("project_dir")):
            out[path_key(p.get("project_dir"))] = p
    return out


def default_reasoning(config: dict[str, Any]) -> str:
    x = norm(config.get("default_reasoning") or "medium").lower()
    return x if x in EFFORTS else "medium"


def build_state(fleet: dict[str, Any], catalog: dict[str, Any], analytics: dict[str, Any], policy: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    instances, projects = fleet_maps(fleet)
    models = normalize_catalog(catalog, analytics)
    pmap = policy_map(policy)
    project_rows: list[dict[str, Any]] = []
    configured = 0
    for key, p in sorted(projects.items(), key=lambda kv: norm(kv[1].get("name") or kv[1].get("project_dir")).lower()):
        pd = norm(p.get("project_dir") or p.get("projectDir"))
        iid = norm(p.get("instance_id") or p.get("instanceId"))
        inst = instances.get(iid, {})
        pol = pmap.get(key, {})
        model = norm(pol.get("model"))
        if model:
            configured += 1
        project_rows.append({
            "name": norm(p.get("name")) or norm(inst.get("name")) or Path(pd).name,
            "project_dir": pd,
            "instance_id": iid,
            "account": norm(p.get("preferred_account") or inst.get("account_email") or inst.get("accountEmail")),
            "identity_ok": bool(inst.get("identity_ok", True)),
            "client_running": bool(inst.get("client_running", False)),
            "model": model,
            "reasoning": norm(pol.get("reasoning")) or default_reasoning(config),
            "profile": norm(pol.get("profile")) or "BALANCED",
            "last_applied_utc": norm(pol.get("last_applied_utc")),
            "last_config_sha256": norm(pol.get("last_config_sha256")),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": utcnow(),
        "summary": {
            "models": len(models),
            "projects": len(project_rows),
            "configured_projects": configured,
            "live_catalog": bool(models),
        },
        "models": models,
        "projects": project_rows,
        "privacy": "NO_PROMPT_NO_OAUTH_NO_API_KEY_NO_COOKIE",
        "notes": [
            "Model/reasoning policy is per project/instance.",
            "Stable endpoint, provider binding and session affinity are not changed.",
            "Reasoning capability matrix is conservative; runtime model acceptance remains authoritative.",
        ],
    }


def validate_policy_input(inp: dict[str, Any], fleet: dict[str, Any], catalog_models: list[dict[str, Any]], config: dict[str, Any]) -> tuple[str, str, str, str, dict[str, Any]]:
    hits = secret_scan(inp)
    if hits:
        raise ValueError("MODEL_POLICY_SECRET_FIELD_REJECTED: " + ",".join(hits[:5]))
    project = norm(inp.get("project_dir"))
    if not project:
        raise ValueError("MODEL_POLICY_PROJECT_REQUIRED")
    instances, projects = fleet_maps(fleet)
    p = projects.get(path_key(project))
    if not p:
        raise ValueError("MODEL_POLICY_PROJECT_NOT_BOUND")
    iid = norm(p.get("instance_id") or p.get("instanceId"))
    if iid not in instances:
        raise ValueError("MODEL_POLICY_INSTANCE_MISSING")
    model = norm(inp.get("model"))
    if not model:
        raise ValueError("MODEL_POLICY_MODEL_REQUIRED")
    model_map = {x["id"]: x for x in catalog_models}
    require_live = bool(config.get("require_live_model", True))
    if require_live and model_map and model not in model_map:
        raise ValueError("MODEL_POLICY_MODEL_NOT_IN_LIVE_CATALOG")
    reasoning = norm(inp.get("reasoning") or default_reasoning(config)).lower()
    if reasoning not in EFFORTS:
        raise ValueError("MODEL_POLICY_REASONING_INVALID")
    allowed = efforts_for(model)
    if reasoning not in allowed:
        raise ValueError("MODEL_POLICY_REASONING_NOT_SUPPORTED_BY_MATRIX")
    profile = norm(inp.get("profile") or "BALANCED").upper()
    if profile not in PROFILES:
        raise ValueError("MODEL_POLICY_PROFILE_INVALID")
    return project, iid, model, reasoning, instances[iid]


def set_policy(policy_path: Path, inp: dict[str, Any], fleet: dict[str, Any], catalog: dict[str, Any], analytics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    policy = load_policy(policy_path)
    models = normalize_catalog(catalog, analytics)
    project, iid, model, reasoning, inst = validate_policy_input(inp, fleet, models, config)
    profile = norm(inp.get("profile") or "BALANCED").upper()
    rows = list(policy.get("projects") or [])
    key = path_key(project)
    found = False
    for row in rows:
        if isinstance(row, dict) and path_key(row.get("project_dir")) == key:
            row.update({"project_dir": project, "instance_id": iid, "model": model, "reasoning": reasoning, "profile": profile, "updated_utc": utcnow()})
            found = True
            break
    if not found:
        rows.append({"project_dir": project, "project_key": sha256_text(key), "instance_id": iid, "model": model, "reasoning": reasoning, "profile": profile, "updated_utc": utcnow(), "last_applied_utc": "", "last_config_sha256": ""})
    policy["projects"] = rows
    policy["updated_utc"] = utcnow()
    if secret_scan(policy):
        raise ValueError("MODEL_POLICY_SECRET_SCAN_FAILED")
    atomic_json(policy_path, policy)
    return build_state(fleet, catalog, analytics, policy, config)


def replace_root_toml(text: str, model: str, reasoning: str) -> str:
    lines = text.splitlines()
    first_section = next((idx for idx, line in enumerate(lines) if line.strip().startswith("[")), len(lines))
    root = lines[:first_section]
    tail = lines[first_section:]
    root = [line for line in root if not re.match(r"^\s*(model|model_reasoning_effort)\s*=", line)]
    insert_at = 1 if root and re.match(r"^\s*model_provider\s*=", root[0]) else 0
    inject = [f'model = {json.dumps(model)}']
    if reasoning != "auto":
        inject.append(f'model_reasoning_effort = {json.dumps(reasoning)}')
    root[insert_at:insert_at] = inject
    out = "\n".join(root + tail).rstrip() + "\n"
    return out


def config_contract(text: str, port: int) -> tuple[bool, str]:
    if not re.search(r'^\s*model_provider\s*=\s*["\']hms_instance_router["\']\s*$', text, re.M):
        return False, "MODEL_PROVIDER_MISMATCH"
    expected = f"http://127.0.0.1:{port}/v1"
    m = re.search(r'^\s*base_url\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    if not m or m.group(1).strip() != expected:
        return False, "STABLE_ENDPOINT_MISMATCH"
    return True, "OK"


def safe_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def apply_policy(policy_path: Path, inp: dict[str, Any], fleet: dict[str, Any], catalog: dict[str, Any], analytics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    policy = load_policy(policy_path)
    pmap = policy_map(policy)
    project = norm(inp.get("project_dir"))
    row = pmap.get(path_key(project))
    if not row:
        raise ValueError("MODEL_POLICY_NOT_CONFIGURED")
    models = normalize_catalog(catalog, analytics)
    project, iid, model, reasoning, inst = validate_policy_input(row, fleet, models, config)
    if not bool(inst.get("identity_ok", True)):
        raise ValueError("IDENTITY_ISOLATION_NOT_PASS")
    root = Path(norm(inst.get("root")))
    codex_home = Path(norm(inst.get("codex_home") or inst.get("codexHome")))
    if not root or not codex_home or not safe_under(codex_home, root):
        raise ValueError("MODEL_POLICY_PATH_BOUNDARY_FAILED")
    cfg = codex_home / "config.toml"
    if not cfg.exists() or cfg.is_symlink():
        raise ValueError("MODEL_POLICY_CONFIG_INVALID")
    text = cfg.read_text(encoding="utf-8-sig")
    ok, reason = config_contract(text, int(inst.get("port") or 0))
    if not ok:
        raise ValueError(reason)
    updated = replace_root_toml(text, model, reasoning)
    ok2, reason2 = config_contract(updated, int(inst.get("port") or 0))
    if not ok2:
        raise ValueError("POSTWRITE_" + reason2)
    backup_dir = codex_home / "model-policy-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"config.toml.{stamp}.bak"
    shutil.copy2(cfg, backup)
    tmp = cfg.with_suffix(".toml.v2537.tmp")
    tmp.write_text(updated, encoding="utf-8")
    os.replace(tmp, cfg)
    final = cfg.read_text(encoding="utf-8-sig")
    ok3, reason3 = config_contract(final, int(inst.get("port") or 0))
    if not ok3 or f'model = "{model}"' not in final:
        shutil.copy2(backup, cfg)
        raise ValueError("MODEL_POLICY_READBACK_FAILED:" + reason3)
    config_hash = hashlib.sha256(final.encode("utf-8")).hexdigest()
    row["last_applied_utc"] = utcnow()
    row["last_config_sha256"] = config_hash
    row["last_backup"] = str(backup)
    policy["updated_utc"] = utcnow()
    atomic_json(policy_path, policy)
    state = build_state(fleet, catalog, analytics, policy, config)
    state["apply_result"] = {
        "project_dir": project,
        "instance_id": iid,
        "model": model,
        "reasoning": reasoning,
        "config_sha256": config_hash,
        "backup": str(backup),
        "restart_recommended": bool(inst.get("client_running", False)),
        "stable_endpoint_preserved": True,
        "provider_preserved": True,
    }
    return state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "discover", "set-policy", "apply"), required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--catalog")
    ap.add_argument("--analytics")
    ap.add_argument("--input")
    ap.add_argument("--config-json", default="{}")
    args = ap.parse_args()
    try:
        config = json.loads(args.config_json or "{}")
        fleet = read_json(Path(args.fleet) if args.fleet else None, {}) or {}
        catalog = read_json(Path(args.catalog) if args.catalog else None, {}) or {}
        analytics = read_json(Path(args.analytics) if args.analytics else None, {}) or {}
        policy_path = Path(args.policy)
        policy = load_policy(policy_path)
        if args.mode == "set-policy":
            inp = read_json(Path(args.input) if args.input else None, {}) or {}
            state = set_policy(policy_path, inp, fleet, catalog, analytics, config)
        elif args.mode == "apply":
            inp = read_json(Path(args.input) if args.input else None, {}) or {}
            state = apply_policy(policy_path, inp, fleet, catalog, analytics, config)
        else:
            state = build_state(fleet, catalog, analytics, policy, config)
        atomic_json(Path(args.state), state)
        print(json.dumps({"ok": True, "mode": args.mode, "data": state}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "mode": args.mode, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
