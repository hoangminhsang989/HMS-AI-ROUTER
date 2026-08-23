#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.47'

def run(root:Path,matrix_path:Path):
    m=json.loads(matrix_path.read_text(encoding='utf-8-sig'))
    ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text(encoding='utf-8-sig',errors='replace')
    lan=(root/'HMS_Codex_LanPool.py').read_text(encoding='utf-8-sig',errors='replace')
    tests=[]
    def add(name,ok,detail=''):tests.append({'name':name,'ok':bool(ok),'detail':detail})
    cfg=m['config_contract']; mig=m['migration_contract']
    add('client_process_detection', '$names=@("Codex","ChatGPT")' in ps)
    add('codex_cli_discovery', 'Get-Command codex.exe' in ps and 'Start-Process "codex.exe"' in ps)
    add('codex_desktop_discovery', all(x in ps for x in ['Programs\\Codex\\Codex.exe','LOCALAPPDATA "Codex\\Codex.exe"','ProgramFiles "Codex\\Codex.exe"']))
    add('chatgpt_desktop_launch', "Start-AppByName '^ChatGPT$'" in ps and 'Start-Process "chatgpt.exe"' in ps)
    add('global_provider_contract', all(x in ps for x in [f'[model_providers.{cfg["global_provider"]}]',f'env_key = "{cfg["env_key"]}"',f'wire_api = "{cfg["wire_api"]}"','requires_openai_auth = false']))
    add('instance_provider_contract', f'[model_providers.{cfg["instance_provider"]}]' in ps and "EnvironmentVariables['CODEX_HOME']" in ps)
    add('stable_loopback_endpoint', 'base_url = "http://127.0.0.1:$port/v1"' in ps and 'base_url = "http://127.0.0.1:$([int]$Instance.port)/v1"' in ps)
    add('snapshot_before_mutation', 'Snapshot-ClientConfigIfNeeded' in ps and 'before-router-config.toml' in ps and 'before-router-dotenv' in ps)
    add('restore_on_disable', 'function Restore-ClientConfig' in ps and 'RestoreOnDisable = $true' in ps and 'Đã khôi phục config/.env trước HMS Router.' in ps)
    add('restart_generation_guard', 'CODEX_CLIENT_STALE' in ps and 'CODEX_ENV_RELOAD_NOT_CONFIRMED' in ps and 'Get-CodexConfigGenerationTime' in ps)
    add('current_settings_path_preserved', mig['current_settings'] in ps)
    for name in mig['fallback_settings']:
        add('fallback_settings.'+re.sub(r'[^A-Za-z0-9]+','_',name), name in ps,name)
    add('corrupt_settings_backup', 'settings-corrupt-' in ps and 'Copy-Item $settingsSource $backup -Force' in ps)
    add('protected_router_key_target_preserved', mig['security_router_key_target'] in ps)
    add('protected_lan_pairing_target_preserved', mig['lan_pairing_target'] in ps)
    add('lan_pairing_kdf_salt_preserved', mig['lan_pairing_kdf_salt'] in lan)
    add('plain_key_protected_migration', 'CodexSecurityMigratePlainKeys' in ps and 'Set-HmsProtectedSecret $script:SecurityCredentialGlobalTarget $plainSettingsKey' in ps)
    add('settings_save_removes_plain_global_key', "$persist['LocalApiKey']=''" in ps)
    add('no_client_version_whitelist', 'CodexClientMinVersion' not in ps and 'CodexClientMaxVersion' not in ps)
    passed=sum(1 for x in tests if x['ok'])
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'CODEX_CLIENT_COMPATIBILITY_AND_MIGRATION','generated_utc':datetime.now(timezone.utc).isoformat(),
            'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,
            'runtime_windows_cli_desktop':'DEFERRED_BY_OPERATOR','powershell_5_1_runtime':'DEFERRED_BY_OPERATOR'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--matrix');ap.add_argument('--output');a=ap.parse_args()
    root=Path(a.root);matrix=Path(a.matrix) if a.matrix else root/'CODEX_CLIENT_COMPATIBILITY_MATRIX_V25_46.json'
    out=run(root,matrix);txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n',encoding='utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
