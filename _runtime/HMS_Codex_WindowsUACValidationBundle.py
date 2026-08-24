#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsUACRecoveryValidation as harness

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
SCHEMA_VERSION = 1
SESSION_TTL_SECONDS = 4 * 60 * 60
RUNTIME_DIR = Path(__file__).resolve().parent
SOURCE_FILES = (
    "HMS_Codex_WindowsOneShotElevation.py",
    "HMS_Codex_WindowsRecoveryContract.py",
    "HMS_Codex_WindowsUACRecoveryValidation.py",
    "HMS_Codex_WindowsUACValidationBundle.py",
)
EXPECTED_CANCEL = "PASS_CANCEL_AND_REPLAY_BLOCK"
EXPECTED_CLOSE = "PASS_CLOSE_AND_REPLAY_BLOCK"


def _stable(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, value: Any) -> None:
    path = path.expanduser().resolve(); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8"); os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("VALIDATION_JSON_OBJECT_REQUIRED")
    return value


def _source_bundle_sha256() -> str:
    entries: list[dict[str, str]] = []
    for name in SOURCE_FILES:
        path = RUNTIME_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"VALIDATION_SOURCE_MISSING:{name}")
        entries.append({"name": name, "sha256": _sha256_bytes(path.read_bytes())})
    return _sha256_bytes(_stable(entries))


def _host_ref() -> str:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
    except Exception as exc:
        raise RuntimeError("WINDOWS_MACHINE_ID_UNAVAILABLE") from exc
    digest = _sha256_bytes(f"{PRODUCT}|{VERSION}|{str(machine_guid).strip()}".encode("utf-8"))
    return "sha256:" + digest


def _session_digest(session: dict[str, Any]) -> str:
    return _sha256_bytes(_stable(session))


def session_init(output: Path) -> dict[str, Any]:
    if os.name != "nt":
        return {"verdict": "BLOCKED", "reason": "WINDOWS_REQUIRED", "session_written": False}
    preflight = harness.preflight_report()
    if preflight.get("verdict") != "READY":
        return {"verdict": "BLOCKED", "reason": "PREFLIGHT_NOT_READY", "preflight": preflight, "session_written": False}
    if preflight.get("interactive_prerequisite_met") is not True:
        return {"verdict": "BLOCKED", "reason": "SUPPORTED_CLIENT_REQUIRED_FOR_SESSION", "preflight": preflight, "session_written": False}
    if preflight.get("identity_binding_ready") is not True:
        return {"verdict": "BLOCKED", "reason": "PROCESS_IDENTITY_BINDING_REQUIRED", "preflight": preflight, "session_written": False}
    if preflight.get("session_binding_ready") is not True:
        return {"verdict": "BLOCKED", "reason": "WINDOWS_SESSION_BINDING_REQUIRED", "preflight": preflight, "session_written": False}

    now = _utcnow()
    session = {
        "schema_version": SCHEMA_VERSION,
        "product": PRODUCT,
        "version": VERSION,
        "session_id": secrets.token_urlsafe(24),
        "created_utc": _utc_text(now),
        "expires_utc": _utc_text(now + timedelta(seconds=SESSION_TTL_SECONDS)),
        "host_ref": _host_ref(),
        "source_bundle_sha256": _source_bundle_sha256(),
        "preflight": {
            "supported_client_count": int(preflight.get("supported_client_count") or 0),
            "identity_binding_ready": preflight.get("identity_binding_ready") is True,
            "session_binding_ready": preflight.get("session_binding_ready") is True,
            "fixed_taskkill_available": preflight.get("fixed_taskkill_available") is True,
            "interactive_prerequisite_met": preflight.get("interactive_prerequisite_met") is True,
            "policy": preflight.get("policy") if isinstance(preflight.get("policy"), dict) else {},
        },
        "cryptographic_attestation": False,
        "production_evidence_eligible": False,
        "canonical_seven_case_certification": False,
        "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }
    _atomic_json(output, session)
    return {
        "verdict": "READY", "session_written": True, "session_id": session["session_id"],
        "session_sha256": _session_digest(session), "expires_utc": session["expires_utc"], "next": "run-cancel",
        "identity_binding_ready": True, "session_binding_ready": True,
        "production_evidence_eligible": False, "windows_runtime_certified": False,
    }


def _validate_session_runtime(session: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if session.get("schema_version") != SCHEMA_VERSION: reasons.append("SESSION_SCHEMA_INVALID")
    if session.get("product") != PRODUCT or session.get("version") != VERSION: reasons.append("SESSION_PRODUCT_VERSION_MISMATCH")
    if not str(session.get("session_id") or "").strip(): reasons.append("SESSION_ID_MISSING")
    preflight = session.get("preflight") if isinstance(session.get("preflight"), dict) else {}
    if preflight.get("identity_binding_ready") is not True: reasons.append("SESSION_IDENTITY_BINDING_INVALID")
    if preflight.get("session_binding_ready") is not True: reasons.append("SESSION_WINDOWS_SESSION_BINDING_INVALID")
    try:
        if _utcnow() > _parse_utc(session.get("expires_utc")): reasons.append("SESSION_EXPIRED")
    except Exception:
        reasons.append("SESSION_EXPIRY_INVALID")
    try:
        if session.get("host_ref") != _host_ref(): reasons.append("SESSION_HOST_MISMATCH")
    except Exception:
        reasons.append("SESSION_HOST_UNAVAILABLE")
    try:
        if session.get("source_bundle_sha256") != _source_bundle_sha256(): reasons.append("SESSION_SOURCE_MISMATCH")
    except Exception:
        reasons.append("SESSION_SOURCE_UNAVAILABLE")
    if session.get("production_evidence_eligible") is not False: reasons.append("SESSION_PRODUCTION_BOUNDARY_INVALID")
    if session.get("windows_runtime_certified") is not False: reasons.append("SESSION_CERTIFICATION_BOUNDARY_INVALID")
    return sorted(set(reasons))


def run_case(session_path: Path, output: Path, case_type: str) -> dict[str, Any]:
    if case_type not in {"cancel", "close"}:
        raise ValueError("VALIDATION_CASE_INVALID")
    session = _read_json(session_path); reasons = _validate_session_runtime(session)
    if reasons:
        result = {"verdict": "BLOCKED", "reasons": reasons, "case_type": case_type, "effects_executed": False}
        _atomic_json(output, result); return result
    captured_utc = _utc_text(_utcnow()); interactive = harness.interactive_report(harness.ACKNOWLEDGEMENT)
    expected = EXPECTED_CANCEL if case_type == "cancel" else EXPECTED_CLOSE
    case_pass = interactive.get("verdict") == expected
    report = {
        "schema_version": SCHEMA_VERSION, "product": PRODUCT, "version": VERSION,
        "suite": "WINDOWS_UAC_RECOVERY_VALIDATION_CASE", "case_type": case_type,
        "expected_verdict": expected, "case_pass": case_pass, "captured_utc": captured_utc,
        "session_id": session["session_id"], "session_sha256": _session_digest(session),
        "host_ref": session["host_ref"], "source_bundle_sha256": session["source_bundle_sha256"],
        "interactive": interactive,
        "cryptographic_attestation": False, "production_evidence_eligible": False,
        "canonical_seven_case_certification": False, "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }
    report["report_sha256"] = _sha256_bytes(_stable({k: v for k, v in report.items() if k != "report_sha256"}))
    _atomic_json(output, report); return report


def _verify_pair_data(session: dict[str, Any], cancel: dict[str, Any], close: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []; session_id = str(session.get("session_id") or ""); session_sha = _session_digest(session)
    host_ref = str(session.get("host_ref") or ""); source_sha = str(session.get("source_bundle_sha256") or "")
    session_preflight = session.get("preflight") if isinstance(session.get("preflight"), dict) else {}
    if session_preflight.get("identity_binding_ready") is not True: reasons.append("SESSION_IDENTITY_BINDING_INVALID")
    if session_preflight.get("session_binding_ready") is not True: reasons.append("SESSION_WINDOWS_SESSION_BINDING_INVALID")

    for label, report, case_type, expected in (
        ("CANCEL", cancel, "cancel", EXPECTED_CANCEL), ("CLOSE", close, "close", EXPECTED_CLOSE),
    ):
        if report.get("schema_version") != SCHEMA_VERSION: reasons.append(f"{label}_SCHEMA_INVALID")
        if report.get("product") != PRODUCT or report.get("version") != VERSION: reasons.append(f"{label}_PRODUCT_VERSION_MISMATCH")
        if report.get("case_type") != case_type: reasons.append(f"{label}_CASE_TYPE_INVALID")
        if report.get("expected_verdict") != expected: reasons.append(f"{label}_EXPECTED_VERDICT_INVALID")
        if report.get("case_pass") is not True: reasons.append(f"{label}_CASE_NOT_PASS")
        if report.get("session_id") != session_id or report.get("session_sha256") != session_sha: reasons.append(f"{label}_SESSION_MISMATCH")
        if report.get("host_ref") != host_ref: reasons.append(f"{label}_HOST_MISMATCH")
        if report.get("source_bundle_sha256") != source_sha: reasons.append(f"{label}_SOURCE_MISMATCH")
        if report.get("production_evidence_eligible") is not False: reasons.append(f"{label}_PRODUCTION_BOUNDARY_INVALID")
        if report.get("windows_runtime_certified") is not False: reasons.append(f"{label}_CERTIFICATION_BOUNDARY_INVALID")
        interactive = report.get("interactive") if isinstance(report.get("interactive"), dict) else {}
        if interactive.get("verdict") != expected: reasons.append(f"{label}_INTERACTIVE_VERDICT_INVALID")
        if interactive.get("same_token_replay_blocked") is not True: reasons.append(f"{label}_REPLAY_NOT_BLOCKED")
        if interactive.get("uac_prompt_executed") is not True: reasons.append(f"{label}_UAC_PROMPT_NOT_OBSERVED")
        if interactive.get("identity_binding_used") is not True: reasons.append(f"{label}_IDENTITY_BINDING_NOT_OBSERVED")
        if interactive.get("session_binding_used") is not True: reasons.append(f"{label}_SESSION_BINDING_NOT_OBSERVED")

    cancel_interactive = cancel.get("interactive") if isinstance(cancel.get("interactive"), dict) else {}
    close_interactive = close.get("interactive") if isinstance(close.get("interactive"), dict) else {}
    if cancel_interactive.get("effects_executed") is not False: reasons.append("CANCEL_EFFECT_BOUNDARY_INVALID")
    if close_interactive.get("effects_executed") is not True: reasons.append("CLOSE_EFFECT_NOT_OBSERVED")
    if int(close_interactive.get("closed_pid_count") or 0) <= 0: reasons.append("CLOSE_PID_COUNT_INVALID")
    if close_interactive.get("session_bound") is not True: reasons.append("CLOSE_WINDOWS_SESSION_BOUNDARY_NOT_OBSERVED")
    if close_interactive.get("pid_reuse_blocked_by_open_handles") is not True: reasons.append("CLOSE_PID_REUSE_GUARD_NOT_OBSERVED")

    try:
        cancel_time = _parse_utc(cancel.get("captured_utc")); close_time = _parse_utc(close.get("captured_utc"))
        created = _parse_utc(session.get("created_utc")); expires = _parse_utc(session.get("expires_utc"))
        if not (created <= cancel_time <= close_time <= expires): reasons.append("CASE_TIME_ORDER_INVALID")
    except Exception:
        reasons.append("CASE_TIME_INVALID")
    if cancel.get("report_sha256") == close.get("report_sha256"): reasons.append("CASE_REPORT_DIGEST_COLLISION")
    return {
        "verdict": "PASS_BOUNDED_UAC_RECOVERY_PAIR" if not reasons else "BLOCKED_FAIL_CLOSED", "valid": not reasons,
        "reasons": sorted(set(reasons)), "session_id": session_id, "host_ref": host_ref, "source_bundle_sha256": source_sha,
        "cancel_report_sha256": str(cancel.get("report_sha256") or ""), "close_report_sha256": str(close.get("report_sha256") or ""),
        "identity_binding_required": True, "session_binding_required": True,
        "cryptographic_attestation": False, "production_evidence_eligible": False,
        "canonical_seven_case_certification": False, "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    }


def verify_pair(session_path: Path, cancel_path: Path, close_path: Path, output: Path | None = None) -> dict[str, Any]:
    session = _read_json(session_path); cancel = _read_json(cancel_path); close = _read_json(close_path)
    result = _verify_pair_data(session, cancel, close)
    if output is not None: _atomic_json(output, result)
    return result


def synthetic_proof() -> dict[str, Any]:
    now = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)
    session = {
        "schema_version": 1, "product": PRODUCT, "version": VERSION, "session_id": "session-proof",
        "created_utc": _utc_text(now), "expires_utc": _utc_text(now + timedelta(hours=4)),
        "host_ref": "sha256:" + "a" * 64, "source_bundle_sha256": "b" * 64,
        "preflight": {"identity_binding_ready": True, "session_binding_ready": True},
        "production_evidence_eligible": False, "windows_runtime_certified": False,
    }
    session_sha = _session_digest(session)
    cancel = {
        "schema_version": 1, "product": PRODUCT, "version": VERSION, "case_type": "cancel",
        "expected_verdict": EXPECTED_CANCEL, "case_pass": True, "captured_utc": _utc_text(now + timedelta(minutes=5)),
        "session_id": session["session_id"], "session_sha256": session_sha, "host_ref": session["host_ref"],
        "source_bundle_sha256": session["source_bundle_sha256"], "production_evidence_eligible": False,
        "windows_runtime_certified": False, "report_sha256": "c" * 64,
        "interactive": {"verdict": EXPECTED_CANCEL, "same_token_replay_blocked": True, "uac_prompt_executed": True,
                        "identity_binding_used": True, "session_binding_used": True,
                        "effects_executed": False, "closed_pid_count": 0},
    }
    close = {
        "schema_version": 1, "product": PRODUCT, "version": VERSION, "case_type": "close",
        "expected_verdict": EXPECTED_CLOSE, "case_pass": True, "captured_utc": _utc_text(now + timedelta(minutes=10)),
        "session_id": session["session_id"], "session_sha256": session_sha, "host_ref": session["host_ref"],
        "source_bundle_sha256": session["source_bundle_sha256"], "production_evidence_eligible": False,
        "windows_runtime_certified": False, "report_sha256": "d" * 64,
        "interactive": {"verdict": EXPECTED_CLOSE, "same_token_replay_blocked": True, "uac_prompt_executed": True,
                        "identity_binding_used": True, "session_binding_used": True, "session_bound": True,
                        "pid_reuse_blocked_by_open_handles": True, "effects_executed": True, "closed_pid_count": 2},
    }
    good = _verify_pair_data(session, cancel, close)
    bad_replay = _verify_pair_data(session, dict(cancel, interactive=dict(cancel["interactive"], same_token_replay_blocked=False)), close)
    bad_host = _verify_pair_data(session, cancel, dict(close, host_ref="sha256:" + "e" * 64))
    bad_source = _verify_pair_data(session, cancel, dict(close, source_bundle_sha256="f" * 64))
    bad_order = _verify_pair_data(session, dict(cancel, captured_utc=_utc_text(now + timedelta(minutes=20))), close)
    bad_close = _verify_pair_data(session, cancel, dict(close, interactive=dict(close["interactive"], effects_executed=False, closed_pid_count=0)))
    bad_identity = _verify_pair_data(session, cancel, dict(close, interactive=dict(close["interactive"], identity_binding_used=False)))
    bad_session_use = _verify_pair_data(session, cancel, dict(close, interactive=dict(close["interactive"], session_binding_used=False)))
    bad_session_bound = _verify_pair_data(session, cancel, dict(close, interactive=dict(close["interactive"], session_bound=False)))
    bad_pid_reuse_guard = _verify_pair_data(session, cancel, dict(close, interactive=dict(close["interactive"], pid_reuse_blocked_by_open_handles=False)))
    src = Path(__file__).read_text("utf-8"); impl_src = src[:src.find("def synthetic_proof")]
    checks = {
        "valid_pair_passes": good["valid"] is True and good["verdict"] == "PASS_BOUNDED_UAC_RECOVERY_PAIR",
        "replay_failure_rejected": bad_replay["valid"] is False and "CANCEL_REPLAY_NOT_BLOCKED" in bad_replay["reasons"],
        "host_mismatch_rejected": bad_host["valid"] is False and "CLOSE_HOST_MISMATCH" in bad_host["reasons"],
        "source_mismatch_rejected": bad_source["valid"] is False and "CLOSE_SOURCE_MISMATCH" in bad_source["reasons"],
        "time_order_rejected": bad_order["valid"] is False and "CASE_TIME_ORDER_INVALID" in bad_order["reasons"],
        "close_effect_required": bad_close["valid"] is False and "CLOSE_EFFECT_NOT_OBSERVED" in bad_close["reasons"],
        "identity_binding_required": bad_identity["valid"] is False and "CLOSE_IDENTITY_BINDING_NOT_OBSERVED" in bad_identity["reasons"],
        "session_binding_use_required": bad_session_use["valid"] is False and "CLOSE_SESSION_BINDING_NOT_OBSERVED" in bad_session_use["reasons"],
        "close_session_boundary_required": bad_session_bound["valid"] is False and "CLOSE_WINDOWS_SESSION_BOUNDARY_NOT_OBSERVED" in bad_session_bound["reasons"],
        "pid_reuse_guard_required": bad_pid_reuse_guard["valid"] is False and "CLOSE_PID_REUSE_GUARD_NOT_OBSERVED" in bad_pid_reuse_guard["reasons"],
        "machine_guid_is_hashed_before_output": "MachineGuid" in impl_src and 'return "sha256:" + digest' in impl_src,
        "session_requires_readonly_identity_and_windows_session_preflight": "harness.preflight_report()" in impl_src and "identity_binding_ready" in impl_src and "session_binding_ready" in impl_src,
        "case_runner_uses_bounded_harness": "harness.interactive_report(harness.ACKNOWLEDGEMENT)" in impl_src,
        "cancel_and_close_have_exact_expected_verdicts": EXPECTED_CANCEL in impl_src and EXPECTED_CLOSE in impl_src,
        "four_hour_session_expiry": "SESSION_TTL_SECONDS = 4 * 60 * 60" in impl_src,
        "no_production_authority": '"production_evidence_eligible": False' in impl_src and '"windows_runtime_certified": False' in impl_src,
        "no_certificate_or_evidence_import": "certificate_sign" not in impl_src and "reviewer_import" not in impl_src,
    }
    tests = [{"name": name, "status": "PASS" if value else "FAIL"} for name, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {"product": PRODUCT, "version": VERSION, "suite": "WINDOWS_UAC_VALIDATION_BUNDLE_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)}, "tests": tests,
            "real_windows_uac_executed": False, "production_evidence_eligible": False,
            "windows_runtime_certified": False, "production_score_mutation_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Session-bound bounded UAC recovery validation; never production certification.")
    sub = parser.add_subparsers(dest="command", required=True); sub.add_parser("proof")
    init = sub.add_parser("init"); init.add_argument("--output", required=True)
    cancel = sub.add_parser("run-cancel"); cancel.add_argument("--session", required=True); cancel.add_argument("--output", required=True)
    close = sub.add_parser("run-close"); close.add_argument("--session", required=True); close.add_argument("--output", required=True)
    verify = sub.add_parser("verify"); verify.add_argument("--session", required=True); verify.add_argument("--cancel", required=True); verify.add_argument("--close", required=True); verify.add_argument("--output", default="")
    args = parser.parse_args()
    if args.command == "proof": result = synthetic_proof()
    elif args.command == "init": result = session_init(Path(args.output))
    elif args.command == "run-cancel": result = run_case(Path(args.session), Path(args.output), "cancel")
    elif args.command == "run-close": result = run_case(Path(args.session), Path(args.output), "close")
    else: result = verify_pair(Path(args.session), Path(args.cancel), Path(args.close), Path(args.output) if args.output else None)
    print(json.dumps(result, ensure_ascii=False, indent=2)); verdict = str(result.get("verdict") or "")
    if args.command == "proof": return 0 if verdict == "PASS" else 2
    if args.command == "init": return 0 if verdict == "READY" else 3
    if args.command in {"run-cancel", "run-close"}: return 0 if result.get("case_pass") is True else 4
    return 0 if verdict == "PASS_BOUNDED_UAC_RECOVERY_PAIR" else 5


if __name__ == "__main__":
    raise SystemExit(main())
