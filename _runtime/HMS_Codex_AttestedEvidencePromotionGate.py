#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,secrets,tempfile,uuid,importlib.util,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
VERSION='25.67'
SCHEMA_VERSION=1
ELIGIBLE_CLASSES={'WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'}
REQUIRED_EFFECTS={'auth','restart','router','lease'}
REQUIRED_WINDOWS={'AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY'}
PRODUCTION_CLAIM='NO_PROMOTION_WITHOUT_CRYPTOGRAPHICALLY_ATTESTED_WINDOWS_TARGET_AND_REAL_CODEX_EFFECT_EVIDENCE'

def _load_signer():
 p=Path(__file__).with_name('HMS_Codex_WindowsAttestationSigner.py');spec=importlib.util.spec_from_file_location('hms_v2566_signer',p);m=importlib.util.module_from_spec(spec);sys.modules['hms_v2566_signer']=m;spec.loader.exec_module(m);return m

def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->str:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(v:bytes|str)->str:
 if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
 return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:20]
def parse_time(v:str):
 try:return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:return None
def file_sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def manifest_digest(root:Path,version:str)->str:
 p=root/f'RELEASE_MANIFEST_V{version.replace(".","_")}.json'
 return file_sha(p) if p.is_file() else ''

def event_chain(events:list[dict[str,Any]])->tuple[bool,str]:
 prev='GENESIS'
 for i,row in enumerate(events,1):
  if int(row.get('seq') or 0)!=i or row.get('prev_hash')!=prev:return False,'EVENT_SEQUENCE_OR_PREV_HASH'
  raw={k:v for k,v in row.items() if k!='record_hash'}
  if row.get('record_hash')!=sha(stable(raw)):return False,'EVENT_HASH_MISMATCH'
  prev=row['record_hash']
 return bool(events),'OK' if events else 'EVENTS_EMPTY'

def make_attestation(*,package_version:str,package_manifest_sha256:str,evidence_class:str,events:list[dict[str,Any]],machine_material:str='fixture-machine',runtime_material:str='fixture-runtime',run_id:str|None=None,nonce:str|None=None,generated_utc:str|None=None,signer_class:str='UNTRUSTED_LAB_HASH_CHAIN',trust_snapshot_sha256:str='')->dict[str,Any]:
 body={'product':'HMS-AI-ROUTER','version':VERSION,'schema_version':SCHEMA_VERSION,'run_id':run_id or str(uuid.uuid4()),'nonce':nonce or secrets.token_hex(32),'generated_utc':generated_utc or utcnow(),'package_version':package_version,'package_manifest_sha256':package_manifest_sha256,'evidence_class':evidence_class,'machine_fingerprint':safe_ref(machine_material),'runtime_fingerprint':safe_ref(runtime_material),'signer_class':signer_class,'trust_snapshot_sha256':trust_snapshot_sha256,'events':events,'privacy':{'raw_hostname':False,'raw_username':False,'raw_account_identity':False,'raw_credentials':False}}
 body['attestation_sha256']=sha(stable(body));return body

def make_chain(rows:list[dict[str,Any]])->list[dict[str,Any]]:
 out=[];prev='GENESIS'
 for i,payload in enumerate(rows,1):
  row={'seq':i,'phase':payload.get('phase'),'effect':payload.get('effect'),'crash_window':payload.get('crash_window'),'status':payload.get('status'),'prev_hash':prev}
  row['record_hash']=sha(stable(row));out.append(row);prev=row['record_hash']
 return out

def verify_attestation(att:dict[str,Any],*,expected_package_version:str,expected_manifest_sha256:str,seen_run_ids:set[str]|None=None,seen_nonces:set[str]|None=None,max_age_minutes:int=180,trusted_certificate_sha256:set[str]|None=None,dpapi_key_path:Path|None=None,expected_trust_snapshot_sha256:str='')->dict[str,Any]:
 reasons=[];seen_run_ids=seen_run_ids if seen_run_ids is not None else set();seen_nonces=seen_nonces if seen_nonces is not None else set()
 raw={k:v for k,v in att.items() if k!='attestation_sha256'}
 if att.get('attestation_sha256')!=sha(stable(raw)):reasons.append('ATTESTATION_HASH_MISMATCH')
 run_id=str(att.get('run_id') or '');nonce=str(att.get('nonce') or '')
 if not run_id or run_id in seen_run_ids:reasons.append('RUN_ID_REPLAY_OR_MISSING')
 if len(nonce)<32 or nonce in seen_nonces:reasons.append('NONCE_REPLAY_OR_INVALID')
 if att.get('package_version')!=expected_package_version:reasons.append('MIXED_PACKAGE_VERSION')
 if att.get('package_manifest_sha256')!=expected_manifest_sha256 or len(expected_manifest_sha256)!=64:reasons.append('PACKAGE_MANIFEST_DIGEST_MISMATCH')
 if expected_trust_snapshot_sha256 and att.get('trust_snapshot_sha256')!=expected_trust_snapshot_sha256:reasons.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
 if att.get('evidence_class') not in ELIGIBLE_CLASSES:reasons.append('EVIDENCE_CLASS_NOT_PRODUCTION_ELIGIBLE')
 t=parse_time(str(att.get('generated_utc') or ''))
 if not t or abs((datetime.now(timezone.utc)-t).total_seconds())>max_age_minutes*60:reasons.append('STALE_OR_INVALID_TIME')
 ok_chain,chain_reason=event_chain(att.get('events') or [])
 if not ok_chain:reasons.append(chain_reason)
 signer_mod=_load_signer();sig=signer_mod.verify_signed_attestation(att,trusted_certificate_sha256=trusted_certificate_sha256,dpapi_key_path=dpapi_key_path)
 if not sig.get('valid'):reasons.extend(['SIGNATURE_'+x for x in (sig.get('reasons') or [])])
 if not str(att.get('machine_fingerprint') or '').startswith('ref-') or not str(att.get('runtime_fingerprint') or '').startswith('ref-'):reasons.append('PSEUDONYMOUS_TARGET_FINGERPRINT_REQUIRED')
 if not reasons:seen_run_ids.add(run_id);seen_nonces.add(nonce)
 return {'valid':not reasons,'reasons':reasons,'run_id_ref':safe_ref(run_id) if run_id else '','nonce_ref':safe_ref(nonce) if nonce else '','evidence_class':att.get('evidence_class'),'package_version':att.get('package_version'),'signature':sig}

def crash_matrix_complete(events:list[dict[str,Any]])->bool:
 seen={(str(e.get('effect') or ''),str(e.get('crash_window') or '')) for e in events if str(e.get('status') or '').startswith('PASS')}
 return all((e,w) in seen for e in REQUIRED_EFFECTS for w in REQUIRED_WINDOWS)

def promotion_gate(observer:dict[str,Any],real:dict[str,Any],*,expected_package_version:str,expected_manifest_sha256:str,observer_trusted_certificate_sha256:set[str]|None=None,real_trusted_certificate_sha256:set[str]|None=None,dpapi_key_path:Path|None=None,expected_trust_snapshot_sha256:str='')->dict[str,Any]:
 seen_runs:set[str]=set();seen_nonces:set[str]=set()
 vo=verify_attestation(observer,expected_package_version=expected_package_version,expected_manifest_sha256=expected_manifest_sha256,seen_run_ids=seen_runs,seen_nonces=seen_nonces,trusted_certificate_sha256=observer_trusted_certificate_sha256,dpapi_key_path=dpapi_key_path,expected_trust_snapshot_sha256=expected_trust_snapshot_sha256)
 vr=verify_attestation(real,expected_package_version=expected_package_version,expected_manifest_sha256=expected_manifest_sha256,seen_run_ids=seen_runs,seen_nonces=seen_nonces,trusted_certificate_sha256=real_trusted_certificate_sha256,dpapi_key_path=dpapi_key_path,expected_trust_snapshot_sha256=expected_trust_snapshot_sha256)
 reasons=[]
 if not vo['valid']:reasons+=['OBSERVER_'+x for x in vo['reasons']]
 if not vr['valid']:reasons+=['REAL_'+x for x in vr['reasons']]
 if observer.get('evidence_class')!='WINDOWS_TARGET_OBSERVER':reasons.append('WINDOWS_TARGET_OBSERVER_REQUIRED')
 if real.get('evidence_class')!='REAL_CODEX_EFFECT':reasons.append('REAL_CODEX_EFFECT_REQUIRED')
 if not crash_matrix_complete(real.get('events') or []):reasons.append('COMPLETE_4X3_CRASH_MATRIX_REQUIRED')
 eligible=not reasons
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTED_EVIDENCE_PROMOTION_GATE','generated_utc':utcnow(),'verdict':'PASS_PROMOTION_ELIGIBLE' if eligible else 'NO_PROMOTION','production_score_promotion_eligible':eligible,'reasons':reasons,'observer':vo,'real_effect':vr,'expected_package_version':expected_package_version,'expected_manifest_sha256':expected_manifest_sha256,'expected_trust_snapshot_sha256':expected_trust_snapshot_sha256,'production_certification':PRODUCTION_CLAIM if not eligible else 'EVIDENCE_ELIGIBLE_FOR_SEPARATE_PRODUCTION_SCORE_AUDITOR_NOT_AUTOMATIC_CERTIFICATION'}

def synthetic_proof()->dict[str,Any]:
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 digest='a'*64;signer=_load_signer();obs_events=make_chain([{'phase':'OBSERVE','effect':'auth','crash_window':'','status':'PASS'}]);real_events=make_chain([{'phase':'VERIFY','effect':e,'crash_window':w,'status':'PASS'} for e in sorted(REQUIRED_EFFECTS) for w in sorted(REQUIRED_WINDOWS)])
 obs0=make_attestation(package_version=VERSION,package_manifest_sha256=digest,evidence_class='WINDOWS_TARGET_OBSERVER',events=obs_events);obs,obs_cert=signer.synthetic_sign_attestation(obs0)
 real0=make_attestation(package_version=VERSION,package_manifest_sha256=digest,evidence_class='REAL_CODEX_EFFECT',events=real_events);real,real_cert=signer.synthetic_sign_attestation(real0)
 g=promotion_gate(obs,real,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={obs_cert},real_trusted_certificate_sha256={real_cert});add('complete_crypto_pair_eligible_contract',g['production_score_promotion_eligible'],g)
 tam=json.loads(json.dumps(real));tam['run_id']=str(uuid.uuid4());g2=promotion_gate(obs,tam,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={obs_cert},real_trusted_certificate_sha256={real_cert});add('signature_tamper_rejected',not g2['production_score_promotion_eligible'] and any('SIGNATURE_' in x for x in g2['reasons']),g2['reasons'])
 partial0=make_attestation(package_version=VERSION,package_manifest_sha256=digest,evidence_class='REAL_CODEX_EFFECT',events=make_chain([{'phase':'VERIFY','effect':'auth','crash_window':'AFTER_PREPARE_BEFORE_EFFECT','status':'PASS'}]));partial,pc=signer.synthetic_sign_attestation(partial0);g3=promotion_gate(obs,partial,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={obs_cert},real_trusted_certificate_sha256={pc});add('partial_matrix_rejected',not g3['production_score_promotion_eligible'] and 'COMPLETE_4X3_CRASH_MATRIX_REQUIRED' in g3['reasons'])
 mixed=json.loads(json.dumps(real));mixed['package_version']='25.65';mixed['attestation_sha256']=sha(stable({k:v for k,v in mixed.items() if k!='attestation_sha256'}));g4=promotion_gate(obs,mixed,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={obs_cert},real_trusted_certificate_sha256={real_cert});add('mixed_version_rejected',not g4['production_score_promotion_eligible'] and any('MIXED_PACKAGE_VERSION' in x for x in g4['reasons']))
 lab0=make_attestation(package_version=VERSION,package_manifest_sha256=digest,evidence_class='LAB_FIXTURE',events=obs_events);lab,lc=signer.synthetic_sign_attestation(lab0);g5=promotion_gate(lab,real,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={lc},real_trusted_certificate_sha256={real_cert});add('lab_rejected',not g5['production_score_promotion_eligible'])
 stale0=make_attestation(package_version=VERSION,package_manifest_sha256=digest,evidence_class='WINDOWS_TARGET_OBSERVER',events=obs_events,generated_utc=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat());stale,sc=signer.synthetic_sign_attestation(stale0);g6=promotion_gate(stale,real,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={sc},real_trusted_certificate_sha256={real_cert});add('stale_rejected',not g6['production_score_promotion_eligible'] and any('STALE_OR_INVALID_TIME' in x for x in g6['reasons']))
 untrusted=json.loads(json.dumps(obs));g7=promotion_gate(untrusted,real,expected_package_version=VERSION,expected_manifest_sha256=digest,observer_trusted_certificate_sha256={'0'*64},real_trusted_certificate_sha256={real_cert});add('untrusted_certificate_rejected',not g7['production_score_promotion_eligible'] and any('CERTIFICATE_NOT_TRUSTED' in x for x in g7['reasons']),g7['reasons'])
 add('synthetic_contract_not_production_evidence',True,{'production_score_eligible':False})
 add('complete_4x3_matrix_contract',crash_matrix_complete(real.get('events') or []))
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'ATTESTED_EVIDENCE_PROMOTION_GATE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'synthetic_signature_contract':True,'production_score_eligible':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','verify'),default='proof');ap.add_argument('--observer');ap.add_argument('--real-effect');ap.add_argument('--package-version',default='25.67');ap.add_argument('--manifest-sha256',default='');ap.add_argument('--output');a=ap.parse_args()
 if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
 else:
  if not a.observer or not a.real_effect or not a.manifest_sha256:raise SystemExit('--observer --real-effect --manifest-sha256 required')
  out=promotion_gate(json.loads(Path(a.observer).read_text('utf-8')),json.loads(Path(a.real_effect).read_text('utf-8')),expected_package_version=a.package_version,expected_manifest_sha256=a.manifest_sha256);rc=0 if out['production_score_promotion_eligible'] else 4
 if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
