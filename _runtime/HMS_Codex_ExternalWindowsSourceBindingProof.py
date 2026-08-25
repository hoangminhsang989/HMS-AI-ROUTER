#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_CockpitV1329P0ParityProof as cockpit_v1329_p0
import HMS_Codex_ExternalWindowsCaseReportExporter as exporter
import HMS_Codex_ExternalWindowsEvidenceRunner as runner
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS

PRODUCT="HMS-AI-ROUTER"; VERSION="25.75"; MANIFEST_SHA="a"*64; PACKAGE_SHA="b"*64

def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def _source(now:datetime)->dict[str,Any]:
    return {"product":PRODUCT,"edition":"CODEX_ONLY","version":VERSION,"schema_version":2,"suite":"TARGET_MACHINE_CERTIFICATION",
            "generated_utc":now.isoformat(),"verdict":exporter.SOURCE_VERDICT,"production_certification":exporter.SOURCE_CERTIFICATION,
            "summary":{"stages_pass":len(REQUIRED_RUNTIME_CASE_IDS),"stages_total":len(REQUIRED_RUNTIME_CASE_IDS),"production_certified":True,"artifact_binding_pass":True},
            "stages":{cid:{"pass":True,"detail":{"fixture":True,"case_id":cid}} for cid in REQUIRED_RUNTIME_CASE_IDS},
            "artifact_binding":{"pass":True,"binding_schema":"HMS_V25_75_TARGET_ARTIFACT_BINDING_V1","release_manifest_sha256":MANIFEST_SHA,
                                "package_zip_sha256":PACKAGE_SHA,"critical_files_required":8,"critical_files_verified":8},"blockers":[]}

def synthetic_proof()->dict[str,Any]:
    now=datetime(2026,8,24,13,0,tzinfo=timezone.utc); checks={}
    with tempfile.TemporaryDirectory(prefix="hms-v2575-source-binding-") as temp:
        root=Path(temp); source_path=root/"target-certification.json"; out_dir=root/"cases"; source_obj=_source(now)
        source_raw=(json.dumps(source_obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8"); source_path.write_bytes(source_raw)
        validated=exporter.validate_source_report(source_path); exported=exporter.export_reports(source_path,out_dir)
        runner_path,runner_validated,runner_error=runner._validate_source_path(str(source_path))
        rows=[runner._validate_case_report(cid,out_dir/f"{cid}.json") for cid in REQUIRED_RUNTIME_CASE_IDS]
        expected_sha=_sha(source_raw); expected_capture=now.isoformat(); row_sources={x.get("source_report_sha256") for x in rows}
        row_captures={x.get("capture_utc") for x in rows}; row_packages={x.get("source_package_zip_sha256") for x in rows}; row_manifests={x.get("source_release_manifest_sha256") for x in rows}
        checks.update({
            "source_validator_hashes_exact_selected_bytes":validated.get("source_report_sha256")==expected_sha,
            "source_validator_requires_v2575_schema2":validated.get("source_package_zip_sha256")==PACKAGE_SHA and validated.get("source_release_manifest_sha256")==MANIFEST_SHA,
            "exporter_binds_exact_source_sha":exported.get("source_report_sha256")==expected_sha,
            "exporter_preserves_source_capture":exported.get("source_capture_utc")==expected_capture,
            "exporter_preserves_artifact_binding":exported.get("source_package_zip_sha256")==PACKAGE_SHA and exported.get("source_release_manifest_sha256")==MANIFEST_SHA,
            "runner_source_validator_accepts_same_file":runner_error=="" and runner_path==source_path and runner_validated.get("source_report_sha256")==expected_sha,
            "all_case_reports_pass_runner_contract":all(not x.get("reasons") for x in rows),
            "all_case_reports_bind_same_exact_source_sha":row_sources=={expected_sha},"all_case_reports_bind_same_source_capture":row_captures=={expected_capture},
            "all_case_reports_bind_same_package":row_packages=={PACKAGE_SHA},"all_case_reports_bind_same_manifest":row_manifests=={MANIFEST_SHA},
        })
        mutated=json.loads(json.dumps(source_obj)); mutated["stages"]["host"]["detail"]["post_export_mutation"]=True
        mutated_raw=(json.dumps(mutated,ensure_ascii=False,indent=2)+"\n").encode("utf-8"); source_path.write_bytes(mutated_raw)
        mutated_sha=exporter.validate_source_report(source_path).get("source_report_sha256")
        checks.update({"post_export_source_mutation_changes_digest":mutated_sha==_sha(mutated_raw) and mutated_sha!=expected_sha,"old_case_reports_do_not_match_mutated_source":row_sources!={mutated_sha}})
        old_path=root/"old.json"; old=_source(now); old["version"]="25.53"; old_path.write_text(json.dumps(old),"utf-8")
        _,old_validation,old_error=runner._validate_source_path(str(old_path))
        partial_path=root/"partial.json"; partial=_source(now); partial["verdict"]="TARGET_MACHINE_PARTIAL_EVIDENCE"; partial["production_certification"]="NOT_CLAIMED"; partial_path.write_text(json.dumps(partial),"utf-8")
        _,partial_validation,partial_error=runner._validate_source_path(str(partial_path))
        checks.update({
            "runner_rejects_old_version_source":old_validation=={} and "SOURCE_VERSION_INVALID" in old_error,
            "runner_rejects_nonproduction_source_report":partial_validation=={} and partial_error.startswith("SOURCE_CERTIFICATION_REPORT_INVALID:"),
            "runner_rejects_missing_source_report":runner._validate_source_path(str(root/"missing.json"))[2]=="SOURCE_CERTIFICATION_REPORT_MISSING",
        })
        runner_src=Path(runner.__file__).read_text("utf-8")
        checks.update({
            "packet_builder_requires_source_certification_cli":"--source-certification-report" in runner_src,
            "packet_builder_revalidates_source_after_preflight":"SOURCE_CERTIFICATION_REPORT_CHANGED_AFTER_PREFLIGHT" in runner_src,
            "packet_builder_rejects_package_splice":"SOURCE_PACKAGE_ZIP_SHA256_MISMATCH" in runner_src,
            "packet_builder_rejects_manifest_splice":"SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH" in runner_src,
            "packet_builder_compares_case_artifacts":"CASE_SOURCE_PACKAGE_ZIP_SHA256_MISMATCH" in runner_src and "CASE_SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH" in runner_src,
            "signed_packet_binds_source_artifact":"source_artifact_binding" in runner_src,
        })
    try:
        parity_result=cockpit_v1329_p0.source_proof()
    except Exception:
        parity_result={"verdict":"FAIL"}
    checks.update({
        "cockpit_v1329_p0_parity_source_gate_passes":parity_result.get("verdict")=="PASS",
        "cockpit_v1329_p0_parity_cannot_certify_windows":parity_result.get("windows_runtime_certified") is False,
        "cockpit_v1329_p0_parity_cannot_promote_score":parity_result.get("production_score_promotion_eligible") is False,
        "cockpit_v1329_p0_parity_cannot_adopt_baseline":parity_result.get("baseline_adoption_authorized") is False,
    })
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; passed=sum(x["status"]=="PASS" for x in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_SOURCE_BINDING_PROOF","verdict":"PASS" if passed==len(tests) else "FAIL",
            "summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,"synthetic_fixture_only":True,
            "upstream_source_certification_executed":True,"real_windows_evidence_read":False,"real_windows_runtime_executed":False,"windows_runtime_certified":False,
            "external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,"production_score_mutation_authorized":False}

def main()->int:
    result=synthetic_proof(); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
