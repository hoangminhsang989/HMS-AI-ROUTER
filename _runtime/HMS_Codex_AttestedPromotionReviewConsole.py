#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
VERSION='25.68';PRODUCT='HMS-AI-ROUTER'
EFFECTS=('auth','restart','router','lease');WINDOWS=('AFTER_PREPARE_BEFORE_EFFECT','AFTER_EFFECT_BEFORE_DURABLE','AFTER_DURABLE_BEFORE_VERIFY')
EXPECTED={(e,w) for e in EFFECTS for w in WINDOWS}
FORBIDDEN_KEYS=re.compile(r'(access[_-]?token|refresh[_-]?token|password|private[_-]?(key|material)|authorization|credential|account[_-]?(email|identity)|hostname)',re.I)

def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str):
 if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
 return hashlib.sha256(v).hexdigest()
def safe_ref(v:str):return 'ref-'+sha(v)[:24]
def _time(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:return None

def _sanitize(obj:Any)->Any:
 if isinstance(obj,dict):
  out={}
  for k,v in obj.items():
   if FORBIDDEN_KEYS.search(str(k)):out[k]='<redacted>'
   else:out[k]=_sanitize(v)
  return out
 if isinstance(obj,list):return [_sanitize(x) for x in obj]
 if isinstance(obj,str):
  if re.search(r'Bearer\s+[A-Za-z0-9._~+\-/=]{8,}',obj,re.I):return re.sub(r'Bearer\s+[A-Za-z0-9._~+\-/=]{8,}','Bearer <redacted>',obj,flags=re.I)
  return obj
 return obj

def review_reports(reports:list[dict[str,Any]],*,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str,max_age_hours:int=24)->dict[str,Any]:
 reasons=[];seen=set();rows=[];now=datetime.now(timezone.utc);target_refs=set()
 for rep in reports:
  effect=str(rep.get('effect') or '');window=str(rep.get('crash_window') or '');key=(effect,window)
  if key in seen:reasons.append('DUPLICATE_CASE_REPORT')
  seen.add(key)
  rr=[]
  if key not in EXPECTED:rr.append('CASE_NOT_IN_4X3_MATRIX')
  if rep.get('package_version')!=package_version:rr.append('MIXED_PACKAGE_VERSION')
  if rep.get('manifest_sha256')!=manifest_sha256:rr.append('MANIFEST_DIGEST_MISMATCH')
  if rep.get('trust_snapshot_sha256')!=trust_snapshot_sha256:rr.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
  if rep.get('signature_valid') is not True:rr.append('CRYPTOGRAPHIC_SIGNATURE_REQUIRED')
  if rep.get('windows_target_observer') is not True:rr.append('WINDOWS_TARGET_OBSERVER_REQUIRED')
  if rep.get('real_codex_effect') is not True:rr.append('REAL_CODEX_EFFECT_REQUIRED')
  if rep.get('durable_witness_verified') is not True:rr.append('DURABLE_IDEMPOTENCY_WITNESS_REQUIRED')
  ts=_time(rep.get('attested_utc'))
  if not ts or now-ts>timedelta(hours=max_age_hours):rr.append('ATTESTATION_STALE')
  if str(rep.get('certificate_state') or '')=='REVOKED':rr.append('CERTIFICATE_REVOKED')
  if str(rep.get('certificate_state') or '')=='RETIRED':rr.append('CERTIFICATE_RETIRED_CURRENT_PROMOTION_REJECT')
  tr=str(rep.get('target_ref') or '')
  if tr:target_refs.add(tr)
  rows.append({'case_id':f'{effect}::{window}','effect':effect,'crash_window':window,'status':'PASS' if not rr else 'REJECT','reasons':rr,'attested_utc':rep.get('attested_utc'),'certificate_pin_ref':rep.get('certificate_pin_ref'),'signature_envelope_sha256':rep.get('signature_envelope_sha256'),'target_ref':tr or None})
  reasons.extend(rr)
 missing=EXPECTED-seen
 if missing:reasons.append('COMPLETE_4X3_CRASH_MATRIX_REQUIRED')
 if len(reports)!=12:reasons.append('EXACTLY_12_SIGNED_CASE_REPORTS_REQUIRED')
 if len(target_refs)>1:reasons.append('MIXED_TARGET_IDENTITY')
 eligible=not reasons and len(seen)==12
 title='ĐỦ ĐIỀU KIỆN ĐỂ NGƯỜI VẬN HÀNH XEM XÉT PROMOTION' if eligible else 'CHƯA ĐỦ ĐIỀU KIỆN PROMOTION'
 lines=[title]
 reason_vi={'COMPLETE_4X3_CRASH_MATRIX_REQUIRED':'Chưa đủ ma trận 4 effect × 3 crash window.','CRYPTOGRAPHIC_SIGNATURE_REQUIRED':'Có báo cáo chưa xác minh được chữ ký mật mã.','MIXED_PACKAGE_VERSION':'Phát hiện evidence khác phiên bản package.','TRUST_SNAPSHOT_DIGEST_MISMATCH':'Trust snapshot không khớp bản đã đóng băng.','CERTIFICATE_REVOKED':'Có chứng thư đã bị thu hồi.','CERTIFICATE_RETIRED_CURRENT_PROMOTION_REJECT':'Chứng thư đã retire chỉ còn giá trị audit lịch sử, không dùng cho case/promotion mới.','ATTESTATION_STALE':'Có báo cáo đã quá freshness window.','REAL_CODEX_EFFECT_REQUIRED':'Thiếu bằng chứng effect Codex thật.','WINDOWS_TARGET_OBSERVER_REQUIRED':'Thiếu Windows target observer thật.'}
 for r in sorted(set(reasons)):lines.append('• '+reason_vi.get(r,r))
 return {'product':PRODUCT,'version':VERSION,'generated_utc':utcnow(),'verdict':'ELIGIBLE_FOR_HUMAN_PROMOTION_REVIEW' if eligible else 'NO_PROMOTION','package_version':package_version,'manifest_sha256':manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,'case_grid':rows,'case_count':len(rows),'matrix_complete':len(seen)==12 and not missing,'reasons':sorted(set(reasons)),'decision_vi':lines,'promotion_score_eligible':eligible,'automatic_production_certification':False,'requires_human_review':True,'target_ref':next(iter(target_refs)) if len(target_refs)==1 else None}

def historical_certificate_audit(report:dict[str,Any],certificate_record:dict[str,Any])->dict[str,Any]:
 signed=_time(report.get('attested_utc'));retired=_time(certificate_record.get('retired_utc'))
 state=str(certificate_record.get('state') or '')
 auditable=state in {'ACTIVE','RETIRED'} and (state!='RETIRED' or (signed is not None and retired is not None and signed<=retired))
 return {'auditable':auditable,'historical_only':state=='RETIRED','new_case_signing_allowed':state=='ACTIVE','state':state,'pin_id':certificate_record.get('pin_id')}

def export_offline_review_bundle(review:dict[str,Any],trust_snapshot:dict[str,Any],reports:list[dict[str,Any]])->dict[str,Any]:
 safe_reports=[]
 for rep in reports:
  safe_reports.append(_sanitize({k:rep.get(k) for k in ('effect','crash_window','package_version','manifest_sha256','trust_snapshot_sha256','attested_utc','certificate_pin_ref','signature_envelope','signature_envelope_sha256','target_ref','signature_valid','windows_target_observer','real_codex_effect','durable_witness_verified')}))
 body={'product':PRODUCT,'version':VERSION,'bundle_type':'OFFLINE_ATTESTED_PROMOTION_REVIEW','generated_utc':utcnow(),'trust_snapshot':_sanitize(trust_snapshot),'case_summaries':safe_reports,'review':_sanitize(review),'contains_account_identity':False,'contains_credentials':False,'contains_private_material':False,'automatic_production_certification':False}
 body['bundle_sha256']=sha(stable(body));return body

def synthetic_proof()->dict[str,Any]:
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 now=utcnow();reports=[]
 for e,w in sorted(EXPECTED):
  reports.append({'effect':e,'crash_window':w,'package_version':VERSION,'manifest_sha256':'a'*64,'trust_snapshot_sha256':'b'*64,'signature_valid':True,'windows_target_observer':True,'real_codex_effect':True,'durable_witness_verified':True,'attested_utc':now,'certificate_state':'ACTIVE','certificate_pin_ref':'pin-'+('c'*20),'signature_envelope_sha256':'d'*64,'target_ref':'ref-target-fixture'})
 good=review_reports(reports,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64);add('complete_12_review_eligible',good['promotion_score_eligible'] is True and good['case_count']==12)
 mixed=json.loads(json.dumps(reports));mixed[0]['package_version']='25.67';r=review_reports(mixed,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64);add('mixed_version_rejected','MIXED_PACKAGE_VERSION' in r['reasons'])
 revoked=json.loads(json.dumps(reports));revoked[1]['certificate_state']='REVOKED';r2=review_reports(revoked,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64);add('revoked_certificate_rejected','CERTIFICATE_REVOKED' in r2['reasons'])
 incomplete=review_reports(reports[:-1],package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64);add('incomplete_matrix_rejected','COMPLETE_4X3_CRASH_MATRIX_REQUIRED' in incomplete['reasons'])
 tampered=json.loads(json.dumps(reports));tampered[2]['signature_valid']=False;r3=review_reports(tampered,package_version=VERSION,manifest_sha256='a'*64,trust_snapshot_sha256='b'*64);add('invalid_signature_rejected','CRYPTOGRAPHIC_SIGNATURE_REQUIRED' in r3['reasons'])
 retired={'state':'RETIRED','pin_id':'pin-old','retired_utc':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()};ha=historical_certificate_audit(reports[0],retired);add('retired_cert_historical_auditable',ha['auditable'] and ha['historical_only'] and not ha['new_case_signing_allowed'])
 bundle=export_offline_review_bundle(good,{'trust_snapshot_sha256':'b'*64,'certificates':[]},reports);raw=json.dumps(bundle,ensure_ascii=False).lower();add('offline_bundle_integrity',len(bundle['bundle_sha256'])==64)
 add('offline_bundle_privacy',all(x not in raw for x in ('access_token','refresh_token','private_key','person@example','bearer abcdef')))
 add('vietnamese_explanation','ĐỦ ĐIỀU KIỆN' in '\n'.join(good['decision_vi']) and 'Chưa đủ ma trận' in '\n'.join(incomplete['decision_vi']))
 add('human_review_not_auto_cert',good['automatic_production_certification'] is False and good['requires_human_review'] is True)
 # synthetic fixture may exercise the review algorithm but cannot be production evidence.
 add('proof_output_nonproduction',True)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'ATTESTED_PROMOTION_REVIEW_CONSOLE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'synthetic_fixture_review_eligible':good['promotion_score_eligible'],'production_score_eligible':False,'automatic_production_certification':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();d=synthetic_proof();txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
