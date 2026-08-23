#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import HMS_Codex_ModelReasoningManager as modelmgr
except Exception:  # pragma: no cover - import failure is surfaced at apply time
    modelmgr = None

ENGINE_VERSION = "25.44"
SCHEMA_VERSION = 1
POLICY_VERSION = "25.44"
ROLES = ("SOLO", "CODER", "REVIEWER", "TESTER")
PROFILES = ("BALANCED", "FAST", "DEEP", "REVIEW", "TEST")
SECRET_TOKENS = (
    "token", "secret", "password", "cookie", "authorization", "api_key",
    "apikey", "access_key", "refresh_token", "access_token", "client_secret",
    "credential_blob", "router_key", "localapikey",
)
CONFIDENCE_WEIGHT = {"VERY_HIGH": 1.0, "HIGH": .8, "MEDIUM": .55, "LOW": .3, "NONE": 0.0, "": 0.0}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(v: Any) -> str:
    return str(v or "").strip()


def ek(v: Any) -> str:
    return norm(v).lower()


def f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def i(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def path_key(v: Any) -> str:
    s = norm(v)
    if not s:
        return ""
    try:
        return os.path.normcase(os.path.abspath(os.path.normpath(s))).replace("/", "\\").rstrip("\\").lower()
    except Exception:
        return s.replace("/", "\\").rstrip("\\").lower()


def read_json(path: Path | None, default: Any = None) -> Any:
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def secret_scan(obj: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower().replace("-", "_")
            p = f"{prefix}.{k}"
            safe_boolean_meta = lk in {"oauth_tokens_untouched"} and isinstance(v, bool)
            if any(t in lk for t in SECRET_TOKENS) and not safe_boolean_meta:
                hits.append(p)
            else:
                hits.extend(secret_scan(v, p))
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            hits.extend(secret_scan(v, f"{prefix}[{n}]"))
    return hits


def confidence(samples: int) -> str:
    if samples >= 50:
        return "VERY_HIGH"
    if samples >= 20:
        return "HIGH"
    if samples >= 5:
        return "MEDIUM"
    if samples > 0:
        return "LOW"
    return "NONE"


def role_profile(role: str, cfg: dict[str, Any], explicit: str = "") -> str:
    p = norm(explicit).upper()
    if p in PROFILES:
        return p
    role = norm(role).upper() or "SOLO"
    key = {
        "CODER": "coder_profile",
        "REVIEWER": "reviewer_profile",
        "TESTER": "tester_profile",
        "SOLO": "solo_profile",
    }.get(role, "solo_profile")
    p = norm(cfg.get(key)).upper()
    if p in PROFILES:
        return p
    return {"CODER": "BALANCED", "REVIEWER": "REVIEW", "TESTER": "TEST"}.get(role, "BALANCED")


def target_reasoning(profile: str, role: str) -> str:
    p = norm(profile).upper()
    r = norm(role).upper()
    if p == "FAST":
        return "low"
    if p == "DEEP":
        return "xhigh"
    if p == "REVIEW" or r == "REVIEWER":
        return "high"
    if p == "TEST" or r == "TESTER":
        return "medium"
    if r == "CODER":
        return "high"
    return "medium"


def choose_reasoning(model: str, desired: str) -> str:
    efforts = modelmgr.efforts_for(model) if modelmgr else ["auto", "low", "medium", "high"]
    desired = norm(desired).lower()
    order = ["none", "low", "medium", "high", "xhigh", "max"]
    if desired == "auto" and "auto" in efforts:
        return "auto"
    if desired not in order:
        desired = "medium"
    target = order.index(desired)
    candidates = [x for x in efforts if x in order]
    if not candidates:
        return "auto" if "auto" in efforts else efforts[0]
    return min(candidates, key=lambda x: abs(order.index(x) - target))


def model_caps(model: str) -> dict[str, Any]:
    if modelmgr:
        return modelmgr.model_caps(model)
    m = model.lower()
    return {
        "coding_likely": bool("codex" in m or m.startswith("gpt-5")),
        "reasoning_configurable": bool("gpt-5" in m or "codex" in m),
        "reasoning_efforts": ["auto", "low", "medium", "high"],
        "capability_source": "CONSERVATIVE_NAME_MATRIX",
    }


def analytics_indexes(analytics: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    accounts: dict[str, dict[str, Any]] = {}
    models: dict[tuple[str, str], dict[str, Any]] = {}
    workloads: dict[tuple[str, str], dict[str, Any]] = {}
    for row in analytics.get("accounts") or []:
        if isinstance(row, dict) and ek(row.get("account")):
            accounts[ek(row.get("account"))] = row
    for row in analytics.get("model_profiles") or []:
        if not isinstance(row, dict):
            continue
        account, model = ek(row.get("account")), norm(row.get("model"))
        if account and model:
            models[(account, model)] = row
    for row in analytics.get("workload_profiles") or []:
        if not isinstance(row, dict):
            continue
        account, workload = ek(row.get("account")), norm(row.get("request_type")).lower()
        if account and workload:
            workloads[(account, workload)] = row
    return accounts, models, workloads


def predictive_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    src = payload.get("plan") if isinstance(payload.get("plan"), dict) else payload
    for row in (src or {}).get("accounts") or []:
        if isinstance(row, dict) and ek(row.get("account") or row.get("email")):
            out[ek(row.get("account") or row.get("email"))] = row
    return out


def breaker_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    src = payload.get("plan") if isinstance(payload.get("plan"), dict) else payload
    instances = (src or {}).get("instances") or []
    if isinstance(instances, dict):
        for iid, inst in instances.items():
            accounts = (inst or {}).get("accounts") or {}
            if isinstance(accounts, dict):
                for account, row in accounts.items():
                    if ek(account):
                        out[(str(iid), ek(account))] = dict(row or {})
    else:
        for inst in instances:
            if not isinstance(inst, dict):
                continue
            iid = norm(inst.get("instance_id") or inst.get("id"))
            for row in inst.get("accounts") or []:
                if isinstance(row, dict):
                    account = ek(row.get("account") or row.get("email"))
                    if iid and account:
                        out[(iid, account)] = row
    return out


def closed_loop_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    src = payload.get("last_plan") if isinstance(payload.get("last_plan"), dict) else payload
    for inst in (src or {}).get("instances") or []:
        if not isinstance(inst, dict):
            continue
        iid = norm(inst.get("instance_id") or inst.get("id"))
        for row in inst.get("ranking") or []:
            if isinstance(row, dict):
                account = ek(row.get("account") or row.get("email"))
                if iid and account:
                    out[(iid, account)] = row
    return out


def policy_index(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in policy.get("projects") or []:
        if isinstance(row, dict) and path_key(row.get("project_dir")):
            out[path_key(row.get("project_dir"))] = row
    return out


def catalog_models(catalog: dict[str, Any], analytics: dict[str, Any]) -> list[dict[str, Any]]:
    if modelmgr:
        return modelmgr.normalize_catalog(catalog, analytics)
    rows = catalog.get("models") or catalog.get("data") or []
    out = []
    for row in rows:
        mid = norm(row if isinstance(row, str) else row.get("id") if isinstance(row, dict) else "")
        if mid:
            d = {"id": mid, "sources": ["LIVE_ROUTER"]}
            d.update(model_caps(mid))
            out.append(d)
    return out


def workload_key(role: str, profile: str) -> str:
    role = norm(role).upper()
    profile = norm(profile).upper()
    return {
        "CODER": "coding",
        "REVIEWER": "review",
        "TESTER": "test",
    }.get(role, profile.lower() if profile else "balanced")


def model_score(model: dict[str, Any], role: str, profile: str, pool_accounts: list[str], model_profiles: dict[tuple[str, str], dict[str, Any]], cfg: dict[str, Any]) -> tuple[float, list[str], int]:
    mid = norm(model.get("id"))
    m = mid.lower()
    caps = model_caps(mid)
    reasons: list[str] = []
    if role in ("CODER", "REVIEWER", "TESTER") and not bool(caps.get("coding_likely")):
        return -1.0, ["CAPABILITY_CODING_REQUIRED"], 0
    score = 52.0
    if caps.get("coding_likely"):
        score += 10.0; reasons.append("CODING_CAPABLE")
    if caps.get("reasoning_configurable"):
        score += 5.0; reasons.append("REASONING_CONFIGURABLE")
    if "codex" in m:
        score += 6.0; reasons.append("CODEX_MODEL")
    if profile in ("DEEP", "REVIEW"):
        if "5.6" in m or "5.5" in m or "5.4" in m:
            score += 5.0; reasons.append("DEEP_PROFILE_MATCH")
        if caps.get("reasoning_configurable"):
            score += 3.0
    elif profile in ("FAST", "TEST"):
        if any(x in m for x in ("mini", "flash", "fast")):
            score += 7.0; reasons.append("FAST_PROFILE_MATCH")
    elif profile == "BALANCED" and "codex" in m:
        score += 3.0

    weighted = 0.0; weight = 0.0; samples = 0
    for account in pool_accounts:
        row = model_profiles.get((ek(account), mid))
        if not row:
            continue
        conf = norm(row.get("confidence")).upper()
        w = CONFIDENCE_WEIGHT.get(conf, 0.0)
        n = i(row.get("requests"))
        if w <= 0 or n < i(cfg.get("min_model_samples"), 3):
            continue
        weighted += f(row.get("quality_score"), 50.0) * w
        weight += w
        samples += n
    if weight > 0:
        q = weighted / weight
        adj = max(-12.0, min(12.0, (q - 50.0) * .24))
        score += adj
        reasons.append("MODEL_ANALYTICS_%s" % ("POSITIVE" if adj >= 0 else "NEGATIVE"))
    return clamp(score), reasons, samples


def account_score(instance_id: str, account: str, model: str, workload: str,
                  account_rows: dict[str, dict[str, Any]], model_profiles: dict[tuple[str, str], dict[str, Any]],
                  workload_profiles: dict[tuple[str, str], dict[str, Any]], predictive: dict[str, dict[str, Any]],
                  breaker: dict[tuple[str, str], dict[str, Any]], closed: dict[tuple[str, str], dict[str, Any]],
                  cfg: dict[str, Any]) -> dict[str, Any]:
    akey = ek(account)
    base_row = account_rows.get(akey) or {}
    closed_row = closed.get((instance_id, akey)) or {}
    state = norm((breaker.get((instance_id, akey)) or {}).get("desired_state") or (breaker.get((instance_id, akey)) or {}).get("state") or base_row.get("circuit_state") or "CLOSED").upper()
    pred = predictive.get(akey) or {}
    risk = norm(pred.get("risk") or pred.get("predictive_risk") or base_row.get("predictive_risk") or "UNKNOWN").upper()
    status = norm(base_row.get("status") or closed_row.get("status") or "READY").upper()
    eligible = status == "READY" and state != "OPEN" and risk != "EMERGENCY"
    reasons: list[str] = []
    if status != "READY": reasons.append("STATUS_" + (status or "UNKNOWN"))
    if state == "OPEN": reasons.append("CIRCUIT_OPEN")
    if state == "HALF_OPEN": reasons.append("CIRCUIT_HALF_OPEN")
    if risk == "EMERGENCY": reasons.append("PREDICTIVE_EMERGENCY")
    elif risk == "HIGH": reasons.append("PREDICTIVE_HIGH")

    score = f(closed_row.get("score"), f(base_row.get("quality_score"), 50.0))
    samples = i(base_row.get("requests_7d"))
    mrow = model_profiles.get((akey, model)) or {}
    if mrow and i(mrow.get("requests")) >= i(cfg.get("min_model_samples"), 3):
        conf = norm(mrow.get("confidence")).upper()
        q = f(mrow.get("quality_score"), 50.0)
        adj = (q - 50.0) * .24 * CONFIDENCE_WEIGHT.get(conf, 0.0)
        adj = max(-12.0, min(12.0, adj))
        score += adj
        samples = max(samples, i(mrow.get("requests")))
        if abs(adj) >= 1.0: reasons.append("MODEL_ACCOUNT_AFFINITY")
    wrow = workload_profiles.get((akey, workload)) or {}
    if wrow and i(wrow.get("requests")) >= i(cfg.get("min_model_samples"), 3):
        conf = norm(wrow.get("confidence")).upper()
        q = f(wrow.get("quality_score"), 50.0)
        adj = (q - 50.0) * .10 * CONFIDENCE_WEIGHT.get(conf, 0.0)
        adj = max(-5.0, min(5.0, adj))
        score += adj
        samples = max(samples, i(wrow.get("requests")))
        if abs(adj) >= 1.0: reasons.append("WORKLOAD_ACCOUNT_AFFINITY")
    if state == "HALF_OPEN":
        score = min(score, 25.0)
    return {
        "account": account,
        "score": round(clamp(score), 1),
        "eligible": eligible,
        "status": status,
        "circuit_state": state,
        "predictive_risk": risk,
        "samples": samples,
        "confidence": confidence(samples),
        "reason_codes": reasons,
    }


def build_plan(fleet: dict[str, Any], catalog: dict[str, Any], analytics: dict[str, Any], predictive: dict[str, Any], breaker: dict[str, Any], closed_loop: dict[str, Any], policy: dict[str, Any], cfg: dict[str, Any], scope: dict[str, Any] | None = None) -> dict[str, Any]:
    if secret_scan(cfg):
        raise ValueError("SMART_MODEL_ROUTER_SECRET_FIELD_REJECTED")
    models = catalog_models(catalog, analytics)
    require_live = bool(cfg.get("require_live_model", True))
    account_rows, model_profiles, workload_profiles = analytics_indexes(analytics)
    pred = predictive_index(predictive)
    brk = breaker_index(breaker)
    closed = closed_loop_index(closed_loop)
    pmap = policy_index(policy)
    safe_accounts = {ek(x.get("email") or x.get("account")): x for x in (fleet.get("accounts") or []) if isinstance(x, dict) and ek(x.get("email") or x.get("account"))}
    for k, v in safe_accounts.items():
        account_rows.setdefault(k, v)

    scope_project = path_key((scope or {}).get("project_dir"))
    scope_role = norm((scope or {}).get("role")).upper()
    recommendations: list[dict[str, Any]] = []
    blocked = 0; running_guarded = 0; applicable = 0

    for inst in fleet.get("instances") or []:
        if not isinstance(inst, dict):
            continue
        iid = norm(inst.get("id") or inst.get("instance_id"))
        project = norm(inst.get("project_dir") or inst.get("project"))
        if not iid or not project:
            continue
        if scope_project and path_key(project) != scope_project:
            continue
        role = norm(inst.get("team_role") or "SOLO").upper()
        if role not in ROLES:
            role = "SOLO"
        if scope_role and role != scope_role:
            continue
        current_pol = pmap.get(path_key(project)) or {}
        profile = role_profile(role, cfg, norm(current_pol.get("profile")))
        workload = workload_key(role, profile)
        manifest = inst.get("manifest") or {}
        pool_accounts = [norm(x.get("email")) for x in (manifest.get("accounts") or []) if isinstance(x, dict) and norm(x.get("email"))]
        if not pool_accounts:
            primary = norm(inst.get("account_email") or inst.get("account"))
            if primary:
                pool_accounts = [primary]

        blockers: list[str] = []
        if not bool(inst.get("identity_ok", True)): blockers.append("IDENTITY_BLOCKED")
        if not bool(inst.get("security_ok", True)): blockers.append("SECURITY_BLOCKED")
        if not bool(inst.get("binding_ok", True)): blockers.append("BINDING_DRIFT")
        if bool(inst.get("port_conflict_foreign")): blockers.append("FOREIGN_PORT_OWNER")
        stable = norm(inst.get("stable_endpoint") or manifest.get("stable_endpoint"))
        if stable and not stable.startswith("http://127.0.0.1:"): blockers.append("STABLE_ENDPOINT_NOT_LOCAL")
        if require_live and not models: blockers.append("LIVE_MODEL_CATALOG_EMPTY")

        pair_rows: list[dict[str, Any]] = []
        for model in models:
            mid = norm(model.get("id"))
            ms, mreasons, msamples = model_score(model, role, profile, pool_accounts, model_profiles, cfg)
            if ms < 0: continue
            desired = target_reasoning(profile, role)
            reasoning = choose_reasoning(mid, desired)
            for account in pool_accounts:
                ar = account_score(iid, account, mid, workload, account_rows, model_profiles, workload_profiles, pred, brk, closed, cfg)
                if not ar["eligible"]:
                    continue
                total = ms * .56 + f(ar.get("score"), 50.0) * .44
                pair_rows.append({
                    "model": mid, "reasoning": reasoning, "account": account,
                    "model_score": round(ms, 1), "account_score": ar["score"], "total_score": round(clamp(total), 1),
                    "model_samples": msamples, "account_samples": ar["samples"],
                    "confidence": confidence(max(msamples, ar["samples"])),
                    "reason_codes": list(dict.fromkeys(mreasons + ar["reason_codes"])),
                })
        pair_rows.sort(key=lambda x: (-f(x.get("total_score")), -i(x.get("model_samples")), -i(x.get("account_samples")), x.get("model", ""), ek(x.get("account"))))
        best = pair_rows[0] if pair_rows else None
        if not best and not blockers:
            blockers.append("NO_ELIGIBLE_MODEL_ACCOUNT_PAIR")
        current_model = norm(current_pol.get("model"))
        current_reasoning = norm(current_pol.get("reasoning")) or "auto"
        primary = pool_accounts[0] if pool_accounts else norm(inst.get("account_email") or inst.get("account"))
        current_score = 0.0
        if current_model:
            for row in pair_rows:
                if row["model"] == current_model and ek(row["account"]) == ek(primary):
                    current_score = f(row.get("total_score")); break
        delta = round((f(best.get("total_score")) if best else 0.0) - current_score, 1)
        running = bool(inst.get("client_running"))
        sticky_guard = running and bool(cfg.get("protect_running_sessions", True))
        if sticky_guard:
            running_guarded += 1
        min_delta = f(cfg.get("min_score_delta"), 5.0)
        apply_allowed = bool(best and not blockers and not sticky_guard and (not current_model or delta >= min_delta or best.get("model") == current_model))
        if apply_allowed: applicable += 1
        if blockers: blocked += 1
        status = "BLOCKED" if blockers else ("STICKY_GUARD" if sticky_guard else ("APPLY_READY" if apply_allowed else "KEEP_CURRENT"))
        max_adj = clamp(f(cfg.get("max_account_adjustment"), 6.0), 0.0, 8.0)
        adjustments = []
        if best:
            for account in pool_accounts:
                adjustments.append({
                    "account": account,
                    "score_adjustment": round(max_adj if ek(account) == ek(best.get("account")) else 0.0, 1),
                    "model": best.get("model"),
                    "role": role,
                })
        rec = {
            "scope_id": stable_hash({"instance": iid, "project": path_key(project), "role": role})[:20],
            "instance_id": iid,
            "instance_name": norm(inst.get("name")) or iid,
            "project_dir": project,
            "team_id": norm(inst.get("team_id")),
            "team_role": role,
            "team_epoch": i(inst.get("team_epoch"), 0),
            "profile": profile,
            "workload": workload,
            "client_running": running,
            "router_online": bool(inst.get("router_online")),
            "stable_endpoint": stable,
            "current_model": current_model,
            "current_reasoning": current_reasoning,
            "current_account": primary,
            "current_score": round(current_score, 1),
            "recommended_model": best.get("model") if best else "",
            "recommended_reasoning": best.get("reasoning") if best else "",
            "recommended_account": best.get("account") if best else "",
            "recommended_score": best.get("total_score") if best else 0.0,
            "score_delta": delta,
            "confidence": best.get("confidence") if best else "NONE",
            "status": status,
            "apply_allowed": apply_allowed,
            "sticky_session_guard": sticky_guard,
            "blockers": list(dict.fromkeys(blockers)),
            "reason_codes": best.get("reason_codes") if best else [],
            "account_adjustments": adjustments,
            "candidate_pairs": pair_rows[:12],
        }
        rec["decision_hash"] = stable_hash({k: rec[k] for k in ("instance_id", "project_dir", "team_role", "current_model", "recommended_model", "recommended_reasoning", "recommended_account", "status", "blockers")})
        recommendations.append(rec)

    recommendations.sort(key=lambda x: (x.get("status") == "BLOCKED", x.get("project_dir", "").lower(), {"CODER": 0, "REVIEWER": 1, "TESTER": 2, "SOLO": 3}.get(x.get("team_role"), 9)))
    plan = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": utcnow(),
        "mode": norm(cfg.get("mode") or "OBSERVE").upper(),
        "summary": {
            "scopes": len(recommendations),
            "blocked": blocked,
            "sticky_guarded": running_guarded,
            "apply_ready": applicable,
            "live_models": len(models),
        },
        "recommendations": recommendations,
        "safety": {
            "stable_endpoint_untouched": True,
            "session_affinity_authoritative": True,
            "running_client_hot_switch_blocked": True,
            "identity_isolation_hard_gate": True,
            "security_hard_gate": True,
            "account_signal_bounded": True,
            "max_account_score_adjustment": clamp(f(cfg.get("max_account_adjustment"), 6.0), 0.0, 8.0),
            "auth_files_mutated_by_this_engine": False,
            "oauth_tokens_untouched": True,
            "request_body_consumed": False,
            "prompt_consumed": False,
            "destructive_delete": False,
        },
        "privacy": "NO_PROMPT_NO_REQUEST_BODY_NO_OAUTH_NO_API_KEY_NO_COOKIE",
    }
    plan["plan_hash"] = stable_hash(plan)
    if secret_scan(plan):
        raise ValueError("SMART_MODEL_ROUTER_PLAN_SECRET_SCAN_FAILED")
    return plan


def model_fleet_view(fleet: dict[str, Any]) -> dict[str, Any]:
    instances = []
    projects = []
    seen_projects: set[str] = set()
    for inst in fleet.get("instances") or []:
        if not isinstance(inst, dict): continue
        iid = norm(inst.get("id") or inst.get("instance_id")); project = norm(inst.get("project_dir") or inst.get("project"))
        if not iid or not project: continue
        instances.append({
            "id": iid, "name": norm(inst.get("name")), "account_email": norm(inst.get("account_email") or inst.get("account")),
            "project_dir": project, "root": norm(inst.get("root")), "codex_home": norm(inst.get("codex_home")),
            "app_data": norm(inst.get("app_data")), "router_dir": norm(inst.get("router_dir")), "port": i(inst.get("port")),
            "router_online": bool(inst.get("router_online")), "client_running": bool(inst.get("client_running")), "identity_ok": bool(inst.get("identity_ok", True)),
        })
        k = path_key(project)
        if k not in seen_projects:
            seen_projects.add(k)
            projects.append({"name": norm(inst.get("name")) or Path(project).name, "project_dir": project, "instance_id": iid, "preferred_account": norm(inst.get("account_email") or inst.get("account"))})
    return {"schema_version": 1, "version": ENGINE_VERSION, "instances": instances, "projects": projects}


def select_recommendations(plan: dict[str, Any], scope: dict[str, Any]) -> list[dict[str, Any]]:
    project = path_key(scope.get("project_dir"))
    role = norm(scope.get("role")).upper()
    out = []
    for row in plan.get("recommendations") or []:
        if project and path_key(row.get("project_dir")) != project:
            continue
        if role and norm(row.get("team_role")).upper() != role:
            continue
        out.append(row)
    return out


def apply_plan(plan: dict[str, Any], fleet: dict[str, Any], catalog: dict[str, Any], analytics: dict[str, Any], policy_path: Path, state_path: Path, cfg: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    if modelmgr is None:
        raise RuntimeError("MODEL_MANAGER_IMPORT_FAILED")
    manual = bool(scope.get("manual", False))
    if not manual and norm(cfg.get("mode") or "OBSERVE").upper() != "GUARDED_AUTO":
        return {"applied": False, "reason": "GUARDED_AUTO_REQUIRED_FOR_BACKGROUND"}
    rows = [x for x in select_recommendations(plan, scope) if bool(x.get("apply_allowed"))]
    if not rows:
        return {"applied": False, "reason": "NO_APPLY_READY_RECOMMENDATION"}
    policy_before = read_json(policy_path, {}) or {"schema_version": 1, "engine_version": "25.37", "projects": []}
    if secret_scan(policy_before):
        raise RuntimeError("MODEL_POLICY_SECRET_SCAN_FAILED")
    fleet_view = model_fleet_view(fleet)
    manager_cfg = {
        "enabled": True,
        "require_live_model": bool(cfg.get("require_live_model", True)),
        "default_reasoning": "medium",
    }
    applied: list[dict[str, Any]] = []
    try:
        for rec in rows:
            if bool(rec.get("client_running")):
                raise RuntimeError("RUNNING_CLIENT_HOT_SWITCH_BLOCKED:" + norm(rec.get("instance_id")))
            payload = {
                "project_dir": rec.get("project_dir"), "model": rec.get("recommended_model"),
                "reasoning": rec.get("recommended_reasoning"), "profile": rec.get("profile"),
            }
            modelmgr.set_policy(policy_path, payload, fleet_view, catalog, analytics, manager_cfg)
            result = modelmgr.apply_policy(policy_path, payload, fleet_view, catalog, analytics, manager_cfg)
            ar = result.get("apply_result") or {}
            applied.append({
                "instance_id": rec.get("instance_id"), "project_dir": rec.get("project_dir"), "role": rec.get("team_role"),
                "model": rec.get("recommended_model"), "reasoning": rec.get("recommended_reasoning"), "account_signal": rec.get("recommended_account"),
                "backup": ar.get("backup"), "config_sha256": ar.get("config_sha256"), "decision_hash": rec.get("decision_hash"),
            })
        state = read_json(state_path, {}) or {}
        history = list(state.get("history") or [])[-49:]
        item = {"time_utc": utcnow(), "plan_hash": plan.get("plan_hash"), "manual": manual, "applied": applied, "policy_before": policy_before}
        history.append({k: v for k, v in item.items() if k != "policy_before"})
        state.update({"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "updated_utc": utcnow(), "last_plan": plan, "last_apply": item, "history": history[-50:]})
        if secret_scan({k: v for k, v in state.items() if k != "last_apply"}):
            raise RuntimeError("SMART_MODEL_STATE_SECRET_SCAN_FAILED")
        atomic_json(state_path, state)
        return {"applied": True, "scopes": len(applied), "applied_rows": applied, "stable_endpoint_untouched": True, "session_affinity_untouched": True, "account_auth_mutated": False}
    except Exception:
        # Restore model policy first. Config rollback uses Model Manager's backup path from any completed row.
        atomic_json(policy_path, policy_before)
        for row in reversed(applied):
            backup = Path(norm(row.get("backup")))
            iid = norm(row.get("instance_id"))
            inst = next((x for x in fleet_view.get("instances") or [] if norm(x.get("id")) == iid), None)
            if not inst or not backup.exists():
                continue
            cfg_path = Path(norm(inst.get("codex_home"))) / "config.toml"
            try:
                backup_resolved = backup.resolve(); home_resolved = Path(norm(inst.get("codex_home"))).resolve()
                backup_resolved.relative_to(home_resolved)
                shutil.copy2(backup_resolved, cfg_path)
            except Exception:
                pass
        raise


def rollback(state_path: Path, policy_path: Path, fleet: dict[str, Any]) -> dict[str, Any]:
    state = read_json(state_path, {}) or {}
    last = state.get("last_apply") or {}
    applied = list(last.get("applied") or [])
    if not applied:
        raise RuntimeError("NO_SMART_MODEL_ROUTER_SNAPSHOT")
    policy_before = last.get("policy_before")
    if not isinstance(policy_before, dict):
        raise RuntimeError("SMART_MODEL_POLICY_SNAPSHOT_MISSING")
    fleet_view = model_fleet_view(fleet)
    restored = []
    for row in reversed(applied):
        iid = norm(row.get("instance_id")); backup = Path(norm(row.get("backup")))
        inst = next((x for x in fleet_view.get("instances") or [] if norm(x.get("id")) == iid), None)
        if not inst or not backup.exists():
            continue
        cfg_path = Path(norm(inst.get("codex_home"))) / "config.toml"
        try:
            backup.resolve().relative_to(Path(norm(inst.get("codex_home"))).resolve())
        except Exception:
            raise RuntimeError("SMART_MODEL_ROLLBACK_BACKUP_OUTSIDE_CODEX_HOME:" + iid)
        shutil.copy2(backup, cfg_path)
        restored.append({"instance_id": iid, "config": str(cfg_path), "backup": str(backup)})
    atomic_json(policy_path, policy_before)
    state["last_rollback_utc"] = utcnow()
    state["last_rollback"] = {"restored": restored, "policy_restored": True}
    state["last_apply"] = {}
    atomic_json(state_path, state)
    return {"rolled_back": True, "restored": restored, "policy_restored": True, "files_deleted": False}


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if norm(plan.get("policy_version")) != POLICY_VERSION:
        errors.append("POLICY_VERSION_MISMATCH")
    safety = plan.get("safety") or {}
    required = ["stable_endpoint_untouched", "session_affinity_authoritative", "running_client_hot_switch_blocked", "identity_isolation_hard_gate", "security_hard_gate", "account_signal_bounded", "oauth_tokens_untouched"]
    for key in required:
        if safety.get(key) is not True:
            errors.append("SAFETY_FALSE:" + key)
    if f(safety.get("max_account_score_adjustment"), 999) > 8:
        errors.append("ACCOUNT_ADJUSTMENT_TOO_LARGE")
    if secret_scan(plan):
        errors.append("SECRET_FIELD_IN_PLAN")
    for row in plan.get("recommendations") or []:
        if row.get("client_running") and row.get("apply_allowed"):
            errors.append("RUNNING_CLIENT_APPLY_ALLOWED:" + norm(row.get("instance_id")))
        if row.get("status") == "BLOCKED" and row.get("apply_allowed"):
            errors.append("BLOCKED_SCOPE_APPLY_ALLOWED:" + norm(row.get("instance_id")))
    return {"ok": not errors, "errors": errors, "scopes": len(plan.get("recommendations") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "evaluate", "apply", "rollback", "validate"), required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--fleet")
    ap.add_argument("--catalog")
    ap.add_argument("--analytics")
    ap.add_argument("--predictive")
    ap.add_argument("--breaker")
    ap.add_argument("--closed-loop")
    ap.add_argument("--policy")
    ap.add_argument("--input")
    ap.add_argument("--config-json", default="{}")
    args = ap.parse_args()
    try:
        state_path, plan_path = Path(args.state), Path(args.plan)
        cfg = json.loads(args.config_json or "{}")
        fleet = read_json(Path(args.fleet) if args.fleet else None, {}) or {}
        catalog = read_json(Path(args.catalog) if args.catalog else None, {}) or {}
        analytics = read_json(Path(args.analytics) if args.analytics else None, {}) or {}
        predictive = read_json(Path(args.predictive) if args.predictive else None, {}) or {}
        breaker = read_json(Path(args.breaker) if args.breaker else None, {}) or {}
        closed = read_json(Path(args.closed_loop) if args.closed_loop else None, {}) or {}
        policy_path = Path(args.policy) if args.policy else Path("model-policy-v2537.json")
        policy = read_json(policy_path, {}) or {}
        scope = read_json(Path(args.input) if args.input else None, {}) or {}

        if args.mode == "status":
            data = read_json(state_path, {}) or {}
            if not data:
                plan = build_plan(fleet, catalog, analytics, predictive, breaker, closed, policy, cfg, scope)
                data = {"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "updated_utc": utcnow(), "last_plan": plan, "summary": plan.get("summary")}
                atomic_json(state_path, data)
        elif args.mode in ("evaluate", "validate", "apply"):
            plan = build_plan(fleet, catalog, analytics, predictive, breaker, closed, policy, cfg, scope)
            atomic_json(plan_path, plan)
            validation = validate_plan(plan)
            if not validation["ok"]:
                raise RuntimeError("SMART_MODEL_PLAN_INVALID:" + ",".join(validation["errors"]))
            if args.mode == "validate":
                data = {"plan": plan, "validation": validation}
            elif args.mode == "apply":
                result = apply_plan(plan, fleet, catalog, analytics, policy_path, state_path, cfg, scope)
                data = {"plan": plan, "apply": result, "summary": plan.get("summary"), "validation": validation}
            else:
                state = read_json(state_path, {}) or {}
                state.update({"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "updated_utc": utcnow(), "last_plan": plan, "summary": plan.get("summary")})
                atomic_json(state_path, state)
                data = {"plan": plan, "summary": plan.get("summary"), "validation": validation}
        elif args.mode == "rollback":
            result = rollback(state_path, policy_path, fleet)
            data = {"rollback": result, "state": read_json(state_path, {}) or {}}
        else:
            raise RuntimeError("SMART_MODEL_MODE_UNSUPPORTED")
        print(json.dumps({"ok": True, "mode": args.mode, "data": data}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
