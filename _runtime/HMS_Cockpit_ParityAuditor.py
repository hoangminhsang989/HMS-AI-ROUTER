#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from datetime import datetime,timezone

WEIGHT_FEATURE={"SYNTHETIC_PASS":1.0,"IMPLEMENTED_PENDING_RUNTIME":0.72,"PARTIAL":0.45,"GAP":0.0}
WEIGHT_PROD={"SYNTHETIC_PASS":0.62,"IMPLEMENTED_PENDING_RUNTIME":0.35,"PARTIAL":0.2,"GAP":0.0}

def text(root,name):
    p=root/name
    return p.read_text("utf-8",errors="replace") if p.exists() else ""

def validation_pass(root,name):
    p=root/name
    if not p.exists():return False
    try:
        j=json.loads(p.read_text("utf-8-sig"))
        if str(j.get("verdict") or "").startswith("PASS") and j.get("summary",{}).get("fail",0) == 0:
            return True
        return bool(j.get("ok")) and j.get("data",{}).get("summary",{}).get("fail")==0
    except:return False

def status(condition,validated=False,partial=False):
    if condition and validated:return "SYNTHETIC_PASS"
    if condition:return "IMPLEMENTED_PENDING_RUNTIME"
    if partial:return "PARTIAL"
    return "GAP"

def audit(root:Path):
    main=""
    for candidate in ("HMS_AI_ROUTER_v25.23.1.ps1","HMS_AI_v25.12.ps1","HMS_AI_v25.11.ps1","HMS_AI_v25.10.ps1","HMS_AI_v25.9.ps1","HMS_AI_v25.8.ps1","HMS_AI_v25.7.ps1","HMS_AI_v25.6.ps1","HMS_AI_v25.5.ps1","HMS_AI_v25.4.ps1","HMS_AI_v25.3.ps1","HMS_AI_v25.2.ps1","HMS_AI_v25.1.ps1","HMS_AI_v25.0.ps1","HMS_AI_v24.0.ps1"):
        main=text(root,candidate)
        if main:break
    gw=text(root,"HMS_Codex_SmartGateway.py")
    ctl=text(root,"HMS_Codex_GatewayControl.py")
    inst=text(root,"HMS_Codex_AccountSessionIndex.py")+text(root,"HMS_Codex_ThreadSync.py")
    session_doctor=text(root,"HMS_Codex_SessionDoctor.py")
    proxy=text(root,"HMS_Codex_ProxyFleet.py")+text(root,"HMS_Codex_EgressGuard.py")
    analytics=text(root,"HMS_Codex_ApiAnalytics.py")
    v24=(validation_pass(root,"API_SUPERSET_VALIDATION_V25.46.json") or
         validation_pass(root,"API_SUPERSET_VALIDATION_V24.json"))
    proto=(validation_pass(root,"PROTOCOL_VALIDATION_V25.46.json") or
           validation_pass(root,"PROTOCOL_VALIDATION_V21.json"))
    proxyv=(validation_pass(root,"PROXY_FLEET_VALIDATION_V25.46.json") or
            validation_pass(root,"PROXY_FLEET_VALIDATION_V23.json"))
    soakv=validation_pass(root,"RELIABILITY_SOAK_VALIDATION_V25.47.json")
    soak_engine=bool(text(root,"HMS_Codex_ReliabilitySoak.py"))
    perfv=validation_pass(root,"PERFORMANCE_SCALE_VALIDATION_V25.48.json")
    perf_engine=bool(text(root,"HMS_Codex_PerformanceScale.py"))
    realcertv=validation_pass(root,"REAL_CODEX_CERT_VALIDATION_V25.49.json")
    realcert_engine=bool(text(root,"HMS_Codex_RealCertification.py"))
    livequotav=validation_pass(root,"LIVE_QUOTA_INTELLIGENCE_VALIDATION_V25.50.json")
    rotationv=validation_pass(root,"SEAMLESS_ROTATION_TORTURE_VALIDATION_V25.51.json")
    uxv=validation_pass(root,"UX_COCKPIT_PARITY_VALIDATION_V25.52.json")
    targetcertv=validation_pass(root,"TARGET_MACHINE_CERTIFICATION_VALIDATION_V25.53.json")
    simulationv=validation_pass(root,"PRODUCTION_SIMULATION_VALIDATION_V25.54.json")
    routertwinv=validation_pass(root,"AUTONOMOUS_ROUTER_TWIN_VALIDATION_V25.55.json")
    protocolchaosv=validation_pass(root,"PROTOCOL_CHAOS_FUZZER_VALIDATION_V25.56.json")
    recoveryplannerv=validation_pass(root,"RECOVERY_PLANNER_VALIDATION_V25.57.json")
    compoundfaultv=validation_pass(root,"COMPOUND_FAULT_RECOVERY_VALIDATION_V25.58.json")
    officialauthv=validation_pass(root,"OFFICIAL_AUTH_COMPAT_VALIDATION_V25.59.json")
    officialauth_engine=bool(text(root,"HMS_Codex_OfficialAuthCompatibility.py"))
    recoveryjournalv=validation_pass(root,"RECOVERY_TRANSACTION_JOURNAL_VALIDATION_V25.60.json")
    recoveryjournal_engine=bool(text(root,"HMS_Codex_RecoveryTransactionJournal.py"))
    usage_token_v=validation_pass(root,"USAGE_TOKEN_CENTER_VALIDATION_V25.61.json")
    recovery_replay_v=validation_pass(root,"RECOVERY_TRANSACTION_REPLAY_VALIDATION_V25.62.json")
    startup_recovery_v=validation_pass(root,"STARTUP_RECOVERY_RECONCILER_VALIDATION_V25.63.json")
    target_crash_v=validation_pass(root,"TARGET_CRASH_HARNESS_VALIDATION_V25.63.json")
    windows_observer_v=validation_pass(root,"WINDOWS_RECOVERY_OBSERVER_BRIDGE_VALIDATION_V25.64.json")
    real_effect_v=validation_pass(root,"REAL_EFFECT_CRASH_CERT_VALIDATION_V25.65.json") or validation_pass(root,"REAL_EFFECT_CRASH_CERT_VALIDATION_V25.64.json")
    target_evidence_v=validation_pass(root,"TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.65.json") or validation_pass(root,"TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.64.json")
    target_adapter_v=validation_pass(root,"WINDOWS_TARGET_ADAPTER_PACK_VALIDATION_V25.65.json")
    promotion_gate_v=validation_pass(root,"ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.66.json") or validation_pass(root,"ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.65.json")
    recovery_timeline_v=validation_pass(root,"RECOVERY_OPERATOR_TIMELINE_VALIDATION_V25.65.json")
    windows_signer_v=validation_pass(root,"WINDOWS_ATTESTATION_SIGNER_VALIDATION_V25.66.json")
    target_runbook_v=validation_pass(root,"TARGET_CERTIFICATION_RUNBOOK_VALIDATION_V25.66.json")
    attestation_exchange_v=validation_pass(root,"ATTESTATION_EXCHANGE_VALIDATION_V25.66.json")
    trust_store_v=validation_pass(root,"ATTESTATION_TRUST_STORE_VALIDATION_V25.67.json")
    offline_verifier_v=validation_pass(root,"OFFLINE_ATTESTATION_VERIFIER_VALIDATION_V25.67.json")
    target_campaign_v=validation_pass(root,"TARGET_CERTIFICATION_CAMPAIGN_VALIDATION_V25.67.json")
    target_campaign_executor_v=validation_pass(root,"TARGET_CAMPAIGN_EXECUTOR_VALIDATION_V25.68.json")
    promotion_review_console_v=validation_pass(root,"ATTESTED_PROMOTION_REVIEW_CONSOLE_VALIDATION_V25.68.json")
    evidence_ingest_v=validation_pass(root,"TARGET_CERTIFICATION_EVIDENCE_INGEST_VALIDATION_V25.69.json")
    promotion_ledger_v=validation_pass(root,"PROMOTION_DECISION_LEDGER_VALIDATION_V25.69.json")
    cockpit1327_v=validation_pass(root,"COCKPIT_1327_PARITY_RESET_VALIDATION_V25.72.json") or validation_pass(root,"COCKPIT_1327_PARITY_RESET_VALIDATION_V25.70.json")
    usage1327_v=validation_pass(root,"COCKPIT_1327_SOURCE_INTEGRATION_VALIDATION_V25.72.json") or validation_pass(root,"COCKPIT_1327_SOURCE_INTEGRATION_VALIDATION_V25.70.json")
    runtime1327_v=(validation_pass(root,"COCKPIT_1327_WINDOWS_RUNTIME_CERTIFICATION_VALIDATION_V25.72.json") or validation_pass(root,"COCKPIT_1327_WINDOWS_RUNTIME_CERTIFICATION_VALIDATION_V25.71.json"))
    promotion_auditor_v=(validation_pass(root,"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR_VALIDATION_V25.72.json") or validation_pass(root,"PRODUCTION_EVIDENCE_PROMOTION_AUDITOR_VALIDATION_V25.71.json"))
    target_capture_v=validation_pass(root,"WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT_VALIDATION_V25.72.json")
    baseline_watch_v=validation_pass(root,"COCKPIT_BASELINE_WATCH_GATE_VALIDATION_V25.72.json")
    import_review_v=validation_pass(root,"WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW_VALIDATION_V25.73.json")
    baseline_delta_v=validation_pass(root,"BASELINE_DELTA_WATCH_AUTOMATION_VALIDATION_V25.73.json")
    review_packet_v=validation_pass(root,"REVIEW_PACKET_VALIDATION_V25.74.json") or validation_pass(root,"EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET_VALIDATION_V25.74.json")
    baseline_reconcile_v=validation_pass(root,"BASELINE_DRIFT_RECONCILIATION_VALIDATION_V25.74.json")
    livequota_engine=bool(text(root,"HMS_Codex_LiveQuotaIntelligence.py"))

    rows=[]
    def add(id,label,cockpit,hms,notes,benchmark=True):
        rows.append({"id":id,"label":label,"cockpit_reference":cockpit,"hms_status":hms,"notes":notes,"benchmark":benchmark})

    add("multi_account","Codex multi-account management","YES",status("Get-CodexAccountRecords" in main,False),
        "HMS account pool exists; real Windows account lifecycle still pending.")
    add("multi_instance","Codex isolated multi-instance","YES",status("CodexInstance" in main and bool(inst),False),
        "HMS has isolated instance/fleet/session layers; target-PC runtime certification pending.")
    add("quota_plan","Hourly/weekly quota + plan recognition","YES",status("Snapshot-CodexQuotaHistory" in main,False,True),
        "HMS has quota history/metadata, but live fidelity across OAuth/PAT/Team remains runtime gap.")
    add("named_keys","Named local client API keys","YES",status("class KeyStore" in gw and "create-key" in ctl,v24),
        "Digest-only key store; plaintext shown only at creation.")
    add("per_key_model","Per-key model allow/deny + prefix","YES",status("model_prefix" in gw and "model_allow" in gw,v24),
        "v24 adds model prefix exposure/rewriting plus existing allow/deny.")
    add("routing_modes","Auto/random/single/quota/plan/expiry/custom routing","YES",
        status(all(x in gw for x in ['strategy=="random"','strategy=="single"','strategy=="quota-first"','strategy=="plan-first"','strategy=="expiry-soon"','strategy=="auto"']),v24),
        "v24 closes current Cockpit routing-mode gap.")
    add("priority_weight_backup","Priority/weight/backup routing","YES",
        status("_effective_priority" in gw and "_effective_weight" in gw and "_backup" in gw,v24),
        "Can be overridden per client key.")
    add("per_key_pool","Per-key target/account pool","NOT_CORE_REFERENCE",
        status("target_allow" in gw and "target_deny" in gw,v24),
        "HMS extension: each client key can have its own target subset.",benchmark=False)
    add("quota_reserve","Fresh quota reserve fail-closed","YES",
        status("quota_reserve_fail_closed" in gw and "quota_evidence_fresh" in gw,v24),
        "Requires real quota metadata feed for production.")
    add("affinity_health","Session affinity + cooldown/failover","YES",
        status("_affinity_key" in gw and "cooldown_until" in gw,proto),
        "Affinity is client-key scoped in v24.")
    add("http_surface","Models/chat/responses/backend Codex generic HTTP surface","YES",
        status("def _proxy" in gw,proto),
        "HMS generic relay covers paths; exact real-Codex compatibility remains target-PC gate.")
    add("websocket","Responses WebSocket relay","YES",status("def _websocket" in gw,proto),
        "Synthetic handshake/relay/failover PASS.")
    add("images","Image endpoint compatibility","YES",status("def _proxy" in gw,False,True),
        "Generic relay exists, but no dedicated image-tool mapping/concurrency scheduler in HMS yet.")
    add("cors","Local CORS preflight","YES",status("_cors_preflight" in gw,v24),
        "Loopback-origin allowlist by default.")
    add("usage_stats","Daily/week/month/all usage by account/model/key","YES",
        status("by_client_key" in analytics and '"month"' in analytics,v24),
        "Trace-derived analytics; token coverage depends on upstream usage fields.")
    add("pricing","Custom model pricing + estimated value","YES",
        status("estimate_cost" in gw and "set-price" in ctl,v24),
        "No hard-coded possibly stale prices; operator supplies pricing.")
    add("diagnostics","Request ID/account/retry/timing diagnostics","YES",
        status("attempt_rows" in gw and "X-HMS-Selected-Target" in gw,proto),
        "HMS also captures TTFT/bytes/protocol telemetry.")
    add("profile_takeover","Backup/restore managed Codex profile","YES",
        status("Backup" in main and "Codex" in main,False,True),
        "HMS safety architecture exists but needs explicit Windows runtime proof.")
    add("session_repair","Session/history visibility repair","YES",
        status("state_5.sqlite" in session_doctor and "update threads set model_provider" in session_doctor.lower(),v24),
        "HMS Session Doctor backs up session metadata and repairs known state_5.sqlite thread provider fields.")
    add("timeout_retry","Advanced timeout/retry/stream controls","YES",
        status("upstream_timeout_sec" in gw and "max_failover_attempts" in gw and "websocket_idle_timeout_sec" in gw,proto),
        "Some Cockpit presets/controls remain richer in UI.")
    add("proxy_fail_closed","Proxy fail-closed egress","YES",
        status("QUARANTINE_EGRESS_DRIFT" in proxy and "strict_block" in proxy,proxyv),
        "HMS Proxy Fleet is deeper than baseline proxy-url handling.")
    add("egress_integrity","Public-IP baseline/drift/quarantine","NOT_CORE_REFERENCE",
        status("expected_ip" in proxy and "DRIFT" in proxy,proxyv),
        "HMS-specific control-plane extension.",benchmark=False)
    add("ha_soak_policy","HA + Soak + Policy Kernel","NOT_CORE_REFERENCE",
        status("Show-HmsPolicyKernelCenter" in main and soak_engine,soakv),
        "v25.47 resumable soak harness synthetic PASS; real 6h/24h Windows soak still pending.",benchmark=False)
    add("runtime_evidence","Windows source/runtime evidence gates","NOT_CORE_REFERENCE",
        status("Show-HmsWindowsRuntimeGateCenter" in main,False),
        "HMS-specific certification layer; real target-PC gate has not been executed.",benchmark=False)
    add("performance_scale","Performance / scale + bounded backpressure","NOT_CORE_REFERENCE",
        status(perf_engine,perfv),
        "v25.48 synthetic/local control-plane benchmark PASS; real Codex model TTFT and Windows scale evidence remain deferred.",benchmark=False)
    add("real_codex_certification","Real Codex target-machine certification harness","NOT_CORE_REFERENCE",
        status(realcert_engine,realcertv),
        "v25.49 harness/validator PASS; build host is non-Windows without live Codex, so real target-machine certification is explicitly deferred.",benchmark=False)
    add("live_quota_intelligence","Last-good quota freshness + plan reserve fail-closed","NOT_CORE_REFERENCE",
        status(livequota_engine,livequotav),
        "v25.50 synthetic gate PASS; real Free/Plus/Pro quota fidelity on Windows remains target-machine evidence and does not increase parity score.",benchmark=False)
    add("seamless_rotation_torture","Seamless rotation torture regression gate","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if rotationv else "GAP",
        "v25.51 1000-cycle synthetic rotation torture is a regression/safety gate only; it does not increase production parity without target-machine evidence.",benchmark=False)
    add("target_machine_certification","Target-machine production certification aggregator","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if targetcertv else "GAP",
        "v25.53 aggregator/negative validator PASS; production score remains unchanged until its real Windows/Codex/quota/failover/LAN/6h/24h evidence itself returns PASS.",benchmark=False)
    add("ux_cockpit_parity_plus","Unified operator UX + route/quota decision surface","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if uxv else "GAP",
        "v25.52 native + loopback read-only Unified UX exposes route eligibility, hold/stale reasons, active route and local filters while preserving the frozen public backend contract.",benchmark=False)
    add("production_simulation_lab","Deterministic production digital twin + fault injection","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if simulationv else "GAP",
        "v25.54 multi-seed/replayable control-plane simulation exercises quota/429/crash/auth/backpressure/SMB/LAN/clock-skew but never increases production evidence score.",benchmark=False)
    add("autonomous_router_digital_twin","Autonomous router large-pool digital twin + bounded model checking","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if routertwinv else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.55 32-account/12-instance/24-project twin + 3,072-state bounded checker + minimized counterexample; synthetic-only and does not increase production evidence.",benchmark=False)
    add("protocol_chaos_fuzzer","Protocol chaos / API compatibility fuzzer","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if protocolchaosv else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.56 deterministic SSE/WebSocket/JSON/chunked/retry/EOF fuzzing plus gateway integrity hardening; synthetic-only and does not increase production evidence.",benchmark=False)
    add("recovery_planner_decision_proof","Cause-aware recovery planner + self-healing decision proof","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if recoveryplannerv else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.57 cause-aware bounded recovery, rollback proof, loop breaker and 9,216-state safety checker; synthetic-only and does not increase production evidence.",benchmark=False)
    add("compound_fault_recovery_convergence","Compound-fault recovery DAG + global convergence proof","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if compoundfaultv else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.58 compound-fault DAG/global budget with 72,960-state convergence checker to HEALTHY/DEGRADED_SAFE/OPERATOR_REQUIRED; synthetic-only and does not increase production evidence.",benchmark=False)
    add("official_auth_v1324","Official Codex auth compatibility / account switching","YES",
        "SYNTHETIC_PASS" if officialauthv else ("IMPLEMENTED_PENDING_RUNTIME" if officialauth_engine else "GAP"),
        "v25.59 established Cockpit v1.3.24 auth semantics; v25.70 re-baselines compatibility to Cockpit v1.3.27 while retaining file/direct-keyring/auto semantics, pre-switch snapshot, serialized field-preserving rewrite, stale-credential cleanup, version-derived Codex identity and controlled restart; encrypted Secrets backend is detected/fail-closed until an official Codex helper is available.",benchmark=False)
    add("recovery_transaction_journal","Crash-consistent recovery transaction journal","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if recoveryjournalv else ("IMPLEMENTED_PENDING_RUNTIME" if recoveryjournal_engine else "GAP"),
        "v25.60 durable hash-chain PREPARE/COMMIT/VERIFY/DONE-or-ROLLBACK journal prevents duplicate auth rewrite/restart/lease reelection after crash; synthetic-only and does not increase production evidence.",benchmark=False)
    add("usage_token_center","Native Usage & Token Center parity+","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if usage_token_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.61 read-only plan/quota/reset/package-expiry/OAuth-lifecycle interpretation, source/freshness and scenario-only after-reset preview; synthetic/control-plane evidence only and does not increase production evidence.",benchmark=False)
    add("recovery_transaction_replay","Multi-subsystem recovery transaction replay","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if recovery_replay_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.62 idempotent replay/verification and reverse-DAG compensation across auth/restart/router/LAN effects with operator-required fail-closed convergence; synthetic-only and does not increase production evidence.",benchmark=False)
    add("startup_recovery_reconciler","Startup recovery reconciler","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if startup_recovery_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.63 cold-start journal discovery, metadata/digest-only external observation and mutation preflight gating; target Windows/Codex live observation remains required.",benchmark=False)
    add("target_crash_injection_harness","Target-machine crash injection harness foundation","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_crash_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.63 executes real subprocess kill/cold-start recovery in a lab state model, but real Codex effects and Windows target-machine evidence are explicitly not claimed.",benchmark=False)
    add("windows_recovery_observer_bridge","Live Windows recovery observer bridge foundation","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if windows_observer_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.64 observer/evidence contracts are validated without claiming a live Windows target run; real target evidence remains required.",benchmark=False)
    add("real_effect_crash_certification","Controlled real-effect crash certification contract","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if real_effect_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.64/v25.65 real-effect mode remains DISARMED by default and cannot directly promote production score.",benchmark=False)
    add("target_recovery_evidence_bundle","Target recovery evidence bundle","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_evidence_v else "IMPLEMENTED_PENDING_RUNTIME",
        "Target evidence bundle is an attestation candidate only; bundle presence alone never certifies production.",benchmark=False)
    add("windows_target_adapter_pack","Windows Target Adapter Pack","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_adapter_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.65 structured-argv adapters expose digest/idempotency witnesses only; synthetic/control-plane validation does not increase production score.",benchmark=False)
    add("attested_evidence_promotion_gate","Attested Evidence Promotion Gate","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if promotion_gate_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.65 centralizes promotion eligibility behind nonce/run/package/signer/freshness/hash-chain and complete 4x3 crash-matrix validation. No target attestation is bundled in this release.",benchmark=False)
    add("recovery_operator_timeline","Vietnamese Recovery Operator Timeline","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if recovery_timeline_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.65 metadata-only Vietnamese timeline improves operator evidence visibility and is non-benchmark control-plane evidence.",benchmark=False)
    add("windows_attestation_signer","Windows-local cryptographic attestation signer","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if windows_signer_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.66 validates DPAPI/certificate signing contracts and cryptographic verification using safe fixtures; no Windows target signing was executed in this build.",benchmark=False)
    add("controlled_target_certification_runbook","One-shot controlled target certification runbook","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_runbook_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.66 locks dry-run/preflight/operator arming/auto-disarm workflow; target mode remains disarmed and requires real Windows integration.",benchmark=False)
    add("attestation_exchange","Privacy-safe attestation export/import and Vietnamese promotion explanation","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if attestation_exchange_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.66 verifies bundle integrity/privacy and explains promotion decisions without making automatic production certification claims.",benchmark=False)
    add("attestation_trust_store","Windows attestation trust store / certificate lifecycle","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if trust_store_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.67 certificate pinning/rotation/revocation plus DPAPI lifecycle metadata and deterministic trust snapshot; control-plane evidence only.",benchmark=False)
    add("offline_attestation_verifier","Offline trust-snapshot attestation verifier","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if offline_verifier_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.67 verifies package/signature/trust state without account credentials or network; synthetic certificate fixture does not raise production score.",benchmark=False)
    add("resumable_target_cert_campaign","Resumable 4x3 target certification campaign","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_campaign_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.67 one-shot per-case campaign journal resumes via VERIFY_ONLY/ATTEST_ONLY/OPERATOR_REQUIRED and never silently repeats durable effects.",benchmark=False)
    add("target_campaign_executor","Windows-only one-case target campaign executor","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_campaign_executor_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.68 binds one explicitly armed case to frozen manifest/trust snapshot, Windows/PS5.1/Codex observer preflight and idempotency witness; synthetic proof never executes real effects.",benchmark=False)
    add("attested_promotion_review_console","Attested 12-case promotion review console","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if promotion_review_console_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.68 reviews exactly 12 signed reports with freshness/revocation/mixed-version checks and Vietnamese human-review decision; no automatic production certification.",benchmark=False)
    add("target_certification_evidence_ingest","Read-only Windows target certification evidence ingest","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if evidence_ingest_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.69 verifies cryptographic binding/replay/trust/package/campaign state and quarantines invalid imported reports without executing target effects or auto-repair.",benchmark=False)
    add("promotion_decision_ledger","Append-only dual-review promotion decision ledger","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if promotion_ledger_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.69 hash-chained reviewer decisions require two distinct pseudonymous reviewers and superseding invalidation entries; promotion eligibility remains separate from production score mutation.",benchmark=False)
    add("cockpit_1327_parity_reset","Cockpit Tools v1.3.27 Codex parity reset","YES",
        "SYNTHETIC_PASS" if cockpit1327_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.70 resets the competitive baseline from Cockpit v1.3.24 to v1.3.27 and audits the Codex-only changes from v1.3.25-v1.3.27 without weakening HMS transactional/fail-closed guarantees.",benchmark=False)
    add("cockpit_1327_source_integration","Cockpit v1.3.27 source-level parity integration","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if usage1327_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.70 integrates runtime foreign-port rebind, launch-time account occupancy, client/API split state, official-account-ref usage continuity, bounded credential backups, WebSocket preservation, composite conversation identity and live-only model context metadata. Windows runtime proof remains pending.",benchmark=False)
    add("cockpit_1327_windows_runtime_certification","Cockpit v1.3.27 Windows runtime parity certification","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if runtime1327_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.71 defines seven target cases bound to external Windows/Codex signed evidence. Synthetic validation proves the gate contract only; windows_runtime_certified remains false until external evidence is imported.",benchmark=False)
    add("production_evidence_promotion_auditor","Production evidence promotion proposal auditor","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if promotion_auditor_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.71 re-verifies runtime certificate, dual-review chain and current Cockpit baseline, then may propose human review only. It never mutates production score or auto-certifies.",benchmark=False)
    add("windows_target_evidence_capture_kit","Portable Windows target evidence capture kit","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if target_capture_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.72 packages seven one-case target capture flows with exact ZIP/manifest/Codex binding, privacy-safe signed reports and DISARMED default. Real Windows execution remains external.",benchmark=False)
    add("cockpit_baseline_watch_gate","Cockpit public baseline watch and promotion freeze gate","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if baseline_watch_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.72 freezes target campaign/promotion whenever public Cockpit is newer than 1.3.27 and requires a Codex-only delta audit before continuing.",benchmark=False)
    add("windows_target_evidence_import_review","Seven-case Windows target evidence import review","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if import_review_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.73 verifies the seven v25.72 runtime-parity reports with exact package/manifest/trust/signature/replay/freshness binding and dual-review ledger semantics; synthetic fixtures never certify Windows runtime.",benchmark=False)
    add("baseline_delta_watch_automation","Two-checkpoint Cockpit baseline delta watch automation","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if baseline_delta_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.73 rechecks Cockpit before import and before promotion review; any newer public baseline freezes promotion and queues Codex-only delta audit without auto-merge.",benchmark=False)
    add("external_windows_evidence_review_packet","Immutable external Windows evidence review packet","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if review_packet_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.74 derives a privacy-safe hash-chained review packet from seven target report digests and pseudonymous append-only review metadata; raw evidence is never normalized in place or embedded.",benchmark=False)
    add("baseline_drift_reconciliation","Baseline drift eligibility invalidation and capability reuse reconciliation","NOT_CORE_REFERENCE",
        "SYNTHETIC_PASS" if baseline_reconcile_v else "IMPLEMENTED_PENDING_RUNTIME",
        "v25.74 freezes review packets on newer Cockpit baselines, generates superseding INVALIDATE ledger entries, and allows evidence reuse only after Codex-only capability binding plus a new dual-review epoch; no silent grandfathering.",benchmark=False)

    bench=[r for r in rows if r["benchmark"]]
    fscore=sum(WEIGHT_FEATURE[r["hms_status"]] for r in bench)/max(1,len(bench))*100
    pscore=sum(WEIGHT_PROD[r["hms_status"]] for r in bench)/max(1,len(bench))*100

    gaps=[r["id"] for r in bench if r["hms_status"] in ("GAP","PARTIAL")]
    pending=[r["id"] for r in bench if r["hms_status"]=="IMPLEMENTED_PENDING_RUNTIME"]
    verdict=("FEATURE_PARITY_CANDIDATE" if fscore>=80 else "BELOW_FEATURE_PARITY")
    return {
        "version":"25.74","generated_utc":datetime.now(timezone.utc).isoformat(),
        "cockpit_baseline":{
            "label":"Cockpit current release v1.3.27",
            "evidence_note":"Public GitHub releases v1.3.25, v1.3.26 and latest v1.3.27 confirmed on 2026-08-23; Codex-only parity scope preserved.",
            "production_maturity":"PUBLIC_RELEASED"
        },
        "hms":{
            "verdict":verdict,
            "feature_evidence_score_pct":round(fscore,1),
            "production_evidence_score_pct":round(pscore,1),
            "windows_runtime_certified":False,
            "gaps":gaps,"runtime_pending":pending
        },
        "capabilities":rows,
        "interpretation":{
            "feature_score":"Evidence-weighted implementation/parity score, not a benchmark of real throughput.",
            "production_score":"Penalizes synthetic/static-only evidence. It is intentionally much lower until Windows runtime gates pass.",
            "no_superset_claim":"HMS must not be called a production superset until the v25.49 live target-machine Real Codex gate, v25.50 real Free/Plus/Pro quota fidelity gate, v25.51 target-machine rotation torture, v25.52 UX target-machine review and the v25.53 seven-stage real target-machine certificate pass. v25.54 simulation, v25.55 autonomous-router model checking, v25.56 protocol chaos fuzzing, v25.57 recovery decision proof, v25.58 compound-fault convergence proof, v25.59 official-auth compatibility fixtures, v25.60 crash-consistent recovery journal proof, v25.61 Usage & Token Center proof, v25.62 transaction replay proof, and v25.63 startup-recovery/crash-lab proof, v25.64 Windows-observer/real-effect contract proof, and v25.65 adapter/attestation/promotion/timeline proof plus v25.66 cryptographic signer/runbook/exchange proof and v25.67 trust-store/offline-verifier/resumable-campaign proof plus v25.68 one-case executor/promotion-review proof and v25.69 evidence-ingest/dual-review-ledger proof and v25.70 Cockpit-v1.3.27 parity reset/source-integration proof plus v25.71 Windows-runtime-certification/promotion-auditor contract proof and v25.72 portable target-capture/baseline-watch proof plus v25.73 seven-case import-review/two-checkpoint baseline-delta-watch proof and v25.74 immutable-review-packet/baseline-drift-reconciliation proof are explicitly non-production evidence until real Windows/Codex evidence is imported, cryptographically validated, dual-reviewed and separately audited for production-score promotion."
        }
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--output")
    a=ap.parse_args();data=audit(Path(a.root));txt=json.dumps({"ok":True,"data":data},ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt)

if __name__=="__main__":main()
