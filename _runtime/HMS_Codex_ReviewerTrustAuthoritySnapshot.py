#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_AttestationTrustStore as trust_store
import HMS_Codex_ReviewerLocalIntegritySeal as local_seal
import HMS_Codex_WindowsAttestationSigner as windows_signer
from HMS_Codex_ExternalWindowsSignerTrustContract import validate_trust_snapshot

VERSION = "25.75"
PRODUCT = "HMS-AI-ROUTER"
SCHEMA_VERSION = 1
AUTHORITY_CLASS = "REVIEWER_SIDE_TRUST_AUTHORITY"
SEAL_PURPOSE = "HMS_V2575_REVIEWER_TRUST_AUTHORITY"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _stable(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(obj: Any) -> str:
    return hashlib.sha256(_stable(obj)).hexdigest()


def _parse_time(value: str | None):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except Exception:
        return None


def _authority_digest(body: dict[str, Any]) -> str:
    core = {k: v for k, v in body.items() if k != "authority_sha256"}
    return _sha(core)


def validate_authority_body(body: dict[str, Any], *, now: datetime | None = None, freshness_hours: int = 24) -> dict[str, Any]:
    reasons: list[str] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if body.get("schema_version") != SCHEMA_VERSION:
        reasons.append("TRUST_AUTHORITY_SCHEMA_INVALID")
    if body.get("product") != PRODUCT or body.get("version") != VERSION:
        reasons.append("TRUST_AUTHORITY_PRODUCT_VERSION_INVALID")
    if body.get("authority_class") != AUTHORITY_CLASS:
        reasons.append("TRUST_AUTHORITY_CLASS_INVALID")
    if body.get("packet_derived") is not False:
        reasons.append("TRUST_AUTHORITY_MUST_NOT_BE_PACKET_DERIVED")
    if body.get("raw_packet_included") is not False:
        reasons.append("TRUST_AUTHORITY_RAW_PACKET_FORBIDDEN")
    if body.get("private_material_exported") is not False:
        reasons.append("TRUST_AUTHORITY_PRIVATE_MATERIAL_FORBIDDEN")
    if not str(body.get("source_trust_store_ref") or "").startswith("ref-"):
        reasons.append("TRUST_AUTHORITY_SOURCE_REF_REQUIRED")
    trust_digest = str(body.get("trust_snapshot_sha256") or "").lower()
    if not HEX64.fullmatch(trust_digest):
        reasons.append("TRUST_AUTHORITY_SNAPSHOT_DIGEST_INVALID")
    if _authority_digest(body) != str(body.get("authority_sha256") or "").lower():
        reasons.append("TRUST_AUTHORITY_DIGEST_MISMATCH")

    created = _parse_time(body.get("created_utc"))
    if created is None:
        reasons.append("TRUST_AUTHORITY_CREATED_UTC_INVALID")
    else:
        if created > now + timedelta(minutes=5):
            reasons.append("TRUST_AUTHORITY_TIME_IN_FUTURE")
        if now - created > timedelta(hours=max(1, int(freshness_hours))):
            reasons.append("TRUST_AUTHORITY_STALE")

    pins = body.get("active_pins") if isinstance(body.get("active_pins"), list) else []
    if not pins:
        reasons.append("TRUST_AUTHORITY_ACTIVE_PIN_REQUIRED")
    seen_cert = set(); seen_ref = set()
    for i, row in enumerate(pins):
        if not isinstance(row, dict):
            reasons.append(f"TRUST_AUTHORITY_PIN_{i}_INVALID"); continue
        cert = str(row.get("certificate_sha256") or "").lower()
        ref = str(row.get("signer_key_id_ref") or "")
        if not HEX64.fullmatch(cert):
            reasons.append(f"TRUST_AUTHORITY_PIN_{i}_CERT_DIGEST_INVALID")
        if not ref.startswith("ref-"):
            reasons.append(f"TRUST_AUTHORITY_PIN_{i}_SIGNER_REF_INVALID")
        if cert in seen_cert:
            reasons.append("TRUST_AUTHORITY_DUPLICATE_CERTIFICATE")
        if ref in seen_ref:
            reasons.append("TRUST_AUTHORITY_DUPLICATE_SIGNER_REF")
        seen_cert.add(cert); seen_ref.add(ref)
        not_before = _parse_time(row.get("not_before_utc")); not_after = _parse_time(row.get("not_after_utc"))
        if not_before and now < not_before:
            reasons.append(f"TRUST_AUTHORITY_PIN_{i}_NOT_YET_VALID")
        if not_after and now > not_after:
            reasons.append(f"TRUST_AUTHORITY_PIN_{i}_EXPIRED")
    return {"valid": not reasons, "reasons": sorted(set(reasons)),
            "trust_snapshot_sha256": trust_digest, "active_pin_count": len(pins),
            "authority_sha256": str(body.get("authority_sha256") or "").lower()}


def capture_authority(trust_path: Path, output_path: Path, key_path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    if not trust_path.is_file():
        raise FileNotFoundError("TRUST_STORE_MISSING")
    store = trust_store.load_store(trust_path)
    snapshot = trust_store.trust_snapshot(store)
    snap_check = validate_trust_snapshot(snapshot)
    if not snap_check["valid"]:
        raise ValueError("TRUST_STORE_SNAPSHOT_INVALID:" + ",".join(snap_check["reasons"]))

    active_pins = []
    by_digest = {str(row.get("certificate_sha256") or "").lower(): row for row in (store.get("certificates") or [])}
    for cert_sha in sorted(trust_store.trusted_certificate_sha256(store)):
        row = by_digest.get(str(cert_sha).lower()) or {}
        active_pins.append({
            "pin_id": row.get("pin_id"), "certificate_sha256": str(cert_sha).lower(),
            "signer_key_id_ref": row.get("signer_key_id_ref"),
            "not_before_utc": row.get("not_before_utc"), "not_after_utc": row.get("not_after_utc"),
        })
    if not active_pins:
        raise ValueError("TRUST_AUTHORITY_ACTIVE_PIN_REQUIRED")

    body = {
        "schema_version": SCHEMA_VERSION, "product": PRODUCT, "version": VERSION,
        "authority_class": AUTHORITY_CLASS, "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_trust_store_ref": windows_signer.safe_ref(str(trust_path.resolve())),
        "trust_store_generation": int(store.get("generation") or 0),
        "trust_snapshot_sha256": snapshot["trust_snapshot_sha256"],
        "active_pins": active_pins, "packet_derived": False, "raw_packet_included": False,
        "private_material_exported": False,
    }
    body["authority_sha256"] = _authority_digest(body)
    body_check = validate_authority_body(body)
    if not body_check["valid"]:
        raise ValueError("TRUST_AUTHORITY_BODY_INVALID:" + ",".join(body_check["reasons"]))
    seal = local_seal.seal_payload(body, purpose=SEAL_PURPOSE, key_path=key_path)
    document = {"authority": body, "integrity_seal": seal}
    trust_store.atomic_json(output_path, document)
    return {"product": PRODUCT, "version": VERSION, "suite": "REVIEWER_TRUST_AUTHORITY_CAPTURE",
            "verdict": "TRUST_AUTHORITY_CAPTURED", "authority_path": str(output_path),
            "authority_sha256": body["authority_sha256"], "trust_snapshot_sha256": body["trust_snapshot_sha256"],
            "active_pin_count": len(active_pins), "integrity_seal": "DPAPI_HMAC_VALID_AT_CAPTURE",
            "packet_derived": False, "private_material_exported": False,
            "windows_runtime_certified": False, "production_score_promotion_eligible": False}


def verify_authority_document(document: dict[str, Any], *, key_path: Path, now: datetime | None = None,
                              freshness_hours: int = 24) -> dict[str, Any]:
    body = document.get("authority") if isinstance(document.get("authority"), dict) else {}
    seal = document.get("integrity_seal") if isinstance(document.get("integrity_seal"), dict) else {}
    body_check = validate_authority_body(body, now=now, freshness_hours=freshness_hours)
    seal_check = local_seal.verify_payload(body, seal, purpose=SEAL_PURPOSE, key_path=key_path)
    reasons = sorted(set(body_check["reasons"] + seal_check["reasons"]))
    return {"valid": not reasons, "reasons": reasons,
            "trust_snapshot_sha256": body_check.get("trust_snapshot_sha256", ""),
            "authority_sha256": body_check.get("authority_sha256", ""),
            "active_pin_count": body_check.get("active_pin_count", 0),
            "local_integrity_seal_valid": seal_check.get("valid") is True,
            "packet_derived": body.get("packet_derived") is True}


def load_and_verify_authority(path: Path, *, key_path: Path, freshness_hours: int = 24) -> dict[str, Any]:
    if not path.is_file():
        return {"valid": False, "reasons": ["TRUST_AUTHORITY_FILE_MISSING"], "trust_snapshot_sha256": ""}
    try:
        document = json.loads(path.read_text("utf-8"))
    except Exception:
        return {"valid": False, "reasons": ["TRUST_AUTHORITY_JSON_INVALID"], "trust_snapshot_sha256": ""}
    return verify_authority_document(document, key_path=key_path, freshness_hours=freshness_hours)


def synthetic_proof() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    body = {
        "schema_version": SCHEMA_VERSION, "product": PRODUCT, "version": VERSION,
        "authority_class": AUTHORITY_CLASS, "created_utc": now.isoformat(),
        "source_trust_store_ref": "ref-" + "1" * 24, "trust_store_generation": 1,
        "trust_snapshot_sha256": "a" * 64,
        "active_pins": [{"pin_id": "pin-a", "certificate_sha256": "b" * 64,
                         "signer_key_id_ref": "ref-" + "2" * 24,
                         "not_before_utc": (now - timedelta(days=1)).isoformat(),
                         "not_after_utc": (now + timedelta(days=30)).isoformat()}],
        "packet_derived": False, "raw_packet_included": False, "private_material_exported": False,
    }
    body["authority_sha256"] = _authority_digest(body)
    good = validate_authority_body(body, now=now)
    stale_body = json.loads(json.dumps(body)); stale_body["created_utc"] = (now - timedelta(hours=25)).isoformat(); stale_body["authority_sha256"] = _authority_digest(stale_body)
    stale = validate_authority_body(stale_body, now=now)
    packet_derived = json.loads(json.dumps(body)); packet_derived["packet_derived"] = True; packet_derived["authority_sha256"] = _authority_digest(packet_derived)
    derived = validate_authority_body(packet_derived, now=now)
    tampered = json.loads(json.dumps(body)); tampered["trust_snapshot_sha256"] = "c" * 64
    tampered_check = validate_authority_body(tampered, now=now)
    checks = {
        "valid_reviewer_authority_body": good["valid"],
        "stale_authority_rejected": not stale["valid"] and "TRUST_AUTHORITY_STALE" in stale["reasons"],
        "packet_derived_authority_rejected": not derived["valid"] and "TRUST_AUTHORITY_MUST_NOT_BE_PACKET_DERIVED" in derived["reasons"],
        "authority_digest_tamper_rejected": not tampered_check["valid"] and "TRUST_AUTHORITY_DIGEST_MISMATCH" in tampered_check["reasons"],
        "local_integrity_seal_required": "local_seal.verify_payload" in Path(__file__).read_text("utf-8"),
        "production_capture_windows_only": os.name == "nt" or _capture_nonwindows_rejected(),
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {"product": PRODUCT, "version": VERSION, "suite": "REVIEWER_TRUST_AUTHORITY_SNAPSHOT_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)}, "tests": tests,
            "real_trust_authority_captured": False, "windows_runtime_certified": False,
            "production_score_promotion_eligible": False}


def _capture_nonwindows_rejected() -> bool:
    try:
        capture_authority(Path("x"), Path("y"), Path("z")); return False
    except RuntimeError as exc:
        return str(exc) == "WINDOWS_REQUIRED"
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Reviewer-side independent trust authority snapshot")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--trust-store", default=""); ap.add_argument("--authority", default="")
    ap.add_argument("--integrity-key", default=""); ap.add_argument("--freshness-hours", type=int, default=24)
    args = ap.parse_args()
    if args.proof or (not args.capture and not args.verify):
        out = synthetic_proof(); code = 0 if out["verdict"] == "PASS" else 2
    elif args.capture:
        if not (args.trust_store and args.authority and args.integrity_key):
            ap.error("--trust-store --authority --integrity-key required for capture")
        try:
            out = capture_authority(Path(args.trust_store), Path(args.authority), Path(args.integrity_key)); code = 0
        except Exception as exc:
            out = {"product": PRODUCT, "version": VERSION, "suite": "REVIEWER_TRUST_AUTHORITY_CAPTURE",
                   "verdict": "BLOCKED_FAIL_CLOSED", "error": type(exc).__name__, "detail": str(exc),
                   "windows_runtime_certified": False, "production_score_promotion_eligible": False}; code = 2
    else:
        if not (args.authority and args.integrity_key):
            ap.error("--authority --integrity-key required for verify")
        out = load_and_verify_authority(Path(args.authority), key_path=Path(args.integrity_key), freshness_hours=args.freshness_hours)
        code = 0 if out.get("valid") else 2
    print(json.dumps(out, ensure_ascii=False, indent=2)); return code


if __name__ == "__main__":
    raise SystemExit(main())
