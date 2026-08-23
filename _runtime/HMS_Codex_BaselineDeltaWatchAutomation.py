#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
VERSION='25.73'; PRODUCT='HMS-AI-ROUTER'; COCKPIT_BASELINE='1.3.27'

def utcnow():return datetime.now(timezone.utc).isoformat()
def sha(v:str)->str:return hashlib.sha256(v.encode('utf-8','surrogatepass')).hexdigest()
def _tuple(v:str):
    p=str(v).lstrip('v').split('.')
    if len(p)!=3 or not all(x.isdigit() for x in p):raise ValueError('INVALID_SEMVER')
    return tuple(map(int,p))
def evaluate_observations(observations:list[dict[str,Any]],*,required_baseline:str=COCKPIT_BASELINE)->dict[str,Any]:
    rows=[];reasons=[];latest=None
    for i,o in enumerate(observations):
        version=str(o.get('version') or '')
        try:t=_tuple(version); latest=max(latest,t) if latest else t;status='CURRENT' if t==_tuple(required_baseline) else ('NEWER' if t>_tuple(required_baseline) else 'OLDER')
        except Exception:status='INVALID';t=None
        digest=str(o.get('source_digest_sha256') or '')
        row={'seq':i+1,'checkpoint':str(o.get('checkpoint') or f'checkpoint-{i+1}'),'observed_version':version.lstrip('v'),'status':status,
             'source_digest_sha256':digest if len(digest)==64 else None,'source_kind':str(o.get('source_kind') or 'PUBLIC_GITHUB_METADATA')}
        rows.append(row)
        if status=='NEWER':reasons.append('UPSTREAM_COCKPIT_NEWER_THAN_CERTIFICATION_BASELINE')
        elif status!='CURRENT':reasons.append('BASELINE_OBSERVATION_INVALID_OR_NOT_CURRENT')
        if row['source_digest_sha256'] is None:reasons.append('BASELINE_SOURCE_DIGEST_REQUIRED')
    two_checkpoints={r['checkpoint'] for r in rows}
    if not {'BEFORE_TARGET_IMPORT','BEFORE_PROMOTION_REVIEW'}.issubset(two_checkpoints):reasons.append('TWO_REQUIRED_CHECKPOINTS_MISSING')
    frozen=bool(reasons)
    queue=[]
    if 'UPSTREAM_COCKPIT_NEWER_THAN_CERTIFICATION_BASELINE' in reasons:
        newer=sorted({r['observed_version'] for r in rows if r['status']=='NEWER'})
        queue=[{'scope':'CODEX_ONLY','from_version':required_baseline,'to_version':v,'status':'PENDING_DELTA_AUDIT','automatic_merge':False} for v in newer]
    out={'product':PRODUCT,'version':VERSION,'suite':'BASELINE_DELTA_WATCH_AUTOMATION','generated_utc':utcnow(),'required_baseline':required_baseline,
         'observations':rows,'promotion_frozen':frozen,'verdict':'PROMOTION_FROZEN_BASELINE_STALE' if frozen else 'BASELINE_CURRENT_TWO_CHECKPOINTS_PASS',
         'reasons':sorted(set(reasons)),'delta_audit_queue':queue,'codex_only_scope':True,'antigravity_scope_imported':False,
         'automatic_upstream_merge':False,'automatic_production_certification':False,'production_score_promotion_eligible':False}
    out['watch_digest']=sha(json.dumps({k:v for k,v in out.items() if k not in ('generated_utc','watch_digest')},ensure_ascii=False,sort_keys=True,separators=(',',':')))
    return out

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    d1='a'*64;d2='b'*64
    ok=evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27','source_digest_sha256':d1},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.27','source_digest_sha256':d2}])
    add('two_current_checkpoints_pass',not ok['promotion_frozen'] and ok['verdict']=='BASELINE_CURRENT_TWO_CHECKPOINTS_PASS')
    stale=evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27','source_digest_sha256':d1},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.28','source_digest_sha256':d2}])
    add('newer_second_checkpoint_freezes',stale['promotion_frozen'] and stale['verdict']=='PROMOTION_FROZEN_BASELINE_STALE')
    add('delta_queue_codex_only',len(stale['delta_audit_queue'])==1 and stale['delta_audit_queue'][0]['scope']=='CODEX_ONLY' and stale['delta_audit_queue'][0]['automatic_merge'] is False)
    missing=evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27','source_digest_sha256':d1}])
    add('missing_second_checkpoint_fails_closed',missing['promotion_frozen'] and 'TWO_REQUIRED_CHECKPOINTS_MISSING' in missing['reasons'])
    bad=evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'latest','source_digest_sha256':d1},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.27','source_digest_sha256':d2}])
    add('invalid_semver_fails_closed',bad['promotion_frozen'])
    nodig=evaluate_observations([{'checkpoint':'BEFORE_TARGET_IMPORT','version':'1.3.27'},{'checkpoint':'BEFORE_PROMOTION_REVIEW','version':'1.3.27','source_digest_sha256':d2}])
    add('source_digest_required',nodig['promotion_frozen'] and 'BASELINE_SOURCE_DIGEST_REQUIRED' in nodig['reasons'])
    add('no_auto_merge_or_promotion',not stale['automatic_upstream_merge'] and not stale['automatic_production_certification'] and not stale['production_score_promotion_eligible'])
    add('scope_preserved',stale['codex_only_scope'] and not stale['antigravity_scope_imported'])
    add('digest_present',len(stale['watch_digest'])==64)
    p=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'BASELINE_DELTA_WATCH_AUTOMATION_PROOF','generated_utc':utcnow(),'verdict':'PASS' if p==len(tests) else 'FAIL','summary':{'pass':p,'fail':len(tests)-p,'total':len(tests)},'tests':tests,'production_score_promotion_eligible':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();out=synthetic_proof();txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
