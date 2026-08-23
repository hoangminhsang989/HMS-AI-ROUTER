#!/usr/bin/env python3
from __future__ import annotations

import argparse,re
import json
import tempfile
from pathlib import Path
from typing import Any

import HMS_Codex_ProductionSimulationLab as lab

VERSION = "25.54"


def run(root: Path) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        tests.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail[:240]})

    report = lab.run(root, [11, 23, 37, 41, 59, 73], 220)
    s = report.get("summary") or {}
    add("lab_verdict_pass", str(report.get("verdict") or "").startswith("PASS"))
    add("six_seeds_exercised", int(s.get("seeds") or 0) == 6)
    add("at_least_1320_cycles", int(s.get("total_cycles") or 0) >= 1320)
    add("all_seeds_pass", int(s.get("seed_pass") or 0) == int(s.get("seeds") or 0))
    add("zero_invariant_failures", int(s.get("invariant_failures") or 0) == 0)
    add("all_fault_events_exercised", set(report.get("event_catalog") or []) <= set(report.get("events_exercised") or []))
    add("deterministic_replay_pass", int(s.get("replay_pass") or 0) == int(s.get("replay_total") or 0) and int(s.get("replay_total") or 0) >= 2)
    add("quota_state_space_zero_fail", int((report.get("quota_state_space") or {}).get("fail") or 0) == 0)
    add("quota_state_space_broad", int((report.get("quota_state_space") or {}).get("total") or 0) >= 100)
    add("mutation_detector_fires", bool((report.get("mutation_sensitivity") or {}).get("detector_fires")))
    add("rotation_runtime_faults_pass", bool(((report.get("focused_runtime_faults") or {}).get("rotation") or {}).get("pass")))
    add("lan_runtime_faults_pass", bool(((report.get("focused_runtime_faults") or {}).get("lan_failure_matrix") or {}).get("pass")))

    seed_rows = report.get("seeds") or []
    add("queue_ends_empty", all(int((x.get("queue") or {}).get("depth") or 0) == 0 for x in seed_rows))
    add("backpressure_rejections_exercised", sum(int((x.get("queue") or {}).get("rejected") or 0) for x in seed_rows) > 0)
    add("session_failover_exercised", sum(int(x.get("failed_over_sessions") or 0) for x in seed_rows) > 0)
    add("rotation_exercised", sum(int(x.get("rotations") or 0) for x in seed_rows) > 0)
    add("new_session_rejection_exercised", sum(int(x.get("rejected_sessions") or 0) for x in seed_rows) > 0)
    add("process_restart_generation_exercised", any(any(int(v) > 1 for v in (x.get("process_generations") or {}).values()) for x in seed_rows))

    safety = report.get("safety") or {}
    add("synthetic_only_true", safety.get("synthetic_only") is True)
    add("no_real_quota_consumed", safety.get("real_quota_consumed") is False)
    add("no_real_codex_request", safety.get("real_codex_request_sent") is False)
    add("oauth_tokens_not_mutated", safety.get("oauth_tokens_mutated") is False)
    add("real_account_files_not_mutated", safety.get("real_account_files_mutated") is False)
    add("real_smb_not_required", safety.get("real_smb_share_required") is False)
    add("raw_secret_evidence_false", safety.get("raw_secret_evidence") is False)
    add("production_cert_never_claimed", safety.get("production_certification") == "NOT_CLAIMED_SIMULATION_ONLY")
    add("claim_boundary_explicit", "never substitutes" in str(report.get("claim_boundary") or ""))
    add("report_has_no_secret_shape", not lab.secret_shape(report))

    # Replay contract: same seed/cycle count must be byte-stable after normalization.
    one = lab.run_seed(991, 140)
    two = lab.run_seed(991, 140)
    three = lab.run_seed(992, 140)
    add("same_seed_same_trace_hash", one.get("trace_hash") == two.get("trace_hash"))
    add("different_seed_different_trace_hash", one.get("trace_hash") != three.get("trace_hash"))
    add("same_seed_pass", bool(one.get("pass") and two.get("pass")))

    # Negative property: a deliberately stale high-quota account must remain ineligible.
    matrix = lab.quota_state_space()
    stale_bad = [x for x in matrix.get("failures") or [] if int(x.get("age_min") or 0) > 20]
    add("stale_matrix_has_no_escape", not stale_bad)

    # Static release contract.
    engine = (root / "HMS_Codex_ProductionSimulationLab.py").read_text("utf-8")
    regression = (root / "HMS_Codex_RegressionFreezeValidator.py").read_text("utf-8")
    main = (root / "HMS_AI_ROUTER_v25.23.1.ps1").read_text("utf-8-sig")
    add("engine_version_25_54", 'VERSION = "25.54"' in engine)
    add("simulation_suite_in_regression", "production_simulation_lab" in regression and "HMS_Codex_ProductionSimulationLabValidator.py" in regression)
    add("main_version_at_least_25_54", bool(re.search(r'\$script:Version\s*=\s*"25\.(?:5[4-9]|[6-9]\d|\d{3,})"', main)))
    add("simulation_gui_visible", "PRODUCTION SIMULATION LAB v25.54" in main and "Show-HmsProductionSimulationLab" in main)
    add("simulation_cli_visible", "SIM LAB" in main and "REPLAY" in main)
    add("target_production_gate_preserved", "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" in (root / "HMS_Codex_TargetMachineCertification.py").read_text("utf-8"))
    add("simulation_cannot_issue_target_verdict", "PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" not in engine)

    # Ensure output path behavior works and never needs a real machine.
    with tempfile.TemporaryDirectory(prefix="hms-v2554-validator-") as td:
        out = Path(td) / "sim.json"
        mini = lab.run(root, [7, 13], 120)
        out.write_text(json.dumps(mini, ensure_ascii=False, indent=2), encoding="utf-8")
        parsed = json.loads(out.read_text("utf-8"))
        add("standalone_artifact_roundtrip", parsed.get("version") == VERSION and str(parsed.get("verdict") or "").startswith("PASS"))

    failed = [x for x in tests if x["status"] == "FAIL"]
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION,
        "suite": "PRODUCTION_SIMULATION_FAULT_INJECTION_VALIDATOR",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests)-len(failed), "fail": len(failed), "total": len(tests)},
        "tests": tests,
        "production_certification": "NOT_CLAIMED_SIMULATION_ONLY",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--output")
    a = ap.parse_args()
    out = run(Path(a.root).resolve())
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
