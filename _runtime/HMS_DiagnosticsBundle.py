#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES_PER_FILE = 2_000_000
MAX_FILES = 120

SECRET_PATTERNS = [
    (re.compile(r'(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+\-/=]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(\bbearer\s+)[A-Za-z0-9._~+\-/=]{6,}'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(api[_-]?key\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(access[_-]?token\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(refresh[_-]?token\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(id[_-]?token\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(client[_-]?secret\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(password\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(cookie\s*[:=]\s*)[^\r\n]+'), r'\1<REDACTED>'),
    (re.compile(r'(?im)^(\s*HMS_ROUTER_API_KEY\s*=\s*).*$'), r'\1<REDACTED>'),
    (re.compile(r'(?i)\b(?:sk[-_]|hms_(?!router_api_key\b)|hms-)[A-Za-z0-9._\-]{10,}\b'), '<REDACTED_KEY>'),
    (re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'), '<REDACTED_JWT>'),
]

DENY_PARTS = {
    'auth', 'oauth', 'credentials', 'credential', 'secrets', 'secret',
    'cookies', 'cookie', '.codex', 'antigravity-accounts', 'client-keys-v20.json'
}

ALLOW_NAMES = {
    'settings-v2523_1.json', 'state-v2523_1.json', 'codex-ops-events.jsonl',
    'codex-route-history.jsonl', 'codex-incidents.jsonl', 'codex-attribution-latest.json',
    'native-gui-maintenance-v2526.json', 'native-gui-maintenance-v2525.json',
    'health-certificate-v8.json', 'startup-report-v8.json', 'gateway-state-v20.json',
    'request-trace-v20.jsonl', 'usage-ledger-latest-v2526.json',
    'closed-loop-router-state-v2531.json', 'closed-loop-router-plan-v2531.json',
    'codex-seamless-router-history-v2530.jsonl', 'unified-diagnostics-latest-v2541.json',
    'unified-diagnostics-history-v2541.jsonl', 'project-orchestrator-latest-v2542.json',
    'project-orchestrator-history-v2542.jsonl', 'multi-codex-team-v2543.json',
    'multi-codex-team-latest-v2543.json', 'multi-codex-team-history-v2543.jsonl',
    'smart-model-router-state-v2544.json', 'smart-model-router-plan-v2544.json', 'smart-model-router-history-v2544.jsonl',
    'lan-pool-latest-v2545.json', 'lan-pool-history-v2545.jsonl', 'local-node-v2545.json',
    'performance-scale-latest-v2548.json', 'real-codex-cert-latest-v2549.json', 'seamless-rotation-torture-v2551-latest.json', 'target-machine-cert-latest-v2553.json', 'production-simulation-latest-v2554.json', 'production-simulation-replay-v2554.json', 'autonomous-router-twin-latest-v2555.json', 'autonomous-router-model-check-v2555.json', 'protocol-chaos-latest-v2556.json', 'recovery-planner-latest-v2557.json', 'compound-fault-recovery-latest-v2558.json', 'official-auth-compat-latest-v2559.json', 'recovery-journal-latest-v2560.json', 'usage-token-latest-v2561.json', 'usage-token-history-v2561.jsonl', 'recovery-replay-latest-v2562.json', 'startup-recovery-latest-v2563.json', 'target-crash-harness-latest-v2563.json', 'startup-recovery-latest-v2564.json', 'windows-recovery-observer-latest-v2564.json', 'real-effect-preflight-latest-v2564.json', 'real-effect-crash-cert-latest-v2564.json', 'target-recovery-evidence-latest-v2564.json', 'startup-recovery-latest-v2565.json', 'windows-target-adapter-latest-v2565.json', 'attested-evidence-promotion-latest-v2565.json', 'recovery-operator-timeline-latest-v2565.json', 'real-effect-preflight-latest-v2565.json', 'real-effect-crash-cert-latest-v2565.json', 'target-recovery-evidence-latest-v2565.json', 'windows-attestation-signer-latest-v2566.json', 'target-cert-runbook-latest-v2566.json', 'attestation-exchange-latest-v2566.json', 'attestation-trust-store-latest-v2567.json', 'offline-attestation-verifier-latest-v2567.json', 'target-cert-campaign-latest-v2567.json', 'target-cert-evidence-ingest-latest-v2569.json', 'promotion-decision-ledger-latest-v2569.json', 'windows-target-capture-kit-latest-v2572.json', 'cockpit-baseline-watch-latest-v2572.json', 'windows-target-import-review-latest-v2573.json', 'baseline-delta-watch-latest-v2573.json', 'external-windows-review-packet-latest-v2574.json', 'baseline-drift-reconciliation-latest-v2574.json'
}


def redact(text: str) -> str:
    result = text
    for pattern, repl in SECRET_PATTERNS:
        result = pattern.sub(repl, result)
    # Generic sensitive JSON fields after more specific patterns.
    result = re.sub(
        r'(?i)("(?:token|secret|password|api_key|authorization|cookie|refresh_token|access_token|id_token|client_secret|prompt|request_body|response|response_body|request_payload|response_payload|input_text|output_text|account|email|username|hostname|private_key|private_material|certificate_private_material|command_line|environment|operator_phrase|arm_token|reviewer_identity|reviewer_email|reviewer_name)"\s*:\s*)"[^"]*"',
        r'\1"<REDACTED>"', result
    )
    result = re.sub(
        r'(?i)("[^"\n]*(?:private[_-]?material|private[_-]?key|signing[_-]?secret)[^"\n]*"\s*:\s*)"[^"]*"',
        r'\1"<REDACTED>"', result
    )
    return result


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def allowed(path: Path) -> bool:
    lname = path.name.lower()
    parts = {p.lower() for p in path.parts}
    # v25.59 auth compatibility evidence is a fixed metadata-only schema; allow it through redaction
    # before the generic auth/oauth path deny-list blocks arbitrary credential files.
    if lname == 'official-auth-compat-latest-v2559.json':
        return True
    if any(x in parts or x in lname for x in DENY_PARTS):
        return False
    if path.name in ALLOW_NAMES:
        return True
    if lname.startswith('soak-') and 'v2547-' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('performance-scale-') and 'v2548' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('real-codex-cert-') and 'v2549' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('seamless-rotation-torture-') and 'v2551' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('target-machine-cert-') and 'v2553' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('production-simulation-') and 'v2554' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('autonomous-router-') and 'v2555' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('protocol-chaos-') and 'v2556' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('recovery-planner-') and 'v2557' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('compound-fault-recovery-') and 'v2558' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('official-auth-compat-') and 'v2559' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('recovery-journal-') and 'v2560' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('usage-token-') and 'v2561' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('recovery-replay-') and 'v2562' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('startup-recovery-') and ('v2563' in lname or 'v2564' in lname or 'v2565' in lname) and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('target-crash-harness-') and 'v2563' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('attestation-trust-store-') or lname.startswith('offline-attestation-verifier-') or lname.startswith('target-cert-campaign-')) and 'v2567' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('target-campaign-executor-') or lname.startswith('attested-promotion-review-')) and 'v2568' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('target-cert-evidence-ingest-') or lname.startswith('promotion-decision-ledger-')) and 'v2569' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('windows-target-capture-kit-') or lname.startswith('cockpit-baseline-watch-')) and 'v2572' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('windows-target-import-review-') or lname.startswith('baseline-delta-watch-')) and 'v2573' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if (lname.startswith('external-windows-review-packet-') or lname.startswith('baseline-drift-reconciliation-')) and 'v2574' in lname and path.suffix.lower() in {'.json','.jsonl','.log'}:
        return True
    if lname.startswith('hms-') and path.suffix.lower() in {'.log', '.json', '.jsonl', '.txt'}:
        return True
    return False


def collect(data_dir: Path, runtime_dir: Path) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    roots = [data_dir]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if len(candidates) >= MAX_FILES:
                break
            if not path.is_file() or not allowed(path):
                continue
            try:
                rel = 'data/' + str(path.relative_to(data_dir)).replace('\\', '/')
            except Exception:
                rel = 'data/' + path.name
            candidates.append((path, rel))
    # Include build/release notes, not source code or auth state.
    for name in ('EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET_VALIDATION_V25.74.json', 'BASELINE_DRIFT_RECONCILIATION_VALIDATION_V25.74.json', 'UNIFIED_DIAGNOSTICS_REVIEW_PACKET_VALIDATION_V25.74.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.74.json', 'WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW_VALIDATION_V25.73.json', 'BASELINE_DELTA_WATCH_AUTOMATION_VALIDATION_V25.73.json', 'UNIFIED_DIAGNOSTICS_IMPORT_REVIEW_VALIDATION_V25.73.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.73.json', 'WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT_VALIDATION_V25.72.json', 'COCKPIT_BASELINE_WATCH_GATE_VALIDATION_V25.72.json', 'UNIFIED_DIAGNOSTICS_TARGET_CAPTURE_VALIDATION_V25.72.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.72.json', 'TARGET_CERTIFICATION_EVIDENCE_INGEST_VALIDATION_V25.69.json', 'PROMOTION_DECISION_LEDGER_VALIDATION_V25.69.json', 'UNIFIED_DIAGNOSTICS_EVIDENCE_LEDGER_VALIDATION_V25.69.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.69.json', 'TARGET_CAMPAIGN_EXECUTOR_VALIDATION_V25.68.json', 'ATTESTED_PROMOTION_REVIEW_CONSOLE_VALIDATION_V25.68.json', 'UNIFIED_DIAGNOSTICS_CAMPAIGN_REVIEW_VALIDATION_V25.68.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.68.json', 'ATTESTATION_TRUST_STORE_VALIDATION_V25.67.json', 'OFFLINE_ATTESTATION_VERIFIER_VALIDATION_V25.67.json', 'TARGET_CERTIFICATION_CAMPAIGN_VALIDATION_V25.67.json', 'WINDOWS_ATTESTATION_SIGNER_VALIDATION_V25.67.json', 'TARGET_CERTIFICATION_RUNBOOK_VALIDATION_V25.67.json', 'ATTESTATION_EXCHANGE_VALIDATION_V25.67.json', 'ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.67.json', 'WINDOWS_ATTESTATION_SIGNER_VALIDATION_V25.66.json', 'TARGET_CERTIFICATION_RUNBOOK_VALIDATION_V25.66.json', 'ATTESTATION_EXCHANGE_VALIDATION_V25.66.json', 'ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.66.json', 'WINDOWS_TARGET_ADAPTER_PACK_VALIDATION_V25.65.json', 'ATTESTED_EVIDENCE_PROMOTION_GATE_VALIDATION_V25.65.json', 'RECOVERY_OPERATOR_TIMELINE_VALIDATION_V25.65.json', 'REAL_EFFECT_CRASH_CERT_VALIDATION_V25.65.json', 'TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.65.json', 'UNIFIED_DIAGNOSTICS_ATTESTED_RECOVERY_VALIDATION_V25.65.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.65.json', 'BUILD_VALIDATION_V25.65.txt', 'CHANGELOG_V25.65.txt', 'ROADMAP_V25.65_CONTINUATION.md', 'WINDOWS_RECOVERY_OBSERVER_BRIDGE_VALIDATION_V25.64.json', 'REAL_EFFECT_CRASH_CERT_VALIDATION_V25.64.json', 'TARGET_RECOVERY_EVIDENCE_BUNDLE_VALIDATION_V25.64.json', 'UNIFIED_DIAGNOSTICS_WINDOWS_RECOVERY_VALIDATION_V25.64.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.64.json', 'BUILD_VALIDATION_V25.64.txt', 'CHANGELOG_V25.64.txt', 'ROADMAP_V25.64_CONTINUATION.md', 'STARTUP_RECOVERY_RECONCILER_VALIDATION_V25.63.json', 'TARGET_CRASH_HARNESS_VALIDATION_V25.63.json', 'UNIFIED_DIAGNOSTICS_STARTUP_RECOVERY_VALIDATION_V25.63.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.63.json', 'RECOVERY_TRANSACTION_REPLAY_VALIDATION_V25.62.json', 'UNIFIED_DIAGNOSTICS_RECOVERY_REPLAY_VALIDATION_V25.62.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.62.json', 'BUILD_VALIDATION_V25.61.txt', 'CHANGELOG_V25.61.txt', 'ROADMAP_V25.61_CONTINUATION.md', 'USAGE_TOKEN_CENTER_VALIDATION_V25.61.json', 'UNIFIED_DIAGNOSTICS_USAGE_TOKEN_VALIDATION_V25.61.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.61.json', 'REGRESSION_FREEZE_VALIDATION_V25.61.json', 'RUNTIME_KIT_VALIDATION_V25.61.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.61.json', 'BUILD_VALIDATION_V25.60.txt', 'CHANGELOG_V25.60.txt', 'ROADMAP_V25.60_CONTINUATION.md', 'RECOVERY_TRANSACTION_JOURNAL_VALIDATION_V25.60.json', 'UNIFIED_DIAGNOSTICS_RECOVERY_JOURNAL_VALIDATION_V25.60.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.60.json', 'COCKPIT_PARITY_AUDIT_V25_60.json', 'REGRESSION_FREEZE_VALIDATION_V25.60.json', 'RUNTIME_KIT_VALIDATION_V25.60.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.60.json', 'BUILD_VALIDATION_V25.59.txt', 'CHANGELOG_V25.59.txt', 'COCKPIT_V1324_AUTH_PARITY_V25.59.md', 'OFFICIAL_AUTH_COMPAT_VALIDATION_V25.59.json', 'UNIFIED_DIAGNOSTICS_AUTH_COMPAT_VALIDATION_V25.59.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.59.json', 'COCKPIT_PARITY_AUDIT_V25_59.json', 'REGRESSION_FREEZE_VALIDATION_V25.59.json', 'RUNTIME_KIT_VALIDATION_V25.59.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.59.json', 'BUILD_VALIDATION_V25.58.txt', 'CHANGELOG_V25.58.txt', 'ROADMAP_V25.58_CONTINUATION.md', 'COMPOUND_FAULT_RECOVERY_VALIDATION_V25.58.json', 'UNIFIED_DIAGNOSTICS_COMPOUND_RECOVERY_VALIDATION_V25.58.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.58.json', 'COCKPIT_PARITY_AUDIT_V25_58.json', 'REGRESSION_FREEZE_VALIDATION_V25.58.json', 'RUNTIME_KIT_VALIDATION_V25.58.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.58.json', 'BUILD_VALIDATION_V25.57.txt', 'CHANGELOG_V25.57.txt', 'ROADMAP_V25.57_CONTINUATION.md', 'RECOVERY_PLANNER_VALIDATION_V25.57.json', 'UNIFIED_DIAGNOSTICS_RECOVERY_VALIDATION_V25.57.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.57.json', 'COCKPIT_PARITY_AUDIT_V25_57.json', 'REGRESSION_FREEZE_VALIDATION_V25.57.json', 'RUNTIME_KIT_VALIDATION_V25.57.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.57.json', 'BUILD_VALIDATION_V25.56.txt', 'CHANGELOG_V25.56.txt', 'ROADMAP_V25.56_CONTINUATION.md', 'PROTOCOL_CHAOS_FUZZER_VALIDATION_V25.56.json', 'UNIFIED_DIAGNOSTICS_PROTOCOL_CHAOS_VALIDATION_V25.56.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.56.json', 'COCKPIT_PARITY_AUDIT_V25_56.json', 'REGRESSION_FREEZE_VALIDATION_V25.56.json', 'RUNTIME_KIT_VALIDATION_V25.56.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.56.json', 'BUILD_VALIDATION_V25.55.txt', 'CHANGELOG_V25.55.txt', 'ROADMAP_V25.55_CONTINUATION.md', 'AUTONOMOUS_ROUTER_TWIN_VALIDATION_V25.55.json', 'UNIFIED_DIAGNOSTICS_ROUTER_TWIN_VALIDATION_V25.55.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.55.json', 'COCKPIT_PARITY_AUDIT_V25_55.json', 'REGRESSION_FREEZE_VALIDATION_V25.55.json', 'RUNTIME_KIT_VALIDATION_V25.55.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.55.json', 'BUILD_VALIDATION_V25.54.txt', 'CHANGELOG_V25.54.txt', 'ROADMAP_V25.54_CONTINUATION.md', 'PRODUCTION_SIMULATION_VALIDATION_V25.54.json', 'UNIFIED_DIAGNOSTICS_SIMULATION_VALIDATION_V25.54.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.54.json', 'COCKPIT_PARITY_AUDIT_V25_54.json', 'REGRESSION_FREEZE_VALIDATION_V25.54.json', 'RUNTIME_KIT_VALIDATION_V25.54.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.54.json', 'BUILD_VALIDATION_V25.53.txt', 'CHANGELOG_V25.53.txt', 'ROADMAP_V25.53_CONTINUATION.md', 'TARGET_MACHINE_CERTIFICATION_VALIDATION_V25.53.json', 'TARGET_MACHINE_HOST_PREFLIGHT_V25.53.json', 'UNIFIED_DIAGNOSTICS_TARGET_CERT_VALIDATION_V25.53.json', 'GUI_STARTUP_SMOKE_V25.53.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.53.json', 'COCKPIT_PARITY_AUDIT_V25_53.json', 'REGRESSION_FREEZE_VALIDATION_V25.53.json', 'RUNTIME_KIT_VALIDATION_V25.53.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.53.json', 'BUILD_VALIDATION_V25.52.txt', 'CHANGELOG_V25.52.txt', 'ROADMAP_V25.52_CONTINUATION.md', 'UX_COCKPIT_PARITY_VALIDATION_V25.52.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.52.json', 'GUI_STARTUP_SMOKE_V25.52.json', 'COCKPIT_PARITY_AUDIT_V25_52.json', 'REGRESSION_FREEZE_VALIDATION_V25.52.json', 'RUNTIME_KIT_VALIDATION_V25.52.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.52.json', 'BUILD_VALIDATION_V25.51.txt', 'CHANGELOG_V25.51.txt', 'ROADMAP_V25.51_CONTINUATION.md', 'SEAMLESS_ROTATION_TORTURE_VALIDATION_V25.51.json', 'UNIFIED_DIAGNOSTICS_ROTATION_VALIDATION_V25.51.json', 'DIAGNOSTICS_BUNDLE_PRIVACY_VALIDATION_V25.51.json', 'REGRESSION_FREEZE_VALIDATION_V25.51.json', 'RUNTIME_KIT_VALIDATION_V25.51.json', 'BUILD_VALIDATION_V25.50.txt', 'CHANGELOG_V25.50.txt', 'ROADMAP_V25.50_CONTINUATION.md', 'LIVE_QUOTA_INTELLIGENCE_VALIDATION_V25.50.json', 'BUILD_VALIDATION_V25.49.txt', 'CHANGELOG_V25.49.txt', 'ROADMAP_V25.49_CONTINUATION.md', 'REAL_CODEX_CERT_VALIDATION_V25.49.json', 'UNIFIED_DIAGNOSTICS_REAL_CODEX_VALIDATION_V25.49.json', 'DIAGNOSTICS_BUNDLE_VALIDATION_V25.49.json', 'REGRESSION_FREEZE_VALIDATION_V25.49.json', 'RUNTIME_KIT_VALIDATION_V25.49.json', 'BUILD_VALIDATION_V25.48.txt', 'CHANGELOG_V25.48.txt', 'ROADMAP_V25.48_CONTINUATION.md', 'PERFORMANCE_SCALE_VALIDATION_V25.48.json', 'REGRESSION_FREEZE_VALIDATION_V25.48.json', 'RUNTIME_KIT_VALIDATION_V25.48.json', 'BUILD_VALIDATION_V25.47.txt', 'CHANGELOG_V25.47.txt', 'ROADMAP_V25.47_CONTINUATION.md', 'RELIABILITY_SOAK_VALIDATION_V25.47.json', 'REGRESSION_FREEZE_VALIDATION_V25.47.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.47.json', 'RUNTIME_KIT_VALIDATION_V25.47.json', 'BUILD_VALIDATION_V25.46.txt', 'CHANGELOG_V25.46.txt', 'ROADMAP_V25.46_CONTINUATION.md', 'REGRESSION_FREEZE_VALIDATION_V25.46.json', 'COMPATIBILITY_FREEZE_VALIDATION_V25.46.json', 'CODEX_CLIENT_COMPAT_VALIDATION_V25.46.json', 'LAN_FAILURE_MATRIX_VALIDATION_V25.46.json', 'LAN_POOL_VALIDATION_V25.46.json', 'BUILD_VALIDATION_V25.45.txt', 'CHANGELOG_V25.45.txt', 'ROADMAP_V25.45_CONTINUATION.md', 'LAN_POOL_VALIDATION_V25.45.json', 'BUILD_VALIDATION_V25.44.txt', 'CHANGELOG_V25.44.txt', 'ROADMAP_V25.44_CONTINUATION.md', 'SMART_MODEL_ROUTER_VALIDATION_V25.44.json', 'BUILD_VALIDATION_V25.43.txt', 'CHANGELOG_V25.43.txt', 'ROADMAP_V25.43_CONTINUATION.md', 'MULTI_CODEX_TEAM_VALIDATION_V25.43.json', 'BUILD_VALIDATION_V25.42.txt', 'PROJECT_ORCHESTRATOR_VALIDATION_V25.42.json', 'UNIFIED_DIAGNOSTICS_VALIDATION_V25.41.json', 'SECURITY_HARDENING_VALIDATION_V25.40.json'):
        p = runtime_dir / name
        if p.exists():
            candidates.append((p, 'runtime/' + name))
    return candidates[:MAX_FILES]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--runtime-dir', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--output')
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    runtime_dir = Path(args.runtime_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    zip_path = out_dir / f'HMS_DIAGNOSTICS_{stamp}.zip'
    manifest = {
        'product': 'HMS-AI-ROUTER',
        'version': '25.74',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'privacy': {
            'contains_raw_oauth': False,
            'contains_request_body': False,
            'contains_api_keys': False,
            'contains_cookies': False,
            'redaction_applied': True,
        },
        'files': [],
        'skipped': [],
    }
    try:
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for src, arc in collect(data_dir, runtime_dir):
                try:
                    raw = src.read_bytes()
                    if len(raw) > MAX_BYTES_PER_FILE:
                        raw = raw[-MAX_BYTES_PER_FILE:]
                        manifest['skipped'].append({'file': arc, 'note': 'tail_only_due_to_size'})
                    text = raw.decode('utf-8-sig', errors='replace')
                    clean = redact(text).encode('utf-8')
                    zf.writestr(arc, clean)
                    manifest['files'].append({'file': arc, 'bytes': len(clean), 'source_sha256': hashlib.sha256(raw).hexdigest()})
                except Exception as exc:
                    manifest['skipped'].append({'file': arc, 'note': type(exc).__name__})
            zf.writestr('DIAGNOSTICS_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        bundle_hash = sha256(zip_path)
        result = {
            'ok': True,
            'path': str(zip_path),
            'sha256': bundle_hash,
            'file_count': len(manifest['files']),
            'privacy': manifest['privacy'],
        }
    except Exception as exc:
        result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    print(text)
    return 0 if result.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
