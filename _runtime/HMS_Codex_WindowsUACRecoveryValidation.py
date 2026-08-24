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


def preflight_report() -> dict[str, Any]:
    out = _base_report("PREFLIGHT_READ_ONLY")
    if os.name != "nt":
        out.update({"verdict": "BLOCKED", "reason": "WINDOWS_REQUIRED", "effects_executed": False})
        return out

    try:
        pids = elevation.discover_supported_client_pids()
    except Exception as exc:
        out.update({
            "verdict": "BLOCKED",
            "reason": "SUPPORTED_CLIENT_DISCOVERY_FAILED",
            "detail": type(exc).__name__,
            "effects_executed": False,
        })
        return out

    try:
        taskkill_path = str(elevation._system_taskkill_path())  # read-only verification of the fixed system target
        taskkill_available = True
    except Exception as exc:
        taskkill_path = ""
        taskkill_available = False
        taskkill_error = type(exc).__name__
    else:
        taskkill_error = ""

    out.update({
        "verdict": "READY" if taskkill_available else "BLOCKED",
        "supported_client_pids": pids,
        "supported_client_count": len(pids),
        "fixed_taskkill_available": taskkill_available,
        "fixed_taskkill_path": taskkill_path,
        "fixed_taskkill_error": taskkill_error,
        "policy": _read_policy_via_backend(),
        "effects_executed": False,
        "uac_prompt_executed": False,
        "operator_note": "Interactive validation requires explicit acknowledgement and may close Codex/ChatGPT if UAC is accepted.",
    })
    return out


def _classify_interactive_exception(exc: Exception) -> str:
    text = str(exc)
    if "WINDOWS_ELEVATION_CANCELLED" in text:
        return "UAC_CANCELLED"
    if "WINDOWS_ELEVATION_TIMEOUT" in text:
        return "UAC_TIMEOUT"
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
        pids = elevation.discover_supported_client_pids()
    except Exception as exc:
        out.update({"verdict": "BLOCKED", "reason": "SUPPORTED_CLIENT_DISCOVERY_FAILED", "detail": type(exc).__name__})
        return out
    if not pids:
        out.update({
            "verdict": "BLOCKED",
            "reason": "NO_SUPPORTED_CODEX_CLIENT_RUNNING",
            "effects_executed": False,
            "uac_prompt_executed": False,
        })
        return out

    token = secrets.token_urlsafe(24)
    first_outcome = ""
    first_detail = ""
    uac_prompt_executed = False
    closed_pid_count = 0
    try:
        first = elevation.elevated_close_supported_processes(pids, operation_token=token)
        uac_prompt_executed = bool(first.get("uac_prompt_started"))
        closed_pid_count = int(first.get("closed_pid_count") or 0)
        first_outcome = "SUPPORTED_CLIENTS_CLOSED" if first.get("ok") else "FAILED"
    except Exception as exc:
        first_outcome = _classify_interactive_exception(exc)
        first_detail = type(exc).__name__
        # A cancellation is only possible after Windows started the elevation prompt.
        uac_prompt_executed = first_outcome in {"UAC_CANCELLED", "UAC_TIMEOUT"}

    replay_blocked = False
    replay_reason = ""
    try:
        elevation.elevated_close_supported_processes(pids, operation_token=token)
    except Exception as exc:
        replay_reason = str(exc)
        replay_blocked = "WINDOWS_ELEVATION_OPERATION_TOKEN_ALREADY_CONSUMED" in replay_reason

    try:
        remaining = elevation.discover_supported_client_pids()
    except Exception:
        remaining = []

    if first_outcome == "SUPPORTED_CLIENTS_CLOSED" and replay_blocked:
        verdict = "PASS_CLOSE_AND_REPLAY_BLOCK"
    elif first_outcome == "UAC_CANCELLED" and replay_blocked:
        verdict = "PASS_CANCEL_AND_REPLAY_BLOCK"
    elif replay_blocked:
        verdict = "PARTIAL_REPLAY_BLOCKED"
    else:
        verdict = "FAIL"

    out.update({
        "verdict": verdict,
        "initial_supported_client_pids": pids,
        "first_outcome": first_outcome,
        "first_detail_type": first_detail,
        "uac_prompt_executed": uac_prompt_executed,
        "closed_pid_count": closed_pid_count,
        "same_token_replay_blocked": replay_blocked,
        "replay_reason_code": "WINDOWS_ELEVATION_OPERATION_TOKEN_ALREADY_CONSUMED" if replay_blocked else "UNCONFIRMED",
        "remaining_supported_client_pids": remaining,
        "effects_executed": first_outcome == "SUPPORTED_CLIENTS_CLOSED",
        "operator_note": "This report validates recovery mechanics only and cannot certify the canonical seven-case production gate.",
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
    interactive_pos = src.find("def interactive_report")
    helper_pos = src.find("elevation.elevated_close_supported_processes", interactive_pos)
    ack_pos = src.find("acknowledgement != ACKNOWLEDGEMENT", interactive_pos)
    preflight_src = src[src.find("def preflight_report"):interactive_pos]
    policy_src = src[src.find("def _read_policy_via_backend"):src.find("def preflight_report")]
    checks = {
        "interactive_requires_exact_acknowledgement": ACKNOWLEDGEMENT in src and 0 <= ack_pos < helper_pos,
        "preflight_never_calls_elevated_helper": "elevated_close_supported_processes" not in preflight_src,
        "preflight_only_uses_readonly_settings_action": '"-BackendAction", "get_settings"' in policy_src,
        "policy_report_whitelists_only_required_booleans": "CodexLaunchAfterAuthSwitch" in policy_src and "RestartCodexOnSwitch" in policy_src and '"settings": settings' not in policy_src,
        "interactive_discovers_supported_clients_before_uac": src.find("discover_supported_client_pids()", interactive_pos) < helper_pos,
        "interactive_uses_random_one_shot_token": "secrets.token_urlsafe(24)" in src[interactive_pos:],
        "interactive_replays_same_token_for_block_proof": src[interactive_pos:].count("operation_token=token") >= 2,
        "cancel_is_distinguished": "UAC_CANCELLED" in src[interactive_pos:] and "PASS_CANCEL_AND_REPLAY_BLOCK" in src,
        "successful_close_is_distinguished": "PASS_CLOSE_AND_REPLAY_BLOCK" in src,
        "output_is_optional": 'if not target:' in src and "return" in src[src.find("def _write_optional_report"):src.find("def synthetic_proof")],
        "report_never_claims_production_certification": '"windows_runtime_certified": False' in src and '"canonical_seven_case_certification": False' in src,
        "no_automatic_score_mutation": '"production_score_mutation_authorized": False' in src,
        "no_generic_elevation_command": '"runas"' not in src and "ShellExecute" not in src,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    out = _base_report("SYNTHETIC_PROOF")
    out.update({
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
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
    inter = sub.add_parser("interactive", help="Interactive one-shot UAC validation; may close supported Codex/ChatGPT clients.")
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
