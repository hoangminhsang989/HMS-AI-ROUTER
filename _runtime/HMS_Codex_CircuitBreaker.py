#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
POLICY_VERSION = "25.32"
VALID_STATES = {"CLOSED", "OPEN", "HALF_OPEN"}
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization", "bearer",
    "api_key", "apikey", "client_secret", "password",
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


def i(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def ek(value: Any) -> str:
    return str(value or "").strip().lower()


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


def contains_secret_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS or kl.endswith(("_access_token", "_refresh_token", "_client_secret", "_api_key")):
                return True
            if contains_secret_like(v):
                return True
    elif isinstance(obj, list):
        return any(contains_secret_like(v) for v in obj)
    return False


def safe_auth_file(router_dir: Path, filename: str) -> Path:
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


def auth_disabled_snapshot(path: Path) -> tuple[bool, bool]:
    data = read_json(path, None)
    if not isinstance(data, dict):
        raise RuntimeError(f"AUTH_JSON_INVALID:{path.name}")
    had = "disabled" in data
    return had, bool(data.get("disabled", False))


def set_disabled_exact(path: Path, disabled: bool, remove_when_false: bool) -> None:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise RuntimeError(f"AUTH_JSON_INVALID:{path.name}")
    if disabled:
        data["disabled"] = True
    elif remove_when_false:
        data.pop("disabled", None)
    else:
        data["disabled"] = False
    atomic_json(path, data)
    check = read_json(path, None)
    if not isinstance(check, dict):
        raise RuntimeError(f"AUTH_READBACK_INVALID:{path.name}")
    if disabled and check.get("disabled") is not True:
        raise RuntimeError(f"AUTH_DISABLE_READBACK_FAIL:{path.name}")
    if not disabled:
        if remove_when_false and "disabled" in check:
            raise RuntimeError(f"AUTH_ENABLE_REMOVE_READBACK_FAIL:{path.name}")
        if not remove_when_false and bool(check.get("disabled", False)):
            raise RuntimeError(f"AUTH_ENABLE_READBACK_FAIL:{path.name}")


def classify_event(row: dict[str, Any]) -> str:
    status = i(row.get("status"), 0)
    err = str(row.get("error_class") or "").lower()
    if status in (401, 403) or any(x in err for x in ("auth", "unauthor", "forbidden", "credential")):
        return "AUTH"
    if status == 429 or any(x in err for x in ("rate_limit", "ratelimit", "quota", "too many")):
        return "RATE_LIMIT"
    if 500 <= status < 600:
        return "SERVER"
    if any(x in err for x in ("timeout", "timed out", "deadline")):
        return "TIMEOUT"
    if any(x in err for x in ("network", "connect", "connection", "dns", "socket", "reset by peer")):
        return "NETWORK"
    if 200 <= status < 400:
        return "SUCCESS"
    if status >= 400 or err:
        return "OTHER"
    return "IGNORE"


def recent_events(usage: dict[str, Any], account: str, after: datetime | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    key = ek(account)
    for row in list(usage.get("recent") or []):
        if ek(row.get("account")) != key:
            continue
        dt = parse_time(row.get("time"))
        if after and dt and dt <= after:
            continue
        item = dict(row)
        item["_time"] = dt
        item["_class"] = classify_event(item)
        rows.append(item)
    rows.sort(key=lambda r: r.get("_time") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


def trigger_from_events(events: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[str | None, dict[str, int]]:
    counts = {"AUTH": 0, "RATE_LIMIT": 0, "SERVER": 0, "TIMEOUT": 0, "NETWORK": 0, "OTHER": 0, "SUCCESS": 0}
    consecutive_failures = 0
    for row in events:
        cls = row.get("_class") or "IGNORE"
        if cls in counts:
            counts[cls] += 1
        if cls == "SUCCESS":
            break
        if cls not in ("IGNORE", "SUCCESS"):
            consecutive_failures += 1

    if counts["AUTH"] >= max(1, i(cfg.get("auth_threshold"), 1)):
        return "AUTH", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    if counts["RATE_LIMIT"] >= max(1, i(cfg.get("rate_limit_threshold"), 2)):
        return "RATE_LIMIT", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    if counts["TIMEOUT"] >= max(1, i(cfg.get("timeout_threshold"), 2)):
        return "TIMEOUT", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    if counts["SERVER"] >= max(1, i(cfg.get("server_threshold"), 3)):
        return "SERVER", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    if counts["NETWORK"] >= max(1, i(cfg.get("network_threshold"), 3)):
        return "NETWORK", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    if consecutive_failures >= max(1, i(cfg.get("consecutive_failure_threshold"), 3)):
        return "CONSECUTIVE_FAILURES", counts | {"CONSECUTIVE_FAILURES": consecutive_failures}
    return None, counts | {"CONSECUTIVE_FAILURES": consecutive_failures}


def open_duration(reason: str, open_count: int, cfg: dict[str, Any]) -> int:
    base = max(15, i(cfg.get("base_open_seconds"), 120))
    specific = {
        "AUTH": max(base, i(cfg.get("auth_open_seconds"), 900)),
        "RATE_LIMIT": max(base, i(cfg.get("rate_limit_open_seconds"), 180)),
        "SERVER": max(15, i(cfg.get("server_open_seconds"), base)),
        "TIMEOUT": max(15, i(cfg.get("timeout_open_seconds"), 90)),
        "NETWORK": max(15, i(cfg.get("network_open_seconds"), 90)),
        "CONSECUTIVE_FAILURES": base,
    }.get(reason, base)
    exp = max(0, min(i(cfg.get("max_backoff_exponent"), 4), max(0, open_count - 1)))
    return min(max(30, i(cfg.get("max_open_seconds"), 3600)), specific * (2 ** exp))


def account_center_map(fleet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ek(a.get("email")): a for a in list(fleet.get("accounts") or []) if ek(a.get("email"))}


def state_row(old: dict[str, Any] | None) -> dict[str, Any]:
    old = deepcopy(old or {})
    state = str(old.get("state") or "CLOSED").upper()
    if state not in VALID_STATES:
        state = "CLOSED"
    old["state"] = state
    old.setdefault("reason", "")
    old.setdefault("open_count", 0)
    old.setdefault("quarantine_owned", False)
    old.setdefault("previous_had_disabled_property", False)
    old.setdefault("previous_disabled", False)
    return old


def evaluate(fleet: dict[str, Any], usage: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    now = utcnow()
    accounts = account_center_map(fleet)
    old_instances = (state.get("instances") or {}) if isinstance(state, dict) else {}
    plans: list[dict[str, Any]] = []
    summary = {"instances": 0, "accounts": 0, "closed": 0, "open": 0, "half_open": 0, "transitions": 0, "quarantined": 0}

    for inst in list(fleet.get("instances") or []):
        iid = str(inst.get("id") or "").strip()
        manifest = inst.get("manifest") or {}
        if not iid or not isinstance(manifest, dict):
            continue
        prior_accounts = ((old_instances.get(iid) or {}).get("accounts") or {})
        rows: list[dict[str, Any]] = []
        summary["instances"] += 1
        for pool_row in list(manifest.get("accounts") or []):
            email = str(pool_row.get("email") or "").strip()
            key = ek(email)
            filename = str(pool_row.get("file") or "")
            if not key or not filename:
                continue
            summary["accounts"] += 1
            old = state_row(prior_accounts.get(key))
            current_state = old["state"]
            desired_state = current_state
            transition_reason = ""
            transition = False
            account = accounts.get(key) or {}
            account_status = str(account.get("status") or "MISSING").upper()
            router_dir = Path(str(inst.get("router_dir") or ""))
            auth_path = safe_auth_file(router_dir, filename)
            had_disabled, disabled_now = auth_disabled_snapshot(auth_path)

            # Manual/externally-disabled accounts are not owned by the circuit breaker.
            manual_disabled = bool((disabled_now or account_status == "DISABLED") and not old.get("quarantine_owned"))
            last_transition = parse_time(old.get("last_transition_utc"))
            half_open_since = parse_time(old.get("half_open_since_utc"))
            open_until = parse_time(old.get("open_until_utc"))
            events = recent_events(usage, email, last_transition)
            trigger, counters = trigger_from_events(events, cfg)

            if manual_disabled:
                desired_state = "CLOSED"
                transition_reason = "MANUAL_DISABLED_EXCLUDED"
            elif current_state == "CLOSED":
                if trigger:
                    desired_state = "OPEN"
                    transition_reason = trigger
                    transition = True
            elif current_state == "OPEN":
                if open_until and now >= open_until:
                    desired_state = "HALF_OPEN"
                    transition_reason = "OPEN_TIMEOUT_ELAPSED"
                    transition = True
            elif current_state == "HALF_OPEN":
                probe_events = recent_events(usage, email, half_open_since or last_transition)
                probe_classes = [r.get("_class") for r in probe_events if r.get("_class") != "IGNORE"]
                failures = [x for x in probe_classes if x != "SUCCESS"]
                successes = [x for x in probe_classes if x == "SUCCESS"]
                if failures:
                    desired_state = "OPEN"
                    transition_reason = "HALF_OPEN_PROBE_FAILED:" + str(failures[0])
                    transition = True
                elif len(successes) >= max(1, i(cfg.get("half_open_successes"), 1)):
                    desired_state = "CLOSED"
                    transition_reason = "HALF_OPEN_RECOVERED"
                    transition = True

            open_count = max(0, i(old.get("open_count"), 0))
            desired_open_until: datetime | None = open_until
            if transition and desired_state == "OPEN":
                open_count += 1
                reason_key = transition_reason.split(":", 1)[-1] if transition_reason.startswith("HALF_OPEN_PROBE_FAILED:") else transition_reason
                seconds = open_duration(reason_key, open_count, cfg)
                desired_open_until = now + timedelta(seconds=seconds)
            elif transition and desired_state == "HALF_OPEN":
                desired_open_until = None
            elif transition and desired_state == "CLOSED":
                desired_open_until = None
                open_count = max(0, open_count - 1)

            desired_disabled: bool | None
            if manual_disabled:
                desired_disabled = True
            elif desired_state == "OPEN":
                desired_disabled = True
            elif desired_state in ("HALF_OPEN", "CLOSED"):
                desired_disabled = False
            else:
                desired_disabled = None

            row = {
                "account": email,
                "file": filename,
                "account_status": account_status,
                "state": current_state,
                "desired_state": desired_state,
                "transition": transition,
                "transition_reason": transition_reason or old.get("reason") or "",
                "open_count": open_count,
                "open_until_utc": iso(desired_open_until) if desired_open_until else None,
                "half_open_since_utc": iso(now) if transition and desired_state == "HALF_OPEN" else old.get("half_open_since_utc"),
                "last_transition_utc": iso(now) if transition else old.get("last_transition_utc"),
                "auth_disabled_now": disabled_now,
                "auth_had_disabled_property": had_disabled,
                "manual_disabled": manual_disabled,
                "quarantine_owned": bool(old.get("quarantine_owned")),
                "desired_disabled": desired_disabled,
                "probe_only": desired_state == "HALF_OPEN",
                "event_counters": counters,
            }
            rows.append(row)
            if transition:
                summary["transitions"] += 1
            if desired_state == "OPEN":
                summary["open"] += 1
                if not manual_disabled:
                    summary["quarantined"] += 1
            elif desired_state == "HALF_OPEN":
                summary["half_open"] += 1
            else:
                summary["closed"] += 1

        plans.append({
            "instance_id": iid,
            "instance_name": str(inst.get("name") or iid),
            "project": str(inst.get("project") or ""),
            "router_dir": str(inst.get("router_dir") or ""),
            "manifest_path": str(inst.get("manifest_path") or ""),
            "stable_endpoint": str(manifest.get("stable_endpoint") or ""),
            "accounts": rows,
        })

    mode = str(cfg.get("mode") or "OBSERVE").upper()
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_utc": iso(now),
        "enabled": bool(cfg.get("enabled", True)),
        "mode": mode,
        "summary": summary,
        "instances": plans,
        "safety": {
            "stable_endpoint_untouched": True,
            "session_affinity_untouched": True,
            "project_binding_untouched": True,
            "oauth_tokens_untouched": True,
            "request_body_consumed": False,
            "destructive_delete": False,
            "auth_mutation_scope": "disabled_field_only_when_GUARDED_AUTO",
            "manual_disabled_preserved": True,
        },
        "classification": ["AUTH", "RATE_LIMIT", "SERVER", "TIMEOUT", "NETWORK", "OTHER"],
        "note": "v25.32 circuit breaker quarantines OPEN accounts with auth.disabled only in GUARDED_AUTO; HALF_OPEN is a passive probe state and Closed-loop keeps it at probe priority for new sessions.",
    }


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if plan.get("policy_version") != POLICY_VERSION:
        errors.append("policy_version mismatch")
    if contains_secret_like(plan):
        errors.append("secret-like field present in plan")
    safety = plan.get("safety") or {}
    for key in ("stable_endpoint_untouched", "session_affinity_untouched", "project_binding_untouched", "oauth_tokens_untouched", "manual_disabled_preserved"):
        if safety.get(key) is not True:
            errors.append(f"safety invariant false: {key}")
    for inst in list(plan.get("instances") or []):
        endpoint = str(inst.get("stable_endpoint") or "")
        if endpoint and not endpoint.startswith("http://127.0.0.1:"):
            errors.append(f"non-local stable endpoint: {inst.get('instance_id')}")
        seen: set[str] = set()
        for row in list(inst.get("accounts") or []):
            key = ek(row.get("account"))
            if not key or key in seen:
                errors.append(f"duplicate/empty account: {inst.get('instance_id')}:{key}")
            seen.add(key)
            if str(row.get("desired_state") or "") not in VALID_STATES:
                errors.append(f"invalid state: {inst.get('instance_id')}:{key}")
    return {"ok": not errors, "errors": errors, "instances": len(plan.get("instances") or [])}


def apply_plan(plan: dict[str, Any], state_path: Path) -> dict[str, Any]:
    if str(plan.get("mode") or "").upper() != "GUARDED_AUTO":
        return {"applied": False, "reason": "GUARDED_AUTO_REQUIRED"}
    before_state = state_path.read_bytes() if state_path.exists() else None
    originals: list[tuple[Path, bytes]] = []
    old_state = read_json(state_path, {}) or {}
    old_instances = old_state.get("instances") or {}
    new_instances = deepcopy(old_instances)
    changed: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    try:
        for inst in list(plan.get("instances") or []):
            iid = str(inst.get("instance_id") or "")
            router_dir = Path(str(inst.get("router_dir") or ""))
            iold = deepcopy(old_instances.get(iid) or {})
            accounts_state = deepcopy(iold.get("accounts") or {})
            for row in list(inst.get("accounts") or []):
                email = str(row.get("account") or "")
                key = ek(email)
                if not key:
                    continue
                prev = state_row(accounts_state.get(key))
                filename = str(row.get("file") or "")
                path = safe_auth_file(router_dir, filename)
                raw = path.read_bytes()
                originals.append((path, raw))
                had, disabled = auth_disabled_snapshot(path)
                desired_state = str(row.get("desired_state") or prev.get("state") or "CLOSED").upper()
                manual_disabled = bool(row.get("manual_disabled"))

                if manual_disabled and not prev.get("quarantine_owned"):
                    # Never auto-enable a user/external disabled account.
                    desired_state = "CLOSED"
                elif desired_state == "OPEN":
                    if not prev.get("quarantine_owned"):
                        if disabled:
                            # Treat pre-existing disabled as manual; do not claim ownership.
                            manual_disabled = True
                            desired_state = "CLOSED"
                        else:
                            prev["previous_had_disabled_property"] = had
                            prev["previous_disabled"] = disabled
                            prev["quarantine_owned"] = True
                    if prev.get("quarantine_owned"):
                        if not disabled:
                            set_disabled_exact(path, True, False)
                            changed.append({"instance_id": iid, "account": email, "disabled": True, "reason": "CIRCUIT_OPEN"})
                elif desired_state == "HALF_OPEN":
                    if prev.get("quarantine_owned") and disabled:
                        remove = not bool(prev.get("previous_had_disabled_property"))
                        set_disabled_exact(path, False, remove)
                        changed.append({"instance_id": iid, "account": email, "disabled": False, "reason": "HALF_OPEN_PROBE"})
                elif desired_state == "CLOSED":
                    if prev.get("quarantine_owned"):
                        restore_disabled = bool(prev.get("previous_disabled"))
                        remove = not bool(prev.get("previous_had_disabled_property")) and not restore_disabled
                        set_disabled_exact(path, restore_disabled, remove)
                        changed.append({"instance_id": iid, "account": email, "disabled": restore_disabled, "reason": "CIRCUIT_RECOVERED"})
                        prev["quarantine_owned"] = False
                        prev["previous_had_disabled_property"] = False
                        prev["previous_disabled"] = False

                prior_state = str(prev.get("state") or "CLOSED")
                next_row = {
                    "state": desired_state,
                    "reason": str(row.get("transition_reason") or prev.get("reason") or ""),
                    "open_count": max(0, i(row.get("open_count"), i(prev.get("open_count"), 0))),
                    "open_until_utc": row.get("open_until_utc") if desired_state == "OPEN" else None,
                    "half_open_since_utc": row.get("half_open_since_utc") if desired_state == "HALF_OPEN" else None,
                    "last_transition_utc": row.get("last_transition_utc") or prev.get("last_transition_utc"),
                    "quarantine_owned": bool(prev.get("quarantine_owned")),
                    "previous_had_disabled_property": bool(prev.get("previous_had_disabled_property")),
                    "previous_disabled": bool(prev.get("previous_disabled")),
                    "manual_disabled": manual_disabled,
                    "last_event_counters": row.get("event_counters") or {},
                    "updated_utc": iso(),
                }
                accounts_state[key] = next_row
                if prior_state != desired_state:
                    transitions.append({
                        "time_utc": iso(), "instance_id": iid, "account": email,
                        "from": prior_state, "to": desired_state, "reason": next_row["reason"],
                    })
            new_instances[iid] = {"accounts": accounts_state, "updated_utc": iso()}

        history = list(old_state.get("history") or [])[-199:] + transitions
        new_state = {
            "schema_version": SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "updated_utc": iso(),
            "instances": new_instances,
            "history": history[-200:],
            "last_plan": plan,
        }
        atomic_json(state_path, new_state)
        return {
            "applied": True,
            "files_changed": len(changed),
            "changes": changed,
            "transitions": transitions,
            "stable_endpoint_untouched": True,
            "session_affinity_untouched": True,
            "manual_disabled_preserved": True,
            "files_deleted": False,
        }
    except Exception:
        for path, raw in reversed(originals):
            try:
                atomic_bytes(path, raw)
            except Exception:
                pass
        try:
            if before_state is None:
                if state_path.exists():
                    state_path.unlink()
            else:
                atomic_bytes(state_path, before_state)
        except Exception:
            pass
        raise


def reset_state(state_path: Path, fleet: dict[str, Any], account_filter: str = "") -> dict[str, Any]:
    before_state = state_path.read_bytes() if state_path.exists() else None
    state = read_json(state_path, {}) or {}
    fleet_instances = {str(x.get("id") or ""): x for x in list(fleet.get("instances") or [])}
    originals: list[tuple[Path, bytes]] = []
    reset_rows: list[dict[str, Any]] = []
    target = ek(account_filter)
    try:
        for iid, irow in list((state.get("instances") or {}).items()):
            inst = fleet_instances.get(iid)
            if not inst:
                continue
            router_dir = Path(str(inst.get("router_dir") or ""))
            manifest = inst.get("manifest") or {}
            file_map = {ek(x.get("email")): str(x.get("file") or "") for x in list(manifest.get("accounts") or [])}
            accounts_state = irow.get("accounts") or {}
            for email, srow in list(accounts_state.items()):
                if target and ek(email) != target:
                    continue
                if bool(srow.get("quarantine_owned")):
                    filename = file_map.get(ek(email), "")
                    path = safe_auth_file(router_dir, filename)
                    originals.append((path, path.read_bytes()))
                    restore_disabled = bool(srow.get("previous_disabled"))
                    remove = not bool(srow.get("previous_had_disabled_property")) and not restore_disabled
                    set_disabled_exact(path, restore_disabled, remove)
                accounts_state[email] = {
                    "state": "CLOSED", "reason": "MANUAL_RESET", "open_count": 0,
                    "open_until_utc": None, "half_open_since_utc": None,
                    "last_transition_utc": iso(), "quarantine_owned": False,
                    "previous_had_disabled_property": False, "previous_disabled": False,
                    "manual_disabled": False, "last_event_counters": {}, "updated_utc": iso(),
                }
                reset_rows.append({"instance_id": iid, "account": email})
        if not reset_rows:
            raise RuntimeError("NO_CIRCUIT_STATE_TO_RESET")
        state["policy_version"] = POLICY_VERSION
        state["updated_utc"] = iso()
        state.setdefault("history", []).append({"time_utc": iso(), "action": "MANUAL_RESET", "account": account_filter or "ALL"})
        atomic_json(state_path, state)
        return {"reset": True, "accounts": reset_rows, "files_deleted": False, "manual_disabled_preserved": True}
    except Exception:
        for path, raw in reversed(originals):
            try:
                atomic_bytes(path, raw)
            except Exception:
                pass
        try:
            if before_state is None:
                if state_path.exists():
                    state_path.unlink()
            else:
                atomic_bytes(state_path, before_state)
        except Exception:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "evaluate", "apply", "reset", "validate"), required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--usage")
    ap.add_argument("--state", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--config-json")
    ap.add_argument("--account", default="")
    args = ap.parse_args()
    state_path = Path(args.state)
    plan_path = Path(args.plan)
    cfg = json.loads(args.config_json) if args.config_json else {}
    try:
        if args.mode == "status":
            data = {"state": read_json(state_path, {}) or {}, "plan": read_json(plan_path, {}) or {}}
        elif args.mode == "validate":
            validation = validate_plan(read_json(plan_path, {}) or {})
            if not validation["ok"]:
                raise RuntimeError("PLAN_VALIDATION_FAILED:" + ",".join(validation["errors"]))
            data = {"validation": validation}
        else:
            if not args.fleet:
                raise ValueError("--fleet required")
            fleet = read_json(Path(args.fleet), {}) or {}
            if args.mode == "reset":
                data = {"reset": reset_state(state_path, fleet, args.account), "state": read_json(state_path, {}) or {}}
            else:
                usage = read_json(Path(args.usage), {}) if args.usage else {}
                state = read_json(state_path, {}) or {}
                plan = evaluate(fleet, usage or {}, state, cfg)
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
