#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"
BASE_RELEASE = "1.3.28"
BASE_COMMIT = "82576b9634bad0a365abc51eba8f022fb0a50d97"
TARGET_RELEASE = "1.3.29"
TARGET_COMMIT = "83ce2d192cc954cc910ce89edf2d1f710c218798"

PROTOCOL_PATH = "src-tauri/src/modules/codex_protocol.rs"
CATALOG_PATH = (
    "sidecars/cockpit-cliproxy/third_party/CLIProxyAPI/"
    "internal/registry/models/codex_client_models.json"
)
MAIN_PATH = "sidecars/cockpit-cliproxy/main.go"

EXPECTED_BLOBS = {
    (BASE_COMMIT, PROTOCOL_PATH): "b08f10d27859fff50dd11db68b297ea07109a9cd",
    (TARGET_COMMIT, PROTOCOL_PATH): "805062d894e10480a3021d2fc9b90bbcfad052a4",
    (BASE_COMMIT, CATALOG_PATH): "a0fecc5fae1f03d2316c49e3d9cb56ab7e99cb18",
    (TARGET_COMMIT, CATALOG_PATH): "34ead936acacdb4eec0ba49e5c9755098fd11338",
    (BASE_COMMIT, MAIN_PATH): "7316022d43d7d7cbe4bb4b705ff4e969cd9baf83",
    (TARGET_COMMIT, MAIN_PATH): "e04325d1af2eb13b5c9fafdfc7d67c7b435bdf3b",
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


def source_proof() -> dict[str, Any]:
    sources, observed = _load_sources()
    base_protocol = sources[f"{BASE_COMMIT}:{PROTOCOL_PATH}"]
    target_protocol = sources[f"{TARGET_COMMIT}:{PROTOCOL_PATH}"]
    base_catalog = sources[f"{BASE_COMMIT}:{CATALOG_PATH}"]
    target_catalog = sources[f"{TARGET_COMMIT}:{CATALOG_PATH}"]
    base_main = sources[f"{BASE_COMMIT}:{MAIN_PATH}"]
    target_main = sources[f"{TARGET_COMMIT}:{MAIN_PATH}"]

    base_managed_models = _segment(
        base_protocol,
        "pub(crate) fn managed_codex_model_ids() -> Vec<String> {",
        "pub fn normalize_responses_body_for_codex",
    )
    target_managed_models = _segment(
        target_protocol,
        "pub(crate) fn managed_codex_model_ids() -> Vec<String> {",
        "pub fn normalize_responses_body_for_codex",
    )

    base_reasoning_replay = (
        'const REASONING_ENCRYPTED_CONTENT_INCLUDE: &str = "reasoning.encrypted_content";'
        in base_protocol
        and "changed |= ensure_reasoning_include(obj);" in base_protocol
    )
    target_reasoning_replay = (
        'const REASONING_ENCRYPTED_CONTENT_INCLUDE: &str = "reasoning.encrypted_content";'
        in target_protocol
        and "changed |= ensure_reasoning_include(obj);" in target_protocol
    )
    base_multi_agent_v2 = '"multi_agent_version": "v2"' in base_catalog
    target_multi_agent_v2 = '"multi_agent_version": "v2"' in target_catalog
    base_responses_websocket = (
        'router.GET("/v1/responses", s.handleResponsesWebsocket)' in base_main
        and "func (s *relayServer) handleResponsesWebsocket" in base_main
    )
    target_responses_websocket = (
        'router.GET("/v1/responses", s.handleResponsesWebsocket)' in target_main
        and "func (s *relayServer) handleResponsesWebsocket" in target_main
    )

    checks = {
        "v1328_protocol_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{PROTOCOL_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, PROTOCOL_PATH)]
        ),
        "v1329_protocol_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{PROTOCOL_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, PROTOCOL_PATH)]
        ),
        "v1328_catalog_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{CATALOG_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, CATALOG_PATH)]
        ),
        "v1329_catalog_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{CATALOG_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, CATALOG_PATH)]
        ),
        "v1328_main_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{MAIN_PATH}"]
            == EXPECTED_BLOBS[(BASE_COMMIT, MAIN_PATH)]
        ),
        "v1329_main_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MAIN_PATH}"]
            == EXPECTED_BLOBS[(TARGET_COMMIT, MAIN_PATH)]
        ),
        "responses_websocket_preexists_v1329": (
            base_responses_websocket and target_responses_websocket
        ),
        "reasoning_replay_encrypted_content_preexists_v1329": (
            base_reasoning_replay and target_reasoning_replay
        ),
        "multi_agent_v2_catalog_metadata_preexists_v1329": (
            base_multi_agent_v2 and target_multi_agent_v2
        ),
        "v1328_managed_catalog_is_model_overrides_only": (
            '.get("model_overrides")' in base_managed_models
            and '.or_else(|| catalog.get("models")' not in base_managed_models
        ),
        "v1329_catalog_removes_model_overrides_authority": (
            '"model_overrides"' in base_catalog
            and '"model_overrides"' not in target_catalog
        ),
        "v1329_managed_catalog_falls_back_to_full_models_array": (
            'let overrides = catalog.get("model_overrides").and_then(Value::as_array);'
            in target_managed_models
            and '.or_else(|| catalog.get("models").and_then(Value::as_array));'
            in target_managed_models
        ),
        "v1329_full_catalog_fallback_is_responses_lite_and_visibility_bounded": (
            '.get("use_responses_lite")' in target_managed_models
            and '.get("visibility")' in target_managed_models
            and 'visibility.eq_ignore_ascii_case("hide")' in target_managed_models
        ),
        "v1329_catalog_adds_apps_plugin_and_node_repl_metadata": (
            '"include_apps_usage_instructions"' not in base_catalog
            and '"include_plugin_usage_instructions"' not in base_catalog
            and '"node_repl_auto_review_required"' not in base_catalog
            and '"node_repl_disabled"' not in base_catalog
            and '"include_apps_usage_instructions"' in target_catalog
            and '"include_plugin_usage_instructions"' in target_catalog
            and '"node_repl_auto_review_required"' in target_catalog
            and '"node_repl_disabled"' in target_catalog
        ),
        "catalog_blob_changes_between_releases": (
            EXPECTED_BLOBS[(BASE_COMMIT, CATALOG_PATH)]
            != EXPECTED_BLOBS[(TARGET_COMMIT, CATALOG_PATH)]
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
        "suite": "COCKPIT_V1_3_29_API_SERVICE_CONVERSATION_DELTA_SOURCE_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_release": BASE_RELEASE,
        "base_commit": BASE_COMMIT,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "verdict": verdict,
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "observed_blob_sha1": observed,
        "preexisting_capabilities": [
            "RESPONSES_WEBSOCKET",
            "REASONING_ENCRYPTED_CONTENT_REPLAY",
            "MULTI_AGENT_V2_CATALOG_METADATA",
        ],
        "new_source_delta": [
            "MANAGED_MODEL_CATALOG_FALLBACK_EXPANSION",
            "EXPANDED_CATALOG_METADATA",
        ],
        "delta_classification": (
            "P2_SOURCE_CHARACTERIZED_PROOF_WIRED"
            if verdict == "PASS"
            else "P2_SOURCE_PROOF_FAILED"
        ),
        "baseline_blocking": False,
        "hms_parity_implemented": False,
        "source_characterization_only": True,
        "real_conversation_runtime_executed": False,
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
            "suite": "COCKPIT_V1_3_29_API_SERVICE_CONVERSATION_DELTA_SOURCE_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "baseline_blocking": False,
            "hms_parity_implemented": False,
            "source_characterization_only": True,
            "real_conversation_runtime_executed": False,
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
