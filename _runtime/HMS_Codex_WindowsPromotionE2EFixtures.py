#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, verify_packet
from HMS_Codex_WindowsPromotionDecisionLedger import (
    VERSION,
    build_decision,
    evaluate,
    reviewer_ref,
)
from HMS_Codex_WindowsPromotionReviewWorkbench import build_state

EV = "e" * 64
MAN = "b" * 64
PKG = "a" * 64


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _packet(now: datetime) -> dict:
    return {
        "source_classification": "REAL_EXTERNAL_WINDOWS_CODEX",
        "synthetic": False,
        "local_only": False,
        "target_os": "Windows",
        "codex_target": True,
        "package_zip_sha256": PKG,
        "release_manifest_sha256": MAN,
        "cockpit_baseline": COCKPIT_BASELINE,
        "capture_utc": now.isoformat(),
        "nonce": "nonce-e2e-0001",
        "run_id": "run-e2e-000001",
        "report_id": "report-e2e-0001",
        "signer": {
            "status": "VALID",
            "signer_ref": "signer-e2e-0001",
            "signature_sha256": "c" * 64,
        },
        "trust_snapshot": {
            "trusted": True,
            "status": "CURRENT",
            "signer_ref": "signer-e2e-0001",
            "snapshot_sha256": "d" * 64,
        },
        "case_results": [
            {"case_id": f"case-{i}", "status": "PASS", "report_sha256": _sha(f"case-{i}")}
            for i in range(7)
        ],
    }


def _verify(packet: dict, now: datetime, *, seen=None):
    return verify_packet(
        packet,
        raw_packet_sha256=EV,
        expected_package_sha256=PKG,
        expected_manifest_sha256=MAN,
        current_cockpit_baseline=COCKPIT_BASELINE,
        seen=seen or {},
        now=now,
    )


def _approval_set(*, one_reviewer=False):
    records = []
    a = reviewer_ref("fixture-reviewer-a", "fixture-salt-00000001")
    b = reviewer_ref("fixture-reviewer-b", "fixture-salt-00000001")
    reviewers = (a,) if one_reviewer else (a, b)
    for lane in ("TERMINAL_PTY", "PROJECT_RESUME"):
        for ref in reviewers:
            records.append(
                build_decision(
                    records,
                    decision="APPROVE",
                    reviewer_ref=ref,
                    evidence_sha256=EV,
                    manifest_sha256=MAN,
                    package_version=VERSION,
                    cockpit_baseline=COCKPIT_BASELINE,
                    lane=lane,
                )
            )
    return records, a, b


def synthetic_e2e_fixtures():
    now = datetime.now(timezone.utc)
    good = _verify(_packet(now), now)

    synthetic_packet = _packet(now)
    synthetic_packet["synthetic"] = True
    quarantine = _verify(synthetic_packet, now)

    signer_packet = _packet(now)
    signer_packet["signer"] = dict(signer_packet["signer"], status="INVALID")
    signer_fail = _verify(signer_packet, now)

    trust_packet = _packet(now)
    trust_packet["trust_snapshot"] = dict(trust_packet["trust_snapshot"], trusted=False, status="STALE")
    trust_fail = _verify(trust_packet, now)

    stale_packet = _packet(now)
    stale_packet["capture_utc"] = (now - timedelta(hours=73)).isoformat()
    stale = _verify(stale_packet, now)

    replay = _verify(_packet(now), now, seen={"packet_digests": [EV]})

    baseline_packet = _packet(now)
    baseline_packet["cockpit_baseline"] = "1.3.29"
    baseline_drift = _verify(baseline_packet, now)

    one_records, _, _ = _approval_set(one_reviewer=True)
    single_review = evaluate(
        one_records,
        evidence_sha256=EV,
        manifest_sha256=MAN,
        package_version=VERSION,
    )

    approved_records, a, b = _approval_set()
    positive_review = evaluate(
        approved_records,
        evidence_sha256=EV,
        manifest_sha256=MAN,
        package_version=VERSION,
    )

    rejected_records = list(approved_records)
    rejected_records.append(
        build_decision(
            rejected_records,
            decision="REJECT",
            reviewer_ref=a,
            evidence_sha256=EV,
            manifest_sha256=MAN,
            package_version=VERSION,
            cockpit_baseline=COCKPIT_BASELINE,
            lane="TERMINAL_PTY",
            reason_codes=["FIXTURE_REJECT"],
        )
    )
    rejected = evaluate(rejected_records, evidence_sha256=EV, manifest_sha256=MAN, package_version=VERSION)

    invalidated_records = list(approved_records)
    invalidated_records.append(
        build_decision(
            invalidated_records,
            decision="INVALIDATE",
            reviewer_ref=b,
            evidence_sha256=EV,
            manifest_sha256=MAN,
            package_version=VERSION,
            cockpit_baseline="1.3.29",
            lane="PROJECT_RESUME",
            reason_codes=["BASELINE_DRIFT_LIVE_RECHECK"],
        )
    )
    invalidated = evaluate(invalidated_records, evidence_sha256=EV, manifest_sha256=MAN, package_version=VERSION)

    optional_gpu = evaluate(
        approved_records,
        evidence_sha256=EV,
        manifest_sha256=MAN,
        package_version=VERSION,
        optional_gpu_required=True,
    )

    workbench_drift = build_state(
        ingest_report=good,
        ledger_records=approved_records,
        package_version=VERSION,
        manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE,
        baseline_before_final_review="1.3.29",
        optional_gpu_required=False,
    )

    checks = {
        "positive_real_packet_verifies": good["real_packet_verified"] is True,
        "quarantine_synthetic_rejected": "SYNTHETIC_EVIDENCE_REJECTED" in quarantine["reasons"],
        "signer_failure_rejected": "SIGNER_VALIDATION_REQUIRED" in signer_fail["reasons"],
        "trust_failure_rejected": "TRUST_SNAPSHOT_NOT_CURRENT" in trust_fail["reasons"],
        "stale_evidence_rejected": "EVIDENCE_STALE" in stale["reasons"],
        "replay_rejected": "DUPLICATE_PACKET_DIGEST" in replay["reasons"],
        "baseline_drift_packet_rejected": "COCKPIT_BASELINE_CHANGED_OR_STALE" in baseline_drift["reasons"],
        "single_reviewer_never_promotes": not single_review["promotion_eligible"] and any(
            reason.startswith("DUAL_REVIEW_INCOMPLETE:") for reason in single_review["reasons"]
        ),
        "two_reviewer_two_lane_positive_control": positive_review["promotion_eligible"] is True,
        "reject_freezes_promotion": not rejected["promotion_eligible"] and "CURRENT_EPOCH_REJECTED" in rejected["reasons"],
        "invalidate_freezes_promotion": not invalidated["promotion_eligible"] and "CURRENT_EPOCH_INVALIDATED" in invalidated["reasons"],
        "optional_gpu_required_blocks_without_gpu_reviews": not optional_gpu["promotion_eligible"] and "DUAL_REVIEW_INCOMPLETE:OPTIONAL_GPU" in optional_gpu["reasons"],
        "workbench_live_baseline_drift_freezes": workbench_drift["status"] == "FROZEN_BASELINE_DRIFT" and not workbench_drift["production_score_promotion_eligible"],
        "no_fixture_grants_automatic_authority": all(
            value is False
            for value in (
                good["automatic_production_certification"],
                positive_review["automatic_production_certification"],
                positive_review["production_score_mutation_authorized"],
                workbench_drift["automatic_production_certification"],
                workbench_drift["production_score_mutation_authorized"],
            )
        ),
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
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


if __name__ == "__main__":
    result = synthetic_e2e_fixtures()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 2)
