#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.74'; PRODUCT='HMS-AI-ROUTER'; COCKPIT_BASELINE='1.3.27'; TARGET_PACKAGE_VERSION='25.72'
HEX64=re.compile(r'^[0-9a-f]{64}$')
CASE_IDS=(
 'FOREIGN_PORT_AUTO_REBIND','ACCOUNT_OCCUPANCY_GUARD','CLIENT_AUTH_API_SERVICE_SPLIT',
 'OFFICIAL_ACCOUNT_USAGE_CONTINUITY','WEBSOCKET_PREFERENCE_PERSISTENCE','BOUNDED_BACKUP_ROLLBACK_NTFS','STREAM_IDENTITY_ISOLATION')
FORBIDDEN_KEYS=re.compile(r'(access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|cookie|password|private[_-]?(key|material)|credential[_-]?(payload|value)|account[_-]?(email|identity)|command[_-]?line|environment|prompt[_-]?payload|response[_-]?payload)',re.I)
SAFE_FALSE_FLAGS={'raw_account_id_exported','credential_payload_exported','prompt_payload_exported','response_payload_exported','command_line_exported','environment_exported','private_material_exported'}

def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def _privacy_safe(obj:Any)->bool:
    if isinstance(obj,dict):
        for k,v in obj.items():
            ks=str(k)
            if ks in SAFE_FALSE_FLAGS and v is False:continue
            if FORBIDDEN_KEYS.search(ks):return False
            if not _privacy_safe(v):return False
    elif isinstance(obj,list):return all(_privacy_safe(x) for x in obj)
    return True

def _packet_hash(packet:dict[str,Any])->str:
    return sha(stable({k:v for k,v in packet.items() if k!='packet_sha256'}))

def verify_packet_chain(packets:list[dict[str,Any]])->dict[str,Any]:
    prev='0'*64;reasons=[]
    for i,p in enumerate(packets,1):
        if int(p.get('packet_seq') or 0)!=i:reasons.append('PACKET_SEQUENCE_INVALID')
        if p.get('prev_packet_sha256')!=prev:reasons.append('PACKET_PREVIOUS_LINK_INVALID')
        if p.get('packet_sha256')!=_packet_hash(p):reasons.append('PACKET_HASH_INVALID')
        prev=str(p.get('packet_sha256') or '')
    return {'valid':not reasons,'reasons':sorted(set(reasons)),'tail_sha256':prev,'packet_count':len(packets)}

def build_review_packet(*,raw_reports:list[dict[str,Any]],import_review:dict[str,Any],ledger_entries:list[dict[str,Any]],baseline_open:dict[str,Any],
                        baseline_final:dict[str,Any],target_package_zip_sha256:str,target_manifest_sha256:str,trust_snapshot_sha256:str,
                        previous_packets:list[dict[str,Any]]|None=None)->dict[str,Any]:
    reasons=[];previous=list(previous_packets or []);chain=verify_packet_chain(previous)
    if not chain['valid']:reasons.append('PREVIOUS_PACKET_CHAIN_INVALID')
    for d,name in ((target_package_zip_sha256,'TARGET_PACKAGE_ZIP'),(target_manifest_sha256,'TARGET_MANIFEST'),(trust_snapshot_sha256,'TRUST_SNAPSHOT')):
        if not HEX64.fullmatch(str(d).lower()):reasons.append(name+'_DIGEST_INVALID')
    if import_review.get('review_ready_for_promotion_auditor') is not True:reasons.append('IMPORT_REVIEW_NOT_READY')
    if import_review.get('accepted_case_count')!=7 or import_review.get('quarantined_count')!=0:reasons.append('SEVEN_CASE_IMPORT_NOT_CLEAN')
    if import_review.get('read_only_import') is not True or import_review.get('target_effects_executed_during_import') is not False:reasons.append('IMPORT_BOUNDARY_UNSAFE')
    if import_review.get('production_score_promotion_eligible') is not False:reasons.append('IMPORT_MUST_NOT_PROMOTE_SCORE')
    dual=import_review.get('dual_review') or {}
    if dual.get('dual_review_complete') is not True or dual.get('promotion_eligible') is not True:reasons.append('DUAL_REVIEW_REQUIRED')
    if dual.get('production_score_mutation_authorized') is not False:reasons.append('LEDGER_SCORE_MUTATION_AUTHORITY_FORBIDDEN')
    for phase,w in (('PACKET_OPEN',baseline_open),('FINAL_DECISION',baseline_final)):
        if w.get('status')!='CURRENT' or w.get('promotion_frozen') is True:reasons.append(phase+'_BASELINE_STALE')
        if str(w.get('observed_version') or '')!=COCKPIT_BASELINE:reasons.append(phase+'_BASELINE_MISMATCH')
    if len(raw_reports)!=7:reasons.append('RAW_REPORT_COUNT_MUST_BE_SEVEN')
    by_case={};report_rows=[]
    for r in raw_reports:
        cid=str(r.get('case_id') or '')
        rd=sha(stable(r));by_case.setdefault(cid,[]).append(rd)
        report_rows.append({'case_id':cid,'report_sha256':rd,'generated_utc':r.get('generated_utc'),
                            'certificate_sha256':(r.get('signature_envelope') or {}).get('certificate_sha256'),
                            'evidence_classes':sorted(set(r.get('evidence_classes') or [])),
                            'runtime_attestation_verified':r.get('runtime_attestation_verified') is True,
                            'idempotency_witness_verified':r.get('idempotency_witness_verified') is True,
                            'raw_report_embedded':False})
    if any(len(by_case.get(cid,[]))!=1 for cid in CASE_IDS) or set(by_case)!=set(CASE_IDS):reasons.append('SEVEN_CASE_RAW_REPORT_MATRIX_INVALID')
    if not _privacy_safe(report_rows):reasons.append('PACKET_METADATA_PRIVACY_VIOLATION')
    # Reviewer identities must remain pseudonymous. The packet stores only ledger reviewer refs and entry hashes.
    reviewer_rows=[]
    for e in ledger_entries:
        if e.get('decision') not in {'APPROVE','REJECT','INVALIDATE'}:continue
        ref=str(e.get('reviewer_ref') or '')
        if not ref.startswith('ref-'):reasons.append('NON_PSEUDONYMOUS_REVIEWER_REF')
        reviewer_rows.append({'seq':e.get('seq'),'decision':e.get('decision'),'reviewer_ref':ref,'entry_sha256':e.get('entry_sha256'),
                              'supersedes_sha256':e.get('supersedes_sha256'),'reason_code':e.get('reason_code')})
    provenance={
      'raw_evidence_mode':'IMMUTABLE_REFERENCED_BY_DIGEST_ONLY','raw_evidence_modified':False,'raw_evidence_embedded':False,
      'import_review_digest':import_review.get('review_digest'),'evidence_bundle_sha256':import_review.get('evidence_bundle_sha256'),
      'target_package_version':TARGET_PACKAGE_VERSION,'target_package_zip_sha256':target_package_zip_sha256,
      'target_manifest_sha256':target_manifest_sha256,'trust_snapshot_sha256':trust_snapshot_sha256,
      'cockpit_baseline':COCKPIT_BASELINE,'baseline_open_digest':baseline_open.get('watch_digest'),'baseline_final_digest':baseline_final.get('watch_digest')}
    if not all(HEX64.fullmatch(str(provenance.get(k) or '').lower()) for k in ('target_package_zip_sha256','target_manifest_sha256','trust_snapshot_sha256')):reasons.append('PROVENANCE_DIGEST_INVALID')
    packet={
      'product':PRODUCT,'version':VERSION,'suite':'EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET','generated_utc':utcnow(),
      'packet_id':str(uuid.uuid4()),'packet_seq':len(previous)+1,'prev_packet_sha256':chain['tail_sha256'],
      'packet_state':'READY_FOR_HUMAN_REVIEW' if not reasons else 'BLOCKED','cockpit_baseline':COCKPIT_BASELINE,
      'provenance':provenance,'case_count':len(report_rows),'case_reports':sorted(report_rows,key=lambda x:x['case_id']),
      'review_ledger':{'entry_count':len(reviewer_rows),'tail_sha256':dual.get('ledger_tail_sha256'),'entries':reviewer_rows,
                       'dual_review_complete':dual.get('dual_review_complete') is True,'promotion_eligible':dual.get('promotion_eligible') is True},
      'baseline_checkpoints':{
        'packet_open':{k:baseline_open.get(k) for k in ('status','observed_version','required_baseline','promotion_frozen','watch_digest')},
        'final_human_decision':{k:baseline_final.get(k) for k in ('status','observed_version','required_baseline','promotion_frozen','watch_digest')}},
      'immutable_raw_evidence':True,'derived_metadata_only':True,'review_packet_export_safe':not reasons and _privacy_safe({'cases':report_rows,'reviewers':reviewer_rows}),
      'reasons':sorted(set(reasons)),'automatic_upstream_merge':False,'automatic_production_certification':False,
      'production_score_mutation_authorized':False,'production_score_promotion_eligible':False,'codex_only_scope':True,'antigravity_scope_imported':False}
    packet['capability_binding_sha256']=sha(stable({'case_ids':list(CASE_IDS),'cockpit_baseline':COCKPIT_BASELINE,'target_package_version':TARGET_PACKAGE_VERSION,
                                                    'target_manifest_sha256':target_manifest_sha256,'reports':[x['report_sha256'] for x in packet['case_reports']]}))
    packet['packet_sha256']=_packet_hash(packet)
    return packet

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    reports=[]
    for i,cid in enumerate(CASE_IDS):
        reports.append({'case_id':cid,'generated_utc':utcnow(),'signature_envelope':{'certificate_sha256':sha('cert')},
                        'evidence_classes':['WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'],'runtime_attestation_verified':True,
                        'idempotency_witness_verified':True,'raw_account_id_exported':False,'credential_payload_exported':False})
    dual={'dual_review_complete':True,'promotion_eligible':True,'production_score_mutation_authorized':False,'ledger_tail_sha256':'9'*64}
    review={'review_ready_for_promotion_auditor':True,'accepted_case_count':7,'quarantined_count':0,'read_only_import':True,
            'target_effects_executed_during_import':False,'production_score_promotion_eligible':False,'dual_review':dual,
            'review_digest':'8'*64,'evidence_bundle_sha256':'7'*64}
    ledger=[{'seq':1,'decision':'APPROVE','reviewer_ref':'ref-a','entry_sha256':'1'*64,'supersedes_sha256':None,'reason_code':'OK'},
            {'seq':2,'decision':'APPROVE','reviewer_ref':'ref-b','entry_sha256':'2'*64,'supersedes_sha256':None,'reason_code':'OK'}]
    watch={'status':'CURRENT','observed_version':COCKPIT_BASELINE,'required_baseline':COCKPIT_BASELINE,'promotion_frozen':False,'watch_digest':'6'*64}
    p=build_review_packet(raw_reports=reports,import_review=review,ledger_entries=ledger,baseline_open=watch,baseline_final=watch,
                          target_package_zip_sha256='a'*64,target_manifest_sha256='b'*64,trust_snapshot_sha256='c'*64)
    add('packet_ready_for_human_review',p['packet_state']=='READY_FOR_HUMAN_REVIEW' and not p['reasons'],p['reasons'])
    add('raw_evidence_digest_only',p['immutable_raw_evidence'] and p['derived_metadata_only'] and all(not x['raw_report_embedded'] for x in p['case_reports']))
    add('seven_case_matrix_bound',p['case_count']==7 and {x['case_id'] for x in p['case_reports']}==set(CASE_IDS))
    add('reviewers_pseudonymous',all(str(x['reviewer_ref']).startswith('ref-') for x in p['review_ledger']['entries']))
    add('packet_hash_present',HEX64.fullmatch(p['packet_sha256']) is not None and HEX64.fullmatch(p['capability_binding_sha256']) is not None)
    add('packet_never_promotes_score',not p['production_score_promotion_eligible'] and not p['production_score_mutation_authorized'] and not p['automatic_production_certification'])
    chain=verify_packet_chain([p]);add('single_packet_chain_valid',chain['valid'],chain)
    p2=build_review_packet(raw_reports=reports,import_review=review,ledger_entries=ledger,baseline_open=watch,baseline_final=watch,
                           target_package_zip_sha256='a'*64,target_manifest_sha256='b'*64,trust_snapshot_sha256='c'*64,previous_packets=[p])
    add('packet_chain_append_only',verify_packet_chain([p,p2])['valid'] and p2['prev_packet_sha256']==p['packet_sha256'])
    stale=dict(watch);stale.update({'status':'NEWER','observed_version':'1.3.28','promotion_frozen':True})
    blocked=build_review_packet(raw_reports=reports,import_review=review,ledger_entries=ledger,baseline_open=watch,baseline_final=stale,
                                target_package_zip_sha256='a'*64,target_manifest_sha256='b'*64,trust_snapshot_sha256='c'*64)
    add('baseline_drift_blocks_packet',blocked['packet_state']=='BLOCKED' and 'FINAL_DECISION_BASELINE_STALE' in blocked['reasons'])
    leaked=json.loads(json.dumps(reports));leaked[0]['account_email']='secret@example.com'
    bad=build_review_packet(raw_reports=leaked,import_review=review,ledger_entries=ledger,baseline_open=watch,baseline_final=watch,
                            target_package_zip_sha256='a'*64,target_manifest_sha256='b'*64,trust_snapshot_sha256='c'*64)
    # Raw evidence is never embedded; privacy is enforced on derived packet fields, so raw private fields do not propagate.
    add('raw_private_fields_not_propagated',bad['review_packet_export_safe'] and 'secret@example.com' not in json.dumps(bad,ensure_ascii=False))
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':PRODUCT,'version':VERSION,'suite':'EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET_PROOF','generated_utc':utcnow(),
            'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,
            'synthetic_control_plane_only':True,'windows_runtime_certified':False,'production_score_promotion_eligible':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();out=synthetic_proof();txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
