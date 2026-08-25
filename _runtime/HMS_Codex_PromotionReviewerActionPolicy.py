#!/usr/bin/env python3
from __future__ import annotations

import json
import re

VERSION = "25.75"
COCKPIT_BASELINE = "1.3.28"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GIT_HEX = re.compile(r"^[0-9a-f]{40,64}$")
TRUSTED_SOURCE = "GITHUB_RELEASES_LATEST"


def evaluate_action_policy(report, live_observation, *, busy=False):
    report = report if isinstance(report, dict) else {}
    live = live_observation if isinstance(live_observation, dict) else {}
    reasons = {str(x) for x in (report.get("reasons") or [])}
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    signer_trust = report.get("signer_trust") if isinstance(report.get("signer_trust"), dict) else {}
    authority = report.get("reviewer_trust_authority") if isinstance(report.get("reviewer_trust_authority"), dict) else {}
    release_authority = report.get("reviewer_release_authority") if isinstance(report.get("reviewer_release_authority"), dict) else {}

    evidence_verified = report.get("real_packet_verified") is True
    evidence_digest = str(provenance.get("raw_packet_sha256") or "").lower()
    package_digest = str(provenance.get("package_zip_sha256") or "").lower()
    manifest_digest = str(provenance.get("release_manifest_sha256") or "").lower()
    source_certification_digest = str(provenance.get("source_certification_report_sha256") or "").lower()
    trust_digest = str(provenance.get("trust_snapshot_sha256") or "").lower()
    expected_trust = str(provenance.get("expected_trust_snapshot_sha256") or "").lower()
    provenance_ok = bool(
        HEX64.fullmatch(evidence_digest)
        and HEX64.fullmatch(package_digest)
        and HEX64.fullmatch(manifest_digest)
        and HEX64.fullmatch(source_certification_digest)
        and HEX64.fullmatch(trust_digest)
        and HEX64.fullmatch(expected_trust)
        and trust_digest == expected_trust
    )

    signature_ok = evidence_verified and signer_trust.get("valid") is True
    authority_digest = str(authority.get("authority_sha256") or "").lower()
    authority_ok = (
        authority.get("valid") is True
        and authority.get("local_integrity_seal_valid") is True
        and authority.get("packet_derived") is False
        and HEX64.fullmatch(authority_digest) is not None
        and str(authority.get("trust_snapshot_sha256") or "").lower() == expected_trust
    )
    trust_ok = signature_ok and report.get("trust_anchor_match") is True and authority_ok

    release_digest = str(release_authority.get("authority_sha256") or "").lower()
    release_package = str(release_authority.get("package_zip_sha256") or "").lower()
    release_manifest = str(release_authority.get("release_manifest_sha256") or "").lower()
    release_commit = str(release_authority.get("source_commit_sha") or "").lower()
    release_tree = str(release_authority.get("source_tree_sha") or "").lower()
    release_authority_ok = (
        release_authority.get("valid") is True
        and release_authority.get("local_integrity_seal_valid") is True
        and release_authority.get("packet_derived") is False
        and release_authority.get("local_artifact_hashed_at_capture") is False
        and HEX64.fullmatch(release_digest) is not None
        and GIT_HEX.fullmatch(release_commit) is not None
        and GIT_HEX.fullmatch(release_tree) is not None
        and release_package == package_digest
        and release_manifest == manifest_digest
    )
    decision_provenance_ok = provenance_ok and authority_ok and release_authority_ok

    freshness_ok = evidence_verified and not bool(reasons & {"EVIDENCE_STALE", "CAPTURE_UTC_INVALID", "CAPTURE_TIME_IN_FUTURE"})
    idempotency_ok = evidence_verified and "DUPLICATE_PACKET_DIGEST" not in reasons and not any(x.endswith("_REPLAY") for x in reasons)

    trusted_live = (
        live.get("source") == TRUSTED_SOURCE
        and str(live.get("upstream_repository") or "") == "jlcodes99/cockpit-tools"
        and isinstance(live.get("release_id"), int)
        and live.get("release_id") > 0
        and bool(str(live.get("checked_utc") or "").strip())
    )
    observed_baseline = str(live.get("baseline") or "")
    baseline_match = trusted_live and observed_baseline == COCKPIT_BASELINE

    common = (
        evidence_verified
        and decision_provenance_ok
        and signature_ok
        and trust_ok
        and freshness_ok
        and idempotency_ok
        and trusted_live
        and not busy
    )
    permissions = {"APPROVE": common and baseline_match, "REJECT": common and baseline_match, "INVALIDATE": common}
    reasons_out = []
    if not evidence_verified:
        reasons_out.append("VERIFIED_REAL_PACKET_REQUIRED")
    if not provenance_ok:
        reasons_out.append("EVIDENCE_PROVENANCE_REQUIRED")
    if not signature_ok:
        reasons_out.append("SIGNATURE_GATE_BLOCKED")
    if not authority_ok:
        reasons_out.append("SEALED_REVIEWER_TRUST_AUTHORITY_REQUIRED")
    if not trust_ok:
        reasons_out.append("TRUST_GATE_BLOCKED")
    if not release_authority_ok:
        reasons_out.append("SEALED_REVIEWER_RELEASE_AUTHORITY_REQUIRED")
    if not decision_provenance_ok:
        reasons_out.append("DECISION_PROVENANCE_BINDING_REQUIRED")
    if not freshness_ok:
        reasons_out.append("FRESHNESS_GATE_BLOCKED")
    if not idempotency_ok:
        reasons_out.append("IDEMPOTENCY_GATE_BLOCKED")
    if not trusted_live:
        reasons_out.append("TRUSTED_LIVE_BASELINE_REQUIRED")
    if trusted_live and not baseline_match:
        reasons_out.append("FROZEN_BASELINE_DRIFT")
    if busy:
        reasons_out.append("REVIEW_ACTION_BUSY")

    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "PROMOTION_REVIEWER_ACTION_POLICY",
        "permissions": permissions,
        "gates": {
            "evidence": evidence_verified and provenance_ok,
            "decision_provenance": decision_provenance_ok,
            "signature": signature_ok,
            "reviewer_trust_authority": authority_ok,
            "reviewer_release_authority": release_authority_ok,
            "trust": trust_ok,
            "freshness": freshness_ok,
            "idempotency": idempotency_ok,
            "trusted_live_baseline": trusted_live,
            "baseline_match": baseline_match,
        },
        "observed_baseline": observed_baseline,
        "reasons": sorted(set(reasons_out)),
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def synthetic_proof():
    authority = {
        "valid": True,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
        "authority_sha256": "d" * 64,
        "trust_snapshot_sha256": "c" * 64,
    }
    release_authority = {
        "valid": True,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
        "local_artifact_hashed_at_capture": False,
        "authority_sha256": "e" * 64,
        "package_zip_sha256": "f" * 64,
        "release_manifest_sha256": "b" * 64,
        "source_commit_sha": "1" * 40,
        "source_tree_sha": "2" * 40,
    }
    report = {
        "real_packet_verified": True,
        "reasons": [],
        "trust_anchor_match": True,
        "signer_trust": {"valid": True},
        "reviewer_trust_authority": authority,
        "reviewer_release_authority": release_authority,
        "provenance": {
            "raw_packet_sha256": "a" * 64,
            "package_zip_sha256": "f" * 64,
            "release_manifest_sha256": "b" * 64,
            "source_certification_report_sha256": "7" * 64,
            "trust_snapshot_sha256": "c" * 64,
            "expected_trust_snapshot_sha256": "c" * 64,
        },
    }
    live = {
        "source": TRUSTED_SOURCE,
        "upstream_repository": "jlcodes99/cockpit-tools",
        "release_id": 1328,
        "checked_utc": "2026-08-23T00:00:00+00:00",
        "baseline": COCKPIT_BASELINE,
    }
    good = evaluate_action_policy(report, live)
    drift = evaluate_action_policy(report, dict(live, baseline="1.3.29", release_id=1329))
    untrusted = evaluate_action_policy(report, dict(live, source="LOCAL_CONSTANT"))
    no_evidence = evaluate_action_policy(dict(report, real_packet_verified=False), live)
    no_crypto = evaluate_action_policy(dict(report, signer_trust={"valid": False}), live)
    no_anchor = evaluate_action_policy(dict(report, trust_anchor_match=False), live)
    no_source = json.loads(json.dumps(report)); no_source["provenance"].pop("source_certification_report_sha256", None)
    no_source_policy = evaluate_action_policy(no_source, live)
    no_authority = evaluate_action_policy(dict(report, reviewer_trust_authority={}), live)
    unsealed_authority = evaluate_action_policy(dict(report, reviewer_trust_authority=dict(authority, local_integrity_seal_valid=False)), live)
    packet_derived_authority = evaluate_action_policy(dict(report, reviewer_trust_authority=dict(authority, packet_derived=True)), live)
    no_release = evaluate_action_policy(dict(report, reviewer_release_authority={}), live)
    unsealed_release = evaluate_action_policy(dict(report, reviewer_release_authority=dict(release_authority, local_integrity_seal_valid=False)), live)
    derived_release = evaluate_action_policy(dict(report, reviewer_release_authority=dict(release_authority, packet_derived=True)), live)
    self_hashed_release = evaluate_action_policy(dict(report, reviewer_release_authority=dict(release_authority, local_artifact_hashed_at_capture=True)), live)
    wrong_release_package = evaluate_action_policy(dict(report, reviewer_release_authority=dict(release_authority, package_zip_sha256="9" * 64)), live)
    wrong_release_manifest = evaluate_action_policy(dict(report, reviewer_release_authority=dict(release_authority, release_manifest_sha256="8" * 64)), live)
    busy = evaluate_action_policy(report, live, busy=True)
    checks = {
        "match_allows_approve_reject_invalidate": all(good["permissions"].values()),
        "decision_provenance_gate_positive": good["gates"]["decision_provenance"] is True,
        "drift_allows_only_invalidate": drift["permissions"] == {"APPROVE": False, "REJECT": False, "INVALIDATE": True},
        "untrusted_live_blocks_all": not any(untrusted["permissions"].values()),
        "missing_verified_evidence_blocks_all": not any(no_evidence["permissions"].values()),
        "crypto_failure_blocks_all": not any(no_crypto["permissions"].values()) and not no_crypto["gates"]["signature"],
        "independent_anchor_failure_blocks_all": not any(no_anchor["permissions"].values()) and not no_anchor["gates"]["trust"],
        "missing_source_certification_blocks_all": not any(no_source_policy["permissions"].values()) and not no_source_policy["gates"]["decision_provenance"],
        "missing_reviewer_authority_blocks_all": not any(no_authority["permissions"].values()),
        "unsealed_reviewer_authority_blocks_all": not any(unsealed_authority["permissions"].values()),
        "packet_derived_reviewer_authority_blocks_all": not any(packet_derived_authority["permissions"].values()),
        "missing_release_authority_blocks_all": not any(no_release["permissions"].values()),
        "unsealed_release_authority_blocks_all": not any(unsealed_release["permissions"].values()),
        "packet_derived_release_authority_blocks_all": not any(derived_release["permissions"].values()),
        "self_hashed_release_authority_blocks_all": not any(self_hashed_release["permissions"].values()),
        "release_package_mismatch_blocks_all": not any(wrong_release_package["permissions"].values()),
        "release_manifest_mismatch_blocks_all": not any(wrong_release_manifest["permissions"].values()),
        "busy_blocks_all": not any(busy["permissions"].values()),
        "never_auto_certifies": good["automatic_production_certification"] is False,
        "never_mutates_score": good["production_score_mutation_authorized"] is False,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "PROMOTION_REVIEWER_ACTION_POLICY_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


if __name__ == "__main__":
    out = synthetic_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 2)
