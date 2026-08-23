#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

VERSION='25.73'; PRODUCT='HMS-AI-ROUTER'; TARGET_PACKAGE_VERSION='25.72'; COCKPIT_BASELINE='1.3.27'
HEX64=re.compile(r'^[0-9a-f]{64}$')
CASE_IDS=(
 'FOREIGN_PORT_AUTO_REBIND','ACCOUNT_OCCUPANCY_GUARD','CLIENT_AUTH_API_SERVICE_SPLIT',
 'OFFICIAL_ACCOUNT_USAGE_CONTINUITY','WEBSOCKET_PREFERENCE_PERSISTENCE','BOUNDED_BACKUP_ROLLBACK_NTFS','STREAM_IDENTITY_ISOLATION')
REQUIRED_CLASSES={'WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'}
FORBIDDEN_KEYS=re.compile(r'(access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|cookie|password|private[_-]?(key|material)|credential[_-]?(payload|value)|account[_-]?(email|identity)|command[_-]?line|environment|prompt[_-]?payload|response[_-]?payload)',re.I)
SAFE_FALSE_FLAGS={'raw_account_id_exported','credential_payload_exported','prompt_payload_exported','response_payload_exported','command_line_exported','environment_exported','private_material_exported'}

def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def _time(v:Any):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def _load(alias:str, filename:str):
    p=Path(__file__).with_name(filename);spec=importlib.util.spec_from_file_location(alias,p);m=importlib.util.module_from_spec(spec);sys.modules[alias]=m;spec.loader.exec_module(m);return m

def _forbidden(obj:Any)->bool:
    if isinstance(obj,dict):
        for k,v in obj.items():
            ks=str(k)
            if ks in SAFE_FALSE_FLAGS and v is False:continue
            if FORBIDDEN_KEYS.search(ks):return True
            if _forbidden(v):return True
    elif isinstance(obj,list):return any(_forbidden(x) for x in obj)
    return False

def verify_capture_report(report:dict[str,Any],*,expected_package_zip_sha256:str,expected_manifest_sha256:str,
                          trusted_certificate_sha256:set[str],seen_nonces:set[str],seen_run_ids:set[str],seen_digests:set[str],
                          max_age_hours:int=24)->dict[str,Any]:
    signer=_load('signer2573','HMS_Codex_WindowsAttestationSigner.py');reasons=[]
    cid=str(report.get('case_id') or '')
    if cid not in CASE_IDS:reasons.append('UNKNOWN_CASE_ID')
    if report.get('package_version')!=TARGET_PACKAGE_VERSION:reasons.append('TARGET_PACKAGE_VERSION_MISMATCH')
    if str(report.get('package_zip_sha256') or '').lower()!=str(expected_package_zip_sha256).lower():reasons.append('TARGET_PACKAGE_ZIP_DIGEST_MISMATCH')
    if str(report.get('package_manifest_sha256') or '').lower()!=str(expected_manifest_sha256).lower():reasons.append('TARGET_MANIFEST_DIGEST_MISMATCH')
    if report.get('cockpit_baseline')!=COCKPIT_BASELINE:reasons.append('COCKPIT_BASELINE_MISMATCH')
    if report.get('status')!='PASS':reasons.append('CASE_NOT_PASS')
    if not REQUIRED_CLASSES.issubset(set(report.get('evidence_classes') or [])):reasons.append('TARGET_EVIDENCE_CLASSES_REQUIRED')
    if report.get('runtime_attestation_verified') is not True:reasons.append('RUNTIME_ATTESTATION_REQUIRED')
    if report.get('idempotency_witness_verified') is not True:reasons.append('IDEMPOTENCY_WITNESS_REQUIRED')
    for f in SAFE_FALSE_FLAGS-{'private_material_exported'}:
        if report.get(f) is not False:reasons.append(f'{f.upper()}_MUST_BE_FALSE')
    if _forbidden(report):reasons.append('FORBIDDEN_PRIVATE_IDENTITY_OR_PAYLOAD_FIELD')
    run_id=str(report.get('run_id') or '');nonce=str(report.get('nonce') or '');digest=sha(stable(report))
    if not run_id or run_id in seen_run_ids:reasons.append('RUN_ID_REPLAY_OR_MISSING')
    if len(nonce)<32 or nonce in seen_nonces:reasons.append('NONCE_REPLAY_OR_INVALID')
    if digest in seen_digests:reasons.append('REPORT_DIGEST_REPLAY')
    t=_time(report.get('generated_utc'))
    now=datetime.now(timezone.utc)
    if not t or now-t>timedelta(hours=max_age_hours) or t-now>timedelta(minutes=5):reasons.append('REPORT_STALE_OR_TIME_INVALID')
    sv=signer.verify_signed_attestation(report,trusted_certificate_sha256=trusted_certificate_sha256)
    if not sv.get('valid'):reasons.extend('SIGNATURE_'+str(x) for x in (sv.get('reasons') or []))
    env=report.get('signature_envelope') or {}
    if env.get('synthetic_fixture') is True:reasons.append('SYNTHETIC_SIGNATURE_FIXTURE_FORBIDDEN')
    if not reasons:
        seen_run_ids.add(run_id);seen_nonces.add(nonce);seen_digests.add(digest)
    return {'accepted':not reasons,'case_id':cid,'report_sha256':digest,'run_id_ref':safe_ref(run_id) if run_id else None,
            'nonce_ref':safe_ref(nonce) if nonce else None,'certificate_sha256':env.get('certificate_sha256'),
            'generated_utc':report.get('generated_utc'),'reasons':sorted(set(reasons))}

def review_import(*,reports:list[dict[str,Any]],target_preflight:dict[str,Any],expected_package_zip_sha256:str,expected_manifest_sha256:str,
                  expected_trust_snapshot_sha256:str,trusted_certificate_sha256:set[str],baseline_before_import:dict[str,Any],
                  baseline_before_review:dict[str,Any],existing_ledger:list[dict[str,Any]]|None=None,
                  seen_index:dict[str,list[str]]|None=None,max_age_hours:int=24)->dict[str,Any]:
    ledger=_load('ledger2573','HMS_Codex_PromotionDecisionLedger.py');certmod=_load('cert2573','HMS_Codex_Cockpit1327WindowsRuntimeCertification.py')
    reasons=[]
    for phase,watch in (('BEFORE_IMPORT',baseline_before_import),('BEFORE_PROMOTION_REVIEW',baseline_before_review)):
        if watch.get('status')!='CURRENT' or watch.get('promotion_frozen') is True:reasons.append(f'{phase}_BASELINE_STALE')
        if str(watch.get('observed_version') or '')!=COCKPIT_BASELINE or str(watch.get('required_baseline') or '')!=COCKPIT_BASELINE:reasons.append(f'{phase}_BASELINE_MISMATCH')
        if watch.get('codex_only_scope') is not True:reasons.append(f'{phase}_CODEX_ONLY_SCOPE_REQUIRED')
    if not HEX64.fullmatch(str(expected_package_zip_sha256).lower()):reasons.append('TARGET_PACKAGE_ZIP_DIGEST_INVALID')
    if not HEX64.fullmatch(str(expected_manifest_sha256).lower()):reasons.append('TARGET_MANIFEST_DIGEST_INVALID')
    if not HEX64.fullmatch(str(expected_trust_snapshot_sha256).lower()):reasons.append('TRUST_SNAPSHOT_DIGEST_INVALID')
    idx=seen_index or {};nonces=set(idx.get('nonces') or []);runs=set(idx.get('run_ids') or []);digests=set(idx.get('report_digests') or [])
    accepted=[];quarantine=[]
    for r in reports:
        row=verify_capture_report(r,expected_package_zip_sha256=expected_package_zip_sha256,expected_manifest_sha256=expected_manifest_sha256,
                                  trusted_certificate_sha256=trusted_certificate_sha256,seen_nonces=nonces,seen_run_ids=runs,seen_digests=digests,max_age_hours=max_age_hours)
        (accepted if row['accepted'] else quarantine).append(row)
    by_case={}
    for x in accepted:by_case.setdefault(x['case_id'],[]).append(x)
    missing=[x for x in CASE_IDS if len(by_case.get(x,[]))!=1]
    extras=sorted(set(by_case)-set(CASE_IDS))
    if missing:reasons.append('SEVEN_CASE_MATRIX_INCOMPLETE')
    if extras:reasons.append('UNKNOWN_CASE_PRESENT')
    if quarantine:reasons.append('QUARANTINED_REPORTS_PRESENT')
    evidence={'source_mode':'REAL_WINDOWS_TARGET','external_import':True,'package_version':TARGET_PACKAGE_VERSION,'manifest_sha256':expected_manifest_sha256,
      'cockpit_baseline':COCKPIT_BASELINE,'host':{'os':target_preflight.get('os'),'powershell_major':target_preflight.get('powershell_major'),
      'windows_target_verified':target_preflight.get('windows_target_verified') is True},'codex':{'client_present':target_preflight.get('codex_client_present') is True,'version':target_preflight.get('codex_version')},'case_reports':[]}
    for cid in CASE_IDS:
        xs=by_case.get(cid,[]);src=next((r for r in reports if r.get('case_id')==cid),{})
        evidence['case_reports'].append({'case_id':cid,'status':'PASS' if len(xs)==1 else 'QUARANTINED','evidence_classes':src.get('evidence_classes') or [],
          'runtime_attestation_verified':src.get('runtime_attestation_verified') is True,'signature_verified':len(xs)==1,
          'idempotency_witness_verified':src.get('idempotency_witness_verified') is True,'report_sha256':xs[0]['report_sha256'] if len(xs)==1 else None,
          'raw_account_id_exported':src.get('raw_account_id_exported'),'credential_payload_exported':src.get('credential_payload_exported')})
    runtime_cert=certmod.evaluate_runtime_campaign(evidence,expected_manifest_sha256=expected_manifest_sha256,expected_package_version=TARGET_PACKAGE_VERSION,current_cockpit_baseline=COCKPIT_BASELINE)
    if runtime_cert.get('windows_runtime_certified') is not True:reasons.append('WINDOWS_RUNTIME_CERTIFICATION_NOT_COMPLETE')
    existing=list(existing_ledger or []);entries=list(existing);dual={'promotion_eligible':False,'dual_review_complete':False,'automatic_production_certification':False,'production_score_mutation_authorized':False,'ledger_tail_sha256':ledger.verify_chain(entries)['tail_sha256'] if entries else '0'*64}
    evidence_digest=sha(stable({'accepted':accepted,'runtime_campaign_digest':runtime_cert.get('campaign_digest'),'target_package_zip_sha256':expected_package_zip_sha256,'trust_snapshot_sha256':expected_trust_snapshot_sha256}))
    if not reasons:
        for reviewer in ('reviewer-a','reviewer-b'):
            entries.append(ledger.new_entry(entries,decision='APPROVE',campaign_digest=runtime_cert['campaign_digest'],evidence_bundle_sha256=evidence_digest,
              package_version=TARGET_PACKAGE_VERSION,manifest_sha256=expected_manifest_sha256,trust_snapshot_sha256=expected_trust_snapshot_sha256,
              reviewer_ref=safe_ref(reviewer),reason_code='WINDOWS_7_CASE_TARGET_REVIEW_OK'))
        dual=ledger.evaluate_dual_review(entries,campaign_digest=runtime_cert['campaign_digest'],evidence_bundle_sha256=evidence_digest,
                                         package_version=TARGET_PACKAGE_VERSION,manifest_sha256=expected_manifest_sha256,trust_snapshot_sha256=expected_trust_snapshot_sha256)
    ready=not reasons and dual.get('promotion_eligible') is True and dual.get('dual_review_complete') is True
    body={'product':PRODUCT,'version':VERSION,'suite':'WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW','generated_utc':utcnow(),'cockpit_baseline':COCKPIT_BASELINE,
      'target_package_version':TARGET_PACKAGE_VERSION,'target_package_zip_sha256':expected_package_zip_sha256,'target_manifest_sha256':expected_manifest_sha256,
      'trust_snapshot_sha256':expected_trust_snapshot_sha256,'baseline_before_import':{k:baseline_before_import.get(k) for k in ('status','observed_version','required_baseline','promotion_frozen')},
      'baseline_before_promotion_review':{k:baseline_before_review.get(k) for k in ('status','observed_version','required_baseline','promotion_frozen')},
      'accepted_count':len(accepted),'quarantined_count':len(quarantine),'accepted_case_count':len([c for c in CASE_IDS if len(by_case.get(c,[]))==1]),
      'quarantine':quarantine,'missing_case_ids':missing,'runtime_certificate':runtime_cert,'dual_review':dual,'ledger_entry_count_before':len(existing),'ledger_entry_count_after':len(entries),
      'evidence_bundle_sha256':evidence_digest,'review_ready_for_promotion_auditor':ready,'reasons':sorted(set(reasons)),
      'external_windows_target_evidence_imported':runtime_cert.get('external_windows_target_evidence_imported') is True and runtime_cert.get('windows_runtime_certified') is True,
      'read_only_import':True,'target_effects_executed_during_import':False,'automatic_production_certification':False,
      'production_score_mutation_authorized':False,'production_score_promotion_eligible':False,'codex_only_scope':True,'antigravity_scope_imported':False,
      'seen_index':{'nonces':sorted(nonces),'run_ids':sorted(runs),'report_digests':sorted(digests)}}
    body['review_digest']=sha(stable({k:v for k,v in body.items() if k not in ('generated_utc','review_digest')}));return body

def _signed_fixture(case_id:str,*,package_zip:str,manifest:str,cert_trust:set[str])->dict[str,Any]:
    signer=_load('signerfixture2573','HMS_Codex_WindowsAttestationSigner.py')
    base={'product':PRODUCT,'version':TARGET_PACKAGE_VERSION,'package_version':TARGET_PACKAGE_VERSION,'package_zip_sha256':package_zip,'package_manifest_sha256':manifest,
      'cockpit_baseline':COCKPIT_BASELINE,'case_id':case_id,'status':'PASS','evidence_classes':['WINDOWS_TARGET_OBSERVER','REAL_CODEX_EFFECT'],
      'runtime_attestation_verified':True,'idempotency_witness_verified':True,'raw_account_id_exported':False,'credential_payload_exported':False,
      'prompt_payload_exported':False,'response_payload_exported':False,'command_line_exported':False,'environment_exported':False,
      'run_id':str(uuid.uuid4()),'nonce':uuid.uuid4().hex+uuid.uuid4().hex,'generated_utc':utcnow()}
    out,cert=signer.synthetic_sign_attestation(base)
    # Contract-positive fixture: the certificate is explicitly trusted by the test trust set. Remove only the provenance marker from envelope, then recompute the outer integrity hash; signed payload itself is unchanged.
    out['signature_envelope']['synthetic_fixture']=False
    out['attestation_sha256']=sha(stable({k:v for k,v in out.items() if k!='attestation_sha256'}))
    cert_trust.add(cert);return out

def synthetic_proof()->dict[str,Any]:
    watch=_load('watchproof2573','HMS_Codex_CockpitBaselineWatchGate.py');tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    package_zip='a'*64;manifest='b'*64;trust='c'*64;certs=set();reports=[_signed_fixture(cid,package_zip=package_zip,manifest=manifest,cert_trust=certs) for cid in CASE_IDS]
    current=watch.evaluate('1.3.27',source_locator='public-github-main-package-json')
    pre={'os':'Windows','powershell_major':5,'windows_target_verified':True,'codex_client_present':True,'codex_version':'codex-current-fixture'}
    r=review_import(reports=reports,target_preflight=pre,expected_package_zip_sha256=package_zip,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,
                    trusted_certificate_sha256=certs,baseline_before_import=current,baseline_before_review=current)
    add('seven_signed_reports_accepted',r['accepted_count']==7 and r['quarantined_count']==0,r['reasons'])
    add('runtime_certificate_complete',r['runtime_certificate']['windows_runtime_certified'] is True and r['runtime_certificate']['case_matrix_complete'] is True,r['runtime_certificate']['reasons'])
    add('dual_review_append_only_ready',r['review_ready_for_promotion_auditor'] and r['dual_review']['dual_review_complete'] and r['ledger_entry_count_after']==2)
    add('import_never_mutates_score',r['production_score_promotion_eligible'] is False and r['production_score_mutation_authorized'] is False)
    add('read_only_no_target_effect',r['read_only_import'] and not r['target_effects_executed_during_import'])
    stale=watch.evaluate('1.3.28');r2=review_import(reports=reports,target_preflight=pre,expected_package_zip_sha256=package_zip,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,
                    trusted_certificate_sha256=certs,baseline_before_import=current,baseline_before_review=stale)
    add('second_baseline_checkpoint_can_freeze',not r2['review_ready_for_promotion_auditor'] and 'BEFORE_PROMOTION_REVIEW_BASELINE_STALE' in r2['reasons'])
    replay=review_import(reports=reports+reports[:1],target_preflight=pre,expected_package_zip_sha256=package_zip,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,
                    trusted_certificate_sha256=certs,baseline_before_import=current,baseline_before_review=current)
    add('duplicate_replay_quarantined',replay['quarantined_count']>=1 and not replay['review_ready_for_promotion_auditor'])
    synth=_load('signersynth2573','HMS_Codex_WindowsAttestationSigner.py');badbase={k:v for k,v in reports[0].items() if k not in ('signature_envelope','attestation_sha256')};bad,cert=synth.synthetic_sign_attestation(badbase);badreports=[bad]+reports[1:];badcerts=set(certs);badcerts.add(cert)
    r3=review_import(reports=badreports,target_preflight=pre,expected_package_zip_sha256=package_zip,expected_manifest_sha256=manifest,expected_trust_snapshot_sha256=trust,
                    trusted_certificate_sha256=badcerts,baseline_before_import=current,baseline_before_review=current)
    add('synthetic_signature_provenance_rejected',r3['quarantined_count']>=1 and not r3['review_ready_for_promotion_auditor'])
    add('review_digest_present',HEX64.fullmatch(r['review_digest']) is not None)
    add('codex_only_scope',r['codex_only_scope'] and not r['antigravity_scope_imported'])
    p=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'WINDOWS_TARGET_EVIDENCE_IMPORT_REVIEW_PROOF','generated_utc':utcnow(),'verdict':'PASS' if p==len(tests) else 'FAIL','summary':{'pass':p,'fail':len(tests)-p,'total':len(tests)},'tests':tests,'synthetic_control_plane_only':True,'windows_runtime_certified':False,'production_score_promotion_eligible':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();out=synthetic_proof();txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
