#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

VERSION="25.74"

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--output'); a=ap.parse_args()
    root=Path(a.root).resolve(); gui=(root/'HMS_GUI.pyw').read_text('utf-8-sig',errors='replace'); ps=(root/'HMS_AI_ROUTER_v25.23.1.ps1').read_text('utf-8-sig',errors='replace')
    tests=[]
    def add(name,ok,detail=''): tests.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    add('gui_version_current','APP_VERSION = "25.74"' in gui)
    card_start=gui.find('COCKPIT TOOLS v1.3.27 PARITY RESET')
    card_end=gui.find('RECOVERY REPLAY v25.62',card_start)
    card=gui[card_start:card_end if card_end>card_start else card_start+3000]
    add('parity_card_present',card_start>=0 and 'HMS v25.74 · CODEX-ONLY' in card)
    add('proof_buttons_exact',all(x in card for x in [
        'HoverButton(parity1327,"PARITY",self.start_v2570_cockpit_parity_async',
        'HoverButton(parity1327,"SOURCE",self.start_v2570_cockpit_source_async',
        'HoverButton(parity1327,"AUDITOR",self.start_v2570_cockpit_auditor_async',
    ]) and 'AUTH.JSON' not in card.upper() and 'EXPORT' not in card.upper())
    method_start=gui.find('def _start_v2570_cockpit_proof')
    method_end=gui.find('def start_target_crash_harness_async',method_start)
    methods=gui[method_start:method_end if method_end>method_start else method_start+8000]
    add('proof_runner_structured_argv',all(x in methods for x in ['argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]','subprocess.run(argv']) and 'shell=True' not in methods)
    add('proof_runner_no_backend_mutation','self.backend(' not in methods and 'BackendAction' not in methods)
    add('proof_runner_no_target_arm',all(x not in methods.upper() for x in ['ARM REAL EFFECT','ENABLE-SENSITIVE-EXPORT','EXPORT OFFICIAL CODEX AUTH.JSON']))
    add('validator_mapping_exact',all(x in methods for x in ['HMS_Codex_Cockpit1327ParityResetValidator.py','HMS_Codex_Cockpit1327SourceIntegrationValidator.py','HMS_Cockpit_ParityAuditor.py']))
    m=re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction',ps,re.S); actions=re.findall(r'"([^"]+)"',m.group(1)) if m else []
    add('public_backend_action_frozen_90',len(actions)==90 and len(set(actions))==90,f'count={len(actions)}')
    add('claim_boundary_visible','production score không tự tăng' in card and 'Windows runtime certification vẫn riêng biệt' in methods)
    fail=sum(t['status']!='PASS' for t in tests)
    out={'product':'HMS-AI-ROUTER','version':VERSION,'suite':'COCKPIT_1327_GUI_SAFETY','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if fail==0 else 'FAIL','summary':{'pass':len(tests)-fail,'fail':fail,'total':len(tests)},'tests':tests,'claim_boundary':{'proof_only':True,'target_arm_exposed':False,'sensitive_auth_export_exposed':False,'production_score_changed':False}}
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+'\n',encoding='utf-8')
    print(txt); return 0 if fail==0 else 2
if __name__=='__main__': raise SystemExit(main())
