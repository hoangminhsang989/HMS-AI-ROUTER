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

MODEL_PATH = "src-tauri/src/models/codex_local_access.rs"
MODULE_PATH = "src-tauri/src/modules/codex_local_access.rs"
TYPES_PATH = "src/types/codexLocalAccess.ts"

EXPECTED_BLOBS = {
    (BASE_COMMIT, MODEL_PATH): "66d86e5f81daec446a6929d176f6241b2b60a1ca",
    (TARGET_COMMIT, MODEL_PATH): "5490dc89818a949d9d0cb6818342fc38f650d3c2",
    (BASE_COMMIT, MODULE_PATH): "13da594f8d5a84447514635733c9adc0eff71bca",
    (TARGET_COMMIT, MODULE_PATH): "5f54deda290ad11118f0582a23bc7a7b9867e024",
    (BASE_COMMIT, TYPES_PATH): "9622fa26a4a4edcc8140231a96850750673511a5",
    (TARGET_COMMIT, TYPES_PATH): "1845d06d98ef21899f40c4bc09ce8a01ac291890",
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
    with urllib.request.urlopen(request, timeout=30) as response:
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


@dataclass(frozen=True)
class UsageRow:
    local_account_id: str
    official_account_id: str
    input_tokens: int


def _base_window_total(rows: list[UsageRow], local_id: str, official_id: str) -> int:
    # v1.3.28 semantics: if official identity is supplied, it wins over local identity.
    if official_id.strip():
        return sum(row.input_tokens for row in rows if row.official_account_id == official_id)
    return sum(
        row.input_tokens
        for row in rows
        if not row.official_account_id and row.local_account_id == local_id
    )


def _target_window_total(rows: list[UsageRow], local_id: str) -> int:
    # v1.3.29 semantics: account-window aggregation is keyed only by local account id.
    return sum(row.input_tokens for row in rows if row.local_account_id == local_id)


def source_proof() -> dict[str, Any]:
    sources, observed = _load_sources()
    base_model = sources[f"{BASE_COMMIT}:{MODEL_PATH}"]
    target_model = sources[f"{TARGET_COMMIT}:{MODEL_PATH}"]
    base_module = sources[f"{BASE_COMMIT}:{MODULE_PATH}"]
    target_module = sources[f"{TARGET_COMMIT}:{MODULE_PATH}"]
    base_types = sources[f"{BASE_COMMIT}:{TYPES_PATH}"]
    target_types = sources[f"{TARGET_COMMIT}:{TYPES_PATH}"]

    base_query_model = _segment(
        base_model,
        "pub struct CodexLocalAccessAccountWindowQuery {",
        "pub struct CodexLocalAccessAccountWindowStats {",
    )
    target_query_model = _segment(
        target_model,
        "pub struct CodexLocalAccessAccountWindowQuery {",
        "pub struct CodexLocalAccessAccountWindowStats {",
    )
    base_query_type = _segment(
        base_types,
        "export interface CodexLocalAccessAccountWindowQuery {",
        "export interface CodexLocalAccessAccountWindowStats {",
    )
    target_query_type = _segment(
        target_types,
        "export interface CodexLocalAccessAccountWindowQuery {",
        "export interface CodexLocalAccessAccountWindowStats {",
    )
    base_window_impl = _segment(
        base_module,
        "fn backfill_legacy_official_account_ids(",
        "pub async fn query_local_access_account_window_stats(",
    )
    target_window_impl = _segment(
        target_module,
        "fn account_window_stat_identity_matches(",
        "pub async fn query_local_access_account_window_stats(",
    )

    rows = [
        UsageRow("local-member-a", "shared-team", 11),
        UsageRow("local-member-b", "shared-team", 22),
    ]
    base_a = _base_window_total(rows, "local-member-a", "shared-team")
    base_b = _base_window_total(rows, "local-member-b", "shared-team")
    target_a = _target_window_total(rows, "local-member-a")
    target_b = _target_window_total(rows, "local-member-b")

    checks = {
        "v1328_model_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{MODEL_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, MODEL_PATH)]
        ),
        "v1329_model_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MODEL_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, MODEL_PATH)]
        ),
        "v1328_module_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{MODULE_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, MODULE_PATH)]
        ),
        "v1329_module_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MODULE_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, MODULE_PATH)]
        ),
        "v1328_types_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{TYPES_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, TYPES_PATH)]
        ),
        "v1329_types_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{TYPES_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, TYPES_PATH)]
        ),
        "v1328_query_exposes_official_identity_and_email": (
            "pub official_account_id: String" in base_query_model
            and "pub account_email: String" in base_query_model
            and "officialAccountId: string" in base_query_type
            and "accountEmail: string" in base_query_type
        ),
        "v1329_query_contract_removes_official_identity_fallback_inputs": (
            "pub official_account_id: String" not in target_query_model
            and "pub account_email: String" not in target_query_model
            and "officialAccountId: string" not in target_query_type
            and "accountEmail: string" not in target_query_type
            and "pub account_id: String" in target_query_model
            and "accountId: string" in target_query_type
        ),
        "v1328_window_query_prefers_official_identity_when_present": (
            "fn backfill_legacy_official_account_ids(" in base_window_impl
            and "official_account_id: String" in base_window_impl
            and "if official_account_id.is_empty()" in base_window_impl
            and "official_account_ids.insert(official_account_id.clone())" in base_window_impl
            and "spec.official_account_id == row_official_account_id" in base_window_impl
        ),
        "v1329_window_query_declares_local_id_as_statistics_key": (
            "API 服务请求日志的 `account_id` 是本地 Codex 账号 ID" in target_window_impl
            and "Team/Workspace 的官方 `account_id` 可能被多个成员共享" in target_window_impl
            and "不能作为本地账号统计键" in target_window_impl
        ),
        "v1329_window_query_matches_row_and_requested_local_id_directly": (
            "fn account_window_stat_identity_matches(" in target_window_impl
            and "!row_account_id.is_empty() && row_account_id == requested_account_id"
            in target_window_impl
            and "account_window_stat_identity_matches(&row_account_id, &spec.account_id)"
            in target_window_impl
        ),
        "v1329_sql_filters_only_local_account_id_for_window_stats": (
            '"SELECT account_id, timestamp,' in target_window_impl
            and "AND account_id IN ({placeholders})" in target_window_impl
            and "SELECT account_id, official_account_id, timestamp" not in target_window_impl
        ),
        "official_account_id_remains_log_metadata_not_window_identity": (
            "official_account_id TEXT NOT NULL DEFAULT ''" in target_module
            and "UPDATE request_logs SET official_account_id = ?1 WHERE event_key = ?2"
            in target_module
        ),
        "upstream_regression_test_separates_local_team_members": (
            "account_window_stats_match_local_account_id_not_shared_team_id" in target_module
            and '"local-member-a".to_string()' in target_module
            and '"local-member-b".to_string()' in target_module
            and 'assert_eq!(stats.get("local-member-a"), Some(&11));' in target_module
            and 'assert_eq!(stats.get("local-member-b"), Some(&22));' in target_module
        ),
        "adversarial_v1328_shared_team_id_would_duplicate_window_totals": (
            base_a == 33 and base_b == 33
        ),
        "adversarial_v1329_local_ids_remain_separate": (
            target_a == 11 and target_b == 22
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
        "suite": "COCKPIT_V1_3_29_API_SERVICE_USAGE_ATTRIBUTION_SOURCE_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_release": BASE_RELEASE,
        "base_commit": BASE_COMMIT,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "verdict": verdict,
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "observed_blob_sha1": observed,
        "accounting_identity_before": "OFFICIAL_ACCOUNT_ID_WHEN_AVAILABLE",
        "accounting_identity_after": "COCKPIT_LOCAL_ACCOUNT_ID",
        "official_account_id_retained_as_log_metadata": True,
        "delta_classification": (
            "P2_SOURCE_CHARACTERIZED_PROOF_WIRED"
            if verdict == "PASS"
            else "P2_SOURCE_PROOF_FAILED"
        ),
        "baseline_blocking": False,
        "hms_parity_implemented": False,
        "source_characterization_only": True,
        "real_accounting_runtime_executed": False,
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
            "suite": "COCKPIT_V1_3_29_API_SERVICE_USAGE_ATTRIBUTION_SOURCE_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "baseline_blocking": False,
            "hms_parity_implemented": False,
            "source_characterization_only": True,
            "real_accounting_runtime_executed": False,
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
