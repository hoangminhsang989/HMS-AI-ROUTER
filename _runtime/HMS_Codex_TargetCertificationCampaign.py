#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
VERSION='25.67';PRODUCT='HMS-AI-ROUTER';SCHEMA_VERSION=1
EFFECTS=('auth','restart','router','lease')
WINDOWS=('AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY')
CASE_STATES={'PENDING','ARMED','RUNNING','DURABLE_UNVERIFIED','RECOVERED','ATTESTED','REJECTED','OPERATOR_REQUIRED'}
ARM_TOKEN='HMS_V2567_ARM_ONE_CAMPAIGN_CASE'
OPERATOR_PHRASE='TOI XAC NHAN CHAY MOT CASE TARGET CERTIFICATION'

def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str):
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str):return 'ref-'+sha(v)[:24]
def case_id(effect:str,window:str)->str:return effect+'::'+window

def atomic_json(path:Path,obj:Any):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush()
        try:os.fsync(f.fileno())
        except Exception:pass
    os.replace(tmp,path)

def new_campaign(*,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str,campaign_id:str|None=None)->dict[str,Any]:
    if len(manifest_sha256)!=64 or len(trust_snapshot_sha256)!=64:raise ValueError('DIGEST_REQUIRED')
    cases=[]
    for e in EFFECTS:
        for w in WINDOWS:
            cid=case_id(e,w);cases.append({'case_id':cid,'effect':e,'crash_window':w,'state':'PENDING','attempt':0,'case_nonce':None,'idempotency_key_ref':None,'last_transition_utc':utcnow(),'attestation_ref':None})
    body={'product':PRODUCT,'version':VERSION,'schema_version':SCHEMA_VERSION,'campaign_id_ref':safe_ref(campaign_id or secrets.token_hex(24)),'package_version':package_version,'manifest_sha256':manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,'generation':0,'cases':cases,'events':[],'real_effects_disarmed_by_default':True,'production_score_eligible':False,'updated_utc':utcnow()}
    return body

def _event(c:dict[str,Any],cid:str,action:str,state:str,detail_code:str=''):
    prev=(c.get('events') or [])[-1]['record_hash'] if c.get('events') else 'GENESIS';seq=len(c.get('events') or [])+1
    row={'seq':seq,'case_id':cid,'action':action,'state':state,'detail_code':detail_code,'timestamp_utc':utcnow(),'prev_hash':prev};row['record_hash']=sha(stable(row));c.setdefault('events',[]).append(row);c['generation']=int(c.get('generation') or 0)+1;c['updated_utc']=utcnow()

def _find(c:dict[str,Any],cid:str)->dict[str,Any]:
    row=next((x for x in c.get('cases') or [] if x.get('case_id')==cid),None)
    if row is None:raise ValueError('CASE_NOT_FOUND')
    return row

def validate_binding(c:dict[str,Any],*,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str)->list[str]:
    r=[]
    if c.get('package_version')!=package_version:r.append('MIXED_PACKAGE_VERSION')
    if c.get('manifest_sha256')!=manifest_sha256:r.append('MANIFEST_DIGEST_MISMATCH')
    if c.get('trust_snapshot_sha256')!=trust_snapshot_sha256:r.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
    return r

def arm_case(c:dict[str,Any],cid:str,*,arm_token:str,operator_phrase:str,idempotency_material:str)->dict[str,Any]:
    row=_find(c,cid)
    if arm_token!=ARM_TOKEN or operator_phrase!=OPERATOR_PHRASE:return {'armed':False,'reason':'EXPLICIT_CASE_ARM_REQUIRED'}
    if row.get('state')!='PENDING':return {'armed':False,'reason':'CASE_NOT_PENDING','state':row.get('state')}
    row['state']='ARMED';row['attempt']=int(row.get('attempt') or 0)+1;row['case_nonce']=secrets.token_hex(32);row['idempotency_key_ref']=safe_ref(idempotency_material);row['last_transition_utc']=utcnow();_event(c,cid,'ARM_CASE','ARMED')
    return {'armed':True,'case_id':cid,'case_nonce_ref':safe_ref(row['case_nonce']),'idempotency_key_ref':row['idempotency_key_ref']}

def mark_running(c:dict[str,Any],cid:str):
    row=_find(c,cid)
    if row.get('state')!='ARMED':raise ValueError('CASE_NOT_ARMED')
    row['state']='RUNNING';row['last_transition_utc']=utcnow();_event(c,cid,'BEGIN_REAL_EFFECT','RUNNING')

def mark_durable(c:dict[str,Any],cid:str,*,observed_idempotency_key_ref:str):
    row=_find(c,cid)
    if row.get('state')!='RUNNING':raise ValueError('CASE_NOT_RUNNING')
    if observed_idempotency_key_ref!=row.get('idempotency_key_ref'):
        row['state']='OPERATOR_REQUIRED';_event(c,cid,'DURABLE_WITNESS_MISMATCH','OPERATOR_REQUIRED','IDEMPOTENCY_WITNESS_MISMATCH');return
    row['state']='DURABLE_UNVERIFIED';row['last_transition_utc']=utcnow();_event(c,cid,'EFFECT_DURABLE','DURABLE_UNVERIFIED')

def mark_recovered(c:dict[str,Any],cid:str):
    row=_find(c,cid)
    if row.get('state')!='DURABLE_UNVERIFIED':raise ValueError('VERIFY_ONLY_REQUIRED_FROM_DURABLE')
    row['state']='RECOVERED';row['last_transition_utc']=utcnow();_event(c,cid,'VERIFY_RECOVERY','RECOVERED')

def mark_attested(c:dict[str,Any],cid:str,attestation_digest:str):
    row=_find(c,cid)
    if row.get('state')!='RECOVERED':raise ValueError('CASE_NOT_RECOVERED')
    row['state']='ATTESTED';row['attestation_ref']='att-'+str(attestation_digest)[:24];row['last_transition_utc']=utcnow();_event(c,cid,'ATTEST_CASE','ATTESTED')

def resume_plan(c:dict[str,Any])->dict[str,Any]:
    plan=[]
    for row in c.get('cases') or []:
        st=row.get('state');action={'PENDING':'REARM_REQUIRED','ARMED':'OPERATOR_REQUIRED','RUNNING':'OPERATOR_REQUIRED','DURABLE_UNVERIFIED':'VERIFY_ONLY','RECOVERED':'ATTEST_ONLY','ATTESTED':'SKIP_COMPLETE','REJECTED':'OPERATOR_REQUIRED','OPERATOR_REQUIRED':'OPERATOR_REQUIRED'}.get(st,'OPERATOR_REQUIRED')
        plan.append({'case_id':row.get('case_id'),'state':st,'resume_action':action,'silent_effect_repeat_allowed':False})
    return {'product':PRODUCT,'version':VERSION,'campaign_id_ref':c.get('campaign_id_ref'),'complete':all(x.get('state')=='ATTESTED' for x in c.get('cases') or []),'cases':plan,'real_effects_disarmed_by_default':True,'automatic_rearm':False,'production_score_eligible':False}

def campaign_summary(c:dict[str,Any])->dict[str,Any]:
    counts={s:0 for s in sorted(CASE_STATES)}
    for row in c.get('cases') or []:counts[str(row.get('state'))]=counts.get(str(row.get('state')),0)+1
    return {'product':PRODUCT,'version':VERSION,'campaign_id_ref':c.get('campaign_id_ref'),'total_cases':len(c.get('cases') or []),'counts':counts,'complete':counts.get('ATTESTED',0)==len(EFFECTS)*len(WINDOWS),'manifest_sha256':c.get('manifest_sha256'),'trust_snapshot_sha256':c.get('trust_snapshot_sha256'),'production_score_eligible':False}

def event_chain_valid(c:dict[str,Any])->bool:
    prev='GENESIS'
    for i,row in enumerate(c.get('events') or [],1):
        if row.get('seq')!=i or row.get('prev_hash')!=prev:return False
        raw={k:v for k,v in row.items() if k!='record_hash'}
        if row.get('record_hash')!=sha(stable(raw)):return False
        prev=row['record_hash']
    return True

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    c=new_campaign(package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,campaign_id='fixture')
    add('matrix_4x3_exact',len(c['cases'])==12 and {(x['effect'],x['crash_window']) for x in c['cases']}=={(e,w) for e in EFFECTS for w in WINDOWS})
    cid=case_id('auth',WINDOWS[0]);bad=arm_case(c,cid,arm_token='BAD',operator_phrase=OPERATOR_PHRASE,idempotency_material='x');add('explicit_case_arm_required',not bad['armed'])
    ok=arm_case(c,cid,arm_token=ARM_TOKEN,operator_phrase=OPERATOR_PHRASE,idempotency_material='effect-auth-1');add('one_shot_case_armed',ok['armed'])
    mark_running(c,cid);p=resume_plan(c);add('running_resume_operator_required',next(x for x in p['cases'] if x['case_id']==cid)['resume_action']=='OPERATOR_REQUIRED')
    # Simulate operator proving durable state after crash, never re-running the effect.
    mark_durable(c,cid,observed_idempotency_key_ref=_find(c,cid)['idempotency_key_ref']);p=resume_plan(c);add('durable_resume_verify_only',next(x for x in p['cases'] if x['case_id']==cid)['resume_action']=='VERIFY_ONLY')
    mark_recovered(c,cid);p=resume_plan(c);add('recovered_resume_attest_only',next(x for x in p['cases'] if x['case_id']==cid)['resume_action']=='ATTEST_ONLY')
    mark_attested(c,cid,'c'*64);p=resume_plan(c);add('attested_never_repeat',next(x for x in p['cases'] if x['case_id']==cid)['resume_action']=='SKIP_COMPLETE')
    add('pending_requires_rearm',sum(1 for x in p['cases'] if x['resume_action']=='REARM_REQUIRED')==11)
    add('binding_mixed_version_reject','MIXED_PACKAGE_VERSION' in validate_binding(c,package_version='25.66',manifest_sha256='a'*64,trust_snapshot_sha256='b'*64))
    add('binding_trust_snapshot_reject','TRUST_SNAPSHOT_DIGEST_MISMATCH' in validate_binding(c,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='d'*64))
    add('journal_hash_chain',event_chain_valid(c))
    raw=json.dumps(c,ensure_ascii=False).lower();add('no_raw_identity_or_credentials',all(x not in raw for x in ('access_token','refresh_token','password','@example.','private_key')))
    add('disarmed_default',c['real_effects_disarmed_by_default'] is True and resume_plan(c)['automatic_rearm'] is False)
    passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'RESUMABLE_TARGET_CERTIFICATION_CAMPAIGN_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'campaign':campaign_summary(c),'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','summary','resume-plan'),default='proof');ap.add_argument('--campaign');ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        if not a.campaign:raise SystemExit('--campaign required');c=json.loads(Path(a.campaign).read_text('utf-8'));out=campaign_summary(c) if a.mode=='summary' else resume_plan(c);rc=0
    if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
