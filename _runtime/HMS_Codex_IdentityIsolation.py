#!/usr/bin/env python3
"""HMS-AI-ROUTER v25.36 - Codex identity isolation auditor.

The auditor is deliberately metadata-only. It never parses credential contents and never
serializes OAuth/API secrets. It validates filesystem boundaries, binding identity,
endpoint ownership and per-instance uniqueness, then emits a deterministic fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.36"
SECRET_RE = re.compile(r"(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|client[_-]?secret|password|cookie|authorization|bearer)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_path(value: str) -> str:
    if not value:
        return ""
    # ntpath semantics are more useful for Windows paths even when synthetic tests run elsewhere.
    value = os.path.expandvars(os.path.expanduser(str(value).strip()))
    return os.path.normcase(os.path.normpath(os.path.abspath(value)))


def path_key(value: str) -> str:
    return hashlib.sha256(norm_path(value).encode("utf-8", "replace")).hexdigest()


def sha_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_within(child: str, parent: str) -> bool:
    try:
        c = Path(norm_path(child))
        p = Path(norm_path(parent))
        return c == p or p in c.parents
    except Exception:
        return False


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def read_binding(root: Path) -> tuple[dict[str, Any] | None, str]:
    for name in ("binding-v2536.json", "binding-v2530.json", "binding-v2529.json", "binding-v2528.json"):
        p = root / name
        if p.is_file():
            try:
                data = load_json(p)
                return (data if isinstance(data, dict) else None), name
            except Exception:
                return None, name
    return None, ""


def config_endpoint(codex_home: Path) -> str:
    p = codex_home / "config.toml"
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r'(?im)^\s*base_url\s*=\s*["\']([^"\']+)["\']', text)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def safe_binding(binding: dict[str, Any] | None) -> bool:
    if not binding:
        return True
    stack = [binding]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for k, v in item.items():
                if SECRET_RE.search(str(k)):
                    return False
                stack.append(v)
        elif isinstance(item, list):
            stack.extend(item)
    return True


def audit_instance(inst: dict[str, Any], all_instances: list[dict[str, Any]], strict: bool = True) -> dict[str, Any]:
    iid = str(inst.get("id") or "").strip()
    account = str(inst.get("accountEmail") or "").strip().lower()
    project = str(inst.get("projectDir") or "").strip()
    root_s = str(inst.get("root") or "").strip()
    home_s = str(inst.get("codexHome") or "").strip()
    app_s = str(inst.get("appData") or "").strip()
    router_s = str(inst.get("routerDir") or "").strip()
    port = int(inst.get("port") or 0)
    launch_mode = str(inst.get("launchMode") or "").strip().lower()

    issues: list[str] = []
    warnings: list[str] = []
    if not iid:
        issues.append("INSTANCE_ID_MISSING")
    if not account or "@" not in account:
        issues.append("ACCOUNT_IDENTITY_INVALID")
    if not project:
        issues.append("PROJECT_IDENTITY_MISSING")
    if port < 1024 or port > 65535:
        issues.append("PORT_INVALID")
    if launch_mode not in {"cli", "desktop"}:
        issues.append("LAUNCH_MODE_INVALID")

    paths = {"root": root_s, "codex_home": home_s, "app_data": app_s, "router_dir": router_s}
    path_norm = {k: norm_path(v) for k, v in paths.items()}
    for key, raw in paths.items():
        if not raw:
            issues.append(key.upper() + "_MISSING")
        elif not Path(raw).is_dir():
            issues.append(key.upper() + "_NOT_DIRECTORY")

    root = Path(root_s) if root_s else Path(".")
    if strict and root_s:
        for key in ("codex_home", "app_data", "router_dir"):
            if path_norm[key] and not is_within(paths[key], root_s):
                issues.append(key.upper() + "_OUTSIDE_INSTANCE_ROOT")
    inner = [path_norm[k] for k in ("codex_home", "app_data", "router_dir") if path_norm[k]]
    if len(inner) != len(set(inner)):
        issues.append("INSTANCE_BOUNDARY_PATH_COLLISION")

    endpoint = f"http://127.0.0.1:{port}/v1" if port else ""
    found_endpoint = config_endpoint(Path(home_s)) if home_s else ""
    if endpoint and found_endpoint and found_endpoint.rstrip("/") != endpoint.rstrip("/"):
        issues.append("CODEX_CONFIG_ENDPOINT_MISMATCH")
    elif endpoint and not found_endpoint:
        issues.append("CODEX_CONFIG_ENDPOINT_MISSING")

    binding, binding_name = read_binding(root)
    if binding is None:
        issues.append("IDENTITY_BINDING_MISSING_OR_INVALID")
    else:
        if str(binding.get("instance_id") or "") != iid:
            issues.append("IDENTITY_BINDING_INSTANCE_MISMATCH")
        bacc = str(binding.get("account_email") or binding.get("primary_account") or "").strip().lower()
        if bacc and bacc != account:
            issues.append("IDENTITY_BINDING_ACCOUNT_MISMATCH")
        bproj = str(binding.get("project_dir") or "").strip()
        if bproj and norm_path(bproj) != norm_path(project):
            issues.append("IDENTITY_BINDING_PROJECT_MISMATCH")
        try:
            if int(binding.get("port") or 0) != port:
                issues.append("IDENTITY_BINDING_PORT_MISMATCH")
        except Exception:
            issues.append("IDENTITY_BINDING_PORT_INVALID")
        if not safe_binding(binding):
            issues.append("IDENTITY_BINDING_SECRET_FIELD_PRESENT")

    # Fleet collision audit: no boundary directory may be shared/nested across instances.
    for other in all_instances:
        if other is inst or str(other.get("id") or "") == iid:
            continue
        oid = str(other.get("id") or "")
        other_paths = {
            "root": str(other.get("root") or ""),
            "codex_home": str(other.get("codexHome") or ""),
            "app_data": str(other.get("appData") or ""),
            "router_dir": str(other.get("routerDir") or ""),
        }
        for k, raw in paths.items():
            if not raw:
                continue
            for ok, oraw in other_paths.items():
                if not oraw:
                    continue
                a, b = norm_path(raw), norm_path(oraw)
                if a == b:
                    issues.append(f"CROSS_INSTANCE_PATH_COLLISION:{k}:{ok}:{oid}")
                elif k != "root" and ok != "root" and (is_within(raw, oraw) or is_within(oraw, raw)):
                    issues.append(f"CROSS_INSTANCE_PATH_NESTING:{k}:{ok}:{oid}")
        if project and norm_path(str(other.get("projectDir") or "")) == norm_path(project):
            issues.append(f"CROSS_INSTANCE_PROJECT_COLLISION:{oid}")
        if account and str(other.get("accountEmail") or "").strip().lower() == account:
            warnings.append(f"ACCOUNT_REUSED_BY_INSTANCE:{oid}")
        try:
            if port and int(other.get("port") or 0) == port:
                issues.append(f"CROSS_INSTANCE_PORT_COLLISION:{oid}")
        except Exception:
            pass

    config_hash = ""
    config_path = Path(home_s) / "config.toml" if home_s else None
    if config_path and config_path.is_file():
        try:
            config_hash = sha_file(config_path)
        except Exception:
            warnings.append("CODEX_CONFIG_HASH_UNAVAILABLE")

    boundary = {
        "schema_version": 1,
        "instance_id": iid,
        "account_sha256": sha_text(account),
        "project_path_sha256": path_key(project),
        "root_path_sha256": path_key(root_s),
        "codex_home_path_sha256": path_key(home_s),
        "app_data_path_sha256": path_key(app_s),
        "router_dir_path_sha256": path_key(router_s),
        "port": port,
        "stable_endpoint": endpoint,
        "launch_mode": launch_mode,
        "config_sha256": config_hash,
        "binding_generation": binding_name,
    }
    fingerprint = sha_text(json.dumps(boundary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    issue_unique = sorted(set(issues))
    warning_unique = sorted(set(warnings))
    return {
        "instance_id": iid,
        "ok": not issue_unique,
        "grade": "PASS" if not issue_unique else "BLOCKED",
        "fingerprint_sha256": fingerprint,
        "fingerprint_short": fingerprint[:12],
        "issues": issue_unique,
        "warnings": warning_unique,
        "boundary": boundary,
        "secret_fields_excluded": True,
    }


def audit_store(store_path: Path, instance_id: str = "", strict: bool = True, write_fingerprint: bool = False) -> dict[str, Any]:
    if not store_path.is_file():
        return {"ok": True, "version": VERSION, "summary": {"total": 0, "pass": 0, "blocked": 0}, "instances": [], "note": "INSTANCE_STORE_MISSING"}
    store = load_json(store_path)
    instances = store.get("instances") if isinstance(store, dict) else []
    if not isinstance(instances, list):
        raise ValueError("INSTANCE_STORE_INVALID")
    selected = [x for x in instances if isinstance(x, dict) and (not instance_id or str(x.get("id") or "") == instance_id)]
    if instance_id and not selected:
        raise ValueError("INSTANCE_NOT_FOUND")
    reports = [audit_instance(inst, instances, strict=strict) for inst in selected]
    if write_fingerprint:
        by_id = {str(x.get("id") or ""): x for x in instances if isinstance(x, dict)}
        for report in reports:
            inst = by_id.get(report["instance_id"])
            if not inst:
                continue
            root = Path(str(inst.get("root") or ""))
            if root.is_dir():
                atomic_json(root / "identity-v2536.json", {
                    "schema_version": 1,
                    "version": VERSION,
                    "generated_utc": utc_now(),
                    "instance_id": report["instance_id"],
                    "fingerprint_sha256": report["fingerprint_sha256"],
                    "boundary": report["boundary"],
                    "secret_fields_excluded": True,
                })
    passed = sum(1 for r in reports if r["ok"])
    blocked = len(reports) - passed
    return {
        "ok": blocked == 0,
        "version": VERSION,
        "generated_utc": utc_now(),
        "summary": {"total": len(reports), "pass": passed, "blocked": blocked},
        "instances": reports,
        "secret_fields_excluded": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--instance-id", default="")
    ap.add_argument("--strict", choices=("true", "false"), default="true")
    ap.add_argument("--write-fingerprint", action="store_true")
    ap.add_argument("--output", default="")
    ns = ap.parse_args()
    try:
        result = audit_store(Path(ns.store), ns.instance_id, ns.strict == "true", ns.write_fingerprint)
        envelope = {"ok": True, "data": result}
        exit_code = 0 if result.get("ok") else 2
    except Exception as exc:
        envelope = {"ok": False, "error": str(exc), "version": VERSION}
        exit_code = 3
    text = json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"
    if ns.output:
        atomic_json(Path(ns.output), envelope)
    print(text, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
