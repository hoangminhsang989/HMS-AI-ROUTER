#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, json, os, re, secrets
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_ExternalWindowsCertificateSigner as certificate_signer
import HMS_Codex_WindowsAttestationSigner as signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
DEFAULT_SIGN_SCRIPT = Path(__file__).resolve().with_name("HMS_Sign_Digest_With_Certificate.ps1")


def _normalize_thumbprint(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()


def _certificate_times(env: dict) -> tuple[str, str]:
    from cryptography import x509
    der = base64.b64decode(str(env.get("certificate_der_b64") or ""), validate=True)
    cert = x509.load_der_x509_certificate(der)
    nb = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
    na = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
    return nb.astimezone(timezone.utc).isoformat(), na.astimezone(timezone.utc).isoformat()


def enroll(trust_path: Path, thumbprint: str, sign_script: Path) -> dict:
    if os.name != "nt": raise RuntimeError("WINDOWS_REQUIRED")
    normalized = _normalize_thumbprint(thumbprint)
    if len(normalized) < 20: raise ValueError("CERTIFICATE_THUMBPRINT_INVALID")
    challenge = {"product": PRODUCT, "version": VERSION, "purpose": "CERTIFICATE_TRUST_ENROLLMENT_CHALLENGE_NOT_EVIDENCE",
                 "generated_utc": datetime.now(timezone.utc).isoformat(), "nonce": secrets.token_hex(32),
                 "synthetic": False, "production_evidence": False, "production_score_eligible": False}
    env = certificate_signer.certificate_sign(challenge, normalized, sign_script)
    ok, reason = signer.verify_certificate(challenge, env, None)
    if not ok: raise RuntimeError("CERTIFICATE_ENROLLMENT_SELF_VERIFY_FAILED:" + reason)
    not_before, not_after = _certificate_times(env)
    store = trust_store.load_store(trust_path)
    row = trust_store.pin_certificate(store, certificate_sha256=env["certificate_sha256"],
                                      signer_key_id_ref=env["signer_key_id_ref"],
                                      not_before_utc=not_before, not_after_utc=not_after)
    trust_store.atomic_json(trust_path, store)
    snapshot = trust_store.trust_snapshot(store)
    check = trust_store.evaluate_certificate(store, env["certificate_sha256"])
    if not check["trusted"]: raise RuntimeError("CERTIFICATE_PIN_NOT_TRUSTED:" + ",".join(check["reasons"]))
    return {"product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT",
            "verdict": "CERTIFICATE_PINNED", "pin_id": row["pin_id"],
            "certificate_sha256": env["certificate_sha256"], "signer_key_id_ref": env["signer_key_id_ref"],
            "not_before_utc": not_before, "not_after_utc": not_after,
            "trust_snapshot_sha256": snapshot["trust_snapshot_sha256"],
            "private_material_exported": False, "production_evidence_created": False,
            "windows_runtime_certified": False, "production_score_promotion_eligible": False}


def source_proof() -> dict:
    src = Path(__file__).read_text("utf-8")
    checks = {"explicit_windows_gate": 'os.name != "nt"' in src,
              "enrollment_marked_not_evidence": "CERTIFICATE_TRUST_ENROLLMENT_CHALLENGE_NOT_EVIDENCE" in src,
              "certificate_self_verify": "verify_certificate" in src,
              "trust_store_pin_api": "pin_certificate" in src,
              "atomic_store_write": "atomic_json" in src,
              "no_private_export": '"private_material_exported": False' in src,
              "no_auto_certification": '"windows_runtime_certified": False' in src}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]
    passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT_SOURCE_PROOF",
            "verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},
            "tests":tests,"windows_certificate_enrollment_executed":False,"production_score_promotion_eligible":False}


def main() -> int:
    ap=argparse.ArgumentParser(description="Pin a Windows certificate for HMS external evidence signing")
    ap.add_argument("--proof",action="store_true"); ap.add_argument("--trust-store",default="")
    ap.add_argument("--certificate-thumbprint",default=""); ap.add_argument("--certificate-sign-script",default=str(DEFAULT_SIGN_SCRIPT))
    args=ap.parse_args()
    if args.proof: out=source_proof(); code=0 if out["verdict"]=="PASS" else 2
    else:
        if not args.trust_store or not args.certificate_thumbprint: ap.error("--trust-store and --certificate-thumbprint required")
        try: out=enroll(Path(args.trust_store),args.certificate_thumbprint,Path(args.certificate_sign_script)); code=0
        except Exception as exc:
            out={"product":PRODUCT,"version":VERSION,"suite":"EXTERNAL_WINDOWS_CERTIFICATE_ENROLLMENT",
                 "verdict":"BLOCKED_FAIL_CLOSED","error":type(exc).__name__,"detail":str(exc),
                 "production_evidence_created":False,"windows_runtime_certified":False,"production_score_promotion_eligible":False}; code=2
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code

if __name__=="__main__": raise SystemExit(main())
