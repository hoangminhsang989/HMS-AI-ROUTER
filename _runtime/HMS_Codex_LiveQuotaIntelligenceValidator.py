#!/usr/bin/env python3
from __future__ import annotations

import json
import re as regex
from datetime import datetime, timedelta, timezone
from pathlib import Path

import HMS_Codex_LiveQuotaIntelligence as lq
import HMS_Codex_AdaptiveRouterPolicy as arp

VERSION = "25.50"


def run(root: Path) -> dict:
    checks: list[dict] = []
    def add(name: str, ok: bool, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})

    now = datetime(2026, 8, 22, 2, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(minutes=2)).isoformat()
    aging = (now - timedelta(minutes=15)).isoformat()
    stale = (now - timedelta(minutes=30)).isoformat()

    add("version_25_50", lq.VERSION == VERSION, lq.VERSION)
    add("schema_v1", lq.SCHEMA_VERSION == 1)
    add("default_fail_closed", lq.DEFAULT_POLICY["fail_closed"] is True)
    add("free_reserve_25", lq.reserve_for("Free", lq.DEFAULT_POLICY) == 25)
    add("plus_reserve_15", lq.reserve_for("Plus", lq.DEFAULT_POLICY) == 15)
    add("pro_reserve_10", lq.reserve_for("Pro", lq.DEFAULT_POLICY) == 10)
    add("business_reserve_10", lq.reserve_for("Business", lq.DEFAULT_POLICY) == 10)
    add("unknown_default_15", lq.reserve_for("mystery", lq.DEFAULT_POLICY) == 15)

    def acct(email, plan, ref, h=80, w=70, status="READY", source_state="FRESH", hp=True, wp=True):
        return {"email": email, "plan": plan, "status": status, "quota": {
            "five_hour_remaining": h, "weekly_remaining": w,
            "five_hour_window_present": hp, "weekly_window_present": wp,
            "last_success_utc": ref, "last_attempt_utc": ref,
            "source_state": source_state,
        }}

    r = lq.evaluate({"accounts": [acct("p@example", "Plus", fresh)]}, now=now)
    row = r["accounts"][0]
    add("fresh_state", row["freshness_state"] == "FRESH", row)
    add("fresh_route_ok", row["routing_eligible"] is True, row)
    add("plus_usable_55", row["usable_remaining_pct"] == 55, row)
    add("session_affinity_kept", row["session_affinity_action"] == "KEEP_EXISTING_SESSION")
    add("no_secret_output", not lq.contains_secret_like(r))

    ra = lq.evaluate({"accounts": [acct("a@example", "Plus", aging)]}, now=now)["accounts"][0]
    add("aging_state", ra["freshness_state"] == "AGING", ra)
    add("aging_can_route_when_above_reserve", ra["routing_eligible"] is True, ra)
    add("aging_reason", "QUOTA_AGING" in ra["reason_codes"], ra)

    rs = lq.evaluate({"accounts": [acct("s@example", "Plus", stale)]}, now=now)["accounts"][0]
    add("stale_state", rs["freshness_state"] == "STALE", rs)
    add("stale_fail_closed", rs["routing_eligible"] is False, rs)
    add("stale_reason", "QUOTA_STALE" in rs["reason_codes"], rs)

    ru = lq.evaluate({"accounts": [acct("u@example", "Plus", None)]}, now=now)["accounts"][0]
    add("unknown_state", ru["freshness_state"] == "UNKNOWN", ru)
    add("unknown_fail_closed", ru["routing_eligible"] is False, ru)

    rr = lq.evaluate({"accounts": [acct("r@example", "Plus", fresh, h=14, w=40)]}, now=now)["accounts"][0]
    add("reserve_blocks_new_session", rr["routing_eligible"] is False, rr)
    add("reserve_reason", "PLAN_RESERVE_HELD" in rr["reason_codes"], rr)
    add("reserve_usable_zero", rr["usable_remaining_pct"] == 0, rr)

    rn = lq.evaluate({"accounts": [acct("n@example", "Plus", fresh, h=18, w=40)]}, now=now)["accounts"][0]
    add("near_reserve_allows_but_warns", rn["routing_eligible"] is True and "NEAR_PLAN_RESERVE" in rn["reason_codes"], rn)

    rm = lq.evaluate({"accounts": [acct("m@example", "Pro", fresh, hp=False)]}, now=now)["accounts"][0]
    add("missing_window_fail_closed", rm["routing_eligible"] is False, rm)
    add("missing_window_reason", any(x.startswith("QUOTA_WINDOW_MISSING") for x in rm["reason_codes"]), rm)

    re = lq.evaluate({"accounts": [acct("e@example", "Pro", fresh, source_state="ERROR")]}, now=now)["accounts"][0]
    add("last_refresh_failure_not_auto_block_if_last_good_fresh", re["routing_eligible"] is True, re)
    add("last_refresh_failure_visible", "LAST_REFRESH_FAILED" in re["reason_codes"], re)

    rd = lq.evaluate({"accounts": [acct("d@example", "Pro", fresh, status="DISABLED")]}, now=now)["accounts"][0]
    add("disabled_blocked", rd["routing_eligible"] is False, rd)

    multi = lq.evaluate({"accounts": [
        acct("stale@example", "Pro", stale, h=99, w=99),
        acct("fresh@example", "Plus", fresh, h=50, w=50),
    ]}, now=now)
    add("fresh_ranked_before_stale", multi["accounts"][0]["account"] == "fresh@example", multi["accounts"])
    add("summary_eligible_one", multi["summary"]["routing_eligible"] == 1, multi["summary"])
    add("summary_stale_one", multi["summary"]["stale"] == 1, multi["summary"])

    # Adaptive Router integration: explicit v25.50 live quota gate must be authoritative for NEW sessions.
    accounts_obj = {"accounts": [{
        "email": "stale@example", "status": "READY", "plan": "Pro", "pool_score": 99,
        "quota": {"five_hour_remaining": 99, "weekly_remaining": 99, "freshness_state": "STALE",
                  "routing_eligible": False, "reserve_pct": 10, "reason_codes": ["QUOTA_STALE"]},
    }, {
        "email": "fresh@example", "status": "READY", "plan": "Plus", "pool_score": 70,
        "quota": {"five_hour_remaining": 60, "weekly_remaining": 60, "freshness_state": "FRESH",
                  "routing_eligible": True, "reserve_pct": 15, "reason_codes": []},
    }]}
    plan = arp.evaluate(accounts_obj, {"by_account_week": []}, {}, {"enabled": True, "mode": "OBSERVE", "min_samples": 0})
    ranking = {x["account"]: x for x in plan["ranking"]}
    add("adaptive_stale_ineligible", ranking["stale@example"]["eligible"] is False, ranking)
    add("adaptive_stale_reason", "QUOTA_STALE" in ranking["stale@example"]["blocks"], ranking)
    add("adaptive_fresh_eligible", ranking["fresh@example"]["eligible"] is True, ranking)
    add("adaptive_recommends_fresh", plan["recommended_account"] == "fresh@example", plan)
    add("adaptive_safety_fail_closed", plan["safety"]["live_quota_fail_closed"] is True, plan["safety"])
    add("adaptive_session_affinity_untouched", plan["safety"]["session_affinity_untouched"] is True, plan["safety"])

    ps = (root / "HMS_AI_ROUTER_v25.23.1.ps1").read_text(encoding="utf-8-sig", errors="replace")
    gui = (root / "HMS_GUI.pyw").read_text(encoding="utf-8-sig", errors="replace")
    pm = regex.search(r'\$script:Version\s*=\s*"(\d+)\.(\d+)"', ps)
    pver = (int(pm.group(1)), int(pm.group(2))) if pm else (0, 0)
    add("ps_main_version_at_least_25_50", pver >= (25, 50), pver)
    add("ps_last_good_comment", "preserve the last known-good quota" in ps)
    add("ps_failure_does_not_advance_refreshed", 'refreshedUtc=$null;lastSuccessUtc=$null;lastAttemptUtc=$attemptUtc' in ps)
    add("ps_success_has_last_success", 'lastSuccessUtc=$nowUtc' in ps)
    add("ps_window_presence", 'hourlyWindowPresent=' in ps and 'weeklyWindowPresent=' in ps)
    add("ps_freshness_helper", 'function Get-CodexQuotaFreshness' in ps)
    add("ps_reserve_helper", 'function Get-CodexQuotaReservePct' in ps)
    add("ps_routing_eligible_exposed", 'routing_eligible=[bool]$liveQuota.routingEligible' in ps)
    add("ps_error_is_generic", 'error="QUOTA_REFRESH_FAILED"' in ps)
    gm = regex.search(r'APP_VERSION\s*=\s*"(\d+)\.(\d+)"', gui)
    gver = (int(gm.group(1)), int(gm.group(2))) if gm else (0, 0)
    add("gui_main_version_at_least_25_50", gver >= (25, 50), gver)
    add("gui_live_quota_surface_preserved", ('Live Quota v25.50' in gui) or ('Usage & Token Center v25.61' in gui and 'LIVE {fresh} · RESERVE' in gui))
    add("gui_freshness_reserve", 'LIVE {fresh} · RESERVE' in gui)
    add("gui_explains_fail_closed", ('STALE/UNKNOWN fail-closed' in gui) or ('HOLD NEW SESSION' in gui and 'routing_eligible' in gui))

    failed = [c for c in checks if not c["ok"]]
    return {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "verdict": "PASS_LIVE_QUOTA_INTELLIGENCE_V25_50" if not failed else "FAIL_LIVE_QUOTA_INTELLIGENCE_V25_50",
        "summary": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks)},
        "checks": checks,
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    report = run(root)
    out = root / "LIVE_QUOTA_INTELLIGENCE_VALIDATION_V25.50.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"version": report["version"], "verdict": report["verdict"], "summary": report["summary"]}, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
