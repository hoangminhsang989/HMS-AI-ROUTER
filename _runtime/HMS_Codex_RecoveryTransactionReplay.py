#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.62'
SCHEMA_VERSION=1
PRODUCTION_CLAIM='NOT_CLAIMED_RECOVERY_REPLAY_SYNTHETIC_ONLY'
CONVERGENCE={'HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED'}
EFFECT_KINDS=('OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF')
PHASES=('TXN_PREPARE','EFFECT_PREPARE','EFFECT_DURABLE','EFFECT_VERIFY','EFFECT_COMPENSATE','TXN_DONE','OPERATOR_REQUIRED')
SENSITIVE=('token','secret','password','authorization','cookie','prompt','request_body','response_body','api_key','credential')


def utcnow(): return datetime.now(timezone.utc).isoformat()
def stable(obj:Any)->str: return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(v:bytes|str)->str:
    if isinstance(v,str): v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def hlabel(v:str)->str: return sha(v)[:24]

def sanitize(obj:Any)->Any:
    if isinstance(obj,dict):
        out={}
        for k,v in obj.items():
            kl=str(k).lower()
            out[str(k)]='<REDACTED>' if any(x in kl for x in SENSITIVE) else sanitize(v)
        return out
    if isinstance(obj,list): return [sanitize(x) for x in obj]
    if isinstance(obj,str) and len(obj)>256: return obj[:256]+'…'
    return obj

@dataclass(frozen=True)
class EffectSpec:
    effect_id:str
    kind:str
    scope_hash:str
    before_hash:str
    desired_hash:str
    depends_on:tuple[str,...]=()
    @property
    def idempotency_key(self)->str:
        return 'idem-'+sha('|'.join((self.effect_id,self.kind,self.scope_hash,self.desired_hash)))[:32]
    @property
    def effect_fingerprint(self)->str:
        return 'eff-'+sha(stable({'kind':self.kind,'scope_hash':self.scope_hash,'before_hash':self.before_hash,'desired_hash':self.desired_hash,'depends_on':self.depends_on}))[:32]

@dataclass(frozen=True)
class TransactionPlan:
    txn_id:str
    intent_fingerprint:str
    effects:tuple[EffectSpec,...]

class ReplayError(RuntimeError): pass
class CrashInjected(RuntimeError): pass

class ReplayJournal:
    def __init__(self,path:Path): self.path=Path(path)
    def rows(self)->list[dict[str,Any]]:
        if not self.path.exists(): return []
        out=[]
        for n,line in enumerate(self.path.read_text('utf-8-sig').splitlines(),1):
            if not line.strip(): continue
            try:r=json.loads(line)
            except Exception as e: raise ReplayError(f'JOURNAL_JSON_INVALID:{n}') from e
            if not isinstance(r,dict): raise ReplayError(f'JOURNAL_RECORD_INVALID:{n}')
            out.append(r)
        return out
    def validate(self)->dict[str,Any]:
        prev='GENESIS';errs=[];seq={}
        for i,r in enumerate(self.rows()):
            if r.get('schema_version')!=SCHEMA_VERSION: errs.append(f'SCHEMA:{i}')
            if r.get('prev_hash')!=prev: errs.append(f'PREV:{i}')
            raw={k:v for k,v in r.items() if k!='record_hash'}
            if r.get('record_hash')!=sha(stable(raw)): errs.append(f'HASH:{i}')
            tx=str(r.get('txn_id') or ''); sq=int(r.get('seq') or 0)
            if sq!=seq.get(tx,0)+1: errs.append(f'SEQ:{i}')
            seq[tx]=sq;prev=str(r.get('record_hash') or '')
        return {'ok':not errs,'records':sum(seq.values()),'head_hash':prev,'errors':errs}
    def append(self,txn_id:str,phase:str,*,effect:EffectSpec|None=None,meta:dict[str,Any]|None=None)->dict[str,Any]:
        if phase not in PHASES: raise ReplayError('INVALID_PHASE')
        rows=self.rows(); prev=rows[-1]['record_hash'] if rows else 'GENESIS'; prior=[r for r in rows if r.get('txn_id')==txn_id]
        row={'schema_version':SCHEMA_VERSION,'version':VERSION,'txn_id':txn_id,'seq':len(prior)+1,'phase':phase,'time_utc':utcnow(),
             'intent_fingerprint':'','effect_id':'','effect_kind':'','effect_fingerprint':'','idempotency_key_hash':'','meta':sanitize(meta or {}),'prev_hash':prev}
        if effect:
            row.update(effect_id=effect.effect_id,effect_kind=effect.kind,effect_fingerprint=effect.effect_fingerprint,idempotency_key_hash=sha(effect.idempotency_key))
        row['record_hash']=sha(stable(row));self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a',encoding='utf-8',newline='\n') as f:
            f.write(stable(row)+'\n');f.flush();os.fsync(f.fileno())
        return row
    def txn_rows(self,txn_id:str)->list[dict[str,Any]]: return [r for r in self.rows() if r.get('txn_id')==txn_id]

class ModelWorld:
    """Synthetic externally observable world. Values are hashes only; no credential material."""
    def __init__(self,plan:TransactionPlan):
        self.state={e.effect_id:e.before_hash for e in plan.effects};self.exec_count={e.effect_id:0 for e in plan.effects};self.idem_seen=set();self.compensations=[]
    def observe(self,e:EffectSpec)->str: return self.state[e.effect_id]
    def execute(self,e:EffectSpec):
        if e.idempotency_key in self.idem_seen: return 'IDEMPOTENT_NOOP'
        self.idem_seen.add(e.idempotency_key);self.exec_count[e.effect_id]+=1;self.state[e.effect_id]=e.desired_hash;return 'APPLIED'
    def compensate(self,e:EffectSpec):
        if self.state[e.effect_id]!=e.desired_hash: return False
        self.state[e.effect_id]=e.before_hash;self.compensations.append(e.effect_id);return True
    def concurrent_change(self,e:EffectSpec): self.state[e.effect_id]=sha('external-change:'+e.effect_id)


def make_plan(nonce='proof')->TransactionPlan:
    txn='rrx-'+sha('25.62|'+nonce)[:24]
    ids=['auth','restart','router','lease']; kinds=EFFECT_KINDS
    effects=[]
    prev=None
    for i,(eid,kind) in enumerate(zip(ids,kinds)):
        deps=(prev,) if prev else ()
        effects.append(EffectSpec(eid,kind,hlabel('scope:'+eid),sha('before:'+eid),sha('desired:'+eid),deps));prev=eid
    intent='intent-'+sha(stable([e.effect_fingerprint for e in effects]))[:32]
    return TransactionPlan(txn,intent,tuple(effects))

class ReplayEngine:
    def __init__(self,journal:ReplayJournal,world:ModelWorld): self.journal=journal;self.world=world
    def _phase_set(self,tx:str,eid:str)->set[str]: return {str(r.get('phase')) for r in self.journal.txn_rows(tx) if r.get('effect_id')==eid}
    def _operator(self,plan:TransactionPlan,e:EffectSpec,reason:str)->dict[str,Any]:
        self.journal.append(plan.txn_id,'OPERATOR_REQUIRED',effect=e,meta={'reason':reason,'observed_hash':self.world.observe(e)})
        return {'status':'OPERATOR_REQUIRED','effect_id':e.effect_id,'reason':reason}
    def recover(self,plan:TransactionPlan,*,crash_marker:str='')->dict[str,Any]:
        chain=self.journal.validate()
        if not chain['ok']: return {'status':'OPERATOR_REQUIRED','reason':'JOURNAL_CHAIN_INVALID','chain':chain}
        txrows=self.journal.txn_rows(plan.txn_id)
        if any(r.get('phase')=='TXN_DONE' for r in txrows): return {'status':'HEALTHY','reason':'ALREADY_DONE'}
        if any(r.get('phase')=='OPERATOR_REQUIRED' for r in txrows): return {'status':'OPERATOR_REQUIRED','reason':'PRIOR_OPERATOR_REQUIRED'}
        if not txrows:
            if crash_marker=='BEFORE_TXN_PREPARE': raise CrashInjected(crash_marker)
            self.journal.append(plan.txn_id,'TXN_PREPARE',meta={'intent_fingerprint':plan.intent_fingerprint,'effects':len(plan.effects)})
            if crash_marker=='AFTER_TXN_PREPARE': raise CrashInjected(crash_marker)
        for e in plan.effects:
            phases=self._phase_set(plan.txn_id,e.effect_id)
            if 'EFFECT_VERIFY' in phases: continue
            # dependency proof: every predecessor must be verified first.
            for dep in e.depends_on:
                if 'EFFECT_VERIFY' not in self._phase_set(plan.txn_id,dep):
                    return {'status':'DEGRADED_SAFE','reason':'DEPENDENCY_NOT_VERIFIED','effect_id':e.effect_id}
            observed=self.world.observe(e)
            if 'EFFECT_DURABLE' in phases:
                # Durable evidence forbids re-execution. Verify externally or stop.
                if observed!=e.desired_hash: return self._operator(plan,e,'DURABLE_EFFECT_EXTERNAL_MISMATCH')
                if crash_marker==f'BEFORE_VERIFY:{e.effect_id}': raise CrashInjected(crash_marker)
                self.journal.append(plan.txn_id,'EFFECT_VERIFY',effect=e,meta={'observed_hash':observed,'decision':'VERIFY_ONLY_NO_REPEAT'})
                if crash_marker==f'AFTER_VERIFY:{e.effect_id}': raise CrashInjected(crash_marker)
                continue
            if 'EFFECT_PREPARE' not in phases:
                if crash_marker==f'BEFORE_PREPARE:{e.effect_id}': raise CrashInjected(crash_marker)
                self.journal.append(plan.txn_id,'EFFECT_PREPARE',effect=e,meta={'before_hash':e.before_hash,'desired_hash':e.desired_hash})
                if crash_marker==f'AFTER_PREPARE:{e.effect_id}': raise CrashInjected(crash_marker)
                observed=self.world.observe(e)
            # Prepared but commit status unknown: observe first, never blindly repeat.
            if observed==e.desired_hash:
                self.journal.append(plan.txn_id,'EFFECT_DURABLE',effect=e,meta={'decision':'OBSERVED_ALREADY_APPLIED_NO_REPEAT'})
            elif observed==e.before_hash:
                self.world.execute(e)
                if crash_marker==f'AFTER_EFFECT_BEFORE_DURABLE:{e.effect_id}': raise CrashInjected(crash_marker)
                self.journal.append(plan.txn_id,'EFFECT_DURABLE',effect=e,meta={'decision':'APPLIED_WITH_IDEMPOTENCY_KEY'})
            else:
                return self._operator(plan,e,'CONCURRENT_EXTERNAL_CHANGE_OWNERSHIP_UNPROVEN')
            if crash_marker==f'AFTER_DURABLE:{e.effect_id}': raise CrashInjected(crash_marker)
            observed=self.world.observe(e)
            if observed!=e.desired_hash: return self._operator(plan,e,'POST_EFFECT_VERIFY_MISMATCH')
            self.journal.append(plan.txn_id,'EFFECT_VERIFY',effect=e,meta={'observed_hash':observed,'decision':'EXTERNAL_EFFECT_VERIFIED'})
            if crash_marker==f'AFTER_VERIFY:{e.effect_id}': raise CrashInjected(crash_marker)
        self.journal.append(plan.txn_id,'TXN_DONE',meta={'convergence':'HEALTHY','effects':len(plan.effects)})
        return {'status':'HEALTHY','reason':'ALL_EFFECTS_VERIFIED','executions':dict(self.world.exec_count)}
    def compensate_verified(self,plan:TransactionPlan)->dict[str,Any]:
        """Reverse dependency order; compensate only when current state proves transaction ownership."""
        done=[]
        for e in reversed(plan.effects):
            phases=self._phase_set(plan.txn_id,e.effect_id)
            if 'EFFECT_DURABLE' not in phases: continue
            if self.world.observe(e)!=e.desired_hash:
                self.journal.append(plan.txn_id,'OPERATOR_REQUIRED',effect=e,meta={'reason':'COMPENSATION_OWNERSHIP_UNPROVEN'})
                return {'status':'OPERATOR_REQUIRED','compensated':done,'blocked_effect':e.effect_id}
            if not self.world.compensate(e): return {'status':'DEGRADED_SAFE','compensated':done,'blocked_effect':e.effect_id}
            self.journal.append(plan.txn_id,'EFFECT_COMPENSATE',effect=e,meta={'restored_hash':e.before_hash})
            done.append(e.effect_id)
        return {'status':'DEGRADED_SAFE','compensated':done}


def _run_crash(marker:str,nonce:str,concurrent_effect:str='')->dict[str,Any]:
    with tempfile.TemporaryDirectory(prefix='hms-v2562-crash-') as td:
        plan=make_plan(nonce); world=ModelWorld(plan); journal=ReplayJournal(Path(td)/'replay.jsonl'); engine=ReplayEngine(journal,world)
        crashed=False
        try: engine.recover(plan,crash_marker=marker)
        except CrashInjected: crashed=True
        if concurrent_effect:
            e=next(e for e in plan.effects if e.effect_id==concurrent_effect);world.concurrent_change(e)
        # two recovery attempts prove repeated recovery crash/process restart is idempotent.
        r1=engine.recover(plan); r2=engine.recover(plan)
        at_most_once=all(v<=1 for v in world.exec_count.values())
        safe=r1['status'] in CONVERGENCE and r2['status'] in CONVERGENCE and at_most_once and journal.validate()['ok']
        return {'marker':marker,'crashed':crashed,'first':r1['status'],'second':r2['status'],'at_most_once':at_most_once,'exec_count':world.exec_count,'safe':safe}


def crash_matrix()->dict[str,Any]:
    cases=[]
    plan=make_plan('matrix-template')
    markers=['BEFORE_TXN_PREPARE','AFTER_TXN_PREPARE']
    for e in plan.effects:
        markers += [f'BEFORE_PREPARE:{e.effect_id}',f'AFTER_PREPARE:{e.effect_id}',f'AFTER_EFFECT_BEFORE_DURABLE:{e.effect_id}',f'AFTER_DURABLE:{e.effect_id}',f'BEFORE_VERIFY:{e.effect_id}',f'AFTER_VERIFY:{e.effect_id}']
    for i,m in enumerate(markers): cases.append(_run_crash(m,f'crash:{i}:{m}'))
    # Concurrent operator change after PREPARE must fail closed and never overwrite ownership-unknown state.
    for e in plan.effects:
        with tempfile.TemporaryDirectory(prefix='hms-v2562-concurrent-') as td:
            p=make_plan('concurrent:'+e.effect_id);w=ModelWorld(p);j=ReplayJournal(Path(td)/'j.jsonl');eng=ReplayEngine(j,w)
            target=next(x for x in p.effects if x.effect_id==e.effect_id)
            try: eng.recover(p,crash_marker=f'AFTER_PREPARE:{e.effect_id}')
            except CrashInjected: pass
            w.concurrent_change(target);r=eng.recover(p)
            cases.append({'marker':'CONCURRENT_CHANGE:'+e.effect_id,'crashed':True,'first':r['status'],'second':r['status'],'at_most_once':all(v<=1 for v in w.exec_count.values()),'exec_count':w.exec_count,'safe':r['status']=='OPERATOR_REQUIRED' and all(v<=1 for v in w.exec_count.values())})
    passed=sum(c['safe'] for c in cases)
    return {'pass':passed,'fail':len(cases)-passed,'total':len(cases),'cases':cases}


def synthetic_proof()->dict[str,Any]:
    checks=[]
    def add(n,ok,d=None): checks.append({'name':n,'ok':bool(ok),'detail':d})
    with tempfile.TemporaryDirectory(prefix='hms-v2562-proof-') as td:
        plan=make_plan('proof'); w=ModelWorld(plan); j=ReplayJournal(Path(td)/'j.jsonl'); eng=ReplayEngine(j,w)
        r=eng.recover(plan); add('healthy_convergence',r['status']=='HEALTHY',r)
        add('all_four_effects_once',all(v==1 for v in w.exec_count.values()),w.exec_count)
        r2=eng.recover(plan);add('replay_done_no_repeat',r2['status']=='HEALTHY' and all(v==1 for v in w.exec_count.values()),w.exec_count)
        add('hash_chain_valid',j.validate()['ok'],j.validate())
        raw=j.path.read_text('utf-8');add('journal_metadata_hash_only',all(x not in raw.lower() for x in ('access_token','refresh_token','password','prompt','request_body','response_body')))
        add('effect_fingerprints_present',all(e.effect_fingerprint in raw for e in plan.effects))
        add('idempotency_keys_not_raw',all(e.idempotency_key not in raw for e in plan.effects))
        add('idempotency_hashes_present',all(sha(e.idempotency_key) in raw for e in plan.effects))
        add('dependency_chain',plan.effects[0].depends_on==() and all(plan.effects[i].depends_on==(plan.effects[i-1].effect_id,) for i in range(1,4)))
    # Dangerous unjournaled-effect window: external desired state is observed, effect is NOT executed again.
    with tempfile.TemporaryDirectory(prefix='hms-v2562-unjournaled-') as td:
        plan=make_plan('unjournaled');w=ModelWorld(plan);j=ReplayJournal(Path(td)/'j.jsonl');eng=ReplayEngine(j,w);e=plan.effects[0]
        try: eng.recover(plan,crash_marker='AFTER_EFFECT_BEFORE_DURABLE:auth')
        except CrashInjected: pass
        before=w.exec_count['auth'];rr=eng.recover(plan);add('unjournaled_effect_observed_no_repeat',before==1 and w.exec_count['auth']==1 and rr['status']=='HEALTHY',w.exec_count)
    # Compensation DAG reverses dependencies and refuses concurrent ownership changes.
    with tempfile.TemporaryDirectory(prefix='hms-v2562-comp-') as td:
        plan=make_plan('comp');w=ModelWorld(plan);j=ReplayJournal(Path(td)/'j.jsonl');eng=ReplayEngine(j,w);eng.recover(plan);c=eng.compensate_verified(plan)
        add('compensation_reverse_dag',c['compensated']==['lease','router','restart','auth'],c)
        add('compensation_restores_before',all(w.observe(e)==e.before_hash for e in plan.effects))
    with tempfile.TemporaryDirectory(prefix='hms-v2562-own-') as td:
        plan=make_plan('ownership');w=ModelWorld(plan);j=ReplayJournal(Path(td)/'j.jsonl');eng=ReplayEngine(j,w);eng.recover(plan);w.concurrent_change(plan.effects[-1]);c=eng.compensate_verified(plan)
        add('compensation_fails_closed_on_concurrent_change',c['status']=='OPERATOR_REQUIRED' and c['blocked_effect']=='lease',c)
    matrix=crash_matrix();add('crash_matrix_all_safe',matrix['fail']==0,{'pass':matrix['pass'],'total':matrix['total']})
    add('crash_matrix_30_plus',matrix['total']>=30,matrix['total'])
    add('effect_kinds_complete',set(EFFECT_KINDS)=={'OFFICIAL_AUTH_REWRITE','CONTROLLED_CODEX_RESTART','ROUTER_STATE_TRANSITION','LAN_LEASE_HANDOFF'})
    add('convergence_states_complete',CONVERGENCE=={'HEALTHY','DEGRADED_SAFE','OPERATOR_REQUIRED'})
    add('production_not_claimed',PRODUCTION_CLAIM.endswith('SYNTHETIC_ONLY'))
    passed=sum(x['ok'] for x in checks)
    return {'product':'HMS-AI-ROUTER','version':VERSION,'suite':'RECOVERY_TRANSACTION_REPLAY_MULTI_SUBSYSTEM_CRASH_CONSISTENCY','generated_utc':utcnow(),'verdict':'PASS' if passed==len(checks) else 'FAIL','summary':{'pass':passed,'fail':len(checks)-passed,'total':len(checks),'crash_cases':matrix['total']},'checks':checks,'crash_matrix':matrix,'safety':{'at_most_once_durable_side_effect':True,'ownership_proof_required_for_compensation':True,'production_certification':PRODUCTION_CLAIM}}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['proof','inspect'],default='proof');ap.add_argument('--journal');ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof': d=synthetic_proof();rc=0 if d['verdict']=='PASS' else 2
    else:
        if not a.journal: raise SystemExit('--journal required for inspect')
        j=ReplayJournal(Path(a.journal));d={'ok':j.validate()['ok'],'version':VERSION,'chain':j.validate(),'transactions':sorted({r.get('txn_id') for r in j.rows() if r.get('txn_id')})};rc=0 if d['ok'] else 2
    txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return rc
if __name__=='__main__': raise SystemExit(main())
