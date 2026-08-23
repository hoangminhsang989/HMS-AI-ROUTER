#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
VERSION='25.74'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();src=(root/'HMS_GUI.pyw').read_text('utf-8');c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('app_version_current','APP_VERSION = "25.74"' in src)
 add('card_present','EXTERNAL WINDOWS EVIDENCE REVIEW PACKET · HMS v25.74' in src)
 add('three_controls',all(x in src for x in ['start_v2574_review_packet_async','start_v2574_reconcile_async','start_v2574_review_diagnostics_async']))
 start=src.find('def _start_v2574_proof');end=src.find('def start_target_crash_harness_async');block=src[start:end]
 add('proof_only_subprocess',all(x in block for x in ['HMS_Codex_ExternalWindowsEvidenceReviewPacketValidator.py','HMS_Codex_BaselineDriftReconciliationValidator.py','HMS_Codex_UnifiedDiagnosticsReviewPacketValidator.py']))
 add('no_backend_mutation','self.backend(' not in block)
 add('no_arm_or_executor_call',all(x not in block for x in ['arm_token','operator_phrase','execute_one_case','TargetCampaignExecutor']))
 add('no_credential_export_control','auth.json' not in block and 'EXPORT' not in block)
 add('immutable_boundary_visible','immutable raw evidence' in src.lower() and 'new review epoch' in src.lower())
 add('no_auto_score','score-mutation=FALSE' in src)
 out={'version':VERSION,'suite':'EXTERNAL_REVIEW_PACKET_GUI_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
