#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import HMS_Codex_CockpitV1329DeviceAuthAdoptionContract as device_auth_adoption
import HMS_Codex_CockpitV1329DeviceAuthDeltaProof as device_auth_delta
import HMS_Codex_CockpitV1329LaunchConfirmationProof as launch_confirmation
import HMS_Codex_CockpitV1329SessionProviderMigrationProof as session_provider_migration

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"

FROZEN_BASELINE = "1.3.28"
FROZEN_RELEASE_COMMIT = "82576b9634bad0a365abc51eba8f022fb0a50d97"
RECONCILIATION_TARGET = "1.3.29"
RECONCILIATION_TARGET_COMMIT = "83ce2d192cc954cc910ce89edf2d1f710c218798"

# New-baseline adoption is deliberately separate from source characterization.
# It must stay false while any adoption-blocking decision remains OPEN.
TARGET_BASELINE_ADOPTION_AUTHORIZED = False


def _current_device_auth_state(
    source_result: dict[str, Any] | None = None,
) -> str:
    observed = device_auth_delta.source_proof() if source_result is None else source_result
    if not (
        observed.get("verdict") == "PASS"
        and observed.get("target_commit") == RECONCILIATION_TARGET_COMMIT
        and observed.get("source_characterization_only") is True
        and observed.get("device_auth_adoption_decision") == "OPEN"
        and observed.get("windows_runtime_certified") is False
        and observed.get("production_score_promotion_eligible") is False
        and observed.get("baseline_adoption_authorized") is False
    ):
        return "DEVICE_AUTH_SOURCE_PROOF_FAILED"

    contract = device_auth_adoption.current_contract()
    if not contract.get("valid_record"):
        return "DEVICE_AUTH_DECISION_RECORD_INVALID"
    return str(
        contract.get("reconciliation_state")
        or "DEVICE_AUTH_DECISION_RECORD_INVALID"
    )


def _source_proof_state(
    result: dict[str, Any],
    *,
    failure_state: str,
) -> str:
    if (
        result.get("verdict") == "PASS"
        and result.get("target_release") == RECONCILIATION_TARGET
        and result.get("target_commit") == RECONCILIATION_TARGET_COMMIT
        and result.get("source_reconciliation_state")
        == "SOURCE_RECONCILED_PROOF_WIRED"
        and result.get("windows_runtime_certified") is False
        and result.get("production_score_promotion_eligible") is False
        and result.get("baseline_adoption_authorized") is False
    ):
        return "SOURCE_RECONCILED_PROOF_WIRED"
    return failure_state


def current_reconciliation_states(
    device_result: dict[str, Any] | None = None,
    launch_result: dict[str, Any] | None = None,
    session_result: dict[str, Any] | None = None,
) -> dict[str, str]:
    observed_device = (
        device_auth_delta.source_proof()
        if device_result is None
        else device_result
    )
    observed_launch = (
        launch_confirmation.source_proof()
        if launch_result is None
        else launch_result
    )
    observed_session = (
        session_provider_migration.source_proof()
        if session_result is None
        else session_result
    )
    return {
        "quota_refresh_token_ownership": "SOURCE_CLOSED_PROOF_WIRED",
        "combined_oauth_api_key_credential_ownership": "SOURCE_CLOSED_PROOF_WIRED",
        "device_auth": _current_device_auth_state(observed_device),
        "launch_confirmation_before_mutation": _source_proof_state(
            observed_launch,
            failure_state="LAUNCH_CONFIRMATION_SOURCE_PROOF_FAILED",
        ),
        "session_provider_migration_safety": _source_proof_state(
            observed_session,
            failure_state="SESSION_PROVIDER_MIGRATION_SOURCE_PROOF_FAILED",
        ),
        "api_service_realtime_breadth": "DEFERRED_P2_NOT_BASELINE_BLOCKING",
    }


ADOPTION_BLOCKING_KEYS = (
    "quota_refresh_token_ownership",
    "combined_oauth_api_key_credential_ownership",
    "device_auth",
    "launch_confirmation_before_mutation",
    "session_provider_migration_safety",
)

RESOLVED_STATES = {
    "SOURCE_CLOSED_PROOF_WIRED",
    "IMPLEMENTED_PARITY_PROOF_WIRED",
    "ACCEPTED_CAPABILITY_GAP_RECORDED",
    "SOURCE_RECONCILED_PROOF_WIRED",
}

EXPECTED_LITERAL_AUTHORITIES = {
    "HMS_Codex_ExternalWindowsReviewPacketIngest.py",
    "HMS_Codex_PromotionReviewerActionPolicy.py",
    "HMS_Codex_WindowsPromotionDecisionLedger.py",
}


class BaselineReconciliationError(RuntimeError):
    pass


def target_adoption_blockers(states: dict[str, str] | None = None) -> list[str]:
    values = current_reconciliation_states() if states is None else states
    blockers = []
    for key in ADOPTION_BLOCKING_KEYS:
        state = str(values.get(key) or "MISSING")
        if state not in RESOLVED_STATES:
            blockers.append(f"{key}:{state}")
    return blockers


def validate_baseline_contract(
    *,
    frozen_baseline: str = FROZEN_BASELINE,
    target_adoption_authorized: bool = TARGET_BASELINE_ADOPTION_AUTHORIZED,
    states: dict[str, str] | None = None,
) -> dict[str, Any]:
    values = current_reconciliation_states() if states is None else states
    baseline = str(frozen_baseline or "").strip()
    blockers = target_adoption_blockers(values)
    reasons: list[str] = []

    if baseline == FROZEN_BASELINE:
        pass
    elif baseline == RECONCILIATION_TARGET:
        if not target_adoption_authorized:
            reasons.append("TARGET_BASELINE_ADOPTION_NOT_AUTHORIZED")
        if blockers:
            reasons.append("TARGET_BASELINE_RECONCILIATION_INCOMPLETE")
    else:
        reasons.append("UNRECOGNIZED_FROZEN_BASELINE")

    if target_adoption_authorized and blockers:
        reasons.append("ADOPTION_AUTHORITY_WITH_OPEN_BLOCKERS")

    return {
        "valid": not reasons,
        "frozen_baseline": baseline,
        "frozen_release_commit": FROZEN_RELEASE_COMMIT,
        "reconciliation_target": RECONCILIATION_TARGET,
        "reconciliation_target_commit": RECONCILIATION_TARGET_COMMIT,
        "target_baseline_adoption_authorized": bool(target_adoption_authorized),
        "reconciliation_states": values,
        "adoption_blockers": blockers,
        "reasons": sorted(set(reasons)),
    }


def _literal_baseline_assignments(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise BaselineReconciliationError(
            f"baseline authority source unreadable: {path.name}: {exc}"
        ) from exc

    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "COCKPIT_BASELINE"
            for target in targets
        ):
            continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            raise BaselineReconciliationError(
                f"COCKPIT_BASELINE must be a literal string in {path.name}"
            )
        values.append(value.value)
    return values


def audit_runtime_baseline_authorities(
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    root = runtime_dir or Path(__file__).resolve().parent
    definitions: dict[str, list[str]] = {}
    for path in sorted(root.glob("HMS_Codex_*.py")):
        values = _literal_baseline_assignments(path)
        if values:
            definitions[path.name] = values

    names = set(definitions)
    missing = sorted(EXPECTED_LITERAL_AUTHORITIES - names)
    unexpected = sorted(names - EXPECTED_LITERAL_AUTHORITIES)
    wrong = sorted(
        f"{name}:{value}"
        for name, values in definitions.items()
        for value in values
        if value != FROZEN_BASELINE
    )
    duplicate = sorted(name for name, values in definitions.items() if len(values) != 1)

    reasons = []
    if missing:
        reasons.append("EXPECTED_BASELINE_AUTHORITY_MISSING")
    if unexpected:
        reasons.append("UNEXPECTED_BASELINE_LITERAL_AUTHORITY")
    if wrong:
        reasons.append("FROZEN_BASELINE_LITERAL_MISMATCH")
    if duplicate:
        reasons.append("DUPLICATE_BASELINE_LITERAL_AUTHORITY")

    return {
        "valid": not reasons,
        "frozen_baseline": FROZEN_BASELINE,
        "definitions": definitions,
        "missing": missing,
        "unexpected": unexpected,
        "wrong": wrong,
        "duplicate": duplicate,
        "reasons": reasons,
    }


def synthetic_proof() -> dict[str, Any]:
    device_result = device_auth_delta.source_proof()
    launch_result = launch_confirmation.source_proof()
    session_result = session_provider_migration.source_proof()
    states = current_reconciliation_states(device_result, launch_result, session_result)
    device_contract = device_auth_adoption.current_contract()
    contract = validate_baseline_contract(states=states)
    source_audit = audit_runtime_baseline_authorities()
    bare_target_flip = validate_baseline_contract(
        frozen_baseline=RECONCILIATION_TARGET,
        target_adoption_authorized=False,
        states=states,
    )
    forged_authority = validate_baseline_contract(
        frozen_baseline=RECONCILIATION_TARGET,
        target_adoption_authorized=True,
        states=states,
    )

    future_gap_record = {
        **device_auth_adoption.DECISION_RECORD_TEMPLATE,
        "decision": device_auth_adoption.DECISION_ACCEPT_GAP,
        "accepted_by": "future-human-operator",
        "rationale": "Explicit future capability-gap decision for contract proof only.",
        "risk_acknowledged": True,
    }
    future_gap_contract = device_auth_adoption.validate_decision_record(future_gap_record)
    fully_resolved_states = {
        **states,
        "device_auth": str(
            future_gap_contract.get("reconciliation_state") or "INVALID"
        ),
    }
    explicit_future_adoption = validate_baseline_contract(
        frozen_baseline=RECONCILIATION_TARGET,
        target_adoption_authorized=True,
        states=fully_resolved_states,
    )

    checks = {
        "current_frozen_epoch_contract_valid": contract["valid"],
        "current_frozen_baseline_is_v1328": contract["frozen_baseline"] == "1.3.28",
        "v1329_target_commit_pinned": contract["reconciliation_target_commit"] == RECONCILIATION_TARGET_COMMIT,
        "v1329_adoption_currently_not_authorized": contract["target_baseline_adoption_authorized"] is False,
        "device_auth_exact_source_proof_passes": device_result.get("verdict") == "PASS",
        "device_auth_source_characterization_is_bound_to_v1329_target": (
            device_result.get("target_commit") == RECONCILIATION_TARGET_COMMIT
            and device_result.get("source_characterization_only") is True
            and device_result.get("device_auth_adoption_decision") == "OPEN"
        ),
        "device_auth_decision_authority_record_valid": device_contract.get("valid_record") is True,
        "device_auth_decision_authority_remains_open": device_contract.get("decision") == "OPEN",
        "device_auth_reconciliation_state_requires_source_proof_and_decision_authority": (
            states["device_auth"]
            == device_contract.get("reconciliation_state")
            == "SOURCE_CHARACTERIZED_PROOF_WIRED_DECISION_OPEN"
        ),
        "device_auth_open_decision_is_only_current_adoption_blocker": (
            contract["adoption_blockers"]
            == ["device_auth:SOURCE_CHARACTERIZED_PROOF_WIRED_DECISION_OPEN"]
        ),
        "device_auth_contract_cannot_authorize_baseline": device_contract.get("baseline_adoption_authorized") is False,
        "launch_confirmation_exact_source_proof_passes": launch_result.get("verdict") == "PASS",
        "launch_confirmation_state_is_derived_from_proof": states["launch_confirmation_before_mutation"] == "SOURCE_RECONCILED_PROOF_WIRED",
        "session_provider_migration_exact_source_proof_passes": session_result.get("verdict") == "PASS",
        "session_provider_migration_proof_is_bound_to_v1329_target": session_result.get("target_commit") == RECONCILIATION_TARGET_COMMIT,
        "session_provider_migration_state_is_derived_from_proof": states["session_provider_migration_safety"] == "SOURCE_RECONCILED_PROOF_WIRED",
        "session_provider_migration_has_five_required_invariants": session_result.get("safety_invariants") == [
            "ROLLBACK_ON_FAILED_MUTATION",
            "SELECTED_SCOPE_ONLY",
            "DEEP_MIGRATION_REQUIRES_STOPPED_TARGET",
            "PROVIDER_BOUND_FILTERING",
            "QUICK_REPAIR_OFFICIAL_SIDEBAR_ONLY",
        ],
        "source_proofs_cannot_authorize_windows_or_promotion": (
            device_result.get("windows_runtime_certified") is False
            and device_result.get("production_score_promotion_eligible") is False
            and device_result.get("baseline_adoption_authorized") is False
            and launch_result.get("windows_runtime_certified") is False
            and launch_result.get("production_score_promotion_eligible") is False
            and launch_result.get("baseline_adoption_authorized") is False
            and session_result.get("windows_runtime_certified") is False
            and session_result.get("production_score_promotion_eligible") is False
            and session_result.get("baseline_adoption_authorized") is False
        ),
        "runtime_baseline_literal_authorities_exact": source_audit["valid"],
        "bare_baseline_flip_to_v1329_fails_closed": (
            bare_target_flip["valid"] is False
            and "TARGET_BASELINE_ADOPTION_NOT_AUTHORIZED" in bare_target_flip["reasons"]
            and "TARGET_BASELINE_RECONCILIATION_INCOMPLETE" in bare_target_flip["reasons"]
        ),
        "forged_adoption_authority_with_open_device_decision_fails_closed": (
            forged_authority["valid"] is False
            and "ADOPTION_AUTHORITY_WITH_OPEN_BLOCKERS" in forged_authority["reasons"]
        ),
        "future_device_gap_requires_valid_explicit_decision_record": (
            future_gap_contract.get("valid_record") is True
            and future_gap_contract.get("reconciliation_state") == "ACCEPTED_CAPABILITY_GAP_RECORDED"
            and future_gap_contract.get("baseline_adoption_authorized") is False
        ),
        "future_adoption_requires_explicit_device_resolution_and_separate_authority": explicit_future_adoption["valid"],
    }
    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_BASELINE_RECONCILIATION_CONTRACT",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "contract": contract,
        "device_auth_source_proof": device_result,
        "device_auth_decision_contract": device_contract,
        "launch_confirmation_source_proof": launch_result,
        "session_provider_migration_source_proof": session_result,
        "runtime_baseline_authority_audit": source_audit,
        "source_contract_only": True,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
        "baseline_adoption_authorized": False,
    }


def main() -> int:
    try:
        result = synthetic_proof()
    except Exception as exc:
        result = {
            "product": PRODUCT,
            "version": VERSION,
            "suite": "COCKPIT_BASELINE_RECONCILIATION_CONTRACT",
            "verdict": "FAIL",
            "error": str(exc),
            "source_contract_only": True,
            "real_windows_runtime_executed": False,
            "windows_runtime_certified": False,
            "external_windows_target_evidence_imported": False,
            "production_score_promotion_eligible": False,
            "production_score_mutation_authorized": False,
            "baseline_adoption_authorized": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verdict") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
