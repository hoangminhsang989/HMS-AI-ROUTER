#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from datetime import datetime, timezone

VERSION="25.74"

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def extract_backend_actions(ps: str) -> list[str]:
    m=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',ps,re.S)
    if not m:
        return []
    return re.findall(r'"([^"]+)"',m.group(1))

def check(name: str, ok: bool, detail: str="") -> dict:
    return {"name":name,"ok":bool(ok),"detail":detail}

def run(root: Path, contract_path: Path) -> dict:
    root=root.resolve()
    contract_path=contract_path.resolve()
    contract=load(contract_path)
    ps_path=root/'HMS_AI_ROUTER_v25.23.1.ps1'
    gui_path=root/'HMS_GUI.pyw'
    readme_path=root.parent/'README.txt'
    lan_path=root/'HMS_Codex_LanPool.py'
    ps=ps_path.read_text(encoding='utf-8-sig',errors='replace')
    gui=gui_path.read_text(encoding='utf-8-sig',errors='replace')
    readme=readme_path.read_text(encoding='utf-8-sig',errors='replace') if readme_path.exists() else ''
    lan=lan_path.read_text(encoding='utf-8-sig',errors='replace')
    expected=list(contract.get('backend_actions') or [])
    actual=extract_backend_actions(ps)
    tests=[]
    tests.append(check('backend_action_set_exact', actual==expected, f'expected={len(expected)} actual={len(actual)}'))
    tests.append(check('backend_actions_unique', len(actual)==len(set(actual)), f'unique={len(set(actual))}'))
    for a in expected:
        if a=='ui':
            continue
        # Every public action must have a concrete dispatch reference beyond ValidateSet.
        tests.append(check(f'dispatch.{a}', ps.count(a)>=2, 'public action referenced by dispatcher/runtime'))
    gui_literals=sorted(set(re.findall(r'self\.backend\(\s*["\']([^"\']+)',gui)))
    unknown=[a for a in gui_literals if a not in expected]
    tests.append(check('gui_literal_actions_subset_contract', not unknown, 'unknown='+','.join(unknown)))
    forbidden=[x.lower() for x in contract['codex_only_public_surface']['forbid_backend_action_substrings']]
    bad=[a for a in actual if any(f in a.lower() for f in forbidden)]
    tests.append(check('codex_only_no_antigravity_public_action', not bad, 'bad='+','.join(bad)))
    tests.append(check('powershell_version_sync', f'$script:Version = "{VERSION}"' in ps))
    tests.append(check('gui_version_sync', f'APP_VERSION = "{VERSION}"' in gui))
    tests.append(check('readme_version_sync', f'v{VERSION}' in readme))
    stable=contract['stable_runtime_contract']
    stable_tokens=[
        f'ProxyPort = {stable["default_proxy_port"]}',
        f"Set-RootTomlKey $t \"model_provider\" '\"{stable['global_provider']}\"'",
        f'[model_providers.{stable["global_provider"]}]',
        f'[model_providers.{stable["instance_provider"]}]',
        f'wire_api = "{stable["wire_api"]}"',
        stable['settings_path_name'], stable['state_path_name'], stable['lan_node_state_name'],
        stable['lan_latest_name'], stable['lan_history_name'], stable['lan_pairing_credential_target'],
        stable['security_router_key_target'], stable['security_seal_key_target'],
    ]
    for tok in stable_tokens:
        tests.append(check('stable_token.'+re.sub(r'[^A-Za-z0-9]+','_',tok)[:80], tok in ps, tok))
    tests.append(check('lan_pairing_kdf_salt_stable', stable['lan_pairing_kdf_salt'] in lan, stable['lan_pairing_kdf_salt']))
    for tok in contract['codex_only_public_surface']['required_defaults']:
        tests.append(check('codex_only_default.'+re.sub(r'[^A-Za-z0-9]+','_',tok)[:70], tok in ps,tok))
    tests.append(check('antigravity_gui_hidden_default', 'CodexShowAntigravityPanel = $false' in ps and 'OpenAntigravityOnEnable = $false' in ps))
    tests.append(check('stable_endpoint_not_changed', 'base_url = "http://127.0.0.1:$port/v1"' in ps and 'hms_api_router' in ps))
    for ver,spec in contract.get('milestones',{}).items():
        files_ok=all((root/f).exists() for f in spec.get('files',[]))
        actions_ok=all(a in actual for a in spec.get('actions',[]))
        tokens_ok=all(tok in ps for tok in spec.get('tokens',[]))
        tests.append(check(f'milestone_{ver}_surface_preserved', files_ok and actions_ok and tokens_ok,
                           f'files={files_ok} actions={actions_ok} tokens={tokens_ok}'))
    passed=sum(1 for x in tests if x['ok'])
    return {
        'product':'HMS-AI-ROUTER','version':VERSION,'suite':'REGRESSION_COMPATIBILITY_FREEZE',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'verdict':'PASS' if passed==len(tests) else 'FAIL',
        'summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},
        'contract':{'path':contract_path.name,'baseline':contract.get('contract_baseline'),'backend_actions':len(expected)},
        'tests':tests,
        'windows_powershell_5_1_runtime':'DEFERRED_BY_OPERATOR'
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--contract'); ap.add_argument('--output'); a=ap.parse_args()
    root=Path(a.root); contract=Path(a.contract) if a.contract else root/'CODEX_PUBLIC_CONTRACT_V25_46.json'
    out=run(root,contract); txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+'\n',encoding='utf-8')
    print(txt); return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
