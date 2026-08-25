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

MAIN_PATH = "sidecars/cockpit-cliproxy/main.go"
TEST_PATH = "sidecars/cockpit-cliproxy/main_test.go"
GO_MOD_PATH = "sidecars/cockpit-cliproxy/go.mod"

EXPECTED_BLOBS = {
    (BASE_COMMIT, MAIN_PATH): "7316022d43d7d7cbe4bb4b705ff4e969cd9baf83",
    (TARGET_COMMIT, MAIN_PATH): "e04325d1af2eb13b5c9fafdfc7d67c7b435bdf3b",
    (BASE_COMMIT, TEST_PATH): "cb58e674394ccbbf9b82a14dcb6ead4c197dc7f0",
    (TARGET_COMMIT, TEST_PATH): "7628a8d4df8ecf42ff3c1b0e869da55e04bc2e78",
    (BASE_COMMIT, GO_MOD_PATH): "1352ec4862b016a5e7f2f255dc91ed2b973f6b42",
    (TARGET_COMMIT, GO_MOD_PATH): "b36f59d9bfc3513d2225923b235b97efb1158354",
}

NEW_REALTIME_ROUTES = (
    'router.POST("/v1/live", s.handleCodexLive)',
    'router.GET("/v1/live/:call_id", s.handleCodexLiveSideband)',
    'router.POST("/v1/realtime/calls", s.handleCodexLive)',
    'router.GET("/v1/realtime/calls/:call_id", s.handleCodexLiveSideband)',
    'router.GET("/v1/realtime", s.handleCodexRealtimeWebsocket)',
    'router.POST("/v1/realtime", s.handleCodexRealtime)',
    'router.POST("/v1/realtime/client_secrets", s.handleCodexClientSecret)',
    'router.POST("/v1/realtime/sessions", s.handleCodexLegacySession)',
    'router.POST("/v1/realtime/transcription_sessions", s.handleCodexTranscriptionSession)',
    'router.GET("/v1/realtime/translations", s.handleCodexTranslation)',
    'router.POST("/v1/realtime/translations", s.handleCodexTranslation)',
    'router.POST("/v1/realtime/translations/client_secrets", s.handleCodexTranslation)',
    'router.POST("/v1/realtime/calls/:call_id/hangup", s.handleCodexHangup)',
    'router.POST("/v1/realtime/calls/:call_id/accept", s.handleCodexSIPControl)',
    'router.POST("/v1/realtime/calls/:call_id/reject", s.handleCodexSIPControl)',
    'router.POST("/v1/realtime/calls/:call_id/refer", s.handleCodexSIPControl)',
)


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


def _all_present(source: str, needles: tuple[str, ...]) -> bool:
    return all(needle in source for needle in needles)


def _all_absent(source: str, needles: tuple[str, ...]) -> bool:
    return all(needle not in source for needle in needles)


def source_proof() -> dict[str, Any]:
    sources, observed = _load_sources()
    base_main = sources[f"{BASE_COMMIT}:{MAIN_PATH}"]
    target_main = sources[f"{TARGET_COMMIT}:{MAIN_PATH}"]
    base_tests = sources[f"{BASE_COMMIT}:{TEST_PATH}"]
    target_tests = sources[f"{TARGET_COMMIT}:{TEST_PATH}"]
    base_mod = sources[f"{BASE_COMMIT}:{GO_MOD_PATH}"]
    target_mod = sources[f"{TARGET_COMMIT}:{GO_MOD_PATH}"]

    base_responses_ws = (
        'router.GET("/v1/responses", s.handleResponsesWebsocket)' in base_main
        and "func (s *relayServer) handleResponsesWebsocket" in base_main
        and "TestResponsesWebsocketRouteDisabledByDefault" in base_tests
    )
    target_responses_ws = (
        'router.GET("/v1/responses", s.handleResponsesWebsocket)' in target_main
        and "func (s *relayServer) handleResponsesWebsocket" in target_main
        and "TestResponsesWebsocketRouteDisabledByDefault" in target_tests
    )

    checks = {
        "v1328_main_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{MAIN_PATH}"] == EXPECTED_BLOBS[(BASE_COMMIT, MAIN_PATH)]
        ),
        "v1329_main_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{MAIN_PATH}"] == EXPECTED_BLOBS[(TARGET_COMMIT, MAIN_PATH)]
        ),
        "v1328_test_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{TEST_PATH}"] == EXPECTED_BLOBS[(BASE_COMMIT, TEST_PATH)]
        ),
        "v1329_test_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{TEST_PATH}"] == EXPECTED_BLOBS[(TARGET_COMMIT, TEST_PATH)]
        ),
        "v1328_go_mod_exact_blob_pinned": (
            observed[f"{BASE_COMMIT}:{GO_MOD_PATH}"] == EXPECTED_BLOBS[(BASE_COMMIT, GO_MOD_PATH)]
        ),
        "v1329_go_mod_exact_blob_pinned": (
            observed[f"{TARGET_COMMIT}:{GO_MOD_PATH}"] == EXPECTED_BLOBS[(TARGET_COMMIT, GO_MOD_PATH)]
        ),
        "responses_websocket_is_preexisting_not_new_v1329_surface": (
            base_responses_ws and target_responses_ws
        ),
        "v1328_has_no_live_or_realtime_route_matrix": _all_absent(
            base_main,
            NEW_REALTIME_ROUTES,
        ),
        "v1329_registers_complete_live_realtime_route_matrix": _all_present(
            target_main,
            NEW_REALTIME_ROUTES,
        ),
        "v1329_imports_and_constructs_codex_live_handler": (
            'codexlive "github.com/router-for-me/CLIProxyAPI/v7/internal/client/codex/live"' in target_main
            and "codexLive          *codexlive.Handler" in target_main
            and "liveHandler := codexlive.NewHandler(coreManager, cfg)" in target_main
            and "defer liveHandler.Close()" in target_main
            and "codexLive:          liveHandler" in target_main
        ),
        "v1328_does_not_construct_codex_live_handler": (
            "codexlive.NewHandler" not in base_main
            and "codexLive          *codexlive.Handler" not in base_main
        ),
        "live_routes_require_api_key_and_reject_provider_gateway": (
            "func (s *relayServer) handleCodexLive(c *gin.Context)" in target_main
            and "spec, ok := s.requireAPIKey(c)" in target_main
            and '"provider gateway does not support Codex live"' in target_main
            and '"live_not_supported"' in target_main
            and '"Codex live unavailable"' in target_main
        ),
        "realtime_routes_share_api_key_and_provider_gateway_guard": (
            "func (s *relayServer) codexRealtimeHandler" in target_main
            and '"provider gateway does not support Codex realtime"' in target_main
            and '"realtime_not_supported"' in target_main
            and '"Codex realtime unavailable"' in target_main
            and "s.codexRealtimeHandler(c" in target_main
        ),
        "realtime_handler_maps_all_operation_families": (
            "HandleRealtimeWebsocket(ctx)" in target_main
            and "CreateClientSecret(ctx)" in target_main
            and "CreateLegacySession(ctx)" in target_main
            and "HandleTranscriptionSession(ctx)" in target_main
            and "HandleTranslation(ctx)" in target_main
            and "HandleHangup(ctx)" in target_main
            and "HandleSIPControl(ctx)" in target_main
        ),
        "cliproxy_dependency_jumps_to_v7_2_140": (
            "github.com/router-for-me/CLIProxyAPI/v7 v7.1.22" in base_mod
            and "github.com/router-for-me/CLIProxyAPI/v7 v7.2.140" in target_mod
        ),
        "v1329_adds_webrtc_transport_dependency_stack": (
            "github.com/pion/webrtc/v4 v4.2.17" in target_mod
            and "github.com/pion/datachannel v1.6.2" in target_mod
            and "github.com/pion/ice/v4 v4.3.0" in target_mod
            and "github.com/pion/sdp/v3 v3.0.19" in target_mod
            and "github.com/pion/webrtc/v4" not in base_mod
        ),
        "v1329_tests_live_sideband_and_realtime_call_routes": (
            '"/v1/live/call-123"' in target_tests
            and '"/v1/realtime/calls"' in target_tests
            and "realtime call status" in target_tests
            and '"/v1/live/call-123"' not in base_tests
            and '"/v1/realtime/calls"' not in base_tests
        ),
        "responses_websocket_safety_remains_separate_preexisting_surface": (
            "TestResponsesWebsocketRouteDisabledByDefault" in target_tests
            and "TestResponsesWebsocketRejectsProviderGatewayBeforeCodexAuth" in target_tests
            and "TestResponsesWebsocketRouteDisabledByDefault" in base_tests
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
        "suite": "COCKPIT_V1_3_29_API_SERVICE_REALTIME_DELTA_SOURCE_PROOF",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "base_release": BASE_RELEASE,
        "base_commit": BASE_COMMIT,
        "target_release": TARGET_RELEASE,
        "target_commit": TARGET_COMMIT,
        "verdict": verdict,
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "observed_blob_sha1": observed,
        "new_realtime_route_count": len(NEW_REALTIME_ROUTES),
        "responses_websocket_preexisting_in_v1328": base_responses_ws,
        "delta_classification": (
            "P2_SOURCE_CHARACTERIZED_PROOF_WIRED" if verdict == "PASS" else "P2_SOURCE_PROOF_FAILED"
        ),
        "baseline_blocking": False,
        "hms_parity_implemented": False,
        "source_characterization_only": True,
        "real_realtime_runtime_executed": False,
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
            "suite": "COCKPIT_V1_3_29_API_SERVICE_REALTIME_DELTA_SOURCE_PROOF",
            "verdict": "FAIL",
            "error": str(exc),
            "baseline_blocking": False,
            "hms_parity_implemented": False,
            "source_characterization_only": True,
            "real_realtime_runtime_executed": False,
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
