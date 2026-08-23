#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE, VERSION, verify_packet
from HMS_Codex_ExternalWindowsSignerTrustContract import synthetic_signed_packet
from HMS_Codex_WindowsRuntimeCaseContract import REQUIRED_RUNTIME_CASE_IDS
from HMS_Codex_WindowsPromotionDecisionLedger import append_decision, build_decision, read_ledger, reviewer_ref
from HMS_Codex_WindowsPromotionReviewWorkbench import build_state

HEX64=re.compile(r"^[0-9a-f]{64}$")


def _verified_report_gate(report):
    """Require the full persisted ingest contract before any ledger mutation.

    This is intentionally duplicated below the GUI/policy layer so a direct
    controller caller cannot gain review authority by setting only
    real_packet_verified=true in local metadata.
    """
    report=report if isinstance(report,dict) else {}; reasons=[]
    provenance=report.get("provenance") if isinstance(report.get("provenance"),dict) else {}
    signer_trust=report.get("signer_trust") if isinstance(report.get("signer_trust"),dict) else {}
    case_matrix=report.get("case_matrix") if isinstance(report.get("case_matrix"),dict) else {}
    if report.get("real_packet_verified") is not True: reasons.append("VERIFIED_REAL_PACKET_REQUIRED")
    if report.get("ingest_status")!="VERIFIED_REAL_PACKET": reasons.append("VERIFIED_INGEST_STATUS_REQUIRED")
    if report.get("case_matrix_complete") is not True or case_matrix.get("valid") is not True: reasons.append("EXACT_CASE_MATRIX_REQUIRED")
    if report.get("raw_evidence_rewritten") is not False: reasons.append("RAW_EVIDENCE_IMMUTABILITY_REQUIRED")
    if report.get("cockpit_baseline")!=COCKPIT_BASELINE: reasons.append("FROZEN_BASELINE_REQUIRED")
    if report.get("reasons") not in ([],None): reasons.append("INGEST_REASONS_MUST_BE_EMPTY")
    if signer_trust.get("valid") is not True: reasons.append("CRYPTOGRAPHIC_SIGNER_TRUST_REQUIRED")
    if report.get("trust_anchor_match") is not True: reasons.append("INDEPENDENT_TRUST_ANCHOR_REQUIRED")
    required_digests=("raw_packet_sha256","package_zip_sha256","release_manifest_sha256","trust_snapshot_sha256",
                      "expected_trust_snapshot_sha256","signature_sha256","certificate_sha256","signed_payload_sha256")
    for field in required_digests:
        value=str(provenance.get(field) or "").lower()
        if HEX64.fullmatch(value) is None: reasons.append("PROVENANCE_DIGEST_INVALID:"+field)
    if str(provenance.get("trust_snapshot_sha256") or "").lower()!=str(provenance.get("expected_trust_snapshot_sha256") or "").lower():
        reasons.append("PROVENANCE_TRUST_ANCHOR_MISMATCH")
    if str(signer_trust.get("trust_snapshot_sha256") or "").lower()!=str(provenance.get("trust_snapshot_sha256") or "").lower():
        reasons.append("SIGNER_TRUST_PROVENANCE_MISMATCH")
    if str(signer_trust.get("certificate_sha256") or "").lower()!=str(provenance.get("certificate_sha256") or "").lower():
        reasons.append("CERTIFICATE_PROVENANCE_MISMATCH")
    if str(signer_trust.get("signature_sha256") or "").lower()!=str(provenance.get("signature_sha256") or "").lower():
        reasons.append("SIGNATURE_PROVENANCE_MISMATCH")
    if not isinstance(provenance.get("required_case_ids"),list) or tuple(provenance.get("required_case_ids"))!=tuple(REQUIRED_RUNTIME_CASE_IDS):
        reasons.append("PROVENANCE_CASE_CONTRACT_MISMATCH")
    return {"valid":not reasons,"reasons":sorted(set(reasons)),"provenance":provenance}


class PromotionWorkbenchController:
    def __init__(self,state_dir):
        self.root=Path(state_dir); self.root.mkdir(parents=True,exist_ok=True)
        self.report_path=self.root/"verified_ingest_metadata.json"; self.replay_path=self.root/"replay_registry.json"; self.ledger_path=self.root/"promotion_decisions.jsonl"

    def _load_json(self,path,default):
        if not path.exists(): return default
        value=json.loads(path.read_text("utf-8")); return value if isinstance(value,type(default)) else default

    def _atomic_json(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as f:
                json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path)
        finally:
            try:
                if os.path.exists(tmp): os.unlink(tmp)
            except OSError: pass

    def ingest(self,packet_path,*,expected_package_sha256,expected_manifest_sha256,expected_trust_snapshot_sha256,
               current_cockpit_baseline=COCKPIT_BASELINE):
        path=Path(packet_path); raw=path.read_bytes(); packet=json.loads(raw.decode("utf-8-sig"))
        registry=self._load_json(self.replay_path,{"packet_digests":[],"nonces":[],"run_ids":[],"report_ids":[]})
        report=verify_packet(packet,raw_packet_sha256=hashlib.sha256(raw).hexdigest(),expected_package_sha256=expected_package_sha256,
            expected_manifest_sha256=expected_manifest_sha256,expected_trust_snapshot_sha256=expected_trust_snapshot_sha256,
            current_cockpit_baseline=current_cockpit_baseline,seen=registry)
        if report["real_packet_verified"]:
            gate=_verified_report_gate(report)
            if not gate["valid"]: raise ValueError("verified ingest metadata contract failed:"+",".join(gate["reasons"]))
            for key,value in (("packet_digests",report["provenance"]["raw_packet_sha256"]),("nonces",packet.get("nonce")),
                              ("run_ids",packet.get("run_id")),("report_ids",packet.get("report_id"))):
                items=registry.setdefault(key,[])
                if value not in items: items.append(value)
            self._atomic_json(self.report_path,report); self._atomic_json(self.replay_path,registry)
        return report

    def record_decision(self,*,decision,reviewer_identity,reviewer_salt,lane,package_version,
                        observed_cockpit_baseline=COCKPIT_BASELINE,reason_codes=None,note_vi=""):
        report=self._load_json(self.report_path,{})
        gate=_verified_report_gate(report)
        if not gate["valid"]: raise ValueError("verified ingest metadata required before review:"+",".join(gate["reasons"]))
        provenance=gate["provenance"]; records=read_ledger(self.ledger_path); ref=reviewer_ref(reviewer_identity,reviewer_salt)
        record=build_decision(records,decision=decision,reviewer_ref=ref,evidence_sha256=provenance.get("raw_packet_sha256",""),
            manifest_sha256=provenance.get("release_manifest_sha256",""),package_version=package_version,
            cockpit_baseline=observed_cockpit_baseline,lane=lane,reason_codes=reason_codes,note_vi=note_vi)
        append_decision(self.ledger_path,record)
        return {"reviewer_ref":ref,"decision_sha256":record["decision_sha256"],"epoch":record["epoch"],"decision":record["decision"],
                "lane":record["lane"],"observed_cockpit_baseline":record["cockpit_baseline"],"raw_reviewer_identity_stored":False}

    def record_review_action(self,*,decision,reviewer_identity,reviewer_salt,lane,package_version,
                             live_baseline_provider,reason_codes=None,note_vi=""):
        if not callable(live_baseline_provider): raise ValueError("live baseline provider required")
        live_baseline=str(live_baseline_provider() or "").strip()
        if not live_baseline: raise ValueError("live baseline recheck returned empty value")
        requested=str(decision or "").upper(); drift=live_baseline!=COCKPIT_BASELINE; effective="INVALIDATE" if drift and requested!="INVALIDATE" else requested
        reasons=list(reason_codes or [])
        if drift and "BASELINE_DRIFT_LIVE_RECHECK" not in reasons: reasons.append("BASELINE_DRIFT_LIVE_RECHECK")
        result=self.record_decision(decision=effective,reviewer_identity=reviewer_identity,reviewer_salt=reviewer_salt,lane=lane,
            package_version=package_version,observed_cockpit_baseline=live_baseline,reason_codes=reasons,note_vi=note_vi)
        result.update({"requested_decision":requested,"baseline_recheck_performed":True,"baseline_recheck_passed":not drift,
            "action_blocked_by_baseline_drift":drift and effective=="INVALIDATE","automatic_production_certification":False,
            "production_score_mutation_authorized":False})
        return result

    def state(self,*,package_version,manifest_sha256,baseline_at_open,baseline_before_final_review,optional_gpu_required=False):
        report=self._load_json(self.report_path,{})
        return build_state(ingest_report=report,ledger_records=read_ledger(self.ledger_path),package_version=package_version,
            manifest_sha256=manifest_sha256,baseline_at_open=baseline_at_open,baseline_before_final_review=baseline_before_final_review,
            optional_gpu_required=optional_gpu_required)

def synthetic_proof():
    h=lambda s:hashlib.sha256(s.encode()).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); packet_path=root/"external-review.json"; state_dir=root/"state"; now=datetime.now(timezone.utc)
        base={"source_classification":"REAL_EXTERNAL_WINDOWS_CODEX","synthetic":False,"local_only":False,"target_os":"Windows","codex_target":True,
            "package_zip_sha256":"a"*64,"release_manifest_sha256":"b"*64,"cockpit_baseline":COCKPIT_BASELINE,"capture_utc":now.isoformat(),
            "nonce":"nonce-012345","run_id":"run-01234567","report_id":"report-012345",
            "case_results":[{"case_id":cid,"status":"PASS","report_sha256":h(cid)} for cid in REQUIRED_RUNTIME_CASE_IDS]}
        packet=synthetic_signed_packet(base); packet["signer"].pop("synthetic_fixture",None); anchor=packet["trust_snapshot"]["trust_snapshot_sha256"]
        raw=(json.dumps(packet,ensure_ascii=False,sort_keys=True)+"\n").encode(); packet_path.write_bytes(raw)
        original=hashlib.sha256(raw).hexdigest(); ctl=PromotionWorkbenchController(state_dir)
        first=ctl.ingest(packet_path,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor)
        second=ctl.ingest(packet_path,expected_package_sha256="a"*64,expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor)
        rogue=synthetic_signed_packet(base); rogue["signer"].pop("synthetic_fixture",None); rogue_path=root/"rogue.json"
        rogue_path.write_text(json.dumps(rogue,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
        rogue_report=PromotionWorkbenchController(root/"rogue-state").ingest(rogue_path,expected_package_sha256="a"*64,
            expected_manifest_sha256="b"*64,expected_trust_snapshot_sha256=anchor)
        fake_ctl=PromotionWorkbenchController(root/"fake-state")
        fake_ctl._atomic_json(fake_ctl.report_path,{"real_packet_verified":True})
        fake_blocked=False
        try:
            fake_ctl.record_review_action(decision="APPROVE",reviewer_identity="reviewer-x",reviewer_salt="controller-proof-salt-01",
                lane="TERMINAL_PTY",package_version=VERSION,live_baseline_provider=lambda:COCKPIT_BASELINE)
        except ValueError:
            fake_blocked=True
        provider_calls=[]
        def frozen_provider(): provider_calls.append("frozen"); return COCKPIT_BASELINE
        for lane in ("TERMINAL_PTY","PROJECT_RESUME"):
            for identity in ("reviewer-a","reviewer-b"):
                ctl.record_review_action(decision="APPROVE",reviewer_identity=identity,reviewer_salt="controller-proof-salt-01",
                    lane=lane,package_version=VERSION,live_baseline_provider=frozen_provider)
        state=ctl.state(package_version=VERSION,manifest_sha256="b"*64,baseline_at_open=COCKPIT_BASELINE,baseline_before_final_review=COCKPIT_BASELINE)
        drift=ctl.record_review_action(decision="APPROVE",reviewer_identity="reviewer-a",reviewer_salt="controller-proof-salt-01",
            lane="TERMINAL_PTY",package_version=VERSION,live_baseline_provider=lambda:"1.3.29")
        checks={"verified_crypto_packet_persisted_metadata_only":first["real_packet_verified"] and first["trust_anchor_match"] and ctl.report_path.exists(),
                "persisted_report_passes_full_gate":_verified_report_gate(ctl._load_json(ctl.report_path,{}))["valid"],
                "raw_packet_unchanged":hashlib.sha256(packet_path.read_bytes()).hexdigest()==original,
                "replay_rejected":"DUPLICATE_PACKET_DIGEST" in second["reasons"],
                "rogue_self_anchor_rejected":"TRUST_ANCHOR_MISMATCH" in rogue_report["reasons"],
                "forged_minimal_metadata_cannot_write_ledger":fake_blocked and not fake_ctl.ledger_path.exists(),
                "two_reviewer_two_lane_state_eligible":state["production_score_promotion_eligible"],
                "live_baseline_rechecked_for_each_review":len(provider_calls)==4,
                "drift_blocks_requested_approve":drift["requested_decision"]=="APPROVE" and drift["decision"]=="INVALIDATE" and drift["action_blocked_by_baseline_drift"],
                "drift_records_observed_baseline":drift["observed_cockpit_baseline"]=="1.3.29",
                "controller_never_certifies":state["automatic_production_certification"] is False and drift["automatic_production_certification"] is False,
                "raw_reviewer_identity_not_in_ledger":"reviewer-a" not in ctl.ledger_path.read_text("utf-8") and "reviewer-b" not in ctl.ledger_path.read_text("utf-8"),
                "no_raw_packet_copy_in_state_dir":all(p.name!="external-review.json" for p in state_dir.iterdir())}
        tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)
        return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_WORKBENCH_CONTROLLER_PROOF",
                "verdict":"PASS" if n==len(tests) else "FAIL","summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},
                "tests":tests,"synthetic_fixture_only":True,"windows_runtime_certified":False,"production_score_mutation_authorized":False}

if __name__=="__main__":
    out=synthetic_proof(); print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out["verdict"]=="PASS" else 2)
