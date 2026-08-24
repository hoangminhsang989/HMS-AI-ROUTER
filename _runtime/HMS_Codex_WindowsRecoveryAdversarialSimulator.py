#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
RUNTIME_DIR = Path(__file__).resolve().parent
GUI_RECOVERY_ENTRY = RUNTIME_DIR / "HMS_GUI_RECOVERY_ENTRY.pyw"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import HMS_Codex_WindowsOneShotElevation as elevation
import HMS_Codex_WindowsRecoveryContract as contract


def _load_gui_recovery_entry():
    loader = importlib.machinery.SourceFileLoader("hms_gui_recovery_adversarial", str(GUI_RECOVERY_ENTRY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("GUI_RECOVERY_SPEC_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gui = _load_gui_recovery_entry()


def _expect_raises(exc_type: type[BaseException], fn: Callable[[], Any], contains: str = "") -> bool:
    try:
        fn()
    except exc_type as exc:
        return not contains or contains in str(exc)
    except Exception:
        return False
    return False


def _case(name: str, ok: bool, *, group: str, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "group": group,
        "status": "PASS" if ok else "FAIL",
        "detail": detail,
    }


def _policy(*, known: bool, launch: bool, restart: bool, source: str = "ADVERSARIAL") -> dict[str, Any]:
    return {
        "known": known,
        "launch_after_auth_switch": launch,
        "restart_codex_on_switch": restart,
        "source": source,
    }


def _recovery_plan_cases() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    close_enable = contract.build_recovery_plan(
        "CODEX_RESTART_REQUIRED: old client survives",
        operation="ENABLE",
        supported_client=True,
    )
    tests.append(_case(
        "close_barrier_enable_offers_one_shot_uac",
        close_enable["uac_eligible"] is True and contract.ACTION_REQUEST_UAC_ONCE in close_enable["actions"],
        group="recovery-plan",
    ))

    close_disable = contract.build_recovery_plan(
        "CODEX_RESTART_REQUIRED: old client survives",
        operation="DISABLE",
        supported_client=True,
    )
    tests.append(_case(
        "close_barrier_disable_offers_one_shot_uac",
        close_disable["uac_eligible"] is True,
        group="recovery-plan",
    ))

    access_start = contract.build_recovery_plan(
        "Access denied (WinError 5)",
        operation="CODEX_CLIENT_START",
        supported_client=True,
    )
    tests.append(_case(
        "client_start_never_elevates",
        access_start["uac_eligible"] is False and contract.ACTION_REQUEST_UAC_ONCE not in access_start["actions"],
        group="recovery-plan",
    ))

    access_backup = contract.build_recovery_plan(
        "Access denied (os error 5)",
        operation="BACKUP_EXPORT",
        supported_client=True,
    )
    tests.append(_case(
        "unrelated_access_denied_never_elevates",
        access_backup["uac_eligible"] is False,
        group="recovery-plan",
    ))

    file_busy = contract.build_recovery_plan(
        "WinError 32: file is being used by another process",
        operation="ENABLE",
        supported_client=True,
    )
    tests.append(_case(
        "file_busy_recoverable_but_not_elevatable",
        file_busy["recoverable"] is True and file_busy["uac_eligible"] is False,
        group="recovery-plan",
    ))

    missing = contract.build_recovery_plan(
        "WinError 2: The system cannot find the file specified",
        operation="CODEX_CLIENT_START",
        supported_client=True,
    )
    tests.append(_case(
        "program_missing_recoverable_but_not_elevatable",
        missing["recoverable"] is True and missing["uac_eligible"] is False,
        group="recovery-plan",
    ))

    background = contract.build_recovery_plan(
        "CODEX_RESTART_REQUIRED: background probe collision",
        operation="ENABLE",
        background_probe=True,
        supported_client=True,
    )
    tests.append(_case(
        "background_failure_never_surfaces_actions",
        background["surface_mode"] == "QUIET_BACKGROUND" and background["actions"] == [],
        group="recovery-plan",
    ))

    unknown = contract.build_recovery_plan("HTTP 500", operation="UNKNOWN", supported_client=True)
    tests.append(_case(
        "unknown_failure_is_not_recoverable",
        unknown["recoverable"] is False and unknown["uac_eligible"] is False,
        group="recovery-plan",
    ))

    gate_ok = contract.evaluate_uac_once(close_enable, operation_token="adversarial-token-123456", already_consumed=False)
    gate_replay = contract.evaluate_uac_once(close_enable, operation_token="adversarial-token-123456", already_consumed=True)
    gate_blank = contract.evaluate_uac_once(close_enable, operation_token="", already_consumed=False)
    gate_ineligible = contract.evaluate_uac_once(access_backup, operation_token="adversarial-token-654321", already_consumed=False)
    tests.extend([
        _case("uac_gate_first_attempt_allowed", gate_ok["allowed"] is True, group="recovery-plan"),
        _case(
            "uac_gate_replay_blocked",
            gate_replay["allowed"] is False and "UAC_OPERATION_TOKEN_ALREADY_CONSUMED" in gate_replay["reasons"],
            group="recovery-plan",
        ),
        _case(
            "uac_gate_blank_token_blocked",
            gate_blank["allowed"] is False and "UAC_OPERATION_TOKEN_REQUIRED" in gate_blank["reasons"],
            group="recovery-plan",
        ),
        _case(
            "uac_gate_ineligible_plan_blocked",
            gate_ineligible["allowed"] is False and "UAC_NOT_ELIGIBLE" in gate_ineligible["reasons"],
            group="recovery-plan",
        ),
    ])

    tests.append(_case(
        "wrapper_enable_requires_exact_restart_barrier",
        gui._uac_allowed_for_backend_failure("enable", "CODEX_RESTART_REQUIRED: x") is True
        and gui._uac_allowed_for_backend_failure("enable", "Access denied WinError 5") is False,
        group="recovery-plan",
    ))
    tests.append(_case(
        "wrapper_unrelated_operation_never_elevates",
        gui._uac_allowed_for_backend_failure("backup_export", "CODEX_RESTART_REQUIRED: x") is False,
        group="recovery-plan",
    ))
    return tests


def _pid_race_cases() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    process_map = {101: "Codex.exe", 102: "ChatGPT.exe", 103: "notepad.exe", 104: "explorer.exe"}

    tests.append(_case(
        "supported_pid_pair_validates",
        elevation._validate_target_map([102, 101], process_map) == [101, 102],
        group="pid-race",
    ))
    tests.append(_case(
        "pid_substitution_to_notepad_rejected",
        _expect_raises(ValueError, lambda: elevation._validate_target_map([101], {101: "notepad.exe"}), "TARGET_NOT_ALLOWED"),
        group="pid-race",
    ))
    tests.append(_case(
        "pid_substitution_to_explorer_rejected",
        _expect_raises(ValueError, lambda: elevation._validate_target_map([101], {101: "explorer.exe"}), "TARGET_NOT_ALLOWED"),
        group="pid-race",
    ))
    tests.append(_case(
        "pid_exited_before_revalidation_is_resolved",
        elevation._validate_target_map([101], {}) == [],
        group="pid-race",
    ))
    tests.append(_case(
        "mixed_survivor_and_exited_pid_targets_only_survivor",
        elevation._validate_target_map([101, 102], {102: "ChatGPT.exe"}) == [102],
        group="pid-race",
    ))
    tests.append(_case(
        "duplicate_pids_are_canonicalized",
        elevation._normalize_pids([102, 101, 102, 101]) == [101, 102],
        group="pid-race",
    ))
    tests.append(_case(
        "zero_and_negative_pids_are_removed",
        elevation._normalize_pids([-1, 0, 101]) == [101],
        group="pid-race",
    ))
    tests.append(_case(
        "all_invalid_pids_fail_closed",
        _expect_raises(ValueError, lambda: elevation._normalize_pids([-1, 0]), "TARGET_INVALID"),
        group="pid-race",
    ))
    tests.append(_case(
        "current_process_pid_is_never_targetable",
        elevation._normalize_pids([os.getpid(), 101]) == [101],
        group="pid-race",
    ))
    tests.append(_case(
        "current_process_only_fails_closed",
        _expect_raises(ValueError, lambda: elevation._normalize_pids([os.getpid()]), "TARGET_INVALID"),
        group="pid-race",
    ))
    tests.append(_case(
        "pid_bound_32_is_accepted",
        len(elevation._normalize_pids(range(1000, 1032))) == 32,
        group="pid-race",
    ))
    tests.append(_case(
        "pid_bound_33_is_rejected",
        _expect_raises(ValueError, lambda: elevation._normalize_pids(range(1000, 1033)), "TARGET_INVALID"),
        group="pid-race",
    ))
    tests.append(_case(
        "taskkill_arguments_are_sorted_numeric_only",
        elevation._taskkill_arguments([102, 101]) == "/PID 101 /PID 102 /T /F",
        group="pid-race",
    ))
    return tests


def _official_lifecycle_cases() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    derive = gui._derive_official_client_lifecycle

    unknown = derive([101], [101], _policy(known=False, launch=False, restart=False), uac_consumed=False)
    tests.append(_case(
        "unknown_policy_fails_closed",
        unknown["code"] == "POLICY_UNKNOWN" and unknown["can_elevate"] is False,
        group="official-lifecycle",
    ))

    not_requested = derive([101], [101], _policy(known=True, launch=False, restart=True), uac_consumed=False)
    tests.append(_case(
        "launch_not_requested_is_complete_without_elevation",
        not_requested["code"] == "NOT_REQUESTED" and not_requested["close_lifecycle_complete"] is True and not_requested["can_elevate"] is False,
        group="official-lifecycle",
    ))

    restart_disabled = derive([101], [101], _policy(known=True, launch=True, restart=False), uac_consumed=False)
    tests.append(_case(
        "restart_disabled_respects_policy",
        restart_disabled["code"] == "RESTART_DISABLED" and restart_disabled["can_elevate"] is False,
        group="official-lifecycle",
    ))

    replaced = derive([101, 102], [201, 202], _policy(known=True, launch=True, restart=True), uac_consumed=False)
    tests.append(_case(
        "replacement_pids_mean_restart_complete",
        replaced["code"] == "OK" and replaced["remaining_original_pids"] == [] and replaced["close_lifecycle_complete"] is True,
        group="official-lifecycle",
    ))

    old_and_new = derive([101, 102], [102, 201, 202], _policy(known=True, launch=True, restart=True), uac_consumed=False)
    tests.append(_case(
        "old_plus_new_targets_only_surviving_original",
        old_and_new["code"] == "CODEX_RESTART_REQUIRED" and old_and_new["remaining_original_pids"] == [102] and old_and_new["can_elevate"] is True,
        group="official-lifecycle",
    ))

    consumed = derive([101, 102], [102, 201], _policy(known=True, launch=True, restart=True), uac_consumed=True)
    tests.append(_case(
        "consumed_uac_epoch_cannot_elevate_again",
        consumed["code"] == "CODEX_RESTART_REQUIRED" and consumed["remaining_original_pids"] == [102] and consumed["can_elevate"] is False,
        group="official-lifecycle",
    ))

    duplicate = derive([101, 101, 102], [102, 102, 201], _policy(known=True, launch=True, restart=True), uac_consumed=False)
    tests.append(_case(
        "duplicate_pid_observations_are_normalized",
        duplicate["initial_pid_count"] == 2 and duplicate["remaining_original_pids"] == [102],
        group="official-lifecycle",
    ))

    empty_initial = derive([], [201], _policy(known=True, launch=True, restart=True), uac_consumed=False)
    tests.append(_case(
        "no_original_client_with_new_client_is_complete",
        empty_initial["code"] == "OK" and empty_initial["initial_pid_count"] == 0,
        group="official-lifecycle",
    ))

    tests.append(_case(
        "lifecycle_derivation_never_parses_human_message",
        all(x["human_message_parsed"] is False for x in (unknown, not_requested, restart_disabled, replaced, old_and_new, consumed)),
        group="official-lifecycle",
    ))
    tests.append(_case(
        "lifecycle_derivation_never_grants_production_authority",
        all(
            x["production_effect_authorized"] is False
            and x["windows_runtime_certified"] is False
            and x["production_score_mutation_authorized"] is False
            for x in (unknown, not_requested, restart_disabled, replaced, old_and_new, consumed)
        ),
        group="official-lifecycle",
    ))
    return tests


def _classification_and_redaction_cases() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    tests.extend([
        _case(
            "restart_barrier_requires_prefix",
            contract.classify_error("CODEX_RESTART_REQUIRED: x") == contract.RECOVERY_CLIENT_CLOSE_BLOCKED
            and contract.classify_error("prefix CODEX_RESTART_REQUIRED: x") != contract.RECOVERY_CLIENT_CLOSE_BLOCKED,
            group="classification-redaction",
        ),
        _case(
            "wsaeacces_is_access_denied",
            contract.classify_error("WSAEACCES WinError 10013") == contract.RECOVERY_ACCESS_DENIED,
            group="classification-redaction",
        ),
        _case(
            "sharing_violation_is_file_in_use",
            contract.classify_error("sharing violation") == contract.RECOVERY_FILE_IN_USE,
            group="classification-redaction",
        ),
        _case(
            "errno2_is_program_missing",
            contract.classify_error("errno 2 executable not found") == contract.RECOVERY_PROGRAM_MISSING,
            group="classification-redaction",
        ),
    ])

    secret = (
        r"C:\Users\alice\AppData\Local\HMS authORIZATION=abc123 access_token=tok123 "
        r"user@example.com Bearer verysecrettoken123456 sk-supersecret123456 "
        r"eyJabcdefghijklmno.abcdefghijk.abcdefghijk"
    )
    sanitized = contract.sanitize_detail(secret)
    tests.append(_case(
        "secrets_username_and_email_are_redacted",
        all(token not in sanitized for token in ("alice", "abc123", "tok123", "verysecrettoken", "supersecret", "eyJabcdefgh"))
        and r"C:\Users\<USER>" in sanitized
        and "u***@example.com" in sanitized,
        group="classification-redaction",
    ))

    long_text = "x" * 10000
    tests.append(_case(
        "sanitized_detail_is_bounded",
        len(contract.sanitize_detail(long_text, limit=512)) == 512,
        group="classification-redaction",
    ))

    quiet_names = ["get_status", "refresh_quota", "health_probe", "list_accounts", "telemetry_snapshot", "inspect_state"]
    interactive_names = ["enable", "disable", "restart_router", "open_codex", "set_request_log", "repair_profile", "backup_export"]
    tests.append(_case(
        "background_action_names_remain_quiet",
        all(gui._is_interactive_backend_action(name) is False for name in quiet_names),
        group="classification-redaction",
    ))
    tests.append(_case(
        "interactive_action_names_remain_interactive",
        all(gui._is_interactive_backend_action(name) is True for name in interactive_names),
        group="classification-redaction",
    ))
    tests.append(_case(
        "mixed_token_action_prefers_interactive_safety",
        gui._is_interactive_backend_action("refresh_enable") is True,
        group="classification-redaction",
    ))
    return tests


def adversarial_proof() -> dict[str, Any]:
    tests = [
        *_recovery_plan_cases(),
        *_pid_race_cases(),
        *_official_lifecycle_cases(),
        *_classification_and_redaction_cases(),
    ]

    source = Path(__file__).read_text("utf-8")
    implementation = source[:source.find("def adversarial_proof")]
    source_checks = [
        _case(
            "simulator_never_invokes_real_elevation_helper",
            "elevated_close_supported_processes(" not in implementation,
            group="source-boundary",
        ),
        _case(
            "simulator_never_enumerates_real_processes",
            "discover_supported_client_pids(" not in implementation and "_enumerate_process_map_windows(" not in implementation,
            group="source-boundary",
        ),
        _case(
            "simulator_never_invokes_win32_uac_runner",
            "_run_elevated_taskkill(" not in implementation,
            group="source-boundary",
        ),
        _case(
            "simulator_has_no_production_authority",
            '"production_score_mutation_authorized": True' not in implementation
            and '"windows_runtime_certified": True' not in implementation,
            group="source-boundary",
        ),
    ]
    tests.extend(source_checks)

    failed = [test for test in tests if test["status"] != "PASS"]
    groups: dict[str, dict[str, int]] = {}
    for test in tests:
        bucket = groups.setdefault(test["group"], {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        bucket["pass" if test["status"] == "PASS" else "fail"] += 1

    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "WINDOWS_RECOVERY_ADVERSARIAL_SIMULATOR",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests) - len(failed), "fail": len(failed), "total": len(tests)},
        "groups": groups,
        "tests": tests,
        "deterministic": True,
        "real_windows_processes_enumerated": False,
        "real_uac_prompt_executed": False,
        "real_client_process_closed": False,
        "production_evidence_eligible": False,
        "canonical_seven_case_certification": False,
        "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }


def main() -> int:
    result = adversarial_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
