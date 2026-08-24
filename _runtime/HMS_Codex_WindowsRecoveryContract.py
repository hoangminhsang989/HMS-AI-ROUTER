#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
SCHEMA_VERSION = 1

RECOVERY_ACCESS_DENIED = "ACCESS_DENIED"
RECOVERY_FILE_IN_USE = "FILE_IN_USE"
RECOVERY_PROGRAM_MISSING = "PROGRAM_MISSING"
RECOVERY_CLIENT_CLOSE_BLOCKED = "CLIENT_CLOSE_BLOCKED"
RECOVERY_OTHER = "OTHER"

ACTION_RETRY = "RETRY"
ACTION_MANUAL_RETRY = "MANUAL_RETRY"
ACTION_OPEN_LOCATION = "OPEN_LOCATION"
ACTION_COPY_ERROR = "COPY_ERROR"
ACTION_REQUEST_UAC_ONCE = "REQUEST_UAC_ONCE"
ACTION_CANCEL = "CANCEL"

# UAC is restricted to closing/restarting an already-running supported Codex client.
# Starting an arbitrary executable is intentionally not eligible.
ELEVATION_OPERATION_ALLOWLIST = frozenset({
    "CODEX_CLIENT_STOP",
    "CODEX_CLIENT_RESTART",
    "CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE",
    "ENABLE",
    "DISABLE",
})

_ACCESS_PATTERNS = (
    "access is denied", "access denied", "permission denied", "refused access",
    "os error 5", "winerror 5", "error 5:", "拒绝访问", "拒絕存取",
    "os error 10013", "winerror 10013", "wsaeacces",
)
_FILE_IN_USE_PATTERNS = (
    "file in use", "being used by another process", "used by another process",
    "sharing violation", "os error 32", "winerror 32", "process cannot access the file",
    "文件被占用", "檔案正在使用",
)
_PROGRAM_MISSING_PATTERNS = (
    "program missing", "executable not found", "command not found", "not recognized as an internal",
    "no such file or directory", "the system cannot find the file specified",
    "os error 2", "winerror 2", "errno 2", "找不到指定的文件", "找不到指定的檔案",
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(authorization|access[_ -]?token|refresh[_ -]?token|api[_ -]?key|password|secret)\b\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/=]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)
_EMAIL_RE = re.compile(r"(?i)\b([A-Z0-9._%+-])([A-Z0-9._%+-]*)@([A-Z0-9.-]+\.[A-Z]{2,})\b")
_WINDOWS_USER_RE = re.compile(r"(?i)([A-Z]:\\Users\\)([^\\\r\n]+)")


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sanitize_detail(value: Any, *, limit: int = 4000) -> str:
    text = str(value or "").replace("\x00", "")
    text = _EMAIL_RE.sub(lambda m: f"{m.group(1)}***@{m.group(3)}", text)
    text = _WINDOWS_USER_RE.sub(lambda m: m.group(1) + "<USER>", text)
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.lower().startswith("(?i)\\b(authorization"):
            text = pattern.sub(lambda m: f"{m.group(1)}=<REDACTED>", text)
        else:
            text = pattern.sub("<REDACTED>", text)
    return text[: max(256, int(limit))]


def classify_error(detail: Any) -> str:
    normalized = str(detail or "").strip().lower()
    if normalized.startswith("codex_restart_required:"):
        return RECOVERY_CLIENT_CLOSE_BLOCKED
    if any(token in normalized for token in _ACCESS_PATTERNS):
        return RECOVERY_ACCESS_DENIED
    if any(token in normalized for token in _FILE_IN_USE_PATTERNS):
        return RECOVERY_FILE_IN_USE
    if any(token in normalized for token in _PROGRAM_MISSING_PATTERNS):
        return RECOVERY_PROGRAM_MISSING
    return RECOVERY_OTHER


def build_recovery_plan(
    detail: Any,
    *,
    operation: str,
    target_path: str = "",
    background_probe: bool = False,
    supported_client: bool = False,
) -> dict[str, Any]:
    operation = str(operation or "UNKNOWN").strip().upper()
    category = classify_error(detail)
    recoverable = category in {
        RECOVERY_ACCESS_DENIED,
        RECOVERY_FILE_IN_USE,
        RECOVERY_PROGRAM_MISSING,
        RECOVERY_CLIENT_CLOSE_BLOCKED,
    }
    sanitized = sanitize_detail(detail)

    uac_eligible = bool(
        recoverable
        and category in {RECOVERY_ACCESS_DENIED, RECOVERY_CLIENT_CLOSE_BLOCKED}
        and supported_client
        and operation in ELEVATION_OPERATION_ALLOWLIST
    )

    if background_probe:
        actions: list[str] = []
        surface_mode = "QUIET_BACKGROUND"
    elif recoverable:
        actions = [ACTION_RETRY, ACTION_MANUAL_RETRY]
        if str(target_path or "").strip():
            actions.append(ACTION_OPEN_LOCATION)
        actions.append(ACTION_COPY_ERROR)
        if uac_eligible:
            actions.append(ACTION_REQUEST_UAC_ONCE)
        actions.append(ACTION_CANCEL)
        surface_mode = "TOP_LEVEL_DIALOG"
    else:
        actions = [ACTION_COPY_ERROR, ACTION_CANCEL]
        surface_mode = "TOP_LEVEL_DIALOG"

    return {
        "schema_version": SCHEMA_VERSION,
        "product": PRODUCT,
        "version": VERSION,
        "operation": operation,
        "category": category,
        "recoverable": recoverable,
        "background_probe": bool(background_probe),
        "surface_mode": surface_mode,
        "sanitized_detail": sanitized,
        "target_path": str(target_path or ""),
        "actions": actions,
        "uac_eligible": uac_eligible,
        "uac_automatic": False,
        "uac_requires_explicit_user_action": True,
        "uac_execution_owned_by_caller": True,
        "raw_error_persisted": False,
        "production_effect_authorized": False,
        "real_codex_request_authorized": False,
        "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }


def evaluate_uac_once(plan: dict[str, Any], *, operation_token: str, already_consumed: bool) -> dict[str, Any]:
    token = str(operation_token or "").strip()
    reasons: list[str] = []
    if plan.get("uac_eligible") is not True:
        reasons.append("UAC_NOT_ELIGIBLE")
    if not token:
        reasons.append("UAC_OPERATION_TOKEN_REQUIRED")
    if already_consumed:
        reasons.append("UAC_OPERATION_TOKEN_ALREADY_CONSUMED")
    allowed = not reasons
    return {
        "allowed": allowed,
        "reasons": reasons,
        "operation_token": token if allowed else "",
        "consume_token_if_launched": allowed,
        "auto_launch": False,
        "production_effect_authorized": False,
    }


def synthetic_proof() -> dict[str, Any]:
    access = build_recovery_plan(
        "Access is denied. (os error 5)", operation="CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE",
        target_path=r"C:\Users\alice\AppData\Local\Codex\Codex.exe", supported_client=True,
    )
    close_blocked = build_recovery_plan(
        "CODEX_RESTART_REQUIRED: ChatGPT/Codex vẫn còn process đang chạy.",
        operation="ENABLE", supported_client=True,
    )
    start_denied = build_recovery_plan(
        "Access is denied. (os error 5)", operation="CODEX_CLIENT_START",
        target_path=r"C:\Users\alice\AppData\Local\Codex\Codex.exe", supported_client=True,
    )
    file_busy = build_recovery_plan(
        "The process cannot access the file because it is being used by another process. WinError 32",
        operation="BACKUP_EXPORT", target_path=r"D:\backup\router.json",
    )
    missing = build_recovery_plan(
        "The system cannot find the file specified. WinError 2", operation="CODEX_CLIENT_START",
        target_path=r"C:\Program Files\Codex\Codex.exe", supported_client=True,
    )
    quiet = build_recovery_plan(
        "Access denied os error 5", operation="BACKGROUND_HEALTH_PROBE", background_probe=True,
        supported_client=True,
    )
    generic = build_recovery_plan("HTTP 500 unknown failure", operation="UNKNOWN")
    sanitized = sanitize_detail(
        r"C:\Users\alice\x authORIZATION=abc123 access_token=tok123 user@example.com sk-supersecret123456"
    )
    first_uac = evaluate_uac_once(close_blocked, operation_token="op-1", already_consumed=False)
    second_uac = evaluate_uac_once(close_blocked, operation_token="op-1", already_consumed=True)
    denied_nonclient = build_recovery_plan(
        "Access denied os error 5", operation="BACKUP_EXPORT", supported_client=False,
    )

    checks = {
        "access_denied_classified": access["category"] == RECOVERY_ACCESS_DENIED,
        "client_close_blocked_classified": close_blocked["category"] == RECOVERY_CLIENT_CLOSE_BLOCKED,
        "file_in_use_classified": file_busy["category"] == RECOVERY_FILE_IN_USE,
        "program_missing_classified": missing["category"] == RECOVERY_PROGRAM_MISSING,
        "generic_error_not_recoverable": generic["recoverable"] is False,
        "interactive_recovery_actions_present": all(x in close_blocked["actions"] for x in (ACTION_RETRY, ACTION_MANUAL_RETRY, ACTION_COPY_ERROR)),
        "background_probe_is_quiet": quiet["surface_mode"] == "QUIET_BACKGROUND" and quiet["actions"] == [],
        "sensitive_detail_redacted": "abc123" not in sanitized and "tok123" not in sanitized and "supersecret" not in sanitized and "alice" not in sanitized and "u***@example.com" in sanitized,
        "uac_only_for_supported_allowlisted_client": close_blocked["uac_eligible"] is True and denied_nonclient["uac_eligible"] is False,
        "uac_start_is_forbidden": start_denied["uac_eligible"] is False and ACTION_REQUEST_UAC_ONCE not in start_denied["actions"],
        "uac_never_automatic": close_blocked["uac_automatic"] is False and first_uac["auto_launch"] is False,
        "uac_one_shot_gate_first_allowed": first_uac["allowed"] is True and first_uac["consume_token_if_launched"] is True,
        "uac_one_shot_gate_replay_blocked": second_uac["allowed"] is False and "UAC_OPERATION_TOKEN_ALREADY_CONSUMED" in second_uac["reasons"],
        "missing_program_does_not_offer_uac": ACTION_REQUEST_UAC_ONCE not in missing["actions"],
        "no_production_authority": not any((access["production_effect_authorized"], access["real_codex_request_authorized"], access["windows_runtime_certified"], access["production_score_mutation_authorized"])),
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "WINDOWS_RECOVERY_CONTRACT_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "real_windows_recovery_executed": False,
        "uac_executed": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
    }


def main() -> int:
    out = synthetic_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
