#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile,os,signal,time
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.74'

def run(root:Path, checkpoint:Path|None=None):
    with tempfile.TemporaryDirectory(prefix='hms-v2574-regression-') as td:
        temp=Path(td)
        suites=[
          ('compatibility_freeze',[sys.executable,'HMS_Codex_CompatibilityFreezeValidator.py','--root',str(root)]),
          ('client_compatibility',[sys.executable,'HMS_Codex_ClientCompatibilityValidator.py','--root',str(root)]),
          ('lan_pool',[sys.executable,'HMS_Codex_LanPoolValidator.py']),
          ('lan_failure_matrix',[sys.executable,'HMS_Codex_LanFailureMatrixValidator.py']),
          ('reliability_soak_harness',[sys.executable,'HMS_Codex_ReliabilitySoakValidator.py']),
          ('performance_scale',[sys.executable,'HMS_Codex_PerformanceScaleValidator.py']),
          ('real_codex_certification',[sys.executable,'HMS_Codex_RealCertificationValidator.py','--root',str(root)]),
          ('live_quota_intelligence',[sys.executable,'HMS_Codex_LiveQuotaIntelligenceValidator.py']),
          ('seamless_rotation_torture',[sys.executable,'HMS_Codex_SeamlessRotationTortureValidator.py']),
          ('ux_cockpit_parity_plus',[sys.executable,'HMS_Codex_UxParityValidator.py','--root',str(root),'--output',str(temp/'ux-v2552.json')]),
          ('target_machine_certification',[sys.executable,'HMS_Codex_TargetMachineCertificationValidator.py','--root',str(root)]),
          ('production_simulation_lab',[sys.executable,'HMS_Codex_ProductionSimulationLabValidator.py','--root',str(root)]),
          ('autonomous_router_digital_twin',[sys.executable,'HMS_Codex_AutonomousRouterDigitalTwinValidator.py','--root',str(root)]),
          ('protocol_chaos_fuzzer',[sys.executable,'HMS_Codex_ProtocolChaosFuzzerValidator.py','--root',str(root)]),
          ('recovery_planner',[sys.executable,'HMS_Codex_RecoveryPlannerValidator.py','--root',str(root)]),
          ('compound_fault_recovery',[sys.executable,'HMS_Codex_CompoundFaultRecoveryValidator.py','--root',str(root)]),
          ('official_auth_compatibility',[sys.executable,'HMS_Codex_OfficialAuthCompatibilityValidator.py','--root',str(root)]),
          ('recovery_transaction_journal',[sys.executable,'HMS_Codex_RecoveryTransactionJournalValidator.py','--root',str(root)]),
          ('usage_token_center',[sys.executable,'HMS_Codex_UsageTokenCenterValidator.py','--root',str(root),'--output',str(temp/'usage-token-v2561.json')]),
          ('unified_diagnostics_usage_token',[sys.executable,'HMS_Codex_UnifiedDiagnosticsUsageTokenValidator.py','--root',str(root),'--output',str(temp/'unified-usage-v2561.json')]),
          ('diagnostics_bundle_privacy_v2561',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2561.py','--root',str(root),'--output',str(temp/'diag-privacy-v2561.json')]),
          ('recovery_transaction_replay',[sys.executable,'HMS_Codex_RecoveryTransactionReplayValidator.py','--root',str(root),'--output',str(temp/'replay-v2562.json')]),
          ('unified_diagnostics_recovery_replay',[sys.executable,'HMS_Codex_UnifiedDiagnosticsRecoveryReplayValidator.py','--root',str(root),'--output',str(temp/'unified-replay-v2562.json')]),
          ('diagnostics_bundle_privacy_v2562',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2562.py','--root',str(root),'--output',str(temp/'diag-privacy-v2562.json')]),
          ('startup_recovery_reconciler',[sys.executable,'HMS_Codex_StartupRecoveryReconcilerValidator.py','--root',str(root),'--output',str(temp/'startup-recovery-v2563.json')]),
          ('target_crash_harness',[sys.executable,'HMS_Codex_TargetCrashHarnessValidator.py','--root',str(root),'--output',str(temp/'target-crash-v2563.json')]),
          ('unified_diagnostics_startup_recovery',[sys.executable,'HMS_Codex_UnifiedDiagnosticsStartupRecoveryValidator.py','--root',str(root),'--output',str(temp/'unified-startup-v2563.json')]),
          ('diagnostics_bundle_privacy_v2563',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2563.py','--root',str(root),'--output',str(temp/'diag-privacy-v2563.json')]),
          ('windows_recovery_observer_bridge',[sys.executable,'HMS_Codex_WindowsRecoveryObserverBridgeValidator.py','--root',str(root),'--output',str(temp/'observer-v2564.json')]),
          ('real_effect_crash_cert',[sys.executable,'HMS_Codex_RealEffectCrashCertificationValidator.py','--root',str(root),'--output',str(temp/'real-effect-v2564.json')]),
          ('target_recovery_evidence_bundle',[sys.executable,'HMS_Codex_TargetRecoveryEvidenceBundleValidator.py','--root',str(root),'--output',str(temp/'evidence-v2564.json')]),
          ('unified_diagnostics_windows_recovery',[sys.executable,'HMS_Codex_UnifiedDiagnosticsWindowsRecoveryValidator.py','--root',str(root),'--output',str(temp/'unified-windows-v2564.json')]),
          ('diagnostics_bundle_privacy_v2564',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2564.py','--root',str(root),'--output',str(temp/'diag-privacy-v2564.json')]),
          ('windows_target_adapter_pack_v2565',[sys.executable,'HMS_Codex_WindowsTargetAdapterPackValidator.py','--root',str(root),'--output',str(temp/'adapter-v2565.json')]),
          ('attested_evidence_promotion_gate_v2565',[sys.executable,'HMS_Codex_AttestedEvidencePromotionGateValidator.py','--root',str(root),'--output',str(temp/'promotion-v2565.json')]),
          ('recovery_operator_timeline_v2565',[sys.executable,'HMS_Codex_RecoveryOperatorTimelineValidator.py','--root',str(root),'--output',str(temp/'timeline-v2565.json')]),
          ('unified_diagnostics_attested_recovery_v2565',[sys.executable,'HMS_Codex_UnifiedDiagnosticsAttestedRecoveryValidator.py','--root',str(root),'--output',str(temp/'unified-attested-v2565.json')]),
          ('diagnostics_bundle_privacy_v2565',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2565.py','--root',str(root),'--output',str(temp/'diag-privacy-v2565.json')]),
          ('windows_attestation_signer_v2566',[sys.executable,'HMS_Codex_WindowsAttestationSignerValidator.py','--root',str(root),'--output',str(temp/'signer-v2566.json')]),
          ('target_certification_runbook_v2566',[sys.executable,'HMS_Codex_TargetCertificationRunbookValidator.py','--root',str(root),'--output',str(temp/'runbook-v2566.json')]),
          ('attestation_exchange_v2566',[sys.executable,'HMS_Codex_AttestationExchangeValidator.py','--root',str(root),'--output',str(temp/'exchange-v2566.json')]),
          ('attested_promotion_crypto_v2566',[sys.executable,'HMS_Codex_AttestedEvidencePromotionGateValidator.py','--root',str(root),'--output',str(temp/'promotion-v2566.json')]),
          ('unified_diagnostics_signed_cert_v2566',[sys.executable,'HMS_Codex_UnifiedDiagnosticsSignedCertificationValidator.py','--root',str(root),'--output',str(temp/'unified-signed-v2566.json')]),
          ('diagnostics_bundle_privacy_v2566',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2566.py','--root',str(root),'--output',str(temp/'diag-privacy-v2566.json')]),
          ('attestation_trust_store_v2567',[sys.executable,'HMS_Codex_AttestationTrustStoreValidator.py','--root',str(root),'--output',str(temp/'trust-store-v2567.json')]),
          ('offline_attestation_verifier_v2567',[sys.executable,'HMS_Codex_OfflineAttestationVerifierValidator.py','--root',str(root),'--output',str(temp/'offline-verifier-v2567.json')]),
          ('target_certification_campaign_v2567',[sys.executable,'HMS_Codex_TargetCertificationCampaignValidator.py','--root',str(root),'--output',str(temp/'campaign-v2567.json')]),
          ('unified_diagnostics_trust_campaign_v2567',[sys.executable,'HMS_Codex_UnifiedDiagnosticsTrustCampaignValidator.py','--root',str(root),'--output',str(temp/'unified-trust-campaign-v2567.json')]),
          ('diagnostics_bundle_privacy_v2567',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2567.py','--root',str(root),'--output',str(temp/'diag-privacy-v2567.json')]),
          ('target_campaign_executor_v2568',[sys.executable,'HMS_Codex_TargetCampaignExecutorValidator.py','--root',str(root),'--output',str(temp/'executor-v2568.json')]),
          ('attested_promotion_review_console_v2568',[sys.executable,'HMS_Codex_AttestedPromotionReviewConsoleValidator.py','--root',str(root),'--output',str(temp/'review-v2568.json')]),
          ('unified_diagnostics_campaign_review_v2568',[sys.executable,'HMS_Codex_UnifiedDiagnosticsCampaignReviewValidator.py','--root',str(root),'--output',str(temp/'unified-campaign-review-v2568.json')]),
          ('diagnostics_bundle_privacy_v2568',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2568.py','--root',str(root),'--output',str(temp/'diag-privacy-v2568.json')]),
          ('campaign_review_gui_v2568',[sys.executable,'HMS_Codex_CampaignReviewGUIValidator.py','--root',str(root),'--output',str(temp/'campaign-review-gui-v2568.json')]),
          ('target_certification_evidence_ingest_v2569',[sys.executable,'HMS_Codex_TargetCertificationEvidenceIngestValidator.py','--root',str(root),'--output',str(temp/'evidence-ingest-v2569.json')]),
          ('promotion_decision_ledger_v2569',[sys.executable,'HMS_Codex_PromotionDecisionLedgerValidator.py','--root',str(root),'--output',str(temp/'promotion-ledger-v2569.json')]),
          ('unified_diagnostics_evidence_ledger_v2569',[sys.executable,'HMS_Codex_UnifiedDiagnosticsEvidenceLedgerValidator.py','--root',str(root),'--output',str(temp/'unified-evidence-ledger-v2569.json')]),
          ('diagnostics_bundle_privacy_v2569',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2569.py','--root',str(root),'--output',str(temp/'diag-privacy-v2569.json')]),
          ('evidence_inbox_gui_v2569',[sys.executable,'HMS_Codex_EvidenceInboxGUIValidator.py','--root',str(root),'--output',str(temp/'evidence-inbox-gui-v2569.json')]),
          ('cockpit_1327_parity_reset_v2570',[sys.executable,'HMS_Codex_Cockpit1327ParityResetValidator.py','--root',str(root),'--output',str(temp/'cockpit-1327-parity-v2570.json')]),
          ('cockpit_1327_source_integration_v2570',[sys.executable,'HMS_Codex_Cockpit1327SourceIntegrationValidator.py','--root',str(root),'--output',str(temp/'cockpit-1327-source-v2570.json')]),
          ('cockpit_1327_gui_safety_v2570',[sys.executable,'HMS_Codex_Cockpit1327GUIValidator.py','--root',str(root),'--output',str(temp/'cockpit-1327-gui-v2570.json')]),
          ('cockpit_1327_windows_runtime_cert_v2571',[sys.executable,'HMS_Codex_Cockpit1327WindowsRuntimeCertificationValidator.py','--root',str(root),'--output',str(temp/'cockpit-1327-runtime-v2571.json')]),
          ('production_evidence_promotion_auditor_v2571',[sys.executable,'HMS_Codex_ProductionEvidencePromotionAuditorValidator.py','--root',str(root),'--output',str(temp/'promotion-auditor-v2571.json')]),
          ('unified_diagnostics_parity_runtime_v2571',[sys.executable,'HMS_Codex_UnifiedDiagnosticsParityRuntimeValidator.py','--root',str(root),'--output',str(temp/'unified-parity-runtime-v2571.json')]),
          ('cockpit_1327_runtime_gui_v2571',[sys.executable,'HMS_Codex_Cockpit1327RuntimeGUIValidator.py','--root',str(root),'--output',str(temp/'cockpit-1327-runtime-gui-v2571.json')]),
          ('windows_target_evidence_capture_kit_v2572',[sys.executable,'HMS_Codex_WindowsTargetEvidenceCaptureKitValidator.py','--root',str(root),'--output',str(temp/'capture-kit-v2572.json')]),
          ('cockpit_baseline_watch_gate_v2572',[sys.executable,'HMS_Codex_CockpitBaselineWatchGateValidator.py','--root',str(root),'--output',str(temp/'baseline-watch-v2572.json')]),
          ('unified_diagnostics_target_capture_v2572',[sys.executable,'HMS_Codex_UnifiedDiagnosticsTargetCaptureValidator.py','--root',str(root),'--output',str(temp/'unified-capture-v2572.json')]),
          ('diagnostics_bundle_privacy_v2572',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2572.py','--root',str(root),'--output',str(temp/'privacy-v2572.json')]),
          ('target_evidence_capture_gui_v2572',[sys.executable,'HMS_Codex_TargetEvidenceCaptureGUIValidator.py','--root',str(root),'--output',str(temp/'gui-capture-v2572.json')]),
          ('windows_target_evidence_import_review_v2573',[sys.executable,'HMS_Codex_WindowsTargetEvidenceImportReviewValidator.py','--root',str(root),'--output',str(temp/'import-review-v2573.json')]),
          ('baseline_delta_watch_automation_v2573',[sys.executable,'HMS_Codex_BaselineDeltaWatchAutomationValidator.py','--root',str(root),'--output',str(temp/'baseline-delta-v2573.json')]),
          ('unified_diagnostics_import_review_v2573',[sys.executable,'HMS_Codex_UnifiedDiagnosticsImportReviewValidator.py','--root',str(root),'--output',str(temp/'unified-import-v2573.json')]),
          ('diagnostics_bundle_privacy_v2573',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2573.py','--root',str(root),'--output',str(temp/'privacy-v2573.json')]),
          ('import_review_gui_v2573',[sys.executable,'HMS_Codex_ImportReviewGUIValidator.py','--root',str(root),'--output',str(temp/'gui-import-v2573.json')]),
          ('external_windows_review_packet_v2574',[sys.executable,'HMS_Codex_ExternalWindowsEvidenceReviewPacketValidator.py','--root',str(root),'--output',str(temp/'review-packet-v2574.json')]),
          ('baseline_drift_reconciliation_v2574',[sys.executable,'HMS_Codex_BaselineDriftReconciliationValidator.py','--root',str(root),'--output',str(temp/'baseline-reconcile-v2574.json')]),
          ('unified_diagnostics_review_packet_v2574',[sys.executable,'HMS_Codex_UnifiedDiagnosticsReviewPacketValidator.py','--root',str(root),'--output',str(temp/'unified-review-v2574.json')]),
          ('diagnostics_bundle_privacy_v2574',[sys.executable,'HMS_DiagnosticsBundlePrivacyValidatorV2574.py','--root',str(root),'--output',str(temp/'privacy-v2574.json')]),
          ('external_review_packet_gui_v2574',[sys.executable,'HMS_Codex_ExternalReviewPacketGUIValidator.py','--root',str(root),'--output',str(temp/'gui-review-v2574.json')]),
          ('runtime_kit',[sys.executable,'HMS_Runtime_KitValidator.py','--root',str(root)]),
          ('smart_model_router',[sys.executable,'HMS_Codex_SmartModelRouterValidator.py']),
          ('api_compatibility',[sys.executable,'HMS_Codex_ApiCompatibility.py','--root',str(root),'--temp',str(temp/'api-compat')]),
          ('api_superset',[sys.executable,'HMS_Codex_ApiSupersetValidator.py','--root',str(root),'--temp',str(temp/'api-superset')]),
          ('protocol',[sys.executable,'HMS_Codex_ProtocolValidator.py','--root',str(root),'--temp',str(temp/'protocol')]),
          ('self_healing',[sys.executable,'HMS_Codex_SelfHealing.py','--mode','synthetic']),
          ('security_hardening',[sys.executable,'HMS_Codex_SecurityHardening.py','--mode','synthetic']),
          ('project_orchestrator',[sys.executable,'HMS_Codex_ProjectOrchestratorValidator.py']),
          ('powershell_static_lint',[sys.executable,'HMS_PowerShell_StaticLint.py','--file',str(root/'HMS_AI_ROUTER_v25.23.1.ps1'),'--version',VERSION]),
          ('powershell_coherence',[sys.executable,'HMS_PowerShell_CoherenceAudit.py','--file',str(root/'HMS_AI_ROUTER_v25.23.1.ps1'),'--version',VERSION]),
        ]
        def run_one(item):
            name,cmd=item
            out_path=temp/(name+'.stdout.json')
            err_path=temp/(name+'.stderr.txt')
            try:
                with out_path.open('w',encoding='utf-8') as out_f, err_path.open('w',encoding='utf-8') as err_f:
                    popen_kwargs={}
                    if os.name!='nt':popen_kwargs['start_new_session']=True
                    elif hasattr(subprocess,'CREATE_NEW_PROCESS_GROUP'):popen_kwargs['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
                    proc=subprocess.Popen(cmd,cwd=str(root),text=True,stdout=out_f,stderr=err_f,**popen_kwargs)
                    try:
                        code=proc.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        if os.name!='nt':
                            try:os.killpg(proc.pid,signal.SIGKILL)
                            except Exception:pass
                        else:
                            try:proc.kill()
                            except Exception:pass
                        try:proc.wait(timeout=5)
                        except Exception:pass
                        return {'suite':name,'ok':False,'exit_code':124,'summary':{},'stderr':'SUITE_TIMEOUT_120S'}
                    finally:
                        # Some network/simulation suites leave short-lived descendants. Kill only the
                        # suite's isolated POSIX process group after the suite parent exits so the
                        # outer supervisor cannot be held open by inherited file descriptors.
                        if os.name!='nt':
                            try:os.killpg(proc.pid,signal.SIGTERM)
                            except Exception:pass
                            time.sleep(0.01)
                            try:os.killpg(proc.pid,signal.SIGKILL)
                            except Exception:pass
                stdout=out_path.read_text('utf-8',errors='replace') if out_path.exists() else ''
                stderr=err_path.read_text('utf-8',errors='replace') if err_path.exists() else ''
                parsed=None
                try: parsed=json.loads(stdout)
                except Exception: pass
                summary=(parsed or {}).get('summary') or ((parsed or {}).get('data') or {}).get('summary') or {}
                return {'suite':name,'ok':code==0,'exit_code':code,'summary':summary,
                        'stderr':stderr[-400:] if code else ''}
            except Exception as exc:
                return {'suite':name,'ok':False,'exit_code':125,'summary':{},'stderr':f'SUITE_EXCEPTION:{type(exc).__name__}:{exc}'}


        # v25.62 final freeze is intentionally sequential. Several legacy network validators
        # create short-lived HTTP/process children and some evidence suites share ports/files.
        # Sequential execution removes inherited-handle/port races and host-load timing noise;
        # per-suite 120s timeout and every original assertion remain unchanged.
        rows=[]
        saved={}
        if checkpoint and checkpoint.exists():
            try:
                old=json.loads(checkpoint.read_text('utf-8'))
                saved={str(x.get('suite')):x for x in (old.get('suites') or []) if x.get('ok') is True}
            except Exception:
                saved={}
        def publish_checkpoint():
            if not checkpoint:return
            payload={'version':VERSION,'generated_utc':datetime.now(timezone.utc).isoformat(),'complete':len(rows)==len(suites),'suites':rows}
            checkpoint.parent.mkdir(parents=True,exist_ok=True)
            tmp=checkpoint.with_suffix(checkpoint.suffix+'.tmp')
            with tmp.open('w',encoding='utf-8',newline='\n') as f:
                json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n');f.flush()
                try:
                    import os;os.fsync(f.fileno())
                except Exception:pass
            tmp.replace(checkpoint)
        for item in suites:
            name=item[0]
            if name in saved:
                rows.append(saved[name])
            else:
                rows.append(run_one(item))
            publish_checkpoint()
        numeric_pass=0;numeric_total=0
        for row in rows:
            summary=row.get('summary') or {}
            if isinstance(summary.get('pass'),int) and isinstance(summary.get('total'),int):
                numeric_pass+=summary['pass'];numeric_total+=summary['total']
        passed=sum(1 for x in rows if x['ok'])
        return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'V25_28_TO_V25_74_REGRESSION_FREEZE','generated_utc':datetime.now(timezone.utc).isoformat(),
                'verdict':'PASS' if passed==len(rows) else 'FAIL','summary':{'suite_pass':passed,'suite_fail':len(rows)-passed,'suite_total':len(rows),
                'numeric_assertions_pass':numeric_pass,'numeric_assertions_total':numeric_total},'suites':rows,
                'windows_powershell_5_1':'TARGET_MACHINE_GATE_READY','real_codex_cli_desktop':'TARGET_MACHINE_GATE_READY','real_multi_pc_smb_nas':'DEFERRED_BY_OPERATOR','soak':'HARNESS_READY_6H_24H_NOT_EXECUTED','performance_scale':'SYNTHETIC_VALIDATED','real_codex_certification':'HARNESS_SYNTHETIC_VALIDATED_TARGET_MACHINE_LIVE_REQUIRED','live_quota_intelligence':'SYNTHETIC_VALIDATED_LIVE_REFRESH_TARGET_MACHINE_REQUIRED','seamless_rotation_torture':'SYNTHETIC_1000_CYCLE_VALIDATED_TARGET_MACHINE_TORTURE_STILL_REQUIRED','ux_cockpit_parity_plus':'CONTROL_PLANE_UX_VALIDATED_READ_ONLY_WEB_NO_PRODUCTION_SCORE','target_machine_certification':'SYNTHETIC_AGGREGATOR_VALIDATED_REAL_WINDOWS_CODEX_LAN_SOAK_REQUIRED','production_simulation_lab':'DIGITAL_TWIN_FAULT_INJECTION_VALIDATED_NO_PRODUCTION_CLAIM','autonomous_router_digital_twin':'LARGE_POOL_STATE_MODEL_CHECK_VALIDATED_NO_PRODUCTION_CLAIM','protocol_chaos_fuzzer':'SSE_WS_JSON_CHUNKED_RETRY_FUZZ_VALIDATED_NO_PRODUCTION_CLAIM','recovery_planner':'CAUSE_AWARE_BOUNDED_SELF_HEALING_MODEL_CHECK_VALIDATED_NO_PRODUCTION_CLAIM','compound_fault_recovery':'RECOVERY_DAG_GLOBAL_BUDGET_CONVERGENCE_MODEL_CHECK_VALIDATED_NO_PRODUCTION_CLAIM','official_auth_compatibility':'FILE_KEYRING_AUTO_SWITCH_SEMANTICS_SYNTHETIC_VALIDATED_REAL_CODEX_LIVE_DEFERRED','recovery_transaction_journal':'HASH_CHAIN_CRASH_RESUME_SYNTHETIC_VALIDATED_NO_PRODUCTION_CLAIM','usage_token_center':'RESET_LIFECYCLE_SCENARIO_HISTORY_SYNTHETIC_VALIDATED_NO_PRODUCTION_CLAIM','usage_token_diagnostics':'METADATA_ONLY_PRIVACY_VALIDATED_NO_PRODUCTION_CLAIM','recovery_transaction_replay':'CROSS_SUBSYSTEM_AT_MOST_ONCE_OWNERSHIP_PROOF_SYNTHETIC_VALIDATED_NO_PRODUCTION_CLAIM','startup_recovery_reconciler':'STARTUP_FAIL_CLOSED_OBSERVER_GATE_SYNTHETIC_VALIDATED_TARGET_MACHINE_LIVE_REQUIRED','target_crash_harness':'OS_PROCESS_KILL_COLD_START_LAB_VALIDATED_WINDOWS_REAL_CODEX_EFFECTS_REQUIRED' }

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');ap.add_argument('--checkpoint');a=ap.parse_args();out=run(Path(a.root),Path(a.checkpoint) if a.checkpoint else None);txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n',encoding='utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
