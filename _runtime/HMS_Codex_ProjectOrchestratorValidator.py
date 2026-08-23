# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from copy import deepcopy
from HMS_Codex_ProjectOrchestrator import build_state, select_project


def base_project(**kw):
    x = {
        "name": "QR",
        "project_dir": r"F:\\PHAN-MEM-QUAN-LY-QR",
        "project_exists": True,
        "affinity_mapped": True,
        "affinity_state": "READY",
        "instance_id": "codex-0001",
        "instance_name": "QR",
        "account": "a@example.com",
        "fallback_account": "b@example.com",
        "client_running": False,
        "router_online": False,
        "router_endpoint": "http://127.0.0.1:8400/v1",
        "identity_ok": True,
        "identity_fingerprint": "a" * 64,
        "security_ok": True,
        "port_conflict_foreign": False,
        "binding_drift": False,
        "model_policy_drift": False,
        "model_configured": True,
        "model": "gpt-5-codex",
        "reasoning": "high",
        "profile": "BALANCED",
        "account_health": 96,
        "hourly_remaining": 72,
        "weekly_remaining": 51,
        "reason": "READY",
    }
    x.update(kw)
    return x


def check(name, fn):
    try:
        fn()
        return {"name": name, "pass": True}
    except Exception as exc:
        return {"name": name, "pass": False, "error": str(exc)}


def main():
    tests = []
    def t_ready():
        s = build_state({"projects": [base_project()]})
        p = s["projects"][0]
        assert p["one_click_ready"] and any(x["step"] == "START_MANAGED_CODEX" for x in p["plan"])
    tests.append(check("ready_project_one_click", t_ready))

    def t_running():
        s = build_state({"projects": [base_project(client_running=True, router_online=True, affinity_state="RUNNING")]})
        p = s["projects"][0]
        assert p["readiness"] == "RUNNING" and [x["step"] for x in p["plan"]] == ["FOCUS_INSTANCE"]
    tests.append(check("running_project_focus_only", t_running))

    def t_identity():
        p = build_state({"projects": [base_project(identity_ok=False)]})["projects"][0]
        assert not p["one_click_ready"] and "IDENTITY_ISOLATION_BLOCKED" in p["blockers"]
    tests.append(check("identity_is_hard_gate", t_identity))

    def t_security():
        p = build_state({"projects": [base_project(security_ok=False)]})["projects"][0]
        assert not p["one_click_ready"] and "SECURITY_HARD_GATE_BLOCKED" in p["blockers"]
    tests.append(check("security_is_hard_gate", t_security))

    def t_foreign_port():
        p = build_state({"projects": [base_project(port_conflict_foreign=True)]})["projects"][0]
        assert not p["one_click_ready"] and "FOREIGN_PORT_OWNER" in p["blockers"]
    tests.append(check("foreign_port_fail_closed", t_foreign_port))

    def t_missing():
        p = build_state({"projects": [base_project(project_exists=False, affinity_state="PROJECT_MISSING")]})["projects"][0]
        assert not p["one_click_ready"] and "PROJECT_MISSING" in p["blockers"]
    tests.append(check("missing_project_blocked", t_missing))

    def t_model_optional():
        p = build_state({"projects": [base_project(model_configured=False, model="", reasoning="")]})["projects"][0]
        assert p["one_click_ready"] and "MODEL_POLICY_NOT_CONFIGURED_USING_EXISTING_CONFIG" in p["warnings"]
    tests.append(check("model_policy_optional_not_fake", t_model_optional))

    def t_select():
        s = build_state({"projects": [base_project()]})
        assert select_project(s, r"F:\\PHAN-MEM-QUAN-LY-QR")["instance_id"] == "codex-0001"
    tests.append(check("project_selection_exact_path", t_select))

    def t_secret():
        bad = {"projects": [base_project()], "api_key": "should-not-be-here"}
        try:
            build_state(bad)
        except ValueError as e:
            assert "SECRET_FIELD_REJECTED" in str(e)
            return
        raise AssertionError("secret payload was accepted")
    tests.append(check("secret_field_rejected", t_secret))

    passed = sum(1 for x in tests if x["pass"])
    result = {"version": "25.47", "suite": "PROJECT_ORCHESTRATOR", "passed": passed, "total": len(tests), "tests": tests}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed == len(tests) else 2


if __name__ == "__main__":
    raise SystemExit(main())
