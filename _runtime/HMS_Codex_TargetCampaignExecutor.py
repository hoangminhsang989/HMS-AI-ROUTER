#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, platform, secrets, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION='25.68'; PRODUCT='HMS-AI-ROUTER'; SCHEMA_VERSION=1
EXECUTOR_ENV_GATE='HMS_V2568_ENABLE_TARGET_CASE'
EXECUTOR_ARM_TOKEN='HMS_V2568_EXECUTE_ONE_ARMED_CASE'
EXECUTOR_OPERATOR_PHRASE='TOI XAC NHAN THUC THI MOT CASE TARGET DA ARM'
ALLOWED_EFFECTS={'auth','restart','router','lease'}


def utcnow(): return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes: return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str): v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str: return 'ref-'+sha(v)[:24]

def _load_campaign_module(root:Path):
    p=root/'HMS_Codex_TargetCertificationCampaign.py'
    spec=importlib.util.spec_from_file_location('hms_campaign_2568',p);m=importlib.util.module_from_spec(spec);sys.modules['hms_campaign_2568']=m;spec.loader.exec_module(m);return m

def _case(campaign:dict[str,Any],case_id:str)->dict[str,Any]:
    row=next((x for x in campaign.get('cases') or [] if x.get('case_id')==case_id),None)
    if row is None: raise ValueError('CASE_NOT_FOUND')
    return row

def validate_frozen_binding(campaign:dict[str,Any],*,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str)->list[str]:
    reasons=[]
    if campaign.get('package_version')!=package_version: reasons.append('MIXED_PACKAGE_VERSION')
    if campaign.get('manifest_sha256')!=manifest_sha256: reasons.append('MANIFEST_DIGEST_MISMATCH')
    if campaign.get('trust_snapshot_sha256')!=trust_snapshot_sha256: reasons.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
    return reasons

def windows_target_preflight(*,windows_host:bool|None=None,powershell_51_parser_ok:bool=False,powershell_51_runtime_ok:bool=False,codex_process_owned:bool=False,official_auth_observer_ok:bool=False,idempotency_witness_ok:bool=False)->dict[str,Any]:
    if windows_host is None: windows_host=(os.name=='nt')
    checks={
      'WINDOWS_HOST':bool(windows_host),
      'POWERSHELL_5_1_PARSER':bool(powershell_51_parser_ok),
      'POWERSHELL_5_1_RUNTIME':bool(powershell_51_runtime_ok),
      'CODEX_PROCESS_OWNERSHIP':bool(codex_process_owned),
      'OFFICIAL_AUTH_OBSERVER':bool(official_auth_observer_ok),
      'IDEMPOTENCY_WITNESS':bool(idempotency_witness_ok),
    }
    failed=[k for k,v in checks.items() if not v]
    return {'ok':not failed,'checks':checks,'failed':failed,'evidence_class':'WINDOWS_TARGET_OBSERVER' if windows_host else 'LAB_FIXTURE'}

def _arm_ok(*,arm_token:str,operator_phrase:str,env_value:str|None)->bool:
    return arm_token==EXECUTOR_ARM_TOKEN and operator_phrase==EXECUTOR_OPERATOR_PHRASE and str(env_value or '')=='1'

def _disarm_record(case_id:str,reason:str)->dict[str,Any]:
    return {'case_id':case_id,'action':'AUTO_DISARM','reason':reason,'disarmed_utc':utcnow(),'armed':False}

def execute_one_case(campaign:dict[str,Any],case_id:str,*,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str,arm_token:str='',operator_phrase:str='',env_value:str|None=None,windows_host:bool|None=None,powershell_51_parser_ok:bool=False,powershell_51_runtime_ok:bool=False,codex_process_owned:bool=False,official_auth_observer_ok:bool=False,idempotency_witness_ok:bool=False,adapter_runner:Callable[[dict[str,Any]],dict[str,Any]]|None=None)->dict[str,Any]:
    row=_case(campaign,case_id);reasons=validate_frozen_binding(campaign,package_version=package_version,manifest_sha256=manifest_sha256,trust_snapshot_sha256=trust_snapshot_sha256)
    if row.get('effect') not in ALLOWED_EFFECTS: reasons.append('EFFECT_NOT_ALLOWED')
    if row.get('state')!='ARMED': reasons.append('CASE_NOT_ARMED')
    if not _arm_ok(arm_token=arm_token,operator_phrase=operator_phrase,env_value=env_value): reasons.append('EXPLICIT_EXECUTOR_ARM_REQUIRED')
    pf=windows_target_preflight(windows_host=windows_host,powershell_51_parser_ok=powershell_51_parser_ok,powershell_51_runtime_ok=powershell_51_runtime_ok,codex_process_owned=codex_process_owned,official_auth_observer_ok=official_auth_observer_ok,idempotency_witness_ok=idempotency_witness_ok)
    if not pf['ok']: reasons.extend('PREFLIGHT_'+x for x in pf['failed'])
    # LAN/NAS lease is separately guarded by ownership+readback; no generic mutation shortcut.
    if row.get('effect')=='lease' and not (codex_process_owned and idempotency_witness_ok): reasons.append('LEASE_OWNERSHIP_READBACK_REQUIRED')
    base={'product':PRODUCT,'version':VERSION,'case_id':case_id,'case_id_ref':safe_ref(case_id),'effect':row.get('effect'),'crash_window':row.get('crash_window'),'package_version':package_version,'manifest_sha256':manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,'preflight':pf,'automatic_next_case':False,'automatic_rearm':False,'production_score_eligible':False,'real_effects_disarmed_by_default':True}
    if reasons:
        return {**base,'verdict':'DEFERRED_NOT_ARMED','reasons':sorted(set(reasons)),'effect_executed':False,'auto_disarm':_disarm_record(case_id,'PRECONDITION_NOT_MET')}
    if adapter_runner is None:
        return {**base,'verdict':'DEFERRED_TARGET_ADAPTER_REQUIRED','reasons':['TARGET_ADAPTER_RUNNER_REQUIRED'],'effect_executed':False,'auto_disarm':_disarm_record(case_id,'NO_ADAPTER')}
    try:
        request={'case_id':case_id,'effect':row.get('effect'),'crash_window':row.get('crash_window'),'idempotency_key_ref':row.get('idempotency_key_ref'),'manifest_sha256':manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,'one_shot':True}
        result=adapter_runner(request) or {}
        observed=str(result.get('observed_idempotency_key_ref') or '')
        expected=str(row.get('idempotency_key_ref') or '')
        if not result.get('effect_executed'):
            return {**base,'verdict':'TARGET_EFFECT_NOT_EXECUTED','reasons':['ADAPTER_DID_NOT_EXECUTE_EFFECT'],'effect_executed':False,'adapter_status':result.get('status'),'auto_disarm':_disarm_record(case_id,'ADAPTER_NO_EFFECT')}
        if not expected or observed!=expected:
            return {**base,'verdict':'OPERATOR_REQUIRED','reasons':['IDEMPOTENCY_WITNESS_MISMATCH'],'effect_executed':True,'adapter_status':result.get('status'),'auto_disarm':_disarm_record(case_id,'WITNESS_MISMATCH')}
        return {**base,'verdict':'PASS_EFFECT_DURABLE_VERIFY_REQUIRED','reasons':[],'effect_executed':True,'durable_witness_verified':True,'observed_idempotency_key_ref':observed,'adapter_status':result.get('status','PASS'),'auto_disarm':_disarm_record(case_id,'CASE_ATTEMPT_FINISHED')}
    finally:
        # No persisted arm state is retained by the executor. Target adapters must also use one-shot sessions.
        pass

def structured_subprocess_adapter(argv:list[str],request:dict[str,Any],timeout:int=120)->dict[str,Any]:
    if os.name!='nt': return {'status':'DEFERRED_NON_WINDOWS','effect_executed':False}
    if not argv or any(not isinstance(x,str) or '\x00' in x for x in argv): raise ValueError('STRUCTURED_ARGV_REQUIRED')
    proc=subprocess.run(argv,input=json.dumps(request,ensure_ascii=False),text=True,capture_output=True,timeout=timeout,shell=False)
    if proc.returncode!=0:return {'status':'ADAPTER_FAILED','effect_executed':False,'exit_code':proc.returncode}
    try: out=json.loads(proc.stdout)
    except Exception:return {'status':'ADAPTER_OUTPUT_INVALID','effect_executed':False}
    return out if isinstance(out,dict) else {'status':'ADAPTER_OUTPUT_INVALID','effect_executed':False}

def synthetic_proof(root:Path)->dict[str,Any]:
    campaign_mod=_load_campaign_module(root);tests=[]
    def add(name,ok,detail=None):tests.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    c=campaign_mod.new_campaign(package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,campaign_id='v2568-fixture')
    cid=campaign_mod.case_id('auth',campaign_mod.WINDOWS[1])
    armed=campaign_mod.arm_case(c,cid,arm_token=campaign_mod.ARM_TOKEN,operator_phrase=campaign_mod.OPERATOR_PHRASE,idempotency_material='fixture-effect')
    add('campaign_case_armed',armed.get('armed') is True)
    bad=execute_one_case(c,cid,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,arm_token=EXECUTOR_ARM_TOKEN,operator_phrase=EXECUTOR_OPERATOR_PHRASE,env_value='1',windows_host=False,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=True,official_auth_observer_ok=True,idempotency_witness_ok=True)
    add('nonwindows_target_blocked',bad['effect_executed'] is False and 'PREFLIGHT_WINDOWS_HOST' in bad['reasons'],bad['reasons'])
    mismatch=execute_one_case(c,cid,package_version=VERSION,manifest_sha256='c'*64,trust_snapshot_sha256='b'*64,arm_token=EXECUTOR_ARM_TOKEN,operator_phrase=EXECUTOR_OPERATOR_PHRASE,env_value='1',windows_host=True,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=True,official_auth_observer_ok=True,idempotency_witness_ok=True)
    add('frozen_manifest_binding',mismatch['effect_executed'] is False and 'MANIFEST_DIGEST_MISMATCH' in mismatch['reasons'])
    noarm=execute_one_case(c,cid,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,windows_host=True,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=True,official_auth_observer_ok=True,idempotency_witness_ok=True)
    add('independent_executor_arm_required',noarm['effect_executed'] is False and 'EXPLICIT_EXECUTOR_ARM_REQUIRED' in noarm['reasons'])
    def ok_adapter(req):return {'status':'PASS','effect_executed':True,'observed_idempotency_key_ref':req['idempotency_key_ref']}
    good=execute_one_case(c,cid,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,arm_token=EXECUTOR_ARM_TOKEN,operator_phrase=EXECUTOR_OPERATOR_PHRASE,env_value='1',windows_host=True,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=True,official_auth_observer_ok=True,idempotency_witness_ok=True,adapter_runner=ok_adapter)
    add('one_case_effect_durable_witness',good['verdict']=='PASS_EFFECT_DURABLE_VERIFY_REQUIRED' and good.get('durable_witness_verified') is True)
    add('auto_disarm_always',good['auto_disarm']['armed'] is False and noarm['auto_disarm']['armed'] is False)
    add('no_automatic_next_case',good['automatic_next_case'] is False and good['automatic_rearm'] is False)
    def bad_witness(req):return {'status':'PASS','effect_executed':True,'observed_idempotency_key_ref':'ref-wrong'}
    wrong=execute_one_case(c,cid,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,arm_token=EXECUTOR_ARM_TOKEN,operator_phrase=EXECUTOR_OPERATOR_PHRASE,env_value='1',windows_host=True,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=True,official_auth_observer_ok=True,idempotency_witness_ok=True,adapter_runner=bad_witness)
    add('witness_mismatch_operator_required',wrong['verdict']=='OPERATOR_REQUIRED')
    lease=campaign_mod.case_id('lease',campaign_mod.WINDOWS[0]);campaign_mod.arm_case(c,lease,arm_token=campaign_mod.ARM_TOKEN,operator_phrase=campaign_mod.OPERATOR_PHRASE,idempotency_material='lease-fixture')
    lg=execute_one_case(c,lease,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64,arm_token=EXECUTOR_ARM_TOKEN,operator_phrase=EXECUTOR_OPERATOR_PHRASE,env_value='1',windows_host=True,powershell_51_parser_ok=True,powershell_51_runtime_ok=True,codex_process_owned=False,official_auth_observer_ok=True,idempotency_witness_ok=True)
    add('lease_separate_ownership_gate','LEASE_OWNERSHIP_READBACK_REQUIRED' in lg['reasons'])
    import inspect
    adapter_src=inspect.getsource(structured_subprocess_adapter)
    add('structured_argv_no_shell','subprocess.run(argv' in adapter_src and 'shell=False' in adapter_src)
    raw=json.dumps({'good':good,'bad':bad},ensure_ascii=False).lower();add('privacy_no_raw_credentials',all(x not in raw for x in ('access_token','refresh_token','password','private_key','authorization')))
    add('synthetic_never_production_eligible',good['production_score_eligible'] is False)
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':PRODUCT,'version':VERSION,'suite':'TARGET_CAMPAIGN_EXECUTOR_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'real_codex_effects_executed':False,'windows_target_execution':False,'production_score_eligible':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.');ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();d=synthetic_proof(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
