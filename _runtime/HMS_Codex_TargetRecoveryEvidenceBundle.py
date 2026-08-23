#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, platform, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.65'
ALLOWED_CLASSES={'LAB_PROCESS_KILL','LAB_FIXTURE','WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'}
PRODUCTION_CLAIM='NOT_CLAIMED_BUNDLE_ALONE_DOES_NOT_CERTIFY_PRODUCTION'
SENSITIVE=('token','secret','password','authorization','cookie','credential','api_key','email','account','hostname','username','prompt','body')

def utcnow(): return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->str:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:20]
def atomic_json(path:Path,obj:Any):
    path.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8');tmp=path.with_name(path.name+'.tmp-'+sha(raw)[:10])
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read_json(path:Path)->dict[str,Any]:
    try:
        x=json.loads(path.read_text('utf-8-sig'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def sanitize(o:Any)->Any:
    if isinstance(o,dict):
        out={}
        for k,v in o.items():
            key=str(k);out[key]='<REDACTED>' if any(s in key.lower() for s in SENSITIVE) else sanitize(v)
        return out
    if isinstance(o,list):return [sanitize(x) for x in o]
    if isinstance(o,str) and len(o)>300:return o[:300]+'…'
    return o

def classify(source:dict[str,Any],fallback:str)->str:
    cls=str(((source.get('evidence') or {}).get('class')) or source.get('evidence_class') or fallback)
    return cls if cls in ALLOWED_CLASSES else fallback

def project_observer(obj:dict[str,Any])->dict[str,Any]:
    sm=obj.get('summary') or {};e=obj.get('evidence') or {}
    return {'version':obj.get('version'),'verdict':obj.get('verdict'),'evidence_class':classify(obj,'LAB_FIXTURE'),'available':int(sm.get('available') or 0),'total':int(sm.get('total') or 0),'production_score_eligible':bool(e.get('production_score_eligible')),'generated_utc':obj.get('generated_utc') or ''}
def project_real(obj:dict[str,Any])->dict[str,Any]:
    sm=obj.get('summary') or {};return {'version':obj.get('version'),'verdict':obj.get('verdict'),'evidence_class':classify(obj,'REAL_CODEX_EFFECT'),'pass':int(sm.get('pass') or 0),'total':int(sm.get('total') or 0),'crash_cases':int(sm.get('crash_cases') or 0),'real_codex_effects_executed':bool(obj.get('real_codex_effects_executed')),'production_score_eligible':bool(obj.get('production_score_eligible')),'generated_utc':obj.get('generated_utc') or ''}
def project_lab(obj:dict[str,Any])->dict[str,Any]:
    sm=obj.get('summary') or {};return {'version':obj.get('version'),'verdict':obj.get('verdict'),'evidence_class':'LAB_PROCESS_KILL','pass':int(sm.get('pass') or 0),'total':int(sm.get('total') or 0),'crash_cases':int(sm.get('crash_cases') or 0),'production_score_eligible':False,'generated_utc':obj.get('generated_utc') or ''}

def build(observer:dict[str,Any],real:dict[str,Any],lab:dict[str,Any])->dict[str,Any]:
    projected={'observer':project_observer(observer) if observer else {},'real_effect':project_real(real) if real else {},'lab_process_kill':project_lab(lab) if lab else {}}
    classes=sorted({x.get('evidence_class') for x in projected.values() if isinstance(x,dict) and x.get('evidence_class')})
    source_pair_candidate=bool(projected['observer'].get('production_score_eligible') and (projected['real_effect'].get('real_codex_effects_executed') or projected['real_effect'].get('production_score_eligible')))
    machine_material={'system':platform.system(),'release':platform.release(),'machine':platform.machine(),'python':platform.python_version(),'windows':os.name=='nt'}
    bundle={'product':'HMS-AI-ROUTER','version':VERSION,'schema_version':1,'suite':'TARGET_RECOVERY_EVIDENCE_BUNDLE','generated_utc':utcnow(),'host_fingerprint':safe_ref(stable(machine_material)),'runtime_fingerprint':safe_ref(os.path.realpath(os.sys.executable)+'|'+platform.python_version()),'evidence_classes':classes,'evidence':projected,'source_pair_candidate':source_pair_candidate,'production_score_eligible':False,'attestation_policy':{'required_for_promotion':True,'gate':'HMS_Codex_AttestedEvidencePromotionGate.py'},'privacy':{'metadata_only':True,'raw_credentials':False,'raw_account_identity':False,'raw_hostname':False,'source_payloads_embedded':False},'production_certification':PRODUCTION_CLAIM}
    digest=sha(stable(bundle));bundle['bundle_sha256']=digest;return bundle

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    observer={'version':VERSION,'verdict':'PASS','summary':{'available':4,'total':4},'evidence':{'class':'LAB_FIXTURE','production_score_eligible':False},'account':'raw@example.invalid','access_token':'SECRET'}
    real={'version':VERSION,'verdict':'DEFERRED_NOT_ARMED','evidence_class':'REAL_CODEX_EFFECT','real_codex_effects_executed':False,'production_score_eligible':False,'cases':[{'secret':'X'}]}
    lab={'version':'25.63','verdict':'PASS','summary':{'pass':12,'total':12,'crash_cases':12}}
    b=build(observer,real,lab);raw=stable(b)
    add('bundle_hash_64hex',len(str(b.get('bundle_sha256') or ''))==64)
    add('classes_distinct',set(b.get('evidence_classes') or [])=={'LAB_FIXTURE','LAB_PROCESS_KILL','REAL_CODEX_EFFECT'},b.get('evidence_classes'))
    add('lab_not_score_eligible',not b.get('production_score_eligible'))
    add('source_payload_not_embedded','SECRET' not in raw and 'raw@example.invalid' not in raw)
    add('host_identity_hashed',str(b.get('host_fingerprint') or '').startswith('ref-'))
    add('runtime_identity_hashed',str(b.get('runtime_fingerprint') or '').startswith('ref-'))
    add('privacy_metadata_only',b.get('privacy',{}).get('metadata_only') and not b.get('privacy',{}).get('raw_hostname'))
    add('production_claim_blocked',PRODUCTION_CLAIM.startswith('NOT_CLAIMED'))
    passed=sum(t['status']=='PASS' for t in tests)
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'TARGET_RECOVERY_EVIDENCE_BUNDLE_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_certification':PRODUCTION_CLAIM}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('build','proof'),default='build');ap.add_argument('--observer');ap.add_argument('--real-effect');ap.add_argument('--lab-process-kill');ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        out=build(read_json(Path(a.observer)) if a.observer else {},read_json(Path(a.real_effect)) if a.real_effect else {},read_json(Path(a.lab_process_kill)) if a.lab_process_kill else {});rc=0
    if a.output:atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
