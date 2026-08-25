#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"
TARGET_RELEASE = "1.3.29"
TARGET_COMMIT = "83ce2d192cc954cc910ce89edf2d1f710c218798"
SCOPE = "CODEX_ONLY"
DEVICE_CAPABILITY = "DEVICE_CODE_OAUTH"
DECISION_RECORD_NAME = "HMS_Codex_CockpitV1329DeviceAuthAdoptionDecision.json"

DECISION_OPEN = "OPEN"
DECISION_REQUIRE_PARITY = "REQUIRE_PARITY"
DECISION_ACCEPT_GAP = "ACCEPT_CAPABILITY_GAP"
ALLOWED_DECISIONS = {
    DECISION_OPEN,
    DECISION_REQUIRE_PARITY,
    DECISION_ACCEPT_GAP,
}

DECISION_RECORD_TEMPLATE: dict[str, Any] = {
    "schema_version": 1,
    "product": PRODUCT,
    "version": VERSION,
    "upstream_repository": UPSTREAM_REPOSITORY,
    "target_release": TARGET_RELEASE,
    "target_commit": TARGET_COMMIT,
    "scope": SCOPE,
    "capability": DEVICE_CAPABILITY,
    "decision": DECISION_OPEN,
    "accepted_by": "",
    "rationale": "",
    "risk_acknowledged": False,
    "parity_proof_ref": "",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _record_with(**updates: Any) -> dict[str, Any]:
    record = deepcopy(DECISION_RECORD_TEMPLATE)
    record.update(updates)
    return record


def _load_current_decision_authority() -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(__file__).resolve().with_name(DECISION_RECORD_NAME)
    authority: dict[str, Any] = {
        "file": DECISION_RECORD_NAME,
        "loaded": False,
        "sha256": "",
        "error": "",
    }
    try:
        raw = path.read_bytes()
    except OSError as exc:
        authority["error"] = f"DEVICE_AUTH_DECISION_FILE_UNREADABLE:{exc}"
        return {}, authority

    authority["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        authority["error"] = f"DEVICE_AUTH_DECISION_FILE_INVALID_JSON:{exc}"
        return {}, authority

    if not isinstance(parsed, dict):
        authority["error"] = "DEVICE_AUTH_DECISION_FILE_SHAPE_INVALID"
        return {}, authority

    authority["loaded"] = True
    return parsed, authority


def validate_decision_record(
    record: dict[str, Any],
    *,
    parity_proof_ready: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(record, dict):
        record = {}
        reasons.append("DEVICE_AUTH_DECISION_RECORD_SHAPE_INVALID")

    expected = {
        "schema_version": 1,
        "product": PRODUCT,
        "version": VERSION,
        "upstream_repository": UPSTREAM_REPOSITORY,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "scope": SCOPE,
        "capability": DEVICE_CAPABILITY,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            reasons.append(f"DEVICE_AUTH_DECISION_{key.upper()}_INVALID")

    decision = _text(record.get("decision"))
    accepted_by = _text(record.get("accepted_by"))
    rationale = _text(record.get("rationale"))
    parity_proof_ref = _text(record.get("parity_proof_ref"))
    risk_acknowledged = record.get("risk_acknowledged") is True

    if decision not in ALLOWED_DECISIONS:
        reasons.append("DEVICE_AUTH_DECISION_VALUE_INVALID")

    reconciliation_state = "DEVICE_AUTH_DECISION_RECORD_INVALID"
    if not reasons and decision == DECISION_OPEN:
        if accepted_by or rationale or risk_acknowledged or parity_proof_ref:
            reasons.append("OPEN_DEVICE_AUTH_DECISION_MUST_NOT_CARRY_ACCEPTANCE_AUTHORITY")
        else:
            reconciliation_state = "SOURCE_CHARACTERIZED_PROOF_WIRED_DECISION_OPEN"

    elif not reasons and decision == DECISION_ACCEPT_GAP:
        if not accepted_by:
            reasons.append("DEVICE_AUTH_GAP_ACCEPTOR_REQUIRED")
        if not rationale:
            reasons.append("DEVICE_AUTH_GAP_RATIONALE_REQUIRED")
        if not risk_acknowledged:
            reasons.append("DEVICE_AUTH_GAP_RISK_ACKNOWLEDGEMENT_REQUIRED")
        if parity_proof_ref:
            reasons.append("DEVICE_AUTH_GAP_MUST_NOT_CLAIM_PARITY_PROOF")
        if not reasons:
            reconciliation_state = "ACCEPTED_CAPABILITY_GAP_RECORDED"

    elif not reasons and decision == DECISION_REQUIRE_PARITY:
        if not accepted_by:
            reasons.append("DEVICE_AUTH_PARITY_DECISION_ACCEPTOR_REQUIRED")
        if not rationale:
            reasons.append("DEVICE_AUTH_PARITY_DECISION_RATIONALE_REQUIRED")
        if risk_acknowledged:
            reasons.append("DEVICE_AUTH_PARITY_DECISION_MUST_NOT_ACCEPT_GAP_RISK")
        if parity_proof_ready and not parity_proof_ref:
            reasons.append("DEVICE_AUTH_PARITY_PROOF_REF_REQUIRED")
        if not reasons:
            reconciliation_state = (
                "IMPLEMENTED_PARITY_PROOF_WIRED"
                if parity_proof_ready and parity_proof_ref
                else "DEVICE_AUTH_PARITY_REQUIRED_IMPLEMENTATION_OPEN"
            )

    valid_record = not reasons
    if not valid_record:
        reconciliation_state = "DEVICE_AUTH_DECISION_RECORD_INVALID"

    return {
        "valid_record": valid_record,
        "decision": decision,
        "reconciliation_state": reconciliation_state,
        "resolved_for_baseline": reconciliation_state
        in {"ACCEPTED_CAPABILITY_GAP_RECORDED", "IMPLEMENTED_PARITY_PROOF_WIRED"},
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "accepted_by_present": bool(accepted_by),
        "rationale_present": bool(rationale),
        "risk_acknowledged": risk_acknowledged,
        "parity_proof_ready": bool(parity_proof_ready),
        "parity_proof_ref_present": bool(parity_proof_ref),
        "reasons": sorted(set(reasons)),
        "source_contract_only": True,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
        "baseline_adoption_authorized": False,
    }


def current_contract() -> dict[str, Any]:
    record, authority = _load_current_decision_authority()
    result = validate_decision_record(record, parity_proof_ready=False)
    if not authority["loaded"]:
        result["valid_record"] = False
        result["reconciliation_state"] = "DEVICE_AUTH_DECISION_RECORD_INVALID"
        result["resolved_for_baseline"] = False
        result["reasons"] = sorted(
            set(result.get("reasons", []))
            | {str(authority.get("error") or "DEVICE_AUTH_DECISION_FILE_LOAD_FAILED")}
        )
    result["decision_record_authority"] = authority
    return result


def synthetic_proof() -> dict[str, Any]:
    current = current_contract()
    authority = current.get("decision_record_authority", {})
    forged_gap = validate_decision_record(
        _record_with(decision=DECISION_ACCEPT_GAP),
        parity_proof_ready=False,
    )
    future_gap = validate_decision_record(
        _record_with(
            decision=DECISION_ACCEPT_GAP,
            accepted_by="future-human-operator",
            rationale="Explicitly accept device-code OAuth as a documented Codex-only capability gap.",
            risk_acknowledged=True,
        ),
        parity_proof_ready=False,
    )
    future_parity_pending = validate_decision_record(
        _record_with(
            decision=DECISION_REQUIRE_PARITY,
            accepted_by="future-human-operator",
            rationale="Require device-code OAuth parity before adopting the v1.3.29 baseline.",
        ),
        parity_proof_ready=False,
    )
    forged_parity_ready_without_ref = validate_decision_record(
        _record_with(
            decision=DECISION_REQUIRE_PARITY,
            accepted_by="future-human-operator",
            rationale="Require device-code OAuth parity before adopting the v1.3.29 baseline.",
        ),
        parity_proof_ready=True,
    )
    future_parity_ready = validate_decision_record(
        _record_with(
            decision=DECISION_REQUIRE_PARITY,
            accepted_by="future-human-operator",
            rationale="Require device-code OAuth parity before adopting the v1.3.29 baseline.",
            parity_proof_ref="future-device-auth-parity-proof-sha256",
        ),
        parity_proof_ready=True,
    )
    wrong_target = validate_decision_record(
        _record_with(target_commit="0" * 40),
        parity_proof_ready=False,
    )

    checks = {
        "current_device_auth_decision_authority_file_loaded": (
            authority.get("loaded") is True
            and authority.get("file") == DECISION_RECORD_NAME
            and len(str(authority.get("sha256") or "")) == 64
            and not authority.get("error")
        ),
        "current_device_auth_decision_record_valid": current["valid_record"],
        "current_device_auth_decision_remains_open": current["decision"] == DECISION_OPEN,
        "current_device_auth_state_is_unresolved": (
            current["reconciliation_state"] == "SOURCE_CHARACTERIZED_PROOF_WIRED_DECISION_OPEN"
            and current["resolved_for_baseline"] is False
        ),
        "current_contract_cannot_authorize_baseline": current["baseline_adoption_authorized"] is False,
        "gap_acceptance_requires_explicit_human_authority": (
            forged_gap["valid_record"] is False
            and "DEVICE_AUTH_GAP_ACCEPTOR_REQUIRED" in forged_gap["reasons"]
            and "DEVICE_AUTH_GAP_RATIONALE_REQUIRED" in forged_gap["reasons"]
            and "DEVICE_AUTH_GAP_RISK_ACKNOWLEDGEMENT_REQUIRED" in forged_gap["reasons"]
        ),
        "future_explicit_gap_record_can_resolve_only_device_auth": (
            future_gap["valid_record"] is True
            and future_gap["reconciliation_state"] == "ACCEPTED_CAPABILITY_GAP_RECORDED"
            and future_gap["resolved_for_baseline"] is True
            and future_gap["baseline_adoption_authorized"] is False
        ),
        "require_parity_decision_stays_open_without_implementation_proof": (
            future_parity_pending["valid_record"] is True
            and future_parity_pending["reconciliation_state"]
            == "DEVICE_AUTH_PARITY_REQUIRED_IMPLEMENTATION_OPEN"
            and future_parity_pending["resolved_for_baseline"] is False
        ),
        "forged_parity_ready_without_proof_ref_fails_closed": (
            forged_parity_ready_without_ref["valid_record"] is False
            and "DEVICE_AUTH_PARITY_PROOF_REF_REQUIRED"
            in forged_parity_ready_without_ref["reasons"]
        ),
        "future_parity_requires_explicit_proof_ref": (
            future_parity_ready["valid_record"] is True
            and future_parity_ready["reconciliation_state"] == "IMPLEMENTED_PARITY_PROOF_WIRED"
            and future_parity_ready["resolved_for_baseline"] is True
            and future_parity_ready["baseline_adoption_authorized"] is False
        ),
        "decision_record_is_bound_to_exact_v1329_target_commit": (
            wrong_target["valid_record"] is False
            and "DEVICE_AUTH_DECISION_TARGET_COMMIT_INVALID" in wrong_target["reasons"]
        ),
    }
    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_V1_3_29_DEVICE_AUTH_ADOPTION_CONTRACT",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "current_contract": current,
        "device_auth_adoption_decision": current["decision"],
        "device_auth_reconciliation_state": current["reconciliation_state"],
        "decision_record_authority": authority,
        "source_contract_only": True,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
        "baseline_adoption_authorized": False,
    }


def main() -> int:
    result = synthetic_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
