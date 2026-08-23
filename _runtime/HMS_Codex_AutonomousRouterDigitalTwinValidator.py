#!/usr/bin/env python3
from __future__ import annotations

import argparse,re
import json
import tempfile
from pathlib import Path
from typing import Any

import HMS_Codex_AutonomousRouterDigitalTwin as twin

VERSION = "25.55"


def run(root: Path) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        tests.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:240]})

    report = twin.run(root, [13, 29, 47, 61, 79, 97], 300, 32, 12, 24)
    s = report.get("summary") or {}
    add("verdict_pass", str(report.get("verdict") or "").startswith("PASS"))
    add("version_25_55", report.get("version") == VERSION)
    add("six_seeds", int(s.get("seeds") or 0) == 6)
    add("at_least_1800_cycles", int(s.get("total_cycles") or 0) >= 1800)
    add("pool_32_accounts", int(s.get("accounts") or 0) == 32)
    add("pool_12_instances", int(s.get("instances") or 0) == 12)
    add("pool_24_projects", int(s.get("projects") or 0) == 24)
    add("all_seeds_pass", int(s.get("seed_pass") or 0) == int(s.get("seed_total") or 0) == 6)
    add("all_events_exercised", set(report.get("event_catalog") or []) <= set(report.get("events_exercised") or []))
    add("all_15_events", int(s.get("events_exercised") or 0) == int(s.get("events_required") or 0) == 15)

    rows = report.get("seed_runs") or []
    add("zero_invariant_failures", all(not (r.get("failures") or []) for r in rows))
    add("hard_failover_exercised", sum(int(r.get("hard_failovers") or 0) for r in rows) > 0)
    add("rotation_exercised", sum(int(r.get("rotations") or 0) for r in rows) > 0)
    add("backpressure_rejection_exercised", sum(int(r.get("rejected_sessions") or 0) for r in rows) > 0)
    add("no_eligible_starvation", all(int((r.get("fairness") or {}).get("starved_eligible") or 0) == 0 for r in rows))
    add("fairness_jain_reasonable", min(float((r.get("fairness") or {}).get("jain") or 0.0) for r in rows) >= 0.55)
    add("max_share_bounded", max(float((r.get("fairness") or {}).get("max_share") or 1.0) for r in rows) < 0.20)
    add("instance_capacity_bounded", all(int(r.get("max_instance_inflight") or 0) <= int(r.get("max_instance_capacity") or 0) for r in rows))

    replay = report.get("deterministic_replay") or []
    add("two_replays", len(replay) >= 2)
    add("deterministic_replay", all(bool(x.get("match")) for x in replay))
    one = twin.run_seed(255501, 160, 16, 8, 12)
    two = twin.run_seed(255501, 160, 16, 8, 12)
    three = twin.run_seed(255502, 160, 16, 8, 12)
    add("same_seed_same_hash", one.get("trace_hash") == two.get("trace_hash"))
    add("different_seed_different_hash", one.get("trace_hash") != three.get("trace_hash"))
    add("small_seed_pass", bool(one.get("pass") and two.get("pass") and three.get("pass")))

    mc = report.get("bounded_model_check") or {}
    add("model_checker_pass", mc.get("pass") is True)
    add("model_checker_zero_fail", not (mc.get("failures") or []))
    add("model_checker_3072_states", int(mc.get("states_checked") or 0) == 3072)
    add("model_checker_broad", int(mc.get("states_checked") or 0) >= 3000)

    tm = report.get("trace_minimization") or {}
    add("mutant_detected", tm.get("mutant_detected") is True)
    add("trace_minimization_pass", tm.get("pass") is True)
    add("trace_reduced", int(tm.get("minimized_length") or 99) < int(tm.get("original_length") or 0))
    add("trace_reduced_to_at_most_3", int(tm.get("minimized_length") or 99) <= 3)
    add("trace_contains_fail_recover", tm.get("contains_required_events") is True)
    add("trace_hash_present", len(str(tm.get("minimized_trace_hash") or "")) == 64)

    adv = report.get("adversarial_ordering") or {}
    add("adversarial_pass", adv.get("pass") is True)
    add("no_account_recovery_pullback", adv.get("account_recovery_pullback") is False)
    add("no_instance_recovery_pullback", adv.get("instance_recovery_pullback") is False)
    add("stale_high_quota_blocked", adv.get("stale_high_quota_blocked") is True)
    add("adversarial_has_sessions", int(adv.get("initial_sessions") or 0) >= 20)

    safety = report.get("safety") or {}
    add("synthetic_only", safety.get("synthetic_only") is True)
    add("no_real_codex_request", safety.get("real_codex_request_sent") is False)
    add("no_real_quota", safety.get("real_quota_consumed") is False)
    add("no_real_auth", safety.get("real_auth_read_or_mutated") is False)
    add("no_real_lan_required", safety.get("real_lan_smb_required") is False)
    add("project_affinity_preserved", safety.get("project_affinity_preserved") is True)
    add("session_continuity_preserved", safety.get("session_continuity_preserved") is True)
    add("stale_fail_closed", safety.get("stale_quota_fail_closed") is True)
    add("production_never_claimed", safety.get("production_certification") == "NOT_CLAIMED_DIGITAL_TWIN_ONLY")
    add("claim_boundary_explicit", "cannot emit target-machine production certification" in str(report.get("claim_boundary") or ""))
    add("report_has_no_secret_shape", not twin.has_secret_shape(report))

    # Static/integration contracts.
    engine = (root / "HMS_Codex_AutonomousRouterDigitalTwin.py").read_text("utf-8")
    regression = (root / "HMS_Codex_RegressionFreezeValidator.py").read_text("utf-8")
    main = (root / "HMS_AI_ROUTER_v25.23.1.ps1").read_text("utf-8-sig")
    add("engine_version_literal", 'VERSION = "25.55"' in engine)
    add("regression_suite_present", "autonomous_router_digital_twin" in regression and "HMS_Codex_AutonomousRouterDigitalTwinValidator.py" in regression)
    add("main_version_at_least_25_55", bool(re.search(r'\$script:Version\s*=\s*"25\.(?:5[5-9]|[6-9]\d|\d{3,})"', main)))
    add("native_gui_visible", "AUTONOMOUS ROUTER DIGITAL TWIN v25.55" in main and "Show-HmsAutonomousRouterDigitalTwin" in main)
    add("gui_replay_visible", "MODEL CHECK" in main and "TWIN RUN" in main)
    add("target_cert_preserved", "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" in (root / "HMS_Codex_TargetMachineCertification.py").read_text("utf-8"))
    add("engine_cannot_issue_target_cert", "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" not in engine)

    with tempfile.TemporaryDirectory(prefix="hms-v2555-validator-") as td:
        p = Path(td) / "twin.json"
        mini = twin.run(root, [7, 19], 140, 12, 6, 8)
        p.write_text(json.dumps(mini, ensure_ascii=False, indent=2), encoding="utf-8")
        parsed = json.loads(p.read_text("utf-8"))
        add("artifact_roundtrip", parsed.get("version") == VERSION and str(parsed.get("verdict") or "").startswith("PASS"))

    failed = [x for x in tests if x["status"] == "FAIL"]
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION,
        "suite": "AUTONOMOUS_ROUTER_DIGITAL_TWIN_VALIDATOR",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests)-len(failed), "fail": len(failed), "total": len(tests)},
        "tests": tests,
        "production_certification": "NOT_CLAIMED_DIGITAL_TWIN_ONLY",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--output")
    a = ap.parse_args()
    out = run(Path(a.root).resolve())
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
