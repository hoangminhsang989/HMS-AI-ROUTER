#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, re, tempfile
from datetime import datetime, timezone
from pathlib import Path

from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS, validate_case_ids

VERSION="25.75"; PRODUCT="HMS-AI-ROUTER"; SOURCE_SCHEMA_VERSION=2
SOURCE_VERDICT="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"
SOURCE_CERTIFICATION="TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK"
HEX64=re.compile(r"^[0-9a-f]{64}$")


def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _utc(value)->str:
    try:
        dt=datetime.fromisoformat(str(value or "").replace("Z","+00:00"))
        if dt.tzinfo is None:return ""
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError,ValueError):return ""


def _source_reasons(obj:dict)->list[str]:
    reasons=[]; stages=obj.get("stages") if isinstance(obj.get("stages"),dict) else {}
    summary=obj.get("summary") if isinstance(obj.get("summary"),dict) else {}
    binding=obj.get("artifact_binding") if isinstance(obj.get("artifact_binding"),dict) else {}
    matrix=validate_case_ids(stages.keys()); source_capture=_utc(obj.get("generated_utc"))
    manifest_sha=str(binding.get("release_manifest_sha256") or "").lower(); package_sha=str(binding.get("package_zip_sha256") or "").lower()
    if obj.get("product")!=PRODUCT: reasons.append("SOURCE_PRODUCT_INVALID")
    if str(obj.get("version") or "")!=VERSION: reasons.append("SOURCE_VERSION_INVALID")
    if int(obj.get("schema_version") or 0)!=SOURCE_SCHEMA_VERSION: reasons.append("SOURCE_SCHEMA_VERSION_INVALID")
    if obj.get("suite")!="TARGET_MACHINE_CERTIFICATION": reasons.append("SOURCE_SUITE_INVALID")
    if obj.get("verdict")!=SOURCE_VERDICT: reasons.append("SOURCE_NOT_FULLY_CERTIFIED")
    if obj.get("production_certification")!=SOURCE_CERTIFICATION: reasons.append("SOURCE_PRODUCTION_CERTIFICATION_MISSING")
    if not source_capture: reasons.append("SOURCE_GENERATED_UTC_INVALID")
    if not matrix["valid"]: reasons.append("SOURCE_STAGE_MATRIX_NOT_EXACT_SEVEN")
    if int(summary.get("stages_pass") or 0)!=len(REQUIRED_RUNTIME_CASE_IDS): reasons.append("SOURCE_STAGE_PASS_COUNT_NOT_7")
    if int(summary.get("stages_total") or 0)!=len(REQUIRED_RUNTIME_CASE_IDS): reasons.append("SOURCE_STAGE_TOTAL_NOT_7")
    if summary.get("production_certified") is not True: reasons.append("SOURCE_PRODUCTION_CERTIFIED_FLAG_NOT_TRUE")
    if summary.get("artifact_binding_pass") is not True: reasons.append("SOURCE_ARTIFACT_BINDING_SUMMARY_NOT_TRUE")
    if binding.get("pass") is not True: reasons.append("SOURCE_ARTIFACT_BINDING_NOT_PASS")
    if binding.get("binding_schema")!="HMS_V25_75_TARGET_ARTIFACT_BINDING_V1": reasons.append("SOURCE_ARTIFACT_BINDING_SCHEMA_INVALID")
    if not HEX64.fullmatch(manifest_sha): reasons.append("SOURCE_RELEASE_MANIFEST_SHA256_INVALID")
    if not HEX64.fullmatch(package_sha): reasons.append("SOURCE_PACKAGE_ZIP_SHA256_INVALID")
    if int(binding.get("critical_files_required") or 0)<=0 or int(binding.get("critical_files_verified") or 0)!=int(binding.get("critical_files_required") or 0):
        reasons.append("SOURCE_ARTIFACT_CRITICAL_FILES_NOT_VERIFIED")
    for cid in REQUIRED_RUNTIME_CASE_IDS:
        if not isinstance(stages.get(cid),dict) or stages[cid].get("pass") is not True: reasons.append("SOURCE_STAGE_NOT_PASS:"+cid)
    return sorted(set(reasons))


def validate_source_report(source:Path)->dict:
    raw=source.read_bytes(); obj=json.loads(raw.decode("utf-8-sig")); reasons=_source_reasons(obj)
    if reasons: raise ValueError(",".join(reasons))
    binding=obj["artifact_binding"]
    return {
        "source_report_sha256":_sha(raw), "source_capture_utc":_utc(obj.get("generated_utc")), "source_object":obj,
        "source_release_manifest_sha256":str(binding["release_manifest_sha256"]).lower(),
        "source_package_zip_sha256":str(binding["package_zip_sha256"]).lower(),
        "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS), "windows_runtime_certified":False,
        "production_score_promotion_eligible":False,
    }


def export_reports(source:Path,output_dir:Path)->dict:
    validated=validate_source_report(source); obj=validated["source_object"]
    source_sha=validated["source_report_sha256"]; source_capture=validated["source_capture_utc"]
    manifest_sha=validated["source_release_manifest_sha256"]; package_sha=validated["source_package_zip_sha256"]
    stages=obj["stages"]; output_dir.mkdir(parents=True,exist_ok=True); files=[]
    for cid in REQUIRED_RUNTIME_CASE_IDS:
        case={"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_RUNTIME_CASE_REPORT",
              "case_id":cid,"status":"PASS","synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
              "capture_utc":source_capture,"source_suite":"TARGET_MACHINE_CERTIFICATION","source_report_sha256":source_sha,
              "source_release_manifest_sha256":manifest_sha,"source_package_zip_sha256":package_sha,
              "source_verdict":obj.get("verdict"),"source_production_certification":obj.get("production_certification"),
              "detail":stages[cid].get("detail") or {},
              "claim_boundary":"Derived only from an exact v25.75 schema-2 artifact-bound 7/7 target-machine certification report; no stage, version, timestamp or artifact identity is upgraded or synthesized."}
        path=output_dir/(cid+".json"); path.write_text(json.dumps(case,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        files.append({"case_id":cid,"path":str(path),"sha256":_sha(path.read_bytes())})
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_CASE_REPORT_EXPORTER",
            "verdict":"EXACT_SEVEN_CASE_REPORTS_EXPORTED","source_report_sha256":source_sha,"source_capture_utc":source_capture,
            "source_release_manifest_sha256":manifest_sha,"source_package_zip_sha256":package_sha,"files":files,
            "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"synthetic_evidence_created":False,
            "windows_runtime_certified":False,"production_score_promotion_eligible":False}


def synthetic_proof()->dict:
    stages={cid:{"pass":True,"detail":{"fixture":True}} for cid in REQUIRED_RUNTIME_CASE_IDS}; now=datetime.now(timezone.utc).isoformat()
    binding={"pass":True,"binding_schema":"HMS_V25_75_TARGET_ARTIFACT_BINDING_V1","release_manifest_sha256":"a"*64,
             "package_zip_sha256":"b"*64,"critical_files_required":8,"critical_files_verified":8}
    good={"product":PRODUCT,"version":VERSION,"schema_version":SOURCE_SCHEMA_VERSION,"suite":"TARGET_MACHINE_CERTIFICATION",
          "verdict":SOURCE_VERDICT,"production_certification":SOURCE_CERTIFICATION,"generated_utc":now,
          "summary":{"stages_pass":7,"stages_total":7,"production_certified":True,"artifact_binding_pass":True},
          "stages":stages,"artifact_binding":binding}
    old=json.loads(json.dumps(good)); old["version"]="25.53"
    bad_schema=json.loads(json.dumps(good)); bad_schema["schema_version"]=1
    bad_binding=json.loads(json.dumps(good)); bad_binding["artifact_binding"]["pass"]=False
    bad_digest=json.loads(json.dumps(good)); bad_digest["artifact_binding"]["package_zip_sha256"]="bad"
    bad_total=json.loads(json.dumps(good)); bad_total["summary"]["stages_total"]=8
    bad_flag=json.loads(json.dumps(good)); bad_flag["summary"]["production_certified"]=False
    bad_time=json.loads(json.dumps(good)); bad_time["generated_utc"]="not-a-time"
    with tempfile.TemporaryDirectory(prefix="hms-v2575-source-bind-") as temp:
        path=Path(temp)/"source.json"; raw=json.dumps(good,ensure_ascii=False,sort_keys=True).encode("utf-8"); path.write_bytes(raw)
        validated=validate_source_report(path)
        checks={
            "exact_stage_contract":validate_case_ids(stages.keys())["valid"],
            "old_source_version_rejected":"SOURCE_VERSION_INVALID" in _source_reasons(old),
            "old_source_schema_rejected":"SOURCE_SCHEMA_VERSION_INVALID" in _source_reasons(bad_schema),
            "artifact_binding_required":"SOURCE_ARTIFACT_BINDING_NOT_PASS" in _source_reasons(bad_binding),
            "artifact_digest_required":"SOURCE_PACKAGE_ZIP_SHA256_INVALID" in _source_reasons(bad_digest),
            "contradictory_stage_total_rejected":"SOURCE_STAGE_TOTAL_NOT_7" in _source_reasons(bad_total),
            "contradictory_production_flag_rejected":"SOURCE_PRODUCTION_CERTIFIED_FLAG_NOT_TRUE" in _source_reasons(bad_flag),
            "invalid_source_capture_rejected":"SOURCE_GENERATED_UTC_INVALID" in _source_reasons(bad_time),
            "source_validator_hashes_exact_bytes":validated["source_report_sha256"]==_sha(raw),
            "source_validator_preserves_artifact_digests":validated["source_release_manifest_sha256"]=="a"*64 and validated["source_package_zip_sha256"]=="b"*64,
            "source_validator_grants_no_authority":validated["windows_runtime_certified"] is False and validated["production_score_promotion_eligible"] is False,
        }
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_CASE_REPORT_EXPORTER_PROOF",
            "verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},
            "tests":tests,"synthetic_fixture_only":True,"windows_runtime_certified":False,"production_score_promotion_eligible":False}


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--proof",action="store_true"); ap.add_argument("--source"); ap.add_argument("--output-dir")
    a=ap.parse_args()
    if a.proof: out=synthetic_proof(); code=0 if out["verdict"]=="PASS" else 2
    else:
        if not a.source or not a.output_dir: ap.error("--source and --output-dir required")
        try: out=export_reports(Path(a.source),Path(a.output_dir)); code=0
        except Exception as exc:
            out={"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_CASE_REPORT_EXPORTER","verdict":"BLOCKED_FAIL_CLOSED",
                 "error":type(exc).__name__,"detail":str(exc),"synthetic_evidence_created":False,"windows_runtime_certified":False,
                 "production_score_promotion_eligible":False}; code=2
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code

if __name__=="__main__": raise SystemExit(main())
