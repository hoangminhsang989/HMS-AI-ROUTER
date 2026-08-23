#!/usr/bin/env python3
from __future__ import annotations
import argparse,contextlib,hashlib,json,os,re,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
VERSION='25.69';PRODUCT='HMS-AI-ROUTER';HEX64=re.compile(r'^[0-9a-f]{64}$');DECISIONS={'APPROVE','REJECT','INVALIDATE'}
def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str):
 if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
 return hashlib.sha256(v).hexdigest()
def safe_ref(v:str):return 'ref-'+sha(v)[:24]
def _entry_hash(e:dict[str,Any])->str:return sha(stable({k:v for k,v in e.items() if k!='entry_sha256'}))

def verify_chain(entries:list[dict[str,Any]])->dict[str,Any]:
 prev='0'*64;reasons=[]
 for i,e in enumerate(entries,1):
  if int(e.get('seq') or 0)!=i:reasons.append('SEQUENCE_INVALID')
  if e.get('prev_entry_sha256')!=prev:reasons.append('PREVIOUS_LINK_INVALID')
  if e.get('entry_sha256')!=_entry_hash(e):reasons.append('ENTRY_HASH_INVALID')
  prev=str(e.get('entry_sha256') or '')
 return {'valid':not reasons,'reasons':sorted(set(reasons)),'tail_sha256':prev,'entries':len(entries)}

def new_entry(entries:list[dict[str,Any]],*,decision:str,campaign_digest:str,evidence_bundle_sha256:str,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str,reviewer_ref:str,reason_code:str,supersedes_sha256:str='')->dict[str,Any]:
 chain=verify_chain(entries)
 if not chain['valid']:raise ValueError('LEDGER_CHAIN_INVALID')
 if decision not in DECISIONS:raise ValueError('DECISION_INVALID')
 if not str(reviewer_ref).startswith('ref-'):raise ValueError('PSEUDONYMOUS_REVIEWER_REF_REQUIRED')
 for v in (campaign_digest,evidence_bundle_sha256,manifest_sha256,trust_snapshot_sha256):
  if not HEX64.fullmatch(str(v).lower()):raise ValueError('DIGEST_INVALID')
 if decision=='INVALIDATE' and not supersedes_sha256:raise ValueError('INVALIDATE_REQUIRES_SUPERSEDES')
 e={'product':PRODUCT,'version':VERSION,'seq':len(entries)+1,'decision':decision,'campaign_digest':campaign_digest,'evidence_bundle_sha256':evidence_bundle_sha256,'package_version':package_version,'manifest_sha256':manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,'reviewer_ref':reviewer_ref,'reason_code':str(reason_code)[:96],'supersedes_sha256':supersedes_sha256 or None,'prev_entry_sha256':chain['tail_sha256'],'decided_utc':utcnow(),'automatic_production_certification':False,'production_score_mutation_authorized':False}
 e['entry_sha256']=_entry_hash(e);return e

@contextlib.contextmanager
def _locked_append(path:Path):
 path.parent.mkdir(parents=True,exist_ok=True);f=path.open('a+b')
 try:
  if os.name=='nt':
   import msvcrt;f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
  else:
   import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX)
  yield f
 finally:
  try:
   if os.name=='nt':
    import msvcrt;f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:
    import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_UN)
  except Exception:pass
  f.close()

def load_jsonl(path:Path)->list[dict[str,Any]]:
 if not path.exists():return []
 out=[]
 for line in path.read_text('utf-8').splitlines():
  if line.strip():out.append(json.loads(line))
 return out

def append_jsonl(path:Path,entry:dict[str,Any],*,expected_tail_sha256:str)->dict[str,Any]:
 with _locked_append(path) as f:
  f.seek(0);raw=f.read().decode('utf-8');entries=[json.loads(x) for x in raw.splitlines() if x.strip()];chain=verify_chain(entries)
  if not chain['valid']:raise ValueError('LEDGER_CHAIN_INVALID')
  if chain['tail_sha256']!=expected_tail_sha256:raise ValueError('LEDGER_CONCURRENT_APPEND_DETECTED')
  if entry.get('prev_entry_sha256')!=chain['tail_sha256'] or entry.get('entry_sha256')!=_entry_hash(entry):raise ValueError('ENTRY_NOT_BOUND_TO_CURRENT_TAIL')
  f.seek(0,os.SEEK_END);f.write((json.dumps(entry,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8'));f.flush();os.fsync(f.fileno())
 return {'appended':True,'entry_sha256':entry['entry_sha256'],'seq':entry['seq']}

def evaluate_dual_review(entries:list[dict[str,Any]],*,campaign_digest:str,evidence_bundle_sha256:str,package_version:str,manifest_sha256:str,trust_snapshot_sha256:str)->dict[str,Any]:
 chain=verify_chain(entries);reasons=[]
 if not chain['valid']:reasons.append('LEDGER_CHAIN_INVALID')
 relevant=[e for e in entries if e.get('campaign_digest')==campaign_digest and e.get('evidence_bundle_sha256')==evidence_bundle_sha256]
 # Any INVALIDATE that supersedes one of the relevant approvals starts a new review epoch.
 invalidated={str(e.get('supersedes_sha256') or '') for e in relevant if e.get('decision')=='INVALIDATE'}
 live=[e for e in relevant if e.get('entry_sha256') not in invalidated and e.get('decision') in {'APPROVE','REJECT'}]
 if any(e.get('decision')=='REJECT' for e in live):reasons.append('HUMAN_REVIEW_REJECTED')
 approvals=[e for e in live if e.get('decision')=='APPROVE']
 reviewers={e.get('reviewer_ref') for e in approvals}
 if len(reviewers)<2:reasons.append('DUAL_DISTINCT_REVIEW_REQUIRED')
 for e in approvals:
  if e.get('package_version')!=package_version:reasons.append('PACKAGE_SUPERSEDED_REVIEW_STALE')
  if e.get('manifest_sha256')!=manifest_sha256:reasons.append('MANIFEST_CHANGED_REVIEW_STALE')
  if e.get('trust_snapshot_sha256')!=trust_snapshot_sha256:reasons.append('TRUST_SNAPSHOT_CHANGED_REVIEW_STALE')
 eligible=not reasons and len(approvals)>=2
 return {'product':PRODUCT,'version':VERSION,'verdict':'PROMOTION_ELIGIBLE_FOR_SEPARATE_SCORE_AUDIT' if eligible else 'NO_PROMOTION','promotion_eligible':eligible,'dual_review_complete':len(reviewers)>=2,'reviewer_count':len(reviewers),'approval_count':len(approvals),'reasons':sorted(set(reasons)),'ledger_tail_sha256':chain['tail_sha256'],'automatic_production_certification':False,'production_score_mutation_authorized':False}

def re_evaluate(entries:list[dict[str,Any]],*,current_package_version:str,current_manifest_sha256:str,current_trust_snapshot_sha256:str,certificate_revoked:bool=False,evidence_stale:bool=False)->dict[str,Any]:
 reasons=[]
 if certificate_revoked:reasons.append('CERTIFICATE_REVOKED')
 if evidence_stale:reasons.append('EVIDENCE_AGED_BEYOND_POLICY')
 approvals=[e for e in entries if e.get('decision')=='APPROVE']
 if approvals:
  if any(e.get('package_version')!=current_package_version for e in approvals):reasons.append('PACKAGE_SUPERSEDED')
  if any(e.get('manifest_sha256')!=current_manifest_sha256 for e in approvals):reasons.append('MANIFEST_CHANGED')
  if any(e.get('trust_snapshot_sha256')!=current_trust_snapshot_sha256 for e in approvals):reasons.append('TRUST_SNAPSHOT_CHANGED')
 return {'requires_superseding_entry':bool(reasons),'reasons':sorted(set(reasons)),'historical_entries_deleted':False,'automatic_mutation':False}

def synthetic_proof()->dict[str,Any]:
 tests=[]
 def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 camp='a'*64;ev='b'*64;man='c'*64;trust='d'*64;entries=[]
 e1=new_entry(entries,decision='APPROVE',campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust,reviewer_ref='ref-reviewer-a',reason_code='REVIEW_OK');entries.append(e1)
 r1=evaluate_dual_review(entries,campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust);add('one_review_not_enough',not r1['promotion_eligible'] and 'DUAL_DISTINCT_REVIEW_REQUIRED' in r1['reasons'])
 e2=new_entry(entries,decision='APPROVE',campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust,reviewer_ref='ref-reviewer-b',reason_code='SECOND_REVIEW_OK');entries.append(e2)
 r2=evaluate_dual_review(entries,campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust);add('dual_review_eligible',r2['promotion_eligible'] and r2['reviewer_count']==2,r2)
 add('eligibility_not_score_mutation',r2['production_score_mutation_authorized'] is False and r2['automatic_production_certification'] is False)
 add('chain_valid',verify_chain(entries)['valid'])
 tam=json.loads(json.dumps(entries));tam[0]['reason_code']='TAMPER';add('tamper_detected',not verify_chain(tam)['valid'])
 reval=re_evaluate(entries,current_package_version=VERSION,current_manifest_sha256=man,current_trust_snapshot_sha256='e'*64,certificate_revoked=True);add('revocation_or_trust_change_requires_supersede',reval['requires_superseding_entry'] and not reval['historical_entries_deleted'])
 inv=new_entry(entries,decision='INVALIDATE',campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust,reviewer_ref='ref-reviewer-c',reason_code='CERT_REVOKED',supersedes_sha256=e1['entry_sha256']);entries.append(inv);r3=evaluate_dual_review(entries,campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust);add('invalidation_removes_prior_approval',not r3['promotion_eligible'])
 with tempfile.TemporaryDirectory(prefix='hms-ledger-proof-') as td:
  p=Path(td)/'ledger.jsonl';empty_tail='0'*64;a=new_entry([],decision='APPROVE',campaign_digest=camp,evidence_bundle_sha256=ev,package_version=VERSION,manifest_sha256=man,trust_snapshot_sha256=trust,reviewer_ref='ref-r1',reason_code='OK');append_jsonl(p,a,expected_tail_sha256=empty_tail);loaded=load_jsonl(p);add('append_only_jsonl_roundtrip',len(loaded)==1 and verify_chain(loaded)['valid'])
  try:append_jsonl(p,a,expected_tail_sha256=empty_tail);ok=False
  except ValueError as ex:ok='CONCURRENT_APPEND' in str(ex)
  add('concurrent_tail_guard',ok)
 raw=json.dumps(entries,ensure_ascii=False).lower();add('pseudonymous_reviewers_only','@' not in raw and 'reviewer_ref' in raw)
 add('historical_append_only',all('entry_sha256' in x and 'prev_entry_sha256' in x for x in entries))
 passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'PROMOTION_DECISION_LEDGER_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False,'automatic_production_certification':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();d=synthetic_proof();txt=json.dumps(d,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt+'\n','utf-8')
 print(txt);return 0 if d['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
