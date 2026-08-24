#!/usr/bin/env python3
from __future__ import annotations

import json, os, subprocess, tempfile
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsAttestationSigner as signer

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"


def certificate_sign(attestation: dict[str, Any], thumbprint: str, script_path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    digest = signer.payload_digest(attestation)
    with tempfile.TemporaryDirectory(prefix="hms-v2575-external-cert-sign-") as td:
        inp = Path(td) / "input.txt"
        out = Path(td) / "output.json"
        inp.write_text(digest, encoding="ascii")
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(script_path), "-Thumbprint", thumbprint, "-DigestFile", str(inp), "-Output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError("CERTIFICATE_SIGNER_FAILED")
        result = json.loads(out.read_text("utf-8"))
    env = {"schema_version": 1, "signer_class": "WINDOWS_CERTIFICATE_SIGNATURE",
           "algorithm": result.get("algorithm", "RSA-SHA256"), "signed_payload_sha256": digest,
           "signature_b64": result.get("signature_b64", ""),
           "signer_key_id_ref": signer.safe_ref(str(result.get("thumbprint") or thumbprint)),
           "certificate_der_b64": result.get("certificate_der_b64", ""),
           "certificate_sha256": str(result.get("certificate_sha256") or "").lower(),
           "private_material_exported": False, "generated_utc": signer.utcnow()}
    ok, reason = signer.verify_certificate(attestation, env, None)
    if not ok:
        raise RuntimeError("CERTIFICATE_SIGNER_SELF_VERIFY_FAILED:" + reason)
    return env


def source_contract_proof() -> dict[str, Any]:
    source = Path(__file__).read_text("utf-8")
    impl_source = source[:source.find("def source_contract_proof")]
    checks = {
        "single_dash_thumbprint": '"-Thumbprint"' in impl_source and '"--Thumbprint"' not in impl_source,
        "single_dash_digest_file": '"-DigestFile"' in impl_source and '"--DigestFile"' not in impl_source,
        "single_dash_output": '"-Output"' in impl_source and '"--Output"' not in impl_source,
        "shell_false": "shell=False" in impl_source,
        "self_verifies_certificate": "verify_certificate" in impl_source,
        "private_material_never_exported": '"private_material_exported": False' in impl_source,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {"product": PRODUCT, "version": VERSION, "suite": "EXTERNAL_WINDOWS_CERTIFICATE_SIGNER_SOURCE_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)}, "tests": tests,
            "windows_signing_executed": False, "windows_runtime_certified": False,
            "production_score_promotion_eligible": False}


if __name__ == "__main__":
    proof = source_contract_proof()
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    raise SystemExit(0 if proof["verdict"] == "PASS" else 2)
