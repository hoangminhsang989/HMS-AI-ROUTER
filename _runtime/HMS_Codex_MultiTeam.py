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

ENGINE_VERSION = "25.43"
SCHEMA_VERSION = 1
ROLE_ORDER = {"CODER": 0, "REVIEWER": 1, "TESTER": 2}
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


def path_overlap(a: Any, b: Any) -> bool:
    aa, bb = path_key(a), path_key(b)
    if not aa or not bb:
        return False
    if aa == bb:
        return True
    sep = "\\"
    return aa.startswith(bb + sep) or bb.startswith(aa + sep)


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
            json.dump(data, f, ensure_ascii=False, indent=2)
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


def plan_hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def clean_member(m: dict[str, Any]) -> dict[str, Any]:
    role = norm(m.get("role")).upper()
    return {
        "role": role,
        "instance_id": norm(m.get("instance_id")),
        "instance_name": norm(m.get("instance_name")),
        "account": norm(m.get("account")).lower(),
        "workspace": norm(m.get("workspace")),
        "project_exists": bool(m.get("project_exists")),
        "client_running": bool(m.get("client_running")),
        "router_online": bool(m.get("router_online")),
        "identity_ok": bool(m.get("identity_ok")),
        "security_ok": bool(m.get("security_ok")),
        "binding_ok": bool(m.get("binding_ok", True)),
        "port_conflict_foreign": bool(m.get("port_conflict_foreign")),
        "model": norm(m.get("model")),
        "reasoning": norm(m.get("reasoning")) or "—",
        "profile": norm(m.get("profile")) or "BALANCED",
        "git_common_dir": norm(m.get("git_common_dir")),
        "git_toplevel": norm(m.get("git_toplevel")),
        "port": m.get("port"),
    }


def classify_team(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    members = [clean_member(x) for x in (row.get("members") or []) if isinstance(x, dict)]
    members.sort(key=lambda x: ROLE_ORDER.get(x["role"], 99))

    team_id = norm(row.get("team_id"))
    project_dir = norm(row.get("project_dir"))
    epoch = int(row.get("epoch") or 1)
    if not team_id:
        blockers.append("TEAM_ID_MISSING")
    if not bool(row.get("project_exists")):
        blockers.append("PROJECT_MISSING")
    if len(members) < 2:
        blockers.append("TEAM_REQUIRES_AT_LEAST_2_ROLES")
    if len(members) > int(config.get("max_members") or 3):
        blockers.append("TEAM_TOO_MANY_MEMBERS")

    roles = [m["role"] for m in members]
    if roles.count("CODER") != 1:
        blockers.append("TEAM_REQUIRES_EXACTLY_ONE_CODER")
    if any(r not in ROLE_ORDER for r in roles):
        blockers.append("TEAM_ROLE_UNSUPPORTED")
    if len(set(roles)) != len(roles):
        blockers.append("DUPLICATE_ROLE")

    ids = [m["instance_id"] for m in members if m["instance_id"]]
    if len(ids) != len(members) or len(set(ids)) != len(ids):
        blockers.append("INSTANCE_ROLE_COLLISION")

    if bool(config.get("require_distinct_account", True)):
        accounts = [m["account"] for m in members if m["account"]]
        if len(accounts) != len(members) or len(set(accounts)) != len(accounts):
            blockers.append("ACCOUNT_ROLE_COLLISION")

    for m in members:
        role = m["role"] or "UNKNOWN"
        if not m["project_exists"]:
            blockers.append(f"{role}_WORKSPACE_MISSING")
        if not m["identity_ok"]:
            blockers.append(f"{role}_IDENTITY_BLOCKED")
        if not m["security_ok"]:
            blockers.append(f"{role}_SECURITY_BLOCKED")
        if not m["binding_ok"]:
            blockers.append(f"{role}_BINDING_DRIFT")
        if m["port_conflict_foreign"]:
            blockers.append(f"{role}_FOREIGN_PORT_OWNER")
        if m["client_running"] and not m["router_online"]:
            blockers.append(f"{role}_CLIENT_RUNNING_ROUTER_OFFLINE")

    if bool(config.get("require_distinct_workspace", True)):
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if path_overlap(members[i]["workspace"], members[j]["workspace"]):
                    blockers.append(f"WORKSPACE_OVERLAP_{members[i]['role']}_{members[j]['role']}")

    coder = next((m for m in members if m["role"] == "CODER"), None)
    if coder and bool(config.get("coder_must_match_project", True)) and path_key(coder["workspace"]) != path_key(project_dir):
        blockers.append("CODER_WORKSPACE_PROJECT_MISMATCH")

    common_dirs = {path_key(m["git_common_dir"]) for m in members if path_key(m["git_common_dir"])}
    git_known = sum(1 for m in members if path_key(m["git_common_dir"]))
    if git_known == len(members) and len(common_dirs) > 1 and bool(config.get("require_same_git_repo", True)):
        blockers.append("GIT_REPOSITORY_MISMATCH")
    elif git_known < len(members):
        warnings.append("GIT_TOPOLOGY_PARTIAL_OR_NON_GIT")
    elif len(common_dirs) == 1 and len(members) > 1:
        warnings.append("SHARED_REPOSITORY_SEPARATE_WORKTREES")

    running = sum(1 for m in members if m["client_running"])
    all_running = bool(members) and running == len(members)
    partial = 0 < running < len(members)
    unique_blockers = list(dict.fromkeys(blockers))
    unique_warnings = list(dict.fromkeys(warnings))
    if unique_blockers:
        readiness = "BLOCKED"
    elif all_running:
        readiness = "RUNNING"
    elif partial:
        readiness = "PARTIAL_RUNNING"
    else:
        readiness = "READY"

    steps: list[dict[str, Any]] = []
    if not unique_blockers:
        steps.extend([
            {"step": "VERIFY_TEAM_TOPOLOGY", "mutation": False},
            {"step": "VERIFY_ROLE_IDENTITY", "mutation": False},
            {"step": "VERIFY_WORKSPACE_OWNERSHIP", "mutation": False},
        ])
        for m in members:
            steps.append({
                "step": "KEEP_RUNNING" if m["client_running"] else "START_ROLE",
                "role": m["role"],
                "instance_id": m["instance_id"],
                "mutation": not m["client_running"],
            })
        steps.append({"step": "VERIFY_ALL_PROCESS_OWNERSHIP", "mutation": False})

    topology_hash = plan_hash({
        "team_id": team_id,
        "project_dir": path_key(project_dir),
        "epoch": epoch,
        "members": [{"role": m["role"], "instance_id": m["instance_id"], "workspace": path_key(m["workspace"])} for m in members],
    })
    ownership = [
        {
            "role": m["role"],
            "instance_id": m["instance_id"],
            "lease": hashlib.sha256(f"{team_id}|{epoch}|{m['role']}|{m['instance_id']}".encode("utf-8")).hexdigest()[:24],
        }
        for m in members
    ]
    out = {
        "team_id": team_id,
        "name": norm(row.get("name")) or (Path(project_dir).name + " Team" if project_dir else "Codex Team"),
        "project_dir": project_dir,
        "epoch": epoch,
        "readiness": readiness,
        "one_click_ready": not unique_blockers,
        "running_members": running,
        "member_count": len(members),
        "members": members,
        "blockers": unique_blockers,
        "warnings": unique_warnings,
        "plan": steps,
        "topology_hash": topology_hash,
        "ownership_leases": ownership,
    }
    out["plan_hash"] = plan_hash({
        "topology_hash": topology_hash,
        "readiness": readiness,
        "steps": steps,
        "blockers": unique_blockers,
    })
    return out


def build_state(fleet: dict[str, Any]) -> dict[str, Any]:
    hits = secret_scan(fleet)
    if hits:
        raise ValueError("MULTI_CODEX_TEAM_SECRET_FIELD_REJECTED: " + ",".join(hits[:8]))
    config = fleet.get("config") or {}
    teams = [classify_team(x, config) for x in (fleet.get("teams") or []) if isinstance(x, dict)]
    teams.sort(key=lambda x: (x["readiness"] == "BLOCKED", x["name"].lower()))
    summary = {
        "teams": len(teams),
        "running": sum(1 for x in teams if x["readiness"] == "RUNNING"),
        "ready": sum(1 for x in teams if x["one_click_ready"] and x["readiness"] != "RUNNING"),
        "blocked": sum(1 for x in teams if not x["one_click_ready"]),
        "members": sum(int(x["member_count"]) for x in teams),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": utcnow(),
        "summary": summary,
        "teams": teams,
        "project_catalog": fleet.get("project_catalog") or [],
        "instance_catalog": fleet.get("instance_catalog") or [],
        "privacy": "NO_PROMPT_NO_REQUEST_BODY_NO_OAUTH_NO_API_KEY_NO_COOKIE",
        "invariants": [
            "Each team role maps to one managed Codex instance.",
            "Distinct workspace is a hard gate when enabled; shared working tree is blocked.",
            "Identity Isolation and Security Hardening remain hard gates.",
            "Existing running role instances are preserved and are not restarted by team launch.",
            "Role rebinding uses an explicit epoch; there is no silent takeover.",
            "Unowned processes are never killed by Multi-Codex Team.",
        ],
    }


def select_team(state: dict[str, Any], project_dir: str = "", team_id: str = "") -> dict[str, Any]:
    tid = norm(team_id)
    pkey = path_key(project_dir)
    for row in state.get("teams") or []:
        if tid and row.get("team_id") == tid:
            return row
        if pkey and path_key(row.get("project_dir")) == pkey:
            return row
    raise ValueError("MULTI_CODEX_TEAM_NOT_FOUND")


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
                raise ValueError("MULTI_CODEX_TEAM_INPUT_SECRET_REJECTED: " + ",".join(hits[:8]))
            selected = select_team(state, norm(inp.get("project_dir")), norm(inp.get("team_id")))
            state["selected"] = selected
            state["preflight"] = {
                "ok": bool(selected.get("one_click_ready")),
                "team_id": selected.get("team_id"),
                "project_dir": selected.get("project_dir"),
                "epoch": selected.get("epoch"),
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
