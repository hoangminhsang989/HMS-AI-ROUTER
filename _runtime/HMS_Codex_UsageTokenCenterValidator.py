#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, tempfile, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

VERSION="25.61"

def load(root:Path):
    p=root/'HMS_Codex_UsageTokenCenter.py'
    spec=importlib.util.spec_from_file_location('utc_v2561',p);m=importlib.util.module_from_spec(spec);sys.modules['utc_v2561']=m;spec.loader.exec_module(m);return m

def run(root:Path):
    m=load(root); tests=[]
    def add(name,ok,detail=None):tests.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    now=datetime(2026,8,22,8,0,tzinfo=timezone.utc)
    def acct(email,plan,h,w,hr='2026-08-22T10:00:00+00:00',wr='2026-08-28T08:00:00+00:00',extra=None,package=None,token=None,last='2026-08-22T07:59:00+00:00'):
        q={'five_hour_remaining':h,'weekly_remaining':w,'five_hour_reset':hr,'weekly_reset':wr,'five_hour_window_minutes':300,'weekly_window_minutes':10080,'source':'WHAM_USAGE','last_success_utc':last,'routing_eligible':True}
        if extra is not None:q['additional_windows']=extra
        if package is not None:q['package_expiry_utc']=package;q['package_expiry_source']='UPSTREAM_EXPLICIT'
        a={'email':email,'plan':plan,'status':'READY','quota':q}
        if token is not None:a['token_expiry_utc']=token
        return a
    accounts=[
        acct('free@example.invalid','FREE',70,80),
        acct('plus@example.invalid','PLUS',60,75,extra=[{'model':'gpt-5.6-sol','remaining_pct':55,'reset_utc':'2026-08-23T08:00:00+00:00','window_minutes':1440}]),
        acct('pro@example.invalid','PRO',85,90,package='2026-09-22T08:00:00+00:00',token='2026-08-22T09:00:00+00:00'),
        acct('business@example.invalid','BUSINESS',50,65),
        acct('enterprise@example.invalid','ENTERPRISE',95,98),
    ]
    report=m.build({'accounts':accounts},now=now)
    add('build_valid',len(report['cards'])==5 and report['safety']['live_quota_authoritative'],{'ok':True,'errors':[],'cards':len(report['cards'])})
    add('version_25_61',report['version']==VERSION,report['version'])
    counts=report['summary']['plans'];add('five_plan_classes',all(counts[k]==1 for k in ('FREE','PLUS','PRO','TEAM_BUSINESS','ENTERPRISE')),counts)
    for key,name in [('FREE','plan_free'),('PLUS','plan_plus'),('PRO','plan_pro'),('TEAM_BUSINESS','plan_team_business'),('ENTERPRISE','plan_enterprise')]:add(name,counts[key]==1)
    first=report['cards'][0]['windows'][0]
    add('reset_countdown_present',first['countdown_text']=='2h 0m',first)
    add('reset_absolute_present',first['absolute_utc_text']=='2026-08-22 10:00 UTC',first['absolute_utc_text'])
    add('source_and_freshness_same_row_model',first['source']=='WHAM_USAGE' and first['freshness_state']=='FRESH',{'source':first['source'],'fresh':first['freshness_state']})
    plus=next(c for c in report['cards'] if c['plan_class']=='PLUS');add('model_specific_window',any(w['kind']=='MODEL_SPECIFIC' and w['name']=='gpt-5.6-sol' for w in plus['windows']))
    pro=next(c for c in report['cards'] if c['plan_class']=='PRO')
    add('package_expiry_explicit',pro['lifecycle']['package']['expiry_utc']=='2026-09-22T08:00:00+00:00')
    add('token_expiry_separate',pro['lifecycle']['oauth_token_lifecycle']['expiry_utc']=='2026-08-22T09:00:00+00:00')
    nopkg=m.build({'accounts':[acct('x','PLUS',50,50,token='2026-08-22T09:00:00+00:00')]},now=now)['cards'][0]
    add('package_expiry_not_invented',nopkg['lifecycle']['package']['expiry_utc'] is None)
    malformed=m.build({'accounts':[acct('bad','PLUS',40,40,hr='not-a-time',package='bad-package')]},now=now)['cards'][0]
    add('malformed_reset_fail_soft',malformed['windows'][0]['reset_utc'] is None and malformed['windows'][0]['state']=='UNKNOWN')
    add('malformed_package_not_timestamp',malformed['lifecycle']['package']['expiry_utc'] is None and malformed['lifecycle']['package']['source']=='INVALID_METADATA')
    stale=m.build({'accounts':[acct('stale','PRO',99,99,last='2026-08-22T06:00:00+00:00')]},now=now)['cards'][0]
    add('stale_preserved',stale['freshness_state']=='STALE')
    sr=m.build({'accounts':[acct('stale','PRO',99,99,last='2026-08-22T06:00:00+00:00')]},now=now)
    add('stale_not_promoted_by_reset_preview',not sr['router_preview']['after_next_reset'][0]['eligible'])
    prev=report['router_preview'];add('router_preview_scenario_only',prev['after_reset_kind']==m.SCENARIO_KIND and prev['after_reset_label']=='SCENARIO ONLY')
    add('router_preview_has_rank_now',all('rank' in r for r in prev['now']))
    add('router_preview_has_rank_after_reset',all('rank' in r for r in prev['after_next_reset']))
    add('preferred_now_single',sum(r['rank']==1 for r in prev['now'])==1)
    add('preferred_after_single',sum(r['rank']==1 for r in prev['after_next_reset'])==1)
    # History transition matrix.
    r1=m.build({'accounts':[acct('hist','PLUS',10,20,hr='2026-08-22T09:00:00+00:00',package='2026-09-01T00:00:00+00:00')]},now=now)
    r2=m.build({'accounts':[acct('hist','PLUS',90,90,hr='2026-08-22T14:00:00+00:00',package='2026-10-01T00:00:00+00:00')]},now=now+timedelta(minutes=10))
    with tempfile.TemporaryDirectory(prefix='hms-v2561-') as td:
        hp=Path(td)/'usage-token-history-v2561.jsonl';s1=m.append_history(hp,r1);s2=m.append_history(hp,r2);rows=m.read_history(hp);ev=m.replay_events(rows)
        counts_ev={k:sum(x['event']==k for x in ev) for k in ('RESET_TIMESTAMP_CHANGED','RESET_REPLENISHMENT_OBSERVED','PACKAGE_EXPIRY_METADATA_CHANGED')}
        detail={'events':len(ev),'reset_timestamp_changes':counts_ev['RESET_TIMESTAMP_CHANGED'],'reset_replenishment_observed':counts_ev['RESET_REPLENISHMENT_OBSERVED'],'package_expiry_metadata_changes':counts_ev['PACKAGE_EXPIRY_METADATA_CHANGED']}
        add('history_reset_timestamp_change',counts_ev['RESET_TIMESTAMP_CHANGED']>=1,detail)
        add('history_replenishment_observed',counts_ev['RESET_REPLENISHMENT_OBSERVED']>=1,detail)
        add('history_package_change',counts_ev['PACKAGE_EXPIRY_METADATA_CHANGED']>=1,detail)
        add('replay_metadata_only',not m.contains_secret_like(ev))
        add('history_round_trip',len(rows)==2,len(rows))
        add('history_no_secret_fields',not m.contains_secret_like(rows))
    add('secret_detector_access_token',m.contains_secret_like({'access_token':'secret'}))
    add('report_no_secret_like_fields',not m.contains_secret_like(report))
    missing=m.build({'accounts':[{'email':'m','plan':'PLUS','status':'READY','quota':{}}]},now=now)['cards'][0]
    add('missing_metadata_remains_missing',all(w['remaining_pct'] is None and w['reset_utc'] is None for w in missing['windows']))
    add('package_token_non_conflation',pro['lifecycle']['package']['expiry_utc']!=pro['lifecycle']['oauth_token_lifecycle']['expiry_utc'] and pro['lifecycle']['non_conflation'])
    add('live_quota_authoritative',report['safety']['live_quota_authoritative'] is True)
    before=json.dumps(report,sort_keys=True);_ = m.router_preview(report['cards']);after=json.dumps(report,sort_keys=True)
    add('preview_no_router_mutation',before==after and prev['live_router_mutated'] is False and prev['quota_mutated'] is False)
    passed=sum(x['status']=='PASS' for x in tests)
    return {'ok':passed==len(tests),'data':{'product':'HMS-AI-ROUTER','version':VERSION,'suite':'NATIVE_USAGE_TOKEN_CENTER_PARITY_PLUS','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'fixture_matrix':{'plans':5,'accounts':5,'model_specific':1,'malformed':2,'stale':1},'production_certification':'NOT_CLAIMED_USAGE_TOKEN_CENTER_SYNTHETIC_ONLY'}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();d=run(Path(a.root));txt=json.dumps(d,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt+'\n','utf-8')
    print(txt);return 0 if d.get('ok') else 2
if __name__=='__main__':raise SystemExit(main())
