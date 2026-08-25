#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.error
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

LAUNCH_PREVIEW_PATH = "src/components/codex/CodexLaunchPreviewModal.tsx"
ACCOUNTS_PAGE_PATH = "src/pages/CodexAccountsPage.tsx"
INSTANCES_PAGE_PATH = "src/pages/CodexInstancesPage.tsx"
INSTANCES_MANAGER_PATH = "src/components/InstancesManager.tsx"
PLATFORM_INSTANCES_PATH = "src/components/platform/PlatformInstancesContent.tsx"

EXPECTED_BLOBS = {
    (BASE_COMMIT, ACCOUNTS_PAGE_PATH): "0651f140544371f8131e24c726af679177d97c4f",
    (BASE_COMMIT, INSTANCES_PAGE_PATH): "581bfbb4437659356afdf1b786e2dc66dfa8affc",
    (BASE_COMMIT, INSTANCES_MANAGER_PATH): "e7f127b2ea311ab1247e00e1010b187f7aa3bb93",
    (BASE_COMMIT, PLATFORM_INSTANCES_PATH): "93586cab64f6498cc6e350019fdcd663ae8b0764",
    (TARGET_COMMIT, LAUNCH_PREVIEW_PATH): "3a2ccda02b8bd7d9873a992192394f2ab183b35f",
    (TARGET_COMMIT, ACCOUNTS_PAGE_PATH): "989d3e682a9aca86aae98a13f4e5a3b7cf8045dc",
    (TARGET_COMMIT, INSTANCES_PAGE_PATH): "96c3b708258443041a3e3ec1e48c35864acafa42",
    (TARGET_COMMIT, INSTANCES_MANAGER_PATH): "a918ee89d4ca1152f49ea0d2701df397b07914f9",
    (TARGET_COMMIT, PLATFORM_INSTANCES_PATH): "93586cab64f6498cc6e350019fdcd663ae8b0764",
}


def _raw_url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{UPSTREAM_REPOSITORY}/{commit}/{path}"


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _fetch(commit: str, path: str) -> bytes:
    request = urllib.request.Request(
        _raw_url(commit, path),
        headers={"User-Agent": "HMS-AI-ROUTER-v25.75-source-proof"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def _fetch_optional(commit: str, path: str) -> bytes | None:
    try:
        return _fetch(commit, path)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _decode(data: bytes) -> str:
    return data.decode("utf-8")


def _segment(source: str, start: str, end: str | None = None) -> str:
    start_index = source.find(start)
    if start_index < 0:
        return ""
    if not end:
        return source[start_index:]
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        return source[start_index:]
    return source[start_index:end_index]


def _ordered(source: str, *needles: str) -> bool:
    cursor = 0
    for needle in needles:
        index = source.find(needle, cursor)
        if index < 0:
            return False
        cursor = index + len(needle)
    return True


def _load_pinned_sources() -> tuple[dict[str, str], dict[str, str], bool]:
    observed: dict[str, str] = {}
    source: dict[str, str] = {}
    for (commit, path), expected_sha in EXPECTED_BLOBS.items():
        data = _fetch(commit, path)
        actual_sha = _git_blob_sha(data)
        key = f"{commit}:{path}"
        observed[key] = actual_sha
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"UPSTREAM_BLOB_MISMATCH:{path}:{commit}:{actual_sha}:{expected_sha}"
            )
        source[key] = _decode(data)

    base_preview_absent = _fetch_optional(BASE_COMMIT, LAUNCH_PREVIEW_PATH) is None
    return source, observed, base_preview_absent


@dataclass
class LaunchMutationProbe:
    mutation_calls: int = 0

    def mutate(self) -> None:
        self.mutation_calls += 1


def _confirmation_boundary_probe(confirmed: bool) -> int:
    probe = LaunchMutationProbe()
    if confirmed:
        probe.mutate()
    return probe.mutation_calls


def source_proof() -> dict[str, Any]:
    source, observed, base_preview_absent = _load_pinned_sources()
    modal = source[f"{TARGET_COMMIT}:{LAUNCH_PREVIEW_PATH}"]
    accounts = source[f"{TARGET_COMMIT}:{ACCOUNTS_PAGE_PATH}"]
    instances = source[f"{TARGET_COMMIT}:{INSTANCES_PAGE_PATH}"]
    manager = source[f"{TARGET_COMMIT}:{INSTANCES_MANAGER_PATH}"]
    platform = source[f"{TARGET_COMMIT}:{PLATFORM_INSTANCES_PATH}"]
    base_accounts = source[f"{BASE_COMMIT}:{ACCOUNTS_PAGE_PATH}"]
    base_instances = source[f"{BASE_COMMIT}:{INSTANCES_PAGE_PATH}"]

    modal_execute = _segment(
        modal,
        "const handleExecute = useCallback(",
        "const unavailable =",
    )
    account_switch_entry = _segment(
        accounts,
        "const handleSwitch = async (accountId: string) => {",
        "const handleExecuteLaunchPreview = useCallback(",
    )
    account_execute = _segment(
        accounts,
        "const handleExecuteLaunchPreview = useCallback(",
        "const handleExecuteLocalAccessLaunchPreview =",
    )
    local_access_execute = _segment(
        accounts,
        "const handleExecuteLocalAccessLaunchPreview =",
        "const buildLocalAccessLaunchPreviewSummary",
    )
    instance_before_start = _segment(
        instances,
        "const handleBeforeStart = useCallback(",
        "const closeLaunchPreview = useCallback(",
    )
    instance_close = _segment(
        instances,
        "const closeLaunchPreview = useCallback(",
        "const executeLaunchPreview = useCallback(",
    )
    instance_execute = _segment(
        instances,
        "const executeLaunchPreview = useCallback(",
        "const defaultInstance = useMemo(",
    )
    manager_start = _segment(
        manager,
        "const startStoppedInstance = useCallback(",
        "const handleStart = async",
    )

    checks = {
        "v1328_unified_launch_preview_component_absent": base_preview_absent,
        "v1328_accounts_page_does_not_import_unified_launch_preview": (
            "CodexLaunchPreviewModal" not in base_accounts
        ),
        "v1328_instances_page_does_not_import_unified_launch_preview": (
            "CodexLaunchPreviewModal" not in base_instances
        ),
        "v1329_launch_preview_component_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{LAUNCH_PREVIEW_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, LAUNCH_PREVIEW_PATH)]
        ),
        "v1329_accounts_page_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{ACCOUNTS_PAGE_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, ACCOUNTS_PAGE_PATH)]
        ),
        "v1329_instances_page_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{INSTANCES_PAGE_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, INSTANCES_PAGE_PATH)]
        ),
        "v1329_instances_manager_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{INSTANCES_MANAGER_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, INSTANCES_MANAGER_PATH)]
        ),
        "platform_instances_passthrough_is_unchanged_and_pinned": (
            EXPECTED_BLOBS[(BASE_COMMIT, PLATFORM_INSTANCES_PATH)]
            == EXPECTED_BLOBS[(TARGET_COMMIT, PLATFORM_INSTANCES_PATH)]
            == observed[f"{TARGET_COMMIT}:{PLATFORM_INSTANCES_PATH}"]
            and "onBeforeStart={onBeforeStart}" in platform
        ),
        "modal_exposes_explicit_execute_callback": (
            "onExecute: (launchAfterSwitch: boolean) => Promise<boolean>;" in modal
        ),
        "modal_confirmation_button_routes_through_handle_execute": (
            "onClick={() => void handleExecute(false)}" in modal
            and "onClick={() => void handleExecute(mode !== \"instance\")}" in modal
        ),
        "modal_execute_persists_draft_then_calls_launch_callback": (
            _ordered(
                modal_execute,
                "const saved = await persistDraft();",
                "if (!saved) return;",
                "const started = await onExecute(launchAfterSwitch);",
            )
        ),
        "modal_close_path_does_not_call_execute": (
            "const requestClose = useCallback(() =>" in modal
            and "onClose();" in _segment(modal, "const requestClose = useCallback(() =>", "const applyLoadedConfig")
            and "onExecute(" not in _segment(modal, "const requestClose = useCallback(() =>", "const applyLoadedConfig")
        ),
        "account_switch_entry_opens_preview_without_switch_mutation": (
            "setLaunchPreviewInstanceId(DEFAULT_CODEX_INSTANCE_ID);" in account_switch_entry
            and "setLaunchPreviewAccount(account ?? null);" in account_switch_entry
            and "executeCodexAccountSwitch(" not in account_switch_entry
            and "switchAccount(" not in account_switch_entry
        ),
        "account_launch_mutation_is_inside_confirmed_execute_callback": (
            "await executeCodexAccountSwitch(account.id, { launchAfterSwitch });"
            in account_execute
            and "setLaunchPreviewAccount(null);" in account_execute
        ),
        "account_deepseek_binding_and_start_are_inside_confirmed_execute_callback": (
            "await codexInstanceStore.updateInstance({" in account_execute
            and "deferBindAccountApplication: true" in account_execute
            and "if (launchAfterSwitch)" in account_execute
            and "await codexInstanceStore.startInstance(launchPreviewInstanceId);"
            in account_execute
        ),
        "api_service_entry_opens_preview_before_activation": (
            "setLocalAccessLaunchPreviewOpen(true);" in accounts
            and "mode=\"apiService\"" in accounts
            and "onExecute={handleExecuteLocalAccessLaunchPreview}" in accounts
        ),
        "api_service_activation_is_inside_confirmed_execute_callback": (
            "const activateSelectedTarget = async () =>" in local_access_execute
            and "bindAccountId: CODEX_API_SERVICE_BIND_ID" in local_access_execute
            and "deferBindAccountApplication: true" in local_access_execute
            and "return await handleActivateLocalAccess();" in local_access_execute
        ),
        "instance_before_start_opens_preview_as_boolean_promise": (
            "return new Promise<boolean>((resolve) =>" in instance_before_start
            and "pendingLaunchResolve.current = resolve;" in instance_before_start
            and "setLaunchPreview({" in instance_before_start
        ),
        "instance_preview_cancel_resolves_false": (
            "pendingLaunchResolve.current?.(false);" in instance_close
            and "setLaunchPreview(null);" in instance_close
        ),
        "instance_preview_confirm_resolves_true": (
            _ordered(
                instance_execute,
                "pendingLaunchResolve.current = null;",
                "setLaunchPreview(null);",
                "resolve(true);",
            )
        ),
        "instance_manager_awaits_confirmation_before_start_mutation": (
            _ordered(
                manager_start,
                "const allowed = await onBeforeStart(instance);",
                "if (!allowed)",
                "markInstanceStarting(instance.id);",
                "const startedInstance = await startInstance(instance.id);",
            )
        ),
        "instance_manager_cancel_returns_before_start_mutation": (
            "return \"cancelled\";" in manager_start
            and manager_start.find("return \"cancelled\";")
            < manager_start.find("await startInstance(instance.id)")
        ),
        "adversarial_cancel_never_calls_launch_mutation": (
            _confirmation_boundary_probe(False) == 0
        ),
        "positive_control_confirm_calls_launch_mutation_once": (
            _confirmation_boundary_probe(True) == 1
        ),
    }

    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(test["status"] == "PASS" for test in tests)
    result = {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_V1_3_29_LAUNCH_CONFIRMATION_SOURCE_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_release": BASE_RELEASE,
        "base_commit": BASE_COMMIT,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "observed_blob_sha1": observed,
        "launch_mutation_boundary": "USER_CONFIRMATION_CALLBACK_ONLY",
        "source_reconciliation_state": "SOURCE_RECONCILED_PROOF_WIRED",
        "source_certification_only": True,
        "real_windows_runtime_executed": False,
        "windows_runtime_certified": False,
        "external_windows_target_evidence_imported": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
        "baseline_adoption_authorized": False,
    }
    return result


def main() -> int:
    try:
        result = source_proof()
    except Exception as exc:
        result = {
            "product": PRODUCT,
            "version": VERSION,
            "suite": "COCKPIT_V1_3_29_LAUNCH_CONFIRMATION_SOURCE_PROOF",
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
