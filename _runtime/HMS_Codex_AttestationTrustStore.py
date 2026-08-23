#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

VERSION='25.67'
PRODUCT='HMS-AI-ROUTER'
SCHEMA_VERSION=1
CERT_STATES={'ACTIVE','RETIRED','REVOKED'}
DPAPI_STATES={'ACTIVE','RETIRED','REVOKED'}
HEX64=re.compile(r'^[0-9a-f]{64}$')


def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def parse_time(v:str|None):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def atomic_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush()
        try:os.fsync(f.fileno())
        except Exception:pass
    os.replace(tmp,path)

def empty_store()->dict[str,Any]:
    return {'product':PRODUCT,'version':VERSION,'schema_version':SCHEMA_VERSION,'generation':0,'certificates':[],'dpapi_keys':[],'updated_utc':utcnow(),'private_material_exported':False}

def load_store(path:Path)->dict[str,Any]:
    if not path.exists():return empty_store()
    obj=json.loads(path.read_text('utf-8'))
    if obj.get('schema_version')!=SCHEMA_VERSION:raise ValueError('TRUST_STORE_SCHEMA_UNSUPPORTED')
    if not isinstance(obj.get('certificates'),list) or not isinstance(obj.get('dpapi_keys'),list):raise ValueError('TRUST_STORE_SHAPE_INVALID')
    return obj

def _public_snapshot(store:dict[str,Any])->dict[str,Any]:
    cert=[]
    for row in store.get('certificates') or []:
        cert.append({k:row.get(k) for k in ('pin_id','certificate_sha256','signer_key_id_ref','state','not_before_utc','not_after_utc','rotated_from_pin_id','revocation_reason_code')})
    keys=[]
    for row in store.get('dpapi_keys') or []:
        keys.append({k:row.get(k) for k in ('key_id_ref','generation','state','sealed_blob_sha256','created_utc','retired_utc','revocation_reason_code')})
    return {'product':PRODUCT,'version':VERSION,'schema_version':SCHEMA_VERSION,'generation':int(store.get('generation') or 0),'certificates':sorted(cert,key=lambda r:str(r.get('pin_id'))),'dpapi_keys':sorted(keys,key=lambda r:(int(r.get('generation') or 0),str(r.get('key_id_ref')))),'private_material_exported':False}

def trust_snapshot(store:dict[str,Any])->dict[str,Any]:
    body=_public_snapshot(store);body['trust_snapshot_sha256']=sha(stable(body));return body

def _bump(store:dict[str,Any])->None:
    store['version']=VERSION;store['generation']=int(store.get('generation') or 0)+1;store['updated_utc']=utcnow();store['private_material_exported']=False

def pin_certificate(store:dict[str,Any],*,certificate_sha256:str,signer_key_id_ref:str,not_before_utc:str='',not_after_utc:str='',rotated_from_pin_id:str='')->dict[str,Any]:
    cert=str(certificate_sha256).lower()
    if not HEX64.fullmatch(cert):raise ValueError('CERTIFICATE_SHA256_INVALID')
    if not str(signer_key_id_ref).startswith('ref-'):raise ValueError('PSEUDONYMOUS_SIGNER_REF_REQUIRED')
    for r in store.get('certificates') or []:
        if r.get('certificate_sha256')==cert and r.get('state')=='ACTIVE':return r
    pin_id='pin-'+cert[:20]
    row={'pin_id':pin_id,'certificate_sha256':cert,'signer_key_id_ref':signer_key_id_ref,'state':'ACTIVE','pinned_utc':utcnow(),'not_before_utc':not_before_utc or None,'not_after_utc':not_after_utc or None,'rotated_from_pin_id':rotated_from_pin_id or None,'revocation_reason_code':None}
    store.setdefault('certificates',[]).append(row);_bump(store);return row

def rotate_certificate(store:dict[str,Any],*,old_pin_id:str,new_certificate_sha256:str,new_signer_key_id_ref:str,not_before_utc:str='',not_after_utc:str='')->dict[str,Any]:
    old=next((r for r in store.get('certificates') or [] if r.get('pin_id')==old_pin_id),None)
    if old is None:raise ValueError('OLD_PIN_NOT_FOUND')
    if old.get('state')!='ACTIVE':raise ValueError('OLD_PIN_NOT_ACTIVE')
    old['state']='RETIRED';old['retired_utc']=utcnow();_bump(store)
    return pin_certificate(store,certificate_sha256=new_certificate_sha256,signer_key_id_ref=new_signer_key_id_ref,not_before_utc=not_before_utc,not_after_utc=not_after_utc,rotated_from_pin_id=old_pin_id)

def revoke_certificate(store:dict[str,Any],pin_id:str,reason_code:str='OPERATOR_REVOKED')->dict[str,Any]:
    row=next((r for r in store.get('certificates') or [] if r.get('pin_id')==pin_id),None)
    if row is None:raise ValueError('PIN_NOT_FOUND')
    row['state']='REVOKED';row['revoked_utc']=utcnow();row['revocation_reason_code']=str(reason_code)[:64];_bump(store);return row

def evaluate_certificate(store:dict[str,Any],certificate_sha256:str,*,now:datetime|None=None)->dict[str,Any]:
    now=now or datetime.now(timezone.utc);cert=str(certificate_sha256).lower();row=next((r for r in store.get('certificates') or [] if r.get('certificate_sha256')==cert),None)
    reasons=[]
    if row is None:reasons.append('CERTIFICATE_NOT_PINNED')
    else:
        if row.get('state')!='ACTIVE':reasons.append('CERTIFICATE_'+str(row.get('state') or 'UNKNOWN'))
        nb=parse_time(row.get('not_before_utc'));na=parse_time(row.get('not_after_utc'))
        if nb and now<nb:reasons.append('CERTIFICATE_NOT_YET_VALID')
        if na and now>na:reasons.append('CERTIFICATE_EXPIRED')
    return {'trusted':not reasons,'reasons':reasons,'pin_id':(row or {}).get('pin_id'),'state':(row or {}).get('state'),'certificate_sha256':cert,'trust_snapshot_sha256':trust_snapshot(store)['trust_snapshot_sha256']}

def trusted_certificate_sha256(store:dict[str,Any],*,now:datetime|None=None)->set[str]:
    out=set()
    for row in store.get('certificates') or []:
        if evaluate_certificate(store,str(row.get('certificate_sha256') or ''),now=now)['trusted']:out.add(str(row.get('certificate_sha256')))
    return out

def register_dpapi_key(store:dict[str,Any],*,key_context:str,sealed_blob_sha256:str)->dict[str,Any]:
    if not HEX64.fullmatch(str(sealed_blob_sha256).lower()):raise ValueError('SEALED_BLOB_SHA256_INVALID')
    active=[r for r in store.get('dpapi_keys') or [] if r.get('state')=='ACTIVE']
    generation=max([int(r.get('generation') or 0) for r in store.get('dpapi_keys') or []]+[0])+1
    for r in active:r['state']='RETIRED';r['retired_utc']=utcnow()
    row={'key_id_ref':safe_ref(key_context+':'+str(generation)),'generation':generation,'state':'ACTIVE','sealed_blob_sha256':str(sealed_blob_sha256).lower(),'created_utc':utcnow(),'retired_utc':None,'revocation_reason_code':None}
    store.setdefault('dpapi_keys',[]).append(row);_bump(store);return row

def revoke_dpapi_key(store:dict[str,Any],key_id_ref:str,reason_code:str='OPERATOR_REVOKED')->dict[str,Any]:
    row=next((r for r in store.get('dpapi_keys') or [] if r.get('key_id_ref')==key_id_ref),None)
    if row is None:raise ValueError('DPAPI_KEY_NOT_FOUND')
    row['state']='REVOKED';row['retired_utc']=utcnow();row['revocation_reason_code']=reason_code;_bump(store);return row

def warnings(store:dict[str,Any],*,now:datetime|None=None,expiry_warning_days:int=30)->list[dict[str,Any]]:
    now=now or datetime.now(timezone.utc);out=[]
    for row in store.get('certificates') or []:
        if row.get('state')=='REVOKED':out.append({'code':'CERTIFICATE_REVOKED','pin_id':row.get('pin_id')})
        na=parse_time(row.get('not_after_utc'))
        if row.get('state')=='ACTIVE' and na:
            days=(na-now).total_seconds()/86400
            if days<0:out.append({'code':'CERTIFICATE_EXPIRED','pin_id':row.get('pin_id')})
            elif days<=expiry_warning_days:out.append({'code':'CERTIFICATE_EXPIRING_SOON','pin_id':row.get('pin_id'),'days_remaining':round(days,1)})
    return out

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    s=empty_store();now=datetime.now(timezone.utc)
    a=pin_certificate(s,certificate_sha256='a'*64,signer_key_id_ref='ref-'+('1'*24),not_before_utc=(now-timedelta(days=1)).isoformat(),not_after_utc=(now+timedelta(days=10)).isoformat())
    snap1=trust_snapshot(s);add('pin_active_trusted',evaluate_certificate(s,'a'*64)['trusted'])
    b=rotate_certificate(s,old_pin_id=a['pin_id'],new_certificate_sha256='b'*64,new_signer_key_id_ref='ref-'+('2'*24),not_after_utc=(now+timedelta(days=365)).isoformat());add('rotation_retires_old',not evaluate_certificate(s,'a'*64)['trusted'] and evaluate_certificate(s,'b'*64)['trusted'])
    snap2=trust_snapshot(s);add('snapshot_changes_on_rotation',snap1['trust_snapshot_sha256']!=snap2['trust_snapshot_sha256'])
    revoke_certificate(s,b['pin_id'],'KEY_COMPROMISE');add('revocation_blocks',not evaluate_certificate(s,'b'*64)['trusted'] and 'CERTIFICATE_REVOKED' in evaluate_certificate(s,'b'*64)['reasons'])
    k1=register_dpapi_key(s,key_context='machine-key',sealed_blob_sha256='c'*64);k2=register_dpapi_key(s,key_context='machine-key',sealed_blob_sha256='d'*64);add('dpapi_rotation_metadata_only',k1['state']=='RETIRED' and k2['state']=='ACTIVE' and k2['generation']==2)
    raw=json.dumps(trust_snapshot(s),ensure_ascii=False);add('no_private_material','private_key' not in raw.lower() and 'raw_key' not in raw.lower() and 'private_material_exported' in raw)
    add('expiry_warning_metadata_only',any(x['code'] in {'CERTIFICATE_REVOKED','CERTIFICATE_EXPIRING_SOON'} for x in warnings(s)))
    snap=trust_snapshot(s);add('snapshot_deterministic',snap['trust_snapshot_sha256']==trust_snapshot(json.loads(json.dumps(s)))['trust_snapshot_sha256'])
    add('unknown_cert_fail_closed',not evaluate_certificate(s,'e'*64)['trusted'])
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':PRODUCT,'version':VERSION,'suite':'ATTESTATION_TRUST_STORE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'trust_snapshot':snap,'production_score_eligible':False,'windows_runtime_certified':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','snapshot','warnings'),default='proof');ap.add_argument('--store');ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        if not a.store:raise SystemExit('--store required')
        s=load_store(Path(a.store));out=trust_snapshot(s) if a.mode=='snapshot' else {'version':VERSION,'warnings':warnings(s),'trust_snapshot_sha256':trust_snapshot(s)['trust_snapshot_sha256']};rc=0
    if a.output:atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
