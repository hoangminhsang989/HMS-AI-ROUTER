#!/usr/bin/env python3
from __future__ import annotations

import json
import re

VERSION = "25.75"
COCKPIT_BASELINE = "1.3.28"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TRUSTED_SOURCE = "GITHUB_RELEASES_LATEST"


def evaluate_action_policy(report, live_observation, *, busy=False):
    report = report if isinstance(report, dict) else {}
    live = live_observation if isinstance(live_observation, dict) else {}
    reasons = {str(x) for x in (report.get("reasons") or [])}
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    signer_trust = report.get("signer_trust") if isinstance(report.get("signer_trust"), dict) else {}

    evidence_verified = report.get("real_packet_verified") is True
    evidence_digest = str(provenance.get("raw_packet_sha256") or "").lower()
    manifest_digest = str(provenance.get("release_manifest_sha256") or "").lower()
    trust_digest = str(provenance.get("trust_snapshot_sha256") or "").lower()
    provenance_ok = bool(HEX64.fullmatch(evidence_digest) and HEX64.fullmatch(manifest_digest) and HEX64.fullmatch(trust_digest))

    signature_ok = evidence_verified and signer_trust.get("valid") is True
    trust_ok = signature_ok and report.get("trust_anchor_match") is True
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

    common = evidence_verified and provenance_ok and signature_ok and trust_ok and freshness_ok and idempotency_ok and trusted_live and not busy
    permissions = {"APPROVE": common and baseline_match, "REJECT": common and baseline_match, "INVALIDATE": common}
    reasons_out = []
    if not evidence_verified: reasons_out.append("VERIFIED_REAL_PACKET_REQUIRED")
    if not provenance_ok: reasons_out.append("EVIDENCE_PROVENANCE_REQUIRED")
    if not signature_ok: reasons_out.append("SIGNATURE_GATE_BLOCKED")
    if not trust_ok: reasons_out.append("TRUST_GATE_BLOCKED")
    if not freshness_ok: reasons_out.append("FRESHNESS_GATE_BLOCKED")
    if not idempotency_ok: reasons_out.append("IDEMPOTENCY_GATE_BLOCKED")
    if not trusted_live: reasons_out.append("TRUSTED_LIVE_BASELINE_REQUIRED")
    if trusted_live and not baseline_match: reasons_out.append("FROZEN_BASELINE_DRIFT")
    if busy: reasons_out.append("REVIEW_ACTION_BUSY")

    return {"product": "HMS-AI-ROUTER", "version": VERSION, "suite": "PROMOTION_REVIEWER_ACTION_POLICY",
        "permissions": permissions,
        "gates": {"evidence": evidence_verified and provenance_ok, "signature": signature_ok, "trust": trust_ok,
            "freshness": freshness_ok, "idempotency": idempotency_ok, "trusted_live_baseline": trusted_live, "baseline_match": baseline_match},
        "observed_baseline": observed_baseline, "reasons": sorted(set(reasons_out)),
        "automatic_production_certification": False, "production_score_mutation_authorized": False}


def synthetic_proof():
    report = {"real_packet_verified": True, "reasons": [], "trust_anchor_match": True, "signer_trust": {"valid": True},
        "provenance": {"raw_packet_sha256": "a" * 64, "release_manifest_sha256": "b" * 64, "trust_snapshot_sha256": "c" * 64}}
    live = {"source": TRUSTED_SOURCE, "upstream_repository": "jlcodes99/cockpit-tools", "release_id": 1328,
        "checked_utc": "2026-08-23T00:00:00+00:00", "baseline": COCKPIT_BASELINE}
    good = evaluate_action_policy(report, live)
    drift = evaluate_action_policy(report, dict(live, baseline="1.3.29", release_id=1329))
    untrusted = evaluate_action_policy(report, dict(live, source="LOCAL_CONSTANT"))
    no_evidence = evaluate_action_policy(dict(report, real_packet_verified=False), live)
    no_crypto = evaluate_action_policy(dict(report, signer_trust={"valid": False}), live)
    no_anchor = evaluate_action_policy(dict(report, trust_anchor_match=False), live)
    busy = evaluate_action_policy(report, live, busy=True)
    checks = {
        "match_allows_approve_reject_invalidate": all(good["permissions"].values()),
        "drift_allows_only_invalidate": drift["permissions"] == {"APPROVE": False, "REJECT": False, "INVALIDATE": True},
        "untrusted_live_blocks_all": not any(untrusted["permissions"].values()),
        "missing_verified_evidence_blocks_all": not any(no_evidence["permissions"].values()),
        "crypto_failure_blocks_all": not any(no_crypto["permissions"].values()) and not no_crypto["gates"]["signature"],
        "independent_anchor_failure_blocks_all": not any(no_anchor["permissions"].values()) and not no_anchor["gates"]["trust"],
        "busy_blocks_all": not any(busy["permissions"].values()),
        "never_auto_certifies": good["automatic_production_certification"] is False,
        "never_mutates_score": good["production_score_mutation_authorized"] is False,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(x["status"] == "PASS" for x in tests)
    return {"product": "HMS-AI-ROUTER", "version": VERSION, "suite": "PROMOTION_REVIEWER_ACTION_POLICY_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL", "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests, "automatic_production_certification": False, "production_score_mutation_authorized": False}


if __name__ == "__main__":
    out = synthetic_proof(); print(json.dumps(out, ensure_ascii=False, indent=2)); raise SystemExit(0 if out["verdict"] == "PASS" else 2)
