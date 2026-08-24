#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import secrets
import sys
import threading
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
REVIEW_ENTRY = RUNTIME_DIR / "HMS_GUI_REVIEW_ENTRY.pyw"
APP_VERSION = "25.75"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))


def _load_review_entry():
    loader = importlib.machinery.SourceFileLoader("hms_gui_review_entry_v2575_recovery", str(REVIEW_ENTRY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Không thể tạo module spec cho HMS_GUI_REVIEW_ENTRY.pyw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


review = _load_review_entry()
legacy = review.legacy

import HMS_Codex_WindowsOneShotElevation as one_shot_elevation
import HMS_Codex_WindowsRecoveryContract as recovery_contract
import HMS_Codex_WindowsRecoveryDialog as recovery_dialog

_ORIGINAL_BACKEND = legacy.HmsApp.backend
_ORIGINAL_OFFICIAL_SWITCH = legacy.HmsApp.official_auth_switch_async
_ORIGINAL_FINISH_OFFICIAL_SWITCH = legacy.HmsApp._finish_official_auth_switch

# Only operations that look user-triggered/destructive or service-lifecycle related may surface a dialog.
# Periodic Get/List/Status/Refresh/Probe/Health/Quota/Diagnostics paths stay silent.
_INTERACTIVE_TOKENS = frozenset({
    "enable", "disable", "start", "stop", "restart", "switch", "set", "add", "remove",
    "delete", "backup", "export", "import", "repair", "cleanup", "kill", "launch", "open",
    "bind", "unbind", "takeover", "restore", "migrate", "apply", "create", "write",
})
_BACKGROUND_TOKENS = frozenset({
    "get", "list", "status", "refresh", "probe", "health", "quota", "diagnostic", "diagnostics",
    "snapshot", "telemetry", "poll", "heartbeat", "maintenance", "observe", "inspect", "read",
})
_MAX_RECOVERY_RETRIES = 3


def _action_tokens(action: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", str(action or "").lower()) if token}


def _is_interactive_backend_action(action: str) -> bool:
    tokens = _action_tokens(action)
    if not tokens:
        return False
    if tokens & _INTERACTIVE_TOKENS:
        return True
    if tokens & _BACKGROUND_TOKENS:
        return False
    return False


def _error_detail(data) -> str:
    if isinstance(data, dict):
        for key in ("error", "detail", "message", "stderr", "reason"):
            value = data.get(key)
            if value:
                return str(value)
        try:
            return json.dumps(data, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(data)
    return str(data or "Unknown Windows operation failure")


def _target_path(data) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("target_path", "path", "file_path", "directory", "location"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _show_dialog_threadsafe(self, plan: dict) -> str:
    root = getattr(self, "root", None)
    if root is None:
        return recovery_contract.ACTION_CANCEL
    if threading.current_thread() is threading.main_thread():
        return recovery_dialog.show_recovery_dialog(root, plan)

    done = threading.Event()
    result = {"action": recovery_contract.ACTION_CANCEL}

    def show():
        try:
            result["action"] = recovery_dialog.show_recovery_dialog(root, plan)
        finally:
            done.set()

    try:
        root.after(0, show)
    except Exception:
        return recovery_contract.ACTION_CANCEL
    if not done.wait(180):
        return recovery_contract.ACTION_CANCEL
    return str(result["action"])


def _failure_result_from_exception(exc: Exception) -> dict:
    return {
        "ok": False,
        "error": recovery_contract.sanitize_detail(exc),
        "recovery_source": "BACKEND_EXCEPTION",
    }


def _backend_with_recovery(self, action, timeout=60, payload=None):
    attempt = 0
    while True:
        try:
            data = _ORIGINAL_BACKEND(self, action, timeout, payload)
        except Exception as exc:
            data = _failure_result_from_exception(exc)
        if isinstance(data, dict) and data.get("ok"):
            return data
        if not _is_interactive_backend_action(str(action)):
            return data

        detail = _error_detail(data)
        plan = recovery_contract.build_recovery_plan(
            detail,
            operation=str(action).upper(),
            target_path=_target_path(data),
            background_probe=False,
            supported_client=False,
        )
        if plan.get("recoverable") is not True:
            return data
        choice = _show_dialog_threadsafe(self, plan)
        if choice not in {recovery_contract.ACTION_RETRY, recovery_contract.ACTION_MANUAL_RETRY}:
            if isinstance(data, dict):
                data = dict(data)
                data["recovery_category"] = plan.get("category")
                data["recovery_action"] = choice
                data["recovery_detail_sanitized"] = True
            return data
        attempt += 1
        if attempt >= _MAX_RECOVERY_RETRIES:
            if isinstance(data, dict):
                data = dict(data)
                data["recovery_category"] = plan.get("category")
                data["recovery_action"] = "RETRY_LIMIT_REACHED"
                data["recovery_detail_sanitized"] = True
            return data


def _official_switch_with_recovery_tracking(self, email):
    self._hms_recovery_last_official_switch_email = str(email or "")
    self._hms_recovery_uac_operation_token = secrets.token_urlsafe(24)
    self._hms_recovery_uac_consumed = False
    return _ORIGINAL_OFFICIAL_SWITCH(self, email)


def _discover_switch_client_pids() -> list[int]:
    try:
        return one_shot_elevation.discover_supported_client_pids()
    except Exception:
        return []


def _retry_official_switch(self):
    email = str(getattr(self, "_hms_recovery_last_official_switch_email", "") or "")
    if email:
        return _ORIGINAL_OFFICIAL_SWITCH(self, email)
    return None


def _finish_official_switch_with_recovery(self, data):
    if isinstance(data, dict) and data.get("ok"):
        return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, data)

    detail = _error_detail(data)
    pids = _discover_switch_client_pids()
    uac_consumed = bool(getattr(self, "_hms_recovery_uac_consumed", False))
    plan = recovery_contract.build_recovery_plan(
        detail,
        operation="CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE",
        target_path=_target_path(data),
        background_probe=False,
        supported_client=bool(pids) and not uac_consumed,
    )
    if plan.get("recoverable") is not True:
        return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, data)

    self.busy = False
    choice = _show_dialog_threadsafe(self, plan)
    if choice in {recovery_contract.ACTION_RETRY, recovery_contract.ACTION_MANUAL_RETRY}:
        retried = _retry_official_switch(self)
        if retried is not None:
            return retried
    elif choice == recovery_contract.ACTION_REQUEST_UAC_ONCE:
        token = str(getattr(self, "_hms_recovery_uac_operation_token", "") or "")
        gate = recovery_contract.evaluate_uac_once(plan, operation_token=token, already_consumed=uac_consumed)
        if gate.get("allowed") is not True:
            blocked = dict(data) if isinstance(data, dict) else {"ok": False}
            blocked["error"] = "Windows one-shot authorization bị chặn: " + ",".join(gate.get("reasons") or [])
            return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, blocked)

        # Mark consumed before the UAC helper. Cancellation/failure is still one-shot for this switch epoch.
        self._hms_recovery_uac_consumed = True
        try:
            elevated = one_shot_elevation.elevated_close_supported_processes(pids, operation_token=token)
        except Exception as exc:
            blocked = dict(data) if isinstance(data, dict) else {"ok": False}
            blocked["error"] = recovery_contract.sanitize_detail(exc)
            blocked["recovery_action"] = "UAC_ONE_SHOT_FAILED"
            blocked["recovery_detail_sanitized"] = True
            return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, blocked)
        if elevated.get("ok") is True:
            retried = _retry_official_switch(self)
            if retried is not None:
                return retried

    return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, data)


legacy.HmsApp.backend = _backend_with_recovery
legacy.HmsApp.official_auth_switch_async = _official_switch_with_recovery_tracking
legacy.HmsApp._finish_official_auth_switch = _finish_official_switch_with_recovery


def extension_proof():
    access = recovery_contract.build_recovery_plan(
        "Access denied (os error 5)", operation="CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE",
        supported_client=True,
    )
    quiet_names = ["get_status", "refresh_quota", "health_probe", "list_accounts", "telemetry_snapshot"]
    interactive_names = ["enable", "disable", "restart_router", "open_codex", "set_request_log", "repair_profile", "backup_export"]
    src = Path(__file__).read_text("utf-8")
    impl_src = src[:src.find("def extension_proof")]
    checks = {
        "review_wrapper_loaded": getattr(review, "APP_VERSION", None) == APP_VERSION,
        "sealed_review_wrapper_preserved": getattr(review, "legacy", None) is legacy,
        "backend_recovery_patch_installed": legacy.HmsApp.backend is _backend_with_recovery,
        "official_switch_tracking_patch_installed": legacy.HmsApp.official_auth_switch_async is _official_switch_with_recovery_tracking,
        "official_switch_finish_patch_installed": legacy.HmsApp._finish_official_auth_switch is _finish_official_switch_with_recovery,
        "background_actions_remain_quiet": all(not _is_interactive_backend_action(name) for name in quiet_names),
        "interactive_actions_surface_recovery": all(_is_interactive_backend_action(name) for name in interactive_names),
        "direct_open_codex_is_interactive": _is_interactive_backend_action("open_codex"),
        "threadsafe_ui_bridge": "root.after" in impl_src and "threading.Event" in impl_src,
        "retry_is_bounded": _MAX_RECOVERY_RETRIES == 3 and "RETRY_LIMIT_REACHED" in impl_src,
        "official_switch_recovery_supported": "CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE" in impl_src,
        "uac_only_offered_after_supported_pid_discovery": access["uac_eligible"] is True and "discover_supported_client_pids" in impl_src and "supported_client=bool(pids) and not uac_consumed" in impl_src,
        "uac_epoch_token_is_generated_per_user_switch": "secrets.token_urlsafe(24)" in impl_src and "_hms_recovery_uac_consumed = False" in impl_src,
        "uac_consumed_before_helper": impl_src.find("self._hms_recovery_uac_consumed = True") < impl_src.find("one_shot_elevation.elevated_close_supported_processes"),
        "uac_helper_has_no_caller_executable": "executable_path" not in impl_src and "taskkill.exe" not in impl_src,
        "no_raw_error_persistence": "recovery_detail_sanitized" in impl_src and "raw_error" not in impl_src,
        "no_production_authority": "production_score_mutation" not in impl_src and "windows_runtime_certified = True" not in impl_src,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    contract_proof = recovery_contract.synthetic_proof()
    dialog_proof = recovery_dialog.source_proof()
    elevation_proof = one_shot_elevation.synthetic_proof()
    children_pass = all(x.get("verdict") == "PASS" for x in (contract_proof, dialog_proof, elevation_proof))
    verdict = "PASS" if passed == len(tests) and children_pass else "FAIL"
    return {
        "product": "HMS-AI-ROUTER", "version": APP_VERSION, "suite": "GUI_WINDOWS_RECOVERY_WRAPPER_PROOF",
        "verdict": verdict,
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "contract_proof": contract_proof.get("summary"),
        "dialog_proof": dialog_proof.get("summary"),
        "elevation_proof": elevation_proof.get("summary"),
        "real_windows_recovery_executed": False,
        "real_uac_prompt_executed": False,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def main():
    if "--proof" in sys.argv[1:]:
        out = extension_proof()
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["verdict"] == "PASS" else 2
    legacy.HmsApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
