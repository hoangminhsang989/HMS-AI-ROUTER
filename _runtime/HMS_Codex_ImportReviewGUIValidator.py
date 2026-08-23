#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
VERSION='25.73'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();src=(root/'HMS_GUI.pyw').read_text('utf-8');c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('app_version_current','APP_VERSION = "25.74"' in src)
 add('card_present','WINDOWS EVIDENCE IMPORT REVIEW · HMS v25.74' in src)
 add('three_controls',all(x in src for x in ['start_v2573_import_review_async','start_v2573_delta_watch_async','start_v2573_import_diagnostics_async']))
 block=src[src.find('def _start_v2573_proof'):src.find('def start_target_crash_harness_async')]
 add('proof_only_subprocess',all(x in block for x in ['HMS_Codex_WindowsTargetEvidenceImportReviewValidator.py','HMS_Codex_BaselineDeltaWatchAutomationValidator.py','HMS_Codex_UnifiedDiagnosticsImportReviewValidator.py']))
 add('no_backend_mutation','self.backend(' not in block)
 add('no_arm_or_executor_call',all(x not in block for x in ['arm_token','operator_phrase','execute_one_case','TargetCampaignExecutor']))
 add('no_auto_score','score-mutation=FALSE' in src and 'dual-review=REQUIRED' in src)
 add('baseline_visible','baseline 1.3.27 ×2' in src)
 add('no_credential_export_control','auth.json' not in block and 'EXPORT' not in block)
 out={'version':VERSION,'suite':'IMPORT_REVIEW_GUI_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
