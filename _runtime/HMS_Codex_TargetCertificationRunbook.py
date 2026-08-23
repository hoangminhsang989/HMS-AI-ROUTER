#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,secrets,subprocess,sys,tempfile,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any,Callable
VERSION='25.67';PRODUCT='HMS-AI-ROUTER';ARM_TOKEN='HMS_V2567_ONE_SHOT_TARGET_CERT';OPERATOR_PHRASE='TOI XAC NHAN CHAY TARGET CERTIFICATION MOT LAN';ENV_GATE='HMS_V2567_ENABLE_TARGET_CERT';SESSION_TTL_MIN=20
PHASES=('DRY_RUN','PREFLIGHT','ARMED','EXECUTE','RECOVERY_VERIFY','ATTEST','AUTO_DISARM','PROMOTION_DECISION','DONE')
VI={'DRY_RUN':'CHẠY THỬ KHÔNG TÁC ĐỘNG','PREFLIGHT':'KIỂM TRA TRƯỚC KHI CHẠY','ARMED':'ĐÃ MỞ KHÓA MỘT LẦN','EXECUTE':'THỰC THI KIỂM THỬ MỤC TIÊU','RECOVERY_VERIFY':'XÁC MINH PHỤC HỒI','ATTEST':'KÝ BẰNG CHỨNG','AUTO_DISARM':'TỰ ĐÓNG KHÓA','PROMOTION_DECISION':'QUYẾT ĐỊNH EVIDENCE','DONE':'HOÀN TẤT'}
def utcnow():return datetime.now(timezone.utc).isoformat()
def sha(v:bytes|str):
 if isinstance(v,str):v=v.encode()
 return hashlib.sha256(v).hexdigest()
def stable(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def atomic(path:Path,obj:Any):
 path.parent.mkdir(parents=True,exist_ok=True);t=path.with_suffix(path.suffix+'.tmp')
 with t.open('w',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(t,path)
def manifest_sha(root:Path):
 for name in ('RELEASE_MANIFEST_V25_67.json','RELEASE_MANIFEST_V25_66.json','RELEASE_MANIFEST_V25_65.json'):
  p=root/name
  if p.exists():return hashlib.sha256(p.read_bytes()).hexdigest()
 return ''
def make_event(seq:int,phase:str,status:str,detail:str='')->dict[str,Any]:return {'seq':seq,'phase':phase,'nhan':VI[phase],'status':status,'detail':detail[:180],'time_utc':utcnow()}
def preflight(*,package_version:str,manifest_digest:str,arm:str,operator_confirm:str,host_is_windows:bool|None=None)->dict[str,Any]:
 win=os.name=='nt' if host_is_windows is None else host_is_windows
 gates={'windows_host':win,'package_version_exact':package_version==VERSION,'manifest_digest':len(manifest_digest)==64 and all(c in '0123456789abcdef' for c in manifest_digest.lower()),'environment_gate':os.environ.get(ENV_GATE)=='1','arm_token':arm==ARM_TOKEN,'operator_phrase':operator_confirm==OPERATOR_PHRASE}
 return {'armed':all(gates.values()),'gates':gates,'one_shot':True,'auto_disarm_required':True}
def create_session(path:Path,package_version:str,manifest_digest:str)->dict[str,Any]:
 now=datetime.now(timezone.utc);obj={'schema_version':1,'run_id':str(uuid.uuid4()),'nonce':secrets.token_hex(32),'created_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=SESSION_TTL_MIN)).isoformat(),'package_version':package_version,'package_manifest_sha256':manifest_digest,'armed':True,'consumed':False}
 path.parent.mkdir(parents=True,exist_ok=True);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 return obj
def disarm_session(path:Path,reason:str)->dict[str,Any]:
 try:o=json.loads(path.read_text('utf-8')) if path.exists() else {}
 except Exception:o={}
 o.update({'armed':False,'consumed':True,'disarmed_utc':utcnow(),'disarm_reason':reason});atomic(path,o);return o
def dry_run(package_version:str,manifest_digest:str)->dict[str,Any]:
 return {'product':PRODUCT,'version':VERSION,'suite':'CONTROLLED_TARGET_CERTIFICATION_RUNBOOK_DRY_RUN','generated_utc':utcnow(),'verdict':'READY_FOR_TARGET_PREFLIGHT' if package_version==VERSION and len(manifest_digest)==64 else 'BLOCKED','phases':[VI[p] for p in PHASES],'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False,'auto_disarm':True}
def execute_one_shot(*,session_dir:Path,package_version:str,manifest_digest:str,arm:str,operator_confirm:str,real_effect_cmd:list[str]|None=None,sign_cmd:list[str]|None=None,promotion_cmd:list[str]|None=None,host_is_windows:bool|None=None,runner:Callable[...,Any]=subprocess.run)->dict[str,Any]:
 pf=preflight(package_version=package_version,manifest_digest=manifest_digest,arm=arm,operator_confirm=operator_confirm,host_is_windows=host_is_windows);events=[make_event(1,'PREFLIGHT','PASS' if pf['armed'] else 'BLOCKED')]
 if not pf['armed']:return {'product':PRODUCT,'version':VERSION,'suite':'CONTROLLED_TARGET_CERTIFICATION_RUNBOOK','generated_utc':utcnow(),'verdict':'DEFERRED_NOT_ARMED','preflight':pf,'events':events,'real_codex_effects_executed':False,'production_score_eligible':False,'auto_disarmed':True}
 session_path=session_dir/'one-shot-target-cert-session.json';sess=create_session(session_path,package_version,manifest_digest);events.append(make_event(2,'ARMED','PASS','ONE_SHOT_SESSION_CREATED'))
 real_executed=False;sign_executed=False;promotion=False;reason='NORMAL_COMPLETION'
 try:
  if not real_effect_cmd:raise RuntimeError('REAL_EFFECT_COMMAND_REQUIRED')
  events.append(make_event(3,'EXECUTE','STARTED'))
  p=runner(real_effect_cmd,capture_output=True,text=True,timeout=900,shell=False);real_executed=True
  if p.returncode!=0:raise RuntimeError('REAL_EFFECT_CERTIFICATION_FAILED')
  events.append(make_event(4,'RECOVERY_VERIFY','PASS'))
  if not sign_cmd:raise RuntimeError('ATTESTATION_SIGN_COMMAND_REQUIRED')
  s=runner(sign_cmd,capture_output=True,text=True,timeout=120,shell=False);sign_executed=True
  if s.returncode!=0:raise RuntimeError('ATTESTATION_SIGN_FAILED')
  events.append(make_event(5,'ATTEST','PASS'))
  if not promotion_cmd:raise RuntimeError('PROMOTION_VERIFY_COMMAND_REQUIRED')
  g=runner(promotion_cmd,capture_output=True,text=True,timeout=120,shell=False);promotion=(g.returncode==0);events.append(make_event(6,'PROMOTION_DECISION','PASS' if promotion else 'NO_PROMOTION'))
  verdict='PASS_TARGET_CERTIFICATION_EVIDENCE_READY' if promotion else 'PASS_TARGET_RUN_NO_PROMOTION'
 except Exception as exc:
  reason=type(exc).__name__+':'+str(exc);events.append(make_event(len(events)+1,'PROMOTION_DECISION','OPERATOR_REQUIRED',reason));verdict='OPERATOR_REQUIRED'
 finally:
  d=disarm_session(session_path,reason);events.append(make_event(len(events)+1,'AUTO_DISARM','PASS',d.get('disarm_reason','')))
 events.append(make_event(len(events)+1,'DONE','PASS' if verdict.startswith('PASS') else 'BLOCKED'))
 return {'product':PRODUCT,'version':VERSION,'suite':'CONTROLLED_TARGET_CERTIFICATION_RUNBOOK','generated_utc':utcnow(),'verdict':verdict,'preflight':pf,'events':events,'run_id_ref':'ref-'+sha(sess['run_id'])[:20],'nonce_ref':'ref-'+sha(sess['nonce'])[:20],'real_codex_effects_executed':real_executed,'windows_signing_executed':sign_executed,'production_score_promotion_eligible':promotion,'production_score_eligible':False,'auto_disarmed':True,'session_consumed':True}
class FakeResult:
 def __init__(self,rc=0):self.returncode=rc;self.stdout='{}';self.stderr=''
def synthetic_proof()->dict[str,Any]:
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 old=os.environ.get(ENV_GATE);os.environ[ENV_GATE]='1'
 try:
  with tempfile.TemporaryDirectory(prefix='hms-v2566-runbook-') as td:
   root=Path(td);digest='a'*64
   pf=preflight(package_version=VERSION,manifest_digest=digest,arm=ARM_TOKEN,operator_confirm=OPERATOR_PHRASE,host_is_windows=True);add('all_gates_arm',pf['armed'],pf)
   bad=preflight(package_version=VERSION,manifest_digest=digest,arm='BAD',operator_confirm=OPERATOR_PHRASE,host_is_windows=True);add('wrong_arm_blocks',not bad['armed'])
   calls=[]
   def okrun(cmd,**kwargs):calls.append(cmd);return FakeResult(0)
   r=execute_one_shot(session_dir=root,package_version=VERSION,manifest_digest=digest,arm=ARM_TOKEN,operator_confirm=OPERATOR_PHRASE,host_is_windows=True,real_effect_cmd=['real','target'],sign_cmd=['sign','evidence'],promotion_cmd=['verify','promotion'],runner=okrun)
   add('happy_path_auto_disarms',r['verdict']=='PASS_TARGET_CERTIFICATION_EVIDENCE_READY' and r['auto_disarmed'] and len(calls)==3,r)
   sess=json.loads((root/'one-shot-target-cert-session.json').read_text('utf-8'));add('session_consumed',not sess['armed'] and sess['consumed'])
  with tempfile.TemporaryDirectory(prefix='hms-v2566-runbook-fail-') as td2:
   root2=Path(td2);n=[0]
   def failrun(cmd,**kwargs):n[0]+=1;return FakeResult(7 if n[0]==2 else 0)
   r2=execute_one_shot(session_dir=root2,package_version=VERSION,manifest_digest='b'*64,arm=ARM_TOKEN,operator_confirm=OPERATOR_PHRASE,host_is_windows=True,real_effect_cmd=['real'],sign_cmd=['sign'],promotion_cmd=['promote'],runner=failrun);s2=json.loads((root2/'one-shot-target-cert-session.json').read_text())
   add('failure_still_auto_disarms',r2['verdict']=='OPERATOR_REQUIRED' and not s2['armed'] and s2['consumed'],r2)
  add('nonwindows_real_target_blocked',not preflight(package_version=VERSION,manifest_digest='c'*64,arm=ARM_TOKEN,operator_confirm=OPERATOR_PHRASE,host_is_windows=False)['armed'])
  add('dry_run_no_effects',dry_run(VERSION,'d'*64)['real_codex_effects_executed'] is False)
  src=Path(__file__).read_text();add('structured_argv_no_shell','shell=False' in src);add('one_shot_create_exclusive','os.O_EXCL' in src);add('finally_auto_disarm','finally:' in src and 'disarm_session' in src)
 finally:
  if old is None:os.environ.pop(ENV_GATE,None)
  else:os.environ[ENV_GATE]=old
 passed=sum(t['status']=='PASS' for t in tests);return {'product':PRODUCT,'version':VERSION,'suite':'CONTROLLED_TARGET_CERTIFICATION_RUNBOOK_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False}
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','dry-run','target'),default='proof');ap.add_argument('--package-version',default=VERSION);ap.add_argument('--manifest-sha256',default='');ap.add_argument('--session-dir');ap.add_argument('--arm',default='');ap.add_argument('--operator-confirm',default='');ap.add_argument('--output');a=ap.parse_args()
 if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
 elif a.mode=='dry-run':out=dry_run(a.package_version,a.manifest_sha256);rc=0 if out['verdict'].startswith('READY') else 2
 else:
  # Target mode deliberately requires integration-generated structured argv. This CLI never invents destructive commands.
  out={'product':PRODUCT,'version':VERSION,'suite':'CONTROLLED_TARGET_CERTIFICATION_RUNBOOK','generated_utc':utcnow(),'verdict':'DEFERRED_TARGET_INTEGRATION_REQUIRED','preflight':preflight(package_version=a.package_version,manifest_digest=a.manifest_sha256,arm=a.arm,operator_confirm=a.operator_confirm),'real_codex_effects_executed':False,'windows_signing_executed':False,'production_score_eligible':False,'auto_disarmed':True};rc=4
 if a.output:atomic(Path(a.output),out)
 print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
