#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, mimetypes, os, socketserver, http.server, threading, time
from pathlib import Path

HTML=r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HMS Codex Command Center</title>
<style>
:root{--bg:#0d1014;--panel:#171b21;--panel2:#1e242c;--text:#edf2f7;--muted:#8d98a7;--border:#2e3640;--good:#5fc58e;--warn:#d8ad55;--bad:#e16b6b;--accent:#5da7d9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif}
header{height:66px;display:flex;align-items:center;padding:0 22px;border-bottom:1px solid var(--border);background:#11151a;position:sticky;top:0;z-index:3}
h1{font-size:20px;margin:0}.sub{color:var(--muted);margin-left:14px;font-size:12px}
main{padding:18px;max-width:1700px;margin:auto}
.cards{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:12px}
.card,.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px}
.card{padding:14px}.card .k{color:var(--muted);font-size:11px;text-transform:uppercase}.card .v{font-size:23px;font-weight:650;margin-top:7px}
.grid2{display:grid;grid-template-columns:1.2fr .8fr;gap:12px;margin-top:12px}.panel{padding:14px;overflow:auto}
.panel h2{font-size:14px;margin:0 0 12px 0}.topology{font-family:Consolas,monospace;white-space:pre;line-height:1.55;color:#d9e1e9}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px 7px;border-bottom:1px solid #28303a;text-align:left;white-space:nowrap}th{color:#a9b3bf;font-weight:600}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}.muted{color:var(--muted)}
.tag{display:inline-block;padding:2px 7px;border:1px solid var(--border);border-radius:20px;font-size:10px}
@media(max-width:1000px){.cards{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>HMS CODEX COMMAND CENTER</h1><span class="sub">read-only local dashboard · no tokens</span></header>
<main>
<div class="cards">
<div class="card"><div class="k">Router</div><div id="router" class="v">—</div></div>
<div class="card"><div class="k">Accounts ready</div><div id="accounts" class="v">—</div></div>
<div class="card"><div class="k">Fleet SLA</div><div id="sla" class="v">—</div></div>
<div class="card"><div class="k">Active route</div><div id="route" class="v" style="font-size:15px">—</div></div>
<div class="card"><div class="k">Instances</div><div id="instances" class="v">—</div></div>
<div class="card"><div class="k">HA circuits</div><div id="circuits" class="v">—</div></div>
</div>
<div class="grid2">
<div class="panel"><h2>Topology</h2><div id="topology" class="topology">Loading...</div></div>
<div class="panel"><h2>Health summary</h2><div id="health">Loading...</div></div>
</div>
<div class="grid2">
<div class="panel"><h2>Accounts</h2><table><thead><tr><th>Account</th><th>Status</th><th>5h</th><th>Weekly</th><th>Health</th><th>Circuit</th></tr></thead><tbody id="acctBody"></tbody></table></div>
<div class="panel"><h2>Instances</h2><table><thead><tr><th>Name</th><th>Account</th><th>Project</th><th>Client</th><th>Router</th></tr></thead><tbody id="instBody"></tbody></table></div>
</div>
<div class="grid2">
<div class="panel"><h2>Recent incidents</h2><table><thead><tr><th>Time</th><th>Severity</th><th>Type</th><th>Account</th><th>Message</th></tr></thead><tbody id="incidentBody"></tbody></table></div>
<div class="panel"><h2>Persistent metrics</h2><table><thead><tr><th>Account</th><th>Samples</th><th>Error %</th><th>P50 ms</th><th>P95 ms</th></tr></thead><tbody id="metricBody"></tbody></table></div>
</div>
</main>
<script>
function esc(v){return String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function cls(v){v=String(v||'').toUpperCase();return /HEALTHY|ONLINE|READY|CLOSED|RUNNING/.test(v)?'good':/WARN|DEGRADED|HALF_OPEN|COOLDOWN/.test(v)?'warn':/CRITICAL|OFF|OPEN|ERROR|FAIL|LOCKED/.test(v)?'bad':''}
async function load(){
 try{
  const r=await fetch('/snapshot.json?ts='+Date.now(),{cache:'no-store'});const d=await r.json();
  router.textContent=d.router?.state||'—';router.className='v '+cls(router.textContent);
  accounts.textContent=(d.pool?.ready??0)+' / '+(d.pool?.total??0);
  sla.textContent=(d.sla?.Score??'—')+'/100';sla.className='v '+cls(d.sla?.State);
  route.textContent=d.active_route?.account ? d.active_route.account+' ['+(d.active_route.confidence||'')+']' : 'UNATTRIBUTED';
  instances.textContent=(d.instances||[]).filter(x=>x.Client==='RUNNING').length+' / '+(d.instances||[]).length;
  circuits.textContent=(d.ha?.accounts||[]).filter(x=>['OPEN','LOCKED_OPEN','HALF_OPEN'].includes(x.state)).length;
  topology.textContent=d.topology||'—';
  health.innerHTML='<div><span class="tag '+cls(d.sla?.State)+'">'+esc(d.sla?.State||'UNKNOWN')+'</span></div><div class="muted" style="margin-top:8px">'+esc(d.summary||'')+'</div>';
  acctBody.innerHTML=(d.accounts||[]).map(x=>`<tr><td>${esc(x.Account)}</td><td class="${cls(x.Status)}">${esc(x.Status)}</td><td>${esc(x.Hourly)}</td><td>${esc(x.Weekly)}</td><td>${esc(x.Health)}</td><td class="${cls(x.Circuit)}">${esc(x.Circuit)}</td></tr>`).join('');
  instBody.innerHTML=(d.instances||[]).map(x=>`<tr><td>${esc(x.Name)}</td><td>${esc(x.Account)}</td><td title="${esc(x.Project)}">${esc(x.Project)}</td><td class="${cls(x.Client)}">${esc(x.Client)}</td><td class="${cls(x.Router)}">${esc(x.Router)}</td></tr>`).join('');
  incidentBody.innerHTML=(d.incidents||[]).slice(0,40).map(x=>`<tr><td>${esc(x.Time)}</td><td class="${cls(x.Severity)}">${esc(x.Severity)}</td><td>${esc(x.Type)}</td><td>${esc(x.Account)}</td><td title="${esc(x.Message)}">${esc(String(x.Message||'').slice(0,120))}</td></tr>`).join('');
  metricBody.innerHTML=(d.ha?.accounts||[]).map(x=>`<tr><td>${esc(x.account)}</td><td>${esc(x.samples)}</td><td>${esc(x.error_rate_pct)}</td><td>${esc(x.latency_p50_ms)}</td><td>${esc(x.latency_p95_ms)}</td></tr>`).join('');
 }catch(e){health.textContent='Dashboard error: '+e}
}
load();setInterval(load,5000);
</script>
</body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    root: Path=None
    def do_GET(self):
        if self.path.startswith("/snapshot.json"):
            p=self.root/"snapshot.json"
            if not p.exists():
                self.send_response(404);self.end_headers();return
            b=p.read_bytes();self.send_response(200);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b);return
        if self.path=="/" or self.path.startswith("/index"):
            b=HTML.encode("utf-8");self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b);return
        self.send_response(404);self.end_headers()
    def log_message(self,fmt,*args):return

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dir",required=True);ap.add_argument("--port",type=int,default=8765)
    a=ap.parse_args();root=Path(a.dir);root.mkdir(parents=True,exist_ok=True);Handler.root=root
    with socketserver.ThreadingTCPServer(("127.0.0.1",a.port),Handler) as s:
        s.daemon_threads=True
        print(f"HMS dashboard http://127.0.0.1:{a.port}",flush=True);s.serve_forever()
if __name__=="__main__":main()
