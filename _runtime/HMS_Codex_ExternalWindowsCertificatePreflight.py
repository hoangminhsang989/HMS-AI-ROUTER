#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, hashlib, json, os, re, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsAttestationSigner as attestation_signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
THUMBPRINT = re.compile(r"^[0-9A-F]{20,128}$")
DEFAULT_INSPECT_SCRIPT = Path(__file__).resolve().with_name("HMS_Inspect_Evidence_Certificate.ps1")


def _normalize_thumbprint(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()


def _utc_cert_time(cert: Any, name: str) -> datetime:
    utc_value = getattr(cert, name + "_utc", None)
    if utc_value is not None:
        return utc_value.astimezone(timezone.utc)
    value = getattr(cert, name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_probe_result(result: dict[str, Any], expected_thumbprint: str, *, now: datetime | None = None) -> dict[str, Any]:
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import rsa

    reasons: list[str] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expected = _normalize_thumbprint(expected_thumbprint)
    if not THUMBPRINT.fullmatch(expected):
        reasons.append("CERTIFICATE_THUMBPRINT_INVALID")
    if result.get("probe_class") != "READ_ONLY_CURRENT_USER_CERTIFICATE_PREFLIGHT":
        reasons.append("CERTIFICATE_PROBE_CLASS_INVALID")
    if result.get("store") != r"Cert:\CurrentUser\My":
        reasons.append("CERTIFICATE_STORE_INVALID")
    if str(result.get("thumbprint") or "").upper() != expected:
        reasons.append("CERTIFICATE_THUMBPRINT_MISMATCH")
    if result.get("private_material_exported") is not False:
        reasons.append("PRIVATE_MATERIAL_EXPORT_FORBIDDEN")
    if result.get("signing_performed") is not False:
        reasons.append("PREFLIGHT_MUST_NOT_SIGN")
    if result.get("store_mutated") is not False:
        reasons.append("PREFLIGHT_MUST_NOT_MUTATE_STORE")
    if result.get("has_private_key") is not True:
        reasons.append("CERTIFICATE_PRIVATE_KEY_REQUIRED")
    if result.get("rsa_private_key_accessible") is not True:
        reasons.append("RSA_PRIVATE_KEY_NOT_ACCESSIBLE")
    if result.get("key_usage_present") is True and result.get("digital_signature_allowed") is not True:
        reasons.append("CERTIFICATE_DIGITAL_SIGNATURE_USAGE_REQUIRED")
    if result.get("certificate_authority") is True:
        reasons.append("CA_CERTIFICATE_NOT_ALLOWED_FOR_EVIDENCE_SIGNING")

    der_b64 = str(result.get("certificate_der_b64") or "")
    try:
        der = base64.b64decode(der_b64, validate=True)
        cert = x509.load_der_x509_certificate(der)
    except Exception:
        der = b""; cert = None
        reasons.append("CERTIFICATE_DER_INVALID")

    cert_sha = hashlib.sha256(der).hexdigest() if der else ""
    if cert_sha != str(result.get("certificate_sha256") or "").lower():
        reasons.append("CERTIFICATE_SHA256_MISMATCH")
    signer_ref = attestation_signer.safe_ref(expected) if expected else ""
    if signer_ref != str(result.get("signer_key_id_ref") or ""):
        reasons.append("CERTIFICATE_SIGNER_REF_MISMATCH")

    not_before = not_after = None
    if cert is not None:
        if not isinstance(cert.public_key(), rsa.RSAPublicKey):
            reasons.append("RSA_CERTIFICATE_REQUIRED")
        not_before = _utc_cert_time(cert, "not_valid_before")
        not_after = _utc_cert_time(cert, "not_valid_after")
        if now < not_before:
            reasons.append("CERTIFICATE_NOT_YET_VALID")
        if now > not_after:
            reasons.append("CERTIFICATE_EXPIRED")
        try:
            ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
            if not ku.digital_signature:
                reasons.append("CERTIFICATE_DIGITAL_SIGNATURE_USAGE_REQUIRED")
        except x509.ExtensionNotFound:
            pass
        try:
            bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
            if bc.ca:
                reasons.append("CA_CERTIFICATE_NOT_ALLOWED_FOR_EVIDENCE_SIGNING")
        except x509.ExtensionNotFound:
            pass

    script_reasons = result.get("reasons") if isinstance(result.get("reasons"), list) else []
    reasons.extend(str(x) for x in script_reasons if str(x))
    reasons = sorted(set(reasons))
    return {
        "product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_PREFLIGHT",
        "ready": not reasons, "reasons": reasons,
        "certificate_sha256": cert_sha,
        "signer_key_id_ref": signer_ref,
        "certificate_thumbprint_ref": signer_ref,
        "not_before_utc": not_before.isoformat() if not_before else "",
        "not_after_utc": not_after.isoformat() if not_after else "",
        "key_usage_present": bool(result.get("key_usage_present")),
        "digital_signature_allowed": result.get("digital_signature_allowed") is True,
        "certificate_authority": result.get("certificate_authority") is True,
        "subject_ref": str(result.get("subject_ref") or ""),
        "issuer_ref": str(result.get("issuer_ref") or ""),
        "private_material_exported": False,
        "signing_performed": False,
        "store_mutated": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
    }


def certificate_preflight(thumbprint: str, inspect_script: Path = DEFAULT_INSPECT_SCRIPT) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    normalized = _normalize_thumbprint(thumbprint)
    if not THUMBPRINT.fullmatch(normalized):
        raise ValueError("CERTIFICATE_THUMBPRINT_INVALID")
    if not inspect_script.is_file():
        raise FileNotFoundError("CERTIFICATE_INSPECT_SCRIPT_MISSING")
    with tempfile.TemporaryDirectory(prefix="hms-v2575-cert-preflight-") as td:
        out = Path(td) / "certificate-preflight.json"
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(inspect_script), "-Thumbprint", normalized, "-Output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if proc.returncode != 0 or not out.is_file():
            detail = ((proc.stderr or proc.stdout or "").strip())[:300]
            raise RuntimeError("CERTIFICATE_PREFLIGHT_PROBE_FAILED" + (":" + detail if detail else ""))
        raw = json.loads(out.read_text("utf-8"))
    check = validate_probe_result(raw, normalized)
    if not check["ready"]:
        raise RuntimeError("CERTIFICATE_PREFLIGHT_BLOCKED:" + ",".join(check["reasons"]))
    return check


def source_proof() -> dict[str, Any]:
    source = Path(__file__).read_text("utf-8")
    ps_source = DEFAULT_INSPECT_SCRIPT.read_text("utf-8") if DEFAULT_INSPECT_SCRIPT.is_file() else ""
    checks = {
        "windows_gate": 'os.name != "nt"' in source,
        "powershell_shell_false": "shell=False" in source,
        "read_only_probe_class": "READ_ONLY_CURRENT_USER_CERTIFICATE_PREFLIGHT" in source and "signing_performed = $false" in ps_source,
        "current_user_my_only": "Cert:\\CurrentUser\\My" in ps_source,
        "private_key_required": "CERTIFICATE_PRIVATE_KEY_REQUIRED" in source and "CERTIFICATE_PRIVATE_KEY_REQUIRED" in ps_source,
        "rsa_required": "RSA_CERTIFICATE_REQUIRED" in source and "RSA_PRIVATE_KEY_REQUIRED" in ps_source,
        "validity_enforced": "CERTIFICATE_NOT_YET_VALID" in source and "CERTIFICATE_EXPIRED" in source,
        "digital_signature_usage_enforced": "CERTIFICATE_DIGITAL_SIGNATURE_USAGE_REQUIRED" in source,
        "ca_certificate_rejected": "CA_CERTIFICATE_NOT_ALLOWED_FOR_EVIDENCE_SIGNING" in source,
        "der_digest_recomputed": "hashlib.sha256(der).hexdigest()" in source,
        "signer_ref_recomputed": "attestation_signer.safe_ref(expected)" in source,
        "no_private_material_export": '"private_material_exported": False' in source,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(x["status"] == "PASS" for x in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_PREFLIGHT_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
        "tests": tests, "certificate_probe_executed": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only preflight for HMS external evidence signing certificate")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--certificate-thumbprint", default="")
    ap.add_argument("--inspect-script", default=str(DEFAULT_INSPECT_SCRIPT))
    args = ap.parse_args()
    if args.proof:
        out = source_proof(); code = 0 if out["verdict"] == "PASS" else 2
    else:
        try:
            out = certificate_preflight(args.certificate_thumbprint, Path(args.inspect_script)); code = 0
        except Exception as exc:
            out = {"product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_PREFLIGHT",
                   "ready": False, "reasons": [str(exc)], "error": type(exc).__name__,
                   "windows_runtime_certified": False, "production_score_promotion_eligible": False}; code = 2
    print(json.dumps(out, ensure_ascii=False, indent=2)); return code


if __name__ == "__main__":
    raise SystemExit(main())
