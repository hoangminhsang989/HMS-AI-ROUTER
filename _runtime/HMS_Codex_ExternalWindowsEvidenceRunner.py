#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, importlib.util, json, platform, re, secrets, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_WindowsAttestationSigner as attestation_signer
import HMS_Codex_ExternalWindowsCertificateSigner as external_certificate_signer
from HMS_Codex_ExternalWindowsSignerTrustContract import signing_payload, validate_trust_snapshot
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS, validate_case_ids
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, SOURCE_CLASSIFICATION, verify_packet

VERSION = "25.75"
THUMBPRINT = re.compile(r"^[0-9A-Fa-f]{20,128}$")
DEFAULT_SIGN_SCRIPT = Path(__file__).resolve().with_name("HMS_Sign_Digest_With_Certificate.ps1")

REASON_VI = {
    "WINDOWS_TARGET_REQUIRED": "Phải chạy trên máy Windows đích.",
    "CODEX_CLI_NOT_FOUND": "Không tìm thấy Codex CLI trên PATH hoặc đường dẫn --codex.",
    "CODEX_VERSION_FAILED": "Codex CLI có tồn tại nhưng lệnh --version không chạy thành công.",
    "PACKAGE_ZIP_MISSING": "Thiếu file ZIP gói phát hành cần đối chiếu SHA-256.",
    "RELEASE_MANIFEST_MISSING": "Thiếu release manifest cần đối chiếu SHA-256.",
    "EXACT_SEVEN_CASE_REPORTS_REQUIRED": "Phải cung cấp đúng 7 báo cáo: host, codex, quota, failover, lan, soak_6h, soak_24h.",
    "CASE_REPORT_FILES_MISSING": "Có báo cáo case được khai báo nhưng file không tồn tại.",
    "TRUST_STORE_MISSING": "Thiếu trust store certificate của HMS-AI-ROUTER.",
    "TRUST_STORE_INVALID": "Trust store không hợp lệ hoặc không đọc được.",
    "TRUST_STORE_NO_ACTIVE_CERTIFICATE": "Trust store chưa có certificate ACTIVE hợp lệ.",
    "CERTIFICATE_THUMBPRINT_INVALID": "Thiếu hoặc sai định dạng certificate thumbprint dùng để ký packet.",
    "CERTIFICATE_SIGN_SCRIPT_MISSING": "Thiếu PowerShell certificate signing helper.",
    "CRYPTOGRAPHY_REQUIRED": "Thiếu Python package cryptography cần để xác minh chữ ký certificate.",
}

def _reason_vi(reason: str) -> str:
    key=str(reason).split(":",1)[0]
    return REASON_VI.get(key, reason)

def _sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()

def _stable_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",",":"))+"\n").encode("utf-8")

def _codex_probe(codex: str=""):
    exe=codex.strip() if codex else (shutil.which("codex") or "")
    if not exe: return {"ok":False,"reason":"CODEX_CLI_NOT_FOUND","path":""}
    try:
        p=subprocess.run([exe,"--version"],capture_output=True,text=True,timeout=15,check=False)
        text=(p.stdout or p.stderr or "").strip()
        return {"ok":p.returncode==0 and bool(text),"reason":"" if p.returncode==0 else "CODEX_VERSION_FAILED",
                "path":exe,"version":text[:200]}
    except Exception as exc:
        return {"ok":False,"reason":"CODEX_PROBE_"+type(exc).__name__.upper(),"path":exe}

def _parse_case_specs(values):
    out={}
    for raw in values or []:
        if "=" not in raw: raise ValueError("case report must use CASE_ID=PATH")
        cid,p=raw.split("=",1); cid=cid.strip(); p=p.strip()
        if cid in out: raise ValueError("duplicate case report: "+cid)
        out[cid]=Path(p)
    return out

def _normalize_thumbprint(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()

def preflight(args):
    reasons=[]; is_windows=platform.system().lower()=="windows"
    if not is_windows: reasons.append("WINDOWS_TARGET_REQUIRED")
    codex=_codex_probe(args.codex)
    if not codex["ok"]: reasons.append(codex["reason"])
    package=Path(args.package_zip) if args.package_zip else None
    manifest=Path(args.release_manifest) if args.release_manifest else None
    if not package or not package.is_file(): reasons.append("PACKAGE_ZIP_MISSING")
    if not manifest or not manifest.is_file(): reasons.append("RELEASE_MANIFEST_MISSING")
    try: specs=_parse_case_specs(args.case_report)
    except ValueError as exc: specs={}; reasons.append("CASE_SPEC_INVALID:"+str(exc))
    matrix=validate_case_ids(specs.keys())
    if not matrix["valid"]: reasons.append("EXACT_SEVEN_CASE_REPORTS_REQUIRED")
    missing_files=[cid for cid,p in specs.items() if not p.is_file()]
    if missing_files: reasons.append("CASE_REPORT_FILES_MISSING")

    trust_path=Path(args.trust_store) if args.trust_store else None
    trust_snapshot={}; active_certificates=[]
    if not trust_path or not trust_path.is_file(): reasons.append("TRUST_STORE_MISSING")
    else:
        try:
            store=trust_store.load_store(trust_path); trust_snapshot=trust_store.trust_snapshot(store)
            snap_check=validate_trust_snapshot(trust_snapshot)
            if not snap_check["valid"]: reasons.append("TRUST_STORE_INVALID")
            active_certificates=sorted(trust_store.trusted_certificate_sha256(store))
            if not active_certificates: reasons.append("TRUST_STORE_NO_ACTIVE_CERTIFICATE")
        except Exception: reasons.append("TRUST_STORE_INVALID")
    thumbprint=_normalize_thumbprint(args.certificate_thumbprint)
    if not THUMBPRINT.fullmatch(thumbprint): reasons.append("CERTIFICATE_THUMBPRINT_INVALID")
    script=Path(args.certificate_sign_script) if args.certificate_sign_script else DEFAULT_SIGN_SCRIPT
    if not script.is_file(): reasons.append("CERTIFICATE_SIGN_SCRIPT_MISSING")
    if importlib.util.find_spec("cryptography") is None: reasons.append("CRYPTOGRAPHY_REQUIRED")

    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER_PREFLIGHT",
            "ready":not reasons,"reasons":reasons,"reasons_vi":[_reason_vi(x) for x in reasons],"windows":is_windows,"codex":codex,
            "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"case_matrix":matrix,"missing_case_files":missing_files,
            "trust_snapshot_sha256":trust_snapshot.get("trust_snapshot_sha256",""),"trusted_active_certificate_count":len(active_certificates),
            "certificate_thumbprint_ref":attestation_signer.safe_ref(thumbprint) if thumbprint else "","certificate_sign_script":str(script),
            "creates_synthetic_evidence":False,"windows_runtime_certified":False,"production_score_promotion_eligible":False}

def _validate_case_report(cid,path):
    raw=path.read_bytes(); obj=json.loads(raw.decode("utf-8-sig")); reasons=[]
    if obj.get("case_id")!=cid: reasons.append("CASE_ID_MISMATCH")
    if obj.get("status")!="PASS": reasons.append("CASE_NOT_PASS")
    if obj.get("synthetic") is not False: reasons.append("CASE_SYNTHETIC_OR_UNMARKED")
    if obj.get("local_only") is not False: reasons.append("CASE_LOCAL_ONLY_OR_UNMARKED")
    if str(obj.get("target_os") or "").lower()!="windows": reasons.append("CASE_WINDOWS_TARGET_REQUIRED")
    if obj.get("codex_target") is not True: reasons.append("CASE_CODEX_TARGET_REQUIRED")
    return {"case_id":cid,"status":"PASS" if not reasons else "REJECT","report_sha256":hashlib.sha256(raw).hexdigest(),"reasons":reasons}

def build_packet(args):
    pf=preflight(args)
    if not pf["ready"]: raise ValueError("preflight failed: "+",".join(pf["reasons"]))
    specs=_parse_case_specs(args.case_report); case_results=[]; bad=[]
    for cid in REQUIRED_RUNTIME_CASE_IDS:
        row=_validate_case_report(cid,specs[cid]); case_results.append(row)
        if row["reasons"]: bad.append(cid)
    if bad: raise ValueError("case reports rejected: "+",".join(bad))

    store=trust_store.load_store(Path(args.trust_store)); snapshot=trust_store.trust_snapshot(store)
    packet={"source_classification":SOURCE_CLASSIFICATION,"synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
            "package_zip_sha256":_sha_file(Path(args.package_zip)),"release_manifest_sha256":_sha_file(Path(args.release_manifest)),
            "cockpit_baseline":args.cockpit_baseline,"capture_utc":datetime.now(timezone.utc).isoformat(),
            "nonce":"nonce-"+secrets.token_hex(16),"run_id":"run-"+secrets.token_hex(16),"report_id":"report-"+secrets.token_hex(16),
            "trust_snapshot":snapshot,"case_results":[{"case_id":x["case_id"],"status":"PASS","report_sha256":x["report_sha256"]} for x in case_results]}
    script=Path(args.certificate_sign_script) if args.certificate_sign_script else DEFAULT_SIGN_SCRIPT
    packet["signer"]=external_certificate_signer.certificate_sign(signing_payload(packet),_normalize_thumbprint(args.certificate_thumbprint),script)
    raw=_stable_bytes(packet)
    check=verify_packet(packet,raw_packet_sha256=hashlib.sha256(raw).hexdigest(),expected_package_sha256=packet["package_zip_sha256"],
        expected_manifest_sha256=packet["release_manifest_sha256"],expected_trust_snapshot_sha256=snapshot["trust_snapshot_sha256"],
        current_cockpit_baseline=args.cockpit_baseline)
    if not check["real_packet_verified"]: raise ValueError("packet rejected by ingest gate: "+",".join(check["reasons"]))
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(raw)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER","verdict":"PACKET_READY_FOR_HUMAN_REVIEW",
            "packet_path":str(out),"packet_sha256":hashlib.sha256(raw).hexdigest(),"package_zip_sha256":packet["package_zip_sha256"],
            "release_manifest_sha256":packet["release_manifest_sha256"],"certificate_sha256":check["provenance"].get("certificate_sha256",""),
            "trust_snapshot_sha256":check["provenance"].get("trust_snapshot_sha256",""),"required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),
            "ingest_precheck":"PASS","windows_runtime_certified":False,"external_windows_target_evidence_imported":False,
            "production_score_promotion_eligible":False,"automatic_production_certification":False}

def main():
    ap=argparse.ArgumentParser(description="HMS v25.75 real Windows/current-Codex evidence packet runner")
    ap.add_argument("--preflight",action="store_true"); ap.add_argument("--package-zip",default=""); ap.add_argument("--release-manifest",default="")
    ap.add_argument("--case-report",action="append",default=[],help="CASE_ID=PATH; repeat exactly seven times"); ap.add_argument("--trust-store",default="")
    ap.add_argument("--certificate-thumbprint",default=""); ap.add_argument("--certificate-sign-script",default=str(DEFAULT_SIGN_SCRIPT)); ap.add_argument("--codex",default="")
    ap.add_argument("--cockpit-baseline",default=COCKPIT_BASELINE); ap.add_argument("--output",default="HMS_EXTERNAL_WINDOWS_CODEX_REVIEW_PACKET.json")
    a=ap.parse_args()
    try:
        out=preflight(a) if a.preflight else build_packet(a); print(json.dumps(out,ensure_ascii=False,indent=2))
        return 0 if (out.get("ready") if a.preflight else out.get("ingest_precheck")=="PASS") else 2
    except Exception as exc:
        out={"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_EVIDENCE_RUNNER","verdict":"BLOCKED_FAIL_CLOSED",
             "error":type(exc).__name__,"detail":str(exc),"windows_runtime_certified":False,
             "production_score_promotion_eligible":False,"synthetic_evidence_created":False}
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 2

if __name__=="__main__": raise SystemExit(main())
