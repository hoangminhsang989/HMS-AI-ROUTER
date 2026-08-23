#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json
from datetime import datetime, timedelta, timezone

from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, verify_packet
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS
from HMS_Codex_WindowsPromotionDecisionLedger import VERSION, build_decision, evaluate, reviewer_ref
from HMS_Codex_WindowsPromotionReviewWorkbench import build_state

EV="e"*64; MAN="b"*64; PKG="a"*64

def _sha(text:str)->str:return hashlib.sha256(text.encode()).hexdigest()

def _packet(now:datetime)->dict:
    base={"source_classification":"REAL_EXTERNAL_WINDOWS_CODEX","synthetic":False,"local_only":False,
          "target_os":"Windows","codex_target":True,"package_zip_sha256":PKG,"release_manifest_sha256":MAN,
          "cockpit_baseline":COCKPIT_BASELINE,"capture_utc":now.isoformat(),"nonce":"nonce-e2e-0001",
          "run_id":"run-e2e-000001","report_id":"report-e2e-0001",
          "case_results":[{"case_id":cid,"status":"PASS","report_sha256":_sha(cid)} for cid in REQUIRED_RUNTIME_CASE_IDS]}
    packet=synthetic_signed_packet(base); packet["signer"].pop("synthetic_fixture",None); return packet

def _verify(packet:dict,now:datetime,*,seen=None,expected_anchor=None):
    anchor=expected_anchor if expected_anchor is not None else str((packet.get("trust_snapshot") or {}).get("trust_snapshot_sha256") or "")
    return verify_packet(packet,raw_packet_sha256=EV,expected_package_sha256=PKG,expected_manifest_sha256=MAN,
                         expected_trust_snapshot_sha256=anchor,current_cockpit_baseline=COCKPIT_BASELINE,seen=seen or {},now=now)

def _approval_set(*,one_reviewer=False):
    records=[]; a=reviewer_ref("fixture-reviewer-a","fixture-salt-00000001"); b=reviewer_ref("fixture-reviewer-b","fixture-salt-00000001")
    reviewers=(a,) if one_reviewer else (a,b)
    for lane in ("TERMINAL_PTY","PROJECT_RESUME"):
        for ref in reviewers:
            records.append(build_decision(records,decision="APPROVE",reviewer_ref=ref,evidence_sha256=EV,manifest_sha256=MAN,
                                          package_version=VERSION,cockpit_baseline=COCKPIT_BASELINE,lane=lane))
    return records,a,b

def synthetic_e2e_fixtures():
    now=datetime.now(timezone.utc); packet=_packet(now); approved_anchor=packet["trust_snapshot"]["trust_snapshot_sha256"]; good=_verify(packet,now,expected_anchor=approved_anchor)
    synthetic_packet=json.loads(json.dumps(packet)); synthetic_packet["synthetic"]=True; quarantine=_verify(synthetic_packet,now,expected_anchor=approved_anchor)
    signer_packet=json.loads(json.dumps(packet)); signer_packet["signer"]["signature_b64"]="not-base64"; signer_fail=_verify(signer_packet,now,expected_anchor=approved_anchor)
    trust_packet=json.loads(json.dumps(packet)); trust_packet["trust_snapshot"]["generation"]+=1; trust_fail=_verify(trust_packet,now,expected_anchor=approved_anchor)
    rogue_anchor_packet=_packet(now); rogue_anchor=_verify(rogue_anchor_packet,now,expected_anchor=approved_anchor)
    stale_packet=json.loads(json.dumps(packet)); stale_packet["capture_utc"]=(now-timedelta(hours=73)).isoformat(); stale=_verify(stale_packet,now,expected_anchor=approved_anchor)
    replay=_verify(packet,now,seen={"packet_digests":[EV]},expected_anchor=approved_anchor)
    baseline_packet=json.loads(json.dumps(packet)); baseline_packet["cockpit_baseline"]="1.3.29"; baseline_drift=_verify(baseline_packet,now,expected_anchor=approved_anchor)

    one_records,_,_=_approval_set(one_reviewer=True); single_review=evaluate(one_records,evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION)
    approved_records,a,b=_approval_set(); positive_review=evaluate(approved_records,evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION)
    rejected_records=list(approved_records); rejected_records.append(build_decision(rejected_records,decision="REJECT",reviewer_ref=a,
        evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION,cockpit_baseline=COCKPIT_BASELINE,lane="TERMINAL_PTY",reason_codes=["FIXTURE_REJECT"]))
    rejected=evaluate(rejected_records,evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION)
    invalidated_records=list(approved_records); invalidated_records.append(build_decision(invalidated_records,decision="INVALIDATE",reviewer_ref=b,
        evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION,cockpit_baseline="1.3.29",lane="PROJECT_RESUME",reason_codes=["BASELINE_DRIFT_LIVE_RECHECK"]))
    invalidated=evaluate(invalidated_records,evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION)
    optional_gpu=evaluate(approved_records,evidence_sha256=EV,manifest_sha256=MAN,package_version=VERSION,optional_gpu_required=True)
    workbench_drift=build_state(ingest_report=good,ledger_records=approved_records,package_version=VERSION,manifest_sha256=MAN,
        baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review="1.3.29",optional_gpu_required=False)

    checks={
        "positive_crypto_packet_verifies":good["real_packet_verified"] is True and good["trust_anchor_match"] is True,
        "canonical_exact_seven_cases":good["case_matrix"]["valid"] is True,
        "quarantine_synthetic_rejected":"SYNTHETIC_EVIDENCE_REJECTED" in quarantine["reasons"],
        "signature_failure_rejected":"CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED" in signer_fail["reasons"],
        "trust_snapshot_tamper_rejected":"TRUST_SNAPSHOT_DIGEST_MISMATCH" in trust_fail["reasons"],
        "rogue_self_anchor_rejected":"TRUST_ANCHOR_MISMATCH" in rogue_anchor["reasons"],
        "stale_evidence_rejected":"EVIDENCE_STALE" in stale["reasons"],
        "replay_rejected":"DUPLICATE_PACKET_DIGEST" in replay["reasons"],
        "baseline_drift_packet_rejected":"COCKPIT_BASELINE_CHANGED_OR_STALE" in baseline_drift["reasons"],
        "single_reviewer_never_promotes":not single_review["promotion_eligible"] and any(r.startswith("DUAL_REVIEW_INCOMPLETE:") for r in single_review["reasons"]),
        "two_reviewer_two_lane_positive_control":positive_review["promotion_eligible"] is True,
        "reject_freezes_promotion":not rejected["promotion_eligible"] and "CURRENT_EPOCH_REJECTED" in rejected["reasons"],
        "invalidate_freezes_promotion":not invalidated["promotion_eligible"] and "CURRENT_EPOCH_INVALIDATED" in invalidated["reasons"],
        "optional_gpu_required_blocks_without_gpu_reviews":not optional_gpu["promotion_eligible"] and "DUAL_REVIEW_INCOMPLETE:OPTIONAL_GPU" in optional_gpu["reasons"],
        "workbench_live_baseline_drift_freezes":workbench_drift["status"]=="FROZEN_BASELINE_DRIFT" and not workbench_drift["production_score_promotion_eligible"],
        "workbench_signature_trust_gates":good["signer_trust"]["valid"] and good["trust_anchor_match"],
        "no_fixture_grants_automatic_authority":all(v is False for v in (good["automatic_production_certification"],positive_review["automatic_production_certification"],
            positive_review["production_score_mutation_authorized"],workbench_drift["automatic_production_certification"],workbench_drift["production_score_mutation_authorized"]))}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; passed=sum(t["status"]=="PASS" for t in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_E2E_NEGATIVE_PATH_FIXTURES",
            "verdict":"PASS" if passed==len(tests) else "FAIL","summary":{"pass":passed,"fail":len(tests)-passed,"total":len(tests)},"tests":tests,
            "synthetic_fixture_only":True,"windows_runtime_certified":False,"production_score_promotion_eligible":False,
            "automatic_production_certification":False,"production_score_mutation_authorized":False}

if __name__=="__main__":
    result=synthetic_e2e_fixtures(); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result["verdict"]=="PASS" else 2)
