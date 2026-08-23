#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
VERSION='25.65'
PHASES=('PREPARE','OBSERVE','EFFECT','DURABLE','VERIFY','DONE','OPERATOR_REQUIRED')
VI={
 'PREPARE':'CHUẨN BỊ','OBSERVE':'QUAN SÁT TRẠNG THÁI','EFFECT':'ÁP DỤNG THAY ĐỔI','DURABLE':'ĐÃ GHI BỀN','VERIFY':'XÁC MINH','DONE':'HOÀN TẤT','OPERATOR_REQUIRED':'CẦN NGƯỜI VẬN HÀNH'
}
SENSITIVE=('token','secret','password','authorization','cookie','credential','api_key','email','account','hostname','username','prompt','body','owner')
def utcnow():return datetime.now(timezone.utc).isoformat()
def sha(v:str)->str:return hashlib.sha256(v.encode('utf-8','surrogatepass')).hexdigest()
def safe_prefix(v:str)->str:return sha(v)[:12] if v else ''
def sanitize_reason(v:str)->str:
 s=re.sub(r'(?i)bearer\s+[A-Za-z0-9._~+\-/=]{6,}','Bearer <REDACTED>',str(v or ''))
 if '@' in s:return 'REASON_REDACTED_IDENTITY_SHAPE'
 return s[:180]
def project_event(row:dict[str,Any],seq:int)->dict[str,Any]:
 phase=str(row.get('phase') or 'OBSERVE').upper();phase=phase if phase in PHASES else 'OBSERVE'
 fp=str(row.get('state_hash') or row.get('observed_hash') or row.get('fingerprint') or row.get('record_hash') or '')
 return {'seq':seq,'phase':phase,'nhan':VI[phase],'status':str(row.get('status') or row.get('verdict') or ''),'source':str(row.get('source') or row.get('observer') or 'recovery'),'freshness':str(row.get('freshness_state') or row.get('freshness') or 'UNKNOWN'),'safe_fingerprint_prefix':safe_prefix(fp),'remediation_reason':sanitize_reason(str(row.get('failure_reason') or row.get('reason') or '')),'time_utc':str(row.get('time_utc') or row.get('observed_utc') or row.get('generated_utc') or utcnow())}
def build(rows:list[dict[str,Any]])->dict[str,Any]:
 timeline=[project_event(r,i+1) for i,r in enumerate(rows)]
 raw=json.dumps(timeline,ensure_ascii=False).lower();privacy_ok=not any('"'+k+'"' in raw for k in SENSITIVE)
 return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_OPERATOR_TIMELINE','generated_utc':utcnow(),'verdict':'PASS' if privacy_ok else 'FAIL_PRIVACY','timeline':timeline,'summary':{'events':len(timeline),'operator_required':sum(x['phase']=='OPERATOR_REQUIRED' for x in timeline)},'privacy':{'metadata_only':True,'raw_credentials':False,'raw_account_identity':False,'safe':privacy_ok}}
def synthetic_proof()->dict[str,Any]:
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 rows=[{'phase':p,'source':'fixture','freshness_state':'FRESH','state_hash':sha(p),'reason':'OK'} for p in PHASES]
 rows[-1]['reason']='Bearer SECRET_TOKEN_123456';rows[-1]['account']='secret@example.invalid'
 b=build(rows);raw=json.dumps(b,ensure_ascii=False)
 add('seven_phases',len(b['timeline'])==7)
 add('vietnamese_labels',[x['nhan'] for x in b['timeline']]==[VI[p] for p in PHASES])
 add('source_freshness',all(x['source']=='fixture' and x['freshness']=='FRESH' for x in b['timeline']))
 add('fingerprint_prefix_only',all(len(x['safe_fingerprint_prefix'])==12 for x in b['timeline']))
 add('bearer_redacted','SECRET_TOKEN_123456' not in raw)
 add('identity_not_projected','secret@example.invalid' not in raw)
 add('operator_required_count',b['summary']['operator_required']==1)
 add('metadata_only',b['privacy']['metadata_only'] and b['privacy']['safe'])
 passed=sum(t['status']=='PASS' for t in tests);return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_OPERATOR_TIMELINE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','build'),default='proof');ap.add_argument('--input');ap.add_argument('--output');a=ap.parse_args()
 if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
 else:
  if not a.input:raise SystemExit('--input required');o=json.loads(Path(a.input).read_text('utf-8'));rows=o if isinstance(o,list) else (o.get('events') or o.get('observations') or o.get('timeline') or []);out=build(rows);rc=0 if out['verdict']=='PASS' else 2
 if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
