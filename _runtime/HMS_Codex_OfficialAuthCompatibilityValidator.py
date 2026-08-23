#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tempfile, threading, time
from pathlib import Path
from datetime import datetime, timezone
from HMS_Codex_OfficialAuthCompatibility import *
VERSION = "25.59"
def ck(name, ok, detail=""): return {"name": name, "ok": bool(ok), "detail": detail}
def run(root: Path):
    t=[]
    with tempfile.TemporaryDirectory(prefix="hms-auth59-") as td:
        home=Path(td)/".codex"; home.mkdir(); (home/"config.toml").write_text('cli_auth_credentials_store = "file"\n',encoding="utf-8")
        cur={"auth_mode":"chatgpt","type":"codex","tokens":{"access_token":"OLD_A","refresh_token":"OLD_R","id_token":"OLD_I","account_id":"acc-old"},"last_refresh":"old","custom_device_id":"keep-me","custom_keep":{"x":1},"email":"old@example.com"}
        (home/"auth.json").write_text(json.dumps(cur),encoding="utf-8")
        target={"auth_mode":"chatgpt","tokens":{"access_token":"NEW_A","refresh_token":"NEW_R","id_token":"NEW_I","account_id":"acc-new"},"last_refresh":"new"}
        snap=snapshot_current(home)
        t += [
            ck("snapshot_before_switch",snap["metadata"]["sha256"]==auth_metadata(cur,"file")["sha256"]),
            ck("snapshot_raw_not_in_metadata","OLD_A" not in json.dumps(snap["metadata"])),
            ck("codex_home_default",resolve_codex_home(None).name==".codex"),
            ck("store_key_shape",store_key(home).startswith("cli|") and len(store_key(home))==20),
            ck("file_store_parse",parse_store_mode('cli_auth_credentials_store="file"')=="file"),
            ck("keyring_store_parse",parse_store_mode('cli_auth_credentials_store="keyring"')=="keyring"),
            ck("auto_store_parse",parse_store_mode('cli_auth_credentials_store="auto"')=="auto"),
            ck("default_store_file",parse_store_mode("")=="file"),
            ck("keyring_backend_direct_default",keyring_backend_kind("")=="direct"),
            ck("keyring_backend_secrets_feature",keyring_backend_kind('[features]\nsecret_auth_storage = true\n')=="secrets"),
            ck("keyring_backend_direct_feature",keyring_backend_kind('[features]\nsecret_auth_storage = false\n')=="direct"),
        ]
        merged=rewrite_preserving_fields(cur,target)
        t += [
            ck("preserve_unrelated_custom",merged.get("custom_device_id")=="keep-me" and merged.get("custom_keep")=={"x":1}),
            ck("stale_account_identity_removed","email" not in merged),
            ck("stale_tokens_replaced",merged["tokens"]["access_token"]=="NEW_A" and "OLD_A" not in json.dumps(merged)),
            ck("oauth_auth_mode",merged.get("auth_mode")=="chatgpt"),
            ck("oauth_type_codex",merged.get("type")=="codex"),
            ck("oauth_clears_api_key",merged.get("OPENAI_API_KEY") is None),
            ck("new_account_id",merged["tokens"].get("account_id")=="acc-new"),
        ]
        missing_mode={"tokens":{"access_token":"x","refresh_token":"y"}}
        t.append(ck("missing_auth_mode_repaired",normalize_target_auth(missing_mode).get("auth_mode")=="chatgpt"))
        empty_refresh=normalize_target_auth({"tokens":{"access_token":"x"}})
        t.append(ck("empty_refresh_key_preserved","refresh_token" in empty_refresh["tokens"] and empty_refresh["tokens"]["refresh_token"]==""))
        tgt_identity={"tokens":{"access_token":"x","refresh_token":""},"agent_identity":"TARGET_AGENT"}
        merged_identity=rewrite_preserving_fields({**cur,"agent_identity":"OLD_AGENT"},tgt_identity)
        t.append(ck("target_agent_identity_preserved",merged_identity.get("agent_identity")=="TARGET_AGENT" and "OLD_AGENT" not in json.dumps(merged_identity)))
        api_target={"OPENAI_API_KEY":"sk-new","tokens":{"access_token":"stale"},"last_refresh":"stale"}
        api=rewrite_preserving_fields(cur,api_target)
        t += [ck("api_mode_normalized",api.get("auth_mode")=="apikey"),ck("api_stale_tokens_removed","tokens" not in api),ck("api_last_refresh_removed","last_refresh" not in api),ck("api_key_replaced",api.get("OPENAI_API_KEY")=="sk-new")]
        result=switch_auth(home,target); got,src=load_auth(home)
        t += [ck("file_switch_ok",result["ok"] and got==merged),ck("file_switch_readback",src=="file"),ck("file_switch_serialized",result.get("serialized") is True),ck("atomic_no_temp_left",not list(home.glob("auth.json.hms-*.tmp")))]
        # Keyring/auto deterministic fixtures.
        kr=MemoryKeyring({}); home2=Path(td)/"keyhome"; home2.mkdir(); (home2/"config.toml").write_text('cli_auth_credentials_store="keyring"\n')
        kr.save(KEYRING_SERVICE,store_key(home2),json.dumps(cur)); r2=switch_auth(home2,target,keyring=kr,keyring_backend="direct"); got2,src2=load_auth(home2,keyring=kr,keyring_backend="direct")
        t += [ck("keyring_service_name",KEYRING_SERVICE=="Codex Auth"),ck("keyring_switch",r2["resolved_source"]=="keyring" and src2=="keyring" and got2["tokens"]["access_token"]=="NEW_A"),ck("keyring_removes_auth_file",not (home2/"auth.json").exists())]
        home2s=Path(td)/"secretshome"; home2s.mkdir(); (home2s/"config.toml").write_text('cli_auth_credentials_store="keyring"\n[features]\nsecret_auth_storage=true\n'); kr.save(KEYRING_SERVICE,store_key(home2s),json.dumps(cur))
        try: load_auth(home2s,keyring=kr); secrets_blocked=False
        except AuthCompatibilityError as e: secrets_blocked="KEYRING_SECRETS_BACKEND_REQUIRES_OFFICIAL_CODEX_HELPER" in str(e)
        t.append(ck("secrets_backend_fail_closed",secrets_blocked))
        home3=Path(td)/"auto"; home3.mkdir(); (home3/"config.toml").write_text('cli_auth_credentials_store="auto"\n'); (home3/"auth.json").write_text(json.dumps(cur))
        a,src=load_auth(home3,keyring=kr,keyring_backend="direct"); t.append(ck("auto_fallback_file",src=="file" and a["tokens"]["access_token"]=="OLD_A"))
        switch_auth(home3,target,keyring=kr,keyring_backend="direct"); a3,src3=load_auth(home3,keyring=kr,keyring_backend="direct"); t += [ck("auto_prefers_keyring_on_save",src3=="keyring" and a3["tokens"]["access_token"]=="NEW_A"),ck("auto_removes_stale_file",not (home3/"auth.json").exists())]
        # Serialized switching: second write cannot interleave with first.
        home4=Path(td)/"serial"; home4.mkdir(); (home4/"auth.json").write_text(json.dumps(cur)); events=[]
        ta={"tokens":{"access_token":"A","refresh_token":"AR"}}; tb={"tokens":{"access_token":"B","refresh_token":"BR"}}
        def one(): events.append(("a0",time.monotonic())); switch_auth(home4,ta,hold_seconds=.12); events.append(("a1",time.monotonic()))
        def two(): time.sleep(.02); events.append(("b0",time.monotonic())); switch_auth(home4,tb); events.append(("b1",time.monotonic()))
        x=threading.Thread(target=one); y=threading.Thread(target=two); x.start(); y.start(); x.join(); y.join(); final,_=load_auth(home4); times=dict(events)
        t += [ck("serialized_lock_waits",times["b1"]>=times["a1"]),ck("serialized_final_consistent",final["tokens"]["access_token"]=="B")]
        # Readback mismatch must rollback raw pre-switch auth.
        class BadKR(MemoryKeyring):
            corrupt_once=True
            def load(self,service,key):
                raw=super().load(service,key)
                if self.corrupt_once and raw and "NEW_A" in raw:
                    self.corrupt_once=False
                    return raw.replace("NEW_A","CORRUPT")
                return raw
        bad=BadKR({}); home5=Path(td)/"bad"; home5.mkdir(); (home5/"config.toml").write_text('cli_auth_credentials_store="keyring"\n'); bad.save(KEYRING_SERVICE,store_key(home5),json.dumps(cur))
        try: switch_auth(home5,target,keyring=bad,keyring_backend="direct"); rolled=False
        except AuthCompatibilityError: rolled=True
        raw=bad.values[(KEYRING_SERVICE,store_key(home5))]
        t += [ck("readback_mismatch_raises",rolled),ck("readback_mismatch_rolls_back","OLD_A" in raw and "NEW_A" not in raw)]
        # Ephemeral is explicitly unsupported for persistent account switching.
        try: load_auth(home,"ephemeral",kr); eph=False
        except AuthCompatibilityError: eph=True
        t.append(ck("ephemeral_fail_closed",eph))
        # Official Codex credential-face identity remains compatible under Cockpit v1.3.27 baseline.
        ident=official_http_identity(); ident2=official_http_identity(originator="codex_vscode",codex_version="codex-cli 0.200.1")
        profiles=identity_profiles("codex-cli 0.200.1")
        t += [ck("originator_v1327_compatible",ident["originator"]=="codex_vscode"),ck("user_agent_compat_fallback",ident["User-Agent"].startswith("codex_vscode/")),ck("future_identity_derived",ident2["User-Agent"]=="codex_vscode/0.200.1"),ck("official_cli_profile",profiles["official_codex_cli"]["originator"]=="codex_cli_rs" and profiles["official_codex_cli"]["User-Agent"]=="codex_cli_rs/0.200.1")]
        audit=audit_payload(home)
        audit_text=json.dumps(audit)
        t += [ck("audit_metadata_only",all(s not in audit_text for s in ["NEW_A","NEW_R","NEW_I"])),ck("audit_claim_boundary","NO_LIVE_CODEX_CLAIM" in audit["claim_boundary"])]
        red=redact({"access_token":"SECRET_A","prompt":"SECRET_PROMPT","nested":{"response_body":"SECRET_BODY"}}); rt=json.dumps(red)
        t.append(ck("redaction_defense",all(s not in rt for s in ["SECRET_A","SECRET_PROMPT","SECRET_BODY"])))
    # Release/runtime wiring.
    ps=(root/"HMS_AI_ROUTER_v25.23.1.ps1").read_text(encoding="utf-8-sig",errors="replace")
    gui=(root/"HMS_GUI.pyw").read_text(encoding="utf-8-sig",errors="replace")
    rt=(root/"HMS_Runtime_KitValidator.py").read_text(encoding="utf-8",errors="replace")
    reg=(root/"HMS_Codex_RegressionFreezeValidator.py").read_text(encoding="utf-8",errors="replace")
    t += [
        ck("release_version_ps", bool(re.search(r'\$script:Version\s*=\s*\"(\d+)\.(\d+)\"', ps)) and tuple(map(int,re.search(r'\$script:Version\s*=\s*\"(\d+)\.(\d+)\"', ps).groups())) >= (25,59)),
        ck("release_version_gui", bool(re.search(r'APP_VERSION\s*=\s*\"(\d+)\.(\d+)\"', gui)) and tuple(map(int,re.search(r'APP_VERSION\s*=\s*\"(\d+)\.(\d+)\"', gui).groups())) >= (25,59)),
        ck("default_store_setting",'CodexOfficialAuthStoreMode = "auto"' in ps),
        ck("official_keyring_setting",'CodexOfficialAuthKeyringEntry = "Codex Auth"' in ps),
        ck("powershell_secret_backend_guard",'secret_auth_storage' in ps and 'OFFICIAL_KEYRING_SECRETS_BACKEND_REQUIRES_CODEX_HELPER' in ps),
        ck("official_originator_setting",'CodexOfficialOriginator = "codex_vscode"' in ps),
        ck("official_ua_setting",'CodexOfficialAuthUserAgent = "codex_vscode/0.146.0"' in ps),
        ck("snapshot_credential_manager",'Snapshot-HmsCodexOfficialAuthState' in ps and 'CodexOfficialAuthSnapshotCredentialTarget' in ps),
        ck("snapshot_cleanup",'DeleteGeneric' in ps and 'Clear-HmsCodexOfficialAuthSnapshot' in ps),
        ck("serialized_switch_mutex",'HMS_Codex_OfficialAuthSwitch_v1' in ps),
        ck("field_preserving_rewrite",'ConvertTo-HmsCodexOfficialAuthProjection' in ps and 'STALE_AUTH' in ps),
        ck("controlled_restart",'CodexLaunchAfterAuthSwitch' in ps and 'Restart-CodexForSwitch' in ps),
        ck("powershell_readback_verify",'AUTH_READBACK_FINGERPRINT_MISMATCH' in ps),
        ck("powershell_rollback",'Restore-HmsCodexOfficialAuthSnapshot' in ps),
        ck("gui_surface",all(x in gui for x in ["OFFICIAL AUTH COMPAT v25.59", "AUTH AUDIT", "start_official_auth_compat_async"])),
        ck("native_account_switch_button",all(x in gui for x in ["CHUYỂN AUTH", "official_auth_switch_async", "_finish_official_auth_switch"])),
        ck("private_switch_path_no_backend_action",all(x in ps for x in ["OfficialAuthSwitchEmail", "OfficialAuthSwitchResultPath", "Invoke-HmsCodexOfficialAuthSwitch $OfficialAuthSwitchEmail"]) and '"official_auth_switch"' not in ps.split('[ValidateSet(',1)[1].split(')]',1)[0]),
        ck("runtime_gate_wired","official_auth_compat" in rt.lower()),
        ck("regression_gate_wired","official_auth_compatibility" in reg),
    ]
    passed=sum(x["ok"] for x in t)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"OFFICIAL_AUTH_COMPATIBILITY_LAYER","generated_utc":datetime.now(timezone.utc).isoformat(),"verdict":"PASS" if passed==len(t) else "FAIL","summary":{"pass":passed,"fail":len(t)-passed,"total":len(t)},"tests":t,"cockpit_parity_baseline":"v1.3.27","oauth_identity":{"originator":OFFICIAL_ORIGINATOR,"User-Agent":OFFICIAL_AUTH_USER_AGENT_BASELINE},"claim_boundary":"SYNTHETIC_FILE_DIRECT_KEYRING_FIXTURES; SECRETS_BACKEND_GUARDED; REAL_CODEX_APP_SWITCH_DEFERRED"}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True); ap.add_argument("--output"); a=ap.parse_args(); o=run(Path(a.root)); txt=json.dumps(o,ensure_ascii=False,indent=2); print(txt)
    if a.output: Path(a.output).write_text(txt+"\n",encoding="utf-8")
    return 0 if o["verdict"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
