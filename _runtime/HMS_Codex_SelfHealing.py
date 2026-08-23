#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from datetime import datetime, timezone

VERSION = "25.39"
SECRET_RX = re.compile(r"(?:token|secret|password|cookie|api[_-]?key|authorization|refresh[_-]?token|access[_-]?token)", re.I)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path):
    return json.loads(Path(path).read_text("utf-8-sig"))


def scan_secret_keys(obj, prefix=""):
    hits=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            # Explicitly allow boolean/meta key-match fields; never raw secret values.
            if SECRET_RX.search(str(k)) and not str(k).lower().endswith(("_match","_present","_configured","_excluded")):
                hits.append(p)
            hits.extend(scan_secret_keys(v,p))
    elif isinstance(obj, list):
        for i,v in enumerate(obj): hits.extend(scan_secret_keys(v,f"{prefix}[{i}]"))
    return hits


def issue(code, severity, scope, detail, action=None, auto_safe=False, restart=False):
    return {
        "code": code, "severity": severity, "scope": scope, "detail": detail,
        "action": action, "auto_safe": bool(auto_safe), "restart_required": bool(restart)
    }


def audit(snapshot: dict):
    secret_hits=scan_secret_keys(snapshot)
    if secret_hits:
        raise ValueError("SNAPSHOT_CONTAINS_SECRET_FIELDS: "+", ".join(secret_hits[:12]))
    issues=[]
    g=snapshot.get("global") or {}
    if g.get("port_conflict_foreign"):
        issues.append(issue("GLOBAL_PORT_FOREIGN", "CRITICAL", "GLOBAL",
                            f"Port {g.get('proxy_port')} thuộc process không do HMS sở hữu. HMS sẽ không kill process này.",
                            None, False))
    if g.get("expected_hms_mode") and not g.get("provider_ok"):
        issues.append(issue("GLOBAL_PROVIDER_DRIFT", "HIGH", "GLOBAL",
                            "Codex global provider không còn trỏ tới hms_api_router.",
                            "REPAIR_GLOBAL_CONFIG", True, bool(g.get("client_running"))))
    if g.get("expected_hms_mode") and not g.get("endpoint_ok"):
        issues.append(issue("GLOBAL_ENDPOINT_DRIFT", "HIGH", "GLOBAL",
                            "Codex global base_url lệch stable HMS endpoint.",
                            "REPAIR_GLOBAL_CONFIG", True, bool(g.get("client_running"))))
    if g.get("expected_hms_mode") and not g.get("client_key_match"):
        issues.append(issue("GLOBAL_CLIENT_KEY_DRIFT", "HIGH", "GLOBAL",
                            "HMS_ROUTER_API_KEY trong .env không khớp key hiện hành.",
                            "REPAIR_GLOBAL_CONFIG", True, bool(g.get("client_running"))))
    if g.get("managed_pid_stale"):
        issues.append(issue("GLOBAL_STALE_PID", "MEDIUM", "GLOBAL",
                            "State PID của Router global đã stale; chỉ xóa metadata PID, không kill process.",
                            "ARCHIVE_GLOBAL_STALE_STATE", True))

    for inst in snapshot.get("instances") or []:
        iid=str(inst.get("id") or "?")
        scope=f"INSTANCE:{iid}"
        if not inst.get("root_exists", True):
            issues.append(issue("INSTANCE_ROOT_MISSING","CRITICAL",scope,"Instance root không tồn tại.",None,False)); continue
        if not inst.get("project_exists", True):
            issues.append(issue("PROJECT_MISSING","CRITICAL",scope,"Project path không tồn tại hoặc ổ đĩa đang offline.",None,False))
        if not inst.get("identity_ok", True):
            issues.append(issue("IDENTITY_DRIFT","CRITICAL",scope,"Identity Isolation audit không PASS; fail-closed.",None,False))
        if not inst.get("binding_ok", True):
            issues.append(issue("BINDING_DRIFT","HIGH",scope,"Project/account/instance binding bị lệch hoặc thiếu.","RESYNC_BINDING",True))
        if not inst.get("config_exists", True) or not inst.get("config_provider_ok", True) or not inst.get("config_endpoint_ok", True):
            issues.append(issue("INSTANCE_CONFIG_DRIFT","HIGH",scope,"Isolated config.toml thiếu hoặc provider/endpoint bị lệch.","REPAIR_INSTANCE_CONFIG",True,bool(inst.get("client_running"))))
        if not inst.get("router_config_exists", True):
            issues.append(issue("ROUTER_CONFIG_MISSING","HIGH",scope,"Router config.yaml của instance bị thiếu.","REWRITE_ROUTER_CONFIG",True,bool(inst.get("router_running"))))
        if inst.get("port_conflict_foreign"):
            issues.append(issue("INSTANCE_PORT_FOREIGN","CRITICAL",scope,
                                f"Port {inst.get('port')} đang thuộc process khác. HMS tuyệt đối không kill process lạ.",None,False))
        elif inst.get("listener_owned") and int(inst.get("listener_pid") or 0)>0 and int(inst.get("router_pid") or 0)!=int(inst.get("listener_pid") or 0):
            issues.append(issue("ROUTER_PID_NOT_ADOPTED","MEDIUM",scope,"Router đúng executable đang listen nhưng store PID chưa khớp.","ADOPT_ROUTER_PID",True))
        elif int(inst.get("router_pid") or 0)>0 and not inst.get("router_owned") and int(inst.get("listener_pid") or 0)==0:
            issues.append(issue("STALE_ROUTER_PID","MEDIUM",scope,"Router PID stale; chỉ xóa metadata PID.","CLEAR_STALE_ROUTER_PID",True))
        if int(inst.get("client_pid") or 0)>0 and not inst.get("client_owned"):
            issues.append(issue("STALE_CLIENT_PID","MEDIUM",scope,"Client PID không còn chứng minh được ownership; chỉ xóa metadata PID.","CLEAR_STALE_CLIENT_PID",True))
        if not inst.get("auth_pool_ok", True):
            issues.append(issue("AUTH_POOL_DRIFT","HIGH",scope,"Credential pool snapshot không khớp Project Affinity/fallback hiện tại.","RESYNC_CREDENTIAL_POOL",not bool(inst.get("router_running")),bool(inst.get("router_running"))))
        if inst.get("model_policy_drift"):
            issues.append(issue("MODEL_POLICY_DRIFT","MEDIUM",scope,"Model/reasoning policy đã lưu nhưng isolated config chưa khớp.","REAPPLY_MODEL_POLICY",not bool(inst.get("client_running")),bool(inst.get("client_running"))))

    counts={"critical":0,"high":0,"medium":0,"low":0,"auto_safe":0,"operator":0}
    for x in issues:
        sev=x["severity"].lower(); counts[sev]=counts.get(sev,0)+1
        if x.get("auto_safe"): counts["auto_safe"]+=1
        else: counts["operator"]+=1
    verdict="PASS" if not issues else ("BLOCKED" if counts["critical"] else "REPAIRABLE")
    return {"version":VERSION,"generated_utc":now_utc(),"verdict":verdict,"summary":{"issues":len(issues),**counts},"issues":issues,
            "invariants":{"never_kill_unowned_process":True,"no_destructive_delete":True,"no_secret_snapshot":True,"evidence_before_repair":True,"readback_required":True}}


def plan(snapshot: dict, safe_only=True):
    a=audit(snapshot)
    actions=[]
    seen=set()
    for x in a["issues"]:
        act=x.get("action")
        if not act or (safe_only and not x.get("auto_safe")): continue
        key=(x["scope"],act)
        if key in seen: continue
        seen.add(key)
        actions.append({"scope":x["scope"],"action":act,"reason":x["code"],"auto_safe":x["auto_safe"],"restart_required":x["restart_required"]})
    return {"version":VERSION,"generated_utc":now_utc(),"audit":a,"safe_only":bool(safe_only),"actions":actions,
            "action_count":len(actions),"requires_operator":a["summary"]["operator"]>0}


def synthetic():
    base={"global":{"proxy_port":8317,"expected_hms_mode":True,"provider_ok":True,"endpoint_ok":True,"client_key_match":True,
                    "client_running":False,"port_conflict_foreign":False,"managed_pid_stale":False},
          "instances":[{"id":"A","root_exists":True,"project_exists":True,"identity_ok":True,"binding_ok":True,
                        "config_exists":True,"config_provider_ok":True,"config_endpoint_ok":True,"router_config_exists":True,
                        "port":8400,"port_conflict_foreign":False,"listener_owned":True,"listener_pid":120,"router_pid":99,
                        "router_owned":False,"router_running":True,"client_pid":77,"client_owned":False,"client_running":False,
                        "auth_pool_ok":True,"model_policy_drift":False}]}
    p=plan(base,True)
    acts={(x["scope"],x["action"]) for x in p["actions"]}
    checks=[]
    checks.append(("adopt_owned_router",("INSTANCE:A","ADOPT_ROUTER_PID") in acts))
    checks.append(("clear_stale_client",("INSTANCE:A","CLEAR_STALE_CLIENT_PID") in acts))
    foreign=json.loads(json.dumps(base)); foreign["instances"][0].update({"listener_owned":False,"port_conflict_foreign":True,"listener_pid":222,"router_pid":0})
    fp=plan(foreign,True)
    checks.append(("foreign_port_never_auto_killed",not any(x["action"] in ("STOP_PROCESS","KILL_PROCESS") for x in fp["actions"])))
    drift=json.loads(json.dumps(base)); drift["instances"][0].update({"listener_pid":120,"router_pid":120,"router_owned":True,"client_pid":0,"config_endpoint_ok":False,"router_running":False,"auth_pool_ok":False})
    dp=plan(drift,True); da={x["action"] for x in dp["actions"]}
    checks.append(("config_repair_planned","REPAIR_INSTANCE_CONFIG" in da))
    checks.append(("auth_resync_only_when_router_stopped","RESYNC_CREDENTIAL_POOL" in da))
    secret=json.loads(json.dumps(base)); secret["global"]["api_key"]="DO_NOT_STORE"
    rejected=False
    try:audit(secret)
    except ValueError:rejected=True
    checks.append(("secret_snapshot_rejected",rejected))
    return {"version":VERSION,"checks":[{"name":n,"ok":ok} for n,ok in checks],"pass":sum(1 for _,x in checks if x),"total":len(checks),"verdict":"PASS" if all(x for _,x in checks) else "FAIL"}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("audit","plan","synthetic"),default="audit")
    ap.add_argument("--snapshot")
    ap.add_argument("--safe-only",default="true")
    ap.add_argument("--output")
    a=ap.parse_args()
    try:
        if a.mode=="synthetic": data=synthetic()
        else:
            if not a.snapshot: raise ValueError("--snapshot required")
            snap=load_json(a.snapshot)
            data=audit(snap) if a.mode=="audit" else plan(snap,str(a.safe_only).lower() not in ("0","false","no"))
        out={"ok": data.get("verdict")!="FAIL", "mode":a.mode,"data":data}
    except Exception as e:
        out={"ok":False,"mode":a.mode,"error":repr(e)}
    text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text,"utf-8")
    print(text)
    return 0 if out.get("ok") else 2

if __name__=="__main__": raise SystemExit(main())
