#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import HMS_Codex_ExternalWindowsCaseReportExporter as exporter
import HMS_Codex_ExternalWindowsEvidenceRunner as runner
import HMS_Codex_ExternalWindowsReviewPacketIngest as ingest
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _case(name: str, ok: bool, *, group: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "group": group, "status": "PASS" if ok else "FAIL", "detail": detail}


def _expect_raises(fn: Callable[[], Any], contains: str) -> bool:
    try:
        fn()
    except Exception as exc:
        return contains in str(exc)
    return False


def _base_packet(now: datetime, *, seed: str = "base", case_ids: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    ids = list(case_ids if case_ids is not None else REQUIRED_RUNTIME_CASE_IDS)
    source_ref = _sha("source-certification:" + seed)
    return {
        "source_classification": ingest.SOURCE_CLASSIFICATION,
        "synthetic": False,
        "local_only": False,
        "target_os": "Windows",
        "codex_target": True,
        "package_zip_sha256": "a" * 64,
        "release_manifest_sha256": "b" * 64,
        "source_certification_report_sha256": source_ref,
        "cockpit_baseline": ingest.COCKPIT_BASELINE,
        "capture_utc": now.isoformat(),
        "nonce": f"nonce-{seed}-01234567",
        "run_id": f"run-{seed}-0123456789",
        "report_id": f"report-{seed}-01234567",
        "case_results": [
            {
                "case_id": cid,
                "status": "PASS",
                "report_sha256": _sha(f"{seed}:{i}:{cid}"),
                "source_report_sha256": source_ref,
            }
            for i, cid in enumerate(ids)
        ],
    }


def _signed(base: dict[str, Any]) -> dict[str, Any]:
    packet = synthetic_signed_packet(base)
    # Remove only the synthetic signer marker so field-specific ingest gates are reachable.
    # The fixture remains in-memory proof data and never becomes external evidence.
    packet["signer"].pop("synthetic_fixture", None)
    return packet


def _verify(packet: dict[str, Any], *, now: datetime, raw: str, seen: dict[str, Any] | None = None,
            expected_package: str = "a" * 64, expected_manifest: str = "b" * 64,
            expected_trust: str | None = None) -> dict[str, Any]:
    trust = expected_trust
    if trust is None:
        trust = str((packet.get("trust_snapshot") or {}).get("trust_snapshot_sha256") or "")
    return ingest.verify_packet(
        packet,
        raw_packet_sha256=raw,
        expected_package_sha256=expected_package,
        expected_manifest_sha256=expected_manifest,
        expected_trust_snapshot_sha256=trust,
        current_cockpit_baseline=ingest.COCKPIT_BASELINE,
        seen=seen,
        now=now,
    )


def _ingest_cases() -> list[dict[str, Any]]:
    now = datetime(2026, 8, 24, 13, 0, tzinfo=timezone.utc)
    tests: list[dict[str, Any]] = []

    def check(name: str, mutate: Callable[[dict[str, Any]], None], reason: str, *, seed: str | None = None,
              verify_kwargs: dict[str, Any] | None = None) -> None:
        fixture_seed = seed or name
        base = _base_packet(now, seed=fixture_seed)
        mutate(base)
        packet = _signed(base)
        result = _verify(packet, now=now, raw=_sha("raw:" + fixture_seed), **(verify_kwargs or {}))
        tests.append(_case(name, result["real_packet_verified"] is False and reason in result["reasons"],
                           group="ingest-negative", detail=reason))

    good = _signed(_base_packet(now, seed="good"))
    good_result = _verify(good, now=now, raw=_sha("raw:good"))
    tests.append(_case("exact_seven_control_still_verifies", good_result["real_packet_verified"] is True,
                       group="ingest-control"))

    six = _signed(_base_packet(now, seed="six", case_ids=REQUIRED_RUNTIME_CASE_IDS[:-1]))
    six_result = _verify(six, now=now, raw=_sha("raw:six"))
    tests.extend([
        _case("six_case_matrix_rejected", "RUNTIME_CASE_MATRIX_NOT_7" in six_result["reasons"], group="ingest-negative"),
        _case("six_case_missing_required_reported", "RUNTIME_CASE_MATRIX_MISSING_REQUIRED" in six_result["reasons"], group="ingest-negative"),
    ])

    eight_ids = list(REQUIRED_RUNTIME_CASE_IDS) + ["unexpected_case"]
    eight = _signed(_base_packet(now, seed="eight", case_ids=eight_ids))
    eight_result = _verify(eight, now=now, raw=_sha("raw:eight"))
    tests.extend([
        _case("eight_case_matrix_rejected", "RUNTIME_CASE_MATRIX_NOT_7" in eight_result["reasons"], group="ingest-negative"),
        _case("eight_case_unexpected_id_reported", "RUNTIME_CASE_MATRIX_UNEXPECTED_ID" in eight_result["reasons"], group="ingest-negative"),
    ])

    check("failed_case_status_rejected", lambda b: b["case_results"][3].__setitem__("status", "FAIL"), "CASE_3_NOT_PASS")
    check("wrong_target_os_rejected", lambda b: b.__setitem__("target_os", "Linux"), "WINDOWS_TARGET_REQUIRED")
    check("codex_target_false_rejected", lambda b: b.__setitem__("codex_target", False), "CODEX_TARGET_REQUIRED")
    check("wrong_source_classification_rejected", lambda b: b.__setitem__("source_classification", "LOCAL_SYNTHETIC"), "REAL_EXTERNAL_WINDOWS_CODEX_SOURCE_REQUIRED")
    check("local_only_rejected", lambda b: b.__setitem__("local_only", True), "LOCAL_ONLY_EVIDENCE_REJECTED")
    check("synthetic_flag_rejected", lambda b: b.__setitem__("synthetic", True), "SYNTHETIC_EVIDENCE_REJECTED")
    check("missing_source_certification_hash_rejected", lambda b: b.pop("source_certification_report_sha256"), "SOURCE_CERTIFICATION_REPORT_SHA256_REQUIRED")
    check("invalid_case_source_hash_rejected", lambda b: b["case_results"][0].__setitem__("source_report_sha256", "bad"), "CASE_0_SOURCE_REPORT_SHA256_INVALID")
    check("case_source_mismatch_rejected", lambda b: b["case_results"][0].__setitem__("source_report_sha256", "d" * 64), "RUNTIME_CASE_SOURCE_REPORT_MISMATCH")
    check("package_digest_mismatch_rejected", lambda b: None, "PACKAGE_ZIP_SHA256_MISMATCH",
          verify_kwargs={"expected_package": "c" * 64})
    check("invalid_expected_package_digest_rejected", lambda b: None, "PACKAGE_ZIP_SHA256_MISMATCH",
          verify_kwargs={"expected_package": "bad"})
    check("manifest_digest_mismatch_rejected", lambda b: None, "RELEASE_MANIFEST_SHA256_MISMATCH",
          verify_kwargs={"expected_manifest": "d" * 64})
    check("invalid_expected_manifest_digest_rejected", lambda b: None, "RELEASE_MANIFEST_SHA256_MISMATCH",
          verify_kwargs={"expected_manifest": "bad"})
    check("case_report_digest_invalid_rejected", lambda b: b["case_results"][0].__setitem__("report_sha256", "bad"), "CASE_0_REPORT_DIGEST_INVALID")
    check("duplicate_case_id_rejected", lambda b: b["case_results"][1].__setitem__("case_id", b["case_results"][0]["case_id"]), "DUPLICATE_RUNTIME_CASE_ID")
    check("unexpected_case_id_rejected", lambda b: b["case_results"][1].__setitem__("case_id", "surprise"), "RUNTIME_CASE_MATRIX_UNEXPECTED_ID")

    def duplicate_report_digest(base: dict[str, Any]) -> None:
        base["case_results"][1]["report_sha256"] = base["case_results"][0]["report_sha256"]
    check("duplicate_runtime_report_digest_rejected", duplicate_report_digest, "DUPLICATE_RUNTIME_REPORT_DIGEST")

    def non_dict_case(base: dict[str, Any]) -> None:
        base["case_results"][2] = "invalid-case-shape"
    check("non_dict_case_rejected", non_dict_case, "CASE_2_INVALID")

    stale_base = _base_packet(now - timedelta(hours=73), seed="stale")
    stale = _signed(stale_base)
    stale_result = _verify(stale, now=now, raw=_sha("raw:stale"))
    tests.append(_case("stale_capture_rejected", "EVIDENCE_STALE" in stale_result["reasons"], group="ingest-negative"))

    future_base = _base_packet(now + timedelta(minutes=6), seed="future")
    future = _signed(future_base)
    future_result = _verify(future, now=now, raw=_sha("raw:future"))
    tests.append(_case("future_capture_rejected", "CAPTURE_TIME_IN_FUTURE" in future_result["reasons"], group="ingest-negative"))

    invalid_time_base = _base_packet(now, seed="badtime")
    invalid_time_base["capture_utc"] = "not-a-time"
    invalid_time = _signed(invalid_time_base)
    invalid_time_result = _verify(invalid_time, now=now, raw=_sha("raw:badtime"))
    tests.append(_case("invalid_capture_time_rejected", "CAPTURE_UTC_INVALID" in invalid_time_result["reasons"], group="ingest-negative"))

    for field, seen_key, reason in (
        ("nonce", "nonces", "NONCE_REPLAY"),
        ("run_id", "run_ids", "RUN_ID_REPLAY"),
        ("report_id", "report_ids", "REPORT_ID_REPLAY"),
    ):
        packet = _signed(_base_packet(now, seed="replay-" + field))
        value = packet[field]
        result = _verify(packet, now=now, raw=_sha("raw:replay:" + field), seen={seen_key: [value]})
        tests.append(_case(f"{field}_replay_rejected", reason in result["reasons"], group="ingest-replay"))

    for field, reason in (("nonce", "NONCE_INVALID"), ("run_id", "RUN_ID_INVALID"), ("report_id", "REPORT_ID_INVALID")):
        base = _base_packet(now, seed="short-" + field)
        base[field] = "short"
        packet = _signed(base)
        result = _verify(packet, now=now, raw=_sha("raw:short:" + field))
        tests.append(_case(f"{field}_length_rejected", reason in result["reasons"], group="ingest-negative"))

    invalid_raw = _signed(_base_packet(now, seed="invalid-raw"))
    invalid_raw_result = _verify(invalid_raw, now=now, raw="bad")
    tests.append(_case("invalid_raw_packet_digest_rejected", "RAW_PACKET_DIGEST_INVALID" in invalid_raw_result["reasons"], group="ingest-negative"))

    packet_replay = _signed(_base_packet(now, seed="packet-replay"))
    raw_replay = _sha("raw:packet-replay")
    packet_replay_result = _verify(packet_replay, now=now, raw=raw_replay, seen={"packet_digests": [raw_replay]})
    tests.append(_case("packet_digest_replay_rejected", "DUPLICATE_PACKET_DIGEST" in packet_replay_result["reasons"], group="ingest-replay"))

    wrong_baseline_base = _base_packet(now, seed="baseline")
    wrong_baseline_base["cockpit_baseline"] = "1.3.27"
    wrong_baseline = _signed(wrong_baseline_base)
    wrong_baseline_result = _verify(wrong_baseline, now=now, raw=_sha("raw:baseline"))
    tests.append(_case("baseline_drift_rejected", "COCKPIT_BASELINE_CHANGED_OR_STALE" in wrong_baseline_result["reasons"], group="ingest-negative"))

    boundary_ok = all(
        result.get("windows_runtime_certified") is False
        and result.get("external_windows_target_evidence_imported") is False
        and result.get("production_score_promotion_eligible") is False
        and result.get("production_score_mutation_authorized") is False
        for result in (good_result, six_result, eight_result, stale_result, future_result, packet_replay_result)
    )
    tests.append(_case("ingest_fixtures_never_cross_production_boundary", boundary_ok, group="authority-boundary"))
    return tests


def _cert_source(now: datetime) -> dict[str, Any]:
    return {
        "product": exporter.PRODUCT,
        "suite": "TARGET_MACHINE_CERTIFICATION",
        "verdict": exporter.SOURCE_VERDICT,
        "production_certification": exporter.SOURCE_CERTIFICATION,
        "generated_utc": now.isoformat(),
        "summary": {"stages_pass": 7, "stages_total": 7, "production_certified": True},
        "stages": {
            cid: {"pass": True, "detail": {"fixture": True, "case_id": cid}}
            for cid in REQUIRED_RUNTIME_CASE_IDS
        },
    }


def _exporter_and_runner_cases() -> list[dict[str, Any]]:
    now = datetime(2026, 8, 24, 13, 0, tzinfo=timezone.utc)
    tests: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="hms-v2575-exporter-fixtures-") as temp:
        root = Path(temp)
        source_path = root / "source.json"
        output_dir = root / "out"

        good = _cert_source(now)
        source_path.write_text(json.dumps(good, ensure_ascii=False), "utf-8")
        exported = exporter.export_reports(source_path, output_dir)
        exported_ids = [row["case_id"] for row in exported["files"]]
        rows = [runner._validate_case_report(cid, output_dir / f"{cid}.json") for cid in REQUIRED_RUNTIME_CASE_IDS]
        tests.extend([
            _case("exporter_exact_seven_control_exports", exported["verdict"] == "EXACT_SEVEN_CASE_REPORTS_EXPORTED" and len(exported["files"]) == 7,
                  group="exporter-control"),
            _case("exporter_preserves_canonical_case_ids", exported_ids == list(REQUIRED_RUNTIME_CASE_IDS), group="exporter-control"),
            _case("exporter_preserves_source_capture", exported.get("source_capture_utc") == now.isoformat(), group="provenance-control"),
            _case("runner_accepts_exporter_case_contract", all(not row["reasons"] for row in rows), group="provenance-control"),
            _case("runner_rows_share_one_source_hash", len({row["source_report_sha256"] for row in rows}) == 1 and next(iter({row["source_report_sha256"] for row in rows})) == exported["source_report_sha256"],
                  group="provenance-control"),
            _case("runner_rows_share_source_capture", {row["capture_utc"] for row in rows} == {exported["source_capture_utc"]}, group="provenance-control"),
            _case("exporter_never_auto_certifies_from_export", exported["windows_runtime_certified"] is False and exported["production_score_promotion_eligible"] is False,
                  group="authority-boundary"),
        ])

        def reject(name: str, mutate: Callable[[dict[str, Any]], None], reason: str) -> None:
            candidate = _cert_source(now)
            mutate(candidate)
            path = root / f"{name}.json"
            path.write_text(json.dumps(candidate, ensure_ascii=False), "utf-8")
            tests.append(_case(name, _expect_raises(lambda: exporter.export_reports(path, root / (name + "-out")), reason),
                               group="exporter-negative", detail=reason))

        reject("exporter_wrong_product_rejected", lambda x: x.__setitem__("product", "OTHER"), "SOURCE_PRODUCT_INVALID")
        reject("exporter_wrong_suite_rejected", lambda x: x.__setitem__("suite", "OTHER"), "SOURCE_SUITE_INVALID")
        reject("exporter_partial_verdict_rejected", lambda x: x.__setitem__("verdict", "TARGET_MACHINE_PARTIAL_EVIDENCE"), "SOURCE_NOT_FULLY_CERTIFIED")
        reject("exporter_missing_certification_rejected", lambda x: x.__setitem__("production_certification", ""), "SOURCE_PRODUCTION_CERTIFICATION_MISSING")
        reject("exporter_invalid_generated_time_rejected", lambda x: x.__setitem__("generated_utc", "not-a-time"), "SOURCE_GENERATED_UTC_INVALID")
        reject("exporter_pass_count_six_rejected", lambda x: x["summary"].__setitem__("stages_pass", 6), "SOURCE_STAGE_PASS_COUNT_NOT_7")
        reject("exporter_stage_total_mismatch_rejected", lambda x: x["summary"].__setitem__("stages_total", 8), "SOURCE_STAGE_TOTAL_NOT_7")
        reject("exporter_false_production_flag_rejected", lambda x: x["summary"].__setitem__("production_certified", False), "SOURCE_PRODUCTION_CERTIFIED_FLAG_NOT_TRUE")
        reject("exporter_failed_stage_rejected", lambda x: x["stages"]["quota"].__setitem__("pass", False), "SOURCE_STAGE_NOT_PASS:quota")
        reject("exporter_missing_stage_rejected", lambda x: x["stages"].pop("soak_24h"), "SOURCE_STAGE_MATRIX_NOT_EXACT_SEVEN")
        reject("exporter_unexpected_stage_rejected", lambda x: x["stages"].__setitem__("extra", {"pass": True}), "SOURCE_STAGE_MATRIX_NOT_EXACT_SEVEN")

        valid_case_path = output_dir / "host.json"
        valid_case = json.loads(valid_case_path.read_text("utf-8"))
        bad_case_time = dict(valid_case); bad_case_time["capture_utc"] = "not-a-time"
        bad_case_time_path = root / "bad-case-time.json"; bad_case_time_path.write_text(json.dumps(bad_case_time), "utf-8")
        bad_case_source = dict(valid_case); bad_case_source["source_verdict"] = "TARGET_MACHINE_PARTIAL_EVIDENCE"
        bad_case_source_path = root / "bad-case-source.json"; bad_case_source_path.write_text(json.dumps(bad_case_source), "utf-8")
        tests.extend([
            _case("runner_invalid_case_capture_rejected", "CASE_CAPTURE_UTC_INVALID" in runner._validate_case_report("host", bad_case_time_path)["reasons"], group="runner-negative"),
            _case("runner_nonproduction_source_verdict_rejected", "CASE_SOURCE_VERDICT_INVALID" in runner._validate_case_report("host", bad_case_source_path)["reasons"], group="runner-negative"),
        ])

        runner_source = Path(runner.__file__).read_text("utf-8")
        tests.extend([
            _case("runner_has_common_capture_mismatch_guard", "CASE_CAPTURE_UTC_MISMATCH" in runner_source, group="source-boundary"),
            _case("runner_has_common_source_hash_guard", "CASE_SOURCE_REPORT_SHA256_MISMATCH" in runner_source, group="source-boundary"),
            _case("runner_packet_uses_source_capture_not_packaging_now", '"capture_utc": source_capture_utc' in runner_source, group="source-boundary"),
            _case("runner_packet_binds_source_certification_hash", '"source_certification_report_sha256": source_report_sha256' in runner_source, group="source-boundary"),
        ])
    return tests


def synthetic_proof() -> dict[str, Any]:
    tests = [*_ingest_cases(), *_exporter_and_runner_cases()]
    failed = [test for test in tests if test["status"] != "PASS"]
    groups: dict[str, dict[str, int]] = {}
    for test in tests:
        bucket = groups.setdefault(test["group"], {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        bucket["pass" if test["status"] == "PASS" else "fail"] += 1
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "EXTERNAL_WINDOWS_EVIDENCE_ADVERSARIAL_FIXTURES",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests) - len(failed), "fail": len(failed), "total": len(tests)},
        "groups": groups,
        "tests": tests,
        "synthetic_fixture_only": True,
        "real_windows_evidence_read": False,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
    }


def main() -> int:
    result = synthetic_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
