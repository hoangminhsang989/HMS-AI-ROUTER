#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path


def load(path: Path):
    spec=importlib.util.spec_from_file_location('p', path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--output'); a=ap.parse_args()
    root=Path(a.root); m=load(root/'HMS_Codex_Cockpit1327ParityReset.py')
    checks=[]
    def add(name, ok, detail=None): checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    r=m.report()
    add('baseline_is_1_3_27',r['cockpit_parity_baseline']=='1.3.27')
    add('matrix_12',r['summary']['total']==12,r['summary'])
    add('no_open_gap',r['summary']['gap_count']==0)
    s=m.availability_state(client_authorized=False,api_token_available=True)
    add('client_reauth_api_still_available',s['overall']=='API_ONLY_CLIENT_REAUTH_REQUIRED' and not s['invalid_account'],s)
    s2=m.availability_state(client_authorized=False,api_token_available=False)
    add('invalid_only_when_both_unavailable',s2['invalid_account'] is True,s2)
    occ=m.occupancy_decision(target_account_ref='a',target_instance_id='i2',running=[{'instance_id':'i1','account_ref':'a','running':True}])
    add('occupancy_blocks_duplicate_running_oauth',not occ['ok'] and occ['action']=='BLOCK_ACCOUNT_OCCUPIED',occ)
    occ2=m.occupancy_decision(target_account_ref='a',target_instance_id='i2',running=[{'instance_id':'i1','account_ref':'a','running':False}])
    add('occupancy_allows_stopped_other_instance',occ2['ok'],occ2)
    pr=m.port_recovery_plan(requested_port=8400,occupied_by_foreign=True,candidate_ports=[8401,8402],client_running=False)
    add('foreign_port_rebind_no_kill',pr['action']=='REBIND_BEFORE_START' and pr['new_port']==8401 and pr['kill_foreign_process'] is False,pr)
    pr2=m.port_recovery_plan(requested_port=8400,occupied_by_foreign=True,candidate_ports=[8401],client_running=True)
    add('running_client_port_conflict_fail_closed',pr2['action']=='BLOCK_RUNNING_CLIENT',pr2)
    ret=m.bounded_backup_retention([
      {'source':'auth','instance_id':'i1','path':'a1','created_utc':'2026-08-23T01:00:00Z'},
      {'source':'auth','instance_id':'i1','path':'a2','created_utc':'2026-08-23T02:00:00Z'},
      {'source':'auth','instance_id':'i2','path':'b1','created_utc':'2026-08-23T01:00:00Z'},
    ],1)
    add('bounded_backup_newest_per_source_instance',ret['keep']==['a2','b1'] and ret['prune']==['a1'],ret)
    i1=m.conversation_identity(conversation_id='c1',thread_id='t',client_key_id='k',account_ref='a')
    i2=m.conversation_identity(conversation_id='c2',thread_id='t',client_key_id='k',account_ref='a')
    add('conversation_identity_isolated',i1!=i2,(i1,i2))
    add('conversation_identity_stable',i1==m.conversation_identity(conversation_id='c1',thread_id='t',client_key_id='k',account_ref='a'))
    oa=m.safe_account_ref('official-123','a@example.com'); oa2=m.safe_account_ref('official-123','new@example.com')
    add('official_account_id_preserves_usage_continuity',oa==oa2 and oa.startswith('oaid-'),oa)
    add('email_not_exported_in_usage_key','@' not in oa)
    add('websocket_preserved_when_no_override',m.preserve_websocket_setting(current_enabled=False,requested_override=None) is False)
    md=m.model_runtime_metadata(model='gpt-x',context_window=200000,compact_threshold=160000)
    add('model_context_metadata',md['context_window']==200000 and md['compact_threshold']==160000,md)
    try:
      m.model_runtime_metadata(model='gpt-x',context_window=100000,compact_threshold=100000); bad=False
    except ValueError: bad=True
    add('compaction_below_context_enforced',bad)
    life=m.stable_windows_lifecycle_strategy()
    add('no_windowsapps_internal_daemon_stop','WINDOWSAPPS_INTERNAL_CODEX_DAEMON_STOP' in life['forbidden'] and life['foreign_process_kill'] is False,life)
    add('powershell_not_required_for_internal_daemon_stop',life['powershell_required_for_daemon_stop'] is False)
    add('production_claim_not_promoted',r['benchmark'] is False and 'NOT_CLAIMED' in r['production_claim'])
    add('p0_coverage',r['summary']['p0']>=6,r['summary'])
    add('p1_coverage',r['summary']['p1']>=4,r['summary'])
    out={'version':'25.72','cockpit_baseline':'1.3.27','summary':{'pass':sum(x['status']=='PASS' for x in checks),'fail':sum(x['status']=='FAIL' for x in checks),'total':len(checks)},'checks':checks,'parity':r}
    if a.output: Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out['summary']['fail']==0 else 1
if __name__=='__main__': raise SystemExit(main())
