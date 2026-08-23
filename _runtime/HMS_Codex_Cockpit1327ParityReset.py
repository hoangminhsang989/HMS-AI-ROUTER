#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "25.72"
COCKPIT_BASELINE = "1.3.27"
COCKPIT_BASELINE_DATE = "2026-08-23"
PRODUCTION_CLAIM = "NOT_CLAIMED_COCKPIT_1327_PARITY_RESET_CONTROL_PLANE_ONLY"

FEATURES = (
    "OFFICIAL_AUTH_SWITCH_CONTINUATION",
    "CLIENT_AUTH_API_SERVICE_SPLIT",
    "MULTI_INSTANCE_ACCOUNT_OCCUPANCY",
    "API_PORT_CONFLICT_AUTO_RECOVERY",
    "BOUNDED_BEHAVIOR_BACKUP_RETENTION",
    "STREAM_SESSION_IDENTITY_ISOLATION",
    "USAGE_CONTINUITY_BY_OFFICIAL_ACCOUNT_ID",
    "DEFAULT_INSTANCE_LIFECYCLE_DETECTION",
    "WEBSOCKET_SETTING_PRESERVATION",
    "OFFICIAL_AUTH_JSON_EXPORT",
    "MODEL_CONTEXT_COMPACTION_METADATA",
    "WINDOWS_STABLE_CLIENT_LIFECYCLE",
)

SECRET_KEYS = {
    "access_token", "refresh_token", "id_token", "openai_api_key", "api_key",
    "authorization", "cookie", "password", "secret", "private_key", "credential",
}


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8", "surrogatepass")
    return hashlib.sha256(value).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_account_ref(official_account_id: Any = None, email: Any = None) -> str:
    official = str(official_account_id or "").strip()
    if official:
        return "oaid-" + sha256(official)[:20]
    fallback = str(email or "").strip().lower()
    return "email-" + sha256(fallback)[:20] if fallback else "account-unknown"


def availability_state(*, client_authorized: bool, api_token_available: bool) -> dict[str, Any]:
    # Cockpit 1.3.25 split: a client re-auth requirement must not invalidate an API token
    # that is still usable. HMS keeps both dimensions explicit and never conflates them.
    client = "AUTHORIZED" if client_authorized else "REAUTH_REQUIRED"
    api = "AVAILABLE" if api_token_available else "UNAVAILABLE"
    if client_authorized and api_token_available:
        overall = "FULLY_AVAILABLE"
    elif api_token_available:
        overall = "API_ONLY_CLIENT_REAUTH_REQUIRED"
    elif client_authorized:
        overall = "CLIENT_ONLY_API_UNAVAILABLE"
    else:
        overall = "UNAVAILABLE"
    return {
        "client_auth_state": client,
        "api_service_state": api,
        "overall": overall,
        "invalid_account": not (client_authorized or api_token_available),
    }


def occupancy_decision(*, target_account_ref: str, target_instance_id: str,
                       running: Iterable[dict[str, Any]], transfer_from: str | None = None) -> dict[str, Any]:
    conflicts = []
    for row in running:
        if not bool(row.get("running")):
            continue
        if str(row.get("account_ref") or "") != target_account_ref:
            continue
        iid = str(row.get("instance_id") or "")
        if iid and iid != target_instance_id:
            conflicts.append(iid)
    conflicts = sorted(set(conflicts))
    if not conflicts:
        return {"ok": True, "action": "START", "conflicts": []}
    if transfer_from and transfer_from in conflicts and len(conflicts) == 1:
        return {
            "ok": False,
            "action": "TRANSFER_REQUIRES_EXPLICIT_STOP_THEN_REBIND",
            "conflicts": conflicts,
            "transfer_from": transfer_from,
        }
    return {"ok": False, "action": "BLOCK_ACCOUNT_OCCUPIED", "conflicts": conflicts}


def port_recovery_plan(*, requested_port: int, occupied_by_foreign: bool,
                       candidate_ports: Iterable[int], client_running: bool = False) -> dict[str, Any]:
    requested_port = int(requested_port)
    if not occupied_by_foreign:
        return {"action": "KEEP", "old_port": requested_port, "new_port": requested_port, "settings_preserved": True}
    if client_running:
        return {"action": "BLOCK_RUNNING_CLIENT", "old_port": requested_port, "new_port": None, "settings_preserved": True}
    for port in candidate_ports:
        port = int(port)
        if port > 0 and port != requested_port:
            return {
                "action": "REBIND_BEFORE_START", "old_port": requested_port, "new_port": port,
                "settings_preserved": True, "kill_foreign_process": False,
            }
    return {"action": "BLOCK_NO_FREE_PORT", "old_port": requested_port, "new_port": None, "settings_preserved": True}


def bounded_backup_retention(entries: Iterable[dict[str, Any]], keep_per_source_instance: int = 1) -> dict[str, Any]:
    keep_n = max(1, int(keep_per_source_instance))
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        source = str(row.get("source") or "UNKNOWN")
        instance = str(row.get("instance_id") or "DEFAULT")
        groups[(source, instance)].append(dict(row))
    keep: list[str] = []
    prune: list[str] = []
    for _, rows in groups.items():
        rows.sort(key=lambda r: str(r.get("created_utc") or ""), reverse=True)
        keep.extend(str(r.get("path") or "") for r in rows[:keep_n] if r.get("path"))
        prune.extend(str(r.get("path") or "") for r in rows[keep_n:] if r.get("path"))
    return {"keep": sorted(keep), "prune": sorted(prune), "keep_per_source_instance": keep_n}


def conversation_identity(*, conversation_id: Any, thread_id: Any, client_key_id: Any, account_ref: Any) -> str:
    # Stable within one conversation; different conversation/thread/client/account produces a different identity.
    basis = "|".join(str(x or "") for x in (conversation_id, thread_id, client_key_id, account_ref))
    return "sess-" + sha256(basis)[:24]


def preserve_websocket_setting(*, current_enabled: bool | None, requested_override: bool | None = None) -> bool | None:
    # Account switching must not silently turn WebSocket back on/off.
    return current_enabled if requested_override is None else bool(requested_override)


def model_runtime_metadata(*, model: str, context_window: Any = None, compact_threshold: Any = None) -> dict[str, Any]:
    def pos_int(v: Any) -> int | None:
        try:
            n = int(v)
            return n if n > 0 else None
        except Exception:
            return None
    ctx = pos_int(context_window)
    compact = pos_int(compact_threshold)
    if ctx is not None and compact is not None and compact >= ctx:
        raise ValueError("COMPACTION_THRESHOLD_MUST_BE_BELOW_CONTEXT_WINDOW")
    return {"model": str(model), "context_window": ctx, "compact_threshold": compact}


def stable_windows_lifecycle_strategy() -> dict[str, Any]:
    return {
        "close": ["CLOSE_MAIN_WINDOW", "OPTIONAL_OWNED_PROCESS_FORCE_CLOSE"],
        "launch": ["START_APPS_APPID", "CLASSIC_APP_PATH", "CLI_FALLBACK"],
        "forbidden": ["WINDOWSAPPS_INTERNAL_CODEX_DAEMON_STOP"],
        "powershell_required_for_daemon_stop": False,
        "foreign_process_kill": False,
    }


def parity_matrix() -> list[dict[str, Any]]:
    return [
        {"id": "auth_switch_continuation", "cockpit": "1.3.25", "hms": "TRANSACTIONAL_SUPERSET", "priority": "P0"},
        {"id": "client_api_split", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70", "priority": "P0"},
        {"id": "account_occupancy", "cockpit": "1.3.25", "hms": "DEDICATED_ACCOUNT_SUPERSET_PLUS_RUNTIME_GUARD", "priority": "P0"},
        {"id": "port_auto_recovery", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70", "priority": "P0"},
        {"id": "backup_retention", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70", "priority": "P1"},
        {"id": "stream_identity", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70_GATEWAY", "priority": "P0"},
        {"id": "usage_account_id", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70", "priority": "P1"},
        {"id": "default_instance_lifecycle", "cockpit": "1.3.25", "hms": "OWNERSHIP_CHECKED_SUPERSET", "priority": "P0"},
        {"id": "websocket_preserve", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70_CONTRACT", "priority": "P1"},
        {"id": "official_auth_export", "cockpit": "1.3.25", "hms": "SECURITY_GATED_MANUAL_EXPORT", "priority": "P1"},
        {"id": "model_context_compaction", "cockpit": "1.3.25", "hms": "IMPLEMENTED_V25_70_METADATA", "priority": "P1"},
        {"id": "windows_stable_lifecycle", "cockpit": "1.3.27", "hms": "ALREADY_SUPERSET_NO_INTERNAL_DAEMON_STOP", "priority": "P0"},
    ]


def report() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    matrix = parity_matrix()
    return {
        "version": VERSION,
        "generated_utc": now,
        "cockpit_parity_baseline": COCKPIT_BASELINE,
        "cockpit_baseline_date": COCKPIT_BASELINE_DATE,
        "features": list(FEATURES),
        "matrix": matrix,
        "summary": {
            "total": len(matrix),
            "p0": sum(1 for x in matrix if x["priority"] == "P0"),
            "p1": sum(1 for x in matrix if x["priority"] == "P1"),
            "gap_count": sum(1 for x in matrix if "GAP" in x["hms"]),
        },
        "lifecycle_strategy": stable_windows_lifecycle_strategy(),
        "production_claim": PRODUCTION_CLAIM,
        "benchmark": False,
    }


def main() -> int:
    print(json.dumps(report(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
