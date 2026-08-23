#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone
VERSION='25.69'
def run(root:Path):
 s=(root/'HMS_GUI.pyw').read_text('utf-8');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('app_version', any(f'APP_VERSION = "{v}"' in s for v in ('25.69','25.70','25.71','25.72','25.73','25.74')))
 add('evidence_ledger_card','EVIDENCE INBOX + PROMOTION LEDGER v25.74' in s)
 add('proof_buttons',all(x in s for x in ['"INGEST",self.start_v2569_ingest_proof_async','"LEDGER",self.start_v2569_ledger_proof_async','"INBOX",self.start_v2569_inbox_proof_async']))
 add('read_only_copy',all(x in s for x in ['read-only ingest=TRUE','dual-review=REQUIRED','score-mutation=FALSE']))
 add('proof_validator_bindings',all(x in s for x in ['HMS_Codex_TargetCertificationEvidenceIngestValidator.py','HMS_Codex_PromotionDecisionLedgerValidator.py','HMS_Codex_UnifiedDiagnosticsEvidenceLedgerValidator.py']))
 # No v25.69 proof method may call backend mutation or real-effect arm functions.
 m=re.search(r'def _start_v2569_proof\(.*?\n    def start_target_crash_harness_async',s,re.S);body=m.group(0) if m else ''
 add('no_backend_mutation_binding','self.backend(' not in body and 'arm_real' not in body.lower() and 'execute_one_case' not in body)
 add('real_effect_controls_still_preflight_lab',all(x in s for x in ['"PREFLIGHT",self.start_real_effect_preflight_async','"LAB CRASH",self.start_target_crash_harness_async']))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'EVIDENCE_INBOX_GUI_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
