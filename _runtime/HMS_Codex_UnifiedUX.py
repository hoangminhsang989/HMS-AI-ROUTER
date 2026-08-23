#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, http.server, socketserver, time
from pathlib import Path
from urllib.parse import urlparse

HTML=r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HMS-AI-ROUTER · Unified UX</title>
<style>
:root{
 --bg:#0b0e12;--side:#10141a;--panel:#151a21;--panel2:#1a2029;--line:#28313d;
 --text:#edf2f7;--muted:#8e9aa8;--good:#60c68e;--warn:#e0b35b;--bad:#e56e72;--accent:#63aee0;
 --violet:#9b8cff;--cyan:#5ccbd6;--radius:9px
}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.4 "Segoe UI",Arial,sans-serif;overflow:hidden}
.shell{display:grid;grid-template-columns:232px 1fr;height:100vh}
aside{background:var(--side);border-right:1px solid var(--line);padding:16px 12px;display:flex;flex-direction:column;min-width:0}
.brand{padding:4px 10px 17px}.brand h1{font-size:17px;letter-spacing:.4px;margin:0}.brand small{color:var(--muted);display:block;margin-top:4px}
.nav{display:flex;flex-direction:column;gap:3px}.nav button{border:0;background:transparent;color:#bac4cf;text-align:left;padding:10px 11px;border-radius:7px;cursor:pointer;font:inherit}
.nav button:hover{background:#171d25}.nav button.active{background:#202834;color:#fff;box-shadow:inset 3px 0 var(--accent)}
.nav .section{color:#65717e;font-size:10px;text-transform:uppercase;letter-spacing:1px;padding:15px 11px 5px}
.asideFoot{margin-top:auto;border-top:1px solid var(--line);padding:12px 10px 0;color:var(--muted);font-size:11px}
main{min-width:0;height:100vh;display:flex;flex-direction:column}
.top{height:66px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 20px;background:#0e1217;gap:14px}
.topTitle{font-size:18px;font-weight:650}.routePill{margin-left:8px}
.spacer{flex:1}.fresh{color:var(--muted);font-size:11px}.btn{background:#1c2430;border:1px solid #354150;color:#dfe7ef;border-radius:7px;padding:7px 11px;cursor:pointer}.btn:hover{border-color:#526274}
.content{overflow:auto;padding:16px 18px 34px}
.view{display:none}.view.active{display:block}
.cards{display:grid;grid-template-columns:repeat(8,minmax(120px,1fr));gap:9px}
.card,.panel,.acct,.inst{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}
.card{padding:12px;min-height:84px}.card .k{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.65px}.card .v{font-size:20px;font-weight:680;margin-top:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.card .s{font-size:10px;color:var(--muted);margin-top:2px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:10px}
.panel{padding:13px;min-width:0}.panel h2{font-size:12px;text-transform:uppercase;letter-spacing:.65px;margin:0 0 11px;color:#c8d0d8}.panelHead{display:flex;align-items:center;gap:8px;margin-bottom:10px}.panelHead h2{margin:0}.panelHead .spacer{flex:1}
.good{color:var(--good)!important}.warn{color:var(--warn)!important}.bad{color:var(--bad)!important}.accent{color:var(--accent)!important}.muted{color:var(--muted)!important}
.badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #35404d;border-radius:20px;padding:2px 7px;font-size:10px;white-space:nowrap}.dot{width:6px;height:6px;border-radius:50%;background:currentColor}
table{width:100%;border-collapse:collapse;font-size:11px}th,td{padding:7px 6px;border-bottom:1px solid #252d37;text-align:left;white-space:nowrap;max-width:300px;overflow:hidden;text-overflow:ellipsis}th{position:sticky;top:0;background:var(--panel);color:#8995a3;font-weight:600;z-index:1}
.scroll{max-height:470px;overflow:auto}.topology{font:11px/1.55 Consolas,monospace;white-space:pre;color:#ced7e0;overflow:auto}
.search{background:#10151b;border:1px solid #303a46;color:#dfe7ef;border-radius:6px;padding:7px 9px;min-width:220px}
.accountGrid,.instanceGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:9px}
.acct,.inst{padding:12px}.acctTop,.instTop{display:flex;align-items:flex-start;gap:8px}.acctName,.instName{font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{font-size:10px;color:var(--muted);margin-top:2px}
.bars{display:grid;gap:7px;margin-top:12px}.barRow{display:grid;grid-template-columns:48px 1fr 38px;gap:8px;align-items:center;font-size:10px;color:var(--muted)}
.bar{height:6px;background:#252d36;border-radius:10px;overflow:hidden}.fill{height:100%;background:var(--accent);border-radius:10px}.fill.weekly{background:var(--violet)}
.kv{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:11px}.kv div{background:#11161c;border:1px solid #222b35;border-radius:6px;padding:7px}.kv b{display:block;font-size:12px}.kv span{font-size:9px;color:var(--muted);text-transform:uppercase}
.timeline{display:grid;gap:6px}.event{display:grid;grid-template-columns:132px 82px minmax(120px,190px) 1fr;gap:8px;border-bottom:1px solid #242c35;padding:6px 2px;font-size:11px}.event .msg{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pre{font:11px/1.5 Consolas,monospace;white-space:pre-wrap;background:#10151b;border:1px solid #242e39;border-radius:7px;padding:10px;max-height:550px;overflow:auto}
.empty{padding:28px;color:var(--muted);text-align:center}
.progress{height:5px;background:#202833;border-radius:9px;overflow:hidden;margin-top:6px}.progress>i{display:block;height:100%;background:var(--cyan)}
.notice{border-left:3px solid var(--warn);background:#191812;padding:10px 12px;border-radius:5px;margin-bottom:10px;color:#d9d0bc}.filters{display:flex;gap:5px;flex-wrap:wrap}.filter{background:#111820;border:1px solid #303b48;color:#9eabb8;border-radius:18px;padding:5px 9px;font-size:10px;cursor:pointer}.filter.active{background:#203349;border-color:#4c78a0;color:#e8f2fb}.holdReason{font-size:9px;color:var(--warn);margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:1250px){.cards{grid-template-columns:repeat(4,1fr)}.grid3{grid-template-columns:1fr 1fr}}
@media(max-width:850px){.shell{grid-template-columns:72px 1fr}.brand h1,.brand small,.nav button span,.nav .section,.asideFoot{display:none}.nav button{text-align:center}.cards{grid-template-columns:repeat(2,1fr)}.grid2,.grid3{grid-template-columns:1fr}}
</style></head>
<body><div class="shell">
<aside>
 <div class="brand"><h1>HMS-AI-ROUTER</h1><small>Unified UX v25.52 · local only</small></div>
 <div class="nav">
  <div class="section">Command</div>
  <button data-view="overview" class="active">◈ <span>Tổng quan</span></button>
  <button data-view="accounts">◎ <span>Tài khoản</span></button>
  <button data-view="instances">▦ <span>Instances</span></button>
  <button data-view="operations">⌁ <span>Vận hành</span></button>
  <div class="section">Intelligence</div>
  <button data-view="policy">◆ <span>Policy Kernel</span></button>
  <button data-view="reliability">◌ <span>Reliability</span></button>
  <button data-view="topology">⌘ <span>Topology</span></button>
  <div class="section">System</div>
  <button data-view="raw">{} <span>Raw Snapshot</span></button>
 </div>
 <div class="asideFoot">READ-ONLY WEB SURFACE<br>Operator mutation remains in native HMS console.</div>
</aside>
<main>
 <div class="top"><div class="topTitle">HMS / CODEX CONTROL PLANE <span id="version" class="muted"></span></div><span id="routeTop" class="badge routePill">UNATTRIBUTED</span><div class="spacer"></div><span id="fresh" class="fresh">—</span><button id="refresh" class="btn">REFRESH</button></div>
 <div class="content">
  <section id="overview" class="view active">
   <div class="cards">
    <div class="card"><div class="k">Router</div><div id="cRouter" class="v">—</div><div id="cRouterSub" class="s">—</div></div>
    <div class="card"><div class="k">Ready accounts</div><div id="cPool" class="v">—</div><div id="cPoolSub" class="s">—</div></div>
    <div class="card"><div class="k">Route eligible</div><div id="cEligible" class="v">—</div><div class="s">new sessions</div></div>
    <div class="card"><div class="k">Hold</div><div id="cHold" class="v">—</div><div class="s">fail-closed / reserve</div></div>
    <div class="card"><div class="k">Stale quota</div><div id="cStale" class="v">—</div><div class="s">needs refresh</div></div>
    <div class="card"><div class="k">Proxy Groups</div><div id="cProxy" class="v">—</div><div id="cProxySub" class="s">—</div></div>
    <div class="card"><div class="k">Cockpit Parity</div><div id="cParity" class="v">—</div><div id="cParitySub" class="s">—</div></div>
    <div class="card"><div class="k">Fleet SLA</div><div id="cSla" class="v">—</div><div id="cSlaSub" class="s">—</div></div>
    <div class="card"><div class="k">Active route</div><div id="cRoute" class="v" style="font-size:13px">—</div><div id="cRouteSub" class="s">—</div></div>
    <div class="card"><div class="k">Policy Kernel</div><div id="cKernel" class="v">—</div><div id="cKernelSub" class="s">—</div></div>
    <div class="card"><div class="k">Instances</div><div id="cInstances" class="v">—</div><div class="s">running / total</div></div>
    <div class="card"><div class="k">Latency P95</div><div id="cLatency" class="v">—</div><div class="s">real samples only</div></div>
    <div class="card"><div class="k">Soak</div><div id="cSoak" class="v">—</div><div id="cSoakSub" class="s">—</div></div>
   </div>
   <div id="attention" class="notice" style="display:none"></div>
   <div class="grid2">
    <div class="panel"><div class="panelHead"><h2>Account Pool</h2><div class="spacer"></div><span id="poolBadge" class="badge">—</span></div><div id="overviewAccounts" class="accountGrid"></div></div>
    <div class="panel"><h2>Current Decision</h2><div id="decision" class="pre"></div></div>
   </div>
   <div class="grid2">
    <div class="panel"><h2>Recent Incidents</h2><div id="overviewTimeline" class="timeline"></div></div>
    <div class="panel"><h2>Managed Instances</h2><div id="overviewInstances" class="instanceGrid"></div></div>
   </div>
  </section>

  <section id="accounts" class="view">
   <div class="panelHead"><h2>ACCOUNT POOL · QUOTA · ROUTING</h2><div class="spacer"></div><input id="accountSearch" class="search" placeholder="Tìm account / status / tag..."></div>
   <div class="filters" id="accountFilters" style="margin-bottom:10px"><button class="filter active" data-filter="ALL">TẤT CẢ</button><button class="filter" data-filter="ROUTE_OK">ROUTE OK</button><button class="filter" data-filter="HOLD">HOLD</button><button class="filter" data-filter="STALE">STALE</button><button class="filter" data-filter="FAVORITE">FAVORITE</button></div>
   <div id="accountGrid" class="accountGrid"></div>
  </section>

  <section id="instances" class="view">
   <div class="panelHead"><h2>MANAGED INSTANCES</h2><div class="spacer"></div><span id="instanceCount" class="badge">—</span></div>
   <div id="instanceGrid" class="instanceGrid"></div>
  </section>

  <section id="operations" class="view">
   <div class="grid2">
    <div class="panel"><h2>Incident Timeline</h2><div id="incidentTimeline" class="timeline"></div></div>
    <div class="panel"><h2>HA / Circuit Metrics</h2><div class="scroll"><table><thead><tr><th>Account</th><th>State</th><th>Samples</th><th>Error %</th><th>P50</th><th>P95</th></tr></thead><tbody id="haBody"></tbody></table></div></div>
   </div>
   <div class="grid2">
    <div class="panel"><h2>Router Intelligence</h2><div id="routerIntel" class="pre"></div></div>
    <div class="panel"><h2>Pool Reconciliation</h2><div id="reconcile" class="pre"></div></div>
   </div>
  </section>

  <section id="policy" class="view">
   <div class="grid3">
    <div class="card"><div class="k">Mode</div><div id="pMode" class="v">—</div></div>
    <div class="card"><div class="k">State</div><div id="pState" class="v">—</div></div>
    <div class="card"><div class="k">Score</div><div id="pScore" class="v">—</div></div>
   </div>
   <div class="grid2">
    <div class="panel"><h2>Kernel Actions</h2><div class="scroll"><table><thead><tr><th>Action</th><th>Status</th><th>Priority</th><th>Streak</th><th>Auto</th><th>Reason</th></tr></thead><tbody id="policyActions"></tbody></table></div></div>
    <div class="panel"><h2>Kernel Signals</h2><div class="scroll"><table><thead><tr><th>Severity</th><th>Code</th><th>Value</th></tr></thead><tbody id="policySignals"></tbody></table></div></div>
   </div>
   <div class="panel" style="margin-top:10px"><h2>Safety Contract</h2><div class="notice">Web UX không có endpoint mutation. Chuyển mode / SAFE_AUTO / reconcile / restart vẫn phải thực hiện từ native HMS console.</div><div id="policySafety" class="pre"></div></div>
  </section>

  <section id="reliability" class="view">
   <div class="cards" style="grid-template-columns:repeat(6,minmax(130px,1fr))">
    <div class="card"><div class="k">Performance</div><div id="rPerf" class="v">—</div></div>
    <div class="card"><div class="k">RAM P95</div><div id="rRam" class="v">—</div></div>
    <div class="card"><div class="k">Latency P95</div><div id="rLatency" class="v">—</div></div>
    <div class="card"><div class="k">Failovers</div><div id="rFail" class="v">—</div></div>
    <div class="card"><div class="k">Soak verdict</div><div id="rSoak" class="v">—</div></div>
    <div class="card"><div class="k">Soak progress</div><div id="rProgress" class="v">—</div><div class="progress"><i id="soakBar" style="width:0"></i></div></div>
   </div>
   <div class="grid2">
    <div class="panel"><h2>Performance Findings</h2><div id="performanceFindings" class="timeline"></div></div>
    <div class="panel"><h2>Soak Findings</h2><div id="soakFindings" class="timeline"></div></div>
   </div>
  </section>

  <section id="topology" class="view"><div class="panel"><h2>TOPOLOGY</h2><div id="topologyText" class="topology"></div></div></section>
  <section id="raw" class="view"><div class="panel"><h2>RAW SNAPSHOT · REDACTED CONTROL-PLANE STATE</h2><div id="rawText" class="pre"></div></div></section>
 </div>
</main></div>
<script>
let DATA=null;let ACCOUNT_FILTER="ALL";let ACCOUNT_SEARCH="";
const $=id=>document.getElementById(id);
function esc(v){return String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function num(v){const n=parseFloat(String(v??'').replace('%',''));return Number.isFinite(n)?n:null}
function tone(v){v=String(v||'').toUpperCase();if(/HEALTHY|ONLINE|READY|CLOSED|RUNNING|PASS|ACTIVE/.test(v))return'good';if(/WARN|DEGRADED|HALF_OPEN|COOLDOWN|PROBABLE|IN_PROGRESS|MAINTENANCE/.test(v))return'warn';if(/CRITICAL|OFFLINE|OPEN|ERROR|FAIL|LOCKED|QUARANTIN|PROTECT|FOREIGN/.test(v))return'bad';return''}
function badge(v){return `<span class="badge ${tone(v)}"><i class="dot"></i>${esc(v??'—')}</span>`}
function pctBar(label,v,weekly=false){let n=num(v);let width=n===null?0:Math.max(0,Math.min(100,n));return `<div class="barRow"><span>${label}</span><div class="bar"><div class="fill ${weekly?'weekly':''}" style="width:${width}%"></div></div><b>${n===null?'—':Math.round(n)+'%'}</b></div>`}
function acctCard(a){
 const q5=a.HourlyValue??a.Hourly, qw=a.WeeklyValue??a.Weekly, eligible=a.RouteEligible===true;
 const reasons=Array.isArray(a.HoldReasons)?a.HoldReasons:[];
 return `<div class="acct" data-route="${eligible?'OK':'HOLD'}" data-fresh="${esc(a.Freshness||'UNKNOWN')}" data-favorite="${a.Favorite?'1':'0'}" data-search="${esc([a.Account,a.Status,a.OpsState,a.Tag,a.Alias,a.Group,a.Freshness].join(' ').toLowerCase())}">
  <div class="acctTop"><div style="min-width:0;flex:1"><div class="acctName" title="${esc(a.Account)}">${esc(a.Alias||a.Account)}</div><div class="meta">${esc(a.Account)} · ${esc(a.Plan||'—')}</div></div>${badge(a.Status)}</div>
  <div style="margin-top:7px;display:flex;gap:5px;flex-wrap:wrap">${badge(eligible?'ROUTE OK':'HOLD')}${badge(a.Freshness||'UNKNOWN')}${badge(a.Circuit||'CLOSED')}${a.IsActiveRoute?'<span class="badge accent">ACTIVE ROUTE</span>':''}${a.Favorite?'<span class="badge accent">★ FAVORITE</span>':''}</div>
  ${!eligible&&reasons.length?`<div class="holdReason" title="${esc(reasons.join(' · '))}">WHY HOLD: ${esc(reasons.slice(0,3).join(' · '))}</div>`:''}
  <div class="bars">${pctBar('5h',q5)}${pctBar('Week',qw,true)}</div>
  <div class="kv"><div><span>Health</span><b>${esc(a.Health??'—')}</b></div><div><span>Reserve</span><b>${esc(a.ReservePct??'—')}%</b></div><div><span>Usable</span><b>${esc(a.UsablePct??'—')}%</b></div><div><span>Route</span><b>${esc(a.RouteConfidence||'—')}</b></div></div>
 </div>`
}
function instCard(i){return `<div class="inst"><div class="instTop"><div style="flex:1;min-width:0"><div class="instName">${esc(i.Name)}</div><div class="meta">${esc(i.Account||'—')}</div></div>${badge(i.Client)}</div><div style="margin-top:8px">${badge(i.Router)} ${i.Port?`<span class="badge">:${esc(i.Port)}</span>`:''}</div><div class="meta" style="margin-top:9px" title="${esc(i.Project)}">${esc(i.Project||'No project')}</div></div>`}
function evRow(e){return `<div class="event"><span class="muted">${esc(e.Time||e.time||'—')}</span><span class="${tone(e.Severity||e.severity||e.Type||e.type)}">${esc(e.Severity||e.severity||e.Type||e.type||'INFO')}</span><span>${esc(e.Account||e.account||'—')}</span><span class="msg" title="${esc(e.Message||e.message)}">${esc(e.Message||e.message||'')}</span></div>`}
function setText(id,v,cls){$(id).textContent=v??'—'; if(cls)$(id).className=cls+' '+tone(v)}
function fill(){
 const d=DATA||{}, pool=d.pool||{}, sla=d.sla||{}, route=d.active_route||{}, kernel=d.kernel||{}, perf=d.performance_detail||{}, soak=d.soak||{};
 $('version').textContent='v'+(d.version||'—');
 setText('cRouter',d.router?.state,'v');$('cRouterSub').textContent=`PID ${d.router?.pid||'—'} · :${d.router?.port||'—'}`;
 setText('cPool',`${pool.ready??0} / ${pool.total??0}`,'v');$('cPoolSub').textContent=`cooldown ${pool.cooldown??0}`;
 const qr=d.quota_routing||{};$('cEligible').textContent=qr.eligible??0;$('cEligible').className='v '+((qr.eligible??0)>0?'good':'bad');$('cHold').textContent=qr.hold??0;$('cHold').className='v '+((qr.hold??0)>0?'warn':'good');$('cStale').textContent=qr.stale??0;$('cStale').className='v '+((qr.stale??0)>0?'bad':'good');
 const att=d.operator_attention||[];$('attention').style.display=att.length?'block':'none';$('attention').textContent=att.length?'CẦN CHÚ Ý · '+att.join(' · '):'';
 const pg=d.proxy_groups||[];const pHealthy=pg.filter(x=>String(x.health).toUpperCase()==='PASS'&&String(x.egress).toUpperCase()==='PASS'&&String(x.ops_state).toUpperCase()==='ACTIVE').length;const pRunning=pg.filter(x=>x.sidecar_running===true).length;const pDrift=pg.filter(x=>String(x.egress).toUpperCase()==='DRIFT').length;const pQuarantine=pg.filter(x=>String(x.ops_state).toUpperCase()==='QUARANTINED').length;
 $('cProxy').textContent=`${pHealthy} / ${pg.length}`;$('cProxy').className='v '+(pg.length===0?'':(pHealthy===pg.length?'good':pHealthy===0?'bad':'warn'));$('cProxySub').textContent=`sidecars ${pRunning} · drift ${pDrift} · quarantine ${pQuarantine}`;
 const parity=d.cockpit_parity?.data?.hms||{};$('cParity').textContent=parity.feature_evidence_score_pct==null?'—':`${parity.feature_evidence_score_pct}%`;$('cParity').className='v '+((parity.feature_evidence_score_pct||0)>=80?'good':(parity.feature_evidence_score_pct||0)>=60?'warn':'bad');$('cParitySub').textContent=`prod evidence ${parity.production_evidence_score_pct??'—'}%`;
 setText('cSla',sla.Score??'—','v');$('cSlaSub').textContent=sla.State||'UNKNOWN';
 $('cRoute').textContent=route.account||'UNATTRIBUTED';$('cRouteSub').textContent=route.account?(route.confidence||'UNKNOWN'):'NO EVIDENCE';
 setText('cKernel',kernel.mode||'—','v');$('cKernelSub').textContent=`${kernel.state||'—'} · score ${kernel.score??'—'}`;
 const inst=d.instances||[];$('cInstances').textContent=inst.filter(x=>String(x.Client).toUpperCase()==='RUNNING').length+' / '+inst.length;
 const p95=perf.metrics?.latency_ms?.p95;$('cLatency').textContent=p95==null?'—':Math.round(p95)+' ms';
 setText('cSoak',soak.verdict||'—','v');$('cSoakSub').textContent=soak.progressPct==null?'no active evidence':`${soak.progressPct}%`;
 const rc=route.account?`${route.account} [${route.confidence||'UNKNOWN'}]`:'UNATTRIBUTED';$('routeTop').textContent=rc;$('routeTop').className='badge routePill '+tone(route.confidence);
 $('poolBadge').outerHTML=badge(`${pool.ready??0}/${pool.total??0} READY`).replace('<span','<span id="poolBadge"');
 const accts=d.accounts||[];$('overviewAccounts').innerHTML=accts.slice(0,4).map(acctCard).join('')||'<div class=empty>No accounts</div>';
 renderAccountGrid(accts);
 $('overviewInstances').innerHTML=inst.slice(0,4).map(instCard).join('')||'<div class=empty>No managed instances</div>';$('instanceGrid').innerHTML=inst.map(instCard).join('')||'<div class=empty>No managed instances</div>';$('instanceCount').textContent=inst.length+' INSTANCE(S)';
 const incidents=d.incidents||[];$('overviewTimeline').innerHTML=incidents.slice(0,8).map(evRow).join('')||'<div class=empty>No incidents</div>';$('incidentTimeline').innerHTML=incidents.slice(0,80).map(evRow).join('')||'<div class=empty>No incidents</div>';
 const decision=[d.summary||'',d.router_intelligence||'',d.performance||'',d.policy_kernel||''].filter(Boolean).join('\n\n');$('decision').textContent=decision||'No decision snapshot.';
 $('topologyText').textContent=d.topology||'—';
 const ha=d.ha?.accounts||[];$('haBody').innerHTML=ha.map(x=>`<tr><td>${esc(x.account)}</td><td class="${tone(x.state)}">${esc(x.state)}</td><td>${esc(x.samples)}</td><td>${esc(x.error_rate_pct)}</td><td>${esc(x.latency_p50_ms)}</td><td>${esc(x.latency_p95_ms)}</td></tr>`).join('');
 $('routerIntel').textContent=JSON.stringify(d.router_intel_detail||d.router_intelligence||{},null,2);$('reconcile').textContent=JSON.stringify(d.pool_reconcile||{},null,2);
 $('pMode').textContent=kernel.mode||'—';$('pState').textContent=kernel.state||'—';$('pScore').textContent=kernel.score??'—';$('pMode').className='v '+tone(kernel.mode);$('pState').className='v '+tone(kernel.state);
 $('policyActions').innerHTML=(kernel.actions||[]).map(x=>`<tr><td>${esc(x.kind)}</td><td class="${tone(x.status)}">${esc(x.status)}</td><td>${esc(x.priority)}</td><td>${esc(x.streak)} / ${esc(x.hysteresis_required)}</td><td>${x.auto_allowed?'YES':'NO'}</td><td title="${esc(x.reason)}">${esc(x.reason)}</td></tr>`).join('');
 $('policySignals').innerHTML=(kernel.signals||[]).map(x=>`<tr><td class="${tone(x.severity)}">${esc(x.severity)}</td><td>${esc(x.code)}</td><td>${esc(x.value)}</td></tr>`).join('');
 $('policySafety').textContent=JSON.stringify(kernel.safety||{},null,2);
 setText('rPerf',perf.verdict||'—','v');$('rRam').textContent=perf.metrics?.ram?.p95==null?'—':Math.round(perf.metrics.ram.p95)+' MB';$('rLatency').textContent=p95==null?'—':Math.round(p95)+' ms';$('rFail').textContent=perf.metrics?.events?.FAILOVER??'—';setText('rSoak',soak.verdict||'—','v');$('rProgress').textContent=soak.progressPct==null?'—':soak.progressPct+'%';$('soakBar').style.width=Math.max(0,Math.min(100,num(soak.progressPct)||0))+'%';
 $('performanceFindings').innerHTML=(perf.findings||[]).map(x=>evRow({time:'',type:x.severity,account:x.code,message:x.message})).join('')||'<div class=empty>No findings</div>';$('soakFindings').innerHTML=(soak.findings||[]).map(x=>evRow({time:'',type:x.severity,account:x.code,message:x.message})).join('')||'<div class=empty>No findings</div>';
 $('rawText').textContent=JSON.stringify(d,null,2);
 const gen=new Date(d.generatedUtc||0);const age=Math.max(0,(Date.now()-gen.getTime())/1000);$('fresh').textContent=Number.isFinite(age)?`snapshot ${Math.round(age)}s ago`:'snapshot —';$('fresh').className='fresh '+(age>15?'warn':'');
}
function renderAccountGrid(accts){
 let rows=(accts||[]).filter(a=>{const s=[a.Account,a.Status,a.OpsState,a.Tag,a.Alias,a.Group,a.Freshness].join(' ').toLowerCase();if(ACCOUNT_SEARCH&&!s.includes(ACCOUNT_SEARCH))return false;if(ACCOUNT_FILTER==='ROUTE_OK'&&a.RouteEligible!==true)return false;if(ACCOUNT_FILTER==='HOLD'&&a.RouteEligible===true)return false;if(ACCOUNT_FILTER==='STALE'&&!['STALE','UNKNOWN'].includes(String(a.Freshness||'UNKNOWN').toUpperCase()))return false;if(ACCOUNT_FILTER==='FAVORITE'&&!a.Favorite)return false;return true});
 $('accountGrid').innerHTML=rows.map(acctCard).join('')||'<div class=empty>Không có account khớp bộ lọc</div>';
}
async function load(){try{const r=await fetch('/api/snapshot?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);DATA=await r.json();fill()}catch(e){$('fresh').textContent='Dashboard error: '+e;$('fresh').className='fresh bad'}}
document.querySelectorAll('.nav button[data-view]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));$(b.dataset.view).classList.add('active')}));
$('refresh').addEventListener('click',load);
$('accountSearch').addEventListener('input',e=>{ACCOUNT_SEARCH=e.target.value.toLowerCase().trim();renderAccountGrid((DATA||{}).accounts||[])});
document.querySelectorAll('#accountFilters .filter').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('#accountFilters .filter').forEach(x=>x.classList.remove('active'));b.classList.add('active');ACCOUNT_FILTER=b.dataset.filter;renderAccountGrid((DATA||{}).accounts||[])}));
load();setInterval(load,3000);
</script></body></html>"""

class ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

class Handler(http.server.BaseHTTPRequestHandler):
    root:Path=None

    def headers_common(self,ctype,length=0):
        self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(int(length)))
        self.send_header("Connection","close")
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")

    def send_bytes(self,status,body,ctype):
        if not isinstance(body,(bytes,bytearray)):
            body=str(body).encode("utf-8")
        body=bytes(body)
        self.send_response(status)
        self.headers_common(ctype,len(body))
        self.end_headers()
        if body:
            self.wfile.write(body)
        self.close_connection=True

    def do_GET(self):
        path=urlparse(self.path).path
        if path in ("/api/snapshot","/snapshot.json"):
            p=self.root/"snapshot.json"
            if not p.exists():
                self.send_bytes(404,b'{"error":"snapshot unavailable"}',"application/json; charset=utf-8");return
            self.send_bytes(200,p.read_bytes(),"application/json; charset=utf-8");return
        if path=="/healthz":
            b=json.dumps({"ok":True,"read_only":True,"time":time.time()}).encode()
            self.send_bytes(200,b,"application/json; charset=utf-8");return
        if path in ("/","/index.html"):
            self.send_bytes(200,HTML.encode("utf-8"),"text/html; charset=utf-8");return
        self.send_bytes(404,b"","text/plain; charset=utf-8")

    def do_POST(self):
        # Read-only web surface. Consume the complete request body before replying.
        # This avoids a Windows/.NET HttpWebRequest connection reset when the server
        # closes a socket that still has unread POST bytes.
        try:
            length=int(self.headers.get("Content-Length","0") or "0")
        except Exception:
            length=0
        if length>0:
            remaining=length
            while remaining>0:
                chunk=self.rfile.read(min(remaining,65536))
                if not chunk:
                    break
                remaining-=len(chunk)
        body=b'{"error":"read-only surface; use native HMS console for operator actions"}'
        self.send_bytes(405,body,"application/json; charset=utf-8")

    def log_message(self,fmt,*args):return

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dir",required=True);ap.add_argument("--port",type=int,default=8765)
    a=ap.parse_args();root=Path(a.dir);root.mkdir(parents=True,exist_ok=True);Handler.root=root
    with ReuseTCPServer(("127.0.0.1",a.port),Handler) as srv:
        print(f"HMS Unified UX http://127.0.0.1:{a.port}/",flush=True)
        srv.serve_forever()
if __name__=="__main__":main()
