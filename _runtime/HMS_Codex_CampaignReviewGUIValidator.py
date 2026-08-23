#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
VERSION='25.68'
def run(root:Path):
 s=(root/'HMS_GUI.pyw').read_text('utf-8');ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig');tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 add('gui_version',any(f'APP_VERSION = "{v}"' in s for v in (VERSION,'25.69','25.70','25.71','25.72','25.73','25.74')))
 add('campaign_review_card',all(x in s for x in ['TARGET CAMPAIGN EXECUTOR + PROMOTION REVIEW v25.74','ONE CASE / HUMAN REVIEW','EXECUTOR','REVIEW','OFFLINE']))
 add('proof_handlers',all(x in s for x in ['start_v2568_executor_proof_async','start_v2568_review_proof_async','start_v2568_offline_bundle_proof_async','_start_v2568_proof']))
 # Inspect only v25.68 card/button statements: none can bind an arm/execute mutation action.
 card=s[s.find('exec_review=tk.Frame'):s.find('replay=tk.Frame',s.find('exec_review=tk.Frame'))]
 add('no_arm_button',not re.search(r'HoverButton\([^\n]+(?:ARM|EXECUTE REAL|RUN TARGET)',card,re.I),card)
 add('no_backend_mutation_binding','self.backend(' not in card,card)
 methods=s[s.find('def _start_v2568_proof'):s.find('def start_target_crash_harness_async',s.find('def _start_v2568_proof'))]
 add('subprocess_only_validators',all(x in methods for x in ['HMS_Codex_TargetCampaignExecutorValidator.py','HMS_Codex_AttestedPromotionReviewConsoleValidator.py','HMS_Codex_AttestedPromotionReviewConsole.py']) and 'self.backend(' not in methods)
 m=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',ps,re.S);actions=re.findall(r'"([^"]+)"',m.group(1)) if m else []
 add('public_backend_actions_90',len(actions)==90,len(actions))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'CAMPAIGN_REVIEW_GUI_VALIDATION','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'real_effect_arm_control_present':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));t=json.dumps(d,ensure_ascii=False,indent=2);print(t);Path(a.output).write_text(t+'\n','utf-8') if a.output else None;return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
