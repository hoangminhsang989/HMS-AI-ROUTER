#requires -version 5.1
param(
    [ValidateSet("ui","status","enable","disable","open_codex","get_settings","save_settings","get_accounts","refresh_quota","set_account_disabled","set_account_meta","add_codex","get_logs","get_service","create_client_key","set_request_log","restart_router","test_api","run_failover","maintenance_tick","get_usage","sync_usage","diagnostics_bundle","get_release","release_install","release_rollback","get_adaptive_router","evaluate_adaptive_router","apply_adaptive_router","rollback_adaptive_router","get_closed_loop_router","evaluate_closed_loop_router","apply_closed_loop_router","rollback_closed_loop_router","get_circuit_breaker","evaluate_circuit_breaker","apply_circuit_breaker","reset_circuit_breaker","get_predictive_quota","evaluate_predictive_quota","get_quota_center","sync_quota_center","get_account_analytics","sync_account_analytics","update_status","update_check","update_stage","update_activate","get_instances","create_instance","start_instance","stop_instance","restart_instance","focus_instance","audit_identity","get_project_affinity","save_project_affinity","launch_project_affinity","sync_project_router","get_model_manager","discover_models","save_model_policy","apply_model_policy","get_api_compatibility","run_api_compatibility","get_self_healing","audit_self_healing","repair_self_healing","get_security","audit_security","harden_security","seal_security","get_unified_diagnostics","refresh_unified_diagnostics","get_project_orchestrator","preflight_project_orchestrator","launch_project_orchestrator","get_multi_codex_team","save_multi_codex_team","preflight_multi_codex_team","launch_multi_codex_team","get_smart_model_router","evaluate_smart_model_router","apply_smart_model_router","rollback_smart_model_router","get_lan_pool","pair_lan_pool","heartbeat_lan_pool","acquire_lan_project","release_lan_project")]
    [string]$BackendAction="ui",
    [string]$BackendResultPath="",
    [string]$BackendInputPath="",
    [string]$OfficialAuthSwitchEmail="",
    [string]$OfficialAuthSwitchResultPath=""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Security

$ErrorActionPreference = "Stop"

# Windows Credential Manager helper for HMS protected current-user secrets.
if (-not ("HmsCredentialManager" -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public static class HmsCredentialManager {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL {
        public UInt32 Flags;
        public UInt32 Type;
        public string TargetName;
        public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public UInt32 CredentialBlobSize;
        public IntPtr CredentialBlob;
        public UInt32 Persist;
        public UInt32 AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    [DllImport("Advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredWrite(ref CREDENTIAL userCredential, UInt32 flags);

    [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, UInt32 type, UInt32 reservedFlag, out IntPtr credentialPtr);

    [DllImport("Advapi32.dll", EntryPoint = "CredDeleteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredDelete(string target, UInt32 type, UInt32 flags);

    [DllImport("Advapi32.dll", EntryPoint = "CredFree", SetLastError = true)]
    private static extern void CredFree(IntPtr buffer);

    public static void WriteGeneric(string target, string userName, string secret) {
        if (target == null) throw new ArgumentNullException("target");
        if (userName == null) userName = String.Empty;
        if (secret == null) secret = String.Empty;
        byte[] blob = Encoding.UTF8.GetBytes(secret);
        GCHandle handle = default(GCHandle);
        bool pinned = false;
        try {
            if (blob.Length > 0) { handle = GCHandle.Alloc(blob, GCHandleType.Pinned); pinned = true; }
            CREDENTIAL cred = new CREDENTIAL();
            cred.Type = 1; // CRED_TYPE_GENERIC
            cred.TargetName = target;
            cred.UserName = userName;
            cred.CredentialBlobSize = (UInt32)blob.Length;
            cred.CredentialBlob = blob.Length == 0 ? IntPtr.Zero : handle.AddrOfPinnedObject();
            cred.Persist = 2; // CRED_PERSIST_LOCAL_MACHINE
            if (!CredWrite(ref cred, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
        } finally {
            if (pinned) handle.Free();
        }
    }

    public static string ReadGeneric(string target, out string userName) {
        userName = null;
        IntPtr pcred;
        if (!CredRead(target, 1, 0, out pcred)) {
            int err = Marshal.GetLastWin32Error();
            if (err == 1168) return null; // ERROR_NOT_FOUND
            throw new Win32Exception(err);
        }
        try {
            CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(pcred, typeof(CREDENTIAL));
            userName = cred.UserName;
            if (cred.CredentialBlob == IntPtr.Zero || cred.CredentialBlobSize == 0) return String.Empty;
            byte[] bytes = new byte[(int)cred.CredentialBlobSize];
            Marshal.Copy(cred.CredentialBlob, bytes, 0, bytes.Length);
            return Encoding.UTF8.GetString(bytes);
        } finally {
            CredFree(pcred);
        }
    }

    public static void DeleteGeneric(string target) {
        if (String.IsNullOrWhiteSpace(target)) return;
        if (!CredDelete(target, 1, 0)) {
            int err = Marshal.GetLastWin32Error();
            if (err != 1168) throw new Win32Exception(err); // ERROR_NOT_FOUND is idempotent success.
        }
    }
}
'@
}


# ============================================================
# HMS-AI-ROUTER v25.66 WINDOWS TARGET ADAPTER PACK · ATTESTED EVIDENCE PROMOTION GATE
# Startup fail-closed gate runs before conflicting auth/router/process/LAN mutations.
# Cross-subsystem effect fingerprints/idempotency/ownership proof; synthetic-only, no production claim.
# HMS-AI-ROUTER v25.60 RECOVERY TRANSACTION JOURNAL · CRASH-CONSISTENT RESUME
# HMS-AI-ROUTER v25.57 RECOVERY PLANNER / SELF-HEALING DECISION PROOF
# Cause-aware bounded recovery, loop breaker, rollback proof and model checking; synthetic-only, no production claim.
# HMS-AI-ROUTER v25.56 PROTOCOL CHAOS / API COMPATIBILITY FUZZER
# Synthetic-only SSE/WebSocket/JSON/chunked/retry/EOF hardening; no production claim.
# HMS-AI-ROUTER v25.55 AUTONOMOUS ROUTER DIGITAL TWIN / MODEL CHECK
# - CLIProxyAPI
# - Codex custom provider in API-key mode
# - Codex OAuth pool
# - Cockpit-safe enable/disable
# - Graceful Codex/ChatGPT restart
# - Connection verification
# ============================================================

$script:Version = "25.74"
# Release manifest authority: RELEASE_MANIFEST_V25_59.json
$script:DataDir = Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter"
$script:SettingsPath = Join-Path $script:DataDir "settings-v2523_1.json"
$script:LegacySettingsPath = Join-Path $script:DataDir "settings-v2522.json"
$script:StatePath = Join-Path $script:DataDir "state-v2523_1.json"

$script:CodexDir = Join-Path $env:USERPROFILE ".codex"
$script:CodexConfig = Join-Path $script:CodexDir "config.toml"
$script:CodexEnv = Join-Path $script:CodexDir ".env"
$script:CodexQuotaCachePath = Join-Path $script:DataDir "codex-quota-cache-v1.json"
$script:CodexAccountMetaPath = Join-Path $script:DataDir "codex-account-meta-v1.json"
$script:CodexInstancesPath = Join-Path $script:DataDir "codex-instances-v1.json"
$script:CodexInstancesRoot = Join-Path $script:DataDir "codex-instances"
$script:CodexProjectAffinityPath = Join-Path $script:DataDir "codex-project-affinity-v2529.json"
$script:CodexProjectAffinityHistoryPath = Join-Path $script:DataDir "codex-project-affinity-history-v2529.jsonl"
$script:CodexSeamlessRouterHistoryPath = Join-Path $script:DataDir "codex-seamless-router-history-v2530.jsonl"
$script:CodexRouteHistoryPath = Join-Path $script:DataDir "codex-route-history.jsonl"
$script:CodexWakeupPath = Join-Path $script:DataDir "codex-wakeup-v1.json"
$script:CodexWakeupLogPath = Join-Path $script:DataDir "codex-wakeup-history.jsonl"
$script:CodexSessionDoctorState = Join-Path $script:DataDir "codex-session-doctor-v1.json"
$script:CodexAccountExportDir = Join-Path $script:DataDir "exports"
$script:CodexControlPlaneDir = Join-Path $script:DataDir "control-plane"
$script:CodexBackupsDir = Join-Path $script:DataDir "backups"
$script:CodexThreadSyncState = Join-Path $script:DataDir "codex-thread-sync-v2.json"
$script:CodexInstanceGuardPath = Join-Path $script:DataDir "instance-start-guards.json"
$script:CodexTelemetryPath = Join-Path $script:DataDir "codex-telemetry-latest.json"
$script:CodexConfigDoctorLog = Join-Path $script:DataDir "codex-config-doctor.jsonl"
$script:CodexFleetPolicyPath = Join-Path $script:DataDir "codex-fleet-policy-v3.json"
$script:CodexFleetHistoryPath = Join-Path $script:DataDir "codex-fleet-history.jsonl"
$script:CodexFleetExportDir = Join-Path $script:DataDir "fleet-exports"
$script:CodexSlaPath = Join-Path $script:DataDir "codex-sla-latest.json"
$script:CodexOpsDir = Join-Path $script:DataDir "operations"
$script:CodexOpsEventsPath = Join-Path $script:DataDir "codex-ops-events.jsonl"
$script:CodexQuotaHistoryPath = Join-Path $script:DataDir "codex-quota-history.jsonl"
$script:CodexIncidentPath = Join-Path $script:DataDir "codex-incidents.jsonl"
$script:CodexAttributionPath = Join-Path $script:DataDir "codex-attribution-latest.json"
$script:NativeGuiMaintenanceStatePath = Join-Path $script:DataDir "native-gui-maintenance-v2526.json"
$script:CodexRecoveryPolicyPath = Join-Path $script:DataDir "codex-recovery-policy-v4.json"
$script:CodexDiagnosticBundleDir = Join-Path $script:DataDir "diagnostic-bundles"
$script:UsageLedgerDir = Join-Path $script:DataDir "usage-ledger"
$script:UsageLedgerDbPath = Join-Path $script:UsageLedgerDir "usage-ledger-v2526.sqlite"
$script:UsageLedgerLatestPath = Join-Path $script:UsageLedgerDir "usage-ledger-latest-v2526.json"
$script:AdaptiveRouterDir = Join-Path $script:DataDir "adaptive-router"
$script:AdaptiveRouterStatePath = Join-Path $script:AdaptiveRouterDir "adaptive-router-state-v2527.json"
$script:AdaptiveRouterPlanPath = Join-Path $script:AdaptiveRouterDir "adaptive-router-plan-v2527.json"
$script:ClosedLoopRouterDir = Join-Path $script:DataDir "closed-loop-router"
$script:ClosedLoopRouterStatePath = Join-Path $script:ClosedLoopRouterDir "closed-loop-router-state-v2531.json"
$script:ClosedLoopRouterPlanPath = Join-Path $script:ClosedLoopRouterDir "closed-loop-router-plan-v2532.json"
$script:CircuitBreakerDir = Join-Path $script:DataDir "circuit-breaker"
$script:CircuitBreakerStatePath = Join-Path $script:CircuitBreakerDir "circuit-breaker-state-v2532.json"
$script:CircuitBreakerPlanPath = Join-Path $script:CircuitBreakerDir "circuit-breaker-plan-v2532.json"
$script:PredictiveQuotaDir = Join-Path $script:DataDir "predictive-quota"
$script:PredictiveQuotaStatePath = Join-Path $script:PredictiveQuotaDir "predictive-quota-state-v2533.json"
$script:PredictiveQuotaPlanPath = Join-Path $script:PredictiveQuotaDir "predictive-quota-plan-v2533.json"
$script:QuotaCenterDir = Join-Path $script:DataDir "quota-center"
$script:UsageTokenCenterDir = Join-Path $script:DataDir "usage-token-v2561"
$script:UsageTokenCenterLatestPath = Join-Path $script:UsageTokenCenterDir "usage-token-latest-v2561.json"
$script:UsageTokenCenterHistoryPath = Join-Path $script:UsageTokenCenterDir "usage-token-history-v2561.jsonl"
$script:QuotaCenterDbPath = Join-Path $script:QuotaCenterDir "quota-center-v2534.sqlite3"
$script:QuotaCenterStatePath = Join-Path $script:QuotaCenterDir "quota-center-state-v2534.json"
$script:QuotaCenterReportPath = Join-Path $script:QuotaCenterDir "quota-center-report-v2534.json"
$script:AccountAnalyticsDir = Join-Path $script:DataDir "account-analytics"
$script:AccountAnalyticsDbPath = Join-Path $script:AccountAnalyticsDir "account-analytics-v2535.sqlite3"
$script:AccountAnalyticsReportPath = Join-Path $script:AccountAnalyticsDir "account-analytics-report-v2535.json"
$script:CodexIdentityAuditPath = Join-Path $script:DataDir "codex-identity-audit-v2536.json"
$script:CodexIdentityHistoryPath = Join-Path $script:DataDir "codex-identity-audit-history-v2536.jsonl"
$script:ModelManagerDir = Join-Path $script:DataDir "model-manager"
$script:ModelManagerStatePath = Join-Path $script:ModelManagerDir "model-manager-state-v2537.json"
$script:ModelManagerPolicyPath = Join-Path $script:ModelManagerDir "model-policy-v2537.json"
$script:ApiCompatibilityDir = Join-Path $script:DataDir "api-compatibility"
$script:ApiCompatibilityLatestPath = Join-Path $script:ApiCompatibilityDir "api-compatibility-latest-v2538.json"
$script:ApiCompatibilityHistoryPath = Join-Path $script:ApiCompatibilityDir "api-compatibility-history-v2538.jsonl"
$script:SelfHealingDir = Join-Path $script:DataDir "self-healing"
$script:SelfHealingLatestPath = Join-Path $script:SelfHealingDir "self-healing-latest-v2539.json"
$script:SelfHealingHistoryPath = Join-Path $script:SelfHealingDir "self-healing-history-v2539.jsonl"
$script:SelfHealingEvidenceDir = Join-Path $script:SelfHealingDir "evidence"
$script:SecurityDir = Join-Path $script:DataDir "security"
$script:SecurityLatestPath = Join-Path $script:SecurityDir "security-latest-v2540.json"
$script:SecurityHistoryPath = Join-Path $script:SecurityDir "security-history-v2540.jsonl"
$script:SecurityEvidenceDir = Join-Path $script:SecurityDir "evidence"
$script:SecuritySealsPath = Join-Path $script:SecurityDir "integrity-seals-v2540.json"
$script:SecurityCredentialGlobalTarget = "HMS_AI_Cockpit:RouterKey:global:v25.40"
$script:SecurityCredentialSealTarget = "HMS_AI_Cockpit:IntegritySealKey:v25.40"
$script:UnifiedDiagnosticsDir = Join-Path $script:DataDir "unified-diagnostics"
$script:UnifiedDiagnosticsLatestPath = Join-Path $script:UnifiedDiagnosticsDir "unified-diagnostics-latest-v2541.json"
$script:UnifiedDiagnosticsHistoryPath = Join-Path $script:UnifiedDiagnosticsDir "unified-diagnostics-history-v2541.jsonl"
$script:ProjectOrchestratorDir = Join-Path $script:DataDir "project-orchestrator"
$script:ProjectOrchestratorLatestPath = Join-Path $script:ProjectOrchestratorDir "project-orchestrator-latest-v2542.json"
$script:ProjectOrchestratorHistoryPath = Join-Path $script:ProjectOrchestratorDir "project-orchestrator-history-v2542.jsonl"
$script:MultiCodexTeamDir = Join-Path $script:DataDir "multi-codex-team"
$script:MultiCodexTeamStorePath = Join-Path $script:MultiCodexTeamDir "multi-codex-team-v2543.json"
$script:MultiCodexTeamLatestPath = Join-Path $script:MultiCodexTeamDir "multi-codex-team-latest-v2543.json"
$script:MultiCodexTeamHistoryPath = Join-Path $script:MultiCodexTeamDir "multi-codex-team-history-v2543.jsonl"
$script:SmartModelRouterDir = Join-Path $script:DataDir "smart-model-router"
$script:SmartModelRouterStatePath = Join-Path $script:SmartModelRouterDir "smart-model-router-state-v2544.json"
$script:SmartModelRouterPlanPath = Join-Path $script:SmartModelRouterDir "smart-model-router-plan-v2544.json"
$script:SmartModelRouterHistoryPath = Join-Path $script:SmartModelRouterDir "smart-model-router-history-v2544.jsonl"
$script:LanPoolDir = Join-Path $script:DataDir "lan-pool"
$script:LanPoolNodeStatePath = Join-Path $script:LanPoolDir "local-node-v2545.json"
$script:LanPoolLatestPath = Join-Path $script:LanPoolDir "lan-pool-latest-v2545.json"
$script:LanPoolHistoryPath = Join-Path $script:LanPoolDir "lan-pool-history-v2545.jsonl"
$script:LanPoolCredentialTarget = "HMS_AI_Cockpit:LanPoolPairingKey:v25.45"
$script:TargetMachineCertDir = Join-Path $script:DataDir "target-machine-cert-v2553"
$script:TargetMachineCertLatestPath = Join-Path $script:TargetMachineCertDir "target-machine-cert-latest-v2553.json"
$script:TargetMachineRealCodexPath = Join-Path $script:TargetMachineCertDir "real-codex-live-v2549.json"
$script:ProductionSimulationDir = Join-Path $script:DataDir "production-simulation-v2554"
$script:ProductionSimulationLatestPath = Join-Path $script:ProductionSimulationDir "production-simulation-latest-v2554.json"
$script:ProductionSimulationReplayPath = Join-Path $script:ProductionSimulationDir "production-simulation-replay-v2554.json"
$script:AutonomousRouterTwinDir = Join-Path $script:DataDir "autonomous-router-twin-v2555"
$script:AutonomousRouterTwinLatestPath = Join-Path $script:AutonomousRouterTwinDir "autonomous-router-twin-latest-v2555.json"
$script:AutonomousRouterTwinModelPath = Join-Path $script:AutonomousRouterTwinDir "autonomous-router-model-check-v2555.json"
$script:ProtocolChaosDir = Join-Path $script:DataDir "protocol-chaos-v2556"
$script:ProtocolChaosLatestPath = Join-Path $script:ProtocolChaosDir "protocol-chaos-latest-v2556.json"
$script:RecoveryPlannerDir = Join-Path $script:DataDir "recovery-planner-v2557"
$script:RecoveryPlannerLatestPath = Join-Path $script:RecoveryPlannerDir "recovery-planner-latest-v2557.json"
$script:CompoundFaultRecoveryDir = Join-Path $script:DataDir "compound-fault-recovery-v2558"
$script:CompoundFaultRecoveryLatestPath = Join-Path $script:CompoundFaultRecoveryDir "compound-fault-recovery-latest-v2558.json"
$script:RecoveryJournalDir = Join-Path $script:DataDir "recovery-journal-v2560"
$script:RecoveryJournalPath = Join-Path $script:RecoveryJournalDir "recovery-transaction-journal-v2560.jsonl"
$script:RecoveryJournalLatestPath = Join-Path $script:RecoveryJournalDir "recovery-journal-latest-v2560.json"
$script:StartupRecoveryDir = Join-Path $script:DataDir "startup-recovery-v2565"
$script:StartupRecoveryGatePath = Join-Path $script:StartupRecoveryDir "startup-recovery-gate-v2565.json"
$script:StartupRecoveryLatestPath = Join-Path $script:StartupRecoveryDir "startup-recovery-latest-v2565.json"
$script:UpdateChannelStatePath = Join-Path $script:DataDir "update-channel-latest-v2527.json"
$script:UpdatePublicKeyPath = Join-Path $PSScriptRoot "HMS_UPDATE_PUBLIC_KEY.json"
$script:CodexAutopilotStatePath = Join-Path $script:DataDir "codex-autopilot-state-v5.json"
$script:CodexAutopilotHistoryPath = Join-Path $script:DataDir "codex-autopilot-history.jsonl"
$script:CodexRequestMetricsPath = Join-Path $script:DataDir "codex-request-metrics.jsonl"
$script:CodexQuotaForecastPath = Join-Path $script:DataDir "codex-quota-forecast.json"
$script:CodexReserveActivationPath = Join-Path $script:DataDir "codex-reserve-activation.jsonl"
$script:CodexHaDbPath = Join-Path $script:DataDir "codex-ha-v6.sqlite"
$script:CodexHaSnapshotPath = Join-Path $script:DataDir "codex-ha-snapshot-v6.json"
$script:CodexCorrelationPath = Join-Path $script:DataDir "codex-correlation-latest.json"
$script:CodexHaHistoryPath = Join-Path $script:DataDir "codex-ha-history.jsonl"
$script:CodexUnifiedSnapshotPath = Join-Path $script:DataDir "codex-unified-snapshot-v7.json"
$script:CodexWebDashboardDir = Join-Path $script:DataDir "web-dashboard"
$script:CodexWebDashboardStatePath = Join-Path $script:DataDir "web-dashboard-state-v7.json"
$script:ProductionDir = Join-Path $script:DataDir "production"
$script:RuntimeMarkerPath = Join-Path $script:ProductionDir "runtime-session-v8.json"
$script:LastCleanExitPath = Join-Path $script:ProductionDir "last-clean-exit-v8.json"
$script:StartupReportPath = Join-Path $script:ProductionDir "startup-report-v8.json"
$script:HealthCertificatePath = Join-Path $script:ProductionDir "health-certificate-v8.json"
$script:HealthCertificateTextPath = Join-Path $script:ProductionDir "health-certificate-v8.txt"
$script:ProductionArchiveDir = Join-Path $script:ProductionDir "archives"
$script:ProductionSelfTestPath = Join-Path $script:ProductionDir "self-test-v8.json"
$script:ReleaseManifestPath = Join-Path $PSScriptRoot "RELEASE_MANIFEST_V25_45.json"
$script:ReleaseEngineeringDir = Join-Path $script:DataDir "release-engineering"
$script:ReleasePreflightPath = Join-Path $script:ReleaseEngineeringDir "preflight-v9.json"
$script:ReleaseCertificatePath = Join-Path $script:ReleaseEngineeringDir "release-certificate-v9.json"
$script:ReleaseInstallStatePath = Join-Path $script:ReleaseEngineeringDir "install-state-v25_45.json"

# v10+ runtime path normalization (v17 authority)
$script:ValidationDir = Join-Path $script:DataDir "runtime-validation"
$script:ValidationCatalogPath = Join-Path $script:ValidationDir "validation-catalog-v10.json"
$script:ValidationStatePath = Join-Path $script:ValidationDir "validation-state-v10.json"
$script:ValidationLatestPath = Join-Path $script:ValidationDir "validation-latest-v10.json"
$script:ValidationHistoryPath = Join-Path $script:ValidationDir "validation-history-v10.jsonl"
$script:ValidationEvidenceDir = Join-Path $script:ValidationDir "evidence"
$script:ValidationReportDir = Join-Path $script:ValidationDir "reports"

$script:AccountOpsPath = Join-Path $script:DataDir "codex-account-ops-v11.json"
$script:AccountOpsHistoryPath = Join-Path $script:DataDir "codex-account-ops-history-v11.jsonl"
$script:SessionOpsPath = Join-Path $script:DataDir "codex-session-ops-v11.json"
$script:SessionOpsExportDir = Join-Path $script:DataDir "session-ops-exports"
$script:PoolMetadataExportDir = Join-Path $script:DataDir "pool-metadata-exports"

$script:RouterIntelPath = Join-Path $script:DataDir "codex-router-intelligence-v12.json"
$script:RouterIntelHistoryPath = Join-Path $script:DataDir "codex-router-intelligence-history-v12.jsonl"
$script:RouterIntelExportDir = Join-Path $script:DataDir "router-intelligence-exports"

$script:PoolReconcileDir = Join-Path $script:DataDir "pool-reconciliation"
$script:PoolReconcileSnapshotPath = Join-Path $script:PoolReconcileDir "pool-snapshot-v13.json"
$script:PoolReconcileLatestPath = Join-Path $script:PoolReconcileDir "reconcile-latest-v13.json"
$script:PoolReconcileHistoryPath = Join-Path $script:PoolReconcileDir "reconcile-history-v13.jsonl"
$script:PoolReconcileBackupDir = Join-Path $script:PoolReconcileDir "backups"

$script:SoakDir = Join-Path $script:DataDir "reliability-soak"
$script:SoakStatePath = Join-Path $script:SoakDir "soak-state-v14.json"
$script:SoakSamplesPath = Join-Path $script:SoakDir "soak-samples-v14.jsonl"
$script:SoakLatestAnalysisPath = Join-Path $script:SoakDir "soak-analysis-v14.json"
$script:SoakCertificatePath = Join-Path $script:SoakDir "soak-certificate-v14.json"
$script:SoakCertificateTextPath = Join-Path $script:SoakDir "soak-certificate-v14.txt"
$script:SoakArchiveDir = Join-Path $script:SoakDir "archives"

$script:PerformanceDir = Join-Path $script:DataDir "performance-analytics"
$script:PerformanceLatestPath = Join-Path $script:PerformanceDir "performance-latest-v15.json"
$script:PerformanceHistoryPath = Join-Path $script:PerformanceDir "performance-history-v15.jsonl"
$script:PerformanceReportDir = Join-Path $script:PerformanceDir "reports"
$script:PerformanceReportStatePath = Join-Path $script:PerformanceDir "report-state-v15.json"

$script:PolicyKernelDir = Join-Path $script:DataDir "policy-kernel"
$script:PolicyKernelStatePath = Join-Path $script:PolicyKernelDir "kernel-state-v16.json"
$script:PolicyKernelLatestPath = Join-Path $script:PolicyKernelDir "kernel-latest-v16.json"
$script:PolicyKernelHistoryPath = Join-Path $script:PolicyKernelDir "kernel-history-v16.jsonl"
$script:PolicyKernelActionHistoryPath = Join-Path $script:PolicyKernelDir "kernel-actions-v16.jsonl"
$script:PolicyKernelDecisionDir = Join-Path $script:PolicyKernelDir "decisions"

$script:UnifiedUxStatePath = Join-Path $script:DataDir "unified-ux-state-v17.json"
$script:UnifiedUxAuditPath = Join-Path $script:DataDir "unified-ux-audit-v17.jsonl"
$script:PowerShellAuditDir = Join-Path $script:DataDir "powershell-source-audit"
$script:PowerShellAuditLatestPath = Join-Path $script:PowerShellAuditDir "source-audit-v18.json"
$script:PowerShellAuditHistoryPath = Join-Path $script:PowerShellAuditDir "source-audit-history-v18.jsonl"
$script:WindowsGateDir = Join-Path $script:DataDir "windows-runtime-gates"
$script:WindowsGateLatestPath = Join-Path $script:WindowsGateDir "runtime-gate-latest-v19.json"
$script:WindowsGateHistoryPath = Join-Path $script:WindowsGateDir "runtime-gate-history-v19.jsonl"
$script:WindowsGateEvidenceDir = Join-Path $script:WindowsGateDir "evidence"
$script:SmartGatewayDir = Join-Path $script:DataDir "smart-gateway"
$script:SmartGatewayConfigPath = Join-Path $script:SmartGatewayDir "gateway-config-v20.json"
$script:SmartGatewayKeysPath = Join-Path $script:SmartGatewayDir "client-keys-v20.json"
$script:SmartGatewayTracePath = Join-Path $script:SmartGatewayDir "request-trace-v20.jsonl"
$script:SmartGatewayStatePath = Join-Path $script:SmartGatewayDir "gateway-state-v20.json"
$script:SmartGatewayPolicyExportDir = Join-Path $script:SmartGatewayDir "policy-exports"
$script:ProtocolValidationDir = Join-Path $script:SmartGatewayDir "protocol-validation"
$script:ProtocolValidationLatestPath = Join-Path $script:ProtocolValidationDir "protocol-latest-v21.json"
$script:ProtocolValidationHistoryPath = Join-Path $script:ProtocolValidationDir "protocol-history-v21.jsonl"
$script:ProxyAffinityDir = Join-Path $script:DataDir "proxy-affinity"
$script:ProxyProfilesPath = Join-Path $script:ProxyAffinityDir "proxy-profiles-v22.json"
$script:ProxyBindingsPath = Join-Path $script:ProxyAffinityDir "proxy-bindings-v22.json"
$script:ProxyHealthPath = Join-Path $script:ProxyAffinityDir "proxy-health-v22.json"
$script:ProxySecretsPath = Join-Path $script:ProxyAffinityDir "proxy-secrets-v22.json"
$script:ProxyAuditPath = Join-Path $script:ProxyAffinityDir "proxy-audit-v22.jsonl"
$script:ProxySidecarDir = Join-Path $script:ProxyAffinityDir "sidecars"
$script:ProxySidecarStatePath = Join-Path $script:ProxyAffinityDir "sidecar-state-v22.json"
$script:ProxyEgressPath = Join-Path $script:ProxyAffinityDir "egress-integrity-v23.json"
$script:ProxyFleetStatePath = Join-Path $script:ProxyAffinityDir "fleet-state-v23.json"
$script:ProxyFleetLatestPath = Join-Path $script:ProxyAffinityDir "fleet-latest-v23.json"
$script:ProxyFleetHistoryPath = Join-Path $script:ProxyAffinityDir "fleet-history-v23.jsonl"
$script:ProxyFleetActionHistoryPath = Join-Path $script:ProxyAffinityDir "fleet-actions-v23.jsonl"
$script:ProxyImportAuditPath = Join-Path $script:ProxyAffinityDir "proxy-import-v23.jsonl"
$script:ApiSupersetDir = Join-Path $script:DataDir "codex-api-superset"
$script:ApiAnalyticsLatestPath = Join-Path $script:ApiSupersetDir "analytics-latest-v24.json"
$script:ApiAnalyticsHistoryPath = Join-Path $script:ApiSupersetDir "analytics-history-v24.jsonl"
$script:ApiParityLatestPath = Join-Path $script:ApiSupersetDir "parity-latest-v24.json"
$script:ApiParityHistoryPath = Join-Path $script:ApiSupersetDir "parity-history-v24.jsonl"
$script:ApiPricingPath = Join-Path $script:ApiSupersetDir "model-pricing-v24.json"
$script:RuntimeCertDir = Join-Path $script:DataDir "runtime-certification-v25_23_1"
$script:RuntimeCertLatestPath = Join-Path $script:RuntimeCertDir "latest-v25_23_1.json"
$script:RuntimeCertHistoryPath = Join-Path $script:RuntimeCertDir "history-v25_23_1.jsonl"
$script:RuntimeCertSnapshotDir = Join-Path $script:RuntimeCertDir "snapshots"










$script:SafeStartupMode = $false
$script:ParallelInstanceDetected = $false
$script:RuntimeAutomationBlocked = $false








$script:AuthDir = Join-Path $env:USERPROFILE ".cli-proxy-api"

$script:SnapConfig = Join-Path $script:DataDir "before-router-config.toml"
$script:SnapConfigMissing = Join-Path $script:DataDir "before-router-config.missing"
$script:SnapEnv = Join-Path $script:DataDir "before-router-dotenv"
$script:SnapEnvMissing = Join-Path $script:DataDir "before-router-dotenv.missing"

$script:BridgeVsix = Join-Path $PSScriptRoot "bridge\HMS_Antigravity_Bridge_v0.7.1.vsix"
$script:BridgeStatusPath = Join-Path $script:DataDir "ag-bridge-server.json"
$script:BridgeSecretPath = Join-Path $script:DataDir "ag-bridge-secret.txt"
$script:AgCredentialBackup = Join-Path $script:DataDir "ag-credential-before-hms.bin"
$script:AgSwitchLog = Join-Path $script:DataDir "ag-switch-history.jsonl"

$script:Defaults = @{
    ProxyDir = "C:\CLIProxyAPI"
    ProxyPort = 8317
    LocalApiKey = ""
    RestoreOnDisable = $true
    RestartCodexOnSwitch = $true
    ForceCloseIfNeeded = $true
    OpenCodexOnEnable = $true
    OpenAntigravityOnEnable = $false
    AutoEnable = $false
    AgSeamlessEnabled = $false
    AgFallbackRestart = $false
    AgAutoSwitchEnabled = $false
    AgAutoSwitchThreshold = 10
    AgAutoSwitchIntervalSec = 30
    AgAutoSwitchCooldownSec = 120
    AgCurrentEmail = ""
    AgLastAutoSwitchUtc = ""
    AgCandidateMinQuota = 15
    AgMinScoreImprovement = 12
    AgRequireVerifiedReadback = $true
    AgWatchdogEnabled = $false
    AgSwitchHistoryMax = 200
    AgSeamlessHostOnly = $true
    AgRestartVerifySeconds = 18
    AgAutoRecoveryOnRestartFailure = $true

    # CODEX FIRST v0.8
    CodexRoutingProfile = "stable"
    CodexSessionAffinityTtl = "1h"
    CodexWatchdogEnabled = $true
    CodexWatchdogIntervalSec = 15
    CodexAutoRecoverRouter = $true
    CodexOptimizeMultiAgentV2 = $true
    CodexSaveCooldownStatus = $true
    CodexRequestRetry = 3
    CodexMaxRetryCredentials = 0
    CodexMaxRetryInterval = 12
    CodexShowAntigravityPanel = $false

    # v1.0 Codex Superset
    CodexQuotaDirectEnabled = $true
    CodexQuotaRefreshMinutes = 5
    # v25.50 Live Quota Intelligence: last-good + freshness TTL + plan reserve
    CodexQuotaFreshSeconds = 600
    CodexQuotaStaleSeconds = 1200
    CodexQuotaFailClosed = $true
    CodexQuotaReserveFreePct = 25
    CodexQuotaReservePlusPct = 15
    CodexQuotaReserveProPct = 10
    CodexQuotaReserveDefaultPct = 15
    CodexQuotaSwitchReleaseMarginPct = 5
    # v25.59 Official Auth Compatibility Layer (P0)
    CodexOfficialAuthStoreMode = "auto"
    CodexOfficialAuthKeyringEntry = "Codex Auth"
    CodexLaunchAfterAuthSwitch = $true
    CodexOfficialOriginator = "codex_vscode"
    CodexOfficialAuthUserAgent = "codex_vscode/0.146.0"
    # v25.70 Cockpit Tools v1.3.27 Codex-only parity reset (2026-08-23)
    CodexCockpitParityBaseline = "1.3.27"
    CodexInstancePortAutoRecover = $true
    CodexInstancePortAutoRecoverMaxScan = 64
    CodexBehaviorBackupKeepPerSourceInstance = 1
    CodexUsagePreferOfficialAccountId = $true
    CodexPreserveWebSocketPreference = $true
    CodexOfficialAuthExportEnabled = $false
    CodexModelContextMetadataEnabled = $true
    # v25.60 Crash-consistent recovery journal: metadata/hash only, no raw auth/prompt/body.
    RecoveryJournalEnabled = $true
    CodexTrayEnabled = $true
    CodexMinimizeToTray = $false
    CodexMissionControlAutoOpen = $false
    CodexInstanceBasePort = 8400
    CodexInstanceLaunchMode = "cli"
    CodexWakeupEnabled = $false
    CodexWakeupModel = ""
    CodexWakeupPrompt = "Reply exactly: HMS_OK"
    CodexWakeupMaxOutputTokens = 8
    CodexWakeupSchedulerEnabled = $false
    CodexWakeupSchedulerIntervalSec = 30
    CodexQuotaRefreshConcurrency = 5
    CodexSessionAuditEnabled = $true
    CodexSessionDoctorPython = "python"
    CodexAutoQuotaRefresh = $false
    CodexAutoQuotaRefreshMinutes = 10
    CodexThreadSyncEnabled = $false
    CodexThreadSyncOnAllIdle = $false
    CodexThreadSyncPython = "python"
    CodexInstanceRouterWatchdog = $true
    CodexTelemetryEnabled = $true
    CodexTelemetryIntervalSec = 5
    CodexConfigDoctorEnabled = $true
    CodexBackupRetention = 5
    CodexAutoSanitizeBeforeLaunch = $true
    CodexGuardTimeoutSec = 45
    # v25.28 Codex-only multi-instance isolation
    CodexOnlyEdition = $true
    CodexInstanceEnforceIsolation = $true
    CodexInstanceRequireUniqueProject = $true
    CodexInstanceRequireDedicatedAccount = $true
    CodexInstanceProjectRequired = $true
    CodexInstanceSyncCredentialOnStart = $true
    CodexInstanceDefaultLaunchMode = "cli"
    # v25.36 Codex identity isolation hardening
    CodexIdentityIsolationEnabled = $true
    CodexIdentityAuditBeforeLaunch = $true
    CodexIdentityFingerprintStrict = $true
    CodexIdentityRequirePathsUnderRoot = $true
    # v25.37 Codex Model & Reasoning Manager
    ModelManagerEnabled = $true
    ModelManagerAutoDiscover = $true
    ModelManagerRequireLiveModel = $true
    ModelManagerApplyBeforeLaunch = $true
    ModelManagerDefaultReasoning = "medium"
    ModelManagerDefaultProfile = "BALANCED"
    # v25.39 Codex Self-Healing (safe by default; never kill unowned processes)
    CodexSelfHealingEnabled = $true
    CodexSelfHealingAutoAudit = $true
    CodexSelfHealingAutoRepairSafe = $false
    CodexSelfHealingIntervalSec = 60
    CodexSelfHealingSafeRepairsOnly = $true
    CodexSelfHealingRepairGlobalConfig = $true
    CodexSelfHealingRepairInstanceConfig = $true
    CodexSelfHealingRepairBinding = $true
    CodexSelfHealingRepairCredentialPool = $true
    CodexSelfHealingRepairModelPolicy = $true
    # v25.40 Codex Security Hardening
    CodexSecurityHardeningEnabled = $true
    CodexSecurityCredentialManagerEnabled = $true
    CodexSecurityDpapiFallbackEnabled = $true
    CodexSecurityAclHardeningEnabled = $true
    CodexSecurityIntegritySealsEnabled = $true
    CodexSecurityBlockReparsePoints = $true
    CodexSecurityStrictRedaction = $true
    CodexSecurityAutoAudit = $true
    CodexSecurityIntervalSec = 120
    CodexSecurityMigratePlainKeys = $true
    CodexSecurityHardenInstancePaths = $true
    # v25.41 Unified Diagnostics
    UnifiedDiagnosticsEnabled = $true
    UnifiedDiagnosticsAutoRefresh = $true
    UnifiedDiagnosticsIntervalSec = 60
    UnifiedDiagnosticsMaxEvents = 600
    # v25.42 Project Orchestrator
    ProjectOrchestratorEnabled = $true
    ProjectOrchestratorRequireIdentity = $true
    ProjectOrchestratorRequireSecurity = $true
    ProjectOrchestratorVerifyOwnershipAfterLaunch = $true
    # v25.43 Multi-Codex Team
    MultiCodexTeamEnabled = $true
    MultiCodexTeamRequireDistinctWorkspace = $true
    MultiCodexTeamRequireDistinctAccount = $true
    MultiCodexTeamRequireSameGitRepository = $true
    MultiCodexTeamCoderMustMatchProject = $true
    MultiCodexTeamVerifyOwnershipAfterLaunch = $true
    MultiCodexTeamInjectRoleEnvironment = $true
    MultiCodexTeamMaxMembers = 3
    # v25.44 Smart Model Router (OBSERVE by default; no hot-switch of active sticky sessions)
    SmartModelRouterEnabled = $true
    SmartModelRouterMode = "OBSERVE"
    SmartModelRouterIntervalSec = 90
    SmartModelRouterApplyBeforeLaunch = $true
    SmartModelRouterRequireLiveModel = $true
    SmartModelRouterProtectRunningSessions = $true
    SmartModelRouterMinModelSamples = 3
    SmartModelRouterMinScoreDelta = 5
    SmartModelRouterMaxAccountAdjustment = 6
    SmartModelRouterCoderProfile = "BALANCED"
    SmartModelRouterReviewerProfile = "REVIEW"
    SmartModelRouterTesterProfile = "TEST"
    SmartModelRouterSoloProfile = "BALANCED"
    # v25.45 Cross-PC/LAN Codex Pool (disabled until a shared SMB/NAS path is paired)
    LanPoolEnabled = $false
    LanPoolSharedPath = ""
    LanPoolNodeName = ""
    LanPoolAutoHeartbeat = $true
    LanPoolHeartbeatIntervalSec = 15
    LanPoolLeaseTtlSec = 45
    LanPoolRequireSignedRegistry = $true
    LanPoolBlockCrossNodeProjectConflict = $true
    LanPoolFailoverEnabled = $true
    # v25.29 Project Affinity Engine
    CodexProjectAffinityEnabled = $true
    CodexProjectAutoRegisterInstances = $true
    CodexProjectBlockUnhealthyPrimary = $true
    CodexProjectFallbackMax = 3
    CodexProjectStickyMinutes = 180
    CodexProjectFocusIfRunning = $true
    # v25.30 Seamless Codex Router
    CodexSeamlessRouterEnabled = $true
    CodexSeamlessLivePoolSync = $true
    CodexSeamlessMaxFallback = 3
    CodexSeamlessMaxRetryCredentials = 3
    CodexSeamlessSessionAffinity = $true
    CodexSeamlessSessionTtlHours = 24
    CodexSeamlessArchiveStaleCredentials = $true
    CodexSeamlessRequireManifest = $true
    # v25.31 Closed-loop Router (supersedes legacy Adaptive background automation)
    ClosedLoopRouterEnabled = $true
    ClosedLoopRouterMode = "OBSERVE"
    ClosedLoopRouterIntervalSec = 45
    ClosedLoopRouterMinSamples = 5
    ClosedLoopRouterMinScoreDelta = 8
    ClosedLoopRouterHoldMinutes = 20
    ClosedLoopRouterCooldownSec = 120
    ClosedLoopRouterQuotaFloor = 10
    ClosedLoopRouterEmergencyQuota = 3
    ClosedLoopRouterPreferredWeight = 8
    ClosedLoopRouterSecondaryWeight = 3
    ClosedLoopRouterTailWeight = 1

    # v25.32 Circuit Breaker + Failover State Machine
    CircuitBreakerEnabled = $true
    CircuitBreakerMode = "OBSERVE"
    CircuitBreakerIntervalSec = 20
    CircuitBreakerConsecutiveFailures = 3
    CircuitBreakerRateLimitThreshold = 2
    CircuitBreakerAuthThreshold = 1
    CircuitBreakerServerThreshold = 3
    CircuitBreakerTimeoutThreshold = 2
    CircuitBreakerNetworkThreshold = 3
    CircuitBreakerBaseOpenSec = 120
    CircuitBreakerRateLimitOpenSec = 180
    CircuitBreakerAuthOpenSec = 900
    CircuitBreakerMaxOpenSec = 3600
    CircuitBreakerHalfOpenSuccesses = 1
    CircuitBreakerMaxBackoffExponent = 4
    CircuitBreakerHalfOpenProbePriority = 5

    # v25.34 Predictive Quota Engine (forecast is advisory; live quota remains authoritative)
    PredictiveQuotaEnabled = $true
    PredictiveQuotaIntervalSec = 60
    PredictiveQuotaHourlyLookbackHours = 8
    PredictiveQuotaWeeklyLookbackHours = 72
    PredictiveQuotaMinSpanMinutes = 20
    PredictiveQuotaResetJumpPct = 8
    PredictiveQuotaReserveTriggerPct = 15
    PredictiveQuotaEmergencyPct = 3
    PredictiveQuotaProactiveRunwayMinutes = 90
    PredictiveQuotaWarningRunwayMinutes = 240
    PredictiveQuotaResetGuardMinutes = 10
    PredictiveQuotaMaxScorePenalty = 42
    PredictiveQuotaMinLoadFactorPct = 10

    # v25.34 Advanced Quota Center (durable quota history + freshness + forecast accuracy)
    QuotaCenterEnabled = $true
    QuotaCenterIntervalSec = 60
    QuotaCenterRetentionDays = 45
    QuotaCenterForecastRetentionDays = 90
    QuotaCenterSnapshotMinIntervalSec = 300
    QuotaCenterChartHistoryHours = 168
    QuotaCenterChartMaxPoints = 72
    QuotaCenterFreshMinutes = 10
    QuotaCenterStaleMinutes = 30
    QuotaCenterAccuracyHorizonMinutes = 60
    QuotaCenterAccuracyToleranceMinutes = 35
    QuotaCenterPredictionMinIntervalMinutes = 15
    QuotaCenterAlertLowPct = 15
    QuotaCenterAlertCriticalPct = 5

    # v25.35 Account Analytics (normalized metadata only; bounded Router signal)
    AccountAnalyticsEnabled = $true
    AccountAnalyticsIntervalSec = 90
    AccountAnalyticsRetentionDays = 180
    AccountAnalyticsMinSamples = 5

    # v3.0 Fleet / Policy Engine
    CodexFleetEnabled = $false
    CodexFleetPolicy = "balanced"
    CodexFleetQuotaFloor = 15
    CodexFleetReserveCount = 1
    CodexFleetMaxInstancesPerAccount = 1
    CodexFleetPreferFavorite = $true
    CodexFleetAvoidCooldown = $true
    CodexFleetAutoRebalance = $false
    CodexFleetRebalanceIntervalSec = 60
    CodexFleetSlaWindowMinutes = 60
    CodexFleetAutoRecoverClients = $false

    # v4.0 Operations Center
    CodexOpsEnabled = $true
    CodexOpsScanIntervalSec = 5
    CodexAttributionWindowLines = 2500
    CodexQuotaHistoryEnabled = $true
    CodexQuotaHistoryMinIntervalMinutes = 5
    CodexRecoveryPolicy = "safe"
    CodexRecoveryCooldownSec = 60
    CodexIncidentRetention = 500
    CodexRedactedBundleMaxLogLines = 3000

    # v25.26 Durable Usage Ledger / Adaptive Advisory
    UsageLedgerEnabled = $true
    UsageLedgerSyncSec = 30
    UsageLedgerMaxTraceLines = 200000
    AdaptivePoolAdvisoryEnabled = $true
    # v25.27 Adaptive Router Policy (OBSERVE by default; GUARDED_AUTO is explicit)
    AdaptiveRouterEnabled = $true
    AdaptiveRouterMode = "OBSERVE"
    AdaptiveRouterIntervalSec = 60
    AdaptiveRouterMinSamples = 5
    AdaptiveRouterMinScoreDelta = 10
    AdaptiveRouterHoldMinutes = 30
    AdaptiveRouterCooldownSec = 180
    AdaptiveRouterQuotaFloor = 10
    AdaptiveRouterEmergencyQuota = 3
    AdaptiveRouterPreferredWeight = 8
    AdaptiveRouterSecondaryWeight = 3
    AdaptiveRouterReserveWeight = 1

    # v5.0 Autopilot / Predictive Operations
    CodexAutopilotEnabled = $false
    CodexAutopilotMode = "recommend"
    CodexAutopilotIntervalSec = 30
    CodexQuotaForecastHours = 6
    CodexQuotaCriticalPercent = 10
    CodexQuotaReserveTriggerPercent = 15
    CodexErrorRateCriticalPercent = 25
    CodexMinimumSamplesForAutomation = 5
    CodexReserveAutoActivation = $false
    CodexPredictiveFailover = $false
    CodexAutopilotCooldownSec = 120

    # v6.0 High Availability
    CodexHaEnabled = $true
    CodexHaIntervalSec = 10
    CodexCircuitOpenSeconds = 300
    CodexCircuitErrorRatePercent = 40
    CodexCircuitMinSamples = 5
    CodexCircuitMaxTransitionsPerHour = 6
    CodexCircuitHalfOpenSuccessSamples = 3
    CodexHaWindowMinutes = 30
    CodexHaIntegrateFleet = $true
    CodexHaAutoResetHealthy = $true

    # v7.0 Unified Command Center
    CodexUnifiedRefreshSec = 5
    CodexWebDashboardEnabled = $true
    CodexWebDashboardPort = 8765
    CodexWebDashboardAutoStart = $false
    CodexWebDashboardRefreshSec = 5
    CodexUnifiedShowTopology = $true
    CodexUnifiedShowAntigravity = $false

    # v8.0 Production Hardening
    ProductionSelfTestOnStartup = $true
    ProductionSafeStartupAfterCrash = $true
    ProductionHealthIntervalSec = 60
    ProductionArchiveMinAgeDays = 2
    ProductionArchiveKeepLatest = 3
    ProductionWarnParallelInstance = $true
    ProductionCertificateEnabled = $true

    # v9.0 Release Engineering
    ReleaseInstallRoot = ""
    ReleasePortablePreferred = $true
    ReleaseKeepRollbackVersions = 2
    ReleasePreflightOnStartup = $true
    ReleaseAllowWingetRepair = $false
    ReleaseCreateDesktopShortcut = $false
    ReleaseCreateStartMenuShortcut = $false
    # v25.27 Signed Update Channel. Never auto-activates a downloaded release.
    UpdateChannelEnabled = $false
    UpdateFeedUrl = ""
    UpdateChannelName = "stable"
    UpdateAutoCheckHours = 24
    UpdateAutoStage = $false
    # v10.0 Runtime Validation
    ValidationDefaultProfile = "SAFE_RUNTIME"
    ValidationAllowFullRuntime = $false
    ValidationEvidenceMaxLogLines = 2000
    ValidationAutoSaveEvidence = $true
    ValidationStopOnCriticalFailure = $true
    ValidationParallelism = 1
    ValidationRequireOperatorForDestructive = $true

    # v11.0 Account & Session Operations
    AccountOpsDefaultState = "ACTIVE"
    AccountOpsExcludeMaintenanceFromFleet = $true
    AccountOpsExcludeQuarantineFromFleet = $true
    AccountOpsHistoryRetention = 1000
    SessionOpsMaxRows = 500
    SessionOpsConfidenceWindowMinutes = 30
    SessionOpsIncludeArchived = $true
    PoolMetadataAutoBackup = $true

    # v12.0 Router Intelligence
    RouterIntelRecentWindowMinutes = 60
    RouterIntelMaxTimelineEvents = 500
    RouterIntelAutoRefreshSec = 5
    RouterIntelExportEnabled = $true
    RouterIntelShowEstimated = $true

    # v13.0 Pool Reconciliation
    PoolReconcileEnabled = $true
    PoolReconcileAutoAuditMinutes = 5
    PoolReconcileAllowAutoSync = $false
    PoolReconcileRequireStoppedInstance = $true
    PoolReconcileClockSkewSeconds = 2
    PoolReconcileSnapshotRetention = 20
    PoolReconcileConflictPolicy = "review"

    # v14.0 Reliability & Soak
    SoakEnabled = $true
    SoakSampleIntervalSec = 60
    SoakDefaultProfile = "QUICK_1H"
    SoakRouterOfflineCriticalSamples = 3
    SoakPoolReadyZeroCriticalSamples = 3
    SoakRecoveryLoopWindowMinutes = 15
    SoakRecoveryLoopCriticalCount = 8
    SoakRamGrowthWarnMbPerHour = 250
    SoakStateGrowthWarnMbPerHour = 50
    SoakMinSamplesPerHour = 30
    SoakAutoCertificate = $true

    # v15.0 Performance Analytics
    PerformanceEnabled = $true
    PerformanceWindowHours = 24
    PerformanceAutoRefreshSec = 30
    PerformanceMaxPoints = 720
    PerformanceAnomalyZ = 4.0
    PerformanceSlaDropWarn = 20
    PerformanceLatencyP95WarnMs = 5000
    PerformanceRamGrowthWarnMbPerHour = 250
    PerformanceHtmlAutoOpen = $false
    PerformanceHistoryMinIntervalMinutes = 5

    # v16.0 Policy Kernel
    PolicyKernelEnabled = $true
    PolicyKernelMode = "OBSERVE"
    PolicyKernelIntervalSec = 30
    PolicyKernelCooldownSec = 180
    PolicyKernelMaxActionsPerHour = 4
    PolicyKernelMaxRouterStartsPerHour = 2
    PolicyKernelHysteresisCycles = 2
    PolicyKernelSlaCritical = 50
    PolicyKernelSlaDegraded = 75
    PolicyKernelReadyCritical = 0
    PolicyKernelPerformanceWarnCycles = 2
    PolicyKernelAutoStartOwnedRouter = $true
    PolicyKernelAutoRunReadOnlyAudits = $true
    PolicyKernelAllowCredentialSync = $false
    PolicyKernelAllowRebind = $false
    PolicyKernelAllowProcessKill = $false
    PolicyKernelAllowDestructive = $false

    # v17.0 Unified UX
    UnifiedUxEnabled = $true
    UnifiedUxAutoStart = $false
    UnifiedUxPort = 8765
    UnifiedUxRefreshSec = 3
    UnifiedUxOpenBrowserOnStart = $true
    UnifiedUxDefaultSection = "overview"
    UnifiedUxShowAdvancedRaw = $true

    # v18.0 PowerShell Runtime Hardening
    PowerShellStaticAuditOnStartup = $true
    PowerShellStaticAuditBlockAutomation = $true
    PowerShellStaticAuditHistory = $true
    PowerShellStaticAuditRequireZeroGlue = $true

    # v19.0 Windows Runtime Gate Orchestrator
    WindowsRuntimeGateProfile = "PREFLIGHT"
    WindowsRuntimeGateOperatorMode = $false
    WindowsRuntimeGateUiSmokeSeconds = 8
    WindowsRuntimeGateHttpTimeoutSec = 5
    WindowsRuntimeGateEvidenceRetention = 20
    WindowsRuntimeGateRequirePs51 = $true
    WindowsRuntimeGateRequireSourceLint = $true
    WindowsRuntimeGateAllowRouterSmoke = $false
    WindowsRuntimeGateAllowUiSmoke = $false
    WindowsRuntimeGateAllowSafeRuntime = $false

    # v20.0 HMS Codex Smart Gateway
    SmartGatewayEnabled = $true
    SmartGatewayAutoStart = $false
    SmartGatewayHost = "127.0.0.1"
    SmartGatewayPort = 8320
    SmartGatewayStrategy = "stable-round-robin"
    SmartGatewaySessionAffinity = $true
    SmartGatewaySessionTtlSec = 3600
    SmartGatewayHealthFailThreshold = 3
    SmartGatewayHealthCooldownSec = 120
    SmartGatewayTraceRetentionLines = 50000
    SmartGatewayAllowWeighted = $true
    SmartGatewayAllowResetAware = $true
    SmartGatewayRequireClientKey = $true

    # v21.0 Codex Protocol & Streaming Superset
    SmartGatewayMaxFailoverAttempts = 3
    SmartGatewayRetryStatuses = "429,500,502,503,504"
    SmartGatewayRequireIdempotencyForPostReplay = $true
    SmartGatewayStreamChunkBytes = 65536
    SmartGatewayWebSocketEnabled = $true
    SmartGatewayWebSocketIdleTimeoutSec = 300
    SmartGatewayWebSocketRequireModelHint = $true
    SmartGatewayProtocolTrace = $true
    SmartGatewayExposeSelectedTargetHeaders = $true
    ProtocolValidationAutoSave = $true

    # v22.0 Proxy Affinity & Egress Control
    ProxyAffinityEnabled = $true
    ProxyAffinityMode = "STRICT"
    ProxyAccountsPerProxy = 5
    ProxySidecarBasePort = 8420
    ProxyHealthProbeHost = "api.openai.com"
    ProxyHealthProbePort = 443
    ProxyHealthTimeoutSec = 8
    ProxyHealthRequiredBeforeStart = $true
    ProxyAutoAssignPreserveExisting = $true
    ProxySidecarSessionAffinity = $true
    ProxySidecarSessionTtl = "1h"
    ProxySidecarStartOnDemand = $true
    ProxyDirectFallbackAllowed = $false
    ProxyPublicIpProbeEnabled = $false

    # v23.0 Proxy Fleet Supervisor & Egress Integrity
    ProxyEgressProbeEnabled = $true
    ProxyEgressProbeUrl = "https://api.ipify.org?format=json"
    ProxyEgressAutoLearnBaseline = $true
    ProxyEgressRequireStableIp = $true
    ProxyEgressRequireBeforeSidecarStart = $true
    ProxyEgressTimeoutSec = 10
    ProxyHealthMaxAgeSec = 300
    ProxyEgressMaxAgeSec = 300
    ProxyEgressDriftQuarantine = $true
    ProxyFleetAuditEnabled = $true
    ProxyFleetAuditIntervalSec = 60
    ProxyFleetAutoRecovery = $false
    ProxyFleetRecoveryCooldownSec = 300
    ProxyFleetMaxRestartsPerHour = 2
    ProxyFleetDrainGraceSec = 60
    ProxyFleetImportDefaultMode = "STRICT"
    ProxyFleetImportMaxAccounts = 5
    ProxyFleetQuarantineOnHealthFail = $true

    # v24.0 Codex API Superset & Parity Auditor
    ApiSupersetEnabled = $true
    ApiAnalyticsMaxTraceLines = 100000
    ApiAnalyticsRefreshSec = 30
    ApiQuotaEvidenceMaxAgeSec = 900
    ApiQuotaReserveFailClosed = $true
    ApiDefaultQuotaReservePct = 0
    ApiCorsEnabled = $true
    ApiCorsAllowLoopbackOnly = $true
    ApiUsageCaptureMaxBytes = 2097152
    ApiParityBaseline = "Cockpit-current-main-v1.3.16-era"
    ApiParityAutoAudit = $true

    # v25.0 Runtime Certification
    RuntimeCertEnabled = $true
    RuntimeCertRequirePreflight = $true
    RuntimeCertRequireParse = $true
    RuntimeCertRequireSynthetic = $true
    RuntimeCertAllowRouterSmoke = $false
    RuntimeCertAllowSafeRuntime = $false
    RuntimeCertCoexistCockpit = $true
    RuntimeCertPreferredFallbackPort = 8318
    RuntimeCertSmartGatewayPort = 8320
    RuntimeCertSnapshotBeforeRun = $true
    RuntimeCertOpenEvidenceOnFailure = $true

}

$script:S = $null
$script:ProxyExe = $null
$script:ProxyCfg = $null
$script:ProxyExample = $null

# ---------------- Core helpers ----------------

function Ensure-Dir([string]$p) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}
function Write-Utf8([string]$p,[string]$t) {
    [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding($false)))
}
function Save-Json([string]$p,[object]$o) {
    # -InputObject preserves empty arrays/collections as valid JSON [] instead of
    # producing an empty file through pipeline enumeration.
    Write-Utf8 $p (ConvertTo-Json -InputObject $o -Depth 16)
}
function New-LocalKey {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return "hms_" + ([Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_'))
}
function Refresh-Paths {
    $script:ProxyExe = Join-Path ([string]$script:S.ProxyDir) "cli-proxy-api.exe"
    $script:ProxyCfg = Join-Path ([string]$script:S.ProxyDir) "config.yaml"
    $script:ProxyExample = Join-Path ([string]$script:S.ProxyDir) "config.example.yaml"
}
# ---------------- v25.40 protected secret vault ----------------
function Set-HmsSecurityPathAclEarly {
    param([string]$Path)
    if(-not $Path -or -not (Test-Path -LiteralPath $Path)){return $false}
    try{
        $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $item=Get-Item -LiteralPath $Path -Force
        if($item.PSIsContainer){$a=@($Path,'/inheritance:r','/grant:r',('*'+$sid+':(OI)(CI)F'),'*S-1-5-18:(OI)(CI)F','/T','/C','/Q')}
        else{$a=@($Path,'/inheritance:r','/grant:r',('*'+$sid+':F'),'*S-1-5-18:F','/C','/Q')}
        $p=Start-Process -FilePath 'icacls.exe' -ArgumentList $a -NoNewWindow -Wait -PassThru
        return ($p.ExitCode -eq 0)
    }catch{return $false}
}
function Get-HmsSecurityCredentialTargetForInstance {
    param([string]$InstanceId)
    return ('HMS_AI:RouterKey:instance:'+([string]$InstanceId)+':v25.40')
}
function Get-HmsProtectedSecretFallbackPath {
    param([string]$Target)
    Ensure-Dir $script:SecurityDir
    $null=Set-HmsSecurityPathAclEarly $script:SecurityDir
    $id=Get-HmsStringSha256 ([string]$Target)
    return (Join-Path $script:SecurityDir ('vault-'+$id.Substring(0,24)+'.dpapi'))
}
function Set-HmsProtectedSecret {
    param([string]$Target,[string]$Value)
    if([string]::IsNullOrWhiteSpace($Target)){throw 'SECURITY_SECRET_TARGET_EMPTY'}
    if($null -eq $Value){throw 'SECURITY_SECRET_VALUE_NULL'}
    Ensure-Dir $script:SecurityDir
    $useCred=$true;$allowDpapi=$true
    try{if($script:S){$useCred=[bool]$script:S.CodexSecurityCredentialManagerEnabled;$allowDpapi=[bool]$script:S.CodexSecurityDpapiFallbackEnabled}}catch{}
    if($useCred){
        try{
            [HmsCredentialManager]::WriteGeneric($Target,'HMS_AI',[string]$Value)
            return 'CREDENTIAL_MANAGER'
        }catch{}
    }
    if(-not $allowDpapi){throw 'SECURITY_CREDENTIAL_MANAGER_WRITE_FAILED_AND_DPAPI_FALLBACK_DISABLED'}
    $plain=[Text.Encoding]::UTF8.GetBytes([string]$Value)
    try{
        $cipher=[Security.Cryptography.ProtectedData]::Protect($plain,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
        $p=Get-HmsProtectedSecretFallbackPath $Target
        Write-Utf8 $p ([Convert]::ToBase64String($cipher))
        if(-not (Set-HmsSecurityPathAclEarly $p)){throw 'SECURITY_DPAPI_FILE_ACL_HARDEN_FAILED'}
        return 'DPAPI_CURRENT_USER_FILE'
    }finally{if($plain){[Array]::Clear($plain,0,$plain.Length)}}
}
function Get-HmsProtectedSecret {
    param([string]$Target)
    if([string]::IsNullOrWhiteSpace($Target)){return $null}
    $useCred=$true;$allowDpapi=$true
    try{if($script:S){$useCred=[bool]$script:S.CodexSecurityCredentialManagerEnabled;$allowDpapi=[bool]$script:S.CodexSecurityDpapiFallbackEnabled}}catch{}
    if($useCred){
        try{
            $u='';$v=[HmsCredentialManager]::ReadGeneric($Target,[ref]$u)
            if($null -ne $v){return [string]$v}
        }catch{}
    }
    if($allowDpapi){
        try{
            $p=Get-HmsProtectedSecretFallbackPath $Target
            if(Test-Path -LiteralPath $p){
                $cipher=[Convert]::FromBase64String(([IO.File]::ReadAllText($p)).Trim())
                $plain=[Security.Cryptography.ProtectedData]::Unprotect($cipher,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
                try{return [Text.Encoding]::UTF8.GetString($plain)}finally{if($plain){[Array]::Clear($plain,0,$plain.Length)}}
            }
        }catch{}
    }
    return $null
}
function Get-HmsInstanceApiKey {
    param([object]$Instance)
    if(-not $Instance){return ''}
    $ref='';try{$ref=[string]$Instance.apiKeyRef}catch{}
    if([string]::IsNullOrWhiteSpace($ref)){try{$ref=Get-HmsSecurityCredentialTargetForInstance ([string]$Instance.id)}catch{}}
    if($ref){$secret=Get-HmsProtectedSecret $ref;if(-not [string]::IsNullOrWhiteSpace([string]$secret)){return [string]$secret}}
    try{if(-not [string]::IsNullOrWhiteSpace([string]$Instance.apiKey)){return [string]$Instance.apiKey}}catch{}
    return ''
}
function Test-HmsProtectedSecretPresent {
    param([string]$Target)
    try{return -not [string]::IsNullOrWhiteSpace([string](Get-HmsProtectedSecret $Target))}catch{return $false}
}

function Load-Settings {
    Ensure-Dir $script:DataDir
    $script:SettingsLoadWarning = ""
    $h=@{}
    foreach($k in $script:Defaults.Keys){$h[$k]=$script:Defaults[$k]}

    $settingsSource = $script:SettingsPath
    if(-not (Test-Path $settingsSource)){
        $candidates=@(
            $script:LegacySettingsPath,
            (Join-Path $script:DataDir "settings-v60.json"),
            (Join-Path $script:DataDir "settings-v50.json"),
            (Join-Path $script:DataDir "settings-v40.json"),
            (Join-Path $script:DataDir "settings-v30.json"),
            (Join-Path $script:DataDir "settings-v20.json"),
            (Join-Path $script:DataDir "settings-v15.json"),
            (Join-Path $script:DataDir "settings-v10.json"),
            (Join-Path $script:DataDir "settings-v08.json")
        )
        foreach($candidate in $candidates){
            if($candidate -and (Test-Path $candidate)){$settingsSource=$candidate;break}
        }
    }

    if(Test-Path $settingsSource){
        try{
            $r=Get-Content $settingsSource -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach($k in $script:Defaults.Keys){if($null -ne $r.$k){$h[$k]=$r.$k}}
        }catch{
            try{
                $stamp=Get-Date -Format "yyyyMMdd-HHmmss"
                $backup=Join-Path $script:DataDir ("settings-corrupt-"+$stamp+".json")
                Copy-Item $settingsSource $backup -Force
                $script:SettingsLoadWarning="Settings JSON lỗi; đã backup: $backup"
            }catch{
                $script:SettingsLoadWarning="Settings JSON lỗi và backup cũng thất bại."
            }
        }
    }

    $plainSettingsKey=[string]$h.LocalApiKey
    $script:S=$h
    if([bool]$h.CodexSecurityHardeningEnabled -and [bool]$h.CodexSecurityMigratePlainKeys){
        $protected=Get-HmsProtectedSecret $script:SecurityCredentialGlobalTarget
        if(-not [string]::IsNullOrWhiteSpace([string]$protected)){
            $script:S.LocalApiKey=[string]$protected
        }elseif(-not [string]::IsNullOrWhiteSpace($plainSettingsKey)){
            $null=Set-HmsProtectedSecret $script:SecurityCredentialGlobalTarget $plainSettingsKey
            $script:S.LocalApiKey=$plainSettingsKey
        }else{
            $generated=New-LocalKey
            $null=Set-HmsProtectedSecret $script:SecurityCredentialGlobalTarget $generated
            $script:S.LocalApiKey=$generated
        }
    }elseif([string]::IsNullOrWhiteSpace([string]$script:S.LocalApiKey)){
        $script:S.LocalApiKey=New-LocalKey
    }
    Refresh-Paths
    Save-Settings
}
function Save-Settings {
    Ensure-Dir $script:DataDir
    $persist=@{}
    foreach($k in $script:Defaults.Keys){$persist[$k]=$script:S[$k]}
    if([bool]$script:S.CodexSecurityHardeningEnabled -and [bool]$script:S.CodexSecurityMigratePlainKeys){
        $persist['LocalApiKey']=''
        if(-not (Test-HmsProtectedSecretPresent $script:SecurityCredentialGlobalTarget)){
            $null=Set-HmsProtectedSecret $script:SecurityCredentialGlobalTarget ([string]$script:S.LocalApiKey)
        }
    }
    Save-JsonAtomic $script:SettingsPath $persist
    Refresh-Paths
}
function Norm([string]$p){
    try{return ([IO.Path]::GetFullPath($p)).TrimEnd('\').ToLowerInvariant()}catch{return ($p+"").TrimEnd('\').ToLowerInvariant()}
}
function ProcPath([int]$id){try{(Get-Process -Id $id -ErrorAction Stop).Path}catch{$null}}
function IsOurProxy([int]$id){
    if($id -le 0){return $false}
    $p=ProcPath $id
    if(-not $p){return $false}
    return (Norm $p) -eq (Norm $script:ProxyExe)
}
function ListenerPid ([int]$port){
    try{
        $c=Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop| Select-Object -First 1
        if($c){return [int]$c.OwningProcess}
    }catch{}
    try{
        foreach($l in (& netstat.exe -ano -p tcp 2>$null)){
            if($l -match "^\s*TCP\s+\S+:$port\s+\S+\s+LISTENING\s+(\d+)\s*$"){return [int]$matches[1]}
        }
    }catch{}
    return 0
}
function PortOpen ([int]$port){
    $c=New-Object Net.Sockets.TcpClient
    try{
        $a=$c.BeginConnect("127.0.0.1",$port,$null,$null)
        if(-not $a.AsyncWaitHandle.WaitOne(700,$false)){return $false}
        $c.EndConnect($a);return $true
    }catch{return $false}
    finally{try{$c.Close()}catch{}}
}
function Save-State([int]$id,[int]$port){
    Save-Json $script:StatePath @{pid=$id;port=$port;exe=$script:ProxyExe;startedUtc=[DateTime]::UtcNow.ToString("o")}
}
function Clear-State{Remove-Item $script:StatePath -Force -ErrorAction SilentlyContinue}
function ManagedPid{
    if(-not (Test-Path $script:StatePath)){return 0}
    try{$st=Get-Content $script:StatePath -Raw -Encoding UTF8| ConvertFrom-Json}catch{Clear-State;return 0}
    $id=[int]$st.pid
    if($id -le 0 -or -not (IsOurProxy $id)){Clear-State;return 0}
    return $id
}
function AdoptOurExisting{
    $id=ListenerPid ([int]$script:S.ProxyPort)
    if($id -gt 0 -and (IsOurProxy $id)){Save-State $id ([int]$script:S.ProxyPort);return $id}
    return 0
}
function Ensure-ProxyFiles{
    if(-not (Test-Path $script:ProxyExe)){throw "Không tìm thấy $($script:ProxyExe)"}
    if(-not (Test-Path $script:ProxyCfg)){
        if(-not (Test-Path $script:ProxyExample)){throw "Không có config.yaml hoặc config.example.yaml trong $($script:S.ProxyDir)"}
        Copy-Item $script:ProxyExample $script:ProxyCfg -Force
    }
}
function Backup([string]$p,[string]$tag){
    if(Test-Path $p){
        $stamp=Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item $p "$p.hms-$tag-$stamp" -Force
    }
}

# ---------------- YAML config ----------------

function Set-TopYaml([string]$t,[string]$key,[string]$value){
    $pat="(?m)^"+[regex]::Escape($key)+":\s*.*$"
    if($t -match $pat){return [regex]::Replace($t,$pat,($key+": "+$value),1)}
    return $t.TrimEnd()+"`r`n$key`: $value`r`n"
}
function Ensure-Routing([string]$t){
    if($t -match '(?m)^routing:\s*$'){
        if($t -match '(?m)^\s{2}strategy:\s*.*$'){
            $t=[regex]::Replace($t,'(?m)^\s{2}strategy:\s*.*$','  strategy: "round-robin"',1)
        }else{
            $t=[regex]::Replace($t,'(?m)^routing:\s*$',"routing:`r`n  strategy: `"round-robin`"",1)
        }
        if($t -match '(?m)^\s{2}session-affinity:\s*.*$'){
            $t=[regex]::Replace($t,'(?m)^\s{2}session-affinity:\s*.*$','  session-affinity: true',1)
        }else{
            $t=[regex]::Replace($t,'(?m)^\s{2}strategy:\s*.*$',('$0'+"`r`n  session-affinity: true"),1)
        }
        if($t -match '(?m)^\s{2}session-affinity-ttl:\s*.*$'){
            $t=[regex]::Replace($t,'(?m)^\s{2}session-affinity-ttl:\s*.*$','  session-affinity-ttl: "1h"',1)
        }else{
            $t=[regex]::Replace($t,'(?m)^\s{2}session-affinity:\s*.*$',('$0'+"`r`n  session-affinity-ttl: `"1h`""),1)
        }
        return $t
    }
    return $t.TrimEnd()+@"

routing:
  strategy: "round-robin"
  session-affinity: true
  session-affinity-ttl: "1h"
"@+"`r`n"
}

function Remove-CLIProxyExampleApiKeys([string]$Text){
    $unsafe=@("your-api-key-1","your-api-key-2","your-api-key-3")
    $lines=[System.Collections.Generic.List[string]]::new()
    $inApiKeys=$false
    foreach($line in ($Text -split "`r?`n")){
        if($line -match '^api-keys\s*:\s*(?:#.*)?$'){
            $inApiKeys=$true
            $lines.Add($line)
            continue
        }
        if($inApiKeys -and $line -match '^\S'){
            $inApiKeys=$false
        }
        if($inApiKeys -and $line -match '^\s*-\s*["'']?([^"''#]+?)["'']?\s*(?:#.*)?$'){
            $v=[string]$matches[1]
            $v=$v.Trim()
            if($unsafe -contains $v){
                continue
            }
        }
        $lines.Add($line)
    }
    return ($lines -join "`r`n")
}
function Get-CLIProxyExampleApiKeys {
    $unsafe=@("your-api-key-1","your-api-key-2","your-api-key-3")
    $found=[System.Collections.Generic.List[string]]::new()
    foreach($k in @(Get-ProxyConfiguredApiKeys)){
        if($unsafe -contains $k){$found.Add($k)}
    }
    return $found.ToArray()
}

function Ensure-ApiKey([string]$t,[string]$key){
    $quoted='"'+$key+'"'
    if($t.Contains($quoted)){return $t}

    if($t -match '(?m)^api-keys:\s*\[\s*\]\s*$'){
        return [regex]::Replace($t,'(?m)^api-keys:\s*\[\s*\]\s*$',"api-keys:`r`n  - $quoted",1)
    }
    if($t -match '(?m)^api-keys:\s*$'){
        return [regex]::Replace($t,'(?m)^api-keys:\s*$',("api-keys:`r`n  - "+$quoted),1)
    }
    return $t.TrimEnd()+"`r`napi-keys:`r`n  - $quoted`r`n"
}


function Get-SecretFingerprint([string]$Value){
    if([string]::IsNullOrWhiteSpace($Value)){return "EMPTY"}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{
        $bytes=[Text.Encoding]::UTF8.GetBytes($Value)
        $hash=$sha.ComputeHash($bytes)
        return (([BitConverter]::ToString($hash)).Replace("-","").Substring(0,12).ToLowerInvariant())
    }finally{$sha.Dispose()}
}
function Get-ProxyConfiguredApiKeys {
    $keys=[System.Collections.Generic.List[string]]::new()
    if(-not (Test-Path $script:ProxyCfg)){return @()}
    $inBlock=$false
    foreach($line in @(Get-Content $script:ProxyCfg -Encoding UTF8)){
        if($line -match '^\s*api-keys\s*:\s*\[\s*\]\s*(?:#.*)?$'){
            return @()
        }
        if($line -match '^\s*api-keys\s*:\s*(?:#.*)?$'){
            $inBlock=$true
            continue
        }
        if($inBlock){
            if($line -match '^\S'){break}
            if($line -match '^\s*-\s*["'']?([^"''#]+?)["'']?\s*(?:#.*)?$'){
                $v=[string]$matches[1]
                $v=$v.Trim()
                if($v){$keys.Add($v)}
            }
        }
    }
    return $keys.ToArray()
}
function Get-ProxyApiKeyAudit {
    $expected=[string]$script:S.LocalApiKey
    $keys=@(Get-ProxyConfiguredApiKeys)
    $match=@($keys | Where-Object {$_ -ceq $expected}).Count -gt 0
    $unsafe=@(Get-CLIProxyExampleApiKeys)
    return [PSCustomObject]@{
        Match=$match
        ExpectedFingerprint=(Get-SecretFingerprint $expected)
        ConfigFingerprints=@($keys | ForEach-Object {Get-SecretFingerprint $_})
        Count=$keys.Count
        UnsafeExampleKeys=$unsafe
        UnsafeExampleKeyCount=$unsafe.Count
        ConfigPath=$script:ProxyCfg
    }
}
function Redact-HmsSecurityText([string]$Text){
    if($null -eq $Text){return ""}
    $r=[string]$Text
    # Replace exact known HMS router secrets without serializing them anywhere else.
    try{$key=[string]$script:S.LocalApiKey;if($key){$r=$r.Replace($key,'<redacted-local-api-key>')}}catch{}
    try{
        foreach($i in @((Get-CodexInstanceStore).instances)){
            $ik='';try{$ik=[string](Get-HmsInstanceApiKey $i)}catch{}
            if($ik){$r=$r.Replace($ik,'<redacted-instance-api-key>')}
        }
    }catch{}
    # Authorization headers / Bearer tokens / JWTs.
    $r=[regex]::Replace($r,'(?im)(Authorization\s*:\s*Bearer\s+)[^\s,;]+','$1<redacted-bearer>')
    $r=[regex]::Replace($r,'(?i)\bBearer\s+[A-Za-z0-9._~+\-/=]{12,}','Bearer <redacted-token>')
    $r=[regex]::Replace($r,'(?i)\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b','<redacted-jwt>')
    # Common JSON/YAML/TOML/ENV secret fields. Preserve only the field name.
    $r=[regex]::Replace($r,'(?im)(["'']?(?:access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|client[_-]?secret|password|cookie|authorization)["'']?\s*[:=]\s*)["'']?[^,\r\n"'']+["'']?','$1<redacted-secret>')
    $r=[regex]::Replace($r,'(?im)^(\s*HMS_ROUTER_API_KEY\s*=\s*).*$','$1<redacted-local-api-key>')
    # Router yaml api-keys entries and common OpenAI/HMS key shapes.
    $r=[regex]::Replace($r,'(?im)^(\s*-\s*)["'']?(?:hms[_-]|sk[-_])[A-Za-z0-9._\-]{8,}["'']?\s*$','$1<redacted-key>')
    $r=[regex]::Replace($r,'(?i)\b(?:sk[-_]|hms_(?!router_api_key\b)|hms-)[A-Za-z0-9._\-]{10,}\b','<redacted-key>')
    return $r
}
function Redact-LocalApiText([string]$Text){
    $r=Redact-HmsSecurityText $Text
    if($r.Length -gt 1600){$r=$r.Substring(0,1600)+"..."}
    return $r
}

function Set-RoutingProfileYaml {
    param([string]$Text)
    $profile=([string]$script:S.CodexRoutingProfile).Trim().ToLowerInvariant()
    if($profile -notin @("stable","balanced","fill-first")){$profile="stable"}

    $strategy = if($profile -eq "fill-first"){"fill-first"}else{"round-robin"}
    $affinity = if($profile -eq "balanced"){"false"}else{"true"}
    $ttl = [string]$script:S.CodexSessionAffinityTtl
    if([string]::IsNullOrWhiteSpace($ttl)){$ttl="1h"}

    if($Text -notmatch '(?m)^routing:\s*$'){
        $Text=$Text.TrimEnd()+"`r`nrouting:`r`n  strategy: `"$strategy`"`r`n  session-affinity: $affinity`r`n  session-affinity-ttl: `"$ttl`"`r`n"
        return $Text
    }

    if($Text -match '(?m)^\s{2}strategy:\s*.*$'){
        $Text=[regex]::Replace($Text,'(?m)^\s{2}strategy:\s*.*$',("  strategy: `"$strategy`""),1)
    }else{
        $Text=[regex]::Replace($Text,'(?m)^routing:\s*$',("routing:`r`n  strategy: `"$strategy`""),1)
    }

    if($Text -match '(?m)^\s{2}session-affinity:\s*.*$'){
        $Text=[regex]::Replace($Text,'(?m)^\s{2}session-affinity:\s*.*$',("  session-affinity: "+$affinity),1)
    }else{
        $Text=[regex]::Replace($Text,'(?m)^\s{2}strategy:\s*.*$',('$0'+"`r`n  session-affinity: "+$affinity),1)
    }

    if($Text -match '(?m)^\s{2}session-affinity-ttl:\s*.*$'){
        $Text=[regex]::Replace($Text,'(?m)^\s{2}session-affinity-ttl:\s*.*$',("  session-affinity-ttl: `"$ttl`""),1)
    }else{
        $Text=[regex]::Replace($Text,'(?m)^\s{2}session-affinity:\s*.*$',('$0'+"`r`n  session-affinity-ttl: `"$ttl`""),1)
    }
    return $Text
}

function Ensure-CodexYamlBlock {
    param([string]$Text)

    if($Text -notmatch '(?m)^codex:\s*$'){
        return $Text.TrimEnd()+"`r`ncodex:`r`n  identity-confuse: false`r`n  disable-codex-cloaking: false`r`n  optimize-multi-agent-v2: "+$(if([bool]$script:S.CodexOptimizeMultiAgentV2){"true"}else{"false"})+"`r`n"
    }

    $desired = if([bool]$script:S.CodexOptimizeMultiAgentV2){"true"}else{"false"}
    if($Text -match '(?m)^\s{2}optimize-multi-agent-v2:\s*.*$'){
        $Text=[regex]::Replace($Text,'(?m)^\s{2}optimize-multi-agent-v2:\s*.*$',("  optimize-multi-agent-v2: "+$desired),1)
    }else{
        $Text=[regex]::Replace($Text,'(?m)^codex:\s*$',("codex:`r`n  optimize-multi-agent-v2: "+$desired),1)
    }
    return $Text
}

function Get-CodexRoutingDescription {
    $p=([string]$script:S.CodexRoutingProfile).Trim().ToLowerInvariant()
    switch($p){
        "balanced" { return "CHIA ĐỀU — round-robin, không sticky session" }
        "fill-first" { return "DÙNG HẾT TỪNG ACC — fill-first + sticky" }
        default { return "ỔN ĐỊNH — round-robin + session affinity + failover" }
    }
}


function Configure-Proxy{
    Ensure-ProxyFiles
    Backup $script:ProxyCfg "v08"
    $t=[IO.File]::ReadAllText($script:ProxyCfg)
    $t=Set-TopYaml $t "host" '"127.0.0.1"'
    $t=Set-TopYaml $t "port" ([string][int]$script:S.ProxyPort)
    $t=Set-TopYaml $t "logging-to-file" "true"
    $t=Set-TopYaml $t "usage-statistics-enabled" "true"
    $t=Set-TopYaml $t "save-cooldown-status" $(if([bool]$script:S.CodexSaveCooldownStatus){"true"}else{"false"})
    $t=Set-TopYaml $t "request-retry" ([string][int]$script:S.CodexRequestRetry)
    $t=Set-TopYaml $t "max-retry-credentials" ([string][int]$script:S.CodexMaxRetryCredentials)
    $t=Set-TopYaml $t "max-retry-interval" ([string][int]$script:S.CodexMaxRetryInterval)
    $t=Set-RoutingProfileYaml $t
    $t=Ensure-CodexYamlBlock $t
    # CLIProxyAPI v7 enters Example API Key Safe Mode when any official
    # template values remain in top-level api-keys. Remove ONLY those exact
    # official placeholders; preserve all user/custom keys.
    $t=Remove-CLIProxyExampleApiKeys $t
    $t=Ensure-ApiKey $t ([string]$script:S.LocalApiKey)
    Write-Utf8 $script:ProxyCfg $t
}

# ---------------- Codex API-mode config ----------------

function CodexInHmsMode{
    if(-not (Test-Path $script:CodexConfig)){return $false}
    try{
        $t=[IO.File]::ReadAllText($script:CodexConfig)
        return ($t -match '(?m)^model_provider\s*=\s*"hms_api_router"\s*$') -and
               ($t -match '\[model_providers\.hms_api_router\]')
    }catch{return $false}
}
function Snapshot-ClientConfigIfNeeded{
    Ensure-Dir $script:DataDir
    # Never overwrite Cockpit/direct snapshot while HMS mode is already active.
    if(CodexInHmsMode){return}

    Remove-Item $script:SnapConfigMissing,$script:SnapEnvMissing -Force -ErrorAction SilentlyContinue

    if(Test-Path $script:CodexConfig){
        Copy-Item $script:CodexConfig $script:SnapConfig -Force
    }else{
        Remove-Item $script:SnapConfig -Force -ErrorAction SilentlyContinue
        "missing"|Set-Content $script:SnapConfigMissing -Encoding ASCII
    }

    if(Test-Path $script:CodexEnv){
        Copy-Item $script:CodexEnv $script:SnapEnv -Force
    }else{
        Remove-Item $script:SnapEnv -Force -ErrorAction SilentlyContinue
        "missing"|Set-Content $script:SnapEnvMissing -Encoding ASCII
    }
}
function Set-RootTomlKey([string]$t,[string]$key,[string]$value){
    $pat="(?m)^"+[regex]::Escape($key)+"\s*=.*$"
    if($t -match $pat){return [regex]::Replace($t,$pat,($key+" = "+$value),1)}

    # TOML root keys must stay before the first table.
    $m=[regex]::Match($t,'(?m)^\[')
    if($m.Success){
        return $t.Substring(0,$m.Index).TrimEnd()+"`r`n"+$key+" = "+$value+"`r`n`r`n"+$t.Substring($m.Index)
    }
    return $t.TrimEnd()+"`r`n"+$key+" = "+$value+"`r`n"
}
function Remove-ProviderBlock([string]$t,[string]$id){
    $pat='(?ms)^\[model_providers\.'+[regex]::Escape($id)+'\]\s*\r?\n.*?(?=^\[|\z)'
    return [regex]::Replace($t,$pat,'')
}
function Configure-CodexApiMode{
    Ensure-Dir $script:CodexDir
    if(-not (Test-Path $script:CodexConfig)){New-Item -ItemType File $script:CodexConfig|Out-Null}

    Backup $script:CodexConfig "v08"
    Backup $script:CodexEnv "v08"

    $t=[IO.File]::ReadAllText($script:CodexConfig)
    $t=Remove-ProviderBlock $t "hms_multirouter"
    $t=Remove-ProviderBlock $t "hms_api_router"
    $t=Set-RootTomlKey $t "model_provider" '"hms_api_router"'

    $port=[int]$script:S.ProxyPort
    $block=@"

[model_providers.hms_api_router]
name = "API"
base_url = "http://127.0.0.1:$port/v1"
env_key = "HMS_ROUTER_API_KEY"
env_key_instructions = "Managed automatically by HMS-AI-ROUTER Multi Router"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 4
stream_max_retries = 5
stream_idle_timeout_ms = 300000
"@
    $t=$t.TrimEnd()+"`r`n"+$block.TrimStart()+"`r`n"
    Write-Utf8 $script:CodexConfig $t

    $envText=""
    if(Test-Path $script:CodexEnv){$envText=[IO.File]::ReadAllText($script:CodexEnv)}
    if($envText -match '(?m)^HMS_ROUTER_API_KEY=.*$'){
        $envText=[regex]::Replace($envText,'(?m)^HMS_ROUTER_API_KEY=.*$',("HMS_ROUTER_API_KEY="+[string]$script:S.LocalApiKey),1)
    }else{
        if($envText.Length -gt 0 -and -not $envText.EndsWith("`n")){$envText+="`r`n"}
        $envText+="HMS_ROUTER_API_KEY="+[string]$script:S.LocalApiKey+"`r`n"
    }
    Write-Utf8 $script:CodexEnv $envText
}
function Restore-ClientConfig{
    if(-not [bool]$script:S.RestoreOnDisable){return "Không restore config (theo thiết lập)."}

    if(Test-Path $script:SnapConfig){
        Ensure-Dir $script:CodexDir
        Copy-Item $script:SnapConfig $script:CodexConfig -Force
    }elseif(Test-Path $script:SnapConfigMissing){
        Remove-Item $script:CodexConfig -Force -ErrorAction SilentlyContinue
    }

    if(Test-Path $script:SnapEnv){
        Ensure-Dir $script:CodexDir
        Copy-Item $script:SnapEnv $script:CodexEnv -Force
    }elseif(Test-Path $script:SnapEnvMissing){
        Remove-Item $script:CodexEnv -Force -ErrorAction SilentlyContinue
    }
    return "Đã khôi phục config/.env trước HMS Router."
}


function Restore-ClientSnapshotTransactional{
    try{
        if(Test-Path $script:SnapConfig){
            Ensure-Dir $script:CodexDir
            Copy-Item $script:SnapConfig $script:CodexConfig -Force
        }elseif(Test-Path $script:SnapConfigMissing){
            Remove-Item $script:CodexConfig -Force -ErrorAction SilentlyContinue
        }
        if(Test-Path $script:SnapEnv){
            Ensure-Dir $script:CodexDir
            Copy-Item $script:SnapEnv $script:CodexEnv -Force
        }elseif(Test-Path $script:SnapEnvMissing){
            Remove-Item $script:CodexEnv -Force -ErrorAction SilentlyContinue
        }
        return $true
    }catch{return $false}
}
function Get-CodexConfigGenerationTime{
    $times=[System.Collections.Generic.List[datetime]]::new()
    foreach($f in @($script:CodexConfig,$script:CodexEnv)){
        try{if(Test-Path $f){$times.Add((Get-Item $f).LastWriteTime)}}catch{}
    }
    if($times.Count -eq 0){return [datetime]::MinValue}
    return ($times | Sort-Object -Descending | Select-Object -First 1)
}
function Test-CodexEnvDiskReady{
    if(-not (CodexInHmsMode)){return $false}
    if(-not (Test-Path $script:CodexEnv)){return $false}
    try{
        $e=[IO.File]::ReadAllText($script:CodexEnv)
        $expected="HMS_ROUTER_API_KEY="+[string]$script:S.LocalApiKey
        return @($e -split "`r?`n" | Where-Object {$_ -ceq $expected}).Count -gt 0
    }catch{return $false}
}
function Test-CodexClientFresh{
    $clients=@(Get-CodexClientProcesses)
    if($clients.Count -eq 0){return $false}
    $generation=Get-CodexConfigGenerationTime
    foreach($proc in $clients){
        try{if($proc.StartTime -le $generation){return $false}}catch{return $false}
    }
    return $true
}
function Wait-CodexClientFresh([int]$TimeoutSec=15){
    $deadline=(Get-Date).AddSeconds([Math]::Max(1,$TimeoutSec))
    do{
        if(Test-CodexClientFresh){return $true}
        Start-Sleep -Milliseconds 300
    }while((Get-Date) -lt $deadline)
    return $false
}
function Ensure-CodexRestartBarrier{
    $clients=@(Get-CodexClientProcesses)
    if($clients.Count -eq 0){
        return @{WasOpen=$false;Closed=$true;Message="Codex/ChatGPT chưa mở."}
    }
    $r=Close-CodexClientGracefully
    if(-not $r.Closed){
        throw "CODEX_RESTART_REQUIRED: ChatGPT/Codex vẫn còn process đang chạy. HMS chưa thay đổi provider/.env. Hãy thoát hẳn app hoặc bật tùy chọn force-close, rồi thử lại."
    }
    return $r
}

# ---------------- Proxy lifecycle ----------------

function Start-Router{
    Ensure-ProxyFiles
    $port=[int]$script:S.ProxyPort
    $id=ListenerPid $port
    if($id -gt 0){
        if(IsOurProxy $id){Save-State $id $port;return "Router đã ONLINE PID $id."}
        $foreignPath=ProcPath $id;if(-not $foreignPath){$foreignPath="PID $id"}
        throw "Port $port đang bị dịch vụ khác chiếm: $foreignPath`nTool KHÔNG tắt dịch vụ này để tránh ảnh hưởng Cockpit."
    }

    Ensure-Dir $script:DataDir
    $stdout=Join-Path $script:DataDir "cliproxy-live-stdout.log"
    $stderr=Join-Path $script:DataDir "cliproxy-live-stderr.log"
    Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue

    # Explicit --config removes working-directory/default-config ambiguity.
    $cfgArg='"'+$script:ProxyCfg+'"'
    $p=Start-Process $script:ProxyExe `
        -ArgumentList @("--config",$cfgArg) `
        -WorkingDirectory ([string]$script:S.ProxyDir) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    Save-State $p.Id $port
    for($i=0;$i -lt 40;$i++){
        Start-Sleep -Milliseconds 300
        if(PortOpen $port){
            $owner=ListenerPid $port
            if($owner -gt 0 -and $owner -ne $p.Id -and -not (IsOurProxy $owner)){
                try{if(-not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}}catch{}
                Clear-State
                throw "Port $port chuyển sang PID lạ $owner trong lúc start; HMS đã dừng child của mình."
            }
            return "Router ONLINE PID $($p.Id), port $port, config=$($script:ProxyCfg)."
        }
        if($p.HasExited){
            Clear-State
            $err=""
            try{if(Test-Path $stderr){$err=Get-Content $stderr -Raw -Encoding UTF8}}catch{}
            throw "CLIProxyAPI thoát trong lúc khởi động. exit=$($p.ExitCode) "+(Redact-LocalApiText $err)
        }
    }
    try{if(-not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}}catch{}
    Clear-State
    throw "CLIProxyAPI chạy nhưng port $port chưa phản hồi. Xem $stderr"
}
function Stop-Router{
    $id=ManagedPid
    if($id -le 0){$id=AdoptOurExisting}
    if($id -le 0){return "Không có HMS Router do tool quản lý để tắt."}
    if(-not (IsOurProxy $id)){Clear-State;return "PID không còn thuộc HMS Router; bỏ qua để bảo vệ Cockpit."}
    Stop-Process -Id $id -Force -ErrorAction Stop
    Start-Sleep -Milliseconds 350
    Clear-State
    return "Đã tắt HMS Router PID $id."
}
function Restart-Router{
    $a=Stop-Router
    Configure-Proxy
    $b=Start-Router
    return "$a $b"
}

# ---------------- Codex / ChatGPT client restart ----------------

function Get-CodexClientProcesses{
    $names=@("Codex","ChatGPT")
    $all=@()
    foreach($n in $names){
        try{$all+=@(Get-Process -Name $n -ErrorAction SilentlyContinue)}catch{}
    }
    # Deduplicate by PID.
    return @($all| Sort-Object Id -Unique)
}
function Close-CodexClientGracefully{
    $ps=@(Get-CodexClientProcesses)
    if($ps.Count -eq 0){return @{WasOpen=$false;Closed=$true;Message="Codex/ChatGPT chưa mở."}}

    foreach($p in $ps){
        try{
            if($p.MainWindowHandle -ne 0){$null=$p.CloseMainWindow()}
        }catch{}
    }
    Start-Sleep -Seconds 2

    $left=@(Get-CodexClientProcesses)
    if($left.Count -eq 0){return @{WasOpen=$true;Closed=$true;Message="Đã đóng Codex/ChatGPT an toàn."}}

    if([bool]$script:S.ForceCloseIfNeeded){
        foreach($p in $left){
            try{Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}catch{}
        }
        Start-Sleep -Milliseconds 400
        return @{WasOpen=$true;Closed=(@(Get-CodexClientProcesses).Count -eq 0);Message="Đã force-close client theo tùy chọn."}
    }

    return @{WasOpen=$true;Closed=$false;Message="Client vẫn còn chạy; không force-close vì tùy chọn an toàn đang bật."}
}
function Start-AppByName([string]$pattern){
    try{
        $apps=@(Get-StartApps|Where-Object{$_.Name -match $pattern})
        if($apps.Count -gt 0){
            $a=$apps| Select-Object -First 1
            Start-Process explorer.exe -ArgumentList ("shell:AppsFolder\"+$a.AppID)|Out-Null
            return $true
        }
    }catch{}
    return $false
}
function Open-CodexClient{
    $existing=@(Get-CodexClientProcesses)
    if($existing.Count -gt 0 -and (CodexInHmsMode)){
        if(-not (Test-CodexEnvDiskReady)){
            throw "CODEX_ENV_NOT_READY: ~/.codex/.env chưa chứa HMS_ROUTER_API_KEY mong đợi."
        }
        if(-not (Test-CodexClientFresh)){
            throw "CODEX_CLIENT_STALE: ChatGPT/Codex đang chạy từ trước lần ghi config/.env. Hãy thoát hẳn app rồi bấm MỞ CODEX lại."
        }
    }

    if(Start-AppByName '^Codex$'){return "Đã mở/focus Codex Desktop."}
    if(Start-AppByName '^ChatGPT$'){return "Đã mở/focus ChatGPT Desktop (Codex view)."}
    try{Start-Process "codex.exe" -ErrorAction Stop|Out-Null;return "Đã mở Codex."}catch{}
    try{Start-Process "chatgpt.exe" -ErrorAction Stop|Out-Null;return "Đã mở ChatGPT."}catch{}
    Start-Process "https://chatgpt.com/"|Out-Null
    return "Không tìm thấy app Desktop; đã mở chatgpt.com."
}
function Restart-CodexForSwitch([bool]$openAfter){
    if(-not [bool]$script:S.RestartCodexOnSwitch){
        return "Không restart Codex (theo thiết lập)."
    }
    $r=Close-CodexClientGracefully
    if(-not $r.Closed){
        return $r.Message+" Hãy đóng/mở Codex thủ công để áp dụng cấu hình."
    }
    if($openAfter -or $r.WasOpen){
        Start-Sleep -Milliseconds 800
        return $r.Message+" "+(Open-CodexClient)
    }
    return $r.Message
}

# ---------------- Providers ----------------

function Login-Provider([string]$flag){
    Ensure-ProxyFiles

    $w=New-Object Windows.Forms.Form
    $w.Text="HMS — Đăng nhập tài khoản"
    $w.Size=New-Object Drawing.Size(560,280)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(19,22,27)
    $w.ForeColor=[Drawing.Color]::FromArgb(235,240,246)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5)
    $w.FormBorderStyle="FixedDialog"
    $w.MaximizeBox=$false
    $w.MinimizeBox=$false

    $title=New-Object Windows.Forms.Label
    $title.Text=if($flag -eq "--codex-login"){"ĐĂNG NHẬP CODEX"}else{"ĐĂNG NHẬP NHÀ CUNG CẤP"}
    $title.Font=New-Object Drawing.Font("Segoe UI Semibold",15)
    $title.Location=New-Object Drawing.Point(22,20)
    $title.AutoSize=$true
    $w.Controls.Add($title)

    $status=New-Object Windows.Forms.Label
    $status.Text="HMS đang khởi tạo OAuth ở chế độ ẩn. Trình duyệt sẽ tự mở nếu cần."
    $status.Location=New-Object Drawing.Point(24,62)
    $status.Size=New-Object Drawing.Size(500,54)
    $status.ForeColor=[Drawing.Color]::FromArgb(154,165,178)
    $w.Controls.Add($status)

    $bar=New-Object Windows.Forms.ProgressBar
    $bar.Style="Marquee"
    $bar.MarqueeAnimationSpeed=24
    $bar.Location=New-Object Drawing.Point(26,126)
    $bar.Size=New-Object Drawing.Size(490,18)
    $w.Controls.Add($bar)

    $close=New-Object Windows.Forms.Button
    $close.Text="ĐÓNG"
    $close.Location=New-Object Drawing.Point(392,177)
    $close.Size=New-Object Drawing.Size(124,38)
    $close.FlatStyle="Flat"
    $close.FlatAppearance.BorderSize=0
    $close.BackColor=[Drawing.Color]::FromArgb(38,44,52)
    $close.ForeColor=$w.ForeColor
    $close.Enabled=$false
    $w.Controls.Add($close)

    $stdout=Join-Path $env:TEMP ("hms-oauth-"+[Guid]::NewGuid().ToString("N")+".out.log")
    $stderr=Join-Path $env:TEMP ("hms-oauth-"+[Guid]::NewGuid().ToString("N")+".err.log")
    $openedUrl=$false
    $proc=$null

    try{
        $proc=Start-Process $script:ProxyExe `
            -ArgumentList @($flag) `
            -WorkingDirectory ([string]$script:S.ProxyDir) `
            -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    }catch{
        $bar.Style="Blocks"
        $status.Text="Không thể khởi tạo OAuth: "+(Redact-LocalApiText $_.Exception.Message)
        $status.ForeColor=[Drawing.Color]::FromArgb(238,120,112)
        $close.Enabled=$true
    }

    $timer=New-Object Windows.Forms.Timer
    $timer.Interval=500
    $timer.Add_Tick({
        if(-not $proc){return}
        try{
            $combined=""
            if(Test-Path $stdout){$combined+=(Get-Content $stdout -Raw -ErrorAction SilentlyContinue)}
            if(Test-Path $stderr){$combined+="`n"+(Get-Content $stderr -Raw -ErrorAction SilentlyContinue)}

            if(-not $openedUrl -and $combined){
                $m=[regex]::Match($combined,'https?://[^\s"''<>]+')
                if($m.Success){
                    $url=[string]$m.Value
                    if($url -match '^https://'){
                        $openedUrl=$true
                        try{Start-Process $url|Out-Null}catch{}
                        $status.Text="Trình duyệt OAuth đã mở. Hoàn tất đăng nhập trong trình duyệt; HMS đang chờ callback."
                    }
                }
            }

            if($proc.HasExited){
                $timer.Stop()
                $bar.Style="Blocks"
                if($proc.ExitCode -eq 0){
                    $status.Text="Đăng nhập hoàn tất. HMS sẽ tự nhận credential mới."
                    $status.ForeColor=[Drawing.Color]::FromArgb(106,216,157)
                }else{
                    $safe=Redact-LocalApiText $combined
                    if($safe.Length -gt 260){$safe=$safe.Substring($safe.Length-260)}
                    $status.Text="OAuth kết thúc với mã "+$proc.ExitCode+". "+$safe
                    $status.ForeColor=[Drawing.Color]::FromArgb(238,120,112)
                }
                $close.Enabled=$true
                try{Status}catch{}
            }
        }catch{}
    })
    $close.Add_Click({$w.Close()})
    $w.Add_FormClosed({
        try{$timer.Stop()}catch{}
        try{
            if($proc -and -not $proc.HasExited){
                # Closing the dialog does not kill OAuth; it may still be waiting for browser callback.
            }
        }catch{}
        Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue
    })
    if($proc){$timer.Start()}
    [void]$w.ShowDialog($form)
}
function AuthCount([string]$prefix){
    if(-not (Test-Path $script:AuthDir)){return 0}
    return @(Get-ChildItem $script:AuthDir -File -Filter "$prefix*.json" -ErrorAction SilentlyContinue).Count
}
function Open-Antigravity{
    if(Start-AppByName 'Antigravity'){return "Đã mở Antigravity."}
    $c=@(
        (Join-Path $env:LOCALAPPDATA "Programs\Antigravity\Antigravity.exe"),
        (Join-Path $env:LOCALAPPDATA "Antigravity\Antigravity.exe"),
        (Join-Path $env:ProgramFiles "Antigravity\Antigravity.exe")
    )
    foreach($p in $c){if(Test-Path $p){Start-Process $p|Out-Null;return "Đã mở Antigravity."}}
    try{Start-Process "antigravity.exe" -ErrorAction Stop|Out-Null;return "Đã mở Antigravity."}catch{}
    Start-Process "https://antigravity.google/"|Out-Null
    return "Không tìm thấy app Antigravity; đã mở trang web."
}


# ---------------- Antigravity 2.0 seamless bridge ----------------

function Ensure-BridgeSecret {
    Ensure-Dir $script:DataDir
    if (Test-Path $script:BridgeSecretPath) {
        try {
            $v = [IO.File]::ReadAllText($script:BridgeSecretPath).Trim()
            if ($v) { return $v }
        } catch {}
    }
    $v = "hms_ag_" + (New-LocalKey)
    Write-Utf8 $script:BridgeSecretPath $v
    return $v
}

function Find-AntigravityExe {
    try {
        $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^Antigravity$' })
        foreach ($p in $running) {
            try { if ($p.Path -and (Test-Path $p.Path)) { return $p.Path } } catch {}
        }
    } catch {}
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Antigravity\Antigravity.exe"),
        (Join-Path $env:LOCALAPPDATA "Antigravity\Antigravity.exe"),
        (Join-Path $env:ProgramFiles "Antigravity\Antigravity.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Antigravity\Antigravity.exe")
    )
    foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }
    try {
        $cmd = Get-Command antigravity.exe -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    } catch {}
    return $null
}

function Get-AntigravityInstalledInfo {
    $exe = Find-AntigravityExe
    if (-not $exe) { return [PSCustomObject]@{Found=$false;Path="";Version=""} }
    $ver = ""
    try { $ver = (Get-Item $exe).VersionInfo.ProductVersion } catch {}
    return [PSCustomObject]@{Found=$true;Path=$exe;Version=$ver}
}

function Get-AntigravityProcesses {
    try { return @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^Antigravity$' }) }
    catch { return @() }
}

function Close-AntigravityGracefully {
    $ps = @(Get-AntigravityProcesses)
    if ($ps.Count -eq 0) { return [PSCustomObject]@{WasOpen=$false;Closed=$true;Message="Antigravity chưa mở."} }
    foreach ($p in $ps) {
        try { if ($p.MainWindowHandle -ne 0) { $null = $p.CloseMainWindow() } } catch {}
    }
    $deadline = (Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 250
        $left = @(Get-AntigravityProcesses)
        if ($left.Count -eq 0) { return [PSCustomObject]@{WasOpen=$true;Closed=$true;Message="Đã đóng Antigravity an toàn."} }
    } while ((Get-Date) -lt $deadline)
    if ([bool]$script:S.ForceCloseIfNeeded) {
        foreach ($p in $left) { try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {} }
        Start-Sleep -Milliseconds 500
        return [PSCustomObject]@{WasOpen=$true;Closed=(@(Get-AntigravityProcesses).Count -eq 0);Message="Đã force-close Antigravity theo tùy chọn."}
    }
    return [PSCustomObject]@{WasOpen=$true;Closed=$false;Message="Antigravity vẫn còn chạy; không force-close vì chế độ an toàn."}
}

function Start-AntigravityDesktop {
    $exe = Find-AntigravityExe
    if ($exe) { Start-Process $exe | Out-Null; return "Đã mở Antigravity Desktop." }
    return (Open-Antigravity)
}

function Install-HmsAntigravityBridge {
    if (-not (Test-Path $script:BridgeVsix)) { throw "Không tìm thấy VSIX bridge: $script:BridgeVsix" }
    $exe = Find-AntigravityExe
    if (-not $exe) { throw "Không tìm thấy Antigravity.exe. Hãy cài Antigravity 2.0 trước." }
    $null = Ensure-BridgeSecret
    $args = "--install-extension `"$script:BridgeVsix`" --force"
    $p = Start-Process -FilePath $exe -ArgumentList $args -PassThru
    $exited = $false
    try { $exited = $p.WaitForExit(15000) } catch {}
    if ($exited -and $p.ExitCode -ne 0) { throw "Antigravity trả mã lỗi $($p.ExitCode) khi cài HMS Bridge." }
    return "Đã gửi lệnh cài HMS Antigravity Bridge. Nếu bridge chưa ONLINE, restart Antigravity một lần."
}

function Read-BridgeStatus {
    if (-not (Test-Path $script:BridgeStatusPath)) { return $null }
    try { return (Get-Content $script:BridgeStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}

function Invoke-AgBridge {
    param([hashtable]$Payload, [int]$TimeoutMs = 10000)
    $st = Read-BridgeStatus
    if (-not $st -or -not $st.port) { throw "HMS Antigravity Bridge chưa ONLINE. Hãy cài bridge và mở/restart Antigravity." }
    $port = [int]$st.port
    $secret = Ensure-BridgeSecret
    $Payload["secret"] = $secret
    $client = New-Object Net.Sockets.TcpClient
    try {
        $a = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $a.AsyncWaitHandle.WaitOne([Math]::Min($TimeoutMs,2500), $false)) { throw "Timeout kết nối bridge port $port." }
        $client.EndConnect($a)
        $stream = $client.GetStream()
        $stream.ReadTimeout = $TimeoutMs
        $stream.WriteTimeout = 5000
        $enc = New-Object Text.UTF8Encoding($false)
        $writer = New-Object IO.StreamWriter($stream,$enc)
        $writer.AutoFlush = $true
        $reader = New-Object IO.StreamReader($stream,$enc)
        $writer.WriteLine(($Payload | ConvertTo-Json -Compress -Depth 8))
        $line = $reader.ReadLine()
        if ([string]::IsNullOrWhiteSpace($line)) { throw "Bridge không trả dữ liệu." }
        return ($line | ConvertFrom-Json)
    } finally {
        try { $client.Close() } catch {}
    }
}

function Test-HmsAntigravityBridge {
    try {
        $r = Invoke-AgBridge -Payload @{type="ping"} -TimeoutMs 4000
        if (-not $r.success) { return [PSCustomObject]@{Ok=$false;Message=([string]$r.message);Response=$r} }
        $api = [string]$r.hostApi
        $msg = if ($r.apiAvailable) { "Bridge ONLINE — host API: $api — port $($r.port)" } else { "Bridge ONLINE nhưng Antigravity host token API chưa khả dụng." }
        return [PSCustomObject]@{Ok=[bool]$r.apiAvailable;Message=$msg;Response=$r}
    } catch {
        return [PSCustomObject]@{Ok=$false;Message=$_.Exception.Message;Response=$null}
    }
}

function Get-TokenFingerprint {
    param([string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { return "" }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Token)
        $hash = $sha.ComputeHash($bytes)
        return (($hash | ForEach-Object { $_.ToString("x2") }) -join "").Substring(0,16)
    } finally { $sha.Dispose() }
}


function Test-AgSystemCredentialMatchesAccount {
    param([object]$Account)
    if(-not $Account){return $false}
    try{
        $snap=Get-AgCredentialSnapshot
        if(-not $snap.Exists -or [string]::IsNullOrWhiteSpace([string]$snap.Secret)){return $false}
        $j=([string]$snap.Secret)| ConvertFrom-Json
        $rt=[string]$j.token.refresh_token
        $at=[string]$j.token.access_token
        if([string]::IsNullOrWhiteSpace($rt)){return $false}
        # Compare refresh token exactly in-memory; never log it.
        if($rt -ne [string]$Account.RefreshToken){return $false}
        if($Account.AccessToken -and $at -and (Get-TokenFingerprint $at) -ne (Get-TokenFingerprint ([string]$Account.AccessToken))){
            # Access token can legitimately rotate; refresh-token match remains authoritative.
            return $true
        }
        return $true
    }catch{return $false}
}

function Wait-AgBridgeActiveAccount {
    param([string]$Email,[int]$Seconds=18)
    $deadline=(Get-Date).AddSeconds([Math]::Max(3,$Seconds))
    while((Get-Date) -lt $deadline){
        Start-Sleep -Milliseconds 700
        try{
            $a=Get-AgActiveAccountFromBridge
            if($a -and $a.Email.Trim().ToLowerInvariant() -eq $Email.Trim().ToLowerInvariant()){return $true}
        }catch{}
    }
    return $false
}

function Invoke-AgBridgeRollbackLast {
    try{
        $r=Invoke-AgBridge -Payload @{type="rollbackLast"} -TimeoutMs 8000
        if($r.success){return "Bridge host token đã rollback."}
        return "Bridge rollback không thành công: "+[string]$r.message
    }catch{
        return "Bridge rollback lỗi: "+$_.Exception.Message
    }
}

function Recover-AntigravitySession {
    $messages=[System.Collections.Generic.List[string]]::new()
    try{$messages.Add((Invoke-AgBridgeRollbackLast))}catch{}
    try{$messages.Add((Restore-AntigravityCredentialBackup))}catch{$messages.Add("Restore credential lỗi: "+$_.Exception.Message)}
    try{
        $c=Close-AntigravityGracefully
        $messages.Add($c.Message)
        if($c.Closed){
            Start-Sleep -Milliseconds 800
            $messages.Add((Start-AntigravityDesktop))
        }else{
            $messages.Add("Hãy đóng Antigravity thủ công rồi mở lại để credential gốc được nạp.")
        }
    }catch{$messages.Add("Restart recovery lỗi: "+$_.Exception.Message)}
    return ($messages -join " ")
}

function Get-AgCredentialSnapshot {
    $user=$null
    $secret=[HmsCredentialManager]::ReadGeneric("gemini:antigravity",[ref]$user)
    return [PSCustomObject]@{Exists=($null -ne $secret);User=$user;Secret=$secret}
}

function Restore-AgCredentialSnapshot {
    param([object]$Snapshot)
    if ($Snapshot -and $Snapshot.Exists) {
        [HmsCredentialManager]::WriteGeneric("gemini:antigravity",([string]$Snapshot.User),([string]$Snapshot.Secret))
        return $true
    }
    # If the credential did not exist before this transaction, deletion would be destructive.
    # Do not auto-delete; caller reports the residual credential instead.
    return $false
}

function Backup-AntigravityCredentialIfNeeded {
    if (Test-Path $script:AgCredentialBackup) { return }
    $user = $null
    $secret = [HmsCredentialManager]::ReadGeneric("gemini:antigravity", [ref]$user)
    $obj = [PSCustomObject]@{Exists=($null -ne $secret);User=$user;Secret=$secret}
    $raw = [Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json -Compress -Depth 4))
    $protected = [Security.Cryptography.ProtectedData]::Protect($raw,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    [IO.File]::WriteAllBytes($script:AgCredentialBackup,$protected)
}

function Restore-AntigravityCredentialBackup {
    if (-not (Test-Path $script:AgCredentialBackup)) { return "Không có snapshot Antigravity credential để khôi phục." }
    $enc = [IO.File]::ReadAllBytes($script:AgCredentialBackup)
    $raw = [Security.Cryptography.ProtectedData]::Unprotect($enc,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    $obj = ([Text.Encoding]::UTF8.GetString($raw) | ConvertFrom-Json)
    if ($obj.Exists) {
        [HmsCredentialManager]::WriteGeneric("gemini:antigravity",([string]$obj.User),([string]$obj.Secret))
        return "Đã khôi phục credential Antigravity trước HMS."
    }
    return "Snapshot cho biết trước đó không có credential; HMS không tự xóa credential hiện tại để tránh destructive action."
}

function Get-AgExpiryFromJson {
    param([object]$Json)
    if (-not $Json) { return $null }
    $v = Get-DeepValue $Json @("expired","expires_at","expiry","expires","expiration","expiresAt","expire_at")
    $dt = Convert-ToDateSafe $v
    if ($dt) { return $dt }
    $expiresIn = Get-DeepValue $Json @("expires_in","expiresIn")
    $timestamp = Get-DeepValue $Json @("timestamp","issued_at","created_at")
    try {
        if ($null -ne $expiresIn -and $null -ne $timestamp) {
            $sec = [double]$expiresIn
            $ts = [Int64]$timestamp
            if ($ts -gt 100000000000) { return [DateTimeOffset]::FromUnixTimeMilliseconds($ts).LocalDateTime.AddSeconds($sec) }
            return [DateTimeOffset]::FromUnixTimeSeconds($ts).LocalDateTime.AddSeconds($sec)
        }
    } catch {}
    return $null
}

function Get-QuotaPercentNumber {
    param([object]$Json,[string]$Raw)
    $v = Get-DeepValue $Json @("remainingFraction","remaining_fraction","quota_remaining","remaining_percent","quotaPercent")
    if ($null -ne $v) {
        try {
            $d=[double]$v
            if ($d -ge 0 -and $d -le 1.000001) { return [int][Math]::Round($d*100) }
            if ($d -ge 0 -and $d -le 100) { return [int][Math]::Round($d) }
        } catch {}
    }
    if ($Raw -match '"remainingFraction"\s*:\s*([0-9.]+)') {
        try { return [int][Math]::Round(([double]$matches[1])*100) } catch {}
    }
    return $null
}

function Get-AntigravityAccountRecords {
    $rows = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path $script:AuthDir)) { return @() }
    $files = @(Get-ChildItem $script:AuthDir -File -Filter "antigravity-*.json" -ErrorAction SilentlyContinue | Sort-Object Name)
    foreach ($f in $files) {
        try { $raw=[IO.File]::ReadAllText($f.FullName); $j=$raw| ConvertFrom-Json } catch { continue }
        $email = Get-DeepValue $j @("email","account_email","user_email","account")
        if (-not $email) { $email = Guess-EmailFromFilename $f.BaseName "Antigravity" }
        $access = Get-DeepValue $j @("access_token","accessToken")
        $refresh = Get-DeepValue $j @("refresh_token","refreshToken")
        $project = Get-DeepValue $j @("project_id","projectId")
        $expiry = Get-AgExpiryFromJson $j
        $runtime = Get-RuntimeCooldown $f
        $quotaPct = Get-QuotaPercentNumber $j $raw
        $status = "READY"
        if (-not $refresh) { $status="MISSING_REFRESH" }
        elseif ($runtime -like "Cooldown →*") { $status="COOLDOWN" }
        elseif ($expiry -and $expiry -lt (Get-Date).AddMinutes(-2)) { $status="TOKEN_EXPIRED" }
        $rows.Add([PSCustomObject]@{
            Email=[string]$email; AccessToken=[string]$access; RefreshToken=[string]$refresh;
            ProjectId=[string]$project; Expiry=$expiry; Status=$status; Runtime=$runtime;
            QuotaPercent=$quotaPct; FilePath=$f.FullName; FileName=$f.Name; Updated=$f.LastWriteTime
        })
    }
    return @($rows)
}

function Get-AntigravityAccountByEmail {
    param([string]$Email)
    $target=$Email.Trim().ToLowerInvariant()
    return @(Get-AntigravityAccountRecords | Where-Object { $_.Email.Trim().ToLowerInvariant() -eq $target } | Select-Object -First 1)[0]
}

function Write-AntigravitySystemCredential {
    param([object]$Account)
    Backup-AntigravityCredentialIfNeeded
    if (-not $Account.RefreshToken) { throw "ACC Antigravity thiếu refresh_token." }
    $expiry = $Account.Expiry
    if (-not $expiry) { $expiry=(Get-Date).AddHours(1) }
    $payload = [ordered]@{
        token = [ordered]@{
            access_token = [string]$Account.AccessToken
            token_type = "Bearer"
            refresh_token = [string]$Account.RefreshToken
            expiry = $expiry.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
        }
        auth_method = "consumer"
    } | ConvertTo-Json -Compress -Depth 5
    [HmsCredentialManager]::WriteGeneric("gemini:antigravity","antigravity",$payload)
}

function Add-AgSwitchLog {
    param([string]$From,[string]$To,[string]$Mode,[bool]$Success,[string]$Reason,[string]$Message)
    try {
        Ensure-Dir $script:DataDir
        $o=[ordered]@{time=(Get-Date).ToUniversalTime().ToString("o");from=$From;to=$To;mode=$Mode;success=$Success;reason=$Reason;message=$Message}
        [IO.File]::AppendAllText($script:AgSwitchLog,(($o| ConvertTo-Json -Compress)+"`r`n"),(New-Object Text.UTF8Encoding($false)))
    } catch {}
}

function Get-AgActiveAccountFromBridge {
    $t=Test-HmsAntigravityBridge
    if (-not $t.Response -or -not $t.Response.tokenFingerprint) { return $null }
    $fp=[string]$t.Response.tokenFingerprint
    foreach ($a in @(Get-AntigravityAccountRecords)) {
        if ($a.AccessToken -and (Get-TokenFingerprint $a.AccessToken) -eq $fp) { return $a }
    }
    return $null
}

function Switch-AntigravityAccount {
    param([string]$Email,[string]$Reason="manual")
    $acc=Get-AntigravityAccountByEmail $Email
    if (-not $acc) { throw "Không tìm thấy Antigravity ACC: $Email" }
    if (-not $acc.RefreshToken) { throw "ACC $Email thiếu refresh_token." }

    $activeBefore=Get-AgActiveAccountFromBridge
    $from=if($activeBefore){[string]$activeBefore.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{""}
    if($from -and $from.Trim().ToLowerInvariant() -eq $acc.Email.Trim().ToLowerInvariant()){
        return "Antigravity đã ở đúng ACC $($acc.Email), không cần switch."
    }

    # Transaction snapshot. IMPORTANT v0.7.1:
    # Seamless mode does NOT modify Windows Credential Manager before host verification.
    $beforeCredential=Get-AgCredentialSnapshot
    Backup-AntigravityCredentialIfNeeded

    if ([bool]$script:S.AgSeamlessEnabled -and $acc.AccessToken) {
        try {
            $expiry=$acc.Expiry
            if(-not $expiry){$expiry=(Get-Date).AddMinutes(55)}
            $epoch=[DateTimeOffset]$expiry
            $cmd=@{
                type="switch"; email=$acc.Email;
                token=@{
                    accessToken=$acc.AccessToken
                    refreshToken=$acc.RefreshToken
                    expiryDateSeconds=$epoch.ToUnixTimeSeconds()
                }
                transactional=$true
            }

            $r=Invoke-AgBridge -Payload $cmd -TimeoutMs 14000
            if ($r.success) {
                $verificationSupported = ($null -ne $r.verificationSupported) -and [bool]$r.verificationSupported
                $verified = ($null -ne $r.verified) -and [bool]$r.verified
                $rolledBack = ($null -ne $r.rolledBack) -and [bool]$r.rolledBack

                if($rolledBack){
                    $bridgeError="Bridge đã tự rollback token host vì xác minh thất bại."
                } elseif([bool]$script:S.AgRequireVerifiedReadback -and $verificationSupported -and -not $verified){
                    $bridgeError="Readback fingerprint không khớp. Bridge phải rollback; HMS không xác nhận ACC mới."
                    $null=Invoke-AgBridgeRollbackLast
                } else {
                    # Do not write gemini:antigravity in seamless mode by default.
                    # Antigravity host API owns the live token state; this avoids invalidating its persistent session.
                    if(-not [bool]$script:S.AgSeamlessHostOnly){
                        Write-AntigravitySystemCredential $acc
                        if(-not (Test-AgSystemCredentialMatchesAccount $acc)){
                            $null=Restore-AgCredentialSnapshot $beforeCredential
                            $null=Invoke-AgBridgeRollbackLast
                            throw "Không xác minh được persistent system credential; đã rollback cả host và Credential Manager."
                        }
                    }

                    $script:S.AgCurrentEmail=$acc.Email
                    Save-Settings
                    $verifyText=if($verificationSupported){if($verified){"verified"}else{"unverified"}}else{"readback-n/a"}
                    $persistText=if([bool]$script:S.AgSeamlessHostOnly){"host-only"}else{"host+system"}
                    Add-AgSwitchLog $from $acc.Email "seamless-transactional" $true $Reason ("hostApi="+[string]$r.hostApi+"; "+$verifyText+"; "+$persistText)
                    return "Antigravity seamless an toàn: $from → $($acc.Email) qua $($r.hostApi), không restart ($verifyText, $persistText)."
                }
            } else {
                $bridgeError=[string]$r.message
            }
        } catch {
            $bridgeError=$_.Exception.Message
        }

        # Since seamless mode did not touch Windows Credential Manager, only host rollback is needed.
        $rb=Invoke-AgBridgeRollbackLast
        if (-not [bool]$script:S.AgFallbackRestart) {
            Add-AgSwitchLog $from $acc.Email "seamless-transactional" $false $Reason ($bridgeError+"; "+$rb)
            throw ("Seamless switch thất bại: "+$bridgeError+". "+$rb)
        }
    }

    if (-not [bool]$script:S.AgFallbackRestart) {
        throw "Seamless không khả dụng và fallback restart đang tắt."
    }

    # Restart fallback is the only path that writes the persistent Windows credential.
    # Write + readback BEFORE closing Antigravity.
    try{
        Write-AntigravitySystemCredential $acc
        if(-not (Test-AgSystemCredentialMatchesAccount $acc)){
            $null=Restore-AgCredentialSnapshot $beforeCredential
            throw "Credential Manager write/readback không khớp; đã rollback trước khi đóng Antigravity."
        }
    }catch{
        $null=Restore-AgCredentialSnapshot $beforeCredential
        Add-AgSwitchLog $from $acc.Email "restart-fallback" $false $Reason ("persistent credential preflight failed: "+$_.Exception.Message)
        throw
    }

    $close=Close-AntigravityGracefully
    if (-not $close.Closed) {
        $null=Restore-AgCredentialSnapshot $beforeCredential
        throw $close.Message+" Credential đã rollback. Antigravity chưa bị đổi phiên."
    }

    Start-Sleep -Milliseconds 700
    $open=Start-AntigravityDesktop

    # Verify after restart. If new account is not observed, restore original persistent credential
    # and optionally reopen original session instead of leaving the user at a login screen.
    $verifiedRestart=Wait-AgBridgeActiveAccount -Email $acc.Email -Seconds ([int]$script:S.AgRestartVerifySeconds)
    if(-not $verifiedRestart){
        $restored=Restore-AgCredentialSnapshot $beforeCredential
        $msg="Fallback restart không xác minh được ACC mới."
        if($restored){$msg+=" Credential cũ đã được restore."}
        if([bool]$script:S.AgAutoRecoveryOnRestartFailure -and $restored){
            try{
                $c2=Close-AntigravityGracefully
                if($c2.Closed){
                    Start-Sleep -Milliseconds 700
                    $null=Start-AntigravityDesktop
                    $msg+=" Đã mở lại phiên cũ tự động."
                }
            }catch{}
        }
        Add-AgSwitchLog $from $acc.Email "restart-fallback" $false $Reason $msg
        throw $msg
    }

    $script:S.AgCurrentEmail=$acc.Email
    Save-Settings
    Add-AgSwitchLog $from $acc.Email "restart-fallback-verified" $true $Reason $open
    return "Đã chuyển AG ACC bằng fallback restart và xác minh PASS: $from → $($acc.Email). $open"
}

function Get-AgAccountHealth {
    param([object]$Account)
    if (-not $Account) {
        return [PSCustomObject]@{Score=0;Grade="F";Reason="Không có dữ liệu";QuotaKnown=$false}
    }

    $score = 55
    $reasons = [System.Collections.Generic.List[string]]::new()

    switch ([string]$Account.Status) {
        "READY" { $score += 20; $reasons.Add("READY") }
        "COOLDOWN" { $score -= 65; $reasons.Add("cooldown") }
        "MISSING_REFRESH" { $score = 0; $reasons.Add("thiếu refresh token") }
        "TOKEN_EXPIRED" { $score -= 35; $reasons.Add("access token cũ") }
        default { $score -= 25; $reasons.Add("status="+[string]$Account.Status) }
    }

    $quotaKnown = $null -ne $Account.QuotaPercent
    if ($quotaKnown) {
        $q = [Math]::Max(0,[Math]::Min(100,[int]$Account.QuotaPercent))
        # Quota is the biggest positive signal.
        $score += [int][Math]::Round(($q - 50) * 0.55)
        $reasons.Add("quota=$q%")
        if ($q -le [int]$script:S.AgAutoSwitchThreshold) { $score -= 18 }
    } else {
        $reasons.Add("quota chưa rõ")
    }

    if ($Account.Expiry) {
        $minutes = ($Account.Expiry - (Get-Date)).TotalMinutes
        if ($minutes -lt -2) { $score -= 25; $reasons.Add("token hết hạn") }
        elseif ($minutes -lt 10) { $score -= 8; $reasons.Add("token sắp refresh") }
        elseif ($minutes -gt 30) { $score += 5 }
    }

    if ([string]$Account.Runtime -like "Cooldown →*") { $score -= 25 }
    $score = [Math]::Max(0,[Math]::Min(100,$score))
    $grade = if($score -ge 85){"A"}elseif($score -ge 70){"B"}elseif($score -ge 55){"C"}elseif($score -ge 35){"D"}else{"F"}

    return [PSCustomObject]@{
        Score=[int]$score
        Grade=$grade
        Reason=($reasons -join " · ")
        QuotaKnown=$quotaKnown
    }
}

function Get-AgRankedAccounts {
    param([string]$CurrentEmail="")
    $items = [System.Collections.Generic.List[object]]::new()
    foreach($a in @(Get-AntigravityAccountRecords)){
        $h = Get-AgAccountHealth $a
        $items.Add([PSCustomObject]@{
            Email=$a.Email
            Status=$a.Status
            QuotaPercent=$a.QuotaPercent
            HealthScore=$h.Score
            Grade=$h.Grade
            HealthReason=$h.Reason
            Expiry=$a.Expiry
            Runtime=$a.Runtime
            ProjectId=$a.ProjectId
            IsCurrent=((-not [string]::IsNullOrWhiteSpace($CurrentEmail)) -and ($a.Email.Trim().ToLowerInvariant() -eq $CurrentEmail.Trim().ToLowerInvariant()))
            Account=$a
        })
    }
    return @($items | Sort-Object @{Expression={$_.HealthScore};Descending=$true}, @{Expression={ if($null -ne $_.QuotaPercent){[int]$_.QuotaPercent}else{-1} };Descending=$true}, Email)
}

function Get-AgSwitchHistory {
    param([int]$Max=200)
    if(-not (Test-Path $script:AgSwitchLog)){return @()}
    $lines=@(Get-Content $script:AgSwitchLog -Tail ([Math]::Max(1,$Max)) -Encoding UTF8 -ErrorAction SilentlyContinue)
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($line in $lines){
        if([string]::IsNullOrWhiteSpace($line)){continue}
        try{
            $j=$line| ConvertFrom-Json
            $dt=Convert-ToDateSafe $j.time
            $rows.Add([PSCustomObject]@{
                Time=if($dt){$dt.ToString("dd/MM HH:mm:ss")}else{[string]$j.time}
                From=[string]$j.from
                To=[string]$j.to
                Mode=[string]$j.mode
                Success=[bool]$j.success
                Reason=[string]$j.reason
                Message=[string]$j.message
            })
        }catch{}
    }
    return @($rows | Sort-Object Time -Descending)
}

function Show-AgSwitchHistory {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Antigravity — Lịch sử chuyển tài khoản"
    $w.Size=New-Object Drawing.Size(1120,560)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(18,20,24)
    $w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5)

    $grid=New-Object Windows.Forms.DataGridView
    $grid.Location=New-Object Drawing.Point(18,18);$grid.Size=New-Object Drawing.Size(1065,450)
    $grid.ReadOnly=$true;$grid.AllowUserToAddRows=$false;$grid.AllowUserToDeleteRows=$false;$grid.RowHeadersVisible=$false
    $grid.AutoSizeColumnsMode="Fill";$grid.SelectionMode="FullRowSelect"
    $grid.BackgroundColor=[Drawing.Color]::FromArgb(24,27,32);$grid.GridColor=[Drawing.Color]::FromArgb(55,61,70)
    $grid.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(37,42,49);$grid.ColumnHeadersDefaultCellStyle.ForeColor=[Drawing.Color]::White
    $grid.EnableHeadersVisualStyles=$false
    $grid.DefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(24,27,32);$grid.DefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(230,234,239)
    $grid.DefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(55,72,86);$grid.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    $grid.DataSource=@(Get-AgSwitchHistory -Max ([int]$script:S.AgSwitchHistoryMax))
    $w.Controls.Add($grid)

    $b=Btn "LÀM MỚI" 18 482 150 34;$w.Controls.Add($b)
    $b.Add_Click({$grid.DataSource=$null;$grid.DataSource=@(Get-AgSwitchHistory -Max ([int]$script:S.AgSwitchHistoryMax))})
    [void]$w.ShowDialog($form)
}

function Show-AgSmartPool {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Antigravity Smart Pool"
    $w.Size=New-Object Drawing.Size(1180,650)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(18,20,24)
    $w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5)

    $top=New-Object Windows.Forms.Label
    $top.Text="ANTIGRAVITY SMART POOL"
    $top.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$top.AutoSize=$true;$top.Location=New-Object Drawing.Point(18,14);$w.Controls.Add($top)
    $sum=New-Object Windows.Forms.Label
    $sum.Location=New-Object Drawing.Point(20,50);$sum.Size=New-Object Drawing.Size(1120,45);$sum.ForeColor=[Drawing.Color]::FromArgb(155,166,178);$w.Controls.Add($sum)

    $grid=New-Object Windows.Forms.DataGridView
    $grid.Location=New-Object Drawing.Point(20,95);$grid.Size=New-Object Drawing.Size(1120,410)
    $grid.ReadOnly=$true;$grid.AllowUserToAddRows=$false;$grid.AllowUserToDeleteRows=$false;$grid.RowHeadersVisible=$false
    $grid.AutoSizeColumnsMode="Fill";$grid.SelectionMode="FullRowSelect";$grid.MultiSelect=$false
    $grid.BackgroundColor=[Drawing.Color]::FromArgb(24,27,32);$grid.GridColor=[Drawing.Color]::FromArgb(55,61,70)
    $grid.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(37,42,49);$grid.ColumnHeadersDefaultCellStyle.ForeColor=[Drawing.Color]::White;$grid.EnableHeadersVisualStyles=$false
    $grid.DefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(24,27,32);$grid.DefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(230,234,239)
    $grid.DefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(55,72,86);$grid.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    $w.Controls.Add($grid)

    $bRefresh=Btn "LÀM MỚI" 20 523 130 38;$w.Controls.Add($bRefresh)
    $bSwitch=Btn "CHUYỂN ACC ĐÃ CHỌN" 165 523 200 38;$bSwitch.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bSwitch)
    $bBest=Btn "CHUYỂN SANG ACC TỐT NHẤT" 380 523 230 38;$w.Controls.Add($bBest)
    $bHistory=Btn "LỊCH SỬ SWITCH" 625 523 165 38;$w.Controls.Add($bHistory)
    $bBridge=Btn "TEST BRIDGE" 805 523 145 38;$w.Controls.Add($bBridge)
    $bDiag2=Btn "DIAGNOSTICS" 965 523 175 38;$w.Controls.Add($bDiag2)

    $note=New-Object Windows.Forms.Label
    $note.Text="Health Score 0–100 tổng hợp trạng thái credential, cooldown, hạn token và quota khi có. Auto-switch chỉ đổi khi candidate đủ tốt hơn để hạn chế ping-pong."
    $note.Location=New-Object Drawing.Point(20,575);$note.Size=New-Object Drawing.Size(1110,38);$note.ForeColor=[Drawing.Color]::FromArgb(130,142,155);$w.Controls.Add($note)

    function Refresh-Smart {
        $active=Get-AgActiveAccountFromBridge
        $current=if($active){$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{""}
        $rows=@(Get-AgRankedAccounts -CurrentEmail $current | ForEach-Object {
            [PSCustomObject]@{
                Current=if($_.IsCurrent){"●"}else{""}
                Email=$_.Email
                Status=$_.Status
                Quota=if($null -ne $_.QuotaPercent){([string]$_.QuotaPercent+"%")}else{"—"}
                Score=$_.HealthScore
                Grade=$_.Grade
                Reason=$_.HealthReason
                Expiry=if($_.Expiry){$_.Expiry.ToString("dd/MM HH:mm")}else{"—"}
                Runtime=if($_.Runtime){$_.Runtime}else{"—"}
                Project=$_.ProjectId
            }
        })
        $grid.DataSource=$null;$grid.DataSource=$rows
        $best=@(Get-AgRankedAccounts -CurrentEmail $current | Where-Object {-not $_.IsCurrent} | Select-Object -First 1)
        $bestText=if($best.Count -gt 0){"$($best[0].Email) — score $($best[0].HealthScore)"}else{"không có"}
        $sum.Text="ACC hiện tại: "+$(if($current){$current}else{"chưa xác định"})+"    |    ACC tốt nhất dự phòng: $bestText`r`nNgưỡng auto-switch: $($script:S.AgAutoSwitchThreshold)% · Candidate min quota: $($script:S.AgCandidateMinQuota)% · Min score improvement: $($script:S.AgMinScoreImprovement)"
    }

    $bRefresh.Add_Click({Refresh-Smart})
    $bSwitch.Add_Click({
        try{
            if($grid.SelectedRows.Count -lt 1){throw "Hãy chọn một ACC."}
            $email=[string]$grid.SelectedRows[0].Cells["Email"].Value
            if(-not $email){throw "Không đọc được email ACC."}
            $m=Switch-AntigravityAccount -Email $email -Reason "manual-smart-pool"
            [Windows.Forms.MessageBox]::Show($m,"Antigravity Switch")|Out-Null
            Refresh-Smart
        }catch{Err $_.Exception.Message}
    })
    $bBest.Add_Click({
        try{
            $active=Get-AgActiveAccountFromBridge
            $current=if($active){$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{""}
            $best=Get-BestAgCandidate $current
            if(-not $best){throw "Không có ACC dự phòng đủ điều kiện theo Smart Score."}
            $m=Switch-AntigravityAccount -Email $best.Email -Reason "manual-best-candidate"
            [Windows.Forms.MessageBox]::Show($m,"Antigravity Smart Switch")|Out-Null
            Refresh-Smart
        }catch{Err $_.Exception.Message}
    })
    $bHistory.Add_Click({Show-AgSwitchHistory})
    $bBridge.Add_Click({$r=Test-HmsAntigravityBridge;[Windows.Forms.MessageBox]::Show($r.Message,"HMS AG Bridge")|Out-Null;Refresh-Smart})
    $bDiag2.Add_Click({try{[Windows.Forms.MessageBox]::Show((Get-HmsDiagnosticsText),"HMS Diagnostics")|Out-Null}catch{Err $_.Exception.Message}})
    $w.Add_Shown({Refresh-Smart})
    [void]$w.ShowDialog($form)
}

function Get-HmsDiagnosticsText {
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add("HMS-AI-ROUTER v$($script:Version) — Diagnostics")
    $lines.Add("")

    $agInfo=Get-AntigravityInstalledInfo
    $lines.Add("Antigravity installed: "+$(if($agInfo.Found){"YES  v"+$agInfo.Version}else{"NO"}))
    if($agInfo.Found){$lines.Add("Antigravity path: "+$agInfo.Path)}

    $bridge=Test-HmsAntigravityBridge
    $lines.Add("Bridge: "+$(if($bridge.Ok){"PASS"}else{"WARN"})+" — "+$bridge.Message)
    if($bridge.Response){
        if($bridge.Response.uptimeSec -ne $null){$lines.Add("Bridge uptime: "+[string]$bridge.Response.uptimeSec+"s")}
        if($bridge.Response.vscodeVersion){$lines.Add("Host VS Code API: "+[string]$bridge.Response.vscodeVersion)}
    }

    $active=Get-AgActiveAccountFromBridge
    $current=if($active){$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{""}
    $ranked=@(Get-AgRankedAccounts -CurrentEmail $current)
    $lines.Add("AG pool: "+$ranked.Count+" account(s)")
    $lines.Add("AG current: "+$(if($current){$current}else{"unknown"}))
    if($ranked.Count -gt 0){
        $best=@($ranked|Where-Object{-not $_.IsCurrent}| Select-Object -First 1)
        if($best.Count -gt 0){$lines.Add("Best reserve: $($best[0].Email) / score $($best[0].HealthScore) / quota "+$(if($null -ne $best[0].QuotaPercent){[string]$best[0].QuotaPercent+"%"}else{"unknown"}))}
    }

    $port=[int]$script:S.ProxyPort
    $procId=ListenerPid $port
    if($procId -gt 0){
        $lines.Add("CLIProxyAPI port ${port}: LISTENING PID $procId"+$(if(IsOurProxy $procId){" (HMS managed exe)"}else{" (foreign/Cockpit-safe)"}))
    }else{$lines.Add("CLIProxyAPI port ${port}: OFFLINE")}

    $api=Test-ApiModels
    $lines.Add("Codex local API: "+$(if($api.Ok){"PASS — "+$api.Count+" models"}else{"WARN — "+$api.Error}))
    $lines.Add("Codex provider mode: "+$(if(CodexInHmsMode){"HMS API MODE"}else{"Cockpit/direct/other"}))
    $lines.Add("Codex OAuth files: "+(AuthCount "codex-"))
    $lines.Add("Antigravity OAuth files: "+(AuthCount "antigravity-"))
    $lines.Add("")
    $lines.Add("Safety: không hiển thị raw token; không kill foreign listener; AG fallback restart="+[string]$script:S.AgFallbackRestart)
    return ($lines -join "`r`n")
}


function Get-BestAgCandidate {
    param([string]$CurrentEmail)
    $current=if($CurrentEmail){Get-AntigravityAccountByEmail $CurrentEmail}else{$null}
    $currentScore=if($current){(Get-AgAccountHealth $current).Score}else{0}
    $minImprove=[int]$script:S.AgMinScoreImprovement
    $minQuota=[int]$script:S.AgCandidateMinQuota

    foreach($r in @(Get-AgRankedAccounts -CurrentEmail $CurrentEmail)){
        if($r.IsCurrent -or $r.Status -ne "READY"){continue}
        if($null -ne $r.QuotaPercent -and [int]$r.QuotaPercent -lt $minQuota){continue}
        if($current -and $current.Status -eq "READY" -and ([int]$r.HealthScore -lt ($currentScore+$minImprove))){continue}
        if([int]$r.HealthScore -lt 45){continue}
        return $r.Account
    }
    return $null
}

function Invoke-AgAutoSwitchCheck {
    if (-not [bool]$script:S.AgAutoSwitchEnabled) { return $null }
    $now=[DateTime]::UtcNow
    if ($script:S.AgLastAutoSwitchUtc) {
        try {
            $last=[DateTime]::Parse([string]$script:S.AgLastAutoSwitchUtc).ToUniversalTime()
            if (($now-$last).TotalSeconds -lt [int]$script:S.AgAutoSwitchCooldownSec) { return $null }
        } catch {}
    }
    $active=Get-AgActiveAccountFromBridge
    if(-not $active -and $script:S.AgCurrentEmail){$active=Get-AntigravityAccountByEmail ([string]$script:S.AgCurrentEmail)}
    if(-not $active){return $null}
    $trigger=$false
    $why=""
    if($active.Status -ne "READY"){$trigger=$true;$why="status=$($active.Status)"}
    elseif($null -ne $active.QuotaPercent -and [int]$active.QuotaPercent -le [int]$script:S.AgAutoSwitchThreshold){$trigger=$true;$why="quota=$($active.QuotaPercent)%"}
    if(-not $trigger){return $null}
    $candidate=Get-BestAgCandidate $active.Email
    if(-not $candidate){return "AutoSwitch: $why nhưng Smart Pool chưa có ACC dự phòng đủ khỏe/đủ chênh lệch điểm."}
    $msg=Switch-AntigravityAccount -Email $candidate.Email -Reason ("auto:"+$why)
    $script:S.AgLastAutoSwitchUtc=$now.ToString("o");Save-Settings
    return "AutoSwitch: $msg"
}



# ---------------- Account monitor ----------------

function Get-DeepValue {
    param(
        [object]$Object,
        [string[]]$Names,
        [int]$Depth = 0
    )
    if ($null -eq $Object -or $Depth -gt 6) { return $null }

    if ($Object -is [string] -or $Object -is [ValueType]) { return $null }

    if ($Object -is [System.Collections.IDictionary]) {
        foreach ($n in $Names) {
            foreach ($k in $Object.Keys) {
                if (([string]$k).Equals($n, [StringComparison]::OrdinalIgnoreCase)) {
                    return $Object[$k]
                }
            }
        }
        foreach ($k in $Object.Keys) {
            $v = Get-DeepValue -Object $Object[$k] -Names $Names -Depth ($Depth + 1)
            if ($null -ne $v) { return $v }
        }
        return $null
    }

    if ($Object -is [System.Collections.IEnumerable] -and -not ($Object -is [string])) {
        foreach ($item in $Object) {
            $v = Get-DeepValue -Object $item -Names $Names -Depth ($Depth + 1)
            if ($null -ne $v) { return $v }
        }
        return $null
    }

    $props = @($Object.PSObject.Properties)
    foreach ($n in $Names) {
        foreach ($p in $props) {
            if ($p.Name.Equals($n, [StringComparison]::OrdinalIgnoreCase)) {
                return $p.Value
            }
        }
    }
    foreach ($p in $props) {
        $v = Get-DeepValue -Object $p.Value -Names $Names -Depth ($Depth + 1)
        if ($null -ne $v) { return $v }
    }
    return $null
}

function Decode-JwtPayload {
    param([string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { return $null }
    $parts = $Token.Split('.')
    if ($parts.Count -lt 2) { return $null }
    try {
        $s = $parts[1].Replace('-','+').Replace('_','/')
        switch ($s.Length % 4) {
            2 { $s += '==' }
            3 { $s += '=' }
        }
        $bytes = [Convert]::FromBase64String($s)
        $json = [Text.Encoding]::UTF8.GetString($bytes)
        return ($json | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Convert-ToDateSafe {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    try {
        if ($Value -is [DateTime]) { return [DateTime]$Value }

        $s = ([string]$Value).Trim()
        if ($s -match '^\d{10,13}$') {
            $n = [Int64]$s
            if ($s.Length -ge 13) {
                return [DateTimeOffset]::FromUnixTimeMilliseconds($n).LocalDateTime
            }
            return [DateTimeOffset]::FromUnixTimeSeconds($n).LocalDateTime
        }

        $dt = [DateTime]::MinValue
        if ([DateTime]::TryParse($s, [ref]$dt)) { return $dt }
    } catch {}
    return $null
}

function Short-Value {
    param([object]$Value, [int]$Max = 60)
    if ($null -eq $Value) { return "" }
    try {
        if ($Value -is [string] -or $Value -is [ValueType]) {
            $s = [string]$Value
        } else {
            $s = ($Value | ConvertTo-Json -Compress -Depth 3)
        }
    } catch {
        $s = [string]$Value
    }
    $s = $s.Replace("`r"," ").Replace("`n"," ").Trim()
    if ($s.Length -gt $Max) { return $s.Substring(0,$Max-3) + "..." }
    return $s
}

function Get-QuotaText {
    param([object]$Json, [string]$Raw)
    $v = Get-DeepValue $Json @("remainingFraction","remaining_fraction","quota_remaining","remaining","remaining_percent","quotaPercent")
    if ($null -ne $v) {
        try {
            $d = [double]$v
            if ($d -ge 0 -and $d -le 1.000001) { return ("{0:N0}%" -f ($d * 100)) }
            if ($d -ge 0 -and $d -le 100) { return ("{0:N0}%" -f $d) }
        } catch {}
        return (Short-Value $v 35)
    }
    $q = Get-DeepValue $Json @("quota","usage_limit","limits")
    if ($null -ne $q) { return (Short-Value $q 35) }

    if ($Raw -match '"remainingFraction"\s*:\s*([0-9.]+)') {
        try { return ("{0:N0}%" -f ([double]$matches[1] * 100)) } catch {}
    }
    return "—"
}

function Get-RuntimeCooldown {
    param([IO.FileInfo]$AuthFile)

    $candidates = @(
        ($AuthFile.FullName + ".cds"),
        ([IO.Path]::ChangeExtension($AuthFile.FullName, ".cds"))
    ) | Select-Object -Unique

    foreach ($p in $candidates) {
        if (-not (Test-Path $p)) { continue }
        try {
            $raw = [IO.File]::ReadAllText($p)
            $j = $null
            try { $j = $raw | ConvertFrom-Json } catch {}

            $nr = Get-DeepValue $j @("next_retry_after","nextRetryAfter","retry_after","retryAfter","cooldown_until","cooldownUntil")
            if ($null -ne $nr) {
                $dt = Convert-ToDateSafe $nr
                if ($dt) {
                    if ($dt -gt (Get-Date)) { return "Cooldown → " + $dt.ToString("dd/MM HH:mm") }
                    return "Cooldown đã hết"
                }
                return "Cooldown: " + (Short-Value $nr 30)
            }

            if ($raw -match '(?i)cooldown|quota|429|exhaust') {
                return "Có runtime state"
            }
        } catch {}
    }
    return ""
}

function Guess-EmailFromFilename {
    param([string]$BaseName, [string]$Provider)
    $s = $BaseName
    if ($Provider -eq "Codex") {
        if ($s -match '^codex-[^-]+-(.+)-(free|plus|pro|team|business|enterprise)$') {
            return $matches[1]
        }
        $s = $s -replace '^codex-',''
    } elseif ($Provider -eq "Antigravity") {
        $s = $s -replace '^antigravity-',''
    }
    if ($s -match '([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})') {
        return $matches[1]
    }
    return $s
}

function Get-AuthAccountRows {
    $rows = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path $script:AuthDir)) { return @() }

    $files = @(Get-ChildItem $script:AuthDir -File -Filter "*.json" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "codex-*.json" -or $_.Name -like "antigravity-*.json" } |
        Sort-Object Name)

    foreach ($f in $files) {
        $provider = if ($f.Name -like "codex-*") { "Codex" } else { "Antigravity" }
        $raw = ""
        $j = $null
        $parseError = $false
        try {
            $raw = [IO.File]::ReadAllText($f.FullName)
            $j = $raw | ConvertFrom-Json
        } catch {
            $parseError = $true
        }

        $jwt = $null
        if ($j) {
            $idToken = Get-DeepValue $j @("id_token","idToken")
            if ($idToken -is [string]) { $jwt = Decode-JwtPayload $idToken }
        }

        $email = $null
        if ($j) { $email = Get-DeepValue $j @("email","account_email","user_email","account") }
        if (-not $email -and $jwt) { $email = Get-DeepValue $jwt @("email","preferred_username","upn") }
        if (-not $email) { $email = Guess-EmailFromFilename $f.BaseName $provider }
        $email = Short-Value $email 52

        $plan = $null
        if ($j) { $plan = Get-DeepValue $j @("plan_type","plan","subscription_type","subscription","tier","account_type") }
        if (-not $plan -and $jwt) { $plan = Get-DeepValue $jwt @("plan_type","plan","subscription","chatgpt_plan_type") }
        if (-not $plan -and $provider -eq "Codex" -and $f.BaseName -match '-(free|plus|pro|team|business|enterprise)$') {
            $plan = $matches[1]
        }
        if (-not $plan) { $plan = "—" }
        $plan = (Short-Value $plan 24).ToUpperInvariant()

        $project = $null
        if ($j) { $project = Get-DeepValue $j @("project_id","projectId","organization_id","organizationId","org_id","orgId") }
        if (-not $project -and $jwt) { $project = Get-DeepValue $jwt @("organization_id","org_id") }
        if (-not $project) { $project = "—" }
        $project = Short-Value $project 32

        $expiryVal = $null
        if ($j) { $expiryVal = Get-DeepValue $j @("expired","expires_at","expiry","expires","expiration","expiresAt","expire_at") }
        $expiry = Convert-ToDateSafe $expiryVal
        if (-not $expiry -and $jwt) {
            $jwtExp = Get-DeepValue $jwt @("exp")
            $expiry = Convert-ToDateSafe $jwtExp
        }

        $disabled = $false
        $unavailable = $false
        $nativeStatus = ""
        if ($j) {
            $d = Get-DeepValue $j @("disabled")
            $u = Get-DeepValue $j @("unavailable")
            $st = Get-DeepValue $j @("status","state")
            try { $disabled = [bool]$d } catch {}
            try { $unavailable = [bool]$u } catch {}
            if ($st) { $nativeStatus = Short-Value $st 26 }
        }

        $runtime = Get-RuntimeCooldown $f
        if ($parseError) {
            $status = "LỖI FILE"
        } elseif ($disabled) {
            $status = "DISABLED"
        } elseif ($unavailable) {
            $status = "UNAVAILABLE"
        } elseif ($expiry -and $expiry -lt (Get-Date)) {
            $status = "TOKEN HẾT HẠN"
        } elseif ($runtime -like "Cooldown →*") {
            $status = "COOLDOWN"
        } elseif ($nativeStatus -and $nativeStatus -notmatch '^(ok|active|ready)$') {
            $status = $nativeStatus.ToUpperInvariant()
        } else {
            $status = "READY"
        }

        $quota = Get-QuotaText $j $raw
        $reset = ""
        if ($j) {
            $rv = Get-DeepValue $j @("resetTime","reset_time","quota_reset","reset_at")
            $rd = Convert-ToDateSafe $rv
            if ($rd) { $reset = $rd.ToString("dd/MM HH:mm") }
            elseif ($rv) { $reset = Short-Value $rv 28 }
        }
        if (-not $reset -and $runtime) { $reset = $runtime }
        if (-not $reset) { $reset = "—" }

        $expiryText = if ($expiry) { $expiry.ToString("dd/MM/yyyy HH:mm") } else { "—" }

        $healthScore = "—"
        $healthGrade = "—"
        if($provider -eq "Antigravity"){
            $agRec = Get-AntigravityAccountByEmail $email
            if($agRec){
                $hh=Get-AgAccountHealth $agRec
                $healthScore=[string]$hh.Score
                $healthGrade=[string]$hh.Grade
            }
        }

        $rows.Add([PSCustomObject]@{
            Provider = $provider
            Account = $email
            Plan = $plan
            Status = $status
            Health = $healthScore
            Grade = $healthGrade
            TokenExpiry = $expiryText
            ProjectOrg = $project
            Quota = $quota
            ResetCooldown = $reset
            Updated = $f.LastWriteTime.ToString("dd/MM HH:mm:ss")
            FileName = $f.Name
        })
    }
    return @($rows)
}

function Show-AccountMonitor {
    $w = New-Object Windows.Forms.Form
    $w.Text = "HMS Account Center — Codex + Antigravity 2.0"
    $w.Size = New-Object Drawing.Size(1260,680)
    $w.StartPosition = "CenterParent"
    $w.BackColor = [Drawing.Color]::FromArgb(18,20,24)
    $w.ForeColor = [Drawing.Color]::FromArgb(236,239,244)
    $w.Font = New-Object Drawing.Font("Segoe UI",9.5)

    $top = New-Object Windows.Forms.Label
    $top.Text = "ACCOUNT CENTER"
    $top.Font = New-Object Drawing.Font("Segoe UI Semibold",17)
    $top.AutoSize = $true
    $top.Location = New-Object Drawing.Point(18,15)
    $w.Controls.Add($top)

    $sum = New-Object Windows.Forms.Label
    $sum.Location = New-Object Drawing.Point(20,51)
    $sum.Size = New-Object Drawing.Size(1200,52)
    $sum.ForeColor = [Drawing.Color]::FromArgb(155,166,178)
    $w.Controls.Add($sum)

    $grid = New-Object Windows.Forms.DataGridView
    $grid.Location = New-Object Drawing.Point(20,105)
    $grid.Size = New-Object Drawing.Size(1200,410)
    $grid.ReadOnly = $true;$grid.AllowUserToAddRows=$false;$grid.AllowUserToDeleteRows=$false;$grid.AllowUserToResizeRows=$false
    $grid.RowHeadersVisible=$false;$grid.AutoSizeColumnsMode="Fill";$grid.SelectionMode="FullRowSelect";$grid.MultiSelect=$false
    $grid.BackgroundColor=[Drawing.Color]::FromArgb(24,27,32);$grid.GridColor=[Drawing.Color]::FromArgb(55,61,70)
    $grid.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(37,42,49);$grid.ColumnHeadersDefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(238,241,245)
    $grid.ColumnHeadersDefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(37,42,49);$grid.EnableHeadersVisualStyles=$false
    $grid.DefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(24,27,32);$grid.DefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(230,234,239)
    $grid.DefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(55,72,86);$grid.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    $w.Controls.Add($grid)

    $bRefresh=Btn "LÀM MỚI" 20 532 135 38;$w.Controls.Add($bRefresh)
    $bSwitch=Btn "CHUYỂN AG ACC" 170 532 170 38;$bSwitch.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bSwitch)
    $bBridge=Btn "TEST AG BRIDGE" 355 532 165 38;$w.Controls.Add($bBridge)
    $bQuota2=Btn "MỞ QUOTA" 535 532 140 38;$w.Controls.Add($bQuota2)
    $bCodex2=Btn "＋ CODEX ACC" 690 532 150 38;$w.Controls.Add($bCodex2)
    $bAg2=Btn "＋ AG ACC" 855 532 135 38;$w.Controls.Add($bAg2)
    $bFolder2=Btn "MỞ AUTH" 1005 532 120 38;$w.Controls.Add($bFolder2)

    $auto = New-Object Windows.Forms.CheckBox
    $auto.Text="Tự refresh 10 giây";$auto.Checked=$true;$auto.AutoSize=$true;$auto.Location=New-Object Drawing.Point(20,585);$auto.ForeColor=$w.ForeColor;$w.Controls.Add($auto)

    $note=New-Object Windows.Forms.Label
    $note.Text="AG seamless: tool ghi credential hệ thống + HMS Bridge cập nhật token ngay trong host Antigravity. Không hiển thị access/refresh token. Nếu Bridge lỗi, fallback restart chỉ chạy khi bạn bật tùy chọn."
    $note.Location=New-Object Drawing.Point(200,580);$note.Size=New-Object Drawing.Size(1020,48);$note.ForeColor=[Drawing.Color]::FromArgb(130,142,155);$w.Controls.Add($note)

    function Refresh-Grid {
        $rows=@(Get-AuthAccountRows)
        $grid.DataSource=$null;$grid.DataSource=$rows
        if($grid.Columns.Count -gt 0){
            $headers=@{Provider="Provider";Account="Tài khoản";Plan="Gói";Status="Trạng thái";Health="Health";Grade="Hạng";TokenExpiry="Hạn token";ProjectOrg="Project / Org";Quota="Quota";ResetCooldown="Reset / Cooldown";Updated="Cập nhật";FileName="Auth file"}
            foreach($c in $grid.Columns){if($headers.ContainsKey($c.Name)){$c.HeaderText=$headers[$c.Name]}}
            if($grid.Columns["FileName"]){$grid.Columns["FileName"].Visible=$false}
        }
        $codex=@($rows|Where-Object Provider -eq "Codex");$ag=@($rows|Where-Object Provider -eq "Antigravity")
        $readyC=@($codex|Where-Object Status -eq "READY").Count;$readyA=@($ag|Where-Object Status -eq "READY").Count
        $bridge=Test-HmsAntigravityBridge
        $active=Get-AgActiveAccountFromBridge
        $activeText=if($active){$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{"chưa xác định"}
        $sum.Text="Codex: $($codex.Count) ACC ($readyC ready)    |    Antigravity: $($ag.Count) ACC ($readyA ready)    |    AG hiện tại: $activeText`r`nBridge: $($bridge.Message)"
    }

    $timer=New-Object Windows.Forms.Timer;$timer.Interval=10000;$timer.Add_Tick({if($auto.Checked){Refresh-Grid}});$timer.Start()
    $bRefresh.Add_Click({Refresh-Grid})
    $bSwitch.Add_Click({
        try{
            if($grid.SelectedRows.Count -lt 1){throw "Hãy chọn một dòng Antigravity."}
            $row=$grid.SelectedRows[0].DataBoundItem
            if(-not $row -or $row.Provider -ne "Antigravity"){throw "Dòng được chọn không phải Antigravity."}
            $w.Cursor=[Windows.Forms.Cursors]::WaitCursor
            $m=Switch-AntigravityAccount -Email ([string]$row.Account) -Reason "manual-account-center"
            [Windows.Forms.MessageBox]::Show($m,"Antigravity Switch",[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Information)|Out-Null
            Refresh-Grid
        }catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}
    })
    $bBridge.Add_Click({$r=Test-HmsAntigravityBridge;[Windows.Forms.MessageBox]::Show($r.Message,"HMS AG Bridge")|Out-Null;Refresh-Grid})
    $bQuota2.Add_Click({try{if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."};Start-Process ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/management.html#/quota")|Out-Null}catch{Err $_.Exception.Message}})
    $bCodex2.Add_Click({try{Login-Provider "--codex-login"}catch{Err $_.Exception.Message}})
    $bAg2.Add_Click({try{Login-Provider "--antigravity-login"}catch{Err $_.Exception.Message}})
    $bFolder2.Add_Click({Ensure-Dir $script:AuthDir;Start-Process explorer.exe $script:AuthDir|Out-Null})
    $w.Add_FormClosed({try{$timer.Stop();$timer.Dispose()}catch{}})
    $w.Add_Shown({Refresh-Grid})
    [void]$w.ShowDialog($form)
}


# ---------------- CODEX FIRST v0.8 ----------------

function Get-CodexAccountRecords {
    $rows=[System.Collections.Generic.List[object]]::new()
    if(-not (Test-Path $script:AuthDir)){return @()}
    $files=@(Get-ChildItem $script:AuthDir -File -Filter "codex-*.json" -ErrorAction SilentlyContinue | Sort-Object Name)

    foreach($f in $files){
        $raw=""
        $j=$null
        try{$raw=[IO.File]::ReadAllText($f.FullName);$j=$raw| ConvertFrom-Json}catch{}

        $email=Get-DeepValue $j @("email","account_email","user_email")
        if(-not $email){$email=Guess-EmailFromFilename $f.BaseName "Codex"}
        $email=Short-Value $email 60

        $plan=Get-DeepValue $j @("plan_type","plan","subscription_type","subscription","tier")
        if(-not $plan -and $f.BaseName -match '-(free|plus|pro|team|business|enterprise)$'){$plan=$matches[1]}
        if(-not $plan){$plan="—"}
        $plan=(Short-Value $plan 20).ToUpperInvariant()

        $expiryVal=Get-DeepValue $j @("expires_at","expiry","expires","expiration","expiresAt","expire_at")
        $expiry=Convert-ToDateSafe $expiryVal

        $runtime=Get-RuntimeCooldown $f
        $status="READY"
        if(-not $j){$status="LỖI FILE"}
        elseif($runtime -like "Cooldown →*"){$status="COOLDOWN"}
        elseif($expiry -and $expiry -lt (Get-Date)){$status="TOKEN HẾT HẠN"}

        $quota=Get-QuotaText $j $raw
        $quotaPercent=$null
        if($quota -match '^(\d+)%$'){$quotaPercent=[int]$matches[1]}

        $reset="—"
        $rv=Get-DeepValue $j @("resetTime","reset_time","quota_reset","reset_at")
        $rd=Convert-ToDateSafe $rv
        if($rd){$reset=$rd.ToString("dd/MM HH:mm")}
        elseif($runtime){$reset=$runtime}

        $priority=Get-DeepValue $j @("priority")
        if($null -eq $priority){$priority=0}
        $weight=Get-DeepValue $j @("weight")
        if($null -eq $weight){$weight=1}
        $websockets=Get-DeepValue $j @("websockets")
        $officialId=Get-DeepValue $j @("official_account_id","account_id","chatgpt_account_id","user_id")
        $officialRef=''
        if($officialId){$officialRef='oaid-'+(Get-HmsStringSha256 ([string]$officialId)).Substring(0,20)}
        $apiCredentialPresent=[bool](Get-DeepValue $j @("api_key","access_token","token","id_token"))
        $clientAuthState=if(-not $j){'INVALID'}elseif($expiry -and $expiry -lt (Get-Date)){'REAUTH_REQUIRED'}else{'AUTHORIZED_OR_UNVERIFIED'}
        $apiServiceState=if($apiCredentialPresent){'CREDENTIAL_PRESENT_UNVERIFIED'}else{'NO_API_CREDENTIAL_EVIDENCE'}
        $overallAvailability=if($clientAuthState -eq 'REAUTH_REQUIRED' -and $apiCredentialPresent){'CLIENT_REAUTH_REQUIRED_API_CREDENTIAL_PRESENT'}elseif($clientAuthState -eq 'INVALID' -and -not $apiCredentialPresent){'UNAVAILABLE'}else{'AVAILABLE_OR_UNVERIFIED'}

        $rows.Add([PSCustomObject]@{
            Email=$email
            Plan=$plan
            Status=$status
            Quota=$quota
            QuotaPercent=$quotaPercent
            Reset=$reset
            Expiry=$expiry
            Runtime=$runtime
            Priority=$priority
            Weight=$weight
            WebSockets=$websockets
            OfficialAccountRef=$officialRef
            ClientAuthState=$clientAuthState
            ApiServiceState=$apiServiceState
            OverallAvailability=$overallAvailability
            Updated=$f.LastWriteTime
            File=$f
            Json=$j
        })
    }
    return @($rows)
}

function Get-CodexAccountHealth {
    param([object]$Account)
    if(-not $Account){return [PSCustomObject]@{Score=0;Grade="F";Reason="no data"}}
    $score=70
    $why=[System.Collections.Generic.List[string]]::new()

    switch([string]$Account.Status){
        "READY" {$score+=15;$why.Add("READY")}
        "COOLDOWN" {$score-=70;$why.Add("cooldown")}
        "TOKEN HẾT HẠN" {$score-=35;$why.Add("token hết hạn")}
        default {$score-=35;$why.Add([string]$Account.Status)}
    }

    if($null -ne $Account.QuotaPercent){
        $q=[int]$Account.QuotaPercent
        $score += [int][Math]::Round(($q-50)*0.35)
        $why.Add("quota metadata=$q%")
    }else{
        $why.Add("quota runtime chưa expose")
    }

    if($Account.Expiry){
        $mins=($Account.Expiry-(Get-Date)).TotalMinutes
        if($mins -lt 0){$score-=20}
        elseif($mins -lt 10){$score-=5}
        else{$score+=3}
    }

    if([int]$Account.Priority -gt 0){$why.Add("priority="+[string]$Account.Priority)}
    if($Account.WebSockets -eq $false){$why.Add("websocket off")}

    $score=[Math]::Max(0,[Math]::Min(100,$score))
    $grade=if($score -ge 85){"A"}elseif($score -ge 70){"B"}elseif($score -ge 55){"C"}elseif($score -ge 35){"D"}else{"F"}
    return [PSCustomObject]@{Score=[int]$score;Grade=$grade;Reason=($why -join " · ")}
}

function Get-CodexPoolSummary {
    $rows=@(Get-CodexAccountRecords)
    $ready=@($rows|Where-Object Status -eq "READY").Count
    $cool=@($rows|Where-Object Status -eq "COOLDOWN").Count
    $free=@($rows|Where-Object Plan -eq "FREE").Count
    return [PSCustomObject]@{Total=$rows.Count;Ready=$ready;Cooldown=$cool;Free=$free}
}

function Get-CodexConfigAudit {
    $lines=[System.Collections.Generic.List[string]]::new()
    $cfg=""
    if(Test-Path $script:ProxyCfg){try{$cfg=[IO.File]::ReadAllText($script:ProxyCfg)}catch{}}

    $profile=Get-CodexRoutingDescription
    $lines.Add("Routing profile: $profile")

    if($cfg -match '(?m)^\s{2}session-affinity:\s*true\s*$'){
        $lines.Add("PASS  session-affinity=true — giữ continuity trong cùng session")
    }else{
        $lines.Add("INFO  session-affinity=false — request/session mới sẽ chia đều hơn nhưng continuity kém hơn")
    }

    if($cfg -match '(?m)^\s{2}optimize-multi-agent-v2:\s*true\s*$'){
        $lines.Add("PASS  codex.optimize-multi-agent-v2=true")
    }else{
        $lines.Add("WARN  optimize-multi-agent-v2 chưa bật")
    }

    if($cfg -match '(?m)^save-cooldown-status:\s*true\s*$'){
        $lines.Add("PASS  save-cooldown-status=true")
    }else{
        $lines.Add("WARN  cooldown chỉ ở RAM; dashboard khó quan sát")
    }

    $m=[regex]::Match($cfg,'(?m)^request-retry:\s*(\d+)')
    if($m.Success){$lines.Add("INFO  request-retry="+$m.Groups[1].Value)}
    $m=[regex]::Match($cfg,'(?m)^max-retry-credentials:\s*(\d+)')
    if($m.Success){$lines.Add("INFO  max-retry-credentials="+$m.Groups[1].Value+" (0 = có thể thử toàn pool)")}
    $m=[regex]::Match($cfg,'(?m)^max-retry-interval:\s*(\d+)')
    if($m.Success){$lines.Add("INFO  max-retry-interval="+$m.Groups[1].Value+"s")}

    return ($lines -join "`r`n")
}

function Show-CodexSmartPool {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Control Center v0.8"
    $w.Size=New-Object Drawing.Size(1220,690)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(17,19,23)
    $w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5)

    $title=New-Object Windows.Forms.Label
    $title.Text="CODEX SMART POOL"
    $title.Font=New-Object Drawing.Font("Segoe UI Semibold",17)
    $title.AutoSize=$true;$title.Location=New-Object Drawing.Point(18,14);$w.Controls.Add($title)

    $sum=New-Object Windows.Forms.Label
    $sum.Location=New-Object Drawing.Point(20,50);$sum.Size=New-Object Drawing.Size(1160,55)
    $sum.ForeColor=[Drawing.Color]::FromArgb(155,166,178);$w.Controls.Add($sum)

    $grid=New-Object Windows.Forms.DataGridView
    $grid.Location=New-Object Drawing.Point(20,108);$grid.Size=New-Object Drawing.Size(1160,390)
    $grid.ReadOnly=$true;$grid.AllowUserToAddRows=$false;$grid.AllowUserToDeleteRows=$false
    $grid.RowHeadersVisible=$false;$grid.AutoSizeColumnsMode="Fill";$grid.SelectionMode="FullRowSelect";$grid.MultiSelect=$false
    $grid.BackgroundColor=[Drawing.Color]::FromArgb(24,27,32);$grid.GridColor=[Drawing.Color]::FromArgb(55,61,70)
    $grid.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(37,42,49);$grid.ColumnHeadersDefaultCellStyle.ForeColor=[Drawing.Color]::White
    $grid.EnableHeadersVisualStyles=$false
    $grid.DefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(24,27,32);$grid.DefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(230,234,239)
    $grid.DefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(55,72,86);$grid.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    $w.Controls.Add($grid)

    $profileLabel=New-Object Windows.Forms.Label
    $profileLabel.Text="Routing:";$profileLabel.Location=New-Object Drawing.Point(20,520);$profileLabel.AutoSize=$true;$w.Controls.Add($profileLabel)

    $combo=New-Object Windows.Forms.ComboBox
    $combo.DropDownStyle="DropDownList";$combo.Location=New-Object Drawing.Point(85,516);$combo.Size=New-Object Drawing.Size(310,28)
    [void]$combo.Items.Add("ỔN ĐỊNH — round-robin + session affinity")
    [void]$combo.Items.Add("CHIA ĐỀU — round-robin, không sticky")
    [void]$combo.Items.Add("DÙNG HẾT TỪNG ACC — fill-first + sticky")
    switch(([string]$script:S.CodexRoutingProfile).ToLowerInvariant()){
        "balanced" {$combo.SelectedIndex=1}
        "fill-first" {$combo.SelectedIndex=2}
        default {$combo.SelectedIndex=0}
    }
    $w.Controls.Add($combo)

    $bApply=Btn "ÁP DỤNG ROUTING" 410 512 180 36;$w.Controls.Add($bApply)
    $bRefresh=Btn "LÀM MỚI" 605 512 140 36;$w.Controls.Add($bRefresh)
    $bVerify2=Btn "XÁC MINH API" 760 512 150 36;$w.Controls.Add($bVerify2)
    $bQuota=Btn "QUOTA CENTER" 925 512 155 36;$w.Controls.Add($bQuota)
    $bAdd2=Btn "＋ ACC" 1090 512 90 36;$w.Controls.Add($bAdd2)

    $audit=New-Object Windows.Forms.TextBox
    $audit.Location=New-Object Drawing.Point(20,565);$audit.Size=New-Object Drawing.Size(1160,75)
    $audit.Multiline=$true;$audit.ReadOnly=$true;$audit.ScrollBars="Vertical"
    $audit.BackColor=[Drawing.Color]::FromArgb(24,27,32);$audit.ForeColor=[Drawing.Color]::FromArgb(205,211,219)
    $w.Controls.Add($audit)

    function Refresh-CodexGrid {
        $rows=@(Get-CodexAccountRecords | ForEach-Object {
            $h=Get-CodexAccountHealth $_
            [PSCustomObject]@{
                Account=$_.Email
                Plan=$_.Plan
                Status=$_.Status
                Health=$h.Score
                Grade=$h.Grade
                Quota=$_.Quota
                Reset=$_.Reset
                Priority=$_.Priority
                Weight=$_.Weight
                WebSocket=if($null -eq $_.WebSockets){"—"}else{[string]$_.WebSockets}
                Updated=$_.Updated.ToString("dd/MM HH:mm")
                Note=$h.Reason
            }
        })
        $grid.DataSource=$null;$grid.DataSource=$rows
        $p=Get-CodexPoolSummary
        $sum.Text="Pool: $($p.Total) ACC · READY $($p.Ready) · COOLDOWN $($p.Cooldown) · FREE $($p.Free)`r`n"+(Get-CodexRoutingDescription)+" · Cùng session giữ ACC khi Stable; auth unavailable thì CLIProxyAPI có failover."
        $audit.Text=Get-CodexConfigAudit
    }

    $bRefresh.Add_Click({Refresh-CodexGrid})
    $bApply.Add_Click({
        try{
            switch($combo.SelectedIndex){
                1 {$script:S.CodexRoutingProfile="balanced"}
                2 {$script:S.CodexRoutingProfile="fill-first"}
                default {$script:S.CodexRoutingProfile="stable"}
            }
            Save-Settings
            Configure-Proxy
            if(PortOpen ([int]$script:S.ProxyPort)){$null=Restart-Router}
            $audit.Text=Get-CodexConfigAudit
            [Windows.Forms.MessageBox]::Show("Đã áp dụng: "+(Get-CodexRoutingDescription),"Codex Routing")|Out-Null
            Refresh-CodexGrid
        }catch{Err $_.Exception.Message}
    })
    $bVerify2.Add_Click({try{[Windows.Forms.MessageBox]::Show((Verify-Mode),"Codex API Verification")|Out-Null}catch{Err $_.Exception.Message}})
    $bQuota.Add_Click({
        try{
            if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."}
            Start-Process ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/management.html#/quota")|Out-Null
        }catch{Err $_.Exception.Message}
    })
    $bAdd2.Add_Click({try{Login-Provider "--codex-login"}catch{Err $_.Exception.Message}})

    $timer=New-Object Windows.Forms.Timer;$timer.Interval=10000
    $timer.Add_Tick({Refresh-CodexGrid});$timer.Start()
    $w.Add_FormClosed({try{$timer.Stop();$timer.Dispose()}catch{}})
    $w.Add_Shown({Refresh-CodexGrid})
    [void]$w.ShowDialog($form)
}

function Invoke-CodexWatchdogCheck {
    if($script:RuntimeAutomationBlocked){return "SAFE STARTUP: main router watchdog recovery blocked."}
    if(-not [bool]$script:S.CodexWatchdogEnabled){return ""}
    if(-not (CodexInHmsMode)){return ""}

    $port=[int]$script:S.ProxyPort
    $procId=ListenerPid $port

    if($procId -gt 0){
        if(IsOurProxy $procId){return ""}
        return "CODEX WATCHDOG: port $port đang do PID $procId khác giữ — không can thiệp."
    }

    if(-not [bool]$script:S.CodexAutoRecoverRouter){
        return "CODEX WATCHDOG: router OFFLINE."
    }

    try{
        Configure-Proxy
        $m=Start-Router
        return "CODEX WATCHDOG: đã tự phục hồi router. $m"
    }catch{
        return "CODEX WATCHDOG lỗi: "+$_.Exception.Message
    }
}

function Get-CodexDiagnosticsText {
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add("HMS CODEX DIAGNOSTICS v$($script:Version)")
    $lines.Add("")
    $pool=Get-CodexPoolSummary
    $lines.Add("Pool: $($pool.Total) ACC | Ready $($pool.Ready) | Cooldown $($pool.Cooldown) | Free $($pool.Free)")
    $lines.Add("Routing: "+(Get-CodexRoutingDescription))
    $lines.Add("")
    $lines.Add((Get-CodexConfigAudit))
    $lines.Add("")

    $port=[int]$script:S.ProxyPort
    $procId=ListenerPid $port
    if($procId -gt 0){
        $lines.Add("Port ${port}: LISTENING PID $procId"+$(if(IsOurProxy $procId){" — HMS CLIProxyAPI"}else{" — FOREIGN / COCKPIT SAFE"}))
    }else{$lines.Add("Port ${port}: OFFLINE")}

    $api=Test-ApiModels
    $lines.Add("Bearer /v1/models: "+$(if($api.Ok){"PASS ("+$api.Count+" models)"}else{"FAIL — "+$api.Error}))
    $lines.Add("Codex provider: "+$(if(CodexInHmsMode){"hms_api_router"}else{"Cockpit/direct/other"}))

    $clients=@(Get-CodexClientProcesses)
    $lines.Add("Codex/ChatGPT process: "+$(if($clients.Count -gt 0){[string]$clients.Count+" running"}else{"not running"}))
    $lines.Add("Watchdog: "+$(if([bool]$script:S.CodexWatchdogEnabled){"ON"}else{"OFF"}))
    $lines.Add("")
    $lines.Add("Ghi chú quota: runtime quota Codex không phải lúc nào cũng được auth-files expose; Quota Center là nguồn quan sát tốt hơn. HMS không giả định 100% khi dữ liệu thiếu.")
    return ($lines -join "`r`n")
}



# ============================================================
# CODEX SUPERSET v1.0
# Dashboard / direct quota / metadata / instances / trace / wake-up
# ============================================================

function Load-JsonObjectSafe {
    param([string]$Path)
    if(-not (Test-Path $Path)){return $null}
    try{return (Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json)}catch{return $null}
}
function Save-JsonAtomic {
    param([string]$Path,[object]$Object)
    Ensure-Dir (Split-Path $Path -Parent)
    $tmp=$Path+".tmp-"+[Guid]::NewGuid().ToString("N")
    Save-Json $tmp $Object
    Move-Item $tmp $Path -Force
}

# ---------------- Codex account metadata ----------------

function Get-CodexMetaStore {
    $j=Load-JsonObjectSafe $script:CodexAccountMetaPath
    if(-not $j){return @{}}
    $h=@{}
    foreach($p in @($j.PSObject.Properties)){$h[$p.Name]=$p.Value}
    return $h
}
function Get-CodexAccountMeta {
    param([string]$Email)
    $store=Get-CodexMetaStore
    $k=$Email.Trim().ToLowerInvariant()
    if($store.ContainsKey($k)){return $store[$k]}
    return [PSCustomObject]@{tag="";note="";favorite=$false;alias="";group="";role="auto"}
}
function Set-CodexAccountMeta {
    param([string]$Email,[string]$Tag,[string]$Note,[bool]$Favorite)
    $store=Get-CodexMetaStore
    $k=$Email.Trim().ToLowerInvariant()
    $old=if($store.ContainsKey($k)){$store[$k]}else{$null}
    $store[$k]=[PSCustomObject]@{
        tag=$Tag;note=$Note;favorite=$Favorite;
        alias=if($old){[string]$old.alias}else{""};
        group=if($old){[string]$old.group}else{""};
        role=if($old -and $old.role){[string]$old.role}else{"auto"};
        updatedUtc=[DateTime]::UtcNow.ToString("o")
    }
    $obj=[ordered]@{}
    foreach($key in ($store.Keys|Sort-Object)){$obj[$key]=$store[$key]}
    Save-JsonAtomic $script:CodexAccountMetaPath $obj
}
function Set-CodexAccountPoolMeta {
    param([string]$Email,[string]$Alias,[string]$Group,[string]$Role,[bool]$Favorite)
    $roleValue=([string]$Role).Trim().ToLowerInvariant()
    if($roleValue -notin @("auto","preferred","reserve")){throw "ACCOUNT_ROLE_INVALID"}
    $store=Get-CodexMetaStore
    $k=$Email.Trim().ToLowerInvariant()
    $old=if($store.ContainsKey($k)){$store[$k]}else{$null}
    $store[$k]=[PSCustomObject]@{
        tag=if($old){[string]$old.tag}else{""};
        note=if($old){[string]$old.note}else{""};
        favorite=$Favorite;
        alias=([string]$Alias).Trim();
        group=([string]$Group).Trim();
        role=$roleValue;
        updatedUtc=[DateTime]::UtcNow.ToString("o")
    }
    $obj=[ordered]@{}
    foreach($key in ($store.Keys|Sort-Object)){$obj[$key]=$store[$key]}
    Save-JsonAtomic $script:CodexAccountMetaPath $obj
}

# ---------------- Direct Codex quota (Cockpit parity lane) ----------------

function Get-CodexQuotaCache {
    $j=Load-JsonObjectSafe $script:CodexQuotaCachePath
    if(-not $j){return @{}}
    $h=@{}
    foreach($p in @($j.PSObject.Properties)){$h[$p.Name]=$p.Value}
    return $h
}
function Save-CodexQuotaCache([hashtable]$Store) {
    $o=[ordered]@{}
    foreach($k in ($Store.Keys|Sort-Object)){$o[$k]=$Store[$k]}
    Save-JsonAtomic $script:CodexQuotaCachePath $o
}
function Get-CodexAccessToken {
    param([object]$Record)
    if(-not $Record -or -not $Record.Json){return ""}
    $v=Get-DeepValue $Record.Json @("access_token","accessToken")
    if($v -is [string]){return $v.Trim()}
    return ""
}
function Get-CodexChatGptAccountId {
    param([object]$Record,[string]$AccessToken)
    if($Record -and $Record.Json){
        $v=Get-DeepValue $Record.Json @("chatgpt_account_id","chatgptAccountId","account_id","accountId")
        if($v -and ([string]$v).Length -gt 4){return [string]$v}
    }
    $jwt=Decode-JwtPayload $AccessToken
    if($jwt){
        $v=Get-DeepValue $jwt @("chatgpt_account_id","chatgptAccountId","account_id","accountId")
        if($v){return [string]$v}
    }
    return ""
}
function Convert-UsageWindow {
    param([object]$Window)
    if(-not $Window){return $null}
    $used=$null
    try{$used=[int]$Window.used_percent}catch{}
    if($null -eq $used){return $null}
    $remaining=100-[Math]::Max(0,[Math]::Min(100,$used))
    $reset=$null
    try{
        if($Window.reset_at){$reset=[DateTimeOffset]::FromUnixTimeSeconds([Int64]$Window.reset_at).LocalDateTime}
        elseif($Window.reset_after_seconds){$reset=(Get-Date).AddSeconds([double]$Window.reset_after_seconds)}
    }catch{}
    $windowMin=$null
    try{if($Window.limit_window_seconds){$windowMin=[Math]::Ceiling([double]$Window.limit_window_seconds/60)}}catch{}
    return [PSCustomObject]@{remaining=[int]$remaining;reset=$reset;windowMinutes=$windowMin}
}
function Convert-CodexAdditionalQuotaWindows {
    param([object]$Response)
    $rows=[System.Collections.Generic.List[object]]::new()
    $limits=@()
    try{$limits=@($Response.additional_rate_limits)}catch{}
    $index=0
    foreach($limit in $limits){
        if(-not $limit){continue}
        $name=[string]$limit.limit_name
        $feature=[string]$limit.metered_feature
        $allowed=$null;$limitReached=$null
        try{$allowed=$limit.rate_limit.allowed}catch{}
        try{$limitReached=$limit.rate_limit.limit_reached}catch{}
        foreach($kind in @("primary_window","secondary_window")){
            $window=$null
            try{$window=$limit.rate_limit.$kind}catch{}
            $converted=Convert-UsageWindow $window
            if(-not $converted){continue}
            $label=if($converted.windowMinutes -eq 300){"5 giờ"}elseif($converted.windowMinutes -eq 10080){"Tuần"}elseif($converted.windowMinutes){"$($converted.windowMinutes) phút"}else{if($kind -eq "primary_window"){"Primary"}else{"Secondary"}}
            $rows.Add([PSCustomObject]@{
                id=("additional:"+$index+":"+$(if($kind -eq "primary_window"){"primary"}else{"secondary"}))
                limit_name=$name
                metered_feature=$feature
                label=$label
                remaining=[int]$converted.remaining
                reset=if($converted.reset){$converted.reset.ToString("o")}else{$null}
                reset_text=if($converted.reset){Format-ResetCountdown $converted.reset.ToString("o")}else{"—"}
                reset_at_text=if($converted.reset){Format-ResetAbsolute $converted.reset.ToString("o")}else{"—"}
                window_minutes=$converted.windowMinutes
                allowed=$allowed
                limit_reached=$limitReached
            })
        }
        $index++
    }
    return @($rows.ToArray())
}

function Convert-CodexMonthlyCredits {
    param([object]$Response)
    $limit=$null
    try{$limit=$Response.spend_control.individual_limit}catch{}
    if($limit){
        $total=$null;$used=$null;$remaining=$null;$remainingPct=$null;$reset=$null
        try{$total=[double]$limit.limit}catch{}
        try{$used=[double]$limit.used}catch{}
        try{$remaining=[double]$limit.remaining}catch{}
        try{$remainingPct=[int]$limit.remaining_percent}catch{}
        try{
            if($limit.reset_at){
                $reset=[DateTimeOffset]::FromUnixTimeSeconds([Int64]$limit.reset_at).LocalDateTime.ToString("o")
            }
        }catch{}
        return [PSCustomObject]@{
            mode="spend_control";total=$total;used=$used;remaining=$remaining
            remaining_percent=$remainingPct;balance=$null;unlimited=$false
            reset=$reset;reset_text=Format-ResetCountdown $reset
        }
    }
    $credits=$null
    try{$credits=$Response.credits}catch{}
    if($credits){
        $balance=$null;$unlimited=$false
        try{$balance=[string]$credits.balance}catch{}
        try{$unlimited=[bool]$credits.unlimited}catch{}
        $remaining=$null
        try{$remaining=[double]$balance}catch{}
        return [PSCustomObject]@{
            mode="credits";total=$null;used=$null;remaining=$remaining
            remaining_percent=$null;balance=$balance;unlimited=$unlimited
            reset=$null;reset_text="—"
        }
    }
    return $null
}

function Convert-CodexCodeReviewQuota {
    param([object]$Response)
    $rate=$null
    try{$rate=$Response.code_review_rate_limit}catch{}
    if(-not $rate){return $null}
    $primary=Convert-UsageWindow $rate.primary_window
    $secondary=Convert-UsageWindow $rate.secondary_window
    if(-not $primary -and -not $secondary){return $null}
    return [PSCustomObject]@{
        primary_remaining=if($primary){$primary.remaining}else{$null}
        primary_reset=if($primary -and $primary.reset){$primary.reset.ToString("o")}else{$null}
        primary_reset_text=if($primary -and $primary.reset){Format-ResetCountdown $primary.reset.ToString("o")}else{"—"}
        primary_window_minutes=if($primary){$primary.windowMinutes}else{$null}
        secondary_remaining=if($secondary){$secondary.remaining}else{$null}
        secondary_reset=if($secondary -and $secondary.reset){$secondary.reset.ToString("o")}else{$null}
        secondary_reset_text=if($secondary -and $secondary.reset){Format-ResetCountdown $secondary.reset.ToString("o")}else{"—"}
        secondary_window_minutes=if($secondary){$secondary.windowMinutes}else{$null}
    }
}

function Invoke-CodexQuotaDirect {
    param([object]$Record)
    if(-not [bool]$script:S.CodexQuotaDirectEnabled){throw "Direct quota đang tắt."}
    $token=Get-CodexAccessToken $Record
    if([string]::IsNullOrWhiteSpace($token)){throw "Auth file không có access_token khả dụng."}
    $headers=@{
        Authorization=("Bearer "+$token)
        Accept="application/json"
    }
    $accountId=Get-CodexChatGptAccountId $Record $token
    if($accountId){$headers["ChatGPT-Account-Id"]=$accountId}
    try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}
    $resp=Invoke-RestMethod -Method Get -Uri "https://chatgpt.com/backend-api/wham/usage" -Headers $headers -TimeoutSec 15
    $primary=Convert-UsageWindow $resp.rate_limit.primary_window
    $secondary=Convert-UsageWindow $resp.rate_limit.secondary_window
    $additional=Convert-CodexAdditionalQuotaWindows $resp
    $monthly=Convert-CodexMonthlyCredits $resp
    $codeReview=Convert-CodexCodeReviewQuota $resp
    $resetCredits=$null
    try{$resetCredits=if($null -ne $resp.rate_limit_reset_credits.available_count){[int]$resp.rate_limit_reset_credits.available_count}else{$null}}catch{}
    $packageExpiry=Get-HmsCodexPackageExpiry $resp
    $nowUtc=[DateTime]::UtcNow.ToString("o")
    return [PSCustomObject]@{
        email=$Record.Email
        plan=if($resp.plan_type){[string]$resp.plan_type}else{$Record.Plan}
        hourlyRemaining=if($primary){$primary.remaining}else{$null}
        hourlyReset=if($primary -and $primary.reset){$primary.reset.ToString("o")}else{$null}
        hourlyWindowMinutes=if($primary){$primary.windowMinutes}else{$null}
        hourlyWindowPresent=[bool]($null -ne $resp.rate_limit.primary_window)
        weeklyRemaining=if($secondary){$secondary.remaining}else{$null}
        weeklyReset=if($secondary -and $secondary.reset){$secondary.reset.ToString("o")}else{$null}
        weeklyWindowMinutes=if($secondary){$secondary.windowMinutes}else{$null}
        weeklyWindowPresent=[bool]($null -ne $resp.rate_limit.secondary_window)
        codeReview=$codeReview
        additionalWindows=@($additional)
        monthlyCredits=$monthly
        resetCreditsAvailable=$resetCredits
        packageExpiry=$packageExpiry
        packageExpirySource=if($packageExpiry){"UPSTREAM_WHAM"}else{"NOT_EXPOSED"}
        refreshedUtc=$nowUtc
        lastSuccessUtc=$nowUtc
        lastAttemptUtc=$nowUtc
        source="WHAM_USAGE"
        sourceState="FRESH"
        errorCode=$null
        error=$null
    }
}
function Refresh-CodexQuotaOne {
    param([string]$Email)
    $rec=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $Email.Trim().ToLowerInvariant()}| Select-Object -First 1)
    if($rec.Count -eq 0){throw "Không tìm thấy Codex ACC $Email"}
    $store=Get-CodexQuotaCache
    $key=$Email.Trim().ToLowerInvariant()
    try{
        $q=Invoke-CodexQuotaDirect $rec[0]
        $store[$key]=$q
        Save-CodexQuotaCache $store
        return $q
    }catch{
        # v25.50: preserve the last known-good quota. A failed attempt MUST NOT advance lastSuccess/refreshedUtc.
        $attemptUtc=[DateTime]::UtcNow.ToString("o")
        $previous=if($store.ContainsKey($key)){$store[$key]}else{$null}
        if($previous){
            try{$previous | Add-Member -NotePropertyName lastAttemptUtc -NotePropertyValue $attemptUtc -Force}catch{}
            try{$previous | Add-Member -NotePropertyName sourceState -NotePropertyValue "ERROR" -Force}catch{}
            try{$previous | Add-Member -NotePropertyName errorCode -NotePropertyValue "QUOTA_REFRESH_FAILED" -Force}catch{}
            try{$previous | Add-Member -NotePropertyName error -NotePropertyValue "QUOTA_REFRESH_FAILED" -Force}catch{}
            $store[$key]=$previous
        }else{
            $store[$key]=[PSCustomObject]@{
                email=$Email;plan=$rec[0].Plan;hourlyRemaining=$null;hourlyReset=$null;hourlyWindowMinutes=$null;hourlyWindowPresent=$false;
                weeklyRemaining=$null;weeklyReset=$null;weeklyWindowMinutes=$null;weeklyWindowPresent=$false;
                refreshedUtc=$null;lastSuccessUtc=$null;lastAttemptUtc=$attemptUtc;source="WHAM_USAGE";sourceState="ERROR";
                errorCode="QUOTA_REFRESH_FAILED";error="QUOTA_REFRESH_FAILED"
            }
        }
        Save-CodexQuotaCache $store
        throw
    }
}
function Refresh-CodexQuotaAll {
    $ok=0;$fail=0;$messages=[System.Collections.Generic.List[string]]::new()
    foreach($r in @(Get-CodexAccountRecords)){
        try{$null=Refresh-CodexQuotaOne $r.Email;$ok++}
        catch{$fail++;$messages.Add($r.Email+": "+$_.Exception.Message)}
    }
    return "Quota refresh: PASS $ok / FAIL $fail"+$(if($messages.Count){". "+($messages -join " | ")}else{""})
}
function Get-CodexQuotaForEmail {
    param([string]$Email)
    $s=Get-CodexQuotaCache;$k=$Email.Trim().ToLowerInvariant()
    if($s.ContainsKey($k)){return $s[$k]}
    return $null
}
function Format-ResetCountdown {
    param([object]$Value)
    if(-not $Value){return "—"}
    try{
        $dt=[DateTime]::Parse([string]$Value).ToLocalTime()
        $span=$dt-(Get-Date)
        if($span.TotalSeconds -le 0){return "đến hạn"}
        if($span.TotalDays -ge 1){return ("{0}d {1}h" -f [int]$span.TotalDays,$span.Hours)}
        return ("{0}h {1}m" -f [int]$span.TotalHours,$span.Minutes)
    }catch{return "—"}
}
function Format-ResetAbsolute {
    param([object]$Value)
    if(-not $Value){return "—"}
    try{return ([DateTime]::Parse([string]$Value).ToLocalTime()).ToString("dd/MM/yyyy HH:mm")}catch{return "—"}
}
function Convert-HmsOptionalExpiryUtc {
    param([object]$Value)
    if($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)){return $null}
    try{
        $text=([string]$Value).Trim()
        $epoch=0L
        if([Int64]::TryParse($text,[ref]$epoch) -and $epoch -gt 1000000000){return [DateTimeOffset]::FromUnixTimeSeconds($epoch).UtcDateTime.ToString("o")}
        return ([DateTime]::Parse($text).ToUniversalTime()).ToString("o")
    }catch{return $null}
}
function Get-HmsCodexPackageExpiry {
    param([object]$Response)
    if(-not $Response){return $null}
    $candidates=[System.Collections.Generic.List[object]]::new()
    foreach($name in @('subscription_expires_at','plan_expires_at','package_expires_at','subscription_expiry','plan_expiry')){try{if($Response.PSObject.Properties[$name]){$candidates.Add($Response.$name)}}catch{}}
    try{if($Response.subscription -and $Response.subscription.expires_at){$candidates.Add($Response.subscription.expires_at)}}catch{}
    try{if($Response.plan -and $Response.plan.expires_at){$candidates.Add($Response.plan.expires_at)}}catch{}
    foreach($v in $candidates){$x=Convert-HmsOptionalExpiryUtc $v;if($x){return $x}}
    return $null
}
function Get-CodexQuotaReservePct {
    param([string]$Plan)
    $p=([string]$Plan).Trim().ToUpperInvariant()
    if($p -match 'FREE|BASIC'){return [double]$script:S.CodexQuotaReserveFreePct}
    if($p -match 'PLUS|PERSONAL'){return [double]$script:S.CodexQuotaReservePlusPct}
    if($p -match 'PRO'){return [double]$script:S.CodexQuotaReserveProPct}
    return [double]$script:S.CodexQuotaReserveDefaultPct
}
function Get-CodexQuotaFreshness {
    param([object]$Quota)
    $lastSuccess=$null
    if($Quota){
        try{$lastSuccess=[string]$Quota.lastSuccessUtc}catch{}
        if([string]::IsNullOrWhiteSpace($lastSuccess)){try{$lastSuccess=[string]$Quota.refreshedUtc}catch{}}
    }
    if([string]::IsNullOrWhiteSpace($lastSuccess)){return [PSCustomObject]@{state='UNKNOWN';ageSeconds=$null;lastSuccessUtc=$null}}
    try{
        $dt=[DateTime]::Parse($lastSuccess).ToUniversalTime()
        $age=[Math]::Max(0,([DateTime]::UtcNow-$dt).TotalSeconds)
        $fresh=[Math]::Max(30,[int]$script:S.CodexQuotaFreshSeconds)
        $stale=[Math]::Max($fresh,[int]$script:S.CodexQuotaStaleSeconds)
        $state=if($age -le $fresh){'FRESH'}elseif($age -le $stale){'AGING'}else{'STALE'}
        return [PSCustomObject]@{state=$state;ageSeconds=[Math]::Round($age,1);lastSuccessUtc=$dt.ToString('o')}
    }catch{return [PSCustomObject]@{state='UNKNOWN';ageSeconds=$null;lastSuccessUtc=$null}}
}
function Get-CodexLiveQuotaDecision {
    param([object]$Record,[object]$Quota)
    $fresh=Get-CodexQuotaFreshness $Quota
    $reserve=Get-CodexQuotaReservePct ([string]$Record.Plan)
    $h=$null;$w=$null;$hp=$false;$wp=$false
    if($Quota){
        try{if($null -ne $Quota.hourlyRemaining){$h=[double]$Quota.hourlyRemaining}}catch{}
        try{if($null -ne $Quota.weeklyRemaining){$w=[double]$Quota.weeklyRemaining}}catch{}
        try{$hp=[bool]$Quota.hourlyWindowPresent}catch{$hp=($null -ne $h)}
        try{$wp=[bool]$Quota.weeklyWindowPresent}catch{$wp=($null -ne $w)}
    }
    if(-not $hp -and $null -ne $h){$hp=$true};if(-not $wp -and $null -ne $w){$wp=$true}
    $floor=$null
    if($null -ne $h -and $null -ne $w){$floor=[Math]::Min($h,$w)}elseif($null -ne $h){$floor=$h}elseif($null -ne $w){$floor=$w}
    $usable=if($null -ne $floor){[Math]::Max(0,$floor-$reserve)}else{$null}
    $eligible=([string]$Record.Status -eq 'READY')
    $reasons=[System.Collections.Generic.List[string]]::new()
    if(-not $eligible){$reasons.Add('STATUS_'+([string]$Record.Status).ToUpperInvariant())}
    if($fresh.state -eq 'UNKNOWN'){$reasons.Add('QUOTA_FRESHNESS_UNKNOWN');if([bool]$script:S.CodexQuotaFailClosed){$eligible=$false}}
    elseif($fresh.state -eq 'STALE'){$reasons.Add('QUOTA_STALE');if([bool]$script:S.CodexQuotaFailClosed){$eligible=$false}}
    elseif($fresh.state -eq 'AGING'){$reasons.Add('QUOTA_AGING')}
    if((-not $hp) -or (-not $wp) -or $null -eq $h -or $null -eq $w){$reasons.Add('QUOTA_WINDOW_MISSING');if([bool]$script:S.CodexQuotaFailClosed){$eligible=$false}}
    if($null -ne $floor){
        if($floor -le 0){$eligible=$false;$reasons.Add('QUOTA_EMPTY')}
        elseif($floor -le 3){$eligible=$false;$reasons.Add('QUOTA_EMERGENCY')}
        elseif($floor -le $reserve){$eligible=$false;$reasons.Add('PLAN_RESERVE_HELD')}
        elseif($floor -le ($reserve+[double]$script:S.CodexQuotaSwitchReleaseMarginPct)){$reasons.Add('NEAR_PLAN_RESERVE')}
    }
    try{if([string]$Quota.sourceState -eq 'ERROR'){$reasons.Add('LAST_REFRESH_FAILED')}}catch{}
    return [PSCustomObject]@{freshnessState=$fresh.state;ageSeconds=$fresh.ageSeconds;lastSuccessUtc=$fresh.lastSuccessUtc;reservePct=[double]$reserve;quotaFloorPct=$floor;usableRemainingPct=$usable;routingEligible=[bool]$eligible;reasonCodes=@($reasons.ToArray())}
}

# ---------------- Route history / log intelligence ----------------

function Add-CodexRouteHistory {
    param([string]$Type,[string]$Message,[string]$Account="")
    Ensure-Dir $script:DataDir
    $o=[ordered]@{time=[DateTime]::UtcNow.ToString("o");type=$Type;account=$Account;message=$Message}
    Add-Content -LiteralPath $script:CodexRouteHistoryPath -Value ($o| ConvertTo-Json -Compress) -Encoding UTF8
}
function Get-CodexRecentProxyLog {
    param([int]$Lines=120)
    $dirs=@(
        (Join-Path ([string]$script:S.ProxyDir) "logs"),
        ([string]$script:S.ProxyDir)
    )
    foreach($d in $dirs){
        if(-not (Test-Path $d)){continue}
        $f=@(Get-ChildItem $d -File -ErrorAction SilentlyContinue |
            Where-Object {$_.Extension -in @(".log",".txt")} |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1)
        if($f.Count){
            try{return ((Get-Content $f[0].FullName -Tail $Lines -Encoding UTF8 -ErrorAction Stop) -join "`r`n")}catch{}
        }
    }
    return "Chưa tìm thấy log file CLIProxyAPI."
}
function Get-CodexRouteEventsFromLogs {
    param([int]$Max=80)
    $raw=Get-CodexRecentProxyLog -Lines 1200
    $emails=@(Get-CodexAccountRecords|ForEach-Object {$_.Email})
    $lines=@($raw -split "`r?`n")
    $events=[System.Collections.Generic.List[object]]::new()
    foreach($line in $lines){
        if($line -notmatch '(?i)codex|auth|credential|cooldown|retry|failover|429|quota'){continue}
        $email=""
        foreach($e in $emails){if($e -and $line -like "*$e*"){$email=$e;break}}
        $kind=if($line -match '(?i)429|quota|cooldown'){"COOLDOWN"}elseif($line -match '(?i)retry|failover'){"FAILOVER"}elseif($email){"ROUTE"}else{"INFO"}
        $events.Add([PSCustomObject]@{Type=$kind;Account=$email;Message=(Short-Value $line 220)})
    }
    return @($events| Select-Object -Last $Max)
}

# ---------------- Isolated Codex instances ----------------

function Get-CodexInstanceStore {
    $j=Load-JsonObjectSafe $script:CodexInstancesPath
    if(-not $j){return [PSCustomObject]@{schemaVersion=2;codexOnly=$true;instances=@()}}
    if(-not $j.PSObject.Properties['instances']){$j|Add-Member -NotePropertyName instances -NotePropertyValue @() -Force}
    return $j
}
function Save-CodexInstanceStore([object]$Store){
    if(-not $Store.PSObject.Properties['schemaVersion']){$Store|Add-Member -NotePropertyName schemaVersion -NotePropertyValue 2 -Force}
    if(-not $Store.PSObject.Properties['codexOnly']){$Store|Add-Member -NotePropertyName codexOnly -NotePropertyValue $true -Force}
    Save-JsonAtomic $script:CodexInstancesPath $Store
}
function Get-FreeCodexInstancePort {
    $store=Get-CodexInstanceStore
    $used=@($store.instances|ForEach-Object {[int]$_.port})
    $p=[int]$script:S.CodexInstanceBasePort
    while($used -contains $p -or (ListenerPid $p) -gt 0){$p++}
    return $p
}
function Repair-HmsCodexInstancePortConflict {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexInstancePortAutoRecover){throw 'INSTANCE_PORT_AUTO_RECOVERY_DISABLED'}
    if(Test-CodexInstanceClientOwned $Instance){throw 'INSTANCE_PORT_REBIND_BLOCKED_CLIENT_RUNNING'}
    $old=[int]$Instance.port
    $listener=ListenerPid $old
    if($listener -le 0){return $old}
    $expected=Join-Path ([string]$Instance.routerDir) 'cli-proxy-api.exe';$path=ProcPath $listener
    if($path -and (Norm $path) -eq (Norm $expected)){return $old}
    # Never terminate a foreign listener. Find a free unassigned port and atomically persist it.
    $store=Get-CodexInstanceStore
    $used=@($store.instances|Where-Object {([string]$_.id) -ne ([string]$Instance.id)}|ForEach-Object {[int]$_.port})
    $candidate=[Math]::Max([int]$script:S.CodexInstanceBasePort,$old+1)
    $limit=[Math]::Max(1,[int]$script:S.CodexInstancePortAutoRecoverMaxScan)
    $found=0
    for($n=0;$n -lt $limit;$n++){
        $try=$candidate+$n
        if(($used -notcontains $try) -and (ListenerPid $try) -le 0){$found=$try;break}
    }
    if($found -le 0){throw 'INSTANCE_PORT_AUTO_RECOVERY_NO_FREE_PORT'}
    $updated=$false
    foreach($x in @($store.instances)){
        if(([string]$x.id) -eq ([string]$Instance.id)){$x.port=[int]$found;$updated=$true;break}
    }
    if(-not $updated){throw 'INSTANCE_PORT_REBIND_INSTANCE_MISSING'}
    Save-CodexInstanceStore $store
    $Instance.port=[int]$found
    $count=@(Get-ChildItem -LiteralPath (Join-Path ([string]$Instance.routerDir) 'auth') -File -Filter 'codex-*.json' -ErrorAction SilentlyContinue).Count
    Write-CodexInstanceRouterConfigV2530 $Instance ([Math]::Max(1,$count))
    $null=Write-CodexInstanceBinding $Instance
    Add-CodexRouteHistory 'INSTANCE_PORT_REBIND' ("Foreign port $old left untouched; rebound instance $($Instance.id) to $found") ([string]$Instance.accountEmail)
    return [int]$found
}
function Invoke-HmsBoundedCredentialArchiveRetention {
    param([string]$Root,[int]$Keep=-1)
    if($Keep -lt 0){$Keep=[Math]::Max(1,[int]$script:S.CodexBehaviorBackupKeepPerSourceInstance)}
    if([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root -PathType Container)){return 0}
    $rootFull=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Root).Path).TrimEnd('\','/')
    $groups=@{}
    foreach($f in @(Get-ChildItem -LiteralPath $Root -File -Filter '*.json' -ErrorAction SilentlyContinue)){
        if($f.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
        $source=$f.Name
        if($source -match '^\d{8}-\d{6}-\d{3}-(.+)$'){$source=$matches[1]}
        if(-not $groups.ContainsKey($source)){$groups[$source]=[System.Collections.Generic.List[object]]::new()}
        $groups[$source].Add($f)
    }
    $removed=0
    foreach($key in @($groups.Keys)){
        $ordered=@($groups[$key]|Sort-Object LastWriteTimeUtc -Descending)
        foreach($f in @($ordered|Select-Object -Skip $Keep)){
            try{
                $full=[IO.Path]::GetFullPath($f.FullName)
                if(-not $full.StartsWith($rootFull+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){continue}
                Remove-Item -LiteralPath $full -Force -ErrorAction Stop;$removed++
            }catch{}
        }
    }
    return $removed
}
function Assert-HmsCodexAccountOccupancyBeforeLaunch {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexInstanceRequireDedicatedAccount){return}
    $key=([string]$Instance.accountEmail).Trim().ToLowerInvariant()
    if(-not $key){throw 'INSTANCE_ACCOUNT_BINDING_MISSING'}
    $store=Get-CodexInstanceStore
    foreach($other in @($store.instances)){
        if(([string]$other.id) -eq ([string]$Instance.id)){continue}
        if(([string]$other.accountEmail).Trim().ToLowerInvariant() -ne $key){continue}
        if(Test-CodexInstanceClientOwned $other){
            throw ('ACCOUNT_OCCUPIED_BY_ACTIVE_INSTANCE:'+([string]$other.id))
        }
    }
}
function Invoke-HmsBoundedInstanceBackupRetention {
    param([string]$Root,[string]$Pattern='*',[int]$Keep=-1)
    if($Keep -lt 0){$Keep=[Math]::Max(1,[int]$script:S.CodexBehaviorBackupKeepPerSourceInstance)}
    if([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root -PathType Container)){return 0}
    $rootFull=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Root).Path).TrimEnd('\','/')
    $items=@(Get-ChildItem -LiteralPath $Root -Directory -Filter $Pattern -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
    $removed=0
    foreach($item in @($items|Select-Object -Skip $Keep)){
        try{
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
            $full=[IO.Path]::GetFullPath($item.FullName)
            if(-not $full.StartsWith($rootFull+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){continue}
            Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop;$removed++
        }catch{}
    }
    return $removed
}
function Find-CodexDesktopExe {
    $candidates=@(
        (Join-Path $env:LOCALAPPDATA "Programs\Codex\Codex.exe"),
        (Join-Path $env:LOCALAPPDATA "Codex\Codex.exe"),
        (Join-Path $env:ProgramFiles "Codex\Codex.exe")
    )
    foreach($p in $candidates){if(Test-Path $p){return $p}}
    return ""
}
function Find-CodexCliExe {
    try{
        $c=Get-Command codex.exe -ErrorAction SilentlyContinue
        if($c){return $c.Source}
        $c=Get-Command codex -ErrorAction SilentlyContinue
        if($c){return $c.Source}
    }catch{}
    return ""
}
function Get-HmsCanonicalProjectPath {
    param([string]$Path)
    if([string]::IsNullOrWhiteSpace($Path)){return ""}
    if(-not (Test-Path -LiteralPath $Path -PathType Container)){throw "Project path không tồn tại: $Path"}
    $resolved=(Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    return ([IO.Path]::GetFullPath($resolved)).TrimEnd([char[]]'\/')
}
function Get-HmsPathKey {
    param([string]$Path)
    if([string]::IsNullOrWhiteSpace($Path)){return ""}
    return ([IO.Path]::GetFullPath($Path)).TrimEnd([char[]]'\/').ToLowerInvariant()
}
function Get-HmsStringSha256 {
    param([string]$Text)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$bytes=[Text.Encoding]::UTF8.GetBytes([string]$Text);return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
}
function Get-CodexInstanceById {
    param([string]$Id)
    $s=Get-CodexInstanceStore
    $r=@($s.instances|Where-Object id -eq $Id|Select-Object -First 1)
    if($r.Count -eq 0){throw "Instance không tồn tại: $Id"}
    return $r[0]
}
function Get-CodexInstanceBindingPath {
    param([object]$Instance)
    return (Join-Path ([string]$Instance.root) 'binding-v2536.json')
}
function Get-CodexInstanceLegacyBindingPaths {
    param([object]$Instance)
    return @((Join-Path ([string]$Instance.root) 'binding-v2530.json'),(Join-Path ([string]$Instance.root) 'binding-v2529.json'),(Join-Path ([string]$Instance.root) 'binding-v2528.json'))
}
function Ensure-CodexInstanceBindingVersion {
    param([object]$Instance)
    $newPath=Get-CodexInstanceBindingPath $Instance
    if(Test-Path -LiteralPath $newPath){return $newPath}
    foreach($oldPath in @(Get-CodexInstanceLegacyBindingPaths $Instance)){
        if(Test-Path -LiteralPath $oldPath){
            $old=Load-JsonObjectSafe $oldPath
            if($old){$null=Write-CodexInstanceBinding $Instance;return $newPath}
        }
    }
    $null=Write-CodexInstanceBinding $Instance
    return $newPath
}
function Invoke-CodexIdentityAudit {
    param([string]$InstanceId='', [bool]$WriteFingerprint=$false)
    if(-not [bool]$script:S.CodexIdentityIsolationEnabled){
        return [PSCustomObject]@{ok=$true;version='25.36';summary=[PSCustomObject]@{total=0;pass=0;blocked=0};instances=@();disabled=$true}
    }
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_IdentityIsolation.py'
    if(-not (Test-Path -LiteralPath $tool)){throw 'IDENTITY_AUDITOR_MISSING'}
    $args=@('--store',$script:CodexInstancesPath,'--strict',$(if([bool]$script:S.CodexIdentityRequirePathsUnderRoot){'true'}else{'false'}))
    if($InstanceId){$args+=@('--instance-id',$InstanceId)}
    if($WriteFingerprint){$args+='--write-fingerprint'}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
    if(-not $j.ok){throw ('IDENTITY_AUDITOR_FAILED: '+[string]$j.error)}
    $d=$j.data
    try{Save-JsonAtomic $script:CodexIdentityAuditPath $d}catch{}
    try{
        $evt=[ordered]@{time=[DateTime]::UtcNow.ToString('o');instance_id=$InstanceId;ok=[bool]$d.ok;summary=$d.summary;version='25.36'}
        Add-Content -LiteralPath $script:CodexIdentityHistoryPath -Value ($evt|ConvertTo-Json -Compress) -Encoding UTF8
    }catch{}
    if($WriteFingerprint -and [bool]$d.ok){
        try{
            $store=Get-CodexInstanceStore
            foreach($ii in @($store.instances)){
                if($InstanceId -and ([string]$ii.id) -ne $InstanceId){continue}
                Set-HmsSecuritySealTrustedPath (Join-Path ([string]$ii.root) 'identity-v2536.json') 'identity-fingerprint-write'
            }
        }catch{}
    }
    return $d
}
function Get-CodexIdentityFingerprintForInstance {
    param([object]$Instance)
    $p=Join-Path ([string]$Instance.root) 'identity-v2536.json'
    if(-not (Test-Path -LiteralPath $p)){return ''}
    $j=Load-JsonObjectSafe $p
    if(-not $j){return ''}
    return [string]$j.fingerprint_sha256
}
function Assert-CodexIdentityBeforeLaunch {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexIdentityIsolationEnabled -or -not [bool]$script:S.CodexIdentityAuditBeforeLaunch){return ''}
    $audit=Invoke-CodexIdentityAudit -InstanceId ([string]$Instance.id) -WriteFingerprint $true
    if(-not [bool]$audit.ok){
        $issues=@();try{$issues=@($audit.instances[0].issues)}catch{}
        throw ('IDENTITY_ISOLATION_BLOCKED: '+($issues -join ', '))
    }
    $fp='';try{$fp=[string]$audit.instances[0].fingerprint_sha256}catch{}
    if([bool]$script:S.CodexIdentityFingerprintStrict -and [string]::IsNullOrWhiteSpace($fp)){throw 'IDENTITY_FINGERPRINT_MISSING'}
    return $fp
}

function Test-CodexInstanceRouterOwned {
    param([object]$Instance)
    $routerProcessId=[int]$Instance.routerPid;if($routerProcessId -le 0){return $false}
    try{
        $proc=Get-Process -Id $routerProcessId -ErrorAction Stop
        $path=ProcPath $routerProcessId;$expected=Join-Path ([string]$Instance.routerDir) 'cli-proxy-api.exe'
        if(-not $path -or (Norm $path) -ne (Norm $expected)){return $false}
        return ((ListenerPid ([int]$Instance.port)) -eq $routerProcessId)
    }catch{return $false}
}
function Test-CodexInstanceClientOwned {
    param([object]$Instance)
    $clientProcessId=[int]$Instance.clientPid;if($clientProcessId -le 0){return $false}
    try{
        $proc=Get-Process -Id $clientProcessId -ErrorAction Stop
        if($Instance.PSObject.Properties['clientProcessPath'] -and $Instance.clientProcessPath){
            $path=ProcPath $clientProcessId;if(-not $path -or (Norm $path) -ne (Norm ([string]$Instance.clientProcessPath))){return $false}
        }else{return $false}
        if($Instance.PSObject.Properties['clientStartUtc'] -and $Instance.clientStartUtc){
            $expected=[DateTime]::Parse([string]$Instance.clientStartUtc).ToUniversalTime()
            $actual=$proc.StartTime.ToUniversalTime()
            if([Math]::Abs(($actual-$expected).TotalSeconds) -gt 3){return $false}
        }
        return $true
    }catch{return $false}
}
function Set-CodexInstanceClientIdentity {
    param([string]$Id,[object]$Process)
    if(-not $Process){return}
    $store=Get-CodexInstanceStore
    foreach($i in $store.instances){
        if($i.id -eq $Id){
            $path='';$started=[DateTime]::UtcNow.ToString('o')
            try{$path=[string]$Process.Path}catch{try{$path=[string](ProcPath ([int]$Process.Id))}catch{}}
            try{$started=$Process.StartTime.ToUniversalTime().ToString('o')}catch{}
            $i|Add-Member -NotePropertyName clientProcessPath -NotePropertyValue $path -Force
            $i|Add-Member -NotePropertyName clientStartUtc -NotePropertyValue $started -Force
        }
    }
    Save-CodexInstanceStore $store
}
function Write-CodexInstanceBinding {
    param([object]$Instance)
    $project=Get-HmsCanonicalProjectPath ([string]$Instance.projectDir)
    $obj=[ordered]@{
        schema_version=5
        product='HMS-AI-ROUTER Codex-only'
        instance_id=[string]$Instance.id
        account_email=([string]$Instance.accountEmail).Trim().ToLowerInvariant()
        project_dir=$project
        project_key_sha256=(Get-HmsStringSha256 (Get-HmsPathKey $project))
        codex_home=[string]$Instance.codexHome
        app_data=[string]$Instance.appData
        router_dir=[string]$Instance.routerDir
        port=[int]$Instance.port
        launch_mode=[string]$Instance.launchMode
        affinity_managed=$true
        seamless_router=[bool]$script:S.CodexSeamlessRouterEnabled
        stable_endpoint=("http://127.0.0.1:"+[int]$Instance.port+"/v1")
        identity_isolation_version="25.36"
        identity_fingerprint_required=[bool]$script:S.CodexIdentityFingerprintStrict
        primary_account=([string]$Instance.accountEmail).Trim().ToLowerInvariant()
        router_pool_accounts=@(Get-CodexInstanceDesiredRouterAccounts $Instance | ForEach-Object {([string]$_).Trim().ToLowerInvariant()})
        secret_fields_excluded=$true
        updated_utc=[DateTime]::UtcNow.ToString('o')
    }
    $bindingPath=Get-CodexInstanceBindingPath $Instance
    Save-JsonAtomic $bindingPath $obj
    Set-HmsSecuritySealTrustedPath $bindingPath 'binding-write'
    return $obj
}
function Ensure-CodexInstanceBinding {
    param([object]$Instance)
    $path=Ensure-CodexInstanceBindingVersion $Instance
    if(-not (Test-Path $path)){return (Write-CodexInstanceBinding $Instance)}
    $b=Load-JsonObjectSafe $path
    if(-not $b){throw "Binding instance hỏng: $path"}
    $project=Get-HmsCanonicalProjectPath ([string]$Instance.projectDir)
    if(([string]$b.instance_id) -ne ([string]$Instance.id)){throw "ISOLATION_BINDING_INSTANCE_MISMATCH"}
    if(([string]$b.account_email).ToLowerInvariant() -ne ([string]$Instance.accountEmail).Trim().ToLowerInvariant()){throw "ISOLATION_BINDING_ACCOUNT_MISMATCH"}
    if((Get-HmsPathKey ([string]$b.project_dir)) -ne (Get-HmsPathKey $project)){throw "ISOLATION_BINDING_PROJECT_MISMATCH"}
    if([int]$b.port -ne [int]$Instance.port){throw "ISOLATION_BINDING_PORT_MISMATCH"}
    return $b
}
function Test-CodexInstanceIsolation {
    param([object]$Instance)
    $issues=[System.Collections.Generic.List[string]]::new()
    foreach($pair in @(
        @('ROOT',[string]$Instance.root),@('CODEX_HOME',[string]$Instance.codexHome),
        @('APP_DATA',[string]$Instance.appData),@('ROUTER',[string]$Instance.routerDir)
    )){if([string]::IsNullOrWhiteSpace($pair[1]) -or -not (Test-Path -LiteralPath $pair[1] -PathType Container)){$issues.Add($pair[0]+'_MISSING')}}
    try{
        $bindingPath=Ensure-CodexInstanceBindingVersion $Instance
        if(-not (Test-Path -LiteralPath $bindingPath)){throw 'BINDING_MISSING'}
        $b=Load-JsonObjectSafe $bindingPath
        if(-not $b){throw 'BINDING_INVALID'}
        $project=Get-HmsCanonicalProjectPath ([string]$Instance.projectDir)
        if(([string]$b.instance_id) -ne ([string]$Instance.id)){throw 'ISOLATION_BINDING_INSTANCE_MISMATCH'}
        if(([string]$b.account_email).ToLowerInvariant() -ne ([string]$Instance.accountEmail).Trim().ToLowerInvariant()){throw 'ISOLATION_BINDING_ACCOUNT_MISMATCH'}
        if((Get-HmsPathKey ([string]$b.project_dir)) -ne (Get-HmsPathKey $project)){throw 'ISOLATION_BINDING_PROJECT_MISMATCH'}
        if([int]$b.port -ne [int]$Instance.port){throw 'ISOLATION_BINDING_PORT_MISMATCH'}
    }catch{$issues.Add($_.Exception.Message)}
    $authDir=Join-Path ([string]$Instance.routerDir) 'auth'
    $authFiles=@(Get-ChildItem -LiteralPath $authDir -File -Filter 'codex-*.json' -ErrorAction SilentlyContinue)
    if([bool]$script:S.CodexSeamlessRouterEnabled){
        try{
            $desired=@(Get-CodexInstanceDesiredRouterAccounts $Instance);$manifestPath=Get-CodexInstancePoolManifestPath $Instance;$hasManifest=(Test-Path -LiteralPath $manifestPath)
            if($hasManifest){if($authFiles.Count -ne $desired.Count){$issues.Add('SEAMLESS_AUTH_COUNT='+$authFiles.Count+'/EXPECTED='+$desired.Count)}}
            elseif($authFiles.Count -ne 1){$issues.Add('SEAMLESS_MIGRATION_AUTH_COUNT='+$authFiles.Count)}
            if([bool]$script:S.CodexSeamlessRequireManifest -and $hasManifest){$m=Load-JsonObjectSafe $manifestPath;if(-not $m -or ([string]$m.instance_id) -ne ([string]$Instance.id)){$issues.Add('SEAMLESS_POOL_MANIFEST_INVALID')}}
        }catch{$issues.Add('SEAMLESS_POOL_RESOLVE='+$_.Exception.Message)}
    }elseif($authFiles.Count -ne 1){$issues.Add('DEDICATED_AUTH_COUNT='+$authFiles.Count)}
    if(-not (Test-Path (Join-Path ([string]$Instance.routerDir) 'config.yaml'))){$issues.Add('ROUTER_CONFIG_MISSING')}
    if(-not (Test-Path (Join-Path ([string]$Instance.codexHome) 'config.toml'))){$issues.Add('CODEX_CONFIG_MISSING')}
    $store=Get-CodexInstanceStore
    $pk=Get-HmsPathKey ([string]$Instance.projectDir)
    if([bool]$script:S.CodexInstanceRequireUniqueProject){
        $dupes=@($store.instances|Where-Object {$_.id -ne $Instance.id -and (Get-HmsPathKey ([string]$_.projectDir)) -eq $pk})
        if($dupes.Count){$issues.Add('PROJECT_DUPLICATE')}
    }
    if([bool]$script:S.CodexInstanceRequireDedicatedAccount){
        $email=([string]$Instance.accountEmail).Trim().ToLowerInvariant()
        $dupes=@($store.instances|Where-Object {$_.id -ne $Instance.id -and ([string]$_.accountEmail).Trim().ToLowerInvariant() -eq $email})
        if($dupes.Count){$issues.Add('ACCOUNT_DUPLICATE')}
    }
    if([bool]$script:S.CodexIdentityIsolationEnabled){
        try{
            $ia=Invoke-CodexIdentityAudit -InstanceId ([string]$Instance.id) -WriteFingerprint $false
            if(-not [bool]$ia.ok){foreach($x in @($ia.instances[0].issues)){$issues.Add('IDENTITY:'+[string]$x)}}
        }catch{$issues.Add('IDENTITY_AUDIT='+$_.Exception.Message)}
    }
    return [PSCustomObject]@{ok=($issues.Count -eq 0);issues=@($issues)}
}
function Sync-CodexInstanceBoundCredential {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexInstanceSyncCredentialOnStart){return 'Credential sync OFF'}
    if(-not (Test-CodexInstanceFullyStopped $Instance)){return 'Credential sync skipped: instance/router đang chạy'}
    $acc=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq ([string]$Instance.accountEmail).Trim().ToLowerInvariant()}|Select-Object -First 1)
    if($acc.Count -eq 0){throw "Bound account không còn trong pool: $($Instance.accountEmail)"}
    $authDir=Join-Path ([string]$Instance.routerDir) 'auth';Ensure-Dir $authDir
    $source=$acc[0].File.FullName
    $final=Join-Path $authDir $acc[0].File.Name
    $srcHash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    $existing=@(Get-ChildItem -LiteralPath $authDir -File -Filter 'codex-*.json' -ErrorAction SilentlyContinue)
    if($existing.Count -eq 1 -and $existing[0].Name -eq $acc[0].File.Name){
        try{if((Get-FileHash -LiteralPath $existing[0].FullName -Algorithm SHA256).Hash -eq $srcHash){return 'Credential snapshot current'}}catch{}
    }
    $archive=Join-Path ([string]$Instance.routerDir) 'auth-archive';Ensure-Dir $archive
    foreach($f in $existing){Move-Item -LiteralPath $f.FullName -Destination (Join-Path $archive ((Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+$f.Name)) -Force}
    $tmp=$final+'.tmp-'+[Guid]::NewGuid().ToString('N')
    try{
        Copy-Item -LiteralPath $source -Destination $tmp -Force
        if((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash -ne $srcHash){throw 'Credential copy hash mismatch'}
        Move-Item -LiteralPath $tmp -Destination $final -Force
        if((Get-FileHash -LiteralPath $final -Algorithm SHA256).Hash -ne $srcHash){throw 'Credential final hash mismatch'}
    }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
    return 'Credential snapshot refreshed'
}
function New-CodexInstance {
    param([string]$Name,[string]$ProjectDir,[string]$AccountEmail,[string]$LaunchMode='cli')
    $Name=([string]$Name).Trim()
    if([string]::IsNullOrWhiteSpace($Name)){throw 'Tên instance không được trống.'}
    if($Name.Length -gt 80){throw 'Tên instance tối đa 80 ký tự.'}
    if([bool]$script:S.CodexInstanceProjectRequired -and [string]::IsNullOrWhiteSpace($ProjectDir)){throw 'v25.31 yêu cầu gắn project cho mỗi instance.'}
    $ProjectDir=Get-HmsCanonicalProjectPath $ProjectDir
    $LaunchMode=([string]$LaunchMode).Trim().ToLowerInvariant();if($LaunchMode -notin @('cli','desktop')){throw 'Launch mode chỉ hỗ trợ cli/desktop.'}
    $account=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq ([string]$AccountEmail).Trim().ToLowerInvariant()}|Select-Object -First 1)
    if($account.Count -eq 0){throw 'Chọn một Codex ACC hợp lệ.'}
    $AccountEmail=[string]$account[0].Email
    $store=Get-CodexInstanceStore
    if([bool]$script:S.CodexInstanceRequireUniqueProject){
        $pk=Get-HmsPathKey $ProjectDir
        if(@($store.instances|Where-Object {(Get-HmsPathKey ([string]$_.projectDir)) -eq $pk}).Count -gt 0){throw 'PROJECT_ALREADY_BOUND_TO_INSTANCE'}
    }
    if([bool]$script:S.CodexInstanceRequireDedicatedAccount){
        $ek=$AccountEmail.Trim().ToLowerInvariant()
        if(@($store.instances|Where-Object {([string]$_.accountEmail).Trim().ToLowerInvariant() -eq $ek}).Count -ge [Math]::Max(1,[int]$script:S.CodexFleetMaxInstancesPerAccount)){throw 'ACCOUNT_ALREADY_BOUND_TO_INSTANCE'}
    }
    if(@($store.instances|Where-Object {([string]$_.name).Trim().ToLowerInvariant() -eq $Name.ToLowerInvariant()}).Count){throw 'INSTANCE_NAME_ALREADY_EXISTS'}

    Ensure-Dir $script:CodexInstancesRoot
    $id=[Guid]::NewGuid().ToString('N').Substring(0,10)
    $root=Join-Path $script:CodexInstancesRoot $id
    $codexHome=Join-Path $root 'codex-home';$appData=Join-Path $root 'app-data';$routerDir=Join-Path $root 'router';$authDir=Join-Path $routerDir 'auth'
    foreach($x in @($root,$codexHome,$appData,$routerDir,$authDir)){Ensure-Dir $x}
    $port=Get-FreeCodexInstancePort;$apiKey=New-LocalKey
    $apiKeyRef=Get-HmsSecurityCredentialTargetForInstance $id
    $null=Set-HmsProtectedSecret $apiKeyRef $apiKey
    Copy-Item -LiteralPath $account[0].File.FullName -Destination (Join-Path $authDir $account[0].File.Name) -Force
    $proxyCopy=Join-Path $routerDir 'cli-proxy-api.exe'
    if(-not (Test-Path $script:ProxyExe)){throw 'Không tìm thấy CLIProxyAPI gốc.'}
    Copy-Item -LiteralPath $script:ProxyExe -Destination $proxyCopy -Force
    $authYaml=$authDir.Replace('\\','/')
    $cfg=@"
host: "127.0.0.1"
port: $port
auth-dir: "$authYaml"
api-keys:
  - "$apiKey"
logging-to-file: true
usage-statistics-enabled: true
save-cooldown-status: true
request-retry: 3
max-retry-credentials: 3
max-retry-interval: 12
routing:
  strategy: "fill-first"
  session-affinity: true
  session-affinity-ttl: "24h"
codex:
  optimize-multi-agent-v2: true
"@
    Write-Utf8 (Join-Path $routerDir 'config.yaml') $cfg
    $toml=@"
model_provider = "hms_instance_router"

[model_providers.hms_instance_router]
name = "API"
base_url = "http://127.0.0.1:$port/v1"
env_key = "HMS_ROUTER_API_KEY"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 4
stream_max_retries = 5
stream_idle_timeout_ms = 300000
"@
    Write-Utf8 (Join-Path $codexHome 'config.toml') $toml
    $items=@($store.instances)
    $inst=[PSCustomObject]@{
        schemaVersion=2;id=$id;name=$Name;projectDir=$ProjectDir;projectKey=(Get-HmsStringSha256 (Get-HmsPathKey $ProjectDir));accountEmail=$AccountEmail;
        launchMode=$LaunchMode;root=$root;codexHome=$codexHome;appData=$appData;routerDir=$routerDir;port=$port;apiKey='';apiKeyRef=$apiKeyRef;secretStorage='PROTECTED_CURRENT_USER';
        routerPid=0;clientPid=0;createdUtc=[DateTime]::UtcNow.ToString('o');lastLaunchUtc=$null;isolationVersion='25.36';identityIsolationVersion='25.36';affinityVersion='25.30';routerVersion='25.31';closedLoopVersion='25.31'
    }
    $items+=$inst;$store.instances=$items;Save-CodexInstanceStore $store
    $null=Write-CodexInstanceBinding $inst
    if([bool]$script:S.CodexIdentityIsolationEnabled){$null=Invoke-CodexIdentityAudit -InstanceId ([string]$inst.id) -WriteFingerprint $true}
    Set-HmsSecuritySealTrustedPath (Join-Path ([string]$inst.codexHome) 'config.toml') 'instance-create-config'
    Add-CodexRouteHistory 'INSTANCE_CREATE' "Tạo isolated instance $Name / project=$ProjectDir / port $port" $AccountEmail
    if([bool]$script:S.CodexProjectAutoRegisterInstances){try{$null=Register-CodexProjectAffinityFromInstance $inst}catch{Add-CodexRouteHistory 'AFFINITY_REGISTER_WARN' $_.Exception.Message $AccountEmail}}
    if([bool]$script:S.CodexSeamlessRouterEnabled){try{$null=Sync-CodexInstanceRouterCredentialPool $inst}catch{Add-CodexRouteHistory 'SEAMLESS_INIT_WARN' $_.Exception.Message $AccountEmail}}
    return $inst
}
function Update-CodexInstanceState {
    param([string]$Id,[int]$RouterPid=-1,[int]$ClientPid=-1,[bool]$TouchLaunch=$false)
    $store=Get-CodexInstanceStore
    foreach($i in $store.instances){if($i.id -eq $Id){if($RouterPid -ge 0){$i.routerPid=$RouterPid};if($ClientPid -ge 0){$i.clientPid=$ClientPid};if($TouchLaunch){$i.lastLaunchUtc=[DateTime]::UtcNow.ToString('o')}}}
    Save-CodexInstanceStore $store
}
function Start-CodexInstanceRouter {
    param([object]$Instance)
    if(Test-CodexInstanceRouterOwned $Instance){return [int]$Instance.routerPid}
    $listener=ListenerPid ([int]$Instance.port)
    if($listener -gt 0){
        $expected=Join-Path $Instance.routerDir 'cli-proxy-api.exe';$path=ProcPath $listener
        if($path -and (Norm $path) -eq (Norm $expected)){Update-CodexInstanceState $Instance.id $listener -1 $false;return $listener}
        if([bool]$script:S.CodexInstancePortAutoRecover){
            $null=Repair-HmsCodexInstancePortConflict $Instance
            $listener=ListenerPid ([int]$Instance.port)
            if($listener -gt 0){throw 'INSTANCE_PORT_REBIND_RACE_DETECTED'}
        }else{throw "Port instance $($Instance.port) đang bị process khác chiếm; HMS không kill process lạ."}
    }
    $exe=Join-Path $Instance.routerDir 'cli-proxy-api.exe'
    $proc=Start-Process $exe -WorkingDirectory $Instance.routerDir -WindowStyle Hidden -PassThru
    for($x=0;$x -lt 25;$x++){
        Start-Sleep -Milliseconds 300
        if((ListenerPid ([int]$Instance.port)) -eq $proc.Id){Update-CodexInstanceState $Instance.id $proc.Id -1 $false;return $proc.Id}
    }
    try{if((ProcPath $proc.Id) -and (Norm (ProcPath $proc.Id)) -eq (Norm $exe)){Stop-Process -Id $proc.Id -Force}}catch{}
    throw "Instance router không mở được port $($Instance.port)."
}

function Start-CodexCliEmbedded {
    param(
        [string]$Cli,
        [string]$WorkingDirectory,
        [string]$CodexHome,
        [string]$ApiKey="",
        [string]$InstanceId="",
        [string]$ProjectDir="",
        [string]$Title="Codex CLI"
    )

    $w=New-Object Windows.Forms.Form
    $w.Text=("HMS — "+$Title)
    $w.Size=New-Object Drawing.Size(900,620)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(15,17,20)
    $w.ForeColor=[Drawing.Color]::FromArgb(230,235,241)
    $w.Font=New-Object Drawing.Font("Consolas",9.5)

    $out=New-Object Windows.Forms.RichTextBox
    $out.Location=New-Object Drawing.Point(14,14)
    $out.Size=New-Object Drawing.Size(854,490)
    $out.ReadOnly=$true
    $out.BackColor=[Drawing.Color]::FromArgb(10,12,15)
    $out.ForeColor=[Drawing.Color]::FromArgb(210,220,230)
    $out.BorderStyle="FixedSingle"
    $out.DetectUrls=$true
    $w.Controls.Add($out)

    $input=New-Object Windows.Forms.TextBox
    $input.Location=New-Object Drawing.Point(14,520)
    $input.Size=New-Object Drawing.Size(720,28)
    $input.BackColor=[Drawing.Color]::FromArgb(25,29,34)
    $input.ForeColor=[Drawing.Color]::FromArgb(235,240,246)
    $w.Controls.Add($input)

    $send=New-Object Windows.Forms.Button
    $send.Text="GỬI"
    $send.Location=New-Object Drawing.Point(746,518)
    $send.Size=New-Object Drawing.Size(122,32)
    $send.FlatStyle="Flat"
    $send.FlatAppearance.BorderSize=0
    $send.BackColor=[Drawing.Color]::FromArgb(28,105,77)
    $send.ForeColor=[Drawing.Color]::White
    $w.Controls.Add($send)

    $psi=New-Object Diagnostics.ProcessStartInfo
    $psi.FileName=$Cli
    $psi.WorkingDirectory=$WorkingDirectory
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $psi.RedirectStandardInput=$true
    $psi.EnvironmentVariables["CODEX_HOME"]=$CodexHome
    if($ApiKey){$psi.EnvironmentVariables["HMS_ROUTER_API_KEY"]=$ApiKey}
    if($InstanceId){$psi.EnvironmentVariables["HMS_CODEX_INSTANCE_ID"]=$InstanceId}
    if($ProjectDir){$psi.EnvironmentVariables["HMS_CODEX_PROJECT"]=$ProjectDir}

    $proc=New-Object Diagnostics.Process
    $proc.StartInfo=$psi
    $proc.EnableRaisingEvents=$true
    try{$proc.SynchronizingObject=$w}catch{}

    $append=[Diagnostics.DataReceivedEventHandler]{
        param($sender,$e)
        if($null -ne $e.Data){
            try{
                $out.AppendText([string]$e.Data+"`r`n")
                $out.SelectionStart=$out.TextLength
                $out.ScrollToCaret()
            }catch{}
        }
    }
    $proc.add_OutputDataReceived($append)
    $proc.add_ErrorDataReceived($append)
    $proc.add_Exited({
        try{
            $out.AppendText("`r`n[HMS] Codex CLI đã kết thúc. ExitCode="+$proc.ExitCode+"`r`n")
            $send.Enabled=$false
            $input.Enabled=$false
        }catch{}
    })

    if(-not $proc.Start()){
        throw "Không thể khởi động Codex CLI embedded."
    }
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()

    $send.Add_Click({
        try{
            if(-not $proc.HasExited -and -not [string]::IsNullOrWhiteSpace($input.Text)){
                $proc.StandardInput.WriteLine($input.Text)
                $input.Clear()
            }
        }catch{}
    })
    $input.Add_KeyDown({
        if($_.KeyCode -eq [Windows.Forms.Keys]::Enter){
            $_.SuppressKeyPress=$true
            $send.PerformClick()
        }
    })
    $w.Add_FormClosed({
        try{
            if($proc -and -not $proc.HasExited){
                # This child belongs to this embedded terminal window only.
                $proc.Kill()
            }
        }catch{}
    })

    if(-not $script:EmbeddedCliSessions){
        $script:EmbeddedCliSessions=[System.Collections.Generic.List[object]]::new()
    }
    $session=[PSCustomObject]@{Window=$w;Process=$proc}
    $script:EmbeddedCliSessions.Add($session)
    $w.Show($form)
    return $proc
}

function Get-HmsMultiCodexTeamStore {
    Ensure-Dir $script:MultiCodexTeamDir
    $j=Load-JsonObjectSafe $script:MultiCodexTeamStorePath
    if(-not $j){return [PSCustomObject]@{schemaVersion=1;codexOnly=$true;teams=@()}}
    if(-not $j.PSObject.Properties['teams']){$j|Add-Member -NotePropertyName teams -NotePropertyValue @() -Force}
    return $j
}
function Save-HmsMultiCodexTeamStore([object]$Store){
    Ensure-Dir $script:MultiCodexTeamDir
    if(-not $Store.PSObject.Properties['schemaVersion']){$Store|Add-Member -NotePropertyName schemaVersion -NotePropertyValue 1 -Force}
    if(-not $Store.PSObject.Properties['codexOnly']){$Store|Add-Member -NotePropertyName codexOnly -NotePropertyValue $true -Force}
    Save-JsonAtomic $script:MultiCodexTeamStorePath $Store
    try{Set-HmsSecuritySealTrustedPath $script:MultiCodexTeamStorePath 'multi-codex-team-store'}catch{}
}
function Get-HmsMultiCodexTeamMembershipForInstance {
    param([string]$InstanceId)
    if([string]::IsNullOrWhiteSpace($InstanceId)){return $null}
    $store=Get-HmsMultiCodexTeamStore
    foreach($t in @($store.teams)){
        foreach($m in @($t.members)){
            if(([string]$m.instanceId) -eq $InstanceId){
                return [PSCustomObject]@{team_id=[string]$t.teamId;team_name=[string]$t.name;project_dir=[string]$t.projectDir;epoch=[int]$t.epoch;role=([string]$m.role).ToUpperInvariant()}
            }
        }
    }
    return $null
}

function Start-CodexCliManagedWindow {
    param([string]$Cli,[string]$WorkingDirectory,[string]$CodexHome,[string]$ApiKey,[string]$InstanceId,[string]$AccountEmail,[string]$IdentityFingerprint='',[string]$AppData='',[string]$TeamId='',[string]$TeamRole='',[int]$TeamEpoch=0)
    # Start Codex directly with an isolated child environment. Do not launch an intermediate
    # PowerShell/cmd helper: the returned PID belongs to Codex itself and can be ownership-checked.
    $psi=New-Object Diagnostics.ProcessStartInfo
    $psi.FileName=$Cli
    $psi.WorkingDirectory=$WorkingDirectory
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$false
    $psi.EnvironmentVariables['CODEX_HOME']=$CodexHome
    $psi.EnvironmentVariables['HMS_ROUTER_API_KEY']=$ApiKey
    $psi.EnvironmentVariables['HMS_CODEX_INSTANCE_ID']=$InstanceId
    $psi.EnvironmentVariables['HMS_CODEX_PROJECT']=$WorkingDirectory
    $psi.EnvironmentVariables['HMS_CODEX_ACCOUNT']=$AccountEmail
    if($IdentityFingerprint){$psi.EnvironmentVariables['HMS_CODEX_IDENTITY_FINGERPRINT']=$IdentityFingerprint}
    if($AppData){$psi.EnvironmentVariables['HMS_CODEX_APP_DATA']=$AppData}
    $psi.EnvironmentVariables['HMS_CODEX_PROFILE_ROOT']=$CodexHome
    if($TeamId){$psi.EnvironmentVariables['HMS_CODEX_TEAM_ID']=$TeamId}
    if($TeamRole){$psi.EnvironmentVariables['HMS_CODEX_TEAM_ROLE']=$TeamRole}
    if($TeamEpoch -gt 0){$psi.EnvironmentVariables['HMS_CODEX_TEAM_EPOCH']=[string]$TeamEpoch}
    $proc=New-Object Diagnostics.Process
    $proc.StartInfo=$psi
    if(-not $proc.Start()){throw 'Không thể khởi động Codex CLI managed instance.'}
    return $proc
}

function Start-CodexInstance {
    param([string]$Id)
    $i=Get-CodexInstanceById $Id
    Assert-HmsCodexAccountOccupancyBeforeLaunch $i
    if([bool]$script:S.CodexInstanceEnforceIsolation){
        $audit=Test-CodexInstanceIsolation $i
        if(-not $audit.ok){throw ('INSTANCE_ISOLATION_BLOCKED: '+(@($audit.issues)-join ', '))}
    }
    $identityFingerprint=Assert-CodexIdentityBeforeLaunch $i
    $lanLease=$null;try{$lanLease=Assert-HmsLanProjectLeaseBeforeLaunch $i}catch{throw}
    $teamMembership=$null;if([bool]$script:S.MultiCodexTeamEnabled -and [bool]$script:S.MultiCodexTeamInjectRoleEnvironment){try{$teamMembership=Get-HmsMultiCodexTeamMembershipForInstance ([string]$i.id)}catch{}}
    if([bool]$script:S.ModelManagerEnabled -and [bool]$script:S.ModelManagerApplyBeforeLaunch){
        try{$null=Invoke-HmsModelManager -Mode "apply" -ProjectDir ([string]$i.projectDir)}catch{
            $mmErr=[string]$_.Exception.Message
            if($mmErr -notmatch 'MODEL_POLICY_NOT_CONFIGURED'){throw ("MODEL_POLICY_PRELAUNCH_BLOCKED: "+$mmErr)}
        }
    }
    $routerPid=Start-CodexInstanceRouter $i
    $mode=([string]$i.launchMode).ToLowerInvariant()
    $wd=Get-HmsCanonicalProjectPath ([string]$i.projectDir)
    if($mode -eq 'desktop'){
        $exe=Find-CodexDesktopExe
        if(-not $exe){throw 'Không tìm thấy Codex Desktop exe dạng classic. Đổi instance sang CLI.'}
        $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$exe;$psi.WorkingDirectory=$wd;$psi.UseShellExecute=$false
        $psi.EnvironmentVariables['CODEX_HOME']=[string]$i.codexHome
        $psi.EnvironmentVariables['HMS_ROUTER_API_KEY']=[string](Get-HmsInstanceApiKey $i)
        $psi.EnvironmentVariables['HMS_CODEX_INSTANCE_ID']=[string]$i.id
        $psi.EnvironmentVariables['HMS_CODEX_PROJECT']=$wd
        $psi.EnvironmentVariables['HMS_CODEX_ACCOUNT']=[string]$i.accountEmail
        if($identityFingerprint){$psi.EnvironmentVariables['HMS_CODEX_IDENTITY_FINGERPRINT']=$identityFingerprint}
        $psi.EnvironmentVariables['HMS_CODEX_PROFILE_ROOT']=[string]$i.codexHome
        $psi.EnvironmentVariables['HMS_CODEX_APP_DATA']=[string]$i.appData
        if($teamMembership){$psi.EnvironmentVariables['HMS_CODEX_TEAM_ID']=[string]$teamMembership.team_id;$psi.EnvironmentVariables['HMS_CODEX_TEAM_ROLE']=[string]$teamMembership.role;$psi.EnvironmentVariables['HMS_CODEX_TEAM_EPOCH']=[string][int]$teamMembership.epoch}
        $psi.Arguments='--user-data-dir="'+[string]$i.appData+'"'
        $proc=[Diagnostics.Process]::Start($psi)
    }else{
        $cli=Find-CodexCliExe;if(-not $cli){throw 'Không tìm thấy Codex CLI trong PATH.'}
        $proc=Start-CodexCliManagedWindow -Cli $cli -WorkingDirectory $wd -CodexHome ([string]$i.codexHome) -ApiKey ([string](Get-HmsInstanceApiKey $i)) -InstanceId ([string]$i.id) -AccountEmail ([string]$i.accountEmail) -IdentityFingerprint $identityFingerprint -AppData ([string]$i.appData) -TeamId $(if($teamMembership){[string]$teamMembership.team_id}else{''}) -TeamRole $(if($teamMembership){[string]$teamMembership.role}else{''}) -TeamEpoch $(if($teamMembership){[int]$teamMembership.epoch}else{0})
    }
    Update-CodexInstanceState $i.id $routerPid $proc.Id $true
    Set-CodexInstanceClientIdentity $i.id $proc
    Add-CodexRouteHistory 'INSTANCE_START' ("Start $($i.name), project=$wd, router PID $routerPid, client PID $($proc.Id), identity="+$(if($identityFingerprint){$identityFingerprint.Substring(0,[Math]::Min(12,$identityFingerprint.Length))}else{'disabled'})+$(if($teamMembership){', team='+[string]$teamMembership.team_id+', role='+[string]$teamMembership.role+', epoch='+[string][int]$teamMembership.epoch}else{''})+$(if($lanLease){', lan-lease-epoch='+[string]$lanLease.lease.epoch}else{''})) $i.accountEmail
    return "Đã mở $($i.name) → $($i.accountEmail) | project=$wd | port=$($i.port)"
}
function Stop-CodexInstance {
    param([string]$Id)
    $i=Get-CodexInstanceById $Id
    $warnings=[System.Collections.Generic.List[string]]::new()
    $clientPid=[int]$i.clientPid
    if($clientPid -gt 0){
        if(Test-CodexInstanceClientOwned $i){
            try{& taskkill.exe /PID $clientPid /T /F 2>$null | Out-Null}catch{try{Stop-Process -Id $clientPid -Force -ErrorAction SilentlyContinue}catch{}}
        }else{$warnings.Add('Client PID ownership không khớp; HMS không kill PID lạ.')}
    }
    $routerPid=[int]$i.routerPid
    if($routerPid -gt 0){
        if(Test-CodexInstanceRouterOwned $i){try{Stop-Process -Id $routerPid -Force -ErrorAction SilentlyContinue}catch{}}
        else{$warnings.Add('Router PID ownership không khớp; HMS không kill PID lạ.')}
    }
    Update-CodexInstanceState $i.id 0 0 $false
    Add-CodexRouteHistory 'INSTANCE_STOP' ("Stop $($i.name)"+$(if($warnings.Count){' | '+($warnings-join' ')}else{''})) $i.accountEmail
    return ("Đã dừng managed instance $($i.name). Dữ liệu profile được giữ nguyên."+$(if($warnings.Count){"`r`n"+($warnings-join"`r`n")}else{''}))
}
function Get-CodexInstanceRows {
    $store=Get-CodexInstanceStore
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($i in @($store.instances)){
        $rp=Test-CodexInstanceRouterOwned $i
        $cp=Test-CodexInstanceClientOwned $i
        $rows.Add([PSCustomObject]@{
            Id=$i.id;Name=$i.name;Account=$i.accountEmail;Project=$i.projectDir;Mode=$i.launchMode;Port=$i.port;
            Router=if($rp){"ONLINE"}else{"OFF"};Client=if($cp){"RUNNING"}else{"OFF"};
            LastLaunch=if($i.lastLaunchUtc){try{([DateTime]::Parse($i.lastLaunchUtc)).ToLocalTime().ToString("dd/MM HH:mm")}catch{"—"}}else{"—"}
        })
    }
    return @($rows)
}


# ---------------- v25.30 Seamless Codex Router ----------------
function Get-CodexInstancePoolManifestPath {
    param([object]$Instance)
    return (Join-Path ([string]$Instance.routerDir) 'router-pool-v2530.json')
}
function Add-CodexSeamlessRouterHistory {
    param([string]$Event,[object]$Instance,[string]$Message)
    try{
        $o=[ordered]@{time=[DateTime]::UtcNow.ToString('o');event=$Event;instance_id=[string]$Instance.id;project=[string]$Instance.projectDir;endpoint=('http://127.0.0.1:'+([int]$Instance.port)+'/v1');message=$Message}
        Add-Content -LiteralPath $script:CodexSeamlessRouterHistoryPath -Value ($o|ConvertTo-Json -Compress) -Encoding UTF8
    }catch{}
}
function Get-CodexInstanceDesiredRouterAccounts {
    param([object]$Instance)
    $out=[System.Collections.Generic.List[string]]::new();$seen=@{}
    $primary=([string]$Instance.accountEmail).Trim()
    if($primary){$out.Add($primary);$seen[$primary.ToLowerInvariant()]=$true}
    if([bool]$script:S.CodexSeamlessRouterEnabled){
        try{
            $aff=@(Get-CodexProjectAffinityByPath ([string]$Instance.projectDir))
            if($aff.Count){
                $limit=[Math]::Min([Math]::Max(0,[int]$script:S.CodexSeamlessMaxFallback),[Math]::Max(0,[int]$script:S.CodexProjectFallbackMax))
                foreach($f in @($aff[0].fallbackAccounts)){
                    $e=([string]$f).Trim();$k=$e.ToLowerInvariant();if(-not $e -or $seen.ContainsKey($k)){continue}
                    $rec=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $k}|Select-Object -First 1)
                    if($rec.Count){$out.Add([string]$rec[0].Email);$seen[$k]=$true}
                    if(($out.Count-1) -ge $limit){break}
                }
            }
        }catch{}
    }
    return @($out)
}
function Write-CodexInstanceRouterConfigV2530 {
    param([object]$Instance,[int]$CredentialCount)
    $authDir=Join-Path ([string]$Instance.routerDir) 'auth';$authYaml=$authDir.Replace('\','/')
    $fallbacks=[Math]::Max(0,$CredentialCount-1)
    $maxRetry=[Math]::Min([Math]::Max(0,[int]$script:S.CodexSeamlessMaxRetryCredentials),$fallbacks)
    $ttl=[Math]::Max(1,[int]$script:S.CodexSeamlessSessionTtlHours)
    $aff=if([bool]$script:S.CodexSeamlessSessionAffinity){'true'}else{'false'}
    $apiKey=[string](Get-HmsInstanceApiKey $Instance)
    $cfg=@"
host: "127.0.0.1"
port: $([int]$Instance.port)
auth-dir: "$authYaml"
api-keys:
  - "$apiKey"
logging-to-file: true
usage-statistics-enabled: true
save-cooldown-status: true
request-retry: 3
max-retry-credentials: $maxRetry
max-retry-interval: 12
routing:
  strategy: "fill-first"
  session-affinity: $aff
  session-affinity-ttl: "${ttl}h"
codex:
  optimize-multi-agent-v2: true
"@
    Write-Utf8 (Join-Path ([string]$Instance.routerDir) 'config.yaml') $cfg
}
function Sync-CodexInstanceRouterCredentialPool {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexSeamlessRouterEnabled){return (Sync-CodexInstanceBoundCredential $Instance)}
    $desired=@(Get-CodexInstanceDesiredRouterAccounts $Instance)
    if($desired.Count -lt 1){throw 'SEAMLESS_POOL_EMPTY'}
    $authDir=Join-Path ([string]$Instance.routerDir) 'auth';Ensure-Dir $authDir
    $archive=Join-Path ([string]$Instance.routerDir) 'auth-archive';Ensure-Dir $archive
    $rows=[System.Collections.Generic.List[object]]::new();$keep=@{}
    for($idx=0;$idx -lt $desired.Count;$idx++){
        $email=[string]$desired[$idx]
        $acc=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $email.Trim().ToLowerInvariant()}|Select-Object -First 1)
        if($acc.Count -eq 0){if($idx -eq 0){throw "Primary account không còn trong pool: $email"}else{continue}}
        $source=$acc[0].File.FullName;$name=$acc[0].File.Name;$final=Join-Path $authDir $name;$keep[$name.ToLowerInvariant()]=$true
        $srcHash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        $routePriority=$null;$routeWeight=$null;$routeWebSockets=$null
        if(Test-Path -LiteralPath $final){
            try{
                $existing=Load-JsonObjectSafe $final
                if($existing -and $existing.PSObject.Properties['priority']){$routePriority=[int]$existing.priority}
                if($existing -and $existing.PSObject.Properties['weight']){$routeWeight=[int]$existing.weight}
                if([bool]$script:S.CodexPreserveWebSocketPreference -and $existing -and $existing.PSObject.Properties['websockets']){$routeWebSockets=$existing.websockets}
            }catch{}
        }
        $needs=$true
        if(Test-Path -LiteralPath $final){try{$needs=((Get-FileHash -LiteralPath $final -Algorithm SHA256).Hash.ToLowerInvariant() -ne $srcHash)}catch{}}
        if($needs){
            $tmp=$final+'.tmp-'+[Guid]::NewGuid().ToString('N')
            try{
                Copy-Item -LiteralPath $source -Destination $tmp -Force
                if((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $srcHash){throw 'SEAMLESS_CREDENTIAL_HASH_MISMATCH'}
                # v25.31: token refresh/pool sync must not erase instance-local Closed-loop routing metadata.
                if($null -ne $routePriority -or $null -ne $routeWeight -or $null -ne $routeWebSockets){
                    $fresh=Load-JsonObjectSafe $tmp
                    if($fresh){
                        if($null -ne $routePriority){$fresh|Add-Member -NotePropertyName priority -NotePropertyValue ([int]$routePriority) -Force}
                        if($null -ne $routeWeight){$fresh|Add-Member -NotePropertyName weight -NotePropertyValue ([int]$routeWeight) -Force}
                        if($null -ne $routeWebSockets){$fresh|Add-Member -NotePropertyName websockets -NotePropertyValue $routeWebSockets -Force}
                        Save-JsonAtomic $tmp $fresh
                    }
                }
                Move-Item -LiteralPath $tmp -Destination $final -Force
            }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
        }
        $finalHash=(Get-FileHash -LiteralPath $final -Algorithm SHA256).Hash.ToLowerInvariant()
        $rows.Add([ordered]@{slot=$idx;role=if($idx -eq 0){'PRIMARY'}else{'FALLBACK'};email=[string]$acc[0].Email;file=$name;sha256=$finalHash})
    }
    foreach($f in @(Get-ChildItem -LiteralPath $authDir -File -Filter 'codex-*.json' -ErrorAction SilentlyContinue)){
        if(-not $keep.ContainsKey($f.Name.ToLowerInvariant())){
            if([bool]$script:S.CodexSeamlessArchiveStaleCredentials){Move-Item -LiteralPath $f.FullName -Destination (Join-Path $archive ((Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+$f.Name)) -Force}
            else{throw 'SEAMLESS_STALE_CREDENTIAL_PRESENT'}
        }
    }
    if($rows.Count -lt 1){throw 'SEAMLESS_POOL_NO_VALID_CREDENTIAL'}
    $null=Invoke-HmsBoundedCredentialArchiveRetention -Root $archive -Keep ([Math]::Max(1,[int]$script:S.CodexBehaviorBackupKeepPerSourceInstance))
    Write-CodexInstanceRouterConfigV2530 $Instance $rows.Count
    $manifest=[ordered]@{schema_version=1;product='HMS-AI-ROUTER';version='25.31';instance_id=[string]$Instance.id;project=[string]$Instance.projectDir;stable_endpoint=('http://127.0.0.1:'+([int]$Instance.port)+'/v1');session_affinity=[bool]$script:S.CodexSeamlessSessionAffinity;session_ttl_hours=[int]$script:S.CodexSeamlessSessionTtlHours;accounts=@($rows);secret_fields_excluded=$true;updated_utc=[DateTime]::UtcNow.ToString('o')}
    Save-JsonAtomic (Get-CodexInstancePoolManifestPath $Instance) $manifest
    $null=Write-CodexInstanceBinding $Instance
    Add-CodexSeamlessRouterHistory 'POOL_SYNC' $Instance ('accounts='+$rows.Count+'; primary='+$rows[0].email)
    return ('Seamless Router pool synced: '+$rows.Count+' account(s) · endpoint http://127.0.0.1:'+([int]$Instance.port)+'/v1')
}
function Get-CodexInstanceSeamlessRouterSnapshot {
    param([object]$Instance)
    $path=Get-CodexInstancePoolManifestPath $Instance;$m=if(Test-Path -LiteralPath $path){Load-JsonObjectSafe $path}else{$null}
    $accounts=if($m){@($m.accounts)}else{@()}
    return [PSCustomObject]@{enabled=[bool]$script:S.CodexSeamlessRouterEnabled;endpoint=('http://127.0.0.1:'+([int]$Instance.port)+'/v1');manifest=$path;poolCount=$accounts.Count;accounts=@($accounts);routerOnline=(PortOpen ([int]$Instance.port));sessionAffinity=[bool]$script:S.CodexSeamlessSessionAffinity;ttlHours=[int]$script:S.CodexSeamlessSessionTtlHours}
}

# ---------------- v25.31 Project Affinity + Seamless Router ----------------

function Get-CodexProjectAffinityStore {
    $j=Load-JsonObjectSafe $script:CodexProjectAffinityPath
    if(-not $j){return [PSCustomObject]@{schemaVersion=1;product='HMS Codex Project Affinity';projects=@()}}
    if(-not $j.PSObject.Properties['projects']){$j|Add-Member -NotePropertyName projects -NotePropertyValue @() -Force}
    return $j
}
function Save-CodexProjectAffinityStore([object]$Store){
    if(-not $Store.PSObject.Properties['schemaVersion']){$Store|Add-Member -NotePropertyName schemaVersion -NotePropertyValue 1 -Force}
    if(-not $Store.PSObject.Properties['product']){$Store|Add-Member -NotePropertyName product -NotePropertyValue 'HMS Codex Project Affinity' -Force}
    Save-JsonAtomic $script:CodexProjectAffinityPath $Store
}
function Add-CodexProjectAffinityHistory {
    param([string]$Event,[string]$Project,[string]$InstanceId,[string]$Account,[string]$Message)
    try{
        $o=[ordered]@{time=[DateTime]::UtcNow.ToString('o');event=$Event;project=$Project;instance_id=$InstanceId;account=$Account;message=$Message}
        Add-Content -LiteralPath $script:CodexProjectAffinityHistoryPath -Value ($o|ConvertTo-Json -Compress) -Encoding UTF8
    }catch{}
}
function Get-CodexProjectAffinityByPath {
    param([string]$ProjectDir)
    $canon=Get-HmsCanonicalProjectPath $ProjectDir;$key=Get-HmsPathKey $canon
    $s=Get-CodexProjectAffinityStore
    return @($s.projects|Where-Object {(Get-HmsPathKey ([string]$_.projectDir)) -eq $key}|Select-Object -First 1)
}
function Convert-CodexAffinityFallbacks {
    param([object]$Values,[string]$Primary='')
    $known=@{};foreach($a in @(Get-CodexAccountRecords)){$known[$a.Email.Trim().ToLowerInvariant()]=$a.Email}
    $primaryKey=([string]$Primary).Trim().ToLowerInvariant()
    $out=[System.Collections.Generic.List[string]]::new();$seen=@{}
    $items=@()
    if($Values -is [string]){$items=@(([string]$Values) -split '[,;\r\n]+')}else{$items=@($Values)}
    foreach($raw in $items){
        $k=([string]$raw).Trim().ToLowerInvariant();if(-not $k -or $k -eq $primaryKey -or $seen.ContainsKey($k)){continue}
        if(-not $known.ContainsKey($k)){throw "Fallback account không tồn tại trong Codex pool: $raw"}
        $seen[$k]=$true;$out.Add([string]$known[$k])
        if($out.Count -ge [Math]::Max(0,[int]$script:S.CodexProjectFallbackMax)){break}
    }
    return @($out)
}
function Get-CodexAffinityAccountSnapshot {
    param([string]$Email)
    $r=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq ([string]$Email).Trim().ToLowerInvariant()}|Select-Object -First 1)
    if($r.Count -eq 0){return [PSCustomObject]@{email=$Email;exists=$false;status='MISSING';health=0;hourly=$null;weekly=$null;eligible=$false}}
    $rec=$r[0];$h=Get-CodexAccountHealth $rec;$q=Get-CodexQuotaForEmail $rec.Email
    $hourly=$null;$weekly=$null
    try{if($null -ne $q.hourlyRemaining){$hourly=[int]$q.hourlyRemaining}}catch{}
    try{if($null -ne $q.weeklyRemaining){$weekly=[int]$q.weeklyRemaining}}catch{}
    $eligible=([string]$rec.Status -eq 'READY')
    return [PSCustomObject]@{email=[string]$rec.Email;exists=$true;status=[string]$rec.Status;health=[int]$h.Score;grade=[string]$h.Grade;hourly=$hourly;weekly=$weekly;eligible=$eligible;reset=[string]$rec.Reset}
}
function Register-CodexProjectAffinityFromInstance {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexProjectAffinityEnabled){return $null}
    $project=Get-HmsCanonicalProjectPath ([string]$Instance.projectDir);$key=Get-HmsPathKey $project
    $store=Get-CodexProjectAffinityStore;$items=@($store.projects);$existing=@($items|Where-Object {(Get-HmsPathKey ([string]$_.projectDir)) -eq $key}|Select-Object -First 1)
    if($existing.Count){
        $x=$existing[0]
        if(-not $x.instanceId){$x|Add-Member -NotePropertyName instanceId -NotePropertyValue ([string]$Instance.id) -Force}
        if(([string]$x.instanceId) -eq ([string]$Instance.id)){$x|Add-Member -NotePropertyName preferredAccount -NotePropertyValue ([string]$Instance.accountEmail) -Force}
        if(-not $x.PSObject.Properties['fallbackAccounts']){$x|Add-Member -NotePropertyName fallbackAccounts -NotePropertyValue @() -Force}
        $x.fallbackAccounts=@(Convert-CodexAffinityFallbacks $x.fallbackAccounts ([string]$Instance.accountEmail))
        $x|Add-Member -NotePropertyName updatedUtc -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
    }else{
        $name=if($Instance.name){[string]$Instance.name}else{[IO.Path]::GetFileName($project)}
        $items += [PSCustomObject]@{schemaVersion=1;name=$name;projectDir=$project;projectKey=(Get-HmsStringSha256 $key);instanceId=[string]$Instance.id;preferredAccount=[string]$Instance.accountEmail;fallbackAccounts=@();lastLaunchUtc=$null;lastResolvedAccount=[string]$Instance.accountEmail;lastResolution='AUTO_REGISTER';updatedUtc=[DateTime]::UtcNow.ToString('o')}
        $store.projects=$items
    }
    Save-CodexProjectAffinityStore $store
    Add-CodexProjectAffinityHistory 'AUTO_REGISTER' $project ([string]$Instance.id) ([string]$Instance.accountEmail) 'Affinity auto-registered from isolated instance.'
    return @(Get-CodexProjectAffinityByPath $project)[0]
}
function Sync-CodexProjectAffinityFromInstances {
    if(-not [bool]$script:S.CodexProjectAutoRegisterInstances){return}
    $store=Get-CodexInstanceStore
    foreach($i in @($store.instances)){try{$null=Register-CodexProjectAffinityFromInstance $i}catch{}}
}
function Set-CodexProjectAffinity {
    param([string]$ProjectDir,[string]$InstanceId,[object]$FallbackAccounts,[string]$Name='')
    if(-not [bool]$script:S.CodexProjectAffinityEnabled){throw 'PROJECT_AFFINITY_DISABLED'}
    $project=Get-HmsCanonicalProjectPath $ProjectDir;$instance=Get-CodexInstanceById $InstanceId
    if((Get-HmsPathKey ([string]$instance.projectDir)) -ne (Get-HmsPathKey $project)){throw 'AFFINITY_INSTANCE_PROJECT_MISMATCH'}
    $primary=[string]$instance.accountEmail;$fallbacks=Convert-CodexAffinityFallbacks $FallbackAccounts $primary
    $store=Get-CodexProjectAffinityStore;$items=@($store.projects);$key=Get-HmsPathKey $project;$found=$false
    foreach($x in $items){
        if((Get-HmsPathKey ([string]$x.projectDir)) -eq $key){
            $found=$true;$x.name=if($Name){$Name}else{[string]$instance.name};$x.instanceId=[string]$instance.id;$x.preferredAccount=$primary
            $x.fallbackAccounts=@($fallbacks);$x.updatedUtc=[DateTime]::UtcNow.ToString('o');$x.projectKey=Get-HmsStringSha256 $key
        }
    }
    if(-not $found){$items += [PSCustomObject]@{schemaVersion=1;name=if($Name){$Name}else{[string]$instance.name};projectDir=$project;projectKey=(Get-HmsStringSha256 $key);instanceId=[string]$instance.id;preferredAccount=$primary;fallbackAccounts=@($fallbacks);lastLaunchUtc=$null;lastResolvedAccount=$primary;lastResolution='MANUAL_BIND';updatedUtc=[DateTime]::UtcNow.ToString('o')};$store.projects=$items}
    Save-CodexProjectAffinityStore $store
    Add-CodexProjectAffinityHistory 'SAVE' $project ([string]$instance.id) $primary ('Fallbacks='+(@($fallbacks)-join ','))
    return @(Get-CodexProjectAffinityByPath $project)[0]
}
function Resolve-CodexProjectAffinity {
    param([string]$ProjectDir)
    if([string]::IsNullOrWhiteSpace($ProjectDir)){return [PSCustomObject]@{ok=$false;state='PROJECT_MISSING';project='';reason='Project path trống.'}}
    if(-not (Test-Path -LiteralPath $ProjectDir -PathType Container)){return [PSCustomObject]@{ok=$false;state='PROJECT_MISSING';project=[string]$ProjectDir;reason='Project path hiện không khả dụng.'}}
    $project=Get-HmsCanonicalProjectPath $ProjectDir;$aff=@(Get-CodexProjectAffinityByPath $project)
    if($aff.Count -eq 0){return [PSCustomObject]@{ok=$false;state='UNMAPPED';project=$project;reason='Project chưa có affinity mapping.'}}
    $a=$aff[0];$inst=$null
    try{$inst=Get-CodexInstanceById ([string]$a.instanceId)}catch{return [PSCustomObject]@{ok=$false;state='INSTANCE_MISSING';project=$project;reason=$_.Exception.Message;affinity=$a}}
    if((Get-HmsPathKey ([string]$inst.projectDir)) -ne (Get-HmsPathKey $project)){return [PSCustomObject]@{ok=$false;state='PROJECT_MISMATCH';project=$project;reason='Mapped instance không còn trỏ đúng project.';affinity=$a}}
    $primary=Get-CodexAffinityAccountSnapshot ([string]$inst.accountEmail)
    $fallback=$null
    foreach($f in @($a.fallbackAccounts)){$snap=Get-CodexAffinityAccountSnapshot ([string]$f);if($snap.eligible){$fallback=$snap;break}}
    $running=Test-CodexInstanceClientOwned $inst
    $state=if($running){'RUNNING'}elseif($primary.eligible){'READY'}elseif($fallback -and [bool]$script:S.CodexSeamlessRouterEnabled){'SEAMLESS_FALLBACK_READY'}elseif($fallback){'FALLBACK_RECOMMENDED'}else{'BLOCKED'}
    $reason=if($running){'Mapped instance đang chạy qua stable endpoint; Router giữ session affinity.'}elseif($primary.eligible){'Primary account READY; seamless pool sẽ giữ fallback phía sau cùng endpoint.'}elseif($fallback -and [bool]$script:S.CodexSeamlessRouterEnabled){'Primary chưa READY; fallback khả dụng có thể được Router dùng phía sau stable endpoint mà không đổi Codex config.'}elseif($fallback){'Fallback khả dụng nhưng Seamless Router đang OFF.'}else{"Primary account không READY: $($primary.status)"}
    return [PSCustomObject]@{ok=($state -in @('RUNNING','READY','SEAMLESS_FALLBACK_READY'));state=$state;project=$project;affinity=$a;instance=$inst;primary=$primary;fallback=$fallback;clientRunning=$running;reason=$reason;router=(Get-CodexInstanceSeamlessRouterSnapshot $inst)}
}
function Start-CodexProjectAffinity {
    param([string]$ProjectDir)
    $r=Resolve-CodexProjectAffinity $ProjectDir
    if($r.state -eq 'RUNNING' -and [bool]$script:S.CodexProjectFocusIfRunning){$msg=Focus-CodexInstance ([string]$r.instance.id)}
    elseif($r.state -eq 'READY'){$msg=Start-CodexInstanceSafe ([string]$r.instance.id)}
    elseif($r.state -eq 'SEAMLESS_FALLBACK_READY'){
        $pool=Sync-CodexInstanceRouterCredentialPool $r.instance
        $msg=(($pool,(Start-CodexInstanceSafe ([string]$r.instance.id))) -join "`r`n")
    }
    elseif($r.state -eq 'FALLBACK_RECOMMENDED'){
        if([bool]$script:S.CodexProjectBlockUnhealthyPrimary){throw "AFFINITY_PRIMARY_UNHEALTHY: $($r.primary.status). Fallback đề xuất: $($r.fallback.email). Bật Seamless Router để dùng fallback an toàn phía sau endpoint cố định."}
        $msg=Start-CodexInstanceSafe ([string]$r.instance.id)
    }else{throw "PROJECT_AFFINITY_BLOCKED: $($r.reason)"}
    $store=Get-CodexProjectAffinityStore;$key=Get-HmsPathKey $r.project
    foreach($x in @($store.projects)){if((Get-HmsPathKey ([string]$x.projectDir)) -eq $key){$x.lastLaunchUtc=[DateTime]::UtcNow.ToString('o');$x.lastResolvedAccount=[string]$r.instance.accountEmail;$x.lastResolution=[string]$r.state;$x.updatedUtc=[DateTime]::UtcNow.ToString('o')}}
    Save-CodexProjectAffinityStore $store
    Add-CodexProjectAffinityHistory 'LAUNCH' $r.project ([string]$r.instance.id) ([string]$r.instance.accountEmail) ([string]$r.state)
    return [string]$msg
}

# ---------------- Wake-up / keep-warm (opt-in only) ----------------

function Invoke-CodexWakeupNow {
    if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."}
    $models=Invoke-RestMethod -Uri ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/v1/models") -Headers @{Authorization=("Bearer "+[string]$script:S.LocalApiKey)} -TimeoutSec 10
    $model=[string]$script:S.CodexWakeupModel
    if([string]::IsNullOrWhiteSpace($model)){
        $m=@($models.data|ForEach-Object {$_.id}|Where-Object {$_ -match '^gpt-|codex'}| Select-Object -First 1)
        if($m.Count -eq 0){throw "Không tìm được model Codex để wake-up."}
        $model=$m[0]
    }
    $body=@{
        model=$model
        input=[string]$script:S.CodexWakeupPrompt
        max_output_tokens=[int]$script:S.CodexWakeupMaxOutputTokens
    }| ConvertTo-Json -Depth 5
    $r=Invoke-RestMethod -Uri ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/v1/responses") -Method Post -Headers @{Authorization=("Bearer "+[string]$script:S.LocalApiKey)} -ContentType "application/json" -Body $body -TimeoutSec 60
    Add-CodexRouteHistory "WAKEUP" ("Wake-up model "+$model) ""
    return "Wake-up PASS — model $model"
}


# ============================================================

# v25.54 PRODUCTION SIMULATION / FAULT-INJECTION LAB
function Invoke-HmsProductionSimulationLab([switch]$Replay){
    Ensure-Dir $script:ProductionSimulationDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_ProductionSimulationLab.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_ProductionSimulationLab.py'}
    $out=$(if($Replay){$script:ProductionSimulationReplayPath}else{$script:ProductionSimulationLatestPath})
    $seeds=$(if($Replay){'991'}else{'11,23,37,41,59,73,89,101'})
    $cycles=$(if($Replay){300}else{300})
    $py=(Get-Command py.exe -ErrorAction SilentlyContinue)
    if($py){& $py.Source -3 $tool --root $PSScriptRoot --seeds $seeds --cycles $cycles --output $out | Out-Null}
    else{
        $python=(Get-Command python.exe -ErrorAction SilentlyContinue)
        if(-not $python){throw 'Không tìm thấy Python để chạy Production Simulation Lab.'}
        & $python.Source $tool --root $PSScriptRoot --seeds $seeds --cycles $cycles --output $out | Out-Null
    }
    if($LASTEXITCODE -ne 0){throw ('Simulation Lab failed. exit='+[string]$LASTEXITCODE)}
    return (Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json)
}
function Format-HmsProductionSimulation([object]$r){
    if(-not $r){return 'Chưa có simulation evidence.'}
    $sm=$r.summary
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add('VERDICT: '+[string]$r.verdict)
    $lines.Add(('SEEDS: {0} · CYCLES: {1} · INVARIANT FAIL: {2}' -f $sm.seeds,$sm.total_cycles,$sm.invariant_failures))
    $lines.Add(('FAULT EVENTS: {0}/{1} · QUOTA MATRIX: {2}/{3}' -f $sm.events_exercised,$sm.events_required,$sm.quota_matrix_pass,$sm.quota_matrix_total))
    $lines.Add(('REPLAY: {0}/{1}' -f $sm.replay_pass,$sm.replay_total))
    try{$lines.Add(('ROTATION: {0} · LAN FAILURE MATRIX: {1}' -f $r.focused_runtime_faults.rotation.pass,$r.focused_runtime_faults.lan_failure_matrix.pass))}catch{}
    $lines.Add('')
    $lines.Add('SIMULATION ONLY · không tiêu quota · không gửi Codex request thật · không thay thế production certificate.')
    return ($lines -join "`r`n")
}
function Show-HmsProductionSimulationLab {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Production Simulation Lab · v25.54';$w.Size=New-Object Drawing.Size(920,590);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='PRODUCTION SIMULATION LAB v25.54';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='Digital twin · deterministic multi-seed fault injection · quota/429/crash/auth/backpressure/SMB/LAN/clock-skew · replayable trace hash.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(850,42);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bRun=Btn 'SIM LAB' 22 110 130 38;$bRun.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bRun)
    $bReplay=Btn 'REPLAY' 165 110 120 38;$w.Controls.Add($bReplay)
    $bEv=Btn 'MỞ EVIDENCE' 298 110 145 38;$w.Controls.Add($bEv)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,166);$out.Size=New-Object Drawing.Size(850,300);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: synthetic-only; không đọc/ghi auth thật; không tiêu quota; không đụng SMB/NAS thật; không thể phát PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED.';$safe.Location=New-Object Drawing.Point(22,482);$safe.Size=New-Object Drawing.Size(850,45);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshSim {if(Test-Path -LiteralPath $script:ProductionSimulationLatestPath){try{$j=Get-Content -LiteralPath $script:ProductionSimulationLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsProductionSimulation $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có simulation evidence. Bấm SIM LAB.'}}
    $bRun.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsProductionSimulationLab;$out.Text=Format-HmsProductionSimulation $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bReplay.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsProductionSimulationLab -Replay;$out.Text=Format-HmsProductionSimulation $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:ProductionSimulationDir;Start-Process explorer.exe $script:ProductionSimulationDir|Out-Null})
    $w.Add_Shown({RefreshSim});[void]$w.ShowDialog($form)
}


# v25.55 AUTONOMOUS ROUTER DIGITAL TWIN + BOUNDED MODEL CHECK
function Invoke-HmsAutonomousRouterDigitalTwin([switch]$ModelCheck){
    Ensure-Dir $script:AutonomousRouterTwinDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_AutonomousRouterDigitalTwin.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_AutonomousRouterDigitalTwin.py'}
    $out=$(if($ModelCheck){$script:AutonomousRouterTwinModelPath}else{$script:AutonomousRouterTwinLatestPath})
    $args=@('--root',$PSScriptRoot,'--output',$out)
    if($ModelCheck){$args+=@('--seeds','2555,2556','--cycles','160','--accounts','16','--instances','8','--projects','12')}
    else{$args+=@('--seeds','13,29,47,61,79,97','--cycles','300','--accounts','32','--instances','12','--projects','24')}
    $py=(Get-Command py.exe -ErrorAction SilentlyContinue)
    if($py){& $py.Source -3 $tool @args | Out-Null}
    else{
        $python=(Get-Command python.exe -ErrorAction SilentlyContinue)
        if(-not $python){throw 'Không tìm thấy Python để chạy Autonomous Router Digital Twin.'}
        & $python.Source $tool @args | Out-Null
    }
    if($LASTEXITCODE -ne 0){throw ('Autonomous Router Digital Twin failed. exit='+[string]$LASTEXITCODE)}
    return (Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json)
}
function Format-HmsAutonomousRouterDigitalTwin([object]$r){
    if(-not $r){return 'Chưa có Autonomous Router Twin evidence.'}
    $sm=$r.summary;$fair=@($r.seed_runs|ForEach-Object {$_.fairness.jain})
    $minFair=$(if($fair.Count){($fair|Measure-Object -Minimum).Minimum}else{0})
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add('VERDICT: '+[string]$r.verdict)
    $lines.Add(('POOL: {0} accounts · {1} instances · {2} projects' -f $sm.accounts,$sm.instances,$sm.projects))
    $lines.Add(('SEEDS: {0}/{1} · CYCLES: {2} · EVENTS: {3}/{4}' -f $sm.seed_pass,$sm.seed_total,$sm.total_cycles,$sm.events_exercised,$sm.events_required))
    $lines.Add(('MODEL STATES: {0} · TRACE MIN: {1} -> {2}' -f $sm.model_states_checked,$sm.trace_minimized_from,$sm.trace_minimized_to))
    $lines.Add(('REPLAY: {0}/{1} · MIN FAIRNESS: {2:N3}' -f $sm.replay_pass,$sm.replay_total,[double]$minFair))
    try{$lines.Add(('ADVERSARIAL: {0} · STALE HIGH-QUOTA BLOCK: {1}' -f $r.adversarial_ordering.pass,$r.adversarial_ordering.stale_high_quota_blocked))}catch{}
    $lines.Add('')
    $lines.Add('DIGITAL TWIN ONLY · không gửi Codex request thật · không đọc auth thật · không thay thế target-machine production certificate.')
    return ($lines -join "`r`n")
}
function Show-HmsAutonomousRouterDigitalTwin {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Autonomous Router Digital Twin · v25.55';$w.Size=New-Object Drawing.Size(960,640);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='AUTONOMOUS ROUTER DIGITAL TWIN v25.55';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='32 account · 12 instance · 24 project · dynamic weights · adversarial ordering · bounded state model checking · failing-trace minimization.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(900,44);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bRun=Btn 'TWIN RUN' 22 112 135 38;$bRun.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bRun)
    $bModel=Btn 'MODEL CHECK' 170 112 145 38;$w.Controls.Add($bModel)
    $bEv=Btn 'MỞ EVIDENCE' 328 112 145 38;$w.Controls.Add($bEv)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,168);$out.Size=New-Object Drawing.Size(910,350);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: synthetic-only; stale/reserve fail-closed; recovery không kéo session cũ quay lại; project/session affinity giữ nguyên trừ hard failure; không thể phát production certificate.';$safe.Location=New-Object Drawing.Point(22,535);$safe.Size=New-Object Drawing.Size(900,50);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshTwin {if(Test-Path -LiteralPath $script:AutonomousRouterTwinLatestPath){try{$j=Get-Content -LiteralPath $script:AutonomousRouterTwinLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsAutonomousRouterDigitalTwin $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có evidence. Bấm TWIN RUN.'}}
    $bRun.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsAutonomousRouterDigitalTwin;$out.Text=Format-HmsAutonomousRouterDigitalTwin $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bModel.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsAutonomousRouterDigitalTwin -ModelCheck;$out.Text=Format-HmsAutonomousRouterDigitalTwin $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:AutonomousRouterTwinDir;Start-Process explorer.exe $script:AutonomousRouterTwinDir|Out-Null})
    $w.Add_Shown({RefreshTwin});[void]$w.ShowDialog($form)
}

# v25.56 PROTOCOL CHAOS / API COMPATIBILITY FUZZER
# Synthetic-only. No real Codex request, no auth mutation, no midstream replay.
# ============================================================
function Invoke-HmsProtocolChaosFuzzer {
    Ensure-Dir $script:ProtocolChaosDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_ProtocolChaosFuzzer.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_ProtocolChaosFuzzer.py'}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments @('--root',$PSScriptRoot,'--seed','2556','--cases','300','--output',$script:ProtocolChaosLatestPath)
    return $j.data
}
function Format-HmsProtocolChaos([object]$r){
    if(-not $r){return 'Chưa có evidence.'}
    $lines=[System.Collections.Generic.List[string]]::new();$lines.Add('VERDICT: '+[string]$r.verdict)
    try{$lines.Add(('TESTS: {0}/{1} · FUZZ CASES: {2} · SEED: {3}' -f $r.summary.pass,$r.summary.total,$r.summary.fuzz_cases,$r.summary.seed))}catch{}
    $lines.Add('SSE: partial-frame + terminal integrity + truncated EOF health penalty; partial stream không replay.')
    $lines.Add('WebSocket: malformed 101 / missing-or-wrong Sec-WebSocket-Accept bị reject trước relay và failover bounded.')
    $lines.Add('HTTP/JSON: Content-Length mismatch, malformed error, chunked parser mutation, retry budget + idempotency boundary.')
    $lines.Add('SYNTHETIC ONLY · không gọi Codex thật · không tiêu quota · không ghi prompt/request/response body.')
    return ($lines -join "`r`n")
}
function Show-HmsProtocolChaosCenter {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Protocol Chaos / API Fuzzer · v25.56';$w.Size=New-Object Drawing.Size(930,610);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='PROTOCOL CHAOS / API FUZZ v25.56';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='300 deterministic case · SSE / WebSocket / JSON / chunked / retry / early EOF · synthetic-only.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(860,38);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bRun=Btn 'FUZZ 300' 22 105 135 38;$bRun.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bRun)
    $bEv=Btn 'MỞ EVIDENCE' 170 105 145 38;$w.Controls.Add($bEv)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,160);$out.Size=New-Object Drawing.Size(870,320);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: malformed 101 không được relay; truncated SSE không được replay; client disconnect không phạt upstream; synthetic evidence không thể cấp production certificate.';$safe.Location=New-Object Drawing.Point(22,500);$safe.Size=New-Object Drawing.Size(860,50);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshChaos {if(Test-Path -LiteralPath $script:ProtocolChaosLatestPath){try{$j=Get-Content -LiteralPath $script:ProtocolChaosLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsProtocolChaos $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có evidence. Bấm FUZZ 300.'}}
    $bRun.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsProtocolChaosFuzzer;$out.Text=Format-HmsProtocolChaos $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:ProtocolChaosDir;Start-Process explorer.exe $script:ProtocolChaosDir|Out-Null})
    $w.Add_Shown({RefreshChaos});[void]$w.ShowDialog($form)
}

# v25.57 RECOVERY PLANNER / SELF-HEALING DECISION PROOF
# Synthetic-only cause-aware recovery proof. Never kills unowned processes, mutates auth, or mints production certification.
# ============================================================
function Invoke-HmsRecoveryPlannerProof {
    param([switch]$ModelCheck)
    Ensure-Dir $script:RecoveryPlannerDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_RecoveryPlanner.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_RecoveryPlanner.py'}
    $mode=if($ModelCheck){'model-check'}else{'proof'}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments @('--mode',$mode,'--output',$script:RecoveryPlannerLatestPath)
    return $j.data
}
function Format-HmsRecoveryPlanner([object]$r){
    if(-not $r){return 'Chưa có evidence.'}
    $lines=[System.Collections.Generic.List[string]]::new();$lines.Add('VERDICT: '+[string]$r.verdict)
    try{$lines.Add(('TESTS: {0}/{1} · MODEL STATES: {2}' -f $r.summary.pass,$r.summary.total,$r.summary.model_states))}catch{}
    $lines.Add('Policy: 429/quota chỉ HOLD/rotate session mới; không restart process và không kéo session đang chạy khỏi affinity.')
    $lines.Add('Restart: chỉ process HMS-owned, bounded max-attempt + verify; foreign port/auth/identity drift luôn fail-closed.')
    $lines.Add('Config repair: atomic + readback + rollback; thiếu backup thì từ chối mutation. Recovery loop >=3 lần mở circuit và escalation.')
    $lines.Add('SYNTHETIC ONLY · không gọi Codex thật · không sửa auth · không kill process · không thể phát production certificate.')
    return ($lines -join "`r`n")
}
function Show-HmsRecoveryPlannerCenter {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Recovery Planner / Self-Healing Proof · v25.57';$w.Size=New-Object Drawing.Size(950,630);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='RECOVERY PLANNER / SELF-HEALING PROOF v25.57';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='Cause-aware recovery · bounded retry/restart · loop breaker · rollback proof · 9,216-state model checker.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(880,40);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bRun=Btn 'PROOF' 22 108 130 38;$bRun.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bRun)
    $bModel=Btn 'MODEL CHECK' 166 108 145 38;$w.Controls.Add($bModel)
    $bEv=Btn 'MỞ EVIDENCE' 325 108 145 38;$w.Controls.Add($bEv)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,165);$out.Size=New-Object Drawing.Size(890,345);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: không restart process lạ; 429/quota không restart; session affinity giữ nguyên; lease takeover cần signed+expired; config mutation cần rollback; loop breaker chống recovery storm.';$safe.Location=New-Object Drawing.Point(22,530);$safe.Size=New-Object Drawing.Size(880,52);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshRecovery {if(Test-Path -LiteralPath $script:RecoveryPlannerLatestPath){try{$j=Get-Content -LiteralPath $script:RecoveryPlannerLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsRecoveryPlanner $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có evidence. Bấm PROOF.'}}
    $bRun.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsRecoveryPlannerProof;$out.Text=Format-HmsRecoveryPlanner $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bModel.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsRecoveryPlannerProof -ModelCheck;$out.Text=Format-HmsRecoveryPlanner $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:RecoveryPlannerDir;Start-Process explorer.exe $script:RecoveryPlannerDir|Out-Null})
    $w.Add_Shown({RefreshRecovery});[void]$w.ShowDialog($form)
}

# v25.58 COMPOUND-FAULT RECOVERY CONVERGENCE LAB
# Synthetic-only recovery DAG + global budget + convergence proof. Never mutates auth or mints production certification.
# ============================================================
function Invoke-HmsCompoundFaultRecovery {
    param([switch]$ModelCheck)
    Ensure-Dir $script:CompoundFaultRecoveryDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_CompoundFaultRecovery.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_CompoundFaultRecovery.py'}
    $mode=if($ModelCheck){'model-check'}else{'proof'}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments @('--mode',$mode,'--output',$script:CompoundFaultRecoveryLatestPath)
    return $j.data
}
function Format-HmsCompoundFaultRecovery([object]$r){
    if(-not $r){return 'Chưa có evidence.'}
    $lines=[System.Collections.Generic.List[string]]::new();$lines.Add('VERDICT: '+[string]$r.verdict)
    try{$lines.Add(('TESTS: {0}/{1} · MODEL STATES: {2}' -f $r.summary.pass,$r.summary.total,$r.summary.model_states))}catch{}
    $lines.Add('DAG: gộp dependency của quota/process/config/network/LAN; hard auth/identity/foreign ownership luôn quarantine trước mutation.')
    $lines.Add('Budget: restart/repair/retry có global cost cap; hết budget => stop auto recovery + escalation thay vì recovery storm.')
    $lines.Add('Convergence: chỉ HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED; existing session không rotate vì quota.')
    $lines.Add('SYNTHETIC ONLY · không gọi Codex thật · không sửa auth · không kill process · không thể phát production certificate.')
    return ($lines -join "`r`n")
}
function Show-HmsCompoundFaultRecoveryCenter {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Compound-Fault Recovery Convergence · v25.58';$w.Size=New-Object Drawing.Size(970,640);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='COMPOUND-FAULT CONVERGENCE v25.58';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='Recovery DAG · global recovery budget · compound quota/process/config/network/LAN faults · 72k+ state model checker.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(900,40);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bRun=Btn 'CONVERGENCE' 22 108 145 38;$bRun.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bRun)
    $bModel=Btn 'MODEL 72K' 181 108 145 38;$w.Controls.Add($bModel)
    $bEv=Btn 'MỞ EVIDENCE' 340 108 145 38;$w.Controls.Add($bEv)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,165);$out.Size=New-Object Drawing.Size(910,350);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: hard operator faults dominate; no unowned restart; quota never causes restart; signed+expired lease required; global budget + bounded rounds prevent recovery storm.';$safe.Location=New-Object Drawing.Point(22,535);$safe.Size=New-Object Drawing.Size(900,54);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshCompound {if(Test-Path -LiteralPath $script:CompoundFaultRecoveryLatestPath){try{$j=Get-Content -LiteralPath $script:CompoundFaultRecoveryLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsCompoundFaultRecovery $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có evidence. Bấm CONVERGENCE.'}}
    $bRun.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsCompoundFaultRecovery;$out.Text=Format-HmsCompoundFaultRecovery $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bModel.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsCompoundFaultRecovery -ModelCheck;$out.Text=Format-HmsCompoundFaultRecovery $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:CompoundFaultRecoveryDir;Start-Process explorer.exe $script:CompoundFaultRecoveryDir|Out-Null})
    $w.Add_Shown({RefreshCompound});[void]$w.ShowDialog($form)
}


$script:OfficialAuthCompatDir = Join-Path $script:DataDir "official-auth-compat-v2559"
$script:OfficialAuthCompatLatestPath = Join-Path $script:OfficialAuthCompatDir "official-auth-compat-latest-v2559.json"
$script:CodexOfficialAuthSnapshotCredentialTarget = "HMS-AI-ROUTER Codex Auth Switch Snapshot"

# v25.60 RECOVERY TRANSACTION JOURNAL / CRASH-CONSISTENT RESUME
function Invoke-HmsRecoveryJournalPhase {
    param([string]$TxnId,[string]$Action,[string]$Phase,[string]$Scope,[string]$ResultHash="")
    if(-not [bool]$script:S.RecoveryJournalEnabled){return $null}
    Ensure-Dir $script:RecoveryJournalDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_RecoveryTransactionJournal.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'RECOVERY_JOURNAL_HELPER_MISSING'}
    $scopeHash=if($Scope){Get-HmsStringSha256 $Scope}else{''}
    $meta=(@{scope_hash=$scopeHash;source='native-powershell';version=$script:Version}|ConvertTo-Json -Compress)
    $args=@('--mode','append','--journal',$script:RecoveryJournalPath,'--txn-id',$TxnId,'--action',$Action,'--phase',$Phase,'--idempotency-key',$TxnId,'--meta-json',$meta)
    if($ResultHash){$args+=@('--result-hash',$ResultHash)}
    return (Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args)
}
function Get-HmsRecoveryJournalResume {
    if(-not (Test-Path -LiteralPath $script:RecoveryJournalPath -PathType Leaf)){return @{ok=$true;version=$script:Version;decisions=@();chain=@{ok=$true;records=0;head_hash='GENESIS'}}}
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_RecoveryTransactionJournal.py'
    return (Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments @('--mode','resume','--journal',$script:RecoveryJournalPath))
}

# v25.59 OFFICIAL AUTH COMPATIBILITY LAYER (P0)
# Live mutation is Windows-only and serialized. Raw rollback snapshot lives only in Windows Credential Manager.
function Get-HmsCodexOfficialAuthFilePath {
    $codexHome=[string]$env:CODEX_HOME
    if([string]::IsNullOrWhiteSpace($codexHome)){$codexHome=$script:CodexDir}
    $codexHome=$codexHome.Trim().Trim('"').Trim("'")
    return (Join-Path $codexHome 'auth.json')
}
function Get-HmsCodexOfficialStoreKey {
    $path=Get-HmsCodexOfficialAuthFilePath;$codexHome=Split-Path -Parent $path
    try{$codexHome=[IO.Path]::GetFullPath($codexHome)}catch{}
    $sha=[Security.Cryptography.SHA256]::Create();try{$bytes=[Text.Encoding]::UTF8.GetBytes($codexHome);$hash=$sha.ComputeHash($bytes);$hex=([BitConverter]::ToString($hash)).Replace('-','').ToLowerInvariant();return ('cli|'+$hex.Substring(0,16))}finally{$sha.Dispose()}
}
function Get-HmsCodexOfficialKeyringTarget {return (([string]$script:S.CodexOfficialAuthKeyringEntry)+':'+(Get-HmsCodexOfficialStoreKey))}
function Get-HmsCodexOfficialKeyringBackendKind {
    $config=Join-Path (Split-Path -Parent (Get-HmsCodexOfficialAuthFilePath)) 'config.toml'
    if(Test-Path -LiteralPath $config){
        try{
            $raw=[IO.File]::ReadAllText($config)
            if($raw -match '(?im)^\s*secret_auth_storage\s*=\s*true\s*(?:#.*)?$'){return 'secrets'}
        }catch{}
    }
    return 'direct'
}
function Assert-HmsCodexOfficialDirectKeyringBackend {
    if((Get-HmsCodexOfficialKeyringBackendKind) -eq 'secrets'){throw 'OFFICIAL_KEYRING_SECRETS_BACKEND_REQUIRES_CODEX_HELPER'}
}
function Get-HmsCodexOfficialAuthStoreMode {
    $requested=([string]$script:S.CodexOfficialAuthStoreMode).Trim().ToLowerInvariant()
    if($requested -notin @('file','keyring','auto')){$requested='auto'}
    if($requested -ne 'auto'){return $requested}
    $config=Join-Path (Split-Path -Parent (Get-HmsCodexOfficialAuthFilePath)) 'config.toml'
    if(Test-Path -LiteralPath $config){try{$raw=[IO.File]::ReadAllText($config);if($raw -match '(?im)^\s*cli_auth_credentials_store\s*=\s*["''](file|keyring|auto|ephemeral)["'']'){$m=$matches[1].ToLowerInvariant();if($m -eq 'ephemeral'){throw 'OFFICIAL_AUTH_EPHEMERAL_NOT_SWITCHABLE'};if($m -in @('file','keyring')){return $m}}}catch{if($_.Exception.Message -eq 'OFFICIAL_AUTH_EPHEMERAL_NOT_SWITCHABLE'){throw}}}
    $kr=Read-HmsCodexOfficialKeyringJson;if($null -ne $kr){return 'keyring'}
    return 'file'
}
function Read-HmsCodexOfficialKeyringJson {
    Assert-HmsCodexOfficialDirectKeyringBackend
    try{$u='';$raw=[HmsCredentialManager]::ReadGeneric((Get-HmsCodexOfficialKeyringTarget),[ref]$u);if([string]::IsNullOrWhiteSpace($raw)){return $null};return ($raw|ConvertFrom-Json)}catch{return $null}
}
function Write-HmsCodexOfficialKeyringJson([object]$Payload){
    Assert-HmsCodexOfficialDirectKeyringBackend
    $raw=$Payload|ConvertTo-Json -Depth 30 -Compress
    [HmsCredentialManager]::WriteGeneric((Get-HmsCodexOfficialKeyringTarget),(Get-HmsCodexOfficialStoreKey),$raw)
}
function Read-HmsCodexOfficialAuthJson([string]$Mode=''){
    if(-not $Mode){$Mode=Get-HmsCodexOfficialAuthStoreMode}
    if($Mode -eq 'keyring'){$j=Read-HmsCodexOfficialKeyringJson;if($null -eq $j){throw 'OFFICIAL_KEYRING_READ_FAILED'};return $j}
    $path=Get-HmsCodexOfficialAuthFilePath;if(-not (Test-Path -LiteralPath $path -PathType Leaf)){return [pscustomobject]@{}}
    return ([IO.File]::ReadAllText($path)|ConvertFrom-Json)
}
function Write-HmsCodexOfficialAuthJson([object]$Payload,[string]$Mode){
    if($Mode -eq 'keyring'){Write-HmsCodexOfficialKeyringJson $Payload;$path=Get-HmsCodexOfficialAuthFilePath;if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue};return}
    $path=Get-HmsCodexOfficialAuthFilePath;$dir=Split-Path -Parent $path;Ensure-Dir $dir
    $tmp=Join-Path $dir ('.auth.json.hms-'+[Guid]::NewGuid().ToString('N')+'.tmp');$raw=$Payload|ConvertTo-Json -Depth 30
    try{[IO.File]::WriteAllText($tmp,$raw,(New-Object Text.UTF8Encoding($false)));if(Test-Path -LiteralPath $path){$bak=$path+'.hms-bak';[IO.File]::Replace($tmp,$path,$bak,$true);Remove-Item -LiteralPath $bak -Force -ErrorAction SilentlyContinue}else{Move-Item -LiteralPath $tmp -Destination $path -Force}}finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
}
function Get-HmsCodexAuthFingerprint([object]$Payload){$raw=$Payload|ConvertTo-Json -Depth 30 -Compress;$sha=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($raw)))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}}
function ConvertTo-HmsCodexOfficialAuthProjection([object]$Current,[object]$Target){
    # STALE_AUTH credential/account identity keys are always removed before target projection.
    $STALE_AUTH=@('access_token','refresh_token','id_token','session_id','expired','last_refresh','expires_in','timestamp','token_type','user_code','verification_uri','verification_uri_complete','OPENAI_API_KEY','personal_access_token','tokens','agent_identity','auth_mode','base_url','api_base_url','email','account_email','account_name','account_id','chatgpt_account_id','chatgpt_user_id','user_id','type')
    $out=[ordered]@{};if($Current){foreach($p in $Current.PSObject.Properties){if($p.Name -notin $STALE_AUTH){$out[$p.Name]=$p.Value}}}
    $kind=if($Target.tokens){'chatgpt'}elseif($Target.OPENAI_API_KEY){'apikey'}else{([string]$Target.auth_mode).ToLowerInvariant()}
    if($kind -eq 'chatgpt'){
        $tokens=[ordered]@{};foreach($p in $Target.tokens.PSObject.Properties){$tokens[$p.Name]=$p.Value};if(-not $tokens.Contains('refresh_token')){$tokens['refresh_token']=''}
        $out['auth_mode']='chatgpt';$out['type']='codex';$out['OPENAI_API_KEY']=$null;$out['tokens']=[pscustomobject]$tokens
        if($Target.PSObject.Properties['last_refresh']){$out['last_refresh']=$Target.last_refresh}
        if($Target.PSObject.Properties['agent_identity']){$out['agent_identity']=$Target.agent_identity}
    }
    elseif($kind -in @('apikey','api_key')){if([string]::IsNullOrWhiteSpace([string]$Target.OPENAI_API_KEY)){throw 'OFFICIAL_AUTH_API_KEY_REQUIRED'};$out['auth_mode']='apikey';$out['OPENAI_API_KEY']=$Target.OPENAI_API_KEY}
    else{throw 'OFFICIAL_AUTH_KIND_UNKNOWN'}
    return [pscustomobject]$out
}
function Sync-HmsCurrentOfficialAuthToManagedAccount([object]$Current){
    if(-not $Current -or -not $Current.tokens){return 'NO_CURRENT_OAUTH_TO_SYNC'}
    $aid=[string](Get-DeepValue $Current.tokens @('account_id','chatgpt_account_id'));if([string]::IsNullOrWhiteSpace($aid)){return 'CURRENT_ACCOUNT_ID_UNKNOWN'}
    $matches=@(Get-CodexAccountRecords|Where-Object{([string](Get-DeepValue $_.Json @('account_id','chatgpt_account_id')) -eq $aid) -or ([string](Get-DeepValue $_.Json.tokens @('account_id','chatgpt_account_id')) -eq $aid)})
    if($matches.Count -ne 1){return 'CURRENT_ACCOUNT_MAPPING_NOT_UNIQUE'}
    $row=$matches[0];$merged=ConvertTo-HmsCodexOfficialAuthProjection $row.Json $Current;Save-JsonAtomic $row.File.FullName $merged;return 'SYNCED_CURRENT_ACCOUNT_LATEST_AUTH'
}
function Snapshot-HmsCodexOfficialAuthState([object]$Current){$raw=$Current|ConvertTo-Json -Depth 30 -Compress;[HmsCredentialManager]::WriteGeneric($script:CodexOfficialAuthSnapshotCredentialTarget,'HMS',$raw);return (Get-HmsCodexAuthFingerprint $Current)}
function Restore-HmsCodexOfficialAuthSnapshot([string]$Mode){$u='';$raw=[HmsCredentialManager]::ReadGeneric($script:CodexOfficialAuthSnapshotCredentialTarget,[ref]$u);if([string]::IsNullOrWhiteSpace($raw)){throw 'AUTH_SWITCH_SNAPSHOT_MISSING'};Write-HmsCodexOfficialAuthJson ($raw|ConvertFrom-Json) $Mode}
function Clear-HmsCodexOfficialAuthSnapshot {try{[HmsCredentialManager]::DeleteGeneric($script:CodexOfficialAuthSnapshotCredentialTarget)}catch{}}
function Get-HmsCodexOfficialHttpIdentity {
    $origin=([string]$script:S.CodexOfficialOriginator).Trim();if([string]::IsNullOrWhiteSpace($origin)){$origin='codex_vscode'}
    $ua=([string]$script:S.CodexOfficialAuthUserAgent).Trim()
    try{
        $codex=Get-Command codex -ErrorAction SilentlyContinue
        if($codex){$v=((& $codex.Source --version 2>$null)|Out-String).Trim();if($v -match '([0-9]+(?:\.[0-9A-Za-z-]+)+)'){$ua=$origin+'/'+$matches[1]}}
    }catch{}
    if([string]::IsNullOrWhiteSpace($ua)){$ua='codex_vscode/0.146.0'}
    return [pscustomobject]@{originator=$origin;user_agent=$ua;source='installed-codex-version-or-compat-fallback'}
}
function Invoke-HmsCodexOfficialAuthSwitch([string]$Email){
    $mutex=New-Object Threading.Mutex($false,'Local\HMS_Codex_OfficialAuthSwitch_v1');$locked=$false;$mode='';$txn=('rtx-'+[Guid]::NewGuid().ToString('N'));$journalPrepared=$false;$journalCommitted=$false
    try{
        $locked=$mutex.WaitOne(8000);if(-not $locked){throw 'AUTH_SWITCH_SERIALIZATION_TIMEOUT'}
        $mode=Get-HmsCodexOfficialAuthStoreMode;$current=Read-HmsCodexOfficialAuthJson $mode;if(-not $current.PSObject.Properties.Count){throw 'OFFICIAL_CURRENT_AUTH_MISSING'}
        $before=Snapshot-HmsCodexOfficialAuthState $current;$sync=Sync-HmsCurrentOfficialAuthToManagedAccount $current
        $rows=@(Get-CodexAccountRecords|Where-Object{([string]$_.Email).Equals($Email,[StringComparison]::OrdinalIgnoreCase)});if($rows.Count -ne 1){throw 'TARGET_ACCOUNT_NOT_UNIQUE_OR_NOT_FOUND'}
        $projected=ConvertTo-HmsCodexOfficialAuthProjection $current $rows[0].Json;$targetFp=Get-HmsCodexAuthFingerprint $projected
        $null=Invoke-HmsRecoveryJournalPhase $txn 'OFFICIAL_AUTH_SWITCH' 'PREPARE' $Email $targetFp;$journalPrepared=$true
        try{
            Write-HmsCodexOfficialAuthJson $projected $mode
            $null=Invoke-HmsRecoveryJournalPhase $txn 'OFFICIAL_AUTH_SWITCH' 'COMMIT' $Email $targetFp;$journalCommitted=$true
            $readback=Read-HmsCodexOfficialAuthJson $mode;$after=Get-HmsCodexAuthFingerprint $readback;if($after -ne $targetFp){throw 'AUTH_READBACK_FINGERPRINT_MISMATCH'}
            $null=Invoke-HmsRecoveryJournalPhase $txn 'OFFICIAL_AUTH_SWITCH' 'VERIFY' $Email $after
        }catch{
            Restore-HmsCodexOfficialAuthSnapshot $mode
            if($journalPrepared){try{$null=Invoke-HmsRecoveryJournalPhase $txn 'OFFICIAL_AUTH_SWITCH' 'ROLLBACK' $Email $before}catch{}}
            throw
        }
        Clear-HmsCodexOfficialAuthSnapshot
        $restart='NOT_REQUESTED';if([bool]$script:S.CodexLaunchAfterAuthSwitch){$restart=Restart-CodexForSwitch $true}
        $null=Invoke-HmsRecoveryJournalPhase $txn 'OFFICIAL_AUTH_SWITCH' 'DONE' $Email $after
        $identity=Get-HmsCodexOfficialHttpIdentity
        return [pscustomobject]@{ok=$true;version='25.60';store_mode=$mode;keyring_backend=(Get-HmsCodexOfficialKeyringBackendKind);before_fp=$before;after_fp=$after;current_account_sync=$sync;verified=$true;official_originator=$identity.originator;official_user_agent=$identity.user_agent;identity_source=$identity.source;restart=$restart;recovery_txn_id=$txn;secrets_included=$false}
    }catch{if($mode -and -not $journalCommitted){try{Restore-HmsCodexOfficialAuthSnapshot $mode}catch{}};Clear-HmsCodexOfficialAuthSnapshot;throw}finally{if($locked){try{$mutex.ReleaseMutex()}catch{}};$mutex.Dispose()}
}
function Invoke-HmsOfficialAuthCompatAudit {
    Ensure-Dir $script:OfficialAuthCompatDir;$tool=Join-Path $PSScriptRoot 'HMS_Codex_OfficialAuthCompatibility.py';$validator=Join-Path $PSScriptRoot 'HMS_Codex_OfficialAuthCompatibilityValidator.py'
    if(-not (Test-Path $tool)){throw 'Thiếu HMS_Codex_OfficialAuthCompatibility.py'};if(-not (Test-Path $validator)){throw 'Thiếu HMS_Codex_OfficialAuthCompatibilityValidator.py'}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $validator -Arguments @('--root',$PSScriptRoot,'--output',$script:OfficialAuthCompatLatestPath);return $j.data
}
function Show-HmsOfficialAuthCompatibilityCenter {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Official Auth Compatibility · v25.59';$w.Size=New-Object Drawing.Size(940,610);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='OFFICIAL AUTH COMPATIBILITY v25.59 · P0';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='file / keyring / auto · snapshot before switch · serialized rewrite · preserve unrelated fields · stale credential cleanup · official OAuth identity.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(875,44);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $b=Btn 'AUTH AUDIT' 22 112 140 38;$b.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($b);$out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,170);$out.Size=New-Object Drawing.Size(875,330);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: atomic commit + readback + rollback. Codex Secrets keyring backend fails closed until an official Codex helper is available; HMS never writes shadow generic credentials.';$safe.Location=New-Object Drawing.Point(22,520);$safe.Size=New-Object Drawing.Size(875,46);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe);$b.Add_Click({try{$r=Invoke-HmsOfficialAuthCompatAudit;$out.Text=($r|ConvertTo-Json -Depth 6)}catch{Err $_.Exception.Message}});[void]$w.ShowDialog($form)
}

# v25.53 TARGET-MACHINE CERTIFICATION
# Single operator flow: preflight -> LIVE 1 -> bounded failover -> 6h/24h soak -> final evidence.
# The aggregator never mutates auth and never consumes quota by itself.
# ============================================================
function Invoke-HmsTargetMachineCertification {
    param([ValidateSet('preflight','evaluate')][string]$Mode='preflight')
    Ensure-Dir $script:TargetMachineCertDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_TargetMachineCertification.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw 'Thiếu HMS_Codex_TargetMachineCertification.py'}
    $accountsFile=Join-Path $env:TEMP ('hms-target-cert-accounts-'+[Guid]::NewGuid().ToString('N')+'.json')
    $lanFile=Join-Path $env:TEMP ('hms-target-cert-lan-'+[Guid]::NewGuid().ToString('N')+'.json')
    try{
        Save-JsonAtomic $accountsFile (Get-HmsNativeAccountCenterObject)
        Save-JsonAtomic $lanFile (Get-HmsNativeLanPoolObject)
        $args=@('--root',$PSScriptRoot,'--data-dir',$script:DataDir,'--instance-store',$script:CodexInstancesPath,'--quota-snapshot',$accountsFile,'--lan-snapshot',$lanFile,'--output',$script:TargetMachineCertLatestPath)
        if([string]$script:S.LanPoolSharedPath){$args+=@('--shared',[string]$script:S.LanPoolSharedPath)}
        if($Mode -eq 'evaluate' -and (Test-Path -LiteralPath $script:TargetMachineRealCodexPath -PathType Leaf)){$args+=@('--real-cert-evidence',$script:TargetMachineRealCodexPath)}
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        Remove-Item -LiteralPath $accountsFile,$lanFile -Force -ErrorAction SilentlyContinue
    }
}
function Invoke-HmsTargetMachineLiveOne {
    Ensure-Dir $script:TargetMachineCertDir
    $model=[Microsoft.VisualBasic.Interaction]::InputBox('Nhập model Codex dùng cho đúng 1 request chứng nhận. Request này có thể tiêu quota.','HMS Target Certification · LIVE 1','')
    if([string]::IsNullOrWhiteSpace($model)){return $null}
    $q=[Windows.Forms.MessageBox]::Show("LIVE 1 sẽ gửi đúng 1 request nhỏ bằng model:`r`n$model`r`n`r`nTiếp tục?",'HMS TARGET CERTIFICATION',[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
    if($q -ne [Windows.Forms.DialogResult]::Yes){return $null}
    $bridge=Join-Path $PSScriptRoot 'HMS_Codex_RealCertificationBridge.ps1'
    if(-not (Test-Path -LiteralPath $bridge -PathType Leaf)){throw 'Thiếu HMS_Codex_RealCertificationBridge.ps1'}
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $bridge -Root $PSScriptRoot -Model $model -MaxLiveRequests 1 -InstanceStore $script:CodexInstancesPath -Output $script:TargetMachineRealCodexPath | Out-Null
    if($LASTEXITCODE -ne 0){throw ('LIVE 1 certification failed. exit='+[string]$LASTEXITCODE)}
    return Invoke-HmsTargetMachineCertification 'evaluate'
}
function Format-HmsTargetMachineCertification([object]$r){
    if(-not $r){return 'Chưa có evidence.'}
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add('VERDICT: '+[string]$r.verdict)
    try{$lines.Add('STAGES: '+[string]$r.summary.stages_pass+'/'+[string]$r.summary.stages_total)}catch{}
    foreach($name in @('host','codex','quota','failover','lan','soak_6h','soak_24h')){
        try{$row=$r.stages.$name;$lines.Add(('{0,-10} {1}' -f $name.ToUpperInvariant(),$(if([bool]$row.pass){'PASS'}else{'WAIT/BLOCKED'})))}catch{}
    }
    try{if(@($r.blockers).Count){$lines.Add('BLOCKERS: '+(@($r.blockers)-join ', '))}}catch{}
    $lines.Add('')
    $lines.Add('PASS production chỉ khi đủ Windows + Codex thật + quota thật + failover restore + >=2 LAN node + soak 6h/24h thật.')
    return ($lines -join "`r`n")
}
function Show-HmsTargetMachineCertificationCenter {
    $w=New-Object Windows.Forms.Form;$w.Text='HMS Target-Machine Certification · v25.53';$w.Size=New-Object Drawing.Size(960,700);$w.StartPosition='CenterParent';$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245);$w.Font=New-Object Drawing.Font('Segoe UI',9.5)
    $title=New-Object Windows.Forms.Label;$title.Text='TARGET-MACHINE CERTIFICATION v25.53';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(20,18);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='Một luồng chứng nhận Codex-only: Windows/PS5.1 → Codex thật → quota thật → failover bounded → LAN >=2 node → soak 6h/24h.';$desc.Location=New-Object Drawing.Point(22,58);$desc.Size=New-Object Drawing.Size(900,44);$desc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($desc)
    $bPre=Btn 'PREFLIGHT' 22 112 135 38;$w.Controls.Add($bPre)
    $bLive=Btn 'LIVE 1 CODEX' 170 112 155 38;$bLive.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bLive)
    $bFail=Btn 'FAILOVER 1' 338 112 145 38;$w.Controls.Add($bFail)
    $bSoak=Btn 'SOAK CENTER' 496 112 150 38;$w.Controls.Add($bSoak)
    $bEval=Btn 'ĐÁNH GIÁ' 659 112 135 38;$w.Controls.Add($bEval)
    $bEv=Btn 'MỞ EVIDENCE' 807 112 125 38;$w.Controls.Add($bEv)
    $bSim=Btn 'SIM LAB' 22 606 120 30;$w.Controls.Add($bSim)
    $bTwin=Btn 'ROUTER TWIN' 155 606 130 30;$w.Controls.Add($bTwin)
    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(22,168);$out.Size=New-Object Drawing.Size(910,360);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $safe=New-Object Windows.Forms.Label;$safe.Text='Safety: PREFLIGHT không tiêu quota. LIVE 1 cần xác nhận. FAILOVER chỉ disable đúng 1 account rồi restore. Runner không xóa auth/credential. Synthetic evidence không thể cấp production PASS.';$safe.Location=New-Object Drawing.Point(22,542);$safe.Size=New-Object Drawing.Size(900,55);$safe.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($safe)
    function RefreshTargetCert {
        if(Test-Path -LiteralPath $script:TargetMachineCertLatestPath){try{$j=Get-Content -LiteralPath $script:TargetMachineCertLatestPath -Raw -Encoding UTF8|ConvertFrom-Json;$out.Text=Format-HmsTargetMachineCertification $j}catch{$out.Text='Evidence invalid: '+$_.Exception.Message}}else{$out.Text='Chưa có target-machine evidence. Bắt đầu bằng PREFLIGHT.'}
    }
    $bPre.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsTargetMachineCertification 'preflight';$out.Text=Format-HmsTargetMachineCertification $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bLive.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsTargetMachineLiveOne;if($r){$out.Text=Format-HmsTargetMachineCertification $r}}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bFail.Add_Click({Show-HmsLiveFailoverCenter;RefreshTargetCert})
    $bSoak.Add_Click({Show-HmsSoakCenter;RefreshTargetCert})
    $bEval.Add_Click({try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$r=Invoke-HmsTargetMachineCertification 'evaluate';$out.Text=Format-HmsTargetMachineCertification $r}catch{Err $_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $bEv.Add_Click({Ensure-Dir $script:TargetMachineCertDir;Start-Process explorer.exe $script:TargetMachineCertDir|Out-Null})
    $bSim.Add_Click({Show-HmsProductionSimulationLab})
    $bTwin.Add_Click({Show-HmsAutonomousRouterDigitalTwin})
    $w.Add_Shown({RefreshTargetCert});[void]$w.ShowDialog($form)
}

# ---------------- Mission Control UI ----------------

function New-DarkGrid {
    param([int]$X,[int]$Y,[int]$W,[int]$H,[object]$Parent)
    $g=New-Object Windows.Forms.DataGridView
    $g.Location=New-Object Drawing.Point($X,$Y);$g.Size=New-Object Drawing.Size($W,$H)
    $g.ReadOnly=$true;$g.AllowUserToAddRows=$false;$g.AllowUserToDeleteRows=$false;$g.RowHeadersVisible=$false
    $g.AutoSizeColumnsMode="Fill";$g.SelectionMode="FullRowSelect";$g.MultiSelect=$false
    $g.BackgroundColor=[Drawing.Color]::FromArgb(22,25,30);$g.GridColor=[Drawing.Color]::FromArgb(52,58,67)
    $g.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(34,39,46);$g.ColumnHeadersDefaultCellStyle.ForeColor=[Drawing.Color]::White
    $g.EnableHeadersVisualStyles=$false
    $g.DefaultCellStyle.BackColor=[Drawing.Color]::FromArgb(22,25,30);$g.DefaultCellStyle.ForeColor=[Drawing.Color]::FromArgb(230,234,239)
    $g.DefaultCellStyle.SelectionBackColor=[Drawing.Color]::FromArgb(50,70,85);$g.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    $Parent.Controls.Add($g);return $g
}
function New-StatCard {
    param([string]$Title,[int]$X,[int]$Y,[int]$W,[object]$Parent)
    $p=New-Object Windows.Forms.Panel;$p.Location=New-Object Drawing.Point($X,$Y);$p.Size=New-Object Drawing.Size($W,82)
    $p.BackColor=[Drawing.Color]::FromArgb(27,31,37);$Parent.Controls.Add($p)
    $t=New-Object Windows.Forms.Label;$t.Text=$Title;$t.Location=New-Object Drawing.Point(12,9);$t.AutoSize=$true;$t.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$p.Controls.Add($t)
    $v=New-Object Windows.Forms.Label;$v.Text="—";$v.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$v.Location=New-Object Drawing.Point(10,33);$v.AutoSize=$true;$p.Controls.Add($v)
    return $v
}
function Show-CodexMissionControl {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Mission Control v25.24"
    $w.Size=New-Object Drawing.Size(1360,860);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5);$w.MinimumSize=New-Object Drawing.Size(1180,760)

    $head=New-Object Windows.Forms.Label;$head.Text="HMS CODEX MISSION CONTROL";$head.Font=New-Object Drawing.Font("Segoe UI Semibold",19)
    $head.AutoSize=$true;$head.Location=New-Object Drawing.Point(18,14);$w.Controls.Add($head)
    $head2=New-Object Windows.Forms.Label;$head2.Text="API Superset · Proxy Fleet · Protocol Streaming · Smart Gateway · Runtime Gates · Reliability"
    $head2.AutoSize=$true;$head2.Location=New-Object Drawing.Point(20,49);$head2.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($head2)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,78);$tabs.Size=New-Object Drawing.Size(1305,720)
    $tabs.Appearance="Normal";$w.Controls.Add($tabs)
    foreach($name in @("Tổng quan","Runtime Certification","API Superset","Proxy Fleet","Proxy Affinity","Smart Gateway","Windows Runtime Gate","Source Integrity","Autonomous Kernel","Performance","Reliability Soak","Pool Recovery","Router Intelligence","Account & Session Ops","Validation","Release","Production","Unified","High Availability","Autopilot","Operations","Tài khoản","Fleet","Orchestrator","Sessions","Thread Sync","Telemetry","Router & Trace","Wake-up","Backup","Runtime Plan")){
        $tp=New-Object Windows.Forms.TabPage;$tp.Text=$name;$tp.BackColor=[Drawing.Color]::FromArgb(18,21,25);$tp.ForeColor=$w.ForeColor;$tabs.TabPages.Add($tp)
    }
    $pOverview=$tabs.TabPages[0];$pRuntimeCert=$tabs.TabPages[1];$pApiSuperset=$tabs.TabPages[2];$pProxyFleet=$tabs.TabPages[3];$pProxyAffinity=$tabs.TabPages[4];$pSmartGateway=$tabs.TabPages[5];$pWindowsGate=$tabs.TabPages[6];$pSourceIntegrity=$tabs.TabPages[7];$pKernel=$tabs.TabPages[8];$pPerformance=$tabs.TabPages[9];$pSoak=$tabs.TabPages[10];$pPoolRecovery=$tabs.TabPages[11];$pRouterIntel=$tabs.TabPages[12];$pAccountSessionOps=$tabs.TabPages[13];$pValidation=$tabs.TabPages[14];$pRelease=$tabs.TabPages[15];$pProduction=$tabs.TabPages[16];$pUnified=$tabs.TabPages[17];$pHa=$tabs.TabPages[18];$pAutopilot=$tabs.TabPages[19];$pOperations=$tabs.TabPages[20];$pAccounts=$tabs.TabPages[21];$pFleet=$tabs.TabPages[22];$pInstances=$tabs.TabPages[23];$pSessions=$tabs.TabPages[24];$pThreadSync=$tabs.TabPages[25];$pTelemetry=$tabs.TabPages[26];$pRouter=$tabs.TabPages[27];$pWake=$tabs.TabPages[28];$pBackup=$tabs.TabPages[29];$pPlan=$tabs.TabPages[30]

    # Overview cards
    $cPool=New-StatCard "CODEX ACCOUNTS" 18 20 220 $pOverview
    $cReady=New-StatCard "READY / COOLDOWN" 250 20 220 $pOverview
    $cRouter=New-StatCard "ROUTER" 482 20 220 $pOverview
    $cInst=New-StatCard "INSTANCES RUNNING" 714 20 220 $pOverview
    $cWatch=New-StatCard "WATCHDOG" 946 20 220 $pOverview

    $bUnifiedUx=Btn "MỞ UNIFIED UX" 1050 76 210 34;$pOverview.Controls.Add($bUnifiedUx)
    $overviewGrid=New-DarkGrid 18 120 1245 480 $pOverview
    $ovNote=New-Object Windows.Forms.Label;$ovNote.Location=New-Object Drawing.Point(18,615);$ovNote.Size=New-Object Drawing.Size(1245,50)
    $ovNote.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pOverview.Controls.Add($ovNote)

    # Runtime Certification
    $rcTitle=New-Object Windows.Forms.Label;$rcTitle.Text="WINDOWS RUNTIME CERTIFICATION";$rcTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$rcTitle.Location=New-Object Drawing.Point(20,20);$rcTitle.AutoSize=$true;$pRuntimeCert.Controls.Add($rcTitle)
    $rcDesc=New-Object Windows.Forms.Label;$rcDesc.Location=New-Object Drawing.Point(20,60);$rcDesc.Size=New-Object Drawing.Size(1160,135);$rcDesc.Text="ALL_READY → PORT_PROFILE → UI_SMOKE → ROUTER_SMOKE → SAFE_RUNTIME. First-run wizard tạo snapshot/evidence, tránh chiếm port Cockpit và chỉ cho phép router mutation sau operator confirmation.";$rcDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pRuntimeCert.Controls.Add($rcDesc)
    $bRuntimeCert=Btn "MỞ FIRST-RUN WIZARD" 20 205 230 42;$pRuntimeCert.Controls.Add($bRuntimeCert)
    $bRuntimeEvidence=Btn "MỞ RUNTIME EVIDENCE" 265 205 220 42;$pRuntimeCert.Controls.Add($bRuntimeEvidence)
    $bTargetCert=Btn "MỞ TARGET CERT v25.53" 500 205 230 42;$bTargetCert.BackColor=[Drawing.Color]::FromArgb(39,96,73);$pRuntimeCert.Controls.Add($bTargetCert)
    $rcState=New-Object Windows.Forms.TextBox;$rcState.Location=New-Object Drawing.Point(20,270);$rcState.Size=New-Object Drawing.Size(1180,260);$rcState.Multiline=$true;$rcState.ReadOnly=$true;$rcState.BackColor=[Drawing.Color]::FromArgb(20,23,27);$rcState.ForeColor=$w.ForeColor;$pRuntimeCert.Controls.Add($rcState)
    $checkpointPath=Join-Path $script:RuntimeCertDir "checkpoint-v25_23_1.json"
    if(Test-Path $checkpointPath){$rcState.Text=Get-Content $checkpointPath -Raw -Encoding UTF8}else{$rcState.Text="Chưa có checkpoint. Chạy First-Run Wizard."}

    # API Superset
    $apiTitle=New-Object Windows.Forms.Label;$apiTitle.Text="CODEX API SUPERSET & PARITY";$apiTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$apiTitle.Location=New-Object Drawing.Point(20,20);$apiTitle.AutoSize=$true;$pApiSuperset.Controls.Add($apiTitle)
    $apiDesc=New-Object Windows.Forms.Label;$apiDesc.Location=New-Object Drawing.Point(20,60);$apiDesc.Size=New-Object Drawing.Size(1160,110);$apiDesc.Text="Per-key target pools · routing modes · quota reserve · model prefix · CORS · usage/token/cost analytics · Cockpit parity auditor.";$apiDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pApiSuperset.Controls.Add($apiDesc)
    $bApiSuperset=Btn "MỞ API SUPERSET" 20 180 230 42;$pApiSuperset.Controls.Add($bApiSuperset)

    # Proxy Fleet
    $pfTitle=New-Object Windows.Forms.Label;$pfTitle.Text="PROXY FLEET & EGRESS INTEGRITY";$pfTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$pfTitle.Location=New-Object Drawing.Point(20,20);$pfTitle.AutoSize=$true;$pProxyFleet.Controls.Add($pfTitle)
    $pfDesc=New-Object Windows.Forms.Label;$pfDesc.Location=New-Object Drawing.Point(20,60);$pfDesc.Size=New-Object Drawing.Size(1160,110);$pfDesc.Text="Public-IP baseline · drift detection · quarantine/drain · provider -ne utral CSV/JSON/TXT import · recovery budget · STRICT egress gate.";$pfDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pProxyFleet.Controls.Add($pfDesc)
    $bProxyFleet=Btn "MỞ PROXY FLEET" 20 180 230 42;$pProxyFleet.Controls.Add($bProxyFleet)

    # Proxy Affinity
    $paTitle=New-Object Windows.Forms.Label;$paTitle.Text="PROXY AFFINITY & EGRESS CONTROL";$paTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$paTitle.Location=New-Object Drawing.Point(20,20);$paTitle.AutoSize=$true;$pProxyAffinity.Controls.Add($paTitle)
    $paDesc=New-Object Windows.Forms.Label;$paDesc.Location=New-Object Drawing.Point(20,60);$paDesc.Size=New-Object Drawing.Size(1160,110);$paDesc.Text="1 proxy → 4–5 account · sticky binding · STRICT fail-closed · HTTP/HTTPS/SOCKS5 health · isolated CLIProxy sidecars · DPAPI proxy secrets · no random rotation.";$paDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pProxyAffinity.Controls.Add($paDesc)
    $bProxyAffinity=Btn "MỞ PROXY AFFINITY" 20 180 230 42;$pProxyAffinity.Controls.Add($bProxyAffinity)

    # Smart Gateway
    $sgTitle=New-Object Windows.Forms.Label;$sgTitle.Text="CODEX SMART GATEWAY";$sgTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$sgTitle.Location=New-Object Drawing.Point(20,20);$sgTitle.AutoSize=$true;$pSmartGateway.Controls.Add($sgTitle)
    $sgDesc=New-Object Windows.Forms.Label;$sgDesc.Location=New-Object Drawing.Point(20,60);$sgDesc.Size=New-Object Drawing.Size(1160,110);$sgDesc.Text="Named client keys · per-key model rules · priority/weight · session affinity · reset-aware optional routing · request -le vel selected-target trace.";$sgDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pSmartGateway.Controls.Add($sgDesc)
    $bSmartGateway=Btn "MỞ SMART GATEWAY" 20 180 230 42;$pSmartGateway.Controls.Add($bSmartGateway)

    # Windows Runtime Gate
    $wgTitle=New-Object Windows.Forms.Label;$wgTitle.Text="WINDOWS RUNTIME GATE ORCHESTRATOR";$wgTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$wgTitle.Location=New-Object Drawing.Point(20,20);$wgTitle.AutoSize=$true;$pWindowsGate.Controls.Add($wgTitle)
    $wgDesc=New-Object Windows.Forms.Label;$wgDesc.Location=New-Object Drawing.Point(20,60);$wgDesc.Size=New-Object Drawing.Size(1160,110);$wgDesc.Text="PowerShell 5.1 parse · source/manifest · Python helpers · launcher/setup · local web smoke · optional UI/router SAFE_RUNTIME with operator/ownership gates · evidence bundle.";$wgDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pWindowsGate.Controls.Add($wgDesc)
    $bWindowsGate=Btn "MỞ WINDOWS RUNTIME GATE" 20 180 270 42;$pWindowsGate.Controls.Add($bWindowsGate)

    # Source Integrity
    $siTitle=New-Object Windows.Forms.Label;$siTitle.Text="POWERSHELL SOURCE INTEGRITY";$siTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$siTitle.Location=New-Object Drawing.Point(20,20);$siTitle.AutoSize=$true;$pSourceIntegrity.Controls.Add($siTitle)
    $siDesc=New-Object Windows.Forms.Label;$siDesc.Location=New-Object Drawing.Point(20,60);$siDesc.Size=New-Object Drawing.Size(1160,110);$siDesc.Text="v18 static gate: zero operator/cmdlet glue · zero missing runtime paths/settings · version/manifest authority · launcher preflight before main PS1.";$siDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pSourceIntegrity.Controls.Add($siDesc)
    $bSourceIntegrity=Btn "MỞ SOURCE INTEGRITY" 20 180 230 42;$pSourceIntegrity.Controls.Add($bSourceIntegrity)

    # Autonomous Kernel
    $kernelTitle=New-Object Windows.Forms.Label;$kernelTitle.Text="POLICY & AUTONOMOUS OPERATIONS KERNEL";$kernelTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$kernelTitle.Location=New-Object Drawing.Point(20,20);$kernelTitle.AutoSize=$true;$pKernel.Controls.Add($kernelTitle)
    $kernelDesc=New-Object Windows.Forms.Label;$kernelDesc.Location=New-Object Drawing.Point(20,60);$kernelDesc.Size=New-Object Drawing.Size(1160,110);$kernelDesc.Text="OBSERVE → RECOMMEND → SAFE_AUTO · action allowlist · hysteresis · cooldown · action budget · ownership gates · unified audit trail.";$kernelDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pKernel.Controls.Add($kernelDesc)
    $bKernel=Btn "MỞ AUTONOMOUS KERNEL" 20 180 240 42;$pKernel.Controls.Add($bKernel)

    # Performance
    $perfTitle=New-Object Windows.Forms.Label;$perfTitle.Text="OBSERVABILITY & PERFORMANCE ANALYTICS";$perfTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$perfTitle.Location=New-Object Drawing.Point(20,20);$perfTitle.AutoSize=$true;$pPerformance.Controls.Add($perfTitle)
    $perfDesc=New-Object Windows.Forms.Label;$perfDesc.Location=New-Object Drawing.Point(20,60);$perfDesc.Size=New-Object Drawing.Size(1160,110);$perfDesc.Text="P50/P95/P99 latency · RAM/SLA/state trends · quota history · failover/cooldown timeline · robust anomaly detection · self-contained HTML report.";$perfDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pPerformance.Controls.Add($perfDesc)
    $bPerformance=Btn "MỞ PERFORMANCE CENTER" 20 180 240 42;$pPerformance.Controls.Add($bPerformance)

    # Reliability Soak
    $soakTitle=New-Object Windows.Forms.Label;$soakTitle.Text="LONG-RUNNING RELIABILITY & SOAK";$soakTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$soakTitle.Location=New-Object Drawing.Point(20,20);$soakTitle.AutoSize=$true;$pSoak.Controls.Add($soakTitle)
    $soakDesc=New-Object Windows.Forms.Label;$soakDesc.Location=New-Object Drawing.Point(20,60);$soakDesc.Size=New-Object Drawing.Size(1160,110);$soakDesc.Text="1h / 6h / 24h observation · resume after restart · router uptime · pool readiness · RAM/state growth · recovery-loop detection · certificate only when complete.";$soakDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pSoak.Controls.Add($soakDesc)
    $bSoak=Btn "MỞ SOAK CENTER" 20 180 210 42;$pSoak.Controls.Add($bSoak)

    # Pool Recovery
    $prTitle=New-Object Windows.Forms.Label;$prTitle.Text="ACCOUNT POOL AUTOMATION & RECOVERY";$prTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$prTitle.Location=New-Object Drawing.Point(20,20);$prTitle.AutoSize=$true;$pPoolRecovery.Controls.Add($prTitle)
    $prDesc=New-Object Windows.Forms.Label;$prDesc.Location=New-Object Drawing.Point(20,60);$prDesc.Size=New-Object Drawing.Size(1160,110);$prDesc.Text="Shared pool inventory · new/removed accounts · isolated credential drift · cooldown lifecycle · safe stopped-instance reconciliation · conflict review.";$prDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pPoolRecovery.Controls.Add($prDesc)
    $bPoolRecovery=Btn "MỞ POOL RECOVERY" 20 180 220 42;$pPoolRecovery.Controls.Add($bPoolRecovery)

    # Router Intelligence
    $riTitle=New-Object Windows.Forms.Label;$riTitle.Text="MULTI-ACCOUNT ROUTER INTELLIGENCE";$riTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$riTitle.Location=New-Object Drawing.Point(20,20);$riTitle.AutoSize=$true;$pRouterIntel.Controls.Add($riTitle)
    $riDesc=New-Object Windows.Forms.Label;$riDesc.Location=New-Object Drawing.Point(20,60);$riDesc.Size=New-Object Drawing.Size(1160,110);$riDesc.Text="Live Pool Map · eligibility reason · recent route/failover/cooldown evidence · routing strategy/session-affinity explanation · no fake next-account prediction.";$riDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pRouterIntel.Controls.Add($riDesc)
    $bRouterIntel=Btn "MỞ ROUTER INTELLIGENCE" 20 180 250 42;$pRouterIntel.Controls.Add($bRouterIntel)

    # Account & Session Ops
    $asoTitle=New-Object Windows.Forms.Label;$asoTitle.Text="ACCOUNT & SESSION OPERATIONS";$asoTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$asoTitle.Location=New-Object Drawing.Point(20,20);$asoTitle.AutoSize=$true;$pAccountSessionOps.Controls.Add($asoTitle)
    $asoDesc=New-Object Windows.Forms.Label;$asoDesc.Location=New-Object Drawing.Point(20,60);$asoDesc.Size=New-Object Drawing.Size(1160,110);$asoDesc.Text="Maintenance/Quarantine metadata overlay · bulk favorite · pool metadata export/import · session explorer · account visibility CONFIRMED/PROBABLE/UNATTRIBUTED.";$asoDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pAccountSessionOps.Controls.Add($asoDesc)
    $bAccountSessionOps=Btn "MỞ ACCOUNT & SESSION OPS" 20 180 270 42;$pAccountSessionOps.Controls.Add($bAccountSessionOps)

    # Validation
    $valTitle=New-Object Windows.Forms.Label;$valTitle.Text="WINDOWS RUNTIME VALIDATION";$valTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$valTitle.Location=New-Object Drawing.Point(20,20);$valTitle.AutoSize=$true;$pValidation.Controls.Add($valTitle)
    $valDesc=New-Object Windows.Forms.Label;$valDesc.Location=New-Object Drawing.Point(20,60);$valDesc.Size=New-Object Drawing.Size(1160,110);$valDesc.Text="STATIC → SAFE_RUNTIME → FULL_RUNTIME. PASS/FAIL/BLOCKED + redacted evidence. Mutation luôn operator-gated.";$valDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pValidation.Controls.Add($valDesc)
    $bValidationCenter=Btn "MỞ VALIDATION CENTER" 20 180 240 42;$pValidation.Controls.Add($bValidationCenter)

    # Release
    $relTitle=New-Object Windows.Forms.Label;$relTitle.Text="RELEASE ENGINEERING";$relTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$relTitle.Location=New-Object Drawing.Point(20,20);$relTitle.AutoSize=$true;$pRelease.Controls.Add($relTitle)
    $relDesc=New-Object Windows.Forms.Label;$relDesc.Location=New-Object Drawing.Point(20,60);$relDesc.Size=New-Object Drawing.Size(1160,105);$relDesc.Text="Preflight · versioned per-user install · stable launcher · non-destructive upgrade · rollback pointer · release certificate · portable mode.";$relDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pRelease.Controls.Add($relDesc)
    $bReleaseCenter=Btn "MỞ RELEASE CENTER" 20 175 220 42;$pRelease.Controls.Add($bReleaseCenter)

    # Production
    $prodTitle=New-Object Windows.Forms.Label;$prodTitle.Text="PRODUCTION HARDENING";$prodTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$prodTitle.Location=New-Object Drawing.Point(20,20);$prodTitle.AutoSize=$true;$pProduction.Controls.Add($prodTitle)
    $prodDesc=New-Object Windows.Forms.Label;$prodDesc.Location=New-Object Drawing.Point(20,60);$prodDesc.Size=New-Object Drawing.Size(1160,105);$prodDesc.Text="Startup self-test · crash marker · Safe Startup · atomic settings · release hash verification · SQLite quick_check · health certificate · manual log archive.";$prodDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pProduction.Controls.Add($prodDesc)
    $bProduction=Btn "MỞ PRODUCTION CENTER" 20 175 230 42;$pProduction.Controls.Add($bProduction)

    # Unified
    $uTitle=New-Object Windows.Forms.Label;$uTitle.Text="UNIFIED COMMAND CENTER";$uTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$uTitle.Location=New-Object Drawing.Point(20,20);$uTitle.AutoSize=$true;$pUnified.Controls.Add($uTitle)
    $uDesc=New-Object Windows.Forms.Label;$uDesc.Location=New-Object Drawing.Point(20,60);$uDesc.Size=New-Object Drawing.Size(1160,95);$uDesc.Text="Một màn hình gom Router / Account / Fleet / HA / Incidents / Topology. Unified UX bind 127.0.0.1, high-density dark dashboard và chỉ đọc snapshot no-token.";$uDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pUnified.Controls.Add($uDesc)
    $bUnified=Btn "MỞ NATIVE COMMAND CENTER" 20 170 260 42;$pUnified.Controls.Add($bUnified)

    # High Availability
    $haTitle=New-Object Windows.Forms.Label
    $haTitle.Text="CODEX HIGH AVAILABILITY"
    $haTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17)
    $haTitle.Location=New-Object Drawing.Point(20,20);$haTitle.AutoSize=$true;$pHa.Controls.Add($haTitle)
    $haDesc=New-Object Windows.Forms.Label
    $haDesc.Location=New-Object Drawing.Point(20,60);$haDesc.Size=New-Object Drawing.Size(1160,100)
    $haDesc.Text="Persistent metrics + Circuit Breaker + HALF_OPEN + anti-flapping + request correlation. OPEN account được Fleet planner tránh; shared router vẫn dùng native CLIProxyAPI failover."
    $haDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pHa.Controls.Add($haDesc)
    $bHa=Btn "MỞ HA CENTER" 20 170 180 42;$pHa.Controls.Add($bHa)

    # Autopilot
    $autoTitle=New-Object Windows.Forms.Label;$autoTitle.Text="CODEX AUTOPILOT";$autoTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$autoTitle.Location=New-Object Drawing.Point(20,20);$autoTitle.AutoSize=$true;$pAutopilot.Controls.Add($autoTitle)
    $autoDesc=New-Object Windows.Forms.Label;$autoDesc.Location=New-Object Drawing.Point(20,60);$autoDesc.Size=New-Object Drawing.Size(1160,100);$autoDesc.Text="Predictive quota + per-account error metrics + reserve activation. Mặc định RECOMMEND. SAFE-AUTO chỉ rebind instance đã STOP; không kill process lạ, không xóa auth.";$autoDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pAutopilot.Controls.Add($autoDesc)
    $bAuto=Btn "MỞ CODEX AUTOPILOT" 20 170 220 42;$pAutopilot.Controls.Add($bAuto)

    # Operations
    $opsTitle=New-Object Windows.Forms.Label;$opsTitle.Text="LIVE OPERATIONS";$opsTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$opsTitle.Location=New-Object Drawing.Point(20,20);$opsTitle.AutoSize=$true;$pOperations.Controls.Add($opsTitle)
    $opsDesc=New-Object Windows.Forms.Label;$opsDesc.Location=New-Object Drawing.Point(20,60);$opsDesc.Size=New-Object Drawing.Size(1160,90);$opsDesc.Text="Request→account attribution có 3 mức CONFIRMED / PROBABLE / UNATTRIBUTED. HMS không báo chắc chắn nếu log không có evidence. Operations Center còn gom incidents, quota delta, recovery policy và diagnostic bundle redacted.";$opsDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pOperations.Controls.Add($opsDesc)
    $bOps=Btn "MỞ OPERATIONS CENTER" 20 165 220 42;$pOperations.Controls.Add($bOps)

    # Accounts
    $accGrid=New-DarkGrid 18 60 1245 485 $pAccounts
    $bQa=Btn "REFRESH QUOTA ALL" 18 15 180 34;$pAccounts.Controls.Add($bQa)
    $bQs=Btn "REFRESH SELECTED" 210 15 170 34;$pAccounts.Controls.Add($bQs)
    $bMeta=Btn "TAG / GHI CHÚ" 392 15 150 34;$pAccounts.Controls.Add($bMeta)
    $bAddAcc=Btn "＋ THÊM ACC" 554 15 140 34;$pAccounts.Controls.Add($bAddAcc)
    $bQuotaCenter=Btn "QUOTA CENTER" 706 15 150 34;$pAccounts.Controls.Add($bQuotaCenter)
    $bBatch=Btn "BATCH CENTER" 868 15 150 34;$pAccounts.Controls.Add($bBatch)
    $bExportRed=Btn "EXPORT REDACTED" 1030 15 170 34;$pAccounts.Controls.Add($bExportRed)
    $accStatus=New-Object Windows.Forms.Label;$accStatus.Location=New-Object Drawing.Point(18,560);$accStatus.Size=New-Object Drawing.Size(1240,80);$accStatus.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pAccounts.Controls.Add($accStatus)

    # Instances
    $instGrid=New-DarkGrid 18 65 1245 470 $pInstances
    $bNewInst=Btn "＋ TẠO INSTANCE" 18 15 160 34;$pInstances.Controls.Add($bNewInst)
    $bOrchestrator=Btn "MỞ ORCHESTRATOR" 865 15 180 34;$pInstances.Controls.Add($bOrchestrator)
    $bStartInst=Btn "▶ START" 190 15 120 34;$pInstances.Controls.Add($bStartInst)
    $bStopInst=Btn "■ STOP" 322 15 120 34;$pInstances.Controls.Add($bStopInst)
    $bOpenInst=Btn "MỞ THƯ MỤC" 454 15 150 34;$pInstances.Controls.Add($bOpenInst)
    $bRestartInst=Btn "↻ RESTART" 616 15 125 34;$pInstances.Controls.Add($bRestartInst)
    $bFocusInst=Btn "FOCUS" 753 15 100 34;$pInstances.Controls.Add($bFocusInst)
    $instNote=New-Object Windows.Forms.Label;$instNote.Location=New-Object Drawing.Point(18,550);$instNote.Size=New-Object Drawing.Size(1240,85)
    $instNote.Text="Mỗi instance HMS có CODEX_HOME + app-data + CLIProxyAPI child riêng và auth-dir chỉ chứa ACC đã bind. Vì vậy project/account isolation là deterministic, không phụ thuộc round-robin của router chính. STOP chỉ dừng process, không xóa profile."
    $instNote.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pInstances.Controls.Add($instNote)

    # Fleet
    $fleetTitle=New-Object Windows.Forms.Label;$fleetTitle.Text="CODEX FLEET";$fleetTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$fleetTitle.Location=New-Object Drawing.Point(20,20);$fleetTitle.AutoSize=$true;$pFleet.Controls.Add($fleetTitle)
    $fleetDesc=New-Object Windows.Forms.Label;$fleetDesc.Location=New-Object Drawing.Point(20,58);$fleetDesc.Size=New-Object Drawing.Size(1160,80);$fleetDesc.Text="Policy Engine lập kế hoạch account→instance dựa trên health/quota/favorite/reserve. SIMULATE trước, APPLY chỉ khi tất cả Codex STOP. Không xóa auth: auth cũ được archive.";$fleetDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pFleet.Controls.Add($fleetDesc)
    $bFleet=Btn "MỞ FLEET & POLICY ENGINE" 20 150 250 42;$pFleet.Controls.Add($bFleet)

    # Sessions
    $sessTitle=New-Object Windows.Forms.Label;$sessTitle.Text="CODEX SESSION VISIBILITY";$sessTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",16);$sessTitle.Location=New-Object Drawing.Point(18,20);$sessTitle.AutoSize=$true;$pSessions.Controls.Add($sessTitle)
    $sessDesc=New-Object Windows.Forms.Label;$sessDesc.Location=New-Object Drawing.Point(20,58);$sessDesc.Size=New-Object Drawing.Size(1160,70);$sessDesc.Text="Cockpit có Session Visibility Repair Quick/Deep. HMS v1.5 đưa lane này vào nhưng mặc định AUDIT READ-ONLY; repair phải xác nhận và luôn backup."; $sessDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pSessions.Controls.Add($sessDesc)
    $bSessionCenter=Btn "MỞ SESSION CENTER" 20 140 200 42;$pSessions.Controls.Add($bSessionCenter)
    $sessHelp=New-Object Windows.Forms.TextBox;$sessHelp.Location=New-Object Drawing.Point(20,205);$sessHelp.Size=New-Object Drawing.Size(1160,330);$sessHelp.Multiline=$true;$sessHelp.ReadOnly=$true;$sessHelp.BackColor=[Drawing.Color]::FromArgb(20,23,27);$sessHelp.ForeColor=$w.ForeColor;$sessHelp.Text="Audit kiểm tra:`r`n- config.toml model_provider`r`n- sessions / archived_sessions JSONL`r`n- session_index.jsonl`r`n- state_5.sqlite / codex-dev.db nếu Python sqlite3 đọc được`r`n- provider mismatch / missing index / stale index`r`n`r`nRepair:`r`n- backup trước`r`n- rewrite provider ở metadata first-line`r`n- update threads.model_provider trong SQLite`r`n- KHÔNG xóa session.";$pSessions.Controls.Add($sessHelp)

    # Thread Sync
    $bThreadCenter=Btn "MỞ THREAD SYNC CENTER" 20 30 230 42;$pThreadSync.Controls.Add($bThreadCenter)
    $ts=New-Object Windows.Forms.Label;$ts.Text="Chỉ sync khi tất cả Codex STOP. COPY missing sessions + merge index; không delete/overwrite.";$ts.Location=New-Object Drawing.Point(20,90);$ts.Size=New-Object Drawing.Size(1100,60);$ts.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pThreadSync.Controls.Add($ts)
    # Telemetry
    $bTelCenter=Btn "MỞ TELEMETRY CENTER" 20 30 220 42;$pTelemetry.Controls.Add($bTelCenter)
    # Backup
    $bBackupCenter=Btn "MỞ BACKUP CENTER" 20 30 210 42;$pBackup.Controls.Add($bBackupCenter)

    # Router Trace
    $routeText=New-Object Windows.Forms.TextBox;$routeText.Location=New-Object Drawing.Point(18,58);$routeText.Size=New-Object Drawing.Size(1245,515)
    $routeText.Multiline=$true;$routeText.ReadOnly=$true;$routeText.ScrollBars="Both";$routeText.WordWrap=$false
    $routeText.BackColor=[Drawing.Color]::FromArgb(20,23,27);$routeText.ForeColor=[Drawing.Color]::FromArgb(213,219,226);$pRouter.Controls.Add($routeText)
    $bRouteRefresh=Btn "REFRESH TRACE" 18 15 150 34;$pRouter.Controls.Add($bRouteRefresh)
    $bRouterDiag=Btn "DIAGNOSTICS" 180 15 150 34;$pRouter.Controls.Add($bRouterDiag)
    $bRouterRestart=Btn "RESTART ROUTER" 342 15 160 34;$pRouter.Controls.Add($bRouterRestart)
    $bOpenLogs=Btn "MỞ LOG FOLDER" 514 15 160 34;$pRouter.Controls.Add($bOpenLogs)

    # Wake-up
    $wakeTitle=New-Object Windows.Forms.Label;$wakeTitle.Text="WAKE-UP / KEEP-WARM — OPT-IN";$wakeTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",16)
    $wakeTitle.Location=New-Object Drawing.Point(20,20);$wakeTitle.AutoSize=$true;$pWake.Controls.Add($wakeTitle)
    $wakeDesc=New-Object Windows.Forms.Label;$wakeDesc.Location=New-Object Drawing.Point(22,60);$wakeDesc.Size=New-Object Drawing.Size(1150,75)
    $wakeDesc.Text="Tương đương lane Wake-up của Cockpit nhưng HMS mặc định TẮT vì request này có thể tiêu thụ quota. Bấm RUN NOW chỉ khi bạn chủ động muốn gửi một Responses request rất nhỏ qua pool."
    $wakeDesc.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$pWake.Controls.Add($wakeDesc)
    $bWake=Btn "RUN WAKE-UP NOW" 22 145 190 42;$pWake.Controls.Add($bWake)
    $bWakeScheduler=Btn "MỞ SCHEDULER" 230 145 190 42;$pWake.Controls.Add($bWakeScheduler)
    $wakeOut=New-Object Windows.Forms.TextBox;$wakeOut.Location=New-Object Drawing.Point(22,205);$wakeOut.Size=New-Object Drawing.Size(1150,300)
    $wakeOut.Multiline=$true;$wakeOut.ReadOnly=$true;$wakeOut.BackColor=[Drawing.Color]::FromArgb(20,23,27);$wakeOut.ForeColor=$w.ForeColor;$pWake.Controls.Add($wakeOut)

    # Plan tab
    $plan=New-Object Windows.Forms.TextBox;$plan.Location=New-Object Drawing.Point(18,18);$plan.Size=New-Object Drawing.Size(1245,610)
    $plan.Multiline=$true;$plan.ReadOnly=$true;$plan.ScrollBars="Vertical";$plan.BackColor=[Drawing.Color]::FromArgb(20,23,27);$plan.ForeColor=[Drawing.Color]::FromArgb(218,224,231)
    $plan.Text=@"
HMS CODEX SUPERSET GATE

COCKPIT BASELINE PHẢI ĐẠT:
✓ Multi-account management
✓ Hourly/5h + Weekly quota + reset
✓ Plan recognition
✓ Local API service
✓ Multi-instance + isolated profile
✓ Account binding + project binding
✓ Wake-up lane
✓ Dashboard / quick actions / progress
✓ Background/tray-style operation

HMS PHẢI HƠN:
✓ Session-affinity routing profiles
✓ Automatic credential failover
✓ Router watchdog/self-heal
✓ Per-account Health Score
✓ Route/failover log intelligence
✓ Dedicated single-account router per managed instance
✓ Cockpit-safe port coexistence
✓ config.toml/.env snapshot restore
✓ Codex API verification & diagnostics
✓ Antigravity retained as optional secondary subsystem

MEGA v1.5 ĐÃ BỔ SUNG:`r`n✓ Persistent wake-up scheduler: startup/daily/weekly/interval/quota_reset`r`n✓ Session visibility audit + backed-up repair lane`r`n✓ Account batch/filter + redacted export`r`n✓ Instance restart/focus lifecycle`r`n`r`nNEXT HARD GATES:
- Verify direct quota refresh against every real account type on target PC.
- Verify Codex Desktop classic isolated launch if installed; CLI isolation is primary guaranteed lane.
- Compare real screenshots/flows side-by-side with current Cockpit.
- No "superset PASS" until all parity gates reproduce on the user's machine.
"@
    $pPlan.Controls.Add($plan)

    function Get-MissionAccountRows {
        $cache=Get-CodexQuotaCache
        return @(Get-CodexAccountRecords|ForEach-Object{
            $h=Get-CodexAccountHealth $_
            $q=Get-CodexQuotaForEmail $_.Email
            $meta=Get-CodexAccountMeta $_.Email
            [PSCustomObject]@{
                Favorite=if($meta.favorite){"★"}else{""}
                Account=$_.Email
                Plan=if($q -and $q.plan){([string]$q.plan).ToUpperInvariant()}else{$_.Plan}
                Status=$_.Status
                Health=$h.Score
                Hourly=if($q -and $null -ne $q.hourlyRemaining){[string]$q.hourlyRemaining+"%"}else{"—"}
                HourlyReset=if($q){Format-ResetCountdown $q.hourlyReset}else{"—"}
                Weekly=if($q -and $null -ne $q.weeklyRemaining){[string]$q.weeklyRemaining+"%"}else{"—"}
                WeeklyReset=if($q){Format-ResetCountdown $q.weeklyReset}else{"—"}
                Tag=[string]$meta.tag
                Note=[string]$meta.note
                Runtime=$_.Runtime
            }
        })
    }
    function Refresh-Mission {
        $pool=Get-CodexPoolSummary
        $cPool.Text=[string]$pool.Total
        $cReady.Text="$($pool.Ready) / $($pool.Cooldown)"
        $procId=ListenerPid ([int]$script:S.ProxyPort);$cRouter.Text=if($procId -gt 0 -and (IsOurProxy $procId)){"ONLINE"}elseif($procId -gt 0){"FOREIGN"}else{"OFFLINE"}
        $ir=@(Get-CodexInstanceRows);$cInst.Text=[string](@($ir|Where-Object Client -eq "RUNNING").Count)
        $cWatch.Text=if([bool]$script:S.CodexWatchdogEnabled){"ON"}else{"OFF"}

        $rows=Get-MissionAccountRows
        $overviewGrid.DataSource=$null;$overviewGrid.DataSource=$rows
        $accGrid.DataSource=$null;$accGrid.DataSource=$rows
        $instGrid.DataSource=$null;$instGrid.DataSource=$ir
        $ovNote.Text=(Get-CodexRoutingDescription)+"`r`nHourly/Weekly = direct ChatGPT usage cache khi refresh thành công; dấu — nghĩa là HMS không có dữ liệu và không tự đoán."

        $events=@(Get-CodexRouteEventsFromLogs)
        $routeText.Text=(Get-CodexDiagnosticsText)+"`r`n`r`n===== RECENT ROUTE / FAILOVER SIGNALS =====`r`n"+
            (($events|ForEach-Object {"[$($_.Type)] $($_.Account) $($_.Message)"}) -join "`r`n")
    }

    $bQa.Add_Click({
        try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$m=Refresh-CodexQuotaAll;$accStatus.Text=$m;Refresh-Mission}
        catch{$accStatus.Text=$_.Exception.Message}
        finally{$w.Cursor=[Windows.Forms.Cursors]::Default}
    })
    $bQs.Add_Click({
        try{
            if($accGrid.SelectedRows.Count -lt 1){throw "Chọn một ACC."}
            $email=[string]$accGrid.SelectedRows[0].Cells["Account"].Value
            $q=Refresh-CodexQuotaOne $email
            $accStatus.Text="PASS $email — Hourly $($q.hourlyRemaining)% / Weekly $($q.weeklyRemaining)%"
            Refresh-Mission
        }catch{$accStatus.Text=$_.Exception.Message}
    })
    $bMeta.Add_Click({
        try{
            if($accGrid.SelectedRows.Count -lt 1){throw "Chọn một ACC."}
            $email=[string]$accGrid.SelectedRows[0].Cells["Account"].Value
            $m=Get-CodexAccountMeta $email
            $tag=[Windows.Forms.Interaction]::InputBox("Tag cho $email","HMS Codex Tag",[string]$m.tag)
            $note=[Windows.Forms.Interaction]::InputBox("Ghi chú","HMS Codex Note",[string]$m.note)
            Set-CodexAccountMeta $email $tag $note ([bool]$m.favorite)
            Refresh-Mission
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bAddAcc.Add_Click({try{Login-Provider "--codex-login"}catch{}})
    $bQuotaCenter.Add_Click({try{Start-Process ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/management.html#/quota")|Out-Null}catch{}})
    $bBatch.Add_Click({Show-CodexAccountBatchCenter})
    $bExportRed.Add_Click({try{$p=Export-CodexAccountsRedacted;[Windows.Forms.MessageBox]::Show("Đã export redacted:`r`n$p","Export")|Out-Null}catch{}})

    $bNewInst.Add_Click({
        try{
            $name=[Windows.Forms.Interaction]::InputBox("Tên instance","Tạo Codex Instance","Project 1")
            if(-not $name){return}
            $proj=[Windows.Forms.Interaction]::InputBox("Project directory (để trống nếu không bind project)","Project Binding","")
            $accounts=@(Get-CodexAccountRecords)
            if($accounts.Count -eq 0){throw "Chưa có Codex ACC."}
            $choices=($accounts|ForEach-Object {$_.Email}) -join "`r`n"
            $email=[Windows.Forms.Interaction]::InputBox("Nhập chính xác email ACC muốn bind:`r`n$choices","Account Binding",$accounts[0].Email)
            $mode=[Windows.Forms.Interaction]::InputBox("Launch mode: cli hoặc desktop","Launch Mode","cli")
            $i=New-CodexInstance $name $proj $email $mode
            [Windows.Forms.MessageBox]::Show("Đã tạo $($i.name) / $($i.accountEmail) / port $($i.port)","Codex Instance")|Out-Null
            Refresh-Mission
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,"Instance Error")|Out-Null}
    })
    $bStartInst.Add_Click({
        try{
            if($instGrid.SelectedRows.Count -lt 1){throw "Chọn instance."}
            $id=[string]$instGrid.SelectedRows[0].Cells["Id"].Value
            [Windows.Forms.MessageBox]::Show((Start-CodexInstance $id),"Codex Instance")|Out-Null
            Refresh-Mission
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,"Start Error")|Out-Null}
    })
    $bStopInst.Add_Click({
        try{
            if($instGrid.SelectedRows.Count -lt 1){throw "Chọn instance."}
            $id=[string]$instGrid.SelectedRows[0].Cells["Id"].Value
            [Windows.Forms.MessageBox]::Show((Stop-CodexInstance $id),"Codex Instance")|Out-Null
            Refresh-Mission
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,"Stop Error")|Out-Null}
    })
    $bOpenInst.Add_Click({
        try{
            if($instGrid.SelectedRows.Count -lt 1){throw "Chọn instance."}
            $id=[string]$instGrid.SelectedRows[0].Cells["Id"].Value
            $s=Get-CodexInstanceStore;$i=@($s.instances|Where-Object id -eq $id| Select-Object -First 1)
            if($i.Count){Start-Process explorer.exe $i[0].root|Out-Null}
        }catch{}
    })
    $bRestartInst.Add_Click({try{if($instGrid.SelectedRows.Count -lt 1){throw"Chọn instance."};$id=[string]$instGrid.SelectedRows[0].Cells["Id"].Value;[Windows.Forms.MessageBox]::Show((Restart-CodexInstance $id),"Instance")|Out-Null;Refresh-Mission}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bFocusInst.Add_Click({try{if($instGrid.SelectedRows.Count -lt 1){throw"Chọn instance."};$id=[string]$instGrid.SelectedRows[0].Cells["Id"].Value;[Windows.Forms.MessageBox]::Show((Focus-CodexInstance $id),"Instance")|Out-Null}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bSessionCenter.Add_Click({Show-CodexSessionCenter})


    $bUnifiedUx.Add_Click({try{$m=Start-HmsUnifiedUx;Status $m}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bRuntimeCert.Add_Click({
        $wiz=Join-Path $PSScriptRoot "HMS_FirstRun_Wizard.ps1"
        if(Test-Path $wiz){
            Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$wiz+'"') -WindowStyle Hidden|Out-Null
        }else{[Windows.Forms.MessageBox]::Show("Thiếu HMS_FirstRun_Wizard.ps1")|Out-Null}
    })
    $bRuntimeEvidence.Add_Click({
        if(Test-Path $script:RuntimeCertDir){Start-Process explorer.exe $script:RuntimeCertDir|Out-Null}
    })
    $bTargetCert.Add_Click({Show-HmsTargetMachineCertificationCenter})
    $bApiSuperset.Add_Click({Show-HmsApiSupersetCenter})
    $bProxyFleet.Add_Click({Show-HmsProxyFleetCenter})
    $bProxyAffinity.Add_Click({Show-HmsProxyAffinityCenter})
    $bSmartGateway.Add_Click({Show-HmsSmartGatewayCenter})
    $bWindowsGate.Add_Click({Show-HmsWindowsRuntimeGateCenter})
    $bSourceIntegrity.Add_Click({Show-HmsPowerShellSourceAudit})
    $bKernel.Add_Click({Show-HmsPolicyKernelCenter})
    $bPerformance.Add_Click({Show-HmsPerformanceCenter})
    $bSoak.Add_Click({Show-HmsSoakCenter})
    $bPoolRecovery.Add_Click({Show-CodexPoolRecoveryCenter})
    $bRouterIntel.Add_Click({Show-CodexRouterIntelligenceCenter})
    $bAccountSessionOps.Add_Click({Show-CodexAccountSessionOperations})
    $bValidationCenter.Add_Click({Show-HmsValidationCenter})
    $bReleaseCenter.Add_Click({Show-HmsReleaseEngineeringCenter})
    $bProduction.Add_Click({Show-HmsProductionCenter})
    $bUnified.Add_Click({Show-CodexUnifiedCommandCenter})
    $bHa.Add_Click({Show-CodexHaCenter})
    $bAuto.Add_Click({Show-CodexAutopilotCenter})
    $bOps.Add_Click({Show-CodexOperationsCenter})
    $bFleet.Add_Click({Show-CodexFleetCenter})
    $bOrchestrator.Add_Click({Show-CodexOrchestrator})
    $bThreadCenter.Add_Click({Show-CodexThreadSyncCenter})
    $bTelCenter.Add_Click({Show-CodexTelemetryCenter})
    $bBackupCenter.Add_Click({Show-HmsBackupCenter})
    $bRouteRefresh.Add_Click({Refresh-Mission})
    $bRouterDiag.Add_Click({[Windows.Forms.MessageBox]::Show((Get-CodexDiagnosticsText),"Codex Diagnostics")|Out-Null})
    $bRouterRestart.Add_Click({try{$null=Restart-Router;Refresh-Mission}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bOpenLogs.Add_Click({
        $d=Join-Path ([string]$script:S.ProxyDir) "logs"
        if(Test-Path $d){Start-Process explorer.exe $d|Out-Null}else{Start-Process explorer.exe ([string]$script:S.ProxyDir)|Out-Null}
    })
    $bWake.Add_Click({
        try{$wakeOut.Text=(Invoke-CodexWakeupNow)+"`r`n"+(Get-Date).ToString("G")}
        catch{$wakeOut.Text="LỖI: "+$_.Exception.Message}
    })
    $bWakeScheduler.Add_Click({Show-CodexWakeupScheduler})

    $timer=New-Object Windows.Forms.Timer;$timer.Interval=10000;$timer.Add_Tick({try{Refresh-Mission}catch{}});$timer.Start()
    $w.Add_FormClosed({try{$timer.Stop();$timer.Dispose()}catch{}})
    $w.Add_Shown({Refresh-Mission})
    [void]$w.ShowDialog($form)
}



# ============================================================
# CODEX MEGA v1.5
# Scheduler / Session Doctor / Account batch / Instance lifecycle
# ============================================================

function Get-SessionDoctorPath {
    return (Join-Path $PSScriptRoot "HMS_Codex_SessionDoctor.py")
}
function Invoke-CodexSessionDoctor {
    param([string]$CodexHome,[ValidateSet("audit","repair")][string]$Mode="audit",[string]$Provider="")
    $py=[string]$script:S.CodexSessionDoctorPython
    $helper=Get-SessionDoctorPath
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_SessionDoctor.py"}
    $tmp=Join-Path $env:TEMP ("hms-session-doctor-"+[Guid]::NewGuid().ToString("N")+".json")
    $args=@($helper,"--home",$CodexHome,"--mode",$Mode,"--output",$tmp)
    if($Provider){$args+=@("--provider",$Provider)}
    $p=Start-Process $py -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    if(-not (Test-Path $tmp)){throw "Session Doctor không tạo kết quả. Python exit=$($p.ExitCode)"}
    try{$j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json}finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    if(-not $j.ok){throw [string]$j.error}
    return $j
}
function Get-AllCodexHomes {
    $rows=[System.Collections.Generic.List[object]]::new()
    $rows.Add([PSCustomObject]@{Id="__default__";Name="Mặc định";Home=$script:CodexDir;Running=(@(Get-CodexClientProcesses).Count -gt 0)})
    $s=Get-CodexInstanceStore
    foreach($i in @($s.instances)){
        $running=$false
        if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;$running=$true}catch{}}
        $rows.Add([PSCustomObject]@{Id=$i.id;Name=$i.name;Home=$i.codexHome;Running=$running})
    }
    return @($rows)
}
function Format-SessionAudit {
    param([object]$Result)
    $d=$Result.data
    $lines=[System.Collections.Generic.List[string]]::new()
    $lines.Add("CODEX_HOME: "+[string]$d.home)
    $lines.Add("Target provider: "+[string]$d.target_provider)
    $lines.Add("Session files: "+[string]$d.session_file_count)
    $lines.Add("Unreadable session files: "+[string]$d.unreadable_session_files)
    $lines.Add("Provider mismatch: "+[string]$d.provider_mismatch_count)
    $lines.Add("Session index rows: "+[string]$d.session_index_rows)
    $lines.Add("Bad index rows: "+[string]$d.bad_session_index_rows)
    $lines.Add("Missing index IDs: "+@($d.missing_index_session_ids).Count)
    $lines.Add("Stale index IDs: "+@($d.stale_index_session_ids).Count)
    foreach($db in @($d.sqlite)){
        $lines.Add("SQLite: $($db.path) | ok=$($db.ok) | threads=$($db.threads) | providers="+(($db.provider_counts| ConvertTo-Json -Compress)))
    }
    return ($lines -join "`r`n")
}
function Show-CodexSessionCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Session Center v1.5"
    $w.Size=New-Object Drawing.Size(1120,690);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244);$w.Font=New-Object Drawing.Font("Segoe UI",9.5)

    $l=New-Object Windows.Forms.Label;$l.Text="SESSION VISIBILITY / DOCTOR";$l.Font=New-Object Drawing.Font("Segoe UI Semibold",17);$l.Location=New-Object Drawing.Point(18,16);$l.AutoSize=$true;$w.Controls.Add($l)
    $combo=New-Object Windows.Forms.ComboBox;$combo.DropDownStyle="DropDownList";$combo.Location=New-Object Drawing.Point(20,60);$combo.Size=New-Object Drawing.Size(410,28);$w.Controls.Add($combo)
    $homes=@(Get-AllCodexHomes)
    foreach($h in $homes){[void]$combo.Items.Add("$($h.Name) | $($h.Home)")}
    if($combo.Items.Count){$combo.SelectedIndex=0}
    $bAudit=Btn "AUDIT READ-ONLY" 450 57 180 34;$w.Controls.Add($bAudit)
    $bRepair=Btn "REPAIR CÓ BACKUP" 645 57 190 34;$bRepair.BackColor=[Drawing.Color]::FromArgb(105,76,38);$w.Controls.Add($bRepair)
    $bOpen=Btn "MỞ CODEX_HOME" 850 57 190 34;$w.Controls.Add($bOpen)

    $outBox=New-Object Windows.Forms.TextBox;$outBox.Location=New-Object Drawing.Point(20,108);$outBox.Size=New-Object Drawing.Size(1040,470)
    $outBox.Multiline=$true;$outBox.ReadOnly=$true;$outBox.ScrollBars="Both";$outBox.WordWrap=$false;$outBox.BackColor=[Drawing.Color]::FromArgb(22,25,30);$outBox.ForeColor=$w.ForeColor;$w.Controls.Add($outBox)
    $note=New-Object Windows.Forms.Label;$note.Location=New-Object Drawing.Point(20,594);$note.Size=New-Object Drawing.Size(1040,50)
    $note.Text="Audit không sửa file. Repair chỉ chạy sau xác nhận, tạo backup trước và không xóa session. Nếu instance đang RUNNING, HMS khuyên dừng instance trước."
    $note.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($note)

    function SelectedHome {
        if($combo.SelectedIndex -lt 0){throw "Chọn CODEX_HOME."}
        return $homes[$combo.SelectedIndex]
    }
    $bAudit.Add_Click({
        try{$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;$h=SelectedHome;$r=Invoke-CodexSessionDoctor $h.Home "audit";$outBox.Text=Format-SessionAudit $r}
        catch{$outBox.Text="LỖI: "+$_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}
    })
    $bRepair.Add_Click({
        try{
            $h=SelectedHome
            if($h.Running){
                $ans=[Windows.Forms.MessageBox]::Show("Instance này đang chạy. Sửa session DB khi Codex đang ghi dữ liệu có rủi ro.`r`n`r`nBạn vẫn muốn tiếp tục?","CẢNH BÁO",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
                if($ans -ne [Windows.Forms.DialogResult]::Yes){return}
            }
            $ans=[Windows.Forms.MessageBox]::Show("HMS sẽ BACKUP trước rồi sửa provider visibility trong session metadata/SQLite. Không xóa session.`r`n`r`nTiếp tục?","XÁC NHẬN REPAIR",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Question)
            if($ans -ne [Windows.Forms.DialogResult]::Yes){return}
            $w.Cursor=[Windows.Forms.Cursors]::WaitCursor
            $r=Invoke-CodexSessionDoctor $h.Home "repair"
            $outBox.Text="REPAIR PASS`r`nBackup: "+[string]$r.data.backup+"`r`nChanged session files: "+[string]$r.data.changed_session_files+"`r`nSQLite rows: "+[string]$r.data.updated_sqlite_rows+"`r`n`r`nAFTER:`r`n"+(Format-SessionAudit ([PSCustomObject]@{data=$r.data.after}))
        }catch{$outBox.Text="LỖI REPAIR: "+$_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}
    })
    $bOpen.Add_Click({try{$h=SelectedHome;Start-Process explorer.exe $h.Home|Out-Null}catch{}})
    [void]$w.ShowDialog($form)
}

# ---------------- Persistent Wake-up scheduler ----------------

function Get-WakeupState {
    $j=Load-JsonObjectSafe $script:CodexWakeupPath
    if(-not $j){return [PSCustomObject]@{enabled=$false;tasks=@()}}
    return $j
}
function Save-WakeupState([object]$State){Save-JsonAtomic $script:CodexWakeupPath $State}
function New-WakeupTask {
    param([string]$Name,[string]$Kind,[string]$Value,[string[]]$Accounts)
    $state=Get-WakeupState
    $tasks=@($state.tasks)
    $task=[PSCustomObject]@{
        id=[Guid]::NewGuid().ToString("N").Substring(0,12);name=$Name;enabled=$true;kind=$Kind;value=$Value;
        accounts=$Accounts;createdUtc=[DateTime]::UtcNow.ToString("o");lastRunUtc=$null;lastResult="";lastDueKey=""
    }
    $tasks+=$task;$state.tasks=$tasks;Save-WakeupState $state;return $task
}
function Get-QuotaResetDueKey {
    param([object]$Task)
    $cache=Get-CodexQuotaCache;$now=Get-Date
    $keys=[System.Collections.Generic.List[string]]::new()
    foreach($email in @($Task.accounts)){
        $k=$email.Trim().ToLowerInvariant()
        if(-not $cache.ContainsKey($k)){continue}
        $q=$cache[$k]
        foreach($v in @($q.hourlyReset,$q.weeklyReset)){
            if(-not $v){continue}
            try{
                $dt=[DateTime]::Parse([string]$v).ToLocalTime()
                if($dt -le $now -and ($now-$dt).TotalMinutes -le 10){$keys.Add($dt.ToString("o"))}
            }catch{}
        }
    }
    if($keys.Count){return (($keys| Sort-Object -Unique) -join "|")}
    return ""
}
function Test-WakeupTaskDue {
    param([object]$Task,[DateTime]$Now)
    if(-not [bool]$Task.enabled){return $false}
    $last=$null;try{if($Task.lastRunUtc){$last=[DateTime]::Parse([string]$Task.lastRunUtc).ToLocalTime()}}catch{}
    switch([string]$Task.kind){
        "startup" { return (-not $last) }
        "interval" {
            $hours=4.0;try{$hours=[double]$Task.value}catch{}
            if($hours -lt 1){$hours=1}
            return (-not $last) -or (($Now-$last).TotalHours -ge $hours)
        }
        "daily" {
            if([string]$Task.value -notmatch '^(\d{1,2}):(\d{2})$'){return $false}
            $h=[int]$matches[1];$m=[int]$matches[2]
            $due=Get-Date -Year $Now.Year -Month $Now.Month -Day $Now.Day -Hour $h -Minute $m -Second 0
            return $due -le $Now -and ((-not $last) -or $last -lt $due)
        }
        "weekly" {
            # value: Mon,Wed,Fri@08:30
            if([string]$Task.value -notmatch '^([^@]+)@(\d{1,2}):(\d{2})$'){return $false}
            $days=@($matches[1].Split(',')|ForEach-Object{$_.Trim().ToLowerInvariant()})
            $map=@{"sun"=0;"mon"=1;"tue"=2;"wed"=3;"thu"=4;"fri"=5;"sat"=6}
            $today=[int]$Now.DayOfWeek
            $match=$false;foreach($d in $days){if($map.ContainsKey($d) -and [int]$map[$d] -eq $today){$match=$true}}
            if(-not $match){return $false}
            $due=Get-Date -Year $Now.Year -Month $Now.Month -Day $Now.Day -Hour ([int]$matches[2]) -Minute ([int]$matches[3]) -Second 0
            return $due -le $Now -and ((-not $last) -or $last -lt $due)
        }
        "quota_reset" {
            $key=Get-QuotaResetDueKey $Task
            return $key -and $key -ne [string]$Task.lastDueKey
        }
    }
    return $false
}
function Invoke-WakeupForAccount {
    param([string]$Email)
    # Deterministic one-account child instance is too heavy for wakeup.
    # Main router is used, but account is recorded only as target intent unless the pool itself binds it.
    # This avoids editing OAuth files merely for a wake-up.
    $m=Invoke-CodexWakeupNow
    return $m
}
function Run-WakeupTask {
    param([string]$TaskId,[string]$Trigger="scheduled")
    $state=Get-WakeupState;$task=@($state.tasks|Where-Object id -eq $TaskId| Select-Object -First 1)
    if($task.Count -eq 0){throw "Wake-up task không tồn tại."}
    $t=$task[0];$results=[System.Collections.Generic.List[string]]::new()
    $accounts=@($t.accounts)
    if($accounts.Count -eq 0){$results.Add((Invoke-CodexWakeupNow))}
    else{foreach($email in $accounts){try{$results.Add("${email}: "+(Invoke-WakeupForAccount $email))}catch{$results.Add("${email}: FAIL "+$_.Exception.Message)}}}
    $t.lastRunUtc=[DateTime]::UtcNow.ToString("o")
    if($t.kind -eq "quota_reset"){$t.lastDueKey=Get-QuotaResetDueKey $t}
    $t.lastResult=($results -join " | ")
    Save-WakeupState $state
    $entry=[ordered]@{time=[DateTime]::UtcNow.ToString("o");taskId=$t.id;name=$t.name;trigger=$Trigger;result=$t.lastResult}
    Add-Content $script:CodexWakeupLogPath ($entry| ConvertTo-Json -Compress) -Encoding UTF8
    return $t.lastResult
}
function Invoke-WakeupSchedulerTick {
    $state=Get-WakeupState
    if(-not [bool]$state.enabled){return ""}
    $now=Get-Date;$ran=[System.Collections.Generic.List[string]]::new()
    foreach($t in @($state.tasks)){
        if(Test-WakeupTaskDue $t $now){
            try{$ran.Add("$($t.name): "+(Run-WakeupTask $t.id "scheduled"))}catch{$ran.Add("$($t.name): FAIL "+$_.Exception.Message)}
        }
    }
    if($ran.Count){return "Wake-up scheduler: "+($ran -join " || ")}
    return ""
}
function Show-CodexWakeupScheduler {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Wake-up Scheduler v1.5";$w.Size=New-Object Drawing.Size(1180,690);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244);$w.Font=New-Object Drawing.Font("Segoe UI",9.5)
    $grid=New-DarkGrid 18 80 1125 430 $w
    $enable=New-Object Windows.Forms.CheckBox;$enable.Text="BẬT SCHEDULER";$enable.Location=New-Object Drawing.Point(20,20);$enable.AutoSize=$true;$enable.ForeColor=$w.ForeColor;$w.Controls.Add($enable)
    $bNew=Btn "＋ TẠO TASK" 180 15 140 34;$w.Controls.Add($bNew)
    $bRun=Btn "RUN NOW" 335 15 120 34;$w.Controls.Add($bRun)
    $bToggle=Btn "BẬT/TẮT TASK" 470 15 140 34;$w.Controls.Add($bToggle)
    $bRefresh=Btn "REFRESH" 625 15 120 34;$w.Controls.Add($bRefresh)
    $help=New-Object Windows.Forms.Label;$help.Location=New-Object Drawing.Point(18,530);$help.Size=New-Object Drawing.Size(1125,95)
    $help.Text="Schedule kind: startup | interval (value=giờ, ví dụ 4) | daily (08:30) | weekly (Mon,Wed,Fri@08:30) | quota_reset. Scheduler kiểm tra mỗi 30 giây. Mặc định toàn hệ thống OFF vì wake-up tiêu thụ quota."
    $help.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($help)

    function Refresh-Wake {
        $s=Get-WakeupState;$enable.Checked=[bool]$s.enabled
        $rows=@($s.tasks|ForEach-Object{[PSCustomObject]@{Id=$_.id;Enabled=$_.enabled;Name=$_.name;Kind=$_.kind;Value=$_.value;Accounts=(@($_.accounts)-join ",");LastRun=$_.lastRunUtc;LastResult=$_.lastResult}})
        $grid.DataSource=$null;$grid.DataSource=$rows
    }
    $enable.Add_CheckedChanged({$s=Get-WakeupState;$s.enabled=[bool]$enable.Checked;Save-WakeupState $s})
    $bNew.Add_Click({
        try{
            $name=[Windows.Forms.Interaction]::InputBox("Tên task","Wake-up task","Codex Keep Warm");if(-not $name){return}
            $kind=[Windows.Forms.Interaction]::InputBox("Kind: startup / interval / daily / weekly / quota_reset","Schedule","interval")
            $value=[Windows.Forms.Interaction]::InputBox("Value theo kind (interval=4, daily=08:30, weekly=Mon,Wed@08:30)","Value","4")
            $accounts=[Windows.Forms.Interaction]::InputBox("Email account, phân cách dấu phẩy. Để trống = pool chung.","Accounts","")
            $arr=@();if($accounts){$arr=@($accounts.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})}
            $null=New-WakeupTask $name $kind $value $arr;Refresh-Wake
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bRun.Add_Click({try{if($grid.SelectedRows.Count -lt 1){throw"Chọn task."};$id=[string]$grid.SelectedRows[0].Cells["Id"].Value;[Windows.Forms.MessageBox]::Show((Run-WakeupTask $id "manual"),"Wake-up")|Out-Null;Refresh-Wake}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bToggle.Add_Click({try{if($grid.SelectedRows.Count -lt 1){throw"Chọn task."};$id=[string]$grid.SelectedRows[0].Cells["Id"].Value;$s=Get-WakeupState;foreach($t in $s.tasks){if($t.id -eq $id){$t.enabled=-not [bool]$t.enabled}};Save-WakeupState $s;Refresh-Wake}catch{}})
    $bRefresh.Add_Click({Refresh-Wake});$w.Add_Shown({Refresh-Wake});[void]$w.ShowDialog($form)
}

# ---------------- Account batch / redacted export ----------------

function Export-CodexAccountsRedacted {
    Ensure-Dir $script:CodexAccountExportDir
    $stamp=Get-Date -Format "yyyyMMdd-HHmmss"
    $dest=Join-Path $script:CodexAccountExportDir ("codex-accounts-redacted-"+$stamp+".json")
    $cache=Get-CodexQuotaCache
    $rows=@(Get-CodexAccountRecords|ForEach-Object{
        $m=Get-CodexAccountMeta $_.Email;$q=Get-CodexQuotaForEmail $_.Email
        [PSCustomObject]@{
            email=$_.Email;plan=$_.Plan;status=$_.Status;tag=[string]$m.tag;note=[string]$m.note;favorite=[bool]$m.favorite;
            quota=$q;priority=$_.Priority;weight=$_.Weight;updated=$_.Updated.ToString("o")
        }
    })
    Save-JsonAtomic $dest ([PSCustomObject]@{exportedUtc=[DateTime]::UtcNow.ToString("o");containsSecrets=$false;accounts=$rows})
    return $dest
}
function Show-CodexAccountBatchCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Account Batch Center v1.5";$w.Size=New-Object Drawing.Size(1120,660);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244);$w.Font=New-Object Drawing.Font("Segoe UI",9.5)
    $filter=New-Object Windows.Forms.TextBox;$filter.Location=New-Object Drawing.Point(18,18);$filter.Size=New-Object Drawing.Size(340,27);$w.Controls.Add($filter)
    $bFilter=Btn "LỌC" 370 15 90 34;$w.Controls.Add($bFilter)
    $bExport=Btn "EXPORT REDACTED" 475 15 170 34;$w.Controls.Add($bExport)
    $bRefreshAll=Btn "REFRESH QUOTA" 660 15 150 34;$w.Controls.Add($bRefreshAll)
    $grid=New-DarkGrid 18 65 1045 500 $w
    function Refresh-Batch {
        $needle=$filter.Text.Trim().ToLowerInvariant()
        $rows=@(Get-CodexAccountRecords|ForEach-Object{$m=Get-CodexAccountMeta $_.Email;$q=Get-CodexQuotaForEmail $_.Email;[PSCustomObject]@{Account=$_.Email;Plan=$_.Plan;Status=$_.Status;Tag=$m.tag;Hourly=if($q){$q.hourlyRemaining}else{$null};Weekly=if($q){$q.weeklyRemaining}else{$null};Note=$m.note}}|Where-Object{(-not $needle) -or (($_| ConvertTo-Json -Compress).ToLowerInvariant().Contains($needle))})
        $grid.DataSource=$null;$grid.DataSource=$rows
    }
    $bFilter.Add_Click({Refresh-Batch})
    $bExport.Add_Click({try{$p=Export-CodexAccountsRedacted;[Windows.Forms.MessageBox]::Show("Đã export không chứa token:`r`n$p","Export")|Out-Null}catch{}})
    $bRefreshAll.Add_Click({try{[Windows.Forms.MessageBox]::Show((Refresh-CodexQuotaAll),"Quota")|Out-Null;Refresh-Batch}catch{}})
    $w.Add_Shown({Refresh-Batch});[void]$w.ShowDialog($form)
}

# ---------------- Instance lifecycle upgrades ----------------

function Restart-CodexInstance {
    param([string]$Id)
    $null=Stop-CodexInstance $Id;Start-Sleep -Milliseconds 600;return (Start-CodexInstanceSafe $Id)
}
function Focus-CodexInstance {
    param([string]$Id)
    $s=Get-CodexInstanceStore;$i=@($s.instances|Where-Object id -eq $Id| Select-Object -First 1)
    if($i.Count -eq 0){throw"Instance không tồn tại."}
    $procId=[int]$i[0].clientPid
    if($procId -le 0){throw"Instance chưa chạy."}
    try{
        $p=Get-Process -Id $procId -ErrorAction Stop
        if($p.MainWindowHandle -ne 0){
            Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class HMSWin32 {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
 [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd,int nCmdShow);
}
"@ -ErrorAction SilentlyContinue
            [HMSWin32]::ShowWindowAsync($p.MainWindowHandle,9)|Out-Null
            [HMSWin32]::SetForegroundWindow($p.MainWindowHandle)|Out-Null
            return "Đã focus $($i[0].name)."
        }
    }catch{}
    return "Không tìm thấy window handle; process vẫn có thể đang chạy."
}


# ============================================================
# CODEX CONTROL PLANE v2.0
# ============================================================
function Invoke-PythonJsonHelper {
    param([string]$Python,[string]$Script,[string[]]$Arguments)
    if(-not (Test-Path $Script)){throw "Thiếu helper: $Script"}
    $tmp=Join-Path $env:TEMP ("hms-helper-"+[Guid]::NewGuid().ToString("N")+".json")
    $args=@($Script)+$Arguments+@("--output",$tmp)
    $p=Start-Process $Python -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    if(-not (Test-Path $tmp)){throw "Helper không tạo output. exit=$($p.ExitCode)"}
    try{$j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json}finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    if(-not $j.ok){throw [string]$j.error}
    return $j
}
function Get-InstanceGuardStore {
    $j=Load-JsonObjectSafe $script:CodexInstanceGuardPath
    if(-not $j){return @{}}
    $h=@{};foreach($p in @($j.PSObject.Properties)){$h[$p.Name]=$p.Value};return $h
}
function Save-InstanceGuardStore([hashtable]$Store){
    $o=[ordered]@{};foreach($k in ($Store.Keys|Sort-Object)){$o[$k]=$Store[$k]};Save-JsonAtomic $script:CodexInstanceGuardPath $o
}
function Acquire-CodexInstanceStartGuard {
    param([string]$Id)
    $s=Get-InstanceGuardStore;$now=[DateTime]::UtcNow
    if($s.ContainsKey($Id)){
        try{
            $dt=[DateTime]::Parse([string]$s[$Id].startedUtc)
            if(($now-$dt).TotalSeconds -lt [int]$script:S.CodexGuardTimeoutSec){throw "Instance $Id đang START. Hãy chờ."}
        }catch{if($_.Exception.Message -like "Instance * đang START*"){throw}}
    }
    $s[$Id]=[PSCustomObject]@{startedUtc=$now.ToString("o");pid=$PID};Save-InstanceGuardStore $s
}
function Release-CodexInstanceStartGuard {
    param([string]$Id)
    $s=Get-InstanceGuardStore;if($s.ContainsKey($Id)){$s.Remove($Id);Save-InstanceGuardStore $s}
}
function Invoke-CodexConfigDoctor {
    param([string]$ConfigPath,[ValidateSet("audit","sanitize")][string]$Mode="audit")
    Invoke-PythonJsonHelper ([string]$script:S.CodexSessionDoctorPython) (Join-Path $PSScriptRoot "HMS_Codex_ConfigDoctor.py") @("--path",$ConfigPath,"--mode",$Mode)
}
function Sanitize-CodexHomeIfEnabled {
    param([string]$codexHome)
    if(-not [bool]$script:S.CodexAutoSanitizeBeforeLaunch){return ""}
    $path=Join-Path $codexHome "config.toml";if(-not (Test-Path $path)){return ""}
    try{
        $a=Invoke-CodexConfigDoctor $path "audit"
        if([int]$a.data.issue_count -le 0){return "Config Doctor: PASS"}
        $r=Invoke-CodexConfigDoctor $path "sanitize"
        Add-Content $script:CodexConfigDoctorLog (([ordered]@{time=[DateTime]::UtcNow.ToString("o");path=$path;changed=$r.data.changed;backup=$r.data.backup})| ConvertTo-Json -Compress) -Encoding UTF8
        return "Config Doctor: sanitized $($a.data.issue_count) issue(s)"
    }catch{return "Config Doctor WARN: "+$_.Exception.Message}
}
function Test-AllManagedCodexStopped {
    if(@(Get-CodexClientProcesses).Count -gt 0){return $false}
    foreach($i in @((Get-CodexInstanceStore).instances)){
        if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;return $false}catch{}}
    }
    return $true
}
function Invoke-CodexThreadSync {
    param([ValidateSet("audit","sync")][string]$Mode="audit")
    $homes=@(Get-AllCodexHomes|ForEach-Object{$_.Home}|Where-Object{$_ -and(Test-Path $_)}| Select-Object -Unique)
    if($homes.Count -lt 2){throw "Cần ít nhất 2 CODEX_HOME."}
    if($Mode -eq "sync" -and -not (Test-AllManagedCodexStopped)){throw "Thread Sync chỉ chạy khi tất cả Codex STOP."}
    $args=[System.Collections.Generic.List[string]]::new()
    foreach($h in $homes){$args.Add("--home");$args.Add([string]$h)}
    $args.Add("--mode");$args.Add($Mode)
    Invoke-PythonJsonHelper ([string]$script:S.CodexThreadSyncPython) (Join-Path $PSScriptRoot "HMS_Codex_ThreadSync.py") $args.ToArray()
}
function Format-ThreadSyncResult {
    param([object]$R)
    $d=$R.data;$l=[System.Collections.Generic.List[string]]::new()
    if($R.mode -eq "audit"){
        $l.Add("Global sessions: "+[string]$d.global_sessions)
        foreach($t in @($d.targets)){$l.Add("$($t.home) | sessions=$($t.session_count) | missing=$($t.missing_from_global)")}
    }else{
        $l.Add("Global session IDs: "+[string]$d.session_ids)
        foreach($t in @($d.targets)){$l.Add("$($t.home) | copied=$($t.copied_sessions) | index_added=$($t.index_added) | conflicts="+@($t.conflicts).Count+" | backup=$($t.backup)")}
    }
    $l-join"`r`n"
}
function Show-CodexThreadSyncCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Idle Thread Sync v2.0";$w.Size=New-Object Drawing.Size(1100,650);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $bA=Btn "AUDIT" 20 25 140 36;$w.Controls.Add($bA);$bS=Btn "SYNC KHI IDLE" 175 25 180 36;$w.Controls.Add($bS)
    $box=New-Object Windows.Forms.TextBox;$box.Location=New-Object Drawing.Point(20,80);$box.Size=New-Object Drawing.Size(1030,490);$box.Multiline=$true;$box.ReadOnly=$true;$box.ScrollBars="Both";$box.BackColor=[Drawing.Color]::FromArgb(22,25,30);$box.ForeColor=$w.ForeColor;$w.Controls.Add($box)
    $bA.Add_Click({try{$box.Text=Format-ThreadSyncResult (Invoke-CodexThreadSync "audit")}catch{$box.Text=$_.Exception.Message}})
    $bS.Add_Click({try{if(-not (Test-AllManagedCodexStopped)){throw"Có Codex đang chạy."};$box.Text=Format-ThreadSyncResult (Invoke-CodexThreadSync "sync")}catch{$box.Text=$_.Exception.Message}})
    [void]$w.ShowDialog($form)
}
function Get-ProcessTelemetrySafe {
    param([int]$procId)
    if($procId -le 0){return $null}
    try{$p=Get-Process -Id $procId -ErrorAction Stop;[PSCustomObject]@{Pid=$procId;Name=$p.ProcessName;RamMB=[Math]::Round($p.WorkingSet64/1MB,1);CpuSec=[Math]::Round($p.CPU,1);Threads=$p.Threads.Count}}catch{$null}
}
function Get-CodexTelemetryRows {
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($p in @(Get-CodexClientProcesses)){$t=Get-ProcessTelemetrySafe $p.Id;if($t){$rows.Add([PSCustomObject]@{Type="Default";Instance="Default";Account="shared";PID=$t.Pid;Process=$t.Name;RAM_MB=$t.RamMB;CPU_s=$t.CpuSec;Threads=$t.Threads;Port=[int]$script:S.ProxyPort})}}
    foreach($i in @((Get-CodexInstanceStore).instances)){
        $t=Get-ProcessTelemetrySafe ([int]$i.clientPid);if($t){$rows.Add([PSCustomObject]@{Type="Managed";Instance=$i.name;Account=$i.accountEmail;PID=$t.Pid;Process=$t.Name;RAM_MB=$t.RamMB;CPU_s=$t.CpuSec;Threads=$t.Threads;Port=$i.port})}
        $r=Get-ProcessTelemetrySafe ([int]$i.routerPid);if($r){$rows.Add([PSCustomObject]@{Type="Router";Instance=$i.name;Account=$i.accountEmail;PID=$r.Pid;Process=$r.Name;RAM_MB=$r.RamMB;CPU_s=$r.CpuSec;Threads=$r.Threads;Port=$i.port})}
    }
    return @($rows)
}
function Show-CodexTelemetryCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Telemetry v2.0";$w.Size=New-Object Drawing.Size(1120,620);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $g=New-DarkGrid 18 55 1065 490 $w
    function R{$g.DataSource=$null;$g.DataSource=@(Get-CodexTelemetryRows)}
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=5000;$tm.Add_Tick({R});$tm.Start();$w.Add_Shown({R});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()});[void]$w.ShowDialog($form)
}
function Invoke-CodexInstanceWatchdog {
    if($script:RuntimeAutomationBlocked){return "SAFE STARTUP: instance router recovery blocked."}
    if(-not [bool]$script:S.CodexInstanceRouterWatchdog){return ""}
    $msgs=[System.Collections.Generic.List[string]]::new()
    foreach($i in @((Get-CodexInstanceStore).instances)){
        $ca=$false;if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;$ca=$true}catch{}}
        if(-not $ca){continue}
        if((PortOpen ([int]$i.port))){continue}
        if((ListenerPid ([int]$i.port)) -gt 0){$msgs.Add("$($i.name): foreign port");continue}
        try{$procId=Start-CodexInstanceRouter $i;$msgs.Add("$($i.name): router recovered PID $procId")}catch{$msgs.Add("$($i.name): FAIL "+$_.Exception.Message)}
    }
    if($msgs.Count){"Instance Watchdog: "+($msgs-join" | ")}else{""}
}
function New-HmsControlPlaneBackup {
    Ensure-Dir $script:CodexBackupsDir;$d=Join-Path $script:CodexBackupsDir ("control-plane-"+(Get-Date -Format "yyyyMMdd-HHmmss"));Ensure-Dir $d
    foreach($f in @($script:SettingsPath,$script:CodexAccountMetaPath,$script:CodexInstancesPath,$script:CodexProjectAffinityPath,$script:CodexProjectAffinityHistoryPath,$script:CodexSeamlessRouterHistoryPath,$script:CodexWakeupPath,$script:CodexQuotaCachePath)){if(Test-Path $f){Copy-Item $f (Join-Path $d ([IO.Path]::GetFileName($f))) -Force}}
    Save-Json (Join-Path $d "manifest.json") ([ordered]@{createdUtc=[DateTime]::UtcNow.ToString("o");containsOAuthTokens=$false;version=$script:Version});$d
}
function Show-HmsBackupCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Backup Center";$w.Size=New-Object Drawing.Size(900,520);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $g=New-DarkGrid 18 70 845 350 $w;$b=Btn "TẠO BACKUP" 18 20 160 36;$w.Controls.Add($b);$o=Btn "MỞ FOLDER" 190 20 150 36;$w.Controls.Add($o)
    function R{$g.DataSource=$null;if(Test-Path $script:CodexBackupsDir){$g.DataSource=@(Get-ChildItem $script:CodexBackupsDir -Directory| Sort-Object Name -Descending|ForEach-Object{[PSCustomObject]@{Name=$_.Name;Path=$_.FullName;Created=$_.CreationTime}})}}
    $b.Add_Click({[Windows.Forms.MessageBox]::Show((New-HmsControlPlaneBackup),"Backup")|Out-Null;R});$o.Add_Click({Ensure-Dir $script:CodexBackupsDir;Start-Process explorer.exe $script:CodexBackupsDir|Out-Null});$w.Add_Shown({R});[void]$w.ShowDialog($form)
}
function Assert-HmsSecurityBeforeInstanceLaunch {
    param([object]$Instance)
    if(-not [bool]$script:S.CodexSecurityHardeningEnabled){return}
    if([bool]$script:S.CodexSecurityBlockReparsePoints){
        foreach($p in @([string]$Instance.root,[string]$Instance.codexHome,[string]$Instance.appData,[string]$Instance.routerDir)){
            if($p -and (Test-HmsPathHasReparsePoint $p)){throw ('SECURITY_REPARSE_POINT_BLOCKED: '+$p)}
        }
    }
    $k=Get-HmsInstanceApiKey $Instance
    if([string]::IsNullOrWhiteSpace([string]$k)){throw 'SECURITY_INSTANCE_PROTECTED_SECRET_MISSING'}
    if([bool]$script:S.CodexSecurityIntegritySealsEnabled){
        $ss=Get-HmsSecuritySealStatus
        if(@($ss.mismatches).Count -gt 0){throw ('SECURITY_INTEGRITY_SEAL_MISMATCH: '+(@($ss.mismatches)-join ', '))}
    }
}
function Start-CodexInstanceSafe {
    param([string]$Id)
    Acquire-CodexInstanceStartGuard $Id
    try{
        $i=Get-CodexInstanceById $Id
        $null=Ensure-CodexInstanceBinding $i
        Assert-HmsSecurityBeforeInstanceLaunch $i
        $sync=Sync-CodexInstanceRouterCredentialPool $i
        $san=Sanitize-CodexHomeIfEnabled $i.codexHome
        return (($sync,$san,(Start-CodexInstance $Id)|Where-Object {$_}) -join "`r`n")
    }finally{Release-CodexInstanceStartGuard $Id}
}
function Show-CodexOrchestrator {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Orchestrator v2.0";$w.Size=New-Object Drawing.Size(1220,670);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(17,19,23);$w.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
    $g=New-DarkGrid 18 80 1165 470 $w
    $bs=Btn "START SAFE" 18 25 130 34;$w.Controls.Add($bs);$bp=Btn "STOP" 160 25 100 34;$w.Controls.Add($bp);$bt=Btn "TELEMETRY" 272 25 130 34;$w.Controls.Add($bt);$by=Btn "THREAD SYNC" 414 25 140 34;$w.Controls.Add($by);$bb=Btn "BACKUP" 566 25 110 34;$w.Controls.Add($bb)
    function R{$g.DataSource=$null;$g.DataSource=@(Get-CodexInstanceRows)};function I{if($g.SelectedRows.Count -lt 1){throw"Chọn instance."};[string]$g.SelectedRows[0].Cells["Id"].Value}
    $bs.Add_Click({try{[Windows.Forms.MessageBox]::Show((Start-CodexInstanceSafe(I)),"Start")|Out-Null;R}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bp.Add_Click({try{[Windows.Forms.MessageBox]::Show((Stop-CodexInstance(I)),"Stop")|Out-Null;R}catch{}})
    $bt.Add_Click({Show-CodexTelemetryCenter});$by.Add_Click({Show-CodexThreadSyncCenter});$bb.Add_Click({Show-HmsBackupCenter});$w.Add_Shown({R});[void]$w.ShowDialog($form)
}


# ============================================================
# CODEX FLEET & POLICY ENGINE v3.0
# ============================================================
function Get-CodexFleetPolicyState {
    $j=Load-JsonObjectSafe $script:CodexFleetPolicyPath
    if(-not $j){
        return [PSCustomObject]@{
            enabled=[bool]$script:S.CodexFleetEnabled;policy=[string]$script:S.CodexFleetPolicy;
            quotaFloor=[int]$script:S.CodexFleetQuotaFloor;reserveCount=[int]$script:S.CodexFleetReserveCount;
            maxPerAccount=[int]$script:S.CodexFleetMaxInstancesPerAccount;preferFavorite=[bool]$script:S.CodexFleetPreferFavorite
        }
    }
    return $j
}
function Save-CodexFleetPolicyState([object]$State){Save-JsonAtomic $script:CodexFleetPolicyPath $State}

function Get-CodexFleetAccountRows {
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($a in @(Get-CodexAccountRecords)){
        $h=Get-CodexAccountHealth $a;$q=Get-CodexQuotaForEmail $a.Email;$m=Get-CodexAccountMeta $a.Email
        $effectiveStatus=$a.Status
        $ops=Get-CodexAccountOps $a.Email
        if(([bool]$script:S.AccountOpsExcludeMaintenanceFromFleet) -and ([string]$ops.state -eq "MAINTENANCE")){$effectiveStatus="MAINTENANCE"}
        if(([bool]$script:S.AccountOpsExcludeQuarantineFromFleet) -and ([string]$ops.state -eq "QUARANTINED")){$effectiveStatus="QUARANTINED"}
        if([bool]$script:S.CodexHaIntegrateFleet){
            $ha=@(Get-CodexHaAccountState $a.Email)
            if($ha.Count -gt 0 -and $ha[0].state -in @("OPEN","LOCKED_OPEN")){$effectiveStatus="CIRCUIT_OPEN"}
        }
        $rows.Add([PSCustomObject]@{
            email=$a.Email;status=$effectiveStatus;health=$h.Score;favorite=[bool]$m.favorite;tag=[string]$m.tag;
            hourly=if($q -and $null -ne $q.hourlyRemaining){[int]$q.hourlyRemaining}else{$null};
            weekly=if($q -and $null -ne $q.weeklyRemaining){[int]$q.weeklyRemaining}else{$null};
            plan=$a.Plan
        })
    }
    return @($rows)
}
function Get-CodexFleetInstanceRows {
    return @((Get-CodexInstanceStore).instances|ForEach-Object{
        [PSCustomObject]@{id=$_.id;name=$_.name;account=$_.accountEmail;project=$_.projectDir;port=$_.port;clientPid=$_.clientPid;routerPid=$_.routerPid}
    })
}
function Invoke-CodexFleetPlan {
    param([object]$PolicyState)
    $input=Join-Path $env:TEMP ("hms-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-fleet-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $obj=[ordered]@{
            policy=[string]$PolicyState.policy;quota_floor=[int]$PolicyState.quotaFloor;reserve_count=[int]$PolicyState.reserveCount;
            max_per_account=[int]$PolicyState.maxPerAccount;prefer_favorite=[bool]$PolicyState.preferFavorite;
            accounts=@(Get-CodexFleetAccountRows);instances=@(Get-CodexFleetInstanceRows)
        }
        Save-Json $input $obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @((Join-Path $PSScriptRoot "HMS_Codex_FleetPolicy.py"),"--input",$input,"--output",$output) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw"FleetPolicy không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        return $j.data
    }finally{Remove-Item $input,$output -Force -ErrorAction SilentlyContinue}
}
function Set-InstanceBoundAccount {
    param([string]$InstanceId,[string]$Email)
    $acc=@(Get-CodexAccountRecords|Where-Object{$_.Email -eq $Email}| Select-Object -First 1)
    if($acc.Count -eq 0){throw"ACC không tồn tại: $Email"}
    $store=Get-CodexInstanceStore
    $inst=@($store.instances|Where-Object id -eq $InstanceId| Select-Object -First 1)
    if($inst.Count -eq 0){throw"Instance không tồn tại: $InstanceId"}
    $i=$inst[0]
    $running=$false
    if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;$running=$true}catch{}}
    if($running){throw"Instance $($i.name) đang chạy. Hãy STOP trước khi rebinding account."}

    $authDir=Join-Path $i.routerDir "auth";Ensure-Dir $authDir
    # Non-destructive policy: existing auth JSON are archived, never deleted.
    $archive=Join-Path $authDir ("archive-"+(Get-Date -Format "yyyyMMdd-HHmmss-fff")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8));Ensure-Dir $archive
    foreach($f in @(Get-ChildItem $authDir -File -Filter "codex-*.json" -ErrorAction SilentlyContinue)){Move-Item $f.FullName (Join-Path $archive $f.Name) -Force}
    Copy-Item $acc[0].File.FullName (Join-Path $authDir $acc[0].File.Name) -Force
    $i.accountEmail=$Email
    Save-CodexInstanceStore $store
    Add-CodexRouteHistory "FLEET_REBIND" ("$($i.name) → $Email") $Email
    return "Rebind PASS: $($i.name) → $Email"
}
function Apply-CodexFleetPlan {
    param([object]$Plan)
    if(-not (Test-AllManagedCodexStopped)){throw"Fleet rebalance yêu cầu tất cả managed/default Codex STOP."}
    $log=[System.Collections.Generic.List[string]]::new()
    foreach($a in @($Plan.assignments)){
        if(-not $a.to){$log.Add("$($a.instance_name): no candidate");continue}
        if([bool]$a.changed){
            try{$log.Add((Set-InstanceBoundAccount([string]$a.instance_id)([string]$a.to)))}catch{$log.Add("$($a.instance_name): FAIL "+$_.Exception.Message)}
        }else{$log.Add("$($a.instance_name): giữ $($a.to)")}
    }
    $entry=[ordered]@{time=[DateTime]::UtcNow.ToString("o");policy=$Plan.policy;reserve=@($Plan.reserve_accounts);assignments=@($Plan.assignments)}
    Add-Content $script:CodexFleetHistoryPath($entry| ConvertTo-Json-Compress-Depth8)-Encoding UTF8
    return ($log-join"`r`n")
}
function Start-CodexFleet {
    $rows=@(Get-CodexInstanceRows);$out=[System.Collections.Generic.List[string]]::new()
    foreach($r in $rows){
        if($r.Client -eq "RUNNING"){$out.Add("$($r.Name): already running");continue}
        try{$out.Add((Start-CodexInstanceSafe([string]$r.Id)))}catch{$out.Add("$($r.Name): FAIL "+$_.Exception.Message)}
    }
    return ($out -join "`r`n")
}
function Stop-CodexFleet {
    $rows=@(Get-CodexInstanceRows);$out=[System.Collections.Generic.List[string]]::new()
    foreach($r in $rows){
        if($r.Client -ne "RUNNING"){$out.Add("$($r.Name): already stopped");continue}
        try{$out.Add((Stop-CodexInstance([string]$r.Id)))}catch{$out.Add("$($r.Name): FAIL "+$_.Exception.Message)}
    }
    return ($out -join "`r`n")
}
function Get-CodexFleetSla {
    $tel=@(Get-CodexTelemetryRows);$inst=@(Get-CodexInstanceRows);$pool=Get-CodexPoolSummary
    $running=@($inst|Where-Object Client -eq "RUNNING").Count
    $routers=@($inst|Where-Object Router -eq "ONLINE").Count
    $ram=0.0;foreach($t in $tel){$ram+=[double]$t.RAM_MB}
    $score=100
    if($pool.Ready -lt 1){$score-=60}
    if($running -gt 0 -and $routers -lt $running){$score-=20*($running-$routers)}
    if(((ListenerPid ([int]$script:S.ProxyPort)) -le 0) -and (CodexInHmsMode)){$score-=30}
    $score=[Math]::Max(0,[Math]::Min(100,$score))
    [PSCustomObject]@{Score=$score;PoolReady=$pool.Ready;PoolCooldown=$pool.Cooldown;InstancesRunning=$running;RoutersOnline=$routers;RAM_MB=[Math]::Round($ram,1);State=if($score -ge 90){"HEALTHY"}elseif($score -ge 70){"DEGRADED"}else{"CRITICAL"}}
}
function Show-CodexFleetCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Fleet & Policy Engine v3.0";$w.Size=New-Object Drawing.Size(1320,760);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(15,17,20);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245)
    $title=New-Object Windows.Forms.Label;$title.Text="CODEX FLEET & POLICY ENGINE";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",18);$title.Location=New-Object Drawing.Point(18,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $policy=New-Object Windows.Forms.ComboBox;$policy.DropDownStyle="DropDownList";$policy.Location=New-Object Drawing.Point(20,58);$policy.Size=New-Object Drawing.Size(220,28)
    foreach($x in @("balanced","quota-first","weekly-first","reserve","sticky")){[void]$policy.Items.Add($x)};$w.Controls.Add($policy)
    $lq=New-Object Windows.Forms.Label;$lq.Text="Quota floor:";$lq.Location=New-Object Drawing.Point(260,62);$lq.AutoSize=$true;$w.Controls.Add($lq)
    $nq=New-Object Windows.Forms.NumericUpDown;$nq.Minimum=0;$nq.Maximum=100;$nq.Location=New-Object Drawing.Point(340,58);$nq.Size=New-Object Drawing.Size(70,26);$w.Controls.Add($nq)
    $lr=New-Object Windows.Forms.Label;$lr.Text="Reserve:";$lr.Location=New-Object Drawing.Point(430,62);$lr.AutoSize=$true;$w.Controls.Add($lr)
    $nr=New-Object Windows.Forms.NumericUpDown;$nr.Minimum=0;$nr.Maximum=20;$nr.Location=New-Object Drawing.Point(490,58);$nr.Size=New-Object Drawing.Size(60,26);$w.Controls.Add($nr)
    $bPlan=Btn "SIMULATE PLAN" 570 54 150 34;$w.Controls.Add($bPlan);$bApply=Btn "APPLY PLAN" 730 54 140 34;$bApply.BackColor=[Drawing.Color]::FromArgb(39,96,73);$w.Controls.Add($bApply)
    $bStart=Btn "START FLEET" 880 54 140 34;$w.Controls.Add($bStart);$bStop=Btn "STOP FLEET" 1030 54 140 34;$w.Controls.Add($bStop)
    $sla=New-Object Windows.Forms.Label;$sla.Location=New-Object Drawing.Point(1180,55);$sla.Size=New-Object Drawing.Size(110,45);$sla.Font=New-Object Drawing.Font("Segoe UI Semibold",12);$w.Controls.Add($sla)

    $g=New-DarkGrid 18 110 1260 430 $w
    $box=New-Object Windows.Forms.TextBox;$box.Location=New-Object Drawing.Point(18,555);$box.Size=New-Object Drawing.Size(1260,120);$box.Multiline=$true;$box.ReadOnly=$true;$box.ScrollBars="Vertical";$box.BackColor=[Drawing.Color]::FromArgb(20,23,27);$box.ForeColor=$w.ForeColor;$w.Controls.Add($box)
    $lastPlan=$null
    function LoadPolicy {
        $s=Get-CodexFleetPolicyState
        $idx=$policy.Items.IndexOf([string]$s.policy);$policy.SelectedIndex=if($idx -ge 0){$idx}else{0}
        $nq.Value=[Math]::Max($nq.Minimum,[Math]::Min($nq.Maximum,[decimal]$s.quotaFloor))
        $nr.Value=[Math]::Max($nr.Minimum,[Math]::Min($nr.Maximum,[decimal]$s.reserveCount))
    }
    function CurrentState {[PSCustomObject]@{enabled=$true;policy=[string]$policy.SelectedItem;quotaFloor=[int]$nq.Value;reserveCount=[int]$nr.Value;maxPerAccount=[int]$script:S.CodexFleetMaxInstancesPerAccount;preferFavorite=[bool]$script:S.CodexFleetPreferFavorite}}
    function RefreshFleet {
        $rows=@(Get-CodexInstanceRows);$g.DataSource=$null;$g.DataSource=$rows
        $s=Get-CodexFleetSla;$sla.Text="$($s.Score)/100`r`n$($s.State)"
    }
    $bPlan.Add_Click({try{$st=CurrentState;Save-CodexFleetPolicyState$st;$lastPlan=Invoke-CodexFleetPlan $st;$box.Text="Policy: $($lastPlan.policy)`r`nReserve: "+(@($lastPlan.reserve_accounts)-join", ")+"`r`n"+((@($lastPlan.assignments)|ForEach-Object{"$($_.instance_name): $($_.from) → $($_.to) | score=$($_.score)"})-join"`r`n")}catch{$box.Text="LỖI: "+$_.Exception.Message}})
    $bApply.Add_Click({try{if(-not $lastPlan){$lastPlan=Invoke-CodexFleetPlan(CurrentState)};$box.Text=Apply-CodexFleetPlan$lastPlan;RefreshFleet}catch{$box.Text="LỖI APPLY: "+$_.Exception.Message}})
    $bStart.Add_Click({try{$box.Text=Start-CodexFleet;RefreshFleet}catch{$box.Text=$_.Exception.Message}})
    $bStop.Add_Click({try{$box.Text=Stop-CodexFleet;RefreshFleet}catch{$box.Text=$_.Exception.Message}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=5000;$tm.Add_Tick({RefreshFleet});$tm.Start();$w.Add_Shown({LoadPolicy;RefreshFleet});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()});[void]$w.ShowDialog($form)
}
function Invoke-CodexFleetAutoRebalance {
    if($script:RuntimeAutomationBlocked){return "SAFE STARTUP: fleet auto-rebalance blocked."}
    if(-not [bool]$script:S.CodexFleetAutoRebalance){return ""}
    if(-not (Test-AllManagedCodexStopped)){return ""}
    try{
        $st=Get-CodexFleetPolicyState;$p=Invoke-CodexFleetPlan $st
        $changed=@($p.assignments|Where-Object changed).Count
        if($changed -le 0){return ""}
        return "Fleet AutoRebalance:`r`n"+(Apply-CodexFleetPlan$p)
    }catch{return "Fleet AutoRebalance FAIL: "+$_.Exception.Message}
}


# ============================================================
# CODEX OPERATIONS CENTER v4.0
# Attribution / analytics / incidents / recovery / redacted bundle
# ============================================================

function Get-CodexProxyLogFiles {
    $files=[System.Collections.Generic.List[string]]::new()
    foreach($d in @((Join-Path ([string]$script:S.ProxyDir) "logs"),([string]$script:S.ProxyDir))){
        if(-not (Test-Path $d)){continue}
        foreach($f in @(Get-ChildItem $d -File -ErrorAction SilentlyContinue | Where-Object{$_.Extension -in @(".log",".txt")}| Sort-Object LastWriteTime -Descending| Select-Object -First 5)){
            if(-not $files.Contains($f.FullName)){$files.Add($f.FullName)}
        }
    }
    return @($files)
}
function Invoke-CodexOperationsScan {
    Ensure-Dir $script:CodexOpsDir
    $logs=@(Get-CodexProxyLogFiles)
    if($logs.Count -eq 0){return [PSCustomObject]@{events=@();latest_attribution=$null;counts=@{};scanned_lines=0}}
    $accountsFile=Join-Path $env:TEMP ("hms-ops-accounts-"+[Guid]::NewGuid().ToString("N")+".json")
    $outFile=Join-Path $env:TEMP ("hms-ops-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        Save-Json $accountsFile (@(Get-CodexAccountRecords | ForEach-Object {$_.Email}))
        $args=[System.Collections.Generic.List[string]]::new()
        $args.Add((Join-Path $PSScriptRoot "HMS_Codex_OperationsAnalyzer.py"))
        foreach($l in $logs){$args.Add("--logs");$args.Add($l)}
        $args.Add("--accounts");$args.Add($accountsFile);$args.Add("--max-lines");$args.Add([string][int]$script:S.CodexAttributionWindowLines);$args.Add("--output");$args.Add($outFile)
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList $args.ToArray() -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $outFile)){throw"OperationsAnalyzer không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $outFile -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        Save-JsonAtomic $script:CodexAttributionPath $j.data
        return $j.data
    }finally{Remove-Item $accountsFile,$outFile -Force -ErrorAction SilentlyContinue}
}

function Append-CodexIncident {
    param([string]$Severity,[string]$Type,[string]$Message,[string]$Account="")
    $o=[ordered]@{time=[DateTime]::UtcNow.ToString("o");severity=$Severity;type=$Type;account=$Account;message=$Message}
    Add-Content $script:CodexIncidentPath($o| ConvertTo-Json-Compress)-Encoding UTF8
}
function Get-CodexIncidents {
    if(-not (Test-Path $script:CodexIncidentPath)){return @()}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($line in @(Get-Content $script:CodexIncidentPath-Tail([int]$script:S.CodexIncidentRetention)-Encoding UTF8 -ErrorAction SilentlyContinue)){
        try{$j=$line| ConvertFrom-Json;$rows.Add([PSCustomObject]@{Time=try{([DateTime]::Parse($j.time)).ToLocalTime().ToString("dd/MM HH:mm:ss")}catch{$j.time};Severity=$j.severity;Type=$j.type;Account=$j.account;Message=$j.message})}catch{}
    }
    return @($rows| Sort-Object Time-Descending)
}
function Update-CodexIncidentsFromScan {
    param([object]$Scan)
    foreach($e in @($Scan.events|Select-Object-Last30)){
        $sev=if($e.kind -eq "ERROR"){"ERROR"}elseif($e.kind -in @("COOLDOWN","FAILOVER")){"WARN"}else{""}
        if(-not $sev){continue}
        $finger=([string]$e.kind+"|"+[string]$e.account+"|"+[string]$e.message)
        $recent=@(Get-CodexIncidents| Select-Object -First 40)
        if(@($recent|Where-Object{$_.Type -eq $e.kind -and $_.Account -eq $e.account -and $_.Message -eq $e.message}).Count -eq 0){
            Append-CodexIncident$sev([string]$e.kind)([string]$e.message)([string]$e.account)
        }
    }
}

function Snapshot-CodexQuotaHistory {
    if(-not [bool]$script:S.CodexQuotaHistoryEnabled){return}
    $now=[DateTime]::UtcNow
    $last=$null
    if(Test-Path $script:CodexQuotaHistoryPath){
        try{$tail=@(Get-Content $script:CodexQuotaHistoryPath -Tail 1 -Encoding UTF8);if($tail.Count){$j=$tail[0]| ConvertFrom-Json;$last=[DateTime]::Parse($j.time)}}catch{}
    }
    if($last -and ($now-$last).TotalMinutes -lt [int]$script:S.CodexQuotaHistoryMinIntervalMinutes){return}
    $rows=@(Get-CodexAccountRecords|ForEach-Object{
        $q=Get-CodexQuotaForEmail $_.Email
        [ordered]@{
            email=$_.Email;status=$_.Status
            hourly=if($q){$q.hourlyRemaining}else{$null};weekly=if($q){$q.weeklyRemaining}else{$null}
            hourly_reset=if($q){$q.hourlyReset}else{$null};weekly_reset=if($q){$q.weeklyReset}else{$null}
            hourly_window_minutes=if($q){$q.hourlyWindowMinutes}else{$null};weekly_window_minutes=if($q){$q.weeklyWindowMinutes}else{$null}
        }
    })
    Add-Content $script:CodexQuotaHistoryPath(([ordered]@{time=$now.ToString("o");accounts=$rows})| ConvertTo-Json-Compress-Depth6)-Encoding UTF8
}
function Get-CodexQuotaConsumptionRows {
    if(-not (Test-Path $script:CodexQuotaHistoryPath)){return @()}
    $hist=[System.Collections.Generic.List[object]]::new()
    foreach($line in @(Get-Content $script:CodexQuotaHistoryPath -Tail 200 -Encoding UTF8 -ErrorAction SilentlyContinue)){try{$hist.Add(($line| ConvertFrom-Json))}catch{}}
    if($hist.Count -lt 2){return @()}
    $first=$hist[0];$last=$hist[$hist.Count-1]
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($a in @($last.accounts)){
        $prev=@($first.accounts|Where-Object email -eq $a.email| Select-Object -First 1)
        $hDelta=$null;$wDelta=$null
        if($prev.Count -and $null -ne $prev[0].hourly -and $null -ne $a.hourly){$hDelta=[int]$prev[0].hourly-[int]$a.hourly}
        if($prev.Count -and $null -ne $prev[0].weekly -and $null -ne $a.weekly){$wDelta=[int]$prev[0].weekly-[int]$a.weekly}
        $rows.Add([PSCustomObject]@{Account=$a.email;Status=$a.status;HourlyNow=$a.hourly;HourlyConsumed=$hDelta;WeeklyNow=$a.weekly;WeeklyConsumed=$wDelta})
    }
    return @($rows)
}

function Get-CodexRecoveryPolicyState {
    $j=Load-JsonObjectSafe$script:CodexRecoveryPolicyPath
    if(-not $j){return [PSCustomObject]@{mode=[string]$script:S.CodexRecoveryPolicy;lastActionUtc=$null}}
    return $j
}
function Save-CodexRecoveryPolicyState([object]$State){Save-JsonAtomic $script:CodexRecoveryPolicyPath$State}
function Invoke-CodexRecoveryPolicy {
    if($script:RuntimeAutomationBlocked){return "SAFE STARTUP: recovery policy mutation blocked."}
    param([object]$Scan)
    $state=Get-CodexRecoveryPolicyState; $mode=[string]$state.mode
    if($mode -eq "observe"){return ""}
    if($state.lastActionUtc){
        try{if(([DateTime]::UtcNow-[DateTime]::Parse($state.lastActionUtc)).TotalSeconds -lt [int]$script:S.CodexRecoveryCooldownSec){return ""}}catch{}
    }
    $actions=[System.Collections.Generic.List[string]]::new()
    # Safe policy: only recover routers HMS owns; never kill foreign PID and never switch/rebind running clients.
    if((CodexInHmsMode) -and ((ListenerPid ([int]$script:S.ProxyPort)) -le 0)){
        try{$actions.Add((Start-Router))}catch{$actions.Add("Main router recovery FAIL: "+$_.Exception.Message)}
    }
    $iw=Invoke-CodexInstanceWatchdog;if($iw){$actions.Add($iw)}
    if($mode -eq "protect"){
        $sla=Get-CodexFleetSla
        if($sla.Score -lt 50){$actions.Add("Protect mode: SLA CRITICAL — auto fleet rebalance bị giữ vì đang runtime; cần operator review.")}
    }
    if($actions.Count){
        $state.lastActionUtc=[DateTime]::UtcNow.ToString("o");Save-CodexRecoveryPolicyState $state
        Append-CodexIncident"INFO""RECOVERY"($actions-join" | ")""
        return "Recovery Policy: "+($actions-join" | ")
    }
    return ""
}

function Redact-HmsText {
    param([string]$Text)
    return (Redact-HmsSecurityText $Text)
}
function Export-CodexDiagnosticBundle {
    Ensure-Dir $script:CodexDiagnosticBundleDir
    $stamp=Get-Date -Format "yyyyMMdd-HHmmss";$dir=Join-Path $script:CodexDiagnosticBundleDir ("diag-"+$stamp);Ensure-Dir $dir
    Set-Content -Path (Join-Path $dir "diagnostics.txt") -Value (Redact-HmsText (Get-CodexDiagnosticsText)) -Encoding UTF8
    try{$scan=Invoke-CodexOperationsScan;Save-Json (Join-Path $dir "operations.json") $scan}catch{}
    try{Save-Json (Join-Path $dir "telemetry.json") @(Get-CodexTelemetryRows)}catch{}
    try{Save-Json (Join-Path $dir "fleet-sla.json") (Get-CodexFleetSla)}catch{}
    try{Save-Json (Join-Path $dir "quota-consumption.json") @(Get-CodexQuotaConsumptionRows)}catch{}
    try{Save-Json (Join-Path $dir "incidents.json") @(Get-CodexIncidents)}catch{}
    $raw=Get-CodexRecentProxyLog-Lines([int]$script:S.CodexRedactedBundleMaxLogLines)
    Set-Content -Path (Join-Path $dir "proxy-log-redacted.txt") -Value (Redact-HmsText $raw) -Encoding UTF8
    Save-Json (Join-Path $dir "manifest.json") ([ordered]@{createdUtc=[DateTime]::UtcNow.ToString("o");version=$script:Version;containsRawTokens=$false})
    $zip=$dir+".zip";Compress-Archive -Path (Join-Path $dir "*") -DestinationPath $zip -Force
    return $zip
}

function Show-CodexOperationsCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Operations Center v4.0";$w.Size=New-Object Drawing.Size(1400,820);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(14,16,19);$w.ForeColor=[Drawing.Color]::FromArgb(238,241,245)
    $title=New-Object Windows.Forms.Label;$title.Text="CODEX OPERATIONS CENTER";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(18,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $attr=New-Object Windows.Forms.Label;$attr.Location=New-Object Drawing.Point(20,55);$attr.Size=New-Object Drawing.Size(920,50);$attr.Font=New-Object Drawing.Font("Segoe UI Semibold",12);$w.Controls.Add($attr)
    $sla=New-Object Windows.Forms.Label;$sla.Location=New-Object Drawing.Point(960,20);$sla.Size=New-Object Drawing.Size(180,80);$sla.Font=New-Object Drawing.Font("Segoe UI Semibold",18);$w.Controls.Add($sla)
    $policy=New-Object Windows.Forms.ComboBox;$policy.DropDownStyle="DropDownList";$policy.Location=New-Object Drawing.Point(1160,48);$policy.Size=New-Object Drawing.Size(180,28);foreach($x in @("observe","safe","protect")){[void]$policy.Items.Add($x)};$w.Controls.Add($policy)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,110);$tabs.Size=New-Object Drawing.Size(1340,620);$w.Controls.Add($tabs)
    foreach($name in @("Live Attribution","Incidents","Quota Analytics","Recovery","Diagnostics Bundle")){$p=New-Object Windows.Forms.TabPage;$p.Text=$name;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)}
    $pLive=$tabs.TabPages[0];$pInc=$tabs.TabPages[1];$pQuota=$tabs.TabPages[2];$pRec=$tabs.TabPages[3];$pDiag=$tabs.TabPages[4]
    $gLive=New-DarkGrid 15 50 1270 470 $pLive;$bScan=Btn "SCAN NOW" 15 10 130 32;$pLive.Controls.Add($bScan)
    $gInc=New-DarkGrid 15 50 1270 470 $pInc;$bInc=Btn "REFRESH" 15 10 120 32;$pInc.Controls.Add($bInc)
    $gQuota=New-DarkGrid 15 50 1270 470 $pQuota;$bSnap=Btn "SNAPSHOT QUOTA" 15 10 160 32;$pQuota.Controls.Add($bSnap)
    $recBox=New-Object Windows.Forms.TextBox;$recBox.Location=New-Object Drawing.Point(15,65);$recBox.Size=New-Object Drawing.Size(1270,430);$recBox.Multiline=$true;$recBox.ReadOnly=$true;$recBox.BackColor=[Drawing.Color]::FromArgb(20,23,27);$recBox.ForeColor=$w.ForeColor;$pRec.Controls.Add($recBox)
    $bRunRec=Btn "RUN RECOVERY CHECK" 15 15 190 34;$pRec.Controls.Add($bRunRec)
    $diagBox=New-Object Windows.Forms.TextBox;$diagBox.Location=New-Object Drawing.Point(15,80);$diagBox.Size=New-Object Drawing.Size(1270,400);$diagBox.Multiline=$true;$diagBox.ReadOnly=$true;$diagBox.BackColor=[Drawing.Color]::FromArgb(20,23,27);$diagBox.ForeColor=$w.ForeColor;$pDiag.Controls.Add($diagBox)
    $bBundle=Btn "EXPORT REDACTED BUNDLE" 15 20 220 38;$pDiag.Controls.Add($bBundle)

    function LoadPolicy {$st=Get-CodexRecoveryPolicyState;$ix=$policy.Items.IndexOf([string]$st.mode);$policy.SelectedIndex=if($ix -ge 0){$ix}else{1}}
    function Refresh-Ops {
        try{
            $scan=Invoke-CodexOperationsScan;Update-CodexIncidentsFromScan$scan;Snapshot-CodexQuotaHistory
            $gLive.DataSource=$null;$gLive.DataSource=@($scan.events|Select-Object-Last100)
            $a=$scan.latest_attribution
            $attr.Text=if($a){"ACTIVE ROUTE: $($a.account)  [$($a.confidence)]`r`n$($a.source)"}else{"ACTIVE ROUTE: UNATTRIBUTED`r`nChưa đủ evidence trong log/runtime."}
        }catch{$attr.Text="Operations scan error: "+$_.Exception.Message}
        $gInc.DataSource=$null;$gInc.DataSource=@(Get-CodexIncidents)
        $gQuota.DataSource=$null;$gQuota.DataSource=@(Get-CodexQuotaConsumptionRows)
        $s=Get-CodexFleetSla;$sla.Text="$($s.Score)/100`r`n$($s.State)"
    }
    $policy.Add_SelectedIndexChanged({if($policy.SelectedIndex -ge 0){$st=Get-CodexRecoveryPolicyState;$st.mode=[string]$policy.SelectedItem;Save-CodexRecoveryPolicyState $st}})
    $bScan.Add_Click({Refresh-Ops});$bInc.Add_Click({Refresh-Ops});$bSnap.Add_Click({Snapshot-CodexQuotaHistory;Refresh-Ops})
    $bRunRec.Add_Click({try{$scan=Invoke-CodexOperationsScan;$recBox.Text=Invoke-CodexRecoveryPolicy$scan;if(-not $recBox.Text){$recBox.Text="Không cần recovery action."};Refresh-Ops}catch{$recBox.Text=$_.Exception.Message}})
    $bBundle.Add_Click({try{$p=Export-CodexDiagnosticBundle;$diagBox.Text="Diagnostic bundle PASS:`r`n$p`r`n`r`nBundle đã redacted token patterns."}catch{$diagBox.Text=$_.Exception.Message}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=[Math]::Max(3000,[int]$script:S.CodexOpsScanIntervalSec*1000);$tm.Add_Tick({Refresh-Ops});$tm.Start()
    $w.Add_Shown({LoadPolicy;Refresh-Ops});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()});[void]$w.ShowDialog($form)
}


# ============================================================
# CODEX AUTOPILOT v5.0
# Predictive quota / per-account metrics / reserve activation
# ============================================================
function Get-CodexQuotaHistoryObjects {
    if(-not (Test-Path $script:CodexQuotaHistoryPath)){return @()}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($line in @(Get-Content $script:CodexQuotaHistoryPath -Tail 500 -Encoding UTF8 -ErrorAction SilentlyContinue)){
        try{$rows.Add(($line| ConvertFrom-Json))}catch{}
    }
    return @($rows)
}
function Invoke-CodexPredictiveEngine {
    $scan=Invoke-CodexOperationsScan
    $input=Join-Path $env:TEMP ("hms-predict-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-predict-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $obj=[ordered]@{
            quota_history=@(Get-CodexQuotaHistoryObjects);events=@($scan.events);
            forecast_hours=[int]$script:S.CodexQuotaForecastHours;
            quota_trigger=[int]$script:S.CodexQuotaReserveTriggerPercent;
            error_trigger=[int]$script:S.CodexErrorRateCriticalPercent;
            min_samples=[int]$script:S.CodexMinimumSamplesForAutomation
        }
        Save-Json $input$obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList@((Join-Path $PSScriptRoot "HMS_Codex_PredictiveEngine.py"),"--input",$input,"--output",$output) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw"PredictiveEngine không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        Save-JsonAtomic $script:CodexQuotaForecastPath$j.data
        return $j.data
    }finally{Remove-Item $input,$output -Force -ErrorAction SilentlyContinue}
}
function Get-CodexReserveCandidates {
    $st=Get-CodexFleetPolicyState
    $plan=Invoke-CodexFleetPlan $st
    return @($plan.reserve_accounts)
}
function Invoke-CodexReserveActivation {
    param([string]$ExhaustedAccount,[switch]$Apply)
    $reserve=@(Get-CodexReserveCandidates|Where-Object{$_ -and $_ -ne $ExhaustedAccount}| Select-Object -First 1)
    if($reserve.Count -eq 0){return "Không có reserve account khả dụng."}
    $target=[string]$reserve[0]
    $affected=@((Get-CodexInstanceStore).instances|Where-Object accountEmail -eq $ExhaustedAccount)
    if($affected.Count -eq 0){return "Không có instance nào bind với $ExhaustedAccount."}
    $lines=[System.Collections.Generic.List[string]]::new()
    foreach($i in $affected){
        $running=$false;if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;$running=$true}catch{}}
        if($running){$lines.Add("$($i.name): đang chạy → chỉ RECOMMEND, không rebind.");continue}
        if($Apply){
            try{$lines.Add((Set-InstanceBoundAccount([string]$i.id)$target))}catch{$lines.Add("$($i.name): FAIL "+$_.Exception.Message)}
        }else{$lines.Add("$($i.name): đề xuất $ExhaustedAccount → $target")}
    }
    $ev=[ordered]@{time=[DateTime]::UtcNow.ToString("o");from=$ExhaustedAccount;to=$target;apply=[bool]$Apply;instances=@($affected|ForEach-Object{$_.name})}
    Add-Content $script:CodexReserveActivationPath($ev| ConvertTo-Json-Compress-Depth5)-Encoding UTF8
    return ($lines-join"`r`n")
}
function Get-CodexAutopilotState {
    $j=Load-JsonObjectSafe$script:CodexAutopilotStatePath
    if(-not $j){return [PSCustomObject]@{enabled=[bool]$script:S.CodexAutopilotEnabled;mode=[string]$script:S.CodexAutopilotMode;lastActionUtc=$null}}
    return $j
}
function Save-CodexAutopilotState([object]$State){Save-JsonAtomic $script:CodexAutopilotStatePath$State}
function Invoke-CodexAutopilotCycle {
    if($script:RuntimeAutomationBlocked){return "SAFE STARTUP: autopilot mutation blocked."}
    $state=Get-CodexAutopilotState
    if(-not [bool]$state.enabled){return ""}
    if($state.lastActionUtc){
        try{if(([DateTime]::UtcNow-[DateTime]::Parse($state.lastActionUtc)).TotalSeconds -lt [int]$script:S.CodexAutopilotCooldownSec){return ""}}catch{}
    }
    $p=Invoke-CodexPredictiveEngine
    $notes=[System.Collections.Generic.List[string]]::new()
    foreach($r in @($p.recommendations)){
        if([string]$state.mode -eq "recommend"){
            $notes.Add((Invoke-CodexReserveActivation([string]$r.account)))
        }elseif([string]$state.mode -eq "safe-auto"){
            # Auto-apply remains bounded: only STOPPED instances can be rebound.
            $notes.Add((Invoke-CodexReserveActivation([string]$r.account)-Apply))
        }
    }
    if($notes.Count){
        $state.lastActionUtc=[DateTime]::UtcNow.ToString("o");Save-CodexAutopilotState$state
        Add-Content $script:CodexAutopilotHistoryPath(([ordered]@{time=$state.lastActionUtc;mode=$state.mode;notes=@($notes)})| ConvertTo-Json-Compress-Depth5)-Encoding UTF8
        return "Autopilot: "+($notes-join" | ")
    }
    return ""
}
function Show-CodexAutopilotCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Codex Autopilot v5.0";$w.Size=New-Object Drawing.Size(1420,830);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="CODEX AUTOPILOT";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",20);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $mode=New-Object Windows.Forms.ComboBox;$mode.DropDownStyle="DropDownList";$mode.Location=New-Object Drawing.Point(230,22);$mode.Size=New-Object Drawing.Size(170,28);foreach($x in @("recommend","safe-auto")){[void]$mode.Items.Add($x)};$w.Controls.Add($mode)
    $enabled=New-Object Windows.Forms.CheckBox;$enabled.Text="BẬT AUTOPILOT";$enabled.Location=New-Object Drawing.Point(420,22);$enabled.Size=New-Object Drawing.Size(160,28);$enabled.ForeColor=$w.ForeColor;$w.Controls.Add($enabled)
    $bRun=Btn "RUN PREDICTIVE SCAN" 600 18 190 36;$w.Controls.Add($bRun)
    $bOps=Btn "OPERATIONS CENTER" 805 18 170 36;$w.Controls.Add($bOps)
    $bFleet=Btn "FLEET CENTER" 990 18 145 36;$w.Controls.Add($bFleet)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,75);$tabs.Size=New-Object Drawing.Size(1360,650);$w.Controls.Add($tabs)
    foreach($n in @("Quota Forecast","Account Metrics","Recommendations","Reserve Pool","Safety")){$p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)}
    $gF=New-DarkGrid 15 20 1290 520 $tabs.TabPages[0]
    $gM=New-DarkGrid 15 20 1290 520 $tabs.TabPages[1]
    $gR=New-DarkGrid 15 20 1290 520 $tabs.TabPages[2]
    $gP=New-DarkGrid 15 20 1290 520 $tabs.TabPages[3]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1290,520);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor;$tabs.TabPages[4].Controls.Add($safe)
    $last=$null
    function LoadState{
        $s=Get-CodexAutopilotState;$enabled.Checked=[bool]$s.enabled;$ix=$mode.Items.IndexOf([string]$s.mode);$mode.SelectedIndex=if($ix -ge 0){$ix}else{0}
        $safe.Text="SAFE-AUTO GUARDRAILS`r`n`r`n• Không kill foreign/Cockpit PID.`r`n• Không rebind instance đang chạy.`r`n• Không xóa auth; auth cũ archive.`r`n• Automation cần đủ sample trước khi dùng error-rate.`r`n• Forecast không được coi là quota thật; quota hiện tại vẫn lấy từ cache/runtime.`r`n• Có thể tắt Autopilot và tiếp tục dùng Cockpit."
    }
    function SaveState{
        $s=Get-CodexAutopilotState;$s.enabled=$enabled.Checked;$s.mode=[string]$mode.SelectedItem;Save-CodexAutopilotState$s
    }
    function RefreshPred{
        try{
            Snapshot-CodexQuotaHistory;$last=Invoke-CodexPredictiveEngine
            $gF.DataSource=$null;$gF.DataSource=@($last.forecast)
            $gM.DataSource=$null;$gM.DataSource=@($last.metrics)
            $gR.DataSource=$null;$gR.DataSource=@($last.recommendations)
            $pool=@(Get-CodexReserveCandidates|ForEach-Object{[PSCustomObject]@{ReserveAccount=$_}})
            $gP.DataSource=$null;$gP.DataSource=$pool
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,"Predictive Engine")|Out-Null}
    }
    $enabled.Add_CheckedChanged({SaveState});$mode.Add_SelectedIndexChanged({if($mode.SelectedIndex -ge 0){SaveState}})
    $bRun.Add_Click({RefreshPred});$bOps.Add_Click({Show-CodexOperationsCenter});$bFleet.Add_Click({Show-CodexFleetCenter})
    $w.Add_Shown({LoadState;RefreshPred});[void]$w.ShowDialog($form)
}


# ============================================================
# CODEX HIGH AVAILABILITY v6.0
# Persistent metrics / circuit breaker / anti-flapping / correlation
# ============================================================
function Invoke-CodexCorrelationEngine {
    param([object]$Scan)
    $input = Join-Path $env:TEMP ("hms-corr-" + [Guid]::NewGuid().ToString("N") + ".json")
    $output = Join-Path $env:TEMP ("hms-corr-out-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        Save-Json $input ([ordered]@{events=@($Scan.events)})
        $p = Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            (Join-Path $PSScriptRoot "HMS_Codex_CorrelationEngine.py"),
            "--input",$input,"--output",$output
        ) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "CorrelationEngine không tạo output. exit=$($p.ExitCode)"}
        $j = Get-Content $output -Raw -Encoding UTF8 | ConvertFrom-Json
        if(-not $j.ok){throw [string]$j.error}
        Save-JsonAtomic $script:CodexCorrelationPath $j.data
        return $j.data
    } finally {
        Remove-Item $input,$output -Force -ErrorAction SilentlyContinue
    }
}
function Invoke-CodexHaEngine {
    param(
        [ValidateSet("ingest","evaluate","snapshot","reset")][string]$Mode,
        [object]$Scan=$null,
        [string]$Account=""
    )
    $accountsFile = Join-Path $env:TEMP ("hms-ha-accounts-" + [Guid]::NewGuid().ToString("N") + ".json")
    $eventsFile = Join-Path $env:TEMP ("hms-ha-events-" + [Guid]::NewGuid().ToString("N") + ".json")
    $output = Join-Path $env:TEMP ("hms-ha-out-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        Save-Json $accountsFile @(Get-CodexAccountRecords | ForEach-Object {$_.Email})
        $args = [System.Collections.Generic.List[string]]::new()
        $args.Add((Join-Path $PSScriptRoot "HMS_Codex_HAEngine.py"))
        $args.Add("--db");$args.Add($script:CodexHaDbPath)
        $args.Add("--mode");$args.Add($Mode)
        $args.Add("--accounts");$args.Add($accountsFile)
        $args.Add("--window-min");$args.Add([string][int]$script:S.CodexHaWindowMinutes)
        $args.Add("--error-rate");$args.Add([string][int]$script:S.CodexCircuitErrorRatePercent)
        $args.Add("--min-samples");$args.Add([string][int]$script:S.CodexCircuitMinSamples)
        $args.Add("--open-seconds");$args.Add([string][int]$script:S.CodexCircuitOpenSeconds)
        $args.Add("--max-transitions");$args.Add([string][int]$script:S.CodexCircuitMaxTransitionsPerHour)
        $args.Add("--half-success");$args.Add([string][int]$script:S.CodexCircuitHalfOpenSuccessSamples)
        if($Mode -eq "ingest"){
            if(-not $Scan){$Scan=Invoke-CodexOperationsScan}
            $corr=Invoke-CodexCorrelationEngine $Scan
            $events=@()
            foreach($e in @($Scan.events)){
                $events += [PSCustomObject]@{
                    source=$e.source;kind=$e.kind;account=$e.account;confidence=$e.confidence;
                    request_id=$null;status_code=$null;latency_ms=$null;message=$e.message
                }
            }
            foreach($c in @($corr.correlated)){
                foreach($e in @($c.events)){
                    $events += [PSCustomObject]@{
                        source=$e.source;kind=$e.kind;account=$e.account;confidence=$e.confidence;
                        request_id=$c.correlation_id;status_code=$e.status_code;latency_ms=$e.latency_ms;message=$e.message
                    }
                }
            }
            Save-Json $eventsFile $events
            $args.Add("--events");$args.Add($eventsFile)
        }
        if($Mode -eq "reset"){
            $args.Add("--account");$args.Add($Account)
        }
        $args.Add("--output");$args.Add($output)
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList $args.ToArray() -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "HAEngine không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8 | ConvertFrom-Json
        if(-not $j.ok){throw [string]$j.error}
        if($Mode -in @("evaluate","snapshot")){Save-JsonAtomic $script:CodexHaSnapshotPath $j.data}
        return $j.data
    } finally {
        Remove-Item $accountsFile,$eventsFile,$output -Force -ErrorAction SilentlyContinue
    }
}
function Get-CodexHaSnapshot {
    $j=Load-JsonObjectSafe $script:CodexHaSnapshotPath
    if(-not $j){return [PSCustomObject]@{accounts=@()}}
    return $j
}
function Get-CodexHaAccountState {
    param([string]$Email)
    $s=Get-CodexHaSnapshot
    return @($s.accounts | Where-Object {$_.account -eq $Email} | Select-Object -First 1)
}
function Invoke-CodexHaCycle {
    if(-not [bool]$script:S.CodexHaEnabled){return ""}
    try {
        $scan=Invoke-CodexOperationsScan
        $null=Invoke-CodexHaEngine -Mode "ingest" -Scan $scan
        $eval=Invoke-CodexHaEngine -Mode "evaluate"
        $open=@($eval.accounts|Where-Object {$_.state -in @("OPEN","LOCKED_OPEN")})
        if($open.Count -gt 0){
            return "HA: circuit open → " + (($open|ForEach-Object{"$($_.account) [$($_.state)]"}) -join ", ")
        }
        return ""
    } catch {
        return "HA cycle WARN: " + $_.Exception.Message
    }
}
function Show-CodexHaCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex High Availability v6.0"
    $w.Size=New-Object Drawing.Size(1420,820)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18)
    $w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label
    $title.Text="CODEX HIGH AVAILABILITY"
    $title.Font=New-Object Drawing.Font("Segoe UI Semibold",20)
    $title.Location=New-Object Drawing.Point(20,15)
    $title.AutoSize=$true
    $w.Controls.Add($title)

    $bIngest=Btn "INGEST NOW" 20 58 130 34;$w.Controls.Add($bIngest)
    $bEval=Btn "EVALUATE CIRCUITS" 160 58 170 34;$w.Controls.Add($bEval)
    $bReset=Btn "RESET CIRCUIT" 340 58 150 34;$w.Controls.Add($bReset)
    $bOps=Btn "OPERATIONS" 500 58 130 34;$w.Controls.Add($bOps)
    $bAuto=Btn "AUTOPILOT" 640 58 130 34;$w.Controls.Add($bAuto)
    $bFleet=Btn "FLEET" 780 58 110 34;$w.Controls.Add($bFleet)

    $tabs=New-Object Windows.Forms.TabControl
    $tabs.Location=New-Object Drawing.Point(18,110)
    $tabs.Size=New-Object Drawing.Size(1360,620)
    $w.Controls.Add($tabs)
    foreach($n in @("Circuit Breakers","Request Correlation","Persistent Metrics","Safety")){
        $p=New-Object Windows.Forms.TabPage
        $p.Text=$n
        $p.BackColor=[Drawing.Color]::FromArgb(18,21,25)
        $p.ForeColor=$w.ForeColor
        $tabs.TabPages.Add($p)
    }
    $gCircuit=New-DarkGrid 15 20 1290 520 $tabs.TabPages[0]
    $gCorr=New-DarkGrid 15 20 1290 520 $tabs.TabPages[1]
    $gMetrics=New-DarkGrid 15 20 1290 520 $tabs.TabPages[2]
    $safe=New-Object Windows.Forms.TextBox
    $safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1290,520)
    $safe.Multiline=$true;$safe.ReadOnly=$true
    $safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="HA GUARDRAILS`r`n`r`n• Circuit breaker không xóa/disable auth file của shared router.`r`n• OPEN/LOCKED_OPEN chủ yếu dùng cho quan sát và Fleet planner.`r`n• Shared router vẫn để CLIProxyAPI native failover xử lý.`r`n• Anti-flapping có thể đưa account sang LOCKED_OPEN.`r`n• Manual RESET chỉ reset circuit metadata.`r`n• Không kill Cockpit/foreign listener."
    $tabs.TabPages[4].Controls.Add($safe)

    function Refresh-Ha {
        try {
            $snap=Invoke-CodexHaEngine -Mode "snapshot"
            $gCircuit.DataSource=$null;$gCircuit.DataSource=@($snap.accounts)
            $gMetrics.DataSource=$null;$gMetrics.DataSource=@($snap.accounts|ForEach-Object{
                [PSCustomObject]@{
                    Account=$_.account;Samples=$_.samples;Requests=$_.REQUEST;Errors=$_.ERROR;
                    ErrorRate=$_.error_rate_pct;Cooldowns=$_.COOLDOWN;Failovers=$_.FAILOVER;
                    P50_ms=$_.latency_p50_ms;P95_ms=$_.latency_p95_ms
                }
            })
            $corr=Load-JsonObjectSafe $script:CodexCorrelationPath
            $gCorr.DataSource=$null
            if($corr){$gCorr.DataSource=@($corr.correlated)}
        } catch {
            [Windows.Forms.MessageBox]::Show($_.Exception.Message,"HA Center")|Out-Null
        }
    }
    $bIngest.Add_Click({
        try{$scan=Invoke-CodexOperationsScan;$null=Invoke-CodexHaEngine -Mode "ingest" -Scan $scan;Refresh-Ha}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bEval.Add_Click({
        try{$null=Invoke-CodexHaEngine -Mode "evaluate";Refresh-Ha}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bReset.Add_Click({
        try{
            if($gCircuit.SelectedRows.Count -lt 1){throw "Chọn một account."}
            $email=[string]$gCircuit.SelectedRows[0].Cells["account"].Value
            $null=Invoke-CodexHaEngine -Mode "reset" -Account $email
            $null=Invoke-CodexHaEngine -Mode "evaluate"
            Refresh-Ha
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bOps.Add_Click({Show-CodexOperationsCenter})
    $bAuto.Add_Click({Show-CodexAutopilotCenter})
    $bFleet.Add_Click({Show-CodexFleetCenter})
    $tm=New-Object Windows.Forms.Timer
    $tm.Interval=10000
    $tm.Add_Tick({Refresh-Ha})
    $tm.Start()
    $w.Add_Shown({Refresh-Ha})
    $w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# ============================================================
# V25.12 LIVE FAILOVER CERTIFICATION
# Non-destructive credential availability probe with automatic restore.
# ============================================================

function Get-HmsFailoverEvidenceRoot {
    $p=Join-Path $script:DataDir "live-failover-v25_23_1"
    Ensure-Dir $p
    return $p
}
function Test-HmsProxyRequestLogEnabled {
    if(-not (Test-Path $script:ProxyCfg)){return $false}
    try{
        $t=[IO.File]::ReadAllText($script:ProxyCfg)
        return $t -match '(?m)^request-log:\s*true\s*(?:#.*)?$'
    }catch{return $false}
}
function Get-HmsAuthDisabledSnapshot([IO.FileInfo]$File){
    if(-not $File -or -not (Test-Path $File.FullName)){throw "Auth file không tồn tại."}
    $raw=[IO.File]::ReadAllText($File.FullName)
    $j=$raw | ConvertFrom-Json
    $prop=$j.PSObject.Properties['disabled']
    return [PSCustomObject]@{
        Raw=$raw
        HadProperty=($null -ne $prop)
        Disabled=if($prop){[bool]$prop.Value}else{$false}
        Sha256=((Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant())
        Email=(Short-Value (Get-DeepValue $j @('email','account_email','user_email')) 100)
    }
}
function Set-HmsAuthDisabledProperty([IO.FileInfo]$File,[bool]$Disabled,[bool]$RemoveWhenFalse=$false){
    if(-not $File -or -not (Test-Path $File.FullName)){throw "Auth file không tồn tại."}
    # Re-read current bytes for every mutation so token refresh fields written by
    # CLIProxyAPI are preserved. Only the disabled field is changed.
    $j=([IO.File]::ReadAllText($File.FullName) | ConvertFrom-Json)
    if($RemoveWhenFalse){
        $j.PSObject.Properties.Remove('disabled')
    }else{
        Add-Member -InputObject $j -NotePropertyName disabled -NotePropertyValue $Disabled -Force
    }
    Save-JsonAtomic $File.FullName $j
}
function Find-HmsFailoverRequestEvidence([string]$Marker,[datetime]$Since){
    $roots=[System.Collections.Generic.List[string]]::new()
    foreach($candidate in @(
        (Join-Path ([string]$script:S.ProxyDir) 'logs'),
        (Join-Path $script:AuthDir 'logs')
    )){
        if($candidate -and (Test-Path $candidate) -and -not $roots.Contains($candidate)){$roots.Add($candidate)}
    }
    foreach($root in $roots){
        $files=@(Get-ChildItem -LiteralPath $root -File -Recurse -Filter '*.log' -ErrorAction SilentlyContinue |
            Where-Object {$_.LastWriteTime -ge $Since.AddSeconds(-2)} |
            Sort-Object LastWriteTime -Descending | Select-Object -First 80)
        foreach($f in $files){
            try{
                $text=[IO.File]::ReadAllText($f.FullName)
                if($text -notlike ('*'+$Marker+'*')){continue}
                $m=[regex]::Match($text,'(?m)^Auth:\s+provider=codex,\s+auth_id=([^,\r\n]+),\s+label=([^,\r\n]+),\s+type=oauth\s*$')
                if($m.Success){
                    return [PSCustomObject]@{Found=$true;Path=$f.FullName;AuthId=$m.Groups[1].Value.Trim();Label=$m.Groups[2].Value.Trim()}
                }
                return [PSCustomObject]@{Found=$true;Path=$f.FullName;AuthId='';Label=''}
            }catch{}
        }
    }
    return [PSCustomObject]@{Found=$false;Path='';AuthId='';Label=''}
}
function Invoke-HmsLiveFailoverProbe([IO.FileInfo]$TargetFile){
    $runId=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    $evRoot=Join-Path (Get-HmsFailoverEvidenceRoot) $runId
    Ensure-Dir $evRoot
    $resultPath=Join-Path $evRoot 'result.json'
    $started=Get-Date
    $snap=$null
    $restoreOk=$false
    $probeHttp=0
    $probeError=''
    $selected=$null
    $marker='HMS_FAILOVER_PROBE_'+[Guid]::NewGuid().ToString('N')
    $verdict='FAIL'
    $detail=''

    try{
        if(-not (CodexInHmsMode)){throw 'Codex chưa ở HMS API mode.'}
        $routerPid=ListenerPid ([int]$script:S.ProxyPort)
        if($routerPid -le 0 -or -not (IsOurProxy $routerPid)){throw 'HMS Router chưa ONLINE hoặc port đang do process khác sở hữu.'}
        if(-not (Test-HmsProxyRequestLogEnabled)){throw 'Request Log chưa bật. Hãy bật Request Log trong CLIProxy Management Center trước khi chạy test.'}
        $records=@(Get-CodexAccountRecords | Where-Object {$_.File -and $_.Status -ne 'LỖI FILE'})
        if($records.Count -lt 2){throw 'Cần tối thiểu 2 Codex OAuth account để test failover.'}
        if(-not $TargetFile){throw 'Chưa chọn account cần tạm disable.'}
        $snap=Get-HmsAuthDisabledSnapshot $TargetFile
        if($snap.Disabled){throw 'Account được chọn đã disabled từ trước; không dùng nó cho test.'}

        # One bounded mutation: mark exactly one selected auth unavailable.
        Set-HmsAuthDisabledProperty $TargetFile $true $false
        Start-Sleep -Milliseconds 1400

        # Re-read to prove the on-disk disable persisted before the live request.
        $check=Get-HmsAuthDisabledSnapshot $TargetFile
        if(-not $check.Disabled){throw 'CLIProxy/auth watcher đã ghi đè disabled=true; dừng test để tránh kết luận sai.'}

        $sid=[Guid]::NewGuid().ToString()
        $headers=@{
            Authorization=('Bearer '+[string]$script:S.LocalApiKey)
            'Session-Id'=$sid
            'Thread-Id'=$sid
            'X-Client-Request-Id'=$sid
            Originator='HMS-Failover-Test'
        }
        $body=ConvertTo-Json -Compress -Depth 6 -InputObject ([ordered]@{
            model='gpt-5.4-mini'
            input=($marker+' Reply exactly OK.')
            stream=$false
        })
        try{
            $r=Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:'+([int]$script:S.ProxyPort)+'/v1/responses') `
                -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 45
            $probeHttp=[int]$r.StatusCode
        }catch{
            try{$probeHttp=[int]$_.Exception.Response.StatusCode}catch{}
            $probeError=Redact-LocalApiText ([string]$_.Exception.Message)
        }

        # Request logger flush can lag slightly behind HTTP completion.
        for($i=0;$i -lt 20;$i++){
            $selected=Find-HmsFailoverRequestEvidence $marker $started
            if($selected.Found){break}
            Start-Sleep -Milliseconds 300
        }

        $targetEmail=if($snap.Email){[string]$snap.Email}else{$TargetFile.Name}
        if($probeHttp -ne 200){
            $detail="Probe HTTP=$probeHttp; $probeError"
            throw $detail
        }
        if(-not $selected -or -not $selected.Found -or [string]::IsNullOrWhiteSpace([string]$selected.Label)){
            $detail='HTTP 200 nhưng chưa tìm được Auth mapping trong Request Log; không đủ evidence để PASS.'
            throw $detail
        }
        if(([string]$selected.Label).Trim().ToLowerInvariant() -eq $targetEmail.Trim().ToLowerInvariant()){
            $detail='Request vẫn dùng account đã disabled; failover không được chứng minh.'
            throw $detail
        }
        $verdict='PASS'
        $detail="Disabled $targetEmail; live request HTTP 200 được xử lý bởi $($selected.Label)."
    }catch{
        if(-not $detail){$detail=Redact-LocalApiText ([string]$_.Exception.Message)}
    }finally{
        if($snap -and $TargetFile -and (Test-Path $TargetFile.FullName)){
            try{
                if($snap.HadProperty){
                    Set-HmsAuthDisabledProperty $TargetFile ([bool]$snap.Disabled) $false
                }else{
                    Set-HmsAuthDisabledProperty $TargetFile $false $true
                }
                Start-Sleep -Milliseconds 900
                $rest=Get-HmsAuthDisabledSnapshot $TargetFile
                $restoreOk=($rest.Disabled -eq [bool]$snap.Disabled)
            }catch{$restoreOk=$false}
        }
        if(-not $restoreOk){
            $verdict='FAIL_RESTORE'
            $detail=($detail+' | RESTORE_NOT_CONFIRMED').Trim()
        }
        $obj=[ordered]@{
            version='25.12'
            run_id=$runId
            started_local=$started.ToString('o')
            completed_local=(Get-Date).ToString('o')
            verdict=$verdict
            detail=$detail
            target_file=if($TargetFile){$TargetFile.Name}else{''}
            target_email=if($snap){$snap.Email}else{''}
            target_original_disabled=if($snap){[bool]$snap.Disabled}else{$null}
            target_original_had_disabled_property=if($snap){[bool]$snap.HadProperty}else{$null}
            target_sha256_before=if($snap){$snap.Sha256}else{''}
            probe_http=$probeHttp
            marker=$marker
            selected_auth_id=if($selected){$selected.AuthId}else{''}
            selected_label=if($selected){$selected.Label}else{''}
            request_log_path=if($selected){$selected.Path}else{''}
            restored=$restoreOk
            safety='No auth deletion; only selected disabled flag was temporarily changed and restored.'
        }
        Save-JsonAtomic $resultPath $obj
    }
    return [PSCustomObject]@{Verdict=$verdict;Detail=$detail;Evidence=$resultPath;Restored=$restoreOk;Http=$probeHttp;Selected=if($selected){$selected.Label}else{''}}
}
function Show-HmsLiveFailoverCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text='HMS Codex Live Failover Test · v25.12'
    $w.Size=New-Object Drawing.Size(820,570)
    $w.StartPosition='CenterParent'
    $w.BackColor=[Drawing.Color]::FromArgb(12,14,17)
    $w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label;$title.Text='LIVE FAILOVER CERTIFICATION';$title.Font=New-Object Drawing.Font('Segoe UI Semibold',18);$title.Location=New-Object Drawing.Point(22,20);$title.AutoSize=$true;$w.Controls.Add($title)
    $desc=New-Object Windows.Forms.Label;$desc.Text='Tạm disable đúng 1 OAuth account → gửi 1 /v1/responses → chứng minh account khác xử lý → tự restore.';$desc.Location=New-Object Drawing.Point(24,62);$desc.Size=New-Object Drawing.Size(750,42);$desc.ForeColor=[Drawing.Color]::FromArgb(150,161,175);$w.Controls.Add($desc)

    $lab=New-Object Windows.Forms.Label;$lab.Text='Account tạm disable:';$lab.Location=New-Object Drawing.Point(24,116);$lab.AutoSize=$true;$w.Controls.Add($lab)
    $combo=New-Object Windows.Forms.ComboBox;$combo.DropDownStyle='DropDownList';$combo.Location=New-Object Drawing.Point(165,111);$combo.Size=New-Object Drawing.Size(585,28);$w.Controls.Add($combo)

    $bRefresh=Btn 'REFRESH ACCOUNTS' 24 155 170 36;$w.Controls.Add($bRefresh)
    $bRun=Btn 'CHẠY 1 FAILOVER TEST' 205 155 190 36;$bRun.BackColor=[Drawing.Color]::FromArgb(42,104,80);$w.Controls.Add($bRun)
    $bEvidence=Btn 'MỞ EVIDENCE' 405 155 150 36;$w.Controls.Add($bEvidence)
    $bQuota=Btn 'QUẢN LÝ / QUOTA' 565 155 185 36;$w.Controls.Add($bQuota)

    $out=New-Object Windows.Forms.TextBox;$out.Location=New-Object Drawing.Point(24,210);$out.Size=New-Object Drawing.Size(726,270);$out.Multiline=$true;$out.ReadOnly=$true;$out.ScrollBars='Vertical';$out.BackColor=[Drawing.Color]::FromArgb(20,23,27);$out.ForeColor=$w.ForeColor;$out.Font=New-Object Drawing.Font('Consolas',10);$w.Controls.Add($out)
    $warn=New-Object Windows.Forms.Label;$warn.Text='Safety: không xóa auth. Test tiêu thụ đúng 1 request nhỏ. Nếu restore không xác nhận được, verdict = FAIL_RESTORE và tool dừng.';$warn.Location=New-Object Drawing.Point(24,493);$warn.Size=New-Object Drawing.Size(740,42);$warn.ForeColor=[Drawing.Color]::FromArgb(218,175,90);$w.Controls.Add($warn)

    $script:LastFailoverEvidence=''
    function Refresh-Accounts {
        $combo.Items.Clear()
        foreach($r in @(Get-CodexAccountRecords)){
            if(-not $r.File){continue}
            $item=[PSCustomObject]@{Text=("$($r.Email) | $($r.Status) | $($r.Plan)");File=$r.File;Email=$r.Email;Status=$r.Status}
            [void]$combo.Items.Add($item)
        }
        $combo.DisplayMember='Text'
        if($combo.Items.Count -gt 0){$combo.SelectedIndex=0}
        $out.Text="Router: $(if(PortOpen ([int]$script:S.ProxyPort)){'ONLINE'}else{'OFFLINE'})`r`nRequest Log: $(if(Test-HmsProxyRequestLogEnabled){'ON'}else{'OFF'})`r`nAccounts: $($combo.Items.Count)"
    }
    $bRefresh.Add_Click({Refresh-Accounts})
    $bRun.Add_Click({
        try{
            if($combo.SelectedIndex -lt 0){throw 'Hãy chọn account.'}
            $item=$combo.SelectedItem
            $q=[Windows.Forms.MessageBox]::Show("Test sẽ tạm disable:`r`n$($item.Email)`r`n`r`nSau đó gửi đúng 1 request nhỏ và tự restore. Tiếp tục?",'HMS LIVE FAILOVER',[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
            if($q -ne [Windows.Forms.DialogResult]::Yes){return}
            $w.Cursor=[Windows.Forms.Cursors]::WaitCursor
            $out.Text='Đang chạy bounded live failover test...'
            [Windows.Forms.Application]::DoEvents()
            $r=Invoke-HmsLiveFailoverProbe $item.File
            $script:LastFailoverEvidence=$r.Evidence
            $out.Text="VERDICT: $($r.Verdict)`r`nHTTP: $($r.Http)`r`nSELECTED: $($r.Selected)`r`nRESTORED: $($r.Restored)`r`n`r`n$($r.Detail)`r`n`r`nEVIDENCE:`r`n$($r.Evidence)"
            if($r.Verdict -eq 'PASS'){
                [Windows.Forms.MessageBox]::Show('LIVE FAILOVER PASS và account đã restore.','HMS LIVE FAILOVER',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Information)|Out-Null
            }else{
                [Windows.Forms.MessageBox]::Show("FAILOVER chưa PASS: $($r.Detail)",'HMS LIVE FAILOVER',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Warning)|Out-Null
            }
            Refresh-Accounts
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'HMS LIVE FAILOVER',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Error)|Out-Null}
        finally{$w.Cursor=[Windows.Forms.Cursors]::Default}
    })
    $bEvidence.Add_Click({
        try{
            $p=[string]$script:LastFailoverEvidence
            if($p -and (Test-Path $p)){Start-Process explorer.exe ('/select,"'+$p+'"')|Out-Null}else{Start-Process explorer.exe (Get-HmsFailoverEvidenceRoot)|Out-Null}
        }catch{}
    })
    $bQuota.Add_Click({try{Start-Process ('http://127.0.0.1:'+([int]$script:S.ProxyPort)+'/management.html#/quota')|Out-Null}catch{}})
    $w.Add_Shown({Refresh-Accounts})
    [void]$w.ShowDialog($form)
}

# CODEX UNIFIED COMMAND CENTER v7.0
# Unified snapshot / topology / local read-only web dashboard
# ============================================================
function Get-CodexUnifiedAccountRows {
    $ha=Get-CodexHaSnapshot
    $attr=Load-JsonObjectSafe $script:CodexAttributionPath
    $active=$null
    if($attr){$active=$attr.latest_attribution}
    return @(Get-CodexAccountRecords | ForEach-Object {
        $q=Get-CodexQuotaForEmail $_.Email
        $h=Get-CodexAccountHealth $_
        $hs=@($ha.accounts | Where-Object account -eq $_.Email | Select-Object -First 1)
        $meta=Get-CodexAccountMeta $_.Email
        $ops=Get-CodexAccountOps $_.Email
        $liveQuota=Get-CodexLiveQuotaDecision $_ $q
        $hourly=$null;$weekly=$null
        if($q -and $null -ne $q.hourlyRemaining){$hourly=[double]$q.hourlyRemaining}
        if($q -and $null -ne $q.weeklyRemaining){$weekly=[double]$q.weeklyRemaining}
        [PSCustomObject]@{
            Account=$_.Email
            Plan=$_.Plan
            Status=$_.Status
            OpsState=[string]$ops.state
            Alias=[string]$ops.alias
            Group=[string]$ops.group
            Tag=[string]$meta.tag
            Favorite=[bool]$meta.favorite
            Hourly=if($null -ne $hourly){([Math]::Round($hourly,1).ToString()+"%")}else{"—"}
            Weekly=if($null -ne $weekly){([Math]::Round($weekly,1).ToString()+"%")}else{"—"}
            HourlyValue=$hourly
            WeeklyValue=$weekly
            Health=$h.Score
            Circuit=if($hs.Count){[string]$hs[0].state}else{"CLOSED"}
            Freshness=[string]$liveQuota.freshnessState
            ReservePct=[double]$liveQuota.reservePct
            UsablePct=$liveQuota.usableRemainingPct
            RouteEligible=[bool]$liveQuota.routingEligible
            HoldReasons=@($liveQuota.reasonCodes)
            IsActiveRoute=[bool]($active -and ([string]$active.account -eq [string]$_.Email))
            RouteConfidence=if($active -and ([string]$active.account -eq [string]$_.Email)){[string]$active.confidence}else{""}
        }
    })
}
function Get-CodexUnifiedTopologyText {
    $pool=Get-CodexPoolSummary
    $lines=[System.Collections.Generic.List[string]]::new()
    $listener=ListenerPid ([int]$script:S.ProxyPort)
    $routerState=if($listener -gt 0){if(IsOurProxy $listener){"ONLINE"}else{"FOREIGN"}}else{"OFFLINE"}
    $lines.Add("CODEX CLIENT / SESSIONS")
    $lines.Add("        │")
    $lines.Add("        ▼")
    $lines.Add("HMS SHARED ROUTER :$([int]$script:S.ProxyPort)  [$routerState]")
    $lines.Add("        │")
    $lines.Add("        ├── round-robin / session-affinity / native failover")
    $lines.Add("        │")
    foreach($a in @(Get-CodexUnifiedAccountRows)){
        $lines.Add(("        ├── {0} | {1} | OPS {2} | 5h {3} | W {4} | HA {5}" -f $a.Account,$a.Status,$a.OpsState,$a.Hourly,$a.Weekly,$a.Circuit))
    }
    $inst=@(Get-CodexInstanceRows)
    if($inst.Count){
        $lines.Add("")
        $lines.Add("MANAGED INSTANCES")
        foreach($i in $inst){
            $lines.Add(("  └── {0} → {1} → router :{2} [{3}] → client {4}" -f $i.Name,$i.Account,$i.Port,$i.Router,$i.Client))
        }
    }
    return ($lines -join "`r`n")
}
function Publish-CodexUnifiedSnapshot {
    Ensure-Dir $script:CodexWebDashboardDir
    $pool=Get-CodexPoolSummary
    $sla=Get-CodexFleetSla
    $ha=Get-CodexHaSnapshot
    $attr=Load-JsonObjectSafe $script:CodexAttributionPath
    $active=$null
    if($attr){$active=$attr.latest_attribution}
    $procId=ListenerPid ([int]$script:S.ProxyPort)
    $router=[ordered]@{
        state=if($procId -gt 0){if(IsOurProxy $procId){"ONLINE"}else{"FOREIGN"}}else{"OFFLINE"}
        pid=$procId
        port=[int]$script:S.ProxyPort
    }
    $accountRows=@(Get-CodexUnifiedAccountRows)
    $quotaRoute=[ordered]@{
        eligible=@($accountRows | Where-Object {[bool]$_.RouteEligible}).Count
        hold=@($accountRows | Where-Object {-not [bool]$_.RouteEligible}).Count
        fresh=@($accountRows | Where-Object {[string]$_.Freshness -eq "FRESH"}).Count
        aging=@($accountRows | Where-Object {[string]$_.Freshness -eq "AGING"}).Count
        stale=@($accountRows | Where-Object {[string]$_.Freshness -eq "STALE"}).Count
        unknown=@($accountRows | Where-Object {[string]$_.Freshness -eq "UNKNOWN"}).Count
    }
    $operatorAttention=[System.Collections.Generic.List[string]]::new()
    if($router.state -ne "ONLINE"){$operatorAttention.Add("ROUTER_"+$router.state)}
    if($accountRows.Count -gt 0 -and [int]$quotaRoute.eligible -eq 0){$operatorAttention.Add("NO_ROUTE_ELIGIBLE_ACCOUNT")}
    if([int]$quotaRoute.stale -gt 0){$operatorAttention.Add("STALE_QUOTA="+[string]$quotaRoute.stale)}
    if($active){
        $ar=@($accountRows | Where-Object {$_.Account -eq [string]$active.account} | Select-Object -First 1)
        if($ar.Count -and -not [bool]$ar[0].RouteEligible){$operatorAttention.Add("ACTIVE_ROUTE_HOLD")}
    }
    $kernel=Load-JsonObjectSafe $script:PolicyKernelLatestPath
    $perf=Load-JsonObjectSafe $script:PerformanceLatestPath
    $soak=Load-JsonObjectSafe $script:SoakLatestAnalysisPath
    $reconcile=Load-JsonObjectSafe $script:PoolReconcileLatestPath
    $routerIntel=Load-JsonObjectSafe $script:RouterIntelPath
    $apiAnalytics=Load-JsonObjectSafe $script:ApiAnalyticsLatestPath
    $apiParity=Load-JsonObjectSafe $script:ApiParityLatestPath
    $proxySafe=@()
    try{
        $pp=@(Get-HmsProxyProfiles)
        $pb=@(Get-HmsProxyBindings)
        $ph=@(Get-HmsProxyHealthRows)
        $pe=@(Get-HmsProxyEgressRows)
        $pside=@((Get-HmsProxySidecarState).sidecars)
        $fleetLatest=Load-JsonObjectSafe $script:ProxyFleetLatestPath
        $proxySafe=@($pp|ForEach-Object{
            $id=[string]$_.id
            $hh=@($ph|Where-Object ProfileId -eq $id|Select-Object -First 1)
            $ee=@($pe|Where-Object ProfileId -eq $id|Select-Object -First 1)
            $ss=@($pside|Where-Object profile_id -eq $id|Select-Object -First 1)
            $ff=@()
            if($fleetLatest){$ff=@($fleetLatest.profiles|Where-Object profile_id -eq $id|Select-Object -First 1)}
            [PSCustomObject]@{
                id=$id
                name=[string]$_.name
                mode=[string]$_.mode
                ops_state=Get-HmsProxyFleetOpsState $id
                country=[string]$_.country
                isp=[string]$_.isp
                assigned=@($pb|Where-Object proxy_profile_id -eq $id).Count
                capacity=[int]$_.max_accounts
                health=if($hh.Count){[string]$hh[0].Status}else{"UNKNOWN"}
                egress=if($ee.Count){[string]$ee[0].Integrity}else{"UNKNOWN"}
                expected_ip=if($ee.Count){[string]$ee[0].ExpectedIp}else{$null}
                observed_ip=if($ee.Count){[string]$ee[0].ObservedIp}else{$null}
                fleet_severity=if($ff.Count){[string]$ff[0].severity}else{"UNKNOWN"}
                recommendation=if($ff.Count){[string]$ff[0].recommendation}else{"NONE"}
                sidecar_running=($ss.Count -gt 0 -and ((ListenerPid ([int]$ss[0].port)) -eq [int]$ss[0].pid))
                sidecar_port=if($ss.Count){[int]$ss[0].port}else{$null}
            }
        })
    }catch{}
    $snap=[ordered]@{
        generatedUtc=[DateTime]::UtcNow.ToString("o")
        version=$script:Version
        readOnlyWeb=$true
        router=$router
        pool=[ordered]@{total=$pool.Total;ready=$pool.Ready;cooldown=$pool.Cooldown}
        sla=$sla
        active_route=$active
        accounts=$accountRows
        quota_routing=$quotaRoute
        operator_attention=@($operatorAttention.ToArray())
        instances=@(Get-CodexInstanceRows)
        ha=$ha
        incidents=@(Get-CodexIncidents | Select-Object -First 100)
        topology=Get-CodexUnifiedTopologyText
        router_intelligence=$(try{Get-CodexRouterIntelSummary}catch{"Router Intelligence unavailable"})
        router_intel_detail=$routerIntel
        performance=$(try{Get-HmsPerformanceSummary}catch{"Performance Analytics unavailable"})
        performance_detail=$perf
        policy_kernel=$(try{Get-HmsPolicyKernelSummary}catch{"Policy Kernel unavailable"})
        kernel=$kernel
        soak=$soak
        pool_reconcile=$reconcile
        proxy_affinity=$(try{Get-HmsProxyAffinitySummary}catch{"Proxy Affinity unavailable"})
        proxy_fleet=$(try{Get-HmsProxyFleetSummary}catch{"Proxy Fleet unavailable"})
        proxy_groups=$proxySafe
        api_analytics=$apiAnalytics
        cockpit_parity=$apiParity
        summary=("Router={0}; Ready={1}/{2}; RouteEligible={3}; Hold={4}; SLA={5}; Running instances={6}; Kernel={7}; ProxyGroups={8}; Parity={9}" -f
            $router.state,$pool.Ready,$pool.Total,$quotaRoute.eligible,$quotaRoute.hold,$sla.Score,
            @((Get-CodexInstanceRows) | Where-Object Client -eq "RUNNING").Count,
            $(if($kernel){[string]$kernel.state}else{"UNKNOWN"}),
            @($proxySafe).Count,
            $(if($apiParity -and $apiParity.data){[string]$apiParity.data.hms.feature_evidence_score_pct+"%"}else{"N/A"}))
    }
    Save-JsonAtomic $script:CodexUnifiedSnapshotPath $snap
    try{
        $safeJson=Redact-HmsText ($snap | ConvertTo-Json -Depth 16)
        $safeSnap=$safeJson | ConvertFrom-Json
        Save-JsonAtomic (Join-Path $script:CodexWebDashboardDir "snapshot.json") $safeSnap
    }catch{
        $fallback=[ordered]@{
            generatedUtc=[DateTime]::UtcNow.ToString("o")
            version=$script:Version
            readOnlyWeb=$true
            router=$router
            pool=[ordered]@{total=$pool.Total;ready=$pool.Ready;cooldown=$pool.Cooldown}
            sla=$sla
            active_route=$active
            accounts=@(Get-CodexUnifiedAccountRows)
            instances=@(Get-CodexInstanceRows)
            incidents=@()
            summary="Web snapshot redaction fallback; advanced detail omitted."
        }
        Save-JsonAtomic (Join-Path $script:CodexWebDashboardDir "snapshot.json") $fallback
    }
    return $snap
}
function Get-CodexWebDashboardState {
    $j=Load-JsonObjectSafe $script:UnifiedUxStatePath
    if(-not $j){return [PSCustomObject]@{pid=0;port=[int]$script:S.UnifiedUxPort;startedUtc=$null;script=""}}
    return $j
}
function Stop-CodexWebDashboard {
    $s=Get-CodexWebDashboardState
    $procId=[int]$s.pid
    $port=[int]$s.port
    if($procId -gt 0){
        try{
            $listener=ListenerPid $port
            if($listener -ne $procId){throw "State PID không còn sở hữu port $port; HMS không stop process."}
            $p=Get-Process -Id $procId -ErrorAction Stop
            if($p.ProcessName -notlike "python*"){throw "Dashboard PID không phải Python; HMS không stop."}
            $cmd=""
            try{
                $ci=Get-CimInstance Win32_Process -Filter ("ProcessId="+$procId) -ErrorAction Stop
                $cmd=[string]$ci.CommandLine
            }catch{}
            if($cmd -and ($cmd -notlike "*HMS_Codex_UnifiedUX.py*")){throw "Dashboard PID không khớp HMS_Codex_UnifiedUX.py; HMS không stop."}
            Stop-Process -Id $procId -Force -ErrorAction Stop
        }catch{
            Save-JsonAtomic $script:UnifiedUxStatePath ([PSCustomObject]@{pid=0;port=[int]$script:S.UnifiedUxPort;startedUtc=$null;script=""})
            return "Unified UX stop skipped/blocked: $($_.Exception.Message)"
        }
    }
    Save-JsonAtomic $script:UnifiedUxStatePath ([PSCustomObject]@{pid=0;port=[int]$script:S.UnifiedUxPort;startedUtc=$null;script=""})
    return "Unified UX đã dừng."
}
function Start-CodexWebDashboard {
    if(-not [bool]$script:S.UnifiedUxEnabled){throw "Unified UX đang tắt trong settings."}
    $port=[int]$script:S.UnifiedUxPort
    $existing=ListenerPid $port
    if($existing -gt 0){
        $s=Get-CodexWebDashboardState
        if(([int]$s.pid -eq $existing) -and ([int]$s.port -eq $port)){
            return "Unified UX đã chạy: http://127.0.0.1:$port/"
        }
        throw "Port $port đang do process khác sử dụng. HMS không can thiệp."
    }
    $null=Publish-CodexUnifiedSnapshot
    $scriptPath=Join-Path $PSScriptRoot "HMS_Codex_UnifiedUX.py"
    if(-not (Test-Path $scriptPath)){throw "Thiếu HMS_Codex_UnifiedUX.py"}
    $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
        $scriptPath,"--dir",$script:CodexWebDashboardDir,"--port",[string]$port
    ) -WindowStyle Hidden -PassThru
    for($i=0;$i -lt 25;$i++){
        Start-Sleep -Milliseconds 200
        if(PortOpen $port){break}
    }
    if(-not (PortOpen $port)){
        try{Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}catch{}
        throw "Unified UX không mở được port $port."
    }
    Save-JsonAtomic $script:UnifiedUxStatePath ([PSCustomObject]@{
        pid=$p.Id;port=$port;startedUtc=[DateTime]::UtcNow.ToString("o");script=$scriptPath
    })
    Add-Content -LiteralPath $script:UnifiedUxAuditPath -Value (([ordered]@{
        time=[DateTime]::UtcNow.ToString("o");event="START";pid=$p.Id;port=$port;readOnly=$true
    })| ConvertTo-Json -Compress) -Encoding UTF8
    $url="http://127.0.0.1:$port/"
    if([bool]$script:S.UnifiedUxOpenBrowserOnStart){Start-Process $url | Out-Null}
    return "Unified UX ONLINE: $url"
}
function Start-HmsUnifiedUx { return Start-CodexWebDashboard }
function Stop-HmsUnifiedUx { return Stop-CodexWebDashboard }
function Show-CodexUnifiedCommandCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Native Command Center · v25.43"
    $w.Size=New-Object Drawing.Size(1500,900)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(12,14,17)
    $w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $w.MinimumSize=New-Object Drawing.Size(1250,760)

    $head=New-Object Windows.Forms.Label
    $head.Text="HMS CODEX NATIVE COMMAND CENTER"
    $head.Font=New-Object Drawing.Font("Segoe UI Semibold",21)
    $head.Location=New-Object Drawing.Point(20,14);$head.AutoSize=$true;$w.Controls.Add($head)

    $route=New-Object Windows.Forms.Label
    $route.Location=New-Object Drawing.Point(22,53);$route.Size=New-Object Drawing.Size(900,38)
    $route.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($route)

    $bRefresh=Btn "REFRESH" 1000 18 110 34;$w.Controls.Add($bRefresh)
    $bWeb=Btn "UNIFIED UX" 1120 18 160 34;$w.Controls.Add($bWeb)
    $bHa=Btn "HA" 1290 18 70 34;$w.Controls.Add($bHa)
    $bOps=Btn "OPS" 1370 18 70 34;$w.Controls.Add($bOps)

    $tabs=New-Object Windows.Forms.TabControl
    $tabs.Location=New-Object Drawing.Point(18,95);$tabs.Size=New-Object Drawing.Size(1440,735);$w.Controls.Add($tabs)
    foreach($n in @("Overview","Accounts","Instances","HA & Metrics","Incidents","Topology","Advanced")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(17,20,24);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $pO=$tabs.TabPages[0];$pA=$tabs.TabPages[1];$pI=$tabs.TabPages[2];$pH=$tabs.TabPages[3];$pInc=$tabs.TabPages[4];$pTopo=$tabs.TabPages[5];$pAdv=$tabs.TabPages[6]

    $c1=New-StatCard "ROUTER" 20 25 210 $pO
    $c2=New-StatCard "READY ACCOUNTS" 245 25 210 $pO
    $c3=New-StatCard "FLEET SLA" 470 25 210 $pO
    $c4=New-StatCard "RUNNING INSTANCES" 695 25 210 $pO
    $c5=New-StatCard "OPEN CIRCUITS" 920 25 210 $pO
    $c6=New-StatCard "ACTIVE ROUTE" 1145 25 210 $pO
    $overview=New-Object Windows.Forms.TextBox
    $overview.Location=New-Object Drawing.Point(20,125);$overview.Size=New-Object Drawing.Size(1335,500)
    $overview.Multiline=$true;$overview.ReadOnly=$true;$overview.ScrollBars="Both";$overview.WordWrap=$false
    $overview.BackColor=[Drawing.Color]::FromArgb(20,23,27);$overview.ForeColor=$w.ForeColor;$pO.Controls.Add($overview)

    $gA=New-DarkGrid 15 20 1350 590 $pA
    $gI=New-DarkGrid 15 20 1350 590 $pI
    $gH=New-DarkGrid 15 20 1350 590 $pH
    $gInc=New-DarkGrid 15 20 1350 590 $pInc

    $topo=New-Object Windows.Forms.TextBox
    $topo.Location=New-Object Drawing.Point(15,20);$topo.Size=New-Object Drawing.Size(1350,590)
    $topo.Multiline=$true;$topo.ReadOnly=$true;$topo.ScrollBars="Both";$topo.WordWrap=$false
    $topo.Font=New-Object Drawing.Font("Consolas",10);$topo.BackColor=[Drawing.Color]::FromArgb(20,23,27);$topo.ForeColor=$w.ForeColor;$pTopo.Controls.Add($topo)

    $advText=New-Object Windows.Forms.Label
    $advText.Text="Advanced Centers";$advText.Font=New-Object Drawing.Font("Segoe UI Semibold",16)
    $advText.Location=New-Object Drawing.Point(20,20);$advText.AutoSize=$true;$pAdv.Controls.Add($advText)
    $buttons=@(
        @("AUTOPILOT",20,70,{Show-CodexAutopilotCenter}),
        @("OPERATIONS",190,70,{Show-CodexOperationsCenter}),
        @("FLEET",360,70,{Show-CodexFleetCenter}),
        @("ORCHESTRATOR",530,70,{Show-CodexOrchestrator}),
        @("SESSION CENTER",700,70,{Show-CodexSessionCenter}),
        @("THREAD SYNC",870,70,{Show-CodexThreadSyncCenter}),
        @("TELEMETRY",1040,70,{Show-CodexTelemetryCenter}),
        @("BACKUP",1210,70,{Show-HmsBackupCenter}),
        @("PRODUCTION",20,125,{Show-HmsProductionCenter}),
        @("RELEASE",190,125,{Show-HmsReleaseEngineeringCenter}),
        @("VALIDATION",360,125,{Show-HmsValidationCenter}),
        @("ACCOUNT OPS",530,125,{Show-CodexAccountSessionOperations}),
        @("ROUTER INTEL",700,125,{Show-CodexRouterIntelligenceCenter}),
        @("POOL RECOVERY",870,125,{Show-CodexPoolRecoveryCenter}),
        @("SOAK",1040,125,{Show-HmsSoakCenter}),
        @("PERFORMANCE",1210,125,{Show-HmsPerformanceCenter}),
        @("KERNEL",20,180,{Show-HmsPolicyKernelCenter}),
        @("FAILOVER TEST",190,180,{Show-HmsLiveFailoverCenter})
    )
    foreach($x in $buttons){$b=Btn ([string]$x[0]) ([int]$x[1]) ([int]$x[2]) 150 38;$b.Add_Click($x[3]);$pAdv.Controls.Add($b)}

    function Refresh-U {
        try{
            $snap=Publish-CodexUnifiedSnapshot
            $c1.Text=[string]$snap.router.state
            $c2.Text="$($snap.pool.ready) / $($snap.pool.total)"
            $c3.Text=[string]$snap.sla.Score
            $c4.Text=[string](@($snap.instances|Where-Object Client -eq "RUNNING").Count)
            $c5.Text=[string](@($snap.ha.accounts|Where-Object state -in @("OPEN","HALF_OPEN","LOCKED_OPEN")).Count)
            $c6.Text=if($snap.active_route -and $snap.active_route.account){[string]$snap.active_route.account}else{"—"}
            $route.Text=if($snap.active_route -and $snap.active_route.account){"ACTIVE ROUTE: $($snap.active_route.account) [$($snap.active_route.confidence)]"}else{"ACTIVE ROUTE: UNATTRIBUTED"}
            $overview.Text=$snap.topology+"`r`n`r`nSUMMARY`r`n"+$snap.summary
            $gA.DataSource=$null;$gA.DataSource=@($snap.accounts)
            $gI.DataSource=$null;$gI.DataSource=@($snap.instances)
            $gH.DataSource=$null;$gH.DataSource=@($snap.ha.accounts)
            $gInc.DataSource=$null;$gInc.DataSource=@($snap.incidents)
            $topo.Text=$snap.topology
        }catch{$route.Text="Unified refresh error: "+$_.Exception.Message}
    }
    $bRefresh.Add_Click({Refresh-U})
    $bWeb.Add_Click({
        try{
            $m=Start-HmsUnifiedUx
            $url="http://127.0.0.1:$([int]$script:S.UnifiedUxPort)/"
            if(-not [bool]$script:S.UnifiedUxOpenBrowserOnStart){Start-Process $url | Out-Null}
            $route.Text=$m
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bHa.Add_Click({Show-CodexHaCenter})
    $bOps.Add_Click({Show-CodexOperationsCenter})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=[Math]::Max(3000,[int]$script:S.CodexUnifiedRefreshSec*1000);$tm.Add_Tick({Refresh-U});$tm.Start()
    $w.Add_Shown({Refresh-U})
    $w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# PRODUCTION HARDENING v8.0
# startup crash recovery / self-test / health certificate / log archive
# ============================================================
function Invoke-HmsProductionDoctor {
    param([ValidateSet("audit","archive")][string]$Mode="audit",[string]$LogDir="")
    Ensure-Dir $script:ProductionDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_ProductionDoctor.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_ProductionDoctor.py"}
    $tmp=Join-Path $env:TEMP ("hms-prod-"+[Guid]::NewGuid().ToString("N")+".json")
    $args=@($helper,"--mode",$Mode,"--root",$PSScriptRoot,"--data",$script:DataDir,"--output",$tmp)
    if($Mode -eq "archive"){
        if(-not $LogDir){throw "Thiếu log directory."}
        $args+=@("--log-dir",$LogDir,"--archive-dir",$script:ProductionArchiveDir,
                 "--min-age-days",[string][int]$script:S.ProductionArchiveMinAgeDays,
                 "--keep-latest",[string][int]$script:S.ProductionArchiveKeepLatest)
    }
    $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    if(-not (Test-Path $tmp)){throw "Production Doctor không tạo output. exit=$($p.ExitCode)"}
    try{$j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json}finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    if(-not $j.ok){throw[string]$j.error}
    return $j.data
}
function Test-HmsPidAlive {
    param([int]$procId)
    if($procId -le 0){return $false}
    try{$null=Get-Process -Id $procId -ErrorAction Stop;return $true}catch{return $false}
}
function Initialize-HmsProductionRuntime {
    Ensure-Dir $script:ProductionDir
    Ensure-Dir $script:ProductionArchiveDir
    $previous=$null
    if(Test-Path $script:RuntimeMarkerPath){
        try{$previous=Get-Content $script:RuntimeMarkerPath -Raw -Encoding UTF8| ConvertFrom-Json}catch{}
    }
    $unclean=$false;$parallel=$false
    if($previous){
        $clean=$false;try{$clean=[bool]$previous.cleanExit}catch{}
        $prevPid=0;try{$prevPid=[int]$previous.pid}catch{}
        if(-not $clean){
            if(Test-HmsPidAlive $prevPid){$parallel=$true}else{$unclean=$true}
        }
    }
    $script:ParallelInstanceDetected=$parallel
    if($unclean -and [bool]$script:S.ProductionSafeStartupAfterCrash){
        $script:SafeStartupMode=$true
        $script:RuntimeAutomationBlocked=$true
    }
    if($parallel -and [bool]$script:S.ProductionWarnParallelInstance){
        $script:SafeStartupMode=$true
        $script:RuntimeAutomationBlocked=$true
    }

    $marker=[ordered]@{
        version=$script:Version;pid=$PID;startedUtc=[DateTime]::UtcNow.ToString("o");
        cleanExit=$false;safeStartup=[bool]$script:SafeStartupMode;previousUnclean=$unclean;parallelInstance=$parallel
    }
    Save-JsonAtomic $script:RuntimeMarkerPath $marker

    $audit=$null
    if([bool]$script:S.ProductionSelfTestOnStartup){
        try{$audit=Invoke-HmsProductionDoctor "audit";Save-JsonAtomic $script:ProductionSelfTestPath $audit}catch{
            $audit=[PSCustomObject]@{score=0;grade="FAIL";error=$_.Exception.Message}
            Save-JsonAtomic $script:ProductionSelfTestPath $audit
            $script:SafeStartupMode=$true;$script:RuntimeAutomationBlocked=$true
        }
    }
    $report=[ordered]@{
        time=[DateTime]::UtcNow.ToString("o");version=$script:Version;previousUnclean=$unclean;
        parallelInstance=$parallel;safeStartup=[bool]$script:SafeStartupMode;
        settingsWarning=[string]$script:SettingsLoadWarning;selfTest=$audit
    }
    Save-JsonAtomic $script:StartupReportPath $report
    return $report
}
function Complete-HmsRuntimeSession {
    try{
        $marker=[ordered]@{version=$script:Version;pid=$PID;startedUtc=$null;endedUtc=[DateTime]::UtcNow.ToString("o");cleanExit=$true;safeStartup=[bool]$script:SafeStartupMode}
        Save-JsonAtomic $script:RuntimeMarkerPath $marker
        Save-JsonAtomic $script:LastCleanExitPath $marker
    }catch{}
}
function Publish-HmsHealthCertificate {
    if(-not [bool]$script:S.ProductionCertificateEnabled){return $null}
    Ensure-Dir $script:ProductionDir
    $audit=$null
    try{$audit=Invoke-HmsProductionDoctor "audit"}catch{$audit=[PSCustomObject]@{score=0;grade="FAIL";error=$_.Exception.Message}}
    $score=[int]$audit.score
    $pool=$null;$sla=$null
    try{$pool=Get-CodexPoolSummary}catch{}
    try{$sla=Get-CodexFleetSla}catch{}
    if(CodexInHmsMode){
        $listener=ListenerPid ([int]$script:S.ProxyPort)
        if($listener -le 0){$score-=20}
        elseif(-not (IsOurProxy $listener)){$score-=25}
    }
    if($pool -and [int]$pool.Total -gt 0 -and [int]$pool.Ready -eq 0){$score-=15}
    if($sla -and [int]$sla.Score -lt 70){$score-=10}
    if($script:SafeStartupMode){$score-=10}
    $score=[Math]::Max(0,[Math]::Min(100,$score))
    $grade=if($score -ge 90){"PASS"}elseif($score -ge 70){"WARN"}else{"FAIL"}
    $cert=[ordered]@{
        generatedUtc=[DateTime]::UtcNow.ToString("o");version=$script:Version;score=$score;grade=$grade;
        safeStartup=[bool]$script:SafeStartupMode;parallelInstance=[bool]$script:ParallelInstanceDetected;
        productionDoctor=$audit;pool=$pool;sla=$sla
    }
    Save-JsonAtomic $script:HealthCertificatePath $cert
    $txt="HMS-AI-ROUTER v$($script:Version)`r`nHEALTH CERTIFICATE: $grade $score/100`r`nGenerated: $($cert.generatedUtc)`r`nSafe Startup: $($cert.safeStartup)`r`nParallel Instance: $($cert.parallelInstance)"
    Set-Content -Path $script:HealthCertificateTextPath -Value $txt -Encoding UTF8
    return $cert
}
function Invoke-HmsArchiveOldLogs {
    $logDir=Join-Path ([string]$script:S.ProxyDir) "logs"
    if(-not (Test-Path $logDir)){throw "Không có thư mục logs: $logDir"}
    $listener=ListenerPid ([int]$script:S.ProxyPort)
    if($listener -gt 0 -and (IsOurProxy $listener)){throw "Hãy STOP HMS router trước khi archive/move log cũ."}
    return Invoke-HmsProductionDoctor -Mode "archive" -LogDir $logDir
}
function Exit-HmsSafeStartup {
    $script:SafeStartupMode=$false
    $script:RuntimeAutomationBlocked=$false
    return "Đã rời Safe Startup cho phiên hiện tại. Không thay đổi settings tự động."
}
function Show-HmsProductionCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Production Center v8.0"
    $w.Size=New-Object Drawing.Size(1220,760);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="PRODUCTION HARDENING";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,55);$status.Size=New-Object Drawing.Size(1120,55);$status.Font=New-Object Drawing.Font("Segoe UI Semibold",12);$w.Controls.Add($status)
    $bTest=Btn "RUN SELF-TEST" 20 115 150 36;$w.Controls.Add($bTest)
    $bCert=Btn "HEALTH CERTIFICATE" 185 115 180 36;$w.Controls.Add($bCert)
    $bLogs=Btn "ARCHIVE OLD LOGS" 380 115 180 36;$w.Controls.Add($bLogs)
    $bSafe=Btn "EXIT SAFE STARTUP" 575 115 180 36;$w.Controls.Add($bSafe)
    $bOpen=Btn "OPEN PRODUCTION DIR" 770 115 190 36;$w.Controls.Add($bOpen)
    $bRelease=Btn "RELEASE CENTER" 975 115 160 36;$w.Controls.Add($bRelease)
    $bValidation=Btn "VALIDATION" 975 155 160 36;$w.Controls.Add($bValidation)
    $box=New-Object Windows.Forms.TextBox;$box.Location=New-Object Drawing.Point(20,170);$box.Size=New-Object Drawing.Size(1140,480);$box.Multiline=$true;$box.ReadOnly=$true;$box.ScrollBars="Both";$box.WordWrap=$false;$box.BackColor=[Drawing.Color]::FromArgb(20,23,27);$box.ForeColor=$w.ForeColor;$w.Controls.Add($box)
    function Refresh-P {
        $status.Text="SAFE STARTUP: $($script:SafeStartupMode)   |   PARALLEL INSTANCE: $($script:ParallelInstanceDetected)   |   SETTINGS: "+$(if($script:SettingsLoadWarning){$script:SettingsLoadWarning}else{"OK"})
        if(Test-Path $script:StartupReportPath){$box.Text=Get-Content $script:StartupReportPath -Raw -Encoding UTF8}
    }
    $bTest.Add_Click({try{$r=Invoke-HmsProductionDoctor "audit";Save-JsonAtomic $script:ProductionSelfTestPath $r;$box.Text=$r| ConvertTo-Json -Depth 8;Refresh-P}catch{$box.Text=$_.Exception.Message}})
    $bCert.Add_Click({try{$r=Publish-HmsHealthCertificate;$box.Text=$r| ConvertTo-Json -Depth 8}catch{$box.Text=$_.Exception.Message}})
    $bLogs.Add_Click({
        try{
            $ans=[Windows.Forms.MessageBox]::Show("Archive log cũ sẽ tạo ZIP rồi xóa các file gốc đã archive. HMS router phải STOP.`r`n`r`nTiếp tục?","ARCHIVE OLD LOGS",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
            if($ans -ne [Windows.Forms.DialogResult]::Yes){return}
            $r=Invoke-HmsArchiveOldLogs;$box.Text=$r| ConvertTo-Json -Depth 6
        }catch{$box.Text=$_.Exception.Message}
    })
    $bSafe.Add_Click({$box.Text=Exit-HmsSafeStartup;Refresh-P})
    $bOpen.Add_Click({Ensure-Dir $script:ProductionDir;Start-Process explorer.exe $script:ProductionDir|Out-Null})
    $bRelease.Add_Click({Show-HmsReleaseEngineeringCenter})
    $bValidation.Add_Click({Show-HmsValidationCenter})
    $w.Add_Shown({Refresh-P})
    [void]$w.ShowDialog($form)
}


# ============================================================
# RELEASE ENGINEERING v9.0
# ============================================================
function Get-HmsDefaultInstallRoot {
    if($script:S.ReleaseInstallRoot){return [string]$script:S.ReleaseInstallRoot}
    return (Join-Path $env:LOCALAPPDATA "HMS_AI")
}
function Invoke-HmsReleaseManager {
    param([ValidateSet("preflight","install","rollback","certificate","status")][string]$Mode)
    Ensure-Dir $script:ReleaseEngineeringDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_ReleaseManager.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_ReleaseManager.py"}
    $packageRoot=Split-Path -Parent $PSScriptRoot
    $args=@("--mode",$Mode,"--root",$packageRoot,"--version",$script:Version)
    if($Mode -in @("install","rollback","status")){$args+=@("--install-root",(Get-HmsDefaultInstallRoot))}
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $helper -Arguments $args
    $data=$j.data
    if($Mode -eq "preflight"){Save-JsonAtomic $script:ReleasePreflightPath $data}
    elseif($Mode -eq "certificate"){Save-JsonAtomic $script:ReleaseCertificatePath $data}
    elseif($Mode -in @("install","rollback")){Save-JsonAtomic $script:ReleaseInstallStatePath $data}
    return $data
}
function Show-HmsReleaseEngineeringCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Release Engineering v9.0";$w.Size=New-Object Drawing.Size(1220,760);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="RELEASE ENGINEERING";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $path=New-Object Windows.Forms.Label;$path.Location=New-Object Drawing.Point(20,55);$path.Size=New-Object Drawing.Size(1120,45);$path.Text="Install root: "+(Get-HmsDefaultInstallRoot);$path.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($path)
    $bPre=Btn "PREFLIGHT" 20 105 140 36;$w.Controls.Add($bPre)
    $bCert=Btn "RELEASE CERTIFICATE" 175 105 180 36;$w.Controls.Add($bCert)
    $bInstall=Btn "INSTALL / ACTIVATE" 370 105 180 36;$w.Controls.Add($bInstall)
    $bRollback=Btn "ROLLBACK" 565 105 140 36;$w.Controls.Add($bRollback)
    $bOpen=Btn "OPEN INSTALL ROOT" 720 105 180 36;$w.Controls.Add($bOpen)
    $box=New-Object Windows.Forms.TextBox;$box.Location=New-Object Drawing.Point(20,160);$box.Size=New-Object Drawing.Size(1140,500);$box.Multiline=$true;$box.ReadOnly=$true;$box.ScrollBars="Both";$box.WordWrap=$false;$box.BackColor=[Drawing.Color]::FromArgb(20,23,27);$box.ForeColor=$w.ForeColor;$w.Controls.Add($box)
    $bPre.Add_Click({try{$box.Text=(Invoke-HmsReleaseManager "preflight")| ConvertTo-Json -Depth 10}catch{$box.Text=$_.Exception.Message}})
    $bCert.Add_Click({try{$box.Text=(Invoke-HmsReleaseManager "certificate")| ConvertTo-Json -Depth 10}catch{$box.Text=$_.Exception.Message}})
    $bInstall.Add_Click({try{$a=[Windows.Forms.MessageBox]::Show("Install/activate v9 theo thư mục versioned. Không ghi đè release cũ.`r`nTiếp tục?","INSTALL",[Windows.Forms.MessageBoxButtons]::YesNo);if($a -eq [Windows.Forms.DialogResult]::Yes){$box.Text=(Invoke-HmsReleaseManager "install")| ConvertTo-Json -Depth 10}}catch{$box.Text=$_.Exception.Message}})
    $bRollback.Add_Click({try{$a=[Windows.Forms.MessageBox]::Show("Rollback chỉ đổi active pointer; không xóa release hiện tại.`r`nTiếp tục?","ROLLBACK",[Windows.Forms.MessageBoxButtons]::YesNo);if($a -eq [Windows.Forms.DialogResult]::Yes){$box.Text=(Invoke-HmsReleaseManager "rollback")| ConvertTo-Json -Depth 10}}catch{$box.Text=$_.Exception.Message}})
    $bOpen.Add_Click({$r=Get-HmsDefaultInstallRoot;Ensure-Dir $r;Start-Process explorer.exe $r|Out-Null})
    [void]$w.ShowDialog($form)
}


# ============================================================
# WINDOWS RUNTIME VALIDATION HARNESS v10.0
# ============================================================
function Invoke-HmsRuntimeValidator {
    param([ValidateSet("STATIC","SAFE_RUNTIME","FULL_RUNTIME")][string]$Profile="SAFE_RUNTIME")
    Ensure-Dir $script:ValidationDir;Ensure-Dir $script:ValidationEvidenceDir;Ensure-Dir $script:ValidationReportDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_RuntimeValidator.py"
    $tmp=Join-Path $env:TEMP ("hms-validation-"+[Guid]::NewGuid().ToString("N")+".json")
    $cfg=Join-Path $env:TEMP ("hms-validation-cfg-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        Save-Json $cfg ([ordered]@{proxy_port=[int]$script:S.ProxyPort;api_key=[string]$script:S.LocalApiKey;auth_dir=[string]$script:AuthDir;web_port=[int]$script:S.UnifiedUxPort;install_root=(Get-HmsDefaultInstallRoot)})
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @($helper,"--mode","run","--root",$PSScriptRoot,"--data",$script:DataDir,"--profile",$Profile,"--config",$cfg,"--output",$tmp) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $tmp)){throw "RuntimeValidator không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json;if(-not $j.ok){throw[string]$j.error}
        $r=$j.data;$report=Join-Path $script:ValidationReportDir ("validation-"+$Profile.ToLowerInvariant()+"-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".json")
        Save-JsonAtomic $report $r;Save-JsonAtomic $script:ValidationLatestPath $r
        Add-Content $script:ValidationHistoryPath (($r| ConvertTo-Json -Compress -Depth 12)) -Encoding UTF8
        if([bool]$script:S.ValidationAutoSaveEvidence){try{$r.evidence_bundle=New-HmsValidationEvidence $report;Save-JsonAtomic $report $r;Save-JsonAtomic $script:ValidationLatestPath $r}catch{}}
        return $r
    }finally{Remove-Item $tmp,$cfg -Force -ErrorAction SilentlyContinue}
}
function New-HmsValidationEvidence {
    param([string]$ReportPath)
    $helper=Join-Path $PSScriptRoot "HMS_Codex_EvidencePacker.py";$tmp=Join-Path $env:TEMP ("hms-evidence-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @($helper,"--report",$ReportPath,"--out-dir",$script:ValidationEvidenceDir,"--output",$tmp) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $tmp)){throw "Evidence packer không tạo output"}
        $j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json;if(-not $j.ok){throw "Evidence pack failed"};return [string]$j.zip
    }finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
}
function Invoke-HmsFullRuntimeStep {
    param([string]$TestId)
    if(-not [bool]$script:S.ValidationAllowFullRuntime){throw "FULL_RUNTIME đang khóa trong settings."}
    switch($TestId){
        "full.router_restart" {
            $a=[Windows.Forms.MessageBox]::Show("STOP/START router HMS và verify port. Foreign PID sẽ không bị đụng.`r`nTiếp tục?","FULL RUNTIME",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
            if($a -ne [Windows.Forms.DialogResult]::Yes){return [PSCustomObject]@{status="BLOCKED";summary="Operator hủy"}}
            $procId=ListenerPid ([int]$script:S.ProxyPort);if($procId -gt 0 -and -not (IsOurProxy $procId)){return [PSCustomObject]@{status="BLOCKED";summary="Foreign port owner"}}
            try{if($procId -gt 0){$null=Stop-Router};Start-Sleep -Milliseconds 500;$m=Start-Router;Start-Sleep -Seconds 1;$ok=PortOpen ([int]$script:S.ProxyPort);return [PSCustomObject]@{status=if($ok){"PASS"}else{"FAIL"};summary=$m}}catch{return [PSCustomObject]@{status="FAIL";summary=$_.Exception.Message}}
        }
        "full.rollback" {
            $a=[Windows.Forms.MessageBox]::Show("Rollback chỉ đổi active release pointer; không xóa release.`r`nTiếp tục?","FULL RUNTIME",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
            if($a -ne [Windows.Forms.DialogResult]::Yes){return [PSCustomObject]@{status="BLOCKED";summary="Operator hủy"}}
            try{$r=Invoke-HmsReleaseManager "rollback";return [PSCustomObject]@{status="PASS";summary=($r| ConvertTo-Json -Compress -Depth 5)}}catch{return [PSCustomObject]@{status="FAIL";summary=$_.Exception.Message}}
        }
        "full.two_instances" {return [PSCustomObject]@{status="BLOCKED";summary="Chọn 2 instance thật trong Orchestrator; harness không tự tạo/bind."}}
        "full.failover" {return [PSCustomObject]@{status="BLOCKED";summary="Không phá credential để ép failover; chờ failure/cooldown thật."}}
        "full.crash_recovery" {return [PSCustomObject]@{status="BLOCKED";summary="Forced crash chạy ở phiên test riêng; không tự kill chính HMS."}}
        default{return [PSCustomObject]@{status="BLOCKED";summary="Unknown full-runtime test"}}
    }
}
function Show-HmsValidationCenter {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Windows Runtime Validation Center v10.0";$w.Size=New-Object Drawing.Size(1380,820);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $t=New-Object Windows.Forms.Label;$t.Text="WINDOWS RUNTIME VALIDATION";$t.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$t.Location=New-Object Drawing.Point(20,15);$t.AutoSize=$true;$w.Controls.Add($t)
    $profile=New-Object Windows.Forms.ComboBox;$profile.DropDownStyle="DropDownList";$profile.Location=New-Object Drawing.Point(20,60);$profile.Size=New-Object Drawing.Size(190,28);foreach($x in @("STATIC","SAFE_RUNTIME","FULL_RUNTIME")){[void]$profile.Items.Add($x)};$profile.SelectedItem=[string]$script:S.ValidationDefaultProfile;$w.Controls.Add($profile)
    $bRun=Btn "RUN PROFILE" 225 56 150 34;$w.Controls.Add($bRun);$bEv=Btn "OPEN EVIDENCE" 390 56 150 34;$w.Controls.Add($bEv);$bProd=Btn "PRODUCTION" 555 56 130 34;$w.Controls.Add($bProd);$bRel=Btn "RELEASE" 700 56 120 34;$w.Controls.Add($bRel)
    $sum=New-Object Windows.Forms.Label;$sum.Location=New-Object Drawing.Point(850,52);$sum.Size=New-Object Drawing.Size(470,50);$sum.Font=New-Object Drawing.Font("Segoe UI Semibold",12);$w.Controls.Add($sum)
    $g=New-DarkGrid 18 110 1315 500 $w
    $d=New-Object Windows.Forms.TextBox;$d.Location=New-Object Drawing.Point(18,625);$d.Size=New-Object Drawing.Size(1315,100);$d.Multiline=$true;$d.ReadOnly=$true;$d.ScrollBars="Vertical";$d.BackColor=[Drawing.Color]::FromArgb(20,23,27);$d.ForeColor=$w.ForeColor;$w.Controls.Add($d)
    function Load-R($r){$g.DataSource=$null;$g.DataSource=@($r.tests|ForEach-Object{[PSCustomObject]@{Id=$_.id;Status=$_.status;Severity=$_.severity;Summary=$_.summary}});$sum.Text="VERDICT: $($r.verdict)   PASS=$($r.summary.pass) FAIL=$($r.summary.fail) BLOCKED=$($r.summary.blocked)";$d.Text="Evidence: "+[string]$r.evidence_bundle}
    $bRun.Add_Click({try{$p=[string]$profile.SelectedItem;if($p -eq "FULL_RUNTIME"){$a=[Windows.Forms.MessageBox]::Show("FULL_RUNTIME có operator gates. Chạy catalog/profile?","FULL RUNTIME",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning);if($a -ne [Windows.Forms.DialogResult]::Yes){return}};$w.Cursor=[Windows.Forms.Cursors]::WaitCursor;Load-R (Invoke-HmsRuntimeValidator $p)}catch{$d.Text=$_.Exception.Message}finally{$w.Cursor=[Windows.Forms.Cursors]::Default}})
    $g.Add_CellDoubleClick({try{if($g.SelectedRows.Count -lt 1){return};$id=[string]$g.SelectedRows[0].Cells["Id"].Value;if($id -like "full.*"){$r=Invoke-HmsFullRuntimeStep $id;$d.Text="$id`r`n$($r.status): $($r.summary)"}}catch{$d.Text=$_.Exception.Message}})
    $bEv.Add_Click({Ensure-Dir $script:ValidationEvidenceDir;Start-Process explorer.exe $script:ValidationEvidenceDir|Out-Null});$bProd.Add_Click({Show-HmsProductionCenter});$bRel.Add_Click({Show-HmsReleaseEngineeringCenter})
    $w.Add_Shown({$r=Load-JsonObjectSafe $script:ValidationLatestPath;if($r){Load-R $r}});[void]$w.ShowDialog($form)
}


# ============================================================
# ACCOUNT & SESSION OPERATIONS v11.0
# Non-destructive account overlays + session visibility
# ============================================================
function Get-CodexAccountOpsStore {
    $j=Load-JsonObjectSafe $script:AccountOpsPath
    if(-not $j){return @{}}
    $h=@{};foreach($p in @($j.PSObject.Properties)){$h[$p.Name]=$p.Value};return $h
}
function Save-CodexAccountOpsStore([hashtable]$Store){
    $o=[ordered]@{};foreach($k in($Store.Keys|Sort-Object)){$o[$k]=$Store[$k]};Save-JsonAtomic $script:AccountOpsPath $o
}
function Get-CodexAccountOps {
    param([string]$Email)
    $k=$Email.Trim().ToLowerInvariant();$s=Get-CodexAccountOpsStore
    if($s.ContainsKey($k)){return $s[$k]}
    return [PSCustomObject]@{state=[string]$script:S.AccountOpsDefaultState;alias="";group="";reason="";updatedUtc=$null}
}
function Set-CodexAccountOps {
    param([string]$Email,[ValidateSet("ACTIVE","MAINTENANCE","QUARANTINED")][string]$State,[string]$Alias="",[string]$Group="",[string]$Reason="")
    $store=Get-CodexAccountOpsStore;$k=$Email.Trim().ToLowerInvariant();$before=Get-CodexAccountOps $Email
    $after=[PSCustomObject]@{state=$State;alias=$Alias;group=$Group;reason=$Reason;updatedUtc=[DateTime]::UtcNow.ToString("o")}
    $store[$k]=$after;Save-CodexAccountOpsStore $store
    $ev=[ordered]@{time=[DateTime]::UtcNow.ToString("o");account=$Email;action="OPS_STATE";before=$before;after=$after}
    Add-Content -LiteralPath $script:AccountOpsHistoryPath -Value ($ev| ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
    Add-CodexRouteHistory "ACCOUNT_OPS" ("$Email → $State") $Email
    return $after
}
function Get-CodexAccountOperationsRows {
    return @(Get-CodexAccountRecords|ForEach-Object{
        $m=Get-CodexAccountMeta $_.Email;$o=Get-CodexAccountOps $_.Email;$q=Get-CodexQuotaForEmail $_.Email
        [PSCustomObject]@{
            Account=$_.Email;Plan=$_.Plan;RouterStatus=$_.Status;OpsState=$o.state;Alias=$o.alias;Group=$o.group;
            Favorite=[bool]$m.favorite;Tag=$m.tag;Hourly=if($q){$q.hourlyRemaining}else{$null};Weekly=if($q){$q.weeklyRemaining}else{$null};
            Reason=$o.reason;Note=$m.note
        }
    })
}
function Export-CodexPoolMetadata {
    Ensure-Dir $script:PoolMetadataExportDir
    $dest=Join-Path $script:PoolMetadataExportDir ("pool-metadata-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".json")
    $rows=@(Get-CodexAccountRecords|ForEach-Object{
        $m=Get-CodexAccountMeta $_.Email;$o=Get-CodexAccountOps $_.Email
        [ordered]@{email=$_.Email;tag=$m.tag;note=$m.note;favorite=[bool]$m.favorite;ops_state=$o.state;alias=$o.alias;group=$o.group;reason=$o.reason}
    })
    Save-JsonAtomic $dest ([ordered]@{version=1;exportedUtc=[DateTime]::UtcNow.ToString("o");containsSecrets=$false;accounts=$rows})
    return $dest
}
function Import-CodexPoolMetadata {
    param([string]$Path)
    if(-not (Test-Path $Path)){throw "File import không tồn tại."}
    $j=Get-Content $Path -Raw -Encoding UTF8| ConvertFrom-Json
    if($j.containsSecrets -eq $true){throw "HMS từ chối import metadata file tự khai chứa secrets."}
    $known=@{};foreach($a in @(Get-CodexAccountRecords)){$known[$a.Email.ToLowerInvariant()]=$true}
    $applied=0;$skipped=0
    foreach($r in @($j.accounts)){
        $email=[string]$r.email;if((-not $email) -or (-not $known.ContainsKey($email.ToLowerInvariant()))){$skipped++;continue}
        $state=[string]$r.ops_state;if($state -notin @("ACTIVE","MAINTENANCE","QUARANTINED")){$state="ACTIVE"}
        Set-CodexAccountMeta $email ([string]$r.tag) ([string]$r.note) ([bool]$r.favorite)
        $null=Set-CodexAccountOps $email $state ([string]$r.alias) ([string]$r.group) ([string]$r.reason)
        $applied++
    }
    return "Import metadata PASS: applied=$applied skipped=$skipped"
}
function Invoke-CodexAccountSessionIndex {
    Ensure-Dir $script:SessionOpsExportDir
    $homes=@(Get-AllCodexHomes|Where-Object{$_.Home -and (Test-Path $_.Home)})
    if($homes.Count -eq 0){throw "Không tìm thấy CODEX_HOME."}
    $helper=Join-Path $PSScriptRoot "HMS_Codex_AccountSessionIndex.py"
    $tmp=Join-Path $env:TEMP ("hms-session-index-"+[Guid]::NewGuid().ToString("N")+".json")
    $args=[System.Collections.Generic.List[string]]::new();$args.Add($helper)
    foreach($h in $homes){$args.Add("--home");$args.Add([string]$h.Home)}
    if([bool]$script:S.SessionOpsIncludeArchived){$args.Add("--include-archived")}
    $args.Add("--max");$args.Add([string][int]$script:S.SessionOpsMaxRows)
    if(Test-Path $script:CodexAttributionPath){$args.Add("--attribution");$args.Add($script:CodexAttributionPath)}
    if(Test-Path $script:CodexRouteHistoryPath){$args.Add("--route-history");$args.Add($script:CodexRouteHistoryPath)}
    $args.Add("--output");$args.Add($tmp)
    $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList $args.ToArray() -Wait -PassThru -WindowStyle Hidden
    if(-not (Test-Path $tmp)){throw "AccountSessionIndex không tạo output. exit=$($p.ExitCode)"}
    try{$j=Get-Content $tmp -Raw -Encoding UTF8| ConvertFrom-Json}finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    if(-not $j.ok){throw[string]$j.error}
    Save-JsonAtomic $script:SessionOpsPath $j.data
    return $j.data
}
function Export-CodexSessionOps {
    $j=Load-JsonObjectSafe $script:SessionOpsPath;if(-not $j){$j=Invoke-CodexAccountSessionIndex}
    Ensure-Dir $script:SessionOpsExportDir
    $dest=Join-Path $script:SessionOpsExportDir ("sessions-redacted-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".json")
    $rows=@($j.sessions|ForEach-Object{
        [ordered]@{session_id=$_.session_id;kind=$_.kind;home=$_.home;provider=$_.provider;model=$_.model;project=$_.project;
        account=$_.account;confidence=$_.confidence;evidence=$_.evidence;mtime_utc=$_.mtime_utc}
    })
    Save-JsonAtomic $dest ([ordered]@{exportedUtc=[DateTime]::UtcNow.ToString("o");containsSecrets=$false;sessions=$rows})
    return $dest
}
function Show-CodexAccountSessionOperations {
    $w=New-Object Windows.Forms.Form;$w.Text="HMS Account & Session Operations v11.0";$w.Size=New-Object Drawing.Size(1450,840);$w.StartPosition="CenterParent";$w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="ACCOUNT & SESSION OPERATIONS";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,60);$tabs.Size=New-Object Drawing.Size(1390,700);$w.Controls.Add($tabs)
    foreach($n in @("Accounts","Sessions","History / Export","Safety")){$p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)}
    $pa=$tabs.TabPages[0];$psess=$tabs.TabPages[1];$ph=$tabs.TabPages[2];$psafe=$tabs.TabPages[3]
    $ga=New-DarkGrid 15 65 1325 540 $pa;$ga.MultiSelect=$true
    $bActive=Btn "ACTIVE" 15 15 105 34;$pa.Controls.Add($bActive);$bMaint=Btn "MAINTENANCE" 130 15 145 34;$pa.Controls.Add($bMaint);$bQ=Btn "QUARANTINE" 285 15 135 34;$pa.Controls.Add($bQ)
    $bFav=Btn "FAVORITE ON" 430 15 135 34;$pa.Controls.Add($bFav);$bUnFav=Btn "FAVORITE OFF" 575 15 135 34;$pa.Controls.Add($bUnFav);$bRefresh=Btn "REFRESH" 720 15 105 34;$pa.Controls.Add($bRefresh)
    $gs=New-DarkGrid 15 65 1325 540 $psess;$bScan=Btn "SCAN SESSIONS" 15 15 150 34;$psess.Controls.Add($bScan);$bExportSess=Btn "EXPORT REDACTED" 175 15 170 34;$psess.Controls.Add($bExportSess)
    $hist=New-Object Windows.Forms.TextBox;$hist.Location=New-Object Drawing.Point(15,65);$hist.Size=New-Object Drawing.Size(1325,500);$hist.Multiline=$true;$hist.ReadOnly=$true;$hist.ScrollBars="Both";$hist.WordWrap=$false;$hist.BackColor=[Drawing.Color]::FromArgb(20,23,27);$hist.ForeColor=$w.ForeColor;$ph.Controls.Add($hist)
    $bMetaEx=Btn "EXPORT POOL METADATA" 15 15 210 34;$ph.Controls.Add($bMetaEx);$bMetaIm=Btn "IMPORT METADATA" 235 15 170 34;$ph.Controls.Add($bMetaIm);$bHist=Btn "REFRESH HISTORY" 415 15 160 34;$ph.Controls.Add($bHist)
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1325,550);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor;$safe.Text="SAFETY`r`n`r`n• MAINTENANCE/QUARANTINED là HMS metadata overlay, không sửa/xóa OAuth auth JSON.`r`n• Fleet planner tránh account overlay bị loại, nhưng shared CLIProxyAPI pool vẫn giữ native routing/failover.`r`n• Session→account chỉ CONFIRMED nếu session payload có evidence trực tiếp.`r`n• PROBABLE chỉ dùng cho latest session + latest global route; các session khác giữ UNATTRIBUTED.`r`n• Metadata import chỉ áp vào account hiện đang có trong local auth pool.`r`n• Export không chứa access/refresh token.";$psafe.Controls.Add($safe)
    function Refresh-A{$ga.DataSource=$null;$ga.DataSource=@(Get-CodexAccountOperationsRows)}
    function Emails{if($ga.SelectedRows.Count -lt 1){throw"Chọn ít nhất một account."};return @($ga.SelectedRows|ForEach-Object{[string]$_.Cells["Account"].Value}|Where-Object{$_}|Select-Object-Unique)}
    function SetState([string]$st){foreach($e in @(Emails)){$o=Get-CodexAccountOps $e;$null=Set-CodexAccountOps $e $st ([string]$o.alias) ([string]$o.group) ([string]$o.reason)};Refresh-A}
    function SetFav([bool]$f){foreach($e in @(Emails)){$m=Get-CodexAccountMeta $e;Set-CodexAccountMeta $e ([string]$m.tag) ([string]$m.note) $f};Refresh-A}
    function Refresh-S{$j=Invoke-CodexAccountSessionIndex;$gs.DataSource=$null;$gs.DataSource=@($j.sessions|ForEach-Object{[PSCustomObject]@{Session=$_.session_id;Kind=$_.kind;Account=$_.account;Confidence=$_.confidence;Provider=$_.provider;Model=$_.model;Project=$_.project;Updated=$_.mtime_utc}})}
    function Refresh-H{$lines=[System.Collections.Generic.List[string]]::new();if(Test-Path $script:AccountOpsHistoryPath){$lines.Add("ACCOUNT OPS HISTORY");$lines.AddRange([string[]]@(Get-Content $script:AccountOpsHistoryPath -Tail 300 -Encoding UTF8))};if(Test-Path $script:CodexRouteHistoryPath){$lines.Add("");$lines.Add("ROUTE HISTORY");$lines.AddRange([string[]]@(Get-Content $script:CodexRouteHistoryPath -Tail 300 -Encoding UTF8))};$hist.Text=$lines -join "`r`n"}
    $bActive.Add_Click({try{SetState "ACTIVE"}catch{}});$bMaint.Add_Click({try{SetState "MAINTENANCE"}catch{}});$bQ.Add_Click({try{SetState "QUARANTINED"}catch{}})
    $bFav.Add_Click({try{SetFav $true}catch{}});$bUnFav.Add_Click({try{SetFav $false}catch{}});$bRefresh.Add_Click({Refresh-A})
    $bScan.Add_Click({try{Refresh-S}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}});$bExportSess.Add_Click({try{[Windows.Forms.MessageBox]::Show((Export-CodexSessionOps),"Export")|Out-Null}catch{}})
    $bMetaEx.Add_Click({try{[Windows.Forms.MessageBox]::Show((Export-CodexPoolMetadata),"Export")|Out-Null}catch{}})
    $bMetaIm.Add_Click({$fd=New-Object Windows.Forms.OpenFileDialog;$fd.Filter="JSON (*.json)|*.json";if($fd.ShowDialog() -eq [Windows.Forms.DialogResult]::OK){try{$a=[Windows.Forms.MessageBox]::Show("Import chỉ cập nhật metadata HMS cho account hiện có. Tiếp tục?","IMPORT",[Windows.Forms.MessageBoxButtons]::YesNo);if($a -eq [Windows.Forms.DialogResult]::Yes){[Windows.Forms.MessageBox]::Show((Import-CodexPoolMetadata $fd.FileName),"Import")|Out-Null;Refresh-A}}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}}})
    $bHist.Add_Click({Refresh-H});$w.Add_Shown({Refresh-A;Refresh-H});[void]$w.ShowDialog($form)
}


# ============================================================
# ROUTER INTELLIGENCE v12.0
# Explain eligible pool / actual attribution / routing strategy
# ============================================================
function Get-CodexRouterIntelAccountRows {
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($a in @(Get-CodexAccountRecords)){
        $ops=Get-CodexAccountOps $a.Email
        $ha=@(Get-CodexHaAccountState $a.Email)
        $q=Get-CodexQuotaForEmail $a.Email
        $h=Get-CodexAccountHealth $a
        $rows.Add([PSCustomObject]@{
            email=$a.Email
            router_status=$a.Status
            ops_state=[string]$ops.state
            circuit=if($ha.Count){[string]$ha[0].state}else{"CLOSED"}
            health=[int]$h.Score
            hourly=if($q -and $null -ne $q.hourlyRemaining){[int]$q.hourlyRemaining}else{$null}
            weekly=if($q -and $null -ne $q.weeklyRemaining){[int]$q.weeklyRemaining}else{$null}
            priority=$a.Priority
            weight=$a.Weight
            reset=$a.Reset
            plan=$a.Plan
        })
    }
    return @($rows)
}
function Invoke-CodexRouterIntelligence {
    Ensure-Dir $script:RouterIntelExportDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_RouterIntelligence.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_RouterIntelligence.py"}
    $input=Join-Path $env:TEMP ("hms-router-intel-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-router-intel-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $attr=$null
        $aj=Load-JsonObjectSafe $script:CodexAttributionPath
        if($aj){$attr=$aj.latest_attribution}
        $logEvents=@(Get-CodexRouteEventsFromLogs -Max 300|ForEach-Object{
            [ordered]@{type=$_.Type;account=$_.Account;message=$_.Message}
        })
        $obj=[ordered]@{
            profile=[string]$script:S.CodexRoutingProfile
            affinity_ttl=[string]$script:S.CodexSessionAffinityTtl
            window_minutes=[int]$script:S.RouterIntelRecentWindowMinutes
            max_events=[int]$script:S.RouterIntelMaxTimelineEvents
            accounts=@(Get-CodexRouterIntelAccountRows)
            active_attribution=$attr
            history=$script:CodexRouteHistoryPath
            log_events=$logEvents
        }
        Save-Json $input $obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @($helper,"--input",$input,"--output",$output) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "RouterIntelligence không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        Save-JsonAtomic $script:RouterIntelPath $j.data
        $hist=[ordered]@{time=[DateTime]::UtcNow.ToString("o");strategy=$j.data.strategy;totals=$j.data.totals;active_route=$j.data.active_route}
        Add-Content -LiteralPath $script:RouterIntelHistoryPath -Value ($hist| ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
        return $j.data
    }finally{Remove-Item $input,$output -Force -ErrorAction SilentlyContinue}
}
function Export-CodexRouterIntelligence {
    $j=Load-JsonObjectSafe $script:RouterIntelPath
    if(-not $j){$j=Invoke-CodexRouterIntelligence}
    Ensure-Dir $script:RouterIntelExportDir
    $dest=Join-Path $script:RouterIntelExportDir ("router-intelligence-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".json")
    $safe=[ordered]@{
        exportedUtc=[DateTime]::UtcNow.ToString("o")
        containsSecrets=$false
        strategy=$j.strategy
        active_route=$j.active_route
        totals=$j.totals
        accounts=@($j.accounts|ForEach-Object{
            [ordered]@{
                email=$_.email;router_status=$_.router_status;ops_state=$_.ops_state;circuit=$_.circuit;health=$_.health;
                hourly=$_.hourly;weekly=$_.weekly;priority=$_.priority;weight=$_.weight;eligible=$_.eligible;
                eligibility_reason=$_.eligibility_reason;recent_confirmed_routes=$_.recent_confirmed_routes;
                recent_failovers=$_.recent_failovers;recent_cooldowns=$_.recent_cooldowns;last_seen=$_.last_seen
            }
        })
        decision_explanation=$j.decision_explanation
    }
    Save-JsonAtomic $dest $safe
    return $dest
}
function Get-CodexRouterIntelSummary {
    $j=Load-JsonObjectSafe $script:RouterIntelPath
    if(-not $j){return "Router Intelligence chưa có snapshot."}
    $a=$j.active_route
    $route=if($a -and $a.account){"$($a.account) [$($a.confidence)]"}else{"UNATTRIBUTED"}
    return "Strategy=$($j.strategy.strategy); affinity=$($j.strategy.session_affinity); eligible=$($j.totals.eligible)/$($j.totals.accounts); route=$route; failovers=$($j.totals.failovers); cooldowns=$($j.totals.cooldowns)"
}
function Show-CodexRouterIntelligenceCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Router Intelligence v12.0"
    $w.Size=New-Object Drawing.Size(1480,860);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="MULTI-ACCOUNT ROUTER INTELLIGENCE";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,52);$status.Size=New-Object Drawing.Size(1050,48);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bRefresh=Btn "REFRESH INTELLIGENCE" 1080 18 190 36;$w.Controls.Add($bRefresh)
    $bExport=Btn "EXPORT REDACTED" 1280 18 160 36;$w.Controls.Add($bExport)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1420,680);$w.Controls.Add($tabs)
    foreach($n in @("Live Pool Map","Decision Explanation","Timeline","Routing Config","Safety")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $gp=New-DarkGrid 15 20 1355 555 $tabs.TabPages[0]
    $decision=New-Object Windows.Forms.TextBox;$decision.Location=New-Object Drawing.Point(15,20);$decision.Size=New-Object Drawing.Size(1355,555);$decision.Multiline=$true;$decision.ReadOnly=$true;$decision.ScrollBars="Both";$decision.WordWrap=$true;$decision.BackColor=[Drawing.Color]::FromArgb(20,23,27);$decision.ForeColor=$w.ForeColor;$tabs.TabPages[1].Controls.Add($decision)
    $gt=New-DarkGrid 15 20 1355 555 $tabs.TabPages[2]
    $config=New-Object Windows.Forms.TextBox;$config.Location=New-Object Drawing.Point(15,20);$config.Size=New-Object Drawing.Size(1355,555);$config.Multiline=$true;$config.ReadOnly=$true;$config.ScrollBars="Both";$config.WordWrap=$false;$config.BackColor=[Drawing.Color]::FromArgb(20,23,27);$config.ForeColor=$w.ForeColor;$tabs.TabPages[3].Controls.Add($config)
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1355,555);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor;$safe.Text="ROUTER INTELLIGENCE SAFETY`r`n`r`n• ACTIVE ROUTE chỉ theo evidence hiện có.`r`n• CONFIRMED/PROBABLE/UNATTRIBUTED không bị trộn lẫn.`r`n• HMS không dự đoán chắc chắn account kế tiếp khi session-affinity có thể giữ binding.`r`n• Eligible Pool là HMS view để giải thích trạng thái, không phải bằng chứng CLIProxyAPI đã chọn account đó.`r`n• Shared router vẫn dùng native round-robin/session-affinity/failover.`r`n• v12 không đổi thuật toán routing mặc định.`r`n• MAINTENANCE/QUARANTINED/CIRCUIT_OPEN chỉ được giải thích rõ trong HMS control plane.";$tabs.TabPages[4].Controls.Add($safe)

    function Refresh-Intel {
        try{
            $j=Invoke-CodexRouterIntelligence
            $gp.DataSource=$null
            $gp.DataSource=@($j.accounts|ForEach-Object{
                [PSCustomObject]@{
                    Account=$_.email;Router=$_.router_status;Ops=$_.ops_state;Circuit=$_.circuit;Eligible=$_.eligible;
                    Reason=$_.eligibility_reason;"5h"=$_.hourly;Weekly=$_.weekly;Health=$_.health;Priority=$_.priority;Weight=$_.weight;
                    RecentRoutes=$_.recent_confirmed_routes;Failovers=$_.recent_failovers;Cooldowns=$_.recent_cooldowns;LastSeen=$_.last_seen
                }
            })
            $gt.DataSource=$null;$gt.DataSource=@($j.timeline|ForEach-Object{[PSCustomObject]@{Time=$_.time;Type=$_.type;Account=$_.account;Message=$_.message}})
            $decision.Text="ACTIVE ROUTE`r`n-------------`r`n"+$(if($j.active_route.account){"$($j.active_route.account) [$($j.active_route.confidence)]`r`nEvidence: $($j.active_route.evidence)"}else{"UNATTRIBUTED"})+"`r`n`r`nELIGIBLE POOL`r`n-------------`r`n"+(@($j.eligible_accounts)-join"`r`n")+"`r`n`r`nDECISION EXPLANATION`r`n--------------------`r`n$($j.decision_explanation)"
            $config.Text=(Get-CodexConfigAudit)+"`r`n`r`nINTELLIGENCE INTERPRETATION`r`n---------------------------`r`nStrategy: $($j.strategy.strategy)`r`nSession affinity: $($j.strategy.session_affinity)`r`nTTL: $($j.strategy.ttl)`r`n$($j.strategy.explanation)"
            $status.Text=Get-CodexRouterIntelSummary
        }catch{$status.Text="Router Intelligence error: "+$_.Exception.Message}
    }
    $bRefresh.Add_Click({Refresh-Intel})
    $bExport.Add_Click({try{[Windows.Forms.MessageBox]::Show((Export-CodexRouterIntelligence),"Export")|Out-Null}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=[Math]::Max(3000,[int]$script:S.RouterIntelAutoRefreshSec*1000);$tm.Add_Tick({Refresh-Intel});$tm.Start()
    $w.Add_Shown({Refresh-Intel});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# ACCOUNT POOL AUTOMATION & RECOVERY v13.0
# Audit-first reconciliation for shared pool and isolated instances
# ============================================================
function Invoke-CodexPoolReconcileAudit {
    Ensure-Dir $script:PoolReconcileDir
    Ensure-Dir $script:PoolReconcileBackupDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_PoolReconciler.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_PoolReconciler.py"}
    $input=Join-Path $env:TEMP ("hms-pool-reconcile-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-pool-reconcile-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $obj=[ordered]@{
            shared_auth_dir=[string]$script:AuthDir
            previous_snapshot=if(Test-Path $script:PoolReconcileSnapshotPath){$script:PoolReconcileSnapshotPath}else{$null}
            clock_skew_seconds=[int]$script:S.PoolReconcileClockSkewSeconds
            instances=@((Get-CodexInstanceStore).instances)
        }
        Save-Json $input $obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @($helper,"--input",$input,"--output",$output) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "PoolReconciler không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        Save-JsonAtomic $script:PoolReconcileLatestPath $j.data
        Save-JsonAtomic $script:PoolReconcileSnapshotPath ([ordered]@{
            capturedUtc=[DateTime]::UtcNow.ToString("o")
            shared_accounts=@($j.data.shared_accounts)
            instances=@($j.data.instances)
        })
        $h=[ordered]@{time=[DateTime]::UtcNow.ToString("o");summary=$j.data.summary;changes=$j.data.changes}
        Add-Content -LiteralPath $script:PoolReconcileHistoryPath -Value ($h| ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
        return $j.data
    }finally{Remove-Item $input,$output -Force -ErrorAction SilentlyContinue}
}
function Test-CodexInstanceFullyStopped {
    param([object]$Instance)
    if(-not $Instance){return $false}
    if(Test-CodexInstanceClientOwned $Instance){return $false}
    if(Test-CodexInstanceRouterOwned $Instance){return $false}
    if([int]$Instance.port -gt 0 -and (ListenerPid ([int]$Instance.port)) -gt 0){return $false}
    return $true
}
function Sync-CodexInstanceCredentialSafe {
    param([string]$InstanceId)
    $audit=Load-JsonObjectSafe $script:PoolReconcileLatestPath
    if(-not $audit){$audit=Invoke-CodexPoolReconcileAudit}
    $row=@($audit.instances|Where-Object id -eq $InstanceId| Select-Object -First 1)
    if($row.Count -eq 0){throw "Không có reconcile row cho instance $InstanceId."}
    $r=$row[0]
    if([string]$r.recommendation -notin @("COPY_FROM_SHARED","SYNC_FROM_SHARED")){throw "Reconcile recommendation=$($r.recommendation). HMS không tự ghi đè trường hợp cần REVIEW."}
    $store=Get-CodexInstanceStore
    $inst=@($store.instances|Where-Object id -eq $InstanceId| Select-Object -First 1)
    if($inst.Count -eq 0){throw "Instance không tồn tại."}
    $i=$inst[0]
    if([bool]$script:S.PoolReconcileRequireStoppedInstance -and -not (Test-CodexInstanceFullyStopped $i)){throw "Instance/client/router phải STOP hoàn toàn trước khi sync credential."}
    $acc=@(Get-CodexAccountRecords|Where-Object Email -eq ([string]$i.accountEmail)| Select-Object -First 1)
    if($acc.Count -eq 0){throw "Bound account không còn trong shared pool: $($i.accountEmail)"}

    $authDir=Join-Path $i.routerDir "auth";Ensure-Dir $authDir
    $archive=Join-Path $authDir ("reconcile-"+(Get-Date -Format "yyyyMMdd-HHmmss-fff")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8))
    Ensure-Dir $archive
    $existing=@(Get-ChildItem $authDir -File -Filter "codex-*.json" -ErrorAction SilentlyContinue)
    foreach($f in $existing){Copy-Item $f.FullName (Join-Path $archive ("backup-"+$f.Name)) -Force}

    $source=$acc[0].File.FullName
    $final=Join-Path $authDir $acc[0].File.Name
    $tmp=$final+".tmp-"+[Guid]::NewGuid().ToString("N")
    try{
        Copy-Item $source $tmp -Force
        $srcHash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
        $tmpHash=(Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash
        if($srcHash -ne $tmpHash){throw "Credential temp copy hash mismatch."}
        foreach($f in $existing){Move-Item $f.FullName (Join-Path $archive $f.Name) -Force}
        Move-Item $tmp $final -Force
        $finalHash=(Get-FileHash -LiteralPath $final -Algorithm SHA256).Hash
        if($finalHash -ne $srcHash){throw "Credential final hash mismatch."}
    }catch{
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        foreach($b in @(Get-ChildItem $archive -File -Filter "backup-codex-*.json" -ErrorAction SilentlyContinue)){
            $name=$b.Name.Substring(7)
            try{Copy-Item $b.FullName (Join-Path $authDir $name) -Force}catch{}
        }
        throw
    }
    $null=Invoke-HmsBoundedInstanceBackupRetention -Root $authDir -Pattern 'reconcile-*' -Keep ([Math]::Max(1,[int]$script:S.CodexBehaviorBackupKeepPerSourceInstance))
    Add-CodexRouteHistory "POOL_RECONCILE" ("Sync credential PASS: $($i.name) ← $($i.accountEmail)") ([string]$i.accountEmail)
    return "SYNC PASS: $($i.name) ← $($i.accountEmail)`r`nArchive: $archive"
}
function Get-CodexPoolReconcileRows {
    $j=Load-JsonObjectSafe $script:PoolReconcileLatestPath
    if(-not $j){return @()}
    return @($j.instances|ForEach-Object{
        [PSCustomObject]@{
            Id=$_.id;Instance=$_.name;BoundAccount=$_.bound_account;Status=$_.status;Recommendation=$_.recommendation;
            Reason=$_.reason;ClientPid=$_.client_pid;RouterPid=$_.router_pid;AuthDir=$_.auth_dir
        }
    })
}
function Show-CodexPoolRecoveryCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Account Pool Automation & Recovery v13.0"
    $w.Size=New-Object Drawing.Size(1480,860);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="ACCOUNT POOL AUTOMATION & RECOVERY";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $sum=New-Object Windows.Forms.Label;$sum.Location=New-Object Drawing.Point(20,52);$sum.Size=New-Object Drawing.Size(1040,48);$sum.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($sum)
    $bAudit=Btn "AUDIT POOL" 1080 18 130 36;$w.Controls.Add($bAudit)
    $bSync=Btn "SYNC SELECTED SAFE" 1220 18 190 36;$w.Controls.Add($bSync)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1420,680);$w.Controls.Add($tabs)
    foreach($n in @("Reconciliation","Shared Pool Changes","Cooldown Lifecycle","Safety")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $gr=New-DarkGrid 15 20 1355 555 $tabs.TabPages[0]
    $changes=New-Object Windows.Forms.TextBox;$changes.Location=New-Object Drawing.Point(15,20);$changes.Size=New-Object Drawing.Size(1355,555);$changes.Multiline=$true;$changes.ReadOnly=$true;$changes.ScrollBars="Both";$changes.WordWrap=$false;$changes.BackColor=[Drawing.Color]::FromArgb(20,23,27);$changes.ForeColor=$w.ForeColor;$tabs.TabPages[1].Controls.Add($changes)
    $gc=New-DarkGrid 15 20 1355 555 $tabs.TabPages[2]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1355,555);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="POOL RECOVERY SAFETY`r`n`r`n• Audit mặc định read-only.`r`n• Không xóa shared OAuth/auth file.`r`n• Child credential mới hơn shared → CONFLICT_CHILD_NEWER / REVIEW, không overwrite.`r`n• Drift mơ hồ → REVIEW.`r`n• Chỉ COPY/SYNC khi recommendation cho phép.`r`n• Client + child router + port phải STOP trước khi sync.`r`n• Credential cũ được archive bằng UTC millisecond + GUID.`r`n• Temp copy được SHA-256 verify trước khi activate.`r`n• Nếu commit lỗi, HMS cố restore từ backup.`r`n• Không đụng Cockpit/foreign listener.";$tabs.TabPages[3].Controls.Add($safe)

    function Refresh-R {
        try{
            $j=Invoke-CodexPoolReconcileAudit
            $gr.DataSource=$null;$gr.DataSource=@(Get-CodexPoolReconcileRows)
            $gc.DataSource=$null;$gc.DataSource=@($j.cooldowns|ForEach-Object{[PSCustomObject]@{Account=$_.email;Until=$_.until_utc;State=$_.state}})
            $changes.Text="NEW ACCOUNTS`r`n------------`r`n"+(@($j.changes.new_accounts)-join"`r`n")+"`r`n`r`nREMOVED ACCOUNTS`r`n----------------`r`n"+(@($j.changes.removed_accounts)-join"`r`n")
            $sum.Text="Shared=$($j.summary.shared_accounts)   Instances=$($j.summary.instances)   Problems=$($j.summary.problems)   New=$($j.summary.new_accounts)   Removed=$($j.summary.removed_accounts)"
        }catch{$sum.Text="Pool audit error: "+$_.Exception.Message}
    }
    $bAudit.Add_Click({Refresh-R})
    $bSync.Add_Click({
        try{
            if($gr.SelectedRows.Count -lt 1){throw "Chọn một instance reconcile row."}
            $id=[string]$gr.SelectedRows[0].Cells["Id"].Value
            $rec=[string]$gr.SelectedRows[0].Cells["Recommendation"].Value
            if($rec -notin @("COPY_FROM_SHARED","SYNC_FROM_SHARED")){throw "Recommendation=$rec; HMS chỉ sync các case an toàn."}
            $a=[Windows.Forms.MessageBox]::Show("Sync credential shared → child instance đã STOP. Credential child cũ sẽ được archive, không xóa.`r`n`r`nTiếp tục?","POOL RECONCILE",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
            if($a -ne [Windows.Forms.DialogResult]::Yes){return}
            [Windows.Forms.MessageBox]::Show((Sync-CodexInstanceCredentialSafe $id),"Pool Reconcile")|Out-Null
            Refresh-R
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,"Pool Reconcile")|Out-Null}
    })
    $w.Add_Shown({Refresh-R})
    [void]$w.ShowDialog($form)
}


# ============================================================
# LONG-RUNNING RELIABILITY & SOAK ENGINE v14.0
# 1h / 6h / 24h observation with resume/checkpoint/certificate
# ============================================================
function Get-HmsSoakProfileSeconds {
    param([string]$Profile)
    switch($Profile){
        "QUICK_1H" { return 3600 }
        "STANDARD_6H" { return 21600 }
        "PROD_24H" { return 86400 }
        default { return 3600 }
    }
}
function Get-HmsSoakState {
    $j=Load-JsonObjectSafe $script:SoakStatePath
    if(-not $j){return [PSCustomObject]@{active=$false;profile="";runId="";startedUtc=$null;targetSeconds=0;samplesPath="";runDir=""}}
    return $j
}
function Get-HmsDirectorySizeMb {
    param([string]$Path)
    if(-not (Test-Path $Path)){return 0.0}
    try{
        $sum=0L
        foreach($f in @(Get-ChildItem $Path -File -Recurse -ErrorAction SilentlyContinue)){
            if($f.FullName -like ($script:SoakDir+"*")){continue}
            $sum+=[int64]$f.Length
        }
        return [Math]::Round($sum/1MB,3)
    }catch{return 0.0}
}
function Get-HmsSoakEventTotals {
    $tot=[ordered]@{RECOVERY=0;FAILOVER=0;RETRY=0;COOLDOWN=0;ERROR=0}
    if(Test-Path $script:CodexRouteHistoryPath){
        foreach($line in @(Get-Content $script:CodexRouteHistoryPath -Tail 5000 -Encoding UTF8 -ErrorAction SilentlyContinue)){
            try{
                $j=$line| ConvertFrom-Json
                $t=([string]$j.type).ToUpperInvariant()
                if($t -like "*RECOVERY*"){$tot.RECOVERY++}
                if($t -like "*FAILOVER*"){$tot.FAILOVER++}
                if($t -like "*RETRY*"){$tot.RETRY++}
                if($t -like "*COOLDOWN*"){$tot.COOLDOWN++}
                if($t -like "*ERROR*"){$tot.ERROR++}
            }catch{}
        }
    }
    return $tot
}
function Start-HmsSoakRun {
    param([ValidateSet("QUICK_1H","STANDARD_6H","PROD_24H")][string]$Profile="QUICK_1H")
    Ensure-Dir $script:SoakDir
    Ensure-Dir $script:SoakArchiveDir
    $existing=Get-HmsSoakState
    if([bool]$existing.active){throw "Đang có soak run active: $($existing.runId)"}
    $runId=(Get-Date -Format "yyyyMMdd-HHmmss")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8)
    $runDir=Join-Path $script:SoakDir ("run-"+$runId)
    Ensure-Dir $runDir
    $state=[ordered]@{
        version=14
        active=$true
        profile=$Profile
        runId=$runId
        runDir=$runDir
        startedUtc=[DateTime]::UtcNow.ToString("o")
        stoppedUtc=$null
        stopReason=$null
        targetSeconds=(Get-HmsSoakProfileSeconds $Profile)
        samplesPath=(Join-Path $runDir "samples.jsonl")
        analysisPath=(Join-Path $runDir "analysis.json")
        certificatePath=(Join-Path $runDir "certificate.json")
        sampleCount=0
        lastSampleUtc=$null
    }
    Save-JsonAtomic $script:SoakStatePath $state
    Add-CodexRouteHistory "SOAK_START" ("Soak $Profile / $runId") ""
    $null=Add-HmsSoakSample
    return $state
}
function Stop-HmsSoakRun {
    param([string]$Reason="operator_stop")
    $state=Get-HmsSoakState
    if(-not [bool]$state.active){return "Không có soak run active."}
    $state.active=$false
    $state.stoppedUtc=[DateTime]::UtcNow.ToString("o")
    $state.stopReason=$Reason
    Save-JsonAtomic $script:SoakStatePath $state
    Add-CodexRouteHistory "SOAK_STOP" ("Soak $($state.runId) / $Reason") ""
    return "Soak đã STOP: $($state.runId)"
}
function Add-HmsSoakSample {
    $state=Get-HmsSoakState
    if(-not [bool]$state.active){return $null}
    $procId=ListenerPid ([int]$script:S.ProxyPort)
    $owned=$false
    if($procId -gt 0){try{$owned=IsOurProxy $procId}catch{}}
    $pool=$null;$sla=$null;$tel=@()
    try{$pool=Get-CodexPoolSummary}catch{}
    try{$sla=Get-CodexFleetSla}catch{}
    try{$tel=@(Get-CodexTelemetryRows)}catch{}
    $ram=0.0
    foreach($r in $tel){try{$ram+=[double]$r.RAM_MB}catch{}}
    $sample=[ordered]@{
        time=[DateTime]::UtcNow.ToString("o")
        router_online=($procId -gt 0)
        router_owned=[bool]$owned
        router_pid=$procId
        pool_total=if($pool){[int]$pool.Total}else{0}
        pool_ready=if($pool){[int]$pool.Ready}else{0}
        pool_cooldown=if($pool){[int]$pool.Cooldown}else{0}
        sla_score=if($sla){[int]$sla.Score}else{$null}
        sla_state=if($sla){[string]$sla.State}else{"UNKNOWN"}
        instances_running=if($sla){[int]$sla.InstancesRunning}else{0}
        routers_online=if($sla){[int]$sla.RoutersOnline}else{0}
        total_ram_mb=[Math]::Round($ram,2)
        state_size_mb=(Get-HmsDirectorySizeMb $script:DataDir)
        event_totals=(Get-HmsSoakEventTotals)
    }
    Add-Content -LiteralPath ([string]$state.samplesPath) -Value ($sample| ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
    $state.sampleCount=[int]$state.sampleCount+1
    $state.lastSampleUtc=$sample.time
    Save-JsonAtomic $script:SoakStatePath $state
    $analysis=Invoke-HmsSoakAnalysis
    if([bool]$script:S.SoakAutoCertificate -and [string]$analysis.verdict -in @("PASS","WARN","FAIL")){
        try{$null=Publish-HmsSoakCertificate}catch{}
    }
    return $sample
}
function Invoke-HmsSoakAnalysis {
    $state=Get-HmsSoakState
    if(-not $state.runDir){throw "Chưa có soak run."}
    $helper=Join-Path $PSScriptRoot "HMS_Codex_SoakAnalyzer.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_SoakAnalyzer.py"}
    $cfgPath=Join-Path $env:TEMP ("hms-soak-cfg-"+[Guid]::NewGuid().ToString("N")+".json")
    $outPath=Join-Path $env:TEMP ("hms-soak-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $cfg=[ordered]@{
            sample_interval_sec=[int]$script:S.SoakSampleIntervalSec
            router_offline_critical_samples=[int]$script:S.SoakRouterOfflineCriticalSamples
            pool_ready_zero_critical_samples=[int]$script:S.SoakPoolReadyZeroCriticalSamples
            recovery_loop_window_minutes=[int]$script:S.SoakRecoveryLoopWindowMinutes
            recovery_loop_critical_count=[int]$script:S.SoakRecoveryLoopCriticalCount
            ram_growth_warn_mb_per_hour=[double]$script:S.SoakRamGrowthWarnMbPerHour
            state_growth_warn_mb_per_hour=[double]$script:S.SoakStateGrowthWarnMbPerHour
        }
        Save-Json $cfgPath $cfg
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $helper,"--samples",[string]$state.samplesPath,"--state",$script:SoakStatePath,"--config",$cfgPath,"--output",$outPath
        ) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $outPath)){throw "SoakAnalyzer không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $outPath -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw[string]$j.error}
        Save-JsonAtomic ([string]$state.analysisPath) $j.data
        Save-JsonAtomic $script:SoakLatestAnalysisPath $j.data
        return $j.data
    }finally{Remove-Item $cfgPath,$outPath -Force -ErrorAction SilentlyContinue}
}
function Publish-HmsSoakCertificate {
    $state=Get-HmsSoakState
    $analysis=Invoke-HmsSoakAnalysis
    if([string]$analysis.verdict -eq "IN_PROGRESS"){throw "Soak chưa đủ thời lượng; không cấp certificate."}
    if([string]$analysis.verdict -eq "BLOCKED"){throw "Soak bị BLOCKED; không cấp certificate."}
    $cert=[ordered]@{
        product="HMS-AI-ROUTER"
        version=$script:Version
        runId=$state.runId
        profile=$state.profile
        startedUtc=$state.startedUtc
        generatedUtc=[DateTime]::UtcNow.ToString("o")
        targetSeconds=$state.targetSeconds
        verdict=$analysis.verdict
        progressPct=$analysis.progressPct
        metrics=$analysis.metrics
        findings=$analysis.findings
    }
    Save-JsonAtomic ([string]$state.certificatePath) $cert
    Save-JsonAtomic $script:SoakCertificatePath $cert
    $txt="HMS-AI-ROUTER v$($script:Version)`r`nSOAK CERTIFICATE: $($cert.verdict)`r`nProfile: $($cert.profile)`r`nRun: $($cert.runId)`r`nProgress: $($cert.progressPct)%`r`nSamples: $($cert.metrics.samples)`r`nRouter Offline Longest Run: $($cert.metrics.routerOfflineLongestRun)`r`nRAM Growth MB/h: $($cert.metrics.ramGrowthMbPerHour)`r`nState Growth MB/h: $($cert.metrics.stateGrowthMbPerHour)"
    Set-Content -LiteralPath $script:SoakCertificateTextPath -Value $txt -Encoding UTF8
    return $cert
}
function Show-HmsSoakCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Long-Running Reliability & Soak v14.0"
    $w.Size=New-Object Drawing.Size(1420,830);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label;$title.Text="LONG-RUNNING RELIABILITY & SOAK";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $profile=New-Object Windows.Forms.ComboBox;$profile.DropDownStyle="DropDownList";$profile.Location=New-Object Drawing.Point(20,58);$profile.Size=New-Object Drawing.Size(190,28);foreach($x in @("QUICK_1H","STANDARD_6H","PROD_24H")){[void]$profile.Items.Add($x)};$profile.SelectedItem=[string]$script:S.SoakDefaultProfile;$w.Controls.Add($profile)
    $bStart=Btn "START" 225 54 110 34;$w.Controls.Add($bStart)
    $bStop=Btn "STOP" 345 54 100 34;$w.Controls.Add($bStop)
    $bSample=Btn "SAMPLE NOW" 455 54 135 34;$w.Controls.Add($bSample)
    $bAnalyze=Btn "ANALYZE" 600 54 120 34;$w.Controls.Add($bAnalyze)
    $bCert=Btn "CERTIFICATE" 730 54 130 34;$w.Controls.Add($bCert)
    $bOpen=Btn "OPEN RUN DIR" 870 54 140 34;$w.Controls.Add($bOpen)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(1030,48);$status.Size=New-Object Drawing.Size(340,48);$status.Font=New-Object Drawing.Font("Segoe UI Semibold",11);$w.Controls.Add($status)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,105);$tabs.Size=New-Object Drawing.Size(1360,640);$w.Controls.Add($tabs)
    foreach($n in @("Analysis","Findings","Recent Samples","Safety")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $analysisBox=New-Object Windows.Forms.TextBox;$analysisBox.Location=New-Object Drawing.Point(15,20);$analysisBox.Size=New-Object Drawing.Size(1295,520);$analysisBox.Multiline=$true;$analysisBox.ReadOnly=$true;$analysisBox.ScrollBars="Both";$analysisBox.WordWrap=$false;$analysisBox.BackColor=[Drawing.Color]::FromArgb(20,23,27);$analysisBox.ForeColor=$w.ForeColor;$tabs.TabPages[0].Controls.Add($analysisBox)
    $gf=New-DarkGrid 15 20 1295 520 $tabs.TabPages[1]
    $gs=New-DarkGrid 15 20 1295 520 $tabs.TabPages[2]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1295,520);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="SOAK SAFETY`r`n`r`n• Soak chỉ quan sát; không tự crash/restart/ép failover.`r`n• Mỗi run có thư mục riêng, không truncate run cũ.`r`n• State global chỉ trỏ tới run hiện tại/gần nhất.`r`n• Certificate chỉ cấp khi đủ thời lượng.`r`n• IN_PROGRESS không bị giả thành PASS.`r`n• 1h / 6h / 24h dùng cùng engine nhưng targetSeconds khác nhau.`r`n• Nếu HMS đóng/mở lại, state vẫn giữ active và timer tiếp tục lấy mẫu.`r`n• Memory/state growth chỉ là chỉ báo trend, cần runtime thật để kết luận leak.";$tabs.TabPages[3].Controls.Add($safe)

    function Refresh-S {
        $st=Get-HmsSoakState
        if(-not $st.runId){$status.Text="Chưa có soak run.";return}
        $a=Load-JsonObjectSafe ([string]$st.analysisPath)
        if(-not $a){try{$a=Invoke-HmsSoakAnalysis}catch{}}
        if($a){
            $status.Text="$($st.profile) · $($a.verdict) · $($a.progressPct)% · samples=$($a.metrics.samples)"
            $analysisBox.Text=$a| ConvertTo-Json -Depth 10
            $gf.DataSource=$null;$gf.DataSource=@($a.findings|ForEach-Object{[PSCustomObject]@{Severity=$_.severity;Code=$_.code;Message=$_.message}})
        }else{$status.Text="$($st.profile) · active=$($st.active)"}
        if(Test-Path ([string]$st.samplesPath)){
            $rows=[System.Collections.Generic.List[object]]::new()
            foreach($line in @(Get-Content ([string]$st.samplesPath) -Tail 200 -Encoding UTF8 -ErrorAction SilentlyContinue)){
                try{
                    $j=$line| ConvertFrom-Json
                    $rows.Add([PSCustomObject]@{Time=$j.time;Router=$j.router_online;Ready=("$($j.pool_ready)/$($j.pool_total)");SLA=$j.sla_score;RAM_MB=$j.total_ram_mb;State_MB=$j.state_size_mb})
                }catch{}
            }
            $gs.DataSource=$null;$gs.DataSource=@($rows)
        }
    }
    $bStart.Add_Click({try{$st=Start-HmsSoakRun ([string]$profile.SelectedItem);Refresh-S}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bStop.Add_Click({try{[Windows.Forms.MessageBox]::Show((Stop-HmsSoakRun "operator_stop"),"Soak")|Out-Null;Refresh-S}catch{}})
    $bSample.Add_Click({try{$null=Add-HmsSoakSample;Refresh-S}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bAnalyze.Add_Click({try{$null=Invoke-HmsSoakAnalysis;Refresh-S}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bCert.Add_Click({try{$c=Publish-HmsSoakCertificate;[Windows.Forms.MessageBox]::Show("Certificate: $($c.verdict)","Soak")|Out-Null;Refresh-S}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bOpen.Add_Click({$st=Get-HmsSoakState;if($st.runDir -and (Test-Path ([string]$st.runDir))){Start-Process explorer.exe ([string]$st.runDir)|Out-Null}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=5000;$tm.Add_Tick({Refresh-S});$tm.Start()
    $w.Add_Shown({Refresh-S});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# OBSERVABILITY & PERFORMANCE ANALYTICS v15.0
# P50/P95/P99 + trends + anomalies + self-contained HTML report
# ============================================================
function Get-HmsPerformanceSoakSamplesPath {
    $st=Get-HmsSoakState
    if($st -and $st.samplesPath -and (Test-Path ([string]$st.samplesPath))){return [string]$st.samplesPath}
    return ""
}
function Invoke-HmsPerformanceAnalytics {
    Ensure-Dir $script:PerformanceDir
    Ensure-Dir $script:PerformanceReportDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_PerformanceAnalytics.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_PerformanceAnalytics.py"}
    $input=Join-Path $env:TEMP ("hms-performance-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-performance-out-"+[Guid]::NewGuid().ToString("N")+".json")
    $html=Join-Path $script:PerformanceReportDir ("performance-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".html")
    try{
        try{Snapshot-CodexQuotaHistory}catch{}
        $obj=[ordered]@{
            window_hours=[int]$script:S.PerformanceWindowHours
            max_points=[int]$script:S.PerformanceMaxPoints
            anomaly_z=[double]$script:S.PerformanceAnomalyZ
            sla_drop_warn=[double]$script:S.PerformanceSlaDropWarn
            latency_p95_warn_ms=[double]$script:S.PerformanceLatencyP95WarnMs
            ram_growth_warn_mb_per_hour=[double]$script:S.PerformanceRamGrowthWarnMbPerHour
            soak_samples=(Get-HmsPerformanceSoakSamplesPath)
            ops_events=$script:CodexOpsEventsPath
            quota_history=$script:CodexQuotaHistoryPath
            ha_db=$script:CodexHaDbPath
        }
        Save-Json $input $obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $helper,"--input",$input,"--output",$output,"--html",$html
        ) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "PerformanceAnalytics không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8| ConvertFrom-Json
        if(-not $j.ok){throw [string]$j.error}
        $j.data.htmlReport=$html
        Save-JsonAtomic $script:PerformanceLatestPath $j.data
        Save-JsonAtomic $script:PerformanceReportStatePath ([ordered]@{generatedUtc=[DateTime]::UtcNow.ToString("o");html=$html;verdict=$j.data.verdict})
        $last=$null
        if(Test-Path $script:PerformanceHistoryPath){
            try{$tail=@(Get-Content $script:PerformanceHistoryPath -Tail 1 -Encoding UTF8);if($tail.Count){$last=$tail[0]| ConvertFrom-Json}}catch{}
        }
        $append=$true
        if($last -and $last.time){
            try{$append=(([DateTime]::UtcNow-[DateTime]::Parse([string]$last.time)).TotalMinutes -ge [int]$script:S.PerformanceHistoryMinIntervalMinutes)}catch{}
        }
        if($append){
            $h=[ordered]@{time=[DateTime]::UtcNow.ToString("o");verdict=$j.data.verdict;summary=$j.data.summary;metrics=$j.data.metrics}
            Add-Content -LiteralPath $script:PerformanceHistoryPath -Value ($h| ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
        }
        return $j.data
    }finally{Remove-Item $input,$output -Force -ErrorAction SilentlyContinue}
}
function Get-HmsPerformanceSummary {
    $j=Load-JsonObjectSafe $script:PerformanceLatestPath
    if(-not $j){return "Performance Analytics chưa có snapshot."}
    $lat=$j.metrics.latency_ms
    return "Perf=$($j.verdict); RAM P95=$([Math]::Round([double]$(if($j.metrics.ram.p95){$j.metrics.ram.p95}else{0}),1))MB; Lat P95=$([Math]::Round([double]$(if($lat.p95){$lat.p95}else{0}),1))ms; anomalies=$($j.summary.anomalies)"
}
function Open-HmsPerformanceHtmlReport {
    $j=Load-JsonObjectSafe $script:PerformanceLatestPath
    if(-not $j -or -not $j.htmlReport -or -not (Test-Path ([string]$j.htmlReport))){$j=Invoke-HmsPerformanceAnalytics}
    if($j.htmlReport -and (Test-Path ([string]$j.htmlReport))){Start-Process ([string]$j.htmlReport)|Out-Null;return [string]$j.htmlReport}
    throw "Không tạo được HTML performance report."
}
function Show-HmsPerformanceCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Observability & Performance Analytics v15.0"
    $w.Size=New-Object Drawing.Size(1480,860);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label;$title.Text="OBSERVABILITY & PERFORMANCE ANALYTICS";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,52);$status.Size=New-Object Drawing.Size(1000,48);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bRefresh=Btn "REFRESH ANALYTICS" 1040 18 175 36;$w.Controls.Add($bRefresh)
    $bHtml=Btn "OPEN HTML REPORT" 1225 18 175 36;$w.Controls.Add($bHtml)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1420,680);$w.Controls.Add($tabs)
    foreach($n in @("Overview","Per-account Latency","Quota","Findings","Timeline","Raw Analytics","Safety")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }

    $overview=New-Object Windows.Forms.TextBox;$overview.Location=New-Object Drawing.Point(15,20);$overview.Size=New-Object Drawing.Size(1355,555);$overview.Multiline=$true;$overview.ReadOnly=$true;$overview.ScrollBars="Both";$overview.WordWrap=$false;$overview.BackColor=[Drawing.Color]::FromArgb(20,23,27);$overview.ForeColor=$w.ForeColor;$tabs.TabPages[0].Controls.Add($overview)
    $gl=New-DarkGrid 15 20 1355 555 $tabs.TabPages[1]
    $gq=New-DarkGrid 15 20 1355 555 $tabs.TabPages[2]
    $gf=New-DarkGrid 15 20 1355 555 $tabs.TabPages[3]
    $gt=New-DarkGrid 15 20 1355 555 $tabs.TabPages[4]
    $raw=New-Object Windows.Forms.TextBox;$raw.Location=New-Object Drawing.Point(15,20);$raw.Size=New-Object Drawing.Size(1355,555);$raw.Multiline=$true;$raw.ReadOnly=$true;$raw.ScrollBars="Both";$raw.WordWrap=$false;$raw.BackColor=[Drawing.Color]::FromArgb(20,23,27);$raw.ForeColor=$w.ForeColor;$tabs.TabPages[5].Controls.Add($raw)
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1355,555);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="PERFORMANCE ANALYTICS SAFETY`r`n`r`n• HA SQLite được mở read-only bởi Python analytics.`r`n• P50/P95/P99 chỉ có ý nghĩa khi có đủ sample thực.`r`n• Không có latency sample → hiển thị rỗng, không giả 0ms là số đo thật.`r`n• Anomaly dùng median/MAD, là tín hiệu điều tra chứ không tự kết luận lỗi.`r`n• RAM/state slope là trend đầu-cuối theo cửa sổ, không phải chứng minh memory leak.`r`n• HTML report tự chứa, không tải JS/CSS từ Internet.`r`n• Analytics không restart router, không sửa auth và không đổi routing.";$tabs.TabPages[6].Controls.Add($safe)

    function Refresh-P {
        try{
            $j=Invoke-HmsPerformanceAnalytics
            $m=$j.metrics
            $overview.Text="WINDOW: $($j.windowHours)h`r`nVERDICT: $($j.verdict)`r`n`r`nRAM`r`n---`r`nP50=$($m.ram.p50) MB`r`nP95=$($m.ram.p95) MB`r`nP99=$($m.ram.p99) MB`r`nGrowth=$($m.ramGrowthMbPerHour) MB/h`r`n`r`nLATENCY`r`n-------`r`nSamples=$($m.latency_ms.count)`r`nP50=$($m.latency_ms.p50) ms`r`nP95=$($m.latency_ms.p95) ms`r`nP99=$($m.latency_ms.p99) ms`r`n`r`nSLA`r`n---`r`nP50=$($m.sla.p50)`r`nP95=$($m.sla.p95)`r`nMin=$($m.sla.min)`r`n`r`nEVENTS`r`n------`r`nFAILOVER=$($m.events.FAILOVER)`r`nCOOLDOWN=$($m.events.COOLDOWN)`r`nRECOVERY=$($m.events.RECOVERY)`r`nRETRY=$($m.events.RETRY)`r`nERROR=$($m.events.ERROR)`r`n`r`nHTML`r`n----`r`n$($j.htmlReport)"
            $latRows=[System.Collections.Generic.List[object]]::new()
            foreach($p in @($j.perAccountLatency.PSObject.Properties)){
                $x=$p.Value;$latRows.Add([PSCustomObject]@{Account=$p.Name;Samples=$x.count;P50_ms=$x.p50;P95_ms=$x.p95;P99_ms=$x.p99;Avg_ms=$x.avg;Max_ms=$x.max})
            }
            $gl.DataSource=$null;$gl.DataSource=@($latRows)
            $qRows=[System.Collections.Generic.List[object]]::new()
            foreach($p in @($j.quota.PSObject.Properties)){
                $x=$p.Value;$qRows.Add([PSCustomObject]@{Account=$p.Name;Samples=$x.samples;HourlyLatest=$x.latest_hourly;WeeklyLatest=$x.latest_weekly;HourlyP50=$x.hourly.p50;WeeklyP50=$x.weekly.p50})
            }
            $gq.DataSource=$null;$gq.DataSource=@($qRows)
            $gf.DataSource=$null;$gf.DataSource=@($j.findings|ForEach-Object{[PSCustomObject]@{Severity=$_.severity;Code=$_.code;Message=$_.message}})
            $gt.DataSource=$null;$gt.DataSource=@($j.timeline|ForEach-Object{[PSCustomObject]@{Time=$_.time;Type=$_.type;Account=$_.account;Message=$_.message}})
            $raw.Text=$j| ConvertTo-Json -Depth 12
            $status.Text=Get-HmsPerformanceSummary
        }catch{$status.Text="Performance Analytics error: "+$_.Exception.Message}
    }
    $bRefresh.Add_Click({Refresh-P})
    $bHtml.Add_Click({try{$null=Open-HmsPerformanceHtmlReport}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=[Math]::Max(10000,[int]$script:S.PerformanceAutoRefreshSec*1000);$tm.Add_Tick({Refresh-P});$tm.Start()
    $w.Add_Shown({Refresh-P});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# POLICY & AUTONOMOUS OPERATIONS KERNEL v16.0
# OBSERVE / RECOMMEND / SAFE_AUTO with action budget + hysteresis
# ============================================================
function Get-HmsPolicyKernelMode {
    $m=([string]$script:S.PolicyKernelMode).ToUpperInvariant()
    if($m -notin @("OBSERVE","RECOMMEND","SAFE_AUTO")){$m="OBSERVE"}
    return $m
}
function Get-HmsPolicyKernelState {
    $j=Load-JsonObjectSafe $script:PolicyKernelStatePath
    if(-not $j){
        return [PSCustomObject]@{
            streaks=[PSCustomObject]@{}
            lastActionUtc=[PSCustomObject]@{}
            lastCycleUtc=$null
        }
    }
    return $j
}
function Write-HmsPolicyActionHistory {
    param([string]$Kind,[string]$Result,[string]$Message,[string]$Mode)
    Ensure-Dir $script:PolicyKernelDir
    $row=[ordered]@{
        time=[DateTime]::UtcNow.ToString("o")
        kind=$Kind
        result=$Result
        mode=$Mode
        message=$Message
    }
    Add-Content -LiteralPath $script:PolicyKernelActionHistoryPath -Value ($row| ConvertTo-Json -Compress -Depth 5) -Encoding UTF8
}
function Set-HmsPolicyLastActionUtc {
    param([object]$KernelState,[string]$Kind,[string]$Utc)
    $streaks=[ordered]@{}
    if($KernelState.streaks){
        foreach($p in @($KernelState.streaks.PSObject.Properties)){$streaks[$p.Name]=$p.Value}
    }
    $last=[ordered]@{}
    if($KernelState.lastActionUtc){
        foreach($p in @($KernelState.lastActionUtc.PSObject.Properties)){$last[$p.Name]=$p.Value}
    }
    $last[$Kind]=$Utc
    $new=[ordered]@{
        streaks=$streaks
        lastActionUtc=$last
        lastCycleUtc=[DateTime]::UtcNow.ToString("o")
    }
    Save-JsonAtomic $script:PolicyKernelStatePath $new
    return $new
}
function Invoke-HmsPolicySafeAction {
    param([string]$Kind)
    if($script:RuntimeAutomationBlocked){
        return [PSCustomObject]@{result="BLOCKED";message="SAFE STARTUP đang chặn automation mutation."}
    }
    switch($Kind){
        "START_OWNED_MAIN_ROUTER" {
            if(-not (CodexInHmsMode)){return [PSCustomObject]@{result="BLOCKED";message="Codex không ở HMS mode."}}
            $procId=ListenerPid ([int]$script:S.ProxyPort)
            if($procId -gt 0){
                if(IsOurProxy $procId){return [PSCustomObject]@{result="SKIPPED";message="HMS router đã online PID=$procId."}}
                return [PSCustomObject]@{result="BLOCKED";message="Port $($script:S.ProxyPort) thuộc foreign process PID=$procId; HMS không can thiệp."}
            }
            try{
                $m=Start-Router
                return [PSCustomObject]@{result="EXECUTED";message=[string]$m}
            }catch{
                return [PSCustomObject]@{result="FAILED";message=$_.Exception.Message}
            }
        }
        "RUN_POOL_AUDIT" {
            try{
                $r=Invoke-CodexPoolReconcileAudit
                return [PSCustomObject]@{result="EXECUTED";message="Pool audit PASS; problems=$($r.summary.problems)."}
            }catch{return [PSCustomObject]@{result="FAILED";message=$_.Exception.Message}}
        }
        "REFRESH_ROUTER_INTELLIGENCE" {
            try{
                $r=Invoke-CodexRouterIntelligence
                return [PSCustomObject]@{result="EXECUTED";message="Router Intelligence refreshed; eligible=$($r.totals.eligible)/$($r.totals.accounts)."}
            }catch{return [PSCustomObject]@{result="FAILED";message=$_.Exception.Message}}
        }
        "REFRESH_PERFORMANCE" {
            try{
                $r=Invoke-HmsPerformanceAnalytics
                return [PSCustomObject]@{result="EXECUTED";message="Performance refreshed; verdict=$($r.verdict)."}
            }catch{return [PSCustomObject]@{result="FAILED";message=$_.Exception.Message}}
        }
        "PUBLISH_HEALTH_CERTIFICATE" {
            try{
                $r=Publish-HmsHealthCertificate
                return [PSCustomObject]@{result="EXECUTED";message="Health certificate published; grade=$($r.grade) score=$($r.score)."}
            }catch{return [PSCustomObject]@{result="FAILED";message=$_.Exception.Message}}
        }
        default {
            return [PSCustomObject]@{result="BLOCKED";message="Action '$Kind' không nằm trong SAFE_AUTO executor allowlist."}
        }
    }
}
function Invoke-HmsPolicyKernelCycle {
    Ensure-Dir $script:PolicyKernelDir
    Ensure-Dir $script:PolicyKernelDecisionDir
    $helper=Join-Path $PSScriptRoot "HMS_Codex_PolicyKernel.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_Codex_PolicyKernel.py"}

    $input=Join-Path $env:TEMP ("hms-policy-"+[Guid]::NewGuid().ToString("N")+".json")
    $output=Join-Path $env:TEMP ("hms-policy-out-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $listener=ListenerPid ([int]$script:S.ProxyPort)
        $owned=$false
        if($listener -gt 0){try{$owned=IsOurProxy $listener}catch{}}
        $pool=$null;$sla=$null
        try{$pool=Get-CodexPoolSummary}catch{$pool=[PSCustomObject]@{Ready=0;Total=0;Cooldown=0}}
        try{$sla=Get-CodexFleetSla}catch{$sla=[PSCustomObject]@{Score=0;State="UNKNOWN"}}
        $perf=Load-JsonObjectSafe $script:PerformanceLatestPath
        $reconcile=Load-JsonObjectSafe $script:PoolReconcileLatestPath
        $soak=Load-JsonObjectSafe $script:SoakLatestAnalysisPath
        $state=Get-HmsPolicyKernelState

        $obj=[ordered]@{
            mode=(Get-HmsPolicyKernelMode)
            router=[ordered]@{
                online=($listener -gt 0)
                owned=[bool]$owned
                listener_pid=$listener
                hms_mode=[bool](CodexInHmsMode)
            }
            pool=[ordered]@{
                ready=if($pool){[int]$pool.Ready}else{0}
                total=if($pool){[int]$pool.Total}else{0}
                cooldown=if($pool){[int]$pool.Cooldown}else{0}
            }
            sla=$sla
            performance=$perf
            pool_reconcile=$reconcile
            soak=$soak
            kernel_state=$state
            action_history=$script:PolicyKernelActionHistoryPath
            config=[ordered]@{
                cooldown_sec=[int]$script:S.PolicyKernelCooldownSec
                max_actions_per_hour=[int]$script:S.PolicyKernelMaxActionsPerHour
                max_router_starts_per_hour=[int]$script:S.PolicyKernelMaxRouterStartsPerHour
                hysteresis_cycles=[int]$script:S.PolicyKernelHysteresisCycles
                sla_critical=[int]$script:S.PolicyKernelSlaCritical
                sla_degraded=[int]$script:S.PolicyKernelSlaDegraded
                ready_critical=[int]$script:S.PolicyKernelReadyCritical
            }
        }
        Save-Json $input $obj
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $helper,"--input",$input,"--output",$output
        ) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $output)){throw "PolicyKernel không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $output -Raw -Encoding UTF8 | ConvertFrom-Json
        if(-not $j.ok){throw [string]$j.error}
        $decision=$j.data

        Save-JsonAtomic $script:PolicyKernelLatestPath $decision
        Save-JsonAtomic $script:PolicyKernelStatePath $decision.kernel_state

        $history=[ordered]@{
            time=[DateTime]::UtcNow.ToString("o")
            mode=$decision.mode
            score=$decision.score
            state=$decision.state
            signals=@($decision.signals)
            actionKinds=@($decision.actions|ForEach-Object{$_.kind})
            budget=$decision.budget
        }
        Add-Content -LiteralPath $script:PolicyKernelHistoryPath -Value ($history| ConvertTo-Json -Compress -Depth 8) -Encoding UTF8

        if(([string]$decision.mode -eq "SAFE_AUTO") -and (-not $script:RuntimeAutomationBlocked)){
            foreach($a in @($decision.actions)){
                if(-not [bool]$a.auto_allowed){continue}
                $res=Invoke-HmsPolicySafeAction ([string]$a.kind)
                $utc=[DateTime]::UtcNow.ToString("o")
                Write-HmsPolicyActionHistory ([string]$a.kind) ([string]$res.result) ([string]$res.message) ([string]$decision.mode)
                if([string]$res.result -eq "EXECUTED"){
                    $decision.kernel_state=Set-HmsPolicyLastActionUtc $decision.kernel_state ([string]$a.kind) $utc
                }
                Add-Member -InputObject $a -NotePropertyName executionResult -NotePropertyValue ([string]$res.result) -Force
                Add-Member -InputObject $a -NotePropertyName executionMessage -NotePropertyValue ([string]$res.message) -Force
            }
            Save-JsonAtomic $script:PolicyKernelLatestPath $decision
        }
        return $decision
    }finally{
        Remove-Item $input,$output -Force -ErrorAction SilentlyContinue
    }
}
function Get-HmsPolicyKernelSummary {
    $j=Load-JsonObjectSafe $script:PolicyKernelLatestPath
    if(-not $j){return "Policy Kernel chưa có decision."}
    $auto=@($j.actions|Where-Object auto_allowed -eq $true).Count
    return "Kernel=$($j.mode); state=$($j.state); score=$($j.score); signals=$(@($j.signals).Count); actions=$(@($j.actions).Count); auto-eligible=$auto; budget=$($j.budget.remaining)"
}
function Set-HmsPolicyKernelMode {
    param([ValidateSet("OBSERVE","RECOMMEND","SAFE_AUTO")][string]$Mode)
    if($Mode -eq "SAFE_AUTO"){
        if([bool]$script:S.PolicyKernelAllowCredentialSync -or [bool]$script:S.PolicyKernelAllowRebind -or [bool]$script:S.PolicyKernelAllowProcessKill -or [bool]$script:S.PolicyKernelAllowDestructive){
            throw "SAFE_AUTO từ chối khởi động vì có dangerous permission flag đang bật."
        }
    }
    $script:S.PolicyKernelMode=$Mode
    Save-Settings
    return "Policy Kernel mode = $Mode"
}
function Show-HmsPolicyKernelCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Policy & Autonomous Operations Kernel v16.0"
    $w.Size=New-Object Drawing.Size(1500,880);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label;$title.Text="POLICY & AUTONOMOUS OPERATIONS KERNEL";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $mode=New-Object Windows.Forms.ComboBox;$mode.DropDownStyle="DropDownList";$mode.Location=New-Object Drawing.Point(20,58);$mode.Size=New-Object Drawing.Size(180,28);foreach($x in @("OBSERVE","RECOMMEND","SAFE_AUTO")){[void]$mode.Items.Add($x)};$mode.SelectedItem=Get-HmsPolicyKernelMode;$w.Controls.Add($mode)
    $bMode=Btn "APPLY MODE" 215 54 125 34;$w.Controls.Add($bMode)
    $bCycle=Btn "RUN CYCLE" 350 54 120 34;$w.Controls.Add($bCycle)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(500,50);$status.Size=New-Object Drawing.Size(930,48);$status.Font=New-Object Drawing.Font("Segoe UI Semibold",11);$w.Controls.Add($status)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,105);$tabs.Size=New-Object Drawing.Size(1430,690);$w.Controls.Add($tabs)
    foreach($n in @("Decision","Actions","Signals","Action History","Safety Contract")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $decision=New-Object Windows.Forms.TextBox;$decision.Location=New-Object Drawing.Point(15,20);$decision.Size=New-Object Drawing.Size(1365,555);$decision.Multiline=$true;$decision.ReadOnly=$true;$decision.ScrollBars="Both";$decision.WordWrap=$false;$decision.BackColor=[Drawing.Color]::FromArgb(20,23,27);$decision.ForeColor=$w.ForeColor;$tabs.TabPages[0].Controls.Add($decision)
    $ga=New-DarkGrid 15 20 1365 555 $tabs.TabPages[1]
    $gs=New-DarkGrid 15 20 1365 555 $tabs.TabPages[2]
    $hist=New-Object Windows.Forms.TextBox;$hist.Location=New-Object Drawing.Point(15,20);$hist.Size=New-Object Drawing.Size(1365,555);$hist.Multiline=$true;$hist.ReadOnly=$true;$hist.ScrollBars="Both";$hist.WordWrap=$false;$hist.BackColor=[Drawing.Color]::FromArgb(20,23,27);$hist.ForeColor=$w.ForeColor;$tabs.TabPages[3].Controls.Add($hist)
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1365,555);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="V16 SAFETY CONTRACT`r`n`r`nSAFE_AUTO ALLOWLIST:`r`n• START_OWNED_MAIN_ROUTER — chỉ khi HMS mode và không có foreign port owner.`r`n• RUN_POOL_AUDIT — read-only audit.`r`n• REFRESH_ROUTER_INTELLIGENCE — evidence refresh.`r`n• REFRESH_PERFORMANCE — analytics refresh.`r`n• PUBLISH_HEALTH_CERTIFICATE — evidence publication.`r`n`r`nNEVER AUTO:`r`n• credential sync/delete/disable`r`n• instance rebind`r`n• process kill / foreign process mutation`r`n• release rollback`r`n• crash test / destructive action`r`n`r`nGATES:`r`n• hysteresis nhiều chu kỳ`r`n• per-action cooldown`r`n• action budget/hour`r`n• router-start budget/hour`r`n• Safe Startup blocks mutation`r`n• foreign PID/port ownership blocks router start.";$tabs.TabPages[4].Controls.Add($safe)

    function Refresh-K {
        $j=Load-JsonObjectSafe $script:PolicyKernelLatestPath
        if(-not $j){try{$j=Invoke-HmsPolicyKernelCycle}catch{$status.Text=$_.Exception.Message;return}}
        $decision.Text=$j| ConvertTo-Json -Depth 12
        $ga.DataSource=$null;$ga.DataSource=@($j.actions|ForEach-Object{
            [PSCustomObject]@{
                Action=$_.kind;Priority=$_.priority;Status=$_.status;AutoSafe=$_.auto_safe;
                AutoAllowed=$_.auto_allowed;Streak=$_.streak;Hysteresis=$_.hysteresis_required;
                CooldownOK=$_.cooldown_ok;Reason=$_.reason;Execution=$_.executionResult
            }
        })
        $gs.DataSource=$null;$gs.DataSource=@($j.signals|ForEach-Object{[PSCustomObject]@{Severity=$_.severity;Code=$_.code;Value=$_.value}})
        if(Test-Path $script:PolicyKernelActionHistoryPath){$hist.Text=@(Get-Content $script:PolicyKernelActionHistoryPath -Tail 300 -Encoding UTF8)-join"`r`n"}else{$hist.Text="No action history."}
        $status.Text=Get-HmsPolicyKernelSummary
    }
    $bMode.Add_Click({
        try{
            $m=[string]$mode.SelectedItem
            if($m -eq "SAFE_AUTO"){
                $a=[Windows.Forms.MessageBox]::Show("SAFE_AUTO chỉ thực thi allowlist an toàn, có budget/cooldown/hysteresis. Credential sync/rebind/kill/destructive vẫn bị cấm.`r`n`r`nBật SAFE_AUTO?","POLICY KERNEL",[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning)
                if($a -ne [Windows.Forms.DialogResult]::Yes){return}
            }
            $status.Text=Set-HmsPolicyKernelMode $m
            $null=Invoke-HmsPolicyKernelCycle
            Refresh-K
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bCycle.Add_Click({try{$null=Invoke-HmsPolicyKernelCycle;Refresh-K}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $tm=New-Object Windows.Forms.Timer;$tm.Interval=5000;$tm.Add_Tick({Refresh-K});$tm.Start()
    $w.Add_Shown({Refresh-K});$w.Add_FormClosed({$tm.Stop();$tm.Dispose()})
    [void]$w.ShowDialog($form)
}


# ============================================================
# POWERSHELL SOURCE INTEGRITY v18.0
# Static source gate before runtime automation
# ============================================================
function Invoke-HmsPowerShellSourceAudit {
    Ensure-Dir $script:PowerShellAuditDir
    $helper=Join-Path $PSScriptRoot "HMS_PowerShell_StaticLint.py"
    if(-not (Test-Path $helper)){throw "Thiếu HMS_PowerShell_StaticLint.py"}
    $tmp=Join-Path $env:TEMP ("hms-pslint-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $helper,"--file",$PSCommandPath,"--version",$script:Version,
            "--manifest","RELEASE_MANIFEST_V25_23_1.json","--output",$tmp
        ) -Wait -PassThru -WindowStyle Hidden
        if(-not (Test-Path $tmp)){throw "PowerShell static lint không tạo output. exit=$($p.ExitCode)"}
        $j=Get-Content $tmp -Raw -Encoding UTF8 | ConvertFrom-Json
        Save-JsonAtomic $script:PowerShellAuditLatestPath $j.data
        if([bool]$script:S.PowerShellStaticAuditHistory){
            $h=[ordered]@{
                time=[DateTime]::UtcNow.ToString("o")
                verdict=$j.data.verdict
                glue=$j.data.glue.total
                missingVariables=@($j.data.script_variables.missing).Count
                missingSettings=@($j.data.settings.missing).Count
            }
            Add-Content -LiteralPath $script:PowerShellAuditHistoryPath -Value ($h|ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
        }
        if((-not $j.ok) -or ([string]$j.data.verdict -ne "PASS")){
            if([bool]$script:S.PowerShellStaticAuditBlockAutomation){$script:RuntimeAutomationBlocked=$true}
        }
        return $j.data
    }finally{Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
}
function Get-HmsPowerShellSourceAuditSummary {
    $j=Load-JsonObjectSafe $script:PowerShellAuditLatestPath
    if(-not $j){return "PowerShell Source Audit chưa chạy."}
    return "PS Source=$($j.verdict); glue=$($j.glue.total); vars-missing=$(@($j.script_variables.missing).Count); settings-missing=$(@($j.settings.missing).Count)"
}
function Show-HmsPowerShellSourceAudit {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS PowerShell Source Integrity v18.0"
    $w.Size=New-Object Drawing.Size(1220,760);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="POWERSHELL SOURCE INTEGRITY";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",18);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,52);$status.Size=New-Object Drawing.Size(800,40);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $b=Btn "RUN SOURCE AUDIT" 940 18 220 36;$w.Controls.Add($b)
    $box=New-Object Windows.Forms.TextBox;$box.Location=New-Object Drawing.Point(20,100);$box.Size=New-Object Drawing.Size(1140,560);$box.Multiline=$true;$box.ReadOnly=$true;$box.ScrollBars="Both";$box.WordWrap=$false;$box.BackColor=[Drawing.Color]::FromArgb(20,23,27);$box.ForeColor=$w.ForeColor;$w.Controls.Add($box)
    function Refresh-PsAudit {
        try{
            $j=Invoke-HmsPowerShellSourceAudit
            $box.Text=$j|ConvertTo-Json -Depth 12
            $status.Text=Get-HmsPowerShellSourceAuditSummary
        }catch{$status.Text=$_.Exception.Message}
    }
    $b.Add_Click({Refresh-PsAudit})
    $w.Add_Shown({Refresh-PsAudit})
    [void]$w.ShowDialog($form)
}


# ============================================================
# WINDOWS RUNTIME GATE ORCHESTRATOR v19.0
# ============================================================
function Invoke-HmsWindowsRuntimeGate {
    param(
        [ValidateSet("PREFLIGHT","PARSE","WEB_SMOKE","PROTOCOL_SMOKE","PROXY_SMOKE","PROXY_FLEET_SMOKE","API_SUPERSET_SMOKE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME","ALL_SAFE")]
        [string]$Profile="PREFLIGHT"
    )
    Ensure-Dir $script:WindowsGateDir
    Ensure-Dir $script:WindowsGateEvidenceDir
    $runner=Join-Path $PSScriptRoot "HMS_Windows_Runtime_Gate.ps1"
    if(-not (Test-Path $runner)){throw "Thiếu HMS_Windows_Runtime_Gate.ps1"}

    $runnerArg='"'+$runner+'"'
    $rootArg='"'+$PSScriptRoot+'"'
    $outputArg='"'+$script:WindowsGateLatestPath+'"'
    $args=@(
        "-NoProfile","-ExecutionPolicy","Bypass",
        "-File",$runnerArg,
        "-Root",$rootArg,
        "-Profile",$Profile,
        "-Output",$outputArg
    )
    if([bool]$script:S.WindowsRuntimeGateOperatorMode){$args+="-OperatorMode"}
    if([bool]$script:S.WindowsRuntimeGateAllowUiSmoke){$args+="-AllowUiSmoke"}
    if([bool]$script:S.WindowsRuntimeGateAllowRouterSmoke){$args+="-AllowRouterSmoke"}
    if([bool]$script:S.WindowsRuntimeGateAllowSafeRuntime){$args+="-AllowSafeRuntime"}

    $p=Start-Process "powershell.exe" -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    $j=Load-JsonObjectSafe $script:WindowsGateLatestPath
    if($j){
        Add-Content -LiteralPath $script:WindowsGateHistoryPath -Value (([ordered]@{
            time=[DateTime]::UtcNow.ToString("o")
            profile=$Profile
            verdict=$j.verdict
            passed=$j.summary.passed
            failed=$j.summary.failed
            blocked=$j.summary.blocked
            exitCode=$p.ExitCode
        })|ConvertTo-Json -Compress -Depth 5) -Encoding UTF8
    }
    return $j
}
function Get-HmsWindowsRuntimeGateSummary {
    $j=Load-JsonObjectSafe $script:WindowsGateLatestPath
    if(-not $j){return "Windows Runtime Gate chưa chạy."}
    return "WindowsGate=$($j.verdict); pass=$($j.summary.passed); fail=$($j.summary.failed); blocked=$($j.summary.blocked); profile=$($j.profile)"
}
function Show-HmsWindowsRuntimeGateCenter {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Windows Runtime Gate Orchestrator v24.0"
    $w.Size=New-Object Drawing.Size(1280,800)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18)
    $w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

    $title=New-Object Windows.Forms.Label
    $title.Text="WINDOWS RUNTIME GATE ORCHESTRATOR"
    $title.Font=New-Object Drawing.Font("Segoe UI Semibold",18)
    $title.Location=New-Object Drawing.Point(20,15)
    $title.AutoSize=$true
    $w.Controls.Add($title)

    $profile=New-Object Windows.Forms.ComboBox
    $profile.DropDownStyle="DropDownList"
    $profile.Location=New-Object Drawing.Point(20,58)
    $profile.Size=New-Object Drawing.Size(220,28)
    foreach($x in @("PREFLIGHT","PARSE","WEB_SMOKE","PROTOCOL_SMOKE","PROXY_SMOKE","PROXY_FLEET_SMOKE","API_SUPERSET_SMOKE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME","ALL_SAFE")){[void]$profile.Items.Add($x)}
    $profile.SelectedItem=[string]$script:S.WindowsRuntimeGateProfile
    $w.Controls.Add($profile)

    $bRun=Btn "RUN GATE" 255 54 120 34
    $w.Controls.Add($bRun)

    $status=New-Object Windows.Forms.Label
    $status.Location=New-Object Drawing.Point(400,50)
    $status.Size=New-Object Drawing.Size(820,48)
    $status.Font=New-Object Drawing.Font("Segoe UI Semibold",11)
    $w.Controls.Add($status)

    $grid=New-DarkGrid 20 110 1190 500 $w
    $box=New-Object Windows.Forms.TextBox
    $box.Location=New-Object Drawing.Point(20,625)
    $box.Size=New-Object Drawing.Size(1190,90)
    $box.Multiline=$true
    $box.ReadOnly=$true
    $box.ScrollBars="Vertical"
    $box.BackColor=[Drawing.Color]::FromArgb(20,23,27)
    $box.ForeColor=$w.ForeColor
    $w.Controls.Add($box)

    function Load-GateResult {
        $j=Load-JsonObjectSafe $script:WindowsGateLatestPath
        if(-not $j){$status.Text="Chưa có runtime gate result.";return}
        $grid.DataSource=$null
        $grid.DataSource=@($j.gates|ForEach-Object{
            [PSCustomObject]@{
                Gate=$_.name
                Status=$_.status
                DurationMs=$_.duration_ms
                Detail=$_.detail
                Evidence=$_.evidence
            }
        })
        $status.Text=Get-HmsWindowsRuntimeGateSummary
        $box.Text="Windows host: $($j.host.os) / PowerShell $($j.host.powershell)`r`nEvidence: $($j.evidence_dir)`r`nBLOCKED gate không được tính là PASS."
    }

    $bRun.Add_Click({
        try{
            $selected=[string]$profile.SelectedItem
            if($selected -in @("UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME","ALL_SAFE")){
                $a=[Windows.Forms.MessageBox]::Show(
                    "Profile này có thể mở UI/router hoặc chạy SAFE_RUNTIME. Chỉ gate được settings/operator cho phép mới thực thi; foreign PID/port vẫn bị chặn.`r`n`r`nTiếp tục?",
                    "WINDOWS RUNTIME GATE",
                    [Windows.Forms.MessageBoxButtons]::YesNo,
                    [Windows.Forms.MessageBoxIcon]::Warning
                )
                if($a -ne [Windows.Forms.DialogResult]::Yes){return}
            }
            $script:S.WindowsRuntimeGateProfile=$selected
            Save-Settings
            $null=Invoke-HmsWindowsRuntimeGate $selected
            Load-GateResult
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $w.Add_Shown({Load-GateResult})
    [void]$w.ShowDialog($form)
}


# ============================================================
# HMS CODEX SMART GATEWAY v20.0
# Named client keys + model policy + priority/weight/reset-aware routing
# ============================================================
function Initialize-HmsSmartGatewayConfig {
    Ensure-Dir $script:SmartGatewayDir
    Ensure-Dir $script:SmartGatewayPolicyExportDir
    Ensure-Dir $script:ProtocolValidationDir
    Ensure-Dir $script:ApiSupersetDir
    $ctl=Join-Path $PSScriptRoot "HMS_Codex_GatewayControl.py"
    if(-not (Test-Path $ctl)){throw "Thiếu HMS_Codex_GatewayControl.py"}
    if((-not (Test-Path $script:SmartGatewayConfigPath)) -or (-not (Test-Path $script:SmartGatewayKeysPath))){
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $ctl,"--config",$script:SmartGatewayConfigPath,"--keys",$script:SmartGatewayKeysPath,"init"
        ) -Wait -PassThru -WindowStyle Hidden
        if($p.ExitCode -ne 0){throw "Không init được Smart Gateway config."}
    }
    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    if(-not $cfg){throw "Smart Gateway config parse FAIL."}
    Add-Member -InputObject $cfg -NotePropertyName host -NotePropertyValue ([string]$script:S.SmartGatewayHost) -Force
    Add-Member -InputObject $cfg -NotePropertyName port -NotePropertyValue ([int]$script:S.SmartGatewayPort) -Force
    if(-not $cfg.strategy){Add-Member -InputObject $cfg -NotePropertyName strategy -NotePropertyValue ([string]$script:S.SmartGatewayStrategy) -Force}
    Add-Member -InputObject $cfg -NotePropertyName session_affinity -NotePropertyValue ([bool]$script:S.SmartGatewaySessionAffinity) -Force
    Add-Member -InputObject $cfg -NotePropertyName session_ttl_sec -NotePropertyValue ([int]$script:S.SmartGatewaySessionTtlSec) -Force
    Add-Member -InputObject $cfg -NotePropertyName health_fail_threshold -NotePropertyValue ([int]$script:S.SmartGatewayHealthFailThreshold) -Force
    Add-Member -InputObject $cfg -NotePropertyName health_cooldown_sec -NotePropertyValue ([int]$script:S.SmartGatewayHealthCooldownSec) -Force
    Add-Member -InputObject $cfg -NotePropertyName max_failover_attempts -NotePropertyValue ([int]$script:S.SmartGatewayMaxFailoverAttempts) -Force
    Add-Member -InputObject $cfg -NotePropertyName retry_statuses -NotePropertyValue ([string]$script:S.SmartGatewayRetryStatuses) -Force
    Add-Member -InputObject $cfg -NotePropertyName require_idempotency_for_post_replay -NotePropertyValue ([bool]$script:S.SmartGatewayRequireIdempotencyForPostReplay) -Force
    Add-Member -InputObject $cfg -NotePropertyName stream_chunk_bytes -NotePropertyValue ([int]$script:S.SmartGatewayStreamChunkBytes) -Force
    Add-Member -InputObject $cfg -NotePropertyName websocket_enabled -NotePropertyValue ([bool]$script:S.SmartGatewayWebSocketEnabled) -Force
    Add-Member -InputObject $cfg -NotePropertyName websocket_idle_timeout_sec -NotePropertyValue ([int]$script:S.SmartGatewayWebSocketIdleTimeoutSec) -Force
    Add-Member -InputObject $cfg -NotePropertyName websocket_require_model_hint -NotePropertyValue ([bool]$script:S.SmartGatewayWebSocketRequireModelHint) -Force
    Add-Member -InputObject $cfg -NotePropertyName expose_selected_target_headers -NotePropertyValue ([bool]$script:S.SmartGatewayExposeSelectedTargetHeaders) -Force
    Add-Member -InputObject $cfg -NotePropertyName cors_enabled -NotePropertyValue ([bool]$script:S.ApiCorsEnabled) -Force
    Add-Member -InputObject $cfg -NotePropertyName quota_evidence_max_age_sec -NotePropertyValue ([int]$script:S.ApiQuotaEvidenceMaxAgeSec) -Force
    Add-Member -InputObject $cfg -NotePropertyName quota_reserve_fail_closed -NotePropertyValue ([bool]$script:S.ApiQuotaReserveFailClosed) -Force
    Add-Member -InputObject $cfg -NotePropertyName default_quota_reserve_pct -NotePropertyValue ([double]$script:S.ApiDefaultQuotaReservePct) -Force
    Add-Member -InputObject $cfg -NotePropertyName usage_capture_max_bytes -NotePropertyValue ([int]$script:S.ApiUsageCaptureMaxBytes) -Force
    if(-not $cfg.model_prices){Add-Member -InputObject $cfg -NotePropertyName model_prices -NotePropertyValue ([PSCustomObject]@{}) -Force}
    if(-not $cfg.cors_allowed_origins){
        Add-Member -InputObject $cfg -NotePropertyName cors_allowed_origins -NotePropertyValue @(
            "http://localhost:*","http://127.0.0.1:*","https://localhost:*","https://127.0.0.1:*"
        ) -Force
    }
    Save-JsonAtomic $script:SmartGatewayConfigPath $cfg
}

function Get-HmsSmartGatewayState {
    $j=Load-JsonObjectSafe $script:SmartGatewayStatePath
    if(-not $j){
        $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
        $port=if($cfg -and $cfg.port){[int]$cfg.port}else{[int]$script:S.SmartGatewayPort}
        return [PSCustomObject]@{pid=0;port=$port;startedUtc=$null}
    }
    return $j
}
function Start-HmsSmartGateway {
    Initialize-HmsSmartGatewayConfig
    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    if(-not $cfg){throw "Smart Gateway config unavailable."}
    $port=[int]$cfg.port
    $existing=ListenerPid $port
    if($existing -gt 0){
        $st=Get-HmsSmartGatewayState
        if([int]$st.pid -eq $existing){return "Smart Gateway đã ONLINE PID=$existing :$port"}
        throw "Port $port đang do foreign PID=$existing sử dụng. HMS không can thiệp."
    }
    $server=Join-Path $PSScriptRoot "HMS_Codex_SmartGateway.py"
    if(-not (Test-Path $server)){throw "Thiếu HMS_Codex_SmartGateway.py"}
    $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
        $server,"--config",$script:SmartGatewayConfigPath,
        "--keys",$script:SmartGatewayKeysPath,
        "--trace",$script:SmartGatewayTracePath
    ) -PassThru -WindowStyle Hidden
    for($i=0;$i -lt 30;$i++){Start-Sleep -Milliseconds 200;if(PortOpen $port){break}}
    $owner=ListenerPid $port
    if($owner -ne $p.Id){
        try{if(-not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}}catch{}
        throw "Smart Gateway ownership verify FAIL: child=$($p.Id), listener=$owner."
    }
    Save-JsonAtomic $script:SmartGatewayStatePath ([ordered]@{pid=$p.Id;port=$port;startedUtc=[DateTime]::UtcNow.ToString("o")})
    return "Smart Gateway ONLINE: http://127.0.0.1:$port/v1"
}
function Stop-HmsSmartGateway {
    $st=Get-HmsSmartGatewayState
    $procId=[int]$st.pid;$port=[int]$st.port
    if($procId -le 0){return "Smart Gateway đã STOP."}
    $owner=ListenerPid $port
    if($owner -ne $procId){
        Save-JsonAtomic $script:SmartGatewayStatePath ([ordered]@{pid=0;port=$port;startedUtc=$null})
        return "STOP BLOCKED/SKIPPED: state PID không sở hữu port."
    }
    try{
        $proc=Get-Process -Id $procId -ErrorAction Stop
        if($proc.ProcessName -notlike "python*"){throw "PID owner không phải Python."}
        Stop-Process -Id $procId -Force -ErrorAction Stop
    }catch{throw}
    Save-JsonAtomic $script:SmartGatewayStatePath ([ordered]@{pid=0;port=$port;startedUtc=$null})
    return "Smart Gateway STOP PASS."
}
function Get-HmsSmartGatewaySummary {
    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    $st=Get-HmsSmartGatewayState
    if(-not $cfg){return "SmartGateway chưa init."}
    $online=(([int]$st.pid -gt 0) -and ((ListenerPid ([int]$st.port)) -eq [int]$st.pid))
    return "SmartGateway=$(if($online){'ONLINE'}else{'OFFLINE'}); strategy=$($cfg.strategy); targets=$(@($cfg.targets).Count); :$($cfg.port)"
}
function Invoke-HmsProtocolValidation {
    Ensure-Dir $script:ProtocolValidationDir
    $validator=Join-Path $PSScriptRoot "HMS_Codex_ProtocolValidator.py"
    if(-not (Test-Path $validator)){throw "Thiếu HMS_Codex_ProtocolValidator.py"}
    $tmp=Join-Path $env:TEMP ("hms-v21-protocol-"+[Guid]::NewGuid().ToString("N"))
    try{
        $p=Start-Process ([string]$script:S.CodexSessionDoctorPython) -ArgumentList @(
            $validator,"--root",$PSScriptRoot,"--temp",$tmp,"--output",$script:ProtocolValidationLatestPath
        ) -Wait -PassThru -WindowStyle Hidden
        $j=Load-JsonObjectSafe $script:ProtocolValidationLatestPath
        if(-not $j){throw "Protocol validator không tạo result."}
        if([bool]$script:S.ProtocolValidationAutoSave){
            Add-Content -LiteralPath $script:ProtocolValidationHistoryPath -Value (([ordered]@{
                time=[DateTime]::UtcNow.ToString("o")
                verdict=$j.data.verdict
                pass=$j.data.summary.pass
                fail=$j.data.summary.fail
                exitCode=$p.ExitCode
            })|ConvertTo-Json -Compress -Depth 5) -Encoding UTF8
        }
        return $j
    }finally{
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
function Get-HmsProtocolValidationSummary {
    $j=Load-JsonObjectSafe $script:ProtocolValidationLatestPath
    if(-not $j){return "Protocol Validation chưa chạy."}
    return "Protocol=$($j.data.verdict); pass=$($j.data.summary.pass)/$($j.data.summary.total); fail=$($j.data.summary.fail)"
}
function Show-HmsSmartGatewayCenter {
    Initialize-HmsSmartGatewayConfig
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex Smart Gateway v21.0"
    $w.Size=New-Object Drawing.Size(1380,820);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="CODEX SMART GATEWAY & API CONTROL PLANE";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",18);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,52);$status.Size=New-Object Drawing.Size(850,40);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bStart=Btn "START GATEWAY" 790 18 140 34;$w.Controls.Add($bStart)
    $bStop=Btn "STOP OWNED" 940 18 130 34;$w.Controls.Add($bStop)
    $bProtocol=Btn "PROTOCOL TEST" 1080 18 130 34;$w.Controls.Add($bProtocol)
    $bOpen=Btn "OPEN CONFIG DIR" 1220 18 120 34;$w.Controls.Add($bOpen)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1320,630);$w.Controls.Add($tabs)
    foreach($n in @("Targets & Routing","Client Keys","Request Trace","Protocol Validation","Safety / Parity")){
        $p=New-Object Windows.Forms.TabPage;$p.Text=$n;$p.BackColor=[Drawing.Color]::FromArgb(18,21,25);$p.ForeColor=$w.ForeColor;$tabs.TabPages.Add($p)
    }
    $targets=New-DarkGrid 15 20 1255 500 $tabs.TabPages[0]
    $keys=New-DarkGrid 15 20 1255 500 $tabs.TabPages[1]
    $trace=New-Object Windows.Forms.TextBox;$trace.Location=New-Object Drawing.Point(15,20);$trace.Size=New-Object Drawing.Size(1255,500);$trace.Multiline=$true;$trace.ReadOnly=$true;$trace.ScrollBars="Both";$trace.WordWrap=$false;$trace.BackColor=[Drawing.Color]::FromArgb(20,23,27);$trace.ForeColor=$w.ForeColor;$tabs.TabPages[2].Controls.Add($trace)
    $protocolGrid=New-DarkGrid 15 20 1255 500 $tabs.TabPages[3]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1255,500);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="V21 PROTOCOL & STREAMING`r`n`r`n• HTTP forwarding + SSE incremental streaming.`r`n• WebSocket Upgrade relay + raw bidirectional frame tunnel.`r`n• Selected-target headers + request ID.`r`n• TTFT / header latency / total latency / bytes telemetry.`r`n• Bounded failover.`r`n• POST replay mặc định chỉ khi có Idempotency-Key.`r`n• GET/HEAD/OPTIONS và idempotent methods có thể failover theo policy.`r`n• Request body và plaintext key KHÔNG ghi vào trace.`r`n• Per-key + per-target model policy vẫn áp dụng cho HTTP/SSE/WS.`r`n• Foreign listener không bị stop/chiếm port.`r`n• Runtime thực với Codex client trên Windows vẫn là gate cuối trước Production Superset.";$tabs.TabPages[3].Controls.Add($safe)

    function Refresh-G {
        $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
        $keydb=Load-JsonObjectSafe $script:SmartGatewayKeysPath
        $targets.DataSource=$null;$targets.DataSource=@($cfg.targets|ForEach-Object{
            [PSCustomObject]@{Id=$_.id;Account=$_.account;BaseUrl=$_.base_url;Priority=$_.priority;Weight=$_.weight;Enabled=$_.enabled;Allow=(@($_.model_allow)-join",");Deny=(@($_.model_deny)-join",");ResetUtc=$_.reset_utc}
        })
        $keys.DataSource=$null;$keys.DataSource=@($keydb.keys|ForEach-Object{
            [PSCustomObject]@{Id=$_.id;Name=$_.name;Enabled=$_.enabled;Created=$_.created_utc;Allow=(@($_.model_allow)-join",");Deny=(@($_.model_deny)-join",")}
        })
        if(Test-Path $script:SmartGatewayTracePath){$trace.Text=@(Get-Content $script:SmartGatewayTracePath -Tail 300 -Encoding UTF8)-join"`r`n"}else{$trace.Text="No request trace."}
        $pv=Load-JsonObjectSafe $script:ProtocolValidationLatestPath
        $protocolGrid.DataSource=$null
        if($pv -and $pv.data){
            $protocolGrid.DataSource=@($pv.data.tests|ForEach-Object{
                [PSCustomObject]@{Test=$_.name;Status=$_.status;Detail=$_.detail}
            })
        }
        $status.Text=(Get-HmsSmartGatewaySummary)+" | "+(Get-HmsProtocolValidationSummary)
    }
    $bStart.Add_Click({try{$status.Text=Start-HmsSmartGateway;Refresh-G}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bStop.Add_Click({try{$status.Text=Stop-HmsSmartGateway;Refresh-G}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bProtocol.Add_Click({try{$null=Invoke-HmsProtocolValidation;Refresh-G}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bOpen.Add_Click({Start-Process explorer.exe $script:SmartGatewayDir|Out-Null})
    $w.Add_Shown({Refresh-G})
    [void]$w.ShowDialog($form)
}


# ============================================================
# PROXY AFFINITY & EGRESS CONTROL v22.0
# Sticky account groups -> isolated CLIProxyAPI sidecars -> proxy
# ============================================================
function Initialize-HmsProxyAffinity {
    Ensure-Dir $script:ProxyAffinityDir
    Ensure-Dir $script:ProxySidecarDir
    $mgr=Join-Path $PSScriptRoot "HMS_Codex_ProxyManager.py"
    if(-not (Test-Path $mgr)){throw "Thiếu HMS_Codex_ProxyManager.py"}
    if((-not (Test-Path $script:ProxyProfilesPath)) -or
       (-not (Test-Path $script:ProxyBindingsPath)) -or
       (-not (Test-Path $script:ProxyHealthPath))){
        & ([string]$script:S.CodexSessionDoctorPython) $mgr `
            --profiles $script:ProxyProfilesPath `
            --bindings $script:ProxyBindingsPath `
            --health $script:ProxyHealthPath `
            --audit $script:ProxyAuditPath init | Out-Null
        if($LASTEXITCODE -ne 0){throw "Proxy Manager init FAIL."}
    }
    if(-not (Test-Path $script:ProxySecretsPath)){
        Save-JsonAtomic $script:ProxySecretsPath ([ordered]@{version=22;secrets=[ordered]@{}})
    }
    if(-not (Test-Path $script:ProxySidecarStatePath)){
        Save-JsonAtomic $script:ProxySidecarStatePath ([ordered]@{version=22;sidecars=@()})
    }
}
function Protect-HmsProxySecret {
    param([string]$PlainText)
    if([string]::IsNullOrEmpty($PlainText)){return ""}
    Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue
    $bytes=[Text.Encoding]::UTF8.GetBytes($PlainText)
    $enc=[Security.Cryptography.ProtectedData]::Protect(
        $bytes,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    return [Convert]::ToBase64String($enc)
}
function Unprotect-HmsProxySecret {
    param([string]$CipherText)
    if([string]::IsNullOrEmpty($CipherText)){return ""}
    Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue
    $enc=[Convert]::FromBase64String($CipherText)
    $bytes=[Security.Cryptography.ProtectedData]::Unprotect(
        $enc,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    return [Text.Encoding]::UTF8.GetString($bytes)
}
function Set-HmsProxySecret {
    param([string]$Ref,[string]$PlainText)
    Initialize-HmsProxyAffinity
    if([string]::IsNullOrWhiteSpace($Ref)){throw "Secret Ref trống."}
    $j=Load-JsonObjectSafe $script:ProxySecretsPath
    if(-not $j){$j=[PSCustomObject]@{version=22;secrets=[PSCustomObject]@{}}}
    $map=[ordered]@{}
    if($j.secrets){
        foreach($prop in @($j.secrets.PSObject.Properties)){$map[$prop.Name]=$prop.Value}
    }
    $map[$Ref]=[ordered]@{
        protected=Protect-HmsProxySecret $PlainText
        updatedUtc=[DateTime]::UtcNow.ToString("o")
        scope="CurrentUser-DPAPI"
    }
    Save-JsonAtomic $script:ProxySecretsPath ([ordered]@{version=22;secrets=$map})
}
function Get-HmsProxySecret {
    param([string]$Ref)
    if([string]::IsNullOrWhiteSpace($Ref)){return ""}
    $j=Load-JsonObjectSafe $script:ProxySecretsPath
    if(-not $j -or -not $j.secrets){return ""}
    $prop=$j.secrets.PSObject.Properties[$Ref]
    if(-not $prop){return ""}
    return Unprotect-HmsProxySecret ([string]$prop.Value.protected)
}
function ConvertTo-HmsYamlSingleQuoted {
    param([string]$Value)
    return "'" + ([string]$Value).Replace("'","''") + "'"
}
function Get-HmsProxyProfiles {
    Initialize-HmsProxyAffinity
    $j=Load-JsonObjectSafe $script:ProxyProfilesPath
    if(-not $j){return @()}
    return @($j.profiles)
}
function Get-HmsProxyBindings {
    Initialize-HmsProxyAffinity
    $j=Load-JsonObjectSafe $script:ProxyBindingsPath
    if(-not $j){return @()}
    return @($j.bindings)
}
function Get-HmsProxyHealthRows {
    Initialize-HmsProxyAffinity
    $j=Load-JsonObjectSafe $script:ProxyHealthPath
    if(-not $j -or -not $j.profiles){return @()}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($prop in @($j.profiles.PSObject.Properties)){
        $v=$prop.Value
        $rows.Add([PSCustomObject]@{
            ProfileId=$prop.Name
            Status=[string]$v.status
            LatencyMs=$v.latency_ms
            TlsMs=$v.tls_ms
            CheckedUtc=$v.checked_utc
            Probe="$($v.probe_host):$($v.probe_port)"
            Error=$v.error
        })
    }
    return @($rows)
}
function Add-HmsProxyProfile {
    param(
        [string]$Name,[string]$Scheme,[string]$proxyHost,[int]$Port,
        [string]$Username,[string]$Password,[int]$MaxAccounts=5,
        [string]$Mode="STRICT",[string]$Country="VN",[string]$Isp=""
    )
    Initialize-HmsProxyAffinity
    $id=("proxy-"+[Guid]::NewGuid().ToString("N").Substring(0,10))
    $secretRef=""
    if(-not [string]::IsNullOrEmpty($Password)){
        $secretRef="proxy-password:"+$id
        Set-HmsProxySecret $secretRef $Password
    }
    $mgr=Join-Path $PSScriptRoot "HMS_Codex_ProxyManager.py"
    $args=@(
        $mgr,"--profiles",$script:ProxyProfilesPath,
        "--bindings",$script:ProxyBindingsPath,
        "--health",$script:ProxyHealthPath,
        "--audit",$script:ProxyAuditPath,
        "upsert-profile",
        "--id",$id,"--name",$Name,"--scheme",$Scheme,"--host",$proxyHost,
        "--port",[string]$Port,"--max-accounts",[string]$MaxAccounts,
        "--mode",$Mode,"--country",$Country
    )
    if(-not [string]::IsNullOrWhiteSpace($Username)){$args+=@("--username",$Username)}
    if(-not [string]::IsNullOrWhiteSpace($secretRef)){$args+=@("--secret-ref",$secretRef)}
    if(-not [string]::IsNullOrWhiteSpace($Isp)){$args+=@("--isp",$Isp)}
    $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
    if($LASTEXITCODE -ne 0){throw "Add proxy profile FAIL: $raw"}
    return $id
}
function Invoke-HmsProxyAutoAssign {
    Initialize-HmsProxyAffinity
    $accounts=@(Get-CodexAccountRecords|ForEach-Object{
        [PSCustomObject]@{email=[string]$_.Email;filename=[string]$_.File.Name}
    })
    $tmp=Join-Path $env:TEMP ("hms-proxy-accounts-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        Save-Json $tmp $accounts
        $mgr=Join-Path $PSScriptRoot "HMS_Codex_ProxyManager.py"
        $args=@(
            $mgr,"--profiles",$script:ProxyProfilesPath,
            "--bindings",$script:ProxyBindingsPath,
            "--health",$script:ProxyHealthPath,
            "--audit",$script:ProxyAuditPath,
            "assign","--accounts-json",$tmp,
            "--max-per-proxy",[string][int]$script:S.ProxyAccountsPerProxy
        )
        if(-not [bool]$script:S.ProxyAutoAssignPreserveExisting){$args+="-no-preserve"}
        $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
        if($LASTEXITCODE -ne 0){throw "Proxy auto-assign FAIL: $raw"}
        return "Proxy auto-assign PASS: accounts=$($accounts.Count)"
    }finally{
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
}
function Invoke-HmsProxyHealthCheck {
    param([object]$Profile)
    Initialize-HmsProxyAffinity
    if(-not $Profile){throw "Proxy profile trống."}
    $health=Join-Path $PSScriptRoot "HMS_Codex_ProxyHealth.py"
    if(-not (Test-Path $health)){throw "Thiếu HMS_Codex_ProxyHealth.py"}
    $secret=Get-HmsProxySecret ([string]$Profile.secret_ref)
    $old=[Environment]::GetEnvironmentVariable("HMS_PROXY_PASSWORD","Process")
    try{
        [Environment]::SetEnvironmentVariable("HMS_PROXY_PASSWORD",$secret,"Process")
        $args=@(
            $health,
            "--profile-id",[string]$Profile.id,
            "--scheme",[string]$Profile.scheme,
            "--host",[string]$Profile.host,
            "--port",[string][int]$Profile.port,
            "--health",$script:ProxyHealthPath,
            "--probe-host",[string]$script:S.ProxyHealthProbeHost,
            "--probe-port",[string][int]$script:S.ProxyHealthProbePort,
            "--timeout",[string][int]$script:S.ProxyHealthTimeoutSec
        )
        if(-not [string]::IsNullOrWhiteSpace([string]$Profile.username)){
            $args+=@("--username",[string]$Profile.username)
        }
        $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
        return ($raw -join "`r`n")
    }finally{
        [Environment]::SetEnvironmentVariable("HMS_PROXY_PASSWORD",$old,"Process")
        $secret=$null
    }
}
function Invoke-HmsProxyHealthCheckAll {
    $rows=@(Get-HmsProxyProfiles)
    $pass=0;$fail=0
    foreach($p in $rows){
        if(-not [bool]$p.enabled){continue}
        try{
            $null=Invoke-HmsProxyHealthCheck $p
            $h=@(Get-HmsProxyHealthRows|Where-Object ProfileId -eq ([string]$p.id)|Select-Object -First 1)
            if($h.Count -gt 0 -and [string]$h[0].Status -eq "PASS"){$pass++}else{$fail++}
        }catch{$fail++}
    }
    return "Proxy Health: PASS=$pass FAIL=$fail"
}
function Get-HmsProxySidecarPlan {
    Initialize-HmsProxyAffinity
    $mgr=Join-Path $PSScriptRoot "HMS_Codex_ProxyManager.py"
    $args=@(
        $mgr,"--profiles",$script:ProxyProfilesPath,
        "--bindings",$script:ProxyBindingsPath,
        "--health",$script:ProxyHealthPath,
        "--audit",$script:ProxyAuditPath,
        "plan","--base-port",[string][int]$script:S.ProxySidecarBasePort
    )
    if([bool]$script:S.ProxyDirectFallbackAllowed){$args+="-direct-fallback-allowed"}
    $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
    if($LASTEXITCODE -ne 0){throw "Proxy sidecar plan FAIL."}
    $j=($raw -join "`n")|ConvertFrom-Json
    return $j.data
}
function Get-HmsProxySidecarState {
    Initialize-HmsProxyAffinity
    $j=Load-JsonObjectSafe $script:ProxySidecarStatePath
    if(-not $j){return [PSCustomObject]@{version=22;sidecars=@()}}
    return $j
}
function Save-HmsProxySidecarRows {
    param([object[]]$Rows)
    Save-JsonAtomic $script:ProxySidecarStatePath ([ordered]@{version=22;sidecars=@($Rows)})
}
function New-HmsProxyUrl {
    param([object]$Profile)
    $scheme=[string]$Profile.scheme
    $proxyHost=[string]$Profile.host
    $port=[int]$Profile.port
    $user=[string]$Profile.username
    $secret=Get-HmsProxySecret ([string]$Profile.secret_ref)
    if([string]::IsNullOrWhiteSpace($user)){
        return "$scheme`://$proxyHost`:$port"
    }
    $eu=[Uri]::EscapeDataString($user)
    $ep=[Uri]::EscapeDataString($secret)
    $secret=$null
    return "$scheme`://$eu`:$ep@$proxyHost`:$port"
}
function New-HmsProxySidecarGeneration {
    param([object]$Group)
    if(-not (Test-Path $script:ProxyExe)){throw "Không tìm thấy CLIProxyAPI: $($script:ProxyExe)"}
    $profile=@(Get-HmsProxyProfiles|Where-Object id -eq ([string]$Group.profile_id)|Select-Object -First 1)
    if($profile.Count -lt 1){throw "Proxy profile không tồn tại."}
    $profile=$profile[0]

    if([bool]$script:S.ProxyHealthRequiredBeforeStart){
        $health=@(Get-HmsProxyHealthRows|Where-Object ProfileId -eq ([string]$profile.id)|Select-Object -First 1)
        if($health.Count -lt 1 -or [string]$health[0].Status -ne "PASS"){
            throw "STRICT START BLOCKED: proxy $($profile.name) chưa PASS health check."
        }
        if(-not (Test-HmsEvidenceFresh $health[0].CheckedUtc ([int]$script:S.ProxyHealthMaxAgeSec))){
            throw "STRICT START BLOCKED: proxy health evidence đã stale."
        }
    }
    if(([string]$profile.mode -eq "STRICT") -and (-not [bool]$Group.start_allowed)){
        throw "STRICT START BLOCKED: proxy health=$($Group.health_status)."
    }
    $ops=Get-HmsProxyFleetOpsState ([string]$profile.id)
    if($ops -ne "ACTIVE"){
        throw "SIDECAR START BLOCKED: Proxy Fleet state=$ops."
    }
    if([bool]$script:S.ProxyEgressRequireBeforeSidecarStart){
        $eg=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq ([string]$profile.id)|Select-Object -First 1)
        if($eg.Count -lt 1 -or [string]$eg[0].Integrity -ne "PASS"){
            throw "STRICT START BLOCKED: egress integrity chưa PASS."
        }
        if(-not (Test-HmsEvidenceFresh $eg[0].CheckedUtc ([int]$script:S.ProxyEgressMaxAgeSec))){
            throw "STRICT START BLOCKED: egress evidence đã stale."
        }
        if([bool]$eg[0].StrictBlock){
            throw "STRICT START BLOCKED: egress strict_block=true."
        }
    }
    $port=[int]$Group.sidecar_port
    $existing=ListenerPid $port
    if($existing -gt 0){throw "Sidecar port $port đang do PID=$existing sử dụng. HMS không can thiệp."}

    $stamp=Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $gen=Join-Path (Join-Path $script:ProxySidecarDir ([string]$profile.id)) ("generation-"+$stamp)
    $auth=Join-Path $gen "auth"
    Ensure-Dir $auth

    $copied=0
    foreach($a in @($Group.accounts)){
        $name=[string]$a.filename
        if([string]::IsNullOrWhiteSpace($name)){continue}
        $source=Join-Path $script:AuthDir $name
        if(-not (Test-Path $source)){continue}
        Copy-Item -LiteralPath $source -Destination (Join-Path $auth $name) -Force
        $copied++
    }
    if($copied -lt 1){throw "Sidecar group không có auth file hợp lệ để project."}

    $apiKey="hms-sidecar-"+[Guid]::NewGuid().ToString("N")
    $apiRef="sidecar-api-key:"+[string]$profile.id
    Set-HmsProxySecret $apiRef $apiKey
    $proxyUrl=New-HmsProxyUrl $profile
    $cfg=Join-Path $gen "config.yaml"
    $lines=@(
        'host: "127.0.0.1"',
        "port: $port",
        "auth-dir: $(ConvertTo-HmsYamlSingleQuoted $auth)",
        "proxy-url: $(ConvertTo-HmsYamlSingleQuoted $proxyUrl)",
        "api-keys:",
        "  - $(ConvertTo-HmsYamlSingleQuoted $apiKey)",
        "remote-management:",
        "  allow-remote: false",
        '  secret-key: ""',
        "logging-to-file: true",
        "usage-statistics-enabled: true",
        "routing:",
        '  strategy: "round-robin"',
        "  session-affinity: $(([bool]$script:S.ProxySidecarSessionAffinity).ToString().ToLowerInvariant())",
        "  session-affinity-ttl: $(ConvertTo-HmsYamlSingleQuoted ([string]$script:S.ProxySidecarSessionTtl))"
    )
    [IO.File]::WriteAllLines($cfg,$lines,(New-Object Text.UTF8Encoding($false)))
    $proxyUrl=$null;$apiKey=$null

    try{
        & icacls.exe $gen /inheritance:r /grant:r "$env:USERNAME`:(OI)(CI)F" "SYSTEM`:(OI)(CI)F" /T /C | Out-Null
    }catch{}

    return [PSCustomObject]@{
        profile_id=[string]$profile.id
        profile_name=[string]$profile.name
        port=$port
        generation=$gen
        auth_dir=$auth
        config=$cfg
        api_key_ref=$apiRef
        account_count=$copied
    }
}
function Start-HmsProxySidecar {
    param([object]$Group)
    $gen=New-HmsProxySidecarGeneration $Group
    $p=Start-Process $script:ProxyExe -WorkingDirectory ([string]$script:S.ProxyDir) `
        -ArgumentList @("--config",('"'+[string]$gen.config+'"')) -PassThru -WindowStyle Hidden
    for($i=0;$i -lt 40;$i++){
        Start-Sleep -Milliseconds 250
        if(PortOpen ([int]$gen.port)){break}
    }
    $owner=ListenerPid ([int]$gen.port)
    if($owner -ne $p.Id){
        try{if(-not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}}catch{}
        throw "Sidecar ownership FAIL: child=$($p.Id), listener=$owner."
    }
    $state=Get-HmsProxySidecarState
    $rows=@($state.sidecars|Where-Object profile_id -ne ([string]$gen.profile_id))
    $rows+=,[PSCustomObject]@{
        profile_id=$gen.profile_id
        profile_name=$gen.profile_name
        pid=$p.Id
        port=$gen.port
        generation=$gen.generation
        config=$gen.config
        api_key_ref=$gen.api_key_ref
        account_count=$gen.account_count
        status="RUNNING"
        started_utc=[DateTime]::UtcNow.ToString("o")
    }
    Save-HmsProxySidecarRows $rows
    try{Record-HmsProxyFleetAction ([string]$gen.profile_id) "START_SIDECAR" "PASS" ("PID="+$p.Id+" port="+$gen.port)}catch{}
    return "Sidecar $($gen.profile_name) ONLINE :$($gen.port) PID=$($p.Id) accounts=$($gen.account_count)"
}
function Stop-HmsProxySidecar {
    param([object]$Row)
    $procId=[int]$Row.pid;$port=[int]$Row.port
    if($procId -le 0){return "Sidecar already stopped."}
    $owner=ListenerPid $port
    if($owner -ne $procId){return "STOP BLOCKED: state PID=$procId không sở hữu port $port."}
    try{
        $proc=Get-Process -Id $procId -ErrorAction Stop
        if((Norm $proc.Path) -ne (Norm $script:ProxyExe)){return "STOP BLOCKED: PID không phải CLIProxyAPI HMS."}
        Stop-Process -Id $procId -Force -ErrorAction Stop
    }catch{return "STOP FAIL: $($_.Exception.Message)"}
    $state=Get-HmsProxySidecarState
    $rows=@($state.sidecars|Where-Object profile_id -ne ([string]$Row.profile_id))
    Save-HmsProxySidecarRows $rows
    try{Record-HmsProxyFleetAction ([string]$Row.profile_id) "STOP_SIDECAR" "PASS" ("PID="+$procId+" port="+$port)}catch{}
    return "Sidecar STOP PASS: $($Row.profile_name)"
}
function Start-HmsProxySidecarsHealthy {
    Initialize-HmsProxyFleet
    $plan=Get-HmsProxySidecarPlan
    $started=0;$blocked=0
    foreach($g in @($plan.groups)){
        if([int]$g.account_count -lt 1){continue}
        if(-not [bool]$g.start_allowed){$blocked++;continue}
        if((Get-HmsProxyFleetOpsState ([string]$g.profile_id)) -ne "ACTIVE"){$blocked++;continue}
        if([bool]$script:S.ProxyEgressRequireBeforeSidecarStart){
            $eg=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq ([string]$g.profile_id)|Select-Object -First 1)
            if($eg.Count -lt 1 -or [string]$eg[0].Integrity -ne "PASS" -or [bool]$eg[0].StrictBlock){$blocked++;continue}
            if(-not (Test-HmsEvidenceFresh $eg[0].CheckedUtc ([int]$script:S.ProxyEgressMaxAgeSec))){$blocked++;continue}
        }
        $state=Get-HmsProxySidecarState
        $old=@($state.sidecars|Where-Object profile_id -eq ([string]$g.profile_id)|Select-Object -First 1)
        if($old.Count -gt 0 -and (ListenerPid ([int]$old[0].port)) -eq [int]$old[0].pid){continue}
        try{$null=Start-HmsProxySidecar $g;$started++}catch{$blocked++}
    }
    return "Proxy sidecars: started=$started blocked=$blocked"
}
function Stop-HmsProxySidecarsOwned {
    $state=Get-HmsProxySidecarState
    $stopped=0;$blocked=0
    foreach($r in @($state.sidecars)){
        $m=Stop-HmsProxySidecar $r
        if($m -like "*PASS*"){$stopped++}else{$blocked++}
    }
    return "Proxy sidecars stop: stopped=$stopped blocked=$blocked"
}
function Sync-HmsSmartGatewayProxyTargets {
    Initialize-HmsSmartGatewayConfig
    Initialize-HmsProxyFleet
    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    if(-not $cfg){throw "Smart Gateway config unavailable."}
    $state=Get-HmsProxySidecarState
    $targets=[System.Collections.Generic.List[object]]::new()
    foreach($r in @($state.sidecars)){
        $procId=[string]$r.profile_id
        if((Get-HmsProxyFleetOpsState $procId) -ne "ACTIVE"){continue}
        if([bool]$script:S.ProxyHealthRequiredBeforeStart){
            $hh=@(Get-HmsProxyHealthRows|Where-Object ProfileId -eq $procId|Select-Object -First 1)
            if($hh.Count -lt 1 -or [string]$hh[0].Status -ne "PASS"){continue}
            if(-not (Test-HmsEvidenceFresh $hh[0].CheckedUtc ([int]$script:S.ProxyHealthMaxAgeSec))){continue}
        }
        if([bool]$script:S.ProxyEgressRequireBeforeSidecarStart){
            $eg=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq $procId|Select-Object -First 1)
            if($eg.Count -lt 1 -or [string]$eg[0].Integrity -ne "PASS" -or [bool]$eg[0].StrictBlock){continue}
            if(-not (Test-HmsEvidenceFresh $eg[0].CheckedUtc ([int]$script:S.ProxyEgressMaxAgeSec))){continue}
        }
        $owner=ListenerPid ([int]$r.port)
        if($owner -ne [int]$r.pid){continue}
        $key=Get-HmsProxySecret ([string]$r.api_key_ref)
        if([string]::IsNullOrWhiteSpace($key)){continue}
        $envName=("HMS_SIDECAR_"+$procId.ToUpperInvariant().Replace("-","_")+"_KEY")
        [Environment]::SetEnvironmentVariable($envName,$key,"Process")
        $key=$null
        $targets.Add([PSCustomObject]@{
            id=("proxy-group:"+$procId)
            account=("GROUP "+[string]$r.profile_name)
            base_url=("http://127.0.0.1:"+[string][int]$r.port)
            api_key_env=$envName
            priority=10
            weight=1
            enabled=$true
            model_allow=@("*")
            model_deny=@()
            proxy_profile_id=$procId
            reset_utc=$null
        })
    }
    Add-Member -InputObject $cfg -NotePropertyName targets -NotePropertyValue @($targets) -Force
    Save-JsonAtomic $script:SmartGatewayConfigPath $cfg
    return "Smart Gateway proxy targets synced: $($targets.Count)"
}
function Get-HmsProxyAffinitySummary {
    $profiles=@(Get-HmsProxyProfiles)
    $bindings=@(Get-HmsProxyBindings)
    $health=@(Get-HmsProxyHealthRows)
    $sidecars=@((Get-HmsProxySidecarState).sidecars)
    $pass=@($health|Where-Object Status -eq "PASS").Count
    $assigned=@($bindings|Where-Object Status -eq "ASSIGNED").Count
    return "ProxyAffinity profiles=$($profiles.Count); healthy=$pass; assigned=$assigned/$($bindings.Count); sidecars=$($sidecars.Count); mode=$($script:S.ProxyAffinityMode)"
}
function Show-HmsAddProxyProfileDialog {
    $w=New-Object Windows.Forms.Form
    $w.Text="Thêm Proxy Profile"
    $w.Size=New-Object Drawing.Size(540,520);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(18,21,25);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $labels=@("Tên","Scheme","Host / IP","Port","Username","Password","Max accounts","Mode","ISP")
    $ys=@(25,70,115,160,205,250,295,340,385)
    $boxes=@{}
    foreach($i in 0..($labels.Count-1)){
        $l=New-Object Windows.Forms.Label;$l.Text=$labels[$i];$l.Location=New-Object Drawing.Point(20,$ys[$i]);$l.Size=New-Object Drawing.Size(120,25);$w.Controls.Add($l)
    }
    $name=New-Object Windows.Forms.TextBox;$name.Location=New-Object Drawing.Point(150,22);$name.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($name)
    $scheme=New-Object Windows.Forms.ComboBox;$scheme.Location=New-Object Drawing.Point(150,67);$scheme.Size=New-Object Drawing.Size(340,26);foreach($x in @("http","https","socks5")){[void]$scheme.Items.Add($x)};$scheme.SelectedItem="http";$w.Controls.Add($scheme)
    $proxyHost=New-Object Windows.Forms.TextBox;$proxyHost.Location=New-Object Drawing.Point(150,112);$proxyHost.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($proxyHost)
    $port=New-Object Windows.Forms.NumericUpDown;$port.Location=New-Object Drawing.Point(150,157);$port.Minimum=1;$port.Maximum=65535;$port.Value=1080;$port.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($port)
    $user=New-Object Windows.Forms.TextBox;$user.Location=New-Object Drawing.Point(150,202);$user.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($user)
    $pass=New-Object Windows.Forms.TextBox;$pass.Location=New-Object Drawing.Point(150,247);$pass.Size=New-Object Drawing.Size(340,26);$pass.UseSystemPasswordChar=$true;$w.Controls.Add($pass)
    $max=New-Object Windows.Forms.NumericUpDown;$max.Location=New-Object Drawing.Point(150,292);$max.Minimum=1;$max.Maximum=50;$max.Value=[int]$script:S.ProxyAccountsPerProxy;$max.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($max)
    $mode=New-Object Windows.Forms.ComboBox;$mode.Location=New-Object Drawing.Point(150,337);$mode.Size=New-Object Drawing.Size(340,26);foreach($x in @("STRICT","STICKY_FAILOVER","DIRECT_FALLBACK")){[void]$mode.Items.Add($x)};$mode.SelectedItem="STRICT";$w.Controls.Add($mode)
    $isp=New-Object Windows.Forms.TextBox;$isp.Location=New-Object Drawing.Point(150,382);$isp.Size=New-Object Drawing.Size(340,26);$w.Controls.Add($isp)
    $ok=Btn "THÊM PROXY" 270 430 110 34;$w.Controls.Add($ok)
    $cancel=Btn "HỦY" 390 430 100 34;$w.Controls.Add($cancel)
    $result=$null
    $ok.Add_Click({
        try{
            if([string]::IsNullOrWhiteSpace($name.Text) -or [string]::IsNullOrWhiteSpace($proxyHost.Text)){throw "Tên và Host không được trống."}
            $result=Add-HmsProxyProfile -Name $name.Text -Scheme ([string]$scheme.SelectedItem) -Host $proxyHost.Text -Port ([int]$port.Value) -Username $user.Text -Password $pass.Text -MaxAccounts ([int]$max.Value) -Mode ([string]$mode.SelectedItem) -Country "VN" -Isp $isp.Text
            $w.DialogResult=[Windows.Forms.DialogResult]::OK;$w.Close()
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $cancel.Add_Click({$w.DialogResult=[Windows.Forms.DialogResult]::Cancel;$w.Close()})
    [void]$w.ShowDialog($form)
    return $result
}
function Show-HmsProxyAffinityCenter {
    Initialize-HmsProxyAffinity
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Proxy Affinity & Egress Control v22.0"
    $w.Size=New-Object Drawing.Size(1500,880);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="PROXY AFFINITY & EGRESS CONTROL";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,53);$status.Size=New-Object Drawing.Size(850,40);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bAdd=Btn "ADD PROXY" 860 18 105 34;$w.Controls.Add($bAdd)
    $bAssign=Btn "AUTO ASSIGN" 975 18 115 34;$w.Controls.Add($bAssign)
    $bHealth=Btn "TEST ALL" 1100 18 100 34;$w.Controls.Add($bHealth)
    $bStart=Btn "START HEALTHY" 1210 18 125 34;$w.Controls.Add($bStart)
    $bStop=Btn "STOP OWNED" 1345 18 110 34;$w.Controls.Add($bStop)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1435,690);$w.Controls.Add($tabs)
    foreach($n in @("Proxy Profiles","Account Bindings","Health","Sidecars","Safety")){
        $tp=New-Object Windows.Forms.TabPage;$tp.Text=$n;$tp.BackColor=[Drawing.Color]::FromArgb(18,21,25);$tp.ForeColor=$w.ForeColor;$tabs.TabPages.Add($tp)
    }
    $gp=New-DarkGrid 15 20 1365 555 $tabs.TabPages[0]
    $gb=New-DarkGrid 15 20 1365 555 $tabs.TabPages[1]
    $gh=New-DarkGrid 15 20 1365 555 $tabs.TabPages[2]
    $gs=New-DarkGrid 15 20 1365 555 $tabs.TabPages[3]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1365,555);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="V22 PROXY SAFETY`r`n`r`nDEFAULT = STRICT / FAIL-CLOSED.`r`n• 4–5 account có thể gắn cùng một proxy profile.`r`n• Binding được giữ ổn định; auto-assign không shuffle account đã có nếu còn capacity.`r`n• Proxy password lưu DPAPI CurrentUser, không lưu plaintext trong profile JSON.`r`n• Mỗi proxy group chạy CLIProxyAPI sidecar riêng với global proxy-url.`r`n• Sidecar auth được COPY sang generation mới; không move/delete auth gốc.`r`n• Proxy health không PASS => STRICT group không start.`r`n• Port có foreign PID => BLOCKED, HMS không kill/chiếm port.`r`n• Không tự rotate proxy theo từng request.`r`n• DIRECT_FALLBACK mặc định bị tắt toàn hệ thống.`r`n• Sidecar config có thể chứa proxy credential đã resolve, nên generation dir được giới hạn ACL CurrentUser + SYSTEM.`r`n• Smart Gateway chỉ nhận các sidecar đang chạy và verified ownership."
    $tabs.TabPages[4].Controls.Add($safe)
    $bSync=Btn "SYNC SMART GATEWAY" 15 590 190 34;$tabs.TabPages[3].Controls.Add($bSync)

    function Refresh-P {
        $profiles=@(Get-HmsProxyProfiles)
        $bindings=@(Get-HmsProxyBindings)
        $health=@(Get-HmsProxyHealthRows)
        $state=Get-HmsProxySidecarState
        $gp.DataSource=$null;$gp.DataSource=@($profiles|ForEach-Object{
            [PSCustomObject]@{Id=$_.id;Name=$_.name;Scheme=$_.scheme;Host=$_.host;Port=$_.port;Mode=$_.mode;MaxAccounts=$_.max_accounts;Country=$_.country;ISP=$_.isp;Enabled=$_.enabled;Secret=if($_.secret_ref){"DPAPI"}else{"None"}}
        })
        $gb.DataSource=$null;$gb.DataSource=@($bindings|ForEach-Object{
            [PSCustomObject]@{Account=$_.email;AuthFile=$_.filename;ProxyProfile=$_.proxy_profile_id;Status=$_.status;Updated=$_.updated_utc}
        })
        $gh.DataSource=$null;$gh.DataSource=$health
        $gs.DataSource=$null;$gs.DataSource=@($state.sidecars|ForEach-Object{
            $owner=ListenerPid ([int]$_.port)
            [PSCustomObject]@{Profile=$_.profile_name;Port=$_.port;PID=$_.pid;OwnerOK=($owner -eq [int]$_.pid);Accounts=$_.account_count;Status=$_.status;Started=$_.started_utc;Generation=$_.generation}
        })
        $status.Text=Get-HmsProxyAffinitySummary
    }
    $bAdd.Add_Click({try{$null=Show-HmsAddProxyProfileDialog;Refresh-P}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bAssign.Add_Click({try{$status.Text=Invoke-HmsProxyAutoAssign;Refresh-P}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bHealth.Add_Click({
        try{
            $m1=Invoke-HmsProxyHealthCheckAll
            $m2=if([bool]$script:S.ProxyEgressProbeEnabled){Invoke-HmsProxyEgressProbeAll}else{"Egress disabled"}
            $null=Invoke-HmsProxyFleetSupervisorCycle
            $status.Text=$m1+" | "+$m2
            Refresh-P
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $bStart.Add_Click({try{$status.Text=Start-HmsProxySidecarsHealthy;Refresh-P}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bStop.Add_Click({try{$status.Text=Stop-HmsProxySidecarsOwned;Refresh-P}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bSync.Add_Click({try{$status.Text=Sync-HmsSmartGatewayProxyTargets;Refresh-P}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $w.Add_Shown({Refresh-P})
    [void]$w.ShowDialog($form)
}


# ============================================================
# PROXY FLEET SUPERVISOR & EGRESS INTEGRITY v23.0
# ============================================================
function Initialize-HmsProxyFleet {
    Initialize-HmsProxyAffinity
    if(-not (Test-Path $script:ProxyEgressPath)){
        Save-JsonAtomic $script:ProxyEgressPath ([ordered]@{version=23;profiles=[ordered]@{}})
    }
    if(-not (Test-Path $script:ProxyFleetStatePath)){
        Save-JsonAtomic $script:ProxyFleetStatePath ([ordered]@{version=23;profiles=[ordered]@{}})
    }
}
function Test-HmsEvidenceFresh {
    param([object]$UtcValue,[int]$MaxAgeSec)
    if(-not $UtcValue){return $false}
    try{
        $dt=[DateTimeOffset]::Parse([string]$UtcValue)
        $age=([DateTimeOffset]::UtcNow-$dt.ToUniversalTime()).TotalSeconds
        return ($age -ge 0 -and $age -le [Math]::Max(1,$MaxAgeSec))
    }catch{return $false}
}
function Get-HmsProxyEgressRows {
    Initialize-HmsProxyFleet
    $j=Load-JsonObjectSafe $script:ProxyEgressPath
    if(-not $j -or -not $j.profiles){return @()}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($prop in @($j.profiles.PSObject.Properties)){
        $v=$prop.Value
        $rows.Add([PSCustomObject]@{
            ProfileId=$prop.Name
            Integrity=[string]$v.integrity_status
            ExpectedIp=$v.expected_ip
            ObservedIp=$v.observed_ip
            IpVersion=$v.ip_version
            LatencyMs=$v.latency_ms
            DriftCount=$v.drift_count
            StrictBlock=[bool]$v.strict_block
            CheckedUtc=$v.checked_utc
            Error=$v.error
        })
    }
    return @($rows)
}
function Invoke-HmsProxyEgressProbe {
    param([object]$Profile)
    Initialize-HmsProxyFleet
    if(-not [bool]$script:S.ProxyEgressProbeEnabled){return "Egress probe disabled."}
    if(-not $Profile){throw "Proxy profile trống."}
    $guard=Join-Path $PSScriptRoot "HMS_Codex_EgressGuard.py"
    if(-not (Test-Path $guard)){throw "Thiếu HMS_Codex_EgressGuard.py"}
    $secret=Get-HmsProxySecret ([string]$Profile.secret_ref)
    $old=[Environment]::GetEnvironmentVariable("HMS_PROXY_PASSWORD","Process")
    try{
        [Environment]::SetEnvironmentVariable("HMS_PROXY_PASSWORD",$secret,"Process")
        $args=@(
            $guard,
            "--profile-id",[string]$Profile.id,
            "--scheme",[string]$Profile.scheme,
            "--host",[string]$Profile.host,
            "--port",[string][int]$Profile.port,
            "--url",[string]$script:S.ProxyEgressProbeUrl,
            "--timeout",[string][int]$script:S.ProxyEgressTimeoutSec,
            "--state",$script:ProxyEgressPath
        )
        if(-not [string]::IsNullOrWhiteSpace([string]$Profile.username)){
            $args+=@("--username",[string]$Profile.username)
        }
        if(-not [bool]$script:S.ProxyEgressAutoLearnBaseline){$args+="-no-auto -le arn"}
        if(-not [bool]$script:S.ProxyEgressRequireStableIp){$args+="-allow-drift"}
        $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
        $code=$LASTEXITCODE
        $row=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq ([string]$Profile.id)|Select-Object -First 1)
        if($row.Count -gt 0){
            return "Egress $($Profile.name): $($row[0].Integrity) expected=$($row[0].ExpectedIp) observed=$($row[0].ObservedIp) code=$code"
        }
        return ($raw -join "`r`n")
    }finally{
        [Environment]::SetEnvironmentVariable("HMS_PROXY_PASSWORD",$old,"Process")
        $secret=$null
    }
}
function Invoke-HmsProxyEgressProbeAll {
    $profiles=@(Get-HmsProxyProfiles|Where-Object enabled -eq $true)
    $pass=0;$blocked=0
    foreach($p in $profiles){
        try{
            $null=Invoke-HmsProxyEgressProbe $p
            $e=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq ([string]$p.id)|Select-Object -First 1)
            if($e.Count -gt 0 -and [string]$e[0].Integrity -eq "PASS"){$pass++}else{$blocked++}
        }catch{$blocked++}
    }
    return "Egress Integrity: PASS=$pass BLOCKED=$blocked"
}
function Set-HmsProxyEgressBaseline {
    param([string]$ProfileId,[string]$Ip="")
    Initialize-HmsProxyFleet
    if([string]::IsNullOrWhiteSpace($Ip)){
        $row=@(Get-HmsProxyEgressRows|Where-Object ProfileId -eq $ProfileId|Select-Object -First 1)
        if($row.Count -lt 1 -or [string]::IsNullOrWhiteSpace([string]$row[0].ObservedIp)){throw "Chưa có observed IP."}
        $Ip=[string]$row[0].ObservedIp
    }
    $guard=Join-Path $PSScriptRoot "HMS_Codex_EgressGuard.py"
    $raw=& ([string]$script:S.CodexSessionDoctorPython) $guard `
        --profile-id $ProfileId --state $script:ProxyEgressPath --set-baseline $Ip
    if($LASTEXITCODE -ne 0){throw "Set egress baseline FAIL: $raw"}
    return "Baseline $ProfileId = $Ip"
}
function Get-HmsProxyFleetOpsState {
    param([string]$ProfileId)
    Initialize-HmsProxyFleet
    $j=Load-JsonObjectSafe $script:ProxyFleetStatePath
    if(-not $j -or -not $j.profiles){return "ACTIVE"}
    $prop=$j.profiles.PSObject.Properties[$ProfileId]
    if(-not $prop){return "ACTIVE"}
    $state=[string]$prop.Value.ops_state
    if([string]::IsNullOrWhiteSpace($state)){return "ACTIVE"}
    return $state
}
function Set-HmsProxyFleetOpsState {
    param([string]$ProfileId,[string]$State,[string]$Reason="")
    Initialize-HmsProxyFleet
    $fleet=Join-Path $PSScriptRoot "HMS_Codex_ProxyFleet.py"
    $raw=& ([string]$script:S.CodexSessionDoctorPython) $fleet `
        --profiles $script:ProxyProfilesPath `
        --bindings $script:ProxyBindingsPath `
        --health $script:ProxyHealthPath `
        --egress $script:ProxyEgressPath `
        --sidecars $script:ProxySidecarStatePath `
        --fleet-state $script:ProxyFleetStatePath `
        --history $script:ProxyFleetHistoryPath `
        --actions $script:ProxyFleetActionHistoryPath `
        set-state --profile-id $ProfileId --state $State --reason $Reason
    if($LASTEXITCODE -ne 0){throw "Set proxy fleet state FAIL: $raw"}
    $null=Sync-HmsSmartGatewayProxyTargets
    return "$ProfileId -> $State"
}
function Record-HmsProxyFleetAction {
    param([string]$ProfileId,[string]$Action,[string]$Result,[string]$Detail="")
    $fleet=Join-Path $PSScriptRoot "HMS_Codex_ProxyFleet.py"
    & ([string]$script:S.CodexSessionDoctorPython) $fleet `
        --profiles $script:ProxyProfilesPath `
        --bindings $script:ProxyBindingsPath `
        --health $script:ProxyHealthPath `
        --egress $script:ProxyEgressPath `
        --sidecars $script:ProxySidecarStatePath `
        --fleet-state $script:ProxyFleetStatePath `
        --history $script:ProxyFleetHistoryPath `
        --actions $script:ProxyFleetActionHistoryPath `
        record-action --profile-id $ProfileId --action $Action --result $Result --detail $Detail | Out-Null
}
function Invoke-HmsProxyFleetAudit {
    Initialize-HmsProxyFleet
    $fleet=Join-Path $PSScriptRoot "HMS_Codex_ProxyFleet.py"
    $args=@(
        $fleet,
        "--profiles",$script:ProxyProfilesPath,
        "--bindings",$script:ProxyBindingsPath,
        "--health",$script:ProxyHealthPath,
        "--egress",$script:ProxyEgressPath,
        "--sidecars",$script:ProxySidecarStatePath,
        "--fleet-state",$script:ProxyFleetStatePath,
        "--history",$script:ProxyFleetHistoryPath,
        "--actions",$script:ProxyFleetActionHistoryPath,
        "audit",
        "--max-restarts-hour",[string][int]$script:S.ProxyFleetMaxRestartsPerHour,
        "--recovery-cooldown",[string][int]$script:S.ProxyFleetRecoveryCooldownSec,
        "--health-max-age",[string][int]$script:S.ProxyHealthMaxAgeSec,
        "--egress-max-age",[string][int]$script:S.ProxyEgressMaxAgeSec
    )
    if(-not [bool]$script:S.ProxyFleetQuarantineOnHealthFail){$args+="-no-health-quarantine"}
    if(-not [bool]$script:S.ProxyEgressDriftQuarantine){$args+="-no-drift-quarantine"}
    $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
    if($LASTEXITCODE -ne 0){throw "Proxy Fleet audit FAIL: $raw"}
    $j=($raw -join "`n")|ConvertFrom-Json
    Save-JsonAtomic $script:ProxyFleetLatestPath $j.data
    return $j.data
}
function Invoke-HmsProxyFleetSupervisorCycle {
    if(-not [bool]$script:S.ProxyFleetAuditEnabled){return $null}
    $audit=Invoke-HmsProxyFleetAudit

    # Safety-first quarantine is restrictive metadata only; no foreign process stop.
    foreach($row in @($audit.profiles)){
        if([string]$row.ops_state -ne "ACTIVE"){continue}
        if(([string]$row.recommendation -eq "QUARANTINE_EGRESS_DRIFT") -and [bool]$script:S.ProxyEgressDriftQuarantine){
            $null=Set-HmsProxyFleetOpsState ([string]$row.profile_id) "QUARANTINED" "EGRESS_DRIFT"
        }elseif(([string]$row.recommendation -eq "QUARANTINE_HEALTH_FAIL") -and [bool]$script:S.ProxyFleetQuarantineOnHealthFail){
            $null=Set-HmsProxyFleetOpsState ([string]$row.profile_id) "QUARANTINED" "HEALTH_FAIL"
        }
    }

    if([bool]$script:S.ProxyFleetAutoRecovery -and (-not $script:RuntimeAutomationBlocked)){
        $plan=Get-HmsProxySidecarPlan
        foreach($row in @($audit.profiles)){
            if([string]$row.auto_action -ne "START_SIDECAR"){continue}
            if([string]$row.ops_state -ne "ACTIVE"){continue}
            $g=@($plan.groups|Where-Object profile_id -eq ([string]$row.profile_id)|Select-Object -First 1)
            if($g.Count -lt 1){continue}
            try{
                $msg=Start-HmsProxySidecar $g[0]
                Record-HmsProxyFleetAction ([string]$row.profile_id) "START_SIDECAR" "PASS" $msg
            }catch{
                Record-HmsProxyFleetAction ([string]$row.profile_id) "START_SIDECAR" "FAIL" $_.Exception.Message
            }
        }
    }
    try{$null=Sync-HmsSmartGatewayProxyTargets}catch{}
    return $audit
}
function ConvertFrom-HmsProxyUrl {
    param([string]$ProxyUrl)
    $u=[Uri]$ProxyUrl
    if($u.Scheme -notin @("http","https","socks5")){throw "Proxy scheme không hỗ trợ: $($u.Scheme)"}
    $user="";$pass=""
    if(-not [string]::IsNullOrWhiteSpace($u.UserInfo)){
        $parts=$u.UserInfo.Split(':',2)
        $user=[Uri]::UnescapeDataString($parts[0])
        if($parts.Count -gt 1){$pass=[Uri]::UnescapeDataString($parts[1])}
    }
    return [PSCustomObject]@{
        scheme=$u.Scheme
        host=$u.Host
        port=$u.Port
        username=$user
        password=$pass
    }
}
function Import-HmsProxyFile {
    param([string]$Path)
    Initialize-HmsProxyFleet
    if(-not (Test-Path $Path)){throw "File proxy không tồn tại: $Path"}
    $ext=[IO.Path]::GetExtension($Path).ToLowerInvariant()
    $rows=@()
    if($ext -eq ".csv"){
        $rows=@(Import-Csv -LiteralPath $Path)
    }elseif($ext -eq ".json"){
        $j=Get-Content -LiteralPath $Path -Raw -Encoding UTF8|ConvertFrom-Json
        if($j -is [Array]){$rows=@($j)}elseif($j.proxies){$rows=@($j.proxies)}else{$rows=@($j)}
    }elseif($ext -eq ".txt"){
        $rows=@(Get-Content -LiteralPath $Path -Encoding UTF8|Where-Object{
            -not [string]::IsNullOrWhiteSpace($_) -and (-not $_.Trim().StartsWith("#"))
        }|ForEach-Object{[PSCustomObject]@{proxy_url=$_.Trim()}})
    }else{
        throw "Chỉ hỗ trợ CSV / JSON / TXT."
    }

    $ok=0;$fail=0
    foreach($r in $rows){
        $password=""
        try{
            $name=[string]$r.name
            $scheme=[string]$r.scheme
            $proxyHost=[string]$r.host
            $port=0
            if($r.port){$port=[int]$r.port}
            $username=[string]$r.username
            $password=[string]$r.password
            if($r.proxy_url){
                $u=ConvertFrom-HmsProxyUrl ([string]$r.proxy_url)
                if([string]::IsNullOrWhiteSpace($scheme)){$scheme=$u.scheme}
                if([string]::IsNullOrWhiteSpace($proxyHost)){$proxyHost=$u.host}
                if($port -le 0){$port=[int]$u.port}
                if([string]::IsNullOrWhiteSpace($username)){$username=$u.username}
                if([string]::IsNullOrEmpty($password)){$password=$u.password}
            }
            if([string]::IsNullOrWhiteSpace($name)){$name="Proxy-"+($ok+$fail+1)}
            $mode=if($r.mode){[string]$r.mode}else{[string]$script:S.ProxyFleetImportDefaultMode}
            $max=if($r.max_accounts){[int]$r.max_accounts}else{[int]$script:S.ProxyFleetImportMaxAccounts}
            $country=if($r.country){[string]$r.country}else{"VN"}
            $isp=[string]$r.isp
            $null=Add-HmsProxyProfile -Name $name -Scheme $scheme -Host $proxyHost -Port $port `
                -Username $username -Password $password -MaxAccounts $max -Mode $mode -Country $country -Isp $isp
            $ok++
        }catch{$fail++}
        finally{$password=$null}
    }
    Add-Content -LiteralPath $script:ProxyImportAuditPath -Value (([ordered]@{
        time=[DateTime]::UtcNow.ToString("o")
        source=[IO.Path]::GetFileName($Path)
        rows=$rows.Count
        imported=$ok
        failed=$fail
        passwordLogged=$false
    })|ConvertTo-Json -Compress -Depth 4) -Encoding UTF8
    return "Proxy Import: imported=$ok failed=$fail total=$($rows.Count)"
}
function Show-HmsProxyImportDialog {
    $dlg=New-Object Windows.Forms.OpenFileDialog
    $dlg.Title="Nhập danh sách proxy"
    $dlg.Filter="Proxy files (*.csv;*.json;*.txt)|*.csv;*.json;*.txt|All files (*.*)|*.*"
    if($dlg.ShowDialog($form) -ne [Windows.Forms.DialogResult]::OK){return "Canceled"}
    return Import-HmsProxyFile $dlg.FileName
}
function Get-HmsProxyFleetSummary {
    $a=Load-JsonObjectSafe $script:ProxyFleetLatestPath
    if(-not $a){return "Proxy Fleet chưa audit."}
    return "ProxyFleet=$($a.verdict); healthy=$($a.summary.healthy)/$($a.summary.total); critical=$($a.summary.critical); quarantine=$($a.summary.quarantined); recoverable=$($a.summary.recoverable)"
}
function Show-HmsProxyFleetCenter {
    Initialize-HmsProxyFleet
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Proxy Fleet Supervisor & Egress Integrity v23.0"
    $w.Size=New-Object Drawing.Size(1540,900);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="PROXY FLEET SUPERVISOR & EGRESS INTEGRITY";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,54);$status.Size=New-Object Drawing.Size(850,38);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bAudit=Btn "AUDIT FLEET" 885 18 115 34;$w.Controls.Add($bAudit)
    $bEgress=Btn "TEST EGRESS" 1010 18 115 34;$w.Controls.Add($bEgress)
    $bImport=Btn "IMPORT PROXY" 1135 18 120 34;$w.Controls.Add($bImport)
    $bAffinity=Btn "AFFINITY CENTER" 1265 18 130 34;$w.Controls.Add($bAffinity)
    $bSync=Btn "SYNC GATEWAY" 1405 18 110 34;$w.Controls.Add($bSync)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1490,700);$w.Controls.Add($tabs)
    foreach($n in @("Fleet","Egress Integrity","Actions","Import Format","Safety")){
        $tp=New-Object Windows.Forms.TabPage;$tp.Text=$n;$tp.BackColor=[Drawing.Color]::FromArgb(18,21,25);$tp.ForeColor=$w.ForeColor;$tabs.TabPages.Add($tp)
    }
    $gf=New-DarkGrid 15 20 1415 540 $tabs.TabPages[0]
    $ge=New-DarkGrid 15 20 1415 540 $tabs.TabPages[1]
    $ga=New-DarkGrid 15 20 1415 540 $tabs.TabPages[2]

    $bActive=Btn "ACTIVATE" 15 575 105 34;$tabs.TabPages[0].Controls.Add($bActive)
    $bDrain=Btn "DRAIN" 130 575 105 34;$tabs.TabPages[0].Controls.Add($bDrain)
    $bQuarantine=Btn "QUARANTINE" 245 575 120 34;$tabs.TabPages[0].Controls.Add($bQuarantine)
    $bBaseline=Btn "SET OBSERVED AS BASELINE" 15 575 210 34;$tabs.TabPages[1].Controls.Add($bBaseline)

    $fmt=New-Object Windows.Forms.TextBox;$fmt.Location=New-Object Drawing.Point(15,20);$fmt.Size=New-Object Drawing.Size(1415,600);$fmt.Multiline=$true;$fmt.ReadOnly=$true;$fmt.ScrollBars="Both";$fmt.WordWrap=$false;$fmt.BackColor=[Drawing.Color]::FromArgb(20,23,27);$fmt.ForeColor=$w.ForeColor
    $fmt.Text="CSV columns:`r`nname,scheme,host,port,username,password,max_accounts,mode,country,isp,proxy_url`r`n`r`nExamples:`r`nVN-01,http,1.2.3.4,8080,user,password,5,STRICT,VN,Viettel,`r`nVN-02,,,,,,,STRICT,VN,,socks5://user:password@5.6.7.8:1080`r`n`r`nTXT: one proxy URL per line.`r`nJSON: array of the same fields or { proxies: [...] }.`r`n`r`nPasswords are processed in memory -> DPAPI; import audit never stores password."
    $tabs.TabPages[3].Controls.Add($fmt)

    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1415,600);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="V23 EGRESS SAFETY`r`n`r`n• Public IP probe luôn đi QUA proxy profile, không gọi DIRECT để làm fallback.`r`n• Default probe: api.ipify.org JSON endpoint.`r`n• First successful probe có thể auto -le arn baseline.`r`n• Expected IP khác Observed IP => DRIFT.`r`n• DRIFT/health FAIL có thể tự QUARANTINE metadata; không kill foreign process.`r`n• QUARANTINED/DRAINING proxy group bị loại khỏi Smart Gateway target sync.`r`n• STRICT sidecar start yêu cầu Health PASS + Egress PASS.`r`n• Auto-recovery mặc định OFF; khi bật chỉ start sidecar của ACTIVE/healthy/stable group và vẫn dùng ownership gates.`r`n• Import không scrape free public proxy và không log password.`r`n• DRAIN chỉ ngăn route mới; operator quyết định stop sidecar sau grace period."
    $tabs.TabPages[4].Controls.Add($safe)

    function Refresh-Fleet {
        try{$null=Invoke-HmsProxyFleetAudit}catch{}
        $a=Load-JsonObjectSafe $script:ProxyFleetLatestPath
        $gf.DataSource=$null
        if($a){
            $gf.DataSource=@($a.profiles|ForEach-Object{
                [PSCustomObject]@{
                    Profile=$_.profile_name;Id=$_.profile_id;Ops=$_.ops_state;Severity=$_.severity;
                    Health=$_.health_status;Egress=$_.egress_status;ExpectedIP=$_.expected_ip;ObservedIP=$_.observed_ip;
                    Assigned=$_.assigned;Capacity=$_.capacity;Sidecar=$_.sidecar_running;Port=$_.sidecar_port;
                    Recommendation=$_.recommendation
                }
            })
        }
        $ge.DataSource=$null;$ge.DataSource=@(Get-HmsProxyEgressRows)
        $actions=@()
        if(Test-Path $script:ProxyFleetActionHistoryPath){
            $actions=@(Get-Content $script:ProxyFleetActionHistoryPath -Tail 300 -Encoding UTF8|ForEach-Object{
                try{$_|ConvertFrom-Json}catch{}
            }|Where-Object{$_})
        }
        $ga.DataSource=$null;$ga.DataSource=$actions
        $status.Text=(Get-HmsProxyFleetSummary)+" | "+(Get-HmsProxyAffinitySummary)
    }
    function Selected-FleetId {
        if($gf.SelectedRows.Count -lt 1){return ""}
        return [string]$gf.SelectedRows[0].Cells["Id"].Value
    }
    function Selected-EgressId {
        if($ge.SelectedRows.Count -lt 1){return ""}
        return [string]$ge.SelectedRows[0].Cells["ProfileId"].Value
    }
    $bAudit.Add_Click({try{$null=Invoke-HmsProxyFleetSupervisorCycle;Refresh-Fleet}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bEgress.Add_Click({try{$status.Text=Invoke-HmsProxyEgressProbeAll;$null=Invoke-HmsProxyFleetSupervisorCycle;Refresh-Fleet}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bImport.Add_Click({try{$status.Text=Show-HmsProxyImportDialog;Refresh-Fleet}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bAffinity.Add_Click({Show-HmsProxyAffinityCenter;Refresh-Fleet})
    $bSync.Add_Click({try{$status.Text=Sync-HmsSmartGatewayProxyTargets;Refresh-Fleet}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bActive.Add_Click({try{$id=Selected-FleetId;if($id){$status.Text=Set-HmsProxyFleetOpsState $id "ACTIVE" "OPERATOR_ACTIVATE";Refresh-Fleet}}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bDrain.Add_Click({try{$id=Selected-FleetId;if($id){$status.Text=Set-HmsProxyFleetOpsState $id "DRAINING" "OPERATOR_DRAIN";Refresh-Fleet}}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bQuarantine.Add_Click({try{$id=Selected-FleetId;if($id){$status.Text=Set-HmsProxyFleetOpsState $id "QUARANTINED" "OPERATOR_QUARANTINE";Refresh-Fleet}}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bBaseline.Add_Click({try{$id=Selected-EgressId;if($id){$status.Text=Set-HmsProxyEgressBaseline $id;Refresh-Fleet}}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $w.Add_Shown({Refresh-Fleet})
    [void]$w.ShowDialog($form)
}


# ============================================================
# CODEX API SUPERSET & COCKPIT PARITY AUDITOR v24.0
# ============================================================
function Initialize-HmsApiSuperset {
    Ensure-Dir $script:ApiSupersetDir
    Initialize-HmsSmartGatewayConfig
    if(-not (Test-Path $script:ApiPricingPath)){
        $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
        Save-JsonAtomic $script:ApiPricingPath ([ordered]@{
            version=24
            prices=$cfg.model_prices
            note="No hard-coded model prices. Values are operator-managed."
        })
    }
}
function Invoke-HmsApiAnalytics {
    Initialize-HmsApiSuperset
    $tool=Join-Path $PSScriptRoot "HMS_Codex_ApiAnalytics.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_ApiAnalytics.py"}
    $raw=& ([string]$script:S.CodexSessionDoctorPython) $tool `
        --trace $script:SmartGatewayTracePath `
        --max-lines ([string][int]$script:S.ApiAnalyticsMaxTraceLines) `
        --output $script:ApiAnalyticsLatestPath
    if($LASTEXITCODE -ne 0){throw "API Analytics FAIL: $raw"}
    $j=Load-JsonObjectSafe $script:ApiAnalyticsLatestPath
    if($j -and $j.data){
        Add-Content -LiteralPath $script:ApiAnalyticsHistoryPath -Value (([ordered]@{
            time=[DateTime]::UtcNow.ToString("o")
            requests=$j.data.windows.all.total.requests
            successRate=$j.data.windows.all.total.success_rate_pct
            totalTokens=$j.data.windows.all.total.total_tokens
            estimatedUsd=$j.data.windows.all.total.estimated_usd
        })|ConvertTo-Json -Compress -Depth 5) -Encoding UTF8
    }
    return $j
}
function Invoke-HmsCockpitParityAudit {
    Initialize-HmsApiSuperset
    $tool=Join-Path $PSScriptRoot "HMS_Cockpit_ParityAuditor.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Cockpit_ParityAuditor.py"}
    $raw=& ([string]$script:S.CodexSessionDoctorPython) $tool `
        --root $PSScriptRoot --output $script:ApiParityLatestPath
    if($LASTEXITCODE -ne 0){throw "Parity Auditor FAIL: $raw"}
    $j=Load-JsonObjectSafe $script:ApiParityLatestPath
    if($j -and $j.data){
        Add-Content -LiteralPath $script:ApiParityHistoryPath -Value (([ordered]@{
            time=[DateTime]::UtcNow.ToString("o")
            verdict=$j.data.hms.verdict
            featureScore=$j.data.hms.feature_evidence_score_pct
            productionScore=$j.data.hms.production_evidence_score_pct
            windowsRuntimeCertified=$j.data.hms.windows_runtime_certified
        })|ConvertTo-Json -Compress -Depth 5) -Encoding UTF8
    }
    return $j
}
function Set-HmsApiModelPrice {
    param([string]$Model,[double]$InputPerMillion,[double]$OutputPerMillion,[double]$CachedInputPerMillion=-1)
    Initialize-HmsApiSuperset
    if([string]::IsNullOrWhiteSpace($Model)){throw "Model trống."}
    if($InputPerMillion -lt 0 -or $OutputPerMillion -lt 0){throw "Giá không được âm."}
    if($CachedInputPerMillion -lt 0){$CachedInputPerMillion=$InputPerMillion}
    $ctl=Join-Path $PSScriptRoot "HMS_Codex_GatewayControl.py"
    $raw=& ([string]$script:S.CodexSessionDoctorPython) $ctl `
        --config $script:SmartGatewayConfigPath --keys $script:SmartGatewayKeysPath `
        set-price --model $Model --input ([string]$InputPerMillion) --output ([string]$OutputPerMillion) `
        --cached-input ([string]$CachedInputPerMillion)
    if($LASTEXITCODE -ne 0){throw "Set price FAIL: $raw"}
    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    Save-JsonAtomic $script:ApiPricingPath ([ordered]@{version=24;prices=$cfg.model_prices;updatedUtc=[DateTime]::UtcNow.ToString("o")})
    return "Price updated: $Model"
}
function Show-HmsApiKeyPolicyDialog {
    Initialize-HmsApiSuperset
    $keydb=Load-JsonObjectSafe $script:SmartGatewayKeysPath
    $keys=@($keydb.keys)
    if($keys.Count -lt 1){[Windows.Forms.MessageBox]::Show("Chưa có client key.")|Out-Null;return}
    $w=New-Object Windows.Forms.Form
    $w.Text="Client Key Routing Policy v24"
    $w.Size=New-Object Drawing.Size(620,610);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(18,21,25);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $labels=@("Client Key","Strategy","Target allow (comma)","Target deny (comma)","Single target","Model prefix","Quota reserve %","Priority target=value","Weight target=value","Backup targets")
    $ys=@(25,70,115,160,205,250,295,340,385,430)
    foreach($i in 0..($labels.Count-1)){
        $l=New-Object Windows.Forms.Label;$l.Text=$labels[$i];$l.Location=New-Object Drawing.Point(20,$ys[$i]);$l.Size=New-Object Drawing.Size(170,25);$w.Controls.Add($l)
    }
    $keyBox=New-Object Windows.Forms.ComboBox;$keyBox.Location=New-Object Drawing.Point(200,22);$keyBox.Size=New-Object Drawing.Size(370,26)
    foreach($k in $keys){[void]$keyBox.Items.Add(([string]$k.id+" | "+[string]$k.name))};$keyBox.SelectedIndex=0;$w.Controls.Add($keyBox)
    $strategy=New-Object Windows.Forms.ComboBox;$strategy.Location=New-Object Drawing.Point(200,67);$strategy.Size=New-Object Drawing.Size(370,26)
    foreach($x in @("stable-round-robin","random","single","auto","quota-first","plan-first","expiry-soon","weighted","reset-aware","fill-first")){[void]$strategy.Items.Add($x)}
    $strategy.SelectedItem="stable-round-robin";$w.Controls.Add($strategy)
    $ta=New-Object Windows.Forms.TextBox;$ta.Location=New-Object Drawing.Point(200,112);$ta.Size=New-Object Drawing.Size(370,26);$ta.Text="*";$w.Controls.Add($ta)
    $td=New-Object Windows.Forms.TextBox;$td.Location=New-Object Drawing.Point(200,157);$td.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($td)
    $single=New-Object Windows.Forms.TextBox;$single.Location=New-Object Drawing.Point(200,202);$single.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($single)
    $prefix=New-Object Windows.Forms.TextBox;$prefix.Location=New-Object Drawing.Point(200,247);$prefix.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($prefix)
    $reserve=New-Object Windows.Forms.NumericUpDown;$reserve.Location=New-Object Drawing.Point(200,292);$reserve.Minimum=0;$reserve.Maximum=100;$reserve.DecimalPlaces=1;$reserve.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($reserve)
    $pri=New-Object Windows.Forms.TextBox;$pri.Location=New-Object Drawing.Point(200,337);$pri.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($pri)
    $wei=New-Object Windows.Forms.TextBox;$wei.Location=New-Object Drawing.Point(200,382);$wei.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($wei)
    $backup=New-Object Windows.Forms.TextBox;$backup.Location=New-Object Drawing.Point(200,427);$backup.Size=New-Object Drawing.Size(370,26);$w.Controls.Add($backup)
    $ok=Btn "APPLY POLICY" 345 500 120 34;$w.Controls.Add($ok)
    $cancel=Btn "CANCEL" 475 500 95 34;$w.Controls.Add($cancel)
    $ok.Add_Click({
        try{
            $kid=([string]$keyBox.SelectedItem).Split('|')[0].Trim()
            $ctl=Join-Path $PSScriptRoot "HMS_Codex_GatewayControl.py"
            $args=@($ctl,"--config",$script:SmartGatewayConfigPath,"--keys",$script:SmartGatewayKeysPath,
                "update-key-policy","--id",$kid,"--strategy",[string]$strategy.SelectedItem,
                "--model-prefix",$prefix.Text,"--quota-reserve-pct",[string][double]$reserve.Value)
            if(-not [string]::IsNullOrWhiteSpace($single.Text)){$args+=@("--single-target",$single.Text.Trim())}
            foreach($x in @($ta.Text.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})){$args+=@("--target-allow",$x)}
            foreach($x in @($td.Text.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})){$args+=@("--target-deny",$x)}
            foreach($x in @($pri.Text.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})){$args+=@("--priority",$x)}
            foreach($x in @($wei.Text.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})){$args+=@("--weight",$x)}
            foreach($x in @($backup.Text.Split(',')|ForEach-Object{$_.Trim()}|Where-Object{$_})){$args+=@("--backup-target",$x)}
            $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
            if($LASTEXITCODE -ne 0){throw "Policy update FAIL: $raw"}
            $w.DialogResult=[Windows.Forms.DialogResult]::OK;$w.Close()
        }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
    })
    $cancel.Add_Click({$w.Close()})
    [void]$w.ShowDialog($form)
}
function Show-HmsApiSupersetCenter {
    Initialize-HmsApiSuperset
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS Codex API Superset & Parity Auditor v24.0"
    $w.Size=New-Object Drawing.Size(1540,900);$w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(13,15,18);$w.ForeColor=[Drawing.Color]::FromArgb(239,242,246)
    $title=New-Object Windows.Forms.Label;$title.Text="CODEX API SUPERSET & COCKPIT PARITY";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",19);$title.Location=New-Object Drawing.Point(20,15);$title.AutoSize=$true;$w.Controls.Add($title)
    $status=New-Object Windows.Forms.Label;$status.Location=New-Object Drawing.Point(20,54);$status.Size=New-Object Drawing.Size(900,38);$status.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$w.Controls.Add($status)
    $bAnalytics=Btn "ANALYTICS" 950 18 105 34;$w.Controls.Add($bAnalytics)
    $bParity=Btn "PARITY AUDIT" 1065 18 115 34;$w.Controls.Add($bParity)
    $bPolicy=Btn "KEY POLICY" 1190 18 105 34;$w.Controls.Add($bPolicy)
    $bGateway=Btn "SMART GATEWAY" 1305 18 125 34;$w.Controls.Add($bGateway)
    $bOpen=Btn "OPEN DATA" 1440 18 80 34;$w.Controls.Add($bOpen)

    $tabs=New-Object Windows.Forms.TabControl;$tabs.Location=New-Object Drawing.Point(18,100);$tabs.Size=New-Object Drawing.Size(1490,700);$w.Controls.Add($tabs)
    foreach($n in @("Client Keys","Targets","Usage & Cost","Parity","Safety")){
        $tp=New-Object Windows.Forms.TabPage;$tp.Text=$n;$tp.BackColor=[Drawing.Color]::FromArgb(18,21,25);$tp.ForeColor=$w.ForeColor;$tabs.TabPages.Add($tp)
    }
    $gk=New-DarkGrid 15 20 1415 555 $tabs.TabPages[0]
    $gt=New-DarkGrid 15 20 1415 555 $tabs.TabPages[1]
    $gu=New-DarkGrid 15 20 1415 555 $tabs.TabPages[2]
    $gp=New-DarkGrid 15 20 1415 555 $tabs.TabPages[3]
    $safe=New-Object Windows.Forms.TextBox;$safe.Location=New-Object Drawing.Point(15,20);$safe.Size=New-Object Drawing.Size(1415,600);$safe.Multiline=$true;$safe.ReadOnly=$true;$safe.BackColor=[Drawing.Color]::FromArgb(20,23,27);$safe.ForeColor=$w.ForeColor
    $safe.Text="V24 API SUPERSET`r`n`r`n• Client-key scoped target pool and session affinity.`r`n• Routing: stable/random/single/auto/quota/plan/expiry/weighted/reset/fill-first.`r`n• Per-key priority/weight/backup overrides.`r`n• Quota reserve can fail closed when quota evidence is stale/missing.`r`n• Model prefix is rewritten back to canonical upstream model.`r`n• Loopback CORS preflight is local and allowlisted.`r`n• Usage capture never logs request bodies.`r`n• Pricing is operator-managed; HMS does not hard-code potentially stale model prices.`r`n• Parity score is evidence-weighted, not a real throughput benchmark.`r`n• Production score is intentionally penalized until Windows runtime certification."
    $tabs.TabPages[4].Controls.Add($safe)

    function Refresh-Api {
        $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
        $keys=Load-JsonObjectSafe $script:SmartGatewayKeysPath
        $gk.DataSource=$null;$gk.DataSource=@($keys.keys|ForEach-Object{
            [PSCustomObject]@{
                Id=$_.id;Name=$_.name;Strategy=$_.routing_strategy;Targets=(@($_.target_allow)-join",");
                DenyTargets=(@($_.target_deny)-join",");Prefix=$_.model_prefix;QuotaReserve=$_.quota_reserve_pct;
                ModelAllow=(@($_.model_allow)-join",");Enabled=$_.enabled
            }
        })
        $gt.DataSource=$null;$gt.DataSource=@($cfg.targets|ForEach-Object{
            [PSCustomObject]@{
                Id=$_.id;Account=$_.account;Priority=$_.priority;Weight=$_.weight;Backup=$_.backup;
                Hourly=$_.quota_hourly_pct;Weekly=$_.quota_weekly_pct;QuotaChecked=$_.quota_checked_utc;
                PlanRank=$_.plan_rank;Expiry=$_.expiry_utc;BaseUrl=$_.base_url
            }
        })
        $an=Load-JsonObjectSafe $script:ApiAnalyticsLatestPath
        $gu.DataSource=$null
        if($an -and $an.data){
            $gu.DataSource=@($an.data.windows.all.by_client_key.PSObject.Properties|ForEach-Object{
                $v=$_.Value
                [PSCustomObject]@{ClientKey=$_.Name;Requests=$v.requests;SuccessRate=$v.success_rate_pct;InputTokens=$v.input_tokens;OutputTokens=$v.output_tokens;Cached=$v.cached_input_tokens;TotalTokens=$v.total_tokens;EstimatedUsd=$v.estimated_usd;P95=$v.latency_ms.p95}
            })
        }
        $pa=Load-JsonObjectSafe $script:ApiParityLatestPath
        $gp.DataSource=$null
        if($pa -and $pa.data){
            $gp.DataSource=@($pa.data.capabilities|ForEach-Object{
                [PSCustomObject]@{Capability=$_.label;Cockpit=$_.cockpit_reference;HMS=$_.hms_status;Benchmark=$_.benchmark;Notes=$_.notes}
            })
            $status.Text="Feature evidence="+$pa.data.hms.feature_evidence_score_pct+"% | Production evidence="+$pa.data.hms.production_evidence_score_pct+"% | "+$pa.data.hms.verdict
        }else{
            $status.Text=Get-HmsSmartGatewaySummary
        }
    }
    $bAnalytics.Add_Click({try{$null=Invoke-HmsApiAnalytics;Refresh-Api}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bParity.Add_Click({try{$null=Invoke-HmsCockpitParityAudit;Refresh-Api}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}})
    $bPolicy.Add_Click({Show-HmsApiKeyPolicyDialog;Refresh-Api})
    $bGateway.Add_Click({Show-HmsSmartGatewayCenter;Refresh-Api})
    $bOpen.Add_Click({Start-Process explorer.exe $script:ApiSupersetDir|Out-Null})
    $w.Add_Shown({try{$null=Invoke-HmsApiAnalytics}catch{};try{$null=Invoke-HmsCockpitParityAudit}catch{};Refresh-Api})
    [void]$w.ShowDialog($form)
}

# ---------------- Verification ----------------

function Test-ApiModels{
    $port=[int]$script:S.ProxyPort
    $headers=@{Authorization=("Bearer "+[string]$script:S.LocalApiKey)}
    $url="http://127.0.0.1:$port/v1/models"
    try{
        $r=Invoke-WebRequest -UseBasicParsing -Uri $url -Headers $headers -Method Get -TimeoutSec 10
        $body=[string]$r.Content
        $j=$null
        try{$j=$body | ConvertFrom-Json}catch{}
        $count=if($j -and $j.data){@($j.data).Count}else{0}
        $safeMode=""
        try{$safeMode=[string]$r.Headers["X-CPA-SAFE-MODE"]}catch{}
        return @{Ok=$true;Count=$count;Status=[int]$r.StatusCode;Body=(Redact-LocalApiText $body);Error="";SafeMode=$safeMode}
    }catch{
        $status=0
        $body=""
        $safeMode=""
        try{
            $resp=$_.Exception.Response
            if($resp){
                try{$status=[int]$resp.StatusCode}catch{}
                try{$safeMode=[string]$resp.Headers["X-CPA-SAFE-MODE"]}catch{}
                try{
                    $stream=$resp.GetResponseStream()
                    if($stream){
                        $reader=New-Object IO.StreamReader($stream)
                        try{$body=$reader.ReadToEnd()}finally{$reader.Dispose();$stream.Dispose()}
                    }
                }catch{}
            }
        }catch{}
        $msg=Redact-LocalApiText ([string]$_.Exception.Message)
        $body=Redact-LocalApiText $body
        return @{Ok=$false;Count=0;Status=$status;Body=$body;Error=$msg;SafeMode=$safeMode}
    }
}
function Verify-Mode{
    $lines=New-Object Collections.Generic.List[string]
    $score=0;$total=5
    $port=[int]$script:S.ProxyPort

    $id=ListenerPid $port
    if($id -gt 0 -and (IsOurProxy $id)){$lines.Add("PASS  Router đúng executable đang nghe port $port (PID $id)");$score++}
    elseif($id -gt 0){$lines.Add("FAIL  Port $port thuộc tiến trình khác (PID $id)")}
    else{$lines.Add("FAIL  Không có listener trên port $port")}

    if(CodexInHmsMode){$lines.Add("PASS  config.toml chọn model_provider = hms_api_router");$score++}
    else{$lines.Add("FAIL  config.toml chưa ở HMS API mode")}

    $envOk=$false
    if(Test-Path $script:CodexEnv){
        $e=[IO.File]::ReadAllText($script:CodexEnv)
        $needle="HMS_ROUTER_API_KEY="+[string]$script:S.LocalApiKey
        $envOk=$e.Contains($needle)
    }
    if($envOk){$lines.Add("PASS  ~/.codex/.env chứa đúng local API key");$score++}
    else{$lines.Add("FAIL  ~/.codex/.env thiếu/sai HMS_ROUTER_API_KEY")}

    $api=Test-ApiModels
    if($api.Ok){$lines.Add("PASS  Bearer API key gọi /v1/models thành công ($($api.Count) models)");$score++}
    else{$lines.Add("FAIL  API test lỗi: $($api.Error)")}

    $clients=@(Get-CodexClientProcesses)
    if($clients.Count -gt 0){
        $cfgTime=(Get-Item $script:CodexConfig -ErrorAction SilentlyContinue).LastWriteTime
        $fresh=$false
        foreach($p in $clients){try{if($p.StartTime -gt $cfgTime){$fresh=$true}}catch{}}
        if($fresh){$lines.Add("PASS  Codex/ChatGPT đã được mở sau lần ghi config");$score++}
        else{$lines.Add("WARN  Client có vẻ được mở trước config; nên restart")}
    }else{
        $lines.Add("WARN  Codex/ChatGPT hiện chưa chạy; mở app để sử dụng")
    }

    $lines.Add("")
    if($score -eq $total){$lines.Add("KẾT LUẬN: ĐÃ KẾT NỐI API ROUTER ($score/$total).")}
    elseif($score -ge 4){$lines.Add("KẾT LUẬN: ROUTER/API OK, nhưng cần xử lý cảnh báo client ($score/$total).")}
    else{$lines.Add("KẾT LUẬN: CHƯA HOÀN TẤT ($score/$total).")}
    $lines.Add("")
    $lines.Add("")
    $lines.Add((Get-CodexConfigAudit))
    $lines.Add("")
    $lines.Add("Lưu ý: chữ hiển thị ở góc trái Codex do phiên bản UI của Codex quyết định. Tool xác minh đường request API thực tế bằng provider + env key + endpoint local.")
    return ($lines -join "`r`n")
}

# ---------------- Mode switch ----------------

function Enable-HmsMode{
    Snapshot-ClientConfigIfNeeded
    Ensure-ProxyFiles

    $port=[int]$script:S.ProxyPort
    $existing=ListenerPid $port
    if($existing -gt 0 -and -not (IsOurProxy $existing)){
        $foreignPath=ProcPath $existing;if(-not $foreignPath){$foreignPath="PID $existing"}
        throw "Port $port đang thuộc dịch vụ khác: $foreignPath. HMS không can thiệp."
    }

    Ensure-Dir $script:DataDir
    $proxyTxn=Join-Path $script:DataDir "proxy-config-before-live-handoff-v2511.yaml"
    Copy-Item $script:ProxyCfg $proxyTxn -Force
    $wasOurRunning=($existing -gt 0 -and (IsOurProxy $existing))
    $codexMutated=$false
    $clientWasOpen=$false
    $closeMsg=""

    if([bool]$script:S.RestartCodexOnSwitch){
        $r=Ensure-CodexRestartBarrier
        $clientWasOpen=[bool]$r.WasOpen
        $closeMsg=[string]$r.Message
    }elseif(@(Get-CodexClientProcesses).Count -gt 0){
        throw "CODEX_RESTART_REQUIRED: Restart Codex khi chuyển Router đang tắt nhưng client hiện đang chạy. Hãy đóng app trước khi bật HMS API Router."
    }

    try{
        if($wasOurRunning){$null=Stop-Router}

        Configure-Proxy
        $audit=Get-ProxyApiKeyAudit
        if(-not $audit.Match){
            throw "LOCAL_API_KEY_CONFIG_MISMATCH: key_fp=$($audit.ExpectedFingerprint); api_keys=$($audit.Count); config=$($audit.ConfigPath)"
        }
        if($audit.UnsafeExampleKeyCount -gt 0){
            throw "CLIPROXY_EXAMPLE_API_KEY_SAFEMODE_RISK: unsafe_template_keys=$($audit.UnsafeExampleKeyCount); config=$($audit.ConfigPath)"
        }

        $proxyMsg=Start-Router
        $api=$null
        for($i=1;$i -le 6;$i++){
            $api=Test-ApiModels
            if($api.Ok){break}
            Start-Sleep -Milliseconds 350
        }
        if(-not $api.Ok){
            $body=if($api.Body){$api.Body}else{"<empty-body>"}
            $safe=if($api.SafeMode){$api.SafeMode}else{"none"}
            throw "LOCAL_API_HANDSHAKE_FAIL: HTTP=$($api.Status); $($api.Error); body=$body; safe_mode=$safe; key_fp=$($audit.ExpectedFingerprint); config_key_match=$($audit.Match); unsafe_template_keys=$($audit.UnsafeExampleKeyCount); config=$($audit.ConfigPath)"
        }

        Configure-CodexApiMode
        $codexMutated=$true
        if(-not (Test-CodexEnvDiskReady)){
            throw "CODEX_ENV_WRITE_VERIFY_FAIL: ~/.codex/config.toml hoặc ~/.codex/.env chưa chứa provider/key HMS mong đợi."
        }

        $openMsg=""
        if([bool]$script:S.OpenCodexOnEnable -or $clientWasOpen){
            $openMsg=Open-CodexClient
            if(-not (Wait-CodexClientFresh 15)){
                throw "CODEX_ENV_RELOAD_NOT_CONFIRMED: app đã được gọi mở nhưng process Codex/ChatGPT không mới hơn config/.env. Hãy thoát hẳn app rồi thử lại."
            }
        }

        return "$closeMsg $proxyMsg API key OK ($($api.Count) models, HTTP $($api.Status), key_fp=$($audit.ExpectedFingerprint)). ENV reload OK. $openMsg"
    }catch{
        $originalError=Redact-LocalApiText ([string]$_.Exception.Message)
        try{
            $id=ListenerPid $port
            if($id -gt 0 -and (IsOurProxy $id)){$null=Stop-Router}
        }catch{}
        try{if(Test-Path $proxyTxn){Copy-Item $proxyTxn $script:ProxyCfg -Force}}catch{}
        if($codexMutated){$null=Restore-ClientSnapshotTransactional}
        if($wasOurRunning){try{$null=Start-Router}catch{}}
        throw $originalError
    }
}
function Disable-HmsMode{
    $closeMsg=""
    $clientWasOpen=$false

    if([bool]$script:S.RestartCodexOnSwitch){
        $r=Ensure-CodexRestartBarrier
        $closeMsg=[string]$r.Message
        $clientWasOpen=[bool]$r.WasOpen
    }elseif(@(Get-CodexClientProcesses).Count -gt 0){
        throw "CODEX_RESTART_REQUIRED: Client vẫn đang chạy. HMS không tắt Router/restore config khi app cũ còn giữ provider HMS."
    }

    $p=Stop-Router
    $restore=Restore-ClientConfig
    $open=""
    if([bool]$script:S.RestartCodexOnSwitch -and $clientWasOpen){
        Start-Sleep -Milliseconds 700
        $open=Open-CodexClient
    }
    return "$closeMsg $p $restore $open"
}

# ============================================================
# v25.27 NATIVE GUI BACKEND ACTIONS
# HMS_GUI.pyw is the visible UI. This script exits before legacy UI
# when -BackendAction is status/enable/disable/open_codex/get_settings/save_settings/get_accounts/refresh_quota/set_account_disabled/add_codex/get_logs.
# ============================================================

function Write-HmsBackendResult {
    param([object]$Payload)
    if([string]::IsNullOrWhiteSpace($BackendResultPath)){return}
    try{
        $parent=Split-Path -Parent $BackendResultPath
        if($parent -and -not (Test-Path $parent)){New-Item -ItemType Directory -Force -Path $parent|Out-Null}
        $Payload|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $BackendResultPath -Encoding UTF8
    }catch{}
}

function Set-HmsBackendOneClickPolicy {
    # Safety invariants only. User-facing preferences are respected.
    $script:S.RestoreOnDisable=$true
    $script:S.CodexMinimizeToTray=$false
    Save-Settings
}


function Invoke-HmsUsageLedger {
    param([ValidateSet("sync","status")][string]$Mode="sync")
    Ensure-Dir $script:UsageLedgerDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_UsageLedger.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_UsageLedger.py"}
    $args=@(
        "--mode",$Mode,
        "--trace",$script:SmartGatewayTracePath,
        "--db",$script:UsageLedgerDbPath,
        "--latest",$script:UsageLedgerLatestPath,
        "--max-lines",([string][int]$script:S.UsageLedgerMaxTraceLines)
    )
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
    return $j.data
}

function Get-HmsNativeUsageObject {
    param([bool]$Sync=$false)
    $modeName=if($Sync){"sync"}else{"status"}
    $data=Invoke-HmsUsageLedger $modeName
    return @{
        ok=$true
        version=$script:Version
        usage=$data
        mode=$modeName.ToUpperInvariant()
        note="Durable SQLite ledger · chỉ metadata · không lưu request body/OAuth/API key/cookie."
    }
}

function Test-HmsAccountAnalyticsFresh {
    if(-not (Test-Path $script:AccountAnalyticsReportPath)){return $false}
    try{
        $age=([DateTime]::UtcNow-(Get-Item -LiteralPath $script:AccountAnalyticsReportPath).LastWriteTimeUtc).TotalSeconds
        return ($age -le [Math]::Max(30,[int]$script:S.AccountAnalyticsIntervalSec))
    }catch{return $false}
}

function Invoke-HmsAccountAnalytics {
    param([ValidateSet("sync","status")][string]$Mode="sync")
    Ensure-Dir $script:AccountAnalyticsDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_AccountAnalytics.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_AccountAnalytics.py"}
    $args=@(
        "--mode",$Mode,
        "--db",$script:AccountAnalyticsDbPath,
        "--report",$script:AccountAnalyticsReportPath,
        "--usage-db",$script:UsageLedgerDbPath,
        "--retention-days",([string][int]$script:S.AccountAnalyticsRetentionDays),
        "--min-samples",([string][int]$script:S.AccountAnalyticsMinSamples)
    )
    $tmp=$null
    try{
        if($Mode -eq "sync"){
            if(-not (Test-Path $script:UsageLedgerDbPath)){try{$null=Invoke-HmsUsageLedger "sync"}catch{}}
            $tmp=Join-Path $env:TEMP ("hms-account-analytics-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
            Save-JsonAtomic $tmp (Get-HmsClosedLoopFleetObject)
            $args+=@("--fleet",$tmp)
            if(Test-Path $script:PredictiveQuotaPlanPath){$args+=@("--predictive",$script:PredictiveQuotaPlanPath)}
            if(Test-Path $script:CircuitBreakerPlanPath){$args+=@("--breaker",$script:CircuitBreakerPlanPath)}
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativeAccountAnalyticsObject {
    param([bool]$Sync=$false)
    $modeName=if($Sync){"sync"}else{"status"}
    if($modeName -eq "status" -and -not (Test-Path $script:AccountAnalyticsReportPath)){$modeName="sync"}
    $d=Invoke-HmsAccountAnalytics $modeName
    return @{ok=$true;version=$script:Version;account_analytics=$d;enabled=[bool]$script:S.AccountAnalyticsEnabled;mode=$modeName.ToUpperInvariant()}
}

function New-HmsNativeDiagnosticsBundle {
    Ensure-Dir $script:CodexDiagnosticBundleDir
    $tool=Join-Path $PSScriptRoot "HMS_DiagnosticsBundle.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_DiagnosticsBundle.py"}
    $args=@(
        "--data-dir",$script:DataDir,
        "--runtime-dir",$PSScriptRoot,
        "--output-dir",$script:CodexDiagnosticBundleDir
    )
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
    return @{
        ok=$true;version=$script:Version;path=[string]$j.path;sha256=[string]$j.sha256;
        file_count=[int]$j.file_count;privacy=$j.privacy;
        message="Đã tạo gói chẩn đoán đã redact. Không chứa raw OAuth/request body/API key/cookie."
    }
}

function Get-HmsNativeReleaseObject {
    $data=Invoke-HmsReleaseManager "status"
    return @{ok=$true;version=$script:Version;release=$data}
}


function Get-HmsAdaptiveRouterConfigJson {
    $cfg=[ordered]@{
        enabled=[bool]$script:S.AdaptiveRouterEnabled
        mode=[string]$script:S.AdaptiveRouterMode
        min_samples=[int]$script:S.AdaptiveRouterMinSamples
        min_score_delta=[int]$script:S.AdaptiveRouterMinScoreDelta
        hold_minutes=[int]$script:S.AdaptiveRouterHoldMinutes
        cooldown_sec=[int]$script:S.AdaptiveRouterCooldownSec
        quota_floor_pct=[int]$script:S.AdaptiveRouterQuotaFloor
        emergency_quota_pct=[int]$script:S.AdaptiveRouterEmergencyQuota
        preferred_weight=[int]$script:S.AdaptiveRouterPreferredWeight
        secondary_weight=[int]$script:S.AdaptiveRouterSecondaryWeight
        reserve_weight=[int]$script:S.AdaptiveRouterReserveWeight
    }
    return ($cfg|ConvertTo-Json -Compress)
}

function Invoke-HmsAdaptiveRouter {
    param([ValidateSet("status","evaluate","apply","rollback")][string]$Mode="status")
    Ensure-Dir $script:AdaptiveRouterDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_AdaptiveRouterPolicy.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_AdaptiveRouterPolicy.py"}
    $args=@("--mode",$Mode,"--state",$script:AdaptiveRouterStatePath,"--plan",$script:AdaptiveRouterPlanPath)
    $tmp=$null
    try{
        if($Mode -in @("evaluate","apply")){
            $tmp=Join-Path $env:TEMP ("hms-adaptive-accounts-"+[Guid]::NewGuid().ToString("N")+".json")
            $accounts=Get-HmsNativeAccountCenterObject
            Save-JsonAtomic $tmp $accounts
            if(-not (Test-Path $script:UsageLedgerLatestPath)){
                try{$null=Invoke-HmsUsageLedger "status"}catch{}
            }
            $args+=@("--accounts",$tmp,"--usage",$script:UsageLedgerLatestPath,"--config-json",(Get-HmsAdaptiveRouterConfigJson))
            if($Mode -eq "apply"){
                if((-not [bool]$script:S.AdaptiveRouterEnabled) -or ([string]$script:S.AdaptiveRouterMode).ToUpperInvariant() -ne "GUARDED_AUTO"){
                    throw "ADAPTIVE_ROUTER_GUARDED_AUTO_REQUIRED"
                }
                $args+=@("--auth-dir",$script:AuthDir)
            }
        }elseif($Mode -eq "rollback"){
            $args+=@("--auth-dir",$script:AuthDir)
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativeAdaptiveRouterObject {
    $d=Invoke-HmsAdaptiveRouter "status"
    return @{ok=$true;version=$script:Version;adaptive=$d;mode=[string]$script:S.AdaptiveRouterMode;enabled=[bool]$script:S.AdaptiveRouterEnabled}
}

function Get-HmsClosedLoopRouterConfigJson {
    $cfg=[ordered]@{
        enabled=[bool]$script:S.ClosedLoopRouterEnabled
        mode=[string]$script:S.ClosedLoopRouterMode
        min_samples=[int]$script:S.ClosedLoopRouterMinSamples
        min_score_delta=[int]$script:S.ClosedLoopRouterMinScoreDelta
        hold_minutes=[int]$script:S.ClosedLoopRouterHoldMinutes
        cooldown_sec=[int]$script:S.ClosedLoopRouterCooldownSec
        quota_floor_pct=[int]$script:S.ClosedLoopRouterQuotaFloor
        emergency_quota_pct=[int]$script:S.ClosedLoopRouterEmergencyQuota
        preferred_weight=[int]$script:S.ClosedLoopRouterPreferredWeight
        secondary_weight=[int]$script:S.ClosedLoopRouterSecondaryWeight
        tail_weight=[int]$script:S.ClosedLoopRouterTailWeight
        half_open_probe_priority=[int]$script:S.CircuitBreakerHalfOpenProbePriority
    }
    return ($cfg|ConvertTo-Json -Compress)
}

function Get-HmsClosedLoopFleetObject {
    $accounts=(Get-HmsNativeAccountCenterObject).accounts
    $store=Get-CodexInstanceStore
    $instances=[System.Collections.Generic.List[object]]::new()
    foreach($inst in @($store.instances)){
        $manifestPath=Get-CodexInstancePoolManifestPath $inst
        $manifest=if(Test-Path -LiteralPath $manifestPath){Load-JsonObjectSafe $manifestPath}else{$null}
        if(-not $manifest){continue}
        $instances.Add([ordered]@{
            id=[string]$inst.id;name=[string]$inst.name;project=[string]$inst.projectDir;
            router_dir=[string]$inst.routerDir;manifest_path=[string]$manifestPath;manifest=$manifest
        })
    }
    $safeAccounts=[System.Collections.Generic.List[object]]::new()
    foreach($a in @($accounts)){
        $safeAccounts.Add([ordered]@{
            email=[string]$a.email;status=[string]$a.status;role=[string]$a.role;favorite=[bool]$a.favorite;
            health_score=[int]$a.health_score;pool_score=[int]$a.pool_score;quota=$a.quota
        })
    }
    return [ordered]@{schema_version=1;version='25.36';accounts=@($safeAccounts);instances=@($instances);secret_fields_excluded=$true}
}

function Get-HmsCircuitBreakerConfigJson {
    $cfg=[ordered]@{
        enabled=[bool]$script:S.CircuitBreakerEnabled
        mode=[string]$script:S.CircuitBreakerMode
        consecutive_failure_threshold=[int]$script:S.CircuitBreakerConsecutiveFailures
        rate_limit_threshold=[int]$script:S.CircuitBreakerRateLimitThreshold
        auth_threshold=[int]$script:S.CircuitBreakerAuthThreshold
        server_threshold=[int]$script:S.CircuitBreakerServerThreshold
        timeout_threshold=[int]$script:S.CircuitBreakerTimeoutThreshold
        network_threshold=[int]$script:S.CircuitBreakerNetworkThreshold
        base_open_seconds=[int]$script:S.CircuitBreakerBaseOpenSec
        rate_limit_open_seconds=[int]$script:S.CircuitBreakerRateLimitOpenSec
        auth_open_seconds=[int]$script:S.CircuitBreakerAuthOpenSec
        max_open_seconds=[int]$script:S.CircuitBreakerMaxOpenSec
        half_open_successes=[int]$script:S.CircuitBreakerHalfOpenSuccesses
        max_backoff_exponent=[int]$script:S.CircuitBreakerMaxBackoffExponent
    }
    return ($cfg|ConvertTo-Json -Compress)
}

function Invoke-HmsCircuitBreaker {
    param([ValidateSet("status","evaluate","apply","reset")][string]$Mode="status")
    Ensure-Dir $script:CircuitBreakerDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_CircuitBreaker.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_CircuitBreaker.py"}
    $args=@("--mode",$Mode,"--state",$script:CircuitBreakerStatePath,"--plan",$script:CircuitBreakerPlanPath)
    $tmp=$null
    try{
        if($Mode -ne 'status'){
            $tmp=Join-Path $env:TEMP ("hms-circuit-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
            Save-JsonAtomic $tmp (Get-HmsClosedLoopFleetObject)
            $args+=@("--fleet",$tmp)
        }
        if($Mode -in @('evaluate','apply')){
            if(-not (Test-Path $script:UsageLedgerLatestPath)){try{$null=Invoke-HmsUsageLedger "sync"}catch{}}
            $args+=@("--usage",$script:UsageLedgerLatestPath,"--config-json",(Get-HmsCircuitBreakerConfigJson))
            if($Mode -eq 'apply'){
                if((-not [bool]$script:S.CircuitBreakerEnabled) -or ([string]$script:S.CircuitBreakerMode).ToUpperInvariant() -ne 'GUARDED_AUTO'){
                    throw 'CIRCUIT_BREAKER_GUARDED_AUTO_REQUIRED'
                }
            }
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativeCircuitBreakerObject {
    $d=Invoke-HmsCircuitBreaker 'status'
    return @{ok=$true;version=$script:Version;circuit_breaker=$d;mode=[string]$script:S.CircuitBreakerMode;enabled=[bool]$script:S.CircuitBreakerEnabled}
}

function Get-HmsPredictiveQuotaConfigJson {
    $cfg=[ordered]@{
        enabled=[bool]$script:S.PredictiveQuotaEnabled
        hourly_lookback_hours=[int]$script:S.PredictiveQuotaHourlyLookbackHours
        weekly_lookback_hours=[int]$script:S.PredictiveQuotaWeeklyLookbackHours
        min_span_minutes=[int]$script:S.PredictiveQuotaMinSpanMinutes
        reset_jump_pct=[int]$script:S.PredictiveQuotaResetJumpPct
        reserve_trigger_pct=[int]$script:S.PredictiveQuotaReserveTriggerPct
        emergency_pct=[int]$script:S.PredictiveQuotaEmergencyPct
        proactive_runway_minutes=[int]$script:S.PredictiveQuotaProactiveRunwayMinutes
        warning_runway_minutes=[int]$script:S.PredictiveQuotaWarningRunwayMinutes
        reset_guard_minutes=[int]$script:S.PredictiveQuotaResetGuardMinutes
        max_score_penalty=[int]$script:S.PredictiveQuotaMaxScorePenalty
        min_load_factor_pct=[int]$script:S.PredictiveQuotaMinLoadFactorPct
    }
    return ($cfg|ConvertTo-Json -Compress)
}

function Invoke-HmsPredictiveQuota {
    param([ValidateSet("status","evaluate")][string]$Mode="status")
    Ensure-Dir $script:PredictiveQuotaDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_PredictiveQuota.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_PredictiveQuota.py"}
    $args=@("--mode",$Mode,"--state",$script:PredictiveQuotaStatePath,"--plan",$script:PredictiveQuotaPlanPath)
    $tmp=$null
    try{
        if($Mode -eq 'evaluate'){
            # Snapshot is append-only and bounded by its own interval; failure does not mutate account state.
            try{Snapshot-CodexQuotaHistory}catch{}
            $tmp=Join-Path $env:TEMP ("hms-predictive-quota-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
            Save-JsonAtomic $tmp (Get-HmsClosedLoopFleetObject)
            $args+=@("--fleet",$tmp,"--history",$script:CodexQuotaHistoryPath,"--config-json",(Get-HmsPredictiveQuotaConfigJson))
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativePredictiveQuotaObject {
    $d=Invoke-HmsPredictiveQuota 'status'
    return @{ok=$true;version=$script:Version;predictive_quota=$d;enabled=[bool]$script:S.PredictiveQuotaEnabled}
}

function Test-HmsPredictiveQuotaFresh {
    if(-not (Test-Path $script:PredictiveQuotaPlanPath)){return $false}
    try{
        $age=([DateTime]::UtcNow-(Get-Item -LiteralPath $script:PredictiveQuotaPlanPath).LastWriteTimeUtc).TotalSeconds
        return ($age -le [Math]::Max(15,[int]$script:S.PredictiveQuotaIntervalSec))
    }catch{return $false}
}

function Get-HmsQuotaCenterConfigJson {
    $cfg=[ordered]@{
        enabled=[bool]$script:S.QuotaCenterEnabled
        retention_days=[int]$script:S.QuotaCenterRetentionDays
        forecast_retention_days=[int]$script:S.QuotaCenterForecastRetentionDays
        min_snapshot_interval_seconds=[int]$script:S.QuotaCenterSnapshotMinIntervalSec
        chart_history_hours=[int]$script:S.QuotaCenterChartHistoryHours
        chart_max_points=[int]$script:S.QuotaCenterChartMaxPoints
        fresh_minutes=[int]$script:S.QuotaCenterFreshMinutes
        stale_minutes=[int]$script:S.QuotaCenterStaleMinutes
        accuracy_horizon_minutes=[int]$script:S.QuotaCenterAccuracyHorizonMinutes
        accuracy_tolerance_minutes=[int]$script:S.QuotaCenterAccuracyToleranceMinutes
        prediction_min_interval_minutes=[int]$script:S.QuotaCenterPredictionMinIntervalMinutes
        alert_low_pct=[int]$script:S.QuotaCenterAlertLowPct
        alert_critical_pct=[int]$script:S.QuotaCenterAlertCriticalPct
        legacy_import_max_lines=10000
    }
    return ($cfg|ConvertTo-Json -Compress)
}

function Invoke-HmsUnifiedDiagnostics {
    param([ValidateSet("get","refresh")][string]$Mode="get")
    Ensure-Dir $script:UnifiedDiagnosticsDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_UnifiedDiagnostics.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_UnifiedDiagnostics.py"}
    $args=@("--mode",$Mode,"--data-dir",$script:DataDir,"--latest",$script:UnifiedDiagnosticsLatestPath,
        "--history",$script:UnifiedDiagnosticsHistoryPath,"--max-events",[string]([Math]::Max(50,[int]$script:S.UnifiedDiagnosticsMaxEvents)))
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
    return $j.unified_diagnostics
}

function Get-HmsNativeUnifiedDiagnosticsObject {
    $mode=if((Test-Path $script:UnifiedDiagnosticsLatestPath)){'get'}else{'refresh'}
    $d=Invoke-HmsUnifiedDiagnostics $mode
    return @{ok=$true;version=$script:Version;unified_diagnostics=$d;enabled=[bool]$script:S.UnifiedDiagnosticsEnabled}
}

function Invoke-HmsQuotaCenter {
    param([ValidateSet("status","sync","validate")][string]$Mode="status")
    Ensure-Dir $script:QuotaCenterDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_QuotaCenter.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_QuotaCenter.py"}
    $args=@("--mode",$Mode,"--db",$script:QuotaCenterDbPath,"--state",$script:QuotaCenterStatePath,"--report",$script:QuotaCenterReportPath)
    $tmp=$null
    try{
        if($Mode -eq 'sync'){
            try{Snapshot-CodexQuotaHistory}catch{}
            if([bool]$script:S.PredictiveQuotaEnabled -and (-not (Test-HmsPredictiveQuotaFresh))){
                try{$null=Invoke-HmsPredictiveQuota 'evaluate'}catch{}
            }
            $tmp=Join-Path $env:TEMP ("hms-quota-center-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
            Save-JsonAtomic $tmp (Get-HmsClosedLoopFleetObject)
            $args+=@("--fleet",$tmp,"--legacy-history",$script:CodexQuotaHistoryPath,"--config-json",(Get-HmsQuotaCenterConfigJson))
            if(Test-Path $script:PredictiveQuotaPlanPath){$args+=@("--predictive",$script:PredictiveQuotaPlanPath)}
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativeQuotaCenterObject {
    $d=Invoke-HmsQuotaCenter 'status'
    return @{ok=$true;version=$script:Version;quota_center=$d;enabled=[bool]$script:S.QuotaCenterEnabled}
}

function Invoke-HmsClosedLoopRouter {
    param([ValidateSet("status","evaluate","apply","rollback")][string]$Mode="status")
    Ensure-Dir $script:ClosedLoopRouterDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_ClosedLoopRouter.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_Codex_ClosedLoopRouter.py"}
    $args=@("--mode",$Mode,"--state",$script:ClosedLoopRouterStatePath,"--plan",$script:ClosedLoopRouterPlanPath)
    $tmp=$null
    try{
        if($Mode -ne 'status'){
            $tmp=Join-Path $env:TEMP ("hms-closed-loop-fleet-"+[Guid]::NewGuid().ToString("N")+".json")
            Save-JsonAtomic $tmp (Get-HmsClosedLoopFleetObject)
            $args+=@("--fleet",$tmp)
        }
        if($Mode -in @('evaluate','apply')){
            if(-not (Test-Path $script:UsageLedgerLatestPath)){try{$null=Invoke-HmsUsageLedger "sync"}catch{}}
            if([bool]$script:S.CircuitBreakerEnabled){
                $cbMode=if($Mode -eq 'apply' -and ([string]$script:S.CircuitBreakerMode).ToUpperInvariant() -eq 'GUARDED_AUTO'){'apply'}else{'evaluate'}
                $null=Invoke-HmsCircuitBreaker $cbMode
                if(Test-Path $script:CircuitBreakerPlanPath){$args+=@("--breaker",$script:CircuitBreakerPlanPath)}
            }
            if([bool]$script:S.PredictiveQuotaEnabled){
                if(-not (Test-HmsPredictiveQuotaFresh)){$null=Invoke-HmsPredictiveQuota 'evaluate'}
                if(Test-Path $script:PredictiveQuotaPlanPath){$args+=@("--predictive",$script:PredictiveQuotaPlanPath)}
            }
            if([bool]$script:S.AccountAnalyticsEnabled){
                if(-not (Test-HmsAccountAnalyticsFresh)){try{$null=Invoke-HmsAccountAnalytics 'sync'}catch{}}
                if(Test-Path $script:AccountAnalyticsReportPath){$args+=@("--analytics",$script:AccountAnalyticsReportPath)}
            }
            if([bool]$script:S.SmartModelRouterEnabled -and (Test-Path -LiteralPath $script:SmartModelRouterStatePath)){
                $args+=@("--smart-model",$script:SmartModelRouterStatePath)
            }
            $args+=@("--usage",$script:UsageLedgerLatestPath,"--config-json",(Get-HmsClosedLoopRouterConfigJson))
            if($Mode -eq 'apply'){
                if((-not [bool]$script:S.ClosedLoopRouterEnabled) -or ([string]$script:S.ClosedLoopRouterMode).ToUpperInvariant() -ne 'GUARDED_AUTO'){
                    throw 'CLOSED_LOOP_GUARDED_AUTO_REQUIRED'
                }
            }
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        if($tmp -and (Test-Path $tmp)){Remove-Item $tmp -Force -ErrorAction SilentlyContinue}
    }
}

function Get-HmsNativeClosedLoopRouterObject {
    $d=Invoke-HmsClosedLoopRouter 'status'
    return @{ok=$true;version=$script:Version;closed_loop=$d;mode=[string]$script:S.ClosedLoopRouterMode;enabled=[bool]$script:S.ClosedLoopRouterEnabled}
}

function Invoke-HmsUpdateChannel {
    param([ValidateSet("status","check","stage","activate")][string]$Mode="status")
    $tool=Join-Path $PSScriptRoot "HMS_UpdateChannel.py"
    if(-not (Test-Path $tool)){throw "Thiếu HMS_UpdateChannel.py"}
    if(-not (Test-Path $script:UpdatePublicKeyPath)){throw "Thiếu pinned update public key."}
    if($Mode -in @("check","stage")){
        if(-not [bool]$script:S.UpdateChannelEnabled){throw "UPDATE_CHANNEL_DISABLED"}
        if([string]::IsNullOrWhiteSpace([string]$script:S.UpdateFeedUrl)){throw "UPDATE_FEED_URL_MISSING"}
    }
    $args=@(
        "--mode",$Mode,
        "--feed-url",([string]$script:S.UpdateFeedUrl),
        "--public-key",$script:UpdatePublicKeyPath,
        "--channel",([string]$script:S.UpdateChannelName),
        "--current-version",$script:Version,
        "--install-root",(Get-HmsDefaultInstallRoot),
        "--runtime-dir",$PSScriptRoot
    )
    $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
    $data=$j.data
    if($Mode -in @("check","stage")){
        try{Save-JsonAtomic $script:UpdateChannelStatePath ([ordered]@{time_utc=[DateTime]::UtcNow.ToString("o");mode=$Mode;data=$data})}catch{}
    }
    return $data
}

function Get-HmsNativeUpdateObject {
    $d=Invoke-HmsUpdateChannel "status"
    $last=Load-JsonObjectSafe $script:UpdateChannelStatePath
    return @{ok=$true;version=$script:Version;update=$d;last_check=$last;enabled=[bool]$script:S.UpdateChannelEnabled;feed_url=[string]$script:S.UpdateFeedUrl;channel=[string]$script:S.UpdateChannelName}
}


function Read-HmsInstanceBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw 'INSTANCE_INPUT_MISSING'}
    try{return (Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'INSTANCE_INPUT_INVALID'}
}
function Get-HmsNativeCodexInstancesObject {
    $store=Get-CodexInstanceStore
    $rows=[System.Collections.Generic.List[object]]::new()
    $running=0;$ready=0;$conflicts=0
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    foreach($i in @($store.instances)){
        $rp=Test-CodexInstanceRouterOwned $i
        $cp=Test-CodexInstanceClientOwned $i
        $audit=Test-CodexInstanceIsolation $i
        $ia=$identityMap[[string]$i.id]
        if($cp){$running++};if($audit.ok){$ready++}else{$conflicts++}
        $rows.Add([ordered]@{
            id=[string]$i.id;name=[string]$i.name;account_email=[string]$i.accountEmail;project_dir=[string]$i.projectDir;
            launch_mode=[string]$i.launchMode;port=[int]$i.port;router_online=$rp;client_running=$cp;
            state=if($cp){'RUNNING'}elseif($rp){'ROUTER_ONLY'}elseif($audit.ok){'READY'}else{'BLOCKED'};
            isolation_ok=[bool]$audit.ok;isolation_issues=@($audit.issues);identity_ok=if($ia){[bool]$ia.ok}else{$false};identity_grade=if($ia){[string]$ia.grade}else{'UNKNOWN'};identity_fingerprint=if($ia){[string]$ia.fingerprint_sha256}else{''};identity_warnings=if($ia){@($ia.warnings)}else{@()};last_launch_utc=[string]$i.lastLaunchUtc;
            root=[string]$i.root;router_dir=[string]$i.routerDir;codex_home=[string]$i.codexHome;app_data=[string]$i.appData
        })
    }
    $accounts=@(Get-CodexAccountRecords|ForEach-Object {[ordered]@{email=[string]$_.Email;plan=[string]$_.Plan;status=[string]$_.Status}})
    return @{ok=$true;version=$script:Version;codex_only=$true;instances=@($rows);accounts=$accounts;summary=@{total=$rows.Count;ready=$ready;running=$running;conflicts=$conflicts};settings=@{
        base_port=[int]$script:S.CodexInstanceBasePort;max_per_account=[int]$script:S.CodexFleetMaxInstancesPerAccount;default_launch_mode=[string]$script:S.CodexInstanceDefaultLaunchMode;
        unique_project=[bool]$script:S.CodexInstanceRequireUniqueProject;dedicated_account=[bool]$script:S.CodexInstanceRequireDedicatedAccount;
        enforce_isolation=[bool]$script:S.CodexInstanceEnforceIsolation;sync_credential_on_start=[bool]$script:S.CodexInstanceSyncCredentialOnStart;identity_isolation=[bool]$script:S.CodexIdentityIsolationEnabled;identity_audit_before_launch=[bool]$script:S.CodexIdentityAuditBeforeLaunch;identity_fingerprint_strict=[bool]$script:S.CodexIdentityFingerprintStrict;identity_paths_under_root=[bool]$script:S.CodexIdentityRequirePathsUnderRoot
    }}
}
function New-HmsNativeCodexInstance {
    $input=Read-HmsInstanceBackendInput
    $inst=New-CodexInstance -Name ([string]$input.name) -ProjectDir ([string]$input.project_dir) -AccountEmail ([string]$input.account_email) -LaunchMode ([string]$input.launch_mode)
    $r=Get-HmsNativeCodexInstancesObject;$r['created_id']=[string]$inst.id;$r['message']="Đã tạo isolated Codex instance $($inst.name). Project/account binding đã khóa."
    return $r
}
function Invoke-HmsNativeCodexInstanceAction {
    param([ValidateSet('start','stop','restart','focus')][string]$Mode)
    $input=Read-HmsInstanceBackendInput;$id=([string]$input.id).Trim();if(-not $id){throw 'INSTANCE_ID_MISSING'}
    $message=switch($Mode){'start'{Start-CodexInstanceSafe $id}'stop'{Stop-CodexInstance $id}'restart'{Restart-CodexInstance $id}'focus'{Focus-CodexInstance $id}}
    $r=Get-HmsNativeCodexInstancesObject;$r['message']=[string]$message;return $r
}

function Read-HmsProjectAffinityBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw 'PROJECT_AFFINITY_INPUT_MISSING'}
    try{return (Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'PROJECT_AFFINITY_INPUT_INVALID'}
}
function Get-HmsNativeProjectAffinityObject {
    Sync-CodexProjectAffinityFromInstances
    $store=Get-CodexProjectAffinityStore;$rows=[System.Collections.Generic.List[object]]::new();$healthy=0;$running=0;$attention=0
    foreach($a in @($store.projects)){
        $r=Resolve-CodexProjectAffinity ([string]$a.projectDir)
        if($r.state -eq 'RUNNING'){$running++};if($r.state -in @('RUNNING','READY','SEAMLESS_FALLBACK_READY')){$healthy++}else{$attention++}
        $rows.Add([ordered]@{
            name=[string]$a.name;project_dir=[string]$a.projectDir;instance_id=[string]$a.instanceId;preferred_account=[string]$a.preferredAccount;
            fallback_accounts=@($a.fallbackAccounts);state=[string]$r.state;reason=[string]$r.reason;running=[bool]$r.clientRunning;
            primary_status=if($r.primary){[string]$r.primary.status}else{'MISSING'};primary_health=if($r.primary){[int]$r.primary.health}else{0};
            hourly_remaining=if($r.primary){$r.primary.hourly}else{$null};weekly_remaining=if($r.primary){$r.primary.weekly}else{$null};
            fallback_recommended=if($r.fallback){[string]$r.fallback.email}else{''};router_endpoint=if($r.router){[string]$r.router.endpoint}else{''};router_pool_count=if($r.router){[int]$r.router.poolCount}else{0};router_online=if($r.router){[bool]$r.router.routerOnline}else{$false};seamless_enabled=[bool]$script:S.CodexSeamlessRouterEnabled;last_launch_utc=[string]$a.lastLaunchUtc;updated_utc=[string]$a.updatedUtc
        })
    }
    $instances=Get-HmsNativeCodexInstancesObject
    return @{ok=$true;version=$script:Version;projects=@($rows);instances=@($instances.instances);accounts=@($instances.accounts);summary=@{total=$rows.Count;running=$running;healthy=$healthy;attention=$attention};settings=@{
        enabled=[bool]$script:S.CodexProjectAffinityEnabled;auto_register=[bool]$script:S.CodexProjectAutoRegisterInstances;block_unhealthy_primary=[bool]$script:S.CodexProjectBlockUnhealthyPrimary;fallback_max=[int]$script:S.CodexProjectFallbackMax;sticky_minutes=[int]$script:S.CodexProjectStickyMinutes;seamless_router=[bool]$script:S.CodexSeamlessRouterEnabled;seamless_live_sync=[bool]$script:S.CodexSeamlessLivePoolSync;seamless_retry=[int]$script:S.CodexSeamlessMaxRetryCredentials;seamless_ttl_hours=[int]$script:S.CodexSeamlessSessionTtlHours
    }}
}
function Save-HmsNativeProjectAffinity {
    $input=Read-HmsProjectAffinityBackendInput
    $fallbacks=if($input.PSObject.Properties['fallback_accounts']){@($input.fallback_accounts)}else{@()}
    $aff=Set-CodexProjectAffinity -ProjectDir ([string]$input.project_dir) -InstanceId ([string]$input.instance_id) -FallbackAccounts $fallbacks -Name ([string]$input.name)
    $syncMsg=''
    if([bool]$script:S.CodexSeamlessRouterEnabled -and [bool]$script:S.CodexSeamlessLivePoolSync){$inst=Get-CodexInstanceById ([string]$aff.instanceId);$syncMsg=Sync-CodexInstanceRouterCredentialPool $inst}
    $r=Get-HmsNativeProjectAffinityObject;$r['message']=('Đã lưu Project Affinity. '+$syncMsg);return $r
}
function Launch-HmsNativeProjectAffinity {
    $input=Read-HmsProjectAffinityBackendInput;$msg=Start-CodexProjectAffinity ([string]$input.project_dir)
    $r=Get-HmsNativeProjectAffinityObject;$r['message']=$msg;return $r
}
function Sync-HmsNativeProjectRouter {
    $input=Read-HmsProjectAffinityBackendInput;$r0=Resolve-CodexProjectAffinity ([string]$input.project_dir)
    if(-not $r0.instance){throw 'PROJECT_ROUTER_INSTANCE_MISSING'}
    $msg=Sync-CodexInstanceRouterCredentialPool $r0.instance
    $r=Get-HmsNativeProjectAffinityObject;$r['message']=$msg;return $r
}



# ============================================================
# v25.42 CODEX PROJECT ORCHESTRATOR
# One-click Project -> Instance -> Account -> Model -> Router -> Workspace
# Identity/Security remain hard gates. No unowned process is ever killed here.
# ============================================================
function Read-HmsProjectOrchestratorBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path -LiteralPath $BackendInputPath)){throw 'PROJECT_ORCHESTRATOR_INPUT_MISSING'}
    try{return (Get-Content -LiteralPath $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'PROJECT_ORCHESTRATOR_INPUT_INVALID'}
}
function Get-HmsProjectOrchestratorSecurityOk {
    param([object]$Snapshot)
    if(-not [bool]$script:S.ProjectOrchestratorRequireSecurity){return $true}
    if(-not $Snapshot){return $false}
    try{if([bool]$Snapshot.vault.settings_plain_local_key_present){return $false}}catch{}
    try{if([int]$Snapshot.vault.instance_plain_keys_count -gt 0){return $false}}catch{}
    try{if([int]$Snapshot.vault.instance_secret_refs_missing -gt 0){return $false}}catch{}
    try{if(@($Snapshot.reparse.detected).Count -gt 0){return $false}}catch{}
    try{if(@($Snapshot.seals.mismatches).Count -gt 0){return $false}}catch{}
    try{if([int]$Snapshot.redaction.unsafe_artifacts -gt 0){return $false}}catch{}
    return $true
}
function Get-HmsProjectOrchestratorFleetObject {
    Sync-CodexProjectAffinityFromInstances
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    $security=$null;try{$security=Get-HmsSecuritySnapshot}catch{}
    $securityOk=Get-HmsProjectOrchestratorSecurityOk $security
    $self=$null;try{$self=Get-HmsSelfHealingSnapshot}catch{}
    $selfMap=@{};if($self){foreach($x in @($self.instances)){$selfMap[[string]$x.id]=$x}}
    $policy=$null;try{$policy=Load-JsonObjectSafe $script:ModelManagerPolicyPath}catch{}
    $policyMap=@{}
    if($policy){foreach($x in @($policy.projects)){try{$policyMap[(Get-HmsPathKey ([string]$x.project_dir))]=$x}catch{}}}
    $store=Get-CodexProjectAffinityStore
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($a in @($store.projects)){
        $project=[string]$a.projectDir
        $r=$null;try{$r=Resolve-CodexProjectAffinity $project}catch{}
        $i=$null;if($r -and $r.instance){$i=$r.instance}else{try{$i=Get-CodexInstanceById ([string]$a.instanceId)}catch{}}
        $iid=if($i){[string]$i.id}else{[string]$a.instanceId}
        $ia=$identityMap[$iid];$sh=$selfMap[$iid];$pol=$policyMap[(Get-HmsPathKey $project)]
        $identityOk=if(-not [bool]$script:S.ProjectOrchestratorRequireIdentity){$true}elseif($ia){[bool]$ia.ok}else{$false}
        $bindingDrift=$false;$modelDrift=$false;$foreignPort=$false
        if($sh){$bindingDrift=(-not [bool]$sh.binding_ok);$modelDrift=[bool]$sh.model_policy_drift;$foreignPort=[bool]$sh.port_conflict_foreign}
        $rows.Add([ordered]@{
            name=if($a.name){[string]$a.name}elseif($i){[string]$i.name}else{[IO.Path]::GetFileName($project)}
            project_dir=$project;project_exists=[bool](Test-Path -LiteralPath $project -PathType Container);affinity_mapped=$true
            affinity_state=if($r){[string]$r.state}else{'INSTANCE_MISSING'};reason=if($r){[string]$r.reason}else{'Không resolve được Project Affinity.'}
            instance_id=$iid;instance_name=if($i){[string]$i.name}else{''};account=if($i){[string]$i.accountEmail}else{[string]$a.preferredAccount}
            fallback_account=if($r -and $r.fallback){[string]$r.fallback.email}else{''}
            client_running=if($i){[bool](Test-CodexInstanceClientOwned $i)}else{$false};router_online=if($i){[bool](Test-CodexInstanceRouterOwned $i)}else{$false}
            router_endpoint=if($r -and $r.router){[string]$r.router.endpoint}elseif($i){'http://127.0.0.1:'+([int]$i.port)+'/v1'}else{''}
            identity_ok=[bool]$identityOk;identity_fingerprint=if($ia){[string]$ia.fingerprint_sha256}else{''};security_ok=[bool]$securityOk
            port_conflict_foreign=[bool]$foreignPort;binding_drift=[bool]$bindingDrift;model_policy_drift=[bool]$modelDrift
            model_configured=[bool]($null -ne $pol -and -not [string]::IsNullOrWhiteSpace([string]$pol.model));model=if($pol){[string]$pol.model}else{''};reasoning=if($pol){[string]$pol.reasoning}else{''};profile=if($pol){[string]$pol.profile}else{[string]$script:S.ModelManagerDefaultProfile}
            account_health=if($r -and $r.primary){[int]$r.primary.health}else{$null};hourly_remaining=if($r -and $r.primary){$r.primary.hourly}else{$null};weekly_remaining=if($r -and $r.primary){$r.primary.weekly}else{$null}
        })
    }
    return [ordered]@{schema_version=1;version='25.42';generated_utc=[DateTime]::UtcNow.ToString('o');projects=@($rows);security_gate_ok=[bool]$securityOk}
}
function Invoke-HmsProjectOrchestrator {
    param([ValidateSet('status','preflight')][string]$Mode='status',[string]$ProjectDir='')
    if(-not [bool]$script:S.ProjectOrchestratorEnabled){throw 'PROJECT_ORCHESTRATOR_DISABLED'}
    Ensure-Dir $script:ProjectOrchestratorDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_ProjectOrchestrator.py';if(-not (Test-Path -LiteralPath $tool)){throw 'PROJECT_ORCHESTRATOR_ENGINE_MISSING'}
    $fleetPath=Join-Path $env:TEMP ('hms-project-orchestrator-fleet-'+[Guid]::NewGuid().ToString('N')+'.json')
    $inputPath=$null
    try{
        Save-JsonAtomic $fleetPath (Get-HmsProjectOrchestratorFleetObject)
        $args=@('--mode',$Mode,'--fleet',$fleetPath,'--state',$script:ProjectOrchestratorLatestPath)
        if($Mode -eq 'preflight'){
            if([string]::IsNullOrWhiteSpace($ProjectDir)){$inp=Read-HmsProjectOrchestratorBackendInput;$ProjectDir=[string]$inp.project_dir}
            $inputPath=Join-Path $env:TEMP ('hms-project-orchestrator-input-'+[Guid]::NewGuid().ToString('N')+'.json');Save-JsonAtomic $inputPath ([ordered]@{project_dir=$ProjectDir});$args+=@('--input',$inputPath)
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        foreach($f in @($fleetPath,$inputPath)){if($f -and (Test-Path -LiteralPath $f)){Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue}}
    }
}
function Add-HmsProjectOrchestratorHistory {
    param([string]$Event,[string]$Project,[string]$InstanceId,[string]$Account,[string]$Message,[string]$PlanHash='')
    try{Ensure-Dir $script:ProjectOrchestratorDir;$o=[ordered]@{time=[DateTime]::UtcNow.ToString('o');event=$Event;project=$Project;instance_id=$InstanceId;account=$Account;plan_hash=$PlanHash;message=(Redact-LocalApiText $Message)};Add-Content -LiteralPath $script:ProjectOrchestratorHistoryPath -Value ($o|ConvertTo-Json -Compress) -Encoding UTF8}catch{}
}
function Get-HmsNativeProjectOrchestratorObject {
    $d=Invoke-HmsProjectOrchestrator 'status'
    return @{ok=$true;version=$script:Version;project_orchestrator=$d;enabled=[bool]$script:S.ProjectOrchestratorEnabled}
}
function Preflight-HmsNativeProjectOrchestrator {
    $input=Read-HmsProjectOrchestratorBackendInput;$project=[string]$input.project_dir
    $d=Invoke-HmsProjectOrchestrator -Mode 'preflight' -ProjectDir $project
    $s=$d.selected
    Add-HmsProjectOrchestratorHistory 'PREFLIGHT' $project ([string]$s.instance_id) ([string]$s.account) $(if([bool]$s.one_click_ready){'READY'}else{('BLOCKED: '+(@($s.blockers)-join ','))}) ([string]$s.plan_hash)
    return @{ok=$true;version=$script:Version;project_orchestrator=$d;message=$(if([bool]$s.one_click_ready){'Project Orchestrator preflight PASS.'}else{'Project Orchestrator preflight BLOCKED: '+(@($s.blockers)-join ', ')})}
}
function Launch-HmsNativeProjectOrchestrator {
    $input=Read-HmsProjectOrchestratorBackendInput;$project=[string]$input.project_dir
    $d=Invoke-HmsProjectOrchestrator -Mode 'preflight' -ProjectDir $project;$s=$d.selected
    if(-not [bool]$s.one_click_ready){throw ('PROJECT_ORCHESTRATOR_BLOCKED: '+(@($s.blockers)-join ', '))}
    $r=Resolve-CodexProjectAffinity $project
    if(-not $r.instance){throw 'PROJECT_ORCHESTRATOR_INSTANCE_MISSING'}
    $smartNote=''
    if([bool]$script:S.SmartModelRouterEnabled -and [bool]$script:S.SmartModelRouterApplyBeforeLaunch -and ([string]$script:S.SmartModelRouterMode).ToUpperInvariant() -eq 'GUARDED_AUTO'){
        try{$sm=Invoke-HmsSmartModelRouter -Mode 'apply' -ProjectDir $project -Manual $false;$smartNote=' · SmartModel='+$(if($sm.apply -and [bool]$sm.apply.applied){'APPLIED'}else{'KEEP'})}catch{$smartNote=' · SmartModel=WARN'}
    }
    $msg=(Start-CodexProjectAffinity $project)+$smartNote
    $i=Get-CodexInstanceById ([string]$r.instance.id)
    if([bool]$script:S.ProjectOrchestratorVerifyOwnershipAfterLaunch){
        if(-not (Test-CodexInstanceClientOwned $i)){throw 'PROJECT_ORCHESTRATOR_CLIENT_OWNERSHIP_VERIFY_FAILED'}
        if(-not (Test-CodexInstanceRouterOwned $i)){throw 'PROJECT_ORCHESTRATOR_ROUTER_OWNERSHIP_VERIFY_FAILED'}
    }
    Add-HmsProjectOrchestratorHistory 'LAUNCH' $project ([string]$i.id) ([string]$i.accountEmail) $msg ([string]$s.plan_hash)
    $out=Invoke-HmsProjectOrchestrator 'status'
    return @{ok=$true;version=$script:Version;project_orchestrator=$out;message=('ONE-CLICK PROJECT READY · '+$msg)}
}


# ============================================================
# v25.43 MULTI-CODEX TEAM
# Coder / Reviewer / Tester use separate managed instances/workspaces.
# No silent takeover; topology changes increment explicit epoch.
# ============================================================
function Read-HmsMultiCodexTeamBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path -LiteralPath $BackendInputPath)){throw 'MULTI_CODEX_TEAM_INPUT_MISSING'}
    try{return (Get-Content -LiteralPath $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'MULTI_CODEX_TEAM_INPUT_INVALID'}
}
function Get-HmsMultiCodexTeamGitInfo {
    param([string]$Path)
    $out=[ordered]@{git_toplevel='';git_common_dir=''}
    if([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Container)){return [PSCustomObject]$out}
    try{
        $git=Get-Command git.exe -ErrorAction SilentlyContinue;if(-not $git){$git=Get-Command git -ErrorAction SilentlyContinue};if(-not $git){return [PSCustomObject]$out}
        $top=(& $git.Source -C $Path rev-parse --show-toplevel 2>$null|Select-Object -First 1)
        $common=(& $git.Source -C $Path rev-parse --git-common-dir 2>$null|Select-Object -First 1)
        if($top){try{$out.git_toplevel=(Get-HmsCanonicalProjectPath ([string]$top))}catch{$out.git_toplevel=[string]$top}}
        if($common){
            $c=[string]$common
            if(-not [IO.Path]::IsPathRooted($c)){$c=Join-Path $Path $c}
            try{$out.git_common_dir=([IO.Path]::GetFullPath($c)).TrimEnd([char[]]'\/')}catch{$out.git_common_dir=$c}
        }
    }catch{}
    return [PSCustomObject]$out
}
function Get-HmsMultiCodexTeamByProject {
    param([string]$ProjectDir)
    $key=Get-HmsPathKey $ProjectDir
    if(-not $key){return $null}
    foreach($t in @((Get-HmsMultiCodexTeamStore).teams)){if((Get-HmsPathKey ([string]$t.projectDir)) -eq $key){return $t}}
    return $null
}
function Add-HmsMultiCodexTeamHistory {
    param([string]$Event,[string]$Project,[string]$TeamId,[int]$Epoch,[string]$Message,[string]$PlanHash='')
    try{Ensure-Dir $script:MultiCodexTeamDir;$o=[ordered]@{time=[DateTime]::UtcNow.ToString('o');event=$Event;project=$Project;team_id=$TeamId;epoch=$Epoch;plan_hash=$PlanHash;message=(Redact-LocalApiText $Message)};Add-Content -LiteralPath $script:MultiCodexTeamHistoryPath -Value ($o|ConvertTo-Json -Compress) -Encoding UTF8}catch{}
}
function Get-HmsMultiCodexTeamSecurityOk {
    try{return (Get-HmsProjectOrchestratorSecurityOk (Get-HmsSecuritySnapshot))}catch{return $false}
}
function Get-HmsMultiCodexTeamFleetObject {
    $store=Get-HmsMultiCodexTeamStore
    $instances=Get-CodexInstanceStore
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    $self=$null;try{$self=Get-HmsSelfHealingSnapshot}catch{}
    $selfMap=@{};if($self){foreach($x in @($self.instances)){$selfMap[[string]$x.id]=$x}}
    $securityOk=Get-HmsMultiCodexTeamSecurityOk
    $policy=$null;try{$policy=Load-JsonObjectSafe $script:ModelManagerPolicyPath}catch{}
    $policyMap=@{};if($policy){foreach($x in @($policy.projects)){try{$policyMap[(Get-HmsPathKey ([string]$x.project_dir))]=$x}catch{}}}
    $teams=[System.Collections.Generic.List[object]]::new()
    foreach($t in @($store.teams)){
        $members=[System.Collections.Generic.List[object]]::new()
        foreach($m in @($t.members)){
            $i=$null;try{$i=Get-CodexInstanceById ([string]$m.instanceId)}catch{}
            if(-not $i){$members.Add([ordered]@{role=[string]$m.role;instance_id=[string]$m.instanceId;project_exists=$false;identity_ok=$false;security_ok=$securityOk;binding_ok=$false;workspace=''});continue}
            $iid=[string]$i.id;$ia=$identityMap[$iid];$sh=$selfMap[$iid];$git=Get-HmsMultiCodexTeamGitInfo ([string]$i.projectDir);$pol=$policyMap[(Get-HmsPathKey ([string]$i.projectDir))]
            $members.Add([ordered]@{
                role=([string]$m.role).ToUpperInvariant();instance_id=$iid;instance_name=[string]$i.name;account=[string]$i.accountEmail;workspace=[string]$i.projectDir
                project_exists=[bool](Test-Path -LiteralPath ([string]$i.projectDir) -PathType Container);client_running=[bool](Test-CodexInstanceClientOwned $i);router_online=[bool](Test-CodexInstanceRouterOwned $i)
                identity_ok=if($ia){[bool]$ia.ok}else{$false};security_ok=[bool]$securityOk;binding_ok=if($sh){[bool]$sh.binding_ok}else{$true};port_conflict_foreign=if($sh){[bool]$sh.port_conflict_foreign}else{$false}
                model=if($pol){[string]$pol.model}else{''};reasoning=if($pol){[string]$pol.reasoning}else{''};profile=if($pol){[string]$pol.profile}else{[string]$script:S.ModelManagerDefaultProfile}
                git_common_dir=[string]$git.git_common_dir;git_toplevel=[string]$git.git_toplevel;port=[int]$i.port
            })
        }
        $teams.Add([ordered]@{team_id=[string]$t.teamId;name=[string]$t.name;project_dir=[string]$t.projectDir;project_exists=[bool](Test-Path -LiteralPath ([string]$t.projectDir) -PathType Container);epoch=[int]$t.epoch;members=@($members)})
    }
    $projectCatalog=[System.Collections.Generic.List[object]]::new()
    try{Sync-CodexProjectAffinityFromInstances;foreach($a in @((Get-CodexProjectAffinityStore).projects)){$projectCatalog.Add([ordered]@{name=[string]$a.name;project_dir=[string]$a.projectDir;instance_id=[string]$a.instanceId})}}catch{}
    $instanceCatalog=[System.Collections.Generic.List[object]]::new()
    foreach($i in @($instances.instances)){$instanceCatalog.Add([ordered]@{id=[string]$i.id;name=[string]$i.name;account=[string]$i.accountEmail;project_dir=[string]$i.projectDir;client_running=[bool](Test-CodexInstanceClientOwned $i);router_online=[bool](Test-CodexInstanceRouterOwned $i)})}
    return [ordered]@{
        schema_version=1;version='25.43';generated_utc=[DateTime]::UtcNow.ToString('o');teams=@($teams);project_catalog=@($projectCatalog);instance_catalog=@($instanceCatalog)
        config=[ordered]@{require_distinct_workspace=[bool]$script:S.MultiCodexTeamRequireDistinctWorkspace;require_distinct_account=[bool]$script:S.MultiCodexTeamRequireDistinctAccount;require_same_git_repo=[bool]$script:S.MultiCodexTeamRequireSameGitRepository;coder_must_match_project=[bool]$script:S.MultiCodexTeamCoderMustMatchProject;max_members=[int]$script:S.MultiCodexTeamMaxMembers}
    }
}
function Invoke-HmsMultiCodexTeam {
    param([ValidateSet('status','preflight')][string]$Mode='status',[string]$ProjectDir='')
    if(-not [bool]$script:S.MultiCodexTeamEnabled){throw 'MULTI_CODEX_TEAM_DISABLED'}
    Ensure-Dir $script:MultiCodexTeamDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_MultiTeam.py';if(-not (Test-Path -LiteralPath $tool)){throw 'MULTI_CODEX_TEAM_ENGINE_MISSING'}
    $fleetPath=Join-Path $env:TEMP ('hms-multi-team-fleet-'+[Guid]::NewGuid().ToString('N')+'.json');$inputPath=$null
    try{
        Save-JsonAtomic $fleetPath (Get-HmsMultiCodexTeamFleetObject)
        $args=@('--mode',$Mode,'--fleet',$fleetPath,'--state',$script:MultiCodexTeamLatestPath)
        if($Mode -eq 'preflight'){
            if([string]::IsNullOrWhiteSpace($ProjectDir)){$inp=Read-HmsMultiCodexTeamBackendInput;$ProjectDir=[string]$inp.project_dir}
            $inputPath=Join-Path $env:TEMP ('hms-multi-team-input-'+[Guid]::NewGuid().ToString('N')+'.json');Save-JsonAtomic $inputPath ([ordered]@{project_dir=$ProjectDir});$args+=@('--input',$inputPath)
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{foreach($f in @($fleetPath,$inputPath)){if($f -and (Test-Path -LiteralPath $f)){Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue}}}
}
function Get-HmsNativeMultiCodexTeamObject {
    $d=Invoke-HmsMultiCodexTeam 'status'
    return @{ok=$true;version=$script:Version;multi_codex_team=$d;enabled=[bool]$script:S.MultiCodexTeamEnabled}
}
function Save-HmsNativeMultiCodexTeam {
    $input=Read-HmsMultiCodexTeamBackendInput
    $project=Get-HmsCanonicalProjectPath ([string]$input.project_dir);$name=([string]$input.name).Trim();if(-not $name){$name=([IO.Path]::GetFileName($project)+' Codex Team')}
    $defs=@(@{role='CODER';id=[string]$input.coder_instance_id},@{role='REVIEWER';id=[string]$input.reviewer_instance_id},@{role='TESTER';id=[string]$input.tester_instance_id})
    $members=[System.Collections.Generic.List[object]]::new();$seen=@{}
    foreach($d in $defs){$id=([string]$d.id).Trim();if(-not $id){continue};if($seen.ContainsKey($id)){throw 'TEAM_INSTANCE_DUPLICATE_ROLE'};$seen[$id]=$true;$i=Get-CodexInstanceById $id;$members.Add([PSCustomObject]@{role=[string]$d.role;instanceId=$id})}
    if(@($members).Count -lt 2){throw 'TEAM_REQUIRES_AT_LEAST_2_ROLES'}
    $coder=@($members|Where-Object role -eq 'CODER'|Select-Object -First 1);if($coder.Count -ne 1){throw 'TEAM_REQUIRES_CODER'}
    $coderInst=Get-CodexInstanceById ([string]$coder[0].instanceId);if((Get-HmsPathKey ([string]$coderInst.projectDir)) -ne (Get-HmsPathKey $project)){throw 'TEAM_CODER_PROJECT_MISMATCH'}
    if([bool]$script:S.MultiCodexTeamRequireDistinctAccount){$acc=@();foreach($m in @($members)){$mi=Get-CodexInstanceById ([string]$m.instanceId);$acc+=([string]$mi.accountEmail).Trim().ToLowerInvariant()};if(@($acc|Select-Object -Unique).Count -ne $acc.Count){throw 'TEAM_ACCOUNT_ROLE_COLLISION'}}
    $teamStore=Get-HmsMultiCodexTeamStore;$old=Get-HmsMultiCodexTeamByProject $project
    foreach($other in @($teamStore.teams)){if($old -and ([string]$other.teamId) -eq ([string]$old.teamId)){continue};foreach($om in @($other.members)){if($seen.ContainsKey([string]$om.instanceId)){throw 'INSTANCE_ALREADY_BOUND_TO_OTHER_TEAM'}}}
    $newSig=(@($members|ForEach-Object {([string]$_.role)+':'+([string]$_.instanceId)}) -join '|')
    $oldSig='';if($old){$oldSig=(@($old.members|ForEach-Object {([string]$_.role)+':'+([string]$_.instanceId)}) -join '|')}
    $changed=(-not $old -or $newSig -ne $oldSig)
    if($changed -and $old){$ids=@($old.members|ForEach-Object {[string]$_.instanceId})+@($members|ForEach-Object {[string]$_.instanceId});foreach($id in @($ids|Select-Object -Unique)){try{if(Test-CodexInstanceClientOwned (Get-CodexInstanceById $id)){throw 'TEAM_REBIND_RUNNING_BLOCKED'}}catch{if($_.Exception.Message -eq 'TEAM_REBIND_RUNNING_BLOCKED'){throw}}}}
    $teamId=if($old){[string]$old.teamId}else{'team-'+[Guid]::NewGuid().ToString('N').Substring(0,10)};$epoch=if($old){[int]$old.epoch + $(if($changed){1}else{0})}else{1};if($epoch -lt 1){$epoch=1}
    $items=@($teamStore.teams);$found=$false
    foreach($t in $items){if((Get-HmsPathKey ([string]$t.projectDir)) -eq (Get-HmsPathKey $project)){$found=$true;$t.teamId=$teamId;$t.name=$name;$t.projectDir=$project;$t.epoch=$epoch;$t.members=@($members);$t.updatedUtc=[DateTime]::UtcNow.ToString('o')}}
    if(-not $found){$items+=[PSCustomObject]@{schemaVersion=1;teamId=$teamId;name=$name;projectDir=$project;epoch=$epoch;members=@($members);createdUtc=[DateTime]::UtcNow.ToString('o');updatedUtc=[DateTime]::UtcNow.ToString('o')}}
    $storeExisted=Test-Path -LiteralPath $script:MultiCodexTeamStorePath;$storeBackup=if($storeExisted){Get-Content -LiteralPath $script:MultiCodexTeamStorePath -Raw -Encoding UTF8}else{$null}
    try{
        $teamStore.teams=$items;Save-HmsMultiCodexTeamStore $teamStore
        $d=Invoke-HmsMultiCodexTeam 'preflight' $project;$sel=$d.selected
        if(-not [bool]$sel.one_click_ready){throw ('TEAM_TOPOLOGY_BLOCKED_AFTER_SAVE: '+(@($sel.blockers)-join ', '))}
        Add-HmsMultiCodexTeamHistory 'SAVE' $project $teamId $epoch ('Roles='+$newSig) ([string]$sel.plan_hash)
        return @{ok=$true;version=$script:Version;multi_codex_team=(Invoke-HmsMultiCodexTeam 'status');message=('Đã lưu team '+$name+' · epoch '+$epoch+' · '+$newSig)}
    }catch{
        try{if($storeExisted){Write-Utf8 $script:MultiCodexTeamStorePath $storeBackup;Set-HmsSecuritySealTrustedPath $script:MultiCodexTeamStorePath 'multi-codex-team-rollback'}else{Remove-Item -LiteralPath $script:MultiCodexTeamStorePath -Force -ErrorAction SilentlyContinue}}catch{}
        throw
    }
}
function Preflight-HmsNativeMultiCodexTeam {
    $input=Read-HmsMultiCodexTeamBackendInput;$project=[string]$input.project_dir;$d=Invoke-HmsMultiCodexTeam 'preflight' $project;$s=$d.selected
    Add-HmsMultiCodexTeamHistory 'PREFLIGHT' $project ([string]$s.team_id) ([int]$s.epoch) $(if([bool]$s.one_click_ready){'READY'}else{'BLOCKED: '+(@($s.blockers)-join ',')}) ([string]$s.plan_hash)
    return @{ok=$true;version=$script:Version;multi_codex_team=$d;message=$(if([bool]$s.one_click_ready){'Multi-Codex Team preflight PASS.'}else{'Multi-Codex Team BLOCKED: '+(@($s.blockers)-join ', ')})}
}
function Launch-HmsNativeMultiCodexTeam {
    $input=Read-HmsMultiCodexTeamBackendInput;$project=[string]$input.project_dir;$d=Invoke-HmsMultiCodexTeam 'preflight' $project;$s=$d.selected
    if(-not [bool]$s.one_click_ready){throw ('MULTI_CODEX_TEAM_BLOCKED: '+(@($s.blockers)-join ', '))}
    $started=[System.Collections.Generic.List[string]]::new();$messages=[System.Collections.Generic.List[string]]::new()
    try{
        if([bool]$script:S.SmartModelRouterEnabled -and [bool]$script:S.SmartModelRouterApplyBeforeLaunch -and ([string]$script:S.SmartModelRouterMode).ToUpperInvariant() -eq 'GUARDED_AUTO'){
            try{$sm=Invoke-HmsSmartModelRouter -Mode 'apply' -ProjectDir $project -Manual $false;$messages.Add('SMART_MODEL: '+$(if($sm.apply -and [bool]$sm.apply.applied){'APPLIED'}else{'KEEP'}))}catch{$messages.Add('SMART_MODEL: WARN')}
        }
        foreach($m in @($s.members)){
            $i=Get-CodexInstanceById ([string]$m.instance_id)
            if(Test-CodexInstanceClientOwned $i){$messages.Add(([string]$m.role+': KEEP_RUNNING'));continue}
            $msg=Start-CodexInstanceSafe ([string]$i.id);$started.Add([string]$i.id);$messages.Add(([string]$m.role+': '+$msg))
            if([bool]$script:S.MultiCodexTeamVerifyOwnershipAfterLaunch){$ii=Get-CodexInstanceById ([string]$i.id);if(-not (Test-CodexInstanceClientOwned $ii)){throw ('TEAM_CLIENT_OWNERSHIP_VERIFY_FAILED_'+[string]$m.role)};if(-not (Test-CodexInstanceRouterOwned $ii)){throw ('TEAM_ROUTER_OWNERSHIP_VERIFY_FAILED_'+[string]$m.role)}}
        }
        $coder=@($s.members|Where-Object role -eq 'CODER'|Select-Object -First 1);if($coder.Count){try{$null=Focus-CodexInstance ([string]$coder[0].instance_id)}catch{}}
        Add-HmsMultiCodexTeamHistory 'LAUNCH' $project ([string]$s.team_id) ([int]$s.epoch) ($messages -join ' | ') ([string]$s.plan_hash)
    }catch{
        for($x=$started.Count-1;$x -ge 0;$x--){try{$ii=Get-CodexInstanceById ([string]$started[$x]);if((Test-CodexInstanceClientOwned $ii) -or (Test-CodexInstanceRouterOwned $ii)){$null=Stop-CodexInstance ([string]$ii.id)}}catch{}}
        Add-HmsMultiCodexTeamHistory 'LAUNCH_ROLLBACK' $project ([string]$s.team_id) ([int]$s.epoch) $_.Exception.Message ([string]$s.plan_hash)
        throw
    }
    return @{ok=$true;version=$script:Version;multi_codex_team=(Invoke-HmsMultiCodexTeam 'status');message=('MULTI-CODEX TEAM READY · '+($messages -join ' | '))}
}

function Read-HmsModelManagerBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw 'MODEL_MANAGER_INPUT_MISSING'}
    try{return (Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'MODEL_MANAGER_INPUT_INVALID'}
}
function Get-HmsModelManagerConfigJson {
    return ([ordered]@{
        enabled=[bool]$script:S.ModelManagerEnabled
        auto_discover=[bool]$script:S.ModelManagerAutoDiscover
        require_live_model=[bool]$script:S.ModelManagerRequireLiveModel
        apply_before_launch=[bool]$script:S.ModelManagerApplyBeforeLaunch
        default_reasoning=[string]$script:S.ModelManagerDefaultReasoning
        default_profile=[string]$script:S.ModelManagerDefaultProfile
    }|ConvertTo-Json -Compress)
}
function Get-HmsModelManagerFleetObject {
    Sync-CodexProjectAffinityFromInstances
    $store=Get-CodexInstanceStore
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    $instances=[System.Collections.Generic.List[object]]::new()
    foreach($i in @($store.instances)){
        $ia=$identityMap[[string]$i.id]
        $instances.Add([ordered]@{
            id=[string]$i.id;name=[string]$i.name;account_email=[string]$i.accountEmail;project_dir=[string]$i.projectDir;
            root=[string]$i.root;codex_home=[string]$i.codexHome;app_data=[string]$i.appData;router_dir=[string]$i.routerDir;port=[int]$i.port;
            router_online=(Test-CodexInstanceRouterOwned $i);client_running=(Test-CodexInstanceClientOwned $i);
            identity_ok=if($ia){[bool]$ia.ok}else{$false};identity_fingerprint=if($ia){[string]$ia.fingerprint_sha256}else{''}
        })
    }
    $aff=Get-CodexProjectAffinityStore
    $projects=[System.Collections.Generic.List[object]]::new()
    foreach($p in @($aff.projects)){$projects.Add([ordered]@{name=[string]$p.name;project_dir=[string]$p.projectDir;instance_id=[string]$p.instanceId;preferred_account=[string]$p.preferredAccount})}
    return [ordered]@{schema_version=1;version='25.37';instances=@($instances);projects=@($projects);secret_fields_excluded=$true}
}
function Get-HmsLiveModelCatalog {
    $rows=[System.Collections.Generic.List[object]]::new();$seen=@{}
    $targets=[System.Collections.Generic.List[object]]::new()
    if(PortOpen ([int]$script:S.ProxyPort)){$targets.Add([ordered]@{port=[int]$script:S.ProxyPort;key=[string]$script:S.LocalApiKey;source='GLOBAL_ROUTER'})}
    foreach($i in @((Get-CodexInstanceStore).instances)){
        if(Test-CodexInstanceRouterOwned $i){$targets.Add([ordered]@{port=[int]$i.port;key=[string](Get-HmsInstanceApiKey $i);source=('INSTANCE:'+[string]$i.id)})}
    }
    foreach($t in @($targets)){
        try{
            $r=Invoke-RestMethod -Uri ("http://127.0.0.1:"+[int]$t.port+"/v1/models") -Headers @{Authorization=("Bearer "+[string]$t.key)} -TimeoutSec 8
            foreach($m in @($r.data)){
                $id=[string]$m.id;if([string]::IsNullOrWhiteSpace($id)){continue}
                $k=$id.ToLowerInvariant()+"|"+[string]$t.source
                if(-not $seen.ContainsKey($k)){$rows.Add([ordered]@{id=$id;owned_by=[string]$m.owned_by;source=[string]$t.source});$seen[$k]=$true}
            }
        }catch{}
    }
    return [ordered]@{generated_utc=[DateTime]::UtcNow.ToString('o');models=@($rows);live_sources=@($targets|ForEach-Object{$_.source})}
}
function Invoke-HmsModelManager {
    param([ValidateSet('status','discover','set-policy','apply')][string]$Mode='status',[string]$ProjectDir='')
    Ensure-Dir $script:ModelManagerDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_ModelReasoningManager.py'
    if(-not (Test-Path $tool)){throw 'Thiếu HMS_Codex_ModelReasoningManager.py'}
    $fleetPath=Join-Path $env:TEMP ('hms-model-fleet-'+[Guid]::NewGuid().ToString('N')+'.json')
    $catalogPath=Join-Path $env:TEMP ('hms-model-catalog-'+[Guid]::NewGuid().ToString('N')+'.json')
    $inputPath=$null
    try{
        Save-JsonAtomic $fleetPath (Get-HmsModelManagerFleetObject)
        Save-JsonAtomic $catalogPath (Get-HmsLiveModelCatalog)
        $args=@('--mode',$Mode,'--state',$script:ModelManagerStatePath,'--policy',$script:ModelManagerPolicyPath,'--fleet',$fleetPath,'--catalog',$catalogPath,'--config-json',(Get-HmsModelManagerConfigJson))
        if(Test-Path $script:AccountAnalyticsReportPath){$args+=@('--analytics',$script:AccountAnalyticsReportPath)}
        if($Mode -in @('set-policy','apply')){
            $payload=$null
            if($Mode -eq 'set-policy'){$payload=Read-HmsModelManagerBackendInput}else{$payload=[ordered]@{project_dir=$ProjectDir};if([string]::IsNullOrWhiteSpace($ProjectDir)){$payload=Read-HmsModelManagerBackendInput}}
            $inputPath=Join-Path $env:TEMP ('hms-model-input-'+[Guid]::NewGuid().ToString('N')+'.json');Save-JsonAtomic $inputPath $payload;$args+=@('--input',$inputPath)
        }
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{
        foreach($f in @($fleetPath,$catalogPath,$inputPath)){if($f -and (Test-Path $f)){Remove-Item $f -Force -ErrorAction SilentlyContinue}}
    }
}
function Get-HmsNativeModelManagerObject {
    $d=Invoke-HmsModelManager -Mode $(if([bool]$script:S.ModelManagerAutoDiscover){'discover'}else{'status'})
    return @{ok=$true;version=$script:Version;model_manager=$d;enabled=[bool]$script:S.ModelManagerEnabled}
}
function Save-HmsNativeModelPolicy {
    if(-not [bool]$script:S.ModelManagerEnabled){throw 'MODEL_MANAGER_DISABLED'}
    $d=Invoke-HmsModelManager -Mode 'set-policy'
    Set-HmsSecuritySealTrustedPath $script:ModelManagerPolicyPath 'model-policy-write'
    return @{ok=$true;version=$script:Version;model_manager=$d;message='Đã lưu model/reasoning policy cho project. Chưa restart Codex.'}
}
function Apply-HmsNativeModelPolicy {
    if(-not [bool]$script:S.ModelManagerEnabled){throw 'MODEL_MANAGER_DISABLED'}
    $input=Read-HmsModelManagerBackendInput
    $d=Invoke-HmsModelManager -Mode 'apply' -ProjectDir ([string]$input.project_dir)
    try{
        $aff=@(Get-CodexProjectAffinityByPath ([string]$input.project_dir))
        if($aff.Count){$ii=Get-CodexInstanceById ([string]$aff[0].instanceId);Set-HmsSecuritySealTrustedPath (Join-Path ([string]$ii.codexHome) 'config.toml') 'model-policy-apply'}
    }catch{}
    $rr=$d.apply_result
    $msg='Đã áp dụng model/reasoning vào isolated config.toml; stable endpoint/provider được giữ nguyên.'
    if($rr -and [bool]$rr.restart_recommended){$msg+=' Instance đang chạy: nên RESTART instance để Codex nạp policy chắc chắn.'}
    return @{ok=$true;version=$script:Version;model_manager=$d;message=$msg}
}

# ============================================================
# v25.45 CROSS-PC / LAN CODEX POOL
# Signed metadata-only registry + project lease/epoch. Raw Codex credentials never leave a node.
# ============================================================
function Read-HmsLanPoolBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path -LiteralPath $BackendInputPath)){return $null}
    try{return (Get-Content -LiteralPath $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'LAN_POOL_INPUT_INVALID'}
}
function Get-HmsLanPoolKeyHex {
    $v='';try{$v=[string](Get-HmsProtectedSecret $script:LanPoolCredentialTarget)}catch{}
    if($v -and $v -match '^[0-9a-fA-F]{64}$'){return $v.ToLowerInvariant()}
    return ''
}
function New-HmsLanPoolPairingKeyHex {
    param([string]$Code)
    $Code=([string]$Code).Trim();if($Code.Length -lt 16){throw 'LAN_PAIRING_CODE_MIN_16_CHARS'}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$bytes=[Text.Encoding]::UTF8.GetBytes('HMS-AI-Cockpit-LAN-Pool-v25.45|'+$Code);return (($sha.ComputeHash($bytes)|ForEach-Object{$_.ToString('x2')})-join'')}finally{$sha.Dispose()}
}
function Get-HmsLanGitOrigin {
    param([string]$ProjectDir)
    if([string]::IsNullOrWhiteSpace($ProjectDir) -or -not (Test-Path -LiteralPath $ProjectDir -PathType Container)){return ''}
    try{
        $git=Get-Command git.exe -ErrorAction SilentlyContinue;if(-not $git){$git=Get-Command git -ErrorAction SilentlyContinue};if(-not $git){return ''}
        return ([string]((& $git.Source -C $ProjectDir config --get remote.origin.url 2>$null|Select-Object -First 1))).Trim()
    }catch{return ''}
}
function Get-HmsLanPoolProjectRows {
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($i in @((Get-CodexInstanceStore).instances)){
        $p=[string]$i.projectDir;if([string]::IsNullOrWhiteSpace($p)){continue}
        $rows.Add([ordered]@{project_dir=$p;project_label=$(if($i.name){[string]$i.name}else{[IO.Path]::GetFileName($p)});git_origin=(Get-HmsLanGitOrigin $p);instance_id=[string]$i.id;client_running=[bool](Test-CodexInstanceClientOwned $i)})
    }
    return @($rows)
}
function Get-HmsLanPoolSnapshotInput {
    $projects=Get-HmsLanPoolProjectRows
    $running=@($projects|Where-Object{[bool]$_.client_running})
    $accountHashes=[System.Collections.Generic.List[string]]::new()
    foreach($a in @(Get-CodexAccountRecords)){
        try{$sha=[Security.Cryptography.SHA256]::Create();$b=[Text.Encoding]::UTF8.GetBytes(([string]$a.Email).Trim().ToLowerInvariant());$h=(($sha.ComputeHash($b)|ForEach-Object{$_.ToString('x2')})-join'');$sha.Dispose();if($h){$accountHashes.Add('sha256:'+$h)}}catch{}
    }
    return [ordered]@{health='READY';capacity=[Math]::Max(0,(@((Get-CodexInstanceStore).instances).Count)-$running.Count);running_instances=$running.Count;account_hashes=@($accountHashes);projects=@($projects);secret_values_excluded=$true}
}
function Invoke-HmsLanPoolPython {
    param([ValidateSet('status','heartbeat','acquire','release')][string]$Mode,[object]$Payload=$null)
    if(-not [bool]$script:S.LanPoolEnabled){throw 'LAN_POOL_DISABLED'}
    $shared=([string]$script:S.LanPoolSharedPath).Trim();if(-not $shared){throw 'LAN_POOL_SHARED_PATH_MISSING'}
    $key=Get-HmsLanPoolKeyHex;if(-not $key){throw 'LAN_POOL_NOT_PAIRED'}
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_LanPool.py';if(-not (Test-Path -LiteralPath $tool)){throw 'LAN_POOL_ENGINE_MISSING'}
    Ensure-Dir $script:LanPoolDir
    $inputPath=$null;$oldEnv=$env:HMS_LAN_POOL_KEY_HEX
    try{
        $env:HMS_LAN_POOL_KEY_HEX=$key
        if($null -ne $Payload){$inputPath=Join-Path $env:TEMP ('hms-lanpool-'+[Guid]::NewGuid().ToString('N')+'.json');Save-JsonAtomic $inputPath $Payload}
        $args=@('--mode',$Mode,'--shared',$shared,'--local-state',$script:LanPoolNodeStatePath,'--node-name',([string]$script:S.LanPoolNodeName),'--ttl',([string][int]$script:S.LanPoolLeaseTtlSec))
        if($inputPath){$args+=@('--input',$inputPath)}
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        if($j.data -and $j.data.lan_pool){try{Save-JsonAtomic $script:LanPoolLatestPath $j.data.lan_pool}catch{}}
        return $j.data
    }finally{
        if($null -eq $oldEnv){Remove-Item Env:HMS_LAN_POOL_KEY_HEX -ErrorAction SilentlyContinue}else{$env:HMS_LAN_POOL_KEY_HEX=$oldEnv}
        if($inputPath -and (Test-Path -LiteralPath $inputPath)){Remove-Item -LiteralPath $inputPath -Force -ErrorAction SilentlyContinue}
    }
}
function Invoke-HmsLanPoolHeartbeat {
    if(-not [bool]$script:S.LanPoolEnabled){return $null}
    $payload=Get-HmsLanPoolSnapshotInput
    # Renew project ownership only for managed clients that are actually running on this node.
    foreach($p in @($payload.projects|Where-Object{[bool]$_.client_running})){
        try{$null=Invoke-HmsLanPoolPython -Mode 'acquire' -Payload $p}catch{throw ('LAN_PROJECT_LEASE_RENEW_FAILED: '+[string]$_.Exception.Message)}
    }
    return Invoke-HmsLanPoolPython -Mode 'heartbeat' -Payload $payload
}
function Assert-HmsLanProjectLeaseBeforeLaunch {
    param([object]$Instance)
    if(-not [bool]$script:S.LanPoolEnabled -or -not [bool]$script:S.LanPoolBlockCrossNodeProjectConflict){return $null}
    $p=[ordered]@{project_dir=[string]$Instance.projectDir;project_label=[string]$Instance.name;git_origin=(Get-HmsLanGitOrigin ([string]$Instance.projectDir));instance_id=[string]$Instance.id}
    $r=Invoke-HmsLanPoolPython -Mode 'acquire' -Payload $p
    if(-not $r -or -not [bool]$r.ok){$st='UNKNOWN';try{$st=[string]$r.lease_result.status}catch{};throw ('LAN_PROJECT_OWNERSHIP_BLOCKED: '+$st)}
    return $r.lease_result
}
function Get-HmsNativeLanPoolObject {
    if(-not [bool]$script:S.LanPoolEnabled){return @{ok=$true;version=$script:Version;lan_pool=@{enabled=$false;paired=[bool](Get-HmsLanPoolKeyHex);shared_path=[string]$script:S.LanPoolSharedPath;summary=@{nodes=0;online=0;stale=0;leases=0;invalid_signatures=0};nodes=@();leases=@();projects=@();security=@{credential_sharing=$false;raw_token_sharing=$false;secret_values_excluded=$true}}}}
    $payload=[ordered]@{projects=@(Get-HmsLanPoolProjectRows)}
    try{$d=Invoke-HmsLanPoolPython -Mode 'status' -Payload $payload;return @{ok=$true;version=$script:Version;lan_pool=$d.lan_pool;enabled=$true;paired=$true;shared_path=[string]$script:S.LanPoolSharedPath}}catch{return @{ok=$false;version=$script:Version;error=[string]$_.Exception.Message;enabled=$true;paired=[bool](Get-HmsLanPoolKeyHex);shared_path=[string]$script:S.LanPoolSharedPath}}
}
function Pair-HmsNativeLanPool {
    $input=Read-HmsLanPoolBackendInput;if(-not $input){throw 'LAN_POOL_INPUT_MISSING'}
    $shared=([string]$input.shared_path).Trim();$code=([string]$input.pairing_code).Trim();if(-not $shared){throw 'LAN_POOL_SHARED_PATH_MISSING'}
    if(-not (Test-Path -LiteralPath $shared -PathType Container)){try{New-Item -ItemType Directory -Path $shared -Force|Out-Null}catch{throw 'LAN_POOL_SHARED_PATH_UNAVAILABLE'}}
    $hex=New-HmsLanPoolPairingKeyHex $code;$null=Set-HmsProtectedSecret $script:LanPoolCredentialTarget $hex
    $script:S.LanPoolSharedPath=$shared;$script:S.LanPoolEnabled=$true
    if($input.PSObject.Properties['node_name'] -and [string]$input.node_name){$script:S.LanPoolNodeName=[string]$input.node_name}elseif(-not [string]$script:S.LanPoolNodeName){$script:S.LanPoolNodeName=[string]$env:COMPUTERNAME}
    Save-Settings
    $null=Invoke-HmsLanPoolHeartbeat
    $r=Get-HmsNativeLanPoolObject;$r['message']='LAN Pool đã pair. Pairing key được lưu bằng Windows Credential Manager/DPAPI; shared registry chỉ chứa metadata đã ký.';return $r
}
function Invoke-HmsNativeLanPoolHeartbeat {
    $null=Invoke-HmsLanPoolHeartbeat;$r=Get-HmsNativeLanPoolObject;$r['message']='LAN heartbeat + active project lease renewal hoàn tất.';return $r
}
function Invoke-HmsNativeLanProjectLease {
    param([ValidateSet('acquire','release')][string]$Mode)
    $input=Read-HmsLanPoolBackendInput;if(-not $input){throw 'LAN_POOL_INPUT_MISSING'}
    $p=[ordered]@{project_dir=[string]$input.project_dir;project_label=$(if($input.PSObject.Properties['project_label']){[string]$input.project_label}else{''});git_origin=(Get-HmsLanGitOrigin ([string]$input.project_dir))}
    $d=Invoke-HmsLanPoolPython -Mode $Mode -Payload $p
    if(-not [bool]$d.ok){throw ('LAN_PROJECT_LEASE_'+$Mode.ToUpperInvariant()+'_BLOCKED: '+[string]$d.lease_result.status)}
    $r=Get-HmsNativeLanPoolObject;$r['message']=('LAN project lease '+$Mode+' · '+[string]$d.lease_result.status);return $r
}

# ============================================================
# v25.44 SMART MODEL ROUTER
# Project + team role + workload -> model/reasoning + bounded account affinity.
# Closed-loop remains the sole authority for auth priority/weight and session routing.
# ============================================================
function Get-HmsSmartModelRouterConfigJson {
    return ([ordered]@{
        enabled=[bool]$script:S.SmartModelRouterEnabled
        mode=[string]$script:S.SmartModelRouterMode
        interval_sec=[int]$script:S.SmartModelRouterIntervalSec
        apply_before_launch=[bool]$script:S.SmartModelRouterApplyBeforeLaunch
        require_live_model=[bool]$script:S.SmartModelRouterRequireLiveModel
        protect_running_sessions=[bool]$script:S.SmartModelRouterProtectRunningSessions
        min_model_samples=[int]$script:S.SmartModelRouterMinModelSamples
        min_score_delta=[int]$script:S.SmartModelRouterMinScoreDelta
        max_account_adjustment=[int]([Math]::Min(8,[Math]::Max(0,[int]$script:S.SmartModelRouterMaxAccountAdjustment)))
        coder_profile=[string]$script:S.SmartModelRouterCoderProfile
        reviewer_profile=[string]$script:S.SmartModelRouterReviewerProfile
        tester_profile=[string]$script:S.SmartModelRouterTesterProfile
        solo_profile=[string]$script:S.SmartModelRouterSoloProfile
    }|ConvertTo-Json -Compress)
}
function Get-HmsSmartModelRouterFleetObject {
    $accounts=(Get-HmsNativeAccountCenterObject).accounts
    $store=Get-CodexInstanceStore
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    $security=$null;try{$security=Get-HmsSecuritySnapshot}catch{}
    $securityOk=Get-HmsProjectOrchestratorSecurityOk $security
    $self=$null;try{$self=Get-HmsSelfHealingSnapshot}catch{}
    $selfMap=@{};if($self){foreach($x in @($self.instances)){$selfMap[[string]$x.id]=$x}}
    $roleMap=@{}
    try{
        $teams=Get-HmsMultiCodexTeamStore
        foreach($t in @($teams.teams)){foreach($m in @($t.members)){$roleMap[[string]$m.instanceId]=[ordered]@{team_id=[string]$t.teamId;team_role=([string]$m.role).ToUpperInvariant();team_epoch=[int]$t.epoch}}}
    }catch{}
    $instances=[System.Collections.Generic.List[object]]::new()
    foreach($inst in @($store.instances)){
        $iid=[string]$inst.id;$ia=$identityMap[$iid];$sh=$selfMap[$iid];$rm=$roleMap[$iid]
        $manifestPath=Get-CodexInstancePoolManifestPath $inst
        $manifest=if(Test-Path -LiteralPath $manifestPath){Load-JsonObjectSafe $manifestPath}else{$null}
        $endpoint='http://127.0.0.1:'+([int]$inst.port)+'/v1'
        if($manifest -and $manifest.PSObject.Properties['stable_endpoint']){$endpoint=[string]$manifest.stable_endpoint}
        $instances.Add([ordered]@{
            id=$iid;name=[string]$inst.name;account_email=[string]$inst.accountEmail;project_dir=[string]$inst.projectDir
            root=[string]$inst.root;codex_home=[string]$inst.codexHome;app_data=[string]$inst.appData;router_dir=[string]$inst.routerDir
            manifest_path=[string]$manifestPath;manifest=$manifest;port=[int]$inst.port
            client_running=[bool](Test-CodexInstanceClientOwned $inst);router_online=[bool](Test-CodexInstanceRouterOwned $inst)
            identity_ok=if($ia){[bool]$ia.ok}else{$false};security_ok=[bool]$securityOk
            binding_ok=if($sh){[bool]$sh.binding_ok}else{$true};port_conflict_foreign=if($sh){[bool]$sh.port_conflict_foreign}else{$false}
            stable_endpoint=$endpoint;team_id=if($rm){[string]$rm.team_id}else{''};team_role=if($rm){[string]$rm.team_role}else{'SOLO'};team_epoch=if($rm){[int]$rm.team_epoch}else{0}
        })
    }
    $safeAccounts=[System.Collections.Generic.List[object]]::new()
    foreach($a in @($accounts)){$safeAccounts.Add([ordered]@{email=[string]$a.email;status=[string]$a.status;health_score=[int]$a.health_score;pool_score=[int]$a.pool_score;quota=$a.quota})}
    return [ordered]@{schema_version=1;version='25.44';generated_utc=[DateTime]::UtcNow.ToString('o');accounts=@($safeAccounts);instances=@($instances);secret_fields_excluded=$true}
}
function Read-HmsSmartModelRouterBackendInput {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path -LiteralPath $BackendInputPath)){return [PSCustomObject]@{project_dir='';role='';manual=$false}}
    try{return (Get-Content -LiteralPath $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json)}catch{throw 'SMART_MODEL_ROUTER_INPUT_INVALID'}
}
function Add-HmsSmartModelRouterHistory {
    param([string]$Event,[object]$Data)
    try{Ensure-Dir $script:SmartModelRouterDir;$o=[ordered]@{time=[DateTime]::UtcNow.ToString('o');event=$Event;mode=[string]$script:S.SmartModelRouterMode;summary=if($Data){$Data.summary}else{$null};plan_hash=if($Data -and $Data.plan){[string]$Data.plan.plan_hash}else{''}};Add-Content -LiteralPath $script:SmartModelRouterHistoryPath -Value ($o|ConvertTo-Json -Compress -Depth 8) -Encoding UTF8}catch{}
}
function Invoke-HmsSmartModelRouter {
    param([ValidateSet('status','evaluate','apply','rollback')][string]$Mode='status',[string]$ProjectDir='',[string]$Role='',[bool]$Manual=$false)
    if(-not [bool]$script:S.SmartModelRouterEnabled){throw 'SMART_MODEL_ROUTER_DISABLED'}
    Ensure-Dir $script:SmartModelRouterDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_SmartModelRouter.py';if(-not (Test-Path -LiteralPath $tool)){throw 'SMART_MODEL_ROUTER_ENGINE_MISSING'}
    $fleetPath=Join-Path $env:TEMP ('hms-smart-model-fleet-'+[Guid]::NewGuid().ToString('N')+'.json')
    $catalogPath=Join-Path $env:TEMP ('hms-smart-model-catalog-'+[Guid]::NewGuid().ToString('N')+'.json')
    $inputPath=$null
    try{
        Save-JsonAtomic $fleetPath (Get-HmsSmartModelRouterFleetObject)
        Save-JsonAtomic $catalogPath (Get-HmsLiveModelCatalog)
        $args=@('--mode',$Mode,'--state',$script:SmartModelRouterStatePath,'--plan',$script:SmartModelRouterPlanPath,'--fleet',$fleetPath,'--catalog',$catalogPath,'--policy',$script:ModelManagerPolicyPath,'--config-json',(Get-HmsSmartModelRouterConfigJson))
        if(Test-Path -LiteralPath $script:AccountAnalyticsReportPath){$args+=@('--analytics',$script:AccountAnalyticsReportPath)}
        if(Test-Path -LiteralPath $script:PredictiveQuotaPlanPath){$args+=@('--predictive',$script:PredictiveQuotaPlanPath)}
        if(Test-Path -LiteralPath $script:CircuitBreakerPlanPath){$args+=@('--breaker',$script:CircuitBreakerPlanPath)}
        if(Test-Path -LiteralPath $script:ClosedLoopRouterStatePath){$args+=@('--closed-loop',$script:ClosedLoopRouterStatePath)}
        if($Mode -in @('evaluate','apply')){
            $inputPath=Join-Path $env:TEMP ('hms-smart-model-input-'+[Guid]::NewGuid().ToString('N')+'.json')
            Save-JsonAtomic $inputPath ([ordered]@{project_dir=$ProjectDir;role=$Role;manual=[bool]$Manual});$args+=@('--input',$inputPath)
        }
        if($Mode -eq 'rollback'){$args+=@('--input',(Join-Path $env:TEMP ('hms-smart-model-unused-'+[Guid]::NewGuid().ToString('N')+'.json')))}
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        $d=$j.data
        if($Mode -ne 'status'){Add-HmsSmartModelRouterHistory $Mode $d}
        return $d
    }finally{foreach($f in @($fleetPath,$catalogPath,$inputPath)){if($f -and (Test-Path -LiteralPath $f)){Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue}}}
}
function Get-HmsNativeSmartModelRouterObject {
    $d=Invoke-HmsSmartModelRouter 'status'
    return @{ok=$true;version=$script:Version;smart_model_router=$d;enabled=[bool]$script:S.SmartModelRouterEnabled;mode=[string]$script:S.SmartModelRouterMode}
}
function Evaluate-HmsNativeSmartModelRouter {
    $input=Read-HmsSmartModelRouterBackendInput
    $d=Invoke-HmsSmartModelRouter -Mode 'evaluate' -ProjectDir ([string]$input.project_dir) -Role ([string]$input.role) -Manual $false
    return @{ok=$true;version=$script:Version;smart_model_router=$d;message='Smart Model Router đã đánh giá; chưa thay model/account của session đang chạy.'}
}
function Apply-HmsNativeSmartModelRouter {
    $input=Read-HmsSmartModelRouterBackendInput
    $d=Invoke-HmsSmartModelRouter -Mode 'apply' -ProjectDir ([string]$input.project_dir) -Role ([string]$input.role) -Manual $true
    return @{ok=$true;version=$script:Version;smart_model_router=$d;message='Đã áp dụng model/reasoning cho các instance đang dừng và đủ hard gate. Active sticky sessions không bị hot-switch; account affinity chỉ là tín hiệu bounded cho Closed-loop.'}
}
function Rollback-HmsNativeSmartModelRouter {
    $d=Invoke-HmsSmartModelRouter -Mode 'rollback'
    return @{ok=$true;version=$script:Version;smart_model_router=$d;message='Đã rollback model policy/config từ snapshot Smart Router; không xóa credential và không đổi stable endpoint.'}
}

function Get-HmsLiveCompatibilityContracts {
    $rows=[System.Collections.Generic.List[object]]::new()
    $targets=[System.Collections.Generic.List[object]]::new()
    if(PortOpen ([int]$script:S.ProxyPort)){$targets.Add([ordered]@{port=[int]$script:S.ProxyPort;key=[string]$script:S.LocalApiKey;source='GLOBAL_ROUTER'})}
    foreach($i in @((Get-CodexInstanceStore).instances)){
        if(Test-CodexInstanceRouterOwned $i){$targets.Add([ordered]@{port=[int]$i.port;key=[string](Get-HmsInstanceApiKey $i);source=('INSTANCE:'+[string]$i.id)})}
    }
    foreach($t in @($targets)){
        try{
            $r=Invoke-RestMethod -Uri ('http://127.0.0.1:'+([int]$t.port)+'/hms/compatibility') -Headers @{Authorization=('Bearer '+[string]$t.key)} -TimeoutSec 5
            $rows.Add([ordered]@{source=[string]$t.source;port=[int]$t.port;ok=$true;contract=$r})
        }catch{
            $rows.Add([ordered]@{source=[string]$t.source;port=[int]$t.port;ok=$false;error='Compatibility contract chưa được expose bởi runtime đang chạy hoặc runtime cũ.'})
        }
    }
    return @($rows)
}
function Invoke-HmsApiCompatibilityAudit {
    Ensure-Dir $script:ApiCompatibilityDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_ApiCompatibility.py'
    if(-not (Test-Path $tool)){throw 'Thiếu HMS_Codex_ApiCompatibility.py'}
    $tmp=Join-Path $env:TEMP ('hms-api-compat-'+[Guid]::NewGuid().ToString('N'))
    $out=Join-Path $tmp 'result.json'
    try{
        New-Item -ItemType Directory -Force -Path $tmp|Out-Null
        $args=@('--root',$PSScriptRoot,'--temp',(Join-Path $tmp 'work'),'--output',$out)
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        $data=$j.data
        Save-JsonAtomic $script:ApiCompatibilityLatestPath $data
        try{Add-Content -LiteralPath $script:ApiCompatibilityHistoryPath -Value (($data|ConvertTo-Json -Compress -Depth 12)) -Encoding UTF8}catch{}
        return $data
    }finally{if(Test-Path $tmp){Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue}}
}
function Get-HmsNativeApiCompatibilityObject {
    $audit=$null
    if(Test-Path $script:ApiCompatibilityLatestPath){try{$audit=Get-Content $script:ApiCompatibilityLatestPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{}}
    if(-not $audit){
        $bundled=Join-Path $PSScriptRoot 'API_COMPAT_VALIDATION_V25.38.json'
        if(Test-Path $bundled){try{$j=Get-Content $bundled -Raw -Encoding UTF8|ConvertFrom-Json;$audit=$j.data}catch{}}
    }
    return @{ok=$true;version=$script:Version;api_compatibility=$audit;live_contracts=@(Get-HmsLiveCompatibilityContracts);note='Synthetic compatibility is not a substitute for Windows Codex runtime verification.'}
}


# ============================================================
# ======================================================================
# v25.40 CODEX SECURITY HARDENING
# Protected secret refs + ACL isolation + reparse guard + integrity seals
# ======================================================================
function Get-HmsSha256File {
    param([string]$Path)
    if(-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)){return ''}
    return ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash).ToLowerInvariant()
}
function Test-HmsPathHasReparsePoint {
    param([string]$Path)
    if([string]::IsNullOrWhiteSpace($Path)){return $false}
    try{
        $full=[IO.Path]::GetFullPath($Path)
        $root=[IO.Path]::GetPathRoot($full)
        if([string]::IsNullOrWhiteSpace($root)){return $false}
        $cur=$root
        $rest=$full.Substring($root.Length).TrimStart([char[]]'\/')
        foreach($part in @($rest -split '[\\/]')){
            if([string]::IsNullOrWhiteSpace($part)){continue}
            $cur=Join-Path $cur $part
            if(Test-Path -LiteralPath $cur){
                $item=Get-Item -LiteralPath $cur -Force -ErrorAction Stop
                if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){return $true}
            }
        }
    }catch{return $true}
    return $false
}
function Test-HmsAclWeak {
    param([string]$Path)
    if(-not $Path -or -not (Test-Path -LiteralPath $Path)){return $false}
    try{
        $acl=Get-Acl -LiteralPath $Path
        foreach($r in @($acl.Access)){
            if($r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow){continue}
            $id=[string]$r.IdentityReference
            if($id -notmatch '(?i)(Everyone|BUILTIN\\Users|Authenticated Users|S-1-1-0|S-1-5-11)'){continue}
            $rights=[Security.AccessControl.FileSystemRights]$r.FileSystemRights
            $writeMask=[Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Modify -bor [Security.AccessControl.FileSystemRights]::FullControl -bor [Security.AccessControl.FileSystemRights]::CreateFiles -bor [Security.AccessControl.FileSystemRights]::Delete
            if(($rights -band $writeMask) -ne 0){return $true}
        }
        return $false
    }catch{return $true}
}
function Set-HmsCurrentUserOnlyAcl {
    param([string]$Path)
    if(-not $Path -or -not (Test-Path -LiteralPath $Path)){return $false}
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $item=Get-Item -LiteralPath $Path -Force
    if($item.PSIsContainer){
        $args=@($Path,'/inheritance:r','/grant:r',('*'+$sid+':(OI)(CI)F'),'*S-1-5-18:(OI)(CI)F','/T','/C','/Q')
    }else{
        $args=@($Path,'/inheritance:r','/grant:r',('*'+$sid+':F'),'*S-1-5-18:F','/C','/Q')
    }
    $p=Start-Process -FilePath 'icacls.exe' -ArgumentList $args -NoNewWindow -Wait -PassThru
    if($p.ExitCode -ne 0){throw ('SECURITY_ACL_HARDEN_FAILED: '+$Path+' exit='+$p.ExitCode)}
    return -not (Test-HmsAclWeak $Path)
}
function Get-HmsSecuritySensitiveFiles {
    $out=[System.Collections.Generic.List[string]]::new()
    foreach($p in @($script:SettingsPath,$script:StatePath,$script:CodexInstancesPath,$script:CodexProjectAffinityPath,$script:ModelManagerPolicyPath,$script:SelfHealingLatestPath,$script:SecuritySealsPath,$script:CodexEnv,$script:ProxyCfg)){
        if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){$out.Add([string]$p)}
    }
    try{
        foreach($i in @((Get-CodexInstanceStore).instances)){
            foreach($p in @((Join-Path ([string]$i.routerDir) 'config.yaml'),(Get-CodexInstancePoolManifestPath $i))){if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){$out.Add([string]$p)}}
        }
    }catch{}
    return @($out|Select-Object -Unique)
}
function Get-HmsUnsafeDiagnosticArtifactCount {
    $hits=0
    $roots=@($script:SecurityEvidenceDir,$script:SelfHealingEvidenceDir)
    foreach($root in $roots){
        if(-not $root -or -not (Test-Path -LiteralPath $root -PathType Container)){continue}
        foreach($f in @(Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue)){
            if($f.Name.EndsWith('.dpapi',[StringComparison]::OrdinalIgnoreCase)){continue}
            if($f.Length -gt 5242880){continue}
            try{
                $t=[IO.File]::ReadAllText($f.FullName)
                $unsafe=$false
                if($t -match '(?i)\bBearer\s+(?!<redacted)[A-Za-z0-9._~+\-/=]{12,}'){$unsafe=$true}
                if($t -match '(?i)\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b'){$unsafe=$true}
                if($t -match '(?im)^\s*HMS_ROUTER_API_KEY\s*=\s*(?!<redacted)\S+'){$unsafe=$true}
                if($t -match '(?i)\b(?:sk[-_]|hms_(?!router_api_key\b)|hms-)[A-Za-z0-9._\-]{10,}\b'){$unsafe=$true}
                if($t -match '(?im)["'']?(?:access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|client[_-]?secret|password|cookie)["'']?\s*[:=]\s*["'']?(?!<redacted)[A-Za-z0-9._~+\-/=]{12,}'){$unsafe=$true}
                if($unsafe){$hits++}
            }catch{}
        }
    }
    return $hits
}
function Get-HmsSecurityInstancePaths {
    $out=[System.Collections.Generic.List[string]]::new()
    try{
        $store=Get-CodexInstanceStore
        foreach($i in @($store.instances)){
            foreach($p in @([string]$i.codexHome,[string]$i.appData,[string]$i.routerDir)){
                if($p -and (Test-Path -LiteralPath $p -PathType Container)){$out.Add($p)}
            }
        }
    }catch{}
    return @($out|Select-Object -Unique)
}
function Get-HmsSecuritySealTargets {
    # Only relatively stable authority/config files are sealed. High-churn runtime ledgers,
    # PID stores and router pool manifests are intentionally excluded to avoid false alarms.
    $out=[System.Collections.Generic.List[string]]::new()
    foreach($p in @($script:ModelManagerPolicyPath,$script:UpdatePublicKeyPath,$script:ReleaseManifestPath)){
        if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){$out.Add([string]$p)}
    }
    try{
        $store=Get-CodexInstanceStore
        foreach($i in @($store.instances)){
            foreach($p in @((Get-CodexInstanceBindingPath $i),(Join-Path ([string]$i.root) 'identity-v2536.json'),(Join-Path ([string]$i.codexHome) 'config.toml'))){
                if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){$out.Add([string]$p)}
            }
        }
    }catch{}
    return @($out|Select-Object -Unique)
}
function Get-HmsSecuritySealKeyBytes {
    param([bool]$Create=$false)
    $v=Get-HmsProtectedSecret $script:SecurityCredentialSealTarget
    if([string]::IsNullOrWhiteSpace([string]$v) -and $Create){
        $b=New-Object byte[] 32;$rng=[Security.Cryptography.RandomNumberGenerator]::Create();try{$rng.GetBytes($b)}finally{$rng.Dispose()}
        $v=[Convert]::ToBase64String($b);[Array]::Clear($b,0,$b.Length)
        $null=Set-HmsProtectedSecret $script:SecurityCredentialSealTarget $v
    }
    if([string]::IsNullOrWhiteSpace([string]$v)){return $null}
    try{return [Convert]::FromBase64String([string]$v)}catch{return $null}
}
function Get-HmsSecurityHmac {
    param([string]$Path,[byte[]]$Key)
    $sha=Get-HmsSha256File $Path
    if(-not $sha -or -not $Key){return ''}
    $payload=(Norm $Path)+"`n"+$sha
    $h=New-Object Security.Cryptography.HMACSHA256(,$Key)
    try{return ([BitConverter]::ToString($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($payload)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
}
function Get-HmsSecuritySealStatus {
    $key=Get-HmsSecuritySealKeyBytes $false
    $keyProtected=($null -ne $key)
    $sealObj=$null;if(Test-Path -LiteralPath $script:SecuritySealsPath){$sealObj=Load-JsonObjectSafe $script:SecuritySealsPath}
    $entries=@();if($sealObj -and $sealObj.PSObject.Properties['entries']){$entries=@($sealObj.entries)}
    $map=@{};foreach($e in $entries){$map[(Norm ([string]$e.path))]=$e}
    $missing=[System.Collections.Generic.List[string]]::new();$mismatch=[System.Collections.Generic.List[string]]::new();$verified=0
    foreach($p in @(Get-HmsSecuritySealTargets)){
        $k=Norm $p
        if(-not $map.ContainsKey($k)){$missing.Add([IO.Path]::GetFileName($p));continue}
        $e=$map[$k];$sha=Get-HmsSha256File $p
        if(-not $keyProtected -or ([string]$e.sha256).ToLowerInvariant() -ne $sha -or ([string]$e.hmac_sha256).ToLowerInvariant() -ne (Get-HmsSecurityHmac $p $key)){
            $mismatch.Add([IO.Path]::GetFileName($p))
        }else{$verified++}
    }
    if($key){[Array]::Clear($key,0,$key.Length)}
    return [ordered]@{key_protected=[bool]$keyProtected;tracked=@($entries).Count;verified=[int]$verified;missing=[int]$missing.Count;missing_names=@($missing);mismatches=@($mismatch)}
}
function Update-HmsSecuritySeals {
    param([bool]$TrustedMutation=$false,[string]$Reason='security-harden')
    if(-not [bool]$script:S.CodexSecurityIntegritySealsEnabled){return $null}
    Ensure-Dir $script:SecurityDir
    $key=Get-HmsSecuritySealKeyBytes $true;if(-not $key){throw 'SECURITY_SEAL_KEY_UNAVAILABLE'}
    $old=$null;if(Test-Path -LiteralPath $script:SecuritySealsPath){$old=Load-JsonObjectSafe $script:SecuritySealsPath}
    $map=@{};if($old -and $old.PSObject.Properties['entries']){foreach($e in @($old.entries)){$map[(Norm ([string]$e.path))]=$e}}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($p in @(Get-HmsSecuritySealTargets)){
        $k=Norm $p;$sha=Get-HmsSha256File $p;$h=Get-HmsSecurityHmac $p $key
        if($map.ContainsKey($k) -and -not $TrustedMutation){
            $e=$map[$k]
            # Never auto-accept a changed tracked file. Keep old seal so audit remains BLOCKED.
            if(([string]$e.sha256).ToLowerInvariant() -ne $sha){$rows.Add($e);continue}
        }
        $rows.Add([ordered]@{path=$p;sha256=$sha;hmac_sha256=$h;sealed_utc=[DateTime]::UtcNow.ToString('o')})
    }
    $obj=[ordered]@{version='25.40';generated_utc=[DateTime]::UtcNow.ToString('o');reason=$Reason;entries=@($rows);secret_key_stored='PROTECTED_CURRENT_USER';secret_value_excluded=$true}
    Save-JsonAtomic $script:SecuritySealsPath $obj
    if($key){[Array]::Clear($key,0,$key.Length)}
    return $obj
}
function Set-HmsSecuritySealTrustedPath {
    param([string]$Path,[string]$Reason='trusted-hms-write')
    if(-not [bool]$script:S.CodexSecurityIntegritySealsEnabled -or -not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)){return}
    try{
        Ensure-Dir $script:SecurityDir
        $key=Get-HmsSecuritySealKeyBytes $true;if(-not $key){return}
        $entries=[System.Collections.Generic.List[object]]::new();$targetKey=Norm $Path;$replaced=$false
        $old=$null;if(Test-Path -LiteralPath $script:SecuritySealsPath){$old=Load-JsonObjectSafe $script:SecuritySealsPath}
        if($old -and $old.PSObject.Properties['entries']){
            foreach($e in @($old.entries)){
                if((Norm ([string]$e.path)) -eq $targetKey){
                    $entries.Add([ordered]@{path=$Path;sha256=(Get-HmsSha256File $Path);hmac_sha256=(Get-HmsSecurityHmac $Path $key);sealed_utc=[DateTime]::UtcNow.ToString('o')});$replaced=$true
                }else{$entries.Add($e)}
            }
        }
        if(-not $replaced){$entries.Add([ordered]@{path=$Path;sha256=(Get-HmsSha256File $Path);hmac_sha256=(Get-HmsSecurityHmac $Path $key);sealed_utc=[DateTime]::UtcNow.ToString('o')})}
        $obj=[ordered]@{version='25.40';generated_utc=[DateTime]::UtcNow.ToString('o');reason=$Reason;entries=@($entries);secret_key_stored='PROTECTED_CURRENT_USER';secret_value_excluded=$true}
        Save-JsonAtomic $script:SecuritySealsPath $obj
        [Array]::Clear($key,0,$key.Length)
    }catch{}
}
function Invoke-HmsSecurityMigrateGlobalSecretCore {
    $key=[string]$script:S.LocalApiKey
    if([string]::IsNullOrWhiteSpace($key)){$key=New-LocalKey;$script:S.LocalApiKey=$key}
    $mode=Set-HmsProtectedSecret $script:SecurityCredentialGlobalTarget $key
    Save-Settings
    return ('Global Router key -> '+$mode+'; settings plaintext field cleared')
}
function Invoke-HmsSecurityMigrateInstanceSecrets {
    $store=Get-CodexInstanceStore;$changed=0
    foreach($i in @($store.instances)){
        $ref='';try{$ref=[string]$i.apiKeyRef}catch{}
        $plain='';try{$plain=[string]$i.apiKey}catch{}
        if([string]::IsNullOrWhiteSpace($ref)){$ref=Get-HmsSecurityCredentialTargetForInstance ([string]$i.id)}
        $existing=Get-HmsProtectedSecret $ref
        $needsStore=[string]::IsNullOrWhiteSpace([string]$existing)
        $needsMetadata=([string]::IsNullOrWhiteSpace([string]$i.apiKeyRef) -or -not [string]::IsNullOrWhiteSpace($plain))
        if($needsStore){
            if([string]::IsNullOrWhiteSpace($plain)){throw ('INSTANCE_SECRET_MISSING_NO_RECOVERY:'+([string]$i.id))}
            $null=Set-HmsProtectedSecret $ref $plain
        }
        if($needsStore -or $needsMetadata){
            $i|Add-Member -NotePropertyName apiKeyRef -NotePropertyValue $ref -Force
            $i|Add-Member -NotePropertyName apiKey -NotePropertyValue '' -Force
            $i|Add-Member -NotePropertyName secretStorage -NotePropertyValue 'PROTECTED_CURRENT_USER' -Force
            $changed++
        }
    }
    if($changed -gt 0){Save-CodexInstanceStore $store}
    return ('Protected instance Router keys migrated: '+$changed)
}
function Initialize-HmsSecuritySecretMigration {
    if(-not [bool]$script:S.CodexSecurityHardeningEnabled -or -not [bool]$script:S.CodexSecurityMigratePlainKeys){return}
    try{$null=Invoke-HmsSecurityMigrateInstanceSecrets}catch{try{Add-CodexRouteHistory 'SECURITY_MIGRATION_WARN' (Redact-LocalApiText $_.Exception.Message) ''}catch{}}
}
function Invoke-HmsSecurityHardenSensitiveAcl {
    $ok=0
    foreach($p in @(Get-HmsSecuritySensitiveFiles)){if(Set-HmsCurrentUserOnlyAcl $p){$ok++}}
    return ('Sensitive file ACL hardened: '+$ok)
}
function Invoke-HmsSecurityHardenInstanceAcl {
    $ok=0
    foreach($p in @(Get-HmsSecurityInstancePaths)){if(Set-HmsCurrentUserOnlyAcl $p){$ok++}}
    return ('Instance path ACL hardened: '+$ok)
}
function Get-HmsSecuritySnapshot {
    Ensure-Dir $script:SecurityDir
    $plainSettings=$false
    if(Test-Path -LiteralPath $script:SettingsPath){
        try{$raw=Load-JsonObjectSafe $script:SettingsPath;if($raw -and -not [string]::IsNullOrWhiteSpace([string]$raw.LocalApiKey)){$plainSettings=$true}}catch{}
    }
    $plainInst=0;$missingRefs=0;$reparse=[System.Collections.Generic.List[string]]::new();$instWeak=0
    try{
        $store=Get-CodexInstanceStore
        foreach($i in @($store.instances)){
            try{if(-not [string]::IsNullOrWhiteSpace([string]$i.apiKey)){$plainInst++}}catch{}
            $ref='';try{$ref=[string]$i.apiKeyRef}catch{}
            if([string]::IsNullOrWhiteSpace($ref) -or -not (Test-HmsProtectedSecretPresent $ref)){$missingRefs++}
            foreach($pair in @(@('root',[string]$i.root),@('codex_home',[string]$i.codexHome),@('app_data',[string]$i.appData),@('router_dir',[string]$i.routerDir))){
                if($pair[1] -and (Test-HmsPathHasReparsePoint $pair[1])){$reparse.Add(([string]$i.id+':'+$pair[0]))}
            }
            foreach($p in @([string]$i.codexHome,[string]$i.appData,[string]$i.routerDir)){if($p -and (Test-Path -LiteralPath $p) -and (Test-HmsAclWeak $p)){$instWeak++}}
        }
    }catch{}
    if(Test-HmsPathHasReparsePoint $script:SecurityDir){$reparse.Add('SECURITY_DIR')}
    $sensitive=@(Get-HmsSecuritySensitiveFiles);$weakSensitive=0;foreach($p in $sensitive){if(Test-HmsAclWeak $p){$weakSensitive++}}
    # Router/API protocol still requires key materialization in local runtime files. Canonical HMS storage remains protected;
    # these runtime copies are audited and restricted by ACL rather than falsely claimed to be absent.
    $runtimeMat=0;$runtimeMatWeak=0
    foreach($p in @($script:CodexEnv,$script:ProxyCfg)){
        if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){$runtimeMat++;if(Test-HmsAclWeak $p){$runtimeMatWeak++}}
    }
    try{foreach($i in @((Get-CodexInstanceStore).instances)){$rp=Join-Path ([string]$i.routerDir) 'config.yaml';if(Test-Path -LiteralPath $rp -PathType Leaf){$runtimeMat++;if(Test-HmsAclWeak $rp){$runtimeMatWeak++}}}}catch{}
    $unsafeArtifacts=Get-HmsUnsafeDiagnosticArtifactCount
    $seal=Get-HmsSecuritySealStatus
    return [ordered]@{
        version='25.40';generated_utc=[DateTime]::UtcNow.ToString('o')
        vault=[ordered]@{settings_plain_local_key_present=[bool]$plainSettings;instance_plain_keys_count=[int]$plainInst;global_secret_ref_present=[bool](Test-HmsProtectedSecretPresent $script:SecurityCredentialGlobalTarget);instance_secret_refs_missing=[int]$missingRefs;storage='WINDOWS_CREDENTIAL_MANAGER_WITH_DPAPI_FALLBACK';runtime_materializations_count=[int]$runtimeMat;secret_values_excluded=$true}
        acl=[ordered]@{security_dir_hardened=[bool](-not (Test-HmsAclWeak $script:SecurityDir));sensitive_files_total=[int]$sensitive.Count;sensitive_files_weak=[int]$weakSensitive;instance_paths_weak=[int]$instWeak;runtime_materializations_weak=[int]$runtimeMatWeak}
        reparse=[ordered]@{block_enabled=[bool]$script:S.CodexSecurityBlockReparsePoints;detected=@($reparse)}
        seals=$seal
        redaction=[ordered]@{strict=[bool]$script:S.CodexSecurityStrictRedaction;unsafe_artifacts=[int]$unsafeArtifacts;prompt_body_logging=$false;secret_values_excluded=$true;rollback_backups='DPAPI_CURRENT_USER_FOR_SENSITIVE_FILES'}
        update=[ordered]@{public_key_present=[bool](Test-Path -LiteralPath $script:UpdatePublicKeyPath -PathType Leaf);signed_channel_available=$true}
    }
}
function Invoke-HmsSecurityEngine {
    param([ValidateSet('audit','plan')][string]$Mode='audit',[object]$Snapshot=$null)
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_SecurityHardening.py';if(-not (Test-Path -LiteralPath $tool)){throw 'SECURITY_ENGINE_MISSING'}
    if(-not $Snapshot){$Snapshot=Get-HmsSecuritySnapshot}
    $tmp=Join-Path $env:TEMP ('hms-security-'+[Guid]::NewGuid().ToString('N')+'.json')
    try{
        Save-JsonAtomic $tmp $Snapshot
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments @('--mode',$Mode,'--snapshot',$tmp)
        if(-not $j.ok){throw ('SECURITY_ENGINE_FAILED: '+[string]$j.error)}
        return $j.data
    }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
}
function Invoke-HmsSecurityAction {
    param([string]$Action)
    switch($Action){
        'MIGRATE_GLOBAL_SECRET' {return Invoke-HmsSecurityMigrateGlobalSecretCore}
        'MIGRATE_INSTANCE_SECRETS' {return Invoke-HmsSecurityMigrateInstanceSecrets}
        'CREATE_SEAL_KEY' {$null=Get-HmsSecuritySealKeyBytes $true;return 'Protected integrity seal key created'}
        'HARDEN_SECURITY_ACL' {Ensure-Dir $script:SecurityDir;$null=Set-HmsCurrentUserOnlyAcl $script:SecurityDir;return 'Security directory ACL hardened'}
        'HARDEN_SENSITIVE_ACL' {return Invoke-HmsSecurityHardenSensitiveAcl}
        'HARDEN_INSTANCE_ACL' {return Invoke-HmsSecurityHardenInstanceAcl}
        'ENABLE_STRICT_REDACTION' {$script:S.CodexSecurityStrictRedaction=$true;Save-Settings;return 'Strict redaction enabled'}
        'CREATE_MISSING_SEALS' {$null=Update-HmsSecuritySeals -TrustedMutation $false -Reason 'security-hardening-missing-only';return 'Missing integrity seals created; existing mismatches were not accepted'}
        default {throw ('SECURITY_ACTION_UNSUPPORTED: '+$Action)}
    }
}
function Invoke-HmsSecurityHardening {
    param([ValidateSet('audit','harden','seal')][string]$Mode='audit')
    if(-not [bool]$script:S.CodexSecurityHardeningEnabled){throw 'SECURITY_HARDENING_DISABLED'}
    Ensure-Dir $script:SecurityDir;Ensure-Dir $script:SecurityEvidenceDir
    $stamp=(Get-Date -Format 'yyyyMMdd-HHmmss-fff');$ev=Join-Path $script:SecurityEvidenceDir $stamp;Ensure-Dir $ev
    $pre=Get-HmsSecuritySnapshot;Save-JsonAtomic (Join-Path $ev 'pre-state.json') $pre
    $plan=Invoke-HmsSecurityEngine -Mode 'plan' -Snapshot $pre;Save-JsonAtomic (Join-Path $ev 'plan.json') $plan
    $actions=[System.Collections.Generic.List[object]]::new()
    if($Mode -eq 'harden'){
        foreach($a in @($plan.actions)){
            try{$msg=Invoke-HmsSecurityAction ([string]$a.action);$actions.Add([ordered]@{action=[string]$a.action;ok=$true;message=$msg})}
            catch{$actions.Add([ordered]@{action=[string]$a.action;ok=$false;error=(Redact-LocalApiText $_.Exception.Message)})}
        }
    }elseif($Mode -eq 'seal'){
        # Explicit operator trust action only; never reached by auto audit/hardening.
        $null=Update-HmsSecuritySeals -TrustedMutation $true -Reason 'operator-explicit-reseal'
        $actions.Add([ordered]@{action='OPERATOR_RESEAL_ALL';ok=$true;message='Integrity baseline explicitly resealed by operator action.'})
    }
    $post=Get-HmsSecuritySnapshot;$audit=Invoke-HmsSecurityEngine -Mode 'audit' -Snapshot $post
    $out=[ordered]@{version='25.40';mode=$Mode;generated_utc=[DateTime]::UtcNow.ToString('o');verdict=[string]$audit.verdict;summary=$audit.summary;issues=@($audit.issues);actions=@($actions);evidence_dir=$ev;invariants=$audit.invariants;runtime_windows_codex='DEFERRED_BY_OPERATOR'}
    Save-JsonAtomic (Join-Path $ev 'post-state.json') $post;Save-JsonAtomic (Join-Path $ev 'result.json') $out;Save-JsonAtomic $script:SecurityLatestPath $out
    try{Add-Content -LiteralPath $script:SecurityHistoryPath -Value (($out|ConvertTo-Json -Compress -Depth 8)) -Encoding UTF8}catch{}
    return $out
}
function Get-HmsNativeSecurityObject {
    $d=$null;if(Test-Path -LiteralPath $script:SecurityLatestPath){try{$d=Load-JsonObjectSafe $script:SecurityLatestPath}catch{}}
    if(-not $d){$d=Invoke-HmsSecurityHardening 'audit'}
    return @{ok=$true;version=$script:Version;security=$d;enabled=[bool]$script:S.CodexSecurityHardeningEnabled}
}

# v25.39 CODEX SELF-HEALING
# ============================================================
function Test-HmsSelfHealingBindingMatch {
    param([object]$Instance)
    try{
        $p=Get-CodexInstanceBindingPath $Instance
        if(-not (Test-Path -LiteralPath $p)){return $false}
        $b=Load-JsonObjectSafe $p;if(-not $b){return $false}
        if(([string]$b.instance_id) -ne ([string]$Instance.id)){return $false}
        if(([string]$b.account_email).Trim().ToLowerInvariant() -ne ([string]$Instance.accountEmail).Trim().ToLowerInvariant()){return $false}
        if((Get-HmsPathKey ([string]$b.project_dir)) -ne (Get-HmsPathKey ([string]$Instance.projectDir))){return $false}
        if([int]$b.port -ne [int]$Instance.port){return $false}
        return $true
    }catch{return $false}
}
function Test-HmsSelfHealingModelPolicyDrift {
    param([object]$Instance)
    try{
        if(-not (Test-Path -LiteralPath $script:ModelManagerPolicyPath)){return $false}
        $p=Load-JsonObjectSafe $script:ModelManagerPolicyPath;if(-not $p){return $false}
        $row=@($p.projects|Where-Object {(Get-HmsPathKey ([string]$_.project_dir)) -eq (Get-HmsPathKey ([string]$Instance.projectDir))}|Select-Object -First 1)
        if($row.Count -eq 0){return $false}
        $expected=[string]$row[0].last_config_sha256
        if([string]::IsNullOrWhiteSpace($expected)){return $false}
        $cfg=Join-Path ([string]$Instance.codexHome) 'config.toml'
        if(-not (Test-Path -LiteralPath $cfg)){return $true}
        $actual=(Get-FileHash -LiteralPath $cfg -Algorithm SHA256).Hash.ToLowerInvariant()
        return ($actual -ne $expected.ToLowerInvariant())
    }catch{return $false}
}
function Get-HmsSelfHealingSnapshot {
    $globalListener=ListenerPid ([int]$script:S.ProxyPort)
    $globalOwned=($globalListener -gt 0 -and (IsOurProxy $globalListener))
    $stateExists=Test-Path -LiteralPath $script:StatePath
    $statePid=0;$stateStale=$false
    if($stateExists){
        try{$st=Load-JsonObjectSafe $script:StatePath;if($st){$statePid=[int]$st.pid;$stateStale=($statePid -le 0 -or -not (IsOurProxy $statePid))}}catch{$stateStale=$true}
    }
    $cfgText='';if(Test-Path -LiteralPath $script:CodexConfig){try{$cfgText=[IO.File]::ReadAllText($script:CodexConfig)}catch{}}
    $providerOk=($cfgText -match '(?m)^model_provider\s*=\s*"hms_api_router"\s*$')
    $endpoint=('http://127.0.0.1:'+([int]$script:S.ProxyPort)+'/v1')
    $endpointOk=($cfgText -match ('(?m)^base_url\s*=\s*"'+[regex]::Escape($endpoint)+'"\s*$'))
    $envOk=$false
    if(Test-Path -LiteralPath $script:CodexEnv){try{$e=[IO.File]::ReadAllText($script:CodexEnv);$envOk=$e.Contains('HMS_ROUTER_API_KEY='+[string]$script:S.LocalApiKey)}catch{}}
    $identity=$null;try{$identity=Invoke-CodexIdentityAudit -WriteFingerprint $false}catch{}
    $identityMap=@{};if($identity){foreach($x in @($identity.instances)){$identityMap[[string]$x.instance_id]=$x}}
    $rows=[System.Collections.Generic.List[object]]::new()
    foreach($i in @((Get-CodexInstanceStore).instances)){
        $listener=ListenerPid ([int]$i.port)
        $expectedExe=Join-Path ([string]$i.routerDir) 'cli-proxy-api.exe'
        $listenerOwned=$false
        if($listener -gt 0){$lp=ProcPath $listener;if($lp){$listenerOwned=((Norm $lp) -eq (Norm $expectedExe))}}
        $routerOwned=Test-CodexInstanceRouterOwned $i
        $clientOwned=Test-CodexInstanceClientOwned $i
        $clientRunning=$false
        if([int]$i.clientPid -gt 0){try{$null=Get-Process -Id ([int]$i.clientPid) -ErrorAction Stop;$clientRunning=$true}catch{}}
        $cpath=Join-Path ([string]$i.codexHome) 'config.toml';$ct='';if(Test-Path -LiteralPath $cpath){try{$ct=[IO.File]::ReadAllText($cpath)}catch{}}
        $instEndpoint='http://127.0.0.1:'+([int]$i.port)+'/v1'
        $providerMatch=($ct -match '(?m)^model_provider\s*=\s*"hms_instance_router"\s*$')
        $endpointMatch=($ct -match ('(?m)^base_url\s*=\s*"'+[regex]::Escape($instEndpoint)+'"\s*$'))
        $bindingOk=Test-HmsSelfHealingBindingMatch $i
        $ia=$identityMap[[string]$i.id]
        $identityOk=if($ia){[bool]$ia.ok}else{$false}
        $desired=@(Get-CodexInstanceDesiredRouterAccounts $i)
        $manifest=Load-JsonObjectSafe (Get-CodexInstancePoolManifestPath $i)
        $actual=@();if($manifest){$actual=@($manifest.accounts|ForEach-Object{([string]$_.email).Trim().ToLowerInvariant()})}
        $wanted=@($desired|ForEach-Object{([string]$_).Trim().ToLowerInvariant()})
        $authPoolOk=($actual.Count -eq $wanted.Count)
        if($authPoolOk){for($n=0;$n -lt $wanted.Count;$n++){if($actual[$n] -ne $wanted[$n]){$authPoolOk=$false;break}}}
        $rows.Add([ordered]@{
            id=[string]$i.id;name=[string]$i.name;account_email=[string]$i.accountEmail;project_dir=[string]$i.projectDir;port=[int]$i.port
            root_exists=(Test-Path -LiteralPath ([string]$i.root) -PathType Container);project_exists=(Test-Path -LiteralPath ([string]$i.projectDir) -PathType Container)
            identity_ok=$identityOk;binding_ok=$bindingOk;config_exists=(Test-Path -LiteralPath $cpath);config_provider_ok=$providerMatch;config_endpoint_ok=$endpointMatch
            router_config_exists=(Test-Path -LiteralPath (Join-Path ([string]$i.routerDir) 'config.yaml'));router_pid=[int]$i.routerPid;router_owned=[bool]$routerOwned
            listener_pid=[int]$listener;listener_owned=[bool]$listenerOwned;router_running=[bool]($listener -gt 0);port_conflict_foreign=[bool]($listener -gt 0 -and -not $listenerOwned)
            client_pid=[int]$i.clientPid;client_owned=[bool]$clientOwned;client_running=[bool]$clientRunning;auth_pool_ok=[bool]$authPoolOk;model_policy_drift=[bool](Test-HmsSelfHealingModelPolicyDrift $i)
        })
    }
    return [ordered]@{
        version='25.39';generated_utc=[DateTime]::UtcNow.ToString('o')
        global=[ordered]@{proxy_port=[int]$script:S.ProxyPort;expected_hms_mode=[bool]($globalOwned -or $stateExists);provider_ok=[bool]$providerOk;endpoint_ok=[bool]$endpointOk;client_key_match=[bool]$envOk;client_running=[bool](@(Get-CodexClientProcesses).Count -gt 0);listener_pid=[int]$globalListener;listener_owned=[bool]$globalOwned;port_conflict_foreign=[bool]($globalListener -gt 0 -and -not $globalOwned);managed_pid_stale=[bool]$stateStale}
        instances=@($rows);secret_fields_excluded=$true
    }
}
function Invoke-HmsSelfHealingEngine {
    param([ValidateSet('audit','plan')][string]$Mode='audit',[object]$Snapshot=$null)
    Ensure-Dir $script:SelfHealingDir
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_SelfHealing.py';if(-not (Test-Path -LiteralPath $tool)){throw 'SELF_HEALING_ENGINE_MISSING'}
    if(-not $Snapshot){$Snapshot=Get-HmsSelfHealingSnapshot}
    $tmp=Join-Path $env:TEMP ('hms-selfheal-'+[Guid]::NewGuid().ToString('N')+'.json')
    try{
        Save-JsonAtomic $tmp $Snapshot
        $args=@('--mode',$Mode,'--snapshot',$tmp,'--safe-only',$(if([bool]$script:S.CodexSelfHealingSafeRepairsOnly){'true'}else{'false'}))
        $j=Invoke-PythonJsonHelper -Python ([string]$script:S.CodexSessionDoctorPython) -Script $tool -Arguments $args
        return $j.data
    }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
}
function Protect-HmsSelfHealingRollbackFile {
    param([string]$Source,[string]$Destination)
    if(-not (Test-Path -LiteralPath $Source -PathType Leaf)){return ''}
    try{
        $raw=[IO.File]::ReadAllBytes($Source)
        $enc=[Security.Cryptography.ProtectedData]::Protect($raw,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
        [IO.File]::WriteAllBytes($Destination,$enc)
        try{$null=Set-HmsCurrentUserOnlyAcl $Destination}catch{}
        if($raw){[Array]::Clear($raw,0,$raw.Length)};if($enc){[Array]::Clear($enc,0,$enc.Length)}
        return $Destination
    }catch{throw ('SELF_HEAL_DPAPI_BACKUP_FAILED: '+$Source)}
}
function Restore-HmsSelfHealingEvidenceFile {
    param([string]$Backup,[string]$Destination)
    if([string]::IsNullOrWhiteSpace($Backup) -or -not (Test-Path -LiteralPath $Backup)){return}
    if($Backup.EndsWith('.dpapi',[StringComparison]::OrdinalIgnoreCase)){
        try{
            $enc=[IO.File]::ReadAllBytes($Backup)
            $raw=[Security.Cryptography.ProtectedData]::Unprotect($enc,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
            [IO.File]::WriteAllBytes($Destination,$raw)
            if($enc){[Array]::Clear($enc,0,$enc.Length)};if($raw){[Array]::Clear($raw,0,$raw.Length)}
            return
        }catch{throw ('SELF_HEAL_DPAPI_RESTORE_FAILED: '+$Destination)}
    }
    Copy-Item -LiteralPath $Backup -Destination $Destination -Force
}
function Copy-HmsSelfHealingEvidenceFile {
    param([string]$Path,[string]$EvidenceDir,[string]$Name,[switch]$Sensitive)
    if($Path -and (Test-Path -LiteralPath $Path -PathType Leaf)){
        $dest=Join-Path $EvidenceDir $Name
        if($Sensitive){
            $rollback=Protect-HmsSelfHealingRollbackFile $Path ($dest+'.rollback.dpapi')
            $text='';try{$text=[IO.File]::ReadAllText($Path)}catch{$text='<binary-or-unreadable; raw rollback protected with DPAPI>'}
            Write-Utf8 $dest (Redact-HmsSecurityText $text)
            return $rollback
        }
        Copy-Item -LiteralPath $Path -Destination $dest -Force;return $dest
    }
    return ''
}
function Repair-HmsInstanceConfigContract {
    param([object]$Instance,[string]$EvidenceDir)
    if(-not [bool]$script:S.CodexSelfHealingRepairInstanceConfig){throw 'SELF_HEAL_INSTANCE_CONFIG_DISABLED'}
    $cfg=Join-Path ([string]$Instance.codexHome) 'config.toml';Ensure-Dir ([string]$Instance.codexHome)
    $backup=Copy-HmsSelfHealingEvidenceFile $cfg $EvidenceDir ('instance-'+[string]$Instance.id+'-config-before.toml')
    $text='';if(Test-Path -LiteralPath $cfg){$text=[IO.File]::ReadAllText($cfg)}
    $text=Remove-ProviderBlock $text 'hms_instance_router'
    $text=Set-RootTomlKey $text 'model_provider' '"hms_instance_router"'
    $block=@"

[model_providers.hms_instance_router]
name = "API"
base_url = "http://127.0.0.1:$([int]$Instance.port)/v1"
env_key = "HMS_ROUTER_API_KEY"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 4
stream_max_retries = 5
stream_idle_timeout_ms = 300000
"@
    $updated=$text.TrimEnd()+"`r`n"+$block.TrimStart()+"`r`n"
    $tmp=$cfg+'.selfheal-'+[Guid]::NewGuid().ToString('N')
    try{
        Write-Utf8 $tmp $updated;Move-Item -LiteralPath $tmp -Destination $cfg -Force
        $final=[IO.File]::ReadAllText($cfg);$ep='http://127.0.0.1:'+([int]$Instance.port)+'/v1'
        if($final -notmatch '(?m)^model_provider\s*=\s*"hms_instance_router"\s*$' -or $final -notmatch ('(?m)^base_url\s*=\s*"'+[regex]::Escape($ep)+'"\s*$')){throw 'SELF_HEAL_INSTANCE_CONFIG_READBACK_FAILED'}
        Set-HmsSecuritySealTrustedPath $cfg 'self-heal-instance-config'
    }catch{
        if($backup){Copy-Item -LiteralPath $backup -Destination $cfg -Force}
        throw
    }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
}
function Invoke-HmsSelfHealingAction {
    param([object]$Action,[string]$EvidenceDir)
    $scope=[string]$Action.scope;$name=[string]$Action.action
    if($scope -eq 'GLOBAL'){
        if($name -eq 'REPAIR_GLOBAL_CONFIG'){
            if(-not [bool]$script:S.CodexSelfHealingRepairGlobalConfig){throw 'SELF_HEAL_GLOBAL_CONFIG_DISABLED'}
            $b1=Copy-HmsSelfHealingEvidenceFile $script:CodexConfig $EvidenceDir 'global-config-before.toml'
            $b2=Copy-HmsSelfHealingEvidenceFile $script:CodexEnv $EvidenceDir 'global-env-before.txt' -Sensitive
            try{
                Configure-CodexApiMode
                $g=(Get-HmsSelfHealingSnapshot).global
                if(-not $g.provider_ok -or -not $g.endpoint_ok -or -not $g.client_key_match){throw 'SELF_HEAL_GLOBAL_CONFIG_READBACK_FAILED'}
            }catch{
                if($b1){Copy-Item -LiteralPath $b1 -Destination $script:CodexConfig -Force}
                if($b2){Restore-HmsSelfHealingEvidenceFile $b2 $script:CodexEnv}
                throw
            }
            return 'Global provider/endpoint/client key config repaired with readback.'
        }
        if($name -eq 'ARCHIVE_GLOBAL_STALE_STATE'){
            if(Test-Path -LiteralPath $script:StatePath){Move-Item -LiteralPath $script:StatePath -Destination (Join-Path $EvidenceDir 'global-stale-state.json') -Force}
            return 'Stale global state archived; no process was killed.'
        }
        throw 'SELF_HEAL_ACTION_UNSUPPORTED: '+$name
    }
    if($scope -notmatch '^INSTANCE:(.+)$'){throw 'SELF_HEAL_SCOPE_INVALID'}
    $id=$matches[1];$i=Get-CodexInstanceById $id
    $storeBackup=Copy-HmsSelfHealingEvidenceFile $script:CodexInstancesPath $EvidenceDir ('instances-before-'+$id+'.json')
    try{
        switch($name){
            'ADOPT_ROUTER_PID' {
                $routerListenerPid=ListenerPid ([int]$i.port);if($routerListenerPid -le 0){throw 'SELF_HEAL_ROUTER_NOT_LISTENING'}
                $expected=Join-Path ([string]$i.routerDir) 'cli-proxy-api.exe';$path=ProcPath $routerListenerPid
                if(-not $path -or (Norm $path) -ne (Norm $expected)){throw 'SELF_HEAL_ROUTER_OWNERSHIP_NOT_PROVEN'}
                Update-CodexInstanceState $id $routerListenerPid -1 $false
                return 'Owned router PID adopted.'
            }
            'CLEAR_STALE_ROUTER_PID' {
                if((ListenerPid ([int]$i.port)) -gt 0){throw 'SELF_HEAL_ROUTER_PORT_NOT_EMPTY'}
                if(Test-CodexInstanceRouterOwned $i){throw 'SELF_HEAL_ROUTER_STILL_OWNED'}
                Update-CodexInstanceState $id 0 -1 $false;return 'Stale router PID metadata cleared; no process was killed.'
            }
            'CLEAR_STALE_CLIENT_PID' {
                if(Test-CodexInstanceClientOwned $i){throw 'SELF_HEAL_CLIENT_STILL_OWNED'}
                Update-CodexInstanceState $id -1 0 $false;return 'Stale client PID metadata cleared; no process was killed.'
            }
            'RESYNC_BINDING' {
                if(-not [bool]$script:S.CodexSelfHealingRepairBinding){throw 'SELF_HEAL_BINDING_DISABLED'}
                $bp=Get-CodexInstanceBindingPath $i;$null=Copy-HmsSelfHealingEvidenceFile $bp $EvidenceDir ('binding-before-'+$id+'.json')
                $null=Write-CodexInstanceBinding $i
                if(-not (Test-HmsSelfHealingBindingMatch $i)){throw 'SELF_HEAL_BINDING_READBACK_FAILED'}
                return 'Project/account/instance binding resynced.'
            }
            'REPAIR_INSTANCE_CONFIG' {
                Repair-HmsInstanceConfigContract $i $EvidenceDir;return 'Isolated Codex config contract repaired.'
            }
            'REWRITE_ROUTER_CONFIG' {
                $rp=Join-Path ([string]$i.routerDir) 'config.yaml';$rb=Copy-HmsSelfHealingEvidenceFile $rp $EvidenceDir ('router-config-before-'+$id+'.yaml') -Sensitive
                try{$desired=@(Get-CodexInstanceDesiredRouterAccounts $i);Write-CodexInstanceRouterConfigV2530 $i ([Math]::Max(1,$desired.Count));if(-not (Test-Path -LiteralPath $rp)){throw 'SELF_HEAL_ROUTER_CONFIG_READBACK_FAILED'}}catch{if($rb){Restore-HmsSelfHealingEvidenceFile $rb $rp};throw}
                return 'Router config regenerated; running router is not force-restarted.'
            }
            'RESYNC_CREDENTIAL_POOL' {
                if(-not [bool]$script:S.CodexSelfHealingRepairCredentialPool){throw 'SELF_HEAL_CREDENTIAL_REPAIR_DISABLED'}
                if(-not (Test-CodexInstanceFullyStopped $i)){throw 'SELF_HEAL_CREDENTIAL_REQUIRES_STOPPED_INSTANCE'}
                $authDir=Join-Path ([string]$i.routerDir) 'auth';$backupDir=Join-Path $EvidenceDir ('auth-before-'+$id+'-protected');Ensure-Dir $backupDir;try{$null=Set-HmsCurrentUserOnlyAcl $backupDir}catch{}
                $authMeta=[System.Collections.Generic.List[object]]::new()
                foreach($f in @(Get-ChildItem -LiteralPath $authDir -File -ErrorAction SilentlyContinue)){
                    $null=Protect-HmsSelfHealingRollbackFile $f.FullName (Join-Path $backupDir ($f.Name+'.dpapi'))
                    $authMeta.Add([ordered]@{name=$f.Name;size=[int64]$f.Length;sha256=(Get-HmsSha256File $f.FullName)})
                }
                Save-JsonAtomic (Join-Path $EvidenceDir ('auth-before-'+$id+'-metadata.json')) ([ordered]@{files=@($authMeta);secret_values_excluded=$true;rollback_storage='DPAPI_CURRENT_USER'})
                $mp=Get-CodexInstancePoolManifestPath $i;$null=Copy-HmsSelfHealingEvidenceFile $mp $EvidenceDir ('pool-manifest-before-'+$id+'.json')
                try{$null=Sync-CodexInstanceRouterCredentialPool $i}catch{
                    $failed=Join-Path ([string]$i.routerDir) ('auth-failed-v2540-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'));Ensure-Dir $failed;try{$null=Set-HmsCurrentUserOnlyAcl $failed}catch{}
                    $failedMeta=[System.Collections.Generic.List[object]]::new()
                    foreach($f in @(Get-ChildItem -LiteralPath $authDir -File -ErrorAction SilentlyContinue)){$failedMeta.Add([ordered]@{name=$f.Name;size=[int64]$f.Length;sha256=(Get-HmsSha256File $f.FullName)});Move-Item -LiteralPath $f.FullName -Destination (Join-Path $failed $f.Name) -Force}
                    foreach($bf in @(Get-ChildItem -LiteralPath $backupDir -Filter '*.dpapi' -File -ErrorAction SilentlyContinue)){
                        $name=$bf.Name.Substring(0,$bf.Name.Length-6);Restore-HmsSelfHealingEvidenceFile $bf.FullName (Join-Path $authDir $name)
                    }
                    Save-JsonAtomic (Join-Path $EvidenceDir ('auth-failed-'+$id+'-metadata.json')) ([ordered]@{files=@($failedMeta);raw_failed_credentials_archived_under_instance_acl=$true;secret_values_excluded=$true})
                    throw
                }
                return 'Credential pool resynced while instance was fully stopped.'
            }
            'REAPPLY_MODEL_POLICY' {
                if(-not [bool]$script:S.CodexSelfHealingRepairModelPolicy){throw 'SELF_HEAL_MODEL_POLICY_DISABLED'}
                if(Test-CodexInstanceClientOwned $i){throw 'SELF_HEAL_MODEL_POLICY_REQUIRES_STOPPED_CLIENT'}
                $null=Invoke-HmsModelManager -Mode 'apply' -ProjectDir ([string]$i.projectDir)
                return 'Model/reasoning policy reapplied to isolated config.'
            }
            default {throw 'SELF_HEAL_ACTION_UNSUPPORTED: '+$name}
        }
    }catch{
        if($storeBackup){Copy-Item -LiteralPath $storeBackup -Destination $script:CodexInstancesPath -Force}
        throw
    }
}
function Invoke-HmsSelfHealing {
    param([ValidateSet('audit','repair')][string]$Mode='audit')
    if(-not [bool]$script:S.CodexSelfHealingEnabled){throw 'SELF_HEALING_DISABLED'}
    Ensure-Dir $script:SelfHealingDir;Ensure-Dir $script:SelfHealingEvidenceDir
    $stamp=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    $ev=Join-Path $script:SelfHealingEvidenceDir $stamp;Ensure-Dir $ev
    $pre=Get-HmsSelfHealingSnapshot;Save-JsonAtomic (Join-Path $ev 'pre-state.json') $pre
    $plan=Invoke-HmsSelfHealingEngine -Mode 'plan' -Snapshot $pre;Save-JsonAtomic (Join-Path $ev 'plan.json') $plan
    $results=[System.Collections.Generic.List[object]]::new()
    if($Mode -eq 'repair'){
        foreach($a in @($plan.actions)){
            try{$msg=Invoke-HmsSelfHealingAction $a $ev;$results.Add([ordered]@{scope=[string]$a.scope;action=[string]$a.action;ok=$true;message=$msg})}
            catch{$results.Add([ordered]@{scope=[string]$a.scope;action=[string]$a.action;ok=$false;error=(Redact-LocalApiText ([string]$_.Exception.Message))})}
        }
    }
    $post=Get-HmsSelfHealingSnapshot;$audit=Invoke-HmsSelfHealingEngine -Mode 'audit' -Snapshot $post;Save-JsonAtomic (Join-Path $ev 'post-state.json') $post
    $out=[ordered]@{version='25.39';mode=$Mode;generated_utc=[DateTime]::UtcNow.ToString('o');verdict=[string]$audit.verdict;summary=$audit.summary;issues=@($audit.issues);actions=@($results);planned_actions=@($plan.actions);evidence_dir=$ev;invariants=$audit.invariants;runtime_windows_codex='DEFERRED_BY_OPERATOR'}
    Save-JsonAtomic (Join-Path $ev 'result.json') $out;Save-JsonAtomic $script:SelfHealingLatestPath $out
    try{Add-Content -LiteralPath $script:SelfHealingHistoryPath -Value (([ordered]@{time=$out.generated_utc;mode=$Mode;verdict=$out.verdict;issues=[int]$out.summary.issues;actions=@($results).Count;evidence=$ev}|ConvertTo-Json -Compress -Depth 6)) -Encoding UTF8}catch{}
    return $out
}
function Get-HmsNativeSelfHealingObject {
    $d=$null
    if(Test-Path -LiteralPath $script:SelfHealingLatestPath){try{$d=Load-JsonObjectSafe $script:SelfHealingLatestPath}catch{}}
    if(-not $d){$d=Invoke-HmsSelfHealing 'audit'}
    return @{ok=$true;version=$script:Version;self_healing=$d;enabled=[bool]$script:S.CodexSelfHealingEnabled}
}

function Get-HmsBackendSettingsObject {
    $keys=@(
        "ProxyDir","ProxyPort",
        "RestartCodexOnSwitch","ForceCloseIfNeeded","OpenCodexOnEnable",
        "CodexRoutingProfile","CodexSessionAffinityTtl",
        "CodexWatchdogEnabled","CodexWatchdogIntervalSec","CodexAutoRecoverRouter",
        "CodexOptimizeMultiAgentV2","CodexSaveCooldownStatus",
        "CodexRequestRetry","CodexMaxRetryInterval",
        "CodexQuotaRefreshMinutes","CodexAutoQuotaRefresh","CodexAutoQuotaRefreshMinutes",
        "CodexTelemetryEnabled","CodexTelemetryIntervalSec","CodexConfigDoctorEnabled",
        "CodexAutoSanitizeBeforeLaunch",
        "ProxyAffinityEnabled","ProxyAffinityMode","ProxyAccountsPerProxy",
        "ProxyHealthRequiredBeforeStart","ProxyDirectFallbackAllowed",
        "ProxyPublicIpProbeEnabled","ProxyEgressProbeEnabled","ProxyEgressRequireStableIp",
        "PolicyKernelEnabled","PolicyKernelMode",
        "CodexOpsEnabled","CodexHaEnabled",
        "UsageLedgerEnabled","UsageLedgerSyncSec","UsageLedgerMaxTraceLines","AdaptivePoolAdvisoryEnabled",
        "AdaptiveRouterEnabled","AdaptiveRouterMode","AdaptiveRouterIntervalSec","AdaptiveRouterMinSamples","AdaptiveRouterMinScoreDelta",
        "AdaptiveRouterHoldMinutes","AdaptiveRouterCooldownSec","AdaptiveRouterQuotaFloor","AdaptiveRouterEmergencyQuota",
        "AdaptiveRouterPreferredWeight","AdaptiveRouterSecondaryWeight","AdaptiveRouterReserveWeight",
        "ClosedLoopRouterEnabled","ClosedLoopRouterMode","ClosedLoopRouterIntervalSec","ClosedLoopRouterMinSamples","ClosedLoopRouterMinScoreDelta",
        "ClosedLoopRouterHoldMinutes","ClosedLoopRouterCooldownSec","ClosedLoopRouterQuotaFloor","ClosedLoopRouterEmergencyQuota",
        "ClosedLoopRouterPreferredWeight","ClosedLoopRouterSecondaryWeight","ClosedLoopRouterTailWeight",
        "CircuitBreakerEnabled","CircuitBreakerMode","CircuitBreakerIntervalSec","CircuitBreakerConsecutiveFailures",
        "CircuitBreakerRateLimitThreshold","CircuitBreakerAuthThreshold","CircuitBreakerServerThreshold","CircuitBreakerTimeoutThreshold",
        "CircuitBreakerNetworkThreshold","CircuitBreakerBaseOpenSec","CircuitBreakerRateLimitOpenSec","CircuitBreakerAuthOpenSec",
        "CircuitBreakerMaxOpenSec","CircuitBreakerHalfOpenSuccesses","CircuitBreakerMaxBackoffExponent","CircuitBreakerHalfOpenProbePriority",
        "AccountAnalyticsEnabled","AccountAnalyticsIntervalSec","AccountAnalyticsRetentionDays","AccountAnalyticsMinSamples",
        "UpdateChannelEnabled","UpdateFeedUrl","UpdateChannelName","UpdateAutoCheckHours","UpdateAutoStage",
        "SoakEnabled","PerformanceEnabled",
        "ApiParityAutoAudit",
        "CodexInstanceBasePort","CodexInstanceDefaultLaunchMode","CodexFleetMaxInstancesPerAccount",
        "CodexInstanceEnforceIsolation","CodexInstanceRequireUniqueProject","CodexInstanceRequireDedicatedAccount",
        "CodexInstanceProjectRequired","CodexInstanceSyncCredentialOnStart","CodexInstanceRouterWatchdog",
        "CodexIdentityIsolationEnabled","CodexIdentityAuditBeforeLaunch","CodexIdentityFingerprintStrict","CodexIdentityRequirePathsUnderRoot",
        "ModelManagerEnabled","ModelManagerAutoDiscover","ModelManagerRequireLiveModel","ModelManagerApplyBeforeLaunch","ModelManagerDefaultReasoning","ModelManagerDefaultProfile",
        "SmartModelRouterEnabled","SmartModelRouterMode","SmartModelRouterIntervalSec","SmartModelRouterApplyBeforeLaunch","SmartModelRouterRequireLiveModel","SmartModelRouterProtectRunningSessions",
        "SmartModelRouterMinModelSamples","SmartModelRouterMinScoreDelta","SmartModelRouterMaxAccountAdjustment","SmartModelRouterCoderProfile","SmartModelRouterReviewerProfile","SmartModelRouterTesterProfile","SmartModelRouterSoloProfile",
        "CodexSelfHealingEnabled","CodexSelfHealingAutoAudit","CodexSelfHealingAutoRepairSafe","CodexSelfHealingIntervalSec","CodexSelfHealingSafeRepairsOnly",
        "CodexSelfHealingRepairGlobalConfig","CodexSelfHealingRepairInstanceConfig","CodexSelfHealingRepairBinding","CodexSelfHealingRepairCredentialPool","CodexSelfHealingRepairModelPolicy",
        "CodexSecurityHardeningEnabled","CodexSecurityCredentialManagerEnabled","CodexSecurityDpapiFallbackEnabled","CodexSecurityAclHardeningEnabled",
        "CodexSecurityIntegritySealsEnabled","CodexSecurityBlockReparsePoints","CodexSecurityStrictRedaction","CodexSecurityAutoAudit",
        "CodexSecurityIntervalSec","CodexSecurityMigratePlainKeys","CodexSecurityHardenInstancePaths",
        "CodexProjectAffinityEnabled","CodexProjectAutoRegisterInstances","CodexProjectBlockUnhealthyPrimary",
        "CodexProjectFallbackMax","CodexProjectStickyMinutes","CodexProjectFocusIfRunning",
        "CodexSeamlessRouterEnabled","CodexSeamlessLivePoolSync","CodexSeamlessMaxFallback","CodexSeamlessMaxRetryCredentials","CodexSeamlessSessionAffinity","CodexSeamlessSessionTtlHours","CodexSeamlessArchiveStaleCredentials","CodexSeamlessRequireManifest",
        "CodexCockpitParityBaseline","CodexInstancePortAutoRecover","CodexInstancePortAutoRecoverMaxScan","CodexBehaviorBackupKeepPerSourceInstance",
        "CodexUsagePreferOfficialAccountId","CodexPreserveWebSocketPreference","CodexOfficialAuthExportEnabled","CodexModelContextMetadataEnabled"
    )
    $settings=@{}
    foreach($key in $keys){$settings[$key]=$script:S[$key]}
    return @{
        ok=$true
        version=$script:Version
        settings=$settings
        safety=@{
            RestoreOnDisable=$true
            CodexMinimizeToTray=$false
        }
    }
}

function Convert-HmsSettingBool([object]$Value,[string]$Key){
    if($Value -is [bool]){return [bool]$Value}
    $text=([string]$Value).Trim().ToLowerInvariant()
    if($text -in @("true","1","yes","on")){return $true}
    if($text -in @("false","0","no","off")){return $false}
    throw "SETTINGS_INVALID_BOOL: $Key"
}

function Convert-HmsSettingInt([object]$Value,[string]$Key,[int]$Min,[int]$Max){
    $n=0
    if(-not [int]::TryParse(([string]$Value),[ref]$n)){throw "SETTINGS_INVALID_INT: $Key"}
    if($n -lt $Min -or $n -gt $Max){throw "SETTINGS_RANGE: $Key phải nằm trong $Min..$Max"}
    return $n
}

function Apply-HmsBackendSettings {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){
        throw "SETTINGS_INPUT_MISSING"
    }
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}
    catch{throw "SETTINGS_INPUT_JSON_INVALID"}

    $changed=[System.Collections.Generic.List[string]]::new()
    $restart=[System.Collections.Generic.List[string]]::new()
    $allowed=@(
        "ProxyDir","ProxyPort",
        "RestartCodexOnSwitch","ForceCloseIfNeeded","OpenCodexOnEnable",
        "CodexRoutingProfile","CodexSessionAffinityTtl",
        "CodexWatchdogEnabled","CodexWatchdogIntervalSec","CodexAutoRecoverRouter",
        "CodexOptimizeMultiAgentV2","CodexSaveCooldownStatus",
        "CodexRequestRetry","CodexMaxRetryInterval",
        "CodexQuotaRefreshMinutes","CodexAutoQuotaRefresh","CodexAutoQuotaRefreshMinutes",
        "CodexTelemetryEnabled","CodexTelemetryIntervalSec","CodexConfigDoctorEnabled",
        "CodexAutoSanitizeBeforeLaunch",
        "ProxyAffinityEnabled","ProxyAffinityMode","ProxyAccountsPerProxy",
        "ProxyHealthRequiredBeforeStart","ProxyDirectFallbackAllowed",
        "ProxyPublicIpProbeEnabled","ProxyEgressProbeEnabled","ProxyEgressRequireStableIp",
        "PolicyKernelEnabled","PolicyKernelMode",
        "CodexOpsEnabled","CodexHaEnabled",
        "UsageLedgerEnabled","UsageLedgerSyncSec","UsageLedgerMaxTraceLines","AdaptivePoolAdvisoryEnabled",
        "AdaptiveRouterEnabled","AdaptiveRouterMode","AdaptiveRouterIntervalSec","AdaptiveRouterMinSamples","AdaptiveRouterMinScoreDelta",
        "AdaptiveRouterHoldMinutes","AdaptiveRouterCooldownSec","AdaptiveRouterQuotaFloor","AdaptiveRouterEmergencyQuota",
        "AdaptiveRouterPreferredWeight","AdaptiveRouterSecondaryWeight","AdaptiveRouterReserveWeight",
        "ClosedLoopRouterEnabled","ClosedLoopRouterMode","ClosedLoopRouterIntervalSec","ClosedLoopRouterMinSamples","ClosedLoopRouterMinScoreDelta",
        "ClosedLoopRouterHoldMinutes","ClosedLoopRouterCooldownSec","ClosedLoopRouterQuotaFloor","ClosedLoopRouterEmergencyQuota",
        "ClosedLoopRouterPreferredWeight","ClosedLoopRouterSecondaryWeight","ClosedLoopRouterTailWeight",
        "CircuitBreakerEnabled","CircuitBreakerMode","CircuitBreakerIntervalSec","CircuitBreakerConsecutiveFailures",
        "CircuitBreakerRateLimitThreshold","CircuitBreakerAuthThreshold","CircuitBreakerServerThreshold","CircuitBreakerTimeoutThreshold",
        "CircuitBreakerNetworkThreshold","CircuitBreakerBaseOpenSec","CircuitBreakerRateLimitOpenSec","CircuitBreakerAuthOpenSec",
        "CircuitBreakerMaxOpenSec","CircuitBreakerHalfOpenSuccesses","CircuitBreakerMaxBackoffExponent","CircuitBreakerHalfOpenProbePriority",
        "AccountAnalyticsEnabled","AccountAnalyticsIntervalSec","AccountAnalyticsRetentionDays","AccountAnalyticsMinSamples",
        "UpdateChannelEnabled","UpdateFeedUrl","UpdateChannelName","UpdateAutoCheckHours","UpdateAutoStage",
        "SoakEnabled","PerformanceEnabled",
        "ApiParityAutoAudit",
        "CodexInstanceBasePort","CodexInstanceDefaultLaunchMode","CodexFleetMaxInstancesPerAccount",
        "CodexInstanceEnforceIsolation","CodexInstanceRequireUniqueProject","CodexInstanceRequireDedicatedAccount",
        "CodexInstanceProjectRequired","CodexInstanceSyncCredentialOnStart","CodexInstanceRouterWatchdog",
        "CodexIdentityIsolationEnabled","CodexIdentityAuditBeforeLaunch","CodexIdentityFingerprintStrict","CodexIdentityRequirePathsUnderRoot",
        "ModelManagerEnabled","ModelManagerAutoDiscover","ModelManagerRequireLiveModel","ModelManagerApplyBeforeLaunch","ModelManagerDefaultReasoning","ModelManagerDefaultProfile",
        "SmartModelRouterEnabled","SmartModelRouterMode","SmartModelRouterIntervalSec","SmartModelRouterApplyBeforeLaunch","SmartModelRouterRequireLiveModel","SmartModelRouterProtectRunningSessions",
        "SmartModelRouterMinModelSamples","SmartModelRouterMinScoreDelta","SmartModelRouterMaxAccountAdjustment","SmartModelRouterCoderProfile","SmartModelRouterReviewerProfile","SmartModelRouterTesterProfile","SmartModelRouterSoloProfile",
        "CodexSelfHealingEnabled","CodexSelfHealingAutoAudit","CodexSelfHealingAutoRepairSafe","CodexSelfHealingIntervalSec","CodexSelfHealingSafeRepairsOnly",
        "CodexSelfHealingRepairGlobalConfig","CodexSelfHealingRepairInstanceConfig","CodexSelfHealingRepairBinding","CodexSelfHealingRepairCredentialPool","CodexSelfHealingRepairModelPolicy",
        "CodexSecurityHardeningEnabled","CodexSecurityCredentialManagerEnabled","CodexSecurityDpapiFallbackEnabled","CodexSecurityAclHardeningEnabled",
        "CodexSecurityIntegritySealsEnabled","CodexSecurityBlockReparsePoints","CodexSecurityStrictRedaction","CodexSecurityAutoAudit",
        "CodexSecurityIntervalSec","CodexSecurityMigratePlainKeys","CodexSecurityHardenInstancePaths",
        "CodexProjectAffinityEnabled","CodexProjectAutoRegisterInstances","CodexProjectBlockUnhealthyPrimary",
        "CodexProjectFallbackMax","CodexProjectStickyMinutes","CodexProjectFocusIfRunning",
        "CodexSeamlessRouterEnabled","CodexSeamlessLivePoolSync","CodexSeamlessMaxFallback","CodexSeamlessMaxRetryCredentials","CodexSeamlessSessionAffinity","CodexSeamlessSessionTtlHours","CodexSeamlessArchiveStaleCredentials","CodexSeamlessRequireManifest",
        "CodexCockpitParityBaseline","CodexInstancePortAutoRecover","CodexInstancePortAutoRecoverMaxScan","CodexBehaviorBackupKeepPerSourceInstance",
        "CodexUsagePreferOfficialAccountId","CodexPreserveWebSocketPreference","CodexOfficialAuthExportEnabled","CodexModelContextMetadataEnabled"
    )

    foreach($prop in @($input.PSObject.Properties)){
        $key=[string]$prop.Name
        if($key -notin $allowed){throw "SETTINGS_KEY_NOT_ALLOWED: $key"}
        $value=$prop.Value

        switch($key){
            "ProxyDir" {
                $value=([string]$value).Trim()
                if([string]::IsNullOrWhiteSpace($value)){throw "SETTINGS_EMPTY: ProxyDir"}
                $restart.Add($key)
            }
            "ProxyPort" {$value=Convert-HmsSettingInt $value $key 1024 65535;$restart.Add($key)}
            "CodexRoutingProfile" {
                $value=([string]$value).Trim().ToLowerInvariant()
                if($value -notin @("stable","balanced","fill-first")){throw "SETTINGS_ENUM: $key"}
                $restart.Add($key)
            }
            "CodexSessionAffinityTtl" {
                $value=([string]$value).Trim().ToLowerInvariant()
                if($value -notin @("30m","1h","2h","4h","8h","24h")){throw "SETTINGS_ENUM: $key"}
                $restart.Add($key)
            }
            "CodexWatchdogIntervalSec" {$value=Convert-HmsSettingInt $value $key 5 300}
            "CodexRequestRetry" {$value=Convert-HmsSettingInt $value $key 0 10;$restart.Add($key)}
            "CodexMaxRetryInterval" {$value=Convert-HmsSettingInt $value $key 1 120;$restart.Add($key)}
            "CodexQuotaRefreshMinutes" {$value=Convert-HmsSettingInt $value $key 1 120}
            "CodexAutoQuotaRefreshMinutes" {$value=Convert-HmsSettingInt $value $key 1 240}
            "UsageLedgerSyncSec" {$value=Convert-HmsSettingInt $value $key 10 3600}
            "UsageLedgerMaxTraceLines" {$value=Convert-HmsSettingInt $value $key 1000 1000000}
            "AdaptiveRouterIntervalSec" {$value=Convert-HmsSettingInt $value $key 15 3600}
            "AdaptiveRouterMinSamples" {$value=Convert-HmsSettingInt $value $key 0 1000}
            "AdaptiveRouterMinScoreDelta" {$value=Convert-HmsSettingInt $value $key 0 100}
            "AdaptiveRouterHoldMinutes" {$value=Convert-HmsSettingInt $value $key 0 1440}
            "AdaptiveRouterCooldownSec" {$value=Convert-HmsSettingInt $value $key 0 7200}
            "AdaptiveRouterQuotaFloor" {$value=Convert-HmsSettingInt $value $key 0 100}
            "AdaptiveRouterEmergencyQuota" {$value=Convert-HmsSettingInt $value $key 0 100}
            "AdaptiveRouterPreferredWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "AdaptiveRouterSecondaryWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "AdaptiveRouterReserveWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "AccountAnalyticsIntervalSec" {$value=Convert-HmsSettingInt $value $key 30 3600}
            "AccountAnalyticsRetentionDays" {$value=Convert-HmsSettingInt $value $key 30 3650}
            "AccountAnalyticsMinSamples" {$value=Convert-HmsSettingInt $value $key 1 1000}
            "SmartModelRouterIntervalSec" {$value=Convert-HmsSettingInt $value $key 15 3600}
            "SmartModelRouterMinModelSamples" {$value=Convert-HmsSettingInt $value $key 0 1000}
            "SmartModelRouterMinScoreDelta" {$value=Convert-HmsSettingInt $value $key 0 100}
            "SmartModelRouterMaxAccountAdjustment" {$value=Convert-HmsSettingInt $value $key 0 8}
            "CodexSelfHealingIntervalSec" {$value=Convert-HmsSettingInt $value $key 15 3600}
            "CodexSecurityIntervalSec" {$value=Convert-HmsSettingInt $value $key 30 3600}
            "ClosedLoopRouterIntervalSec" {$value=Convert-HmsSettingInt $value $key 15 3600}
            "ClosedLoopRouterMinSamples" {$value=Convert-HmsSettingInt $value $key 0 1000}
            "ClosedLoopRouterMinScoreDelta" {$value=Convert-HmsSettingInt $value $key 0 100}
            "ClosedLoopRouterHoldMinutes" {$value=Convert-HmsSettingInt $value $key 0 1440}
            "ClosedLoopRouterCooldownSec" {$value=Convert-HmsSettingInt $value $key 0 7200}
            "ClosedLoopRouterQuotaFloor" {$value=Convert-HmsSettingInt $value $key 0 100}
            "ClosedLoopRouterEmergencyQuota" {$value=Convert-HmsSettingInt $value $key 0 100}
            "ClosedLoopRouterPreferredWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "ClosedLoopRouterSecondaryWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "ClosedLoopRouterTailWeight" {$value=Convert-HmsSettingInt $value $key 1 100}
            "CircuitBreakerIntervalSec" {$value=Convert-HmsSettingInt $value $key 10 3600}
            "CircuitBreakerConsecutiveFailures" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CircuitBreakerRateLimitThreshold" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CircuitBreakerAuthThreshold" {$value=Convert-HmsSettingInt $value $key 1 10}
            "CircuitBreakerServerThreshold" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CircuitBreakerTimeoutThreshold" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CircuitBreakerNetworkThreshold" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CircuitBreakerBaseOpenSec" {$value=Convert-HmsSettingInt $value $key 15 7200}
            "CircuitBreakerRateLimitOpenSec" {$value=Convert-HmsSettingInt $value $key 15 7200}
            "CircuitBreakerAuthOpenSec" {$value=Convert-HmsSettingInt $value $key 30 21600}
            "CircuitBreakerMaxOpenSec" {$value=Convert-HmsSettingInt $value $key 30 21600}
            "CircuitBreakerHalfOpenSuccesses" {$value=Convert-HmsSettingInt $value $key 1 10}
            "CircuitBreakerMaxBackoffExponent" {$value=Convert-HmsSettingInt $value $key 0 8}
            "CircuitBreakerHalfOpenProbePriority" {$value=Convert-HmsSettingInt $value $key 1 20}
            "UpdateAutoCheckHours" {$value=Convert-HmsSettingInt $value $key 1 168}
            "CodexTelemetryIntervalSec" {$value=Convert-HmsSettingInt $value $key 2 300}
            "CodexInstanceBasePort" {$value=Convert-HmsSettingInt $value $key 1024 65000}
            "CodexFleetMaxInstancesPerAccount" {$value=Convert-HmsSettingInt $value $key 1 20}
            "CodexProjectFallbackMax" {$value=Convert-HmsSettingInt $value $key 0 10}
            "CodexProjectStickyMinutes" {$value=Convert-HmsSettingInt $value $key 0 10080}
            "CodexSeamlessMaxFallback" {$value=Convert-HmsSettingInt $value $key 0 10}
            "CodexSeamlessMaxRetryCredentials" {$value=Convert-HmsSettingInt $value $key 0 10}
            "CodexSeamlessSessionTtlHours" {$value=Convert-HmsSettingInt $value $key 1 168}
            "CodexInstancePortAutoRecoverMaxScan" {$value=Convert-HmsSettingInt $value $key 1 512}
            "CodexBehaviorBackupKeepPerSourceInstance" {$value=Convert-HmsSettingInt $value $key 1 32}
            "CodexCockpitParityBaseline" {
                $value=([string]$value).Trim()
                if($value -ne "1.3.27"){throw "SETTINGS_ENUM: $key"}
            }
            "CodexInstanceDefaultLaunchMode" {
                $value=([string]$value).Trim().ToLowerInvariant()
                if($value -notin @("cli","desktop")){throw "SETTINGS_ENUM: $key"}
            }
            "ModelManagerDefaultReasoning" {
                $value=([string]$value).Trim().ToLowerInvariant()
                if($value -notin @("auto","none","low","medium","high","xhigh","max")){throw "SETTINGS_ENUM: $key"}
            }
            "ModelManagerDefaultProfile" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("BALANCED","FAST","DEEP","REVIEW","TEST")){throw "SETTINGS_ENUM: $key"}
            }
            "SmartModelRouterMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("OBSERVE","GUARDED_AUTO")){throw "SETTINGS_ENUM: $key"}
            }
            {$_ -in @("SmartModelRouterCoderProfile","SmartModelRouterReviewerProfile","SmartModelRouterTesterProfile","SmartModelRouterSoloProfile")} {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("BALANCED","FAST","DEEP","REVIEW","TEST")){throw "SETTINGS_ENUM: $key"}
            }
            "ProxyAffinityMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("STRICT","STICKY_FAILOVER","DIRECT_FALLBACK")){throw "SETTINGS_ENUM: $key"}
                $restart.Add($key)
            }
            "ProxyAccountsPerProxy" {$value=Convert-HmsSettingInt $value $key 1 20;$restart.Add($key)}
            "PolicyKernelMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("OBSERVE","SAFE_AUTO")){throw "SETTINGS_ENUM: $key"}
            }
            "AdaptiveRouterMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("OBSERVE","GUARDED_AUTO")){throw "SETTINGS_ENUM: $key"}
            }
            "ClosedLoopRouterMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("OBSERVE","GUARDED_AUTO")){throw "SETTINGS_ENUM: $key"}
            }
            "CircuitBreakerMode" {
                $value=([string]$value).Trim().ToUpperInvariant()
                if($value -notin @("OBSERVE","GUARDED_AUTO")){throw "SETTINGS_ENUM: $key"}
            }
            "UpdateFeedUrl" {
                $value=([string]$value).Trim()
                if($value -and -not $value.ToLowerInvariant().StartsWith("https://")){throw "UPDATE_FEED_REQUIRES_HTTPS"}
            }
            "UpdateChannelName" {
                $value=([string]$value).Trim().ToLowerInvariant()
                if($value -notin @("stable","beta")){throw "SETTINGS_ENUM: $key"}
            }
            default {
                $value=Convert-HmsSettingBool $value $key
                if($key -in @(
                    "RestartCodexOnSwitch","ForceCloseIfNeeded","OpenCodexOnEnable",
                    "CodexOptimizeMultiAgentV2","CodexSaveCooldownStatus",
                    "ProxyAffinityEnabled","ProxyHealthRequiredBeforeStart",
                    "ProxyDirectFallbackAllowed","ProxyPublicIpProbeEnabled",
                    "ProxyEgressProbeEnabled","ProxyEgressRequireStableIp"
                )){$restart.Add($key)}
            }
        }

        if([string]$script:S[$key] -ne [string]$value){
            $script:S[$key]=$value
            $changed.Add($key)
        }
    }

    # GUI-only safety invariants.
    $script:S.RestoreOnDisable=$true
    $script:S.CodexMinimizeToTray=$false
    Save-Settings
    Refresh-Paths

    return @{
        ok=$true
        version=$script:Version
        changed=@($changed.ToArray())
        restart_required=@($restart.ToArray()|Select-Object -Unique)
        settings=(Get-HmsBackendSettingsObject).settings
        message=if($restart.Count -gt 0){"Đã lưu. Một số thay đổi áp dụng khi BẬT HMS lại."}else{"Đã lưu cài đặt HMS."}
    }
}

function Select-HmsBackendSafePort {
    $current=[int]$script:S.ProxyPort
    $listener=ListenerPid $current
    if($listener -le 0 -or (IsOurProxy $listener)){return $current}
    foreach($candidate in 8318..8337){
        if((ListenerPid $candidate) -le 0){
            $script:S.ProxyPort=$candidate
            Save-Settings
            Refresh-Paths
            return $candidate
        }
    }
    throw "Không tìm được port HMS trống trong dải 8318-8337."
}

function Get-HmsNativeActivityObject {
    $snapshot=Load-JsonObjectSafe $script:CodexAttributionPath
    $attr=$null
    if($snapshot){try{$attr=$snapshot.latest_attribution}catch{}}
    $events=@(Get-CodexRouteEventsFromLogs -Max 20 | ForEach-Object {
        [PSCustomObject]@{
            type=[string]$_.Type
            account=[string]$_.Account
            message=(Redact-LocalApiText ([string]$_.Message))
        }
    })
    $updated=""
    try{
        if($snapshot -and $snapshot.scanned_utc){$updated=[string]$snapshot.scanned_utc}
        elseif(Test-Path $script:CodexAttributionPath){$updated=(Get-Item $script:CodexAttributionPath).LastWriteTimeUtc.ToString("o")}
    }catch{}
    return @{
        account=if($attr){[string]$attr.account}else{""}
        confidence=if($attr){[string]$attr.confidence}else{""}
        source=if($attr){[string]$attr.source}else{""}
        evidence=if($attr){Redact-LocalApiText ([string]$attr.evidence)}else{""}
        updated_utc=$updated
        scanned_lines=if($snapshot -and $null -ne $snapshot.scanned_lines){[int]$snapshot.scanned_lines}else{0}
        counts=if($snapshot){$snapshot.counts}else{$null}
        account_counts=if($snapshot){$snapshot.account_counts}else{$null}
        recent_events=$events
    }
}

function Get-HmsNativeMaintenanceState {
    $state=@{}
    $j=Load-JsonObjectSafe $script:NativeGuiMaintenanceStatePath
    if($j){foreach($p in @($j.PSObject.Properties)){$state[[string]$p.Name]=$p.Value}}
    return $state
}
function Test-HmsNativeMaintenanceDue {
    param([hashtable]$State,[string]$Key,[int]$Seconds)
    if($Seconds -lt 1){$Seconds=1}
    if(-not $State.ContainsKey($Key)){return $true}
    try{
        $last=[DateTime]::Parse([string]$State[$Key]).ToUniversalTime()
        return (([DateTime]::UtcNow-$last).TotalSeconds -ge $Seconds)
    }catch{return $true}
}
function Set-HmsNativeMaintenanceStamp {
    param([hashtable]$State,[string]$Key)
    $State[$Key]=[DateTime]::UtcNow.ToString("o")
}
function Invoke-HmsNativeMaintenanceTick {
    $state=Get-HmsNativeMaintenanceState
    $actions=[System.Collections.Generic.List[string]]::new()
    $errors=[System.Collections.Generic.List[string]]::new()
    $port=[int]$script:S.ProxyPort
    $listener=ListenerPid $port
    $active=($listener -gt 0 -and (IsOurProxy $listener) -and (CodexInHmsMode))

    if($active -and [bool]$script:S.CodexWatchdogEnabled -and (Test-HmsNativeMaintenanceDue $state "watchdog" ([int]$script:S.CodexWatchdogIntervalSec))){
        try{$m=Invoke-CodexWatchdogCheck;$actions.Add("Watchdog")}catch{$errors.Add("Watchdog: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "watchdog"
    }
    if($active -and [bool]$script:S.CodexOpsEnabled -and (Test-HmsNativeMaintenanceDue $state "ops" ([Math]::Max(5,[int]$script:S.CodexOpsScanIntervalSec)) )){
        try{
            $scan=Invoke-CodexOperationsScan
            Update-CodexIncidentsFromScan $scan
            $actions.Add("Route scan")
        }catch{$errors.Add("Route scan: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "ops"
    }
    if($active -and [bool]$script:S.CodexHaEnabled -and (-not [bool]$script:S.CircuitBreakerEnabled) -and (Test-HmsNativeMaintenanceDue $state "ha" ([Math]::Max(10,[int]$script:S.CodexHaIntervalSec)) )){
        try{$null=Invoke-CodexHaCycle;$actions.Add("HA")}catch{$errors.Add("HA: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "ha"
    }
    if([bool]$script:S.UsageLedgerEnabled -and (Test-HmsNativeMaintenanceDue $state "usage-ledger" ([Math]::Max(10,[int]$script:S.UsageLedgerSyncSec)) )){
        try{$null=Invoke-HmsUsageLedger "sync";$actions.Add("Usage ledger")}catch{$errors.Add("Usage ledger: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "usage-ledger"
    }
    if($active -and [bool]$script:S.CircuitBreakerEnabled -and (Test-HmsNativeMaintenanceDue $state "circuit-breaker" ([Math]::Max(10,[int]$script:S.CircuitBreakerIntervalSec)) )){
        try{
            $cbMode=if(([string]$script:S.CircuitBreakerMode).ToUpperInvariant() -eq "GUARDED_AUTO"){"apply"}else{"evaluate"}
            $cb=Invoke-HmsCircuitBreaker $cbMode
            if($cbMode -eq "apply" -and $cb.apply -and [bool]$cb.apply.applied){$actions.Add("Circuit breaker")}
            else{$actions.Add("Circuit eval")}
        }catch{$errors.Add("Circuit breaker: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "circuit-breaker"
    }
    if([bool]$script:S.PredictiveQuotaEnabled -and (Test-HmsNativeMaintenanceDue $state "predictive-quota" ([Math]::Max(15,[int]$script:S.PredictiveQuotaIntervalSec)) )){
        try{$null=Invoke-HmsPredictiveQuota 'evaluate';$actions.Add("Predictive quota")}catch{$errors.Add("Predictive quota: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "predictive-quota"
    }
    if([bool]$script:S.QuotaCenterEnabled -and (Test-HmsNativeMaintenanceDue $state "quota-center" ([Math]::Max(30,[int]$script:S.QuotaCenterIntervalSec)) )){
        try{$null=Invoke-HmsQuotaCenter 'sync';$actions.Add("Quota center")}catch{$errors.Add("Quota center: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "quota-center"
    }
    if([bool]$script:S.AccountAnalyticsEnabled -and (Test-HmsNativeMaintenanceDue $state "account-analytics" ([Math]::Max(30,[int]$script:S.AccountAnalyticsIntervalSec)) )){
        try{$null=Invoke-HmsAccountAnalytics 'sync';$actions.Add("Account analytics")}catch{$errors.Add("Account analytics: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "account-analytics"
    }
    if([bool]$script:S.SmartModelRouterEnabled -and (Test-HmsNativeMaintenanceDue $state "smart-model-router" ([Math]::Max(15,[int]$script:S.SmartModelRouterIntervalSec)) )){
        try{
            $smMode=if(([string]$script:S.SmartModelRouterMode).ToUpperInvariant() -eq 'GUARDED_AUTO'){'apply'}else{'evaluate'}
            $sm=Invoke-HmsSmartModelRouter -Mode $smMode -Manual $false
            if($smMode -eq 'apply' -and $sm.apply -and [bool]$sm.apply.applied){$actions.Add('Smart model route')}else{$actions.Add('Smart model eval')}
        }catch{$errors.Add('Smart model router: '+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state 'smart-model-router'
    }
    if([bool]$script:S.ClosedLoopRouterEnabled -and (Test-HmsNativeMaintenanceDue $state "closed-loop-router" ([Math]::Max(15,[int]$script:S.ClosedLoopRouterIntervalSec)) )){
        try{
            $closedMode=if(([string]$script:S.ClosedLoopRouterMode).ToUpperInvariant() -eq "GUARDED_AUTO"){"apply"}else{"evaluate"}
            $cl=Invoke-HmsClosedLoopRouter $closedMode
            if($closedMode -eq "apply" -and $cl.apply -and [bool]$cl.apply.applied){$actions.Add("Closed-loop route")}
            else{$actions.Add("Closed-loop eval")}
        }catch{$errors.Add("Closed-loop router: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "closed-loop-router"
    }
    elseif([bool]$script:S.AdaptiveRouterEnabled -and (Test-HmsNativeMaintenanceDue $state "adaptive-router" ([Math]::Max(15,[int]$script:S.AdaptiveRouterIntervalSec)) )){
        try{
            $adaptiveMode=if(([string]$script:S.AdaptiveRouterMode).ToUpperInvariant() -eq "GUARDED_AUTO"){"apply"}else{"evaluate"}
            $ar=Invoke-HmsAdaptiveRouter $adaptiveMode
            if($adaptiveMode -eq "apply" -and $ar.apply -and [bool]$ar.apply.applied){$actions.Add("Adaptive route")}
            else{$actions.Add("Adaptive eval")}
        }catch{$errors.Add("Adaptive router: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "adaptive-router"
    }
    if([bool]$script:S.CodexSelfHealingEnabled -and [bool]$script:S.CodexSelfHealingAutoAudit -and (Test-HmsNativeMaintenanceDue $state "self-healing" ([Math]::Max(15,[int]$script:S.CodexSelfHealingIntervalSec)) )){
        try{
            $shMode=if([bool]$script:S.CodexSelfHealingAutoRepairSafe){'repair'}else{'audit'}
            $sh=Invoke-HmsSelfHealing $shMode
            if($shMode -eq 'repair' -and @($sh.actions).Count -gt 0){$actions.Add("Self-heal") }else{$actions.Add("Self-heal audit")}
        }catch{$errors.Add("Self-healing: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "self-healing"
    }
    if([bool]$script:S.CodexSecurityHardeningEnabled -and [bool]$script:S.CodexSecurityAutoAudit -and (Test-HmsNativeMaintenanceDue $state "security-audit" ([Math]::Max(30,[int]$script:S.CodexSecurityIntervalSec)) )){
        try{$sec=Invoke-HmsSecurityHardening 'audit';$actions.Add("Security audit")}catch{$errors.Add("Security audit: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "security-audit"
    }
    if([bool]$script:S.LanPoolEnabled -and [bool]$script:S.LanPoolAutoHeartbeat -and (Test-HmsNativeMaintenanceDue $state "lan-pool" ([Math]::Max(10,[int]$script:S.LanPoolHeartbeatIntervalSec)) )){
        try{$null=Invoke-HmsLanPoolHeartbeat;$actions.Add("LAN pool heartbeat")}catch{$errors.Add("LAN pool: "+[string]$_.Exception.Message)}
        Set-HmsNativeMaintenanceStamp $state "lan-pool"
    }
    if([bool]$script:S.UnifiedDiagnosticsEnabled -and [bool]$script:S.UnifiedDiagnosticsAutoRefresh -and (Test-HmsNativeMaintenanceDue $state "unified-diagnostics" ([Math]::Max(30,[int]$script:S.UnifiedDiagnosticsIntervalSec)) )){
        try{$null=Invoke-HmsUnifiedDiagnostics 'refresh';$actions.Add("Unified diagnostics")}catch{$errors.Add("Unified diagnostics: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "unified-diagnostics"
    }
    if([bool]$script:S.UpdateChannelEnabled -and (Test-HmsNativeMaintenanceDue $state "update-check" ([Math]::Max(3600,[int]$script:S.UpdateAutoCheckHours*3600)) )){
        try{
            $uc=Invoke-HmsUpdateChannel "check";$actions.Add("Update check")
            if([bool]$script:S.UpdateAutoStage -and [bool]$uc.update_available){$null=Invoke-HmsUpdateChannel "stage";$actions.Add("Update staged")}
        }catch{$errors.Add("Update check: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "update-check"
    }
    if([bool]$script:S.CodexAutoQuotaRefresh -and (Test-HmsNativeMaintenanceDue $state "quota" ([Math]::Max(60,[int]$script:S.CodexAutoQuotaRefreshMinutes*60)) )){
        try{$null=Refresh-CodexQuotaAll;$actions.Add("Quota auto")}catch{$errors.Add("Quota auto: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "quota"
    }
    if([bool]$script:S.PolicyKernelEnabled -and (-not $script:RuntimeAutomationBlocked) -and (Test-HmsNativeMaintenanceDue $state "policy" ([Math]::Max(15,[int]$script:S.PolicyKernelIntervalSec)) )){
        try{$null=Invoke-HmsPolicyKernelCycle;$actions.Add("Policy")}catch{$errors.Add("Policy: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "policy"
    }
    if([bool]$script:S.ProductionCertificateEnabled -and (Test-HmsNativeMaintenanceDue $state "health" ([Math]::Max(30,[int]$script:S.ProductionHealthIntervalSec)) )){
        try{$null=Publish-HmsHealthCertificate;$actions.Add("Health")}catch{$errors.Add("Health: "+(Redact-LocalApiText ([string]$_.Exception.Message)))}
        Set-HmsNativeMaintenanceStamp $state "health"
    }

    try{Save-JsonAtomic $script:NativeGuiMaintenanceStatePath $state}catch{}
    return @{
        ok=$true
        version=$script:Version
        active=$active
        actions=@($actions.ToArray())
        errors=@($errors.ToArray())
        activity=(Get-HmsNativeActivityObject)
    }
}

function Get-HmsNativeServiceCenterObject {
    Initialize-HmsApiSuperset
    $port=[int]$script:S.ProxyPort
    $listener=ListenerPid $port
    $ours=($listener -gt 0 -and (IsOurProxy $listener))
    $api=$null
    $models=[System.Collections.Generic.List[object]]::new()
    if($ours){
        $api=Test-ApiModels
        if($api.Ok -and $api.Body){
            try{
                $mj=$api.Body|ConvertFrom-Json
                foreach($m in @($mj.data)){
                    $models.Add([PSCustomObject]@{
                        id=[string]$m.id
                        object=[string]$m.object
                        owned_by=[string]$m.owned_by
                    })
                }
            }catch{}
        }
    }

    $cfg=Load-JsonObjectSafe $script:SmartGatewayConfigPath
    $keydb=Load-JsonObjectSafe $script:SmartGatewayKeysPath
    $clientKeys=[System.Collections.Generic.List[object]]::new()
    foreach($k in @($keydb.keys)){
        $clientKeys.Add([PSCustomObject]@{
            id=[string]$k.id
            name=[string]$k.name
            enabled=if($null -eq $k.enabled){$true}else{[bool]$k.enabled}
            strategy=[string]$k.routing_strategy
            model_prefix=[string]$k.model_prefix
            quota_reserve_pct=if($null -ne $k.quota_reserve_pct){[double]$k.quota_reserve_pct}else{0}
            target_allow=@($k.target_allow)
            target_deny=@($k.target_deny)
            backup_targets=@($k.backup_targets)
            created_utc=[string]$k.created_utc
            updated_utc=[string]$k.updated_utc
        })
    }

    $audit=Get-ProxyApiKeyAudit
    $pool=Get-CodexPoolSummary
    $requestLog=Test-HmsProxyRequestLogEnabled
    $failoverAccounts=@(Get-CodexAccountRecords|Where-Object {$_.File -and $_.Status -ne "LỖI FILE"}|ForEach-Object{
        [PSCustomObject]@{email=[string]$_.Email;status=[string]$_.Status;plan=[string]$_.Plan}
    })

    $diag=""
    try{$diag=Redact-LocalApiText (Get-CodexDiagnosticsText)}catch{}

    return @{
        ok=$true
        version=$script:Version
        service=@{
            router_online=$ours
            listener_pid=[int]$listener
            port=$port
            codex_mode=[bool](CodexInHmsMode)
            api_ok=if($api){[bool]$api.Ok}else{$false}
            api_http=if($api){[int]$api.Status}else{0}
            api_model_count=@($models).Count
            safe_mode=if($api){[string]$api.SafeMode}else{""}
            local_api_key_fingerprint=[string]$audit.ExpectedFingerprint
            local_api_key_config_match=[bool]$audit.ConfigContainsExpected
            request_log_enabled=[bool]$requestLog
        }
        models=@($models.ToArray())
        client_keys=@($clientKeys.ToArray())
        smart_gateway=@{
            strategy=[string]$cfg.strategy
            session_affinity=[bool]$cfg.session_affinity
            session_ttl_sec=[int]$cfg.session_ttl_sec
            require_client_key=[bool]$cfg.require_client_key
            max_failover_attempts=[int]$cfg.max_failover_attempts
            websocket_enabled=[bool]$cfg.websocket_enabled
        }
        pool=@{
            total=[int]$pool.Total
            ready=[int]$pool.Ready
            cooldown=[int]$pool.Cooldown
            free=[int]$pool.Free
            routing=[string](Get-CodexRoutingDescription)
        }
        failover_accounts=$failoverAccounts
        activity=(Get-HmsNativeActivityObject)
        diagnostics=$diag
    }
}

function New-HmsNativeClientKey {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw "CLIENT_KEY_INPUT_MISSING"}
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "CLIENT_KEY_INPUT_INVALID"}
    $name=([string]$input.name).Trim()
    if([string]::IsNullOrWhiteSpace($name)){throw "Tên client key không được trống."}
    if($name.Length -gt 80){throw "Tên client key quá dài."}
    $strategy=([string]$input.strategy).Trim()
    if([string]::IsNullOrWhiteSpace($strategy)){$strategy="stable-round-robin"}
    $allowedStrategies=@("stable-round-robin","random","single","auto","quota-first","plan-first","expiry-soon","weighted","reset-aware","fill-first")
    if($strategy -notin $allowedStrategies){throw "Strategy không hợp lệ."}
    $reserve=0.0
    try{$reserve=[double]$input.quota_reserve_pct}catch{}
    if($reserve -lt 0 -or $reserve -gt 100){throw "Quota reserve phải nằm trong 0..100."}

    Initialize-HmsApiSuperset
    $ctl=Join-Path $PSScriptRoot "HMS_Codex_GatewayControl.py"
    $args=@($ctl,"--config",$script:SmartGatewayConfigPath,"--keys",$script:SmartGatewayKeysPath,
        "create-key","--name",$name,"--strategy",$strategy,"--quota-reserve-pct",[string]$reserve)
    $raw=& ([string]$script:S.CodexSessionDoctorPython) @args
    if($LASTEXITCODE -ne 0){throw "Create client key FAIL: "+(Redact-LocalApiText ([string]$raw))}
    try{$created=([string]$raw)|ConvertFrom-Json}catch{throw "Create client key trả dữ liệu không hợp lệ."}
    $result=Get-HmsNativeServiceCenterObject
    $result["created_client_key"]=[string]$created.client_key
    $result["created_client_key_id"]=[string]$created.id
    $result["message"]="Client key đã tạo. Secret chỉ hiển thị một lần."
    return $result
}

function Set-HmsNativeRequestLog {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw "REQUEST_LOG_INPUT_MISSING"}
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "REQUEST_LOG_INPUT_INVALID"}
    $enabled=[bool]$input.enabled
    Ensure-ProxyFiles
    $wasOnline=$false
    $listener=ListenerPid ([int]$script:S.ProxyPort)
    if($listener -gt 0){
        if(-not (IsOurProxy $listener)){throw "Port do process khác sở hữu; HMS không sửa/restart dịch vụ đó."}
        $wasOnline=$true
    }
    Backup $script:ProxyCfg "request-log-v2524"
    $text=[IO.File]::ReadAllText($script:ProxyCfg)
    $text=Set-TopYaml $text "request-log" $(if($enabled){"true"}else{"false"})
    Write-Utf8 $script:ProxyCfg $text
    if($wasOnline){$null=Restart-Router}
    $check=Test-HmsProxyRequestLogEnabled
    if($check -ne $enabled){throw "Không xác minh được request-log="+$enabled}
    $result=Get-HmsNativeServiceCenterObject
    $result["message"]=if($enabled){"Request Log đã bật."}else{"Request Log đã tắt."}
    return $result
}

function Invoke-HmsNativeFailover {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw "FAILOVER_INPUT_MISSING"}
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "FAILOVER_INPUT_INVALID"}
    $email=([string]$input.email).Trim()
    if([string]::IsNullOrWhiteSpace($email)){throw "Chưa chọn account failover."}
    $record=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $email.ToLowerInvariant()}|Select-Object -First 1)
    if($record.Count -lt 1 -or -not $record[0].File){throw "Không tìm thấy auth file cho $email"}
    $probe=Invoke-HmsLiveFailoverProbe $record[0].File
    $result=Get-HmsNativeServiceCenterObject
    $result["failover_result"]=@{
        verdict=[string]$probe.Verdict
        http=[int]$probe.Http
        target=[string]$probe.Target
        selected=[string]$probe.Selected
        restored=[bool]$probe.Restored
        detail=[string]$probe.Detail
        evidence=[string]$probe.Evidence
    }
    $result["message"]="Failover "+[string]$probe.Verdict+": "+[string]$probe.Detail
    return $result
}

function Get-HmsNativeAccountUsage {
    param([object]$Activity,[string]$Email)
    $zero=[PSCustomObject]@{attributed_events=0;request_signals=0;route_signals=0;failover=0;retry=0;cooldown=0;errors=0;confirmed=0;probable=0}
    if(-not $Activity -or -not $Activity.account_counts){return $zero}
    try{
        foreach($p in @($Activity.account_counts.PSObject.Properties)){
            if(([string]$p.Name).Trim().ToLowerInvariant() -eq $Email.Trim().ToLowerInvariant()){
                return $p.Value
            }
        }
    }catch{}
    return $zero
}
function Get-HmsNativePoolScore {
    param([object]$Record,[object]$Quota,[object]$Health,[object]$Meta,[object]$Usage)
    $score=[double]$Health.Score*0.48
    $reasons=[System.Collections.Generic.List[string]]::new()
    $reasons.Add("health "+[string]$Health.Score)
    $h=$null;$w=$null
    try{if($null -ne $Quota.hourlyRemaining){$h=[int]$Quota.hourlyRemaining}}catch{}
    try{if($null -ne $Quota.weeklyRemaining){$w=[int]$Quota.weeklyRemaining}}catch{}
    $floor=$null
    if($null -ne $h -and $null -ne $w){$floor=[Math]::Min($h,$w)}elseif($null -ne $h){$floor=$h}elseif($null -ne $w){$floor=$w}
    if($null -ne $floor){$score += [double]$floor*0.38;$reasons.Add("quota floor "+$floor+"%")}
    else{$score += 10;$reasons.Add("quota chưa rõ")}
    $role=if($Meta -and $Meta.role){([string]$Meta.role).ToLowerInvariant()}else{"auto"}
    if($role -eq "preferred"){$score+=16;$reasons.Add("ưu tiên")}
    elseif($role -eq "reserve"){$score-=22;$reasons.Add("dự phòng")}
    if($Meta -and [bool]$Meta.favorite){$score+=6;$reasons.Add("favorite")}
    try{$score += [Math]::Min(8,[Math]::Max(0,[int]$Record.Priority)*1.5)}catch{}
    try{$score += [Math]::Min(5,[Math]::Max(0,[int]$Record.Weight-1))}catch{}
    $requestSignals=0
    try{$requestSignals=[int]$Usage.request_signals}catch{}
    if($requestSignals -gt 0){$pen=[Math]::Min(12,$requestSignals*1.5);$score-=$pen;$reasons.Add("load -"+[int]$pen)}
    if($null -ne $floor -and $floor -le 20){
        $resetSoon=$false
        foreach($candidate in @($Quota.hourlyReset,$Quota.weeklyReset)){
            if(-not $candidate){continue}
            try{if((([DateTime]::Parse([string]$candidate)).ToLocalTime()-(Get-Date)).TotalMinutes -ge 0 -and (([DateTime]::Parse([string]$candidate)).ToLocalTime()-(Get-Date)).TotalMinutes -le 90){$resetSoon=$true}}catch{}
        }
        if($resetSoon){$score+=8;$reasons.Add("reset sớm")}
        else{$score-=10;$reasons.Add("quota thấp")}
    }
    if([string]$Record.Status -ne "READY"){$score-=35;$reasons.Add(([string]$Record.Status).ToLowerInvariant())}
    $score=[Math]::Max(0,[Math]::Min(100,[Math]::Round($score)))
    return [PSCustomObject]@{Score=[int]$score;Role=$role;Reason=($reasons -join " · ")}
}
function Get-HmsNativeAccountCenterObject {
    $rawItems=[System.Collections.Generic.List[object]]::new()
    $activity=Get-HmsNativeActivityObject
    $recentEmail=([string]$activity.account).Trim().ToLowerInvariant()
    foreach($record in @(Get-CodexAccountRecords)){
        $quota=Get-CodexQuotaForEmail $record.Email
        $health=Get-CodexAccountHealth $record
        $meta=Get-CodexAccountMeta $record.Email
        $usage=Get-HmsNativeAccountUsage $activity $record.Email
        $hourlyRemaining=$null;$hourlyReset=$null;$hourlyResetText="—";$hourlyResetAtText="—";$hourlyWindow=$null
        $weeklyRemaining=$null;$weeklyReset=$null;$weeklyResetText="—";$weeklyResetAtText="—";$weeklyWindow=$null
        $packageExpiry=$null;$packageExpiryText="—";$packageRemainingText="—";$packageExpirySource="NOT_EXPOSED"
        $quotaRefreshed=$null;$quotaLastSuccess=$null;$quotaLastAttempt=$null;$quotaSourceState=$null;$quotaErrorCode=$null;$quotaError=$null
        if($quota){
            try{$hourlyRemaining=if($null -ne $quota.hourlyRemaining){[int]$quota.hourlyRemaining}else{$null}}catch{}
            try{$hourlyReset=[string]$quota.hourlyReset}catch{}
            try{$hourlyWindow=if($null -ne $quota.hourlyWindowMinutes){[int]$quota.hourlyWindowMinutes}else{$null}}catch{}
            try{$weeklyRemaining=if($null -ne $quota.weeklyRemaining){[int]$quota.weeklyRemaining}else{$null}}catch{}
            try{$weeklyReset=[string]$quota.weeklyReset}catch{}
            try{$weeklyWindow=if($null -ne $quota.weeklyWindowMinutes){[int]$quota.weeklyWindowMinutes}else{$null}}catch{}
            try{$quotaRefreshed=[string]$quota.refreshedUtc}catch{}
            try{$quotaLastSuccess=[string]$quota.lastSuccessUtc}catch{}
            if([string]::IsNullOrWhiteSpace($quotaLastSuccess)){$quotaLastSuccess=$quotaRefreshed}
            try{$quotaLastAttempt=[string]$quota.lastAttemptUtc}catch{}
            try{$quotaSourceState=[string]$quota.sourceState}catch{}
            try{$quotaErrorCode=[string]$quota.errorCode}catch{}
            try{$quotaError=[string]$quota.error}catch{}
            try{$packageExpiry=[string]$quota.packageExpiry}catch{}
            try{$packageExpirySource=[string]$quota.packageExpirySource}catch{}
            $hourlyResetText=Format-ResetCountdown $hourlyReset
            $weeklyResetText=Format-ResetCountdown $weeklyReset
            $hourlyResetAtText=Format-ResetAbsolute $hourlyReset
            $weeklyResetAtText=Format-ResetAbsolute $weeklyReset
            if($packageExpiry){$packageExpiryText=Format-ResetAbsolute $packageExpiry;$packageRemainingText=Format-ResetCountdown $packageExpiry}
        }
        $quotaView=[PSCustomObject]@{
            hourlyRemaining=$hourlyRemaining;hourlyReset=$hourlyReset;weeklyRemaining=$weeklyRemaining;weeklyReset=$weeklyReset
        }
        $liveQuota=Get-CodexLiveQuotaDecision $record $quota
        $intel=Get-HmsNativePoolScore $record $quotaView $health $meta $usage
        $expiryText="—"
        if($record.Expiry){try{$expiryText=$record.Expiry.ToString("dd/MM/yyyy HH:mm")}catch{}}
        $rawItems.Add([PSCustomObject]@{
            email=[string]$record.Email
            alias=if($meta){[string]$meta.alias}else{""}
            group=if($meta){[string]$meta.group}else{""}
            role=if($meta -and $meta.role){[string]$meta.role}else{"auto"}
            plan=[string]$record.Plan
            status=[string]$record.Status
            client_auth_state=[string]$record.ClientAuthState
            api_service_state=[string]$record.ApiServiceState
            overall_availability=[string]$record.OverallAvailability
            official_account_ref=[string]$record.OfficialAccountRef
            disabled=([string]$record.Status -eq "DISABLED")
            generic_quota=[string]$record.Quota
            generic_quota_percent=$record.QuotaPercent
            reset=[string]$record.Reset
            token_expiry=$expiryText
            runtime=[string]$record.Runtime
            priority=[int]$record.Priority
            weight=[int]$record.Weight
            websockets=$record.WebSockets
            updated=$record.Updated.ToString("o")
            health_score=[int]$health.Score
            health_grade=[string]$health.Grade
            health_reason=[string]$health.Reason
            tag=[string]$meta.tag
            note=[string]$meta.note
            favorite=[bool]$meta.favorite
            is_recent_route=([bool]($recentEmail -and $record.Email.Trim().ToLowerInvariant() -eq $recentEmail))
            pool_score=[int]$intel.Score
            pool_reason=[string]$intel.Reason
            pool_role=[string]$intel.Role
            usage=[PSCustomObject]@{
                attributed_events=try{[int]$usage.attributed_events}catch{0}
                request_signals=try{[int]$usage.request_signals}catch{0}
                route_signals=try{[int]$usage.route_signals}catch{0}
                failover=try{[int]$usage.failover}catch{0}
                retry=try{[int]$usage.retry}catch{0}
                cooldown=try{[int]$usage.cooldown}catch{0}
                errors=try{[int]$usage.errors}catch{0}
                confirmed=try{[int]$usage.confirmed}catch{0}
                probable=try{[int]$usage.probable}catch{0}
            }
            quota=[PSCustomObject]@{
                five_hour_remaining=$hourlyRemaining
                five_hour_reset=$hourlyReset
                five_hour_reset_text=$hourlyResetText
                five_hour_reset_at_text=$hourlyResetAtText
                five_hour_window_minutes=$hourlyWindow
                five_hour_window_present=if($quota){try{[bool]$quota.hourlyWindowPresent}catch{($null -ne $hourlyRemaining)}}else{$false}
                weekly_remaining=$weeklyRemaining
                weekly_reset=$weeklyReset
                weekly_reset_text=$weeklyResetText
                weekly_reset_at_text=$weeklyResetAtText
                weekly_window_minutes=$weeklyWindow
                weekly_window_present=if($quota){try{[bool]$quota.weeklyWindowPresent}catch{($null -ne $weeklyRemaining)}}else{$false}
                refreshed_utc=$quotaRefreshed
                last_success_utc=$quotaLastSuccess
                last_attempt_utc=$quotaLastAttempt
                source=if($quota){try{[string]$quota.source}catch{"WHAM_USAGE"}}else{"WHAM_USAGE"}
                source_state=$quotaSourceState
                freshness_state=[string]$liveQuota.freshnessState
                source_age_seconds=$liveQuota.ageSeconds
                reserve_pct=[double]$liveQuota.reservePct
                quota_floor_pct=$liveQuota.quotaFloorPct
                usable_remaining_pct=$liveQuota.usableRemainingPct
                routing_eligible=[bool]$liveQuota.routingEligible
                reason_codes=@($liveQuota.reasonCodes)
                error_code=$quotaErrorCode
                error=$quotaError
                code_review=if($quota){$quota.codeReview}else{$null}
                additional_windows=if($quota){@($quota.additionalWindows)}else{@()}
                monthly_credits=if($quota){$quota.monthlyCredits}else{$null}
                reset_credits_available=if($quota){$quota.resetCreditsAvailable}else{$null}
                package_expiry_utc=$packageExpiry
                package_expiry_text=$packageExpiryText
                package_remaining_text=$packageRemainingText
                package_expiry_source=$packageExpirySource
            }
        })
    }
    $sorted=@($rawItems.ToArray() | Sort-Object @{Expression={$_.pool_score};Descending=$true}, @{Expression={$_.health_score};Descending=$true}, email)
    for($i=0;$i -lt $sorted.Count;$i++){$sorted[$i] | Add-Member -NotePropertyName pool_rank -NotePropertyValue ($i+1) -Force}
    $pool=Get-CodexPoolSummary
    $top=if($sorted.Count -gt 0){$sorted[0]}else{$null}
    $routeEligible=@($sorted | Where-Object {$_.quota -and [bool]$_.quota.routing_eligible}).Count
    $hold=@($sorted | Where-Object {-not ($_.quota -and [bool]$_.quota.routing_eligible)}).Count
    $stale=@($sorted | Where-Object {$_.quota -and ([string]$_.quota.freshness_state -eq "STALE")}).Count
    $aging=@($sorted | Where-Object {$_.quota -and ([string]$_.quota.freshness_state -eq "AGING")}).Count
    $favorite=@($sorted | Where-Object {[bool]$_.favorite}).Count
    $activeRoute=if($recentEmail){@($sorted | Where-Object {$_.email.Trim().ToLowerInvariant() -eq $recentEmail} | Select-Object -First 1)}else{@()}
    return @{
        ok=$true
        version=$script:Version
        accounts=$sorted
        summary=@{
            total=[int]$pool.Total
            ready=[int]$pool.Ready
            cooldown=[int]$pool.Cooldown
            free=[int]$pool.Free
            route_eligible=[int]$routeEligible
            hold=[int]$hold
            stale=[int]$stale
            aging=[int]$aging
            favorite=[int]$favorite
            active_route=if($activeRoute.Count){[string]$activeRoute[0].email}else{""}
            active_route_eligible=if($activeRoute.Count -and $activeRoute[0].quota){[bool]$activeRoute[0].quota.routing_eligible}else{$null}
            top_account=if($top){[string]$top.email}else{""}
            top_score=if($top){[int]$top.pool_score}else{0}
        }
        quota_direct_enabled=[bool]$script:S.CodexQuotaDirectEnabled
        quota_auto_enabled=[bool]$script:S.CodexAutoQuotaRefresh
        quota_refresh_minutes=[int]$script:S.CodexQuotaRefreshMinutes
        quota_live_policy=@{fresh_seconds=[int]$script:S.CodexQuotaFreshSeconds;stale_seconds=[int]$script:S.CodexQuotaStaleSeconds;fail_closed=[bool]$script:S.CodexQuotaFailClosed;reserve_free_pct=[int]$script:S.CodexQuotaReserveFreePct;reserve_plus_pct=[int]$script:S.CodexQuotaReservePlusPct;reserve_pro_pct=[int]$script:S.CodexQuotaReserveProPct;reserve_default_pct=[int]$script:S.CodexQuotaReserveDefaultPct;release_margin_pct=[int]$script:S.CodexQuotaSwitchReleaseMarginPct}
        activity=$activity
        intelligence_note="v25.50: quota routing dùng last-good + freshness TTL + plan reserve; refresh lỗi không làm quota cũ thành fresh. Existing session affinity không bị cắt vì quota stale."
    }
}

function Add-HmsUsageTokenCenterView {
    param([hashtable]$Result,[bool]$AppendHistory=$false)
    if(-not $Result){return $Result}
    $tool=Join-Path $PSScriptRoot 'HMS_Codex_UsageTokenCenter.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){return $Result}
    try{
        Ensure-Dir $script:UsageTokenCenterDir
        $inputPath=Join-Path $env:TEMP ('hms-v2561-usage-'+[Guid]::NewGuid().ToString('N')+'.json')
        try{
            [IO.File]::WriteAllText($inputPath,($Result|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($false)))
            if($AppendHistory){
                $null=Invoke-PythonJsonHelper ([string]$script:S.CodexSessionDoctorPython) $tool @('--accounts',$inputPath,'--mode','snapshot','--history',$script:UsageTokenCenterHistoryPath)
            }
            $j=Invoke-PythonJsonHelper ([string]$script:S.CodexSessionDoctorPython) $tool @('--accounts',$inputPath,'--mode','build')
            if($j -and $j.usage_token_center){
                $Result['usage_token_center']=$j.usage_token_center
                $latest=[ordered]@{ok=$true;version=$script:Version;usage_token_center=$j.usage_token_center}
                Save-JsonAtomic $script:UsageTokenCenterLatestPath $latest
            }
        }finally{Remove-Item -LiteralPath $inputPath -Force -ErrorAction SilentlyContinue}
    }catch{
        $Result['usage_token_center_warning']='USAGE_TOKEN_CENTER_UNAVAILABLE: '+(Redact-LocalApiText $_.Exception.Message)
    }
    return $Result
}

function Set-HmsNativeAccountDisabled {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){
        throw "ACCOUNT_ACTION_INPUT_MISSING"
    }
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}
    catch{throw "ACCOUNT_ACTION_JSON_INVALID"}
    $email=([string]$input.email).Trim()
    if([string]::IsNullOrWhiteSpace($email)){throw "ACCOUNT_EMAIL_MISSING"}
    $disabled=$false
    try{$disabled=[bool]$input.disabled}catch{throw "ACCOUNT_DISABLED_INVALID"}
    $record=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $email.ToLowerInvariant()}|Select-Object -First 1)
    if($record.Count -eq 0){throw "Không tìm thấy account: $email"}
    if(-not $record[0].File){throw "Account không có auth file hợp lệ."}
    if($disabled){
        Set-HmsAuthDisabledProperty $record[0].File $true $false
    }else{
        Set-HmsAuthDisabledProperty $record[0].File $false $true
    }
    Start-Sleep -Milliseconds 350
    $snap=Get-HmsAuthDisabledSnapshot $record[0].File
    if($disabled -and -not $snap.Disabled){throw "Không xác minh được disabled=true."}
    if(-not $disabled -and $snap.Disabled){throw "Không xác minh được account đã active."}
    $result=Get-HmsNativeAccountCenterObject
    $result["message"]=if($disabled){"Đã tạm dừng $email"}else{"Đã kích hoạt $email"}
    return $result
}


function Set-HmsNativeAccountMeta {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw "ACCOUNT_META_INPUT_MISSING"}
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "ACCOUNT_META_INPUT_INVALID"}
    $email=([string]$input.email).Trim()
    if([string]::IsNullOrWhiteSpace($email)){throw "ACCOUNT_EMAIL_MISSING"}
    $exists=@(Get-CodexAccountRecords|Where-Object {$_.Email.Trim().ToLowerInvariant() -eq $email.ToLowerInvariant()}).Count -gt 0
    if(-not $exists){throw "Không tìm thấy account: $email"}
    $alias=[string]$input.alias;$group=[string]$input.group;$role=[string]$input.role;$favorite=[bool]$input.favorite
    if($alias.Length -gt 40){throw "Alias tối đa 40 ký tự."}
    if($group.Length -gt 40){throw "Group tối đa 40 ký tự."}
    Set-CodexAccountPoolMeta $email $alias $group $role $favorite
    $result=Get-HmsNativeAccountCenterObject
    $result["message"]="Đã cập nhật chính sách pool cho $email"
    return $result
}

function Start-HmsNativeCodexOAuth {
    Ensure-ProxyFiles
    $before=@(Get-CodexAccountRecords).Count
    $stdout=Join-Path $env:TEMP ("hms-v2525-oauth-"+[Guid]::NewGuid().ToString("N")+".out.log")
    $stderr=Join-Path $env:TEMP ("hms-v2525-oauth-"+[Guid]::NewGuid().ToString("N")+".err.log")
    $proc=$null;$opened=$false;$url=""
    try{
        $proc=Start-Process $script:ProxyExe -ArgumentList @("--codex-login") `
            -WorkingDirectory ([string]$script:S.ProxyDir) -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $deadline=(Get-Date).AddMinutes(4)
        while(-not $proc.HasExited -and (Get-Date) -lt $deadline){
            Start-Sleep -Milliseconds 400
            if(-not $opened){
                $text=""
                try{if(Test-Path $stdout){$text+=(Get-Content $stdout -Raw -ErrorAction SilentlyContinue)}}catch{}
                try{if(Test-Path $stderr){$text+="`n"+(Get-Content $stderr -Raw -ErrorAction SilentlyContinue)}}catch{}
                if($text){
                    $m=[regex]::Match($text,'https://[^\s"''<>]+')
                    if($m.Success){
                        $url=[string]$m.Value
                        try{Start-Process $url|Out-Null;$opened=$true}catch{}
                    }
                }
            }
        }
        if(-not $proc.HasExited){
            try{$proc.Kill()}catch{}
            throw "OAuth timeout sau 4 phút."
        }
        if($proc.ExitCode -ne 0){
            $tail=""
            try{
                $text=""
                if(Test-Path $stderr){$text=[IO.File]::ReadAllText($stderr)}
                elseif(Test-Path $stdout){$text=[IO.File]::ReadAllText($stdout)}
                $tail=Redact-LocalApiText $text
                if($tail.Length -gt 320){$tail=$tail.Substring($tail.Length-320)}
            }catch{}
            throw ("OAuth kết thúc với mã "+$proc.ExitCode+". "+$tail)
        }
        Start-Sleep -Milliseconds 700
        $after=@(Get-CodexAccountRecords).Count
        $result=Get-HmsNativeAccountCenterObject
        $result["message"]=if($after -gt $before){"Đã thêm tài khoản Codex."}else{"OAuth hoàn tất; credential hiện có đã được cập nhật."}
        return $result
    }finally{
        Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue
    }
}


function Start-HmsNativeProviderOAuth {
    param([string]$Flag,[string]$Label)
    Ensure-ProxyFiles
    $before=if($Flag -eq "--antigravity-login"){@(Get-AntigravityAccountRecords).Count}else{@(Get-CodexAccountRecords).Count}
    $stdout=Join-Path $env:TEMP ("hms-v2525-oauth-"+[Guid]::NewGuid().ToString("N")+".out.log")
    $stderr=Join-Path $env:TEMP ("hms-v2525-oauth-"+[Guid]::NewGuid().ToString("N")+".err.log")
    try{
        $proc=Start-Process $script:ProxyExe -ArgumentList @($Flag) -WorkingDirectory ([string]$script:S.ProxyDir) -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $deadline=(Get-Date).AddMinutes(4);$opened=$false
        while(-not $proc.HasExited -and (Get-Date) -lt $deadline){
            Start-Sleep -Milliseconds 400
            if(-not $opened){
                $text="";try{if(Test-Path $stdout){$text+=(Get-Content $stdout -Raw -ErrorAction SilentlyContinue)}}catch{};try{if(Test-Path $stderr){$text+="`n"+(Get-Content $stderr -Raw -ErrorAction SilentlyContinue)}}catch{}
                if($text){$m=[regex]::Match($text,'https?://[^\s"''<>]+');if($m.Success -and [string]$m.Value -match '^https://'){$opened=$true;try{Start-Process ([string]$m.Value)|Out-Null}catch{}}}
            }
        }
        if(-not $proc.HasExited){try{$proc.Kill()}catch{};throw "$Label OAuth đang chờ quá lâu. Hãy thử lại từ Trung tâm Antigravity."}
        if($proc.ExitCode -ne 0){$tail="";try{$tail=((Get-Content $stdout,$stderr -Tail 20 -ErrorAction SilentlyContinue)-join" ")}catch{};throw "$Label OAuth exit=$($proc.ExitCode). "+(Redact-LocalApiText $tail)}
        Start-Sleep -Milliseconds 700
        $after=if($Flag -eq "--antigravity-login"){@(Get-AntigravityAccountRecords).Count}else{@(Get-CodexAccountRecords).Count}
        return [PSCustomObject]@{Before=$before;After=$after}
    }finally{Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue}
}
function Get-HmsNativeAntigravityObject {
    $installed=Get-AntigravityInstalledInfo
    $bridge=Test-HmsAntigravityBridge
    $active=$null
    try{$active=Get-AgActiveAccountFromBridge}catch{}
    $current=if($active){[string]$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{""}
    $ranked=@(Get-AgRankedAccounts $current)
    $items=[System.Collections.Generic.List[object]]::new()
    foreach($r in $ranked){
        $expiry="—";if($r.Expiry){try{$expiry=$r.Expiry.ToString("dd/MM/yyyy HH:mm")}catch{}}
        $items.Add([PSCustomObject]@{
            email=[string]$r.Email;status=[string]$r.Status;quota_percent=$r.QuotaPercent;
            health_score=[int]$r.HealthScore;health_grade=[string]$r.Grade;health_reason=[string]$r.HealthReason;
            expiry=$expiry;runtime=[string]$r.Runtime;project_id=[string]$r.ProjectId;is_current=[bool]$r.IsCurrent
        })
    }
    $mode=if([bool]$script:S.AgSeamlessEnabled){if($bridge.Ok){"SEAMLESS"}elseif([bool]$script:S.AgFallbackRestart){"RESTART_FALLBACK"}else{"FAIL_CLOSED"}}elseif([bool]$script:S.AgFallbackRestart){"RESTART_ONLY"}else{"DISABLED"}
    return @{
        ok=$true;version=$script:Version
        installed=@{found=[bool]$installed.Found;path=[string]$installed.Path;version=[string]$installed.Version;processes=@(Get-AntigravityProcesses).Count}
        bridge=@{ok=[bool]$bridge.Ok;message=(Redact-LocalApiText ([string]$bridge.Message));host_api=if($bridge.Response){[string]$bridge.Response.hostApi}else{""};api_available=if($bridge.Response){[bool]$bridge.Response.apiAvailable}else{$false}}
        current_email=$current;mode=$mode
        settings=@{seamless=[bool]$script:S.AgSeamlessEnabled;fallback_restart=[bool]$script:S.AgFallbackRestart;auto_switch=[bool]$script:S.AgAutoSwitchEnabled;threshold=[int]$script:S.AgAutoSwitchThreshold;interval_sec=[int]$script:S.AgAutoSwitchIntervalSec;watchdog=[bool]$script:S.AgWatchdogEnabled;verified_readback=[bool]$script:S.AgRequireVerifiedReadback}
        accounts=@($items.ToArray());history=@(Get-AgSwitchHistory -Max 20)
        message="Antigravity Control Center đã đồng bộ. SEAMLESS = đổi qua Bridge không restart; RESTART_FALLBACK chỉ dùng khi seamless không khả dụng và setting cho phép."
    }
}
function Invoke-HmsNativeAgSwitch {
    if([string]::IsNullOrWhiteSpace($BackendInputPath) -or -not (Test-Path $BackendInputPath)){throw "AG_SWITCH_INPUT_MISSING"}
    try{$input=Get-Content $BackendInputPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "AG_SWITCH_INPUT_INVALID"}
    $email=([string]$input.email).Trim();if(-not $email){throw "Chưa chọn Antigravity account."}
    $message=Switch-AntigravityAccount -Email $email -Reason "native-gui-v2525"
    $result=Get-HmsNativeAntigravityObject;$result["message"]=$message;return $result
}

function Get-HmsNativeLogsObject {
    $routerLines=[System.Collections.Generic.List[string]]::new()
    $requestRows=[System.Collections.Generic.List[object]]::new()
    $roots=[System.Collections.Generic.List[string]]::new()
    foreach($candidate in @(
        (Join-Path ([string]$script:S.ProxyDir) "logs"),
        (Join-Path $script:DataDir "logs")
    )){
        if($candidate -and (Test-Path $candidate) -and -not $roots.Contains($candidate)){$roots.Add($candidate)}
    }
    foreach($root in $roots){
        $files=@(Get-ChildItem $root -File -Recurse -Filter "*.log" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 40)
        foreach($f in $files){
            if($f.Name -like "request-*.log"){
                $requestRows.Add([PSCustomObject]@{
                    file=$f.Name
                    updated=$f.LastWriteTime.ToString("o")
                    size=[int64]$f.Length
                })
                continue
            }
            if($routerLines.Count -ge 220){break}
            try{
                $text=[IO.File]::ReadAllText($f.FullName)
                $safe=Redact-LocalApiText $text
                $lines=@($safe -split "`r?`n")
                $take=[Math]::Min(80,$lines.Count)
                for($i=[Math]::Max(0,$lines.Count-$take);$i -lt $lines.Count;$i++){
                    if($routerLines.Count -ge 220){break}
                    if(-not [string]::IsNullOrWhiteSpace($lines[$i])){$routerLines.Add($lines[$i])}
                }
            }catch{}
        }
    }
    $activity=Get-HmsNativeActivityObject
    return @{
        ok=$true
        version=$script:Version
        router_lines=@($routerLines.ToArray())
        request_logs=@($requestRows.ToArray())
        activity=$activity
        route_events=@($activity.recent_events)
        note="Raw request logs có thể chứa credential/cookie nên HMS chỉ hiển thị metadata của request log, không hiển thị raw body/token."
    }
}

function Get-HmsBackendStatusObject {
    $port=[int]$script:S.ProxyPort
    $listener=ListenerPid $port
    $ours=($listener -gt 0 -and (IsOurProxy $listener))
    $pool=Get-CodexPoolSummary
    $activity=Get-HmsNativeActivityObject
    $recentEmail=([string]$activity.account).Trim().ToLowerInvariant()
    $records=@()
    foreach($record in @(Get-CodexAccountRecords | Select-Object -First 6)){
        $direct=Get-CodexQuotaForEmail $record.Email
        $quotaText=[string]$record.Quota
        if($direct){
            $parts=[System.Collections.Generic.List[string]]::new()
            if($null -ne $direct.hourlyRemaining){$parts.Add("5h "+[string]$direct.hourlyRemaining+"%")}
            if($null -ne $direct.weeklyRemaining){$parts.Add("Tuần "+[string]$direct.weeklyRemaining+"%")}
            if($parts.Count -gt 0){$quotaText=$parts -join " · "}
        }
        $records+=@{
            email=[string]$record.Email
            plan=[string]$record.Plan
            status=[string]$record.Status
            quota=$quotaText
            is_recent_route=([bool]($recentEmail -and $record.Email.Trim().ToLowerInvariant() -eq $recentEmail))
        }
    }
    return @{
        ok=$true
        version=$script:Version
        active=($ours -and (CodexInHmsMode))
        router_online=$ours
        foreign_listener=($listener -gt 0 -and -not $ours)
        listener_pid=[int]$listener
        port=$port
        codex_mode=[bool](CodexInHmsMode)
        accounts=@{
            total=[int]$pool.Total
            ready=[int]$pool.Ready
            cooldown=[int]$pool.Cooldown
            free=[int]$pool.Free
            records=$records
        }
        routing=[string](Get-CodexRoutingDescription)
        activity=$activity
        codex_processes=@(Get-CodexClientProcesses).Count
    }
}


# v25.67 Startup Recovery + Windows target adapter/trust campaign gate.
# Direct backend/private auth mutation cannot bypass GUI startup reconciliation.
$script:StartupRecoveryConflictingActions = @(
    "restart_router","run_failover","apply_adaptive_router","rollback_adaptive_router",
    "apply_closed_loop_router","rollback_closed_loop_router","apply_circuit_breaker","reset_circuit_breaker",
    "create_instance","start_instance","stop_instance","restart_instance","launch_project_affinity","sync_project_router",
    "apply_model_policy","repair_self_healing","launch_project_orchestrator","launch_multi_codex_team",
    "apply_smart_model_router","rollback_smart_model_router","pair_lan_pool","acquire_lan_project","release_lan_project",
    "__official_auth_switch__"
)
function Invoke-HmsStartupRecoveryPreflight {
    param([string]$Action)
    if([string]::IsNullOrWhiteSpace($Action)){return}
    if(-not ($script:StartupRecoveryConflictingActions -contains $Action)){return}
    Ensure-Dir $script:StartupRecoveryDir
    $tool=Join-Path $PSScriptRoot "HMS_Codex_StartupRecoveryReconciler.py"
    if(-not (Test-Path $tool)){throw "STARTUP_RECOVERY_PREFLIGHT_UNAVAILABLE: reconciler missing"}
    $python=(Get-Command python.exe -ErrorAction SilentlyContinue)
    if(-not $python){$python=(Get-Command python -ErrorAction SilentlyContinue)}
    if(-not $python){throw "STARTUP_RECOVERY_PREFLIGHT_UNAVAILABLE: python missing"}
    $args=@($tool,"--mode","reconcile","--data-dir",$script:DataDir,"--output",$script:StartupRecoveryLatestPath)
    & $python.Source @args | Out-Null
    if($LASTEXITCODE -ne 0){throw "STARTUP_RECOVERY_PREFLIGHT_FAILED"}
    if(-not (Test-Path $script:StartupRecoveryLatestPath)){throw "STARTUP_RECOVERY_PREFLIGHT_MISSING_RESULT"}
    try{$gate=Get-Content $script:StartupRecoveryLatestPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw "STARTUP_RECOVERY_PREFLIGHT_INVALID_RESULT"}
    $blocked=@($gate.mutation_gate.blocked_actions)
    if([bool]$gate.mutation_gate.block_conflicting_mutation -and ($blocked -contains $Action)){
        $state=[string]$gate.status
        throw ("STARTUP_RECOVERY_BLOCKED: {0}; resolve Recovery timeline before mutation" -f $state)
    }
}

if(-not [string]::IsNullOrWhiteSpace($OfficialAuthSwitchEmail)){
    $result=$null
    try{
        Load-Settings;Refresh-Paths;Initialize-HmsSecuritySecretMigration
        Invoke-HmsStartupRecoveryPreflight "__official_auth_switch__"
        $sw=Invoke-HmsCodexOfficialAuthSwitch $OfficialAuthSwitchEmail
        $result=[ordered]@{ok=$true;version=$script:Version;message=('Đã chuyển Official Codex auth sang '+$OfficialAuthSwitchEmail+'.');switch=$sw}
    }catch{
        $result=[ordered]@{ok=$false;version=$script:Version;error=(Redact-LocalApiText $_.Exception.Message)}
    }
    $json=$result|ConvertTo-Json -Depth 12
    if(-not [string]::IsNullOrWhiteSpace($OfficialAuthSwitchResultPath)){
        $dir=Split-Path -Parent $OfficialAuthSwitchResultPath;if($dir){Ensure-Dir $dir};[IO.File]::WriteAllText($OfficialAuthSwitchResultPath,$json,(New-Object Text.UTF8Encoding($false)))
    }else{$json}
    if([bool]$result.ok){exit 0}else{exit 2}
}

if($BackendAction -ne "ui"){
    $result=$null
    try{
        Load-Settings
        Refresh-Paths
        Initialize-HmsSecuritySecretMigration
        Invoke-HmsStartupRecoveryPreflight $BackendAction

        if($BackendAction -eq "status"){
            $result=Get-HmsBackendStatusObject
        }
        elseif($BackendAction -eq "get_settings"){
            $result=Get-HmsBackendSettingsObject
        }
        elseif($BackendAction -eq "save_settings"){
            $result=Apply-HmsBackendSettings
        }
        elseif($BackendAction -eq "get_accounts"){
            $result=Get-HmsNativeAccountCenterObject
            $result=Add-HmsUsageTokenCenterView $result $false
        }
        elseif($BackendAction -eq "refresh_quota"){
            $message=Refresh-CodexQuotaAll
            $result=Get-HmsNativeAccountCenterObject
            $result=Add-HmsUsageTokenCenterView $result $true
            $result["message"]=$message
        }
        elseif($BackendAction -eq "set_account_disabled"){
            $result=Set-HmsNativeAccountDisabled
        }
        elseif($BackendAction -eq "set_account_meta"){
            $result=Set-HmsNativeAccountMeta
        }
        elseif($BackendAction -eq "add_codex"){
            $result=Start-HmsNativeCodexOAuth
        }
        elseif($BackendAction -eq "get_logs"){
            $result=Get-HmsNativeLogsObject
        }
        elseif($BackendAction -eq "get_service"){
            $result=Get-HmsNativeServiceCenterObject
        }
        elseif($BackendAction -eq "create_client_key"){
            $result=New-HmsNativeClientKey
        }
        elseif($BackendAction -eq "set_request_log"){
            $result=Set-HmsNativeRequestLog
        }
        elseif($BackendAction -eq "restart_router"){
            $message=Restart-Router
            $result=Get-HmsNativeServiceCenterObject
            $result["message"]=$message
        }
        elseif($BackendAction -eq "test_api"){
            $api=Test-ApiModels
            $result=Get-HmsNativeServiceCenterObject
            $result["test_api"]=@{ok=[bool]$api.Ok;http=[int]$api.Status;count=[int]$api.Count;safe_mode=[string]$api.SafeMode;error=[string]$api.Error}
            $result["message"]=if($api.Ok){"API PASS · HTTP "+$api.Status+" · "+$api.Count+" models"}else{"API FAIL · HTTP "+$api.Status+" · "+$api.Error}
        }
        elseif($BackendAction -eq "run_failover"){
            $result=Invoke-HmsNativeFailover
        }
        elseif($BackendAction -eq "maintenance_tick"){
            $result=Invoke-HmsNativeMaintenanceTick
        }
        elseif($BackendAction -eq "get_usage"){
            $result=Get-HmsNativeUsageObject $false
        }
        elseif($BackendAction -eq "sync_usage"){
            $result=Get-HmsNativeUsageObject $true
            $result["message"]="Usage Ledger đã đồng bộ."
        }
        elseif($BackendAction -eq "diagnostics_bundle"){
            $result=New-HmsNativeDiagnosticsBundle
        }
        elseif($BackendAction -eq "get_release"){
            $result=Get-HmsNativeReleaseObject
        }
        elseif($BackendAction -eq "release_install"){
            $d=Invoke-HmsReleaseManager "install"
            $result=@{ok=$true;version=$script:Version;release=$d;message="Đã đăng ký và kích hoạt release v$($script:Version)."}
        }
        elseif($BackendAction -eq "release_rollback"){
            $d=Invoke-HmsReleaseManager "rollback"
            $result=@{ok=$true;version=$script:Version;release=$d;message="Đã đổi ACTIVE pointer về release trước. Không xóa bản hiện tại."}
        }
        elseif($BackendAction -eq "get_adaptive_router"){
            $result=Get-HmsNativeAdaptiveRouterObject
        }
        elseif($BackendAction -eq "evaluate_adaptive_router"){
            $d=Invoke-HmsAdaptiveRouter "evaluate"
            $result=@{ok=$true;version=$script:Version;adaptive=$d;message="Adaptive Router đã đánh giá pool."}
        }
        elseif($BackendAction -eq "apply_adaptive_router"){
            $d=Invoke-HmsAdaptiveRouter "apply"
            $result=@{ok=$true;version=$script:Version;adaptive=$d;message="Adaptive Router đã áp dụng routing hints có readback; không sửa OAuth token."}
        }
        elseif($BackendAction -eq "rollback_adaptive_router"){
            $d=Invoke-HmsAdaptiveRouter "rollback"
            $result=@{ok=$true;version=$script:Version;adaptive=$d;message="Đã hoàn tác priority/weight từ snapshot Adaptive Router."}
        }
        elseif($BackendAction -eq "get_closed_loop_router"){
            $result=Get-HmsNativeClosedLoopRouterObject
        }
        elseif($BackendAction -eq "evaluate_closed_loop_router"){
            $d=Invoke-HmsClosedLoopRouter "evaluate"
            $result=@{ok=$true;version=$script:Version;closed_loop=$d;message="Closed-loop Router đã đánh giá từng Codex instance từ Usage Ledger + quota/health."}
        }
        elseif($BackendAction -eq "apply_closed_loop_router"){
            $d=Invoke-HmsClosedLoopRouter "apply"
            $result=@{ok=$true;version=$script:Version;closed_loop=$d;message="Closed-loop Router đã áp dụng priority/weight theo từng instance; stable endpoint và session affinity không đổi."}
        }
        elseif($BackendAction -eq "rollback_closed_loop_router"){
            $d=Invoke-HmsClosedLoopRouter "rollback"
            $result=@{ok=$true;version=$script:Version;closed_loop=$d;message="Đã hoàn tác priority/weight Closed-loop Router từ snapshot gần nhất; không xóa credential."}
        }
        elseif($BackendAction -eq "get_circuit_breaker"){
            $result=Get-HmsNativeCircuitBreakerObject
        }
        elseif($BackendAction -eq "evaluate_circuit_breaker"){
            $d=Invoke-HmsCircuitBreaker "evaluate"
            $result=@{ok=$true;version=$script:Version;circuit_breaker=$d;message="Circuit Breaker đã phân loại lỗi và tính trạng thái CLOSED/OPEN/HALF_OPEN; chưa đổi auth khi OBSERVE."}
        }
        elseif($BackendAction -eq "apply_circuit_breaker"){
            $d=Invoke-HmsCircuitBreaker "apply"
            $result=@{ok=$true;version=$script:Version;circuit_breaker=$d;message="Circuit Breaker đã áp dụng quarantine bằng disabled flag có readback; không đổi token/endpoint/session."}
        }
        elseif($BackendAction -eq "reset_circuit_breaker"){
            $d=Invoke-HmsCircuitBreaker "reset"
            $result=@{ok=$true;version=$script:Version;circuit_breaker=$d;message="Đã reset circuit-owned quarantine và khôi phục disabled state trước đó; không xóa credential."}
        }
        elseif($BackendAction -eq "get_predictive_quota"){
            $result=Get-HmsNativePredictiveQuotaObject
        }
        elseif($BackendAction -eq "evaluate_predictive_quota"){
            $d=Invoke-HmsPredictiveQuota "evaluate"
            $result=@{ok=$true;version=$script:Version;predictive_quota=$d;message="Predictive Quota đã cập nhật velocity/runway/risk; forecast không thay thế quota live và không sửa credential."}
        }
        elseif($BackendAction -eq "get_quota_center"){
            $result=Get-HmsNativeQuotaCenterObject
        }
        elseif($BackendAction -eq "sync_quota_center"){
            $d=Invoke-HmsQuotaCenter "sync"
            $result=@{ok=$true;version=$script:Version;quota_center=$d;message="Advanced Quota Center đã đồng bộ lịch sử, freshness, reset timeline và forecast accuracy."}
        }
        elseif($BackendAction -eq "get_account_analytics"){
            $result=Get-HmsNativeAccountAnalyticsObject $false
        }
        elseif($BackendAction -eq "sync_account_analytics"){
            $result=Get-HmsNativeAccountAnalyticsObject $true
            $result["message"]="Account Analytics đã cập nhật quality score, model/workload profile và bounded Router signal."
        }
        elseif($BackendAction -eq "update_status"){
            $result=Get-HmsNativeUpdateObject
        }
        elseif($BackendAction -eq "update_check"){
            $d=Invoke-HmsUpdateChannel "check"
            $result=@{ok=$true;version=$script:Version;update=$d;message=[string]$d.message}
        }
        elseif($BackendAction -eq "update_stage"){
            $d=Invoke-HmsUpdateChannel "stage"
            $result=@{ok=$true;version=$script:Version;update=$d;message="Update đã tải + SHA + chữ ký + manifest PASS và đang ở STAGED. Chưa kích hoạt."}
        }
        elseif($BackendAction -eq "update_activate"){
            $d=Invoke-HmsUpdateChannel "activate"
            $result=@{ok=$true;version=$script:Version;update=$d;message="Đã kích hoạt release STAGED bằng ACTIVE pointer; PREV vẫn được giữ."}
        }
        elseif($BackendAction -eq "get_instances"){
            $result=Get-HmsNativeCodexInstancesObject
        }
        elseif($BackendAction -eq "create_instance"){
            $result=New-HmsNativeCodexInstance
        }
        elseif($BackendAction -eq "start_instance"){
            $result=Invoke-HmsNativeCodexInstanceAction "start"
        }
        elseif($BackendAction -eq "stop_instance"){
            $result=Invoke-HmsNativeCodexInstanceAction "stop"
        }
        elseif($BackendAction -eq "restart_instance"){
            $result=Invoke-HmsNativeCodexInstanceAction "restart"
        }
        elseif($BackendAction -eq "focus_instance"){
            $result=Invoke-HmsNativeCodexInstanceAction "focus"
        }
        elseif($BackendAction -eq "audit_identity"){
            $d=Invoke-CodexIdentityAudit -WriteFingerprint $true
            $result=Get-HmsNativeCodexInstancesObject
            $result['identity_audit']=$d
            $result['message']='Isolation Audit v25.36 hoàn tất; fingerprint đã được refresh cho các instance hợp lệ.'
        }
        elseif($BackendAction -eq "get_project_affinity"){
            $result=Get-HmsNativeProjectAffinityObject
        }
        elseif($BackendAction -eq "save_project_affinity"){
            $result=Save-HmsNativeProjectAffinity
        }
        elseif($BackendAction -eq "launch_project_affinity"){
            $result=Launch-HmsNativeProjectAffinity
        }
        elseif($BackendAction -eq "sync_project_router"){
            $result=Sync-HmsNativeProjectRouter
        }
        elseif($BackendAction -eq "get_project_orchestrator"){
            $result=Get-HmsNativeProjectOrchestratorObject
        }
        elseif($BackendAction -eq "preflight_project_orchestrator"){
            $result=Preflight-HmsNativeProjectOrchestrator
        }
        elseif($BackendAction -eq "launch_project_orchestrator"){
            $result=Launch-HmsNativeProjectOrchestrator
        }
        elseif($BackendAction -eq "get_multi_codex_team"){
            $result=Get-HmsNativeMultiCodexTeamObject
        }
        elseif($BackendAction -eq "save_multi_codex_team"){
            $result=Save-HmsNativeMultiCodexTeam
        }
        elseif($BackendAction -eq "preflight_multi_codex_team"){
            $result=Preflight-HmsNativeMultiCodexTeam
        }
        elseif($BackendAction -eq "launch_multi_codex_team"){
            $result=Launch-HmsNativeMultiCodexTeam
        }
        elseif($BackendAction -eq "get_model_manager"){
            $result=Get-HmsNativeModelManagerObject
        }
        elseif($BackendAction -eq "discover_models"){
            $d=Invoke-HmsModelManager -Mode "discover";$result=@{ok=$true;version=$script:Version;model_manager=$d;message="Đã quét model từ Router đang online."}
        }
        elseif($BackendAction -eq "save_model_policy"){
            $result=Save-HmsNativeModelPolicy
        }
        elseif($BackendAction -eq "apply_model_policy"){
            $result=Apply-HmsNativeModelPolicy
        }
        elseif($BackendAction -eq "get_lan_pool"){
            $result=Get-HmsNativeLanPoolObject
        }
        elseif($BackendAction -eq "pair_lan_pool"){
            $result=Pair-HmsNativeLanPool
        }
        elseif($BackendAction -eq "heartbeat_lan_pool"){
            $result=Invoke-HmsNativeLanPoolHeartbeat
        }
        elseif($BackendAction -eq "acquire_lan_project"){
            $result=Invoke-HmsNativeLanProjectLease -Mode 'acquire'
        }
        elseif($BackendAction -eq "release_lan_project"){
            $result=Invoke-HmsNativeLanProjectLease -Mode 'release'
        }
        elseif($BackendAction -eq "get_smart_model_router"){
            $result=Get-HmsNativeSmartModelRouterObject
        }
        elseif($BackendAction -eq "evaluate_smart_model_router"){
            $result=Evaluate-HmsNativeSmartModelRouter
        }
        elseif($BackendAction -eq "apply_smart_model_router"){
            $result=Apply-HmsNativeSmartModelRouter
        }
        elseif($BackendAction -eq "rollback_smart_model_router"){
            $result=Rollback-HmsNativeSmartModelRouter
        }
        elseif($BackendAction -eq "get_api_compatibility"){
            $result=Get-HmsNativeApiCompatibilityObject
        }
        elseif($BackendAction -eq "run_api_compatibility"){
            $d=Invoke-HmsApiCompatibilityAudit
            $result=Get-HmsNativeApiCompatibilityObject
            $result['api_compatibility']=$d
            $result['message']='API Compatibility v25.38 synthetic audit hoàn tất; Windows Codex runtime vẫn deferred.'
        }
        elseif($BackendAction -eq "get_self_healing"){
            $result=Get-HmsNativeSelfHealingObject
        }
        elseif($BackendAction -eq "audit_self_healing"){
            $d=Invoke-HmsSelfHealing 'audit';$result=@{ok=$true;version=$script:Version;self_healing=$d;message='Self-Healing audit hoàn tất; không sửa process/config khi chỉ AUDIT.'}
        }
        elseif($BackendAction -eq "repair_self_healing"){
            $d=Invoke-HmsSelfHealing 'repair';$result=@{ok=$true;version=$script:Version;self_healing=$d;message='Self-Healing đã áp dụng các repair an toàn có evidence + readback; process không chứng minh ownership không bị kill.'}
        }
        elseif($BackendAction -eq "get_security"){
            $result=Get-HmsNativeSecurityObject
        }
        elseif($BackendAction -eq "audit_security"){
            $d=Invoke-HmsSecurityHardening 'audit';$result=@{ok=$true;version=$script:Version;security=$d;message='Security Audit v25.40 hoàn tất; không sửa secret/ACL/seal khi chỉ AUDIT.'}
        }
        elseif($BackendAction -eq "harden_security"){
            $d=Invoke-HmsSecurityHardening 'harden';$result=@{ok=$true;version=$script:Version;security=$d;message='Security Hardening đã migrate protected secret refs, harden ACL và tạo missing seals; mismatch không bị auto-reseal.'}
        }
        elseif($BackendAction -eq "seal_security"){
            $d=Invoke-HmsSecurityHardening 'seal';$result=@{ok=$true;version=$script:Version;security=$d;message='Integrity baseline đã được RESEAL theo xác nhận operator.'}
        }
        elseif($BackendAction -eq "get_unified_diagnostics"){
            $result=Get-HmsNativeUnifiedDiagnosticsObject
        }
        elseif($BackendAction -eq "refresh_unified_diagnostics"){
            $d=Invoke-HmsUnifiedDiagnostics 'refresh';$result=@{ok=$true;version=$script:Version;unified_diagnostics=$d;message='Unified Diagnostics v25.41 đã hợp nhất request/router/quota/circuit/self-healing/security metadata vào một timeline; không lưu prompt/request body/secret.'}
        }
        elseif($BackendAction -eq "enable"){
            Set-HmsBackendOneClickPolicy

            if(-not (Test-Path $script:ProxyExe)){
                foreach($candidate in @("C:\CLIProxyAPI",(Join-Path $env:LOCALAPPDATA "CLIProxyAPI"),(Join-Path $env:USERPROFILE "CLIProxyAPI"))){
                    if(Test-Path (Join-Path $candidate "cli-proxy-api.exe")){
                        $script:S.ProxyDir=$candidate
                        Save-Settings
                        Refresh-Paths
                        break
                    }
                }
            }
            if(-not (Test-Path $script:ProxyExe)){throw "Không tìm thấy cli-proxy-api.exe."}

            $pool=Get-CodexPoolSummary
            if([int]$pool.Total -lt 1){throw "Chưa có tài khoản Codex. Mở Quản lý từ nút ⚙ để thêm tài khoản trước."}
            if([int]$pool.Ready -lt 1){throw "Không có tài khoản Codex READY."}

            $port=Select-HmsBackendSafePort
            $null=Enable-HmsMode

            $listener=ListenerPid ([int]$script:S.ProxyPort)
            if($listener -le 0 -or -not (IsOurProxy $listener)){throw "VERIFY_FAIL: Router HMS chưa ONLINE."}
            if(-not (CodexInHmsMode)){throw "VERIFY_FAIL: Codex chưa ở hms_api_router."}
            $api=Test-ApiModels
            if(-not $api.Ok){throw "VERIFY_FAIL: /v1/models HTTP=$($api.Status); $($api.Error)"}

            $result=Get-HmsBackendStatusObject
            $result["message"]="HMS READY · port $port · API HTTP $($api.Status)"
        }
        elseif($BackendAction -eq "disable"){
            Set-HmsBackendOneClickPolicy
            $null=Disable-HmsMode
            if(CodexInHmsMode){throw "VERIFY_FAIL: Codex vẫn ở HMS provider sau disable."}
            $listener=ListenerPid ([int]$script:S.ProxyPort)
            if($listener -gt 0 -and (IsOurProxy $listener)){throw "VERIFY_FAIL: Router HMS vẫn còn listener."}
            $result=Get-HmsBackendStatusObject
            $result["message"]="HMS đã tắt và restore cấu hình Codex."
        }
        elseif($BackendAction -eq "open_codex"){
            Set-HmsBackendOneClickPolicy
            if(-not (CodexInHmsMode)){
                throw "HMS Router chưa được bật. Bấm BẬT HMS trước."
            }
            $listener=ListenerPid ([int]$script:S.ProxyPort)
            if($listener -le 0 -or -not (IsOurProxy $listener)){
                throw "Router HMS chưa ONLINE."
            }
            $message=Open-CodexClient
            if(@(Get-CodexClientProcesses).Count -lt 1){
                throw "Không xác nhận được Codex/ChatGPT Desktop đã mở."
            }
            $result=Get-HmsBackendStatusObject
            $result["message"]="Codex đã được mở bằng HMS Router."
        }
    }catch{
        $safe=Redact-LocalApiText ([string]$_.Exception.Message)
        $result=@{ok=$false;version=$script:Version;action=$BackendAction;error=$safe}
    }
    Write-HmsBackendResult $result
    if($result.ok){exit 0}else{exit 2}
}

# ============================================================
# UI
# ============================================================

Load-Settings
Initialize-HmsSecuritySecretMigration
$script:PowerShellStartupAudit=$null
if([bool]$script:S.PowerShellStaticAuditOnStartup){
    try{
        $script:PowerShellStartupAudit=Invoke-HmsPowerShellSourceAudit
    }catch{
        if([bool]$script:S.PowerShellStaticAuditBlockAutomation){$script:RuntimeAutomationBlocked=$true}
        $script:PowerShellStartupAudit=[PSCustomObject]@{verdict="BLOCKED";error=$_.Exception.Message}
    }
}
$script:ProductionStartup = Initialize-HmsProductionRuntime
if([bool]$script:S.ReleasePreflightOnStartup){try{$null=Invoke-HmsReleaseManager "preflight"}catch{}}

$form=New-Object Windows.Forms.Form
$form.Text="HMS-AI-ROUTER v$($script:Version)"
$form.Size=New-Object Drawing.Size(1060,970)
$form.StartPosition="CenterScreen"
$form.BackColor=[Drawing.Color]::FromArgb(17,19,23)
$form.ForeColor=[Drawing.Color]::FromArgb(236,239,244)
$form.Font=New-Object Drawing.Font("Segoe UI",10)
$form.FormBorderStyle="FixedDialog";$form.MaximizeBox=$false

$title=New-Object Windows.Forms.Label;$title.Text="HMS-AI-ROUTER — RUNTIME HARDENED";$title.Font=New-Object Drawing.Font("Segoe UI Semibold",22);$title.AutoSize=$true;$title.Location=New-Object Drawing.Point(28,16);$form.Controls.Add($title)
$sub=New-Object Windows.Forms.Label;$sub.Text="Source Gate · Unified UX · Policy Kernel · HA · Fleet · Safe Recovery";$sub.AutoSize=$true;$sub.ForeColor=[Drawing.Color]::FromArgb(153,164,178);$sub.Location=New-Object Drawing.Point(31,61);$form.Controls.Add($sub)

$g=New-Object Windows.Forms.GroupBox;$g.Text="TỔNG QUAN";$g.Location=New-Object Drawing.Point(28,93);$g.Size=New-Object Drawing.Size(985,152);$g.ForeColor=$form.ForeColor;$form.Controls.Add($g)
$lMode=New-Object Windows.Forms.Label;$lMode.Location=New-Object Drawing.Point(18,29);$lMode.AutoSize=$true;$g.Controls.Add($lMode)
$lProxy=New-Object Windows.Forms.Label;$lProxy.Location=New-Object Drawing.Point(18,57);$lProxy.AutoSize=$true;$g.Controls.Add($lProxy)
$lAg=New-Object Windows.Forms.Label;$lAg.Location=New-Object Drawing.Point(18,85);$lAg.AutoSize=$true;$g.Controls.Add($lAg)
$lAcc=New-Object Windows.Forms.Label;$lAcc.Location=New-Object Drawing.Point(18,112);$lAcc.AutoSize=$true;$g.Controls.Add($lAcc)
$lLast=New-Object Windows.Forms.Label;$lLast.Location=New-Object Drawing.Point(485,29);$lLast.Size=New-Object Drawing.Size(480,92);$lLast.ForeColor=[Drawing.Color]::FromArgb(153,164,178);$g.Controls.Add($lLast)

function Btn([string]$txt,[int]$x,[int]$y,[int]$w=280,[int]$h=44){
    $b=New-Object Windows.Forms.Button;$b.Text=$txt;$b.Location=New-Object Drawing.Point($x,$y);$b.Size=New-Object Drawing.Size($w,$h);$b.FlatStyle="Flat";$b.BackColor=[Drawing.Color]::FromArgb(42,46,54);$b.ForeColor=$form.ForeColor;$b.FlatAppearance.BorderColor=[Drawing.Color]::FromArgb(72,80,91);return $b
}

$bOn=Btn "▶ BẬT CODEX API ROUTER" 28 262 475 56;$bOn.BackColor=[Drawing.Color]::FromArgb(39,96,73);$form.Controls.Add($bOn)
$bOff=Btn "■ TẮT ROUTER / VỀ COCKPIT" 538 262 475 56;$bOff.BackColor=[Drawing.Color]::FromArgb(104,56,56);$form.Controls.Add($bOff)
$bVerify=Btn "✓ XÁC MINH CODEX API" 28 333 230 44;$form.Controls.Add($bVerify)
$bAccounts=Btn "UNIFIED COMMAND CENTER" 277 333 230 44;$bAccounts.BackColor=[Drawing.Color]::FromArgb(42,74,96);$form.Controls.Add($bAccounts)
$bMgmt=Btn "QUẢN LÝ / QUOTA" 526 333 230 44;$form.Controls.Add($bMgmt)
$bDiag=Btn "CODEX DIAGNOSTICS" 775 333 238 44;$form.Controls.Add($bDiag)

$gc=New-Object Windows.Forms.GroupBox;$gc.Text="CODEX — ƯU TIÊN";$gc.Location=New-Object Drawing.Point(28,395);$gc.Size=New-Object Drawing.Size(475,170);$gc.ForeColor=$form.ForeColor;$form.Controls.Add($gc)
$lc=New-Object Windows.Forms.Label;$lc.Location=New-Object Drawing.Point(18,29);$lc.AutoSize=$true;$gc.Controls.Add($lc)
$bcAdd=Btn "＋ THÊM CODEX ACC" 18 58 205 42;$gc.Controls.Add($bcAdd)
$bcOpen=Btn "MỞ CODEX" 240 58 215 42;$gc.Controls.Add($bcOpen)
$bcVerify=Btn "TEST /v1/models" 18 112 132 36;$gc.Controls.Add($bcVerify)
$bcPool=Btn "SMART POOL" 158 112 132 36;$gc.Controls.Add($bcPool)
$bcDiag=Btn "DIAG" 298 112 72 36;$gc.Controls.Add($bcDiag)
$bRestart=Btn "RESTART" 378 112 77 36;$gc.Controls.Add($bRestart)

$ga=New-Object Windows.Forms.GroupBox;$ga.Text="ANTIGRAVITY 2.0 — PHỤ / GIỮ ỔN ĐỊNH";$ga.Location=New-Object Drawing.Point(538,395);$ga.Size=New-Object Drawing.Size(475,170);$ga.ForeColor=$form.ForeColor;$form.Controls.Add($ga)
$la=New-Object Windows.Forms.Label;$la.Location=New-Object Drawing.Point(18,27);$la.AutoSize=$true;$ga.Controls.Add($la)
$lBridge=New-Object Windows.Forms.Label;$lBridge.Location=New-Object Drawing.Point(18,50);$lBridge.Size=New-Object Drawing.Size(435,22);$lBridge.ForeColor=[Drawing.Color]::FromArgb(153,164,178);$ga.Controls.Add($lBridge)
$baInstall=Btn "CÀI HMS BRIDGE" 18 78 135 36;$ga.Controls.Add($baInstall)
$baTest=Btn "TEST BRIDGE" 164 78 130 36;$ga.Controls.Add($baTest)
$baOpen=Btn "MỞ ANTIGRAVITY" 305 78 150 36;$ga.Controls.Add($baOpen)
$baAdd=Btn "＋ THÊM AG ACC" 18 121 205 30;$ga.Controls.Add($baAdd)
$baAccounts=Btn "AG SMART POOL" 240 121 215 30;$ga.Controls.Add($baAccounts)

$gs=New-Object Windows.Forms.GroupBox;$gs.Text="THIẾT LẬP — CODEX FIRST";$gs.Location=New-Object Drawing.Point(28,585);$gs.Size=New-Object Drawing.Size(985,290);$gs.ForeColor=$form.ForeColor;$form.Controls.Add($gs)
$ld=New-Object Windows.Forms.Label;$ld.Text="CLIProxyAPI:";$ld.Location=New-Object Drawing.Point(18,29);$ld.AutoSize=$true;$gs.Controls.Add($ld)
$td=New-Object Windows.Forms.TextBox;$td.Text=[string]$script:S.ProxyDir;$td.Location=New-Object Drawing.Point(110,25);$td.Size=New-Object Drawing.Size(520,26);$gs.Controls.Add($td)
$lp=New-Object Windows.Forms.Label;$lp.Text="Port:";$lp.Location=New-Object Drawing.Point(650,29);$lp.AutoSize=$true;$gs.Controls.Add($lp)
$np=New-Object Windows.Forms.NumericUpDown;$np.Minimum=1024;$np.Maximum=65535;$np.Value=[int]$script:S.ProxyPort;$np.Location=New-Object Drawing.Point(695,25);$np.Size=New-Object Drawing.Size(90,26);$gs.Controls.Add($np)
$bSave=Btn "LƯU" 815 22 140 33;$gs.Controls.Add($bSave)

$chRestore=New-Object Windows.Forms.CheckBox;$chRestore.Text="TẮT Router → khôi phục Codex config/.env trước đó";$chRestore.Checked=[bool]$script:S.RestoreOnDisable;$chRestore.Location=New-Object Drawing.Point(20,66);$chRestore.AutoSize=$true;$chRestore.ForeColor=$form.ForeColor;$gs.Controls.Add($chRestore)
$chRestart=New-Object Windows.Forms.CheckBox;$chRestart.Text="Restart Codex khi chuyển Router";$chRestart.Checked=[bool]$script:S.RestartCodexOnSwitch;$chRestart.Location=New-Object Drawing.Point(470,66);$chRestart.AutoSize=$true;$chRestart.ForeColor=$form.ForeColor;$gs.Controls.Add($chRestart)
$chForce=New-Object Windows.Forms.CheckBox;$chForce.Text="Cho phép force-close app nếu không đóng được";$chForce.Checked=[bool]$script:S.ForceCloseIfNeeded;$chForce.Location=New-Object Drawing.Point(20,98);$chForce.AutoSize=$true;$chForce.ForeColor=$form.ForeColor;$gs.Controls.Add($chForce)
$chOpen=New-Object Windows.Forms.CheckBox;$chOpen.Text="BẬT Router → mở Codex";$chOpen.Checked=[bool]$script:S.OpenCodexOnEnable;$chOpen.Location=New-Object Drawing.Point(470,98);$chOpen.AutoSize=$true;$chOpen.ForeColor=$form.ForeColor;$gs.Controls.Add($chOpen)


$lCodexProfile=New-Object Windows.Forms.Label;$lCodexProfile.Text="Codex routing:";$lCodexProfile.Location=New-Object Drawing.Point(20,137);$lCodexProfile.AutoSize=$true;$gs.Controls.Add($lCodexProfile)
$cCodexProfile=New-Object Windows.Forms.ComboBox;$cCodexProfile.DropDownStyle="DropDownList";$cCodexProfile.Location=New-Object Drawing.Point(120,133);$cCodexProfile.Size=New-Object Drawing.Size(350,28)
[void]$cCodexProfile.Items.Add("ỔN ĐỊNH — round-robin + session affinity")
[void]$cCodexProfile.Items.Add("CHIA ĐỀU — round-robin, không sticky")
[void]$cCodexProfile.Items.Add("DÙNG HẾT TỪNG ACC — fill-first + sticky")
switch(([string]$script:S.CodexRoutingProfile).ToLowerInvariant()){"balanced"{$cCodexProfile.SelectedIndex=1}"fill-first"{$cCodexProfile.SelectedIndex=2}default{$cCodexProfile.SelectedIndex=0}}
$gs.Controls.Add($cCodexProfile)
$chCodexWatch=New-Object Windows.Forms.CheckBox;$chCodexWatch.Text="Codex Watchdog tự phục hồi Router";$chCodexWatch.Checked=[bool]$script:S.CodexWatchdogEnabled;$chCodexWatch.Location=New-Object Drawing.Point(500,136);$chCodexWatch.AutoSize=$true;$chCodexWatch.ForeColor=$form.ForeColor;$gs.Controls.Add($chCodexWatch)
$chCodexOptimize=New-Object Windows.Forms.CheckBox;$chCodexOptimize.Text="Optimize multi-agent v2";$chCodexOptimize.Checked=[bool]$script:S.CodexOptimizeMultiAgentV2;$chCodexOptimize.Location=New-Object Drawing.Point(770,136);$chCodexOptimize.AutoSize=$true;$chCodexOptimize.ForeColor=$form.ForeColor;$gs.Controls.Add($chCodexOptimize)

$chSeam=New-Object Windows.Forms.CheckBox;$chSeam.Text="AG Seamless — không restart app";$chSeam.Checked=[bool]$script:S.AgSeamlessEnabled;$chSeam.Location=New-Object Drawing.Point(20,191);$chSeam.AutoSize=$true;$chSeam.ForeColor=$form.ForeColor;$gs.Controls.Add($chSeam)
$chFallback=New-Object Windows.Forms.CheckBox;$chFallback.Text="AG fallback restart nếu seamless lỗi";$chFallback.Checked=[bool]$script:S.AgFallbackRestart;$chFallback.Location=New-Object Drawing.Point(300,191);$chFallback.AutoSize=$true;$chFallback.ForeColor=$form.ForeColor;$gs.Controls.Add($chFallback)
$chAutoAg=New-Object Windows.Forms.CheckBox;$chAutoAg.Text="AG tự chuyển khi quota thấp/cooldown";$chAutoAg.Checked=[bool]$script:S.AgAutoSwitchEnabled;$chAutoAg.Location=New-Object Drawing.Point(590,191);$chAutoAg.AutoSize=$true;$chAutoAg.ForeColor=$form.ForeColor;$gs.Controls.Add($chAutoAg)
$lThreshold=New-Object Windows.Forms.Label;$lThreshold.Text="Ngưỡng AG:";$lThreshold.Location=New-Object Drawing.Point(20,232);$lThreshold.AutoSize=$true;$gs.Controls.Add($lThreshold)
$nThreshold=New-Object Windows.Forms.NumericUpDown;$nThreshold.Minimum=0;$nThreshold.Maximum=100;$nThreshold.Value=[int]$script:S.AgAutoSwitchThreshold;$nThreshold.Location=New-Object Drawing.Point(105,228);$nThreshold.Size=New-Object Drawing.Size(70,26);$gs.Controls.Add($nThreshold)
$lPct=New-Object Windows.Forms.Label;$lPct.Text="% (chỉ kích hoạt theo quota khi metadata có số; cooldown/token lỗi vẫn kích hoạt)";$lPct.Location=New-Object Drawing.Point(180,232);$lPct.AutoSize=$true;$lPct.ForeColor=[Drawing.Color]::FromArgb(153,164,178);$gs.Controls.Add($lPct)
$bRecoverAg=Btn "CỨU PHIÊN AG" 490 169 190 34;$gs.Controls.Add($bRecoverAg)
$bRestoreAg=Btn "KHÔI PHỤC CREDENTIAL GỐC" 695 169 260 34;$gs.Controls.Add($bRestoreAg)

$foot=New-Object Windows.Forms.Label;$foot.Text="HMS v25.43 MULTI-CODEX TEAM: Coder / Reviewer / Tester run in isolated managed workspaces; no silent takeover; Security and identity remain hard gates.";$foot.Location=New-Object Drawing.Point(31,892);$foot.Size=New-Object Drawing.Size(975,42);$foot.ForeColor=[Drawing.Color]::FromArgb(132,143,156);$form.Controls.Add($foot)

function Save-UI{
    if([bool]$script:OneClickMode){
        Save-Settings
        return
    }
    $script:S.ProxyDir=$td.Text.Trim();$script:S.ProxyPort=[int]$np.Value;$script:S.RestoreOnDisable=[bool]$chRestore.Checked;$script:S.RestartCodexOnSwitch=[bool]$chRestart.Checked;$script:S.ForceCloseIfNeeded=[bool]$chForce.Checked;$script:S.OpenCodexOnEnable=[bool]$chOpen.Checked
    switch($cCodexProfile.SelectedIndex){1{$script:S.CodexRoutingProfile="balanced"}2{$script:S.CodexRoutingProfile="fill-first"}default{$script:S.CodexRoutingProfile="stable"}}
    $script:S.CodexWatchdogEnabled=[bool]$chCodexWatch.Checked;$script:S.CodexOptimizeMultiAgentV2=[bool]$chCodexOptimize.Checked
    $script:S.AgSeamlessEnabled=[bool]$chSeam.Checked;$script:S.AgFallbackRestart=[bool]$chFallback.Checked;$script:S.AgAutoSwitchEnabled=[bool]$chAutoAg.Checked;$script:S.AgAutoSwitchThreshold=[int]$nThreshold.Value
    Save-Settings
}
function Status([string]$msg=""){
    $port=[int]$script:S.ProxyPort;$id=ListenerPid $port
    if(CodexInHmsMode){$lMode.Text="CODEX: ● API MODE → HMS ROUTER";$lMode.ForeColor=[Drawing.Color]::FromArgb(95,207,145)}else{$lMode.Text="CODEX: ○ COCKPIT / DIRECT / CONFIG KHÁC";$lMode.ForeColor=[Drawing.Color]::FromArgb(235,191,95)}
    if($id -gt 0){if(IsOurProxy $id){$lProxy.Text="ROUTER: ● ONLINE  PID $id  127.0.0.1:$port";$lProxy.ForeColor=[Drawing.Color]::FromArgb(95,207,145)}else{$lProxy.Text="PORT ${port}: ● DỊCH VỤ KHÁC PID $id — KHÔNG CAN THIỆP";$lProxy.ForeColor=[Drawing.Color]::FromArgb(235,191,95)}}else{$lProxy.Text="ROUTER: ○ OFFLINE  port $port";$lProxy.ForeColor=[Drawing.Color]::FromArgb(235,120,108)}
    $bridge=Test-HmsAntigravityBridge;$active=Get-AgActiveAccountFromBridge
    $activeText=if($active){$active.Email}elseif($script:S.AgCurrentEmail){[string]$script:S.AgCurrentEmail}else{"chưa xác định"}
    $activeHealth=if($active){Get-AgAccountHealth $active}else{$null}
    $healthText=if($activeHealth){" — score "+[string]$activeHealth.Score}else{""}
    if($bridge.Ok){$lAg.Text="ANTIGRAVITY: ● SEAMLESS READY — $activeText$healthText";$lAg.ForeColor=[Drawing.Color]::FromArgb(95,207,145)}else{$lAg.Text="ANTIGRAVITY: ○ BRIDGE CHƯA READY — $activeText";$lAg.ForeColor=[Drawing.Color]::FromArgb(235,191,95)}
    $cp=Get-CodexPoolSummary;$lAcc.Text="CODEX POOL: $($cp.Total) ACC · READY $($cp.Ready) · COOLDOWN $($cp.Cooldown) · FREE $($cp.Free)  |  AG $(AuthCount 'antigravity-') ACC";$lc.Text="Pool: $(AuthCount 'codex-') OAuth ACC  |  "+(Get-CodexRoutingDescription);$la.Text="OAuth accounts: $(AuthCount 'antigravity-')";$lBridge.Text=$bridge.Message
    if($msg){$lLast.Text=$msg}elseif(-not $lLast.Text){$lLast.Text="Sẵn sàng."}
    [Windows.Forms.Application]::DoEvents()
}
function Err([string]$m){[Windows.Forms.MessageBox]::Show($m,"HMS-AI-ROUTER",[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Error)|Out-Null}

$bSave.Add_Click({try{Save-UI;Status "Đã lưu thiết lập."}catch{Err $_.Exception.Message}})
$bOn.Add_Click({try{Save-UI;$form.Cursor=[Windows.Forms.Cursors]::WaitCursor;Status "Đang bật Codex API Router...";$m=Enable-HmsMode;Status $m}catch{Status("LỖI: "+$_.Exception.Message);Err $_.Exception.Message}finally{$form.Cursor=[Windows.Forms.Cursors]::Default}})
$bOff.Add_Click({try{Save-UI;$form.Cursor=[Windows.Forms.Cursors]::WaitCursor;Status "Đang về Cockpit/direct...";$m=Disable-HmsMode;Status $m}catch{Status("LỖI: "+$_.Exception.Message);Err $_.Exception.Message}finally{$form.Cursor=[Windows.Forms.Cursors]::Default}})
$bVerify.Add_Click({try{Save-UI;$v=Verify-Mode;[Windows.Forms.MessageBox]::Show($v,"Xác minh Codex API Router")|Out-Null;Status "Đã xác minh Codex API."}catch{Err $_.Exception.Message}})
$bAccounts.Add_Click({try{Show-CodexUnifiedCommandCenter;Status "Đã đóng Unified Command Center."}catch{Err $_.Exception.Message}})
$bMgmt.Add_Click({try{if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."};Start-Process ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/management.html")|Out-Null;Status "Đã mở Management Center."}catch{Err $_.Exception.Message}})
$bDiag.Add_Click({try{[Windows.Forms.MessageBox]::Show((Get-CodexDiagnosticsText),"HMS Codex Diagnostics")|Out-Null;Status "Codex diagnostics hoàn tất."}catch{Err $_.Exception.Message}})
$bRestart.Add_Click({try{Save-UI;Status(Restart-Router)}catch{Err $_.Exception.Message}})
$bcAdd.Add_Click({try{Login-Provider "--codex-login";Status "Đã mở Codex OAuth."}catch{Err $_.Exception.Message}})
$bcOpen.Add_Click({try{Status(Open-CodexClient)}catch{Err $_.Exception.Message}})
$bcVerify.Add_Click({try{$r=Test-ApiModels;if($r.Ok){[Windows.Forms.MessageBox]::Show("PASS — $($r.Count) models","Codex API")|Out-Null}else{throw $r.Error}}catch{Err $_.Exception.Message}})
$bcPool.Add_Click({try{Show-CodexSmartPool;Status "Đã đóng Codex Smart Pool."}catch{Err $_.Exception.Message}})
$bcDiag.Add_Click({try{[Windows.Forms.MessageBox]::Show((Get-CodexDiagnosticsText),"HMS Codex Diagnostics")|Out-Null}catch{Err $_.Exception.Message}})
$baInstall.Add_Click({try{$form.Cursor=[Windows.Forms.Cursors]::WaitCursor;$m=Install-HmsAntigravityBridge;Status $m;[Windows.Forms.MessageBox]::Show($m,"HMS AG Bridge")|Out-Null}catch{Err $_.Exception.Message}finally{$form.Cursor=[Windows.Forms.Cursors]::Default}})
$baTest.Add_Click({$r=Test-HmsAntigravityBridge;[Windows.Forms.MessageBox]::Show($r.Message,"HMS AG Bridge")|Out-Null;Status $r.Message})
$baOpen.Add_Click({try{Status(Start-AntigravityDesktop)}catch{Err $_.Exception.Message}})
$baAdd.Add_Click({try{Login-Provider "--antigravity-login";Status "Đã mở Antigravity OAuth của CLIProxyAPI."}catch{Err $_.Exception.Message}})
$baAccounts.Add_Click({try{Show-AgSmartPool;Status "Đã đóng AG Smart Pool."}catch{Err $_.Exception.Message}})
$bRestoreAg.Add_Click({try{$m=Restore-AntigravityCredentialBackup;[Windows.Forms.MessageBox]::Show($m,"Antigravity Credential")|Out-Null;Status $m}catch{Err $_.Exception.Message}})
$bRecoverAg.Add_Click({try{$m=Recover-AntigravitySession;[Windows.Forms.MessageBox]::Show($m,"HMS AG Recovery")|Out-Null;Status $m}catch{Err $_.Exception.Message}})



# ============================================================
# ============================================================
# v25.43 MULTI-CODEX TEAM + PROJECT ORCHESTRATOR + UNIFIED DIAGNOSTICS + SECURITY HARDENING + SELF-HEALING + API COMPATIBILITY + ROUTING UX SHELL
$script:OneClickMode=$true
$script:OneClickBusy=$false
# Daily operation exposes one primary action only: BẬT HMS / TẮT HMS.
# Routing, API handshake, Codex reload, watchdog and rollback stay automatic.
# ============================================================

function Set-HmsUxRoundedRegion {
    param([Windows.Forms.Control]$Control,[int]$Radius=12)
    if(-not $Control){return}
    try{
        $path=New-Object Drawing.Drawing2D.GraphicsPath
        $r=[Math]::Max(2,$Radius)
        $d=$r*2
        $rect=New-Object Drawing.Rectangle(0,0,$Control.Width-1,$Control.Height-1)
        $path.AddArc($rect.X,$rect.Y,$d,$d,180,90)
        $path.AddArc($rect.Right-$d,$rect.Y,$d,$d,270,90)
        $path.AddArc($rect.Right-$d,$rect.Bottom-$d,$d,$d,0,90)
        $path.AddArc($rect.X,$rect.Bottom-$d,$d,$d,90,90)
        $path.CloseFigure()
        $Control.Region=New-Object Drawing.Region($path)
        $path.Dispose()
    }catch{}
}

function New-HmsUxButton {
    param(
        [string]$Text,[int]$X,[int]$Y,[int]$W,[int]$H,
        [Drawing.Color]$Back=[Drawing.Color]::FromArgb(35,40,47),
        [Drawing.Color]$Hover=[Drawing.Color]::FromArgb(45,52,61),
        [Drawing.Color]$Fore=[Drawing.Color]::FromArgb(235,240,246)
    )
    $b=New-Object Windows.Forms.Button
    $b.Text=$Text
    $b.Location=New-Object Drawing.Point($X,$Y)
    $b.Size=New-Object Drawing.Size($W,$H)
    $b.FlatStyle="Flat"
    $b.FlatAppearance.BorderSize=0
    $b.BackColor=$Back
    $b.ForeColor=$Fore
    $b.Font=New-Object Drawing.Font("Segoe UI Semibold",10)
    $b.Cursor=[Windows.Forms.Cursors]::Hand
    $b.Tag=[PSCustomObject]@{Normal=$Back;Hover=$Hover}
    $b.Add_MouseEnter({if($this.Enabled){$this.BackColor=$this.Tag.Hover}})
    $b.Add_MouseLeave({$this.BackColor=$this.Tag.Normal})
    $b.Add_Resize({Set-HmsUxRoundedRegion $this 10})
    Set-HmsUxRoundedRegion $b 10
    return $b
}

function Set-HmsOneClickProgress {
    param([string]$Text,[ValidateSet("normal","busy","ok","error")][string]$Kind="normal")
    try{
        $uxStatusLine.Text=$Text
        switch($Kind){
            "busy" {$uxStatusLine.ForeColor=[Drawing.Color]::FromArgb(238,194,100)}
            "ok" {$uxStatusLine.ForeColor=[Drawing.Color]::FromArgb(106,216,157)}
            "error" {$uxStatusLine.ForeColor=[Drawing.Color]::FromArgb(238,120,112)}
            default {$uxStatusLine.ForeColor=[Drawing.Color]::FromArgb(142,153,166)}
        }
        [Windows.Forms.Application]::DoEvents()
    }catch{}
}

function Resolve-HmsOneClickProxyDir {
    Refresh-Paths
    if(Test-Path $script:ProxyExe){return [string]$script:S.ProxyDir}

    $candidates=[System.Collections.Generic.List[string]]::new()
    foreach($candidate in @(
        [string]$script:S.ProxyDir,
        "C:\CLIProxyAPI",
        (Join-Path $env:LOCALAPPDATA "CLIProxyAPI"),
        (Join-Path $env:USERPROFILE "CLIProxyAPI")
    )){
        if(-not [string]::IsNullOrWhiteSpace($candidate) -and -not $candidates.Contains($candidate)){
            $candidates.Add($candidate)
        }
    }
    foreach($candidate in $candidates){
        $exe=Join-Path $candidate "cli-proxy-api.exe"
        if(Test-Path $exe){
            $script:S.ProxyDir=$candidate
            Refresh-Paths
            Save-Settings
            return $candidate
        }
    }
    throw "Không tìm thấy CLIProxyAPI. HMS đã thử C:\CLIProxyAPI và các vị trí cục bộ chuẩn."
}

function Select-HmsOneClickSafePort {
    $current=[int]$script:S.ProxyPort
    $listener=ListenerPid $current
    if($listener -le 0 -or (IsOurProxy $listener)){return $current}

    foreach($candidate in 8318..8337){
        $candidateListener=ListenerPid $candidate
        if($candidateListener -le 0){
            $script:S.ProxyPort=$candidate
            Save-Settings
            Set-HmsOneClickProgress ("Port "+$current+" đang do Cockpit/ứng dụng khác dùng. HMS tự chuyển sang "+$candidate+".") "busy"
            return $candidate
        }
    }
    throw "Không tìm được port HMS trống trong dải 8318-8337. HMS không chiếm port của Cockpit/ứng dụng khác."
}

function Set-HmsOneClickPolicy {
    # One-click policy: user-approved automatic Codex reload and recovery.
    $script:S.RestoreOnDisable=$true
    $script:S.RestartCodexOnSwitch=$true
    $script:S.ForceCloseIfNeeded=$true
    $script:S.OpenCodexOnEnable=$true
    $script:S.CodexWatchdogEnabled=$true
    $script:S.CodexAutoRecoverRouter=$true
    # GUI-only contract: Windows taskbar minimize must remain a normal minimize.
    # Do not Hide() the main form behind the legacy minimize-to-tray behavior.
    $script:S.CodexMinimizeToTray=$false
    Save-Settings
}

function Assert-HmsOneClickAccounts {
    $pool=Get-CodexPoolSummary
    if([int]$pool.Total -lt 1){
        try{$null=Login-Provider "--codex-login"}catch{}
        throw "Chưa có tài khoản Codex. HMS đã mở đăng nhập OAuth; hoàn tất đăng nhập rồi bấm BẬT HMS lại."
    }
    if([int]$pool.Ready -lt 1){
        throw "Không có tài khoản Codex READY. Mở ⚙ → Quota/Tài khoản để kiểm tra."
    }
    return $pool
}

function Test-HmsOneClickActive {
    $port=[int]$script:S.ProxyPort
    $listener=ListenerPid $port
    return ($listener -gt 0 -and (IsOurProxy $listener) -and (CodexInHmsMode))
}

function Invoke-HmsOneClickEnable {
    Set-HmsOneClickProgress "Đang chuẩn bị HMS..." "busy"
    $null=Resolve-HmsOneClickProxyDir

    Set-HmsOneClickProgress "Đang kiểm tra tài khoản..." "busy"
    $pool=Assert-HmsOneClickAccounts

    Set-HmsOneClickProgress "Đang kiểm tra port và tránh xung đột Cockpit..." "busy"
    $port=Select-HmsOneClickSafePort

    Set-HmsOneClickProgress "Đang bật chế độ tự động..." "busy"
    Set-HmsOneClickPolicy

    Set-HmsOneClickProgress "Đang khởi động Router và kiểm tra API..." "busy"
    $message=Enable-HmsMode

    Set-HmsOneClickProgress "Đang xác minh Codex đã dùng HMS Router..." "busy"
    $listener=ListenerPid ([int]$script:S.ProxyPort)
    if($listener -le 0 -or -not (IsOurProxy $listener)){throw "ONE_CLICK_VERIFY_FAIL: Router HMS chưa ONLINE sau enable."}
    if(-not (CodexInHmsMode)){throw "ONE_CLICK_VERIFY_FAIL: Codex provider chưa ở hms_api_router."}
    $api=Test-ApiModels
    if(-not $api.Ok){throw "ONE_CLICK_VERIFY_FAIL: /v1/models HTTP=$($api.Status); $($api.Error)"}
    if(@(Get-CodexClientProcesses).Count -lt 1){
        $null=Open-CodexClient
        if(-not (Wait-CodexClientFresh 15)){throw "ONE_CLICK_VERIFY_FAIL: Codex chưa mở bằng environment mới."}
    }

    return "HMS READY · $($pool.Total) tài khoản · port $port · API $($api.Status)"
}

function Invoke-HmsOneClickDisable {
    Set-HmsOneClickProgress "Đang đóng Codex và trả cấu hình cũ..." "busy"
    Set-HmsOneClickPolicy
    $message=Disable-HmsMode
    if(CodexInHmsMode){throw "ONE_CLICK_DISABLE_VERIFY_FAIL: Codex vẫn còn provider HMS sau disable."}
    $listener=ListenerPid ([int]$script:S.ProxyPort)
    if($listener -gt 0 -and (IsOurProxy $listener)){throw "ONE_CLICK_DISABLE_VERIFY_FAIL: Router HMS vẫn còn listener."}
    return "HMS đã tắt · Codex đã về cấu hình trước HMS"
}

function Show-HmsUxSettings {
    $w=New-Object Windows.Forms.Form
    $w.Text="HMS — Cài đặt"
    $w.Size=New-Object Drawing.Size(650,470)
    $w.StartPosition="CenterParent"
    $w.BackColor=[Drawing.Color]::FromArgb(19,22,27)
    $w.ForeColor=[Drawing.Color]::FromArgb(235,240,246)
    $w.Font=New-Object Drawing.Font("Segoe UI",9.5)
    $w.FormBorderStyle="FixedDialog";$w.MaximizeBox=$false

    $h=New-Object Windows.Forms.Label
    $h.Text="CÀI ĐẶT"
    $h.Font=New-Object Drawing.Font("Segoe UI Semibold",17)
    $h.Location=New-Object Drawing.Point(24,18);$h.AutoSize=$true;$w.Controls.Add($h)

    $note=New-Object Windows.Forms.Label
    $note.Text="Hằng ngày không cần chỉnh gì ở đây. One-Click tự bật restart, force-close, mở Codex và Watchdog."
    $note.Location=New-Object Drawing.Point(26,55);$note.Size=New-Object Drawing.Size(580,42)
    $note.ForeColor=[Drawing.Color]::FromArgb(142,153,166);$w.Controls.Add($note)

    $l1=New-Object Windows.Forms.Label;$l1.Text="CLIProxyAPI";$l1.Location=New-Object Drawing.Point(26,116);$l1.AutoSize=$true;$w.Controls.Add($l1)
    $t1=New-Object Windows.Forms.TextBox;$t1.Text=[string]$script:S.ProxyDir;$t1.Location=New-Object Drawing.Point(130,112);$t1.Size=New-Object Drawing.Size(455,26);$w.Controls.Add($t1)
    $l2=New-Object Windows.Forms.Label;$l2.Text="Port";$l2.Location=New-Object Drawing.Point(26,157);$l2.AutoSize=$true;$w.Controls.Add($l2)
    $n2=New-Object Windows.Forms.NumericUpDown;$n2.Minimum=1024;$n2.Maximum=65535;$n2.Value=[int]$script:S.ProxyPort;$n2.Location=New-Object Drawing.Point(130,153);$n2.Size=New-Object Drawing.Size(110,26);$w.Controls.Add($n2)

    $lr=New-Object Windows.Forms.Label;$lr.Text="Routing";$lr.Location=New-Object Drawing.Point(26,198);$lr.AutoSize=$true;$w.Controls.Add($lr)
    $route=New-Object Windows.Forms.ComboBox;$route.DropDownStyle="DropDownList";$route.Location=New-Object Drawing.Point(130,194);$route.Size=New-Object Drawing.Size(455,28)
    [void]$route.Items.Add("ỔN ĐỊNH — round-robin + session affinity")
    [void]$route.Items.Add("CHIA ĐỀU — round-robin, không sticky")
    [void]$route.Items.Add("DÙNG HẾT TỪNG ACC — fill-first + sticky")
    $routeIndex=switch([string]$script:S.CodexRoutingProfile){"balanced"{1}"fill-first"{2}default{0}}
    $route.SelectedIndex=[int]$routeIndex
    $w.Controls.Add($route)

    $save=New-HmsUxButton "LƯU" 370 340 215 42 ([Drawing.Color]::FromArgb(30,105,78)) ([Drawing.Color]::FromArgb(37,126,94))
    $close=New-HmsUxButton "ĐÓNG" 260 340 95 42
    $w.Controls.Add($save);$w.Controls.Add($close)
    $save.Add_Click({
        try{
            $script:S.ProxyDir=$t1.Text.Trim()
            $script:S.ProxyPort=[int]$n2.Value
            $script:S.CodexRoutingProfile=switch($route.SelectedIndex){1{"balanced"}2{"fill-first"}default{"stable"}}
            Set-HmsOneClickPolicy
            Refresh-Paths
            Save-Settings
            $w.Close()
            Refresh-HmsOneClickShell
        }catch{Err $_.Exception.Message}
    })
    $close.Add_Click({$w.Close()})
    [void]$w.ShowDialog($form)
}

function Show-HmsOneClickMenu {
    $menu=New-Object Windows.Forms.ContextMenuStrip
    $menu.BackColor=[Drawing.Color]::FromArgb(30,34,40)
    $menu.ForeColor=[Drawing.Color]::FromArgb(235,240,246)
    [void]$menu.Items.Add("Thêm tài khoản Codex")
    [void]$menu.Items.Add("Quota / Tài khoản")
    [void]$menu.Items.Add("Cài đặt")
    [void]$menu.Items.Add("Nâng cao / Diagnostics")
    [void]$menu.Items.Add("Unified Command Center")
    $menu.Items[0].Add_Click({try{Login-Provider "--codex-login"}catch{Err $_.Exception.Message}})
    $menu.Items[1].Add_Click({
        try{
            if(-not (PortOpen ([int]$script:S.ProxyPort))){throw "Router chưa chạy."}
            Start-Process ("http://127.0.0.1:"+[int]$script:S.ProxyPort+"/management.html#/quota")|Out-Null
        }catch{Err $_.Exception.Message}
    })
    $menu.Items[2].Add_Click({Show-HmsUxSettings})
    $menu.Items[3].Add_Click({try{[Windows.Forms.MessageBox]::Show((Get-CodexDiagnosticsText),"HMS Diagnostics")|Out-Null}catch{Err $_.Exception.Message}})
    $menu.Items[4].Add_Click({try{Show-CodexUnifiedCommandCenter}catch{Err $_.Exception.Message}})
    $menu.Show($uxGear,0,$uxGear.Height)
}

# Hide the legacy dashboard. It remains in memory as backing compatibility controls.
foreach($ctl in @($form.Controls)){$ctl.Visible=$false}

$form.Text="HMS-AI-ROUTER v25.24 — One-Click"
$form.Size=New-Object Drawing.Size(780,625)
$form.StartPosition="CenterScreen"
$form.BackColor=[Drawing.Color]::FromArgb(14,16,19)
$form.ForeColor=[Drawing.Color]::FromArgb(236,240,245)
$form.Font=New-Object Drawing.Font("Segoe UI",9.5)
$form.FormBorderStyle="FixedSingle"
$form.MaximizeBox=$false
$form.ShowInTaskbar=$true
$form.MinimizeBox=$true
$form.Opacity=0

$uxRoot=New-Object Windows.Forms.Panel
$uxRoot.Location=New-Object Drawing.Point(0,0)
$uxRoot.Size=New-Object Drawing.Size(764,586)
$uxRoot.BackColor=[Drawing.Color]::FromArgb(14,16,19)
$form.Controls.Add($uxRoot)

$uxBrand=New-Object Windows.Forms.Label
$uxBrand.Text="HMS"
$uxBrand.Font=New-Object Drawing.Font("Segoe UI Semibold",19)
$uxBrand.Location=New-Object Drawing.Point(28,22);$uxBrand.AutoSize=$true;$uxRoot.Controls.Add($uxBrand)

$uxProduct=New-Object Windows.Forms.Label
$uxProduct.Text="CODEX ROUTER"
$uxProduct.Font=New-Object Drawing.Font("Segoe UI Semibold",8.5)
$uxProduct.ForeColor=[Drawing.Color]::FromArgb(118,130,144)
$uxProduct.Location=New-Object Drawing.Point(30,56);$uxProduct.AutoSize=$true;$uxRoot.Controls.Add($uxProduct)

$uxGear=New-HmsUxButton "⚙" 688 20 44 38 ([Drawing.Color]::FromArgb(28,32,38)) ([Drawing.Color]::FromArgb(42,48,56))
$uxGear.Font=New-Object Drawing.Font("Segoe UI Symbol",15)
$uxRoot.Controls.Add($uxGear)
$uxGear.Add_Click({Show-HmsOneClickMenu})

$uxHero=New-Object Windows.Forms.Panel
$uxHero.Location=New-Object Drawing.Point(28,92)
$uxHero.Size=New-Object Drawing.Size(704,124)
$uxHero.BackColor=[Drawing.Color]::FromArgb(25,29,34)
Set-HmsUxRoundedRegion $uxHero 16
$uxRoot.Controls.Add($uxHero)

$uxStateDot=New-Object Windows.Forms.Label
$uxStateDot.Text="●";$uxStateDot.Font=New-Object Drawing.Font("Segoe UI",15)
$uxStateDot.Location=New-Object Drawing.Point(24,20);$uxStateDot.AutoSize=$true;$uxHero.Controls.Add($uxStateDot)

$uxStateTitle=New-Object Windows.Forms.Label
$uxStateTitle.Text="ĐÃ TẮT"
$uxStateTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",16)
$uxStateTitle.Location=New-Object Drawing.Point(52,20);$uxStateTitle.AutoSize=$true;$uxHero.Controls.Add($uxStateTitle)

$uxStatusLine=New-Object Windows.Forms.Label
$uxStatusLine.Text="Sẵn sàng."
$uxStatusLine.Location=New-Object Drawing.Point(28,62)
$uxStatusLine.Size=New-Object Drawing.Size(645,45)
$uxStatusLine.ForeColor=[Drawing.Color]::FromArgb(142,153,166)
$uxHero.Controls.Add($uxStatusLine)

$uxAccounts=New-Object Windows.Forms.Panel
$uxAccounts.Location=New-Object Drawing.Point(28,232)
$uxAccounts.Size=New-Object Drawing.Size(704,142)
$uxAccounts.BackColor=[Drawing.Color]::FromArgb(22,25,30)
Set-HmsUxRoundedRegion $uxAccounts 14
$uxRoot.Controls.Add($uxAccounts)

$uxAccountsTitle=New-Object Windows.Forms.Label
$uxAccountsTitle.Text="TÀI KHOẢN"
$uxAccountsTitle.Font=New-Object Drawing.Font("Segoe UI Semibold",9)
$uxAccountsTitle.ForeColor=[Drawing.Color]::FromArgb(122,134,148)
$uxAccountsTitle.Location=New-Object Drawing.Point(18,14);$uxAccountsTitle.AutoSize=$true;$uxAccounts.Controls.Add($uxAccountsTitle)

$uxAccountsText=New-Object Windows.Forms.Label
$uxAccountsText.Text="Đang đọc tài khoản..."
$uxAccountsText.Font=New-Object Drawing.Font("Segoe UI",10)
$uxAccountsText.Location=New-Object Drawing.Point(18,43)
$uxAccountsText.Size=New-Object Drawing.Size(665,82)
$uxAccountsText.ForeColor=[Drawing.Color]::FromArgb(216,223,231)
$uxAccounts.Controls.Add($uxAccountsText)

$uxOneButton=New-HmsUxButton "BẬT HMS" 202 402 360 74 ([Drawing.Color]::FromArgb(25,116,80)) ([Drawing.Color]::FromArgb(31,137,95))
$uxOneButton.Font=New-Object Drawing.Font("Segoe UI Semibold",16)
Set-HmsUxRoundedRegion $uxOneButton 18
$uxRoot.Controls.Add($uxOneButton)

$uxModeLine=New-Object Windows.Forms.Label
$uxModeLine.Text="Một nút tự xử lý Router · API · Codex reload · Watchdog · rollback"
$uxModeLine.TextAlign="MiddleCenter"
$uxModeLine.Location=New-Object Drawing.Point(75,493)
$uxModeLine.Size=New-Object Drawing.Size(615,26)
$uxModeLine.ForeColor=[Drawing.Color]::FromArgb(113,125,139)
$uxRoot.Controls.Add($uxModeLine)

$uxFooter=New-Object Windows.Forms.Label
$uxFooter.Text="v25.27 ADAPTIVE ROUTER + SIGNED UPDATES"
$uxFooter.Location=New-Object Drawing.Point(28,548)
$uxFooter.AutoSize=$true
$uxFooter.ForeColor=[Drawing.Color]::FromArgb(82,94,108)
$uxFooter.Font=New-Object Drawing.Font("Segoe UI Semibold",8)
$uxRoot.Controls.Add($uxFooter)

function Refresh-HmsOneClickShell {
    try{
        $active=Test-HmsOneClickActive
        $pool=Get-CodexPoolSummary
        if($active){
            $uxStateDot.ForeColor=[Drawing.Color]::FromArgb(93,216,151)
            $uxStateTitle.Text="ĐANG HOẠT ĐỘNG"
            $uxOneButton.Text="TẮT HMS"
            $uxOneButton.BackColor=[Drawing.Color]::FromArgb(104,53,55)
            $uxOneButton.Tag.Normal=[Drawing.Color]::FromArgb(104,53,55)
            $uxOneButton.Tag.Hover=[Drawing.Color]::FromArgb(127,64,67)
            if(@(Get-CodexClientProcesses).Count -gt 0){
                $uxStatusLine.Text="Codex đang dùng HMS Router · "+(Get-CodexRoutingDescription)
            }else{
                $uxStatusLine.Text="Router đang chạy · HMS sẽ tự mở lại Codex."
            }
        }else{
            $uxStateDot.ForeColor=[Drawing.Color]::FromArgb(137,148,161)
            $uxStateTitle.Text="ĐÃ TẮT"
            $uxOneButton.Text="BẬT HMS"
            $uxOneButton.BackColor=[Drawing.Color]::FromArgb(25,116,80)
            $uxOneButton.Tag.Normal=[Drawing.Color]::FromArgb(25,116,80)
            $uxOneButton.Tag.Hover=[Drawing.Color]::FromArgb(31,137,95)
            $uxStatusLine.Text="Sẵn sàng · bấm một lần để bật Router và mở Codex."
        }

        $rows=[System.Collections.Generic.List[string]]::new()
        foreach($record in @(Get-CodexAccountRecords | Select-Object -First 4)){
            $quota=if([string]::IsNullOrWhiteSpace([string]$record.Quota)){"—"}else{[string]$record.Quota}
            $plan=if([string]::IsNullOrWhiteSpace([string]$record.Plan)){"—"}else{[string]$record.Plan}
            $status=if([string]::IsNullOrWhiteSpace([string]$record.Status)){"—"}else{[string]$record.Status}
            $rows.Add(([string]$record.Email+"   · "+$plan+"   · "+$status+"   · "+$quota))
        }
        if($rows.Count -eq 0){
            $uxAccountsText.Text="Chưa có tài khoản Codex.`r`nBấm BẬT HMS để HMS mở đăng nhập OAuth."
        }else{
            $uxAccountsText.Text=($rows -join "`r`n")
        }
        $uxAccountsTitle.Text=("TÀI KHOẢN · "+[string]$pool.Total+"  |  READY "+[string]$pool.Ready+"  |  COOLDOWN "+[string]$pool.Cooldown)
        [Windows.Forms.Application]::DoEvents()
    }catch{}
}

function Status([string]$msg=""){
    Refresh-HmsOneClickShell
    if(-not $msg){return}
    if([bool]$script:OneClickBusy){
        Set-HmsOneClickProgress $msg "busy"
        return
    }
    if($msg -match '(?i)lỗi|error|fail|blocked'){
        Set-HmsOneClickProgress $msg "error"
    }
}

$uxOneButton.Add_Click({
    if(-not $uxOneButton.Enabled){return}
    $uxOneButton.Enabled=$false
    $script:OneClickBusy=$true
    $form.Cursor=[Windows.Forms.Cursors]::WaitCursor
    try{
        if(Test-HmsOneClickActive){
            $uxOneButton.Text="ĐANG TẮT..."
            Set-HmsOneClickProgress "Đang tắt HMS an toàn..." "busy"
            $result=Invoke-HmsOneClickDisable
            Set-HmsOneClickProgress $result "ok"
        }else{
            $uxOneButton.Text="ĐANG BẬT..."
            Set-HmsOneClickProgress "Đang bật HMS tự động..." "busy"
            $result=Invoke-HmsOneClickEnable
            Set-HmsOneClickProgress $result "ok"
        }
    }catch{
        $safeError=Redact-LocalApiText ([string]$_.Exception.Message)
        Set-HmsOneClickProgress ("LỖI: "+$safeError) "error"
        [Windows.Forms.MessageBox]::Show(
            "HMS không hoàn tất thao tác.`r`n`r`n"+$safeError+"`r`n`r`nKhông có trạng thái PASS giả; các mutation transactional sẽ rollback theo engine HMS.",
            "HMS One-Click",
            [Windows.Forms.MessageBoxButtons]::OK,
            [Windows.Forms.MessageBoxIcon]::Warning
        )|Out-Null
    }finally{
        $form.Cursor=[Windows.Forms.Cursors]::Default
        $script:OneClickBusy=$false
        $uxOneButton.Enabled=$true
        Refresh-HmsOneClickShell
    }
})

$uxRefreshTimer=New-Object Windows.Forms.Timer
$uxRefreshTimer.Interval=5000
$uxRefreshTimer.Add_Tick({
    Refresh-HmsOneClickShell
    if((Test-HmsOneClickActive) -and @(Get-CodexClientProcesses).Count -lt 1){
        try{$null=Open-CodexClient}catch{}
    }
})
$uxRefreshTimer.Start()

$uxFade=New-Object Windows.Forms.Timer
$uxFade.Interval=18
$uxFade.Add_Tick({
    if($form.Opacity -lt 1){$form.Opacity=[Math]::Min(1,$form.Opacity+0.11)}
    else{$uxFade.Stop()}
})
$form.Add_Shown({
    Refresh-HmsOneClickShell
    $form.ShowInTaskbar=$true
    $form.WindowState=[Windows.Forms.FormWindowState]::Normal
    $form.BeginInvoke([Action]{Restore-HmsMainWindow})|Out-Null
    if((Test-HmsOneClickActive) -and @(Get-CodexClientProcesses).Count -lt 1){
        $form.BeginInvoke([Action]{try{$null=Open-CodexClient}catch{}})|Out-Null
    }
    $uxFade.Start()
})



function Restore-HmsMainWindow {
    try{
        if(-not $form.Visible){$form.Show()}
        if($form.WindowState -eq [Windows.Forms.FormWindowState]::Minimized){
            $form.WindowState=[Windows.Forms.FormWindowState]::Normal
        }
        $form.ShowInTaskbar=$true
        $form.BringToFront()
        $form.Activate()
        try{
            Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class HmsWindowFocus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@ -ErrorAction SilentlyContinue
            [HmsWindowFocus]::ShowWindowAsync($form.Handle,9)|Out-Null
            [HmsWindowFocus]::SetForegroundWindow($form.Handle)|Out-Null
        }catch{}
    }catch{}
}

# System tray / background controls (Cockpit parity lane).
$tray=$null
if([bool]$script:S.CodexTrayEnabled){
    $tray=New-Object Windows.Forms.NotifyIcon
    $tray.Icon=[Drawing.SystemIcons]::Application
    $tray.Text="HMS-AI-ROUTER — Codex"
    $tray.Visible=$true
    $menu=New-Object Windows.Forms.ContextMenuStrip
    [void]$menu.Items.Add("Mở HMS Cockpit")
    [void]$menu.Items.Add("Codex Mission Control")
    [void]$menu.Items.Add("Bật Router")
    [void]$menu.Items.Add("Tắt Router / về Cockpit")
    [void]$menu.Items.Add("Thoát")
    $menu.Items[0].Add_Click({Restore-HmsMainWindow})
    $menu.Items[1].Add_Click({Show-CodexMissionControl})
    $menu.Items[2].Add_Click({try{$script:OneClickBusy=$true;Set-HmsOneClickProgress "Đang bật HMS..." "busy";$null=Invoke-HmsOneClickEnable}catch{Err $_.Exception.Message}finally{$script:OneClickBusy=$false;Refresh-HmsOneClickShell}})
    $menu.Items[3].Add_Click({try{$script:OneClickBusy=$true;Set-HmsOneClickProgress "Đang tắt HMS..." "busy";$null=Invoke-HmsOneClickDisable}catch{Err $_.Exception.Message}finally{$script:OneClickBusy=$false;Refresh-HmsOneClickShell}})
    $menu.Items[4].Add_Click({$form.Tag="EXIT";$form.Close()})
    $tray.ContextMenuStrip=$menu
    $tray.Add_DoubleClick({Restore-HmsMainWindow})
    $form.Add_Resize({
        # v25.24 GUI-only: normal Windows minimize/restore behavior.
        # Never Hide() the main form on minimize.
        if($form.WindowState -eq [Windows.Forms.FormWindowState]::Normal){
            $form.ShowInTaskbar=$true
        }
    })
}

$policyKernelTimer=New-Object Windows.Forms.Timer
$policyKernelTimer.Interval=[Math]::Max(10000,([int]$script:S.PolicyKernelIntervalSec*1000))
$policyKernelTimer.Add_Tick({
    if(([bool]$script:S.PolicyKernelEnabled) -and (-not $script:RuntimeAutomationBlocked)){
        try{$null=Invoke-HmsPolicyKernelCycle}catch{}
    }
})
$policyKernelTimer.Start()

$soakTimer=New-Object Windows.Forms.Timer
$soakTimer.Interval=[Math]::Max(30000,([int]$script:S.SoakSampleIntervalSec*1000))
$soakTimer.Add_Tick({
    if([bool]$script:S.SoakEnabled){
        try{
            $st=Get-HmsSoakState
            if([bool]$st.active){$null=Add-HmsSoakSample}
        }catch{}
    }
})
$soakTimer.Start()

$poolReconcileTimer=New-Object Windows.Forms.Timer
$poolReconcileTimer.Interval=[Math]::Max(60000,([int]$script:S.PoolReconcileAutoAuditMinutes*60*1000))
$poolReconcileTimer.Add_Tick({
    if([bool]$script:S.PoolReconcileEnabled){
        try{
            $r=Invoke-CodexPoolReconcileAudit
            if([int]$r.summary.problems -gt 0){Status ("Pool Audit: "+[string]$r.summary.problems+" issue(s) cần review.")}
        }catch{}
    }
})
$poolReconcileTimer.Start()

$apiAnalyticsTimer=New-Object Windows.Forms.Timer
$apiAnalyticsTimer.Interval=[Math]::Max(10000,([int]$script:S.ApiAnalyticsRefreshSec*1000))
$apiAnalyticsTimer.Add_Tick({
    if([bool]$script:S.ApiSupersetEnabled){
        try{$null=Invoke-HmsApiAnalytics}catch{}
    }
})
$apiAnalyticsTimer.Start()
if([bool]$script:S.ApiParityAutoAudit){
    try{$null=Invoke-HmsCockpitParityAudit}catch{}
}

$proxyFleetTimer=New-Object Windows.Forms.Timer
$proxyFleetTimer.Interval=[Math]::Max(30000,([int]$script:S.ProxyFleetAuditIntervalSec*1000))
$proxyFleetTimer.Add_Tick({
    if([bool]$script:S.ProxyFleetAuditEnabled){
        try{
            if($script:RuntimeAutomationBlocked){
                $null=Invoke-HmsProxyFleetAudit
            }else{
                $fa=Invoke-HmsProxyFleetSupervisorCycle
                if($fa -and [string]$fa.verdict -eq "CRITICAL"){
                    Status ("Proxy Fleet CRITICAL: "+[string]$fa.summary.critical+" group(s).")
                }
            }
        }catch{}
    }
})
$proxyFleetTimer.Start()

$productionTimer=New-Object Windows.Forms.Timer
$productionTimer.Interval=[Math]::Max(30000,([int]$script:S.ProductionHealthIntervalSec*1000))
$productionTimer.Add_Tick({try{$null=Publish-HmsHealthCertificate}catch{}})
$productionTimer.Start()

$unifiedTimer=New-Object Windows.Forms.Timer
$unifiedTimer.Interval=[Math]::Max(5000,([int]$script:S.CodexUnifiedRefreshSec*1000))
$unifiedTimer.Add_Tick({try{$null=Publish-CodexUnifiedSnapshot}catch{}})
$unifiedTimer.Start()
if([bool]$script:S.UnifiedUxAutoStart){
    try{$null=Start-HmsUnifiedUx}catch{}
}

$haTimer=New-Object Windows.Forms.Timer
$haTimer.Interval=[Math]::Max(10000,([int]$script:S.CodexHaIntervalSec*1000))
$haTimer.Add_Tick({try{$m=Invoke-CodexHaCycle;if($m){Status $m}}catch{}})
$haTimer.Start()

$autopilotTimer=New-Object Windows.Forms.Timer
$autopilotTimer.Interval=[Math]::Max(30000,([int]$script:S.CodexAutopilotIntervalSec*1000))
$autopilotTimer.Add_Tick({try{$m=Invoke-CodexAutopilotCycle;if($m){Status$m}}catch{}})
$autopilotTimer.Start()

$opsTimer=New-Object Windows.Forms.Timer
$opsTimer.Interval=[Math]::Max(5000,([int]$script:S.CodexOpsScanIntervalSec*1000))
$opsTimer.Add_Tick({
    if([bool]$script:S.CodexOpsEnabled){
        try{$scan=Invoke-CodexOperationsScan;Update-CodexIncidentsFromScan$scan;Snapshot-CodexQuotaHistory;$m=Invoke-CodexRecoveryPolicy$scan;if($m){Status$m}}catch{}
    }
})
$opsTimer.Start()

$fleetTimer=New-Object Windows.Forms.Timer
$fleetTimer.Interval=[Math]::Max(30000,([int]$script:S.CodexFleetRebalanceIntervalSec*1000))
$fleetTimer.Add_Tick({try{$m=Invoke-CodexFleetAutoRebalance;if($m){Status$m}}catch{}})
$fleetTimer.Start()

$controlPlaneTimer=New-Object Windows.Forms.Timer
$controlPlaneTimer.Interval=10000
$controlPlaneTimer.Add_Tick({try{$m=Invoke-CodexInstanceWatchdog;if($m){Status$m}}catch{}})
$controlPlaneTimer.Start()
$wakeupTimer=New-Object Windows.Forms.Timer
$wakeupTimer.Interval=[Math]::Max(30000,([int]$script:S.CodexWakeupSchedulerIntervalSec*1000))
$wakeupTimer.Add_Tick({try{$m=Invoke-WakeupSchedulerTick;if($m){Status $m}}catch{}})
$wakeupTimer.Start()

$codexTimer=New-Object Windows.Forms.Timer
$codexTimer.Interval=[Math]::Max(10000,([int]$script:S.CodexWatchdogIntervalSec*1000))
$codexTimer.Add_Tick({
    try{
        Save-UI
        $m=Invoke-CodexWatchdogCheck
        if($m){Status $m}
    }catch{Status("Codex Watchdog lỗi: "+$_.Exception.Message)}
})
$codexTimer.Start()

$agTimer=New-Object Windows.Forms.Timer;$agTimer.Interval=[Math]::Max(10000,([int]$script:S.AgAutoSwitchIntervalSec*1000));$agTimer.Add_Tick({try{Save-UI;$m=Invoke-AgAutoSwitchCheck;if($m){Status $m}}catch{Status("AG AutoSwitch lỗi: "+$_.Exception.Message)}});$agTimer.Start()
$form.Add_Shown({try{$null=AdoptOurExisting}catch{};$null=Ensure-BridgeSecret;$startMsg=if($script:SafeStartupMode){"SAFE STARTUP — automation recovery đang bị chặn."}elseif($script:SettingsLoadWarning){$script:SettingsLoadWarning}else{"Sẵn sàng."};Status $startMsg;if([bool]$script:S.CodexMissionControlAutoOpen){$form.BeginInvoke([Action]{Show-CodexMissionControl})|Out-Null}})
$form.Add_FormClosing({try{$policyKernelTimer.Stop();$policyKernelTimer.Dispose();$soakTimer.Stop();$soakTimer.Dispose();$poolReconcileTimer.Stop();$poolReconcileTimer.Dispose();$apiAnalyticsTimer.Stop();$apiAnalyticsTimer.Dispose();$proxyFleetTimer.Stop();$proxyFleetTimer.Dispose();$productionTimer.Stop();$productionTimer.Dispose();$unifiedTimer.Stop();$unifiedTimer.Dispose();$haTimer.Stop();$haTimer.Dispose();$autopilotTimer.Stop();$autopilotTimer.Dispose();$opsTimer.Stop();$opsTimer.Dispose();$fleetTimer.Stop();$fleetTimer.Dispose();$controlPlaneTimer.Stop();$controlPlaneTimer.Dispose();$wakeupTimer.Stop();$wakeupTimer.Dispose();$codexTimer.Stop();$codexTimer.Dispose();$agTimer.Stop();$agTimer.Dispose();if($tray){$tray.Visible=$false;$tray.Dispose()};Save-UI;$null=Publish-HmsHealthCertificate;Complete-HmsRuntimeSession}catch{Complete-HmsRuntimeSession}})
[void]$form.ShowDialog()