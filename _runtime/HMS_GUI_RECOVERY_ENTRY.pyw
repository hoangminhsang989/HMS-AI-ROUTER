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
_UAC_BACKEND_ACTIONS = frozenset({"enable", "disable"})
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


def _discover_supported_client_pids() -> list[int]:
    try:
        return one_shot_elevation.discover_supported_client_pids()
    except Exception:
        return []


def _uac_allowed_for_backend_failure(action: str, detail: str) -> bool:
    return (
        str(action or "").strip().lower() in _UAC_BACKEND_ACTIONS
        and recovery_contract.classify_error(detail) == recovery_contract.RECOVERY_CLIENT_CLOSE_BLOCKED
    )


def _backend_with_recovery(self, action, timeout=60, payload=None):
    attempt = 0
    uac_token = secrets.token_urlsafe(24)
    uac_consumed = False
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
        pids = _discover_supported_client_pids() if _uac_allowed_for_backend_failure(str(action), detail) else []
        plan = recovery_contract.build_recovery_plan(
            detail,
            operation=str(action).upper(),
            target_path=_target_path(data),
            background_probe=False,
            supported_client=bool(pids) and not uac_consumed,
        )
        if plan.get("recoverable") is not True:
            return data
        choice = _show_dialog_threadsafe(self, plan)
        if choice in {recovery_contract.ACTION_RETRY, recovery_contract.ACTION_MANUAL_RETRY}:
            attempt += 1
            if attempt >= _MAX_RECOVERY_RETRIES:
                if isinstance(data, dict):
                    data = dict(data)
                    data["recovery_category"] = plan.get("category")
                    data["recovery_action"] = "RETRY_LIMIT_REACHED"
                    data["recovery_detail_sanitized"] = True
                return data
            continue
        if choice == recovery_contract.ACTION_REQUEST_UAC_ONCE:
            gate = recovery_contract.evaluate_uac_once(plan, operation_token=uac_token, already_consumed=uac_consumed)
            if gate.get("allowed") is not True:
                if isinstance(data, dict):
                    data = dict(data)
                    data["recovery_category"] = plan.get("category")
                    data["recovery_action"] = "UAC_ONE_SHOT_BLOCKED"
                    data["recovery_detail_sanitized"] = True
                return data
            # Consume before helper/UAC. Cancel and failure remain one-shot for this backend operation epoch.
            uac_consumed = True
            try:
                one_shot_elevation.elevated_close_supported_processes(pids, operation_token=uac_token)
            except Exception as exc:
                if isinstance(data, dict):
                    data = dict(data)
                    data["error"] = recovery_contract.sanitize_detail(exc)
                    data["recovery_category"] = plan.get("category")
                    data["recovery_action"] = "UAC_ONE_SHOT_FAILED"
                    data["recovery_detail_sanitized"] = True
                return data
            # The close barrier has been resolved; retry the same original transaction once through its normal verifier.
            attempt += 1
            if attempt >= _MAX_RECOVERY_RETRIES:
                return data
            continue

        if isinstance(data, dict):
            data = dict(data)
            data["recovery_category"] = plan.get("category")
            data["recovery_action"] = choice
            data["recovery_detail_sanitized"] = True
        return data


def _policy_from_settings(settings: object, *, source: str) -> dict:
    if not isinstance(settings, dict):
        return {"known": False, "launch_after_auth_switch": False, "restart_codex_on_switch": False, "source": source}
    launch = settings.get("CodexLaunchAfterAuthSwitch")
    restart = settings.get("RestartCodexOnSwitch")
    if not isinstance(launch, bool) or not isinstance(restart, bool):
        return {"known": False, "launch_after_auth_switch": False, "restart_codex_on_switch": False, "source": source}
    return {
        "known": True,
        "launch_after_auth_switch": launch,
        "restart_codex_on_switch": restart,
        "source": source,
    }


def _official_switch_policy_snapshot(self) -> dict:
    settings = getattr(self, "settings_data", None)
    loaded = bool(getattr(self, "settings_loaded", False))
    if loaded:
        local = _policy_from_settings(settings, source="GUI_SETTINGS_DATA")
        if local.get("known") is True:
            return local

    # Settings page is lazy-loaded. Read the canonical backend settings before the switch if the GUI cache is absent.
    try:
        data = _ORIGINAL_BACKEND(self, "get_settings", 30, None)
        if isinstance(data, dict) and data.get("ok"):
            backend = _policy_from_settings(data.get("settings"), source="BACKEND_GET_SETTINGS")
            if backend.get("known") is True:
                return backend
    except Exception:
        pass
    return {"known": False, "launch_after_auth_switch": False, "restart_codex_on_switch": False, "source": "UNAVAILABLE"}


def _derive_official_client_lifecycle(
    initial_pids: list[int], current_pids: list[int], policy: dict, *, uac_consumed: bool,
) -> dict:
    initial = sorted({int(pid) for pid in initial_pids if int(pid) > 0})
    current = sorted({int(pid) for pid in current_pids if int(pid) > 0})
    initial_set = set(initial)
    remaining = sorted(initial_set.intersection(current))
    known = policy.get("known") is True
    launch = policy.get("launch_after_auth_switch") is True
    restart = policy.get("restart_codex_on_switch") is True

    if not known:
        code = "POLICY_UNKNOWN"
        complete = False
        can_elevate = False
    elif not launch:
        code = "NOT_REQUESTED"
        complete = True
        can_elevate = False
    elif not restart:
        code = "RESTART_DISABLED"
        complete = False
        can_elevate = False
    elif remaining:
        code = "CODEX_RESTART_REQUIRED"
        complete = False
        can_elevate = not uac_consumed
    else:
        code = "OK"
        complete = True
        can_elevate = False

    return {
        "schema_version": 1,
        "code": code,
        "policy_known": known,
        "policy_source": str(policy.get("source") or "UNKNOWN"),
        "launch_after_auth_switch": launch,
        "restart_codex_on_switch": restart,
        "initial_pid_count": len(initial),
        "remaining_original_pids": remaining,
        "close_lifecycle_complete": complete,
        "can_elevate": can_elevate,
        "uac_consumed": bool(uac_consumed),
        "derived_from_structured_settings_and_pid_identity": True,
        "human_message_parsed": False,
        "production_effect_authorized": False,
        "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }


def _decorate_official_switch_lifecycle(self, data: dict) -> dict:
    decorated = dict(data)
    initial = list(getattr(self, "_hms_recovery_official_initial_pids", []) or [])
    policy = dict(getattr(self, "_hms_recovery_official_policy", {}) or {})
    current = _discover_supported_client_pids()
    consumed = bool(getattr(self, "_hms_recovery_uac_consumed", False))
    lifecycle = _derive_official_client_lifecycle(initial, current, policy, uac_consumed=consumed)
    decorated["client_lifecycle"] = lifecycle
    return decorated


def _official_switch_with_recovery_tracking(self, email):
    self._hms_recovery_last_official_switch_email = str(email or "")
    self._hms_recovery_uac_operation_token = secrets.token_urlsafe(24)
    self._hms_recovery_uac_consumed = False
    self._hms_recovery_official_retry_count = 0
    self._hms_recovery_official_initial_pids = _discover_supported_client_pids()
    self._hms_recovery_official_policy = _official_switch_policy_snapshot(self)
    return _ORIGINAL_OFFICIAL_SWITCH(self, email)


def _retry_official_switch(self):
    count = int(getattr(self, "_hms_recovery_official_retry_count", 0) or 0)
    if count >= _MAX_RECOVERY_RETRIES:
        return None
    self._hms_recovery_official_retry_count = count + 1
    email = str(getattr(self, "_hms_recovery_last_official_switch_email", "") or "")
    if email:
        return _ORIGINAL_OFFICIAL_SWITCH(self, email)
    return None


def _finish_official_switch_with_recovery(self, data):
    if isinstance(data, dict) and data.get("ok"):
        decorated = _decorate_official_switch_lifecycle(self, data)
        lifecycle = decorated.get("client_lifecycle") or {}
        if lifecycle.get("code") != "CODEX_RESTART_REQUIRED":
            return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, decorated)

        remaining = list(lifecycle.get("remaining_original_pids") or [])
        uac_consumed = bool(getattr(self, "_hms_recovery_uac_consumed", False))
        detail = "CODEX_RESTART_REQUIRED: official auth đã chuyển nhưng client cũ vẫn còn chạy."
        plan = recovery_contract.build_recovery_plan(
            detail,
            operation="CODEX_ACCOUNT_SWITCH_CLIENT_LIFECYCLE",
            background_probe=False,
            supported_client=bool(remaining) and lifecycle.get("can_elevate") is True and not uac_consumed,
        )

        self.busy = False
        choice = _show_dialog_threadsafe(self, plan)
        if choice in {recovery_contract.ACTION_RETRY, recovery_contract.ACTION_MANUAL_RETRY}:
            retried = _retry_official_switch(self)
            if retried is not None:
                return retried
            decorated["message"] = str(decorated.get("message") or "") + " · Client restart vẫn chưa hoàn tất; đã đạt giới hạn retry."
            return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, decorated)

        if choice == recovery_contract.ACTION_REQUEST_UAC_ONCE:
            token = str(getattr(self, "_hms_recovery_uac_operation_token", "") or "")
            gate = recovery_contract.evaluate_uac_once(plan, operation_token=token, already_consumed=uac_consumed)
            if gate.get("allowed") is not True:
                decorated["message"] = str(decorated.get("message") or "") + " · UAC one-shot bị chặn; auth đã chuyển nhưng cần đóng/mở Codex thủ công."
                return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, decorated)

            # Consume before the helper/UAC. Auth has already committed; cancellation must not be reported as auth rollback.
            self._hms_recovery_uac_consumed = True
            try:
                elevated = one_shot_elevation.elevated_close_supported_processes(remaining, operation_token=token)
            except Exception as exc:
                decorated["client_lifecycle"] = dict(lifecycle)
                decorated["client_lifecycle"]["recovery_action"] = "UAC_ONE_SHOT_FAILED"
                decorated["client_lifecycle"]["recovery_error"] = recovery_contract.sanitize_detail(exc)
                decorated["message"] = str(decorated.get("message") or "") + " · Auth đã chuyển; UAC đóng client không hoàn tất, hãy đóng/mở Codex thủ công."
                return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, decorated)
            if elevated.get("ok") is True:
                retried = _retry_official_switch(self)
                if retried is not None:
                    return retried

        decorated["message"] = str(decorated.get("message") or "") + " · Auth đã chuyển; client cũ vẫn chạy, hãy đóng/mở Codex để nạp auth mới."
        return _ORIGINAL_FINISH_OFFICIAL_SWITCH(self, decorated)

    detail = _error_detail(data)
    category = recovery_contract.classify_error(detail)
    pids = _discover_supported_client_pids() if category == recovery_contract.RECOVERY_CLIENT_CLOSE_BLOCKED else []
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
    close_blocked = recovery_contract.build_recovery_plan(
        "CODEX_RESTART_REQUIRED: client remains running",
        operation="ENABLE", supported_client=True,
    )
    unrelated_access = recovery_contract.build_recovery_plan(
        "Access denied (os error 5)", operation="BACKUP_EXPORT", supported_client=True,
    )
    policy_on = {"known": True, "launch_after_auth_switch": True, "restart_codex_on_switch": True, "source": "TEST"}
    policy_disabled = {"known": True, "launch_after_auth_switch": True, "restart_codex_on_switch": False, "source": "TEST"}
    policy_not_requested = {"known": True, "launch_after_auth_switch": False, "restart_codex_on_switch": True, "source": "TEST"}
    policy_unknown = {"known": False, "launch_after_auth_switch": False, "restart_codex_on_switch": False, "source": "TEST"}
    life_blocked = _derive_official_client_lifecycle([101, 102], [102, 201], policy_on, uac_consumed=False)
    life_restarted = _derive_official_client_lifecycle([101, 102], [201, 202], policy_on, uac_consumed=False)
    life_disabled = _derive_official_client_lifecycle([101], [101], policy_disabled, uac_consumed=False)
    life_not_requested = _derive_official_client_lifecycle([101], [101], policy_not_requested, uac_consumed=False)
    life_unknown = _derive_official_client_lifecycle([101], [101], policy_unknown, uac_consumed=False)
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
        "pre_mutation_close_barrier_is_uac_eligible": close_blocked["uac_eligible"] is True and _uac_allowed_for_backend_failure("enable", "CODEX_RESTART_REQUIRED: x"),
        "unrelated_access_denied_cannot_elevate": unrelated_access["uac_eligible"] is False and not _uac_allowed_for_backend_failure("backup_export", "Access denied os error 5"),
        "official_lifecycle_uses_structured_settings": "CodexLaunchAfterAuthSwitch" in impl_src and "RestartCodexOnSwitch" in impl_src,
        "official_policy_has_readonly_backend_fallback": '_ORIGINAL_BACKEND(self, "get_settings", 30, None)' in impl_src and "BACKEND_GET_SETTINGS" in impl_src,
        "official_lifecycle_does_not_parse_human_message": life_blocked["human_message_parsed"] is False and "restart_message" not in impl_src,
        "official_old_pid_survival_blocks": life_blocked["code"] == "CODEX_RESTART_REQUIRED" and life_blocked["remaining_original_pids"] == [102] and life_blocked["can_elevate"] is True,
        "official_new_pid_after_restart_is_ok": life_restarted["code"] == "OK" and life_restarted["close_lifecycle_complete"] is True,
        "official_restart_disabled_respects_user_policy": life_disabled["code"] == "RESTART_DISABLED" and life_disabled["can_elevate"] is False,
        "official_launch_not_requested_is_non_elevatable": life_not_requested["code"] == "NOT_REQUESTED" and life_not_requested["can_elevate"] is False,
        "official_unknown_policy_fails_closed": life_unknown["code"] == "POLICY_UNKNOWN" and life_unknown["can_elevate"] is False,
        "official_uac_targets_only_remaining_original_pids": "remaining_original_pids" in impl_src and "elevated_close_supported_processes(remaining" in impl_src,
        "official_auth_success_never_rewritten_as_failure_on_uac_error": "Auth đã chuyển; UAC đóng client không hoàn tất" in impl_src and "decorated[\"ok\"] = False" not in impl_src,
        "uac_only_after_supported_pid_discovery": "discover_supported_client_pids" in impl_src and "supported_client=bool(pids) and not uac_consumed" in impl_src,
        "uac_epoch_token_is_generated_per_operation": "secrets.token_urlsafe(24)" in impl_src,
        "uac_consumed_before_helper": impl_src.find("uac_consumed = True") < impl_src.find("one_shot_elevation.elevated_close_supported_processes"),
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
