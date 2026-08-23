#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from typing import Callable

VERSION = "25.75"
UPSTREAM_REPOSITORY = "jlcodes99/cockpit-tools"
LATEST_RELEASE_API = f"https://api.github.com/repos/{UPSTREAM_REPOSITORY}/releases/latest"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
MAX_RESPONSE_BYTES = 256 * 1024


class LiveBaselineError(RuntimeError):
    pass


def _normalize_version(tag: object) -> str:
    value = str(tag or "").strip()
    match = SEMVER.fullmatch(value)
    if not match:
        raise LiveBaselineError("upstream latest release tag is not a supported semantic version")
    return ".".join(match.groups())


def _validate_release_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise LiveBaselineError("upstream latest release payload is not an object")
    if payload.get("draft") is True:
        raise LiveBaselineError("upstream latest release is draft")
    if payload.get("prerelease") is True:
        raise LiveBaselineError("upstream latest release is prerelease")
    version = _normalize_version(payload.get("tag_name"))
    html_url = str(payload.get("html_url") or "")
    expected_prefix = f"https://github.com/{UPSTREAM_REPOSITORY}/releases/"
    if not html_url.startswith(expected_prefix):
        raise LiveBaselineError("upstream release provenance URL mismatch")
    release_id = payload.get("id")
    if not isinstance(release_id, int) or release_id <= 0:
        raise LiveBaselineError("upstream release id missing or invalid")
    return {
        "baseline": version,
        "tag_name": str(payload.get("tag_name")),
        "release_id": release_id,
        "release_url": html_url,
        "published_at": str(payload.get("published_at") or ""),
    }


def _fetch_latest_release_json(*, timeout_seconds: float = 8.0) -> dict:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"HMS-AI-ROUTER/{VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=max(2.0, float(timeout_seconds)), context=context) as response:
            final_url = str(response.geturl())
            if final_url != LATEST_RELEASE_API:
                raise LiveBaselineError("upstream release API redirected unexpectedly")
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "json" not in content_type:
                raise LiveBaselineError("upstream release API returned non-JSON content")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise LiveBaselineError("upstream release API response too large")
    except LiveBaselineError:
        raise
    except Exception as exc:
        raise LiveBaselineError(f"upstream release API unavailable: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveBaselineError("upstream release API JSON invalid") from exc
    return value


class CockpitLiveBaselineProvider:
    """Read the current upstream Cockpit Tools release at reviewer-action time.

    The default path performs a fresh HTTPS request on every observation. Tests may
    inject a deterministic fetcher; production callers should not cache the result
    across reviewer actions.
    """

    def __init__(self, fetcher: Callable[[], dict] | None = None):
        self._fetcher = fetcher or _fetch_latest_release_json

    def observe(self) -> dict:
        payload = self._fetcher()
        release = _validate_release_payload(payload)
        return {
            "product": "HMS-AI-ROUTER",
            "version": VERSION,
            "source": "GITHUB_RELEASES_LATEST",
            "upstream_repository": UPSTREAM_REPOSITORY,
            "api_url": LATEST_RELEASE_API,
            "checked_utc": datetime.now(timezone.utc).isoformat(),
            **release,
        }

    def get_live_baseline(self) -> str:
        return self.observe()["baseline"]

    def __call__(self) -> str:
        return self.get_live_baseline()


def synthetic_proof():
    good_payload = {
        "id": 1328,
        "tag_name": "v1.3.28",
        "draft": False,
        "prerelease": False,
        "html_url": f"https://github.com/{UPSTREAM_REPOSITORY}/releases/tag/v1.3.28",
        "published_at": "2026-08-23T00:00:00Z",
    }
    calls = []

    def good_fetcher():
        calls.append(1)
        return dict(good_payload)

    provider = CockpitLiveBaselineProvider(good_fetcher)
    first = provider.observe()
    second = provider.get_live_baseline()

    failures = {}
    for name, patch in {
        "draft_rejected": {"draft": True},
        "prerelease_rejected": {"prerelease": True},
        "invalid_tag_rejected": {"tag_name": "latest"},
        "wrong_provenance_rejected": {"html_url": "https://example.invalid/release/v1.3.28"},
    }.items():
        payload = dict(good_payload)
        payload.update(patch)
        try:
            CockpitLiveBaselineProvider(lambda p=payload: p).observe()
            failures[name] = False
        except LiveBaselineError:
            failures[name] = True

    checks = {
        "official_repository_pinned": first["upstream_repository"] == UPSTREAM_REPOSITORY,
        "stable_release_observed": first["baseline"] == "1.3.28",
        "provider_rechecks_each_call": len(calls) == 2 and second == "1.3.28",
        **failures,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "COCKPIT_LIVE_BASELINE_PROVIDER_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


if __name__ == "__main__":
    result = synthetic_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 2)
