#!/usr/bin/env python3
from __future__ import annotations

import base64, hashlib, json, re
from datetime import datetime, timedelta, timezone
from typing import Any

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_WindowsAttestationSigner as attestation_signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXTERNAL_SIGNER_CLASS = "WINDOWS_CERTIFICATE_SIGNATURE"


def _hex64(value: Any) -> bool:
    return HEX64.fullmatch(str(value or "").lower()) is not None


def _parse_time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def signing_payload(packet: dict[str, Any]) -> dict[str, Any]:
    """Every promotion-relevant packet field is signed except the signature itself."""
    return {k: v for k, v in packet.items() if k != "signer"}


def validate_trust_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(snapshot, dict):
        return {"valid": False, "reasons": ["TRUST_SNAPSHOT_SHAPE_INVALID"], "snapshot_sha256": ""}
    claimed = str(snapshot.get("trust_snapshot_sha256") or "").lower()
    body = {k: v for k, v in snapshot.items() if k != "trust_snapshot_sha256"}
    calculated = trust_store.sha(trust_store.stable(body))
    if not _hex64(claimed) or claimed != calculated:
        reasons.append("TRUST_SNAPSHOT_DIGEST_MISMATCH")
    if snapshot.get("product") != trust_store.PRODUCT:
        reasons.append("TRUST_SNAPSHOT_PRODUCT_INVALID")
    if snapshot.get("version") != trust_store.VERSION:
        reasons.append("TRUST_SNAPSHOT_VERSION_INVALID")
    if snapshot.get("schema_version") != trust_store.SCHEMA_VERSION:
        reasons.append("TRUST_SNAPSHOT_SCHEMA_INVALID")
    if snapshot.get("private_material_exported") is not False:
        reasons.append("TRUST_SNAPSHOT_PRIVATE_MATERIAL_FORBIDDEN")
    if not isinstance(snapshot.get("certificates"), list):
        reasons.append("TRUST_SNAPSHOT_CERTIFICATES_INVALID")
    if not isinstance(snapshot.get("dpapi_keys"), list):
        reasons.append("TRUST_SNAPSHOT_DPAPI_KEYS_INVALID")
    return {"valid": not reasons, "reasons": sorted(set(reasons)), "snapshot_sha256": claimed,
            "calculated_snapshot_sha256": calculated}


def _certificate_object_gate(env: dict[str, Any], captured: datetime) -> list[str]:
    reasons: list[str] = []
    try:
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID
        der = base64.b64decode(str(env.get("certificate_der_b64") or ""), validate=True)
        cert = x509.load_der_x509_certificate(der)
        actual_sha = hashlib.sha256(der).hexdigest()
        if str(env.get("certificate_sha256") or "").lower() != actual_sha:
            reasons.append("CERTIFICATE_DIGEST_MISMATCH")
        nb = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
        na = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
        if captured < nb:
            reasons.append("CERTIFICATE_X509_NOT_YET_VALID")
        if captured > na:
            reasons.append("CERTIFICATE_X509_EXPIRED")
        try:
            usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
            if not usage.digital_signature:
                reasons.append("CERTIFICATE_DIGITAL_SIGNATURE_USAGE_REQUIRED")
        except x509.ExtensionNotFound:
            pass
    except Exception:
        reasons.append("CERTIFICATE_X509_INVALID")
    return reasons


def verify_external_signer_trust(packet: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    env = packet.get("signer") if isinstance(packet.get("signer"), dict) else {}
    snapshot = packet.get("trust_snapshot") if isinstance(packet.get("trust_snapshot"), dict) else {}
    captured = _parse_time(packet.get("capture_utc"))
    snapshot_check = validate_trust_snapshot(snapshot)
    reasons.extend(snapshot_check["reasons"])
    if not captured:
        reasons.append("SIGNATURE_CAPTURE_TIME_INVALID")
    if env.get("signer_class") != EXTERNAL_SIGNER_CLASS:
        reasons.append("EXTERNAL_CERTIFICATE_SIGNER_REQUIRED")
    if env.get("private_material_exported") is not False:
        reasons.append("SIGNER_PRIVATE_MATERIAL_FORBIDDEN")
    cert_sha = str(env.get("certificate_sha256") or "").lower()
    if not _hex64(cert_sha):
        reasons.append("CERTIFICATE_SHA256_INVALID")
    if not str(env.get("signature_b64") or ""):
        reasons.append("CERTIFICATE_SIGNATURE_MISSING")
    if captured and _hex64(cert_sha) and snapshot_check["valid"]:
        public_store = {k: v for k, v in snapshot.items() if k != "trust_snapshot_sha256"}
        trust_eval = trust_store.evaluate_certificate(public_store, cert_sha, now=captured)
        if not trust_eval.get("trusted"):
            reasons.extend(trust_eval.get("reasons") or ["CERTIFICATE_NOT_TRUSTED"])
        row = next((r for r in snapshot.get("certificates") or []
                    if str(r.get("certificate_sha256") or "").lower() == cert_sha), None)
        if row is None:
            reasons.append("CERTIFICATE_NOT_PINNED")
        elif row.get("signer_key_id_ref") != env.get("signer_key_id_ref"):
            reasons.append("SIGNER_TRUST_REF_MISMATCH")
        reasons.extend(_certificate_object_gate(env, captured))
        trusted = trust_store.trusted_certificate_sha256(public_store, now=captured)
        sig_ok, sig_reason = attestation_signer.verify_certificate(signing_payload(packet), env, trusted)
        if not sig_ok:
            reasons.append(sig_reason)
    else:
        trust_eval = {"trusted": False, "reasons": ["TRUST_PREREQUISITES_INVALID"]}
    try:
        signature_sha = hashlib.sha256(base64.b64decode(str(env.get("signature_b64") or ""), validate=True)).hexdigest()
    except Exception:
        signature_sha = ""
        reasons.append("SIGNATURE_BASE64_INVALID")
    reasons = sorted(set(reasons))
    return {"valid": not reasons, "reasons": reasons, "certificate_sha256": cert_sha,
            "signer_key_id_ref": env.get("signer_key_id_ref", ""),
            "signature_sha256": signature_sha,
            "signed_payload_sha256": env.get("signed_payload_sha256", ""),
            "trust_snapshot_sha256": snapshot_check.get("snapshot_sha256", ""),
            "trust_evaluation": trust_eval,
            "certificate_only_external": env.get("signer_class") == EXTERNAL_SIGNER_CLASS,
            "automatic_production_certification": False,
            "production_score_mutation_authorized": False}


def synthetic_signed_packet(base: dict[str, Any]) -> dict[str, Any]:
    """Portable in-memory fixture only. Never production evidence."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    now = _parse_time(base.get("capture_utc")) or datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "HMS v25.75 synthetic external packet proof")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(hours=1)).sign(key, hashes.SHA256()))
    der = cert.public_bytes(serialization.Encoding.DER)
    cert_sha = hashlib.sha256(der).hexdigest()
    signer_ref = attestation_signer.safe_ref("synthetic-external-cert")
    store = trust_store.empty_store()
    trust_store.pin_certificate(store, certificate_sha256=cert_sha, signer_key_id_ref=signer_ref,
                                not_before_utc=(now - timedelta(minutes=5)).isoformat(),
                                not_after_utc=(now + timedelta(hours=1)).isoformat())
    packet = json.loads(json.dumps(base))
    packet["trust_snapshot"] = trust_store.trust_snapshot(store)
    digest = attestation_signer.payload_digest(signing_payload(packet))
    signature = key.sign(digest.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    packet["signer"] = {"schema_version": 1, "signer_class": EXTERNAL_SIGNER_CLASS,
        "algorithm": "RSA-SHA256", "signed_payload_sha256": digest,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
        "signer_key_id_ref": signer_ref, "certificate_der_b64": base64.b64encode(der).decode("ascii"),
        "certificate_sha256": cert_sha, "private_material_exported": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(), "synthetic_fixture": True}
    return packet


def synthetic_proof() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    base = {"product": PRODUCT, "version": VERSION, "capture_utc": now.isoformat(),
            "package_zip_sha256": "a" * 64, "release_manifest_sha256": "b" * 64,
            "case_results": [{"case_id": "host", "status": "PASS", "report_sha256": "c" * 64}]}
    good = synthetic_signed_packet(base)
    valid = verify_external_signer_trust(good)
    tampered = json.loads(json.dumps(good)); tampered["package_zip_sha256"] = "d" * 64
    tam = verify_external_signer_trust(tampered)
    fake = json.loads(json.dumps(good)); fake["signer"] = {"status": "VALID", "signer_ref": "fake-self-declared", "signature_sha256": "e" * 64}
    fake_result = verify_external_signer_trust(fake)
    trust_bad = json.loads(json.dumps(good)); trust_bad["trust_snapshot"]["generation"] += 1
    trust_result = verify_external_signer_trust(trust_bad)
    unpinned = json.loads(json.dumps(good)); unpinned["trust_snapshot"]["certificates"] = []
    body = {k:v for k,v in unpinned["trust_snapshot"].items() if k != "trust_snapshot_sha256"}
    unpinned["trust_snapshot"]["trust_snapshot_sha256"] = trust_store.sha(trust_store.stable(body))
    unpinned_result = verify_external_signer_trust(unpinned)
    checks = {"certificate_packet_valid": valid["valid"],
              "payload_tamper_rejected": not tam["valid"],
              "self_declared_signer_rejected": not fake_result["valid"] and "EXTERNAL_CERTIFICATE_SIGNER_REQUIRED" in fake_result["reasons"],
              "trust_snapshot_tamper_rejected": not trust_result["valid"] and "TRUST_SNAPSHOT_DIGEST_MISMATCH" in trust_result["reasons"],
              "unpinned_certificate_rejected": not unpinned_result["valid"],
              "external_dpapi_not_accepted": EXTERNAL_SIGNER_CLASS != "WINDOWS_LOCAL_MACHINE_DPAPI_HMAC",
              "no_automatic_authority": not valid["automatic_production_certification"] and not valid["production_score_mutation_authorized"]}
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k,v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {"product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_SIGNER_TRUST_CONTRACT_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
            "tests": tests, "synthetic_fixture_only": True,
            "windows_runtime_certified": False, "production_score_promotion_eligible": False}


if __name__ == "__main__":
    result = synthetic_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 2)
