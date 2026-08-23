#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tempfile, re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import HMS_Codex_TargetMachineCertification as tm

VERSION="25.53"

def iso(): return datetime.now(timezone.utc).isoformat()
def write(p:Path,o): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding="utf-8");return p

def fake_real(verdict="PASS_REAL_CODEX_CERTIFIED"):
    return {
      "verdict":verdict,"host":{"windows":True},
      "powershell_5_1":{"is_windows_powershell_5_1":True,"parser_ok":True},
      "codex_cli":{"version_ok":True,"version":"0.147.0"},
      "topology":{"at_least_two_instances":True,"unique_projects":True,"unique_codex_homes":True,"dedicated_accounts":True,"unique_ports":True},
      "summary":{"managed_instances":2,"healthy_instance_endpoints":2,"live_requests_pass":1 if verdict.startswith("PASS") else 0,"exact_output_text_delta_ttft_observed":1 if verdict.startswith("PASS") else 0},"blockers":[]}

def quota_snapshot(stale=False):
    t="2020-01-01T00:00:00+00:00" if stale else iso()
    return {"accounts":[
      {"email":"a@example.com","plan":"PLUS","status":"READY","quota":{"source":"WHAM_USAGE","last_success_utc":t,"five_hour_remaining":80,"five_hour_window_present":True,"weekly_remaining":70,"weekly_window_present":True}},
      {"email":"b@example.com","plan":"PRO","status":"READY","quota":{"source":"WHAM_USAGE","last_success_utc":t,"five_hour_remaining":90,"five_hour_window_present":True,"weekly_remaining":85,"weekly_window_present":True}},
    ]}

def lan_snapshot(nodes=2):
    return {"lan_pool":{"summary":{"nodes":nodes,"online":nodes,"invalid_signatures":0},"security":{"credential_sharing":False,"raw_token_sharing":False,"secret_values_excluded":True}}}

def soak(profile,synthetic=False):
    sec=6*3600 if profile=="6h" else 24*3600
    return {"verdict":"PASS","profile":profile,"target_duration_sec":sec,"active_elapsed_sec":sec,"coverage_complete":True,"synthetic":synthetic,
            "coverage":{"router_probe_ok":2,"instance_probe_ok":4,"shared_roundtrip_ok":2},"session_count":2,"cycle_count":100,"resume_semantics":"ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED","privacy":{"lan_key_mode":"REAL"}}

def failover(restored=True):
    return {"verdict":"PASS","completed_local":iso(),"restored":restored,"probe_http":200,"target_email":"a@example.com","selected_label":"b@example.com"}

def mkargs(root,data,quota,lan,shared,real,fo,s6,s24):
    return SimpleNamespace(root=root,data_dir=data,instance_store="",codex="",powershell="",timeout_sec=1.0,quota_snapshot=str(quota),lan_snapshot=str(lan),shared=str(shared),real_cert_evidence=str(real),failover_evidence=str(fo),failover_max_age_hours=168.0,soak_state_dir="",soak6_evidence=str(s6),soak24_evidence=str(s24))

def run(root:Path):
    tests=[]
    def add(name,ok,detail=""): tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
    original=tm.real_cert_preflight
    with tempfile.TemporaryDirectory(prefix="hms-v2553-") as td:
        t=Path(td);data=t/"data";data.mkdir();shared=t/"shared";shared.mkdir()
        q=write(t/"quota.json",quota_snapshot());lan=write(t/"lan.json",lan_snapshot());real=write(t/"real.json",fake_real());fo=write(t/"fo.json",failover());s6=write(t/"s6.json",soak("6h"));s24=write(t/"s24.json",soak("24h"))
        try:
            tm.real_cert_preflight=lambda args: fake_real("READY_LIVE_REQUEST_REQUIRED")
            a=mkargs(root,data,q,lan,shared,real,fo,s6,s24);out=tm.run(a)
            add("full_real_evidence_pass",out["verdict"]=="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED",out["verdict"])
            add("all_7_stages_pass",out["summary"]["stages_pass"]==7 and out["summary"]["stages_total"]==7)
            add("production_scope_exact",out["production_certification"]=="TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK")
            add("preflight_no_quota",out["safety"]["preflight_consumes_quota"] is False)
            add("runner_never_mutates_auth",out["safety"]["runner_mutates_auth"] is False and out["safety"]["runner_disables_account"] is False)
            add("explicit_live_bridge_required",out["safety"]["live_request_requires_separate_explicit_bridge_confirmation"] is True)
            add("explicit_failover_required",out["safety"]["failover_requires_explicit_bounded_operator_test"] is True)
            add("no_secret_persistence",out["safety"]["raw_auth_or_token_persisted"] is False and out["safety"]["prompt_or_response_body_persisted"] is False)
            add("quota_two_real_sources",out["stages"]["quota"]["detail"]["real_source_accounts"]==2)
            add("quota_accounts_hashed",all("@" not in str(x) for r in out["stages"]["quota"]["detail"]["accounts_public"] for x in r.values() if isinstance(x,str)))
            add("lan_requires_two_online",out["stages"]["lan"]["detail"]["online"]==2)
            add("shared_roundtrip_pass",out["stages"]["lan"]["detail"]["shared_roundtrip"]["pass"] is True)
            add("shared_path_redacted","shared_path" not in out["stages"]["lan"]["detail"]["shared_roundtrip"] and bool(out["stages"]["lan"]["detail"]["shared_roundtrip"]["shared_path_hash"]))
            add("failover_different_account",out["stages"]["failover"]["detail"]["different_account_proven"] is True)
            add("failover_restore_required",out["stages"]["failover"]["detail"]["restored"] is True)
            add("soak6_exact_real",out["stages"]["soak_6h"]["detail"]["active_elapsed_sec"]>=21600 and not out["stages"]["soak_6h"]["detail"]["synthetic"])
            add("soak24_exact_real",out["stages"]["soak_24h"]["detail"]["active_elapsed_sec"]>=86400 and not out["stages"]["soak_24h"]["detail"]["synthetic"])
            add("downtime_not_counted",out["stages"]["soak_24h"]["detail"]["resume_semantics"]=="ACTIVE_PROCESS_TIME_ONLY_DOWNTIME_NOT_COUNTED")
            raw=json.dumps(out)
            add("report_no_email",'a@example.com' not in raw and 'b@example.com' not in raw)
            add("report_no_token_fields",all(x not in raw.lower() for x in ['access_token','refresh_token','authorization":"bearer','api_key":"']))

            # Negative gates: none can be satisfied by weaker/synthetic evidence.
            qst=write(t/"quota-stale.json",quota_snapshot(True));o=tm.run(mkargs(root,data,qst,lan,shared,real,fo,s6,s24));add("stale_quota_blocks_production",not o["stages"]["quota"]["pass"] and o["production_certification"]=="NOT_CLAIMED")
            lone=write(t/"lan1.json",lan_snapshot(1));o=tm.run(mkargs(root,data,q,lone,shared,real,fo,s6,s24));add("single_lan_node_blocks",not o["stages"]["lan"]["pass"])
            fs=write(t/"fo-bad.json",failover(False));o=tm.run(mkargs(root,data,q,lan,shared,real,fs,s6,s24));add("failover_restore_failure_blocks",not o["stages"]["failover"]["pass"])
            syn=write(t/"s24-syn.json",soak("24h",True));o=tm.run(mkargs(root,data,q,lan,shared,real,fo,s6,syn));add("synthetic_24h_never_certifies",not o["stages"]["soak_24h"]["pass"])
            deferred=write(t/"real-deferred.json",fake_real("READY_LIVE_REQUEST_REQUIRED"));o=tm.run(mkargs(root,data,q,lan,shared,deferred,fo,s6,s24));add("live_codex_request_required",not o["stages"]["codex"]["pass"])
            mock=quota_snapshot();mock["accounts"][0]["quota"]["source"]="SYNTHETIC";mock["accounts"][1]["quota"]["source"]="MOCK";qm=write(t/"quota-mock.json",mock);o=tm.run(mkargs(root,data,qm,lan,shared,real,fo,s6,s24));add("synthetic_quota_never_certifies",not o["stages"]["quota"]["pass"])
            old=failover();old["completed_local"]="2020-01-01T00:00:00+00:00";fold=write(t/"fo-old.json",old);o=tm.run(mkargs(root,data,q,lan,shared,real,fold,s6,s24));add("stale_failover_evidence_blocks",not o["stages"]["failover"]["pass"])
            nosec=lan_snapshot();nosec["lan_pool"]["security"]["credential_sharing"]=True;ln=write(t/"lan-secret.json",nosec);o=tm.run(mkargs(root,data,q,ln,shared,real,fo,s6,s24));add("lan_credential_sharing_blocks",not o["stages"]["lan"]["pass"])
            sshort=soak("6h");sshort["active_elapsed_sec"]=21599;sp=write(t/"s6-short.json",sshort);o=tm.run(mkargs(root,data,q,lan,shared,real,fo,sp,s24));add("soak_duration_cannot_be_shortened",not o["stages"]["soak_6h"]["pass"])

            # Static integration contract.
            target=(root/"HMS_Codex_TargetMachineCertification.py").read_text("utf-8")
            main=(root/"HMS_AI_ROUTER_v25.23.1.ps1").read_text("utf-8-sig")
            add("claim_boundary_present","Synthetic evidence never satisfies a production stage" in target)
            add("real_codex_module_reused","import HMS_Codex_RealCertification as rc" in target)
            add("live_quota_module_reused","import HMS_Codex_LiveQuotaIntelligence as lq" in target)
            add("seven_stage_names",all(x in target for x in ["host","codex","quota","failover","lan","soak_6h","soak_24h"]))
            mver=re.search(r'\$script:Version\s*=\s*"(\d+)\.(\d+)"',main)
            mv=(int(mver.group(1)),int(mver.group(2))) if mver else (0,0)
            add("main_version_at_least_25_53",mv >= (25,53),str(mv))
            add("public_backend_action_not_extended","target_machine" not in main.split('Add-Type -AssemblyName System.Windows.Forms')[0].lower())
            add("target_center_visible","TARGET-MACHINE CERTIFICATION v25.53" in main and "Show-HmsTargetMachineCertificationCenter" in main)
            add("preflight_button_visible","PREFLIGHT" in main and "LIVE 1 CODEX" in main)
            add("failover_center_reused","Show-HmsLiveFailoverCenter" in main)
            add("soak_center_reused","Show-HmsSoakCenter" in main)
        finally:
            tm.real_cert_preflight=original
    failed=[x for x in tests if x["status"]=="FAIL"]
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"TARGET_MACHINE_CERTIFICATION_VALIDATOR","generated_utc":iso(),"verdict":"PASS" if not failed else "FAIL","summary":{"pass":len(tests)-len(failed),"fail":len(failed),"total":len(tests)},"tests":tests}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",default=str(Path(__file__).resolve().parent));ap.add_argument("--output",default="");a=ap.parse_args()
    out=run(Path(a.root).resolve());txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt,encoding="utf-8")
    print(txt);return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
