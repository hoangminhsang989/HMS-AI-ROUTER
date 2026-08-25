#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from HMS_Codex_WindowsPromotionDecisionLedger import COCKPIT_BASELINE, VERSION, evaluate, read_ledger

SENSITIVE = {
    "access_token", "refresh_token", "authorization", "cookie", "cookies", "credential", "credentials",
    "password", "raw_identity", "reviewer_identity", "secret", "token",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GIT_HEX = re.compile(r"^[0-9a-f]{40,64}$")


def metadata_only(value):
    if isinstance(value, dict):
        return {str(key): metadata_only(item) for key, item in value.items() if str(key).lower() not in SENSITIVE}
    if isinstance(value, list):
        return [metadata_only(item) for item in value]
    return value


def build_state(
    *,
    ingest_report,
    ledger_records,
    package_version,
    manifest_sha256,
    baseline_at_open,
    baseline_before_final_review,
    optional_gpu_required=False,
):
    reasons = []
    if ingest_report.get("real_packet_verified") is not True:
        reasons.append("QUARANTINE")
    if ingest_report.get("case_matrix_complete") is not True:
        reasons.append("RUNTIME_CASE_MATRIX_INCOMPLETE")
    if ingest_report.get("raw_evidence_rewritten") is not False:
        reasons.append("RAW_EVIDENCE_IMMUTABILITY_VIOLATION")

    provenance = ingest_report.get("provenance") if isinstance(ingest_report.get("provenance"), dict) else {}
    signer_trust = ingest_report.get("signer_trust") if isinstance(ingest_report.get("signer_trust"), dict) else {}
    authority = ingest_report.get("reviewer_trust_authority") if isinstance(ingest_report.get("reviewer_trust_authority"), dict) else {}
    release = ingest_report.get("reviewer_release_authority") if isinstance(ingest_report.get("reviewer_release_authority"), dict) else {}

    crypto_ok = signer_trust.get("valid") is True
    anchor_ok = ingest_report.get("trust_anchor_match") is True
    expected_trust = str(provenance.get("expected_trust_snapshot_sha256") or "").lower()
    authority_sha = str(authority.get("authority_sha256") or "").lower()
    release_sha = str(release.get("authority_sha256") or "").lower()
    authority_ok = (
        authority.get("valid") is True
        and authority.get("local_integrity_seal_valid") is True
        and authority.get("packet_derived") is False
        and HEX64.fullmatch(authority_sha) is not None
        and str(authority.get("trust_snapshot_sha256") or "").lower() == expected_trust
    )

    evidence = str(provenance.get("raw_packet_sha256") or "").lower()
    package_digest = str(provenance.get("package_zip_sha256") or "").lower()
    manifest_digest = str(provenance.get("release_manifest_sha256") or "").lower()
    source_certification = str(provenance.get("source_certification_report_sha256") or "").lower()
    release_ok = (
        release.get("valid") is True
        and release.get("local_integrity_seal_valid") is True
        and release.get("packet_derived") is False
        and release.get("local_artifact_hashed_at_capture") is False
        and HEX64.fullmatch(release_sha) is not None
        and GIT_HEX.fullmatch(str(release.get("source_commit_sha") or "").lower()) is not None
        and GIT_HEX.fullmatch(str(release.get("source_tree_sha") or "").lower()) is not None
        and str(release.get("package_zip_sha256") or "").lower() == package_digest
        and str(release.get("release_manifest_sha256") or "").lower() == manifest_digest
    )
    provenance_binding_ok = all(
        HEX64.fullmatch(value) is not None
        for value in (evidence, package_digest, manifest_digest, source_certification, authority_sha, release_sha)
    )

    if ingest_report.get("real_packet_verified") is True and not crypto_ok:
        reasons.append("CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED")
    if ingest_report.get("real_packet_verified") is True and not anchor_ok:
        reasons.append("INDEPENDENT_TRUST_ANCHOR_REQUIRED")
    if ingest_report.get("real_packet_verified") is True and not authority_ok:
        reasons.append("SEALED_REVIEWER_TRUST_AUTHORITY_REQUIRED")
    if ingest_report.get("real_packet_verified") is True and not release_ok:
        reasons.append("SEALED_REVIEWER_RELEASE_AUTHORITY_REQUIRED")
    if ingest_report.get("real_packet_verified") is True and not provenance_binding_ok:
        reasons.append("DECISION_PROVENANCE_BINDING_INVALID")
    if manifest_digest and str(manifest_sha256 or "").lower() != manifest_digest:
        reasons.append("WORKBENCH_MANIFEST_MISMATCH")

    baseline_ok = (
        baseline_at_open == COCKPIT_BASELINE
        and baseline_before_final_review == COCKPIT_BASELINE
        and ingest_report.get("cockpit_baseline") == COCKPIT_BASELINE
    )
    if not baseline_ok:
        reasons.append("FROZEN_BASELINE_DRIFT")

    review = evaluate(
        ledger_records,
        evidence_sha256=evidence,
        manifest_sha256=manifest_digest,
        package_sha256=package_digest,
        source_certification_report_sha256=source_certification,
        reviewer_trust_authority_sha256=authority_sha,
        reviewer_release_authority_sha256=release_sha,
        package_version=package_version,
        current_cockpit_baseline=baseline_before_final_review,
        optional_gpu_required=optional_gpu_required,
    )
    if not review["promotion_eligible"]:
        reasons.extend(review["reasons"])

    eligible = not reasons
    if "FROZEN_BASELINE_DRIFT" in reasons:
        status = "FROZEN_BASELINE_DRIFT"
        text = "Baseline Cockpit đã thay đổi. Phải append INVALIDATE, chạy Codex-only delta audit và mở epoch review mới."
    elif "QUARANTINE" in reasons:
        status = "QUARANTINE"
        text = "Packet chưa được xác minh là evidence Windows/Codex thật; không được dùng để xét promotion."
    elif not eligible:
        status = "REVIEW_REQUIRED"
        text = "Evidence hợp lệ nhưng chưa đủ gate provenance/trust/release/reviewer độc lập cho promotion."
    else:
        status = "ELIGIBLE_FOR_HUMAN_PROMOTION_PROPOSAL"
        text = "Đủ gate để auditor tạo đề xuất cho con người; hệ thống không tự tăng điểm hay tự chứng nhận."

    ingest_reasons = ingest_report.get("reasons") or []
    gates = {
        "evidence": ingest_report.get("real_packet_verified") is True,
        "signature": crypto_ok,
        "reviewer_trust_authority": authority_ok,
        "reviewer_release_authority": release_ok,
        "decision_provenance": provenance_binding_ok,
        "trust": crypto_ok and anchor_ok and authority_ok,
        "freshness": not any(value in ingest_reasons for value in ("EVIDENCE_STALE", "CAPTURE_UTC_INVALID", "CAPTURE_TIME_IN_FUTURE")),
        "idempotency": not any(str(value).endswith("_REPLAY") or value == "DUPLICATE_PACKET_DIGEST" for value in ingest_reasons),
        "reviewer_a_b": review["dual_review_complete"] is True,
        "baseline": baseline_ok,
    }
    return metadata_only({
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_PROMOTION_REVIEW_WORKBENCH",
        "status": status,
        "summary_vi": text,
        "gates": gates,
        "reasons": sorted(set(reasons)),
        "cockpit_baseline_required": COCKPIT_BASELINE,
        "baseline_at_open": baseline_at_open,
        "baseline_before_final_review": baseline_before_final_review,
        "evidence_provenance": provenance,
        "decision_provenance": {
            "evidence_sha256": evidence,
            "manifest_sha256": manifest_digest,
            "package_sha256": package_digest,
            "source_certification_report_sha256": source_certification,
            "reviewer_trust_authority_sha256": authority_sha,
            "reviewer_release_authority_sha256": release_sha,
        },
        "reviewer_trust_authority_sha256": authority_sha,
        "reviewer_release_authority_sha256": release_sha,
        "release_authority_source_commit_sha": release.get("source_commit_sha"),
        "release_authority_source_tree_sha": release.get("source_tree_sha"),
        "ingest_import_digest": ingest_report.get("import_digest"),
        "ledger_tail_sha256": review["ledger_tail_sha256"],
        "current_review_epoch": review["current_epoch"],
        "lane_summary": review["lane_summary"],
        "package_version": package_version,
        "manifest_sha256": manifest_digest,
        "package_sha256": package_digest,
        "source_certification_report_sha256": source_certification,
        "production_score_promotion_eligible": eligible,
        "requires_new_review_epoch": "FROZEN_BASELINE_DRIFT" in reasons,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
        "automatic_upstream_merge_authorized": False,
        "automatic_real_effect_rearm_authorized": False,
        "raw_evidence_included": False,
    })


def sensitive_paths(value):
    out = []
    def walk(item, path=""):
        if isinstance(item, dict):
            for key, child in item.items():
                child_path = f"{path}.{key}" if path else str(key)
                if str(key).lower() in SENSITIVE:
                    out.append(child_path)
                walk(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")
    walk(value)
    return out


def synthetic_proof():
    authority = {
        "valid": True,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
        "authority_sha256": "e" * 64,
        "trust_snapshot_sha256": "d" * 64,
    }
    release = {
        "valid": True,
        "local_integrity_seal_valid": True,
        "packet_derived": False,
        "local_artifact_hashed_at_capture": False,
        "authority_sha256": "9" * 64,
        "package_zip_sha256": "c" * 64,
        "release_manifest_sha256": "b" * 64,
        "source_commit_sha": "1" * 40,
        "source_tree_sha": "2" * 40,
    }
    ingest = {
        "real_packet_verified": True,
        "case_matrix_complete": True,
        "raw_evidence_rewritten": False,
        "cockpit_baseline": COCKPIT_BASELINE,
        "reasons": [],
        "trust_anchor_match": True,
        "signer_trust": {"valid": True},
        "reviewer_trust_authority": authority,
        "reviewer_release_authority": release,
        "provenance": {
            "raw_packet_sha256": "a" * 64,
            "package_zip_sha256": "c" * 64,
            "release_manifest_sha256": "b" * 64,
            "source_certification_report_sha256": "7" * 64,
            "trust_snapshot_sha256": "d" * 64,
            "expected_trust_snapshot_sha256": "d" * 64,
            "reviewer_identity": "secret-name",
        },
        "import_digest": "f" * 64,
    }
    state = build_state(
        ingest_report=ingest,
        ledger_records=[],
        package_version=VERSION,
        manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE,
        baseline_before_final_review=COCKPIT_BASELINE,
    )
    drift = build_state(
        ingest_report=ingest,
        ledger_records=[],
        package_version=VERSION,
        manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE,
        baseline_before_final_review="1.3.29",
    )
    no_anchor = json.loads(json.dumps(ingest)); no_anchor["trust_anchor_match"] = False
    anchor_state = build_state(ingest_report=no_anchor, ledger_records=[], package_version=VERSION, manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)
    no_authority = json.loads(json.dumps(ingest)); no_authority["reviewer_trust_authority"] = {}
    authority_state = build_state(ingest_report=no_authority, ledger_records=[], package_version=VERSION, manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)
    no_release = json.loads(json.dumps(ingest)); no_release["reviewer_release_authority"] = {}
    release_state = build_state(ingest_report=no_release, ledger_records=[], package_version=VERSION, manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)
    no_source = json.loads(json.dumps(ingest)); no_source["provenance"].pop("source_certification_report_sha256", None)
    source_state = build_state(ingest_report=no_source, ledger_records=[], package_version=VERSION, manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)
    wrong_release = json.loads(json.dumps(ingest)); wrong_release["reviewer_release_authority"]["package_zip_sha256"] = "8" * 64
    wrong_release_state = build_state(ingest_report=wrong_release, ledger_records=[], package_version=VERSION, manifest_sha256="b" * 64,
        baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)

    checks = {
        "zero_reviewer_never_promotes": not state["production_score_promotion_eligible"],
        "baseline_drift_freezes": drift["status"] == "FROZEN_BASELINE_DRIFT" and drift["requires_new_review_epoch"],
        "metadata_only_export": not sensitive_paths(state),
        "crypto_signature_gate_authoritative": state["gates"]["signature"] is True,
        "sealed_reviewer_authority_gate": state["gates"]["reviewer_trust_authority"] is True and authority_state["gates"]["reviewer_trust_authority"] is False,
        "sealed_release_authority_gate": state["gates"]["reviewer_release_authority"] is True and release_state["gates"]["reviewer_release_authority"] is False,
        "release_artifact_mismatch_blocks": wrong_release_state["gates"]["reviewer_release_authority"] is False,
        "source_certification_required_for_decision_binding": source_state["gates"]["decision_provenance"] is False,
        "decision_provenance_visible": state["decision_provenance"]["source_certification_report_sha256"] == "7" * 64,
        "independent_trust_anchor_gate": state["gates"]["trust"] is True and anchor_state["gates"]["trust"] is False,
        "anchor_missing_never_promotes": not anchor_state["production_score_promotion_eligible"],
        "authority_missing_never_promotes": not authority_state["production_score_promotion_eligible"],
        "release_authority_missing_never_promotes": not release_state["production_score_promotion_eligible"],
        "no_auto_authority": not state["automatic_production_certification"] and not state["production_score_mutation_authorized"],
        "vietnamese_guidance": any(value in state["summary_vi"].lower() for value in ("chưa", "không", "đủ")),
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_PROMOTION_REVIEW_WORKBENCH_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "production_score_promotion_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", action="store_true")
    parser.add_argument("--ingest-report")
    parser.add_argument("--ledger")
    parser.add_argument("--package-version")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--baseline-at-open", default=COCKPIT_BASELINE)
    parser.add_argument("--baseline-before-final-review", default=COCKPIT_BASELINE)
    parser.add_argument("--optional-gpu-required", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.proof:
        output = synthetic_proof()
        code = 0 if output["verdict"] == "PASS" else 2
    else:
        if not (args.ingest_report and args.ledger and args.package_version and args.manifest_sha256):
            parser.error("workbench inputs required")
        ingest = json.loads(Path(args.ingest_report).read_text("utf-8"))
        output = build_state(
            ingest_report=ingest,
            ledger_records=read_ledger(Path(args.ledger)),
            package_version=args.package_version,
            manifest_sha256=args.manifest_sha256,
            baseline_at_open=args.baseline_at_open,
            baseline_before_final_review=args.baseline_before_final_review,
            optional_gpu_required=args.optional_gpu_required,
        )
        code = 0 if output["production_score_promotion_eligible"] else 4
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
