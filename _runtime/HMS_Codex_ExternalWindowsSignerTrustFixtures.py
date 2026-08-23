#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone

import HMS_Codex_AttestationTrustStore as trust_store
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet, verify_external_signer_trust

VERSION="25.75"; PRODUCT="HMS-AI-ROUTER"


def _base():
    return {"source_classification":"REAL_EXTERNAL_WINDOWS_CODEX","synthetic":False,"local_only":False,
            "target_os":"Windows","codex_target":True,"package_zip_sha256":"a"*64,"release_manifest_sha256":"b"*64,
            "cockpit_baseline":"1.3.28","capture_utc":datetime.now(timezone.utc).isoformat(),
            "nonce":"nonce-fixture-001","run_id":"run-fixture-001","report_id":"report-fixture-001",
            "case_results":[{"case_id":"host","status":"PASS","report_sha256":"c"*64}]}

def _rehash_snapshot(packet):
    snap=packet["trust_snapshot"]; body={k:v for k,v in snap.items() if k!="trust_snapshot_sha256"}
    snap["trust_snapshot_sha256"]=trust_store.sha(trust_store.stable(body))

def run():
    good=synthetic_signed_packet(_base()); good_result=verify_external_signer_trust(good)
    self_declared=json.loads(json.dumps(good)); self_declared["signer"]={"status":"VALID","signer_ref":"self-declared","signature_sha256":"d"*64}
    payload_tamper=json.loads(json.dumps(good)); payload_tamper["release_manifest_sha256"]="e"*64
    snapshot_tamper=json.loads(json.dumps(good)); snapshot_tamper["trust_snapshot"]["generation"]+=1
    revoked=json.loads(json.dumps(good)); revoked["trust_snapshot"]["certificates"][0]["state"]="REVOKED"; revoked["trust_snapshot"]["certificates"][0]["revocation_reason_code"]="KEY_COMPROMISE"; _rehash_snapshot(revoked)
    expired=json.loads(json.dumps(good)); expired["trust_snapshot"]["certificates"][0]["not_after_utc"]="2000-01-01T00:00:00+00:00"; _rehash_snapshot(expired)
    ref_mismatch=json.loads(json.dumps(good)); ref_mismatch["trust_snapshot"]["certificates"][0]["signer_key_id_ref"]="ref-"+("9"*24); _rehash_snapshot(ref_mismatch)
    dpapi=json.loads(json.dumps(good)); dpapi["signer"]["signer_class"]="WINDOWS_LOCAL_MACHINE_DPAPI_HMAC"
    cases={
        "valid_certificate_control": good_result["valid"],
        "self_declared_signer_rejected": not verify_external_signer_trust(self_declared)["valid"],
        "payload_tamper_rejected": not verify_external_signer_trust(payload_tamper)["valid"],
        "trust_snapshot_hash_tamper_rejected": "TRUST_SNAPSHOT_DIGEST_MISMATCH" in verify_external_signer_trust(snapshot_tamper)["reasons"],
        "revoked_pin_rejected": "CERTIFICATE_REVOKED" in verify_external_signer_trust(revoked)["reasons"],
        "expired_pin_rejected": "CERTIFICATE_EXPIRED" in verify_external_signer_trust(expired)["reasons"],
        "signer_ref_mismatch_rejected": "SIGNER_TRUST_REF_MISMATCH" in verify_external_signer_trust(ref_mismatch)["reasons"],
        "dpapi_external_rejected": "EXTERNAL_CERTIFICATE_SIGNER_REQUIRED" in verify_external_signer_trust(dpapi)["reasons"],
    }
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in cases.items()]
    passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_SIGNER_TRUST_NEGATIVE_FIXTURES",
            "verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},
            "tests":tests,"synthetic_fixture_only":True,"windows_runtime_certified":False,"production_score_promotion_eligible":False}

if __name__=="__main__":
    out=run(); print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out["verdict"]=="PASS" else 2)
