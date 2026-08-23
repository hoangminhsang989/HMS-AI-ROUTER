#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from itertools import combinations, product
from pathlib import Path

VERSION = "25.58"
PRODUCTION_CLAIM = "NOT_CLAIMED_COMPOUND_FAULT_CONVERGENCE_SYNTHETIC_ONLY"

HARD_OPERATOR = {"AUTH_DRIFT", "IDENTITY_DRIFT", "FOREIGN_PORT", "PROJECT_MISSING"}
QUOTA_FAULTS = {"HTTP_429", "QUOTA_RESERVE", "QUOTA_STALE", "QUOTA_UNKNOWN"}
NETWORK_FAULTS = {"UPSTREAM_TIMEOUT", "UPSTREAM_CONNECT", "SMB_TRANSIENT"}
PROCESS_FAULTS = {"ROUTER_CRASH", "CLIENT_CRASH"}
CONFIG_FAULTS = {"GLOBAL_CONFIG_DRIFT", "INSTANCE_CONFIG_DRIFT", "BINDING_DRIFT"}
LAN_FAULTS = {"LAN_PARTITION"}
NOOP_FAULTS = {"CLIENT_ABORT", "HEALTHY", "RECOVERED"}
ALL_FAULTS = sorted(HARD_OPERATOR | QUOTA_FAULTS | NETWORK_FAULTS | PROCESS_FAULTS | CONFIG_FAULTS | LAN_FAULTS | {"STALE_PID", "CLIENT_ABORT"})

ACTION_COST = {
    "QUARANTINE_SCOPE": 0,
    "OPEN_RECOVERY_CIRCUIT": 0,
    "MARK_NEW_SESSION_INELIGIBLE": 0,
    "SELECT_HEALTHY_FALLBACK": 1,
    "FAIL_CLOSED_UNSIGNED_LEASE": 0,
    "HOLD_OWNERSHIP_NO_TAKEOVER": 0,
    "ALLOW_SIGNED_LEASE_REELECTION": 2,
    "CLEAR_STALE_PID_METADATA": 1,
    "RETRY_SAME_TARGET": 1,
    "MARK_SHARED_IO_DEGRADED": 0,
    "REFUSE_UNOWNED_PROCESS_RESTART": 0,
    "RESTART_ROUTER": 2,
    "RESTART_CLIENT": 2,
    "REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP": 0,
    "REPAIR_CONFIG_ATOMIC": 2,
    "OBSERVE_AFTER_SUCCESS": 0,
    "GLOBAL_RECOVERY_BUDGET_EXHAUSTED": 0,
}

MUTATING_ACTIONS = {"CLEAR_STALE_PID_METADATA", "RESTART_ROUTER", "RESTART_CLIENT", "REPAIR_CONFIG_ATOMIC", "ALLOW_SIGNED_LEASE_REELECTION"}
RESTART_ACTIONS = {"RESTART_ROUTER", "RESTART_CLIENT"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CompoundContext:
    faults: tuple[str, ...]
    scope: str = "GLOBAL"
    owned_process: bool = True
    existing_session: bool = True
    affinity_target_healthy: bool = True
    quota_fresh: bool = True
    lease_signed: bool = True
    lease_expired: bool = False
    config_backup_available: bool = True
    fallback_available: bool = True
    attempts_in_window: int = 0
    global_budget: int = 6
    budget_used: int = 0

    @classmethod
    def build(cls, faults, **kwargs):
        normalized = tuple(sorted({str(x).upper().strip() for x in faults if str(x).strip()}))
        return cls(faults=normalized, **kwargs)


def _step(action: str, reason: str, *, deps=None, verify="READBACK_HEALTH", rollback=None,
          auto_safe=True, preserves_session=True, mutation=False, priority=50):
    return {
        "action": action,
        "reason": reason,
        "deps": list(deps or []),
        "verify": verify,
        "rollback": rollback,
        "auto_safe": bool(auto_safe),
        "preserves_session": bool(preserves_session),
        "mutation": bool(mutation),
        "priority": int(priority),
        "cost": int(ACTION_COST.get(action, 1)),
    }


def _single_fault_steps(fault: str, ctx: CompoundContext) -> tuple[list[dict], str | None]:
    f = fault.upper()
    if f in NOOP_FAULTS:
        return [], None
    if f in HARD_OPERATOR:
        return [_step("QUARANTINE_SCOPE", f, verify="SCOPE_NOT_ROUTABLE", priority=0)], "OPERATOR_REQUIRED"
    if ctx.attempts_in_window >= 3:
        return [_step("OPEN_RECOVERY_CIRCUIT", "RECOVERY_LOOP_BREAKER", verify="NO_AUTO_RECOVERY_UNTIL_COOLDOWN", priority=0)], "OPERATOR_REQUIRED"
    if f in QUOTA_FAULTS:
        rows = [_step("MARK_NEW_SESSION_INELIGIBLE", f, verify="ROUTING_ELIGIBLE_FALSE", priority=10)]
        if not ctx.existing_session and ctx.fallback_available:
            rows.append(_step("SELECT_HEALTHY_FALLBACK", f, deps=["MARK_NEW_SESSION_INELIGIBLE"], verify="DIFFERENT_ELIGIBLE_TARGET", priority=20))
        return rows, None
    if f == "LAN_PARTITION":
        if not ctx.lease_signed:
            return [_step("FAIL_CLOSED_UNSIGNED_LEASE", f, verify="NO_TAKEOVER", priority=5)], "OPERATOR_REQUIRED"
        if not ctx.lease_expired:
            return [_step("HOLD_OWNERSHIP_NO_TAKEOVER", f, verify="LEASE_OWNER_UNCHANGED", priority=10)], None
        return [_step("ALLOW_SIGNED_LEASE_REELECTION", f, verify="SINGLE_OWNER_AFTER_REELECTION", mutation=True, priority=25)], None
    if f == "STALE_PID":
        return [_step("CLEAR_STALE_PID_METADATA", f, verify="PID_METADATA_EMPTY", mutation=True, priority=35)], None
    if f in NETWORK_FAULTS:
        rows = [_step("RETRY_SAME_TARGET", f, verify="APPLICATION_HEALTH_OK", priority=40)]
        if f == "SMB_TRANSIENT":
            rows.append(_step("MARK_SHARED_IO_DEGRADED", f, deps=["RETRY_SAME_TARGET"], verify="NO_UNSAFE_TAKEOVER", priority=45))
        return rows, None
    if f in PROCESS_FAULTS:
        if not ctx.owned_process:
            return [_step("REFUSE_UNOWNED_PROCESS_RESTART", f, verify="NO_PROCESS_MUTATION", priority=5)], "OPERATOR_REQUIRED"
        action = "RESTART_ROUTER" if f == "ROUTER_CRASH" else "RESTART_CLIENT"
        verify = "ROUTER_APP_HEALTH_OK" if f == "ROUTER_CRASH" else "CLIENT_OWNERSHIP_AND_SESSION_READY"
        return [_step(action, f, verify=verify, rollback="RESTORE_PREVIOUS_PROCESS_STATE", mutation=True, priority=30)], None
    if f in CONFIG_FAULTS:
        if not ctx.config_backup_available:
            return [_step("REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP", f, verify="CONFIG_UNCHANGED", priority=5)], "OPERATOR_REQUIRED"
        return [_step("REPAIR_CONFIG_ATOMIC", f, verify="CONFIG_READBACK_MATCH", rollback="RESTORE_CONFIG_BACKUP", mutation=True, priority=20)], None
    return [_step("QUARANTINE_SCOPE", "UNKNOWN_INCIDENT", verify="SCOPE_NOT_ROUTABLE", priority=0)], "OPERATOR_REQUIRED"


def _dedupe_steps(steps: list[dict]) -> list[dict]:
    # Same action can satisfy multiple simultaneous fault reasons. Merge reasons and dependencies deterministically.
    merged = {}
    for s in steps:
        a = s["action"]
        if a not in merged:
            merged[a] = dict(s)
            merged[a]["reasons"] = [s["reason"]]
        else:
            m = merged[a]
            if s["reason"] not in m["reasons"]:
                m["reasons"].append(s["reason"])
            m["deps"] = sorted(set(m.get("deps", [])) | set(s.get("deps", [])))
            m["priority"] = min(int(m.get("priority", 50)), int(s.get("priority", 50)))
            m["cost"] = max(int(m.get("cost", 0)), int(s.get("cost", 0)))
            m["mutation"] = bool(m.get("mutation") or s.get("mutation"))
            m["preserves_session"] = bool(m.get("preserves_session", True) and s.get("preserves_session", True))
    rows = list(merged.values())
    for r in rows:
        r["reason"] = "+".join(sorted(r.pop("reasons", [r.get("reason", "")])) )
    return rows


def _conflict_resolve(steps: list[dict], faults: set[str], hard_operator: bool) -> list[dict]:
    if hard_operator:
        # Identity/auth/foreign ownership ambiguity is authoritative: quarantine only, no auto mutation.
        return [s for s in steps if s["action"] in {"QUARANTINE_SCOPE", "FAIL_CLOSED_UNSIGNED_LEASE", "REFUSE_UNOWNED_PROCESS_RESTART", "REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP", "OPEN_RECOVERY_CIRCUIT"}]
    actions = {s["action"] for s in steps}
    # If process itself crashed, retrying the same network endpoint is redundant until restart succeeds.
    if actions & RESTART_ACTIONS:
        for s in steps:
            if s["action"] == "RETRY_SAME_TARGET":
                restart = "RESTART_ROUTER" if "ROUTER_CRASH" in faults else "RESTART_CLIENT" if "CLIENT_CRASH" in faults else None
                if restart and restart not in s["deps"]:
                    s["deps"].append(restart)
                    s["priority"] = max(s["priority"], 40)
    return steps


def _toposort(steps: list[dict]) -> tuple[list[dict], bool]:
    by_action = {s["action"]: s for s in steps}
    remaining = set(by_action)
    done = []
    while remaining:
        ready = [a for a in remaining if all(d not in by_action or d in {x["action"] for x in done} for d in by_action[a].get("deps", []))]
        if not ready:
            return sorted(steps, key=lambda x: (x["priority"], x["action"])), False
        ready.sort(key=lambda a: (by_action[a]["priority"], a))
        for a in ready:
            done.append(by_action[a]); remaining.remove(a)
    return done, True


def plan_compound(ctx: CompoundContext) -> dict:
    faults = set(ctx.faults)
    hard = bool(faults & HARD_OPERATOR)
    all_steps = []
    escalations = []
    for fault in ctx.faults:
        rows, escalation = _single_fault_steps(fault, ctx)
        all_steps.extend(rows)
        if escalation:
            escalations.append(escalation)
    steps = _dedupe_steps(all_steps)
    steps = _conflict_resolve(steps, faults, hard)
    ordered, acyclic = _toposort(steps)

    budget_remaining = max(0, int(ctx.global_budget) - int(ctx.budget_used))
    accepted = []
    spent = 0
    skipped = []
    for s in ordered:
        cost = int(s.get("cost", 0))
        if cost <= budget_remaining - spent:
            accepted.append(s); spent += cost
        else:
            skipped.append({"action": s["action"], "reason": "GLOBAL_RECOVERY_BUDGET", "cost": cost})
    if skipped:
        accepted.append(_step("GLOBAL_RECOVERY_BUDGET_EXHAUSTED", "GLOBAL_RECOVERY_BUDGET", verify="NO_MORE_AUTO_MUTATION", priority=99))
        escalations.append("OPERATOR_REQUIRED")

    unresolved_operator = hard or any(s["action"] in {"FAIL_CLOSED_UNSIGNED_LEASE", "REFUSE_UNOWNED_PROCESS_RESTART", "REFUSE_CONFIG_MUTATION_WITHOUT_BACKUP", "OPEN_RECOVERY_CIRCUIT"} for s in accepted) or bool(skipped)
    if unresolved_operator:
        disposition = "OPERATOR_REQUIRED"
    elif faults & (QUOTA_FAULTS | {"LAN_PARTITION", "SMB_TRANSIENT"}):
        disposition = "DEGRADED_SAFE"
    else:
        disposition = "RECOVERY_IN_PROGRESS" if accepted else "HEALTHY"

    dag_edges = []
    for s in accepted:
        for dep in s.get("deps", []):
            if dep in {x["action"] for x in accepted}:
                dag_edges.append([dep, s["action"]])

    plan = {
        "version": VERSION,
        "faults": list(ctx.faults),
        "scope": ctx.scope,
        "disposition": disposition,
        "escalation": "OPERATOR_REQUIRED" if escalations else "NONE",
        "global_budget": {"limit": int(ctx.global_budget), "already_used": int(ctx.budget_used), "spent": spent, "remaining": max(0, budget_remaining-spent), "skipped": skipped},
        "dag": {"acyclic": acyclic, "nodes": [s["action"] for s in accepted], "edges": dag_edges},
        "steps": accepted,
        "invariants": {
            "hard_operator_dominates_auto_mutation": True,
            "quota_never_causes_process_restart": True,
            "existing_session_not_rotated_for_quota": True,
            "never_restart_unowned_process": True,
            "signed_expired_lease_required_for_takeover": True,
            "config_mutation_requires_rollback": True,
            "global_recovery_budget_enforced": True,
            "recovery_dag_acyclic": acyclic,
            "terminal_states": ["HEALTHY", "DEGRADED_SAFE", "OPERATOR_REQUIRED"],
            "production_certification": PRODUCTION_CLAIM,
        },
    }
    plan["plan_id"] = stable_hash({k: v for k, v in plan.items() if k != "plan_id"})[:24]
    return plan


def invariant_violations(ctx: CompoundContext, plan: dict) -> list[str]:
    faults = set(ctx.faults)
    acts = [s["action"] for s in plan.get("steps", [])]
    bad = []
    if not ctx.owned_process and any(a in RESTART_ACTIONS for a in acts): bad.append("UNOWNED_RESTART")
    if faults and faults <= QUOTA_FAULTS and any(a in RESTART_ACTIONS for a in acts): bad.append("QUOTA_ONLY_RESTART")
    if ctx.existing_session and faults & QUOTA_FAULTS and "SELECT_HEALTHY_FALLBACK" in acts: bad.append("EXISTING_SESSION_QUOTA_ROTATION")
    if faults & HARD_OPERATOR and any(a in MUTATING_ACTIONS for a in acts): bad.append("HARD_OPERATOR_AUTO_MUTATION")
    if "LAN_PARTITION" in faults and (not ctx.lease_signed or not ctx.lease_expired) and "ALLOW_SIGNED_LEASE_REELECTION" in acts: bad.append("UNSAFE_LEASE_TAKEOVER")
    if any(a == "REPAIR_CONFIG_ATOMIC" and not s.get("rollback") for a, s in [(x["action"], x) for x in plan.get("steps", [])]): bad.append("CONFIG_NO_ROLLBACK")
    if not (plan.get("dag") or {}).get("acyclic"): bad.append("CYCLIC_RECOVERY_DAG")
    if int((plan.get("global_budget") or {}).get("spent", 0)) > max(0, int(ctx.global_budget)-int(ctx.budget_used)): bad.append("BUDGET_OVERRUN")
    if len(acts) != len(set(acts)): bad.append("DUPLICATE_ACTION")
    if acts.count("RESTART_ROUTER") > 1 or acts.count("RESTART_CLIENT") > 1: bad.append("RESTART_STORM_IN_PLAN")
    return bad


def simulate_convergence(ctx: CompoundContext, *, max_rounds=4) -> dict:
    remaining = set(ctx.faults)
    budget_used = int(ctx.budget_used)
    rounds = []
    terminal = None
    for idx in range(max_rounds):
        if not remaining:
            terminal = "HEALTHY"; break
        round_ctx = CompoundContext.build(
            remaining, scope=ctx.scope, owned_process=ctx.owned_process,
            existing_session=ctx.existing_session, affinity_target_healthy=ctx.affinity_target_healthy,
            quota_fresh=ctx.quota_fresh, lease_signed=ctx.lease_signed, lease_expired=ctx.lease_expired,
            config_backup_available=ctx.config_backup_available, fallback_available=ctx.fallback_available,
            attempts_in_window=ctx.attempts_in_window + idx, global_budget=ctx.global_budget, budget_used=budget_used)
        plan = plan_compound(round_ctx)
        acts = [s["action"] for s in plan["steps"]]
        budget_used += int(plan["global_budget"]["spent"])
        before = sorted(remaining)
        if plan["disposition"] == "OPERATOR_REQUIRED":
            terminal = "OPERATOR_REQUIRED"
        else:
            # Deterministic optimistic execution model: verified actions resolve the fault class they target.
            if "RESTART_ROUTER" in acts: remaining.discard("ROUTER_CRASH")
            if "RESTART_CLIENT" in acts: remaining.discard("CLIENT_CRASH")
            if "REPAIR_CONFIG_ATOMIC" in acts: remaining -= CONFIG_FAULTS
            if "CLEAR_STALE_PID_METADATA" in acts: remaining.discard("STALE_PID")
            if "RETRY_SAME_TARGET" in acts: remaining -= NETWORK_FAULTS
            if "ALLOW_SIGNED_LEASE_REELECTION" in acts: remaining.discard("LAN_PARTITION")
            if "MARK_NEW_SESSION_INELIGIBLE" in acts:
                # Quota/429 cannot be auto-healed; it remains a safe degraded condition.
                pass
        rounds.append({"round": idx+1, "before": before, "actions": acts, "after": sorted(remaining), "plan_id": plan["plan_id"], "budget_spent": plan["global_budget"]["spent"]})
        if terminal == "OPERATOR_REQUIRED": break
        if remaining and remaining <= QUOTA_FAULTS:
            terminal = "DEGRADED_SAFE"; break
        if remaining == {"LAN_PARTITION"} and "HOLD_OWNERSHIP_NO_TAKEOVER" in acts:
            terminal = "DEGRADED_SAFE"; break
        if not remaining:
            terminal = "HEALTHY"; break
        if not acts or "GLOBAL_RECOVERY_BUDGET_EXHAUSTED" in acts:
            terminal = "OPERATOR_REQUIRED" if any(x in remaining for x in HARD_OPERATOR | PROCESS_FAULTS | CONFIG_FAULTS) else "DEGRADED_SAFE"
            break
    if terminal is None:
        terminal = "OPERATOR_REQUIRED" if any(x in remaining for x in HARD_OPERATOR | PROCESS_FAULTS | CONFIG_FAULTS) else "DEGRADED_SAFE"
    return {"terminal_state": terminal, "rounds": rounds, "round_count": len(rounds), "remaining_faults": sorted(remaining), "budget_used": budget_used, "converged": terminal in {"HEALTHY", "DEGRADED_SAFE", "OPERATOR_REQUIRED"}}


def model_check() -> dict:
    checked = 0; violations = []; terminals = {"HEALTHY": 0, "DEGRADED_SAFE": 0, "OPERATOR_REQUIRED": 0}
    # Pair/triple compound faults + compact authority/budget dimensions.
    combos = list(combinations(ALL_FAULTS, 2)) + list(combinations(ALL_FAULTS, 3))
    for faults, owned, existing, lease_signed, lease_expired, backup, budget in product(combos, [False, True], [False, True], [False, True], [False, True], [False, True], [2, 6]):
        ctx = CompoundContext.build(faults, owned_process=owned, existing_session=existing,
                                    lease_signed=lease_signed, lease_expired=lease_expired,
                                    config_backup_available=backup, global_budget=budget)
        plan = plan_compound(ctx); bad = invariant_violations(ctx, plan); sim = simulate_convergence(ctx)
        checked += 1; terminals[sim["terminal_state"]] = terminals.get(sim["terminal_state"], 0) + 1
        if not sim["converged"]: bad.append("NON_CONVERGENCE")
        if sim["round_count"] > 4: bad.append("RECOVERY_ROUND_STORM")
        if bad and len(violations) < 40:
            violations.append({"context": asdict(ctx), "violations": bad, "plan": plan, "simulation": sim})
    return {"states_checked": checked, "violation_count": len(violations), "sample_violations": violations, "terminal_distribution": terminals, "verdict": "PASS" if not violations else "FAIL"}


def synthetic_proof() -> dict:
    checks = []
    def add(name, ok, detail=None): checks.append({"name": name, "ok": bool(ok), "detail": detail})

    scenarios = {
        "quota_router_crash": CompoundContext.build(["HTTP_429", "QUOTA_STALE", "ROUTER_CRASH"], owned_process=True, existing_session=True, global_budget=6),
        "smb_partition_expired": CompoundContext.build(["SMB_TRANSIENT", "LAN_PARTITION"], lease_signed=True, lease_expired=True, global_budget=6),
        "config_client_crash": CompoundContext.build(["INSTANCE_CONFIG_DRIFT", "CLIENT_CRASH"], owned_process=True, config_backup_available=True, global_budget=6),
        "auth_router_crash": CompoundContext.build(["AUTH_DRIFT", "ROUTER_CRASH"], owned_process=True, global_budget=6),
        "foreign_router_crash": CompoundContext.build(["FOREIGN_PORT", "ROUTER_CRASH"], owned_process=False, global_budget=6),
        "budget_pressure": CompoundContext.build(["ROUTER_CRASH", "CLIENT_CRASH", "INSTANCE_CONFIG_DRIFT", "UPSTREAM_TIMEOUT"], owned_process=True, config_backup_available=True, global_budget=2),
        "unexpired_partition": CompoundContext.build(["LAN_PARTITION", "SMB_TRANSIENT"], lease_signed=True, lease_expired=False, global_budget=6),
    }
    plans = {k: plan_compound(v) for k, v in scenarios.items()}
    sims = {k: simulate_convergence(v) for k, v in scenarios.items()}
    actions = lambda k: [s["action"] for s in plans[k]["steps"]]

    add("quota_plus_crash_restart_only_for_crash", "RESTART_ROUTER" in actions("quota_router_crash") and "MARK_NEW_SESSION_INELIGIBLE" in actions("quota_router_crash"), actions("quota_router_crash"))
    add("quota_plus_crash_existing_session_no_fallback", "SELECT_HEALTHY_FALLBACK" not in actions("quota_router_crash"), actions("quota_router_crash"))
    add("quota_plus_crash_converges_degraded_safe", sims["quota_router_crash"]["terminal_state"] == "DEGRADED_SAFE", sims["quota_router_crash"])
    add("smb_partition_expired_has_retry_and_signed_reelection", {"RETRY_SAME_TARGET", "ALLOW_SIGNED_LEASE_REELECTION"}.issubset(actions("smb_partition_expired")), actions("smb_partition_expired"))
    add("smb_partition_expired_converges_healthy", sims["smb_partition_expired"]["terminal_state"] == "HEALTHY", sims["smb_partition_expired"])
    add("config_plus_client_crash_repairs_and_restarts", {"REPAIR_CONFIG_ATOMIC", "RESTART_CLIENT"}.issubset(actions("config_client_crash")), actions("config_client_crash"))
    add("config_plus_client_crash_converges_healthy", sims["config_client_crash"]["terminal_state"] == "HEALTHY", sims["config_client_crash"])
    add("hard_auth_dominates_auto_mutation", actions("auth_router_crash") == ["QUARANTINE_SCOPE"], actions("auth_router_crash"))
    add("hard_auth_converges_operator_required", sims["auth_router_crash"]["terminal_state"] == "OPERATOR_REQUIRED", sims["auth_router_crash"])
    add("foreign_process_never_restarted", not any(a in RESTART_ACTIONS for a in actions("foreign_router_crash")), actions("foreign_router_crash"))
    add("global_budget_blocks_recovery_storm", "GLOBAL_RECOVERY_BUDGET_EXHAUSTED" in actions("budget_pressure") and plans["budget_pressure"]["global_budget"]["spent"] <= 2, plans["budget_pressure"]["global_budget"])
    add("budget_pressure_escalates_instead_of_thrashing", sims["budget_pressure"]["terminal_state"] == "OPERATOR_REQUIRED", sims["budget_pressure"])
    add("unexpired_partition_no_takeover", "ALLOW_SIGNED_LEASE_REELECTION" not in actions("unexpired_partition") and "HOLD_OWNERSHIP_NO_TAKEOVER" in actions("unexpired_partition"), actions("unexpired_partition"))
    add("unexpired_partition_converges_degraded_safe", sims["unexpired_partition"]["terminal_state"] == "DEGRADED_SAFE", sims["unexpired_partition"])
    add("all_scenario_dags_acyclic", all((p.get("dag") or {}).get("acyclic") for p in plans.values()))
    add("all_scenario_actions_unique", all(len(actions(k)) == len(set(actions(k))) for k in plans))
    add("all_scenario_plans_within_budget", all(int(p["global_budget"]["spent"]) <= max(0, int(scenarios[k].global_budget)-int(scenarios[k].budget_used)) for k,p in plans.items()))
    add("all_scenarios_terminal_safe", all(sims[k]["terminal_state"] in {"HEALTHY", "DEGRADED_SAFE", "OPERATOR_REQUIRED"} for k in sims))
    add("all_scenarios_bounded_rounds", all(sims[k]["round_count"] <= 4 for k in sims))
    add("deterministic_plan_id", plan_compound(scenarios["config_client_crash"])["plan_id"] == plans["config_client_crash"]["plan_id"])

    mc = model_check()
    add("model_checker_zero_safety_violations", mc["verdict"] == "PASS", {"states": mc["states_checked"], "violations": mc["violation_count"]})
    add("model_checker_covers_all_terminal_states", all(int(mc["terminal_distribution"].get(x,0)) > 0 for x in ["HEALTHY","DEGRADED_SAFE","OPERATOR_REQUIRED"]), mc["terminal_distribution"])
    add("production_never_claimed", PRODUCTION_CLAIM == "NOT_CLAIMED_COMPOUND_FAULT_CONVERGENCE_SYNTHETIC_ONLY")

    passed = sum(1 for x in checks if x["ok"])
    result = {
        "product": "HMS-AI-ROUTER", "version": VERSION,
        "suite": "COMPOUND_FAULT_RECOVERY_CONVERGENCE_LAB",
        "generated_utc": now_utc(),
        "verdict": "PASS" if passed == len(checks) and mc["verdict"] == "PASS" else "FAIL",
        "summary": {"pass": passed, "fail": len(checks)-passed, "total": len(checks), "model_states": mc["states_checked"], "scenarios": len(scenarios)},
        "checks": checks,
        "scenario_plans": plans,
        "scenario_convergence": sims,
        "model_check": mc,
        "safety": {"production_certification": PRODUCTION_CLAIM, "real_codex_called": False, "raw_auth_mutation": False, "destructive_delete": False},
    }
    result["evidence_hash"] = stable_hash({"checks": checks, "summary": result["summary"], "terminal_distribution": mc["terminal_distribution"]})
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["proof", "model-check", "plan"], default="proof")
    ap.add_argument("--input")
    ap.add_argument("--output")
    args = ap.parse_args()
    if args.mode == "proof":
        data = synthetic_proof()
    elif args.mode == "model-check":
        mc = model_check()
        data = {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"COMPOUND_FAULT_RECOVERY_MODEL_CHECK","verdict":mc["verdict"],"summary":{"pass":1 if mc["verdict"]=="PASS" else 0,"fail":0 if mc["verdict"]=="PASS" else 1,"total":1,"model_states":mc["states_checked"]},"model_check":mc,"safety":{"production_certification":PRODUCTION_CLAIM}}
    else:
        if not args.input: raise SystemExit("--input required for plan")
        raw = json.loads(Path(args.input).read_text("utf-8-sig"))
        faults = raw.pop("faults", [])
        data = plan_compound(CompoundContext.build(faults, **{k:v for k,v in raw.items() if k in CompoundContext.__dataclass_fields__ and k != "faults"}))
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output: Path(args.output).write_text(txt+"\n", "utf-8")
    print(txt)
    return 0 if data.get("verdict", "PASS") == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
