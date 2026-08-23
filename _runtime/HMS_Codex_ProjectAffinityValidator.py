#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,hashlib
from pathlib import Path

def norm(p:str)->str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(p))).rstrip('\\/')
def key(p:str)->str:
    return hashlib.sha256(norm(p).encode('utf-8')).hexdigest()
def validate(store:dict, instances:list[dict], accounts:list[str]):
    errors=[]; warnings=[]; projects=store.get('projects') or []
    by_id={str(i.get('id')):i for i in instances}; known={a.lower() for a in accounts}; seen=set()
    for idx,p in enumerate(projects):
        path=str(p.get('projectDir') or '')
        if not path: errors.append(f'project[{idx}]: projectDir missing'); continue
        nk=norm(path)
        if nk in seen: errors.append(f'project[{idx}]: duplicate project path')
        seen.add(nk)
        if p.get('projectKey') and str(p['projectKey'])!=key(path): errors.append(f'project[{idx}]: projectKey mismatch')
        iid=str(p.get('instanceId') or '')
        inst=by_id.get(iid)
        if not inst: errors.append(f'project[{idx}]: instance missing {iid}'); continue
        if norm(str(inst.get('projectDir') or inst.get('project_dir') or ''))!=nk: errors.append(f'project[{idx}]: instance project mismatch')
        primary=str(p.get('preferredAccount') or '').lower()
        inst_acc=str(inst.get('accountEmail') or inst.get('account_email') or '').lower()
        if primary!=inst_acc: errors.append(f'project[{idx}]: primary account must equal isolated instance account')
        if primary and primary not in known: warnings.append(f'project[{idx}]: primary account not in current pool')
        fbs=[]
        for f in p.get('fallbackAccounts') or []:
            fl=str(f).lower()
            if fl==primary: errors.append(f'project[{idx}]: fallback equals primary')
            if fl in fbs: errors.append(f'project[{idx}]: duplicate fallback')
            if fl not in known: warnings.append(f'project[{idx}]: fallback not in current pool: {f}')
            fbs.append(fl)
    return {'ok':not errors,'errors':errors,'warnings':warnings,'projects':len(projects)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--store',required=True); ap.add_argument('--instances',required=True); ap.add_argument('--accounts',required=True); ap.add_argument('--output')
    a=ap.parse_args(); store=json.loads(Path(a.store).read_text('utf-8-sig')); instances=json.loads(Path(a.instances).read_text('utf-8-sig')); accounts=json.loads(Path(a.accounts).read_text('utf-8-sig'))
    out=validate(store,instances,accounts); s=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(s,'utf-8')
    print(s); return 0 if out['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
