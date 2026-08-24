#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import HMS_Codex_ExternalWindowsEvidenceRunner as evidence_runner
import HMS_Codex_ReviewerPacketImport as reviewer_import
import HMS_Codex_ReviewerTrustAuthoritySnapshot as trust_authority
import HMS_Codex_ReviewerReleaseAuthority as release_authority
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION

PRODUCT = "HMS-AI-ROUTER"
DEFAULT_AUTHORITY_NAME = "reviewer_trust_authority_v2575.json"
DEFAULT_RELEASE_AUTHORITY_NAME = "reviewer_release_authority_v2575.json"
DEFAULT_INTEGRITY_KEY_NAME = "reviewer_local_integrity.key.dpapi"


def _windows_required() -> None:
    if os.name != "nt": raise RuntimeError("WINDOWS_REQUIRED")


def _operator_preflight(args) -> dict:
    _windows_required()
    runner_args = SimpleNamespace(
        codex=args.codex,
        package_zip=args.package_zip,
        release_manifest=args.release_manifest,
        source_certification_report=args.source_certification_report,
        case_report=list(args.case_report or []),
        trust_store=args.trust_store,
        certificate_thumbprint=args.certificate_thumbprint,
        certificate_sign_script=args.certificate_sign_script or str(evidence_runner.DEFAULT_SIGN_SCRIPT),
        certificate_inspect_script=args.certificate_inspect_script or str(evidence_runner.DEFAULT_INSPECT_SCRIPT),
        cockpit_baseline=args.cockpit_baseline,
        output="",
    )
    result = evidence_runner.preflight(runner_args)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "WINDOWS_EVIDENCE_ORCHESTRATOR_OPERATOR_PREFLIGHT",
        "verdict": "READY_FOR_OPERATOR_EVIDENCE_FLOW" if result.get("ready") else "BLOCKED_FAIL_CLOSED",
        "ready": result.get("ready") is True,
        "reasons": result.get("reasons") or [], "reasons_vi": result.get("reasons_vi") or [],
        "codex": result.get("codex") or {}, "case_matrix": result.get("case_matrix") or {},
        "source_certification_report_sha256": result.get("source_certification_report_sha256", ""),
        "source_capture_utc": result.get("source_capture_utc", ""),
        "source_package_zip_sha256": result.get("source_package_zip_sha256", ""),
        "source_release_manifest_sha256": result.get("source_release_manifest_sha256", ""),
        "certificate_preflight_ready": result.get("certificate_preflight_ready") is True,
        "selected_certificate_sha256": result.get("selected_certificate_sha256", ""),
        "trust_snapshot_sha256": result.get("trust_snapshot_sha256", ""),
        "trusted_active_certificate_count": result.get("trusted_active_certificate_count", 0),
        "real_codex_request_executed": False, "production_packet_signed": False, "trust_store_mutated": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
        "automatic_production_certification": False,
    }


def _parse_utc(value: str | None):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except Exception: return None


def _authority_freshness(*, body, verified, freshness_hours, stale_reason, prefix):
    reasons = list(verified.get("reasons") or []); now = datetime.now(timezone.utc)
    created = _parse_utc(body.get("created_utc")) if body else None
    expires = created + timedelta(hours=freshness_hours) if created else None
    remaining_seconds = int((expires - now).total_seconds()) if expires else None
    stale = stale_reason in reasons or (remaining_seconds is not None and remaining_seconds <= 0)
    return reasons, created, expires, remaining_seconds, stale


def _reviewer_authority_status(args) -> dict:
    _windows_required(); state_dir = Path(args.state_dir).resolve()
    authority_path = state_dir / (args.authority_name or DEFAULT_AUTHORITY_NAME); integrity_key_path = state_dir / DEFAULT_INTEGRITY_KEY_NAME
    freshness_hours = max(1, int(args.authority_freshness_hours)); warning_hours = max(0, min(freshness_hours, int(args.renewal_warning_hours)))
    verified = trust_authority.load_and_verify_authority(authority_path, key_path=integrity_key_path, freshness_hours=freshness_hours)
    body = {}
    if authority_path.is_file():
        try:
            document = json.loads(authority_path.read_text("utf-8")); body = document.get("authority") if isinstance(document.get("authority"), dict) else {}
        except Exception: pass
    reasons, created, expires, remaining_seconds, stale = _authority_freshness(body=body, verified=verified, freshness_hours=freshness_hours,
        stale_reason="TRUST_AUTHORITY_STALE", prefix="TRUST")
    valid = verified.get("valid") is True and not reasons; renew_soon = valid and remaining_seconds is not None and remaining_seconds <= warning_hours * 3600
    verdict = "BLOCKED_FAIL_CLOSED" if not valid else ("AUTHORITY_RENEW_SOON" if renew_soon else "AUTHORITY_FRESH")
    return {"product":PRODUCT,"version":VERSION,"suite":"WINDOWS_EVIDENCE_ORCHESTRATOR_REVIEWER_AUTHORITY_STATUS","verdict":verdict,
        "valid":valid,"freshness_state":"STALE" if stale else ("RENEW_SOON" if renew_soon else ("FRESH" if valid else "INVALID")),
        "reasons":sorted(set(reasons)),"authority_path":str(authority_path),"authority_sha256":verified.get("authority_sha256",""),
        "trust_snapshot_sha256":verified.get("trust_snapshot_sha256",""),"active_pin_count":verified.get("active_pin_count",0),
        "local_integrity_seal_valid":verified.get("local_integrity_seal_valid") is True,
        "created_utc":created.isoformat() if created else "","expires_utc":expires.isoformat() if expires else "","remaining_seconds":remaining_seconds,
        "freshness_hours":freshness_hours,"renewal_warning_hours":warning_hours,"renewal_recommended":renew_soon or stale,"renewal_required":stale,
        "authority_recaptured":False,"packet_imported":False,"reviewer_trust_store_mutated":False,"raw_packet_copied_into_state_dir":False,
        "production_packet_signed":False,"real_codex_request_executed":False,"windows_runtime_certified":False,
        "external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,"automatic_production_certification":False,
        "production_score_mutation_authorized":False}


def _reviewer_release_authority_status(args) -> dict:
    _windows_required(); state_dir = Path(args.state_dir).resolve()
    authority_path = state_dir / (args.release_authority_name or DEFAULT_RELEASE_AUTHORITY_NAME); integrity_key_path = state_dir / DEFAULT_INTEGRITY_KEY_NAME
    freshness_hours = max(1, int(args.release_authority_freshness_hours)); warning_hours = max(0, min(freshness_hours, int(args.renewal_warning_hours)))
    verified = release_authority.load_and_verify_authority(authority_path, key_path=integrity_key_path, freshness_hours=freshness_hours)
    body = {}
    if authority_path.is_file():
        try:
            document = json.loads(authority_path.read_text("utf-8")); body = document.get("authority") if isinstance(document.get("authority"), dict) else {}
        except Exception: pass
    reasons, created, expires, remaining_seconds, stale = _authority_freshness(body=body, verified=verified, freshness_hours=freshness_hours,
        stale_reason="RELEASE_AUTHORITY_STALE", prefix="RELEASE")
    valid = verified.get("valid") is True and not reasons; renew_soon = valid and remaining_seconds is not None and remaining_seconds <= warning_hours * 3600
    verdict = "BLOCKED_FAIL_CLOSED" if not valid else ("RELEASE_AUTHORITY_RENEW_SOON" if renew_soon else "RELEASE_AUTHORITY_FRESH")
    return {"product":PRODUCT,"version":VERSION,"suite":"WINDOWS_EVIDENCE_ORCHESTRATOR_RELEASE_AUTHORITY_STATUS","verdict":verdict,
        "valid":valid,"freshness_state":"STALE" if stale else ("RENEW_SOON" if renew_soon else ("FRESH" if valid else "INVALID")),
        "reasons":sorted(set(reasons)),"authority_path":str(authority_path),"authority_sha256":verified.get("authority_sha256",""),
        "package_zip_sha256":verified.get("package_zip_sha256",""),"release_manifest_sha256":verified.get("release_manifest_sha256",""),
        "source_commit_sha":verified.get("source_commit_sha",""),"source_tree_sha":verified.get("source_tree_sha",""),
        "local_integrity_seal_valid":verified.get("local_integrity_seal_valid") is True,
        "created_utc":created.isoformat() if created else "","expires_utc":expires.isoformat() if expires else "","remaining_seconds":remaining_seconds,
        "freshness_hours":freshness_hours,"renewal_warning_hours":warning_hours,"renewal_recommended":renew_soon or stale,"renewal_required":stale,
        "authority_recaptured":False,"packet_imported":False,"local_artifact_hashed_at_capture":False,"raw_packet_copied_into_state_dir":False,
        "windows_runtime_certified":False,"external_windows_target_evidence_imported":False,"production_score_promotion_eligible":False,
        "automatic_production_certification":False,"production_score_mutation_authorized":False}


def _reviewer_import(args) -> dict:
    _windows_required(); state_dir = Path(args.state_dir).resolve(); trust_store_path = Path(args.reviewer_trust_store).resolve()
    packet = Path(args.packet).resolve(); package_zip = Path(args.package_zip).resolve(); release_manifest = Path(args.release_manifest).resolve()
    state_dir.mkdir(parents=True, exist_ok=True); integrity_key_path = state_dir / DEFAULT_INTEGRITY_KEY_NAME
    authority_path = state_dir / (args.authority_name or DEFAULT_AUTHORITY_NAME)
    release_authority_path = state_dir / (args.release_authority_name or DEFAULT_RELEASE_AUTHORITY_NAME)

    captured = trust_authority.capture_authority(trust_store_path, authority_path, integrity_key_path)
    release_captured = release_authority.capture_authority(
        package_zip_sha256=args.reviewed_package_sha256,
        release_manifest_sha256=args.reviewed_manifest_sha256,
        source_commit_sha=args.reviewed_source_commit,
        source_tree_sha=args.reviewed_source_tree,
        output_path=release_authority_path,
        key_path=integrity_key_path,
    )
    imported = reviewer_import.import_for_review(
        state_dir=state_dir, packet=packet, package_zip=package_zip, release_manifest=release_manifest,
        trust_authority=authority_path, release_authority_path=release_authority_path,
        authority_freshness_hours=args.authority_freshness_hours,
        release_authority_freshness_hours=args.release_authority_freshness_hours,
        cockpit_baseline=args.cockpit_baseline,
    )
    if captured.get("verdict") != "TRUST_AUTHORITY_CAPTURED": raise RuntimeError("TRUST_AUTHORITY_CAPTURE_FAILED")
    if release_captured.get("verdict") != "RELEASE_AUTHORITY_CAPTURED": raise RuntimeError("RELEASE_AUTHORITY_CAPTURE_FAILED")
    if imported.get("verdict") != "VERIFIED_PACKET_PERSISTED_FOR_REVIEW": raise RuntimeError("REVIEWER_PACKET_IMPORT_FAILED")
    return {"product":PRODUCT,"version":VERSION,"suite":"WINDOWS_EVIDENCE_ORCHESTRATOR_REVIEWER_IMPORT","verdict":"REVIEWER_STATE_READY_FOR_HUMAN_REVIEW",
        "state_dir":str(state_dir),"authority_path":str(authority_path),"authority_sha256":captured.get("authority_sha256",""),
        "release_authority_path":str(release_authority_path),"release_authority_sha256":release_captured.get("authority_sha256",""),
        "release_authority_source_commit_sha":release_captured.get("source_commit_sha",""),"release_authority_source_tree_sha":release_captured.get("source_tree_sha",""),
        "trust_snapshot_sha256":captured.get("trust_snapshot_sha256",""),"raw_packet_sha256":imported.get("raw_packet_sha256",""),
        "package_zip_sha256":imported.get("package_zip_sha256",""),"release_manifest_sha256":imported.get("release_manifest_sha256",""),
        "report_local_integrity_seal_present":imported.get("report_local_integrity_seal_present") is True,
        "replay_registry_local_integrity_seal_present":imported.get("replay_registry_local_integrity_seal_present") is True,
        "raw_packet_copied_into_state_dir":False,"reviewer_trust_store_mutated":False,"production_packet_signed":False,
        "real_codex_request_executed":False,"windows_runtime_certified":False,"external_windows_target_evidence_imported":False,
        "production_score_promotion_eligible":False,"automatic_production_certification":False,"production_score_mutation_authorized":False}


def source_proof() -> dict:
    src = Path(__file__).read_text("utf-8"); operator_src = src[src.find("def _operator_preflight"):src.find("def _parse_utc")]
    status_src = src[src.find("def _reviewer_authority_status"):src.find("def _reviewer_release_authority_status")]
    release_status_src = src[src.find("def _reviewer_release_authority_status"):src.find("def _reviewer_import")]
    import_src = src[src.find("def _reviewer_import"):src.find("def source_proof")]
    checks = {
        "windows_gate": 'os.name != "nt"' in src,
        "operator_uses_runner_preflight_only": "evidence_runner.preflight" in operator_src and "evidence_runner.build_packet" not in operator_src,
        "operator_requires_source_certification_report": "source_certification_report=args.source_certification_report" in operator_src,
        "operator_never_executes_live_codex": '"real_codex_request_executed": False' in operator_src,
        "operator_never_signs_packet": '"production_packet_signed": False' in operator_src,
        "reviewer_trust_authority_captured_before_import": import_src.find("trust_authority.capture_authority") < import_src.find("reviewer_import.import_for_review"),
        "reviewer_release_authority_captured_before_import": import_src.find("release_authority.capture_authority") < import_src.find("reviewer_import.import_for_review"),
        "release_authority_uses_explicit_reviewed_inputs": all(x in import_src for x in ("args.reviewed_package_sha256","args.reviewed_manifest_sha256","args.reviewed_source_commit","args.reviewed_source_tree")),
        "reviewer_import_receives_release_authority": "release_authority_path=release_authority_path" in import_src,
        "reviewer_authority_status_is_verify_only": "trust_authority.load_and_verify_authority" in status_src and "capture_authority" not in status_src,
        "release_authority_status_is_verify_only": "release_authority.load_and_verify_authority" in release_status_src and "capture_authority" not in release_status_src,
        "reviewer_uses_high_level_import": "reviewer_import.import_for_review" in import_src,
        "reviewer_trust_store_not_mutated": '"reviewer_trust_store_mutated":False' in import_src,
        "raw_packet_not_copied": '"raw_packet_copied_into_state_dir":False' in import_src,
        "no_auto_certification": '"automatic_production_certification":False' in src,
        "no_score_mutation": '"production_score_mutation_authorized":False' in src,
    }
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"WINDOWS_EVIDENCE_ORCHESTRATOR_SOURCE_PROOF","verdict":"PASS" if passed==len(tests) else "FAIL",
        "summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,"real_windows_flow_executed":False,
        "windows_runtime_certified":False,"production_score_promotion_eligible":False}


def _add_common_certificate_args(ap):
    ap.add_argument("--package-zip", required=True); ap.add_argument("--release-manifest", required=True)
    ap.add_argument("--source-certification-report", required=True)
    ap.add_argument("--case-report", action="append", default=[], help="CASE_ID=PATH; repeat exactly seven times")
    ap.add_argument("--trust-store", required=True); ap.add_argument("--certificate-thumbprint", required=True)
    ap.add_argument("--certificate-sign-script", default=str(evidence_runner.DEFAULT_SIGN_SCRIPT)); ap.add_argument("--certificate-inspect-script", default=str(evidence_runner.DEFAULT_INSPECT_SCRIPT))
    ap.add_argument("--codex", default=""); ap.add_argument("--cockpit-baseline", default=COCKPIT_BASELINE)


def main() -> int:
    ap=argparse.ArgumentParser(description="Bounded HMS v25.75 Windows evidence orchestrator"); sub=ap.add_subparsers(dest="command"); sub.add_parser("proof")
    op=sub.add_parser("operator-preflight",help="Read-only prerequisites; no live Codex request and no packet signing"); _add_common_certificate_args(op)
    st=sub.add_parser("reviewer-authority-status",help="Read-only sealed signer authority freshness/integrity diagnostics")
    st.add_argument("--state-dir",required=True); st.add_argument("--authority-name",default=DEFAULT_AUTHORITY_NAME); st.add_argument("--authority-freshness-hours",type=int,default=24); st.add_argument("--renewal-warning-hours",type=int,default=4)
    rs=sub.add_parser("reviewer-release-authority-status",help="Read-only sealed release authority freshness/integrity diagnostics")
    rs.add_argument("--state-dir",required=True); rs.add_argument("--release-authority-name",default=DEFAULT_RELEASE_AUTHORITY_NAME); rs.add_argument("--release-authority-freshness-hours",type=int,default=168); rs.add_argument("--renewal-warning-hours",type=int,default=24)
    rv=sub.add_parser("reviewer-import",help="Capture sealed signer + explicit release authorities then import packet")
    rv.add_argument("--state-dir",required=True); rv.add_argument("--reviewer-trust-store",required=True); rv.add_argument("--packet",required=True)
    rv.add_argument("--package-zip",required=True); rv.add_argument("--release-manifest",required=True); rv.add_argument("--authority-name",default=DEFAULT_AUTHORITY_NAME)
    rv.add_argument("--release-authority-name",default=DEFAULT_RELEASE_AUTHORITY_NAME); rv.add_argument("--authority-freshness-hours",type=int,default=24)
    rv.add_argument("--release-authority-freshness-hours",type=int,default=168); rv.add_argument("--reviewed-package-sha256",required=True)
    rv.add_argument("--reviewed-manifest-sha256",required=True); rv.add_argument("--reviewed-source-commit",required=True); rv.add_argument("--reviewed-source-tree",required=True)
    rv.add_argument("--cockpit-baseline",default=COCKPIT_BASELINE)

    args=ap.parse_args(); command=args.command or "proof"
    if command=="proof": out=source_proof(); code=0 if out["verdict"]=="PASS" else 2
    else:
        try:
            if command=="operator-preflight": out=_operator_preflight(args)
            elif command=="reviewer-authority-status": out=_reviewer_authority_status(args)
            elif command=="reviewer-release-authority-status": out=_reviewer_release_authority_status(args)
            elif command=="reviewer-import": out=_reviewer_import(args)
            else: raise ValueError("UNKNOWN_COMMAND")
            code=0 if out.get("ready",True) and not str(out.get("verdict","")).startswith("BLOCKED") else 2
        except Exception as exc:
            out={"product":PRODUCT,"version":VERSION,"suite":"WINDOWS_EVIDENCE_ORCHESTRATOR","verdict":"BLOCKED_FAIL_CLOSED","command":command,
                 "error":type(exc).__name__,"detail":str(exc),"real_codex_request_executed":False,"production_packet_signed":False,
                 "windows_runtime_certified":False,"production_score_promotion_eligible":False,"automatic_production_certification":False}; code=2
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code


if __name__=="__main__": raise SystemExit(main())
