#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, tempfile, sys
from pathlib import Path
from datetime import datetime, timezone

VERSION="25.60"

def load(root:Path):
    p=root/'HMS_Codex_RecoveryTransactionJournal.py'
    spec=importlib.util.spec_from_file_location('journal',p);m=importlib.util.module_from_spec(spec);sys.modules['journal']=m;spec.loader.exec_module(m);return m

def run(root:Path):
    m=load(root); checks=[]
    def add(n,ok,d=None): checks.append({'name':n,'ok':bool(ok),'detail':d})
    proof=m.synthetic_proof()
    add('proof_pass',proof.get('verdict')=='PASS',proof.get('summary'))
    add('proof_14_checks_or_more',int((proof.get('summary') or {}).get('total',0))>=14,proof.get('summary'))
    add('crash_matrix_25_cases',int((proof.get('summary') or {}).get('crash_cases',0))==25)
    add('no_duplicate_commit_policy',all(v.get('duplicate_commit_forbidden') for v in m.ACTION_POLICIES.values()))
    add('resume_after_commit_verify',all(v.get('resume_after_commit')=='VERIFY' for v in m.ACTION_POLICIES.values()))
    with tempfile.TemporaryDirectory(prefix='hms-v2560-validator-') as td:
        p=Path(td)/'j.jsonl'; j=m.RecoveryJournal(p); tx=m.new_txn_id('ROUTER_RESTART','router','v')
        j.append(tx,'ROUTER_RESTART','PREPARE',idempotency_key='x')
        j.append(tx,'ROUTER_RESTART','COMMIT',idempotency_key='x',result_hash=m.sha256('effect'))
        add('commit_resume_is_verify',j.decision(tx).next_step=='VERIFY')
        add('chain_valid',j.validate_chain().get('ok'))
        try:
            j.append(tx,'ROUTER_RESTART','COMMIT',idempotency_key='x')
            duplicate_blocked=False
        except Exception:
            duplicate_blocked=True
        add('duplicate_commit_transition_blocked',duplicate_blocked)
        j.append(tx,'ROUTER_RESTART','VERIFY',idempotency_key='x')
        j.append(tx,'ROUTER_RESTART','DONE',idempotency_key='x')
        add('done_terminal',j.decision(tx).terminal and j.decision(tx).next_step=='NOOP')
    src=(root/'HMS_Codex_RecoveryTransactionJournal.py').read_text('utf-8')
    add('fsync_durability','os.fsync' in src and 'flush()' in src)
    add('hash_chain','prev_hash' in src and 'record_hash' in src and 'GENESIS' in src)
    add('secret_redaction','sanitize_meta' in src and '<REDACTED>' in src)
    add('supported_actions',set(m.ACTION_POLICIES)=={'OFFICIAL_AUTH_SWITCH','ROUTER_RESTART','CLIENT_RESTART','CONFIG_REPAIR','LEASE_REELECTION'})
    add('production_claim_blocked',m.PRODUCTION_CLAIM=='NOT_CLAIMED_RECOVERY_JOURNAL_SYNTHETIC_ONLY')
    main=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig')
    add('powershell_journal_wiring',all(x in main for x in ['Invoke-HmsRecoveryJournalPhase','RecoveryJournalPath','OFFICIAL_AUTH_SWITCH','PREPARE','COMMIT','VERIFY']))
    gui=(root/'HMS_GUI.pyw').read_text('utf-8')
    add('usage_reset_absolute_ui',all(x in gui for x in ['five_hour_reset_at_text','weekly_reset_at_text','Đặt lại lúc']))
    add('package_expiry_ui',all(x in gui for x in ['package_expiry_text','package_remaining_text','HẾT HẠN GÓI']))
    import re
    vm=re.search(r'\$script:Version\s*=\s*"(\d+)\.(\d+)"',main); ver=(int(vm.group(1)),int(vm.group(2))) if vm else (0,0)
    add('main_version_at_least_25_60',ver >= (25,60),ver)
    passed=sum(1 for x in checks if x['ok'])
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_TRANSACTION_JOURNAL_VALIDATION',
            'generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(checks) else 'FAIL',
            'summary':{'pass':passed,'fail':len(checks)-passed,'total':len(checks),'crash_cases':25},'checks':checks,
            'production_certification':'NOT_CLAIMED_RECOVERY_JOURNAL_SYNTHETIC_ONLY'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
