#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import HMS_Codex_RealCertification as rc

VERSION = "25.49"


class RealHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/hms/health":
            body = b'{"ok":true,"service":"real-cert-validator"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_response(404); self.end_headers(); return
        auth = self.headers.get("Authorization", "")
        if auth != "Bearer validator-secret":
            body = b'{"error":{"message":"bad key"}}'
            self.send_response(401); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        _ = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        events = [
            'data: {"type":"response.created"}\n\n',
            'data: {"type":"response.output_text.delta","delta":"H"}\n\n',
            'data: {"type":"response.completed"}\n\n',
            'data: [DONE]\n\n',
        ]
        body = "".join(events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body); self.wfile.flush()

    def log_message(self, *_args):
        pass


def make_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), RealHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    return srv, th


def write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def fake_codex(path: Path) -> None:
    write_exe(path, r'''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if args==['--version']:
    print('codex-cli 0.147.0'); raise SystemExit(0)
if args==['--help']:
    print('Usage: codex [COMMAND]\nCommands:\n  login\n  doctor\n  exec\n  app\n'); raise SystemExit(0)
if args[:2]==['login','status']:
    print('Logged in using ChatGPT', file=sys.stderr); raise SystemExit(0)
if args and args[0]=='doctor':
    home=os.environ.get('CODEX_HOME','')
    print('overallStatus: ok\nauth.credentials status: ok\nauth is configured\nconfig.load status: ok\nCODEX_HOME: '+home); raise SystemExit(0)
print('unsupported',file=sys.stderr); raise SystemExit(2)
''')


def fake_powershell(path: Path) -> None:
    write_exe(path, r'''#!/usr/bin/env python3
import sys
s=' '.join(sys.argv[1:])
if 'PSVersionTable.PSVersion.ToString' in s:
    print('5.1.19041.5607'); raise SystemExit(0)
if 'Parser]::ParseFile' in s:
    print('{"errors":0}'); raise SystemExit(0)
if 'Get-Process -Id' in s:
    print('{"path":"C:\\\\fake\\\\codex.exe","start":"2026-08-22T00:00:00.0000000Z"}'); raise SystemExit(0)
raise SystemExit(0)
''')


def run(root: Path) -> dict:
    checks = []
    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})

    add("version_is_25_49", rc.VERSION == VERSION, rc.VERSION)
    add("schema_v1", rc.SCHEMA_VERSION == 1)
    add("hard_live_cap_8", rc.MAX_LIVE_REQUEST_CAP == 8)
    add("fixed_safe_prompt", rc.SAFE_PROMPT == "Reply exactly HMS_CERT_OK")

    versions = {
        "codex-cli 0.147.0": "0.147.0",
        "OpenAI Codex v1.2.3": "1.2.3",
        "codex 99.0.1-alpha.4": "99.0.1",
    }
    for raw, expected in versions.items():
        p = rc.parse_codex_version(raw)
        add(f"version_parser_{expected}", p.get("ok") and p.get("version") == expected, p)
    add("version_parser_rejects_noise", not rc.parse_codex_version("hello").get("ok"))

    red = rc.redact_text("Authorization: Bearer SECRET OPENAI_API_KEY=ABC access_token=XYZ refresh_token=ZZZ")
    add("redact_bearer", "SECRET" not in red, red)
    add("redact_openai_key", "ABC" not in red, red)
    add("redact_access_token", "XYZ" not in red, red)
    add("redact_refresh_token", "ZZZ" not in red, red)

    with tempfile.TemporaryDirectory(prefix="hms-realcert-val-") as td:
        t = Path(td)
        codex = t / "codex"
        powershell = t / "powershell.exe"
        fake_codex(codex); fake_powershell(powershell)
        project1=t/"project1"; project2=t/"project2"; project1.mkdir(); project2.mkdir()
        home1=t/"home1"; home2=t/"home2"; home1.mkdir(); home2.mkdir()
        root1=t/"instance1"; root2=t/"instance2"; root1.mkdir(); root2.mkdir()
        (root1/"binding-v2536.json").write_text("{}")
        (root2/"binding-v2536.json").write_text("{}")
        (home1/"auth.json").write_text('{"auth_mode":"chatgpt","tokens":"DO_NOT_LOG"}')
        (home2/"auth.json").write_text('{"auth_mode":"chatgpt","tokens":"DO_NOT_LOG_2"}')

        cli = rc.inspect_codex_cli(str(codex))
        add("fake_cli_detected", cli.get("available"), cli)
        add("fake_cli_version", cli.get("version") == "0.147.0", cli)
        add("fake_cli_login_capability", cli.get("login_status_supported"), cli)
        add("fake_cli_doctor_capability", cli.get("doctor_supported"), cli)
        add("fake_cli_exec_capability", cli.get("exec_supported"), cli)
        add("fake_cli_app_capability", cli.get("app_command_supported"), cli)

        ps = rc.inspect_powershell(str(powershell), root/"HMS_AI_ROUTER_v25.23.1.ps1")
        add("fake_ps_runtime", ps.get("runtime_ok"), ps)
        add("fake_ps_51", ps.get("is_windows_powershell_5_1"), ps)
        add("fake_ps_parser", ps.get("parser_ok") and ps.get("parse_error_count") == 0, ps)

        login = rc.login_status(str(codex), home1)
        add("login_status_chatgpt", login.get("ok") and login.get("auth_mode") == "CHATGPT", login)
        add("login_does_not_mutate_auth", not login.get("auth_file_changed_during_status"), login)
        add("login_auth_hash_present_not_content", len(login.get("auth_file_before",{}).get("sha256", "")) == 64, login)
        add("login_summary_no_token_payload", "DO_NOT_LOG" not in json.dumps(login), login)

        doctor = rc.doctor_status(str(codex), home1)
        add("doctor_ok", doctor.get("ok"), doctor)
        add("doctor_home_signal", doctor.get("codex_home_signal"), doctor)
        add("doctor_auth_signal", doctor.get("auth_configured_signal"), doctor)

        srv1, th1 = make_server(); srv2, th2 = make_server()
        try:
            port1=srv1.server_address[1]; port2=srv2.server_address[1]
            store={"schemaVersion":2,"codexOnly":True,"instances":[
                {"id":"i-one","name":"one","projectDir":str(project1),"accountEmail":"one@example.invalid","root":str(root1),"codexHome":str(home1),"appData":str(root1/"app"),"routerDir":str(root1/"router"),"port":port1,"clientPid":0,"routerPid":0,"launchMode":"cli"},
                {"id":"i-two","name":"two","projectDir":str(project2),"accountEmail":"two@example.invalid","root":str(root2),"codexHome":str(home2),"appData":str(root2/"app"),"routerDir":str(root2/"router"),"port":port2,"clientPid":0,"routerPid":0,"launchMode":"cli"},
            ]}
            store_path=t/"codex-instances-v1.json"; store_path.write_text(json.dumps(store),encoding="utf-8")
            rows=rc.read_instance_store(store_path)
            add("store_two_instances", len(rows)==2, len(rows))
            topo=rc.topology_checks(rows)
            add("topology_two", topo.get("at_least_two_instances"), topo)
            add("topology_unique_projects", topo.get("unique_projects"), topo)
            add("topology_unique_homes", topo.get("unique_codex_homes"), topo)
            add("topology_dedicated_accounts", topo.get("dedicated_accounts"), topo)
            add("topology_unique_ports", topo.get("unique_ports"), topo)
            dumped=json.dumps(topo)
            add("topology_redacts_raw_project", str(project1) not in dumped and str(project2) not in dumped, dumped)
            add("topology_redacts_account", "one@example.invalid" not in dumped and "two@example.invalid" not in dumped, dumped)

            h=rc.health_probe("127.0.0.1",port1,1)
            add("health_application_contract", h.get("ok") and h.get("status")==200, h)

            live=rc.stream_response_probe("127.0.0.1",port1,"validator-secret","gpt-test",rc.SAFE_PROMPT,2)
            add("live_stream_pass", live.get("ok"), live)
            add("live_header_ttfb", live.get("header_ttfb_ms") is not None, live)
            add("live_first_sse", live.get("first_sse_event_ms") is not None, live)
            add("live_exact_text_delta_ttft", live.get("first_token_ttft_certified") and live.get("first_output_text_delta_ms") is not None, live)
            add("live_completion_signal", live.get("stream_completed_signal"), live)
            add("live_no_body_logging", live.get("response_body_logged") is False and live.get("prompt_logged") is False, live)
            add("live_no_key_logging", live.get("api_key_logged") is False and "validator-secret" not in json.dumps(live), live)
            bad=rc.stream_response_probe("127.0.0.1",port1,"wrong","gpt-test",rc.SAFE_PROMPT,2)
            add("live_bad_key_fails_closed", not bad.get("ok") and bad.get("status")==401, bad)
            nomodel=rc.stream_response_probe("127.0.0.1",port1,"validator-secret","",rc.SAFE_PROMPT,2)
            add("live_model_required", nomodel.get("error")=="LIVE_MODEL_REQUIRED", nomodel)

            env1=rc.secret_env_name("i-one","HMS_CERT_KEY_")
            add("secret_env_name_deterministic", env1=="HMS_CERT_KEY_I_ONE", env1)

            base=dict(root=str(root),instance_store=str(store_path),codex=str(codex),powershell=str(powershell),timeout_sec=1.0,allow_live_request=False,max_live_requests=0,model="",api_key_env_prefix="HMS_CERT_KEY_",live_timeout_sec=2.0,output="")
            out=rc.run(SimpleNamespace(**base))
            add("nonwindows_harness_runtime_deferred", out.get("verdict")=="HARNESS_READY_RUNTIME_DEFERRED", out.get("verdict"))
            add("nonwindows_no_production_claim", out.get("production_certification")=="NOT_CLAIMED", out.get("production_certification"))
            add("contract_backend_90_guard", out.get("contract_guards",{}).get("public_backend_action_exact_90_preserved"), out.get("contract_guards"))
            add("contract_no_auth_mutation", out.get("contract_guards",{}).get("auth_mutation") is False, out.get("contract_guards"))
            add("metric_boundary_no_ttft_inference", "never inferred" in out.get("metric_boundary",{}).get("model_token_ttft", ""), out.get("metric_boundary"))

            live_base=dict(base); live_base.update(allow_live_request=True,max_live_requests=1,model="gpt-test")
            old=os.environ.get("HMS_CERT_KEY_I_ONE")
            os.environ["HMS_CERT_KEY_I_ONE"]="validator-secret"
            try:
                live_out=rc.run(SimpleNamespace(**live_base))
            finally:
                if old is None: os.environ.pop("HMS_CERT_KEY_I_ONE",None)
                else: os.environ["HMS_CERT_KEY_I_ONE"]=old
            add("live_budget_exact_one", live_out.get("summary",{}).get("live_requests_executed")==1, live_out.get("summary"))
            add("live_request_pass_recorded", live_out.get("summary",{}).get("live_requests_pass")==1, live_out.get("summary"))
            add("live_output_no_secret", "validator-secret" not in json.dumps(live_out), "secret absent")

            bad_cap=dict(base);bad_cap.update(allow_live_request=True,max_live_requests=9,model="gpt-test")
            try:
                rc.run(SimpleNamespace(**bad_cap)); rejected=False
            except ValueError as exc:
                rejected="CAP_EXCEEDS" in str(exc)
            add("live_hard_cap_rejected", rejected)

            no_allow=dict(base);no_allow.update(max_live_requests=1,model="gpt-test")
            try:
                rc.run(SimpleNamespace(**no_allow)); rejected=False
            except ValueError as exc:
                rejected="EXPLICIT_ALLOW" in str(exc)
            add("live_requires_explicit_allow", rejected)

            no_model=dict(base);no_model.update(allow_live_request=True,max_live_requests=1,model="")
            try:
                rc.run(SimpleNamespace(**no_model)); rejected=False
            except ValueError as exc:
                rejected="LIVE_MODEL_REQUIRED" in str(exc)
            add("live_requires_model", rejected)
        finally:
            srv1.shutdown(); srv2.shutdown(); srv1.server_close(); srv2.server_close(); th1.join(timeout=1); th2.join(timeout=1)

    src=Path(rc.__file__).read_text("utf-8")
    add("source_no_version_allowlist", "allowlist" not in src.lower() or "hard_coded_codex_version_allowlist" in src, "capability based")
    add("source_login_status", '"login", "status"' in src)
    add("source_doctor_probe", '"doctor"' in src)
    add("source_responses_stream", '"/v1/responses"' in src and '"stream": True' in src)
    add("source_output_text_delta", "response.output_text.delta" in src)
    add("source_no_auth_delete", "unlink" not in src and "remove(auth" not in src.lower())
    add("source_no_account_switch", "account_switch_mutation" in src)

    passed=sum(1 for x in checks if x["ok"])
    return {
        "product":"HMS-AI-ROUTER","version":VERSION,"suite":"REAL_CODEX_CERTIFICATION_VALIDATOR",
        "verdict":"PASS" if passed==len(checks) else "FAIL",
        "summary":{"pass":passed,"fail":len(checks)-passed,"total":len(checks)},
        "checks":checks,
        "real_windows_codex_runtime":"NOT_EXECUTED_BY_SYNTHETIC_VALIDATOR",
        "production_certification":"NOT_CLAIMED",
    }


def main() -> int:
    ap=argparse.ArgumentParser();ap.add_argument("--root",default=str(Path(__file__).resolve().parent));ap.add_argument("--output",default="");a=ap.parse_args()
    out=run(Path(a.root));text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text);return 0 if out["verdict"]=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
