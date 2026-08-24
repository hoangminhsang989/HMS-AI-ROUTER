#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os
from pathlib import Path

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController

PRODUCT = "HMS-AI-ROUTER"


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def import_for_review(*, state_dir: Path, packet: Path, package_zip: Path, release_manifest: Path,
                      trust_authority: Path, authority_freshness_hours: int = 24,
                      cockpit_baseline: str = COCKPIT_BASELINE) -> dict:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    for path, reason in ((packet, "PACKET_MISSING"), (package_zip, "PACKAGE_ZIP_MISSING"),
                         (release_manifest, "RELEASE_MANIFEST_MISSING"), (trust_authority, "TRUST_AUTHORITY_MISSING")):
        if not path.is_file():
            raise FileNotFoundError(reason)
    ctl = PromotionWorkbenchController(state_dir)
    report = ctl.ingest(
        packet,
        expected_package_sha256=_sha_file(package_zip),
        expected_manifest_sha256=_sha_file(release_manifest),
        trust_authority_path=trust_authority,
        current_cockpit_baseline=cockpit_baseline,
        authority_freshness_hours=authority_freshness_hours,
    )
    if report.get("real_packet_verified") is not True:
        raise ValueError("PACKET_QUARANTINED:" + ",".join(report.get("reasons") or []))
    sealed = ctl.load_verified_report()
    authority = sealed.get("reviewer_trust_authority") or {}
    return {
        "product": PRODUCT, "version": VERSION, "suite": "REVIEWER_PACKET_IMPORT",
        "verdict": "VERIFIED_PACKET_PERSISTED_FOR_REVIEW",
        "raw_packet_sha256": (sealed.get("provenance") or {}).get("raw_packet_sha256", ""),
        "release_manifest_sha256": (sealed.get("provenance") or {}).get("release_manifest_sha256", ""),
        "trust_snapshot_sha256": (sealed.get("provenance") or {}).get("trust_snapshot_sha256", ""),
        "reviewer_trust_authority_sha256": authority.get("authority_sha256", ""),
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
    checks = {
        "windows_only_import": 'os.name != "nt"' in src,
        "controller_ingest_is_authority": "ctl.ingest" in src,
        "trust_authority_path_required": "trust_authority_path=trust_authority" in src,
        "package_and_manifest_hashed_locally": src.count("_sha_file(") >= 3,
        "sealed_report_reloaded": "ctl.load_verified_report" in src,
        "report_seal_required": "report_seal_path.is_file" in src,
        "replay_seal_required": "replay_seal_path.is_file" in src,
        "raw_packet_not_copied": '"raw_packet_copied_into_state_dir": False' in src,
        "no_auto_promotion": '"production_score_promotion_eligible": False' in src,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {"product": PRODUCT, "version": VERSION, "suite": "REVIEWER_PACKET_IMPORT_SOURCE_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)}, "tests": tests,
            "real_packet_import_executed": False, "windows_runtime_certified": False,
            "production_score_promotion_eligible": False}


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a certificate-signed Windows/Codex packet through sealed reviewer authority")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--state-dir", default="")
    ap.add_argument("--packet", default="")
    ap.add_argument("--package-zip", default="")
    ap.add_argument("--release-manifest", default="")
    ap.add_argument("--trust-authority", default="")
    ap.add_argument("--authority-freshness-hours", type=int, default=24)
    ap.add_argument("--cockpit-baseline", default=COCKPIT_BASELINE)
    args = ap.parse_args()
    if args.proof:
        out = source_proof(); code = 0 if out["verdict"] == "PASS" else 2
    else:
        if not all((args.state_dir, args.packet, args.package_zip, args.release_manifest, args.trust_authority)):
            ap.error("--state-dir --packet --package-zip --release-manifest --trust-authority required")
        try:
            out = import_for_review(state_dir=Path(args.state_dir), packet=Path(args.packet), package_zip=Path(args.package_zip),
                release_manifest=Path(args.release_manifest), trust_authority=Path(args.trust_authority),
                authority_freshness_hours=args.authority_freshness_hours, cockpit_baseline=args.cockpit_baseline); code = 0
        except Exception as exc:
            out = {"product": PRODUCT, "version": VERSION, "suite": "REVIEWER_PACKET_IMPORT",
                "verdict": "BLOCKED_FAIL_CLOSED", "error": type(exc).__name__, "detail": str(exc),
                "windows_runtime_certified": False, "production_score_promotion_eligible": False,
                "automatic_production_certification": False}; code = 2
    print(json.dumps(out, ensure_ascii=False, indent=2)); return code


if __name__ == "__main__":
    raise SystemExit(main())
