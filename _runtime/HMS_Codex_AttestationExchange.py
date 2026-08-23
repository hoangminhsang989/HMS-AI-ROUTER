#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
VERSION='25.67';PRODUCT='HMS-AI-ROUTER'
FORBIDDEN_KEYS={'access_token','refresh_token','id_token','authorization','cookie','password','secret','credential','email','account','hostname','username','command_line','environment','prompt','body','private_key'}
REASON_VI={
 'ATTESTATION_OUTER_HASH_MISMATCH':'Hash bao ngoài bằng chứng không khớp.',
 'SIGNED_PAYLOAD_DIGEST_MISMATCH':'Nội dung hiện tại không còn khớp nội dung đã ký.',
 'CERTIFICATE_NOT_TRUSTED':'Chứng thư ký không nằm trong danh sách tin cậy.',
 'CERTIFICATE_SIGNATURE_INVALID':'Chữ ký chứng thư không hợp lệ.',
 'DPAPI_VERIFICATION_KEY_CONTEXT_REQUIRED':'Thiếu ngữ cảnh DPAPI cục bộ để xác minh.',
 'RUN_ID_REPLAY_OR_MISSING':'run_id bị thiếu hoặc đã được sử dụng.',
 'NONCE_REPLAY_OR_INVALID':'nonce bị thiếu, sai hoặc đã được sử dụng.',
 'MIXED_PACKAGE_VERSION':'Bằng chứng thuộc phiên bản gói khác.',
 'PACKAGE_MANIFEST_DIGEST_MISMATCH':'Digest release manifest không khớp.',
 'COMPLETE_4X3_CRASH_MATRIX_REQUIRED':'Chưa đủ ma trận 4 effect × 3 crash window.',
 'WINDOWS_TARGET_OBSERVER_REQUIRED':'Thiếu bằng chứng Windows Target Observer.',
 'REAL_CODEX_EFFECT_REQUIRED':'Thiếu bằng chứng Real Codex Effect.',
 'STALE_OR_INVALID_TIME':'Bằng chứng quá cũ hoặc thời gian không hợp lệ.'}
def utcnow():return datetime.now(timezone.utc).isoformat()
def sha(v:bytes|str):
 if isinstance(v,str):v=v.encode()
 return hashlib.sha256(v).hexdigest()
def sanitize(obj:Any)->Any:
 if isinstance(obj,dict):
  out={}
  for k,v in obj.items():
   lk=str(k).lower()
   if lk in FORBIDDEN_KEYS or any(x in lk for x in ('token','password','secret','credential')):continue
   out[k]=sanitize(v)
  return out
 if isinstance(obj,list):return [sanitize(x) for x in obj]
 if isinstance(obj,str):
  s=re.sub(r'(?i)bearer\s+[A-Za-z0-9._~+\-/=]{6,}','Bearer <REDACTED>',obj)
  if '@' in s:return '<IDENTITY_REDACTED>'
  return s
 return obj
def export_bundle(observer:dict[str,Any],real_effect:dict[str,Any],promotion:dict[str,Any])->dict[str,Any]:
 body={'product':PRODUCT,'version':VERSION,'schema_version':1,'generated_utc':utcnow(),'observer':sanitize(observer),'real_effect':sanitize(real_effect),'promotion':sanitize(promotion),'privacy':{'raw_credentials':False,'raw_account_identity':False,'raw_hostname':False,'raw_command_line':False,'raw_environment':False,'private_signing_material_exported':False}}
 raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();body['bundle_sha256']=sha(raw);return body
def verify_bundle(bundle:dict[str,Any],expected_version:str=VERSION)->dict[str,Any]:
 reasons=[];raw={k:v for k,v in bundle.items() if k!='bundle_sha256'};digest=sha(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
 if bundle.get('bundle_sha256')!=digest:reasons.append('BUNDLE_HASH_MISMATCH')
 if bundle.get('version')!=expected_version:reasons.append('MIXED_PACKAGE_VERSION')
 text=json.dumps(bundle,ensure_ascii=False).lower()
 if any('"'+k+'"' in text for k in FORBIDDEN_KEYS):reasons.append('PRIVACY_FORBIDDEN_FIELD')
 return {'valid':not reasons,'reasons':reasons,'bundle_sha256':bundle.get('bundle_sha256',''),'version':bundle.get('version'),'production_score_eligible':False}
def explain_promotion(promotion:dict[str,Any])->dict[str,Any]:
 eligible=bool(promotion.get('production_score_promotion_eligible'));reasons=list(promotion.get('reasons') or [])
 lines=[]
 if eligible:lines.append('Bằng chứng đã vượt qua promotion gate về tính toàn vẹn và điều kiện kỹ thuật; việc thay đổi điểm production vẫn thuộc bước auditor riêng, không tự động chứng nhận sản phẩm.')
 else:
  lines.append('Chưa đủ điều kiện promotion production evidence.')
  for r in reasons[:20]:
   base=r
   for prefix in ('OBSERVER_','REAL_','SIGNATURE_'):
    if base.startswith(prefix):base=base[len(prefix):]
   lines.append('• '+REASON_VI.get(base,'Bị chặn bởi gate: '+base))
 return {'product':PRODUCT,'version':VERSION,'suite':'PROMOTION_DECISION_EXPLANATION_VI','generated_utc':utcnow(),'eligible':eligible,'headline':'ĐỦ ĐIỀU KIỆN EVIDENCE' if eligible else 'CHƯA ĐỦ ĐIỀU KIỆN','lines':lines,'automatic_production_certification':False}
def synthetic_proof():
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 bad={'access_token':'SECRET','account':'person@example.invalid','safe':'ok','message':'Bearer ABCDEFGHIJK'};b=export_bundle(bad,bad,{'production_score_promotion_eligible':False,'reasons':['REAL_CERTIFICATE_NOT_TRUSTED']});raw=json.dumps(b,ensure_ascii=False)
 add('secret_fields_removed','SECRET' not in raw and 'person@example.invalid' not in raw)
 add('bearer_redacted','ABCDEFGHIJK' not in raw)
 add('bundle_hash_valid',verify_bundle(b)['valid'])
 t=json.loads(json.dumps(b));t['observer']['safe']='tampered';add('tamper_rejected',not verify_bundle(t)['valid'])
 e=explain_promotion({'production_score_promotion_eligible':False,'reasons':['REAL_CERTIFICATE_NOT_TRUSTED','COMPLETE_4X3_CRASH_MATRIX_REQUIRED']});add('vietnamese_explanation','Chứng thư' in '\n'.join(e['lines']) and '4 effect' in '\n'.join(e['lines']))
 add('no_auto_certification',e['automatic_production_certification'] is False)
 passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'ATTESTATION_EXCHANGE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','verify','explain'),default='proof');ap.add_argument('--input');ap.add_argument('--output');a=ap.parse_args()
 if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
 else:
  if not a.input:raise SystemExit('--input required');o=json.loads(Path(a.input).read_text('utf-8'));out=verify_bundle(o) if a.mode=='verify' else explain_promotion(o);rc=0 if (out.get('valid',True)) else 2
 if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
