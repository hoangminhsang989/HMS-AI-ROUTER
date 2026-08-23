#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION='25.72'
def load(path):
 spec=importlib.util.spec_from_file_location('hms_baseline72',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_CockpitBaselineWatchGate.py');p=m.synthetic_proof();add('proof_pass',p['verdict']=='PASS' and p['summary']['total']==8,p['summary']);add('baseline_exact',m.COCKPIT_BASELINE=='1.3.27');add('repo_exact',m.COCKPIT_REPO=='jlcodes99/cockpit-tools')
 same=m.evaluate('1.3.27');new=m.evaluate('1.3.28');old=m.evaluate('1.3.26')
 add('current_allows_campaign',same['status']=='CURRENT' and not same['promotion_frozen'])
 add('newer_freezes_promotion',new['promotion_frozen'] and new['delta_audit_required'] and new['status']=='STALE_BASELINE')
 add('older_fails_closed',old['promotion_frozen'] and old['status']=='INVALID_ROLLBACK_OR_STALE_SOURCE')
 add('codex_only_scope',same['codex_only_scope'] and not same['antigravity_scope_imported'])
 add('no_auto_promotion',same['automatic_promotion'] is False)
 out={'version':VERSION,'suite':'COCKPIT_BASELINE_WATCH_GATE_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
