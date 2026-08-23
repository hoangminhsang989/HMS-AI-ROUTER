#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, tempfile
from pathlib import Path
import HMS_Codex_SmartModelRouter as sm
import HMS_Codex_ClosedLoopRouter as cl


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(root: Path):
    work = root / "smart-model-v2544"
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    roles = [("i-coder","CODER","coder",8401,True),("i-review","REVIEWER","review",8402,False),("i-test","TESTER","test",8403,False)]
    instances=[]
    for iid, role, name, port, running in roles:
        ir=work/iid; home=ir/"codex-home"; app=ir/"app-data"; router=ir/"router"
        for d in (home,app,router): d.mkdir(parents=True, exist_ok=True)
        project=work/("project-main" if role=="CODER" else f"project-{name}-worktree")
        project.mkdir(parents=True, exist_ok=True)
        (home/"config.toml").write_text(
            f'model_provider = "hms_instance_router"\nmodel = "gpt-5.2-codex"\nmodel_reasoning_effort = "medium"\nbase_url = "http://127.0.0.1:{port}/v1"\n', encoding="utf-8")
        manifest={"stable_endpoint":f"http://127.0.0.1:{port}/v1","accounts":[{"email":"a@example.com"},{"email":"b@example.com"},{"email":"c@example.com"}]}
        instances.append({"id":iid,"name":iid,"account_email":"a@example.com","project_dir":str(project),"root":str(ir),"codex_home":str(home),"app_data":str(app),"router_dir":str(router),"port":port,"client_running":running,"router_online":True,"identity_ok":True,"security_ok":True,"binding_ok":True,"port_conflict_foreign":False,"stable_endpoint":manifest["stable_endpoint"],"team_id":"team-1","team_role":role,"team_epoch":2,"manifest":manifest})
    fleet={"accounts":[
        {"email":"a@example.com","status":"READY","health_score":90,"pool_score":84},
        {"email":"b@example.com","status":"READY","health_score":97,"pool_score":94},
        {"email":"c@example.com","status":"READY","health_score":99,"pool_score":98},
    ],"instances":instances,"secret_fields_excluded":True}
    catalog={"models":[
        {"id":"gpt-5.2-codex","source":"INSTANCE:i-review"},
        {"id":"gpt-5.6-codex","source":"INSTANCE:i-review"},
        {"id":"o4-mini","source":"INSTANCE:i-review"},
    ]}
    analytics={"accounts":[
        {"account":"a@example.com","status":"READY","quality_score":72,"requests_7d":30,"confidence":"HIGH"},
        {"account":"b@example.com","status":"READY","quality_score":93,"requests_7d":55,"confidence":"VERY_HIGH"},
        {"account":"c@example.com","status":"READY","quality_score":98,"requests_7d":80,"confidence":"VERY_HIGH"},
    ],"model_profiles":[
        {"account":"a@example.com","model":"gpt-5.2-codex","quality_score":65,"requests":30,"confidence":"HIGH"},
        {"account":"a@example.com","model":"gpt-5.6-codex","quality_score":78,"requests":20,"confidence":"HIGH"},
        {"account":"b@example.com","model":"gpt-5.2-codex","quality_score":70,"requests":35,"confidence":"HIGH"},
        {"account":"b@example.com","model":"gpt-5.6-codex","quality_score":98,"requests":50,"confidence":"VERY_HIGH"},
        {"account":"c@example.com","model":"gpt-5.6-codex","quality_score":99,"requests":70,"confidence":"VERY_HIGH"},
    ],"workload_profiles":[
        {"account":"b@example.com","request_type":"review","quality_score":97,"requests":25,"confidence":"HIGH"},
        {"account":"b@example.com","request_type":"test","quality_score":94,"requests":20,"confidence":"HIGH"},
    ]}
    predictive={"accounts":[{"account":"a@example.com","risk":"LOW"},{"account":"b@example.com","risk":"LOW"},{"account":"c@example.com","risk":"EMERGENCY"}]}
    breaker={"instances":[
        {"instance_id":"i-coder","accounts":[{"account":"c@example.com","desired_state":"OPEN"}]},
        {"instance_id":"i-review","accounts":[{"account":"c@example.com","desired_state":"OPEN"}]},
        {"instance_id":"i-test","accounts":[{"account":"c@example.com","desired_state":"OPEN"}]},
    ]}
    closed={"instances":[]}
    for iid,*_ in roles:
        closed["instances"].append({"instance_id":iid,"ranking":[
            {"account":"a@example.com","score":68,"status":"READY"},
            {"account":"b@example.com","score":91,"status":"READY"},
            {"account":"c@example.com","score":99,"status":"READY"},
        ]})
    policy={"schema_version":1,"engine_version":"25.37","projects":[]}
    for inst in instances:
        policy["projects"].append({"project_dir":inst["project_dir"],"instance_id":inst["id"],"model":"gpt-5.2-codex","reasoning":"medium","profile":"BALANCED" if inst["team_role"]=="CODER" else ("REVIEW" if inst["team_role"]=="REVIEWER" else "TEST")})
    cfg={"enabled":True,"mode":"OBSERVE","require_live_model":True,"protect_running_sessions":True,"min_model_samples":3,"min_score_delta":5,"max_account_adjustment":6,"coder_profile":"BALANCED","reviewer_profile":"REVIEW","tester_profile":"TEST","solo_profile":"BALANCED"}
    policy_path=work/"policy.json"; state_path=work/"state.json"; plan_path=work/"plan.json"; dump(policy_path,policy)
    plan=sm.build_plan(fleet,catalog,analytics,predictive,breaker,closed,policy,cfg,{})
    valid=sm.validate_plan(plan)
    byrole={x["team_role"]:x for x in plan["recommendations"]}
    checks={}
    checks["plan_valid"]=valid["ok"]
    checks["three_role_scopes"]=set(byrole)=={"CODER","REVIEWER","TESTER"}
    checks["running_coder_sticky_guard"]=byrole["CODER"]["status"]=="STICKY_GUARD" and not byrole["CODER"]["apply_allowed"]
    checks["stopped_reviewer_apply_ready"]=byrole["REVIEWER"]["status"]=="APPLY_READY" and byrole["REVIEWER"]["apply_allowed"]
    checks["best_model_is_live_coding_model"]=byrole["REVIEWER"]["recommended_model"]=="gpt-5.6-codex"
    checks["best_account_uses_analytics"]=byrole["REVIEWER"]["recommended_account"]=="b@example.com"
    checks["open_emergency_account_excluded"]=all(x["account"]!="c@example.com" for x in byrole["REVIEWER"]["candidate_pairs"])
    checks["noncoding_model_excluded"]=all(x["model"]!="o4-mini" for x in byrole["REVIEWER"]["candidate_pairs"])
    checks["account_signal_bounded"]=max(abs(float(a["score_adjustment"])) for r in plan["recommendations"] for a in r["account_adjustments"])<=6
    checks["privacy_contract"]=not sm.secret_scan(plan) and plan["safety"]["prompt_consumed"] is False and plan["safety"]["request_body_consumed"] is False
    # Manual apply only REVIEWER; running CODER remains byte-identical.
    coder_cfg=Path(byrole["CODER"]["project_dir"]).parent/"i-coder"/"codex-home"/"config.toml"
    # above derived path is wrong for temp layout; resolve from fleet instead
    coder_inst=next(x for x in instances if x["id"]=="i-coder"); reviewer_inst=next(x for x in instances if x["id"]=="i-review")
    coder_cfg=Path(coder_inst["codex_home"])/"config.toml"; reviewer_cfg=Path(reviewer_inst["codex_home"])/"config.toml"
    coder_before=coder_cfg.read_bytes(); reviewer_before=reviewer_cfg.read_bytes(); policy_before=policy_path.read_bytes()
    cfg_apply=dict(cfg); cfg_apply["mode"]="OBSERVE"
    apply_result=sm.apply_plan(plan,fleet,catalog,analytics,policy_path,state_path,cfg_apply,{"project_dir":reviewer_inst["project_dir"],"role":"REVIEWER","manual":True})
    reviewer_after=reviewer_cfg.read_text(encoding="utf-8")
    checks["apply_preserves_stable_endpoint_and_provider"]=apply_result["stable_endpoint_untouched"] and 'model_provider = "hms_instance_router"' in reviewer_after and f'base_url = "http://127.0.0.1:{reviewer_inst["port"]}/v1"' in reviewer_after and 'model = "gpt-5.6-codex"' in reviewer_after
    checks["running_coder_untouched_on_apply"]=coder_cfg.read_bytes()==coder_before
    rb=sm.rollback(state_path,policy_path,fleet)
    checks["rollback_restores_policy_and_config"]=rb["rolled_back"] and policy_path.read_bytes()==policy_before and reviewer_cfg.read_bytes()==reviewer_before
    # Direct hard-cap regression if config asks for >8.
    cfg_over=dict(cfg);cfg_over["max_account_adjustment"]=99
    over=sm.build_plan(fleet,catalog,analytics,predictive,breaker,closed,policy,cfg_over,{"project_dir":reviewer_inst["project_dir"]})
    checks["hard_cap_eight_even_if_config_higher"]=max(abs(float(a["score_adjustment"])) for r in over["recommendations"] for a in r["account_adjustments"])<=8
    # Closed-loop integration: Smart affinity changes ranking only within existing hard gates.
    cl_fleet={"accounts":fleet["accounts"],"instances":[{"id":"i-review","manifest":instances[1]["manifest"]}]}
    usage={"by_account_week":[{"account":"a@example.com","requests":30,"success":28,"latency_p95_ms":900},{"account":"b@example.com","requests":30,"success":28,"latency_p95_ms":900},{"account":"c@example.com","requests":30,"success":30,"latency_p95_ms":600}],"by_account_day":[],"by_account_hour":[]}
    cl_cfg={"min_score_delta":0,"min_samples":0,"hold_minutes":0,"cooldown_sec":0,"quota_floor_pct":0,"emergency_quota_pct":0,"preferred_weight":100,"secondary_weight":60,"tail_weight":25,"half_open_probe_priority":10}
    smart_state={"last_plan":plan}
    cl_plan=cl.evaluate(cl_fleet,usage,{},cl_cfg,breaker,predictive,analytics,smart_state)
    ranking=cl_plan["instances"][0]["ranking"]
    b_row=next(x for x in ranking if x["account"]=="b@example.com"); c_row=next(x for x in ranking if x["account"]=="c@example.com")
    checks["closed_loop_consumes_bounded_signal"]=float(b_row.get("smart_model_adjustment",0))==6.0 and "SMART_MODEL_ACCOUNT_AFFINITY" in b_row.get("reason_codes",[])
    checks["circuit_open_still_authoritative"]=c_row.get("eligible") is False and c_row.get("breaker_state")=="OPEN"
    passed=sum(bool(x) for x in checks.values()); total=len(checks)
    return {"product":"HMS-AI-ROUTER","version":"25.44","tranche":"SMART_MODEL_ROUTER","verdict":"PASS" if passed==total else "FAIL","summary":{"pass":passed,"fail":total-passed,"total":total},"checks":checks,"synthetic":{"reviewer_model":byrole["REVIEWER"]["recommended_model"],"reviewer_account":byrole["REVIEWER"]["recommended_account"],"coder_status":byrole["CODER"]["status"],"max_account_adjustment":plan["safety"]["max_account_score_adjustment"]},"runtime_windows_codex":"DEFERRED_BY_OPERATOR"}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--temp");ap.add_argument("--output")
    a=ap.parse_args(); tmp=Path(a.temp) if a.temp else Path(tempfile.mkdtemp(prefix="hms-smartmodel-v2544-"))
    try: out=run(tmp)
    finally:
        if not a.temp: shutil.rmtree(tmp,ignore_errors=True)
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+"\n",encoding="utf-8")
    print(txt)
    return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
