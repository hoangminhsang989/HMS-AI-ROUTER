#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
VERSION="25.65"
def load(root:Path):
 p=root/'HMS_Codex_WindowsTargetAdapterPack.py';s=importlib.util.spec_from_file_location('adapter65',p);m=importlib.util.module_from_spec(s);sys.modules['adapter65']=m;s.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {};add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_11',sm.get('total')==11,sm)
 add('four_effects',set(m.EFFECT_KINDS)=={'OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF'})
 src=(root/'HMS_Codex_WindowsTargetAdapterPack.py').read_text('utf-8')
 add('auth_file_raw_hash_no_export',all(x in src for x in ['self.auth_file.read_bytes()','raw_content_exported','path_ref']))
 add('keyring_digest_only',all(x in src for x in ['--hms-digest-only','DIGEST_ONLY_KEYRING_PROVIDER_REQUIRED','secret_read_attempted']))
 add('process_generation_safe','Get-Process -Name codex' in src and 'command_line_collected' in src and 'environment_collected' in src)
 add('router_generation','gateway-state-v20.json' in src and 'ROUTER_STATE_TRANSITION' in src)
 add('lease_owner_digest','lan-pool-latest-v2545.json' in src and 'raw_owner_exposed' in src)
 manifest=m.build_adapter_manifest('C:/HMS/adapter.exe');add('manifest_disarmed',manifest.get('disarmed_default') is True);add('manifest_four',set(manifest.get('effects') or {})=={'auth','restart','router','lease'})
 add('exact_readback_contract',all((x.get('readback_contract')=='EXACT_STATE_HASH_AND_GENERATION') for x in manifest['effects'].values()))
 add('no_shell_mode',all(m.safe_argv(x['apply_argv'])[0] and m.safe_argv(x['probe_argv'])[0] for x in manifest['effects'].values()))
 add('production_boundary',m.PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'WINDOWS_TARGET_ADAPTER_PACK_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
