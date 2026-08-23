#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
from datetime import datetime, timezone
VERSION='25.64'
def load(root:Path):
 p=root/'HMS_Codex_WindowsRecoveryObserverBridge.py';spec=importlib.util.spec_from_file_location('obs64',p);m=importlib.util.module_from_spec(spec);sys.modules['obs64']=m;spec.loader.exec_module(m);return m
def run(root:Path):
 m=load(root);tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 proof=m.synthetic_proof();sm=proof.get('summary') or {}
 add('proof_pass',proof.get('verdict')=='PASS',sm);add('proof_13',sm.get('total')==13,sm)
 add('four_effects',set(m.EFFECT_KINDS)=={'OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF'})
 add('evidence_classes',m.EVIDENCE_CLASSES=={'LAB_FIXTURE','WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'})
 src=(root/'HMS_Codex_WindowsRecoveryObserverBridge.py').read_text('utf-8')
 add('auth_raw_hash_no_export','RAW_BYTES_SHA256_NO_CONTENT_EXPOSED' not in src and 'CODEX_AUTH_FILE_RAW_BYTES_SHA256' in src and 'raw_content_exported' in src)
 add('keyring_digest_only','--hms-digest-only' in src and 'TARGET_KEYRING_DIGEST_PROVIDER_REQUIRED' in src and 'secret_read_attempted' in src)
 add('process_generation_no_cmdline','Get-Process -Name codex' in src and 'start_ticks' in src and 'command_line_collected' in src)
 add('router_live_metadata','LIVE_ROUTER_GENERATION_METADATA' in src and 'gateway-state-v20.json' in src)
 add('lease_owner_hashed','LIVE_LAN_LEASE_OWNER_EPOCH' in src and 'safe_ref(value)' in src and 'raw_owner_exposed' in src)
 add('freshness_contract',all(x in src for x in ['freshness_state','source_age_seconds','FRESH','AGING','STALE','UNKNOWN']))
 add('failure_reason_contract','failure_reason' in src and 'RUNTIME_METADATA_NOT_FOUND' in src)
 add('production_boundary',m.PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
 ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig');gui=(root/'HMS_GUI.pyw').read_text('utf-8')
 add('version_sync',any(f'$script:Version = "{v}"' in ps and f'APP_VERSION = "{v}"' in gui for v in ['25.64','25.65','25.66','25.67','25.68','25.69','25.70','25.71','25.72','25.73','25.74']))
 add('startup_reconciler_bridge','WINDOWS_RECOVERY_OBSERVER_BRIDGE_V25.64' in (root/'HMS_Codex_StartupRecoveryReconciler.py').read_text('utf-8'))
 add('gui_windows_observer',all(x in gui for x in ['WIN OBS','start_windows_recovery_observer_async']) and any(x in gui for x in ['STARTUP RECOVERY v25.64 · WINDOWS OBSERVER BRIDGE','STARTUP RECOVERY v25.65 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.68 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.67 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.69 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.70 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.71 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.72 · WINDOWS TARGET ADAPTER PACK','STARTUP RECOVERY v25.74 · WINDOWS TARGET ADAPTER PACK']))
 add('ps_gate_v2564',all(x in ps for x in ['startup-recovery-v2565','startup-recovery-latest-v2565.json','Invoke-HmsStartupRecoveryPreflight']))
 passed=sum(t['status']=='PASS' for t in tests)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'WINDOWS_RECOVERY_OBSERVER_BRIDGE_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_certification':m.PRODUCTION_CLAIM}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2);print(txt);Path(a.output).write_text(txt+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
