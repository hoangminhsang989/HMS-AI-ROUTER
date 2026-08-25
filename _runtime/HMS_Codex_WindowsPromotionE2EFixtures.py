#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from HMS_Codex_ExternalWindowsReviewPacketIngest import ARTIFACT_BINDING_SCHEMA, COCKPIT_BASELINE, verify_packet
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsPromotionDecisionLedger import VERSION, build_decision, evaluate, reviewer_ref
from HMS_Codex_WindowsPromotionReviewWorkbench import build_state
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS

EV = "e" * 64
MAN = "b" * 64
PKG = "a" * 64
SRC = "c" * 64
TRUST_AUTH = "9" * 64
RELEASE_AUTH = "8" * 64


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _packet(now: datetime) -> dict:
    base = {
        "source_classification": "REAL_EXTERNAL_WINDOWS_CODEX",
        "synthetic": False,
        "local_only": False,
        "target_os": "Windows",
        "codex_target": True,
        "package_zip_sha256": PKG,
        "release_manifest_sha256": MAN,
        "source_certification_report_sha256": SRC,
        "source_artifact_binding": {
            "binding_schema": ARTIFACT_BINDING_SCHEMA,
            "package_zip_sha256": PKG,
            "release_manifest_sha256": MAN,
        },
        "cockpit_baseline": COCKPIT_BASELINE,
        "capture_utc": now.isoformat(),
        "nonce": "nonce-e2e-0001",
        "run_id": "run-e2e-000001",
        "report_id": "report-e2e-0001",
        "case_results": [
            {
                "case_id": cid,
                "status": "PASS",
                "report_sha256": _sha(cid),
                "source_report_sha256": SRC,
                "source_package_zip_sha256": PKG,
                "source_release_manifest_sha256": MAN,
            }
            for cid in REQUIRED_RUNTIME_CASE_IDS
        ],
    }
    packet = synthetic_signed_packet(base)
    packet["signer"].pop("synthetic_fixture", None)
    return packet


def _verify(packet: dict, now: datetime, *, seen=None, expected_anchor=None):
    anchor = expected_anchor if expected_anchor is not None else str((packet.get("trust_snapshot") or {}).get("trust_snapshot_sha256") or "")
    return verify_packet(
        packet,
        raw_packet_sha256=EV,
        expected_package_sha256=PKG,
        expected_manifest_sha256=MAN,
        expected_trust_snapshot_sha256=anchor,
        current_cockpit_baseline=COCKPIT_BASELINE,
        seen=seen or {},
        now=now,
    )


def _with_reviewer_authorities(report: dict) -> dict:
    out = json.loads(json.dumps(report))
    provenance = out.get("provenance") or {}
    trust = str(provenance.get("expected_trust_snapshot_sha256") or "")
    out["reviewer_trust_authority"] = {
        "valid": True,
        "authority_sha256": TRUST_AUTH,
        "trust_snapshot_sha256": trust,
        "active_pin_count": 1,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
    }
    out["reviewer_release_authority"] = {
        "valid": True,
        "authority_sha256": RELEASE_AUTH,
        "package_zip_sha256": PKG,
        "release_manifest_sha256": MAN,
        "source_commit_sha": "1" * 40,
        "source_tree_sha": "2" * 40,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
        "local_artifact_hashed_at_capture": False,
    }
    return out


def _decision_kwargs(**overrides):
    values = {
        "evidence_sha256": EV,
        "manifest_sha256": MAN,
        "package_sha256": PKG,
        "source_certification_report_sha256": SRC,
        "reviewer_trust_authority_sha256": TRUST_AUTH,
        "reviewer_release_authority_sha256": RELEASE_AUTH,
        "package_version": VERSION,
    }
    values.update(overrides)
    return values


def _evaluate(records, **overrides):
    return evaluate(records, **_decision_kwargs(**overrides))


def _approval_set(*, one_reviewer=False):
    records = []
    reviewer_a = reviewer_ref("fixture-reviewer-a", "fixture-salt-00000001")
    reviewer_b = reviewer_ref("fixture-reviewer-b", "fixture-salt-00000001")
    reviewers = (reviewer_a,) if one_reviewer else (reviewer_a, reviewer_b)
    for lane in ("TERMINAL_PTY", "PROJECT_RESUME"):
        for ref in reviewers:
            records.append(build_decision(
                records,
                decision="APPROVE",
                reviewer_ref=ref,
                cockpit_baseline=COCKPIT_BASELINE,
                lane=lane,
                **_decision_kwargs(),
            ))
    return records, reviewer_a, reviewer_b


def synthetic_e2e_fixtures():
    now = datetime.now(timezone.utc)
    packet = _packet(now)
    approved_anchor = packet["trust_snapshot"]["trust_snapshot_sha256"]
    good = _verify(packet, now, expected_anchor=approved_anchor)
    reviewed_good = _with_reviewer_authorities(good)

    synthetic_packet = json.loads(json.dumps(packet)); synthetic_packet["synthetic"] = True
    quarantine = _verify(synthetic_packet, now, expected_anchor=approved_anchor)
    signer_packet = json.loads(json.dumps(packet)); signer_packet["signer"]["signature_b64"] = "not-base64"
    signer_fail = _verify(signer_packet, now, expected_anchor=approved_anchor)
    trust_packet = json.loads(json.dumps(packet)); trust_packet["trust_snapshot"]["generation"] += 1
    trust_fail = _verify(trust_packet, now, expected_anchor=approved_anchor)
    rogue_anchor_packet = _packet(now)
    rogue_anchor = _verify(rogue_anchor_packet, now, expected_anchor=approved_anchor)
    stale_packet = json.loads(json.dumps(packet)); stale_packet["capture_utc"] = (now - timedelta(hours=73)).isoformat()
    stale = _verify(stale_packet, now, expected_anchor=approved_anchor)
    replay = _verify(packet, now, seen={"packet_digests": [EV]}, expected_anchor=approved_anchor)
    baseline_packet = json.loads(json.dumps(packet)); baseline_packet["cockpit_baseline"] = "1.3.29"
    baseline_drift = _verify(baseline_packet, now, expected_anchor=approved_anchor)
    missing_binding = json.loads(json.dumps(packet)); missing_binding.pop("source_artifact_binding", None)
    binding_fail = _verify(missing_binding, now, expected_anchor=approved_anchor)
    case_splice = json.loads(json.dumps(packet)); case_splice["case_results"][0]["source_package_zip_sha256"] = "f" * 64
    case_splice_fail = _verify(case_splice, now, expected_anchor=approved_anchor)

    one_records, _, _ = _approval_set(one_reviewer=True)
    single_review = _evaluate(one_records)
    approved_records, reviewer_a, reviewer_b = _approval_set()
    positive_review = _evaluate(approved_records)
    source_reuse = _evaluate(approved_records, source_certification_report_sha256="7" * 64)
    release_reuse = _evaluate(approved_records, reviewer_release_authority_sha256="6" * 64)
    package_reuse = _evaluate(approved_records, package_sha256="5" * 64)

    rejected_records = list(approved_records)
    rejected_records.append(build_decision(
        rejected_records,
        decision="REJECT",
        reviewer_ref=reviewer_a,
        cockpit_baseline=COCKPIT_BASELINE,
        lane="TERMINAL_PTY",
        reason_codes=["FIXTURE_REJECT"],
        **_decision_kwargs(),
    ))
    rejected = _evaluate(rejected_records)

    invalidated_records = list(approved_records)
    invalidated_records.append(build_decision(
        invalidated_records,
        decision="INVALIDATE",
        reviewer_ref=reviewer_b,
        cockpit_baseline="1.3.29",
        lane="PROJECT_RESUME",
        reason_codes=["BASELINE_DRIFT_LIVE_RECHECK"],
        **_decision_kwargs(),
    ))
    invalidated = _evaluate(invalidated_records)
    optional_gpu = _evaluate(approved_records, optional_gpu_required=True)

    workbench_match = build_state(
        ingest_report=reviewed_good,
        ledger_records=approved_records,
        package_version=VERSION,
        manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE,
        baseline_before_final_review=COCKPIT_BASELINE,
        optional_gpu_required=False,
    )
    workbench_drift = build_state(
        ingest_report=reviewed_good,
        ledger_records=approved_records,
        package_version=VERSION,
        manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE,
        baseline_before_final_review="1.3.29",
        optional_gpu_required=False,
    )
    no_trust = json.loads(json.dumps(reviewed_good)); no_trust["reviewer_trust_authority"] = {}
    no_trust_state = build_state(ingest_report=no_trust, ledger_records=approved_records, package_version=VERSION, manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE, optional_gpu_required=False)
    no_release = json.loads(json.dumps(reviewed_good)); no_release["reviewer_release_authority"] = {}
    no_release_state = build_state(ingest_report=no_release, ledger_records=approved_records, package_version=VERSION, manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE, optional_gpu_required=False)
    wrong_release = json.loads(json.dumps(reviewed_good)); wrong_release["reviewer_release_authority"]["release_manifest_sha256"] = "f" * 64
    wrong_release_state = build_state(ingest_report=wrong_release, ledger_records=approved_records, package_version=VERSION, manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE, optional_gpu_required=False)
    wrong_source = json.loads(json.dumps(reviewed_good)); wrong_source["provenance"]["source_certification_report_sha256"] = "7" * 64
    wrong_source_state = build_state(ingest_report=wrong_source, ledger_records=approved_records, package_version=VERSION, manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE, optional_gpu_required=False)

    checks = {
        "positive_crypto_packet_verifies": good["real_packet_verified"] is True and good["trust_anchor_match"] is True,
        "canonical_exact_seven_cases": good["case_matrix"]["valid"] is True,
        "artifact_binding_present_in_provenance": good["provenance"]["source_artifact_binding_schema"] == ARTIFACT_BINDING_SCHEMA,
        "quarantine_synthetic_rejected": "SYNTHETIC_EVIDENCE_REJECTED" in quarantine["reasons"],
        "signature_failure_rejected": "CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED" in signer_fail["reasons"],
        "trust_snapshot_tamper_rejected": "TRUST_SNAPSHOT_DIGEST_MISMATCH" in trust_fail["reasons"],
        "rogue_self_anchor_rejected": "TRUST_ANCHOR_MISMATCH" in rogue_anchor["reasons"],
        "stale_evidence_rejected": "EVIDENCE_STALE" in stale["reasons"],
        "replay_rejected": "DUPLICATE_PACKET_DIGEST" in replay["reasons"],
        "baseline_drift_packet_rejected": "COCKPIT_BASELINE_CHANGED_OR_STALE" in baseline_drift["reasons"],
        "missing_artifact_binding_rejected": "SOURCE_ARTIFACT_BINDING_SCHEMA_REQUIRED" in binding_fail["reasons"],
        "case_artifact_splice_rejected": "RUNTIME_CASE_SOURCE_PACKAGE_MISMATCH" in case_splice_fail["reasons"],
        "single_reviewer_never_promotes": not single_review["promotion_eligible"] and any(reason.startswith("DUAL_REVIEW_INCOMPLETE:") for reason in single_review["reasons"]),
        "two_reviewer_two_lane_positive_control": positive_review["promotion_eligible"] is True,
        "source_certification_reuse_blocked": not source_reuse["promotion_eligible"],
        "release_authority_reuse_blocked": not release_reuse["promotion_eligible"],
        "package_digest_reuse_blocked": not package_reuse["promotion_eligible"],
        "reject_freezes_promotion": not rejected["promotion_eligible"] and "CURRENT_EPOCH_REJECTED" in rejected["reasons"],
        "invalidate_freezes_promotion": not invalidated["promotion_eligible"] and "CURRENT_EPOCH_INVALIDATED" in invalidated["reasons"],
        "optional_gpu_required_blocks_without_gpu_reviews": not optional_gpu["promotion_eligible"] and "DUAL_REVIEW_INCOMPLETE:OPTIONAL_GPU" in optional_gpu["reasons"],
        "sealed_authorities_positive_workbench_control": workbench_match["production_score_promotion_eligible"] is True and workbench_match["gates"]["reviewer_trust_authority"] is True and workbench_match["gates"]["reviewer_release_authority"] is True,
        "decision_provenance_positive_workbench_control": workbench_match["gates"]["decision_provenance"] is True and workbench_match["decision_provenance"]["source_certification_report_sha256"] == SRC,
        "missing_reviewer_trust_authority_blocks_workbench": not no_trust_state["production_score_promotion_eligible"] and no_trust_state["gates"]["reviewer_trust_authority"] is False,
        "missing_reviewer_release_authority_blocks_workbench": not no_release_state["production_score_promotion_eligible"] and no_release_state["gates"]["reviewer_release_authority"] is False,
        "release_authority_artifact_mismatch_blocks_workbench": not wrong_release_state["production_score_promotion_eligible"] and wrong_release_state["gates"]["reviewer_release_authority"] is False,
        "source_certification_mismatch_blocks_existing_approvals": not wrong_source_state["production_score_promotion_eligible"],
        "workbench_live_baseline_drift_freezes": workbench_drift["status"] == "FROZEN_BASELINE_DRIFT" and not workbench_drift["production_score_promotion_eligible"],
        "workbench_signature_trust_gates": workbench_match["gates"]["signature"] and workbench_match["gates"]["trust"],
        "no_fixture_grants_automatic_authority": all(value is False for value in (
            good["automatic_production_certification"],
            positive_review["automatic_production_certification"],
            positive_review["production_score_mutation_authorized"],
            workbench_drift["automatic_production_certification"],
            workbench_drift["production_score_mutation_authorized"],
        )),
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_PROMOTION_E2E_NEGATIVE_PATH_FIXTURES",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "synthetic_fixture_only": True,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


if __name__ == "__main__":
    result = synthetic_e2e_fixtures()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 2)
