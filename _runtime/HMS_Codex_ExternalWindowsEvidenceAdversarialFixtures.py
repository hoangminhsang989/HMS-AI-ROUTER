#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import HMS_Codex_ExternalWindowsCaseReportExporter as exporter
import HMS_Codex_ExternalWindowsEvidenceRunner as runner
import HMS_Codex_ExternalWindowsReviewPacketIngest as ingest
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS

PRODUCT="HMS-AI-ROUTER"; VERSION="25.75"; PACKAGE_SHA="a"*64; MANIFEST_SHA="b"*64

def _sha(text:str)->str:return hashlib.sha256(text.encode("utf-8")).hexdigest()
def _case(name:str,ok:bool,*,group:str,detail:str="")->dict[str,Any]:return {"name":name,"group":group,"status":"PASS" if ok else "FAIL","detail":detail}
def _expect_raises(fn:Callable[[],Any],contains:str)->bool:
    try:fn()
    except Exception as exc:return contains in str(exc)
    return False

def _base_packet(now:datetime,*,seed:str="base",case_ids=None)->dict[str,Any]:
    ids=list(case_ids if case_ids is not None else REQUIRED_RUNTIME_CASE_IDS); source_ref=_sha("source-certification:"+seed)
    return {"source_classification":ingest.SOURCE_CLASSIFICATION,"synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
            "package_zip_sha256":PACKAGE_SHA,"release_manifest_sha256":MANIFEST_SHA,"source_certification_report_sha256":source_ref,
            "source_artifact_binding":{"binding_schema":ingest.ARTIFACT_BINDING_SCHEMA,"package_zip_sha256":PACKAGE_SHA,"release_manifest_sha256":MANIFEST_SHA},
            "cockpit_baseline":ingest.COCKPIT_BASELINE,"capture_utc":now.isoformat(),"nonce":f"nonce-{seed}-01234567","run_id":f"run-{seed}-0123456789",
            "report_id":f"report-{seed}-01234567","case_results":[{"case_id":cid,"status":"PASS","report_sha256":_sha(f"{seed}:{i}:{cid}"),
                "source_report_sha256":source_ref,"source_package_zip_sha256":PACKAGE_SHA,"source_release_manifest_sha256":MANIFEST_SHA} for i,cid in enumerate(ids)]}

def _signed(base):
    p=synthetic_signed_packet(base); p["signer"].pop("synthetic_fixture",None); return p

def _verify(packet,*,now,raw,seen=None,expected_package=PACKAGE_SHA,expected_manifest=MANIFEST_SHA,expected_trust=None):
    trust=expected_trust if expected_trust is not None else str((packet.get("trust_snapshot") or {}).get("trust_snapshot_sha256") or "")
    return ingest.verify_packet(packet,raw_packet_sha256=raw,expected_package_sha256=expected_package,expected_manifest_sha256=expected_manifest,
        expected_trust_snapshot_sha256=trust,current_cockpit_baseline=ingest.COCKPIT_BASELINE,seen=seen,now=now)

def _ingest_cases()->list[dict[str,Any]]:
    now=datetime(2026,8,24,13,0,tzinfo=timezone.utc); tests=[]
    def check(name,mutate,reason,*,verify_kwargs=None):
        b=_base_packet(now,seed=name); mutate(b); result=_verify(_signed(b),now=now,raw=_sha("raw:"+name),**(verify_kwargs or {})); tests.append(_case(name,not result["real_packet_verified"] and reason in result["reasons"],group="ingest-negative",detail=reason))
    good=_signed(_base_packet(now,seed="good")); good_result=_verify(good,now=now,raw=_sha("raw:good")); tests.append(_case("exact_seven_artifact_bound_control_verifies",good_result["real_packet_verified"],group="ingest-control"))
    six=_signed(_base_packet(now,seed="six",case_ids=REQUIRED_RUNTIME_CASE_IDS[:-1])); six_result=_verify(six,now=now,raw=_sha("raw:six")); tests.extend([_case("six_case_matrix_rejected","RUNTIME_CASE_MATRIX_NOT_7" in six_result["reasons"],group="ingest-negative"),_case("six_case_missing_required_reported","RUNTIME_CASE_MATRIX_MISSING_REQUIRED" in six_result["reasons"],group="ingest-negative")])
    eight=_signed(_base_packet(now,seed="eight",case_ids=list(REQUIRED_RUNTIME_CASE_IDS)+["unexpected_case"])); eight_result=_verify(eight,now=now,raw=_sha("raw:eight")); tests.extend([_case("eight_case_matrix_rejected","RUNTIME_CASE_MATRIX_NOT_7" in eight_result["reasons"],group="ingest-negative"),_case("unexpected_case_reported","RUNTIME_CASE_MATRIX_UNEXPECTED_ID" in eight_result["reasons"],group="ingest-negative")])
    check("failed_case_status_rejected",lambda b:b["case_results"][3].__setitem__("status","FAIL"),"CASE_3_NOT_PASS")
    check("wrong_target_os_rejected",lambda b:b.__setitem__("target_os","Linux"),"WINDOWS_TARGET_REQUIRED")
    check("local_only_rejected",lambda b:b.__setitem__("local_only",True),"LOCAL_ONLY_EVIDENCE_REJECTED")
    check("synthetic_flag_rejected",lambda b:b.__setitem__("synthetic",True),"SYNTHETIC_EVIDENCE_REJECTED")
    check("missing_source_certification_hash_rejected",lambda b:b.pop("source_certification_report_sha256"),"SOURCE_CERTIFICATION_REPORT_SHA256_REQUIRED")
    check("missing_artifact_binding_rejected",lambda b:b.pop("source_artifact_binding"),"SOURCE_ARTIFACT_BINDING_SCHEMA_REQUIRED")
    check("swapped_artifact_package_rejected",lambda b:b["source_artifact_binding"].__setitem__("package_zip_sha256","f"*64),"SOURCE_ARTIFACT_PACKAGE_SHA256_MISMATCH")
    check("swapped_artifact_manifest_rejected",lambda b:b["source_artifact_binding"].__setitem__("release_manifest_sha256","f"*64),"SOURCE_ARTIFACT_MANIFEST_SHA256_MISMATCH")
    check("invalid_case_source_hash_rejected",lambda b:b["case_results"][0].__setitem__("source_report_sha256","bad"),"CASE_0_SOURCE_REPORT_SHA256_INVALID")
    check("case_source_mismatch_rejected",lambda b:b["case_results"][0].__setitem__("source_report_sha256","d"*64),"RUNTIME_CASE_SOURCE_REPORT_MISMATCH")
    check("case_package_binding_mismatch_rejected",lambda b:b["case_results"][0].__setitem__("source_package_zip_sha256","d"*64),"RUNTIME_CASE_SOURCE_PACKAGE_MISMATCH")
    check("case_manifest_binding_mismatch_rejected",lambda b:b["case_results"][0].__setitem__("source_release_manifest_sha256","d"*64),"RUNTIME_CASE_SOURCE_MANIFEST_MISMATCH")
    check("package_digest_mismatch_rejected",lambda b:None,"PACKAGE_ZIP_SHA256_MISMATCH",verify_kwargs={"expected_package":"c"*64})
    check("manifest_digest_mismatch_rejected",lambda b:None,"RELEASE_MANIFEST_SHA256_MISMATCH",verify_kwargs={"expected_manifest":"d"*64})
    check("duplicate_case_id_rejected",lambda b:b["case_results"][1].__setitem__("case_id",b["case_results"][0]["case_id"]),"DUPLICATE_RUNTIME_CASE_ID")
    def duplicate_digest(b):b["case_results"][1]["report_sha256"]=b["case_results"][0]["report_sha256"]
    check("duplicate_runtime_report_digest_rejected",duplicate_digest,"DUPLICATE_RUNTIME_REPORT_DIGEST")
    stale=_signed(_base_packet(now-timedelta(hours=73),seed="stale")); sr=_verify(stale,now=now,raw=_sha("raw:stale")); tests.append(_case("stale_capture_rejected","EVIDENCE_STALE" in sr["reasons"],group="ingest-negative"))
    future=_signed(_base_packet(now+timedelta(minutes=6),seed="future")); fr=_verify(future,now=now,raw=_sha("raw:future")); tests.append(_case("future_capture_rejected","CAPTURE_TIME_IN_FUTURE" in fr["reasons"],group="ingest-negative"))
    for field,seen_key,reason in (("nonce","nonces","NONCE_REPLAY"),("run_id","run_ids","RUN_ID_REPLAY"),("report_id","report_ids","REPORT_ID_REPLAY")):
        p=_signed(_base_packet(now,seed="replay-"+field)); r=_verify(p,now=now,raw=_sha("raw:replay:"+field),seen={seen_key:[p[field]]}); tests.append(_case(field+"_replay_rejected",reason in r["reasons"],group="ingest-replay"))
    rp=_signed(_base_packet(now,seed="packet-replay")); raw=_sha("raw:packet-replay"); rr=_verify(rp,now=now,raw=raw,seen={"packet_digests":[raw]}); tests.append(_case("packet_digest_replay_rejected","DUPLICATE_PACKET_DIGEST" in rr["reasons"],group="ingest-replay"))
    old=_base_packet(now,seed="baseline"); old["cockpit_baseline"]="1.3.27"; dr=_verify(_signed(old),now=now,raw=_sha("raw:baseline")); tests.append(_case("baseline_drift_rejected","COCKPIT_BASELINE_CHANGED_OR_STALE" in dr["reasons"],group="ingest-negative"))
    boundary=all(x.get("windows_runtime_certified") is False and x.get("external_windows_target_evidence_imported") is False and x.get("production_score_promotion_eligible") is False for x in (good_result,six_result,eight_result,sr,fr,rr)); tests.append(_case("fixtures_never_cross_production_boundary",boundary,group="authority-boundary")); return tests

def _cert_source(now):
    return {"product":exporter.PRODUCT,"version":VERSION,"schema_version":2,"suite":"TARGET_MACHINE_CERTIFICATION","verdict":exporter.SOURCE_VERDICT,
            "production_certification":exporter.SOURCE_CERTIFICATION,"generated_utc":now.isoformat(),"summary":{"stages_pass":7,"stages_total":7,"production_certified":True,"artifact_binding_pass":True},
            "stages":{cid:{"pass":True,"detail":{"fixture":True,"case_id":cid}} for cid in REQUIRED_RUNTIME_CASE_IDS},
            "artifact_binding":{"pass":True,"binding_schema":ingest.ARTIFACT_BINDING_SCHEMA,"release_manifest_sha256":MANIFEST_SHA,"package_zip_sha256":PACKAGE_SHA,"critical_files_required":8,"critical_files_verified":8}}

def _exporter_and_runner_cases()->list[dict[str,Any]]:
    now=datetime(2026,8,24,13,0,tzinfo=timezone.utc); tests=[]
    with tempfile.TemporaryDirectory(prefix="hms-v2575-exporter-fixtures-") as temp:
        root=Path(temp); source=root/"source.json"; out=root/"out"; good=_cert_source(now); source.write_text(json.dumps(good),"utf-8"); exported=exporter.export_reports(source,out)
        rows=[runner._validate_case_report(cid,out/f"{cid}.json") for cid in REQUIRED_RUNTIME_CASE_IDS]
        tests.extend([_case("exporter_exact_seven_control_exports",len(exported["files"])==7,group="exporter-control"),_case("exporter_preserves_source_capture",exported["source_capture_utc"]==now.isoformat(),group="provenance-control"),
                      _case("exporter_preserves_package_binding",exported["source_package_zip_sha256"]==PACKAGE_SHA,group="provenance-control"),_case("exporter_preserves_manifest_binding",exported["source_release_manifest_sha256"]==MANIFEST_SHA,group="provenance-control"),
                      _case("runner_accepts_exporter_case_contract",all(not x["reasons"] for x in rows),group="provenance-control"),_case("runner_rows_share_package",{x["source_package_zip_sha256"] for x in rows}=={PACKAGE_SHA},group="provenance-control"),
                      _case("runner_rows_share_manifest",{x["source_release_manifest_sha256"] for x in rows}=={MANIFEST_SHA},group="provenance-control")])
        def reject(name,mutate,reason):
            c=_cert_source(now); mutate(c); p=root/(name+".json"); p.write_text(json.dumps(c),"utf-8"); tests.append(_case(name,_expect_raises(lambda:exporter.export_reports(p,root/(name+"-out")),reason),group="exporter-negative",detail=reason))
        reject("exporter_old_version_rejected",lambda x:x.__setitem__("version","25.53"),"SOURCE_VERSION_INVALID")
        reject("exporter_old_schema_rejected",lambda x:x.__setitem__("schema_version",1),"SOURCE_SCHEMA_VERSION_INVALID")
        reject("exporter_artifact_binding_false_rejected",lambda x:x["artifact_binding"].__setitem__("pass",False),"SOURCE_ARTIFACT_BINDING_NOT_PASS")
        reject("exporter_package_digest_invalid_rejected",lambda x:x["artifact_binding"].__setitem__("package_zip_sha256","bad"),"SOURCE_PACKAGE_ZIP_SHA256_INVALID")
        reject("exporter_manifest_digest_invalid_rejected",lambda x:x["artifact_binding"].__setitem__("release_manifest_sha256","bad"),"SOURCE_RELEASE_MANIFEST_SHA256_INVALID")
        reject("exporter_stage_total_mismatch_rejected",lambda x:x["summary"].__setitem__("stages_total",8),"SOURCE_STAGE_TOTAL_NOT_7")
        reject("exporter_failed_stage_rejected",lambda x:x["stages"]["quota"].__setitem__("pass",False),"SOURCE_STAGE_NOT_PASS:quota")
        src=Path(runner.__file__).read_text("utf-8"); tests.extend([_case("runner_has_package_splice_guard","SOURCE_PACKAGE_ZIP_SHA256_MISMATCH" in src,group="source-boundary"),_case("runner_has_manifest_splice_guard","SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH" in src,group="source-boundary"),_case("runner_signed_packet_binds_artifact","source_artifact_binding" in src,group="source-boundary")])
    return tests

def synthetic_proof()->dict[str,Any]:
    tests=[*_ingest_cases(),*_exporter_and_runner_cases()]; failed=[x for x in tests if x["status"]!="PASS"]; groups={}
    for t in tests:
        b=groups.setdefault(t["group"],{"pass":0,"fail":0,"total":0}); b["total"]+=1; b["pass" if t["status"]=="PASS" else "fail"]+=1
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_ADVERSARIAL_FIXTURES","verdict":"PASS" if not failed else "FAIL","summary":{"pass":len(tests)-len(failed),"fail":len(failed),"total":len(tests)},"groups":groups,"tests":tests,"synthetic_fixture_only":True,"real_windows_evidence_read":False,"real_windows_runtime_executed":False,"windows_runtime_certified":False,"external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,"production_score_mutation_authorized":False}
def main()->int:
    r=synthetic_proof(); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if r["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
