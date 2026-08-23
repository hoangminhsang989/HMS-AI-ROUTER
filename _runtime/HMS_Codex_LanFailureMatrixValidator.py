#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, tempfile, time
from pathlib import Path
from unittest import mock
import HMS_Codex_LanPool as lp

VERSION='25.47'

def run(root: Path):
    shared=root/'shared'; key=lp.derive_pairing_key('PAIR-2026-SECURE')
    a=lp.ensure_node(root/'a.json','PC-A'); b=lp.ensure_node(root/'b.json','PC-B')
    project={'project_dir':r'C:\\Work\\HMS-QR','git_origin':'https://github.com/acme/HMS-QR.git','project_label':'HMS QR'}
    checks=[]
    def add(name, ok, detail=''):
        checks.append({'name':name,'ok':bool(ok),'detail':detail})

    # 1) Share unavailable/non-directory => no successful heartbeat publication.
    unavailable=root/'share-as-file'; unavailable.write_text('x',encoding='utf-8')
    blocked=False
    try: lp.heartbeat(unavailable,key,a,{'health':'READY'},45)
    except Exception: blocked=True
    add('share_unavailable_fails_closed',blocked)

    # 2) Bounded retry survives a transient os.replace failure.
    real_replace=os.replace; calls={'n':0}
    def flaky(src,dst):
        calls['n']+=1
        if calls['n']==1: raise OSError('synthetic SMB reconnect')
        return real_replace(src,dst)
    with mock.patch.object(lp.os,'replace',side_effect=flaky):
        lp.heartbeat(shared,key,a,{'health':'READY','capacity':2},45)
    add('smb_transient_publish_retry',calls['n']>=2 and lp.node_file(shared,a['node_id']).exists(),f'replace_calls={calls["n"]}')

    # 3) Stale lock is recovered; live lock is not stolen.
    stale=lp.lock_path(shared,'stale-case'); stale.parent.mkdir(parents=True,exist_ok=True); stale.write_text('1|1',encoding='utf-8')
    old=time.time()-120; os.utime(stale,(old,old))
    with lp.FileLock(stale,stale_sec=30,timeout_sec=.3): pass
    add('stale_lock_recovered',not stale.exists())
    live=lp.lock_path(shared,'live-case'); live.write_text('1|1',encoding='utf-8')
    timed=False
    try:
        with lp.FileLock(live,stale_sec=30,timeout_sec=.18): pass
    except TimeoutError: timed=True
    add('active_lock_not_silently_stolen',timed)
    live.unlink(missing_ok=True)

    # 4) Signed future heartbeat beyond skew budget is excluded from failover.
    now=lp.epoch_now(); future_payload={
        'schema_version':lp.SCHEMA_VERSION,'engine_version':lp.ENGINE_VERSION,'node_id':b['node_id'],'node_name':'PC-B','machine':'PC-B',
        'time_utc':lp.utcnow(),'time_epoch':now+lp.MAX_FUTURE_SKEW_SEC+600,'ttl_sec':45,'health':'READY','capacity':9,'running_instances':0,
        'project_fingerprints':[],'account_hashes':['sha256:b'],'features':['SIGNED_HEARTBEAT'],'secret_values_excluded':True}
    lp.atomic_json(lp.node_file(shared,b['node_id']),lp.signed(future_payload,key))
    nodes=lp.read_nodes(shared,key,now_epoch=now); fb=next(x for x in nodes if x.get('node_id')==b['node_id'])
    add('future_clock_skew_heartbeat_rejected',fb.get('state')=='CLOCK_SKEW_FUTURE' and not fb.get('fresh') and not fb.get('payload_ok'))
    add('clock_skew_node_not_failover_candidate',all(x.get('node_id')!=b['node_id'] for x in lp.failover_candidates(nodes,a['node_id'])))

    # 5) Signed malformed heartbeat is not trusted.
    bad={'schema_version':lp.SCHEMA_VERSION,'node_id':'bad-node','time_epoch':'not-int','ttl_sec':45}
    lp.atomic_json(shared/'nodes'/'bad-node.json',lp.signed(bad,key))
    badrow=next(x for x in lp.read_nodes(shared,key) if x.get('node_id')=='bad-node')
    add('signed_malformed_heartbeat_rejected',badrow.get('state')=='MALFORMED_PAYLOAD' and not badrow.get('payload_ok'))

    # 6) Duplicate signed node id across two registry files is fail-closed for ranking.
    dup=dict(future_payload); dup.update({'node_id':'dup-node','time_epoch':lp.epoch_now(),'capacity':5})
    lp.atomic_json(shared/'nodes'/'dup-a.json',lp.signed(dup,key)); lp.atomic_json(shared/'nodes'/'dup-b.json',lp.signed(dup,key))
    duprows=[x for x in lp.read_nodes(shared,key) if x.get('node_id')=='dup-node']
    add('duplicate_node_id_rejected',len(duprows)==2 and all(x.get('state')=='DUPLICATE_NODE_ID' and not x.get('payload_ok') for x in duprows))

    # 7) Corrupted/invalid signature registry is explicit fail-closed.
    corrupt=shared/'nodes'/'corrupt.json'; corrupt.write_text('{broken',encoding='utf-8')
    crow=next(x for x in lp.read_nodes(shared,key) if x.get('node_id')=='corrupt')
    add('corrupt_registry_rejected',crow.get('state')=='INVALID_SIGNATURE' and not crow.get('signature_ok'))

    # 8) Valid active lease blocks foreign node.
    first=lp.acquire_lease(shared,key,a,project,45); blocked=lp.acquire_lease(shared,key,b,project,45)
    add('active_lease_blocks_foreign_node',first.get('ok') and not blocked.get('ok') and blocked.get('status')=='BLOCKED_OWNED_BY_OTHER_NODE')

    # 9) Signed malformed/future lease cannot be silently overwritten.
    fp=first['fingerprint']; lease_path=lp.lease_file(shared,fp); wrap=lp.read_json(lease_path,{})
    future=dict(wrap['payload']); future['renewed_epoch']=now+lp.MAX_FUTURE_SKEW_SEC+600; future['expires_epoch']=future['renewed_epoch']+45
    lp.atomic_json(lease_path,lp.signed(future,key)); r=lp.acquire_lease(shared,key,b,project,45)
    add('future_clock_skew_lease_blocks_takeover',not r.get('ok') and r.get('status')=='BLOCKED_INVALID_PAYLOAD')

    malformed=dict(future); malformed['renewed_epoch']='bad'; lp.atomic_json(lease_path,lp.signed(malformed,key)); r=lp.acquire_lease(shared,key,b,project,45)
    add('signed_malformed_lease_blocks_takeover',not r.get('ok') and r.get('status')=='BLOCKED_INVALID_PAYLOAD')

    # 10) A semantically valid expired lease can be taken over only with newer epoch.
    base=dict(first['lease']); base['renewed_epoch']=now-60; base['expires_epoch']=now-15; base['acquired_epoch']=min(int(base['acquired_epoch']),base['renewed_epoch'])
    lp.atomic_json(lease_path,lp.signed(base,key)); takeover=lp.acquire_lease(shared,key,b,project,45)
    add('expired_lease_takeover_newer_epoch',takeover.get('ok') and takeover.get('status')=='TAKEOVER_EXPIRED' and int(takeover['lease']['epoch'])>int(base['epoch']))
    add('expired_takeover_fresh_nonce',len(str(takeover.get('lease',{}).get('nonce','')))==32 and takeover['lease']['nonce']!=base['nonce'])

    # 11) TTL clamps bound bad configuration values.
    hb=lp.heartbeat(shared,key,a,{'health':'READY'},99999)
    add('heartbeat_ttl_clamped',hb['ttl_sec']==lp.MAX_HEARTBEAT_TTL_SEC)
    p2={'project_dir':r'C:\\Work\\OTHER','logical_id':'logical-other','project_label':'Other'}
    lr=lp.acquire_lease(shared,key,a,p2,99999)
    ttl=int(lr['lease']['expires_epoch'])-int(lr['lease']['renewed_epoch'])
    add('lease_ttl_clamped',ttl==lp.MAX_LEASE_TTL_SEC)

    # 12) Cross-PC fingerprint and secret-sharing invariants remain intact.
    same=lp.project_fingerprint(r'D:\\Repo\\HMS-QR','HTTPS://github.com/acme/HMS-QR')
    orig=lp.project_fingerprint(project['project_dir'],project['git_origin'])
    add('git_origin_identity_survives_path_change',same['fingerprint']==orig['fingerprint'] and same['scope']=='CROSS_PC')
    st=lp.status(shared,key,a,[project])
    add('shared_status_contains_no_secret_fields',not lp.secret_scan(st))
    add('raw_credentials_never_shared_contract',st['security']['credential_sharing'] is False and st['security']['raw_token_sharing'] is False)
    add('invalid_registry_entries_reported',int(st['summary'].get('invalid_registry_entries') or 0)>=4)

    passed=sum(1 for x in checks if x['ok'])
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'LAN_POOL_FAILURE_MATRIX','verdict':'PASS' if passed==len(checks) else 'FAIL',
            'summary':{'pass':passed,'fail':len(checks)-passed,'total':len(checks)},'checks':checks,
            'real_windows_smb_reconnect':'DEFERRED_BY_OPERATOR'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--temp'); ap.add_argument('--output'); a=ap.parse_args()
    owned=not bool(a.temp); root=Path(a.temp) if a.temp else Path(tempfile.mkdtemp(prefix='hms-lan-failure-v2546-'))
    try: out=run(root)
    finally:
        if owned:
            import shutil; shutil.rmtree(root,ignore_errors=True)
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+'\n',encoding='utf-8')
    print(txt); return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
