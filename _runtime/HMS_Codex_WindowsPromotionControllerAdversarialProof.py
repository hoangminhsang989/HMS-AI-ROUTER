#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_ReviewerReleaseAuthority as release_authority
import HMS_Codex_ReviewerTrustAuthoritySnapshot as trust_authority
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController, _exclusive_ingest_lock, _proof_packet

PRODUCT = "HMS-AI-ROUTER"


def _controller_with_reviewer_key(root: Path, key_path: Path) -> PromotionWorkbenchController:
    ctl = PromotionWorkbenchController(root)
    ctl.integrity_key_path = key_path
    return ctl


def synthetic_proof():
    h = lambda text: hashlib.sha256(text.encode()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        now = datetime.now(timezone.utc)
        packet = _proof_packet(now, h)
        packet_path = root / "external-review.json"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

        ctl = PromotionWorkbenchController(root / "state")
        trust_file = root / "reviewer-trust-store.json"
        trust_store = {key: value for key, value in packet["trust_snapshot"].items() if key != "trust_snapshot_sha256"}
        trust_store["updated_utc"] = now.isoformat()
        trust_file.write_text(json.dumps(trust_store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        trust_path = root / "reviewer-trust-authority.json"
        release_path = root / "reviewer-release-authority.json"
        trust_authority.capture_authority(trust_file, trust_path, ctl.integrity_key_path)
        release_authority.capture_authority(
            package_zip_sha256="a" * 64,
            release_manifest_sha256="b" * 64,
            source_commit_sha="1" * 40,
            source_tree_sha="2" * 40,
            output_path=release_path,
            key_path=ctl.integrity_key_path,
        )
        first = ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64,
            trust_authority_path=trust_path, release_authority_path=release_path)

        replay_bytes = ctl.replay_path.read_bytes()
        replay_obj = json.loads(replay_bytes.decode("utf-8")); replay_obj["packet_digests"] = []
        ctl.replay_path.write_text(json.dumps(replay_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        replay_tamper_blocked = False
        try:
            ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64,
                trust_authority_path=trust_path, release_authority_path=release_path)
        except ValueError:
            replay_tamper_blocked = True
        ctl.replay_path.write_bytes(replay_bytes)

        report_bytes = ctl.report_path.read_bytes()
        report_obj = json.loads(report_bytes.decode("utf-8")); report_obj["reviewer_release_authority"]["authority_sha256"] = "0" * 64
        ctl.report_path.write_text(json.dumps(report_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_release_tamper_blocked = False
        try:
            ctl.load_verified_report()
        except ValueError:
            report_release_tamper_blocked = True
        ctl.report_path.write_bytes(report_bytes)

        rogue_trust_obj = json.loads(trust_path.read_text("utf-8")); rogue_trust_obj["authority"]["trust_snapshot_sha256"] = "c" * 64
        rogue_trust_path = root / "rogue-trust.json"
        rogue_trust_path.write_text(json.dumps(rogue_trust_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rogue_trust_ctl = _controller_with_reviewer_key(root / "rogue-trust-state", ctl.integrity_key_path)
        rogue_trust_blocked = False
        try:
            rogue_trust_ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64,
                trust_authority_path=rogue_trust_path, release_authority_path=release_path)
        except ValueError:
            rogue_trust_blocked = True

        rogue_release_obj = json.loads(release_path.read_text("utf-8")); rogue_release_obj["authority"]["package_zip_sha256"] = "9" * 64
        rogue_release_path = root / "rogue-release.json"
        rogue_release_path.write_text(json.dumps(rogue_release_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rogue_release_ctl = _controller_with_reviewer_key(root / "rogue-release-state", ctl.integrity_key_path)
        rogue_release_blocked = False
        try:
            rogue_release_ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64,
                trust_authority_path=trust_path, release_authority_path=rogue_release_path)
        except ValueError:
            rogue_release_blocked = True

        forged_ctl = PromotionWorkbenchController(root / "forged-state")
        forged_ctl._atomic_json(forged_ctl.report_path, {"real_packet_verified": True})
        forged_blocked = False
        try:
            forged_ctl.record_review_action(decision="APPROVE", reviewer_identity="reviewer-z",
                reviewer_salt="controller-adversarial-salt-01", lane="TERMINAL_PTY", package_version=VERSION,
                live_baseline_provider=lambda: COCKPIT_BASELINE)
        except ValueError:
            forged_blocked = True

        stale_ctl = PromotionWorkbenchController(root / "stale-lock-state")
        stale_ctl.ingest_lock_path.write_text("stale-lock\n", encoding="utf-8")
        stale_lock_blocked = False
        try:
            with _exclusive_ingest_lock(stale_ctl.ingest_lock_path, timeout_seconds=0.1):
                pass
        except ValueError:
            stale_lock_blocked = True
        try:
            stale_ctl.ingest_lock_path.unlink()
        except FileNotFoundError:
            pass

        checks = {
            "positive_control_verified_before_adversarial_cases": first.get("real_packet_verified") is True,
            "replay_registry_tamper_rejected_by_local_seal": replay_tamper_blocked,
            "sealed_report_release_authority_tamper_rejected": report_release_tamper_blocked,
            "tampered_reviewer_trust_authority_rejected_with_same_reviewer_key": rogue_trust_blocked,
            "tampered_reviewer_release_authority_rejected_with_same_reviewer_key": rogue_release_blocked,
            "forged_unsealed_metadata_cannot_write_ledger": forged_blocked and not forged_ctl.ledger_path.exists(),
            "stale_ingest_lock_never_auto_stolen": stale_lock_blocked,
            "adversarial_proof_grants_no_production_authority": True,
        }
        tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
        passed = sum(test["status"] == "PASS" for test in tests)
        return {"product": PRODUCT, "version": VERSION, "suite": "WINDOWS_PROMOTION_CONTROLLER_ADVERSARIAL_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)}, "tests": tests,
            "synthetic_fixture_only": True, "real_windows_target_evidence_used": False,
            "windows_runtime_certified": False, "production_score_promotion_eligible": False,
            "automatic_production_certification": False, "production_score_mutation_authorized": False}


def main() -> int:
    result = synthetic_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
