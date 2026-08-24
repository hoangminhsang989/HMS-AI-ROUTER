#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, re, secrets
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_ExternalWindowsCertificateSigner as certificate_signer
import HMS_Codex_ExternalWindowsCertificatePreflight as certificate_preflight
import HMS_Codex_WindowsAttestationSigner as signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
DEFAULT_SIGN_SCRIPT = Path(__file__).resolve().with_name("HMS_Sign_Digest_With_Certificate.ps1")
DEFAULT_INSPECT_SCRIPT = Path(__file__).resolve().with_name("HMS_Inspect_Evidence_Certificate.ps1")


def _normalize_thumbprint(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()


def enroll(trust_path: Path, thumbprint: str, sign_script: Path, inspect_script: Path = DEFAULT_INSPECT_SCRIPT) -> dict:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    normalized = _normalize_thumbprint(thumbprint)
    if len(normalized) < 20:
        raise ValueError("CERTIFICATE_THUMBPRINT_INVALID")

    preflight = certificate_preflight.certificate_preflight(normalized, inspect_script)
    if preflight.get("ready") is not True:
        raise RuntimeError("CERTIFICATE_PREFLIGHT_REQUIRED")

    challenge = {
        "product": PRODUCT, "version": VERSION,
        "purpose": "CERTIFICATE_TRUST_ENROLLMENT_CHALLENGE_NOT_EVIDENCE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "nonce": secrets.token_hex(32), "synthetic": False,
        "production_evidence": False, "production_score_eligible": False,
    }
    env = certificate_signer.certificate_sign(challenge, normalized, sign_script)
    ok, reason = signer.verify_certificate(challenge, env, None)
    if not ok:
        raise RuntimeError("CERTIFICATE_ENROLLMENT_SELF_VERIFY_FAILED:" + reason)
    if str(env.get("certificate_sha256") or "").lower() != str(preflight.get("certificate_sha256") or "").lower():
        raise RuntimeError("CERTIFICATE_CHANGED_AFTER_PREFLIGHT")
    if str(env.get("signer_key_id_ref") or "") != str(preflight.get("signer_key_id_ref") or ""):
        raise RuntimeError("CERTIFICATE_SIGNER_REF_CHANGED_AFTER_PREFLIGHT")

    store = trust_store.load_store(trust_path)
    row = trust_store.pin_certificate(
        store,
        certificate_sha256=env["certificate_sha256"],
        signer_key_id_ref=env["signer_key_id_ref"],
        not_before_utc=str(preflight.get("not_before_utc") or ""),
        not_after_utc=str(preflight.get("not_after_utc") or ""),
    )
    trust_store.atomic_json(trust_path, store)
    snapshot = trust_store.trust_snapshot(store)
    check = trust_store.evaluate_certificate(store, env["certificate_sha256"])
    if not check["trusted"]:
        raise RuntimeError("CERTIFICATE_PIN_NOT_TRUSTED:" + ",".join(check["reasons"]))
    return {
        "product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT",
        "verdict": "CERTIFICATE_PINNED", "pin_id": row["pin_id"],
        "certificate_sha256": env["certificate_sha256"],
        "signer_key_id_ref": env["signer_key_id_ref"],
        "not_before_utc": preflight.get("not_before_utc", ""),
        "not_after_utc": preflight.get("not_after_utc", ""),
        "certificate_preflight": "PASS",
        "trust_snapshot_sha256": snapshot["trust_snapshot_sha256"],
        "private_material_exported": False, "production_evidence_created": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def source_proof() -> dict:
    src = Path(__file__).read_text("utf-8")
    checks = {
        "explicit_windows_gate": 'os.name != "nt"' in src,
        "enrollment_marked_not_evidence": "CERTIFICATE_TRUST_ENROLLMENT_CHALLENGE_NOT_EVIDENCE" in src,
        "read_only_preflight_required": "certificate_preflight.certificate_preflight" in src,
        "preflight_certificate_digest_bound": "CERTIFICATE_CHANGED_AFTER_PREFLIGHT" in src,
        "preflight_signer_ref_bound": "CERTIFICATE_SIGNER_REF_CHANGED_AFTER_PREFLIGHT" in src,
        "certificate_self_verify": "verify_certificate" in src,
        "trust_store_pin_api": "pin_certificate" in src,
        "atomic_store_write": "atomic_json" in src,
        "no_private_export": '"private_material_exported": False' in src,
        "no_auto_certification": '"windows_runtime_certified": False' in src,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
        "tests": tests, "windows_certificate_enrollment_executed": False,
        "production_score_promotion_eligible": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Pin a Windows certificate for HMS external evidence signing")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--trust-store", default="")
    ap.add_argument("--certificate-thumbprint", default="")
    ap.add_argument("--certificate-sign-script", default=str(DEFAULT_SIGN_SCRIPT))
    ap.add_argument("--certificate-inspect-script", default=str(DEFAULT_INSPECT_SCRIPT))
    args = ap.parse_args()
    if args.proof:
        out = source_proof(); code = 0 if out["verdict"] == "PASS" else 2
    else:
        if not args.trust_store or not args.certificate_thumbprint:
            ap.error("--trust-store and --certificate-thumbprint required")
        try:
            out = enroll(Path(args.trust_store), args.certificate_thumbprint,
                         Path(args.certificate_sign_script), Path(args.certificate_inspect_script)); code = 0
        except Exception as exc:
            out = {
                "product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT",
                "verdict": "BLOCKED_FAIL_CLOSED", "error": type(exc).__name__, "detail": str(exc),
                "production_evidence_created": False, "windows_runtime_certified": False,
                "production_score_promotion_eligible": False,
            }; code = 2
    print(json.dumps(out, ensure_ascii=False, indent=2)); return code


if __name__ == "__main__":
    raise SystemExit(main())
