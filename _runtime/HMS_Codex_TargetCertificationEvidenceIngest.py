#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
VERSION='25.69'; PRODUCT='HMS-AI-ROUTER'
EFFECTS=('auth','restart','router','lease'); WINDOWS=('AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY')
EXPECTED={(e,w) for e in EFFECTS for w in WINDOWS}; HEX64=re.compile(r'^[0-9a-f]{64}$')
FORBIDDEN_KEYS=re.compile(r'(access[_-]?token|refresh[_-]?token|password|private[_-]?(key|material)|authorization|credential|account[_-]?(email|identity)|hostname|command[_-]?line|environment)',re.I)

def utcnow(): return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str):
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str):return 'ref-'+sha(v)[:24]
def _time(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def _load_signer():
    p=Path(__file__).with_name('HMS_Codex_WindowsAttestationSigner.py');s=importlib.util.spec_from_file_location('signer2569',p);m=importlib.util.module_from_spec(s);sys.modules['signer2569']=m;s.loader.exec_module(m);return m

def _has_forbidden_key(obj:Any)->bool:
    if isinstance(obj,dict):
        for k,v in obj.items():
            ks=str(k)
            if ks in {'private_material_exported','contains_private_material'}:
                continue
            if FORBIDDEN_KEYS.search(ks) or _has_forbidden_key(v):
                return True
        return False
    if isinstance(obj,list):return any(_has_forbidden_key(x) for x in obj)
    return False

def _report_digest(att:dict[str,Any])->str:return sha(stable(att))

def verify_report(att:dict[str,Any],*,expected_package_version:str,expected_manifest_sha256:str,expected_trust_snapshot_sha256:str,trusted_certificate_sha256:set[str],seen_nonces:set[str],seen_run_ids:set[str],seen_report_digests:set[str],max_age_hours:int=24)->dict[str,Any]:
    reasons=[]
    if _has_forbidden_key(att):reasons.append('FORBIDDEN_PRIVATE_OR_IDENTITY_FIELD')
    effect=str(att.get('effect') or '');window=str(att.get('crash_window') or '');case_id=str(att.get('case_id') or '');expected_case=f'{effect}::{window}'
    if (effect,window) not in EXPECTED or case_id!=expected_case:reasons.append('CASE_ID_OR_MATRIX_INVALID')
    if att.get('package_version')!=expected_package_version:reasons.append('MIXED_PACKAGE_VERSION')
    if att.get('package_manifest_sha256')!=expected_manifest_sha256 or not HEX64.fullmatch(str(expected_manifest_sha256).lower()):reasons.append('MANIFEST_DIGEST_MISMATCH')
    if att.get('trust_snapshot_sha256')!=expected_trust_snapshot_sha256 or not HEX64.fullmatch(str(expected_trust_snapshot_sha256).lower()):reasons.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
    run_id=str(att.get('run_id') or '');nonce=str(att.get('nonce') or '');rd=_report_digest(att)
    if not run_id or run_id in seen_run_ids:reasons.append('RUN_ID_REPLAY_OR_MISSING')
    if len(nonce)<32 or nonce in seen_nonces:reasons.append('NONCE_REPLAY_OR_INVALID')
    if rd in seen_report_digests:reasons.append('REPORT_DIGEST_REPLAY')
    campaign_id=str(att.get('campaign_id') or '')
    if not campaign_id:reasons.append('CAMPAIGN_ID_REQUIRED')
    if att.get('evidence_class')!='REAL_CODEX_EFFECT':reasons.append('REAL_CODEX_EFFECT_REQUIRED')
    if att.get('windows_target_observer') is not True:reasons.append('WINDOWS_TARGET_OBSERVER_REQUIRED')
    if att.get('durable_witness_verified') is not True:reasons.append('DURABLE_IDEMPOTENCY_WITNESS_REQUIRED')
    t=_time(att.get('generated_utc') or att.get('attested_utc'))
    if not t or datetime.now(timezone.utc)-t>timedelta(hours=max_age_hours) or t-datetime.now(timezone.utc)>timedelta(minutes=5):reasons.append('EVIDENCE_STALE_OR_TIME_INVALID')
    signer=_load_signer();sv=signer.verify_signed_attestation(att,trusted_certificate_sha256=trusted_certificate_sha256)
    if not sv.get('valid'):reasons.extend('SIGNATURE_'+x for x in (sv.get('reasons') or []))
    if not reasons:
        seen_run_ids.add(run_id);seen_nonces.add(nonce);seen_report_digests.add(rd)
    env=att.get('signature_envelope') or {}
    return {'accepted':not reasons,'case_id':case_id,'effect':effect,'crash_window':window,'campaign_ref':safe_ref(campaign_id) if campaign_id else None,'run_id_ref':safe_ref(run_id) if run_id else None,'nonce_ref':safe_ref(nonce) if nonce else None,'report_sha256':rd,'certificate_sha256':env.get('certificate_sha256'),'signer_key_id_ref':env.get('signer_key_id_ref'),'attested_utc':att.get('generated_utc') or att.get('attested_utc'),'reasons':sorted(set(reasons)),'synthetic_fixture':bool(env.get('synthetic_fixture'))}

def ingest_reports(reports:list[dict[str,Any]],*,expected_package_version:str,expected_manifest_sha256:str,expected_trust_snapshot_sha256:str,trusted_certificate_sha256:set[str],seen_index:dict[str,list[str]]|None=None,max_age_hours:int=24)->dict[str,Any]:
    idx=seen_index or {};nonces=set(idx.get('nonces') or []);runs=set(idx.get('run_ids') or []);digests=set(idx.get('report_digests') or [])
    accepted=[];quarantine=[]
    for att in reports:
        row=verify_report(att,expected_package_version=expected_package_version,expected_manifest_sha256=expected_manifest_sha256,expected_trust_snapshot_sha256=expected_trust_snapshot_sha256,trusted_certificate_sha256=trusted_certificate_sha256,seen_nonces=nonces,seen_run_ids=runs,seen_report_digests=digests,max_age_hours=max_age_hours)
        (accepted if row['accepted'] else quarantine).append(row)
    seen_cases={(x['effect'],x['crash_window']) for x in accepted};missing=sorted(f'{e}::{w}' for e,w in EXPECTED-seen_cases)
    campaigns={x['campaign_ref'] for x in accepted if x.get('campaign_ref')};campaign_conflict=len(campaigns)>1
    if campaign_conflict:quarantine.append({'accepted':False,'case_id':None,'reasons':['MIXED_CAMPAIGN_OWNERSHIP']})
    summary={'accepted':len(accepted),'quarantined':len(quarantine),'present_cases':len(seen_cases),'missing_cases':len(missing),'matrix_complete':len(seen_cases)==12 and not missing and not campaign_conflict}
    body={'product':PRODUCT,'version':VERSION,'bundle_type':'WINDOWS_TARGET_CERTIFICATION_EVIDENCE_INBOX','expected_package_version':expected_package_version,'expected_manifest_sha256':expected_manifest_sha256,'expected_trust_snapshot_sha256':expected_trust_snapshot_sha256,'summary':summary,'accepted':accepted,'quarantine':quarantine,'missing_case_ids':missing,'seen_index':{'nonces':sorted(nonces),'run_ids':sorted(runs),'report_digests':sorted(digests)},'read_only_ingest':True,'target_effects_executed':False,'automatic_repair':False,'automatic_production_certification':False,'production_score_promotion_eligible':False}
    body['evidence_bundle_sha256']=sha(stable({k:v for k,v in body.items() if k!='evidence_bundle_sha256'}));body['generated_utc']=utcnow()
    body['production_evidence_imported']=bool(accepted) and not any(x.get('synthetic_fixture') for x in accepted)
    return body

def synthetic_report(effect:str,window:str,*,manifest:str,trust:str,campaign_id:str)->tuple[dict[str,Any],str]:
    signer=_load_signer();att={'product':PRODUCT,'version':VERSION,'package_version':VERSION,'package_manifest_sha256':manifest,'trust_snapshot_sha256':trust,'campaign_id':campaign_id,'case_id':f'{effect}::{window}','effect':effect,'crash_window':window,'run_id':str(uuid.uuid4()),'nonce':uuid.uuid4().hex+uuid.uuid4().hex,'generated_utc':utcnow(),'evidence_class':'REAL_CODEX_EFFECT','windows_target_observer':True,'real_codex_effect':True,'durable_witness_verified':True,'target_ref':'ref-target-fixture','events':[{'seq':1,'status':'PASS','effect':effect,'crash_window':window}]}
    return signer.synthetic_sign_attestation(att)

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    manifest='a'*64;trust='b'*64;campaign='campaign-fixture';reports=[];trusted=set()
    for e,w in sorted(EXPECTED):
        a,c=synthetic_report(e,w,manifest=manifest,trust=trust,campaign_id=campaign);reports.append(a);trusted.add(c)
    good=ingest_reports(reports,expected_package_version=VERSION,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,trusted_certificate_sha256=trusted)
    add('complete_matrix_ingested',good['summary']['accepted']==12 and good['summary']['matrix_complete'],good['summary'])
    add('read_only_no_effect',good['read_only_ingest'] and not good['target_effects_executed'])
    add('synthetic_not_production',good['production_evidence_imported'] is False and good['production_score_promotion_eligible'] is False)
    dup=ingest_reports([reports[0],reports[0]],expected_package_version=VERSION,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,trusted_certificate_sha256=trusted)
    add('replay_quarantined',dup['summary']['accepted']==1 and dup['summary']['quarantined']>=1 and any('NONCE_REPLAY_OR_INVALID' in x.get('reasons',[]) or 'REPORT_DIGEST_REPLAY' in x.get('reasons',[]) for x in dup['quarantine']))
    mixed=json.loads(json.dumps(reports[0]));mixed['package_version']='25.68'; signer=_load_signer();mixed,_=signer.synthetic_sign_attestation({k:v for k,v in mixed.items() if k not in ('signature_envelope','attestation_sha256')});bad=ingest_reports([mixed],expected_package_version=VERSION,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,trusted_certificate_sha256=trusted)
    add('mixed_version_quarantined',any('MIXED_PACKAGE_VERSION' in x.get('reasons',[]) for x in bad['quarantine']))
    untrusted=ingest_reports([reports[0]],expected_package_version=VERSION,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,trusted_certificate_sha256={'0'*64})
    add('untrusted_signer_quarantined',any(any('CERTIFICATE_NOT_TRUSTED' in r for r in x.get('reasons',[])) for x in untrusted['quarantine']))
    add('deterministic_bundle_digest',len(good['evidence_bundle_sha256'])==64 and HEX64.fullmatch(good['evidence_bundle_sha256']) is not None)
    raw=json.dumps(good,ensure_ascii=False).lower();add('privacy_no_raw_identity_or_secret',all(x not in raw for x in ('access_token','refresh_token','private_key','raw@example','bearer secret')))
    add('quarantine_no_auto_repair',good['automatic_repair'] is False)
    add('no_auto_certification',good['automatic_production_certification'] is False)
    passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'TARGET_CERTIFICATION_EVIDENCE_INGEST_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False,'automatic_production_certification':False,'real_codex_effects_executed':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();d=synthetic_proof();txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
