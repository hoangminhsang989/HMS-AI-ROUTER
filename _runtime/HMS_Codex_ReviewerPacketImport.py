#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os
from pathlib import Path

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController
import HMS_Codex_ReviewerReleaseAuthority as release_authority

PRODUCT = "HMS-AI-ROUTER"


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_release_authority(*, ctl: PromotionWorkbenchController, authority_path: Path,
                              package_zip: Path, release_manifest: Path,
                              freshness_hours: int) -> dict:
    authority = release_authority.load_and_verify_authority(
        authority_path,
        key_path=ctl.integrity_key_path,
        freshness_hours=freshness_hours,
    )
    if authority.get("valid") is not True:
        raise ValueError("SEALED_REVIEWER_RELEASE_AUTHORITY_INVALID:" + ",".join(authority.get("reasons") or []))
    if authority.get("packet_derived") is not False:
        raise ValueError("RELEASE_AUTHORITY_PACKET_DERIVED")
    if authority.get("local_artifact_hashed_at_capture") is not False:
        raise ValueError("RELEASE_AUTHORITY_SELF_HASHED_LOCAL_ARTIFACT")

    package_sha = _sha_file(package_zip)
    manifest_sha = _sha_file(release_manifest)
    expected_package = str(authority.get("package_zip_sha256") or "").lower()
    expected_manifest = str(authority.get("release_manifest_sha256") or "").lower()
    if package_sha != expected_package:
        raise ValueError("RELEASE_AUTHORITY_PACKAGE_SHA256_MISMATCH")
    if manifest_sha != expected_manifest:
        raise ValueError("RELEASE_AUTHORITY_MANIFEST_SHA256_MISMATCH")
    return {
        "authority": authority,
        "package_zip_sha256": package_sha,
        "release_manifest_sha256": manifest_sha,
    }


def import_for_review(*, state_dir: Path, packet: Path, package_zip: Path, release_manifest: Path,
                      trust_authority: Path, release_authority_path: Path,
                      authority_freshness_hours: int = 24, release_authority_freshness_hours: int = 168,
                      cockpit_baseline: str = COCKPIT_BASELINE) -> dict:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    for path, reason in (
        (packet, "PACKET_MISSING"),
        (package_zip, "PACKAGE_ZIP_MISSING"),
        (release_manifest, "RELEASE_MANIFEST_MISSING"),
        (trust_authority, "TRUST_AUTHORITY_MISSING"),
        (release_authority_path, "RELEASE_AUTHORITY_MISSING"),
    ):
        if not path.is_file():
            raise FileNotFoundError(reason)

    ctl = PromotionWorkbenchController(state_dir)
    release_gate = _verify_release_authority(
        ctl=ctl,
        authority_path=release_authority_path,
        package_zip=package_zip,
        release_manifest=release_manifest,
        freshness_hours=release_authority_freshness_hours,
    )
    reviewed_release = release_gate["authority"]

    report = ctl.ingest(
        packet,
        expected_package_sha256=reviewed_release["package_zip_sha256"],
        expected_manifest_sha256=reviewed_release["release_manifest_sha256"],
        trust_authority_path=trust_authority,
        current_cockpit_baseline=cockpit_baseline,
        authority_freshness_hours=authority_freshness_hours,
    )
    if report.get("real_packet_verified") is not True:
        raise ValueError("PACKET_QUARANTINED:" + ",".join(report.get("reasons") or []))

    sealed = ctl.load_verified_report()
    provenance = sealed.get("provenance") if isinstance(sealed.get("provenance"), dict) else {}
    if str(provenance.get("package_zip_sha256") or "").lower() != reviewed_release["package_zip_sha256"]:
        raise ValueError("SEALED_PROVENANCE_RELEASE_AUTHORITY_PACKAGE_MISMATCH")
    if str(provenance.get("release_manifest_sha256") or "").lower() != reviewed_release["release_manifest_sha256"]:
        raise ValueError("SEALED_PROVENANCE_RELEASE_AUTHORITY_MANIFEST_MISMATCH")

    trust = sealed.get("reviewer_trust_authority") or {}
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "REVIEWER_PACKET_IMPORT",
        "verdict": "VERIFIED_PACKET_PERSISTED_FOR_REVIEW",
        "raw_packet_sha256": provenance.get("raw_packet_sha256", ""),
        "package_zip_sha256": provenance.get("package_zip_sha256", ""),
        "release_manifest_sha256": provenance.get("release_manifest_sha256", ""),
        "trust_snapshot_sha256": provenance.get("trust_snapshot_sha256", ""),
        "reviewer_trust_authority_sha256": trust.get("authority_sha256", ""),
        "reviewer_release_authority_sha256": reviewed_release.get("authority_sha256", ""),
        "release_authority_source_commit_sha": reviewed_release.get("source_commit_sha", ""),
        "release_authority_source_tree_sha": reviewed_release.get("source_tree_sha", ""),
        "release_authority_packet_derived": reviewed_release.get("packet_derived") is True,
        "release_authority_local_artifact_hashed_at_capture": reviewed_release.get("local_artifact_hashed_at_capture") is True,
        "report_local_integrity_seal_present": ctl.report_seal_path.is_file(),
        "replay_registry_local_integrity_seal_present": ctl.replay_seal_path.is_file(),
        "raw_packet_copied_into_state_dir": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def source_proof() -> dict:
    src = Path(__file__).read_text("utf-8")
    pre_ingest = src.split("report = ctl.ingest", 1)[0]
    post_ingest = src.split("report = ctl.ingest", 1)[1] if "report = ctl.ingest" in src else ""
    checks = {
        "windows_only_import": 'os.name != "nt"' in src,
        "release_authority_module_required": "import HMS_Codex_ReviewerReleaseAuthority as release_authority" in src,
        "release_authority_verified_with_reviewer_dpapi_key": "key_path=ctl.integrity_key_path" in src,
        "release_authority_verified_before_controller_ingest": "load_and_verify_authority" in pre_ingest,
        "packet_derived_release_authority_rejected": "RELEASE_AUTHORITY_PACKET_DERIVED" in pre_ingest,
        "self_hashed_release_authority_rejected": "RELEASE_AUTHORITY_SELF_HASHED_LOCAL_ARTIFACT" in pre_ingest,
        "local_package_compared_to_explicit_authority": "RELEASE_AUTHORITY_PACKAGE_SHA256_MISMATCH" in pre_ingest,
        "local_manifest_compared_to_explicit_authority": "RELEASE_AUTHORITY_MANIFEST_SHA256_MISMATCH" in pre_ingest,
        "controller_uses_authority_package_digest": 'expected_package_sha256=reviewed_release["package_zip_sha256"]' in src,
        "controller_uses_authority_manifest_digest": 'expected_manifest_sha256=reviewed_release["release_manifest_sha256"]' in src,
        "sealed_provenance_rechecked_against_release_authority": "SEALED_PROVENANCE_RELEASE_AUTHORITY_PACKAGE_MISMATCH" in post_ingest and "SEALED_PROVENANCE_RELEASE_AUTHORITY_MANIFEST_MISMATCH" in post_ingest,
        "trust_authority_path_required": "trust_authority_path=trust_authority" in src,
        "sealed_report_reloaded": "ctl.load_verified_report" in src,
        "report_seal_required": "report_seal_path.is_file" in src,
        "replay_seal_required": "replay_seal_path.is_file" in src,
        "release_authority_cli_required": 'ap.add_argument("--release-authority"' in src,
        "raw_packet_not_copied": '"raw_packet_copied_into_state_dir": False' in src,
        "no_auto_promotion": '"production_score_promotion_eligible": False' in src,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "REVIEWER_PACKET_IMPORT_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "real_packet_import_executed": False,
        "real_release_authority_verified": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a certificate-signed Windows/Codex packet through sealed reviewer authorities")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--state-dir", default="")
    ap.add_argument("--packet", default="")
    ap.add_argument("--package-zip", default="")
    ap.add_argument("--release-manifest", default="")
    ap.add_argument("--trust-authority", default="")
    ap.add_argument("--release-authority", default="")
    ap.add_argument("--authority-freshness-hours", type=int, default=24)
    ap.add_argument("--release-authority-freshness-hours", type=int, default=168)
    ap.add_argument("--cockpit-baseline", default=COCKPIT_BASELINE)
    args = ap.parse_args()
    if args.proof:
        out = source_proof()
        code = 0 if out["verdict"] == "PASS" else 2
    else:
        if not all((args.state_dir, args.packet, args.package_zip, args.release_manifest, args.trust_authority, args.release_authority)):
            ap.error("--state-dir --packet --package-zip --release-manifest --trust-authority --release-authority required")
        try:
            out = import_for_review(
                state_dir=Path(args.state_dir),
                packet=Path(args.packet),
                package_zip=Path(args.package_zip),
                release_manifest=Path(args.release_manifest),
                trust_authority=Path(args.trust_authority),
                release_authority_path=Path(args.release_authority),
                authority_freshness_hours=args.authority_freshness_hours,
                release_authority_freshness_hours=args.release_authority_freshness_hours,
                cockpit_baseline=args.cockpit_baseline,
            )
            code = 0
        except Exception as exc:
            out = {
                "product": PRODUCT,
                "version": VERSION,
                "suite": "REVIEWER_PACKET_IMPORT",
                "verdict": "BLOCKED_FAIL_CLOSED",
                "error": type(exc).__name__,
                "detail": str(exc),
                "windows_runtime_certified": False,
                "production_score_promotion_eligible": False,
                "automatic_production_certification": False,
            }
            code = 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
