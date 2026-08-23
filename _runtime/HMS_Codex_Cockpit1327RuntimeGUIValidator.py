#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
VERSION='25.74'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();s=(root/'HMS_GUI.pyw').read_text('utf-8');checks=[]
    def add(n,ok,d=None):checks.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    add('app_version_current','APP_VERSION = "25.74"' in s)
    card_start=s.find('COCKPIT v1.3.27 WINDOWS RUNTIME CERT · HMS v25.74');card_end=s.find('capture72=tk.Frame',card_start);card=s[card_start:card_end if card_end>card_start else card_start+5000]
    add('runtime_card_present',card_start>=0 and 'TARGET EVIDENCE ONLY' in card)
    add('three_proof_controls',all(x in card for x in ('"CERTIFY"','"AUDIT"','"EVIDENCE"')))
    add('certify_is_validator_only','start_v2571_runtime_cert_async' in s and 'HMS_Codex_Cockpit1327WindowsRuntimeCertificationValidator.py' in s)
    add('auditor_is_validator_only','start_v2571_promotion_auditor_async' in s and 'HMS_Codex_ProductionEvidencePromotionAuditorValidator.py' in s)
    add('evidence_is_diagnostics_only','start_v2571_runtime_diagnostics_async' in s and 'HMS_Codex_UnifiedDiagnosticsParityRuntimeValidator.py' in s)
    method_start=s.find('def _start_v2571_proof');method_end=s.find('def start_target_crash_harness_async',method_start);methods=s[method_start:method_end]
    add('no_backend_mutation_binding','self.backend(' not in methods and 'BackendAction' not in methods)
    add('no_real_effect_arm_binding','ARM' not in card.upper() and 'start_real_effect' not in card and 'TargetCampaignExecutor' not in methods)
    add('human_review_message','human score review only' in s)
    out={'version':VERSION,'suite':'COCKPIT_1327_WINDOWS_RUNTIME_GUI_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in checks),'fail':sum(x['status']=='FAIL' for x in checks),'total':len(checks)},'checks':checks};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+'\n','utf-8')
    print(text);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
