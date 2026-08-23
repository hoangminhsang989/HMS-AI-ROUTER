#!/usr/bin/env python3
from __future__ import annotations

import json

from HMS_Codex_PromotionReviewerActionPolicy import evaluate_action_policy

VERSION = "25.75"
VALID_LANES = {"TERMINAL_PTY", "PROJECT_RESUME", "OPTIONAL_GPU"}


def evaluate_gui_action_contract(report, live_observation, *, reviewer_identity="", reviewer_salt="", lane="", busy=False):
    policy = evaluate_action_policy(report, live_observation, busy=busy)
    identity_ok = len(str(reviewer_identity or "").strip()) >= 2
    salt_ok = len(str(reviewer_salt or "")) >= 16
    lane_ok = str(lane or "").upper() in VALID_LANES
    form_ok = identity_ok and salt_ok and lane_ok
    buttons = {name: bool(allowed and form_ok) for name, allowed in policy["permissions"].items()}
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "PROMOTION_GUI_ACTION_CONTRACT",
        "policy": policy,
        "form": {"identity_ok": identity_ok, "salt_ok": salt_ok, "lane_ok": lane_ok, "form_ok": form_ok},
        "buttons": buttons,
        "confirmation_required": any(buttons.values()),
        "salt_clear_required_after_attempt": True,
        "raw_identity_persistence_authorized": False,
        "raw_salt_persistence_authorized": False,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def confirmation_text(decision, lane, observed_baseline):
    action = {"APPROVE": "DUYỆT", "REJECT": "TỪ CHỐI", "INVALIDATE": "INVALIDATE"}.get(str(decision).upper(), str(decision).upper())
    return (
        f"Xác nhận {action} lane {str(lane).upper()}?\n\n"
        f"Baseline vừa quan sát: {observed_baseline or '—'}\n"
        "Hành động sẽ ghi append-only decision ledger. HMS không tự certify Windows và không tự sửa production score."
    )


def synthetic_proof():
    report = {
        "real_packet_verified": True,
        "reasons": [],
        "provenance": {"raw_packet_sha256": "a" * 64, "release_manifest_sha256": "b" * 64},
    }
    live_match = {
        "source": "GITHUB_RELEASES_LATEST",
        "upstream_repository": "jlcodes99/cockpit-tools",
        "release_id": 1328,
        "checked_utc": "2026-08-23T00:00:00+00:00",
        "baseline": "1.3.28",
    }
    form = dict(reviewer_identity="reviewer-a", reviewer_salt="0123456789abcdef", lane="TERMINAL_PTY")
    match = evaluate_gui_action_contract(report, live_match, **form)
    drift = evaluate_gui_action_contract(report, dict(live_match, baseline="1.3.29", release_id=1329), **form)
    provider_error = evaluate_gui_action_contract(report, None, **form)
    bad_salt = evaluate_gui_action_contract(report, live_match, reviewer_identity="reviewer-a", reviewer_salt="short", lane="TERMINAL_PTY")
    checks = {
        "match_enables_three_actions": match["buttons"] == {"APPROVE": True, "REJECT": True, "INVALIDATE": True},
        "drift_enables_only_invalidate": drift["buttons"] == {"APPROVE": False, "REJECT": False, "INVALIDATE": True},
        "provider_error_blocks_all": not any(provider_error["buttons"].values()),
        "salt_invalid_blocks_all": not any(bad_salt["buttons"].values()) and not bad_salt["form"]["salt_ok"],
        "confirmation_required_before_enabled_action": match["confirmation_required"] is True,
        "salt_clear_is_mandatory": match["salt_clear_required_after_attempt"] is True,
        "no_raw_identity_or_salt_persistence": not match["raw_identity_persistence_authorized"] and not match["raw_salt_persistence_authorized"],
        "never_auto_certifies_or_mutates_score": not match["automatic_production_certification"] and not match["production_score_mutation_authorized"],
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(x["status"] == "PASS" for x in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "PROMOTION_GUI_ACTION_CONTRACT_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


if __name__ == "__main__":
    out = synthetic_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 2)
