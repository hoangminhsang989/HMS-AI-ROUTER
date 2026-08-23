#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.72"
COCKPIT_BASELINE = "1.3.27"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REAL_SOURCE_MODE = "REAL_WINDOWS_TARGET"
REQUIRED_EVIDENCE_CLASSES = {"WINDOWS_TARGET_OBSERVER", "REAL_CODEX_EFFECT"}

CASE_DEFS = (
    ("FOREIGN_PORT_AUTO_REBIND", "Xung đột cổng tự chuyển cổng, không chạm PID lạ"),
    ("ACCOUNT_OCCUPANCY_GUARD", "Chặn cùng tài khoản ở hai Codex instance đang hoạt động"),
    ("CLIENT_AUTH_API_SERVICE_SPLIT", "Tách trạng thái đăng nhập Codex và API Service"),
    ("OFFICIAL_ACCOUNT_USAGE_CONTINUITY", "Giữ lịch sử usage qua remove/re-add bằng pseudonymous official-account ref"),
    ("WEBSOCKET_PREFERENCE_PERSISTENCE", "Giữ WebSocket preference qua refresh/switch/restart"),
    ("BOUNDED_BACKUP_ROLLBACK_NTFS", "Backup retention hữu hạn và rollback crash-safe trên NTFS"),
    ("STREAM_IDENTITY_ISOLATION", "Cách ly affinity theo composite conversation/thread/request identity"),
)
CASE_IDS = tuple(x[0] for x in CASE_DEFS)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8", "surrogatepass")
    return hashlib.sha256(value).hexdigest()


def _case_reasons(report: dict[str, Any], expected_id: str) -> list[str]:
    reasons: list[str] = []
    if report.get("case_id") != expected_id:
        reasons.append("CASE_ID_MISMATCH")
    if report.get("status") != "PASS":
        reasons.append("CASE_NOT_PASS")
    classes = set(report.get("evidence_classes") or [])
    if not REQUIRED_EVIDENCE_CLASSES.issubset(classes):
        reasons.append("TARGET_EVIDENCE_CLASS_MISSING")
    if report.get("runtime_attestation_verified") is not True:
        reasons.append("RUNTIME_ATTESTATION_NOT_VERIFIED")
    if report.get("signature_verified") is not True:
        reasons.append("SIGNATURE_NOT_VERIFIED")
    if report.get("idempotency_witness_verified") is not True:
        reasons.append("IDEMPOTENCY_WITNESS_NOT_VERIFIED")
    if not HEX64.fullmatch(str(report.get("report_sha256") or "").lower()):
        reasons.append("REPORT_DIGEST_INVALID")
    if report.get("raw_account_id_exported") is not False:
        reasons.append("RAW_ACCOUNT_ID_EXPORTED")
    if report.get("credential_payload_exported") is not False:
        reasons.append("CREDENTIAL_PAYLOAD_EXPORTED")
    return reasons


def evaluate_runtime_campaign(evidence: dict[str, Any], *, expected_manifest_sha256: str, expected_package_version: str = VERSION, current_cockpit_baseline: str = COCKPIT_BASELINE) -> dict[str, Any]:
    reasons: list[str] = []
    if evidence.get("source_mode") != REAL_SOURCE_MODE:
        reasons.append("REAL_WINDOWS_TARGET_EVIDENCE_REQUIRED")
    host = evidence.get("host") or {}
    if host.get("os") != "Windows" or host.get("windows_target_verified") is not True:
        reasons.append("WINDOWS_HOST_NOT_VERIFIED")
    if int(host.get("powershell_major") or 0) < 5:
        reasons.append("POWERSHELL_51_OR_NEWER_REQUIRED")
    codex = evidence.get("codex") or {}
    if codex.get("client_present") is not True or not str(codex.get("version") or "").strip():
        reasons.append("CURRENT_CODEX_RUNTIME_REQUIRED")
    if evidence.get("external_import") is not True:
        reasons.append("EXTERNAL_TARGET_IMPORT_REQUIRED")
    if evidence.get("package_version") != expected_package_version:
        reasons.append("PACKAGE_VERSION_MISMATCH")
    if evidence.get("cockpit_baseline") != current_cockpit_baseline:
        reasons.append("COCKPIT_BASELINE_MISMATCH")
    manifest = str(evidence.get("manifest_sha256") or "").lower()
    if not HEX64.fullmatch(manifest) or manifest != str(expected_manifest_sha256).lower():
        reasons.append("MANIFEST_DIGEST_MISMATCH")
    reports = evidence.get("case_reports") or []
    by_id: dict[str, list[dict[str, Any]]] = {}
    for r in reports:
        by_id.setdefault(str(r.get("case_id") or ""), []).append(r)
    case_results = []
    for case_id, label in CASE_DEFS:
        items = by_id.get(case_id, [])
        cr: list[str] = []
        if len(items) != 1:
            cr.append("CASE_REPORT_COUNT_NOT_EXACTLY_ONE")
        elif items:
            cr.extend(_case_reasons(items[0], case_id))
        case_results.append({"case_id": case_id, "label_vi": label, "status": "CERTIFIED" if not cr else "NOT_CERTIFIED", "reasons": sorted(set(cr)), "report_sha256": items[0].get("report_sha256") if len(items) == 1 else None})
    extras = sorted(set(by_id) - set(CASE_IDS))
    if extras:
        reasons.append("UNKNOWN_CASE_REPORT_PRESENT")
    incomplete = [x["case_id"] for x in case_results if x["status"] != "CERTIFIED"]
    if incomplete:
        reasons.append("RUNTIME_CASE_MATRIX_INCOMPLETE")
    certified = not reasons
    campaign_digest = sha256_hex(stable({"package_version": evidence.get("package_version"), "manifest_sha256": manifest, "cockpit_baseline": evidence.get("cockpit_baseline"), "reports": [{"case_id": x["case_id"], "report_sha256": x["report_sha256"]} for x in case_results]}))
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "COCKPIT_1327_WINDOWS_RUNTIME_CERTIFICATION",
        "generated_utc": utcnow(),
        "cockpit_baseline": current_cockpit_baseline,
        "windows_runtime_certified": certified,
        "external_windows_target_evidence_imported": evidence.get("external_import") is True,
        "case_matrix_complete": not incomplete,
        "case_results": case_results,
        "reasons": sorted(set(reasons)),
        "campaign_digest": campaign_digest,
        "production_score_mutation_authorized": False,
        "automatic_production_certification": False,
    }


def synthetic_proof() -> dict[str, Any]:
    tests = []
    def add(name: str, ok: bool, detail: Any = None):
        tests.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    manifest = "a" * 64
    base_reports = []
    for i, (case_id, _) in enumerate(CASE_DEFS):
        base_reports.append({
            "case_id": case_id, "status": "PASS",
            "evidence_classes": ["WINDOWS_TARGET_OBSERVER", "REAL_CODEX_EFFECT"],
            "runtime_attestation_verified": True, "signature_verified": True,
            "idempotency_witness_verified": True, "report_sha256": sha256_hex(f"report-{i}"),
            "raw_account_id_exported": False, "credential_payload_exported": False,
        })
    lab = {"source_mode": "LAB_FIXTURE", "external_import": False, "package_version": VERSION, "manifest_sha256": manifest, "cockpit_baseline": COCKPIT_BASELINE, "host": {"os": "Linux", "powershell_major": 0, "windows_target_verified": False}, "codex": {"client_present": False, "version": ""}, "case_reports": base_reports}
    r0 = evaluate_runtime_campaign(lab, expected_manifest_sha256=manifest)
    add("lab_fixture_cannot_certify_windows", r0["windows_runtime_certified"] is False and "REAL_WINDOWS_TARGET_EVIDENCE_REQUIRED" in r0["reasons"], r0["reasons"])
    target = {"source_mode": REAL_SOURCE_MODE, "external_import": True, "package_version": VERSION, "manifest_sha256": manifest, "cockpit_baseline": COCKPIT_BASELINE, "host": {"os": "Windows", "powershell_major": 5, "windows_target_verified": True}, "codex": {"client_present": True, "version": "current-codex-fixture"}, "case_reports": base_reports}
    r1 = evaluate_runtime_campaign(target, expected_manifest_sha256=manifest)
    add("complete_contract_can_certify", r1["windows_runtime_certified"] is True and r1["case_matrix_complete"] is True)
    missing = json.loads(json.dumps(target)); missing["case_reports"] = missing["case_reports"][:-1]
    r2 = evaluate_runtime_campaign(missing, expected_manifest_sha256=manifest)
    add("missing_case_rejected", not r2["windows_runtime_certified"] and "RUNTIME_CASE_MATRIX_INCOMPLETE" in r2["reasons"])
    dup = json.loads(json.dumps(target)); dup["case_reports"].append(json.loads(json.dumps(dup["case_reports"][0])))
    r3 = evaluate_runtime_campaign(dup, expected_manifest_sha256=manifest)
    add("duplicate_case_rejected", not r3["windows_runtime_certified"])
    bad = json.loads(json.dumps(target)); bad["case_reports"][0]["evidence_classes"] = ["WINDOWS_TARGET_OBSERVER"]
    r4 = evaluate_runtime_campaign(bad, expected_manifest_sha256=manifest)
    add("real_effect_evidence_required", not r4["windows_runtime_certified"])
    bad2 = json.loads(json.dumps(target)); bad2["case_reports"][1]["idempotency_witness_verified"] = False
    r5 = evaluate_runtime_campaign(bad2, expected_manifest_sha256=manifest)
    add("idempotency_witness_required", not r5["windows_runtime_certified"])
    bad3 = json.loads(json.dumps(target)); bad3["cockpit_baseline"] = "1.3.24"
    r6 = evaluate_runtime_campaign(bad3, expected_manifest_sha256=manifest)
    add("stale_cockpit_baseline_rejected", not r6["windows_runtime_certified"] and "COCKPIT_BASELINE_MISMATCH" in r6["reasons"])
    bad4 = json.loads(json.dumps(target)); bad4["case_reports"][2]["raw_account_id_exported"] = True
    r7 = evaluate_runtime_campaign(bad4, expected_manifest_sha256=manifest)
    add("raw_account_id_export_rejected", not r7["windows_runtime_certified"])
    add("campaign_digest_is_pseudonymous", HEX64.fullmatch(r1["campaign_digest"]) is not None and "current-codex-fixture" not in r1["campaign_digest"])
    add("certification_never_mutates_score", r1["production_score_mutation_authorized"] is False and r1["automatic_production_certification"] is False)
    passed = sum(x["status"] == "PASS" for x in tests)
    return {"product": "HMS-AI-ROUTER", "version": VERSION, "suite": "COCKPIT_1327_WINDOWS_RUNTIME_CERTIFICATION_PROOF", "generated_utc": utcnow(), "verdict": "PASS" if passed == len(tests) else "FAIL", "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)}, "tests": tests, "synthetic_control_plane_only": True, "windows_runtime_certified": False, "production_score_eligible": False}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--proof", action="store_true"); ap.add_argument("--evidence"); ap.add_argument("--manifest-sha256", default=""); ap.add_argument("--output")
    a = ap.parse_args()
    if a.proof or not a.evidence:
        out = synthetic_proof(); rc = 0 if out["verdict"] == "PASS" else 2
    else:
        if not a.manifest_sha256: raise SystemExit("--manifest-sha256 required")
        out = evaluate_runtime_campaign(json.loads(Path(a.evidence).read_text("utf-8")), expected_manifest_sha256=a.manifest_sha256); rc = 0 if out["windows_runtime_certified"] else 4
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output: Path(a.output).write_text(text+"\n", "utf-8")
    print(text); return rc

if __name__ == "__main__": raise SystemExit(main())
