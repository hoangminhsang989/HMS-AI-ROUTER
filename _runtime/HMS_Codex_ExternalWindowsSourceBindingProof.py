#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_ExternalWindowsCaseReportExporter as exporter
import HMS_Codex_ExternalWindowsEvidenceRunner as runner
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source(now: datetime) -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "edition": "CODEX_ONLY",
        "version": "25.53",
        "schema_version": 1,
        "suite": "TARGET_MACHINE_CERTIFICATION",
        "generated_utc": now.isoformat(),
        "verdict": exporter.SOURCE_VERDICT,
        "production_certification": exporter.SOURCE_CERTIFICATION,
        "summary": {
            "stages_pass": len(REQUIRED_RUNTIME_CASE_IDS),
            "stages_total": len(REQUIRED_RUNTIME_CASE_IDS),
            "production_certified": True,
        },
        "stages": {
            cid: {"pass": True, "detail": {"fixture": True, "case_id": cid}}
            for cid in REQUIRED_RUNTIME_CASE_IDS
        },
        "blockers": [],
    }


def synthetic_proof() -> dict[str, Any]:
    now = datetime(2026, 8, 24, 13, 0, tzinfo=timezone.utc)
    checks: dict[str, bool] = {}

    with tempfile.TemporaryDirectory(prefix="hms-v2575-source-binding-") as temp:
        root = Path(temp)
        source_path = root / "target-certification.json"
        out_dir = root / "cases"
        source_obj = _source(now)
        source_raw = (json.dumps(source_obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        source_path.write_bytes(source_raw)

        validated = exporter.validate_source_report(source_path)
        exported = exporter.export_reports(source_path, out_dir)
        runner_path, runner_validated, runner_error = runner._validate_source_path(str(source_path))
        rows = [runner._validate_case_report(cid, out_dir / f"{cid}.json") for cid in REQUIRED_RUNTIME_CASE_IDS]

        expected_sha = _sha(source_raw)
        expected_capture = now.isoformat()
        row_sources = {row.get("source_report_sha256") for row in rows}
        row_captures = {row.get("capture_utc") for row in rows}

        checks.update({
            "source_validator_hashes_exact_selected_bytes": validated.get("source_report_sha256") == expected_sha,
            "exporter_binds_exact_source_sha": exported.get("source_report_sha256") == expected_sha,
            "exporter_preserves_source_capture": exported.get("source_capture_utc") == expected_capture,
            "runner_source_validator_accepts_same_file": runner_error == "" and runner_path == source_path and runner_validated.get("source_report_sha256") == expected_sha,
            "all_case_reports_pass_runner_contract": all(not row.get("reasons") for row in rows),
            "all_case_reports_bind_same_exact_source_sha": row_sources == {expected_sha},
            "all_case_reports_bind_same_source_capture": row_captures == {expected_capture},
        })

        mutated = json.loads(json.dumps(source_obj))
        mutated["stages"]["host"]["detail"]["post_export_mutation"] = True
        mutated_raw = (json.dumps(mutated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        source_path.write_bytes(mutated_raw)
        mutated_validation = exporter.validate_source_report(source_path)
        mutated_sha = mutated_validation.get("source_report_sha256")

        checks.update({
            "post_export_source_mutation_changes_digest": mutated_sha == _sha(mutated_raw) and mutated_sha != expected_sha,
            "old_case_reports_do_not_match_mutated_source": row_sources != {mutated_sha},
        })

        partial_path = root / "partial.json"
        partial = _source(now); partial["verdict"] = "TARGET_MACHINE_PARTIAL_EVIDENCE"; partial["production_certification"] = "NOT_CLAIMED"
        partial_path.write_text(json.dumps(partial, ensure_ascii=False), "utf-8")
        _, partial_validation, partial_error = runner._validate_source_path(str(partial_path))
        checks.update({
            "runner_rejects_nonproduction_source_report": partial_validation == {} and partial_error.startswith("SOURCE_CERTIFICATION_REPORT_INVALID:"),
            "runner_rejects_missing_source_report": runner._validate_source_path(str(root / "missing.json"))[2] == "SOURCE_CERTIFICATION_REPORT_MISSING",
        })

        runner_src = Path(runner.__file__).read_text("utf-8")
        checks.update({
            "packet_builder_requires_source_certification_cli": '--source-certification-report' in runner_src,
            "packet_builder_revalidates_source_after_preflight": 'SOURCE_CERTIFICATION_REPORT_CHANGED_AFTER_PREFLIGHT' in runner_src,
            "packet_builder_compares_case_capture_to_selected_source": 'capture_values != {source_capture_utc}' in runner_src,
            "packet_builder_compares_case_sha_to_selected_source": 'source_values != {source_report_sha256}' in runner_src,
            "packet_capture_comes_from_selected_source": '"capture_utc": source_capture_utc' in runner_src,
            "signed_packet_binds_selected_source_digest": '"source_certification_report_sha256": source_report_sha256' in runner_src,
        })

    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "EXTERNAL_WINDOWS_SOURCE_BINDING_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
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
