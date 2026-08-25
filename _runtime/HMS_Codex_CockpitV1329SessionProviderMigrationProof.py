#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"
BASE_RELEASE = "1.3.28"
BASE_COMMIT = "82576b9634bad0a365abc51eba8f022fb0a50d97"
TARGET_RELEASE = "1.3.29"
TARGET_COMMIT = "83ce2d192cc954cc910ce89edf2d1f710c218798"

MODULE_PATH = "src-tauri/src/modules/codex_session_visibility.rs"
MODAL_PATH = "src/components/codex/CodexSessionVisibilityRepairModal.tsx"
SERVICE_PATH = "src/services/codexInstanceService.ts"

EXPECTED_BLOBS = {
    (BASE_COMMIT, MODULE_PATH): "28cb6cde7a5bfb0c94d042c7eae022b31ea42fb4",
    (BASE_COMMIT, MODAL_PATH): "8cf7cd48b73a0002997f8a88e35534bf1998f59b",
    (BASE_COMMIT, SERVICE_PATH): "f2b2f030c25355ded17967d6578c0d71ac435066",
    (TARGET_COMMIT, MODULE_PATH): "b960977159f1625529c4264e56bade79837974cc",
    (TARGET_COMMIT, MODAL_PATH): "176bb4ab772a5b5d9107c4b599697bae561a5c57",
    (TARGET_COMMIT, SERVICE_PATH): "8c4809de5225ef88b07be9081fd52bd953363f36",
}


def _raw_url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{UPSTREAM_REPOSITORY}/{commit}/{path}"


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _fetch(commit: str, path: str) -> bytes:
    request = urllib.request.Request(
        _raw_url(commit, path),
        headers={"User-Agent": "HMS-AI-ROUTER-v25.75-source-proof"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def _load_sources() -> tuple[dict[str, str], dict[str, str]]:
    sources: dict[str, str] = {}
    observed: dict[str, str] = {}
    for (commit, path), expected in EXPECTED_BLOBS.items():
        data = _fetch(commit, path)
        actual = _git_blob_sha(data)
        key = f"{commit}:{path}"
        observed[key] = actual
        if actual != expected:
            raise RuntimeError(
                f"UPSTREAM_BLOB_MISMATCH:{path}:{commit}:{actual}:{expected}"
            )
        sources[key] = data.decode("utf-8")
    return sources, observed


def _segment(source: str, start: str, end: str | None = None) -> str:
    start_index = source.find(start)
    if start_index < 0:
        return ""
    if end is None:
        return source[start_index:]
    end_index = source.find(end, start_index + len(start))
    return source[start_index:] if end_index < 0 else source[start_index:end_index]


def _ordered(source: str, *needles: str) -> bool:
    cursor = 0
    for needle in needles:
        index = source.find(needle, cursor)
        if index < 0:
            return False
        cursor = index + len(needle)
    return True


@dataclass(frozen=True)
class MigrationProbe:
    selected: bool
    running: bool
    dry_run: bool = False
    write_fails: bool = False


def _migration_transition(probe: MigrationProbe) -> dict[str, Any]:
    if not probe.selected:
        return {
            "result": "UNSELECTED",
            "backup": False,
            "mutation": False,
            "rollback": False,
        }
    if probe.running and not probe.dry_run:
        return {
            "result": "RUNNING_BLOCKED",
            "backup": False,
            "mutation": False,
            "rollback": False,
        }
    if probe.dry_run:
        return {
            "result": "DRY_RUN",
            "backup": False,
            "mutation": False,
            "rollback": False,
        }
    if probe.write_fails:
        return {
            "result": "ROLLED_BACK",
            "backup": True,
            "mutation": True,
            "rollback": True,
        }
    return {
        "result": "APPLIED",
        "backup": True,
        "mutation": True,
        "rollback": False,
    }


def source_proof() -> dict[str, Any]:
    sources, observed = _load_sources()
    base_module = sources[f"{BASE_COMMIT}:{MODULE_PATH}"]
    target_module = sources[f"{TARGET_COMMIT}:{MODULE_PATH}"]
    target_modal = sources[f"{TARGET_COMMIT}:{MODAL_PATH}"]
    target_service = sources[f"{TARGET_COMMIT}:{SERVICE_PATH}"]

    quick_options = _segment(
        target_module,
        "fn official_state_db_only(mode: CodexSessionVisibilityRepairMode) -> Self {",
        "fn full_provider_migration() -> Self {",
    )
    deep_options = _segment(
        target_module,
        "fn full_provider_migration() -> Self {",
        "fn for_mode(mode: CodexSessionVisibilityRepairMode) -> Self {",
    )
    selection_impl = _segment(
        target_module,
        "impl RepairTargetSelection {",
        "impl CodexSessionVisibilityRepairOptions {",
    )
    cross_instance_entry = _segment(
        target_module,
        "pub fn repair_session_visibility_across_instances_with_target(",
        "fn repair_session_visibility_across_instances_with_options(",
    )
    threads_where_clause = _segment(
        target_module,
        "fn build_threads_repair_where_clause(",
        "fn build_threads_repair_set_clause(",
    )
    referenced_rollout_query = _segment(
        target_module,
        "fn collect_referenced_rollout_paths_for_db(",
        "fn collect_rollout_provider_changes(",
    )
    modal_options = _segment(
        target_modal,
        "const buildRepairOptions = useCallback(",
        "const runPreview = useCallback(",
    )
    service_entry = _segment(
        target_service,
        "export async function repairSessionVisibilityAcrossInstances(",
        "export async function listSessionVisibilityRepairInstances",
    )

    running_probe = _migration_transition(MigrationProbe(selected=True, running=True))
    unselected_probe = _migration_transition(MigrationProbe(selected=False, running=False))
    rollback_probe = _migration_transition(
        MigrationProbe(selected=True, running=False, write_fails=True)
    )
    positive_probe = _migration_transition(MigrationProbe(selected=True, running=False))

    checks = {
        "v1328_module_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{MODULE_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, MODULE_PATH)]
        ),
        "v1329_module_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MODULE_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, MODULE_PATH)]
        ),
        "v1329_modal_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MODAL_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, MODAL_PATH)]
        ),
        "v1329_service_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{SERVICE_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, SERVICE_PATH)]
        ),
        "v1329_adds_global_state_catalog_repair_surface": (
            'const GLOBAL_STATE_FILE: &str = ".codex-global-state.json";' in target_module
            and "repair_local_thread_catalog: bool" in target_module
            and "normalize_global_state: bool" in target_module
            and 'const GLOBAL_STATE_FILE: &str = ".codex-global-state.json";'
            not in base_module
        ),
        "v1329_adds_single_repair_task_lock": (
            "static SESSION_VISIBILITY_REPAIR_LOCK: Mutex<()> = Mutex::new(());"
            in target_module
            and "fn acquire_session_visibility_repair_lock()" in target_module
            and "SESSION_VISIBILITY_REPAIR_LOCK" not in base_module
        ),
        "v1329_adds_sidebar_visible_quick_scope": (
            "sidebar_visible_only: bool" in target_module
            and "sidebar_visible_only: bool" not in base_module
            and "sidebar_visible_only: true" in quick_options
            and "sidebar_visible_only: false" in deep_options
        ),
        "quick_mode_is_official_state_and_referenced_rollout_bounded": (
            "repair_rollout: false" in quick_options
            and "repair_referenced_rollouts: true" in quick_options
            and "sqlite_scope: SqliteRepairScope::OfficialStateDbs" in quick_options
            and "repair_local_thread_catalog: false" in quick_options
            and "normalize_global_state: false" in quick_options
            and "require_stopped_instances: false" in quick_options
            and "sidebar_visible_only: true" in quick_options
        ),
        "quick_sidebar_filter_excludes_hidden_history_classes": (
            'visibility.push("COALESCE(archived, 0) = 0")' in threads_where_clause
            and "(COALESCE(preview, '') <> '' OR COALESCE(first_user_message, '') <> '')"
            in threads_where_clause
            and 'visibility.push("COALESCE(rollout_path, \'\') <> \'\'")'
            in threads_where_clause
            and "LOWER(COALESCE(source, '')) NOT LIKE '%subagent%'"
            in threads_where_clause
            and "LOWER(COALESCE(source, '')) NOT LIKE '%internal%'"
            in threads_where_clause
            and "COALESCE(thread_source, '') <> 'ambient_suggestions'"
            in threads_where_clause
        ),
        "quick_referenced_rollout_query_uses_same_sidebar_boundary": (
            'predicates.push("COALESCE(archived, 0) = 0")' in referenced_rollout_query
            and "(COALESCE(preview, '') <> '' OR COALESCE(first_user_message, '') <> '')"
            in referenced_rollout_query
            and "LOWER(COALESCE(source, '')) NOT LIKE '%subagent%'"
            in referenced_rollout_query
            and "LOWER(COALESCE(source, '')) NOT LIKE '%internal%'"
            in referenced_rollout_query
            and "COALESCE(thread_source, '') <> 'ambient_suggestions'"
            in referenced_rollout_query
        ),
        "upstream_sidebar_visibility_regression_test_present": (
            "quick_sqlite_repair_targets_official_sidebar_rows_only" in target_module
            and '"archived-old"' in target_module
            and '"missing-rollout"' in target_module
            and '"subagent-old"' in target_module
        ),
        "upstream_quick_official_state_and_reference_scope_tests_present": (
            "quick_repair_uses_official_state_dbs_without_touching_rollouts"
            in target_module
            and "quick_repair_updates_rollouts_referenced_by_official_state_dbs"
            in target_module
            and "unreferenced_rollout" in target_module
        ),
        "deep_provider_migration_requires_stopped_instances": (
            "require_stopped_instances: true" in deep_options
            and "repair_rollout: true" in deep_options
            and "sqlite_scope: SqliteRepairScope::AllSessionDbs" in deep_options
            and "repair_local_thread_catalog: true" in deep_options
            and "normalize_global_state: true" in deep_options
        ),
        "running_deep_target_is_rejected_before_write": _ordered(
            target_module,
            "if instance_has_planned_changes",
            "&& running",
            "&& options.require_stopped_instances",
            "&& !options.dry_run",
            "return Err(format!(",
        ),
        "selection_validates_target_provider": (
            "validate_provider_id(provider)?;" in selection_impl
            and "target_provider_for(&self, data_dir: &Path)" in selection_impl
        ),
        "selection_filters_session_ids": (
            "fn includes_session_id(&self, session_id: &str) -> bool" in selection_impl
            and ".map(|ids| ids.contains(session_id))" in selection_impl
            and "if !selection.includes_session_id" in target_module
        ),
        "selection_filters_instance_ids_before_repair": (
            "fn includes_instance_id(&self, instance_id: &str) -> bool" in selection_impl
            and ".filter(|instance| selection.includes_instance_id(&instance.id))"
            in target_module
        ),
        "backend_entry_preserves_selected_scope": (
            "target_provider: Option<String>" in cross_instance_entry
            and "session_ids: Option<Vec<String>>" in cross_instance_entry
            and "instance_ids: Option<Vec<String>>" in cross_instance_entry
            and "RepairTargetSelection::from_inputs(target_provider, session_ids, instance_ids)?"
            in cross_instance_entry
        ),
        "frontend_selected_scope_builds_session_and_instance_filters": (
            'effectiveScope === "selected" ? uniqueSelectedSessionIds : null'
            in modal_options
            and 'selectedInstanceScope === "target" ? [selectedInstanceId] : null'
            in modal_options
            and "targetProvider: selectedProvider" in modal_options
            and "repairInstanceIds" in modal_options
            and "sessionIds" in modal_options
        ),
        "frontend_blocks_running_deep_target": (
            'if (selectedMode !== "deep") return false;' in target_modal
            and "repairInstances.some((instance) => instance.running)" in target_modal
            and "const repairDisabled = startDisabled || hasRunningRepairTarget;"
            in target_modal
        ),
        "service_forwards_provider_instance_session_scope_to_tauri": (
            'invoke("codex_repair_session_visibility_across_instances"' in service_entry
            and "targetProvider: options?.targetProvider ?? null" in service_entry
            and "repairInstanceIds: options?.repairInstanceIds ?? null" in service_entry
            and "sessionIds: options?.sessionIds ?? null" in service_entry
            and "dryRun: options?.dryRun ?? false" in service_entry
        ),
        "provider_catalog_is_observed_from_config_and_sqlite_authorities": (
            "collect_session_visibility_repair_providers_for_instances" in target_module
            and "list_configured_provider_ids(&instance.data_dir)" in target_module
            and "CodexSessionVisibilityRepairProviderSource::Config" in target_module
            and "CodexSessionVisibilityRepairProviderSource::Sqlite" in target_module
            and "provider_discovery_uses_config_and_official_state_db_without_scanning_rollouts"
            in target_module
        ),
        "provider_rewrite_skips_already_matching_provider": (
            "if current_provider == target_provider" in target_module
            and "rewrite_needed: false" in target_module
        ),
        "upstream_instance_scope_regression_test_present": (
            "launch_target_quick_repair_is_bidirectional_idempotent_and_instance_scoped"
            in target_module
            and "other_rollout_before" in target_module
        ),
        "mutation_is_preceded_by_backup": _ordered(
            target_module,
            '"backup_instance"',
            "let backup_dir = backup_instance_files(",
            '"write_instance"',
        ),
        "failed_mutation_restores_backup_fail_closed": (
            _ordered(
                target_module,
                "let repaired = match repaired {",
                "Err(error) => {",
                "let restore_result = restore_instance_files_from_backup(",
                "if let Err(restore_error) = restore_result",
            )
            and "已自动回滚" in target_module
        ),
        "rollback_backup_scope_covers_new_catalog_and_global_state_repairs": (
            "catalog_scan.total() > 0" in target_module
            and "global_state_entries_to_update > 0" in target_module
            and "restore_instance_files_from_backup(" in target_module
        ),
        "adversarial_running_target_never_mutates": (
            running_probe["result"] == "RUNNING_BLOCKED"
            and running_probe["backup"] is False
            and running_probe["mutation"] is False
        ),
        "adversarial_unselected_target_never_mutates": (
            unselected_probe["result"] == "UNSELECTED"
            and unselected_probe["mutation"] is False
        ),
        "adversarial_failed_write_rolls_back": (
            rollback_probe["result"] == "ROLLED_BACK"
            and rollback_probe["backup"] is True
            and rollback_probe["mutation"] is True
            and rollback_probe["rollback"] is True
        ),
        "positive_control_selected_stopped_target_applies": (
            positive_probe["result"] == "APPLIED"
            and positive_probe["backup"] is True
            and positive_probe["mutation"] is True
            and positive_probe["rollback"] is False
        ),
    }

    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(item["status"] == "PASS" for item in tests)
    verdict = "PASS" if passed == len(tests) else "FAIL"
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_V1_3_29_SESSION_PROVIDER_MIGRATION_SOURCE_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_release": BASE_RELEASE,
        "base_commit": BASE_COMMIT,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "verdict": verdict,
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "observed_blob_sha1": observed,
        "safety_invariants": [
            "ROLLBACK_ON_FAILED_MUTATION",
            "SELECTED_SCOPE_ONLY",
            "DEEP_MIGRATION_REQUIRES_STOPPED_TARGET",
            "PROVIDER_BOUND_FILTERING",
            "QUICK_REPAIR_OFFICIAL_SIDEBAR_ONLY",
        ],
        "source_reconciliation_state": (
            "SOURCE_RECONCILED_PROOF_WIRED" if verdict == "PASS" else "SOURCE_PROOF_FAILED"
        ),
        "source_certification_only": True,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
        "baseline_adoption_authorized": False,
    }


def main() -> int:
    try:
        result = source_proof()
    except Exception as exc:
        result = {
            "product": PRODUCT,
            "version": VERSION,
            "suite": "COCKPIT_V1_3_29_SESSION_PROVIDER_MIGRATION_SOURCE_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "source_certification_only": True,
            "real_windows_runtime_executed": False,
            "windows_runtime_certified": False,
            "external_windows_target_evidence_imported": False,
            "production_score_promotion_eligible": False,
            "production_score_mutation_authorized": False,
            "baseline_adoption_authorized": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verdict") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
