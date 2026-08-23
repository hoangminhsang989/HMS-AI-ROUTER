#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, platform, re, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.72'; COCKPIT_BASELINE='1.3.27'; PRODUCT='HMS-AI-ROUTER'; KIT_SCHEMA=1
HEX64=re.compile(r'^[0-9a-f]{64}$')
CASE_DEFS=(
 ('FOREIGN_PORT_AUTO_REBIND','Xung đột cổng tự chuyển cổng, không chạm PID lạ'),
 ('ACCOUNT_OCCUPANCY_GUARD','Chặn cùng tài khoản ở hai Codex instance đang hoạt động'),
 ('CLIENT_AUTH_API_SERVICE_SPLIT','Tách trạng thái đăng nhập Codex và API Service'),
 ('OFFICIAL_ACCOUNT_USAGE_CONTINUITY','Giữ lịch sử usage bằng pseudonymous official-account ref'),
 ('WEBSOCKET_PREFERENCE_PERSISTENCE','Giữ WebSocket preference qua refresh/switch/restart'),
 ('BOUNDED_BACKUP_ROLLBACK_NTFS','Backup hữu hạn và rollback crash-safe trên NTFS'),
 ('STREAM_IDENTITY_ISOLATION','Cách ly composite conversation/thread/request identity'),
)
CASE_IDS=tuple(x[0] for x in CASE_DEFS)
FORBIDDEN_SECRET_KEYS=('access_token','refresh_token','id_token','authorization','cookie','private_key')


def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def _load(name:str,root:Path):
    p=root/name;spec=importlib.util.spec_from_file_location('hms72_'+p.stem,p);m=importlib.util.module_from_spec(spec);sys.modules['hms72_'+p.stem]=m;spec.loader.exec_module(m);return m

def validate_binding(*,package_zip_sha256:str,manifest_sha256:str,cockpit_baseline:str,codex_version:str)->list[str]:
    r=[]
    if not HEX64.fullmatch(str(package_zip_sha256).lower()):r.append('PACKAGE_ZIP_SHA256_INVALID')
    if not HEX64.fullmatch(str(manifest_sha256).lower()):r.append('MANIFEST_SHA256_INVALID')
    if cockpit_baseline!=COCKPIT_BASELINE:r.append('COCKPIT_BASELINE_MISMATCH')
    if not str(codex_version or '').strip():r.append('CODEX_VERSION_REQUIRED')
    return r

def build_kit_index(*,package_zip_sha256:str,manifest_sha256:str,codex_version:str,trust_snapshot_sha256:str='')->dict[str,Any]:
    reasons=validate_binding(package_zip_sha256=package_zip_sha256,manifest_sha256=manifest_sha256,cockpit_baseline=COCKPIT_BASELINE,codex_version=codex_version)
    if trust_snapshot_sha256 and not HEX64.fullmatch(trust_snapshot_sha256.lower()):reasons.append('TRUST_SNAPSHOT_SHA256_INVALID')
    cases=[{'case_id':cid,'label_vi':label,'state':'DISARMED','one_case_only':True,'required_evidence_classes':['WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'],'report_file':f'reports/{i+1:02d}_{cid}.signed.json'} for i,(cid,label) in enumerate(CASE_DEFS)]
    body={'product':PRODUCT,'version':VERSION,'schema_version':KIT_SCHEMA,'kit_type':'WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT','generated_utc':utcnow(),'package_version':VERSION,'package_zip_sha256':package_zip_sha256.lower(),'release_manifest_sha256':manifest_sha256.lower(),'cockpit_baseline':COCKPIT_BASELINE,'codex_version':str(codex_version),'codex_version_ref':safe_ref(str(codex_version)),'trust_snapshot_sha256':trust_snapshot_sha256.lower() if trust_snapshot_sha256 else None,'binding_valid':not reasons,'binding_reasons':reasons,'default_state':'DISARMED','automatic_next_case':False,'automatic_rearm':False,'capture_only_orchestration':True,'target_effect_executor':'HMS_Codex_TargetCampaignExecutor.py','cases':cases,'privacy':{'raw_account_ids':False,'credentials':False,'prompts':False,'responses':False,'command_line':False,'environment':False},'production_score_eligible':False,'automatic_production_certification':False}
    body['kit_index_sha256']=sha(stable({k:v for k,v in body.items() if k!='kit_index_sha256'}));return body

def finalize_case_report(*,root:Path,case_id:str,kit_index:dict[str,Any],observer:dict[str,Any],executor:dict[str,Any],signer_mode:str='synthetic-proof')->dict[str,Any]:
    reasons=[]
    if case_id not in CASE_IDS:reasons.append('UNKNOWN_CASE_ID')
    if not kit_index.get('binding_valid'):reasons.append('KIT_BINDING_INVALID')
    if kit_index.get('default_state')!='DISARMED':reasons.append('KIT_NOT_DISARMED_DEFAULT')
    if observer.get('evidence_class')!='WINDOWS_TARGET_OBSERVER':reasons.append('WINDOWS_TARGET_OBSERVER_REQUIRED')
    if executor.get('effect_executed') is not True:reasons.append('REAL_CODEX_EFFECT_REQUIRED')
    if executor.get('durable_witness_verified') is not True:reasons.append('DURABLE_IDEMPOTENCY_WITNESS_REQUIRED')
    report={'product':PRODUCT,'version':VERSION,'package_version':VERSION,'package_zip_sha256':kit_index.get('package_zip_sha256'),'package_manifest_sha256':kit_index.get('release_manifest_sha256'),'cockpit_baseline':kit_index.get('cockpit_baseline'),'codex_version_ref':kit_index.get('codex_version_ref'),'case_id':case_id,'status':'PASS' if not reasons else 'DEFERRED','evidence_classes':['WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'] if not reasons else list({str(observer.get('evidence_class') or ''),'REAL_CODEX_EFFECT' if executor.get('effect_executed') else ''}- {''}),'runtime_attestation_verified':not reasons,'signature_verified':False,'idempotency_witness_verified':executor.get('durable_witness_verified') is True,'raw_account_id_exported':False,'credential_payload_exported':False,'prompt_payload_exported':False,'response_payload_exported':False,'command_line_exported':False,'environment_exported':False,'observer_ref':safe_ref(str(observer.get('snapshot_sha256') or observer.get('digest') or 'observer')),'executor_ref':safe_ref(str(executor.get('observed_idempotency_key_ref') or case_id)),'run_id':str(uuid.uuid4()),'nonce':uuid.uuid4().hex+uuid.uuid4().hex,'generated_utc':utcnow(),'reasons':sorted(set(reasons)),'production_score_eligible':False,'automatic_production_certification':False}
    report['report_sha256']=sha(stable(report))
    if signer_mode=='synthetic-proof':
        signer=_load('HMS_Codex_WindowsAttestationSigner.py',root);signed,cert=signer.synthetic_sign_attestation(report);v=signer.verify_signed_attestation(signed,trusted_certificate_sha256={cert});signed['signature_verified']=bool(v.get('valid'));signed['synthetic_fixture']=True;return signed
    return report

def build_privacy_safe_index(reports:list[dict[str,Any]])->dict[str,Any]:
    rows=[]
    for r in reports:
        rows.append({'case_id':r.get('case_id'),'status':r.get('status'),'report_sha256':r.get('report_sha256') or r.get('attestation_sha256'),'signature_verified':bool(r.get('signature_verified')),'evidence_classes':sorted(set(r.get('evidence_classes') or [])),'generated_utc':r.get('generated_utc')})
    body={'product':PRODUCT,'version':VERSION,'index_type':'WINDOWS_TARGET_EVIDENCE_INDEX','generated_utc':utcnow(),'reports':rows,'report_count':len(rows),'complete_seven_case_matrix':set(x.get('case_id') for x in rows)==set(CASE_IDS) and len(rows)==7,'privacy_safe':True,'production_score_eligible':False}
    body['index_sha256']=sha(stable({k:v for k,v in body.items() if k!='index_sha256'}));return body

def synthetic_proof(root:Path)->dict[str,Any]:
    t=[]
    def add(n,ok,d=None):t.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    idx=build_kit_index(package_zip_sha256='a'*64,manifest_sha256='b'*64,codex_version='codex-current-fixture',trust_snapshot_sha256='c'*64)
    add('exact_seven_cases',len(idx['cases'])==7 and tuple(x['case_id'] for x in idx['cases'])==CASE_IDS)
    add('kit_disarmed_default',idx['default_state']=='DISARMED' and not idx['automatic_next_case'] and not idx['automatic_rearm'])
    add('exact_package_manifest_binding',idx['binding_valid'] and idx['package_zip_sha256']=='a'*64 and idx['release_manifest_sha256']=='b'*64)
    add('codex_version_pseudonymous_ref',idx['codex_version_ref'].startswith('ref-') and 'codex-current-fixture' not in idx['codex_version_ref'])
    add('privacy_contract',all(v is False for v in idx['privacy'].values()))
    blocked=finalize_case_report(root=root,case_id=CASE_IDS[0],kit_index=idx,observer={'evidence_class':'LAB_FIXTURE'},executor={'effect_executed':False,'durable_witness_verified':False})
    add('lab_fixture_cannot_be_real_report',blocked.get('status')=='DEFERRED' and blocked.get('production_score_eligible') is False)
    good=finalize_case_report(root=root,case_id=CASE_IDS[0],kit_index=idx,observer={'evidence_class':'WINDOWS_TARGET_OBSERVER','snapshot_sha256':'d'*64},executor={'effect_executed':True,'durable_witness_verified':True,'observed_idempotency_key_ref':'ref-witness'})
    add('signed_report_contract',good.get('signature_verified') is True and good.get('raw_account_id_exported') is False and good.get('credential_payload_exported') is False)
    raw=json.dumps(good,ensure_ascii=False).lower();add('signed_report_no_secret_payload_keys',all(k not in raw for k in FORBIDDEN_SECRET_KEYS) and good.get('raw_account_id_exported') is False and good.get('credential_payload_exported') is False and good.get('prompt_payload_exported') is False and good.get('response_payload_exported') is False and good.get('command_line_exported') is False and good.get('environment_exported') is False)
    reports=[]
    for cid in CASE_IDS:
        x=finalize_case_report(root=root,case_id=cid,kit_index=idx,observer={'evidence_class':'WINDOWS_TARGET_OBSERVER','snapshot_sha256':sha(cid)},executor={'effect_executed':True,'durable_witness_verified':True,'observed_idempotency_key_ref':safe_ref(cid)});reports.append(x)
    ix=build_privacy_safe_index(reports);add('privacy_index_complete',ix['complete_seven_case_matrix'] and ix['report_count']==7)
    add('capture_kit_never_promotes_score',idx['production_score_eligible'] is False and ix['production_score_eligible'] is False)
    p=sum(x['status']=='PASS' for x in t)
    return {'product':PRODUCT,'version':VERSION,'suite':'WINDOWS_TARGET_EVIDENCE_CAPTURE_KIT_PROOF','generated_utc':utcnow(),'verdict':'PASS' if p==len(t) else 'FAIL','summary':{'pass':p,'fail':len(t)-p,'total':len(t)},'tests':t,'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(Path(__file__).parent));ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();out=synthetic_proof(Path(a.root));txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
