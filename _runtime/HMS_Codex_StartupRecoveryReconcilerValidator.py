#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, re, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.64'

def load(root:Path):
    p=root/'HMS_Codex_StartupRecoveryReconciler.py';spec=importlib.util.spec_from_file_location('sr63',p);m=importlib.util.module_from_spec(spec);sys.modules['sr63']=m;spec.loader.exec_module(m);return m

def run(root:Path):
    m=load(root);tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    proof=m.synthetic_proof();sm=proof.get('summary') or {}
    add('synthetic_proof_pass',proof.get('verdict')=='PASS',sm)
    add('proof_12_checks',int(sm.get('total',0))>=12,sm)
    add('four_observer_effects',m.EFFECT_KINDS=={'OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF'})
    add('convergence_vocab',m.CONVERGENCE=={'HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED'})
    add('conflicting_action_guard_broad',len(m.CONFLICTING_BACKEND_ACTIONS)>=20,len(m.CONFLICTING_BACKEND_ACTIONS))
    add('read_action_not_conflicting','get_accounts' not in m.CONFLICTING_BACKEND_ACTIONS)
    src=(root/'HMS_Codex_StartupRecoveryReconciler.py').read_text('utf-8')
    add('auth_file_hash_only','RAW_BYTES_SHA256_NO_CONTENT_EXPOSED' in src and 'read_bytes()' in src)
    add('keyring_secret_read_forbidden','TARGET_KEYRING_DIGEST_PROVIDER_REQUIRED' in src and 'secret_read_attempted' in src)
    add('process_no_cmdline','PID_IMAGE_DIGEST_NO_CMDLINE' in src and '.cmdline' not in src.lower() and 'commandline' not in src.lower())
    add('lan_owner_hashed','LEASE_METADATA_DIGEST_OWNER_HASHED' in src and 'owner_exposed' in src)
    add('v2560_discovery','recovery-transaction-journal-v2560.jsonl' in src)
    add('v2562_discovery','recovery-replay-v2562' in src and 'rglob("*.jsonl")' in src)
    add('hash_chain_validation','validate_hash_chain' in src and 'JOURNAL_CHAIN_INVALID' in src)
    add('external_change_fail_closed','CONCURRENT_EXTERNAL_CHANGE_OWNERSHIP_UNPROVEN' in src)
    add('durable_no_repeat','VERIFY_ONLY_NO_REPEAT' in src and 'DURABLE_EFFECT_EXTERNAL_MISMATCH' in src)
    add('atomic_gate_fsync','os.fsync' in src and 'os.replace' in src and 'startup-recovery-gate-v2565.json' in src)
    add('raw_identity_hashed','safe_ref(tx)' in src and 'transaction_ref' in src)
    add('production_claim_blocked',m.PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
    ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig');gui=(root/'HMS_GUI.pyw').read_text('utf-8')
    add('powershell_version_current',any(f'$script:Version = "{v}"' in ps for v in ['25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74']))
    add('gui_version_current',any(f'APP_VERSION = "{v}"' in gui for v in ['25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74']))
    add('powershell_direct_backend_guard','Invoke-HmsStartupRecoveryPreflight $BackendAction' in ps)
    add('powershell_private_auth_guard','Invoke-HmsStartupRecoveryPreflight "__official_auth_switch__"' in ps)
    add('powershell_fail_closed_errors',all(x in ps for x in ['STARTUP_RECOVERY_PREFLIGHT_UNAVAILABLE','STARTUP_RECOVERY_BLOCKED','startup-recovery-latest-v2565.json']))
    add('gui_startup_auto_reconcile','self.root.after(120, self.startup_recovery_reconcile_async)' in gui)
    add('gui_operator_banner',all(x in gui for x in ['STARTUP RECOVERY v25.74','HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED','LAB CRASH']))
    c=json.loads((root/'CODEX_PUBLIC_CONTRACT_V25_46.json').read_text('utf-8'));mm=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',ps,re.S);actions=re.findall(r'"([^"]+)"',mm.group(1)) if mm else []
    add('public_actions_still_90',actions==c.get('backend_actions') and len(actions)==90,len(actions))
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'STARTUP_RECOVERY_RECONCILER_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_certification':m.PRODUCTION_CLAIM}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
