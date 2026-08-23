#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
VERSION='25.72'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();s=(root/'HMS_GUI.pyw').read_text('utf-8');c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('app_version_current','APP_VERSION = "25.74"' in s)
 start=s.find('WINDOWS TARGET EVIDENCE CAPTURE KIT · HMS v25.72');end=s.find('replay=tk.Frame',start);card=s[start:end if end>start else start+5000]
 add('card_present',start>=0 and all(x in card for x in ['CAPTURE KIT','BASELINE','PRIVACY','DISARMED']))
 add('proof_only_buttons',all(x in card for x in ['start_v2572_capture_kit_async','start_v2572_baseline_watch_async','start_v2572_capture_privacy_async']))
 methods=s[s.find('def _start_v2572_proof'):s.find('def start_target_crash_harness_async')]
 add('no_backend_mutation_binding','self.backend(' not in methods and 'BackendAction' not in methods)
 add('no_real_effect_arm_binding',all(x not in methods for x in ['EXECUTOR_ARM_TOKEN','operator_phrase','HMS_V2568_ENABLE_TARGET_CASE','execute_one_case(']))
 add('uses_validator_subprocess','subprocess.run(argv' in methods and '--root' in methods and '--output' in methods)
 add('baseline_visible','baseline=1.3.27' in methods and 'production score giữ nguyên' in methods)
 add('no_credential_export_button',all(x not in card for x in ['AUTH.JSON','EXPORT AUTH','TOKEN EXPORT']))
 add('public_actions_not_extended','self.backend(' not in card)
 out={'version':VERSION,'suite':'TARGET_EVIDENCE_CAPTURE_GUI_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
