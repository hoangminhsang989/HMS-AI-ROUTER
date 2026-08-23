#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone

def run(root:Path):
    tests=[]
    def add(name,ok,detail):tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
    def text(name,enc="utf-8"):
        return (root/name).read_text(encoding=enc,errors="replace")
    orch=text("HMS_Runtime_Orchestrator.ps1","utf-8-sig")
    apply=text("HMS_Apply_Runtime_Profile.ps1","utf-8-sig")
    wiz=text("HMS_FirstRun_Wizard.ps1","utf-8-sig")
    web=text("HMS_Codex_UnifiedUX.py","utf-8")
    runtime_validator=text("HMS_Codex_RuntimeValidator.py","utf-8")
    start=text("HMS_Start_RuntimeReady.ps1","utf-8-sig")
    main=text("HMS_AI_ROUTER_v25.23.1.ps1","utf-8-sig")
    gate=text("HMS_Windows_Runtime_Gate.ps1","utf-8-sig")
    bat=text("01_BAT_DAU_CHAY_HMS.bat","ascii")
    gui_launcher=text("HMS_GUI_Launcher.vbs","ascii")
    ps_launcher=text("HMS_Launcher.ps1","utf-8-sig")
    native_gui=text("HMS_GUI.pyw","utf-8")
    predictive=text("HMS_Codex_PredictiveQuota.py","utf-8")
    quota_center=text("HMS_Codex_QuotaCenter.py","utf-8")
    account_analytics=text("HMS_Codex_AccountAnalytics.py","utf-8")
    identity_isolation=text("HMS_Codex_IdentityIsolation.py","utf-8")
    model_manager=text("HMS_Codex_ModelReasoningManager.py","utf-8")
    smart_gateway=text("HMS_Codex_SmartGateway.py","utf-8")
    api_compat=text("HMS_Codex_ApiCompatibility.py","utf-8")
    self_heal=text("HMS_Codex_SelfHealing.py","utf-8")
    security_hardening=text("HMS_Codex_SecurityHardening.py","utf-8")
    diagnostics_bundle=text("HMS_DiagnosticsBundle.py","utf-8")
    unified_diagnostics=text("HMS_Codex_UnifiedDiagnostics.py","utf-8")
    project_orchestrator=text("HMS_Codex_ProjectOrchestrator.py","utf-8")
    project_orchestrator_validator=text("HMS_Codex_ProjectOrchestratorValidator.py","utf-8")
    multi_team=text("HMS_Codex_MultiTeam.py","utf-8")
    smart_model=text("HMS_Codex_SmartModelRouter.py","utf-8")
    lan_pool=text("HMS_Codex_LanPool.py","utf-8")
    lan_pool_validator=text("HMS_Codex_LanPoolValidator.py","utf-8")
    lan_failure_validator=text("HMS_Codex_LanFailureMatrixValidator.py","utf-8")
    compatibility_freeze=text("HMS_Codex_CompatibilityFreezeValidator.py","utf-8")
    client_compat_validator=text("HMS_Codex_ClientCompatibilityValidator.py","utf-8")
    public_contract=text("CODEX_PUBLIC_CONTRACT_V25_46.json","utf-8")
    client_matrix=text("CODEX_CLIENT_COMPATIBILITY_MATRIX_V25_46.json","utf-8")
    regression_freeze=text("HMS_Codex_RegressionFreezeValidator.py","utf-8")
    reliability_soak=text("HMS_Codex_ReliabilitySoak.py","utf-8")
    reliability_soak_validator=text("HMS_Codex_ReliabilitySoakValidator.py","utf-8")
    performance_scale=text("HMS_Codex_PerformanceScale.py","utf-8")
    performance_scale_validator=text("HMS_Codex_PerformanceScaleValidator.py","utf-8")
    real_codex_cert=text("HMS_Codex_RealCertification.py","utf-8")
    real_codex_cert_validator=text("HMS_Codex_RealCertificationValidator.py","utf-8")
    real_codex_bridge=text("HMS_Codex_RealCertificationBridge.ps1","utf-8-sig")
    live_quota=text("HMS_Codex_LiveQuotaIntelligence.py","utf-8")
    live_quota_validator=text("HMS_Codex_LiveQuotaIntelligenceValidator.py","utf-8")
    adaptive_router=text("HMS_Codex_AdaptiveRouterPolicy.py","utf-8")
    closed_loop=text("HMS_Codex_ClosedLoopRouter.py","utf-8")
    rotation_torture=text("HMS_Codex_SeamlessRotationTorture.py","utf-8")
    rotation_torture_validator=text("HMS_Codex_SeamlessRotationTortureValidator.py","utf-8")
    ux_parity_validator=text("HMS_Codex_UxParityValidator.py","utf-8")
    target_machine_cert=text("HMS_Codex_TargetMachineCertification.py","utf-8")
    target_machine_validator=text("HMS_Codex_TargetMachineCertificationValidator.py","utf-8")
    production_sim_lab=text("HMS_Codex_ProductionSimulationLab.py","utf-8")
    production_sim_validator=text("HMS_Codex_ProductionSimulationLabValidator.py","utf-8")
    autonomous_router_twin=text("HMS_Codex_AutonomousRouterDigitalTwin.py","utf-8")
    autonomous_router_validator=text("HMS_Codex_AutonomousRouterDigitalTwinValidator.py","utf-8")
    protocol_chaos=text("HMS_Codex_ProtocolChaosFuzzer.py","utf-8")
    protocol_chaos_validator=text("HMS_Codex_ProtocolChaosFuzzerValidator.py","utf-8")
    recovery_planner=text("HMS_Codex_RecoveryPlanner.py","utf-8")
    recovery_planner_validator=text("HMS_Codex_RecoveryPlannerValidator.py","utf-8")
    compound_fault_recovery=text("HMS_Codex_CompoundFaultRecovery.py","utf-8")
    compound_fault_validator=text("HMS_Codex_CompoundFaultRecoveryValidator.py","utf-8")
    official_auth_compat=text("HMS_Codex_OfficialAuthCompatibility.py","utf-8")
    official_auth_validator=text("HMS_Codex_OfficialAuthCompatibilityValidator.py","utf-8")
    recovery_journal=text("HMS_Codex_RecoveryTransactionJournal.py","utf-8")
    recovery_journal_validator=text("HMS_Codex_RecoveryTransactionJournalValidator.py","utf-8")
    usage_token_center=text("HMS_Codex_UsageTokenCenter.py","utf-8")
    usage_token_validator=text("HMS_Codex_UsageTokenCenterValidator.py","utf-8")
    unified_usage_validator=text("HMS_Codex_UnifiedDiagnosticsUsageTokenValidator.py","utf-8")
    diagnostics_v2561_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2561.py","utf-8")
    recovery_replay=text("HMS_Codex_RecoveryTransactionReplay.py","utf-8")
    recovery_replay_validator=text("HMS_Codex_RecoveryTransactionReplayValidator.py","utf-8")
    startup_recovery=text("HMS_Codex_StartupRecoveryReconciler.py","utf-8")
    startup_recovery_validator=text("HMS_Codex_StartupRecoveryReconcilerValidator.py","utf-8")
    target_crash_harness=text("HMS_Codex_TargetCrashHarness.py","utf-8")
    target_crash_validator=text("HMS_Codex_TargetCrashHarnessValidator.py","utf-8")
    unified_startup_validator=text("HMS_Codex_UnifiedDiagnosticsStartupRecoveryValidator.py","utf-8")
    diagnostics_v2563_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2563.py","utf-8")
    windows_observer=text("HMS_Codex_WindowsRecoveryObserverBridge.py","utf-8")
    windows_observer_validator=text("HMS_Codex_WindowsRecoveryObserverBridgeValidator.py","utf-8")
    real_effect_cert=text("HMS_Codex_RealEffectCrashCertification.py","utf-8")
    real_effect_validator=text("HMS_Codex_RealEffectCrashCertificationValidator.py","utf-8")
    target_evidence_bundle=text("HMS_Codex_TargetRecoveryEvidenceBundle.py","utf-8")
    target_evidence_validator=text("HMS_Codex_TargetRecoveryEvidenceBundleValidator.py","utf-8")
    unified_windows_validator=text("HMS_Codex_UnifiedDiagnosticsWindowsRecoveryValidator.py","utf-8")
    diagnostics_v2564_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2564.py","utf-8")
    windows_target_adapter=text("HMS_Codex_WindowsTargetAdapterPack.py","utf-8")
    windows_target_adapter_validator=text("HMS_Codex_WindowsTargetAdapterPackValidator.py","utf-8")
    attested_promotion=text("HMS_Codex_AttestedEvidencePromotionGate.py","utf-8")
    attested_promotion_validator=text("HMS_Codex_AttestedEvidencePromotionGateValidator.py","utf-8")
    recovery_timeline=text("HMS_Codex_RecoveryOperatorTimeline.py","utf-8")
    recovery_timeline_validator=text("HMS_Codex_RecoveryOperatorTimelineValidator.py","utf-8")
    unified_attested_validator=text("HMS_Codex_UnifiedDiagnosticsAttestedRecoveryValidator.py","utf-8")
    diagnostics_v2565_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2565.py","utf-8")
    windows_attestation_signer=text("HMS_Codex_WindowsAttestationSigner.py","utf-8")
    windows_attestation_signer_validator=text("HMS_Codex_WindowsAttestationSignerValidator.py","utf-8")
    target_cert_runbook=text("HMS_Codex_TargetCertificationRunbook.py","utf-8")
    target_cert_runbook_validator=text("HMS_Codex_TargetCertificationRunbookValidator.py","utf-8")
    attestation_exchange=text("HMS_Codex_AttestationExchange.py","utf-8")
    attestation_exchange_validator=text("HMS_Codex_AttestationExchangeValidator.py","utf-8")
    unified_signed_validator=text("HMS_Codex_UnifiedDiagnosticsSignedCertificationValidator.py","utf-8")
    diagnostics_v2566_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2566.py","utf-8")
    attestation_trust_store=text("HMS_Codex_AttestationTrustStore.py","utf-8")
    attestation_trust_store_validator=text("HMS_Codex_AttestationTrustStoreValidator.py","utf-8")
    offline_attestation_verifier=text("HMS_Codex_OfflineAttestationVerifier.py","utf-8")
    offline_attestation_verifier_validator=text("HMS_Codex_OfflineAttestationVerifierValidator.py","utf-8")
    target_cert_campaign=text("HMS_Codex_TargetCertificationCampaign.py","utf-8")
    target_cert_campaign_validator=text("HMS_Codex_TargetCertificationCampaignValidator.py","utf-8")
    unified_trust_campaign_validator=text("HMS_Codex_UnifiedDiagnosticsTrustCampaignValidator.py","utf-8")
    diagnostics_v2567_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2567.py","utf-8")
    target_campaign_executor=text("HMS_Codex_TargetCampaignExecutor.py","utf-8")
    target_campaign_executor_validator=text("HMS_Codex_TargetCampaignExecutorValidator.py","utf-8")
    promotion_review_console=text("HMS_Codex_AttestedPromotionReviewConsole.py","utf-8")
    promotion_review_validator=text("HMS_Codex_AttestedPromotionReviewConsoleValidator.py","utf-8")
    unified_campaign_review_validator=text("HMS_Codex_UnifiedDiagnosticsCampaignReviewValidator.py","utf-8")
    diagnostics_v2568_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2568.py","utf-8")
    target_evidence_ingest=text("HMS_Codex_TargetCertificationEvidenceIngest.py","utf-8")
    target_evidence_ingest_validator=text("HMS_Codex_TargetCertificationEvidenceIngestValidator.py","utf-8")
    promotion_decision_ledger=text("HMS_Codex_PromotionDecisionLedger.py","utf-8")
    promotion_decision_ledger_validator=text("HMS_Codex_PromotionDecisionLedgerValidator.py","utf-8")
    unified_evidence_ledger_validator=text("HMS_Codex_UnifiedDiagnosticsEvidenceLedgerValidator.py","utf-8")
    diagnostics_v2569_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2569.py","utf-8")
    evidence_inbox_gui_validator=text("HMS_Codex_EvidenceInboxGUIValidator.py","utf-8")
    cockpit1327_parity=text("HMS_Codex_Cockpit1327ParityReset.py","utf-8")
    cockpit1327_parity_validator=text("HMS_Codex_Cockpit1327ParityResetValidator.py","utf-8")
    cockpit1327_source_validator=text("HMS_Codex_Cockpit1327SourceIntegrationValidator.py","utf-8")
    cockpit1327_runtime_cert=text("HMS_Codex_Cockpit1327WindowsRuntimeCertification.py","utf-8")
    cockpit1327_runtime_cert_validator=text("HMS_Codex_Cockpit1327WindowsRuntimeCertificationValidator.py","utf-8")
    production_promotion_auditor=text("HMS_Codex_ProductionEvidencePromotionAuditor.py","utf-8")
    production_promotion_auditor_validator=text("HMS_Codex_ProductionEvidencePromotionAuditorValidator.py","utf-8")
    unified_parity_runtime_validator=text("HMS_Codex_UnifiedDiagnosticsParityRuntimeValidator.py","utf-8")
    cockpit1327_runtime_gui_validator=text("HMS_Codex_Cockpit1327RuntimeGUIValidator.py","utf-8")
    target_capture_kit=text("HMS_Codex_WindowsTargetEvidenceCaptureKit.py","utf-8")
    target_capture_kit_validator=text("HMS_Codex_WindowsTargetEvidenceCaptureKitValidator.py","utf-8")
    cockpit_baseline_watch=text("HMS_Codex_CockpitBaselineWatchGate.py","utf-8")
    cockpit_baseline_watch_validator=text("HMS_Codex_CockpitBaselineWatchGateValidator.py","utf-8")
    unified_target_capture_validator=text("HMS_Codex_UnifiedDiagnosticsTargetCaptureValidator.py","utf-8")
    diagnostics_v2572_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2572.py","utf-8")
    target_capture_gui_validator=text("HMS_Codex_TargetEvidenceCaptureGUIValidator.py","utf-8")
    import_review=text("HMS_Codex_WindowsTargetEvidenceImportReview.py","utf-8")
    import_review_validator=text("HMS_Codex_WindowsTargetEvidenceImportReviewValidator.py","utf-8")
    baseline_delta_watch=text("HMS_Codex_BaselineDeltaWatchAutomation.py","utf-8")
    baseline_delta_watch_validator=text("HMS_Codex_BaselineDeltaWatchAutomationValidator.py","utf-8")
    unified_import_review_validator=text("HMS_Codex_UnifiedDiagnosticsImportReviewValidator.py","utf-8")
    diagnostics_v2573_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2573.py","utf-8")
    import_review_gui_validator=text("HMS_Codex_ImportReviewGUIValidator.py","utf-8")
    external_review_packet=text("HMS_Codex_ExternalWindowsEvidenceReviewPacket.py","utf-8")
    external_review_packet_validator=text("HMS_Codex_ExternalWindowsEvidenceReviewPacketValidator.py","utf-8")
    baseline_drift_reconciliation=text("HMS_Codex_BaselineDriftReconciliation.py","utf-8")
    baseline_drift_reconciliation_validator=text("HMS_Codex_BaselineDriftReconciliationValidator.py","utf-8")
    unified_review_packet_validator=text("HMS_Codex_UnifiedDiagnosticsReviewPacketValidator.py","utf-8")
    diagnostics_v2574_validator=text("HMS_DiagnosticsBundlePrivacyValidatorV2574.py","utf-8")
    external_review_packet_gui_validator=text("HMS_Codex_ExternalReviewPacketGUIValidator.py","utf-8")
    usage_ledger=text("HMS_Codex_UsageLedger.py","utf-8")
    official_auth_export=text("HMS_Codex_OfficialAuthExport.py","utf-8")
    manifest=json.loads(text("RELEASE_MANIFEST_V25_23_1.json"))

    add("entrypoint.native_gui_host",
        'HMS_GUI.pyw' in gui_launcher
        and 'powershell.exe' not in gui_launcher.lower()
        and 'pyw.exe -3' in gui_launcher
        and 'pythonw.exe' in gui_launcher
        and 'shell.Run' in gui_launcher,
        "normal entrypoint launches HMS_GUI.pyw directly; PowerShell is not the primary UI host")
    add("orchestrator.required_stages",all(x in orch for x in ['"ALL_READY"','"UI_SMOKE"','"ROUTER_SMOKE"','"SAFE_RUNTIME"']),
        "required stages present")
    all_ready_block=orch[orch.find('"ALL_READY" {'):orch.find("\n    }\n}",orch.find('"ALL_READY" {'))]
    add("all_ready.non_mutating_router","ROUTER_SMOKE" not in all_ready_block and "SAFE_RUNTIME" not in all_ready_block,
        "ALL_READY does not call router/safe runtime stages")
    add("snapshot.private_inputs",all(x in orch for x in ['"codex-config"','"codex-env"','"cliproxy-config"','icacls.exe']),
        "snapshot covers configs and best-effort ACL")
    add("snapshot.no_oauth_copy",'Get-ChildItem -LiteralPath $authDir -File -Filter "codex-*.json"' in orch and 'codex_auth_metadata' in orch,
        "OAuth auth is inventoried as metadata")
    add("port_profile.safe_defaults",all(x in apply for x in [
        'AutoEnable -NotePropertyValue $false','SmartGatewayAutoStart -NotePropertyValue $false',
        'ProxyFleetAutoRecovery -NotePropertyValue $false','PolicyKernelMode -NotePropertyValue "OBSERVE"']),
        "first runtime profile keeps automation off")
    add("guarded_launcher.runtime_ready",'if(-not [bool]$cp.runtime_ready)' in start and 'exit 4' in start,
        "guarded launcher blocks incomplete checkpoint")
    add("wizard.sequence",all(x in wiz for x in [
        "1. KIỂM TRA ALL READY","2. ÁP DỤNG PORT AN TOÀN","3. UI SMOKE","4. ROUTER SMOKE","5. SAFE RUNTIME"]),
        "operator sequence visible")
    add("main.runtime_cert_tab",'Runtime Certification' in main and 'MỞ FIRST-RUN WIZARD' in main,
        "main Mission Control links Runtime Certification")
    add("gate.v25_23_1_authority",'HMS_AI_ROUTER_v25.23.1.ps1' in gate and 'RELEASE_MANIFEST_V25_23_1.json' in gate and 'version="25.23.1"' in gate,
        "runtime gate authority migrated to v25.23.1")
    add("manifest.v25_23_1",manifest.get("version")=="25.23.1" and len(manifest.get("files",[]))>=60,
        f"manifest files={len(manifest.get('files',[]))}")

    # PowerShell automatic $PID is read-only/constant. Manual $pid/$Pid aliases are equally reserved
    # because variable names are case-insensitive. This exact bug caused v25.0 ALL_READY to terminate
    # during coexistence before latest result publication.
    reserved=[]
    patterns=[
        ("PID",re.compile(r"\$(?:pid|Pid)\b")),
        ("HOST",re.compile(r"\$(?:host|Host|HOST)\b")),
        ("HOME",re.compile(r"\$(?:home|Home|HOME)\b")),
    ]
    for ps in root.glob("*.ps1"):
        src=ps.read_text("utf-8-sig",errors="replace")
        for ln,line in enumerate(src.splitlines(),1):
            for label,pat in patterns:
                # Intentional automatic-variable reads are uppercase and are allowed only when not assigned/declared.
                if not pat.search(line):continue
                if label=="PID" and "$PID" in line and not re.search(r"\$PID\s*=|param\([^)]*\$PID|foreach\s*\(\s*\$PID",line):
                    continue
                if label=="HOST" and "$Host" in line and not re.search(r"\$Host\s*=|param\([^)]*\$Host|foreach\s*\(\s*\$Host",line):
                    continue
                if label=="HOME" and "$HOME" in line and not re.search(r"\$HOME\s*=|param\([^)]*\$HOME|foreach\s*\(\s*\$HOME",line):
                    continue
                reserved.append(f"{label}:{ps.name}:{ln}:{line.strip()}")
    add("powershell.no_reserved_auto_alias",not reserved,
        "no manual PID/HOST/HOME automatic-variable aliases" if not reserved else " | ".join(reserved[:10]))

    add("wizard.fatal_evidence",
        "wizard-child-" in wiz and "FATAL" in wiz and "transcript" in wiz,
        "wizard captures child stdout/stderr and publishes emergency evidence")

    # PowerShell engine issue #27558: @($list) can throw "Argument types do not match"
    # when List[T] is created through New-Object. v25.2 bans that construction form.
    generic_newobject=[]
    for ps in root.glob("*.ps1"):
        src=ps.read_text("utf-8-sig",errors="replace")
        for ln,line in enumerate(src.splitlines(),1):
            if re.search(r"New-Object\s+System\.Collections\.Generic\.List\[",line,re.I):
                generic_newobject.append(f"{ps.name}:{ln}:{line.strip()}")
    add("powershell.ps51_generic_list_compat",not generic_newobject,
        "all Generic List[T] use direct .NET constructors" if not generic_newobject else " | ".join(generic_newobject[:10]))

    add("runtime_gate.toarray_publication",
        "gates=$script:Gates.ToArray()" in gate and "steps=$script:Rows.ToArray()" in orch,
        "critical runtime evidence publication avoids @() around Generic List")

    add("runtime_gate.fatal_evidence",
        'verdict="FATAL"' in gate and "fatal-v25_23_1.txt" in gate,
        "Windows Runtime Gate publishes FATAL JSON/text evidence on unhandled error")

    # A previous packaging edit stripped quotes from a Log banner:
    #   Log v25.2 HOTFIX: ... ; fatal transcript ...
    # The semicolon made PowerShell execute `fatal` as a command when Form.Shown fired.
    bare_log=[]
    for ps in root.glob("*.ps1"):
        src=ps.read_text("utf-8-sig",errors="replace")
        for ln,line in enumerate(src.splitlines(),1):
            stripped=line.strip()
            if not stripped.startswith("Log "):
                continue
            arg=stripped[4:].lstrip()
            if not arg:
                bare_log.append(f"{ps.name}:{ln}:{stripped}")
                continue
            if arg[0] not in ('"', "'", '$', '('):
                bare_log.append(f"{ps.name}:{ln}:{stripped}")
    add("powershell.no_bare_log_calls",not bare_log,
        "all Log calls use quoted/expression arguments" if not bare_log else " | ".join(bare_log[:10]))

    add("wizard.shown_guarded",
        "$form.Add_Shown({" in wiz and "Form.Shown ERROR:" in wiz and "try{" in wiz,
        "Form.Shown initialization is guarded by try/catch")

    add("inventory.current_release_authority",
        '"HMS_AI_ROUTER_v25.23.1.ps1"' in orch and '"RELEASE_MANIFEST_V25_23_1.json"' in orch
        and "RELEASE_MANIFEST_V25_1.json" not in orch,
        "Inventory checks the current v25.23.1 main script and current release manifest")

    add("inventory.operator_spacing",
        '$env:OS -eq "Windows_NT"' in orch and '$env:OS-eq"Windows_NT"' not in orch,
        "Inventory PowerShell comparison operator is tokenized safely")

    add("inventory.detailed_missing",
        "missing_required" in orch and "Thiếu prerequisite bắt buộc:" in orch,
        "Inventory publishes exact missing prerequisite names instead of a generic failure")

    # v25.4 real-machine blocker: Invoke-WindowsGate wrote to $evidenceDir even though
    # the orchestrator never initialized that variable. StrictMode correctly raised:
    # "The variable '$evidenceDir' cannot be retrieved because it has not been set."
    run_dir_pos=orch.find('$runDir=Join-Path $RunsDir $runId')
    evidence_init_pos=orch.find('$RunEvidenceDir=Join-Path $runDir "evidence"')
    invoke_pos=orch.find('function Invoke-WindowsGate')
    evidence_use_pos=orch.find('$childLog=Join-Path $RunEvidenceDir', invoke_pos)
    add("runtime.evidence_initialized_before_use",
        run_dir_pos>=0 and evidence_init_pos>run_dir_pos and invoke_pos>evidence_init_pos and evidence_use_pos>invoke_pos,
        "RunEvidenceDir is initialized and created before Invoke-WindowsGate can use it")

    add("runtime.no_orphan_evidenceDir",
        "$evidenceDir" not in orch,
        "Orchestrator contains no orphan/uninitialized $evidenceDir reference")

    stale_runtime_names=[
        "result-v25.json","fatal-v25_1.txt","RELEASE_MANIFEST_V25_1.json",
        "HMS_AI_v25.4.ps1","RELEASE_MANIFEST_V25_4.json"
    ]
    stale=[x for x in stale_runtime_names if x in orch]
    add("runtime.current_namespace_authority",not stale,
        "no stale runtime authority names" if not stale else "stale: "+", ".join(stale))

    # Real Windows PowerShell 5.1 parser evidence from v25.5 exposed a family of compact
    # syntax defects that the original static linter did not catch. Keep explicit lexical
    # regressions here so these defects cannot silently re-enter a build.
    main_src=main
    parser_risks=[]
    risk_patterns=[
        ("foreach_in_at",re.compile(r"foreach\s*\(\s*\$[A-Za-z_]\w*\s+in@\(",re.I)),
        ("foreach_in_var",re.compile(r"foreach\s*\(\s*\$[A-Za-z_]\w*\s+in\$[A-Za-z_]",re.I)),
        ("argumentlist_glued",re.compile(r"-ArgumentList\$",re.I)),
        ("btn_quote_glued",re.compile(r"\bBtn\"",re.I)),
        ("compact_compare",re.compile(r"\$[A-Za-z_][A-Za-z0-9_\.\[\]\(\)]*-(?:eq|ne|lt|le|gt|ge)(?=[^\s])",re.I)),
    ]
    for label,pat in risk_patterns:
        for m in pat.finditer(main_src):
            ln=main_src.count("\n",0,m.start())+1
            parser_risks.append(f"{label}:line={ln}:{main_src.splitlines()[ln-1].strip()}")
    # Invalid interpolation such as "$port:" or "$email:"; scoped variables like $script:
    # and $env: are valid and intentionally excluded.
    scoped={"script","env","global","local","private","using"}
    for m in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*):",main_src):
        if m.group(1).lower() in scoped:continue
        ln=main_src.count("\n",0,m.start())+1
        parser_risks.append(f"invalid_var_colon:line={ln}:{main_src.splitlines()[ln-1].strip()}")
    add("powershell.real_parser_regression_patterns",not parser_risks,
        "no known PS5.1 parser regression patterns" if not parser_risks else " | ".join(parser_risks[:12]))

    add("powershell.wakeup_parenthesis",
        'if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."}' in main_src,
        "Wake-up router guard has balanced closing parentheses")

    add("launcher_setup.scalar_count_safe",
        '$parseFailures=@($rows | Where-Object {$_.parse_errors -gt 0})' in gate
        and '$parseFailures.Count -eq 0' in gate
        and '($rows|Where-Object{$_.parse_errors -gt 0}).Count' not in gate,
        "launcher.setup wraps pipeline output before Count under StrictMode")

    add("websmoke.server_consumes_post_body",
        'self.headers.get("Content-Length","0")' in web and 'self.rfile.read' in web and 'self.send_bytes(405' in web,
        "read-only POST consumes request body before returning 405")
    add("websmoke.server_content_length",
        'self.send_header("Content-Length"' in web and 'self.send_header("Connection","close")' in web,
        "Unified UX emits explicit Content-Length and Connection: close")
    add("websmoke.httpclient_windows_safe",
        '$req.KeepAlive=$false' in gate and '$req.ProtocolVersion=[Version]"1.0"' in gate and '$req.ServicePoint.Expect100Continue=$false' in gate,
        "Windows HttpWebRequest disables keep-alive and Expect: 100-continue")
    add("websmoke.diagnostic_evidence",
        'server-stdout.log' in gate and 'server-stderr.log' in gate and 'phase="post"' in gate and 'trace=$trace.ToArray()' in gate,
        "WEB_SMOKE captures child logs and per-request HTTP trace")

    add("saferuntime.output_file_no_stdout_tail",
        'if x.output:\n  Path(x.output).write_text(s,"utf-8")\n else:\n  print(s)' in runtime_validator
        and 'print(s);return 0 if o.get("ok") else 1' not in runtime_validator,
        "RuntimeValidator does not print full Unicode JSON after publishing --output")

    add("saferuntime.deferred_first_run_state",
        'deferred_status="DEFERRED" if profile=="SAFE_RUNTIME" else "BLOCKED"' in runtime_validator
        and '"deferred":deferred' in runtime_validator,
        "SAFE_RUNTIME separates deferred first-run state from true blockers")

    add("saferuntime.process_exit_authority",
        'Start-Process -FilePath $python.Source' in gate
        and '$processExit=[int]$proc.ExitCode' in gate
        and 'safe-runtime-process.json' in gate,
        "SAFE_RUNTIME captures child ExitCode/stdout/stderr explicitly")

    add("saferuntime.pass_semantics",
        'if($v -ne "PASS" -or $fail -gt 0)' in gate
        and 'status="PASS"' in gate
        and 'deferred=$deferred' in gate,
        "SAFE_RUNTIME PASS depends on structured fail/verdict, not deferred state")

    add("liveapi.explicit_config_path",
        '-ArgumentList @("--config",$cfgArg)' in main
        and 'config=$($script:ProxyCfg)' in main,
        "CLIProxyAPI is started with an explicit --config path")

    add("liveapi.key_fingerprint_audit",
        'function Get-ProxyApiKeyAudit' in main
        and 'ExpectedFingerprint' in main
        and 'config_key_match=$($audit.Match)' in main,
        "live handoff verifies local key membership without exposing the secret")

    add("liveapi.http_error_body",
        'Status=$status;Body=$body;Error=$msg' in main
        and 'LOCAL_API_HANDSHAKE_FAIL: HTTP=' in main,
        "401/403 diagnostics include HTTP status and redacted response body")

    enable_pos=main.find("function Enable-HmsMode{")
    api_fail_pos=main.find("if(-not $api.Ok)",enable_pos)
    codex_mutate_pos=main.find("Configure-CodexApiMode",enable_pos)
    add("liveapi.transactional_handoff",
        'proxy-config-before-live-handoff-v2511.yaml' in main
        and 'Copy-Item $proxyTxn $script:ProxyCfg -Force' in main
        and enable_pos>=0 and api_fail_pos>enable_pos and codex_mutate_pos>api_fail_pos,
        "failed live handoff restores CLIProxy config and Codex mutation occurs only after local API success")

    add("json.empty_array_safe",
        'ConvertTo-Json -InputObject $o -Depth 16' in main
        and '$o | ConvertTo-Json -Depth 16' not in main,
        "Save-Json preserves empty arrays as valid [] JSON")

    add("listener.get_nettcp_repaired",
        'Get-NetTCPConnection -State Listen' in main
        and 'Get -Ne tTCPConnection' not in main,
        "valid Get-NetTCPConnection cmdlet restored after parser normalization")

    add("ui.footer_current_release",
        'HMS v25.43 MULTI-CODEX TEAM:' in main
        and 'HMS v25.11 CODEX ENV RELOAD:' not in main,
        "legacy hidden footer authority identifies the current one-click release")

    add("cliproxy.safemode_template_cleanup",
        'function Remove-CLIProxyExampleApiKeys' in main
        and '"your-api-key-1","your-api-key-2","your-api-key-3"' in main
        and '$t=Remove-CLIProxyExampleApiKeys $t' in main,
        "HMS removes only official CLIProxy template keys before live startup")

    add("cliproxy.safemode_audit",
        'UnsafeExampleKeyCount' in main
        and 'CLIPROXY_EXAMPLE_API_KEY_SAFEMODE_RISK' in main,
        "live handoff refuses to start if template keys survive cleanup")

    add("cliproxy.safemode_header",
        'X-CPA-SAFE-MODE' in main
        and 'safe_mode=$safe' in main,
        "403 diagnostics capture CLIProxy X-CPA-SAFE-MODE header")

    add("cliproxy.custom_keys_preserved",
        'if($unsafe -contains $v){' in main
        and 'continue' in main,
        "cleanup targets exact unsafe placeholders rather than all custom keys")

    add("codexenv.restart_barrier",
        'function Ensure-CodexRestartBarrier' in main
        and 'CODEX_RESTART_REQUIRED:' in main
        and '$r=Ensure-CodexRestartBarrier' in main,
        "HMS blocks provider/.env mutation while an old Codex/ChatGPT process survives")

    add("codexenv.disk_verification",
        'function Test-CodexEnvDiskReady' in main
        and 'CODEX_ENV_WRITE_VERIFY_FAIL:' in main
        and 'HMS_ROUTER_API_KEY=' in main,
        "HMS verifies ~/.codex/.env after writing the local router key")

    add("codexenv.fresh_process_confirmation",
        'function Test-CodexClientFresh' in main
        and 'function Wait-CodexClientFresh' in main
        and 'CODEX_ENV_RELOAD_NOT_CONFIRMED:' in main,
        "HMS only confirms API-mode launch after a fresh desktop process starts")

    add("codexenv.open_button_stale_guard",
        'CODEX_CLIENT_STALE:' in main
        and 'Đã mở/focus ChatGPT Desktop (Codex view).' in main,
        "MỞ CODEX refuses to silently focus a stale process in HMS API mode")

    add("codexenv.failed_enable_rollback",
        'function Restore-ClientSnapshotTransactional' in main
        and 'if($codexMutated){$null=Restore-ClientSnapshotTransactional}' in main,
        "failed env reload rolls Codex config/.env back to the pre-HMS snapshot")

    add("codexenv.disable_restart_barrier",
        'HMS không tắt Router/restore config khi app cũ còn giữ provider HMS.' in main,
        "disable flow does not remove the router while a stale HMS provider process survives")

    add("ucc.stat_card_token_boundaries",
        'New-StatCard"' not in main
        and 'New-StatCard "ROUTER" 20 25 210 $pO' in main
        and 'New-StatCard "ACTIVE ROUTE" 1145 25 210 $pO' in main,
        "Native UCC StatCard command names cannot absorb quoted arguments")

    add("ucc.current_version_title",
        'HMS Codex Native Command Center · v25.43' in main,
        "Native UCC title tracks the package revision")

    add("native_gui.primary_host",
        'class HmsApp' in native_gui
        and 'tk.Tk()' in native_gui
        and 'GUI VISIBLE; BACKEND + NATIVE AUTOMATION SCHEDULED' in native_gui
        and 'self.root.after(300, self.refresh_async)' in native_gui,
        "Tk GUI is created and shown before backend status polling begins")

    add("native_gui.daily_actions",
        '"BẬT HMS"' in native_gui
        and '"TẮT HMS"' in native_gui
        and '"MỞ CODEX"' in native_gui
        and 'self.toggle' in native_gui
        and 'self.open_codex' in native_gui,
        "daily overview exposes Router toggle plus a dedicated MỞ CODEX action")

    add("native_gui.backend_hidden",
        'CREATE_NO_WINDOW' in native_gui
        and '"-WindowStyle", "Hidden"' in native_gui
        and 'stdout=subprocess.DEVNULL' in native_gui
        and 'stderr=subprocess.DEVNULL' in native_gui,
        "PowerShell backend calls are hidden and cannot create a console")

    add("native_gui.failure_survives",
        'messagebox.showwarning' in native_gui
        and 'BACKEND LỖI' in native_gui
        and 'Backend không tạo result.json' in native_gui,
        "backend failure is surfaced inside the persistent HMS GUI")

    required_backend_actions = [
        '"ui"', '"status"', '"enable"', '"disable"', '"open_codex"',
        '"get_settings"', '"save_settings"', '"get_accounts"', '"refresh_quota"',
        '"get_closed_loop_router"', '"evaluate_closed_loop_router"',
        '"apply_closed_loop_router"', '"rollback_closed_loop_router"',
        '"get_circuit_breaker"', '"evaluate_circuit_breaker"',
        '"apply_circuit_breaker"', '"reset_circuit_breaker"',
        '"get_predictive_quota"', '"evaluate_predictive_quota"',
        '"get_quota_center"', '"sync_quota_center"',
        '"get_account_analytics"', '"sync_account_analytics"',
        '"get_instances"', '"get_project_affinity"', '"sync_project_router"',
        '"get_model_manager"', '"discover_models"', '"save_model_policy"', '"apply_model_policy"'
    ]
    add("native_gui.backend_actions",
        '[ValidateSet(' in main
        and all(action in main for action in required_backend_actions)
        and 'NATIVE GUI BACKEND ACTIONS' in main
        and 'if($BackendAction -ne "ui")' in main
        and 'Write-HmsBackendResult' in main
        and '$BackendAction -eq "open_codex"' in main
        and '$BackendAction -eq "get_settings"' in main
        and '$BackendAction -eq "save_settings"' in main
        and '$BackendAction -eq "get_circuit_breaker"' in main
        and '$BackendAction -eq "apply_circuit_breaker"' in main
        and '$BackendAction -eq "get_predictive_quota"' in main
        and '$BackendAction -eq "evaluate_predictive_quota"' in main
        and '$BackendAction -eq "get_quota_center"' in main
        and '$BackendAction -eq "sync_quota_center"' in main
        and '$BackendAction -eq "get_account_analytics"' in main
        and '$BackendAction -eq "sync_account_analytics"' in main
        and '$BackendAction -eq "get_model_manager"' in main
        and '$BackendAction -eq "apply_model_policy"' in main,
        "PowerShell exposes bounded GUI backend actions including v25.37 model/reasoning controls")

    add("predictive_quota.engine_present",
        'POLICY_VERSION = "25.33"' in predictive
        and 'exhaust_before_reset' in predictive
        and 'new_session_load_factor' in predictive
        and 'forecast_is_not_reported_as_actual_quota' in predictive,
        "v25.33 Predictive Quota engine is reset-aware and explicitly keeps forecast distinct from live quota")

    add("predictive_quota.powershell_integration",
        'function Invoke-HmsPredictiveQuota' in main
        and 'PredictiveQuotaEnabled = $true' in main
        and 'codex-quota-history.jsonl' in main
        and '--predictive' in main,
        "PowerShell snapshots quota history, evaluates forecast, and feeds the plan into Closed-loop Router")

    add("predictive_quota.closed_loop_consumption",
        'predictive_quota_consumed' in closed_loop
        and 'PREDICTIVE_QUOTA_EMERGENCY' in closed_loop
        and 'predictive_load_factor' in closed_loop
        and 'session_affinity_untouched' in closed_loop,
        "Closed-loop lowers new-session score/weight from predictive pressure without changing existing session affinity")

    add("predictive_quota.native_gui",
        'MODEL/REASONING + IDENTITY + CLOSED-LOOP v25.37' in native_gui
        and 'DỰ BÁO' in native_gui
        and 'Predictive Quota v25.35' in native_gui
        and 'evaluate_predictive_quota' in native_gui,
        "native GUI exposes forecast status and on-demand evaluation without a destructive apply action")

    add("identity_isolation.engine_present",
        'VERSION = "25.36"' in identity_isolation
        and 'identity-v2536.json' in identity_isolation
        and 'CROSS_INSTANCE_PATH_COLLISION' in identity_isolation
        and 'IDENTITY_BINDING_SECRET_FIELD_PRESENT' in identity_isolation,
        "v25.36 identity auditor fingerprints boundaries and detects cross-instance collisions/secret-field regressions")

    add("identity_isolation.powershell_prelaunch",
        'function Assert-CodexIdentityBeforeLaunch' in main
        and 'IDENTITY_ISOLATION_BLOCKED' in main
        and 'HMS_CODEX_IDENTITY_FINGERPRINT' in main
        and 'binding-v2536.json' in main,
        "Codex launch is fail-closed behind v25.36 fingerprint audit and binding generation")

    add("identity_isolation.native_gui",
        'AUDIT ISOLATION' in native_gui
        and 'audit_identity' in native_gui
        and 'CodexIdentityFingerprintStrict' in native_gui,
        "native GUI exposes one-click identity audit and strict isolation settings")

    add("model_manager.engine_present",
        'ENGINE_VERSION = "25.74"' in model_manager
        and 'MODEL_POLICY_SECRET_FIELD_REJECTED' in model_manager
        and 'STABLE_ENDPOINT_MISMATCH' in model_manager
        and 'model_reasoning_effort' in model_manager,
        "v25.37 model manager validates live model policy and preserves isolated provider/endpoint contract")

    add("model_manager.powershell_integration",
        'function Invoke-HmsModelManager' in main
        and 'ModelManagerApplyBeforeLaunch = $true' in main
        and 'MODEL_POLICY_PRELAUNCH_BLOCKED' in main
        and 'get_model_manager' in main,
        "project model policy is available through native backend and optionally applied before instance launch")

    add("model_manager.native_gui",
        'Models Codex' in native_gui
        and 'PROJECT MODEL POLICY' in native_gui
        and 'save_model_policy' in native_gui
        and 'apply_model_policy' in native_gui,
        "native GUI exposes project-scoped model/reasoning policy without changing account binding")

    add("quota_center.engine_present",
        'POLICY_VERSION = "25.34"' in quota_center
        and 'CREATE TABLE IF NOT EXISTS quota_snapshots' in quota_center
        and 'CREATE TABLE IF NOT EXISTS forecast_predictions' in quota_center
        and 'source_state' in quota_center
        and 'abs_error_pct' in quota_center,
        "v25.34 Quota Center persists quota metadata and resolves forecast accuracy in SQLite")

    add("quota_center.safety",
        'quota_live_is_authoritative' in quota_center
        and 'forecast_is_labeled_forecast' in quota_center
        and 'no_oauth_token_or_cookie' in quota_center
        and 'stable_endpoint_untouched' in quota_center
        and 'destructive_delete' in quota_center,
        "Quota Center never promotes forecast to live quota and excludes prompt/secrets")

    add("quota_center.powershell_integration",
        'function Invoke-HmsQuotaCenter' in main
        and 'QuotaCenterEnabled = $true' in main
        and 'quota-center-v2534.sqlite3' in main
        and "Invoke-HmsQuotaCenter 'sync'" in main
        and '"quota-center"' in main,
        "PowerShell performs bounded background quota-center sync without touching credentials")

    add("quota_center.native_gui",
        'Advanced Quota Center' in native_gui
        and 'ĐỒNG BỘ QUOTA' in native_gui
        and 'def _quota_sparkline' in native_gui
        and 'Forecast accuracy 5h' in native_gui
        and 'SOURCE {fresh}' in native_gui
        and 'sync_quota_center' in native_gui,
        "native GUI exposes durable 5h/7d history, freshness, reset timeline and forecast accuracy")

    add("account_analytics.engine_present",
        'ENGINE_VERSION = "25.35"' in account_analytics
        and 'CREATE TABLE IF NOT EXISTS account_snapshots' in account_analytics
        and 'model_profiles' in account_analytics
        and 'workload_profiles' in account_analytics
        and 'quality_score' in account_analytics,
        "v25.35 Account Analytics builds confidence-aware long-term account/model/workload profiles")

    add("account_analytics.safety",
        'prompt_stored' in account_analytics
        and 'request_body_stored' in account_analytics
        and 'oauth_token_stored' in account_analytics
        and 'api_key_stored' in account_analytics
        and 'cookie_stored' in account_analytics,
        "Account Analytics consumes normalized metadata only and explicitly excludes prompt/body/secrets")

    add("account_analytics.powershell_integration",
        'function Invoke-HmsAccountAnalytics' in main
        and 'AccountAnalyticsEnabled = $true' in main
        and 'account-analytics-v2535.sqlite3' in main
        and "Invoke-HmsAccountAnalytics 'sync'" in main
        and '--analytics' in main,
        "PowerShell updates Account Analytics before Closed-loop and passes a bounded report signal")

    add("account_analytics.closed_loop_bounded",
        'account_analytics_consumed' in closed_loop
        and 'analytics_adjustment = max(-8.0, min(8.0' in closed_loop
        and 'ACCOUNT_ANALYTICS_POSITIVE' in closed_loop
        and 'session_affinity_untouched' in closed_loop,
        "Closed-loop consumes Account Analytics through a bounded ±8 score adjustment without touching sticky sessions")

    add("account_analytics.native_gui",
        '("analytics", "Phân tích", "logs")' in native_gui
        and 'def _build_account_analytics' in native_gui
        and 'ACCOUNT × MODEL' in native_gui
        and 'ACCOUNT × WORKLOAD' in native_gui
        and 'sync_account_analytics' in native_gui,
        "native GUI provides account quality, model and workload drill-down")

    add("native_gui.cockpit_palette",
        all(x in native_gui for x in [
            '"bg": "#0f172a"',
            '"surface": "#1e293b"',
            '"surface3": "#334155"',
            '"primary": "#3b82f6"',
            '"accent": "#14b8a6"',
            '"text": "#f1f5f9"',
            '"text2": "#94a3b8"'
        ]),
        "native GUI uses the Cockpit dark design-system palette")

    add("native_gui.cockpit_sidebar",
        'self.sidebar = tk.Frame' in native_gui
        and 'width=210' in native_gui
        and 'class NavItem' in native_gui
        and 'self.nav' in native_gui
        and all(x in native_gui for x in ['"Tổng quan"','"Tài khoản"','"Nhật ký"','"Cài đặt"']),
        "Cockpit-like fixed sidebar and active navigation are implemented")

    add("native_gui.cockpit_cards_pills",
        'class Card' in native_gui
        and 'class Pill' in native_gui
        and 'rounded_rect' in native_gui
        and 'status_pill' in native_gui
        and 'hover_border=True' in native_gui,
        "rounded floating cards, status pills and hover borders are implemented")

    add("native_gui.cockpit_motion",
        'class HoverButton' in native_gui
        and 'self.after(18, step)' in native_gui
        and 'self.root.attributes("-alpha", 0.0)' in native_gui
        and 'self._fade_in' in native_gui
        and 'def show_page(self, name, animate=True)' in native_gui,
        "button color interpolation, window fade-in and page slide transitions are implemented")

    add("native_gui.open_codex_action",
        '"MỞ CODEX"' in native_gui
        and 'self.backend("open_codex", 90)' in native_gui
        and 'self.open_codex_btn.set_enabled' in native_gui,
        "dedicated MỞ CODEX action is wired to the hidden backend")

    add("native_gui.settings_tabs",
        all(x in native_gui for x in [
            '"Chung"','"Codex"','"Router"','"Proxy"','"Nâng cao"',
            'show_settings_tab','ScrollableSettings','SettingGroup'
        ]),
        "Settings uses Cockpit-like pill tabs, scrolling groups and card rows")

    add("native_gui.settings_controls",
        'class ToggleSwitch' in native_gui
        and 'ttk.Combobox' in native_gui
        and 'LƯU THAY ĐỔI' in native_gui
        and 'HOÀN TÁC' in native_gui,
        "Settings exposes switches, selectors, inputs and explicit save/reload actions")

    add("native_gui.settings_real_backend",
        'self.backend("get_settings", 35)' in native_gui
        and 'self.backend("save_settings", 45, payload=payload)' in native_gui
        and 'Get-HmsBackendSettingsObject' in main
        and 'Apply-HmsBackendSettings' in main
        and 'SETTINGS_KEY_NOT_ALLOWED' in main,
        "Settings reads/writes a bounded backend allowlist instead of being decorative")

    add("native_gui.settings_core_fields",
        all(x in native_gui for x in [
            'CodexRoutingProfile','CodexSessionAffinityTtl','CodexWatchdogEnabled',
            'ForceCloseIfNeeded','OpenCodexOnEnable','ProxyDir','ProxyPort',
            'ProxyAffinityMode','ProxyAccountsPerProxy','PolicyKernelMode'
        ]),
        "core Codex/Router/Proxy/Policy settings are present in the native GUI")

    add("native_gui.settings_safety",
        '$script:S.RestoreOnDisable=$true' in main
        and '$script:S.CodexMinimizeToTray=$false' in main
        and 'SETTINGS_KEY_NOT_ALLOWED' in main
        and 'Convert-HmsSettingInt' in main,
        "settings preserve GUI-only safety invariants and validate keys/ranges")

    add("native_gui.settings_migration",
        'settings-v2523_1.json' in main
        and '$script:LegacySettingsPath = Join-Path $script:DataDir "settings-v2522.json"' in main,
        "v25.23.1 imports the immediately previous v25.22 settings before publishing the new settings file")

    add("native_gui.settings_feedback",
        'def toast(self, text, kind="success")' in native_gui
        and 'restart_required' in native_gui
        and 'Có thay đổi chưa lưu' in native_gui,
        "settings provides dirty-state, restart-required feedback and animated toast")

    add("native_gui.pixel_polish_windows",
        'def windows_chrome(root)' in native_gui
        and 'DwmSetWindowAttribute' in native_gui
        and 'SetCurrentProcessExplicitAppUserModelID' in native_gui
        and 'DWMWA_WINDOW_CORNER_PREFERENCE' in native_gui,
        "Windows host applies best-effort dark title bar, rounded corners and stable taskbar app id")

    add("native_gui.pixel_polish_tooltips",
        'class ToolTip' in native_gui
        and 'tooltip="Một nút tự xử lý Router, Codex reload, Watchdog và rollback."' in native_gui
        and 'tooltip="Mở hoặc đưa Codex/ChatGPT Desktop lên trước bằng HMS Router."' in native_gui,
        "primary actions expose delayed dark tooltips without adding visible clutter")

    add("native_gui.pixel_polish_loading",
        'def _render_loading_accounts(self)' in native_gui
        and 'if not self.first_status_loaded' in native_gui
        and 'self.status_pill.set("ĐANG TẢI", "primary")' in native_gui,
        "first backend poll uses a compact skeleton/loading state instead of a blank card")

    add("native_gui.pixel_polish_quota_motion",
        'def _animate_quota_fill(self, widget, pct, steps=10)' in native_gui
        and 'bar_fill.place(x=0, y=0, relwidth=0, relheight=1)' in native_gui
        and ('self._animate_quota_fill(bar_fill, pct)' in native_gui
             or 'self._animate_quota_fill(bar_fill, remaining)' in native_gui),
        "account quota bars animate into their live percentage")

    add("native_gui.pixel_polish_status_pulse",
        'def _start_status_pulse(self)' in native_gui
        and 'self.sidebar_status' in native_gui
        and 'math.sin' in native_gui,
        "sidebar runtime indicator gets a restrained running pulse")

    add("native_gui.pixel_polish_toggle_motion",
        'self.pos = 1.0 if bool(self.variable.get()) else 0.0' in native_gui
        and 'self.pos += delta * 0.34' in native_gui
        and 'self.after(16, step)' in native_gui,
        "settings switches animate the knob instead of snapping")

    add("native_gui.pixel_polish_compact_service",
        'hero = Card(page, 820, 82' in native_gui
        and 'width=118, height=31' in native_gui
        and ('card=Card(stats,196,72' in native_gui or 'card = Card(stats, 196, 72' in native_gui)
        and ('gateway=Card(page,820,96' in native_gui or 'gateway = Card(page, 820, 96' in native_gui),
        "Codex service hero, actions, stats and gateway are compacted to desktop-product density")

    add("native_gui.visual_v2_vector_icons",
        'def draw_line_icon' in native_gui
        and 'def draw_hms_mark' in native_gui
        and 'draw_line_icon(self, self.icon_name' in native_gui
        and 'draw_hms_mark(badge, 18, 18, 34)' in native_gui,
        "sidebar/service iconography uses a small HMS vector system instead of platform-dependent glyphs")

    add("native_gui.visual_v2_app_icon",
        (root/"HMS_AI_ROUTER.ico").exists()
        and 'self.root.iconbitmap(str(ROOT / "HMS_AI_ROUTER.ico"))' in native_gui,
        "native GUI ships and applies a dedicated HMS Windows application icon")

    add("native_gui.visual_v2_button_ripple",
        'def _ripple(self, x, y)' in native_gui
        and 'self._ripple(event.x, event.y)' in native_gui,
        "primary canvas buttons get restrained click-ripple feedback")

    add("native_gui.visual_v2_account_summary",
        'self.account_summary_labels' in native_gui
        and all(x in native_gui for x in ['("total","TỔNG")','("ready","READY")','("route_eligible","ROUTE OK")','("hold","HOLD")'])
        and 'self.account_summary_labels[key].configure' in native_gui,
        "Accounts page preserves live pool summary and extends it with routing-state cells")

    add("native_gui.visual_v2_last_sync",
        'self.sync_label' in native_gui
        and 'datetime.datetime.now().strftime("%H:%M:%S")' in native_gui
        and 'Đồng bộ lỗi' in native_gui,
        "topbar communicates last successful/failed backend synchronization")

    add("native_gui.visual_v2_settings_dirty_badge",
        'def set_badge(self, enabled: bool, color=None)' in native_gui
        and 'self.nav["settings"].set_badge(True, C["warning"])' in native_gui
        and 'self.nav["settings"].set_badge(False)' in native_gui,
        "Settings navigation shows a small dirty-state badge until backend config is reloaded/saved")

    add("native_gui.visual_v2_stat_motion",
        'def _animate_stat_value(self, key, new_text, color=None)' in native_gui
        and 'self._animate_stat_value("accounts"' in native_gui,
        "numeric overview stats animate to refreshed values")

    add("native_gui.visual_v2_shortcuts",
        'self.root.bind("<Control-r>"' in native_gui
        and 'self.root.bind("<Control-comma>"' in native_gui
        and 'self.root.bind("<Control-o>"' in native_gui,
        "native desktop shortcuts are available for refresh, settings and Open Codex")

    add("native_account_center.no_management_web",
        "/management.html" not in native_gui
        and "webbrowser.open" not in native_gui
        and "MỞ QUẢN LÝ" not in native_gui,
        "daily account/quota/log workflow no longer opens the CLIProxy management webpage")

    add("native_account_center.backend_actions",
        all(x in main for x in [
            '"get_accounts"','"refresh_quota"','"set_account_disabled"','"add_codex"','"get_logs"',
            'Get-HmsNativeAccountCenterObject','Start-HmsNativeCodexOAuth','Get-HmsNativeLogsObject'
        ]),
        "native backend exposes account center, quota refresh, OAuth, enable/disable and safe logs")

    add("native_account_center.direct_quota",
        'Invoke-CodexQuotaDirect' in main
        and 'hourlyRemaining' in main
        and 'weeklyRemaining' in main
        and 'five_hour_remaining' in main
        and 'weekly_remaining' in main,
        "5h and weekly remaining quota are carried from direct quota cache into native GUI data")

    add("native_account_center.extended_quota",
        'Convert-CodexAdditionalQuotaWindows' in main
        and 'Convert-CodexMonthlyCredits' in main
        and 'Convert-CodexCodeReviewQuota' in main
        and 'resetCreditsAvailable' in main
        and all(x in native_gui for x in ['Code Review','Monthly / Credits','Reset credits','additional_windows']),
        "native quota model includes code-review, monthly/credits, reset-credit count and additional model windows")

    add("native_account_center.quota_ui",
        'LÀM MỚI QUOTA' in native_gui
        and '5 giờ' in native_gui
        and 'Tuần' in native_gui
        and 'def _quota_bar' in native_gui
        and 'self._animate_quota_fill' in native_gui,
        "Account Center renders animated 5h/weekly quota bars with reset countdowns")

    add("native_account_center.account_actions",
        'THÊM TÀI KHOẢN' in native_gui
        and 'KÍCH HOẠT' in native_gui
        and 'TẠM DỪNG' in native_gui
        and 'self.backend("add_codex", 270)' in native_gui
        and '"set_account_disabled"' in native_gui,
        "OAuth add and non-destructive credential enable/disable are native")

    add("native_account_center.safe_logs",
        'self.backend("get_logs", 40)' in native_gui
        and 'Raw request logs có thể chứa credential/cookie' in main
        and 'request_logs' in main
        and 'router_lines' in main,
        "logs are viewable in HMS while raw request bodies/tokens remain excluded")

    add("native_service_center.tabs",
        all(x in native_gui for x in [
            '"Dịch vụ"','"Models"','"API Keys"','"Routing"','"Failover"',
            'show_service_tab','service_views'
        ]),
        "Codex API Service uses compact native tabs instead of new top-level windows")

    add("native_service_center.models",
        'self.backend("get_service",45)' in native_gui
        and 'TEST /v1/models' in native_gui
        and 'models=@($models.ToArray())' in main
        and 'Test-ApiModels' in main,
        "model discovery and /v1/models testing are native")

    add("native_service_center.client_keys",
        'TẠO CLIENT KEY' in native_gui
        and 'self.backend("create_client_key",60' in native_gui
        and 'New-HmsNativeClientKey' in main
        and 'created_client_key' in main
        and 'Secret chỉ hiển thị một lần' in main,
        "Smart Gateway client-key creation is native and plaintext is returned only on creation")

    add("native_service_center.request_log",
        'REQUEST LOG: ON' in native_gui
        and 'self.backend("set_request_log",70' in native_gui
        and 'Set-HmsNativeRequestLog' in main
        and 'Set-TopYaml $text "request-log"' in main,
        "request-log can be toggled from HMS with config verification and safe HMS-owned router restart")

    add("native_service_center.routing",
        'RESTART ROUTER' in native_gui
        and 'self.backend("restart_router",70)' in native_gui
        and 'Smart Gateway:' in native_gui
        and 'diagnostics' in main,
        "routing/pool/router/diagnostics are visible and controllable natively")

    add("native_service_center.failover",
        'CHẠY FAILOVER TEST' in native_gui
        and 'self.backend("run_failover",120' in native_gui
        and 'Invoke-HmsNativeFailover' in main
        and 'Invoke-HmsLiveFailoverProbe' in main
        and 'RESTORED:' in native_gui,
        "bounded live failover test is available inside the native GUI")

    add("native_service_center.no_destructive_key_delete",
        'XÓA CLIENT KEY' not in native_gui
        and 'delete-key' not in native_gui,
        "native client-key center does not expose destructive deletion")

    add("startup_hotfix.account_center_parent",
        'row_frame = tk.Frame(tools.card' not in native_gui
        and 'tools.card, "ACCOUNT CENTER"' in native_gui,
        "Account Center settings shortcut is parented to the SettingGroup card ancestor")

    add("startup_hotfix.fatal_guard",
        'def _fatal_startup(exc)' in native_gui
        and 'traceback.format_exception' in native_gui
        and 'HMS-AI-ROUTER — Startup Error' in native_gui
        and 'FATAL STARTUP CRASH' in native_gui,
        "startup exceptions are logged and surfaced via a GUI error dialog instead of disappearing silently")

    add("ux.one_click_shell",
        'v25.43 MULTI-CODEX TEAM + PROJECT ORCHESTRATOR + UNIFIED DIAGNOSTICS + SECURITY HARDENING + SELF-HEALING + API COMPATIBILITY + ROUTING UX SHELL' in main
        and 'Daily operation exposes one primary action only: BẬT HMS / TẮT HMS.' in main,
        "v25.43 preserves one primary daily action while team/project orchestration/diagnostics/security remain behind GUI controls")

    add("ux.single_primary_action",
        '$uxOneButton=New-HmsUxButton "BẬT HMS"' in main
        and '$uxOneButton.Text="TẮT HMS"' in main
        and 'foreach($ctl in @($form.Controls)){$ctl.Visible=$false}' in main
        and '$uxGear=New-HmsUxButton "⚙"' in main,
        "legacy control wall is hidden; one large toggle plus one settings gear remain visible")

    add("ux.one_click_orchestrator",
        all(x in main for x in [
            'function Invoke-HmsOneClickEnable',
            'function Invoke-HmsOneClickDisable',
            'function Set-HmsOneClickPolicy',
            'function Select-HmsOneClickSafePort',
            'function Assert-HmsOneClickAccounts',
            'Enable-HmsMode',
            'Disable-HmsMode'
        ]),
        "one-click wrapper composes existing transactional router/Codex engine")

    add("ux.one_click_policy_authority",
        'if([bool]$script:OneClickMode)' in main
        and 'Set-HmsOneClickPolicy' in main
        and '$script:S.ForceCloseIfNeeded=$true' in main
        and '$script:S.OpenCodexOnEnable=$true' in main
        and '$script:S.CodexWatchdogEnabled=$true' in main,
        "hidden legacy controls cannot overwrite one-click runtime settings")

    add("ux.foreign_port_autoselect",
        'foreach($candidate in 8318..8337)' in main
        and 'HMS không chiếm port của Cockpit/ứng dụng khác.' in main,
        "one-click automatically avoids foreign/Cockpit listeners without killing them")

    add("ux.cockpit_interaction_patterns",
        'Set-HmsUxRoundedRegion' in main
        and 'Add_MouseEnter' in main
        and '$form.Opacity=0' in main
        and '$uxHero' in main
        and '$uxStateDot' in main,
        "rounded surfaces, hover feedback, fade-in and compact service state remain")

    add("ux.engine_preserved",
        'Show-CodexUnifiedCommandCenter' in main
        and 'Show-HmsLiveFailoverCenter' in main
        and 'Enable-HmsMode' in main
        and 'Disable-HmsMode' in main,
        "previous routing/failover/control-plane engines remain callable behind one-click UX")

    add("gui.no_cmd_start",
        re.search(r'Start-Process\s+["\']?cmd\.exe',main,re.I) is None,
        "main GUI contains no direct cmd.exe launch")

    add("gui.no_visible_windowstyle",
        "WindowStyle Minimized" not in main and "WindowStyle Normal" not in main,
        "main GUI has no Minimized/Normal console helper launch")

    add("gui.router_hidden",
        '-WindowStyle Hidden -PassThru' in main
        and 'RedirectStandardOutput $stdout -RedirectStandardError $stderr' in main,
        "CLIProxyAPI Router starts hidden with diagnostic redirection")

    add("gui.oauth_dialog",
        'function Login-Provider' in main
        and 'HMS — Đăng nhập tài khoản' in main
        and '-WindowStyle Hidden -PassThru' in main
        and 'Start-Process "cmd.exe"' not in main,
        "OAuth uses an HMS WinForms dialog and hidden child instead of cmd.exe")

    add("gui.embedded_cli",
        'function Start-CodexCliEmbedded' in main
        and '$psi.CreateNoWindow=$true' in main
        and '$psi.RedirectStandardInput=$true' in main
        and '$psi.RedirectStandardOutput=$true' in main
        and '$psi.RedirectStandardError=$true' in main,
        "advanced Codex CLI uses an embedded WinForms terminal with no console window")

    visible_ps=[]
    for ln,line in enumerate(main_src.splitlines(),1):
        if re.search(r'Start-Process\s+["\']?powershell\.exe',line,re.I) and "WindowStyle Hidden" not in line:
            visible_ps.append(f"line={ln}:{line.strip()}")
    add("gui.powershell_helpers_hidden",not visible_ps,
        "all direct PowerShell helper launches are hidden" if not visible_ps else " | ".join(visible_ps[:8]))

    runtime_console_risks=[]
    for ps in root.glob("*.ps1"):
        src=ps.read_text("utf-8-sig",errors="replace")
        for ln,line in enumerate(src.splitlines(),1):
            if re.search(r'Start-Process\s+["\']?cmd\.exe',line,re.I):
                runtime_console_risks.append(f"cmd:{ps.name}:{ln}:{line.strip()}")
            if re.search(r'WindowStyle\s+(?:Normal|Minimized)',line,re.I):
                runtime_console_risks.append(f"style:{ps.name}:{ln}:{line.strip()}")
            if re.search(r'Start-Process\s+["\']?powershell\.exe',line,re.I) and "WindowStyle Hidden" not in line:
                runtime_console_risks.append(f"powershell:{ps.name}:{ln}:{line.strip()}")
    add("gui.runtime_no_visible_console",not runtime_console_risks,
        "all PowerShell UI/helper launch paths are hidden" if not runtime_console_risks else " | ".join(runtime_console_risks[:12]))

    add("gui.window_restore_contract",
        'function Restore-HmsMainWindow' in main
        and '$form.ShowInTaskbar=$true' in main
        and '$script:S.CodexMinimizeToTray=$false' in main
        and '$form.Hide()' not in main,
        "main GUI uses normal taskbar minimize/restore and cannot hide itself via legacy tray policy")

    add("gui.window_restore_focus",
        '$form.BringToFront()' in main
        and '$form.Activate()' in main
        and 'SetForegroundWindow' in main
        and 'ShowWindowAsync' in main,
        "restore helper explicitly returns the main WinForms window to foreground")

    add("ui.button_token_boundaries",
        re.search(r'\bBtn\s+[\"\'][^\"\']*[\"\']\d',main) is None,
        "button helper calls cannot absorb numeric coordinates into quoted labels")

    add("failover.bounded_single_auth_mutation",
        'function Invoke-HmsLiveFailoverProbe' in main
        and 'Set-HmsAuthDisabledProperty $TargetFile $true $false' in main
        and 'Cần tối thiểu 2 Codex OAuth account' in main,
        "live failover disables exactly one selected auth only after 2-account preflight")

    add("failover.single_live_responses_probe",
        "HMS_FAILOVER_PROBE_" in main
        and "/v1/responses" in main
        and "model='gpt-5.4-mini'" in main,
        "failover proof uses one bounded Responses API request")

    add("failover.request_log_account_proof",
        'Find-HmsFailoverRequestEvidence' in main
        and 'selected_auth_id' in main
        and 'selected_label' in main,
        "failover verdict is tied to Request Log Auth mapping")

    add("failover.finally_restore",
        '}finally{' in main
        and 'target_original_had_disabled_property' in main
        and "verdict='FAIL_RESTORE'" in main,
        "selected auth disabled state is restored in finally and restore failure is terminal")

    add("failover.no_auth_delete",
        'No auth deletion; only selected disabled flag was temporarily changed and restored.' in main
        and 'Remove-Item $TargetFile' not in main,
        "live failover test never deletes the selected credential")

    add("api_compat.contract_endpoint",
        '"/hms/compatibility"' in smart_gateway and 'compatibility_contract' in smart_gateway and 'version":"25.38"' in smart_gateway,
        "Smart Gateway exposes a versioned local compatibility contract")
    add("api_compat.body_preserving_features",
        all(x in smart_gateway for x in ['tool_calls','mcp','web_search','image_input','attachments','structured_output','reasoning'])
        and 'request_body_logged":False' in smart_gateway,
        "Codex feature labels are detected without logging request bodies")
    add("api_compat.transport",
        'def _read_body(self):' in smart_gateway and 'Transfer-Encoding' in smart_gateway and 'def do_PATCH(self)' in smart_gateway and 'text/event-stream' in smart_gateway,
        "chunked request decode, PATCH and SSE relay paths are present")
    add("api_compat.error_semantics",
        'compat_error_payload' in smart_gateway and 'upstream_error_body_passthrough' in smart_gateway and 'INVALID_CLIENT_KEY' in smart_gateway,
        "HMS-generated errors are normalized while upstream errors stay pass-through")
    add("api_compat.native_gui",
        '"API Compat"' in native_gui and 'AUDIT API' in native_gui and 'run_api_compatibility' in native_gui and 'get_api_compatibility' in main,
        "native GUI exposes API compatibility status and one-click local audit")
    add("api_compat.synthetic_validator",
        'responses.body_preservation' in api_compat and 'streaming.sse' in api_compat and 'transport.chunked_request' in api_compat and 'privacy.no_body_or_secret_trace' in api_compat,
        "v25.38 validator covers body preservation, SSE, chunked transport and privacy")

    add("self_heal.engine_contract",
        'never_kill_unowned_process' in self_heal and 'no_destructive_delete' in self_heal and 'evidence_before_repair' in self_heal and 'readback_required' in self_heal,
        "v25.39 self-healing engine publishes explicit safety invariants")
    add("self_heal.foreign_port_fail_closed",
        'INSTANCE_PORT_FOREIGN' in self_heal and 'GLOBAL_PORT_FOREIGN' in self_heal and 'foreign_port_never_auto_killed' in self_heal,
        "foreign listeners never produce a kill/stop repair action")
    add("self_heal.backend_actions",
        all(x in main for x in ['get_self_healing','audit_self_healing','repair_self_healing','Invoke-HmsSelfHealing','Get-HmsSelfHealingSnapshot']),
        "PowerShell backend exposes audit/repair orchestration")
    add("self_heal.evidence_and_rollback",
        all(x in main for x in ['pre-state.json','post-state.json','plan.json','result.json','SELF_HEAL_INSTANCE_CONFIG_READBACK_FAILED']),
        "self-healing writes pre/post evidence and explicit readback/rollback paths")
    add("self_heal.native_gui",
        '"Tự sửa Codex"' in native_gui and 'SỬA AN TOÀN' in native_gui and 'audit_self_healing' in native_gui and 'repair_self_healing' in native_gui,
        "native GUI exposes one-click audit and guarded safe repair")

    add("security.protected_secret_vault",
        all(x in main for x in ['Set-HmsProtectedSecret','Get-HmsProtectedSecret','HmsCredentialManager','DataProtectionScope]::CurrentUser',"$persist['LocalApiKey']=''"]),
        "canonical Router keys use Credential Manager with CurrentUser DPAPI fallback; settings plaintext is cleared")
    add("security.instance_secret_refs",
        all(x in main for x in ['apiKeyRef','PROTECTED_CURRENT_USER','Get-HmsInstanceApiKey','Invoke-HmsSecurityMigrateInstanceSecrets']),
        "managed Codex instances persist protected key references instead of canonical plaintext keys")
    add("security.acl_and_reparse_guard",
        all(x in main for x in ['Set-HmsCurrentUserOnlyAcl','Set-HmsSecurityPathAclEarly','Test-HmsPathHasReparsePoint']) and 'REPARSE_POINT_IN_SECURITY_BOUNDARY' in security_hardening,
        "security/instance boundaries are ACL hardened and reparse points fail closed")
    add("security.integrity_seals",
        all(x in main for x in ['HMACSHA256','Update-HmsSecuritySeals','operator-explicit-reseal','INTEGRITY_SEAL_MISMATCH'])
        and 'no_auto_reseal_on_mismatch' in security_hardening,
        "HMAC integrity seals never auto-accept an existing mismatch")
    add("security.evidence_redaction",
        all(x in main for x in ['Redact-HmsSecurityText','Protect-HmsSelfHealingRollbackFile','Restore-HmsSelfHealingEvidenceFile','DPAPI_CURRENT_USER_FOR_SENSITIVE_FILES'])
        and 'HMS_ROUTER_API_KEY' in diagnostics_bundle and 'client[_-]?secret' in diagnostics_bundle,
        "sensitive self-heal rollback copies are DPAPI protected and diagnostics use unified strict redaction")
    add("security.native_gui",
        '"Bảo mật"' in native_gui and 'Codex Security Hardening' in native_gui and all(x in native_gui for x in ['audit_security','harden_security','seal_security'])
        and all(x in main for x in ['get_security','audit_security','harden_security','seal_security']),
        "native GUI exposes audit, guarded hardening and operator-only explicit reseal")
    add("security.synthetic_engine_contract",
        all(x in security_hardening for x in ['clean_snapshot_passes','reparse_is_fail_closed','seal_mismatch_never_auto_resealed','runtime_materialization_acl_hardening_planned','secret_values_rejected_from_snapshot']),
        "v25.40 security engine covers protected storage, ACL, reparse, seal mismatch and secret-free snapshot invariants")

    add("unified_diagnostics.engine_contract",
        all(x in unified_diagnostics for x in ['usage_events','closed_loop_events','circuit_events','predictive_events','issue_events','request_timelines']),
        "v25.41 unifies request/router/quota/circuit/self-healing/security metadata")
    add("unified_diagnostics.privacy",
        all(x in unified_diagnostics for x in ['contains_prompt', 'contains_request_body', 'contains_raw_secret', 'PROMPT_KEY', 'SECRET_KEY'])
        and 'metadata_only' in unified_diagnostics,
        "Unified Diagnostics is metadata-only and explicitly excludes prompt/body/secret fields")
    add("unified_diagnostics.backend_actions",
        all(x in main for x in ['get_unified_diagnostics','refresh_unified_diagnostics','Invoke-HmsUnifiedDiagnostics','Get-HmsNativeUnifiedDiagnosticsObject']),
        "PowerShell backend exposes read/refresh diagnostics without mutation actions")
    add("unified_diagnostics.native_gui",
        '"Chẩn đoán"' in native_gui and 'LÀM MỚI TIMELINE' in native_gui and 'refresh_unified_diagnostics' in native_gui and 'UNIFIED REQUEST / ROUTER TIMELINE' in native_gui,
        "native GUI exposes a dedicated unified diagnostics timeline")
    add("unified_diagnostics.bundle_integration",
        'unified-diagnostics-latest-v2541.json' in diagnostics_bundle and 'UNIFIED_DIAGNOSTICS_VALIDATION_V25.41.json' in diagnostics_bundle,
        "redacted diagnostics bundle includes the v25.41 metadata timeline and validation evidence")

    add("project_orchestrator.engine_contract",
        all(x in project_orchestrator for x in ["one_click_ready", "IDENTITY_ISOLATION_BLOCKED", "SECURITY_HARD_GATE_BLOCKED", "FOREIGN_PORT_OWNER", "plan_hash"]),
        "v25.42 orchestrator emits deterministic one-click plans with identity/security/foreign-port hard gates")
    add("project_orchestrator.backend_actions",
        all(x in main for x in ["get_project_orchestrator", "preflight_project_orchestrator", "launch_project_orchestrator", "Launch-HmsNativeProjectOrchestrator"]),
        "PowerShell backend exposes status/preflight/one-click launch actions")
    add("project_orchestrator.native_gui",
        all(x in native_gui for x in ["Điều phối Project", "PRE-FLIGHT", "MỞ MÔI TRƯỜNG", "load_project_orchestrator_async"]),
        "native GUI exposes dedicated one-click project orchestration")
    add("project_orchestrator.no_destructive_process_policy",
        "Unowned processes are never killed" in project_orchestrator and "FOREIGN_PORT_OWNER" in project_orchestrator,
        "project orchestrator fails closed on foreign port/process ownership")
    add("project_orchestrator.synthetic_validator",
        all(x in project_orchestrator_validator for x in ["identity_is_hard_gate", "security_is_hard_gate", "foreign_port_fail_closed", "secret_field_rejected"]),
        "v25.42 synthetic suite covers core hard gates and privacy")

    add("multi_codex_team.engine_contract",
        all(x in multi_team for x in ["CODER", "REVIEWER", "TESTER", "WORKSPACE_OVERLAP_", "ACCOUNT_ROLE_COLLISION", "ownership_leases", "epoch"]),
        "v25.43 team engine models role topology, workspace/account conflicts and explicit epoch ownership")
    add("multi_codex_team.backend_actions",
        all(x in main for x in ["get_multi_codex_team", "save_multi_codex_team", "preflight_multi_codex_team", "launch_multi_codex_team", "Launch-HmsNativeMultiCodexTeam"]),
        "PowerShell backend exposes team status/save/preflight/launch actions")
    add("multi_codex_team.native_gui",
        all(x in native_gui for x in ["Đội Codex", "LƯU TEAM", "MỞ TEAM", "load_multi_codex_team_async"]),
        "native GUI exposes Coder/Reviewer/Tester team topology")
    add("multi_codex_team.no_silent_takeover",
        all(x in main for x in ["TEAM_REBIND_RUNNING_BLOCKED", "HMS_CODEX_TEAM_EPOCH", "HMS_CODEX_TEAM_ROLE"])
        and "Role rebinding uses an explicit epoch" in multi_team,
        "running role rebinding is blocked and process role identity carries explicit epoch")
    add("multi_codex_team.diagnostics_bundle",
        all(x in diagnostics_bundle for x in ["multi-codex-team-v2543.json", "multi-codex-team-latest-v2543.json", "multi-codex-team-history-v2543.jsonl"]),
        "redacted diagnostics bundle includes v25.43 team metadata")

    add("smart_model_router.engine_contract",
        all(x in smart_model for x in ["STICKY_GUARD", "CAPABILITY_CODING_REQUIRED", "account_adjustments", "max_account_score_adjustment", "identity_isolation_hard_gate", "security_hard_gate"]),
        "v25.44 Smart Model Router has capability gates, sticky-session protection and bounded account affinity")
    add("smart_model_router.backend_actions",
        all(x in main for x in ["get_smart_model_router", "evaluate_smart_model_router", "apply_smart_model_router", "rollback_smart_model_router", "Invoke-HmsSmartModelRouter"]),
        "PowerShell backend exposes Smart Model status/evaluate/manual apply/rollback")
    add("smart_model_router.closed_loop_signal",
        '--smart-model' in main and '--smart-model' in closed_loop and 'SMART_MODEL_ACCOUNT_AFFINITY' in closed_loop and 'max(-8.0, min(8.0' in closed_loop,
        "Smart Model account affinity is passed to Closed-loop and hard bounded to ±8")
    add("smart_model_router.no_hot_switch",
        'RUNNING_CLIENT_HOT_SWITCH_BLOCKED' in smart_model and 'running_client_hot_switch_blocked' in smart_model and 'SmartModelRouterProtectRunningSessions' in main,
        "active managed clients are never hot-switched by Smart Model apply")
    add("smart_model_router.native_gui",
        all(x in native_gui for x in ["Smart Router", "ĐÁNH GIÁ", "ÁP DỤNG", "HOÀN TÁC", "load_smart_model_router_async"]),
        "native GUI exposes dedicated Smart Model Router controls")
    add("smart_model_router.privacy",
        all(x in smart_model for x in ["NO_PROMPT_NO_REQUEST_BODY_NO_OAUTH_NO_API_KEY_NO_COOKIE", '"prompt_consumed": False', '"request_body_consumed": False', '"oauth_tokens_untouched": True']),
        "Smart Model Router consumes only metadata/capability signals and no prompt/body/secret")

    add("smart_model_router.diagnostics_bundle",
        all(x in diagnostics_bundle for x in ["smart-model-router-state-v2544.json", "smart-model-router-plan-v2544.json", "smart-model-router-history-v2544.jsonl", "SMART_MODEL_ROUTER_VALIDATION_V25.44.json"]),
        "redacted diagnostics bundle includes Smart Model decision state/plan/history and validation evidence")

    add("lan_pool.engine_contract",
        all(x in lan_pool for x in ["HMAC-SHA256", "PROJECT_LEASE", "NO_RAW_CREDENTIAL_SHARING", "BLOCKED_OWNED_BY_OTHER_NODE", "TAKEOVER_EXPIRED", "normalize_origin"]),
        "v25.45 LAN pool provides signed heartbeat, project lease/epoch and cross-PC Git-origin identity")
    add("lan_pool.backend_actions",
        all(x in main for x in ["get_lan_pool", "pair_lan_pool", "heartbeat_lan_pool", "acquire_lan_project", "release_lan_project", "Assert-HmsLanProjectLeaseBeforeLaunch"]),
        "PowerShell backend exposes LAN status/pair/heartbeat/lease actions and prelaunch ownership hard gate")
    add("lan_pool.native_gui",
        all(x in native_gui for x in ["LAN Pool", "Cross-PC / LAN Codex Pool", "HEARTBEAT", "PAIR", "load_lan_pool_async"]),
        "native GUI exposes LAN node pairing and signed registry status")
    add("lan_pool.protected_pairing_secret",
        all(x in main for x in ["LanPoolCredentialTarget", "Set-HmsProtectedSecret $script:LanPoolCredentialTarget", "Get-HmsProtectedSecret $script:LanPoolCredentialTarget"]) and "HMS_LAN_POOL_KEY_HEX" in main,
        "pairing key stays in Windows Credential Manager/DPAPI and is passed to helper only via inherited environment")
    add("lan_pool.no_raw_credentials",
        all(x in lan_pool for x in ["credential_sharing", "raw_token_sharing", "account_hashes", "secret_values_excluded"]) and "accountEmail" not in lan_pool,
        "shared registry uses account hashes/metadata and never transports Codex account credentials")
    add("lan_pool.validator_contract",
        all(x in lan_pool_validator for x in ["same_git_origin_same_cross_pc_fingerprint", "second_node_blocked_while_lease_active", "tampered_heartbeat_rejected", "expired_lease_takeover_allowed", "pairing_key_not_written_to_shared_registry"]),
        "synthetic LAN validator covers collision, signature tamper, release ownership and expired failover takeover")
    add("lan_pool.diagnostics_bundle",
        all(x in diagnostics_bundle for x in ["lan-pool-latest-v2545.json", "lan-pool-history-v2545.jsonl", "LAN_POOL_VALIDATION_V25.45.json"]),
        "redacted diagnostics bundle includes v25.45 LAN metadata and validation evidence")
    add("lan_pool.unified_diagnostics",
        all(x in unified_diagnostics for x in ["lan_pool_events", "LAN_PROJECT_LEASE", '"lan_pool"']),
        "Unified Diagnostics includes signed LAN node/lease metadata without secrets")

    add("v25_46.public_contract_freeze",
        all(x in public_contract for x in ["EXACT_BACKEND_ACTION_SET_NO_BREAKING_CHANGE", "hms_api_router", "hms_instance_router", "settings-v2523_1.json", "LanPoolPairingKey:v25.45"]),
        "v25.46 freezes public backend actions and stable provider/state/secret references")
    add("v25_46.compatibility_freeze_validator",
        all(x in compatibility_freeze for x in ["backend_action_set_exact", "codex_only_no_antigravity_public_action", "milestone_", "lan_pairing_kdf_salt_stable"]),
        "compatibility validator covers exact actions, Codex-only surface, milestone preservation and migration-stable LAN KDF")
    add("v25_46.client_compatibility_matrix",
        all(x in client_matrix for x in ["Codex CLI", "Codex Desktop", "ChatGPT Desktop (Codex view)", "RUNTIME_DISCOVERY_NO_HARDCODED_CLIENT_VERSION_WHITELIST"]),
        "Codex CLI/Desktop compatibility matrix is explicit without a brittle client version whitelist")
    add("v25_46.client_migration_validator",
        all(x in client_compat_validator for x in ["fallback_settings", "corrupt_settings_backup", "plain_key_protected_migration", "restart_generation_guard"]),
        "client validator checks legacy settings fallback, corrupt backup, protected key migration and restart generation guard")
    add("v25_46.lan_clock_payload_hardening",
        all(x in lan_pool for x in ["MAX_FUTURE_SKEW_SEC", "MAX_HEARTBEAT_TTL_SEC", "MAX_LEASE_TTL_SEC", "MALFORMED_PAYLOAD", "CLOCK_SKEW_FUTURE", "DUPLICATE_NODE_ID", "BLOCKED_INVALID_PAYLOAD"]),
        "LAN registry rejects future skew, malformed signed payloads, duplicate node ids and invalid leases")
    add("v25_46.lan_smb_retry",
        "FS_RETRY_ATTEMPTS = 3" in lan_pool and "synthetic SMB reconnect" in lan_failure_validator and "smb_transient_publish_retry" in lan_failure_validator,
        "atomic JSON publish uses bounded retry and failure matrix exercises a transient SMB publish failure")
    add("v25_46.lan_failure_matrix",
        all(x in lan_failure_validator for x in ["share_unavailable_fails_closed", "active_lock_not_silently_stolen", "future_clock_skew_lease_blocks_takeover", "expired_lease_takeover_newer_epoch"]),
        "failure matrix covers unavailable share, locks, clock skew and controlled expired takeover")
    add("v25_46.regression_aggregator",
        all(x in regression_freeze for x in ["compatibility_freeze", "client_compatibility", "lan_failure_matrix", "runtime_kit", "powershell_static_lint", "powershell_coherence"]),
        "v25.46 regression aggregator reruns cross-version structural and synthetic gates")

    add("v25_47.soak_profiles_and_resume",
        all(x in reliability_soak for x in ['"6h": 6 * 60 * 60', '"24h": 24 * 60 * 60', "ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED", "session_count", "SOAK_TARGET_DURATION_CHANGED"]),
        "v25.47 provides exact 6h/24h profiles, resumable checkpoints and active-process-time-only accounting")
    add("v25_47.standard_profile_duration_immutable",
        "SOAK_STANDARD_PROFILE_DURATION_IMMUTABLE" in reliability_soak,
        "6h/24h named profiles cannot be shortened with --duration-sec and falsely certified")
    add("v25_47.full_topology_gate",
        all(x in reliability_soak for x in ["required_router_target", "required_two_instance_targets", "required_shared_lan_path"]),
        "real 6h/24h cannot pass without Router, at least two instance targets and shared LAN path")
    add("v25_47.application_health_probe",
        all(x in reliability_soak for x in ["gateway_health_probe", 'GET", "/hms/health"', "HEALTH_NOT_OK", "INVALID_HEALTH_JSON"]),
        "Router and Codex instance probes require application-layer /hms/health success, not only an open TCP port")
    add("v25_47.bounded_recovery",
        all(x in reliability_soak for x in ["DEFAULT_RECOVERY_ATTEMPTS", "RECOVERY_EXHAUSTED", "RECOVERY_BUDGET_EXCEEDED", "transient_fault_recovered", "shared_roundtrip"]),
        "soak harness records bounded reconnect recovery and fails closed on exhausted/budget-violating recovery")
    add("v25_47.lease_and_node_faults",
        all(x in reliability_soak for x in ["SOAK_FOREIGN_SILENT_TAKEOVER", "lease_churn_ok", "SOAK_NODE_DISCONNECT_NOT_DETECTED", "SOAK_NODE_REJOIN_FAILED"]),
        "synthetic reliability loop covers foreign ownership, lease churn and disconnect/rejoin")
    add("v25_47.cooperative_stop",
        all(x in reliability_soak for x in ["STOP_REQUESTED", 'self.checkpoint["state"] = "PAUSED"', "no process kill is performed"]),
        "STOP checkpoints and pauses instead of force-killing the soak process")
    add("v25_47.native_gui_soak_controls",
        all(x in native_gui for x in ["RELIABILITY / SOAK v25.47", "start_reliability_soak_async", "resume_reliability_soak_async", "stop_reliability_soak_async", "soak-checkpoint-v2547"]),
        "LAN Pool GUI exposes smoke/6h/24h, resume, stop and live checkpoint status")
    add("v25_47.diagnostics_soak_surface",
        "reliability-soak-v2547" in unified_diagnostics and "SOAK_RUN" in unified_diagnostics and "reliability_soak" in unified_diagnostics,
        "Unified Diagnostics exposes metadata-only soak state without prompt/body/secrets")
    add("v25_47.soak_validator_contract",
        all(x in reliability_soak_validator for x in ["downtime_not_counted", "six_hour_profile_requires_full_topology", "foreign_silent_takeover_blocked", "lease_churn_exercised", "graceful_stop_pauses_partial_run"]),
        "v25.47 synthetic validator covers resume, topology gates, lease safety and cooperative stop")

    add("v25_48.performance_control_plane_metrics",
        all(x in performance_scale for x in ["control_plane_ttfb_ms", "GET", "/hms/health", "NOT model token TTFT", "NOT_MEASURED_NO_QUOTA_CONSUMPTION"]),
        "v25.48 measures control-plane latency/TTFB without mislabeling it as model token TTFT or consuming model quota")
    add("v25_48.performance_multi_instance_roles",
        all(x in performance_scale for x in ["--router-target", "--instance-target", "router_configured", "instance_target_count", "target_roles"]),
        "Router and managed instance targets are explicit and multi-instance coverage requires at least two instance targets")
    add("v25_48.performance_backpressure",
        all(x in performance_scale for x in ["BoundedQueueGate", "queue_capacity", "backpressure_observed", "no_silent_drop", "max_queue_depth"]),
        "bounded queue/backpressure contract rejects overload without silently dropping accepted work")
    add("v25_48.performance_reconnect_and_lan_contention",
        all(x in performance_scale for x in ["reconnect_storm", ".hms_perf", "shared_contention", "throughput_ops_sec", "ROUNDTRIP_MISMATCH"]),
        "reconnect storm and isolated shared-filesystem contention are exercised with integrity checks")
    add("v25_48.performance_privacy_and_claim_boundary",
        all(x in performance_scale for x in ["target_hashes", "shared_path_hash", '"payload_capture": False', '"authorization_capture": False', '"production_certification": "NOT_CLAIMED"']),
        "performance evidence stores hashes/indexes only and never auto-claims production certification")
    add("v25_48.performance_validator_contract",
        all(x in performance_scale_validator for x in ["bounded_queue_never_exceeds_capacity", "router_and_multi_instance_roles_explicit", "reconnect_storm_exercised", "shared_contention_exercised", "unreachable_benchmark_fails_closed"]),
        "synthetic validator covers saturation/backpressure, multi-instance distribution, reconnect storm, LAN contention and fail-closed targets")
    add("v25_48.native_gui_performance_control",
        all(x in native_gui for x in ["PERFORMANCE / SCALE v25.48", "start_performance_scale_async", "performance-scale-latest-v2548.json", "BENCHMARK", "Model TTFT thật chưa được đo"]),
        "LAN Pool GUI exposes a non-blocking benchmark and labels real model TTFT as not measured")
    add("v25_48.unified_diagnostics_performance_surface",
        all(x in unified_diagnostics for x in ["performance_scale_events", "PERFORMANCE_SCALE_RUN", '"performance_scale"', "performance-scale-latest-v2548.json"]),
        "Unified Diagnostics exposes metadata-only performance evidence")
    add("v25_48.diagnostics_bundle_performance_surface",
        all(x in diagnostics_bundle for x in ["performance-scale-latest-v2548.json", "PERFORMANCE_SCALE_VALIDATION_V25.48.json", "BUILD_VALIDATION_V25.48.txt"]),
        "Diagnostics bundle includes redacted v25.48 performance evidence and release validation")

    add("v25_49.real_codex_capability_detection",
        all(x in real_codex_cert for x in ['codex, "--version"', 'codex, "--help"', '"login", "status"', '"doctor"', 'hard_coded_codex_version_allowlist']),
        "v25.49 detects installed Codex capabilities/version without a brittle version allowlist")
    add("v25_49.auth_state_privacy",
        all(x in real_codex_cert for x in ["auth_file_metadata", "sha256", "auth_json_content_logged", "token_or_api_key_logged", "redact_text"]),
        "auth state is fingerprinted/redacted without persisting token or API-key contents")
    add("v25_49.windows_ps51_parser_gate",
        all(x in real_codex_cert for x in ["WindowsPowerShell", "Parser]::ParseFile", "is_windows_powershell_5_1", "parser_ok"]),
        "target-machine harness has an explicit Windows PowerShell 5.1 parser/runtime gate")
    add("v25_49.real_topology_generation_guard",
        all(x in real_codex_cert for x in ["at_least_two_instances", "unique_projects", "unique_codex_homes", "dedicated_accounts", "process_generation_guard", "start_generation_match"]),
        "real certification requires two isolated instances and verifies process restart generation")
    add("v25_49.live_budget_and_ttft_boundary",
        all(x in real_codex_cert for x in ["MAX_LIVE_REQUEST_CAP = 8", "LIVE_REQUEST_REQUIRES_EXPLICIT_ALLOW", "response.output_text.delta", "first_token_ttft_certified", "never inferred"]),
        "live request path is explicit/bounded and exact token TTFT requires output_text.delta")
    add("v25_49.credential_bridge_ephemeral_secret",
        all(x in real_codex_bridge for x in ["ReadGeneric", "SetEnvironmentVariable", "finally", "HMS_CERT_KEY_", "MaxLiveRequests"]),
        "Windows bridge reads protected Router key into process environment only and clears it in finally")
    add("v25_49.native_gui_real_cert_controls",
        all(x in native_gui for x in ["REAL CODEX CERTIFICATION v25.49", "start_real_codex_cert_async", "start_real_codex_live_cert_async", "LIVE 1", "askyesno"]),
        "LAN Pool GUI exposes non-consuming preflight and explicit one-request live certification")
    add("v25_49.real_cert_validator_contract",
        all(x in real_codex_cert_validator for x in ["live_hard_cap_rejected", "live_requires_explicit_allow", "live_exact_text_delta_ttft", "topology_redacts_account", "login_does_not_mutate_auth"]),
        "synthetic validator covers cap/opt-in, TTFT event, redaction and auth immutability")
    add("v25_49.public_backend_contract_preserved",
        'public_backend_action_exact_90_preserved' in real_codex_cert and 'backend_action_added' in real_codex_cert,
        "real certification stays out of the frozen BackendAction surface")
    add("v25_49.unified_diagnostics_real_cert_surface",
        all(x in unified_diagnostics for x in ["real_codex_cert_events", "REAL_CODEX_CERT_RUN", '"real_codex_cert"', "real-codex-cert-latest-v2549.json"]),
        "Unified Diagnostics exposes metadata-only real-Codex certification state")
    add("v25_49.diagnostics_bundle_real_cert_privacy",
        all(x in diagnostics_bundle for x in ["real-codex-cert-latest-v2549.json", "REAL_CODEX_CERT_VALIDATION_V25.49.json", "BUILD_VALIDATION_V25.49.txt", "prompt|request_body|response|response_body"]),
        "Diagnostics bundle includes v25.49 certification evidence while defensively redacting prompt/request/response bodies")

    add("v25_50.live_quota_last_good_freshness",
        all(x in live_quota for x in ["last_success_utc", "QUOTA_STALE", "QUOTA_FRESHNESS_UNKNOWN", "failed_refresh_must_not_advance_last_success"]),
        "v25.50 uses last-success freshness and fail-closed stale/unknown gates for new sessions")
    add("v25_50.plan_reserve_policy",
        all(x in live_quota for x in ['"FREE": 25.0', '"PLUS": 15.0', '"PRO": 10.0', 'PLAN_RESERVE_HELD', 'NEAR_PLAN_RESERVE']),
        "v25.50 applies explicit plan-specific reserve floors with a release margin")
    add("v25_50.native_quota_cache_preserves_last_good",
        all(x in main for x in ["preserve the last known-good quota", "lastSuccessUtc=$nowUtc", "lastAttemptUtc=$attemptUtc", 'errorCode="QUOTA_REFRESH_FAILED"']),
        "failed live refresh attempts do not overwrite the last known-good quota timestamp/value")
    add("v25_50.native_account_surface",
        all(x in main for x in ["freshness_state=[string]$liveQuota.freshnessState", "reserve_pct=[double]$liveQuota.reservePct", "routing_eligible=[bool]$liveQuota.routingEligible"]),
        "Account Center publishes freshness/reserve/routing eligibility metadata without raw auth data")
    add("v25_50.adaptive_router_fail_closed",
        all(x in adaptive_router for x in ["live_quota_gate", "LIVE_QUOTA_FAIL_CLOSED", "stale_quota_never_promotes_new_session", "session_affinity_untouched"]),
        "Adaptive Router treats live quota eligibility as authoritative for new-session ranking")
    add("v25_50.closed_loop_fail_closed",
        all(x in closed_loop for x in ["live_quota_flag", "LIVE_QUOTA_FAIL_CLOSED", "Existing session affinity", "quota_freshness"]),
        "Closed-loop Router also rejects stale/blocked quota candidates for new sessions")
    add("v25_50.gui_live_quota_surface",
        ("Live Quota v25.50" in native_gui or "Usage & Token Center v25.61" in native_gui) and all(x in native_gui for x in ["LIVE {fresh} · RESERVE", "freshness_state", "routing_eligible", "HOLD NEW SESSION"]),
        "Account Center still shows freshness, plan reserve, usable quota and fail-closed routing state")
    add("v25_50.validator_contract",
        all(x in live_quota_validator for x in ["stale_fail_closed", "reserve_blocks_new_session", "adaptive_stale_ineligible", "last_refresh_failure_not_auto_block_if_last_good_fresh"]),
        "v25.50 validator covers stale, reserve, router integration and last-good refresh behavior")

    add("v25_51.active_ineligible_rotation_fix",
        all(x in adaptive_router for x in ["REAL active account", "ineligible_active_account_rotates_new_sessions", "CURRENT_CRITICAL_OVERRIDE"]),
        "Adaptive Router keeps the actual active account visible and rotates NEW sessions when it becomes ineligible")
    add("v25_51.closed_loop_current_fix",
        'POLICY_VERSION = "25.51"' in closed_loop and "ineligible_current_rotates_new_sessions" in closed_loop,
        "Closed-loop preserves real preferred account even when live quota/circuit makes it ineligible")
    add("v25_51.gateway_affinity_authoritative",
        all(x in smart_gateway for x in ["affinity is authoritative across ALL currently eligible targets", "all_rows=self.all_eligible", 'return t,"AFFINITY"']),
        "Recovered higher-priority targets do not pull an existing sticky session back")
    add("v25_51.torture_scenarios",
        all(x in rotation_torture for x in ["scenario_active_becomes_ineligible", "scenario_hysteresis_no_ping_pong", "scenario_gateway_429_affinity", "scenario_auth_isolation", "scenario_two_instance_rotation", "scenario_lan_rejoin"]),
        "torture harness covers quota depletion, hysteresis, 429, auth isolation, 2+ instances and LAN lease rejoin")
    add("v25_51.auth_cross_bleed_guard",
        all(x in rotation_torture for x in ["immutable_auth_fingerprint", "cross_bleed_absent", "report_contains_raw_credential"]),
        "routing-only mutation is checked against immutable auth fingerprints and cross-account secret placement")
    add("v25_51.lan_epoch_guard",
        all(x in rotation_torture for x in ["TAKEOVER_EXPIRED", "BLOCKED_OWNED_BY_OTHER_NODE", "takeover_epoch"]),
        "expired owner can fail over by epoch but a rejoined stale owner cannot steal the active lease")
    add("v25_51.validator_1000_cycles",
        all(x in rotation_torture_validator for x in ["cycles=1000", "gateway_recovered_existing_is_affinity", "multi_instances_all_recommend_beta", "lan_takeover_epoch_exact_2"]),
        "release validator executes 1000-cycle torture and asserts sticky recovery/multi-instance/LAN invariants")
    add("v25_51.gui_torture_surface",
        all(x in native_gui for x in ["ROTATION TORTURE v25.51", "ROTATION TEST", "start_rotation_torture_async", "synthetic 1000 cycle"]),
        "LAN Pool GUI exposes an explicit non-quota-consuming 1000-cycle torture action")
    add("v25_51.public_contract_unchanged",
        "HMS_Codex_SeamlessRotationTorture.py" not in main and "rotation_torture" not in main,
        "v25.51 torture is an internal/local validation surface and adds no frozen BackendAction")

    add("v25_52.native_operator_pulse",
        all(x in native_gui for x in ["Operator Pulse · ROUTE OK", "ROUTE OK","HOLD","STALE","FAVORITE", "ACTIVE ROUTE {active}", "WHY HOLD:"]),
        "native Account Center presents route eligibility/freshness/active-route decisions without another mutation backend")
    add("v25_52.native_account_filters",
        all(x in native_gui for x in ["def _filtered_account_items(self):", 'values=["TẤT CẢ","ROUTE OK","HOLD","STALE","FAVORITE"]', "HOLD NEW SESSION"]),
        "account list can be filtered locally by operational state and favorites")
    add("v25_52.snapshot_decision_fields",
        all(x in main for x in ["route_eligible=[int]$routeEligible", "active_route_eligible=", "quota_routing=$quotaRoute", "operator_attention=@($operatorAttention.ToArray())", "ACTIVE_ROUTE_HOLD"]),
        "PowerShell publishes metadata-only route/hold/stale decision state to both native and web UX")
    add("v25_52.unified_web_parity_plus",
        all(x in web for x in ["Unified UX v25.52", "Route eligible", "Stale quota", 'data-filter="ROUTE_OK"', "WHY HOLD:", "CẦN CHÚ Ý", "renderAccountGrid"]),
        "read-only local Unified UX exposes high-density account/quota/router decision state")
    add("v25_52.web_remains_read_only",
        all(x in web for x in ['("127.0.0.1",a.port)', "self.send_bytes(405", "read-only surface; use native HMS console"]),
        "browser dashboard remains loopback-only/read-only; mutation stays in native operator console")
    add("v25_52.validator_contract",
        all(x in ux_parity_validator for x in ["public_backend_contract_exact", "runtime_post_rejected_405", "gateway_affinity_invariant", "rotation_validator_forward_version_compatible"]),
        "UX validator checks public contract, runtime HTTP read-only behavior and v25.51 rotation invariants")

    add("v25_53.target_machine_seven_stage_gate",
        all(x in target_machine_cert for x in ["SAFE_STAGES", "host", "codex", "quota", "failover", "lan", "soak_6h", "soak_24h", "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"]),
        "v25.53 aggregates seven real target-machine stages and only emits production PASS when all are complete")
    add("v25_53.synthetic_never_production",
        all(x in target_machine_cert for x in ["Synthetic evidence never satisfies a production stage", "synthetic", "real_source_accounts", "different_account_proven"]),
        "synthetic quota/soak and unproven failover cannot satisfy production certification")
    add("v25_53.failover_restore_and_freshness",
        all(x in target_machine_cert for x in ["restored", "different", "failover_max_age_hours", "probe_http"]),
        "bounded failover evidence must be restored, recent, HTTP 200 and use a different account")
    add("v25_53.real_lan_two_node_gate",
        all(x in target_machine_cert for x in ["online >= 2", "nodes >= 2", "invalid == 0", "metadata_only_security", "shared_roundtrip"]),
        "target certification requires two signed online LAN nodes plus real shared filesystem roundtrip")
    add("v25_53.real_soak_duration_gate",
        all(x in target_machine_cert for x in ["6*3600", "24*3600", "coverage_complete", "ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED"]),
        "6h/24h production soak duration cannot be shortened and downtime is not counted")
    add("v25_53.operator_safety_surface",
        all(x in main for x in ["TARGET-MACHINE CERTIFICATION v25.53", "PREFLIGHT", "LIVE 1 CODEX", "FAILOVER 1", "SOAK CENTER", "Show-HmsTargetMachineCertificationCenter"]),
        "native Mission Control exposes one target-cert flow with explicit quota/failover actions")
    add("v25_53.no_public_backend_action",
        "target_machine" not in main.split("Add-Type -AssemblyName System.Windows.Forms")[0].lower(),
        "target-machine certification remains an internal/operator surface and does not extend the frozen 90-action backend")
    add("v25_53.validator_negative_contract",
        all(x in target_machine_validator for x in ["stale_quota_blocks_production", "single_lan_node_blocks", "failover_restore_failure_blocks", "synthetic_24h_never_certifies", "live_codex_request_required", "synthetic_quota_never_certifies", "soak_duration_cannot_be_shortened"]),
        "v25.53 validator explicitly proves weaker/synthetic evidence cannot create production PASS")

    add("v25_54.digital_twin_fault_lab",
        all(x in production_sim_lab for x in ["PRODUCTION_SIMULATION_FAULT_INJECTION_LAB", "EVENTS =", "run_seed", "deterministic_replay", "quota_state_space", "mutation_sensitivity"]),
        "v25.54 adds deterministic multi-seed digital-twin fault injection with replay and state-space checks")
    add("v25_54.fault_catalog",
        all(x in production_sim_lab for x in ["QUOTA_STALE", "HTTP_429", "PROCESS_CRASH", "AUTH_REFRESH", "QUEUE_BURST", "SMB_TRANSIENT", "LAN_PARTITION", "CLOCK_SKEW"]),
        "simulation catalog covers quota, 429, process, auth, backpressure, SMB, partition and clock-skew faults")
    add("v25_54.production_claim_boundary",
        "NOT_CLAIMED_SIMULATION_ONLY" in production_sim_lab and "never substitutes for target Windows/Codex/LAN/soak production certification" in production_sim_lab,
        "digital twin can never mint the target-machine production verdict")
    add("v25_54.validator_replay_mutation",
        all(x in production_sim_validator for x in ["same_seed_same_trace_hash", "different_seed_different_trace_hash", "mutation_detector_fires", "stale_matrix_has_no_escape"]),
        "validator proves deterministic replay and that an intentionally unsafe stale-quota mutant is detected")
    add("v25_54.gui_simulation_surface",
        all(x in native_gui for x in ["PRODUCTION SIMULATION LAB v25.54", "SIM LAB", "REPLAY", "start_production_simulation_async"]),
        "native LAN Pool exposes non-production simulation and deterministic replay without requiring a real machine")
    add("v25_54.public_contract_unchanged",
        "production_simulation" not in main.split("Add-Type -AssemblyName System.Windows.Forms")[0].lower(),
        "simulation lab is local/internal and does not extend the frozen BackendAction contract")

    add("v25_55.autonomous_router_large_pool",
        all(x in autonomous_router_twin for x in ["AUTONOMOUS_ROUTER_DIGITAL_TWIN_STATE_MODEL_CHECK", "dynamic_weight", "project_instance_affinity", "project_account_affinity", "fairness_summary"]),
        "v25.55 digital twin models dynamic weighted routing across accounts/instances/projects")
    add("v25_55.state_model_checker",
        all(x in autonomous_router_twin for x in ["def model_check", "states_checked", "sticky_nonhard", "hard_failover_eligible", "no_eligible_reject"]),
        "bounded checker exhaustively validates compact quota/health/instance/affinity state combinations")
    add("v25_55.trace_minimizer",
        all(x in autonomous_router_twin for x in ["def ddmin", "unsafe_ping_pong", "minimized_trace_hash", "A_FAIL", "A_RECOVER"]),
        "unsafe pull-back mutant is detected and minimized to a short deterministic replay trace")
    add("v25_55.adversarial_recovery_guard",
        all(x in autonomous_router_twin for x in ["account_recovery_pullback", "instance_recovery_pullback", "stale_high_quota_blocked"]),
        "recovery cannot snap existing sessions back and stale high-quota candidates remain blocked")
    add("v25_55.validator_contract",
        all(x in autonomous_router_validator for x in ["model_checker_3072_states", "no_account_recovery_pullback", "no_instance_recovery_pullback", "no_eligible_starvation", "trace_reduced_to_at_most_3"]),
        "release validator locks model-state count, affinity recovery, fairness and minimized counterexample behavior")
    add("v25_55.gui_twin_surface",
        all(x in native_gui for x in ["AUTONOMOUS ROUTER DIGITAL TWIN v25.55", "TWIN RUN", "MODEL CHECK", "start_autonomous_router_twin_async"]),
        "native LAN Pool exposes large-pool twin and bounded model-check actions")
    add("v25_55.production_claim_boundary",
        "NOT_CLAIMED_DIGITAL_TWIN_ONLY" in autonomous_router_twin and "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" not in autonomous_router_twin,
        "digital twin cannot mint target-machine production certification")

    add("v25_56.protocol_chaos_fuzzer",
        all(x in protocol_chaos for x in ["PROTOCOL_CHAOS_API_COMPATIBILITY_FUZZER", "structural_fuzz", "retry.sequence_503_429_200", "chunked.invalid_hex_400"]),
        "v25.56 deterministic protocol fuzzer covers SSE/WebSocket/JSON/chunked/retry paths")
    add("v25_56.sse_integrity_hardening",
        all(x in smart_gateway for x in ["class SSEIntegrityProbe", "TRUNCATED_EOF", "CONTENT_LENGTH_MISMATCH", "stream_terminal_seen", "UPSTREAM_EOF"]),
        "OpenAI SSE truncation and declared Content-Length mismatch become metadata-only upstream health failures")
    add("v25_56.websocket_upgrade_hardening",
        all(x in smart_gateway for x in ["validate_websocket_upgrade_head", "SEC_WEBSOCKET_ACCEPT_MISMATCH", "MALFORMED_UPGRADE"]),
        "malformed WebSocket 101 responses are rejected before relay and bounded failover continues")
    add("v25_56.no_midstream_replay",
        all(x in protocol_chaos for x in ["sse.no_midstream_replay", "retry.post_without_idempotency_not_replayed"]) and '"partial_stream_replay":"FORBIDDEN"' in protocol_chaos.replace(" ",""),
        "partial SSE streams are never replayed and POST replay remains idempotency-gated")
    add("v25_56.client_abort_not_upstream_failure",
        'error_source in ("CLIENT_WRITE","CLIENT_HEADER_WRITE")' in smart_gateway and 'error_source in ("UPSTREAM_READ","UPSTREAM_EOF")' in smart_gateway,
        "client disconnect remains distinguishable from upstream truncation for health accounting")
    add("v25_56.validator_contract",
        all(x in protocol_chaos_validator for x in ["fuzz_cases_300", "gateway_ws_101_validation", "gateway_body_length_integrity", "production_never_claimed"]),
        "release validator locks fuzz count, transport hardening and synthetic claim boundary")
    add("v25_56.gui_protocol_chaos_surface",
        all(x in native_gui for x in ["PROTOCOL CHAOS / API FUZZ v25.56", "FUZZ 300", "start_protocol_chaos_async"]),
        "native LAN Pool exposes protocol chaos fuzzing without adding a public backend action")
    add("v25_56.powershell_protocol_chaos_surface",
        all(x in main for x in ["PROTOCOL CHAOS / API FUZZ v25.56", "Show-HmsProtocolChaosCenter", "Invoke-HmsProtocolChaosFuzzer"]),
        "PowerShell operator surface mirrors the same synthetic-only protocol chaos gate")

    add("v25_57.recovery_planner",
        all(x in recovery_planner for x in ["RECOVERY_PLANNER_SELF_HEALING_DECISION_PROOF", "def decide", "ROTATE_NEW_SESSIONS_ONLY", "BOUNDED_RESTART", "FAIL_CLOSED_OPERATOR"]),
        "v25.57 adds cause-aware deterministic recovery planning instead of reflexive restart/rotation")
    add("v25_57.loop_breaker",
        all(x in recovery_planner for x in ["RECOVERY_LOOP_BREAKER", "OPEN_RECOVERY_CIRCUIT", "attempts_in_window >= 3", "OPERATOR_REQUIRED"]),
        "recovery loops open a bounded circuit after repeated attempts and escalate instead of thrashing")
    add("v25_57.rollback_proof",
        all(x in recovery_planner for x in ["REPAIR_CONFIG_ATOMIC", "RESTORE_CONFIG_BACKUP", "REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP", "config_mutation_requires_rollback"]),
        "config recovery is atomic/readback-verified and refuses mutation without rollback authority")
    add("v25_57.model_checker",
        all(x in recovery_planner for x in ["def model_check", "invariant_violations", "states_checked", "def ddmin", "counterexample_minimized_to_one_429"]),
        "bounded model checker proves no unowned restart, quota-triggered restart, unsafe lease takeover or recovery-loop escape")
    add("v25_57.session_affinity_safety",
        all(x in recovery_planner for x in ["existing_session_not_rotated_on_429", "existing_session_affinity_preserved_unless_hard_failure", "quota_fault_never_restarts_process"]),
        "quota/429 never tears down or rotates an already-running sticky session")
    add("v25_57.validator_contract",
        all(x in recovery_planner_validator for x in ["model_checker_at_least_6000_states", "critical_decision_contract", "zero_model_safety_violations", "production_never_claimed"]),
        "release validator locks the decision proof, bounded state count and synthetic-only claim boundary")
    add("v25_57.gui_recovery_surface",
        all(x in native_gui for x in ["RECOVERY PLANNER / SELF-HEALING PROOF v25.57", "PROOF", "MODEL CHECK", "start_recovery_planner_async"]),
        "native LAN Pool exposes recovery proof/model-check without extending public backend actions")
    add("v25_57.powershell_recovery_surface",
        all(x in main for x in ["RECOVERY PLANNER / SELF-HEALING PROOF v25.57", "Show-HmsRecoveryPlannerCenter", "Invoke-HmsRecoveryPlannerProof"]),
        "PowerShell operator surface mirrors the synthetic recovery proof")

    add("v25_58.compound_fault_dag",
        all(x in compound_fault_recovery for x in ["COMPOUND_FAULT_RECOVERY_CONVERGENCE_LAB", "def plan_compound", "dag", "acyclic", "_toposort"]),
        "compound-fault recovery is merged into an acyclic dependency DAG instead of independent reflex actions")
    add("v25_58.global_recovery_budget",
        all(x in compound_fault_recovery for x in ["GLOBAL_RECOVERY_BUDGET_EXHAUSTED", "ACTION_COST", "global_budget", "budget_used"]),
        "global recovery cost budget prevents restart/repair/retry storms across overlapping incidents")
    add("v25_58.convergence_model",
        all(x in compound_fault_recovery for x in ["def simulate_convergence", "HEALTHY", "DEGRADED_SAFE", "OPERATOR_REQUIRED", "round_count"]),
        "bounded convergence lab accepts only safe terminal outcomes and caps recovery rounds")
    add("v25_58.operator_dominance",
        all(x in compound_fault_recovery for x in ["hard_operator_dominates_auto_mutation", "HARD_OPERATOR", "QUARANTINE_SCOPE", "MUTATING_ACTIONS"]),
        "auth/identity/foreign ownership ambiguity dominates and blocks auto mutation")
    add("v25_58.compound_model_checker",
        all(x in compound_fault_recovery for x in ["states_checked", "violation_count", "terminal_distribution", "model_checker_zero_safety_violations"]),
        "pair/triple compound-fault state model checker proves safety and convergence")
    add("v25_58.validator_contract",
        all(x in compound_fault_validator for x in ["model_checker_at_least_70000_states", "critical_compound_contract", "global_budget_contract", "convergence_contract"]),
        "release validator locks 70k+ state coverage, DAG/budget/convergence semantics and synthetic claim boundary")
    add("v25_58.gui_compound_fault_surface",
        all(x in native_gui for x in ["COMPOUND-FAULT CONVERGENCE v25.58", "CONVERGENCE", "MODEL 72K", "start_compound_fault_recovery_async"]),
        "native LAN Pool exposes compound-fault proof/model checking without adding public backend actions")
    add("v25_58.powershell_compound_fault_surface",
        all(x in main for x in ["COMPOUND-FAULT CONVERGENCE v25.58", "Show-HmsCompoundFaultRecoveryCenter", "Invoke-HmsCompoundFaultRecovery"]),
        "PowerShell operator surface mirrors the synthetic compound-fault convergence lab")


    add("v25_59.official_auth_compat_layer",
        all(x in official_auth_compat for x in ["COCKPIT_V1327_ORIGINATOR = \"codex_vscode\"", "COCKPIT_V1324_ORIGINATOR = COCKPIT_V1327_ORIGINATOR", "OFFICIAL_AUTH_USER_AGENT_BASELINE = \"codex_vscode/0.146.0\"", "KEYRING_SERVICE = \"Codex Auth\"", "def switch_auth", "def rewrite_preserving_fields", "KEYRING_SECRETS_BACKEND_REQUIRES_OFFICIAL_CODEX_HELPER"]),
        "P0 compatibility layer locks Cockpit v1.3.27 credential-face compatibility and file/keyring/auto switch semantics")
    add("v25_59.auth_field_preservation",
        all(x in official_auth_compat for x in ["STALE_AUTH_KEYS", "normalize_target_auth", "OPENAI_API_KEY", "auth_mode", "type"]),
        "rewrite removes stale credential/account identity while preserving unrelated current auth fields")
    add("v25_59.auth_powershell_live_adapter",
        all(x in main for x in ["Get-HmsCodexOfficialAuthStoreMode", "Snapshot-HmsCodexOfficialAuthState", "Invoke-HmsCodexOfficialAuthSwitch", "AUTH_READBACK_FINGERPRINT_MISMATCH", "HMS_Codex_OfficialAuthSwitch_v1"]),
        "PowerShell live adapter snapshots, serializes, verifies readback and rolls back before controlled app restart")
    add("v25_59.official_oauth_identity",
        all(x in main for x in ["CodexOfficialOriginator = \"codex_vscode\"", "CodexOfficialAuthUserAgent = \"codex_vscode/0.146.0\""]) and "official_http_identity" in official_auth_compat,
        "OAuth login/refresh identity remains compatible under Cockpit v1.3.27 baseline")
    add("v25_59.validator_contract",
        all(x in official_auth_validator for x in ["snapshot_before_switch", "serialized_lock_waits", "readback_mismatch_rolls_back", "originator_v1327_compatible", "gui_surface"]),
        "release validator covers snapshot, serialization, rollback, version-derived OAuth identity, Secrets-backend fail-closed and native GUI wiring")
    add("v25_59.native_gui_surface",
        all(x in native_gui for x in ["OFFICIAL AUTH COMPAT v25.59", "AUTH AUDIT", "start_official_auth_compat_async"]),
        "native LAN Pool exposes P0 Official Auth Compatibility audit without adding public backend mutation actions")

    add("v25_60.recovery_journal_hash_chain",
        all(x in recovery_journal for x in ["PREPARE", "COMMIT", "VERIFY", "ROLLBACK", "DONE", "prev_hash", "record_hash", "os.fsync"]),
        "durable append-only hash-chain journal records recovery phases with fsync")
    add("v25_60.no_duplicate_commit_resume",
        all(x in recovery_journal for x in ["COMMIT_ALREADY_DURABLE", "VERIFY", "duplicate_commit_forbidden"]),
        "committed recovery resumes at VERIFY instead of repeating side effects")
    add("v25_60.journal_secret_redaction",
        all(x in recovery_journal for x in ["sanitize_meta", "<REDACTED>", "SENSITIVE_KEYS"]),
        "journal stores metadata/hash only and redacts secret-shaped values")
    add("v25_60.journal_validator_contract",
        all(x in recovery_journal_validator for x in ["crash_matrix_25_cases", "duplicate_commit_transition_blocked", "usage_reset_absolute_ui", "package_expiry_ui"]),
        "release validator locks crash matrix, duplicate-commit guard and Usage/Token reset UX")
    add("v25_60.auth_switch_journal_wiring",
        all(x in main for x in ["Invoke-HmsRecoveryJournalPhase", "OFFICIAL_AUTH_SWITCH", "RecoveryJournalPath", "recovery_txn_id"]),
        "Official Auth switch is journaled around PREPARE/COMMIT/VERIFY/DONE or ROLLBACK")
    add("v25_60.usage_reset_absolute",
        all(x in main for x in ["five_hour_reset_at_text", "weekly_reset_at_text", "Format-ResetAbsolute"]) and all(x in native_gui for x in ["Đặt lại sau", "Đặt lại lúc", "five_hour_reset_at_text", "weekly_reset_at_text"]),
        "Account Center shows reset countdown plus absolute local reset time")
    add("v25_60.package_expiry_optional",
        all(x in main for x in ["Get-HmsCodexPackageExpiry", "package_expiry_utc", "package_remaining_text", "NOT_EXPOSED"]) and all(x in native_gui for x in ["HẾT HẠN GÓI", "package_expiry_text", "package_remaining_text"]),
        "package expiry is shown only when upstream explicitly exposes it")
    add("v25_60.gui_recovery_journal_surface",
        all(x in native_gui for x in ["RECOVERY TRANSACTION JOURNAL v25.60", "RESUME AUDIT", "start_recovery_journal_proof_async", "start_recovery_journal_resume_async"]),
        "native LAN Pool exposes journal proof and crash-resume audit")

    # v25.61 Native Usage & Token Center Parity+ -- read-only/control-plane extension.
    add("v25_61.usage_token_center_contract",
        all(x in usage_token_center for x in ['VERSION = "25.61"','FIVE_HOUR','WEEKLY','MODEL_SPECIFIC','FREE','PLUS','PRO','TEAM_BUSINESS','ENTERPRISE','UNKNOWN']),
        "usage/token model exposes plan classes plus 5h, weekly and model-specific windows")
    add("v25_61.lifecycle_separation",
        all(x in usage_token_center for x in ['oauth_token_lifecycle','non_conflation','package']) and '"oauth_token": {' not in usage_token_center,
        "package expiry and OAuth/token lifecycle are structurally separate without credential-shaped token object")
    add("v25_61.reset_source_freshness",
        all(x in usage_token_center for x in ['countdown_text','absolute_utc_text','source','freshness_state']),
        "reset rows carry countdown, absolute UTC, source and freshness")
    add("v25_61.router_preview_scenario_only",
        all(x in usage_token_center for x in ['HYPOTHETICAL_POST_RESET_SCENARIO','SCENARIO ONLY','live_router_mutated": False','quota_mutated": False']),
        "AFTER RESET router preview is explicitly hypothetical and non-mutating")
    add("v25_61.history_replay",
        'os.fsync' in usage_token_center and all(x in usage_token_center for x in ['RESET_TIMESTAMP_CHANGED','RESET_REPLENISHMENT_OBSERVED','PACKAGE_EXPIRY_METADATA_CHANGED']),
        "metadata-only history is flushed durably and supports deterministic replay events")
    add("v25_61.validator_contract",
        all(x in usage_token_validator for x in ['package_token_non_conflation','preview_no_router_mutation','history_reset_timestamp_change']),
        "usage/token validator covers lifecycle non-conflation, non-mutation and reset history")
    add("v25_61.powershell_internal_wiring",
        all(x in main for x in ['Add-HmsUsageTokenCenterView','UsageTokenCenterHistoryPath','$result=Add-HmsUsageTokenCenterView $result $false','$result=Add-HmsUsageTokenCenterView $result $true']),
        "get_accounts and refresh_quota use an internal helper without expanding public BackendAction")
    add("v25_61.gui_usage_surface",
        all(x in native_gui for x in ['Usage & Token Center v25.61','ROUTER PREVIEW','SCENARIO ONLY','OAuth/token hết hạn','HẾT HẠN GÓI']),
        "native Account Center exposes usage/reset scenario and separate package/OAuth lifecycle labels")
    add("v25_61.unified_diagnostics_metadata_only",
        all(x in unified_diagnostics for x in ['usage_token_events','usage-token-center','usage-token-latest-v2561.json']) and all(x in unified_usage_validator for x in ['account_identity_not_projected','report_has_no_injected_secrets']),
        "unified diagnostics projects usage aggregates only and validator enforces identity/secret exclusion")
    add("v25_61.diagnostics_bearer_hardening",
        'usage-token-latest-v2561.json' in diagnostics_bundle and 'usage-token-history-v2561.jsonl' in diagnostics_bundle and 'bearer\\s+' in diagnostics_bundle.lower() and 'bearer_redacted' in diagnostics_v2561_validator,
        "diagnostics bundle includes v25.61 metadata artifacts and generic Bearer redaction proof")
    expected_actions=json.loads(public_contract).get('backend_actions') or []
    m_actions=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions=re.findall(r'"([^"]+)"',m_actions.group(1)) if m_actions else []
    add("v25_61.public_action_frozen", actual_actions==expected_actions and len(actual_actions)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions)})")

    # v25.62 Recovery Transaction Replay & Multi-Subsystem Crash Consistency.
    add("v25_62.cross_subsystem_effect_contract",
        all(x in recovery_replay for x in ['OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF']),
        "one replay plan spans auth rewrite, controlled restart, router transition and LAN lease handoff")
    add("v25_62.transaction_and_effect_identity",
        all(x in recovery_replay for x in ['intent_fingerprint','effect_fingerprint','txn_id']),
        "transaction intent and each durable effect have stable fingerprints")
    add("v25_62.idempotency_keys",
        all(x in recovery_replay for x in ['idempotency_key','idempotency_key_hash','IDEMPOTENT_NOOP']),
        "every side effect carries an idempotency key while journal stores only its hash")
    add("v25_62.external_verify_before_repeat",
        all(x in recovery_replay for x in ['OBSERVED_ALREADY_APPLIED_NO_REPEAT','VERIFY_ONLY_NO_REPEAT','AFTER_EFFECT_BEFORE_DURABLE']),
        "prepared/durable replay observes external state before deciding and never blindly repeats")
    add("v25_62.ownership_fail_closed",
        all(x in recovery_replay for x in ['CONCURRENT_EXTERNAL_CHANGE_OWNERSHIP_UNPROVEN','COMPENSATION_OWNERSHIP_UNPROVEN','OPERATOR_REQUIRED']),
        "concurrent change or unproven ownership fails closed")
    add("v25_62.compensation_dag",
        'for e in reversed(plan.effects)' in recovery_replay and 'depends_on' in recovery_replay and 'EFFECT_COMPENSATE' in recovery_replay,
        "compensation is reverse dependency order and ownership-gated")
    add("v25_62.convergence_states",
        all(x in recovery_replay for x in ['HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED']),
        "safe terminal convergence vocabulary is explicit")
    add("v25_62.crash_matrix_contract",
        all(x in recovery_replay for x in ['BEFORE_PREPARE','AFTER_PREPARE','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE','BEFORE_VERIFY','AFTER_VERIFY','CONCURRENT_CHANGE']),
        "crash matrix covers pre/post durable phases, dangerous unjournaled-effect window and concurrent changes")
    add("v25_62.validator_contract",
        all(x in recovery_replay_validator for x in ['danger_window_no_duplicate_auth','concurrent_change_operator_required','compensation_reverse_dependency_order','public_actions_still_90']),
        "release validator locks at-most-once, fail-closed compensation and public surface")
    add("v25_62.powershell_version_sync", '$script:Version = "25.74"' in main,
        "PowerShell runtime v25.64 carries forward v25.62 replay without adding BackendAction")
    add("v25_62.gui_replay_surface",
        all(x in native_gui for x in ['REPLAY v25.62','REPLAY PROOF','start_recovery_replay_proof_async','OPERATOR_REQUIRED']),
        "native LAN/recovery page exposes replay proof and convergence states")
    expected_actions62=json.loads(public_contract).get('backend_actions') or []
    m_actions62=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions62=re.findall(r'"([^"]+)"',m_actions62.group(1)) if m_actions62 else []
    add("v25_62.public_action_frozen",actual_actions62==expected_actions62 and len(actual_actions62)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions62)})")

    # v25.63 Startup Recovery Reconciler & OS-level cold-start crash harness.
    add("v25_63.startup_observer_contract",
        all(x in startup_recovery for x in ['OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF','TARGET_KEYRING_DIGEST_PROVIDER_REQUIRED']),
        "read-only observer adapters cover auth/process/router/LAN without reading keyring secrets")
    add("v25_63.startup_fail_closed",
        all(x in startup_recovery for x in ['JOURNAL_CHAIN_INVALID','CONCURRENT_EXTERNAL_CHANGE_OWNERSHIP_UNPROVEN','OPERATOR_REQUIRED','VERIFY_ONLY_NO_REPEAT']),
        "invalid chain, unknown ownership and durable mismatch fail closed")
    add("v25_63.startup_gate_atomic",
        all(x in startup_recovery for x in ['startup-recovery-gate-v2565.json','os.fsync','os.replace','block_conflicting_mutation']),
        "startup gate is atomic/durable and carries conflicting-mutation block")
    add("v25_63.powershell_direct_guard",
        all(x in main for x in ['Invoke-HmsStartupRecoveryPreflight $BackendAction','Invoke-HmsStartupRecoveryPreflight "__official_auth_switch__"','STARTUP_RECOVERY_BLOCKED']),
        "direct BackendAction/private Official Auth mutation cannot bypass startup preflight")
    add("v25_63.gui_startup_reconcile",
        all(x in native_gui for x in ['STARTUP RECOVERY v25.74','self.root.after(120, self.startup_recovery_reconcile_async)','LAB CRASH','OPERATOR_REQUIRED']),
        "native GUI automatically reconciles on startup and exposes operator state/crash lab")
    add("v25_63.crash_process_kill",
        all(x in target_crash_harness for x in ['subprocess.Popen','.kill()','cold_start_distinct_pid','AFTER_EFFECT_BEFORE_DURABLE']),
        "crash harness terminates a real subprocess and recovers in a distinct process")
    add("v25_63.crash_matrix_contract",
        all(x in target_crash_harness for x in ['AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY']) and 'EFFECTS = ("auth", "restart", "router", "lease")' in target_crash_harness,
        "3 crash windows x 4 subsystem effects are locked")
    add("v25_63.crash_no_fake_real_codex",
        'real_codex_effects_executed' in target_crash_harness and 'NOT_CLAIMED_OS_PROCESS_KILL_LAB_REAL_CODEX_EFFECTS_NOT_EXECUTED' in target_crash_harness,
        "OS crash proof does not claim real Codex side effects")
    add("v25_63.validator_contract",
        all(x in startup_recovery_validator for x in ['powershell_direct_backend_guard','powershell_private_auth_guard','public_actions_still_90']) and all(x in target_crash_validator for x in ['cold_start_distinct_pid','all_effects_exactly_once','nonwindows_does_not_fake_windows']),
        "v25.63 validators lock bypass resistance, at-most-once and target-evidence boundary")
    add("v25_63.unified_diagnostics_metadata_only",
        all(x in unified_startup_validator for x in ['startup_identity_not_projected','crash_case_details_not_projected','report_privacy']) and all(x in unified_diagnostics for x in ['startup_recovery_events','target_crash_harness_events']),
        "Unified Diagnostics exports only aggregate startup/crash metadata")
    add("v25_63.diagnostics_bundle_privacy",
        all(x in diagnostics_v2563_validator for x in ['access_token_redacted','bearer_redacted','prompt_redacted']) and 'startup-recovery-latest-v2563.json' in diagnostics_bundle,
        "diagnostics bundle includes v25.63 aggregates with secret redaction")
    add("v25_63.powershell_version_sync", '$script:Version = "25.74"' in main,
        "PowerShell runtime v25.64 carries forward v25.63 recovery semantics")
    expected_actions63=json.loads(public_contract).get('backend_actions') or []
    m_actions63=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions63=re.findall(r'"([^"]+)"',m_actions63.group(1)) if m_actions63 else []
    add("v25_63.public_action_frozen",actual_actions63==expected_actions63 and len(actual_actions63)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions63)})")

    # v25.64 Live Windows Recovery Observer Bridge & Real Codex Effect Crash Certification.
    add("v25_64.observer_evidence_contract",
        all(x in windows_observer for x in ['VERSION = "25.64"','WINDOWS_TARGET_OBSERVER','evidence_class','freshness_state','failure_reason']),
        "observer exposes evidence class, freshness and explicit failure reason for target recovery")
    add("v25_64.observer_secret_safe",
        all(x in windows_observer for x in ['--hms-digest-only','Get-Process -Name codex','command_line_collected": False','environment_collected": False','raw_account_identity": False','secret_read_attempted": False']),
        "observer uses digest-only keyring provider and does not collect command line/environment/account identity")
    add("v25_64.observer_validator_contract",
        all(x in windows_observer_validator for x in ['keyring_digest_only','process_generation_no_cmdline','production_boundary','ps_gate_v2564']),
        "observer validator locks privacy, target-boundary and frozen public surface")
    add("v25_64.real_effect_disarmed_default",
        all(x in real_effect_cert for x in ['REAL_CODEX_EFFECTS','ARM HMS REAL CODEX CRASH CERTIFICATION','HMS_REAL_EFFECT_CRASH_CERT','DEFERRED_NOT_ARMED']),
        "real-effect certification requires independent host, arm-token, operator, environment and adapter gates")
    add("v25_64.real_effect_idempotency_witness",
        all(x in real_effect_cert for x in ['applied_idempotency_key_hash','WITNESS_ALREADY_APPLIED_NO_REPEAT','DURABLE_WITHOUT_EXTERNAL_WITNESS']),
        "cold-start recovery probes a digest-only idempotency witness before any repeat")
    add("v25_64.real_effect_no_shell",
        all(x in real_effect_cert for x in ['SHELL_COMMAND_MODE_FORBIDDEN','def safe_argv','subprocess.run(argv','shell_command_mode_forbidden']),
        "adapter execution is argv-only and shell command modes are rejected")
    add("v25_64.real_effect_validator_contract",
        all(x in real_effect_validator for x in ['default_disarmed','preflight_not_armed','argv_no_shell','idempotency_witness','operator_required_fail_closed','score_not_automatic']),
        "real-effect validator locks multi-gate arming, witness semantics and public compatibility")
    add("v25_64.target_evidence_classes",
        all(x in target_evidence_bundle for x in ['LAB_PROCESS_KILL','LAB_FIXTURE','WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT','production_score_eligible']),
        "target evidence bundle keeps lab, observer and real-effect evidence classes distinct")
    add("v25_64.target_evidence_privacy",
        all(x in target_evidence_bundle for x in ['host_fingerprint','runtime_fingerprint','raw_credentials','raw_account_identity','raw_hostname','source_payloads_embedded']),
        "target evidence bundle fingerprints host/runtime and embeds aggregate metadata only")
    add("v25_64.target_evidence_validator_contract",
        all(x in target_evidence_validator for x in ['four_evidence_classes','host_runtime_hashed','source_payload_not_embedded','score_requires_attestation_gate','bundle_sha256']),
        "evidence validator locks no-score lab proof, metadata-only projection and bundle digest")
    add("v25_64.startup_bridge_integration",
        all(x in startup_recovery for x in ['WindowsTargetAdapterPack','startup-recovery-v2565','startup-recovery-gate-v2565.json']) and 'startup-recovery-v2565' in main,
        "startup reconciler and direct PowerShell mutation preflight use v25.64 observer-backed state")
    add("v25_64.gui_windows_recovery_surface",
        all(x in native_gui for x in ['WINDOWS TARGET ADAPTER PACK','WIN OBS','REAL CODEX EFFECT CRASH CERT','DISARMED DEFAULT','PREFLIGHT','LAB CRASH']),
        "native GUI exposes observer/preflight/lab surfaces while keeping real effects disarmed")
    add("v25_64.unified_diagnostics_metadata_only",
        all(x in unified_windows_validator for x in ['three_aggregate_events','identity_fields_blank','production_not_promoted']) and all(x in unified_diagnostics for x in ['windows_recovery_observer_events','real_effect_crash_cert_events','target_recovery_evidence_events']),
        "Unified Diagnostics exposes aggregate target-recovery evidence only")
    add("v25_64.diagnostics_bundle_privacy",
        all(x in diagnostics_v2564_validator for x in ['access_token_redacted','bearer_redacted','prompt_redacted','account_redacted','hostname_redacted','observer_latest_included','target_evidence_included']) and 'v2564' in diagnostics_bundle and 'windows-recovery-observer-latest-v2564.json' in diagnostics_bundle,
        "diagnostics bundle includes v25.64 artifacts while redacting secret and identity-shaped data")
    add("v25_64.powershell_version_sync", '$script:Version = "25.74"' in main,
        "PowerShell runtime reports v25.64")
    expected_actions64=json.loads(public_contract).get('backend_actions') or []
    m_actions64=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions64=re.findall(r'"([^"]+)"',m_actions64.group(1)) if m_actions64 else []
    add("v25_64.public_action_frozen",actual_actions64==expected_actions64 and len(actual_actions64)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions64)})")

    # v25.65 Windows Target Adapter Pack & Attested Evidence Promotion Gate.
    add("v25_65.adapter_pack_four_effects",
        all(x in windows_target_adapter for x in ['OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF','EXACT_STATE_HASH_AND_GENERATION']),
        "adapter pack covers exact auth/restart/router/lease probes and exact readback contract")
    add("v25_65.adapter_pack_secret_safe",
        all(x in windows_target_adapter for x in ['--hms-digest-only','raw_content_exported','command_line_collected','environment_collected','raw_owner_exposed']),
        "target adapters expose hashes/generation only and keep keyring/process/owner identity secret-safe")
    add("v25_65.adapter_manifest_disarmed",
        all(x in windows_target_adapter for x in ['disarmed_default','DIGEST_AND_IDEMPOTENCY_WITNESS_ONLY','SHELL_COMMAND_MODE_FORBIDDEN']),
        "generated adapter manifest is structured argv and disarmed by default")
    add("v25_65.adapter_validator_contract",
        all(x in windows_target_adapter_validator for x in ['manifest_disarmed','exact_readback_contract','no_shell_mode','production_boundary']),
        "adapter validator locks readback, no-shell and target-evidence boundary")
    add("v25_65.attestation_antireplay",
        all(x in attested_promotion for x in ['run_id','nonce','RUN_ID_REPLAY_OR_MISSING','NONCE_REPLAY_OR_INVALID','EVENT_HASH_MISMATCH','MIXED_PACKAGE_VERSION']),
        "promotion gate rejects replay, event-chain tamper and mixed package versions")
    add("v25_65.attestation_manifest_binding",
        all(x in attested_promotion for x in ['package_manifest_sha256','PACKAGE_MANIFEST_DIGEST_MISMATCH','verify_signed_attestation']),
        "attestation binds current package digest and requires trusted target signer class")
    add("v25_65.promotion_only_target_classes",
        "ELIGIBLE_CLASSES={'WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'}" in attested_promotion.replace(' ',''),
        "only live Windows observer and real Codex effect classes can enter promotion gate")
    add("v25_65.promotion_complete_matrix",
        all(x in attested_promotion for x in ['COMPLETE_4X3_CRASH_MATRIX_REQUIRED','REQUIRED_EFFECTS','REQUIRED_WINDOWS']),
        "real-effect evidence must contain complete 4x3 crash matrix")
    add("v25_65.no_direct_score_promotion",
        '"attestation_candidate":passed==len(cases),"production_score_eligible":False' in real_effect_cert.replace(' ', '') and "'production_score_eligible':False" in target_evidence_bundle.replace(' ',''),
        "real-effect run and target bundle can only become attestation candidates; neither directly promotes score")
    add("v25_65.promotion_validator_contract",
        all(x in attested_promotion_validator for x in ['nonce_run_id','manifest_binding','event_hash_chain','complete_4x3_matrix','separate_promotion_gate']),
        "promotion validator locks anti-replay and non-automatic certification")
    add("v25_65.timeline_vietnamese",
        all(x in recovery_timeline for x in ['CHUẨN BỊ','QUAN SÁT TRẠNG THÁI','ÁP DỤNG THAY ĐỔI','ĐÃ GHI BỀN','XÁC MINH','HOÀN TẤT','CẦN NGƯỜI VẬN HÀNH']),
        "operator recovery timeline provides complete Vietnamese phase vocabulary")
    add("v25_65.timeline_metadata_only",
        all(x in recovery_timeline for x in ['source','freshness','safe_fingerprint_prefix','remediation_reason','Bearer <REDACTED>']),
        "timeline exposes source/freshness/safe fingerprint prefix/remediation only")
    add("v25_65.timeline_validator_contract",
        all(x in recovery_timeline_validator for x in ['seven_phases','vietnamese_operator_required','no_identity_projection','bearer_redaction']),
        "timeline validator locks Vietnamese semantics and privacy")
    add("v25_65.gui_attested_surface",
        all(x in native_gui for x in ['ATTESTED TARGET EVIDENCE v25.74','ADAPTER','PROMOTION','TIMELINE','production auto-promotion=FALSE']),
        "native GUI exposes proof/preflight surfaces without an arming action")
    add("v25_65.unified_diagnostics_metadata_only",
        all(x in unified_attested_validator for x in ['three_sources','identity_not_projected','vi_timeline_exported','no_auto_promotion']) and all(x in unified_diagnostics for x in ['windows_target_adapter_events','attested_evidence_promotion_events','recovery_operator_timeline_events']),
        "Unified Diagnostics projects v25.65 adapter/promotion/timeline metadata only")
    add("v25_65.diagnostics_bundle_privacy",
        all(x in diagnostics_v2565_validator for x in ['access_redacted','bearer_redacted','account_redacted','hostname_redacted']) and 'startup-recovery-latest-v2565.json' in diagnostics_bundle and 'attested-evidence-promotion-latest-v2565.json' in diagnostics_bundle,
        "diagnostics bundle includes v25.65 evidence with secret/identity redaction")
    add("v25_65.startup_adapter_integration",
        all(x in startup_recovery for x in ['WindowsTargetAdapterPack','WINDOWS_TARGET_ADAPTER_PACK_V25.65','startup-recovery-v2565']) and 'startup-recovery-v2565' in main,
        "startup mutation gate prefers v25.65 target adapter pack")
    add("v25_65.powershell_gui_version_sync", '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui,
        "PowerShell and native GUI report v25.65")
    expected_actions65=json.loads(public_contract).get('backend_actions') or []
    m_actions65=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions65=re.findall(r'"([^"]+)"',m_actions65.group(1)) if m_actions65 else []
    add("v25_65.public_action_frozen",actual_actions65==expected_actions65 and len(actual_actions65)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions65)})")

    # v25.66 Live Windows Attestation Signer & Controlled Target Certification Runbook.
    add("v25_66.signer_crypto_binding",
        all(x in windows_attestation_signer for x in ['WINDOWS_LOCAL_MACHINE_DPAPI_HMAC','WINDOWS_CERTIFICATE_SIGNATURE','signed_payload_sha256','package_manifest_sha256','run_id','nonce']),
        "attestation signature binds exact package/run/nonce/evidence payload")
    add("v25_66.signer_private_material_local",
        all(x in windows_attestation_signer for x in ['CryptProtectData','private_material_exported','powershell.exe','shell=False']),
        "DPAPI/certificate signer keeps private material local and invokes PowerShell with structured argv")
    add("v25_66.signer_validator_contract",
        all(x in windows_attestation_signer_validator for x in ['proof_pass','proof_9','certificate_store_structured_argv','nonwindows_no_target_signing']),
        "signer validator proves tamper/trust/host boundary")
    add("v25_66.promotion_requires_crypto_signature",
        all(x in attested_promotion for x in ['verify_signed_attestation','SIGNATURE_','COMPLETE_4X3_CRASH_MATRIX_REQUIRED']),
        "promotion gate requires cryptographic signature plus full crash matrix")
    add("v25_66.runbook_one_shot_auto_disarm",
        all(x in target_cert_runbook for x in ['ONE_SHOT','os.O_EXCL','finally:','disarm_session','AUTO_DISARM','DEFERRED_TARGET_INTEGRATION_REQUIRED']),
        "target certification is one-shot and always auto-disarms")
    add("v25_66.runbook_operator_gates",
        all(x in target_cert_runbook for x in ['ARM_TOKEN','OPERATOR_PHRASE','ENV_GATE','windows_host','shell=False']),
        "runbook requires independent Windows/operator/env/arm gates and structured argv")
    add("v25_66.runbook_validator_contract",
        all(x in target_cert_runbook_validator for x in ['proof_pass','proof_10','auto_disarm_finally','one_shot_operator_gates']),
        "runbook validator locks auto-disarm even on failure")
    add("v25_66.exchange_privacy_integrity",
        all(x in attestation_exchange for x in ['BUNDLE_HASH_MISMATCH','PRIVACY_FORBIDDEN_FIELD','private_signing_material_exported','automatic_production_certification']),
        "evidence exchange hashes bundle and scrubs sensitive identity/signing data")
    add("v25_66.exchange_vietnamese_decision",
        all(x in attestation_exchange for x in ['CHƯA ĐỦ ĐIỀU KIỆN','Chứng thư ký không nằm trong danh sách tin cậy','4 effect × 3 crash window']),
        "promotion decision explanation is Vietnamese")
    add("v25_66.unified_diagnostics_metadata_only",
        all(x in unified_diagnostics for x in ['windows_attestation_signer_events','target_certification_runbook_events','attestation_exchange_events']) and all(x in unified_signed_validator for x in ['no_secret','metadata_only_no_execution']),
        "Unified Diagnostics projects signed-certification aggregate metadata only")
    add("v25_66.diagnostics_bundle_privacy",
        all(x in diagnostics_v2566_validator for x in ['access_redacted','bearer_redacted','private_redacted','v2566_artifacts_included']) and 'WINDOWS_ATTESTATION_SIGNER_VALIDATION_V25.66.json' in diagnostics_bundle,
        "Diagnostics Bundle includes v25.66 evidence with private/signing/identity redaction")
    add("v25_66.gui_signed_cert_surface",
        all(x in native_gui for x in ['SIGNED TARGET CERT v25.74','ONE-SHOT / AUTO-DISARM','SIGNER','RUNBOOK','EVIDENCE','REAL effect executed=FALSE']),
        "GUI exposes proof-only signer/runbook/evidence controls without arming target effects")
    add("v25_66.powershell_gui_version_sync", '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui,
        "PowerShell and native GUI report v25.66")
    expected_actions66=json.loads(public_contract).get('backend_actions') or []
    m_actions66=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions66=re.findall(r'"([^"]+)"',m_actions66.group(1)) if m_actions66 else []
    add("v25_66.public_action_frozen",actual_actions66==expected_actions66 and len(actual_actions66)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions66)})")

    # v25.67 Windows Attestation Trust Store & Resumable Target Certification Campaign.
    add("v25_67.trust_store_pin_rotation_revocation",
        all(x in attestation_trust_store for x in ['pin_certificate','rotate_certificate','revoke_certificate','CERTIFICATE_REVOKED','trust_snapshot_sha256']),
        "trust store pins certificates and tracks rotation/revocation with deterministic snapshot digest")
    add("v25_67.dpapi_key_lifecycle_metadata_only",
        all(x in attestation_trust_store for x in ['register_dpapi_key','sealed_blob_sha256','key_id_ref','private_material_exported']),
        "DPAPI lifecycle exports only sealed-blob digest and pseudonymous key reference")
    add("v25_67.trust_store_validator_contract",
        all(x in attestation_trust_store_validator for x in ['proof_9','rotation_revocation','dpapi_lifecycle_metadata','expiry_warning']),
        "trust store validator locks pin/rotate/revoke/expiry lifecycle")
    add("v25_67.offline_verifier_fail_closed",
        all(x in offline_attestation_verifier for x in ['TRUST_SNAPSHOT_DIGEST_MISMATCH','evaluate_certificate','DPAPI_LOCAL_MACHINE_CONTEXT_REQUIRED_FOR_OFFLINE_VERIFY','network_required']),
        "offline verifier binds trust snapshot and fails closed on revoked/DPAPI context")
    add("v25_67.offline_verifier_validator_contract",
        all(x in offline_attestation_verifier_validator for x in ['proof_7','trust_snapshot_binding','revocation_checked','offline_privacy']),
        "offline verifier validator locks package/trust/privacy checks")
    add("v25_67.campaign_4x3_resume_no_repeat",
        all(x in target_cert_campaign for x in ['DURABLE_UNVERIFIED','VERIFY_ONLY','SKIP_COMPLETE','OPERATOR_REQUIRED','silent_effect_repeat_allowed','automatic_rearm']),
        "campaign resume never silently repeats durable effects and never auto-rearms")
    add("v25_67.campaign_case_binding",
        all(x in target_cert_campaign for x in ['MANIFEST_DIGEST_MISMATCH','TRUST_SNAPSHOT_DIGEST_MISMATCH','ARM_TOKEN','OPERATOR_PHRASE','record_hash','prev_hash']),
        "every case binds manifest+trust snapshot and uses explicit one-shot arm plus hash-chain journal")
    add("v25_67.campaign_validator_contract",
        all(x in target_cert_campaign_validator for x in ['proof_13','resume_never_silent_repeat','per_case_arm','manifest_trust_binding','hash_chain']),
        "campaign validator locks 4x3 resumability semantics")
    add("v25_67.diagnostics_privacy",
        all(x in unified_trust_campaign_validator for x in ['trust_layer','offline_layer','campaign_layer','no_identity_or_secret']) and all(x in diagnostics_v2567_validator for x in ['cert_private_redacted','v2567_artifacts_included']),
        "Unified Diagnostics and Diagnostics Bundle project v25.67 aggregate metadata with private-material redaction")
    add("v25_67.gui_trust_campaign_surface",
        all(x in native_gui for x in ['TRUST STORE + CERT CAMPAIGN v25.74','RESUMABLE / NO SILENT REPEAT','TRUST','OFFLINE','CAMPAIGN','production auto-promotion=FALSE']),
        "GUI exposes proof-only trust/offline/campaign surfaces without target arm action")
    add("v25_67.powershell_gui_version_sync", '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui,
        "PowerShell and native GUI report current v25.69 while preserving v25.67 semantics")
    expected_actions67=json.loads(public_contract).get('backend_actions') or []
    m_actions67=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions67=re.findall(r'"([^"]+)"',m_actions67.group(1)) if m_actions67 else []
    add("v25_67.public_action_frozen",actual_actions67==expected_actions67 and len(actual_actions67)==90,
        f"public BackendAction remains exact contract set ({len(actual_actions67)})")

    # v25.68 Target Campaign Executor & Attested Promotion Review Console.
    add("v25_68.executor_one_case_only",
        all(x in target_campaign_executor for x in ['execute_one_case','automatic_next_case','automatic_rearm','EXPLICIT_EXECUTOR_ARM_REQUIRED']),
        "executor can execute only one explicitly armed case and never auto-advances")
    add("v25_68.executor_frozen_binding",
        all(x in target_campaign_executor for x in ['MIXED_PACKAGE_VERSION','MANIFEST_DIGEST_MISMATCH','TRUST_SNAPSHOT_DIGEST_MISMATCH']),
        "every target case binds frozen package manifest and trust snapshot")
    add("v25_68.executor_windows_preflight",
        all(x in target_campaign_executor for x in ['POWERSHELL_5_1_PARSER','POWERSHELL_5_1_RUNTIME','CODEX_PROCESS_OWNERSHIP','OFFICIAL_AUTH_OBSERVER','IDEMPOTENCY_WITNESS']),
        "executor requires Windows/PowerShell/Codex ownership/observer/idempotency preflight")
    add("v25_68.executor_auto_disarm_witness",
        all(x in target_campaign_executor for x in ['AUTO_DISARM','IDEMPOTENCY_WITNESS_MISMATCH','PASS_EFFECT_DURABLE_VERIFY_REQUIRED']),
        "case attempt auto-disarms and durable effect requires witness before verify-only recovery")
    add("v25_68.executor_structured_argv_lease_gate",
        all(x in target_campaign_executor for x in ['subprocess.run(argv','shell=False','LEASE_OWNERSHIP_READBACK_REQUIRED']),
        "target adapter uses structured argv and LAN lease remains separately ownership-gated")
    add("v25_68.executor_validator_contract",
        all(x in target_campaign_executor_validator for x in ['proof_12','one_case_only','frozen_manifest_trust_binding','windows_ps51_codex_preflight','lease_separate_gate']),
        "executor validator locks one-shot fail-closed semantics")
    add("v25_68.review_exact_12_crypto",
        all(x in promotion_review_console for x in ['EXACTLY_12_SIGNED_CASE_REPORTS_REQUIRED','COMPLETE_4X3_CRASH_MATRIX_REQUIRED','CRYPTOGRAPHIC_SIGNATURE_REQUIRED','WINDOWS_TARGET_OBSERVER_REQUIRED','REAL_CODEX_EFFECT_REQUIRED']),
        "promotion review requires exactly 12 signed real Windows/Codex reports")
    add("v25_68.review_trust_freshness",
        all(x in promotion_review_console for x in ['ATTESTATION_STALE','CERTIFICATE_REVOKED','CERTIFICATE_RETIRED_CURRENT_PROMOTION_REJECT','TRUST_SNAPSHOT_DIGEST_MISMATCH']),
        "review rejects stale/revoked/retired-current/mixed-trust evidence")
    add("v25_68.review_historical_rotation",
        all(x in promotion_review_console for x in ['historical_certificate_audit','historical_only','new_case_signing_allowed']),
        "retired certificates remain historically auditable but cannot sign new cases")
    add("v25_68.review_bundle_privacy_human_gate",
        all(x in promotion_review_console for x in ['OFFLINE_ATTESTED_PROMOTION_REVIEW','contains_account_identity','contains_credentials','contains_private_material','requires_human_review','automatic_production_certification']),
        "offline review bundle is privacy-safe and promotion remains human-reviewed")
    add("v25_68.diagnostics_metadata_only",
        all(x in unified_diagnostics for x in ['target_campaign_executor_events','attested_promotion_review_events']) and all(x in unified_campaign_review_validator for x in ['executor_layer','review_layer','no_identity_or_secret']) and all(x in diagnostics_v2568_validator for x in ['v2568_artifacts_included','cert_private_redacted']),
        "v25.68 executor/review evidence is projected metadata-only with privacy redaction")
    expected_actions68=json.loads(public_contract).get('backend_actions') or []
    m_actions68=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions68=re.findall(r'"([^"]+)"',m_actions68.group(1)) if m_actions68 else []
    add("v25_68.gui_version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['TARGET CAMPAIGN EXECUTOR + PROMOTION REVIEW v25.74','EXECUTOR','REVIEW','OFFLINE','auto-cert=FALSE']) and actual_actions68==expected_actions68 and len(actual_actions68)==90,
        f"GUI v25.68 proof-only surface; public BackendAction remains exact 90 ({len(actual_actions68)})")

    # v25.69 Windows Target Certification Evidence Ingest & Promotion Decision Ledger.
    add("v25_69.ingest_read_only_crypto_replay",
        all(x in target_evidence_ingest for x in ['read_only_ingest','target_effects_executed','RUN_ID_REPLAY_OR_MISSING','NONCE_REPLAY_OR_INVALID','REPORT_DIGEST_REPLAY','verify_signed_attestation']),
        "external target evidence ingest is read-only, cryptographically verified and anti-replay")
    add("v25_69.ingest_binding_quarantine",
        all(x in target_evidence_ingest for x in ['MIXED_PACKAGE_VERSION','MANIFEST_DIGEST_MISMATCH','TRUST_SNAPSHOT_DIGEST_MISMATCH','MIXED_CAMPAIGN_OWNERSHIP','quarantine']),
        "mixed package/trust/campaign evidence is quarantined without auto repair")
    add("v25_69.ingest_validator_contract",all(x in target_evidence_ingest_validator for x in ['proof_10','anti_replay','crypto_trust_required','quarantine','no_auto_promotion']),
        "v25.69 evidence ingest validator locks read-only trust/replay semantics")
    add("v25_69.ledger_hash_chain_dual_review",
        all(x in promotion_decision_ledger for x in ['prev_entry_sha256','entry_sha256','LEDGER_CONCURRENT_APPEND_DETECTED','DUAL_DISTINCT_REVIEW_REQUIRED','PROMOTION_ELIGIBLE_FOR_SEPARATE_SCORE_AUDIT']),
        "promotion decisions are append-only hash-chained and require two distinct reviewers")
    add("v25_69.ledger_supersede_no_delete",
        all(x in promotion_decision_ledger for x in ['INVALIDATE','supersedes_sha256','CERTIFICATE_REVOKED','PACKAGE_SUPERSEDED','TRUST_SNAPSHOT_CHANGED','historical_entries_deleted']),
        "revocation/trust/package changes require superseding entries; history is not deleted")
    add("v25_69.ledger_validator_contract",all(x in promotion_decision_ledger_validator for x in ['proof_11','optimistic_concurrency','dual_distinct_review','superseding_invalidation','eligibility_separate_from_score']),
        "decision ledger validator locks append-only dual-review semantics")
    add("v25_69.diagnostics_privacy",
        all(x in unified_diagnostics for x in ['target_certification_evidence_ingest_events','promotion_decision_ledger_events']) and all(x in unified_evidence_ledger_validator for x in ['ingest_layer','ledger_layer','no_raw_reviewer_or_secret']) and all(x in diagnostics_v2569_validator for x in ['v2569_artifacts_included','reviewer_redacted','private_redacted']),
        "v25.69 diagnostics project aggregate inbox/ledger metadata and redact reviewer/private identity")
    add("v25_69.gui_proof_only",
        all(x in native_gui for x in ['EVIDENCE INBOX + PROMOTION LEDGER v25.74','INGEST','LEDGER','INBOX','score-mutation=FALSE']) and all(x in evidence_inbox_gui_validator for x in ['no_backend_mutation_binding','real_effect_controls_still_preflight_lab']),
        "GUI v25.69 exposes proof-only ingest/ledger/inbox controls with no target arm binding")
    expected_actions69=json.loads(public_contract).get('backend_actions') or []
    m_actions69=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions69=re.findall(r'"([^"]+)"',m_actions69.group(1)) if m_actions69 else []
    add("v25_69.version_public_action_frozen",'$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and actual_actions69==expected_actions69 and len(actual_actions69)==90,
        f"v25.69 current version synchronized; public BackendAction remains exact 90 ({len(actual_actions69)})")
    add("v25_69.no_auto_score_mutation",all(x in promotion_decision_ledger for x in ['production_score_mutation_authorized','automatic_production_certification']) and all(x in target_evidence_ingest for x in ['production_score_promotion_eligible','automatic_production_certification']),
        "ingest and dual-review eligibility remain separate from production score mutation")

    # v25.70 Cockpit Tools v1.3.27 Codex-only parity reset.
    add("v25_70.cockpit_baseline_1327",
        all(x in cockpit1327_parity for x in ['COCKPIT_BASELINE = "1.3.27"','CLIENT_AUTH_API_SERVICE_SPLIT','API_PORT_CONFLICT_AUTO_RECOVERY','WINDOWS_STABLE_CLIENT_LIFECYCLE']),
        "competitive parity baseline is Cockpit Tools v1.3.27")
    add("v25_70.source_port_rebind_no_foreign_kill",
        all(x in main for x in ['CodexInstancePortAutoRecover = $true','function Repair-HmsCodexInstancePortConflict','INSTANCE_PORT_REBIND_RACE_DETECTED']) and 'Stop-Process' not in main[main.find('function Repair-HmsCodexInstancePortConflict'):main.find('function Invoke-HmsBoundedCredentialArchiveRetention')],
        "foreign port conflicts rebind before launch and never kill the foreign process")
    add("v25_70.runtime_account_occupancy",
        'Assert-HmsCodexAccountOccupancyBeforeLaunch $i' in main and 'ACCOUNT_OCCUPIED_BY_ACTIVE_INSTANCE' in main,
        "dedicated OAuth account occupancy is rechecked at launch time")
    add("v25_70.client_api_split",
        all(x in main for x in ['ClientAuthState','ApiServiceState','OverallAvailability','CLIENT_REAUTH_REQUIRED_API_CREDENTIAL_PRESENT']),
        "client authorization and API credential availability are separate states")
    add("v25_70.usage_official_account_continuity",
        all(x in usage_ledger for x in ['SCHEMA_VERSION = 3','official_account_ref','OFFICIAL_ACCOUNT_REF','official_account_id_raw_stored']),
        "usage ledger prefers pseudonymous official account refs across delete/re-add")
    add("v25_70.stream_identity_isolation",
        all(x in smart_gateway for x in ['CLIENT_PLUS_COMPOSITE_CONVERSATION_ID','return "sid-"+hashlib.sha256','conversation_id','thread_id']),
        "gateway affinity identity combines client and composite conversation/thread/request identity")
    add("v25_70.websocket_backup_model_metadata",
        all(x in main for x in ['CodexPreserveWebSocketPreference = $true','Invoke-HmsBoundedCredentialArchiveRetention']) and all(x in model_manager for x in ['context_window_tokens','auto_compact_token_limit','INVALID_COMPACTION_THRESHOLD_IGNORED']),
        "WebSocket preference, bounded backups and live model context/compaction metadata are preserved")
    add("v25_70.auth_export_security_gate",
        all(x in official_auth_export for x in ['OFFICIAL_AUTH_EXPORT_DISABLED_BY_DEFAULT','EXPORT OFFICIAL CODEX AUTH.JSON','diagnostics_export_allowed','router_only_fields_stripped']),
        "official auth.json export is manual, disabled by default and excluded from diagnostics")
    add("v25_70.parity_validators",
        all(x in cockpit1327_parity_validator for x in ['baseline_is_1_3_27','production_claim_not_promoted']) and all(x in cockpit1327_source_validator for x in ['PASS_COCKPIT_1327_SOURCE_INTEGRATION_V25_72','raw_official_account_id_not_persisted']),
        "reference parity and source integration validators are both present")
    expected_actions70=json.loads(public_contract).get('backend_actions') or []
    m_actions70=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions70=re.findall(r'"([^"]+)"',m_actions70.group(1)) if m_actions70 else []
    add("v25_70.gui_version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['COCKPIT TOOLS v1.3.27 PARITY RESET','PARITY','SOURCE','AUDITOR']) and actual_actions70==expected_actions70 and len(actual_actions70)==90,
        f"v25.70 parity surface is proof-only; public BackendAction remains exact 90 ({len(actual_actions70)})")

    # v25.71 Cockpit v1.3.27 Windows runtime certification + production evidence promotion auditor.
    add("v25_71.runtime_cert_seven_cases",
        all(x in cockpit1327_runtime_cert for x in ['FOREIGN_PORT_AUTO_REBIND','ACCOUNT_OCCUPANCY_GUARD','CLIENT_AUTH_API_SERVICE_SPLIT','OFFICIAL_ACCOUNT_USAGE_CONTINUITY','WEBSOCKET_PREFERENCE_PERSISTENCE','BOUNDED_BACKUP_ROLLBACK_NTFS','STREAM_IDENTITY_ISOLATION']),
        "runtime certification covers seven direct Cockpit v1.3.27 Codex parity deltas")
    add("v25_71.runtime_cert_real_windows_evidence_only",
        all(x in cockpit1327_runtime_cert for x in ['REAL_WINDOWS_TARGET','WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT','EXTERNAL_TARGET_IMPORT_REQUIRED','WINDOWS_HOST_NOT_VERIFIED']),
        "certification fails closed unless evidence comes from a verified external Windows/Codex target")
    add("v25_71.runtime_cert_privacy_idempotency",
        all(x in cockpit1327_runtime_cert for x in ['IDEMPOTENCY_WITNESS_NOT_VERIFIED','RAW_ACCOUNT_ID_EXPORTED','CREDENTIAL_PAYLOAD_EXPORTED']),
        "runtime reports require idempotency witness and forbid raw account/credential export")
    add("v25_71.promotion_auditor_human_only",
        all(x in production_promotion_auditor for x in ['ELIGIBLE_FOR_HUMAN_PRODUCTION_SCORE_REVIEW','proposed_score_mutation','automatic_production_certification','production_score_mutation_authorized']),
        "auditor may propose human review but never mutates production score")
    add("v25_71.promotion_auditor_invalidates_stale_baseline",
        all(x in production_promotion_auditor for x in ['COCKPIT_BASELINE_CHANGED_OR_STALE','DUAL_REVIEW_NOT_COMPLETE','WINDOWS_RUNTIME_CERTIFICATE_REQUIRED']),
        "new Cockpit baseline, missing Windows certificate or incomplete dual review invalidates proposal")
    add("v25_71.validators_and_diagnostics",
        all(x in cockpit1327_runtime_cert_validator for x in ['seven_runtime_cases','lab_never_certified','no_score_mutation_authority']) and all(x in production_promotion_auditor_validator for x in ['human_proposal_only','no_score_mutation_authority']) and all(x in unified_parity_runtime_validator for x in ['aggregate_metadata_only','no_raw_account_identity']) and all(x in cockpit1327_runtime_gui_validator for x in ['no_backend_mutation_binding','no_real_effect_arm_binding']),
        "v25.71 runtime cert/auditor/diagnostics/GUI validators lock the claim boundary")
    expected_actions71=json.loads(public_contract).get('backend_actions') or []
    m_actions71=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions71=re.findall(r'"([^"]+)"',m_actions71.group(1)) if m_actions71 else []
    add("v25_71.version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['COCKPIT v1.3.27 WINDOWS RUNTIME CERT','CERTIFY','AUDIT','EVIDENCE']) and actual_actions71==expected_actions71 and len(actual_actions71)==90,
        f"v25.71 proof/review surface; public BackendAction remains exact 90 ({len(actual_actions71)})")

    # v25.72 Windows target evidence capture kit + Cockpit baseline watch gate.
    add("v25_72.capture_exact_seven_cases",
        all(x in target_capture_kit for x in ['FOREIGN_PORT_AUTO_REBIND','ACCOUNT_OCCUPANCY_GUARD','CLIENT_AUTH_API_SERVICE_SPLIT','OFFICIAL_ACCOUNT_USAGE_CONTINUITY','WEBSOCKET_PREFERENCE_PERSISTENCE','BOUNDED_BACKUP_ROLLBACK_NTFS','STREAM_IDENTITY_ISOLATION']),
        "capture kit covers the same seven Cockpit v1.3.27 target runtime cases")
    add("v25_72.capture_disarmed_one_case_only",
        all(x in target_capture_kit for x in ["'default_state':'DISARMED'","'automatic_next_case':False","'automatic_rearm':False","HMS_Codex_TargetCampaignExecutor.py"]),
        "capture orchestration reuses the frozen one-case executor and stays DISARMED by default")
    add("v25_72.capture_exact_binding_privacy",
        all(x in target_capture_kit for x in ['PACKAGE_ZIP_SHA256_INVALID','MANIFEST_SHA256_INVALID','CODEX_VERSION_REQUIRED','raw_account_id_exported','credential_payload_exported','production_score_eligible']),
        "capture evidence binds exact ZIP/manifest/Codex metadata and exports no raw identity/credential payload")
    add("v25_72.baseline_watch_freezes_newer_upstream",
        all(x in cockpit_baseline_watch for x in ['STALE_BASELINE','UPSTREAM_COCKPIT_NEWER_THAN_CERTIFICATION_BASELINE','promotion_frozen','delta_audit_required','codex_only_scope']),
        "newer Cockpit baseline freezes promotion and requires a Codex-only delta audit")
    add("v25_72.validators_diagnostics_privacy",
        all(x in target_capture_kit_validator for x in ['seven_cases_exact','portable_kit_files','no_auto_score_or_cert']) and all(x in cockpit_baseline_watch_validator for x in ['newer_freezes_promotion','codex_only_scope']) and all(x in unified_target_capture_validator for x in ['aggregate_only','codex_baseline_visible']) and all(x in diagnostics_v2572_validator for x in ['v2572_artifacts_included','response_redacted']) and all(x in target_capture_gui_validator for x in ['no_backend_mutation_binding','no_real_effect_arm_binding']),
        "v25.72 validators lock portable capture, baseline watch, diagnostics privacy and GUI proof-only boundary")
    expected_actions72=json.loads(public_contract).get('backend_actions') or []
    m_actions72=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions72=re.findall(r'"([^"]+)"',m_actions72.group(1)) if m_actions72 else []
    add("v25_72.version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['WINDOWS TARGET EVIDENCE CAPTURE KIT','CAPTURE KIT','BASELINE','PRIVACY']) and actual_actions72==expected_actions72 and len(actual_actions72)==90,
        f"v25.72 capture/watch surface is proof-only; public BackendAction remains exact 90 ({len(actual_actions72)})")

    # v25.74 Windows target evidence import review + two-checkpoint baseline delta watch.
    add("v25_73.import_review_crypto_replay_dual_review",
        all(x in import_review for x in ['verify_signed_attestation','RUN_ID_REPLAY_OR_MISSING','NONCE_REPLAY_OR_INVALID','REPORT_DIGEST_REPLAY','evaluate_dual_review','WINDOWS_RUNTIME_CERTIFICATION_NOT_COMPLETE']),
        "import review requires crypto trust, replay guards, seven-case runtime certification and dual review")
    add("v25_73.import_review_read_only_claim_boundary",
        all(x in import_review for x in ["'read_only_import':True","'target_effects_executed_during_import':False","'production_score_mutation_authorized':False","'automatic_production_certification':False"]),
        "import path is read-only and cannot mutate score/certification")
    add("v25_73.two_checkpoint_baseline_watch",
        all(x in baseline_delta_watch for x in ['BEFORE_TARGET_IMPORT','BEFORE_PROMOTION_REVIEW','PROMOTION_FROZEN_BASELINE_STALE','PENDING_DELTA_AUDIT','automatic_upstream_merge']),
        "baseline watch requires import+review checkpoints and queues Codex-only delta audit without auto merge")
    add("v25_73.validators_diagnostics_privacy_gui",
        all(x in import_review_validator for x in ['cryptographic_verification_required','two_baseline_checkpoints_required','dual_review_ledger_reused']) and
        all(x in baseline_delta_watch_validator for x in ['newer_freezes','codex_only_delta_queue','no_auto_merge']) and
        all(x in unified_import_review_validator for x in ['aggregate_only_no_identity_or_secret','dual_review_visible']) and
        all(x in diagnostics_v2573_validator for x in ['v2573_artifacts_included','reviewer_redacted','response_redacted']) and
        all(x in import_review_gui_validator for x in ['no_backend_mutation','no_arm_or_executor_call']),
        "v25.74 validators lock import/baseline/diagnostics/privacy/GUI proof-only boundary")
    expected_actions73=json.loads(public_contract).get('backend_actions') or []
    m_actions73=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions73=re.findall(r'"([^"]+)"',m_actions73.group(1)) if m_actions73 else []
    add("v25_73.version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['WINDOWS EVIDENCE IMPORT REVIEW · HMS v25.74','IMPORT','DELTA WATCH','DIAGNOSTICS']) and actual_actions73==expected_actions73 and len(actual_actions73)==90,
        f"v25.74 import/review surface proof-only; public BackendAction remains exact 90 ({len(actual_actions73)})")

    # v25.74 immutable external Windows evidence review packet + baseline drift reconciliation.
    add("v25_74.review_packet_immutable_provenance",
        all(x in external_review_packet for x in ['IMMUTABLE_REFERENCED_BY_DIGEST_ONLY','verify_packet_chain','capability_binding_sha256','review_packet_export_safe']),
        "review packet references raw target evidence by digest only and adds packet/provenance hash binding")
    add("v25_74.review_packet_dual_review_privacy",
        all(x in external_review_packet for x in ['NON_PSEUDONYMOUS_REVIEWER_REF','dual_review_complete','production_score_mutation_authorized','FORBIDDEN_KEYS']),
        "review packet preserves pseudonymous dual-review metadata and privacy boundary")
    add("v25_74.baseline_drift_superseding_invalidation",
        all(x in baseline_drift_reconciliation for x in ["decision='INVALIDATE'",'supersedes_sha256','FROZEN_BASELINE_DRIFT','eligibility_invalidated']),
        "newer Cockpit baseline freezes packet and creates append-only superseding invalidation entries")
    add("v25_74.delta_reuse_requires_new_review_epoch",
        all(x in baseline_drift_reconciliation for x in ['prior_capability_binding_sha256','unchanged_capability_ids',"'silent_grandfathering':False","'new_dual_review_epoch_required':newer"]),
        "capability-compatible evidence may be reusable only after a new review epoch; no silent grandfathering")
    add("v25_74.validators_diagnostics_privacy_gui",
        all(x in external_review_packet_validator for x in ['raw_evidence_digest_only','packet_hash_chain_present','pseudonymous_reviewers_only']) and
        all(x in baseline_drift_reconciliation_validator for x in ['superseding_invalidation_entries','no_silent_grandfathering','no_auto_merge']) and
        all(x in unified_review_packet_validator for x in ['aggregate_only_no_identity_or_secret','invalidation_count_visible']) and
        all(x in diagnostics_v2574_validator for x in ['v2574_artifacts_included','reviewer_identity_redacted','response_redacted']) and
        all(x in external_review_packet_gui_validator for x in ['no_backend_mutation','no_arm_or_executor_call']),
        "v25.74 validators lock review-packet/reconciliation/diagnostics/privacy/GUI proof-only boundary")
    expected_actions74=json.loads(public_contract).get('backend_actions') or []
    m_actions74=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',main,re.S)
    actual_actions74=re.findall(r'"([^"]+)"',m_actions74.group(1)) if m_actions74 else []
    add("v25_74.version_public_action_frozen",
        '$script:Version = "25.74"' in main and 'APP_VERSION = "25.74"' in native_gui and all(x in native_gui for x in ['EXTERNAL WINDOWS EVIDENCE REVIEW PACKET · HMS v25.74','PACKET','RECONCILE','DIAGNOSTICS']) and actual_actions74==expected_actions74 and len(actual_actions74)==90,
        f"v25.74 review/reconcile surface proof-only; public BackendAction remains exact 90 ({len(actual_actions74)})")

    fail=sum(1 for x in tests if x["status"]=="FAIL")
    return {"version":"25.74","generated_utc":datetime.now(timezone.utc).isoformat(),
            "verdict":"PASS" if fail==0 else "FAIL","summary":{"pass":len(tests)-fail,"fail":fail,"total":len(tests)},"tests":tests}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--output")
    a=ap.parse_args()
    try:data=run(Path(a.root));out={"ok":data["verdict"]=="PASS","data":data}
    except Exception as e:out={"ok":False,"error":repr(e)}
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt)
    return 0 if out.get("ok") else 2
if __name__=="__main__":
    raise SystemExit(main())
