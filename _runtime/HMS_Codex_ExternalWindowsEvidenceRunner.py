#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, importlib.util, json, platform, re, secrets, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_WindowsAttestationSigner as attestation_signer
import HMS_Codex_ExternalWindowsCertificateSigner as external_certificate_signer
import HMS_Codex_ExternalWindowsCertificatePreflight as certificate_preflight
import HMS_Codex_ExternalWindowsCaseReportExporter as case_exporter
from HMS_Codex_ExternalWindowsSignerTrustContract import signing_payload, validate_trust_snapshot
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS, validate_case_ids
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, SOURCE_CLASSIFICATION, verify_packet

VERSION="25.75"; THUMBPRINT=re.compile(r"^[0-9A-Fa-f]{20,128}$"); HEX64=re.compile(r"^[0-9a-f]{64}$")
DEFAULT_SIGN_SCRIPT=Path(__file__).resolve().with_name("HMS_Sign_Digest_With_Certificate.ps1")
DEFAULT_INSPECT_SCRIPT=Path(__file__).resolve().with_name("HMS_Inspect_Evidence_Certificate.ps1")
CASE_SOURCE_SUITE="TARGET_MACHINE_CERTIFICATION"; CASE_SOURCE_VERDICT="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"
CASE_SOURCE_CERTIFICATION="TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK"
REASON_VI={
    "WINDOWS_TARGET_REQUIRED":"Phải chạy trên máy Windows đích.","CODEX_CLI_NOT_FOUND":"Không tìm thấy Codex CLI trên PATH hoặc đường dẫn --codex.",
    "CODEX_VERSION_FAILED":"Codex CLI có tồn tại nhưng lệnh --version không chạy thành công.","PACKAGE_ZIP_MISSING":"Thiếu file ZIP gói phát hành cần đối chiếu SHA-256.",
    "RELEASE_MANIFEST_MISSING":"Thiếu release manifest cần đối chiếu SHA-256.","SOURCE_CERTIFICATION_REPORT_MISSING":"Thiếu target-machine certification report gốc dùng để bind provenance.",
    "SOURCE_CERTIFICATION_REPORT_INVALID":"Target-machine certification report gốc không đạt v25.75 schema-2 artifact-bound exact 7/7 contract.",
    "SOURCE_PACKAGE_ZIP_SHA256_MISMATCH":"Package ZIP không trùng artifact đã được target certification bind.",
    "SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH":"Release manifest không trùng artifact đã được target certification bind.",
    "EXACT_SEVEN_CASE_REPORTS_REQUIRED":"Phải cung cấp đúng 7 báo cáo: host, codex, quota, failover, lan, soak_6h, soak_24h.",
    "CASE_REPORT_FILES_MISSING":"Có báo cáo case được khai báo nhưng file không tồn tại.","TRUST_STORE_MISSING":"Thiếu trust store certificate của HMS-AI-ROUTER.",
    "TRUST_STORE_INVALID":"Trust store không hợp lệ hoặc không đọc được.","TRUST_STORE_NO_ACTIVE_CERTIFICATE":"Trust store chưa có certificate ACTIVE hợp lệ.",
    "CERTIFICATE_THUMBPRINT_INVALID":"Thiếu hoặc sai định dạng certificate thumbprint dùng để ký packet.","CERTIFICATE_SIGN_SCRIPT_MISSING":"Thiếu PowerShell certificate signing helper.",
    "CERTIFICATE_INSPECT_SCRIPT_MISSING":"Thiếu PowerShell certificate preflight helper.","CERTIFICATE_PREFLIGHT_FAILED":"Certificate được chọn không đạt preflight read-only.",
    "CERTIFICATE_NOT_ACTIVE_IN_TRUST_STORE":"Certificate được chọn không phải ACTIVE pin trong trust store hiện hành.","CRYPTOGRAPHY_REQUIRED":"Thiếu Python package cryptography cần để xác minh chữ ký certificate.",
}


def _reason_vi(reason:str)->str:return REASON_VI.get(str(reason).split(":",1)[0],reason)
def _sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def _stable_bytes(obj)->bytes:return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
def _utc_text(value)->str:
    try:
        dt=datetime.fromisoformat(str(value or "").replace("Z","+00:00"))
        if dt.tzinfo is None:return ""
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError,ValueError):return ""


def _codex_probe(codex:str=""):
    exe=codex.strip() if codex else (shutil.which("codex") or "")
    if not exe:return {"ok":False,"reason":"CODEX_CLI_NOT_FOUND","path":""}
    try:
        p=subprocess.run([exe,"--version"],capture_output=True,text=True,timeout=15,check=False); text=(p.stdout or p.stderr or "").strip()
        return {"ok":p.returncode==0 and bool(text),"reason":"" if p.returncode==0 else "CODEX_VERSION_FAILED","path":exe,"version":text[:200]}
    except Exception as exc:return {"ok":False,"reason":"CODEX_PROBE_"+type(exc).__name__.upper(),"path":exe}


def _parse_case_specs(values):
    out={}
    for raw in values or []:
        if "=" not in raw:raise ValueError("case report must use CASE_ID=PATH")
        cid,p=raw.split("=",1); cid=cid.strip(); p=p.strip()
        if cid in out:raise ValueError("duplicate case report: "+cid)
        out[cid]=Path(p)
    return out

def _normalize_thumbprint(value:str)->str:return re.sub(r"[^0-9A-Fa-f]","",str(value or "")).upper()


def _validate_source_path(value:str):
    source=Path(value) if value else None
    if not source or not source.is_file():return None,{},"SOURCE_CERTIFICATION_REPORT_MISSING"
    try:return source,case_exporter.validate_source_report(source),""
    except Exception as exc:return source,{},"SOURCE_CERTIFICATION_REPORT_INVALID:"+str(exc)


def _artifact_preflight(package:Path|None,manifest:Path|None,source_validation:dict)->tuple[str,str,list[str]]:
    reasons=[]; package_sha=""; manifest_sha=""
    if package and package.is_file():package_sha=_sha_file(package)
    if manifest and manifest.is_file():manifest_sha=_sha_file(manifest)
    expected_package=str(source_validation.get("source_package_zip_sha256") or "").lower()
    expected_manifest=str(source_validation.get("source_release_manifest_sha256") or "").lower()
    if expected_package and package_sha and package_sha!=expected_package:reasons.append("SOURCE_PACKAGE_ZIP_SHA256_MISMATCH")
    if expected_manifest and manifest_sha and manifest_sha!=expected_manifest:reasons.append("SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH")
    return package_sha,manifest_sha,reasons


def preflight(args):
    reasons=[]; is_windows=platform.system().lower()=="windows"
    if not is_windows:reasons.append("WINDOWS_TARGET_REQUIRED")
    codex=_codex_probe(args.codex)
    if not codex["ok"]:reasons.append(codex["reason"])
    package=Path(args.package_zip) if args.package_zip else None; manifest=Path(args.release_manifest) if args.release_manifest else None
    if not package or not package.is_file():reasons.append("PACKAGE_ZIP_MISSING")
    if not manifest or not manifest.is_file():reasons.append("RELEASE_MANIFEST_MISSING")
    source_path,source_validation,source_error=_validate_source_path(args.source_certification_report)
    if source_error:reasons.append(source_error)
    package_sha,manifest_sha,artifact_reasons=_artifact_preflight(package,manifest,source_validation); reasons.extend(artifact_reasons)
    try:specs=_parse_case_specs(args.case_report)
    except ValueError as exc:specs={}; reasons.append("CASE_SPEC_INVALID:"+str(exc))
    matrix=validate_case_ids(specs.keys())
    if not matrix["valid"]:reasons.append("EXACT_SEVEN_CASE_REPORTS_REQUIRED")
    missing_files=[cid for cid,p in specs.items() if not p.is_file()]
    if missing_files:reasons.append("CASE_REPORT_FILES_MISSING")

    trust_path=Path(args.trust_store) if args.trust_store else None; trust_snapshot={}; active_certificates=[]
    if not trust_path or not trust_path.is_file():reasons.append("TRUST_STORE_MISSING")
    else:
        try:
            store=trust_store.load_store(trust_path); trust_snapshot=trust_store.trust_snapshot(store); snap_check=validate_trust_snapshot(trust_snapshot)
            if not snap_check["valid"]:reasons.append("TRUST_STORE_INVALID")
            active_certificates=sorted(trust_store.trusted_certificate_sha256(store))
            if not active_certificates:reasons.append("TRUST_STORE_NO_ACTIVE_CERTIFICATE")
        except Exception:reasons.append("TRUST_STORE_INVALID")
    thumbprint=_normalize_thumbprint(args.certificate_thumbprint)
    if not THUMBPRINT.fullmatch(thumbprint):reasons.append("CERTIFICATE_THUMBPRINT_INVALID")
    sign_script=Path(args.certificate_sign_script) if args.certificate_sign_script else DEFAULT_SIGN_SCRIPT
    inspect_script=Path(args.certificate_inspect_script) if args.certificate_inspect_script else DEFAULT_INSPECT_SCRIPT
    if not sign_script.is_file():reasons.append("CERTIFICATE_SIGN_SCRIPT_MISSING")
    if not inspect_script.is_file():reasons.append("CERTIFICATE_INSPECT_SCRIPT_MISSING")
    crypto_ready=importlib.util.find_spec("cryptography") is not None
    if not crypto_ready:reasons.append("CRYPTOGRAPHY_REQUIRED")
    cert_check={}
    if is_windows and THUMBPRINT.fullmatch(thumbprint) and inspect_script.is_file() and crypto_ready:
        try:
            cert_check=certificate_preflight.certificate_preflight(thumbprint,inspect_script); selected_sha=str(cert_check.get("certificate_sha256") or "").lower()
            if active_certificates and selected_sha not in active_certificates:reasons.append("CERTIFICATE_NOT_ACTIVE_IN_TRUST_STORE")
        except Exception as exc:reasons.append("CERTIFICATE_PREFLIGHT_FAILED:"+str(exc))
    reasons=sorted(set(reasons))
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER_PREFLIGHT","ready":not reasons,
            "reasons":reasons,"reasons_vi":[_reason_vi(x) for x in reasons],"windows":is_windows,"codex":codex,
            "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"case_matrix":matrix,"missing_case_files":missing_files,
            "source_certification_report_present":source_path is not None,"source_certification_report_sha256":source_validation.get("source_report_sha256",""),
            "source_capture_utc":source_validation.get("source_capture_utc",""),"source_package_zip_sha256":source_validation.get("source_package_zip_sha256",""),
            "source_release_manifest_sha256":source_validation.get("source_release_manifest_sha256",""),"actual_package_zip_sha256":package_sha,
            "actual_release_manifest_sha256":manifest_sha,"trust_snapshot_sha256":trust_snapshot.get("trust_snapshot_sha256",""),
            "trusted_active_certificate_count":len(active_certificates),"selected_certificate_sha256":cert_check.get("certificate_sha256",""),
            "certificate_preflight_ready":cert_check.get("ready") is True,"certificate_not_after_utc":cert_check.get("not_after_utc",""),
            "certificate_thumbprint_ref":attestation_signer.safe_ref(thumbprint) if thumbprint else "","certificate_sign_script":str(sign_script),
            "certificate_inspect_script":str(inspect_script),"creates_synthetic_evidence":False,"windows_runtime_certified":False,
            "production_score_promotion_eligible":False}


def _validate_case_report(cid,path):
    raw=path.read_bytes(); obj=json.loads(raw.decode("utf-8-sig")); reasons=[]
    capture_utc=_utc_text(obj.get("capture_utc")); source_sha=str(obj.get("source_report_sha256") or "").lower()
    source_manifest=str(obj.get("source_release_manifest_sha256") or "").lower(); source_package=str(obj.get("source_package_zip_sha256") or "").lower()
    if obj.get("product")!="HMS-AI-ROUTER":reasons.append("CASE_PRODUCT_INVALID")
    if str(obj.get("version") or "")!=VERSION:reasons.append("CASE_VERSION_INVALID")
    if obj.get("suite")!="EXTERNAL_WINDOWS_RUNTIME_CASE_REPORT":reasons.append("CASE_SUITE_INVALID")
    if obj.get("case_id")!=cid:reasons.append("CASE_ID_MISMATCH")
    if obj.get("status")!="PASS":reasons.append("CASE_NOT_PASS")
    if obj.get("synthetic") is not False:reasons.append("CASE_SYNTHETIC_OR_UNMARKED")
    if obj.get("local_only") is not False:reasons.append("CASE_LOCAL_ONLY_OR_UNMARKED")
    if str(obj.get("target_os") or "").lower()!="windows":reasons.append("CASE_WINDOWS_TARGET_REQUIRED")
    if obj.get("codex_target") is not True:reasons.append("CASE_CODEX_TARGET_REQUIRED")
    if not capture_utc:reasons.append("CASE_CAPTURE_UTC_INVALID")
    if obj.get("source_suite")!=CASE_SOURCE_SUITE:reasons.append("CASE_SOURCE_SUITE_INVALID")
    if obj.get("source_verdict")!=CASE_SOURCE_VERDICT:reasons.append("CASE_SOURCE_VERDICT_INVALID")
    if obj.get("source_production_certification")!=CASE_SOURCE_CERTIFICATION:reasons.append("CASE_SOURCE_CERTIFICATION_INVALID")
    if not HEX64.fullmatch(source_sha):reasons.append("CASE_SOURCE_REPORT_SHA256_INVALID")
    if not HEX64.fullmatch(source_manifest):reasons.append("CASE_SOURCE_RELEASE_MANIFEST_SHA256_INVALID")
    if not HEX64.fullmatch(source_package):reasons.append("CASE_SOURCE_PACKAGE_ZIP_SHA256_INVALID")
    return {"case_id":cid,"status":"PASS" if not reasons else "REJECT","report_sha256":hashlib.sha256(raw).hexdigest(),
            "capture_utc":capture_utc,"source_report_sha256":source_sha,"source_release_manifest_sha256":source_manifest,
            "source_package_zip_sha256":source_package,"reasons":reasons}


def build_packet(args):
    pf=preflight(args)
    if not pf["ready"]:raise ValueError("preflight failed: "+",".join(pf["reasons"]))
    source_path,source_validation,source_error=_validate_source_path(args.source_certification_report)
    if source_error or source_path is None:raise ValueError(source_error or "SOURCE_CERTIFICATION_REPORT_MISSING")
    source_sha=str(source_validation.get("source_report_sha256") or "").lower(); source_capture=str(source_validation.get("source_capture_utc") or "")
    source_package=str(source_validation.get("source_package_zip_sha256") or "").lower(); source_manifest=str(source_validation.get("source_release_manifest_sha256") or "").lower()
    if source_sha!=str(pf.get("source_certification_report_sha256") or "").lower() or source_capture!=str(pf.get("source_capture_utc") or ""):
        raise RuntimeError("SOURCE_CERTIFICATION_REPORT_CHANGED_AFTER_PREFLIGHT")
    package_sha=_sha_file(Path(args.package_zip)); manifest_sha=_sha_file(Path(args.release_manifest))
    if package_sha!=source_package:raise RuntimeError("SOURCE_PACKAGE_ZIP_SHA256_MISMATCH")
    if manifest_sha!=source_manifest:raise RuntimeError("SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH")
    if package_sha!=str(pf.get("actual_package_zip_sha256") or "") or manifest_sha!=str(pf.get("actual_release_manifest_sha256") or ""):
        raise RuntimeError("ARTIFACT_CHANGED_AFTER_PREFLIGHT")

    specs=_parse_case_specs(args.case_report); case_results=[]; bad=[]
    for cid in REQUIRED_RUNTIME_CASE_IDS:
        row=_validate_case_report(cid,specs[cid]); case_results.append(row)
        if row["reasons"]:bad.append(cid)
    if bad:raise ValueError("case reports rejected: "+",".join(bad))
    if {x["capture_utc"] for x in case_results}!={source_capture}:raise ValueError("CASE_CAPTURE_UTC_MISMATCH")
    if {x["source_report_sha256"] for x in case_results}!={source_sha}:raise ValueError("CASE_SOURCE_REPORT_SHA256_MISMATCH")
    if {x["source_package_zip_sha256"] for x in case_results}!={source_package}:raise ValueError("CASE_SOURCE_PACKAGE_ZIP_SHA256_MISMATCH")
    if {x["source_release_manifest_sha256"] for x in case_results}!={source_manifest}:raise ValueError("CASE_SOURCE_RELEASE_MANIFEST_SHA256_MISMATCH")

    store=trust_store.load_store(Path(args.trust_store)); snapshot=trust_store.trust_snapshot(store)
    if snapshot.get("trust_snapshot_sha256")!=pf.get("trust_snapshot_sha256"):raise RuntimeError("TRUST_STORE_CHANGED_AFTER_PREFLIGHT")
    if str(pf.get("selected_certificate_sha256") or "").lower() not in trust_store.trusted_certificate_sha256(store):raise RuntimeError("CERTIFICATE_NOT_ACTIVE_IN_TRUST_STORE")
    packet={"source_classification":SOURCE_CLASSIFICATION,"synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
            "package_zip_sha256":package_sha,"release_manifest_sha256":manifest_sha,"cockpit_baseline":args.cockpit_baseline,
            "capture_utc":source_capture,"source_certification_report_sha256":source_sha,
            "source_artifact_binding":{"binding_schema":"HMS_V25_75_TARGET_ARTIFACT_BINDING_V1","package_zip_sha256":source_package,
                                       "release_manifest_sha256":source_manifest},
            "nonce":"nonce-"+secrets.token_hex(16),"run_id":"run-"+secrets.token_hex(16),"report_id":"report-"+secrets.token_hex(16),
            "trust_snapshot":snapshot,"case_results":[{"case_id":x["case_id"],"status":"PASS","report_sha256":x["report_sha256"],
                "source_report_sha256":x["source_report_sha256"],"source_package_zip_sha256":x["source_package_zip_sha256"],
                "source_release_manifest_sha256":x["source_release_manifest_sha256"]} for x in case_results]}
    sign_script=Path(args.certificate_sign_script) if args.certificate_sign_script else DEFAULT_SIGN_SCRIPT
    packet["signer"]=external_certificate_signer.certificate_sign(signing_payload(packet),_normalize_thumbprint(args.certificate_thumbprint),sign_script)
    if str(packet["signer"].get("certificate_sha256") or "").lower()!=str(pf.get("selected_certificate_sha256") or "").lower():raise RuntimeError("CERTIFICATE_CHANGED_AFTER_PREFLIGHT")
    raw=_stable_bytes(packet); check=verify_packet(packet,raw_packet_sha256=hashlib.sha256(raw).hexdigest(),expected_package_sha256=package_sha,
        expected_manifest_sha256=manifest_sha,expected_trust_snapshot_sha256=snapshot["trust_snapshot_sha256"],current_cockpit_baseline=args.cockpit_baseline)
    if not check["real_packet_verified"]:raise ValueError("packet rejected by ingest gate: "+",".join(check["reasons"]))
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(raw)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER","verdict":"PACKET_READY_FOR_HUMAN_REVIEW",
            "packet_path":str(out),"packet_sha256":hashlib.sha256(raw).hexdigest(),"package_zip_sha256":package_sha,"release_manifest_sha256":manifest_sha,
            "source_certification_report_sha256":source_sha,"source_capture_utc":source_capture,"artifact_binding_verified":True,
            "certificate_sha256":check["provenance"].get("certificate_sha256",""),"trust_snapshot_sha256":check["provenance"].get("trust_snapshot_sha256",""),
            "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"certificate_preflight":"PASS","ingest_precheck":"PASS","windows_runtime_certified":False,
            "external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,"automatic_production_certification":False}


def main():
    ap=argparse.ArgumentParser(description="HMS v25.75 real Windows/current-Codex evidence packet runner")
    ap.add_argument("--preflight",action="store_true"); ap.add_argument("--package-zip",default=""); ap.add_argument("--release-manifest",default="")
    ap.add_argument("--source-certification-report",default="",help="Original v25.75 schema-2 artifact-bound TARGET_MACHINE_CERTIFICATION JSON")
    ap.add_argument("--case-report",action="append",default=[],help="CASE_ID=PATH; repeat exactly seven times")
    ap.add_argument("--trust-store",default=""); ap.add_argument("--certificate-thumbprint",default=""); ap.add_argument("--certificate-sign-script",default=str(DEFAULT_SIGN_SCRIPT))
    ap.add_argument("--certificate-inspect-script",default=str(DEFAULT_INSPECT_SCRIPT)); ap.add_argument("--codex",default=""); ap.add_argument("--cockpit-baseline",default=COCKPIT_BASELINE)
    ap.add_argument("--output",default="HMS_EXTERNAL_WINDOWS_CODEX_REVIEW_PACKET.json"); a=ap.parse_args()
    try:
        out=preflight(a) if a.preflight else build_packet(a); print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if (out.get("ready") if a.preflight else out.get("ingest_precheck")=="PASS") else 2
    except Exception as exc:
        out={"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER","verdict":"BLOCKED_FAIL_CLOSED",
             "error":type(exc).__name__,"detail":str(exc),"windows_runtime_certified":False,"production_score_promotion_eligible":False,"synthetic_evidence_created":False}
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 2

if __name__=="__main__":raise SystemExit(main())
