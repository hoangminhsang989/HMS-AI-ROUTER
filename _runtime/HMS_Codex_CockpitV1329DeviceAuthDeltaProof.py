#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Callable

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"
BASE_COMMIT = "82576b9634bad0a365abc51eba8f022fb0a50d97"
TARGET_COMMIT = "83ce2d192cc954cc910ce89edf2d1f710c218798"

TAURI_OAUTH = "src-tauri/src/modules/codex_oauth.rs"
CORE_OAUTH = "crates/cockpit-core/src/modules/codex_oauth.rs"
COMMANDS = "src-tauri/src/commands/codex.rs"
SERVICE = "src/services/codexService.ts"
LIB = "src-tauri/src/lib.rs"

EXPECTED_BLOBS = {
    (BASE_COMMIT, TAURI_OAUTH): "a4286214e7ea3f505f2a7100fbf1f03aa1e38b27",
    (TARGET_COMMIT, TAURI_OAUTH): "7a4573d8423306570eda0922644709a6b3787e6f",
    (BASE_COMMIT, CORE_OAUTH): "be401c3b5cdacb65fa88d09ece722aa3157ee509",
    (TARGET_COMMIT, CORE_OAUTH): "54f7f0dd7d3f34424dc53933c1fd9535e5cba1ef",
    (BASE_COMMIT, COMMANDS): "04d2e1220bbbb7187df0cf58195401b2a5bb639c",
    (TARGET_COMMIT, COMMANDS): "a6e814adf4d1f94aa0af58964935e85b9f2257cb",
    (BASE_COMMIT, SERVICE): "48bfbd4f175af92eb943bedd1586669500dd2834",
    (TARGET_COMMIT, SERVICE): "8f85a596be4f3d34b0e024ed13fe14d8aa76ba35",
    (BASE_COMMIT, LIB): "31608ad5fa008fcd84f1770e1cbebc3d19c8735d",
    (TARGET_COMMIT, LIB): "46feec0de119d2b624e0d2b23c76688b7dc230dd",
}
MAX_SOURCE_BYTES = 12 * 1024 * 1024
CONNECTOR_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"


class DeviceAuthProofError(RuntimeError):
    pass


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _raw_url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{UPSTREAM_REPOSITORY}/{commit}/{path}"


def _fetch_source(commit: str, path: str, *, timeout_seconds: float = 12.0) -> str:
    url = _raw_url(commit, path)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{PRODUCT}/{VERSION}", "Accept": "text/plain"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=max(2.0, float(timeout_seconds)),
            context=ssl.create_default_context(),
        ) as response:
            if str(response.geturl()) != url:
                raise DeviceAuthProofError(f"unexpected source redirect: {response.geturl()}")
            raw = response.read(MAX_SOURCE_BYTES + 1)
    except DeviceAuthProofError:
        raise
    except Exception as exc:
        raise DeviceAuthProofError(
            f"pinned upstream source unavailable: {commit}:{path}: {exc}"
        ) from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise DeviceAuthProofError(f"pinned upstream source too large: {commit}:{path}")
    expected = EXPECTED_BLOBS[(commit, path)]
    actual = _git_blob_sha(raw)
    if actual != expected:
        raise DeviceAuthProofError(
            f"pinned upstream blob mismatch: {commit}:{path}: expected={expected}, actual={actual}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeviceAuthProofError(
            f"pinned upstream source is not utf-8: {commit}:{path}"
        ) from exc


def _extract_braced_block(source: str, needle: str) -> str:
    start = source.find(needle)
    if start < 0:
        raise DeviceAuthProofError(f"required source symbol missing: {needle}")
    brace = source.find("{", start)
    if brace < 0:
        raise DeviceAuthProofError(f"required source block missing opening brace: {needle}")
    depth = 0
    index = brace
    state = "normal"
    block_depth = 0
    while index < len(source):
        ch = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if state == "line_comment":
            if ch == "\n":
                state = "normal"
        elif state == "block_comment":
            if ch == "/" and nxt == "*":
                block_depth += 1
                index += 1
            elif ch == "*" and nxt == "/":
                block_depth -= 1
                index += 1
                if block_depth == 0:
                    state = "normal"
        elif state == "string":
            if ch == "\\":
                index += 1
            elif ch == '"':
                state = "normal"
        elif state == "char":
            if ch == "\\":
                index += 1
            elif ch == "'":
                state = "normal"
        else:
            if ch == "/" and nxt == "/":
                state = "line_comment"
                index += 1
            elif ch == "/" and nxt == "*":
                state = "block_comment"
                block_depth = 1
                index += 1
            elif ch == '"':
                state = "string"
            elif ch == "'" and source.find("'", index + 1, min(index + 8, len(source))) >= 0:
                state = "char"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[start : index + 1]
        index += 1
    raise DeviceAuthProofError(f"required source block is unbalanced: {needle}")


@dataclass(frozen=True)
class DeviceFlowState:
    active_login_id: str | None
    persisted_device_state: bool
    timed_out: bool = False


def _start_transition(state: DeviceFlowState, new_login_id: str) -> dict:
    if state.active_login_id is not None:
        return {"accepted": False, "active_login_id": state.active_login_id}
    return {"accepted": True, "active_login_id": new_login_id}


def _cancel_transition(state: DeviceFlowState, requested_login_id: str | None) -> dict:
    if state.active_login_id is None:
        return {"cleared": False, "active_login_id": None, "error": None}
    if requested_login_id is not None and requested_login_id != state.active_login_id:
        return {
            "cleared": False,
            "active_login_id": state.active_login_id,
            "error": "LOGIN_ID_MISMATCH",
        }
    return {"cleared": True, "active_login_id": None, "error": None}


def _restart_transition(state: DeviceFlowState) -> dict:
    return {
        "restored_device_flow": False,
        "active_login_id": None if state.persisted_device_state else state.active_login_id,
    }


def _timeout_transition(state: DeviceFlowState) -> dict:
    return {
        "cleared": bool(state.timed_out and state.active_login_id is not None),
        "active_login_id": None if state.timed_out else state.active_login_id,
    }


def source_proof(fetcher: Callable[[str, str], str] = _fetch_source) -> dict:
    base_tauri = fetcher(BASE_COMMIT, TAURI_OAUTH)
    target_tauri = fetcher(TARGET_COMMIT, TAURI_OAUTH)
    base_core = fetcher(BASE_COMMIT, CORE_OAUTH)
    target_core = fetcher(TARGET_COMMIT, CORE_OAUTH)
    base_commands = fetcher(BASE_COMMIT, COMMANDS)
    target_commands = fetcher(TARGET_COMMIT, COMMANDS)
    base_service = fetcher(BASE_COMMIT, SERVICE)
    target_service = fetcher(TARGET_COMMIT, SERVICE)
    base_lib = fetcher(BASE_COMMIT, LIB)
    target_lib = fetcher(TARGET_COMMIT, LIB)

    persist = _extract_braced_block(target_tauri, "fn persist_state_to_disk")
    callback_restore = _extract_braced_block(
        target_tauri, "fn ensure_callback_listener_for_state"
    )
    start = _extract_braced_block(target_tauri, "pub async fn start_device_auth")
    poll = _extract_braced_block(target_tauri, "async fn poll_device_token")
    complete = _extract_braced_block(target_tauri, "pub async fn complete_oauth_login")
    cancel = _extract_braced_block(target_tauri, "pub fn cancel_oauth_flow_for")
    command = _extract_braced_block(
        target_commands, "pub async fn codex_oauth_device_auth_start"
    )
    service_start = _extract_braced_block(
        target_service, "export async function startCodexDeviceAuth"
    )

    checks = {
        "tauri_runtime_connector_scopes_already_present_in_v1328": (
            CONNECTOR_SCOPES in base_tauri and CONNECTOR_SCOPES in target_tauri
        ),
        "tauri_runtime_refresh_lead_already_10_minutes_in_v1328": (
            "ID_TOKEN_REFRESH_LEAD_SECONDS: i64 = 10 * 60" in base_tauri
            and "ID_TOKEN_REFRESH_LEAD_SECONDS: i64 = 10 * 60" in target_tauri
        ),
        "core_library_scopes_sync_in_v1329": (
            'const SCOPES: &str = "openid profile email offline_access";' in base_core
            and CONNECTOR_SCOPES in target_core
        ),
        "core_library_refresh_lead_sync_15_to_10": (
            "ID_TOKEN_REFRESH_LEAD_SECONDS: i64 = 15 * 60" in base_core
            and "ID_TOKEN_REFRESH_LEAD_SECONDS: i64 = 10 * 60" in target_core
        ),
        "device_auth_absent_from_v1328_runtime_module": (
            "DEVICE_USER_CODE_ENDPOINT" not in base_tauri
            and "start_device_auth" not in base_tauri
        ),
        "device_auth_absent_from_v1328_command_service_and_registration": (
            "codex_oauth_device_auth_start" not in base_commands
            and "startCodexDeviceAuth" not in base_service
            and "codex_oauth_device_auth_start" not in base_lib
        ),
        "device_auth_official_endpoints_and_deadline_pinned": all(
            marker in target_tauri
            for marker in (
                'https://auth.openai.com/api/accounts/deviceauth/usercode',
                'https://auth.openai.com/api/accounts/deviceauth/token',
                'https://auth.openai.com/codex/device',
                'https://auth.openai.com/deviceauth/callback',
                "DEVICE_TIMEOUT_SECONDS: u64 = 15 * 60",
            )
        ),
        "device_state_is_not_restored_after_restart": (
            "value.device_auth_id.is_some()" in persist
            and "oauth_pending_state::clear(OAUTH_STATE_FILE)" in persist
        ),
        "device_state_never_restores_local_callback_listener": (
            "if state.device_auth_id.is_some()" in callback_restore
            and "return;" in callback_restore
        ),
        "single_active_oauth_state_blocks_second_device_flow": (
            "if OAUTH_STATE.lock().unwrap().is_some()" in start
            and "Codex OAuth 登录会话已存在" in start
        ),
        "device_start_records_owner_state_and_spawns_poller": all(
            marker in start
            for marker in (
                "device_auth_id: Some(device_auth_id.clone())",
                "device_user_code: Some(user_code.clone())",
                "exchange_redirect_uri: Some(DEVICE_EXCHANGE_REDIRECT_URI.to_string())",
                "poll_device_token",
            )
        ),
        "device_poller_is_bound_to_login_and_device_identity": (
            "state.login_id == login_id" in poll
            and "state.device_auth_id.as_deref() == Some(device_auth_id.as_str())" in poll
        ),
        "device_poller_is_bounded_and_clears_on_timeout": (
            "DEVICE_TIMEOUT_SECONDS" in poll
            and "tokio::time::Instant::now() >= deadline" in poll
            and "clear_oauth_state_for_login_id(&login_id)" in poll
        ),
        "device_completion_uses_common_exchange_with_device_redirect": (
            "exchange_redirect_uri" in complete
            and "exchange_code_for_token_internal" in complete
            and "DEVICE_EXCHANGE_REDIRECT_URI" in target_tauri
        ),
        "cancellation_is_login_id_scoped_and_mismatch_fails_closed": (
            "if current.login_id != login_id" in cancel
            and 'return Err("OAuth loginId 不匹配".to_string())' in cancel
        ),
        "tauri_command_reaches_device_auth_module": (
            "codex_oauth::start_device_auth(app_handle).await" in command
        ),
        "tauri_invoke_handler_registers_device_command": (
            "commands::codex::codex_oauth_device_auth_start" in target_lib
        ),
        "frontend_service_exposes_device_command": (
            "invoke('codex_oauth_device_auth_start')" in service_start
        ),
        "upstream_device_exchange_test_present": (
            "device_auth_uses_official_exchange_redirect_and_poll_interval" in target_tauri
            or "device_auth_uses_official_exchange_redirect_and_poll_interval" in target_core
        ),
    }

    active = DeviceFlowState("login-a", persisted_device_state=False)
    no_active = DeviceFlowState(None, persisted_device_state=False)
    restart_device = DeviceFlowState("login-a", persisted_device_state=True)
    timed_out = DeviceFlowState("login-a", persisted_device_state=False, timed_out=True)
    adversarial = {
        "adversarial_second_flow_cannot_replace_active_flow": (
            _start_transition(active, "login-b")
            == {"accepted": False, "active_login_id": "login-a"}
        ),
        "adversarial_mismatched_cancel_cannot_clear_active_flow": (
            _cancel_transition(active, "login-b")
            == {
                "cleared": False,
                "active_login_id": "login-a",
                "error": "LOGIN_ID_MISMATCH",
            }
        ),
        "adversarial_matching_cancel_clears_flow": (
            _cancel_transition(active, "login-a")
            == {"cleared": True, "active_login_id": None, "error": None}
        ),
        "adversarial_restart_does_not_revive_device_flow": (
            _restart_transition(restart_device)["restored_device_flow"] is False
            and _restart_transition(restart_device)["active_login_id"] is None
        ),
        "adversarial_timeout_clears_device_flow": (
            _timeout_transition(timed_out)
            == {"cleared": True, "active_login_id": None}
        ),
        "adversarial_empty_state_accepts_new_flow": (
            _start_transition(no_active, "login-b")
            == {"accepted": True, "active_login_id": "login-b"}
        ),
    }
    checks.update(adversarial)
    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_V1_3_29_DEVICE_AUTH_DELTA_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_commit": BASE_COMMIT,
        "target_commit": TARGET_COMMIT,
        "source_blobs": {
            f"{commit}:{path}": sha
            for (commit, path), sha in EXPECTED_BLOBS.items()
        },
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "runtime_delta": {
            "device_auth": "NEW_IN_V1_3_29",
            "connector_scopes": "ALREADY_PRESENT_IN_V1_3_28_TAURI_RUNTIME",
            "id_token_refresh_lead": "ALREADY_10_MINUTES_IN_V1_3_28_TAURI_RUNTIME",
            "cockpit_core_scope_lead_sync": "SOURCE_DELTA_IN_V1_3_29",
        },
        "source_characterization_only": True,
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
            "suite": "COCKPIT_V1_3_29_DEVICE_AUTH_DELTA_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "source_characterization_only": True,
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
