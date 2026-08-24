#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, hashlib, hmac, json, os, secrets
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsAttestationSigner as windows_signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
SCHEMA_VERSION = 1


def _stable(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_digest(payload: Any, purpose: str) -> str:
    body = {"schema_version": SCHEMA_VERSION, "purpose": str(purpose), "payload": payload}
    return hashlib.sha256(_stable(body)).hexdigest()


def _seal_with_key(payload: Any, purpose: str, key: bytes, key_ref: str) -> dict[str, Any]:
    digest = _payload_digest(payload, purpose)
    sig = hmac.new(key, digest.encode("ascii"), hashlib.sha256).digest()
    return {
        "schema_version": SCHEMA_VERSION,
        "seal_class": "WINDOWS_REVIEWER_LOCAL_DPAPI_HMAC",
        "algorithm": "HMAC-SHA256-DPAPI-MACHINE",
        "purpose": str(purpose),
        "payload_sha256": digest,
        "signature_b64": base64.b64encode(sig).decode("ascii"),
        "key_id_ref": str(key_ref),
        "private_material_exported": False,
    }


def _verify_with_key(payload: Any, seal: dict[str, Any], purpose: str, key: bytes, key_ref: str) -> dict[str, Any]:
    reasons: list[str] = []
    if seal.get("schema_version") != SCHEMA_VERSION:
        reasons.append("LOCAL_SEAL_SCHEMA_INVALID")
    if seal.get("seal_class") != "WINDOWS_REVIEWER_LOCAL_DPAPI_HMAC":
        reasons.append("LOCAL_SEAL_CLASS_INVALID")
    if seal.get("algorithm") != "HMAC-SHA256-DPAPI-MACHINE":
        reasons.append("LOCAL_SEAL_ALGORITHM_INVALID")
    if seal.get("purpose") != str(purpose):
        reasons.append("LOCAL_SEAL_PURPOSE_MISMATCH")
    if seal.get("private_material_exported") is not False:
        reasons.append("LOCAL_SEAL_PRIVATE_MATERIAL_FLAG_INVALID")
    if str(seal.get("key_id_ref") or "") != str(key_ref):
        reasons.append("LOCAL_SEAL_KEY_REF_MISMATCH")
    digest = _payload_digest(payload, purpose)
    if str(seal.get("payload_sha256") or "").lower() != digest:
        reasons.append("LOCAL_SEAL_PAYLOAD_DIGEST_MISMATCH")
    try:
        actual = base64.b64decode(str(seal.get("signature_b64") or ""), validate=True)
    except Exception:
        actual = b""; reasons.append("LOCAL_SEAL_SIGNATURE_B64_INVALID")
    expected = hmac.new(key, digest.encode("ascii"), hashlib.sha256).digest()
    if not actual or not hmac.compare_digest(actual, expected):
        reasons.append("LOCAL_SEAL_SIGNATURE_INVALID")
    return {"valid": not reasons, "reasons": sorted(set(reasons)), "payload_sha256": digest,
            "purpose": str(purpose), "key_id_ref": str(key_ref)}


def seal_payload(payload: Any, *, purpose: str, key_path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    if not str(purpose).strip():
        raise ValueError("SEAL_PURPOSE_REQUIRED")
    key = windows_signer.ensure_dpapi_key(key_path)
    key_ref = windows_signer.safe_ref(str(key_path.resolve()))
    return _seal_with_key(payload, purpose, key, key_ref)


def verify_payload(payload: Any, seal: dict[str, Any], *, purpose: str, key_path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    if not key_path.is_file():
        return {"valid": False, "reasons": ["LOCAL_SEAL_KEY_MISSING"], "purpose": str(purpose), "key_id_ref": ""}
    try:
        key = windows_signer.ensure_dpapi_key(key_path)
    except Exception:
        return {"valid": False, "reasons": ["LOCAL_SEAL_KEY_UNAVAILABLE"], "purpose": str(purpose), "key_id_ref": ""}
    key_ref = windows_signer.safe_ref(str(key_path.resolve()))
    return _verify_with_key(payload, seal if isinstance(seal, dict) else {}, purpose, key, key_ref)


def synthetic_proof() -> dict[str, Any]:
    key = secrets.token_bytes(32); key_ref = "ref-" + "1" * 24
    payload = {"report": "verified", "digest": "a" * 64}
    seal = _seal_with_key(payload, "TEST_REVIEWER_SEAL", key, key_ref)
    good = _verify_with_key(payload, seal, "TEST_REVIEWER_SEAL", key, key_ref)
    tampered = _verify_with_key(dict(payload, report="tampered"), seal, "TEST_REVIEWER_SEAL", key, key_ref)
    wrong_purpose = _verify_with_key(payload, seal, "OTHER_PURPOSE", key, key_ref)
    wrong_key = _verify_with_key(payload, seal, "TEST_REVIEWER_SEAL", secrets.token_bytes(32), key_ref)
    checks = {
        "roundtrip_valid": good["valid"],
        "payload_tamper_rejected": not tampered["valid"] and "LOCAL_SEAL_PAYLOAD_DIGEST_MISMATCH" in tampered["reasons"],
        "purpose_substitution_rejected": not wrong_purpose["valid"] and "LOCAL_SEAL_PURPOSE_MISMATCH" in wrong_purpose["reasons"],
        "wrong_key_rejected": not wrong_key["valid"] and "LOCAL_SEAL_SIGNATURE_INVALID" in wrong_key["reasons"],
        "production_api_windows_only": os.name == "nt" or _nonwindows_rejected(),
        "private_material_not_exported": seal["private_material_exported"] is False and "key" not in seal,
        "dpapi_machine_key_api_used": "ensure_dpapi_key" in seal_payload.__code__.co_names,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "REVIEWER_LOCAL_INTEGRITY_SEAL_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
        "tests": tests, "real_dpapi_key_created": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def _nonwindows_rejected() -> bool:
    try:
        seal_payload({}, purpose="X", key_path=Path("unused")); return False
    except RuntimeError as exc:
        return str(exc) == "WINDOWS_REQUIRED"
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--proof", action="store_true"); args = ap.parse_args()
    out = synthetic_proof(); print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
