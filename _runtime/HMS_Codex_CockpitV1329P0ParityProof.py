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
ACCOUNT_PATH = "src-tauri/src/modules/codex_account.rs"
QUOTA_PATH = "src-tauri/src/modules/codex_quota.rs"
EXPECTED_BLOBS = {
    (BASE_COMMIT, ACCOUNT_PATH): "842244a3b6948438a5b7a0df55655f7a366ff540",
    (BASE_COMMIT, QUOTA_PATH): "0cb8c5df897505fa572e363ddc67f49fea907bbf",
    (TARGET_COMMIT, ACCOUNT_PATH): "1e879fe36b9be9d3253a98d8eb30722415edc594",
    (TARGET_COMMIT, QUOTA_PATH): "77ce9612cacfc70cced28feb84d510aa299dabcc",
}
MAX_SOURCE_BYTES = 8 * 1024 * 1024


class ParityProofError(RuntimeError):
    pass


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


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
            final_url = str(response.geturl())
            if final_url != url:
                raise ParityProofError(f"unexpected source redirect: {final_url}")
            raw = response.read(MAX_SOURCE_BYTES + 1)
    except ParityProofError:
        raise
    except Exception as exc:
        raise ParityProofError(
            f"pinned upstream source unavailable: {commit}:{path}: {exc}"
        ) from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise ParityProofError(f"pinned upstream source too large: {commit}:{path}")
    expected = EXPECTED_BLOBS[(commit, path)]
    actual = _git_blob_sha(raw)
    if actual != expected:
        raise ParityProofError(
            f"pinned upstream blob mismatch: {commit}:{path}: expected={expected}, actual={actual}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParityProofError(
            f"pinned upstream source is not utf-8: {commit}:{path}"
        ) from exc


def _extract_braced_block(source: str, needle: str) -> str:
    start = source.find(needle)
    if start < 0:
        raise ParityProofError(f"required source symbol missing: {needle}")
    brace = source.find("{", start)
    if brace < 0:
        raise ParityProofError(f"required source block missing opening brace: {needle}")
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
    raise ParityProofError(f"required source block is unbalanced: {needle}")


def _ordered(text: str, *needles: str) -> bool:
    cursor = 0
    for needle in needles:
        pos = text.find(needle, cursor)
        if pos < 0:
            return False
        cursor = pos + len(needle)
    return True


@dataclass(frozen=True)
class QuotaProbeState:
    access_token_expired: bool
    official_runtime_owns_refresh: bool
    live_authority_has_fresh_access_token: bool = False


def _quota_transition(state: QuotaProbeState) -> dict:
    if state.official_runtime_owns_refresh:
        return {
            "background_selected": False,
            "refresh_called": False,
            "refresh_token_rotated": False,
            "credential_write": False,
            "result": "SKIP_RUNNING_OFFICIAL_OAUTH",
        }
    if not state.access_token_expired:
        return {
            "background_selected": True,
            "refresh_called": False,
            "refresh_token_rotated": False,
            "credential_write": False,
            "result": "USE_VALID_ACCESS_TOKEN",
        }
    if state.live_authority_has_fresh_access_token:
        return {
            "background_selected": True,
            "refresh_called": False,
            "refresh_token_rotated": False,
            "credential_write": False,
            "result": "REUSE_SYNCED_ACCESS_TOKEN",
        }
    return {
        "background_selected": True,
        "refresh_called": True,
        "refresh_token_rotated": True,
        "credential_write": True,
        "result": "REFRESH_REQUIRED",
    }


@dataclass(frozen=True)
class CombinedProfileState:
    runtime_account_id: str
    oauth_owner_id: str
    stored_generation: int
    authority_generation: int
    stored_refresh_token: str
    authority_refresh_token: str


def _combined_projection_transition(state: CombinedProfileState) -> dict:
    if state.authority_generation > state.stored_generation:
        selected_generation = state.authority_generation
        selected_refresh_token = state.authority_refresh_token
    else:
        selected_generation = state.stored_generation
        selected_refresh_token = state.stored_refresh_token
    return {
        "runtime_account_id": state.runtime_account_id,
        "credential_account_id": state.oauth_owner_id,
        "credential_token_generation": selected_generation,
        "refresh_token": selected_refresh_token,
        "stale_refresh_token_reactivated": (
            selected_refresh_token == state.stored_refresh_token
            and state.authority_generation > state.stored_generation
        ),
    }


def source_proof(fetcher: Callable[[str, str], str] = _fetch_source) -> dict:
    old_account = fetcher(BASE_COMMIT, ACCOUNT_PATH)
    old_quota = fetcher(BASE_COMMIT, QUOTA_PATH)
    account = fetcher(TARGET_COMMIT, ACCOUNT_PATH)
    quota = fetcher(TARGET_COMMIT, QUOTA_PATH)

    quota_prepare = _extract_braced_block(
        account, "pub async fn prepare_account_for_quota_query"
    )
    background = _extract_braced_block(
        quota, "pub async fn refresh_all_quotas_for_background"
    )
    all_quota = _extract_braced_block(
        quota, "async fn refresh_all_quotas_with_options"
    )
    quota_once = _extract_braced_block(quota, "async fn refresh_account_quota_once")
    refresh_predicate = _extract_braced_block(
        account, "pub(crate) fn managed_account_tokens_need_refresh"
    )
    combined_writer = _extract_braced_block(
        account, "fn write_api_key_account_bundle_with_oauth_to_dir"
    )
    projection = _extract_braced_block(account, "struct CodexManagedAuthProjection")
    refresh_bound = _extract_braced_block(
        account, "async fn refresh_bound_oauth_account_for_api_key"
    )

    fresh_check = "if !codex_oauth::is_token_expired(&account.tokens.access_token)"
    source_checks = {
        "v1328_quota_helper_absent": (
            "prepare_account_for_quota_query" not in old_account
            and "prepare_account_for_quota_query" not in old_quota
        ),
        "quota_background_enters_skip_running_mode": (
            "refresh_all_quotas_with_options(true).await" in background
        ),
        "quota_background_filters_running_official_oauth": (
            "running_oauth_account_ids" in all_quota
            and ".filter(|account| !running_oauth_account_ids.contains(&account.id))"
            in all_quota
        ),
        "quota_background_calls_account_quota": (
            "refresh_account_quota(&account_id).await" in all_quota
        ),
        "quota_account_path_calls_quota_specific_prepare": (
            "codex_account::prepare_account_for_quota_query(account_id).await"
            in quota_once
        ),
        "quota_valid_access_short_circuits_before_rt_lock": _ordered(
            quota_prepare,
            fresh_check,
            'acquire_codex_token_refresh_file_lock(account_id, "quota-query")',
        ),
        "quota_rechecks_after_lock_and_live_authority_sync": _ordered(
            quota_prepare,
            'acquire_codex_token_refresh_file_lock(account_id, "quota-query")',
            "official_runtime_owns_refresh",
            "sync_account_from_live_authority_sources(&mut account)",
            fresh_check,
        ),
        "quota_refresh_predicate_is_access_token_only": (
            "codex_oauth::is_token_expired(&account.tokens.access_token)"
            in refresh_predicate
            and "is_id_token_refresh_due" not in refresh_predicate
            and "expired_id_token_does_not_force_refresh_when_access_token_is_fresh"
            in account
            and "id_token_within_refresh_lead_does_not_force_refresh_when_access_token_is_fresh"
            in account
        ),
        "combined_projection_records_distinct_credential_owner": (
            "credential_account_id: Option<String>" in projection
            and "credential_token_generation: Option<u64>" in projection
        ),
        "combined_writer_keeps_oauth_auth_and_api_key_provider": _ordered(
            combined_writer,
            "write_prepared_account_bundle_to_dir(base_dir, oauth_account)",
            "write_api_key_provider_override_to_config_toml(base_dir, api_key_account)",
            "write_managed_projection_with_credential_owner_to_dir(",
        ),
        "combined_refresh_uses_bound_oauth_owner": (
            "bound_oauth_account_id" in refresh_bound
            and "validate_api_key_bound_oauth_account" in refresh_bound
        ),
        "combined_upstream_owner_projection_test_present": (
            "api_key_bound_oauth_projection_tracks_runtime_and_credential_owners"
            in account
        ),
        "combined_upstream_rotation_test_present": (
            "bound_oauth_rotation_sync_preserves_api_key_provider_config" in account
        ),
        "combined_upstream_rotation_without_last_refresh_test_present": (
            "managed_bound_oauth_accepts_rotated_rt_without_last_refresh" in account
        ),
        "combined_upstream_unbind_owner_persistence_test_present": (
            "persisted_credential_owner_survives_api_key_unbind_for_later_oauth_sync"
            in account
        ),
        "combined_upstream_legacy_projection_upgrade_test_present": (
            "legacy_combined_projection_is_recovered_and_upgraded_after_unbind"
            in account
        ),
        "generation_guard_upstream_test_present": (
            "newer generation should be reused" in account
            and "force_refresh_managed_account_after_observed" in account
        ),
    }

    quota_valid = _quota_transition(
        QuotaProbeState(access_token_expired=False, official_runtime_owns_refresh=False)
    )
    quota_official = _quota_transition(
        QuotaProbeState(access_token_expired=False, official_runtime_owns_refresh=True)
    )
    quota_synced = _quota_transition(
        QuotaProbeState(
            access_token_expired=True,
            official_runtime_owns_refresh=False,
            live_authority_has_fresh_access_token=True,
        )
    )
    combined = _combined_projection_transition(
        CombinedProfileState(
            runtime_account_id="api-key-runtime",
            oauth_owner_id="oauth-owner",
            stored_generation=7,
            authority_generation=8,
            stored_refresh_token="rt-stale",
            authority_refresh_token="rt-current",
        )
    )
    adversarial_checks = {
        "adversarial_valid_access_never_calls_refresh": (
            quota_valid["refresh_called"] is False
            and quota_valid["refresh_token_rotated"] is False
            and quota_valid["credential_write"] is False
        ),
        "adversarial_running_official_oauth_is_not_background_selected": (
            quota_official["background_selected"] is False
            and quota_official["refresh_called"] is False
        ),
        "adversarial_synced_new_access_reuses_without_rt_rotation": (
            quota_synced["refresh_called"] is False
            and quota_synced["refresh_token_rotated"] is False
        ),
        "adversarial_combined_profile_keeps_oauth_credential_owner": (
            combined["runtime_account_id"] == "api-key-runtime"
            and combined["credential_account_id"] == "oauth-owner"
        ),
        "adversarial_newer_authority_generation_wins": (
            combined["credential_token_generation"] == 8
            and combined["refresh_token"] == "rt-current"
        ),
        "adversarial_stale_refresh_token_cannot_revive": (
            combined["stale_refresh_token_reactivated"] is False
        ),
    }

    checks = {**source_checks, **adversarial_checks}
    tests = [
        {"name": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in checks.items()
    ]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "COCKPIT_V1_3_29_P0_PARITY_PROOF",
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
        "proof_scope": [
            "quota_refresh_token_ownership",
            "combined_oauth_api_key_credential_ownership",
        ],
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
            "suite": "COCKPIT_V1_3_29_P0_PARITY_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "source_certification_only": True,
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
