#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsOneShotElevation as elevation

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
RUNTIME_DIR = Path(__file__).resolve().parent
BACKEND = RUNTIME_DIR / "HMS_AI_ROUTER_v25.23.1.ps1"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ACKNOWLEDGEMENT = "I_UNDERSTAND_CODEX_OR_CHATGPT_MAY_CLOSE"


def _base_report(mode: str) -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "WINDOWS_UAC_RECOVERY_RUNTIME_VALIDATION",
        "mode": mode,
        "windows_runtime_certified": False,
        "production_evidence_eligible": False,
        "production_score_mutation_authorized": False,
        "canonical_seven_case_certification": False,
    }


def _read_policy_via_backend() -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "WINDOWS_REQUIRED"}
    if not BACKEND.is_file():
        return {"available": False, "reason": "BACKEND_NOT_FOUND"}

    fd, result_name = tempfile.mkstemp(prefix="hms-v2575-uac-policy-", suffix=".json")
    os.close(fd)
    result_path = Path(result_name)
    try:
        cmd = [
            "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(BACKEND),
            "-BackendAction", "get_settings",
            "-BackendResultPath", str(result_path),
        ]
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        if completed.returncode != 0:
            return {"available": False, "reason": "GET_SETTINGS_PROCESS_FAILED", "exit_code": completed.returncode}
        if not result_path.is_file():
            return {"available": False, "reason": "GET_SETTINGS_RESULT_MISSING"}
        data = json.loads(result_path.read_text("utf-8-sig"))
        settings = data.get("settings") if isinstance(data, dict) else None
        if not isinstance(settings, dict):
            return {"available": False, "reason": "GET_SETTINGS_SCHEMA_INVALID"}
        launch = settings.get("CodexLaunchAfterAuthSwitch")
        restart = settings.get("RestartCodexOnSwitch")
        if not isinstance(launch, bool) or not isinstance(restart, bool):
            return {"available": False, "reason": "RECOVERY_POLICY_FIELDS_INVALID"}
        return {
            "available": True,
            "launch_after_auth_switch": launch,
            "restart_codex_on_switch": restart,
            "official_auth_uac_policy_eligible": bool(launch and restart),
            "source": "BACKEND_GET_SETTINGS_READ_ONLY",
        }
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "GET_SETTINGS_TIMEOUT"}
    except Exception as exc:
        return {"available": False, "reason": "GET_SETTINGS_FAILED", "detail": type(exc).__name__}
    finally:
        try:
            result_path.unlink(missing_ok=True)
        except Exception:
            pass


def _discover_identity_bound_targets() -> dict[int, dict[str, Any]]:
    return elevation.discover_supported_client_identities()


def _session_binding_ready(identities: dict[int, dict[str, Any]]) -> bool:
    if not identities:
        return False
    try:
        return all(int(row["session_id"]) >= 0 for row in identities.values())
    except Exception:
        return False


def preflight_report() -> dict[str, Any]:
    out = _base_report("PREFLIGHT_READ_ONLY")
    if os.name != "nt":
        out.update({"verdict": "BLOCKED", "reason": "WINDOWS_REQUIRED", "effects_executed": False})
        return out

    try:
        identities = _discover_identity_bound_targets()
        pids = sorted(identities)
    except Exception as exc:
        out.update({
            "verdict": "BLOCKED",
            "reason": "SUPPORTED_CLIENT_IDENTITY_DISCOVERY_FAILED",
            "detail": type(exc).__name__,
            "effects_executed": False,
        })
        return out

    session_ready = _session_binding_ready(identities)
    try:
        taskkill_path = str(elevation._system_taskkill_path())
        taskkill_available = True
    except Exception as exc:
        taskkill_path = ""
        taskkill_available = False
        taskkill_error = type(exc).__name__
    else:
        taskkill_error = ""

    out.update({
        "verdict": "READY" if taskkill_available and session_ready else "BLOCKED",
        "supported_client_pids": pids,
        "supported_client_count": len(pids),
        "identity_binding_ready": bool(pids),
        "session_binding_ready": session_ready,
        "interactive_prerequisite_met": bool(pids) and taskkill_available and session_ready,
        "fixed_taskkill_available": taskkill_available,
        "fixed_taskkill_path": taskkill_path,
        "fixed_taskkill_error": taskkill_error,
        "policy": _read_policy_via_backend(),
        "effects_executed": False,
        "uac_prompt_executed": False,
        "operator_note": "Interactive validation requires explicit acknowledgement and may close only current-session identity-bound Codex/ChatGPT processes if UAC is accepted.",
    })
    return out


def _classify_interactive_exception(exc: Exception) -> str:
    text = str(exc)
    if "WINDOWS_ELEVATION_CANCELLED" in text:
        return "UAC_CANCELLED"
    if "WINDOWS_ELEVATION_TIMEOUT" in text:
        return "UAC_TIMEOUT"
    if "WINDOWS_ELEVATION_TARGET_SESSION_" in text:
        return "SESSION_CHANGED"
    if "WINDOWS_ELEVATION_TARGET_IDENTITY_CHANGED" in text:
        return "IDENTITY_CHANGED"
    return "FAILED"


def interactive_report(acknowledgement: str) -> dict[str, Any]:
    out = _base_report("INTERACTIVE_ONE_SHOT")
    if acknowledgement != ACKNOWLEDGEMENT:
        out.update({
            "verdict": "BLOCKED",
            "reason": "EXPLICIT_ACKNOWLEDGEMENT_REQUIRED",
            "required_acknowledgement": ACKNOWLEDGEMENT,
            "effects_executed": False,
            "uac_prompt_executed": False,
        })
        return out
    if os.name != "nt":
        out.update({"verdict": "BLOCKED", "reason": "WINDOWS_REQUIRED", "effects_executed": False})
        return out

    try:
        identities = _discover_identity_bound_targets()
        pids = sorted(identities)
    except Exception as exc:
        out.update({"verdict": "BLOCKED", "reason": "SUPPORTED_CLIENT_IDENTITY_DISCOVERY_FAILED", "detail": type(exc).__name__})
        return out
    if not pids:
        out.update({
            "verdict": "BLOCKED",
            "reason": "NO_SUPPORTED_CODEX_CLIENT_RUNNING",
            "effects_executed": False,
            "uac_prompt_executed": False,
        })
        return out
    if not _session_binding_ready(identities):
        out.update({
            "verdict": "BLOCKED",
            "reason": "CURRENT_WINDOWS_SESSION_BINDING_REQUIRED",
            "effects_executed": False,
            "uac_prompt_executed": False,
        })
        return out

    token = secrets.token_urlsafe(24)
    first_outcome = ""
    first_detail = ""
    uac_prompt_executed = False
    closed_pid_count = 0
    identity_bound = False
    session_bound = False
    pid_reuse_blocked = False
    try:
        first = elevation.elevated_close_supported_processes(
            pids, operation_token=token, expected_identities=identities,
        )
        uac_prompt_executed = bool(first.get("uac_prompt_started"))
        closed_pid_count = int(first.get("closed_pid_count") or 0)
        identity_bound = first.get("identity_bound") is True
        session_bound = first.get("session_bound") is True
        pid_reuse_blocked = first.get("pid_reuse_blocked_by_open_handles") is True
        if first.get("ok") and uac_prompt_executed and closed_pid_count > 0 and identity_bound and session_bound and pid_reuse_blocked:
            first_outcome = "SUPPORTED_CLIENTS_CLOSED"
        elif first.get("ok") and first.get("already_closed") and identity_bound and session_bound:
            first_outcome = "ALREADY_CLOSED_BEFORE_UAC"
        else:
            first_outcome = "FAILED"
    except Exception as exc:
        first_outcome = _classify_interactive_exception(exc)
        first_detail = type(exc).__name__
        uac_prompt_executed = first_outcome in {"UAC_CANCELLED", "UAC_TIMEOUT"}

    replay_blocked = False
    replay_reason = ""
    try:
        elevation.elevated_close_supported_processes(
            pids, operation_token=token, expected_identities=identities,
        )
    except Exception as exc:
        replay_reason = str(exc)
        replay_blocked = "WINDOWS_ELEVATION_OPERATION_TOKEN_ALREADY_CONSUMED" in replay_reason

    try:
        remaining = sorted(_discover_identity_bound_targets())
    except Exception:
        remaining = []

    if first_outcome == "SUPPORTED_CLIENTS_CLOSED" and replay_blocked and uac_prompt_executed and closed_pid_count > 0 and identity_bound and session_bound and pid_reuse_blocked:
        verdict = "PASS_CLOSE_AND_REPLAY_BLOCK"
    elif first_outcome == "UAC_CANCELLED" and replay_blocked and uac_prompt_executed:
        verdict = "PASS_CANCEL_AND_REPLAY_BLOCK"
    elif first_outcome == "IDENTITY_CHANGED" and replay_blocked:
        verdict = "PASS_IDENTITY_CHANGE_AND_REPLAY_BLOCK"
    elif first_outcome == "SESSION_CHANGED" and replay_blocked:
        verdict = "PASS_SESSION_CHANGE_AND_REPLAY_BLOCK"
    elif replay_blocked:
        verdict = "PARTIAL_REPLAY_BLOCKED"
    else:
        verdict = "FAIL"

    effects_executed = bool(first_outcome == "SUPPORTED_CLIENTS_CLOSED" and uac_prompt_executed and closed_pid_count > 0)
    out.update({
        "verdict": verdict,
        "initial_supported_client_pids": pids,
        "identity_binding_used": True,
        "session_binding_used": True,
        "session_bound": session_bound,
        "pid_reuse_blocked_by_open_handles": pid_reuse_blocked,
        "first_outcome": first_outcome,
        "first_detail_type": first_detail,
        "uac_prompt_executed": uac_prompt_executed,
        "closed_pid_count": closed_pid_count,
        "same_token_replay_blocked": replay_blocked,
        "replay_reason_code": "WINDOWS_ELEVATION_OPERATION_TOKEN_ALREADY_CONSUMED" if replay_blocked else "UNCONFIRMED",
        "remaining_supported_client_pids": remaining,
        "effects_executed": effects_executed,
        "operator_note": "This report validates bounded current-session identity-bound recovery mechanics only and cannot certify the canonical seven-case production gate.",
    })
    return out


def _write_optional_report(report: dict[str, Any], output: str) -> None:
    target = str(output or "").strip()
    if not target:
        return
    path = Path(target).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    os.replace(tmp, path)


def synthetic_proof() -> dict[str, Any]:
    src = Path(__file__).read_text("utf-8")
    proof_pos = src.find("def synthetic_proof")
    impl_src = src[:proof_pos]
    interactive_pos = src.find("def interactive_report")
    writer_pos = src.find("def _write_optional_report")
    helper_pos = src.find("elevation.elevated_close_supported_processes", interactive_pos, writer_pos)
    ack_pos = src.find("acknowledgement != ACKNOWLEDGEMENT", interactive_pos, writer_pos)
    preflight_src = src[src.find("def preflight_report"):interactive_pos]
    policy_src = src[src.find("def _read_policy_via_backend"):src.find("def _discover_identity_bound_targets")]
    interactive_src = src[interactive_pos:writer_pos]
    writer_src = src[writer_pos:proof_pos]
    checks = {
        "interactive_requires_exact_acknowledgement": ACKNOWLEDGEMENT in impl_src and 0 <= ack_pos < helper_pos,
        "preflight_never_calls_elevated_helper": "elevated_close_supported_processes" not in preflight_src,
        "preflight_only_uses_readonly_settings_action": '"-BackendAction", "get_settings"' in policy_src,
        "policy_report_whitelists_only_required_booleans": "CodexLaunchAfterAuthSwitch" in policy_src and "RestartCodexOnSwitch" in policy_src and '"settings": settings' not in policy_src,
        "preflight_requires_current_session_binding": "session_binding_ready" in preflight_src and "interactive_prerequisite_met" in preflight_src,
        "interactive_discovers_identity_bound_targets_before_uac": interactive_src.find("_discover_identity_bound_targets()") < interactive_src.find("elevation.elevated_close_supported_processes"),
        "interactive_passes_expected_identities": interactive_src.count("expected_identities=identities") >= 2,
        "interactive_uses_random_one_shot_token": "secrets.token_urlsafe(24)" in interactive_src,
        "interactive_replays_same_token_for_block_proof": interactive_src.count("operation_token=token") >= 2,
        "cancel_is_distinguished": "UAC_CANCELLED" in interactive_src and "PASS_CANCEL_AND_REPLAY_BLOCK" in interactive_src,
        "identity_change_is_distinguished": "IDENTITY_CHANGED" in interactive_src and "PASS_IDENTITY_CHANGE_AND_REPLAY_BLOCK" in interactive_src,
        "session_change_is_distinguished": "SESSION_CHANGED" in interactive_src and "PASS_SESSION_CHANGE_AND_REPLAY_BLOCK" in interactive_src,
        "successful_close_requires_identity_session_and_pid_reuse_guard": "identity_bound and session_bound and pid_reuse_blocked" in interactive_src and "PASS_CLOSE_AND_REPLAY_BLOCK" in interactive_src,
        "report_surfaces_session_binding": '"session_binding_used": True' in interactive_src and '"session_bound": session_bound' in interactive_src,
        "already_closed_is_not_successful_close": "ALREADY_CLOSED_BEFORE_UAC" in interactive_src and 'first_outcome = "SUPPORTED_CLIENTS_CLOSED" if first.get("ok")' not in interactive_src,
        "output_is_optional": 'if not target:' in writer_src and "return" in writer_src,
        "report_never_claims_production_certification": '"windows_runtime_certified": False' in impl_src and '"canonical_seven_case_certification": False' in impl_src,
        "no_automatic_score_mutation": '"production_score_mutation_authorized": False' in impl_src,
        "no_generic_elevation_command": '"runas"' not in impl_src and "ShellExecute" not in impl_src,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    source_passed = sum(test["status"] == "PASS" for test in tests)

    import HMS_Codex_WindowsRecoveryAdversarialSimulator as adversarial
    adversarial_result = adversarial.adversarial_proof()
    child_summary = adversarial_result.get("summary") if isinstance(adversarial_result.get("summary"), dict) else {}
    child_pass = int(child_summary.get("pass") or 0)
    child_fail = int(child_summary.get("fail") or 0)
    child_total = int(child_summary.get("total") or 0)
    child_ok = adversarial_result.get("verdict") == "PASS" and child_fail == 0 and child_total > 0

    source_fail = len(tests) - source_passed
    out = _base_report("SYNTHETIC_PROOF")
    out.update({
        "verdict": "PASS" if source_fail == 0 and child_ok else "FAIL",
        "summary": {
            "pass": source_passed + child_pass,
            "fail": source_fail + child_fail + (0 if child_ok else (1 if child_total == 0 else 0)),
            "total": len(tests) + child_total + (1 if child_total == 0 else 0),
        },
        "source_proof_summary": {"pass": source_passed, "fail": source_fail, "total": len(tests)},
        "adversarial_simulator_summary": child_summary,
        "adversarial_simulator_groups": adversarial_result.get("groups") or {},
        "tests": tests,
        "real_windows_checked": False,
        "real_uac_prompt_executed": False,
        "real_client_process_closed": False,
    })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded HMS Windows UAC recovery validation; separate from production certification.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("proof", help="Run source/synthetic proof only; no Windows effects.")
    pre = sub.add_parser("preflight", help="Read-only Windows preflight; no UAC and no client close.")
    pre.add_argument("--output", default="", help="Optional JSON report path.")
    inter = sub.add_parser("interactive", help="Interactive one-shot UAC validation; may close current-session identity-bound Codex/ChatGPT clients.")
    inter.add_argument("--acknowledge", default="", help=f"Must equal: {ACKNOWLEDGEMENT}")
    inter.add_argument("--output", default="", help="Optional JSON report path.")
    args = parser.parse_args()

    if args.command == "proof":
        report = synthetic_proof()
    elif args.command == "preflight":
        report = preflight_report()
        _write_optional_report(report, args.output)
    else:
        report = interactive_report(args.acknowledge)
        _write_optional_report(report, args.output)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command == "proof":
        return 0 if report.get("verdict") == "PASS" else 2
    if args.command == "preflight":
        return 0 if report.get("verdict") == "READY" else 3
    return 0 if str(report.get("verdict", "")).startswith("PASS_") else 4


if __name__ == "__main__":
    raise SystemExit(main())
