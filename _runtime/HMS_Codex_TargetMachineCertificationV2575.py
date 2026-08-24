#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_TargetMachineCertification as engine

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
SCHEMA_VERSION = 2
SOURCE_CERTIFICATION = "TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK"
ENGINE_VERSION = str(getattr(engine, "VERSION", "UNKNOWN"))
RUNTIME_DIR = Path(__file__).resolve().parent
ARTIFACT_ROOT = RUNTIME_DIR.parent
CRITICAL_ARTIFACT_PATHS = (
    "_runtime/HMS_AI_ROUTER_v25.23.1.ps1",
    "_runtime/HMS_Codex_TargetMachineCertificationV2575.py",
    "_runtime/HMS_Codex_TargetMachineCertification.py",
    "_runtime/HMS_Codex_RealCertification.py",
    "_runtime/HMS_Codex_LiveQuotaIntelligence.py",
    "_runtime/HMS_Codex_ExternalWindowsCaseReportExporter.py",
    "_runtime/HMS_Codex_ExternalWindowsEvidenceRunner.py",
    "_runtime/HMS_Codex_ExternalWindowsReviewPacketIngest.py",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_index(manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    reasons: list[str] = []
    rows = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    if manifest.get("version") != VERSION:
        reasons.append("ARTIFACT_MANIFEST_VERSION_MISMATCH")
    if str(manifest.get("product") or "") != PRODUCT:
        reasons.append("ARTIFACT_MANIFEST_PRODUCT_MISMATCH")
    if int(manifest.get("file_count") or 0) != len(rows) or not rows:
        reasons.append("ARTIFACT_MANIFEST_FILE_COUNT_INVALID")
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            reasons.append("ARTIFACT_MANIFEST_ROW_INVALID")
            continue
        path = str(row.get("path") or "").replace("\\", "/").lstrip("/")
        digest = str(row.get("sha256") or "").lower()
        if not path or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            reasons.append("ARTIFACT_MANIFEST_ROW_INVALID")
            continue
        if path in index:
            reasons.append("ARTIFACT_MANIFEST_DUPLICATE_PATH:" + path)
            continue
        index[path] = row
    return index, sorted(set(reasons))


def _zip_critical_hashes(package_zip: Path) -> tuple[dict[str, str], list[str]]:
    reasons: list[str] = []
    found: dict[str, str] = {}
    try:
        with zipfile.ZipFile(package_zip, "r") as zf:
            names = [name.replace("\\", "/").lstrip("/") for name in zf.namelist() if not name.endswith("/")]
            for critical in CRITICAL_ARTIFACT_PATHS:
                matches = [name for name in names if name == critical or name.endswith("/" + critical)]
                if len(matches) != 1:
                    reasons.append("ARTIFACT_ZIP_CRITICAL_PATH_COUNT:" + critical)
                    continue
                with zf.open(matches[0], "r") as fh:
                    found[critical] = _sha_bytes(fh.read())
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        reasons.append("ARTIFACT_ZIP_INVALID:" + type(exc).__name__)
    return found, sorted(set(reasons))


def validate_artifact_binding(runtime_root: Path, release_manifest: Path, package_zip: Path) -> dict[str, Any]:
    reasons: list[str] = []
    runtime_root = runtime_root.resolve()
    artifact_root = runtime_root.parent if runtime_root.name.lower() == "_runtime" else runtime_root
    if not release_manifest.is_file():
        reasons.append("ARTIFACT_RELEASE_MANIFEST_MISSING")
        manifest_raw = b""
        manifest: dict[str, Any] = {}
    else:
        manifest_raw = release_manifest.read_bytes()
        try:
            loaded = json.loads(manifest_raw.decode("utf-8-sig"))
            manifest = loaded if isinstance(loaded, dict) else {}
        except Exception:
            manifest = {}
            reasons.append("ARTIFACT_RELEASE_MANIFEST_INVALID_JSON")
    if not package_zip.is_file():
        reasons.append("ARTIFACT_PACKAGE_ZIP_MISSING")

    index, manifest_reasons = _manifest_index(manifest)
    reasons.extend(manifest_reasons)
    zip_hashes: dict[str, str] = {}
    if package_zip.is_file():
        zip_hashes, zip_reasons = _zip_critical_hashes(package_zip)
        reasons.extend(zip_reasons)

    verified: list[dict[str, str]] = []
    for rel in CRITICAL_ARTIFACT_PATHS:
        row = index.get(rel)
        if row is None:
            reasons.append("ARTIFACT_MANIFEST_CRITICAL_PATH_MISSING:" + rel)
            continue
        expected = str(row.get("sha256") or "").lower()
        local = artifact_root / Path(rel)
        if not local.is_file():
            reasons.append("ARTIFACT_RUNTIME_CRITICAL_PATH_MISSING:" + rel)
            continue
        local_sha = _sha_file(local)
        if local_sha != expected:
            reasons.append("ARTIFACT_RUNTIME_SHA256_MISMATCH:" + rel)
        zip_sha = zip_hashes.get(rel, "")
        if zip_sha != expected:
            reasons.append("ARTIFACT_ZIP_SHA256_MISMATCH:" + rel)
        if local_sha == expected and zip_sha == expected:
            verified.append({"path": rel, "sha256": expected})

    reasons = sorted(set(reasons))
    return {
        "pass": not reasons and len(verified) == len(CRITICAL_ARTIFACT_PATHS),
        "binding_schema": "HMS_V25_75_TARGET_ARTIFACT_BINDING_V1",
        "release_manifest_sha256": _sha_bytes(manifest_raw) if manifest_raw else "",
        "package_zip_sha256": _sha_file(package_zip) if package_zip.is_file() else "",
        "manifest_version": str(manifest.get("version") or ""),
        "manifest_product": str(manifest.get("product") or ""),
        "critical_files_required": len(CRITICAL_ARTIFACT_PATHS),
        "critical_files_verified": len(verified),
        "critical_files": verified,
        "reasons": reasons,
        "runtime_root_ref": "artifact-root-relative-only",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    base = engine.run(args)
    runtime_root = Path(args.root).resolve()
    binding = validate_artifact_binding(runtime_root, Path(args.release_manifest), Path(args.package_zip))
    stages = base.get("stages") if isinstance(base.get("stages"), dict) else {}
    exact_seven = tuple(stages.keys()) == tuple(engine.SAFE_STAGES) and all(
        isinstance(stages.get(cid), dict) and stages[cid].get("pass") is True for cid in engine.SAFE_STAGES
    )
    production_pass = (
        base.get("verdict") == "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"
        and exact_seven
        and binding.get("pass") is True
    )
    if production_pass:
        verdict = "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"
    elif exact_seven:
        verdict = "TARGET_MACHINE_ARTIFACT_BINDING_REQUIRED"
    else:
        verdict = str(base.get("verdict") or "BLOCKED_FAIL_CLOSED")
    blockers = list(base.get("blockers") or [])
    if binding.get("pass") is not True:
        blockers.append("ARTIFACT_BINDING")
    report = {
        "product": PRODUCT,
        "edition": "CODEX_ONLY",
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "suite": "TARGET_MACHINE_CERTIFICATION",
        "generated_utc": utcnow(),
        "verdict": verdict,
        "production_certification": SOURCE_CERTIFICATION if production_pass else "NOT_CLAIMED",
        "summary": {
            "stages_pass": sum(1 for cid in engine.SAFE_STAGES if isinstance(stages.get(cid), dict) and stages[cid].get("pass") is True),
            "stages_total": len(engine.SAFE_STAGES),
            "production_certified": production_pass,
            "artifact_binding_pass": binding.get("pass") is True,
        },
        "stages": stages,
        "artifact_binding": binding,
        "certification_engine": {
            "module": "HMS_Codex_TargetMachineCertification.py",
            "engine_version": ENGINE_VERSION,
            "wrapper_version": VERSION,
            "legacy_engine_verdict": str(base.get("verdict") or ""),
        },
        "blockers": sorted(set(str(x) for x in blockers if str(x))),
        "safety": dict(base.get("safety") or {}),
        "claim_boundary": (
            "v25.75 production PASS requires the legacy seven real target-machine stages plus an exact artifact binding: "
            "the release manifest and package ZIP are hashed, and every critical certification/runtime/evidence file must match "
            "the same manifest both on the target filesystem and inside the ZIP. No v25.53 report is relabeled as v25.75."
        ),
    }
    return report


def synthetic_proof() -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    def add(name: str, ok: bool) -> None:
        tests.append({"name": name, "status": "PASS" if ok else "FAIL"})
    with tempfile.TemporaryDirectory(prefix="hms-v2575-artifact-bind-") as td:
        temp = Path(td)
        manifest_rows = []
        for rel in CRITICAL_ARTIFACT_PATHS:
            src = ARTIFACT_ROOT / rel
            manifest_rows.append({"path": rel, "size": src.stat().st_size, "sha256": _sha_file(src)})
        manifest = {"product": PRODUCT, "version": VERSION, "file_count": len(manifest_rows), "files": manifest_rows}
        manifest_path = temp / "RELEASE_MANIFEST_V25_75.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
        package = temp / "package.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in CRITICAL_ARTIFACT_PATHS:
                zf.write(ARTIFACT_ROOT / rel, arcname="HMS-AI-ROUTER/" + rel)
        good = validate_artifact_binding(RUNTIME_DIR, manifest_path, package)
        add("exact_runtime_manifest_zip_binding_passes", good["pass"] is True)
        add("all_critical_files_verified", good["critical_files_verified"] == len(CRITICAL_ARTIFACT_PATHS))
        bad_manifest = dict(manifest); bad_manifest["version"] = "25.53"
        bad_manifest_path = temp / "bad-version.json"; bad_manifest_path.write_text(json.dumps(bad_manifest), "utf-8")
        wrong_version = validate_artifact_binding(RUNTIME_DIR, bad_manifest_path, package)
        add("old_manifest_version_rejected", wrong_version["pass"] is False and "ARTIFACT_MANIFEST_VERSION_MISMATCH" in wrong_version["reasons"])
        bad_zip = temp / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in CRITICAL_ARTIFACT_PATHS:
                if rel == CRITICAL_ARTIFACT_PATHS[0]:
                    zf.writestr("HMS-AI-ROUTER/" + rel, b"tampered")
                else:
                    zf.write(ARTIFACT_ROOT / rel, arcname="HMS-AI-ROUTER/" + rel)
        swapped = validate_artifact_binding(RUNTIME_DIR, manifest_path, bad_zip)
        add("tampered_package_critical_file_rejected", swapped["pass"] is False and any(x.startswith("ARTIFACT_ZIP_SHA256_MISMATCH:") for x in swapped["reasons"]))
        add("proof_grants_no_production_authority", True)
    failed = [x for x in tests if x["status"] != "PASS"]
    return {
        "product": PRODUCT, "version": VERSION, "suite": "TARGET_MACHINE_CERTIFICATION_V2575_ARTIFACT_BINDING_PROOF",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests) - len(failed), "fail": len(failed), "total": len(tests)},
        "tests": tests, "synthetic_fixture_only": True, "real_target_certification_executed": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.75 artifact-bound Target-Machine Certification Runner")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--root", default=str(RUNTIME_DIR))
    ap.add_argument("--data-dir", default=str(Path(os.environ.get("LOCALAPPDATA") or ".") / "HMS_AI_MultiRouter"))
    ap.add_argument("--instance-store", default=""); ap.add_argument("--codex", default=""); ap.add_argument("--powershell", default="")
    ap.add_argument("--timeout-sec", type=float, default=2.0); ap.add_argument("--quota-snapshot", default=""); ap.add_argument("--lan-snapshot", default="")
    ap.add_argument("--shared", default=""); ap.add_argument("--real-cert-evidence", default=""); ap.add_argument("--failover-evidence", default="")
    ap.add_argument("--failover-max-age-hours", type=float, default=168.0); ap.add_argument("--soak-state-dir", default="")
    ap.add_argument("--soak6-evidence", default=""); ap.add_argument("--soak24-evidence", default="")
    ap.add_argument("--release-manifest", default=""); ap.add_argument("--package-zip", default=""); ap.add_argument("--output", default="")
    a = ap.parse_args()
    if a.proof:
        out = synthetic_proof(); code = 0 if out["verdict"] == "PASS" else 2
    else:
        try:
            out = run(a); code = 0 if out.get("verdict") == "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" else 2
        except Exception as exc:
            out = {"product": PRODUCT, "version": VERSION, "suite": "TARGET_MACHINE_CERTIFICATION", "generated_utc": utcnow(),
                   "verdict": "BLOCKED_FAIL_CLOSED", "production_certification": "NOT_CLAIMED",
                   "error": type(exc).__name__, "detail": str(exc), "windows_runtime_certified": False,
                   "production_score_promotion_eligible": False}; code = 2
    if a.output:
        engine.atomic_json(Path(a.output), out)
    print(json.dumps(out, ensure_ascii=False, indent=2)); return code


if __name__ == "__main__":
    raise SystemExit(main())
