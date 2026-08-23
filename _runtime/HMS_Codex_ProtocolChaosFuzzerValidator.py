#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import HMS_Codex_ProtocolChaosFuzzer as chaos

VERSION="25.56"

def version_tuple(v:str):
    return tuple(int(x) for x in re.findall(r"\d+",v)[:3])

def main_version(ps:str):
    m=re.search(r'\$script:Version\s*=\s*"([0-9.]+)"',ps)
    return m.group(1) if m else "0"

def run(root:Path):
    child=chaos.run(root,2556,300);tests=[]
    def add(name,ok,detail=""):tests.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
    for row in child.get("tests") or []:
        add("chaos."+str(row.get("name")),row.get("status")=="PASS",str(row.get("detail") or ""))
    sm=child.get("summary") or {};safety=child.get("safety") or {}
    add("fuzz_cases_300",int(sm.get("fuzz_cases") or 0)==300,str(sm.get("fuzz_cases")))
    add("seed_locked_2556",int(sm.get("seed") or 0)==2556,str(sm.get("seed")))
    add("child_verdict_pass",str(child.get("verdict") or "").startswith("PASS"),str(child.get("verdict")))
    add("no_real_codex",safety.get("real_codex_called") is False)
    add("no_real_quota",safety.get("real_quota_consumed") is False)
    add("no_real_auth",safety.get("real_auth_read_or_mutated") is False)
    add("no_prompt_persist",safety.get("request_or_prompt_persisted") is False)
    add("production_never_claimed",safety.get("production_certification")=="NOT_CLAIMED_PROTOCOL_CHAOS_SYNTHETIC_ONLY")
    add("partial_stream_replay_forbidden",safety.get("partial_stream_replay")=="FORBIDDEN")
    add("malformed_ws_failover_boundary",safety.get("malformed_ws_101")=="FAILOVER_BEFORE_RELAY")
    gw=(root/"HMS_Codex_SmartGateway.py").read_text("utf-8")
    fuzz=(root/"HMS_Codex_ProtocolChaosFuzzer.py").read_text("utf-8")
    reg=(root/"HMS_Codex_RegressionFreezeValidator.py").read_text("utf-8")
    runtime=(root/"HMS_Runtime_KitValidator.py").read_text("utf-8")
    gui=(root/"HMS_GUI.pyw").read_text("utf-8")
    ps=(root/"HMS_AI_ROUTER_v25.23.1.ps1").read_text("utf-8-sig")
    add("gateway_sse_integrity_probe",all(x in gw for x in ["class SSEIntegrityProbe","TRUNCATED_EOF","CLIENT_ABORT","stream_terminal_seen"]))
    add("gateway_body_length_integrity",all(x in gw for x in ["CONTENT_LENGTH_MISMATCH","expected_content_length","UPSTREAM_EOF"]))
    add("gateway_ws_101_validation",all(x in gw for x in ["validate_websocket_upgrade_head","SEC_WEBSOCKET_ACCEPT_MISMATCH","MALFORMED_UPGRADE"]))
    add("client_abort_not_upstream_failure",'error_source in ("CLIENT_WRITE","CLIENT_HEADER_WRITE")' in gw and 'error_source in ("UPSTREAM_READ","UPSTREAM_EOF")' in gw)
    add("fuzzer_retry_budget",all(x in fuzz for x in ["retry.sequence_503_429_200","retry.budget_never_exceeded","retry.post_without_idempotency_not_replayed"]))
    add("fuzzer_chunked_mutations",all(x in fuzz for x in ["chunked.invalid_hex_400","chunked.truncated_400","chunked.bad_terminator_400","chunked.over_limit_413"]))
    add("regression_suite_present","protocol_chaos_fuzzer" in reg and "HMS_Codex_ProtocolChaosFuzzerValidator.py" in reg)
    add("runtime_contract_present",all(x in runtime for x in ["v25_56.protocol_chaos_fuzzer","v25_56.sse_integrity_hardening","v25_56.websocket_upgrade_hardening"]))
    add("native_gui_surface",all(x in gui for x in ["PROTOCOL CHAOS / API FUZZ v25.56","FUZZ 300","start_protocol_chaos_async"]))
    add("powershell_surface",all(x in ps for x in ["PROTOCOL CHAOS / API FUZZ v25.56","Show-HmsProtocolChaosCenter","Invoke-HmsProtocolChaosFuzzer"]))
    add("main_version_at_least_25_56",version_tuple(main_version(ps))>=version_tuple("25.56"),main_version(ps))
    add("fuzzer_cannot_mint_target_cert",'"verdict":"PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED"' not in fuzz.replace(" ",""))
    failed=[x for x in tests if x["status"]=="FAIL"]
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"PROTOCOL_CHAOS_API_COMPATIBILITY_FUZZER_VALIDATOR",
            "verdict":"PASS" if not failed else "FAIL","summary":{"pass":len(tests)-len(failed),"fail":len(failed),"total":len(tests)},"tests":tests,
            "production_certification":"NOT_CLAIMED_PROTOCOL_CHAOS_SYNTHETIC_ONLY"}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",default=str(Path(__file__).resolve().parent));ap.add_argument("--output");a=ap.parse_args();out=run(Path(a.root).resolve());txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+"\n",encoding="utf-8")
    print(txt);return 0 if out["verdict"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
