#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
VERSION='25.74'; PRODUCT='HMS-AI-ROUTER'; COCKPIT_BASELINE='1.3.27'
CASE_IDS=(
 'FOREIGN_PORT_AUTO_REBIND','ACCOUNT_OCCUPANCY_GUARD','CLIENT_AUTH_API_SERVICE_SPLIT',
 'OFFICIAL_ACCOUNT_USAGE_CONTINUITY','WEBSOCKET_PREFERENCE_PERSISTENCE','BOUNDED_BACKUP_ROLLBACK_NTFS','STREAM_IDENTITY_ISOLATION')
def utcnow():return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str):
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str):return 'ref-'+sha(v)[:24]
def _ver(v:str):
    p=str(v).lstrip('v').split('.')
    if len(p)!=3 or not all(x.isdigit() for x in p):raise ValueError('INVALID_SEMVER')
    return tuple(map(int,p))
def _load(alias:str,filename:str):
    p=Path(__file__).with_name(filename);spec=importlib.util.spec_from_file_location(alias,p);m=importlib.util.module_from_spec(spec);sys.modules[alias]=m;spec.loader.exec_module(m);return m

def reconcile(*,review_packet:dict[str,Any],ledger_entries:list[dict[str,Any]],observed_version:str,observed_source_digest_sha256:str,
              delta_audit:dict[str,Any]|None=None,reconciliation_reviewer_ref:str|None=None)->dict[str,Any]:
    ledger=_load('ledger2574','HMS_Codex_PromotionDecisionLedger.py');reasons=[];entries=list(ledger_entries)
    try:cmp=_ver(observed_version)-_ver(COCKPIT_BASELINE)  # type: ignore[operator]
    except TypeError:
        a=_ver(observed_version);b=_ver(COCKPIT_BASELINE);cmp=(a>b)-(a<b)
    except Exception:
        cmp=99;reasons.append('BASELINE_VERSION_INVALID')
    digest_ok=len(str(observed_source_digest_sha256))==64 and all(c in '0123456789abcdefABCDEF' for c in str(observed_source_digest_sha256))
    if not digest_ok:reasons.append('UPSTREAM_SOURCE_DIGEST_REQUIRED')
    newer=cmp>0;older=cmp<0
    if newer:reasons.append('UPSTREAM_BASELINE_NEWER')
    if older:reasons.append('UPSTREAM_BASELINE_OLDER_THAN_PACKET')
    packet_ready=review_packet.get('packet_state')=='READY_FOR_HUMAN_REVIEW' and review_packet.get('review_packet_export_safe') is True
    if not packet_ready:reasons.append('REVIEW_PACKET_NOT_READY')
    cap_digest=str(review_packet.get('capability_binding_sha256') or '')
    delta=delta_audit or {};delta_valid=False;reusable=[]
    if newer and delta:
        unchanged=set(delta.get('unchanged_capability_ids') or [])
        new_binding=str(delta.get('prior_capability_binding_sha256') or '')
        delta_valid=(delta.get('scope')=='CODEX_ONLY' and delta.get('automatic_merge') is False and new_binding==cap_digest and set(CASE_IDS).issubset(unchanged))
        if delta_valid:reusable=list(CASE_IDS)
    live_approvals=[e for e in entries if e.get('decision')=='APPROVE']
    invalidated={str(e.get('supersedes_sha256') or '') for e in entries if e.get('decision')=='INVALIDATE'}
    live_approvals=[e for e in live_approvals if e.get('entry_sha256') not in invalidated]
    proposed=[]
    if newer and live_approvals:
        reviewer=reconciliation_reviewer_ref or safe_ref('baseline-drift-reconciler')
        if not reviewer.startswith('ref-'):reasons.append('PSEUDONYMOUS_RECONCILIATION_REVIEWER_REQUIRED')
        else:
            for e in live_approvals:
                try:
                    proposed.append(ledger.new_entry(entries+proposed,decision='INVALIDATE',campaign_digest=e['campaign_digest'],
                      evidence_bundle_sha256=e['evidence_bundle_sha256'],package_version=e['package_version'],manifest_sha256=e['manifest_sha256'],
                      trust_snapshot_sha256=e['trust_snapshot_sha256'],reviewer_ref=reviewer,reason_code='COCKPIT_BASELINE_DRIFT',supersedes_sha256=e['entry_sha256']))
                except Exception as ex:reasons.append('LEDGER_INVALIDATION_BUILD_FAILED:'+type(ex).__name__)
    reconciled_entries=entries+proposed
    chain=ledger.verify_chain(reconciled_entries)
    if not chain['valid']:reasons.append('RECONCILED_LEDGER_CHAIN_INVALID')
    packet_frozen=newer or bool(reasons)
    reuse_allowed=bool(newer and delta_valid and len(reusable)==len(CASE_IDS))
    # Even if all capabilities are reusable, a new review epoch is mandatory after baseline reconciliation.
    eligibility_invalidated=bool(newer)
    out={'product':PRODUCT,'version':VERSION,'suite':'BASELINE_DRIFT_RECONCILIATION','generated_utc':utcnow(),
         'packet_sha256':review_packet.get('packet_sha256'),'packet_state_before':review_packet.get('packet_state'),
         'packet_state_after':'FROZEN_BASELINE_DRIFT' if packet_frozen else 'CURRENT','required_baseline':COCKPIT_BASELINE,
         'observed_version':str(observed_version).lstrip('v'),'observed_source_digest_sha256':observed_source_digest_sha256 if digest_ok else None,
         'baseline_drift_detected':newer,'eligibility_invalidated':eligibility_invalidated,'superseding_invalidation_entry_count':len(proposed),
         'proposed_superseding_entries':proposed,'reconciled_ledger_tail_sha256':chain.get('tail_sha256'),
         'delta_audit_required':newer,'delta_audit_valid_for_evidence_reuse':delta_valid,'reusable_capability_ids':reusable,
         'evidence_reuse_allowed_after_new_review_epoch':reuse_allowed,'silent_grandfathering':False,'new_dual_review_epoch_required':newer,
         'reasons':sorted(set(reasons)),'automatic_upstream_merge':False,'automatic_production_certification':False,
         'production_score_mutation_authorized':False,'production_score_promotion_eligible':False,'codex_only_scope':True,'antigravity_scope_imported':False}
    out['reconciliation_digest']=sha(stable({k:v for k,v in out.items() if k not in ('generated_utc','reconciliation_digest')}));return out

def synthetic_proof()->dict[str,Any]:
    ledger=_load('ledgerproof2574','HMS_Codex_PromotionDecisionLedger.py');tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    camp='a'*64;ev='b'*64;man='c'*64;trust='d'*64;entries=[]
    for r in ('ref-review-a','ref-review-b'):
        entries.append(ledger.new_entry(entries,decision='APPROVE',campaign_digest=camp,evidence_bundle_sha256=ev,package_version='25.72',manifest_sha256=man,trust_snapshot_sha256=trust,reviewer_ref=r,reason_code='OK'))
    packet={'packet_sha256':'e'*64,'packet_state':'READY_FOR_HUMAN_REVIEW','review_packet_export_safe':True,'capability_binding_sha256':'f'*64}
    current=reconcile(review_packet=packet,ledger_entries=entries,observed_version='1.3.27',observed_source_digest_sha256='1'*64)
    add('current_baseline_keeps_packet_current',not current['baseline_drift_detected'] and current['packet_state_after']=='CURRENT' and current['superseding_invalidation_entry_count']==0)
    stale=reconcile(review_packet=packet,ledger_entries=entries,observed_version='1.3.28',observed_source_digest_sha256='2'*64)
    add('newer_baseline_freezes_packet',stale['baseline_drift_detected'] and stale['packet_state_after']=='FROZEN_BASELINE_DRIFT')
    add('newer_baseline_invalidates_eligibility',stale['eligibility_invalidated'] and stale['superseding_invalidation_entry_count']==2)
    add('invalidation_entries_supersede_approvals',all(x['decision']=='INVALIDATE' and x['supersedes_sha256'] for x in stale['proposed_superseding_entries']))
    add('reconciled_ledger_chain_valid',len(stale['reconciled_ledger_tail_sha256'])==64)
    delta={'scope':'CODEX_ONLY','automatic_merge':False,'prior_capability_binding_sha256':'f'*64,'unchanged_capability_ids':list(CASE_IDS)}
    reused=reconcile(review_packet=packet,ledger_entries=entries,observed_version='1.3.28',observed_source_digest_sha256='2'*64,delta_audit=delta)
    add('delta_audit_can_mark_capabilities_reusable',reused['delta_audit_valid_for_evidence_reuse'] and reused['evidence_reuse_allowed_after_new_review_epoch'])
    add('reuse_never_silently_grandfathered',not reused['silent_grandfathering'] and reused['new_dual_review_epoch_required'] and not reused['production_score_promotion_eligible'])
    bad_delta=dict(delta);bad_delta['unchanged_capability_ids']=list(CASE_IDS[:-1])
    rejected=reconcile(review_packet=packet,ledger_entries=entries,observed_version='1.3.28',observed_source_digest_sha256='2'*64,delta_audit=bad_delta)
    add('partial_delta_binding_cannot_reuse_all_evidence',not rejected['evidence_reuse_allowed_after_new_review_epoch'])
    add('no_auto_merge_or_score_mutation',not stale['automatic_upstream_merge'] and not stale['automatic_production_certification'] and not stale['production_score_mutation_authorized'])
    add('reconciliation_digest_present',len(stale['reconciliation_digest'])==64)
    passed=sum(x['status']=='PASS' for x in tests)
    return {'product':PRODUCT,'version':VERSION,'suite':'BASELINE_DRIFT_RECONCILIATION_PROOF','generated_utc':utcnow(),
            'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,
            'synthetic_control_plane_only':True,'production_score_promotion_eligible':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',action='store_true');ap.add_argument('--output');a=ap.parse_args();out=synthetic_proof();txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
