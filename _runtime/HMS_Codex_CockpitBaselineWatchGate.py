#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.72'
COCKPIT_BASELINE='1.3.27'
COCKPIT_REPO='jlcodes99/cockpit-tools'
SEMVER=re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$')


def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def sha(v:str)->str:return hashlib.sha256(v.encode('utf-8','surrogatepass')).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def parse_version(v:str)->tuple[int,int,int]:
    m=SEMVER.fullmatch(str(v or '').strip())
    if not m: raise ValueError('INVALID_SEMVER')
    return tuple(map(int,m.groups()))

def evaluate(observed_version:str,*,required_baseline:str=COCKPIT_BASELINE,source_kind:str='PUBLIC_GITHUB_RELEASE',source_locator:str='')->dict[str,Any]:
    reasons=[]
    try: obs=parse_version(observed_version); req=parse_version(required_baseline)
    except ValueError:
        return {'product':'HMS-AI-ROUTER','version':VERSION,'gate':'COCKPIT_BASELINE_WATCH','generated_utc':utcnow(),'status':'INVALID','promotion_frozen':True,'delta_audit_required':True,'reasons':['INVALID_BASELINE_VERSION'],'observed_version':str(observed_version),'required_baseline':required_baseline,'source_kind':source_kind,'source_ref':safe_ref(source_locator) if source_locator else None,'codex_only_scope':True,'automatic_promotion':False}
    if obs>req:
        status='STALE_BASELINE';reasons.append('UPSTREAM_COCKPIT_NEWER_THAN_CERTIFICATION_BASELINE')
    elif obs<req:
        status='INVALID_ROLLBACK_OR_STALE_SOURCE';reasons.append('OBSERVED_COCKPIT_BELOW_REQUIRED_BASELINE')
    else: status='CURRENT'
    freeze=status!='CURRENT'
    return {'product':'HMS-AI-ROUTER','version':VERSION,'gate':'COCKPIT_BASELINE_WATCH','generated_utc':utcnow(),'status':status,'promotion_frozen':freeze,'delta_audit_required':freeze,'reasons':reasons,'observed_version':str(observed_version).lstrip('v'),'required_baseline':required_baseline,'source_kind':source_kind,'source_ref':safe_ref(source_locator) if source_locator else None,'codex_only_scope':True,'antigravity_scope_imported':False,'automatic_promotion':False}

def synthetic_proof()->dict[str,Any]:
    t=[]
    def add(n,ok,d=None):t.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    same=evaluate('1.3.27',source_locator='https://github.com/jlcodes99/cockpit-tools/releases/tag/v1.3.27')
    add('current_baseline_passes',same['status']=='CURRENT' and not same['promotion_frozen'])
    newer=evaluate('1.3.28')
    add('newer_upstream_freezes_promotion',newer['status']=='STALE_BASELINE' and newer['promotion_frozen'] and newer['delta_audit_required'])
    older=evaluate('1.3.26')
    add('older_source_rejected',older['promotion_frozen'] and 'OBSERVED_COCKPIT_BELOW_REQUIRED_BASELINE' in older['reasons'])
    invalid=evaluate('latest')
    add('invalid_version_fails_closed',invalid['status']=='INVALID' and invalid['promotion_frozen'])
    add('codex_only_scope_preserved',same['codex_only_scope'] and not same['antigravity_scope_imported'])
    add('source_locator_pseudonymous',str(same.get('source_ref','')).startswith('ref-') and 'github' not in str(same.get('source_ref','')))
    add('no_automatic_promotion',same['automatic_promotion'] is False)
    add('semver_not_lexical',parse_version('1.3.10')>parse_version('1.3.9'))
    p=sum(x['status']=='PASS' for x in t)
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'COCKPIT_BASELINE_WATCH_PROOF','generated_utc':utcnow(),'verdict':'PASS' if p==len(t) else 'FAIL','summary':{'pass':p,'fail':len(t)-p,'total':len(t)},'tests':t,'promotion_score_eligible':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--observed-version');ap.add_argument('--source-kind',default='PUBLIC_GITHUB_RELEASE');ap.add_argument('--source-locator',default='');ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args()
    if a.proof:out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        if not a.observed_version:raise SystemExit('--observed-version required')
        out=evaluate(a.observed_version,source_kind=a.source_kind,source_locator=a.source_locator);rc=0 if out['status']=='CURRENT' else 3
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return rc
if __name__=='__main__':raise SystemExit(main())
