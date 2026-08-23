#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import HMS_Codex_SeamlessRotationTorture as torture

VERSION = "25.51"


def run(root: Path) -> dict:
    checks: list[dict] = []
    def add(name: str, ok: bool, detail: object = ""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})

    report = torture.run(root, cycles=1000)
    add("engine_version_25_51", torture.VERSION == VERSION, torture.VERSION)
    add("engine_schema_v1", torture.SCHEMA_VERSION == 1)
    add("core_torture_verdict", report.get("verdict") == "PASS_SEAMLESS_ROTATION_TORTURE_V25_51", report.get("verdict"))
    add("core_torture_1000_cycles", (report.get("summary") or {}).get("cycles") == 1000, report.get("summary"))
    add("core_torture_all_pass", (report.get("summary") or {}).get("fail") == 0, report.get("summary"))
    for c in report.get("checks") or []:
        add("core." + str(c.get("name")), bool(c.get("ok")))

    sc = report.get("scenarios") or {}
    active = sc.get("active_ineligible") or {}
    hyst = sc.get("hysteresis") or {}
    stale = sc.get("stale_recovery") or {}
    gw = sc.get("gateway_429") or {}
    auth = sc.get("auth_isolation") or {}
    multi = sc.get("multi_instance") or {}
    lan = sc.get("lan_rejoin") or {}

    add("active_reason_critical_override", "CURRENT_CRITICAL_OVERRIDE" in (active.get("reasons") or []), active)
    add("active_current_not_rewritten_to_candidate", active.get("current") != active.get("recommended"), active)
    add("hysteresis_exercised_all_cycles", hyst.get("held") == hyst.get("cycles"), hyst)
    add("hysteresis_candidate_can_differ_without_apply", int(hyst.get("recommended_alpha") or 0) > 0 and int(hyst.get("switchable") or 0) == 0, hyst)
    add("stale_recovery_has_hold_reason", any(x in ("MIN_HOLD", "SWITCH_COOLDOWN") for x in stale.get("recovery_reasons") or []), stale)
    add("gateway_failover_not_affinity_reason_when_target_cooled", gw.get("after_429_reason") != "AFFINITY", gw)
    add("gateway_recovered_existing_is_affinity", gw.get("existing_after_recovery_reason") == "AFFINITY", gw)
    add("gateway_new_session_uses_ranking", gw.get("new_after_recovery_reason") != "AFFINITY", gw)
    add("auth_fixture_two_files", auth.get("auth_file_count") == 2, auth)
    add("auth_fixture_nonempty", int(auth.get("raw_fixture_bytes") or 0) > 100, auth)
    add("multi_instances_have_distinct_endpoints", len({x.get("stable_endpoint") for x in multi.get("rows") or []}) == 2, multi)
    add("multi_instances_all_real_current_alpha", all(x.get("current") == "alpha@example.test" for x in multi.get("rows") or []), multi)
    add("multi_instances_all_recommend_beta", all(x.get("recommended") == "beta@example.test" for x in multi.get("rows") or []), multi)
    add("lan_takeover_epoch_exact_2", lan.get("takeover_epoch") == 2, lan)

    adaptive_src = (root / "HMS_Codex_AdaptiveRouterPolicy.py").read_text(encoding="utf-8-sig", errors="replace")
    closed_src = (root / "HMS_Codex_ClosedLoopRouter.py").read_text(encoding="utf-8-sig", errors="replace")
    gateway_src = (root / "HMS_Codex_SmartGateway.py").read_text(encoding="utf-8-sig", errors="replace")
    ps = (root / "HMS_AI_ROUTER_v25.23.1.ps1").read_text(encoding="utf-8-sig", errors="replace")
    gui = (root / "HMS_GUI.pyw").read_text(encoding="utf-8-sig", errors="replace")

    add("adaptive_real_active_comment", "REAL active account" in adaptive_src)
    add("adaptive_ineligible_active_guard", '"ineligible_active_account_rotates_new_sessions": True' in adaptive_src)
    add("closed_loop_policy_25_51", 'POLICY_VERSION = "25.51"' in closed_src)
    add("closed_loop_ineligible_current_guard", '"ineligible_current_rotates_new_sessions": True' in closed_src)
    add("gateway_affinity_before_priority_comment", "affinity is authoritative across ALL currently eligible targets" in gateway_src)
    add("gateway_uses_all_eligible_before_available", "all_rows=self.all_eligible(model,exclude,client)" in gateway_src and "rows=self.available(model,exclude,client)" in gateway_src)
    import re
    pm = re.search(r'\$script:Version\s*=\s*"(\d+)\.(\d+)"', ps)
    gm = re.search(r'APP_VERSION\s*=\s*"(\d+)\.(\d+)"', gui)
    pver = tuple(map(int, pm.groups())) if pm else (0, 0)
    gver = tuple(map(int, gm.groups())) if gm else (0, 0)
    add("ps_main_version_at_least_25_51", pver >= (25, 51), pver)
    add("gui_main_version_at_least_25_51", gver >= (25, 51), gver)
    add("gui_rotation_torture_visible", "ROTATION TORTURE v25.51" in gui)
    add("gui_rotation_torture_button", "ROTATION TEST" in gui)

    failed = [c for c in checks if not c["ok"]]
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "SEAMLESS_ROTATION_TORTURE_VALIDATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS_SEAMLESS_ROTATION_TORTURE_VALIDATION_V25_51" if not failed else "FAIL_SEAMLESS_ROTATION_TORTURE_VALIDATION_V25_51",
        "summary": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks)},
        "checks": checks,
        "claim_boundary": "Synthetic torture only; real Codex/quota/LAN target-machine certification remains required.",
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    out = run(root)
    path = root / "SEAMLESS_ROTATION_TORTURE_VALIDATION_V25.51.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"version": out["version"], "verdict": out["verdict"], "summary": out["summary"]}, ensure_ascii=False))
    return 0 if out["summary"]["fail"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
