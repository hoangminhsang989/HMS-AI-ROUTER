#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

VERSION = "25.74"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED:{path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    ps_path = root / "HMS_AI_ROUTER_v25.23.1.ps1"
    ps = ps_path.read_text(encoding="utf-8", errors="replace")
    add("powershell_version_current", '$script:Version = "25.74"' in ps)
    add("cockpit_baseline_setting_1327", 'CodexCockpitParityBaseline = "1.3.27"' in ps)
    add("port_auto_rebind_integrated", all(x in ps for x in (
        "CodexInstancePortAutoRecover = $true", "function Repair-HmsCodexInstancePortConflict",
        "Repair-HmsCodexInstancePortConflict $Instance", "INSTANCE_PORT_REBIND_RACE_DETECTED",
    )))
    repair = ps[ps.find("function Repair-HmsCodexInstancePortConflict"):ps.find("function Invoke-HmsBoundedCredentialArchiveRetention")]
    add("port_rebind_never_kills_foreign_listener", "Stop-Process" not in repair and "taskkill" not in repair, repair[:500])
    start = ps[ps.find("function Start-CodexInstance {"):ps.find("function Stop-CodexInstance {")]
    add("launch_time_account_occupancy_guard", "Assert-HmsCodexAccountOccupancyBeforeLaunch $i" in start and start.find("Assert-HmsCodexAccountOccupancyBeforeLaunch $i") < start.find("Start-CodexInstanceRouter $i"))
    add("client_auth_api_service_split_fields", all(x in ps for x in ("ClientAuthState", "ApiServiceState", "OverallAvailability", "CLIENT_REAUTH_REQUIRED_API_CREDENTIAL_PRESENT")))
    add("official_account_ref_hashed_in_account_view", "OfficialAccountRef=$officialRef" in ps and "Get-HmsStringSha256 ([string]$officialId)" in ps)
    add("websocket_preference_preserved_on_refresh", all(x in ps for x in ("CodexPreserveWebSocketPreference = $true", "$routeWebSockets=$existing.websockets", "NotePropertyName websockets -NotePropertyValue $routeWebSockets")))
    add("bounded_credential_backup_retention", all(x in ps for x in ("CodexBehaviorBackupKeepPerSourceInstance = 1", "function Invoke-HmsBoundedCredentialArchiveRetention", "Invoke-HmsBoundedCredentialArchiveRetention -Root $archive")))
    parity_settings = (
        "CodexCockpitParityBaseline","CodexInstancePortAutoRecover","CodexInstancePortAutoRecoverMaxScan",
        "CodexBehaviorBackupKeepPerSourceInstance","CodexUsagePreferOfficialAccountId",
        "CodexPreserveWebSocketPreference","CodexOfficialAuthExportEnabled","CodexModelContextMetadataEnabled",
    )
    get_settings = ps[ps.find("function Get-HmsBackendSettingsObject"):ps.find("function Convert-HmsSettingBool")]
    apply_settings = ps[ps.find("function Apply-HmsBackendSettings"):ps.find("function Get-HmsBackendSettingsObject") if ps.find("function Get-HmsBackendSettingsObject") > ps.find("function Apply-HmsBackendSettings") else len(ps)]
    # Apply-HmsBackendSettings is after Get-HmsBackendSettingsObject in this script; slice explicitly to the next backend handler.
    apply_start = ps.find("function Apply-HmsBackendSettings")
    apply_end = ps.find("function ", apply_start + len("function Apply-HmsBackendSettings"))
    apply_settings = ps[apply_start:apply_end if apply_end > apply_start else len(ps)]
    add("parity_settings_backend_roundtrip_surface", all(k in get_settings and k in apply_settings for k in parity_settings), parity_settings)
    add("parity_settings_type_bounds", all(x in apply_settings for x in (
        'CodexInstancePortAutoRecoverMaxScan" {$value=Convert-HmsSettingInt $value $key 1 512}',
        'CodexBehaviorBackupKeepPerSourceInstance" {$value=Convert-HmsSettingInt $value $key 1 32}',
        'if($value -ne "1.3.27"){throw "SETTINGS_ENUM: $key"}',
    )))
    add("stable_windows_lifecycle_no_internal_daemon_stop", "WindowsApps\\codex.exe app-server daemon stop" not in ps and "WINDOWSAPPS_INTERNAL_CODEX_DAEMON_STOP" not in ps)

    # Usage continuity: migrate a legacy schema and prefer pseudonymous official account ref.
    ledger = load_module("hms_ledger_v2570", root / "HMS_Codex_UsageLedger.py")
    add("usage_ledger_schema_3", getattr(ledger, "SCHEMA_VERSION", 0) == 3)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        db = td / "usage.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE requests (request_id TEXT PRIMARY KEY, time_utc TEXT NOT NULL, account TEXT, model TEXT)")
        conn.commit()
        try:
            ledger.init_db(conn)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
            add("usage_ledger_legacy_migration_adds_official_ref", "official_account_ref" in cols)
        finally:
            conn.close()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        db = td / "usage.db"; trace = td / "trace.jsonl"
        rows = [
            {"request_id":"r1","path":"/v1/responses","status":200,"account":"before@example.invalid","official_account_id":"stable-official-1","total_tokens":100},
            {"request_id":"r2","path":"/v1/responses","status":200,"account":"after@example.invalid","official_account_id":"stable-official-1","total_tokens":200},
        ]
        trace.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
        conn = sqlite3.connect(db)
        try:
            ledger.init_db(conn); sync = ledger.sync_trace(conn, trace, 1000); snap = ledger.build_snapshot(conn, sync)
            groups = snap.get("by_account_week") or []
            add("usage_continuity_survives_readd", len(groups) == 1 and groups[0].get("requests") == 2 and groups[0].get("total_tokens") == 300, groups)
            raw_db = db.read_bytes()
            add("raw_official_account_id_not_persisted", b"stable-official-1" not in raw_db)
            add("usage_privacy_claim_raw_id_false", snap.get("privacy",{}).get("official_account_id_raw_stored") is False)
        finally:
            conn.close()

    # Composite conversation identity in the real SmartGateway.
    gateway = load_module("hms_gateway_v2570", root / "HMS_Codex_SmartGateway.py")
    body1 = json.dumps({"conversation_id":"conv-a","thread_id":"thread-1","metadata":{"user_id":"same-user"}}).encode()
    body2 = json.dumps({"conversation_id":"conv-b","thread_id":"thread-2","metadata":{"user_id":"same-user"}}).encode()
    sid1 = gateway.session_id({"X-Client-Request-Id":"request-a"}, body1, "")
    sid2 = gateway.session_id({"X-Client-Request-Id":"request-b"}, body2, "")
    add("stream_identity_distinguishes_conversations", bool(sid1 and sid2 and sid1 != sid2), [sid1, sid2])
    add("stream_identity_is_pseudonymous_when_composite", str(sid1).startswith("sid-") and "same-user" not in str(sid1), sid1)
    contract = gateway.compatibility_contract({"session_affinity": True})
    add("gateway_contract_declares_composite_identity", contract.get("routing_invariants",{}).get("stream_identity_isolation") == "CLIENT_PLUS_COMPOSITE_CONVERSATION_ID")

    # Manual sensitive auth export is disabled by default, explicit and stripped of HMS router metadata.
    export_mod = load_module("hms_auth_export_v2570", root / "HMS_Codex_OfficialAuthExport.py")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); src = td / "source.json"; eroot = td / "exports"; dest = eroot / "account-a" / "auth.json"
        src.write_text(json.dumps({"auth_mode":"chatgpt","tokens":{"access_token":"fake-access","refresh_token":"fake-refresh","account_id":"acct-1"},"priority":99,"weight":7,"websockets":False}), encoding="utf-8")
        blocked = False
        try:
            export_mod.export_auth(source=src,destination=dest,export_root=eroot,enabled=False,confirmation=export_mod.CONFIRMATION)
        except PermissionError:
            blocked = True
        add("official_auth_export_disabled_by_default", blocked)
        result = export_mod.export_auth(source=src,destination=dest,export_root=eroot,enabled=True,confirmation=export_mod.CONFIRMATION)
        out = json.loads(dest.read_text(encoding="utf-8"))
        add("official_auth_export_manual_gate_works", result.get("ok") is True and result.get("automatic_export") is False)
        add("official_auth_export_strips_router_fields", all(k not in out for k in ("priority","weight","websockets")))
        add("official_auth_export_marked_sensitive_not_diagnostics", result.get("contains_sensitive_credentials") is True and result.get("diagnostics_export_allowed") is False)

    # Model context/compaction metadata: use only upstream-exposed values; malformed threshold is ignored.
    mm = load_module("hms_model_manager_v2570", root / "HMS_Codex_ModelReasoningManager.py")
    models = mm.normalize_catalog({"models":[{"id":"gpt-test","context_window":200000,"auto_compact_token_limit":160000}]},{})
    add("model_live_context_metadata_exposed", models and models[0].get("context_window_tokens") == 200000 and models[0].get("auto_compact_token_limit") == 160000, models)
    bad = mm.normalize_catalog({"models":[{"id":"gpt-bad","context_window":1000,"auto_compact_token_limit":1200}]},{})
    add("model_invalid_compaction_threshold_fail_soft", bad and bad[0].get("auto_compact_token_limit") is None and bad[0].get("runtime_metadata_state") == "INVALID_COMPACTION_THRESHOLD_IGNORED", bad)

    auth = load_module("hms_auth_compat_v2570", root / "HMS_Codex_OfficialAuthCompatibility.py")
    add("official_auth_compat_rebased_current", getattr(auth,"VERSION","") == "25.74" and getattr(auth,"COCKPIT_V1327_ORIGINATOR","") == "codex_vscode")

    parity = load_module("hms_parity_reset_v2570", root / "HMS_Codex_Cockpit1327ParityReset.py")
    report = parity.report()
    add("parity_reset_baseline_1_3_27", report.get("cockpit_parity_baseline") == "1.3.27")
    add("parity_reset_non_benchmark", report.get("benchmark") is False and str(report.get("production_claim","")).startswith("NOT_CLAIMED"))

    fail = sum(1 for x in checks if x["status"] == "FAIL")
    result = {
        "version": VERSION,
        "cockpit_baseline": "1.3.27",
        "verdict": "PASS_COCKPIT_1327_SOURCE_INTEGRATION_V25_72" if fail == 0 else "REJECT_COCKPIT_1327_SOURCE_INTEGRATION_V25_72",
        "summary": {"pass": len(checks)-fail, "fail": fail, "total": len(checks)},
        "checks": checks,
        "claim_boundary": {
            "windows_runtime_certified": False,
            "real_codex_effects_executed": False,
            "production_score_changed_by_this_validator": False,
        },
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
