#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, re, tempfile, threading, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_ReviewerLocalIntegritySeal as local_seal
import HMS_Codex_ReviewerTrustAuthoritySnapshot as trust_authority
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION, verify_packet
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS
from HMS_Codex_WindowsPromotionDecisionLedger import append_decision, build_decision, read_ledger, reviewer_ref
from HMS_Codex_WindowsPromotionReviewWorkbench import build_state

HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPORT_SEAL_PURPOSE = "HMS_V2575_VERIFIED_INGEST_METADATA"
REPLAY_SEAL_PURPOSE = "HMS_V2575_INGEST_REPLAY_REGISTRY"
INGEST_LOCK_WAIT_SECONDS = 2.0
INGEST_LOCK_POLL_SECONDS = 0.02


def _stable(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _expected_import_digest(report):
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    body = {"baseline": report.get("cockpit_baseline"), "verified": report.get("real_packet_verified") is True,
            "provenance": provenance, "reasons": sorted(set(report.get("reasons") or []))}
    return hashlib.sha256(_stable(body)).hexdigest()


@contextmanager
def _exclusive_ingest_lock(lock_path: Path, timeout_seconds: float = INGEST_LOCK_WAIT_SECONDS):
    """Serialize replay load -> packet verify -> replay consume -> sealed report publish.

    A stale lock is never auto-stolen. An operator must inspect/remove it after a crashed
    process rather than HMS guessing lock ownership.
    """
    lock_path = Path(lock_path); lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.1, float(timeout_seconds)); fd = None
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    while fd is None:
        try:
            fd = os.open(lock_path, flags, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("ingest transaction lock busy; import aborted fail-closed")
            time.sleep(INGEST_LOCK_POLL_SECONDS)
    try:
        payload = json.dumps({"pid": os.getpid(), "created_utc": datetime.now(timezone.utc).isoformat()}, sort_keys=True).encode() + b"\n"
        os.write(fd, payload); os.fsync(fd); os.close(fd); fd = None
        yield lock_path
    finally:
        if fd is not None:
            try: os.close(fd)
            except OSError: pass
        try: lock_path.unlink()
        except FileNotFoundError: pass


def _verified_report_gate(report):
    """Require the full persisted ingest contract before any ledger mutation."""
    report = report if isinstance(report, dict) else {}; reasons = []
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    signer_trust = report.get("signer_trust") if isinstance(report.get("signer_trust"), dict) else {}
    case_matrix = report.get("case_matrix") if isinstance(report.get("case_matrix"), dict) else {}
    authority = report.get("reviewer_trust_authority") if isinstance(report.get("reviewer_trust_authority"), dict) else {}
    if report.get("real_packet_verified") is not True: reasons.append("VERIFIED_REAL_PACKET_REQUIRED")
    if report.get("ingest_status") != "VERIFIED_REAL_PACKET": reasons.append("VERIFIED_INGEST_STATUS_REQUIRED")
    if report.get("case_matrix_complete") is not True or case_matrix.get("valid") is not True: reasons.append("EXACT_CASE_MATRIX_REQUIRED")
    if report.get("raw_evidence_rewritten") is not False: reasons.append("RAW_EVIDENCE_IMMUTABILITY_REQUIRED")
    if report.get("cockpit_baseline") != COCKPIT_BASELINE: reasons.append("FROZEN_BASELINE_REQUIRED")
    if report.get("reasons") not in ([], None): reasons.append("INGEST_REASONS_MUST_BE_EMPTY")
    import_digest = str(report.get("import_digest") or "").lower()
    if HEX64.fullmatch(import_digest) is None: reasons.append("IMPORT_DIGEST_REQUIRED")
    elif import_digest != _expected_import_digest(report): reasons.append("IMPORT_DIGEST_RECOMPUTE_MISMATCH")
    if signer_trust.get("valid") is not True: reasons.append("CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED")
    if report.get("trust_anchor_match") is not True: reasons.append("INDEPENDENT_TRUST_ANCHOR_REQUIRED")
    if authority.get("valid") is not True or authority.get("local_integrity_seal_valid") is not True: reasons.append("SEALED_REVIEWER_TRUST_AUTHORITY_REQUIRED")
    if authority.get("packet_derived") is not False: reasons.append("REVIEWER_TRUST_AUTHORITY_PACKET_DERIVED")

    required_digests = ("raw_packet_sha256", "package_zip_sha256", "release_manifest_sha256", "trust_snapshot_sha256",
                        "expected_trust_snapshot_sha256", "signature_sha256", "certificate_sha256", "signed_payload_sha256")
    for field in required_digests:
        if HEX64.fullmatch(str(provenance.get(field) or "").lower()) is None: reasons.append("PROVENANCE_DIGEST_INVALID:" + field)
    observed_trust = str(provenance.get("trust_snapshot_sha256") or "").lower()
    expected_trust = str(provenance.get("expected_trust_snapshot_sha256") or "").lower()
    if observed_trust != expected_trust: reasons.append("PROVENANCE_TRUST_ANCHOR_MISMATCH")
    if str(authority.get("trust_snapshot_sha256") or "").lower() != expected_trust: reasons.append("REVIEWER_AUTHORITY_PROVENANCE_MISMATCH")
    if HEX64.fullmatch(str(authority.get("authority_sha256") or "").lower()) is None: reasons.append("REVIEWER_AUTHORITY_DIGEST_INVALID")
    for field in ("trust_snapshot_sha256", "certificate_sha256", "signature_sha256", "signed_payload_sha256"):
        if str(signer_trust.get(field) or "").lower() != str(provenance.get(field) or "").lower(): reasons.append("SIGNER_PROVENANCE_MISMATCH:" + field)
    if str(signer_trust.get("signer_key_id_ref") or "") != str(provenance.get("signer_key_id_ref") or ""): reasons.append("SIGNER_REF_PROVENANCE_MISMATCH")
    required_ids = provenance.get("required_case_ids")
    if not isinstance(required_ids, list) or tuple(required_ids) != tuple(REQUIRED_RUNTIME_CASE_IDS): reasons.append("PROVENANCE_CASE_CONTRACT_MISMATCH")
    case_digests = provenance.get("case_report_sha256")
    if (not isinstance(case_digests, list) or len(case_digests) != len(REQUIRED_RUNTIME_CASE_IDS)
            or len(set(case_digests)) != len(case_digests)
            or any(HEX64.fullmatch(str(x).lower()) is None for x in case_digests)):
        reasons.append("PROVENANCE_CASE_DIGESTS_INVALID")
    return {"valid": not reasons, "reasons": sorted(set(reasons)), "provenance": provenance}


class PromotionWorkbenchController:
    def __init__(self, state_dir):
        self.root = Path(state_dir); self.root.mkdir(parents=True, exist_ok=True)
        self.report_path = self.root / "verified_ingest_metadata.json"
        self.report_seal_path = self.root / "verified_ingest_metadata.seal.json"
        self.replay_path = self.root / "replay_registry.json"
        self.replay_seal_path = self.root / "replay_registry.seal.json"
        self.ledger_path = self.root / "promotion_decisions.jsonl"
        self.integrity_key_path = self.root / "reviewer_local_integrity.key.dpapi"
        self.ingest_lock_path = self.root / "ingest_transaction.lock"

    def _load_json(self, path, default):
        if not path.exists(): return default
        value = json.loads(path.read_text("utf-8")); return value if isinstance(value, type(default)) else default

    def _atomic_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp): os.unlink(tmp)
            except OSError: pass

    def _write_sealed_json(self, path, seal_path, payload, purpose):
        seal = local_seal.seal_payload(payload, purpose=purpose, key_path=self.integrity_key_path)
        self._atomic_json(path, payload); self._atomic_json(seal_path, seal)

    def _load_sealed_json(self, path, seal_path, default, purpose):
        if not path.exists() and not seal_path.exists(): return default
        if not path.is_file() or not seal_path.is_file(): raise ValueError("LOCAL_INTEGRITY_SEAL_PAIR_INCOMPLETE:" + path.name)
        payload = self._load_json(path, default); seal = self._load_json(seal_path, {})
        check = local_seal.verify_payload(payload, seal, purpose=purpose, key_path=self.integrity_key_path)
        if not check.get("valid"): raise ValueError("LOCAL_INTEGRITY_SEAL_INVALID:" + ",".join(check.get("reasons") or []))
        return payload

    def _load_replay_registry(self):
        return self._load_sealed_json(self.replay_path, self.replay_seal_path,
            {"packet_digests": [], "nonces": [], "run_ids": [], "report_ids": []}, REPLAY_SEAL_PURPOSE)

    def load_verified_report(self):
        report = self._load_sealed_json(self.report_path, self.report_seal_path, {}, REPORT_SEAL_PURPOSE)
        if not report: return {}
        gate = _verified_report_gate(report)
        if not gate["valid"]: raise ValueError("VERIFIED_INGEST_METADATA_INVALID:" + ",".join(gate["reasons"]))
        return report

    def ingest(self, packet_path, *, expected_package_sha256, expected_manifest_sha256, trust_authority_path,
               current_cockpit_baseline=COCKPIT_BASELINE, authority_freshness_hours=24):
        authority = trust_authority.load_and_verify_authority(Path(trust_authority_path), key_path=self.integrity_key_path,
            freshness_hours=authority_freshness_hours)
        if authority.get("valid") is not True:
            raise ValueError("SEALED_REVIEWER_TRUST_AUTHORITY_INVALID:" + ",".join(authority.get("reasons") or []))
        expected_trust = str(authority.get("trust_snapshot_sha256") or "").lower()
        path = Path(packet_path); raw = path.read_bytes(); packet = json.loads(raw.decode("utf-8-sig"))

        with _exclusive_ingest_lock(self.ingest_lock_path):
            registry = self._load_replay_registry()
            report = verify_packet(packet, raw_packet_sha256=hashlib.sha256(raw).hexdigest(),
                expected_package_sha256=expected_package_sha256, expected_manifest_sha256=expected_manifest_sha256,
                expected_trust_snapshot_sha256=expected_trust, current_cockpit_baseline=current_cockpit_baseline, seen=registry)
            if report["real_packet_verified"]:
                report["reviewer_trust_authority"] = {
                    "valid": True, "authority_sha256": authority.get("authority_sha256", ""),
                    "trust_snapshot_sha256": expected_trust, "active_pin_count": int(authority.get("active_pin_count") or 0),
                    "local_integrity_seal_valid": authority.get("local_integrity_seal_valid") is True,
                    "packet_derived": authority.get("packet_derived") is True,
                }
                gate = _verified_report_gate(report)
                if not gate["valid"]: raise ValueError("verified ingest metadata contract failed:" + ",".join(gate["reasons"]))
                next_registry = json.loads(json.dumps(registry))
                for key, value in (("packet_digests", report["provenance"]["raw_packet_sha256"]), ("nonces", packet.get("nonce")),
                                   ("run_ids", packet.get("run_id")), ("report_ids", packet.get("report_id"))):
                    items = next_registry.setdefault(key, [])
                    if value not in items: items.append(value)
                self._write_sealed_json(self.replay_path, self.replay_seal_path, next_registry, REPLAY_SEAL_PURPOSE)
                self._write_sealed_json(self.report_path, self.report_seal_path, report, REPORT_SEAL_PURPOSE)
            return report

    def record_decision(self, *, decision, reviewer_identity, reviewer_salt, lane, package_version,
                        observed_cockpit_baseline=COCKPIT_BASELINE, reason_codes=None, note_vi=""):
        report = self.load_verified_report(); gate = _verified_report_gate(report)
        if not gate["valid"]: raise ValueError("verified ingest metadata required before review:" + ",".join(gate["reasons"]))
        provenance = gate["provenance"]; records = read_ledger(self.ledger_path); ref = reviewer_ref(reviewer_identity, reviewer_salt)
        record = build_decision(records, decision=decision, reviewer_ref=ref, evidence_sha256=provenance.get("raw_packet_sha256", ""),
            manifest_sha256=provenance.get("release_manifest_sha256", ""), package_version=package_version,
            cockpit_baseline=observed_cockpit_baseline, lane=lane, reason_codes=reason_codes, note_vi=note_vi)
        append_decision(self.ledger_path, record)
        return {"reviewer_ref": ref, "decision_sha256": record["decision_sha256"], "epoch": record["epoch"], "decision": record["decision"],
                "lane": record["lane"], "observed_cockpit_baseline": record["cockpit_baseline"], "raw_reviewer_identity_stored": False}

    def record_review_action(self, *, decision, reviewer_identity, reviewer_salt, lane, package_version,
                             live_baseline_provider, reason_codes=None, note_vi=""):
        if not callable(live_baseline_provider): raise ValueError("live baseline provider required")
        live_baseline = str(live_baseline_provider() or "").strip()
        if not live_baseline: raise ValueError("live baseline recheck returned empty value")
        requested = str(decision or "").upper(); drift = live_baseline != COCKPIT_BASELINE
        effective = "INVALIDATE" if drift and requested != "INVALIDATE" else requested; reasons = list(reason_codes or [])
        if drift and "BASELINE_DRIFT_LIVE_RECHECK" not in reasons: reasons.append("BASELINE_DRIFT_LIVE_RECHECK")
        result = self.record_decision(decision=effective, reviewer_identity=reviewer_identity, reviewer_salt=reviewer_salt, lane=lane,
            package_version=package_version, observed_cockpit_baseline=live_baseline, reason_codes=reasons, note_vi=note_vi)
        result.update({"requested_decision": requested, "baseline_recheck_performed": True, "baseline_recheck_passed": not drift,
            "action_blocked_by_baseline_drift": drift and effective == "INVALIDATE", "automatic_production_certification": False,
            "production_score_mutation_authorized": False})
        return result

    def state(self, *, package_version, manifest_sha256, baseline_at_open, baseline_before_final_review, optional_gpu_required=False):
        report = self.load_verified_report()
        return build_state(ingest_report=report, ledger_records=read_ledger(self.ledger_path), package_version=package_version,
            manifest_sha256=manifest_sha256, baseline_at_open=baseline_at_open,
            baseline_before_final_review=baseline_before_final_review, optional_gpu_required=optional_gpu_required)


def synthetic_proof():
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); packet_path = root / "external-review.json"; state_dir = root / "state"; now = datetime.now(timezone.utc)
        base = {"source_classification": "REAL_EXTERNAL_WINDOWS_CODEX", "synthetic": False, "local_only": False,
            "target_os": "Windows", "codex_target": True, "package_zip_sha256": "a" * 64,
            "release_manifest_sha256": "b" * 64, "cockpit_baseline": COCKPIT_BASELINE, "capture_utc": now.isoformat(),
            "nonce": "nonce-012345", "run_id": "run-01234567", "report_id": "report-012345",
            "case_results": [{"case_id": cid, "status": "PASS", "report_sha256": h(cid)} for cid in REQUIRED_RUNTIME_CASE_IDS]}
        packet = synthetic_signed_packet(base); packet["signer"].pop("synthetic_fixture", None)
        raw = (json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n").encode(); packet_path.write_bytes(raw)
        original = hashlib.sha256(raw).hexdigest(); ctl = PromotionWorkbenchController(state_dir)

        trust_file = root / "reviewer-trust-store.json"
        store = {k: v for k, v in packet["trust_snapshot"].items() if k != "trust_snapshot_sha256"}; store["updated_utc"] = now.isoformat()
        trust_file.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        authority_path = root / "reviewer-trust-authority.json"
        authority_capture = trust_authority.capture_authority(trust_file, authority_path, ctl.integrity_key_path)

        first = ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64, trust_authority_path=authority_path)
        second = ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64, trust_authority_path=authority_path)

        forged_ctl = PromotionWorkbenchController(root / "forged-state"); forged_ctl._atomic_json(forged_ctl.report_path, {"real_packet_verified": True}); forged_blocked = False
        try:
            forged_ctl.record_review_action(decision="APPROVE", reviewer_identity="reviewer-x", reviewer_salt="controller-proof-salt-01",
                lane="TERMINAL_PTY", package_version=VERSION, live_baseline_provider=lambda: COCKPIT_BASELINE)
        except ValueError: forged_blocked = True

        report_bytes = ctl.report_path.read_bytes(); tampered_report = json.loads(report_bytes.decode("utf-8")); tampered_report["import_digest"] = "f" * 64
        ctl.report_path.write_text(json.dumps(tampered_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); report_tamper_blocked = False
        try: ctl.load_verified_report()
        except ValueError: report_tamper_blocked = True
        ctl.report_path.write_bytes(report_bytes)

        replay_bytes = ctl.replay_path.read_bytes(); tampered_replay = json.loads(replay_bytes.decode("utf-8")); tampered_replay["packet_digests"] = []
        ctl.replay_path.write_text(json.dumps(tampered_replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); replay_tamper_blocked = False
        try: ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64, trust_authority_path=authority_path)
        except ValueError: replay_tamper_blocked = True
        ctl.replay_path.write_bytes(replay_bytes)

        rogue_authority = json.loads(authority_path.read_text("utf-8")); rogue_authority["authority"]["trust_snapshot_sha256"] = "c" * 64
        rogue_path = root / "rogue-authority.json"; rogue_path.write_text(json.dumps(rogue_authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rogue_authority_blocked = False
        try:
            PromotionWorkbenchController(root / "rogue-state").ingest(packet_path, expected_package_sha256="a" * 64,
                expected_manifest_sha256="b" * 64, trust_authority_path=rogue_path)
        except ValueError: rogue_authority_blocked = True

        concurrent_ctl = PromotionWorkbenchController(root / "concurrent-state")
        concurrent_authority = root / "concurrent-authority.json"
        trust_authority.capture_authority(trust_file, concurrent_authority, concurrent_ctl.integrity_key_path)
        race_results = []; barrier = threading.Barrier(2)
        def import_worker():
            try:
                barrier.wait(timeout=2)
                r = concurrent_ctl.ingest(packet_path, expected_package_sha256="a" * 64, expected_manifest_sha256="b" * 64,
                    trust_authority_path=concurrent_authority)
                race_results.append((bool(r.get("real_packet_verified")), list(r.get("reasons") or [])))
            except Exception as exc:
                race_results.append((False, [type(exc).__name__ + ":" + str(exc)]))
        threads = [threading.Thread(target=import_worker) for _ in range(2)]
        [t.start() for t in threads]; [t.join(timeout=5) for t in threads]
        concurrent_registry_valid = True
        try: concurrent_ctl._load_replay_registry()
        except Exception: concurrent_registry_valid = False

        stale_ctl = PromotionWorkbenchController(root / "stale-lock-state"); stale_ctl.ingest_lock_path.write_text("stale-lock\n", encoding="utf-8")
        stale_lock_blocked = False
        try:
            with _exclusive_ingest_lock(stale_ctl.ingest_lock_path, timeout_seconds=0.1): pass
        except ValueError: stale_lock_blocked = True
        try: stale_ctl.ingest_lock_path.unlink()
        except FileNotFoundError: pass

        provider_calls = []
        def frozen_provider(): provider_calls.append("frozen"); return COCKPIT_BASELINE
        for lane in ("TERMINAL_PTY", "PROJECT_RESUME"):
            for identity in ("reviewer-a", "reviewer-b"):
                ctl.record_review_action(decision="APPROVE", reviewer_identity=identity, reviewer_salt="controller-proof-salt-01",
                    lane=lane, package_version=VERSION, live_baseline_provider=frozen_provider)
        state = ctl.state(package_version=VERSION, manifest_sha256="b" * 64, baseline_at_open=COCKPIT_BASELINE, baseline_before_final_review=COCKPIT_BASELINE)
        drift = ctl.record_review_action(decision="APPROVE", reviewer_identity="reviewer-a", reviewer_salt="controller-proof-salt-01",
            lane="TERMINAL_PTY", package_version=VERSION, live_baseline_provider=lambda: "1.3.29")

        race_verified = sum(1 for ok, _ in race_results if ok)
        race_replay_blocked = sum(1 for ok, reasons in race_results if (not ok) and "DUPLICATE_PACKET_DIGEST" in reasons)
        checks = {
            "reviewer_authority_captured_separately": authority_capture["verdict"] == "TRUST_AUTHORITY_CAPTURED",
            "verified_crypto_packet_persisted_with_local_seal": first["real_packet_verified"] and ctl.report_seal_path.exists(),
            "persisted_report_passes_full_gate": _verified_report_gate(ctl.load_verified_report())["valid"],
            "raw_packet_unchanged": hashlib.sha256(packet_path.read_bytes()).hexdigest() == original,
            "replay_rejected": "DUPLICATE_PACKET_DIGEST" in second["reasons"],
            "concurrent_same_packet_exactly_one_verified": race_verified == 1,
            "concurrent_same_packet_other_replay_blocked": race_replay_blocked == 1,
            "concurrent_registry_stays_seal_valid": concurrent_registry_valid,
            "ingest_lock_released_after_concurrency": not concurrent_ctl.ingest_lock_path.exists(),
            "stale_ingest_lock_never_auto_stolen": stale_lock_blocked,
            "forged_unsealed_metadata_cannot_write_ledger": forged_blocked and not forged_ctl.ledger_path.exists(),
            "persisted_report_tamper_rejected_by_local_seal": report_tamper_blocked,
            "replay_registry_tamper_rejected_by_local_seal": replay_tamper_blocked,
            "tampered_reviewer_authority_rejected": rogue_authority_blocked,
            "two_reviewer_two_lane_state_eligible": state["production_score_promotion_eligible"],
            "live_baseline_rechecked_for_each_review": len(provider_calls) == 4,
            "drift_blocks_requested_approve": drift["requested_decision"] == "APPROVE" and drift["decision"] == "INVALIDATE" and drift["action_blocked_by_baseline_drift"],
            "drift_records_observed_baseline": drift["observed_cockpit_baseline"] == "1.3.29",
            "controller_never_certifies": state["automatic_production_certification"] is False and drift["automatic_production_certification"] is False,
            "raw_reviewer_identity_not_in_ledger": "reviewer-a" not in ctl.ledger_path.read_text("utf-8") and "reviewer-b" not in ctl.ledger_path.read_text("utf-8"),
            "no_raw_packet_copy_in_state_dir": all(p.name != "external-review.json" for p in state_dir.iterdir()),
        }
        tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]; n = sum(x["status"] == "PASS" for x in tests)
        return {"product": "HMS-AI-ROUTER", "version": VERSION, "suite": "WINDOWS_PROMOTION_WORKBENCH_CONTROLLER_PROOF",
                "verdict": "PASS" if n == len(tests) else "FAIL", "summary": {"pass": n, "fail": len(tests)-n, "total": len(tests)},
                "tests": tests, "synthetic_fixture_only": True, "windows_runtime_certified": False,
                "production_score_mutation_authorized": False}


if __name__ == "__main__":
    out = synthetic_proof(); print(json.dumps(out, ensure_ascii=False, indent=2)); raise SystemExit(0 if out["verdict"] == "PASS" else 2)
