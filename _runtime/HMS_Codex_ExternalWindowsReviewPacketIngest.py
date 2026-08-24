#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS, validate_case_ids
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet, verify_external_signer_trust

VERSION="25.75"; COCKPIT_BASELINE="1.3.28"
SOURCE_CLASSIFICATION="REAL_EXTERNAL_WINDOWS_CODEX"; REQUIRED_CASE_COUNT=len(REQUIRED_RUNTIME_CASE_IDS)
HEX64=re.compile(r"^[0-9a-f]{64}$")

def _hex(v): return HEX64.fullmatch(str(v or "").lower()) is not None
def _sha(b): return hashlib.sha256(b).hexdigest()
def _stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _dt(v):
    try:
        x=datetime.fromisoformat(str(v).replace("Z","+00:00")); return x.astimezone(timezone.utc) if x.tzinfo else None
    except (TypeError,ValueError): return None

def verify_packet(packet,*,raw_packet_sha256,expected_package_sha256,expected_manifest_sha256,expected_trust_snapshot_sha256,
                  current_cockpit_baseline=COCKPIT_BASELINE,seen=None,now=None,freshness_hours=72):
    reasons=[]; seen=seen or {}; now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    raw=str(raw_packet_sha256).lower(); pkg=str(packet.get("package_zip_sha256") or "").lower(); man=str(packet.get("release_manifest_sha256") or "").lower()
    source_cert=str(packet.get("source_certification_report_sha256") or "").lower()
    expected_trust=str(expected_trust_snapshot_sha256 or "").lower()
    if not _hex(raw): reasons.append("RAW_PACKET_DIGEST_INVALID")
    if raw in {str(x).lower() for x in seen.get("packet_digests",[])}: reasons.append("DUPLICATE_PACKET_DIGEST")
    if packet.get("source_classification")!=SOURCE_CLASSIFICATION: reasons.append("REAL_EXTERNAL_WINDOWS_CODEX_SOURCE_REQUIRED")
    if packet.get("synthetic") is not False: reasons.append("SYNTHETIC_EVIDENCE_REJECTED")
    if packet.get("local_only") is not False: reasons.append("LOCAL_ONLY_EVIDENCE_REJECTED")
    if str(packet.get("target_os") or "").lower()!="windows": reasons.append("WINDOWS_TARGET_REQUIRED")
    if packet.get("codex_target") is not True: reasons.append("CODEX_TARGET_REQUIRED")
    if not _hex(expected_package_sha256) or pkg!=str(expected_package_sha256).lower(): reasons.append("PACKAGE_ZIP_SHA256_MISMATCH")
    if not _hex(expected_manifest_sha256) or man!=str(expected_manifest_sha256).lower(): reasons.append("RELEASE_MANIFEST_SHA256_MISMATCH")
    if not _hex(source_cert): reasons.append("SOURCE_CERTIFICATION_REPORT_SHA256_REQUIRED")
    if packet.get("cockpit_baseline")!=current_cockpit_baseline: reasons.append("COCKPIT_BASELINE_CHANGED_OR_STALE")
    captured=_dt(packet.get("capture_utc"))
    if not captured: reasons.append("CAPTURE_UTC_INVALID")
    else:
        if captured>now+timedelta(minutes=5): reasons.append("CAPTURE_TIME_IN_FUTURE")
        if now-captured>timedelta(hours=max(1,int(freshness_hours))): reasons.append("EVIDENCE_STALE")
    for field,label in (("nonce","NONCE"),("run_id","RUN_ID"),("report_id","REPORT_ID")):
        value=str(packet.get(field) or "")
        if len(value)<8 or len(value)>256: reasons.append(label+"_INVALID")
        if value in set(seen.get(field+"s",[])): reasons.append(label+"_REPLAY")

    signer=packet.get("signer") if isinstance(packet.get("signer"),dict) else {}
    if signer.get("synthetic_fixture") is True: reasons.append("SYNTHETIC_SIGNER_FIXTURE_REJECTED")
    signer_trust=verify_external_signer_trust(packet)
    if not signer_trust["valid"]:
        reasons.append("CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED"); reasons.extend(signer_trust["reasons"])
    observed_trust=str(signer_trust.get("trust_snapshot_sha256") or "").lower()
    if not _hex(expected_trust): reasons.append("EXPECTED_TRUST_SNAPSHOT_SHA256_REQUIRED")
    elif observed_trust!=expected_trust: reasons.append("TRUST_ANCHOR_MISMATCH")

    cases=packet.get("case_results") if isinstance(packet.get("case_results"),list) else []
    if len(cases)!=REQUIRED_CASE_COUNT: reasons.append("RUNTIME_CASE_MATRIX_NOT_7")
    ids=[]; digests=[]; case_sources=[]
    for i,c in enumerate(cases):
        if not isinstance(c,dict): reasons.append(f"CASE_{i}_INVALID"); continue
        cid=str(c.get("case_id") or ""); dg=str(c.get("report_sha256") or "").lower(); case_source=str(c.get("source_report_sha256") or "").lower(); ids.append(cid)
        if c.get("status")!="PASS": reasons.append(f"CASE_{i}_NOT_PASS")
        if not cid or len(cid)>128: reasons.append(f"CASE_{i}_ID_INVALID")
        if not _hex(dg): reasons.append(f"CASE_{i}_REPORT_DIGEST_INVALID")
        else: digests.append(dg)
        if not _hex(case_source): reasons.append(f"CASE_{i}_SOURCE_REPORT_SHA256_INVALID")
        else: case_sources.append(case_source)
    matrix=validate_case_ids(ids)
    if matrix["duplicates"]: reasons.append("DUPLICATE_RUNTIME_CASE_ID")
    if matrix["missing"]: reasons.append("RUNTIME_CASE_MATRIX_MISSING_REQUIRED")
    if matrix["unexpected"]: reasons.append("RUNTIME_CASE_MATRIX_UNEXPECTED_ID")
    if not matrix["valid"]: reasons.append("RUNTIME_CASE_MATRIX_EXACT_SET_REQUIRED")
    if len(set(digests))!=len(digests): reasons.append("DUPLICATE_RUNTIME_REPORT_DIGEST")
    if case_sources and len(set(case_sources))!=1: reasons.append("RUNTIME_CASE_SOURCE_REPORT_MISMATCH")
    if _hex(source_cert) and any(x!=source_cert for x in case_sources): reasons.append("RUNTIME_CASE_SOURCE_REPORT_MISMATCH")
    if len(case_sources)!=len(cases): reasons.append("RUNTIME_CASE_SOURCE_REPORT_INCOMPLETE")
    reasons=sorted(set(reasons)); ok=not reasons; trust_anchor_match=_hex(expected_trust) and observed_trust==expected_trust
    provenance={"raw_packet_sha256":raw,"package_zip_sha256":pkg,"release_manifest_sha256":man,
                "source_certification_report_sha256":source_cert,
                "trust_snapshot_sha256":observed_trust,"expected_trust_snapshot_sha256":expected_trust,
                "signature_sha256":signer_trust.get("signature_sha256",""),"certificate_sha256":signer_trust.get("certificate_sha256",""),
                "signer_key_id_ref":signer_trust.get("signer_key_id_ref",""),"signed_payload_sha256":signer_trust.get("signed_payload_sha256",""),
                "case_report_sha256":sorted(digests),"case_source_report_sha256":sorted(set(case_sources)),"required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS)}
    digest=_sha(_stable({"baseline":current_cockpit_baseline,"verified":ok,"provenance":provenance,"reasons":reasons}))
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_REVIEW_PACKET_INGEST",
            "real_packet_verified":ok,"ingest_status":"VERIFIED_REAL_PACKET" if ok else "QUARANTINE","reasons":reasons,
            "cockpit_baseline":current_cockpit_baseline,"case_matrix_complete":ok and len(digests)==REQUIRED_CASE_COUNT,
            "case_count":len(cases),"required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"case_matrix":matrix,
            "signer_trust":signer_trust,"trust_anchor_match":trust_anchor_match,"provenance":provenance,"import_digest":digest,
            "windows_runtime_certified":False,"external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,
            "automatic_production_certification":False,"production_score_mutation_authorized":False,"raw_evidence_rewritten":False}

def _proof_packet(now,h,ids):
    source_ref="c"*64
    base={"source_classification":SOURCE_CLASSIFICATION,"synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
       "package_zip_sha256":"a"*64,"release_manifest_sha256":"b"*64,"source_certification_report_sha256":source_ref,
       "cockpit_baseline":COCKPIT_BASELINE,"capture_utc":now.isoformat(),
       "nonce":"nonce-012345","run_id":"run-01234567","report_id":"report-012345",
       "case_results":[{"case_id":cid,"status":"PASS","report_sha256":h(str(i)),"source_report_sha256":source_ref} for i,cid in enumerate(ids)]}
    packet=synthetic_signed_packet(base); packet["signer"].pop("synthetic_fixture",None); return packet

def _child_result(name, result):
    summary=result.get("summary") if isinstance(result.get("summary"),dict) else {}
    passed=int(summary.get("pass") or 0); failed=int(summary.get("fail") or 0); total=int(summary.get("total") or 0)
    ok=result.get("verdict")=="PASS" and failed==0 and total>0
    return {"name":name,"ok":ok,"pass":passed,"fail":failed,"total":total,"summary":summary,"groups":result.get("groups") or {}}

def synthetic_proof():
    now=datetime.now(timezone.utc); h=lambda s:hashlib.sha256(s.encode()).hexdigest(); p=_proof_packet(now,h,REQUIRED_RUNTIME_CASE_IDS)
    anchor=p["trust_snapshot"]["trust_snapshot_sha256"]
    kw=dict(raw_packet_sha256="e"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor,now=now)
    good=verify_packet(p,**kw)
    fake=_proof_packet(now,h,[f"case-{i}" for i in range(7)])
    fake_result=verify_packet(fake,raw_packet_sha256="2"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,
                              expected_trust_snapshot_sha256=fake["trust_snapshot"]["trust_snapshot_sha256"],now=now)
    unapproved=_proof_packet(now,h,REQUIRED_RUNTIME_CASE_IDS)
    unapproved_result=verify_packet(unapproved,raw_packet_sha256="3"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,
                                   expected_trust_snapshot_sha256=anchor,now=now)
    missing_anchor=verify_packet(p,raw_packet_sha256="4"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,
                                 expected_trust_snapshot_sha256="",now=now)
    unsigned=json.loads(json.dumps(p)); unsigned["signer"]={"status":"VALID","signer_ref":"fake-self-declared","signature_sha256":"c"*64}
    unsigned_result=verify_packet(unsigned,**kw)
    tampered=json.loads(json.dumps(p)); tampered["package_zip_sha256"]="f"*64
    tampered_result=verify_packet(tampered,raw_packet_sha256="1"*64,expected_package_sha256="f"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor,now=now)
    missing_source=json.loads(json.dumps(p)); missing_source.pop("source_certification_report_sha256",None)
    missing_source_result=verify_packet(missing_source,raw_packet_sha256="5"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor,now=now)
    source_mismatch=json.loads(json.dumps(p)); source_mismatch["case_results"][0]["source_report_sha256"]="d"*64
    source_mismatch_result=verify_packet(source_mismatch,raw_packet_sha256="6"*64,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor,now=now)
    bad=json.loads(json.dumps(p)); bad["synthetic"]=True; syn=verify_packet(bad,**kw)
    old=json.loads(json.dumps(p)); old["cockpit_baseline"]="1.3.27"; drift=verify_packet(old,**kw)
    replay=verify_packet(p,seen={"packet_digests":["e"*64]},**kw)
    checks={"real_exact_7_of_7_verified":good["real_packet_verified"],"cryptographic_signer_trust_verified":good["signer_trust"]["valid"],
            "independent_trust_anchor_match":good["trust_anchor_match"],"unapproved_self_anchored_trust_rejected":"TRUST_ANCHOR_MISMATCH" in unapproved_result["reasons"],
            "missing_trust_anchor_rejected":"EXPECTED_TRUST_SNAPSHOT_SHA256_REQUIRED" in missing_anchor["reasons"],
            "self_declared_signer_rejected":"CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED" in unsigned_result["reasons"],
            "signed_payload_tamper_rejected":"CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED" in tampered_result["reasons"],
            "source_certification_hash_required":"SOURCE_CERTIFICATION_REPORT_SHA256_REQUIRED" in missing_source_result["reasons"],
            "case_source_mismatch_rejected":"RUNTIME_CASE_SOURCE_REPORT_MISMATCH" in source_mismatch_result["reasons"],
            "arbitrary_7_ids_rejected":"RUNTIME_CASE_MATRIX_EXACT_SET_REQUIRED" in fake_result["reasons"],
            "missing_required_ids_reported":"RUNTIME_CASE_MATRIX_MISSING_REQUIRED" in fake_result["reasons"],
            "unexpected_ids_reported":"RUNTIME_CASE_MATRIX_UNEXPECTED_ID" in fake_result["reasons"],
            "ingest_never_certifies":not good["windows_runtime_certified"],"ingest_never_promotes":not good["production_score_promotion_eligible"],
            "synthetic_rejected":"SYNTHETIC_EVIDENCE_REJECTED" in syn["reasons"],
            "baseline_drift_rejected":"COCKPIT_BASELINE_CHANGED_OR_STALE" in drift["reasons"],"replay_rejected":"DUPLICATE_PACKET_DIGEST" in replay["reasons"]}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)

    from HMS_Codex_ExternalWindowsEvidenceAdversarialFixtures import synthetic_proof as adversarial_fixture_proof
    from HMS_Codex_ExternalWindowsSourceBindingProof import synthetic_proof as source_binding_proof
    children=[_child_result("adversarial",adversarial_fixture_proof()),_child_result("source_binding",source_binding_proof())]
    core_fail=len(tests)-n; child_pass=sum(x["pass"] for x in children); child_fail=sum(x["fail"] for x in children)
    missing_child=sum(1 for x in children if x["total"]<=0); all_children=all(x["ok"] for x in children)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"EXTERNAL_WINDOWS_REVIEW_PACKET_INGEST_PROOF",
            "verdict":"PASS" if core_fail==0 and all_children else "FAIL",
            "summary":{"pass":n+child_pass,"fail":core_fail+child_fail+missing_child,"total":len(tests)+sum(x["total"] for x in children)+missing_child},
            "core_summary":{"pass":n,"fail":core_fail,"total":len(tests)},
            "child_proofs":{x["name"]:{"summary":x["summary"],"groups":x["groups"],"ok":x["ok"]} for x in children},
            "required_case_ids":list(REQUIRED_RUNTIME_CASE_IDS),"tests":tests,"synthetic_fixture_only":True,
            "windows_runtime_certified":False,"production_score_promotion_eligible":False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--proof",action="store_true"); ap.add_argument("--packet")
    ap.add_argument("--expected-package-sha256"); ap.add_argument("--expected-manifest-sha256"); ap.add_argument("--expected-trust-snapshot-sha256")
    ap.add_argument("--cockpit-baseline",default=COCKPIT_BASELINE); ap.add_argument("--output"); a=ap.parse_args()
    if a.proof: out=synthetic_proof()
    else:
        if not(a.packet and a.expected_package_sha256 and a.expected_manifest_sha256 and a.expected_trust_snapshot_sha256):
            ap.error("packet, expected package/manifest digests and expected trust snapshot digest required")
        path=Path(a.packet); raw=path.read_bytes(); packet=json.loads(raw.decode("utf-8-sig"))
        out=verify_packet(packet,raw_packet_sha256=_sha(raw),expected_package_sha256=a.expected_package_sha256,
                          expected_manifest_sha256=a.expected_manifest_sha256,expected_trust_snapshot_sha256=a.expected_trust_snapshot_sha256,
                          current_cockpit_baseline=a.cockpit_baseline)
    text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text); return 0 if (out.get("verdict")=="PASS" if a.proof else out["real_packet_verified"]) else 2
if __name__=="__main__": raise SystemExit(main())
