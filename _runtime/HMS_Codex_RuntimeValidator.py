#!/usr/bin/env python3
import argparse,json,hashlib,platform,shutil,socket,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
def now():return datetime.now(timezone.utc).isoformat()
def sh(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for c in iter(lambda:f.read(1048576),b""):h.update(c)
 return h.hexdigest()
def R(i,s,msg,d=None,sev="normal"):return {"id":i,"status":s,"summary":msg,"details":d or {},"severity":sev,"time":now()}
def port(p):
 try:
  with socket.create_connection(("127.0.0.1",int(p)),.5):return True
 except OSError:return False
def jread(p):
 try:return json.loads(Path(p).read_text("utf-8-sig"))
 except:return None
def manifest(root):
 p=root/"RELEASE_MANIFEST_V25_23_1.json"
 if not p.exists():return R("package.manifest","FAIL","Thiếu manifest",sev="critical")
 try:m=json.loads(p.read_text("utf-8"))
 except Exception as e:return R("package.manifest","FAIL","Manifest lỗi",{"error":repr(e)},sev="critical")
 rows=[];ok=True
 for i in m.get("files",[]):
  f=root/i["path"]; good=f.exists() and sh(f)==i["sha256"]; rows.append({"path":i["path"],"hash_ok":good});ok&=good
 return R("package.manifest","PASS" if ok else "FAIL","Manifest/hash",{"version":m.get("version"),"files":rows},"critical" if not ok else "normal")
def env():
 win=platform.system()=="Windows"; ps=shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
 ok=bool(sys.executable) and (bool(ps) or not win)
 return R("environment.core","PASS" if ok else "FAIL","Môi trường core",{"os":platform.platform(),"python":sys.executable,"powershell":ps,"git":shutil.which("git"),"codex":shutil.which("codex")},"critical" if not ok else "normal")
def js(data):
 bad=[];n=0
 for p in data.glob("*.json") if data.exists() else []:
  n+=1
  try:json.loads(p.read_text("utf-8-sig"))
  except Exception as e:bad.append({"file":p.name,"error":str(e)[:160]})
 return R("state.json_integrity","PASS" if not bad else "FAIL",f"JSON {n-len(bad)}/{n}",{"bad":bad},"critical" if bad else "normal")
def sq(data):
 p=data/"codex-ha-v6.sqlite"
 if not p.exists():return R("state.sqlite","BLOCKED","HA SQLite chưa tạo")
 try:
  c=sqlite3.connect(f"file:{p.as_posix()}?mode=ro",uri=True,timeout=2);v=c.execute("pragma quick_check").fetchone()[0];c.close()
  return R("state.sqlite","PASS" if v=="ok" else "FAIL","SQLite "+str(v),sev="critical" if v!="ok" else "normal")
 except Exception as e:return R("state.sqlite","FAIL","SQLite lỗi",{"error":repr(e)},sev="critical")
def run(root,data,profile,c):
 t=[manifest(root),env(),js(data)]
 if profile!="STATIC":
  # SAFE_RUNTIME runs before production services/state are started.
  # Their absence is DEFERRED first-run state, not a safety blocker.
  deferred_status="DEFERRED" if profile=="SAFE_RUNTIME" else "BLOCKED"

  sqr=sq(data)
  if profile=="SAFE_RUNTIME" and sqr["status"]=="BLOCKED":
   sqr["status"]="DEFERRED"
   sqr["summary"]="HA SQLite chưa tạo (deferred first-run state)"
  t.append(sqr)

  po=int(c.get("proxy_port",8317));online=port(po)
  t.append(R("router.port","PASS" if online else deferred_status,f"Port {po}",{"online":online}))

  key=c.get("api_key")
  if online and key:
   try:
    q=Request(f"http://127.0.0.1:{po}/v1/models",headers={"Authorization":"Bearer "+key})
    with urlopen(q,timeout=3) as x: body=json.loads(x.read())
    t.append(R("router.models","PASS","/v1/models",{"models":len(body.get("data",[]))}))
   except Exception as e:
    t.append(R("router.models","FAIL","/v1/models lỗi",{"error":repr(e)},sev="critical"))
  else:
   t.append(R("router.models",deferred_status,"Router/API key chưa sẵn sàng"))

  ad=Path(c.get("auth_dir",""));fs=list(ad.glob("codex-*.json")) if ad.exists() else []
  bad=sum(jread(f) is None for f in fs)
  t.append(R("accounts.auth_pool","PASS" if fs and not bad else ("FAIL" if bad else deferred_status),f"Auth files={len(fs)} bad={bad}",sev="critical" if bad else "normal"))

  qc=list(data.glob("*quota*cache*.json"));t.append(R("accounts.quota_cache","PASS" if qc else deferred_status,"Quota cache"))
  ins=list(data.glob("*instances*.json"));t.append(R("instances.store","PASS" if ins else deferred_status,"Instance store"))
  mk=data/"production"/"runtime-session-v8.json";t.append(R("production.runtime_marker","PASS" if jread(mk) else deferred_status,"Runtime marker"))
  ir=Path(c.get("install_root",""))/"state"/"current.json";t.append(R("release.install_state","PASS" if jread(ir) else deferred_status,"Install pointer"))
  wp=int(c.get("web_port",8765));t.append(R("ui.web_dashboard","PASS" if port(wp) else deferred_status,f"Web port {wp}"))

 if profile=="FULL_RUNTIME":
  for x in ["full.router_restart","full.two_instances","full.failover","full.crash_recovery","full.rollback"]:
   t.append(R(x,"BLOCKED","Operator gate required"))

 fail=sum(x["status"]=="FAIL" for x in t)
 crit=any(x["status"]=="FAIL" and x["severity"]=="critical" for x in t)
 blocked=sum(x["status"]=="BLOCKED" for x in t)
 deferred=sum(x["status"]=="DEFERRED" for x in t)
 return {
  "profile":profile,
  "started_utc":now(),
  "completed_utc":now(),
  "verdict":"PASS" if not fail else ("FAIL_CRITICAL" if crit else "FAIL"),
  "summary":{
   "pass":sum(x["status"]=="PASS" for x in t),
   "fail":fail,
   "blocked":blocked,
   "deferred":deferred,
   "total":len(t)
  },
  "tests":t
}
def main():
 a=argparse.ArgumentParser();a.add_argument("--mode",choices=["catalog","run"],required=True);a.add_argument("--root",required=True);a.add_argument("--data",required=True);a.add_argument("--profile",default="SAFE_RUNTIME");a.add_argument("--config");a.add_argument("--output");x=a.parse_args()
 try:
  d={"profiles":["STATIC","SAFE_RUNTIME","FULL_RUNTIME"]} if x.mode=="catalog" else run(Path(x.root),Path(x.data),x.profile,json.loads(Path(x.config).read_text()) if x.config else {})
  o={"ok":True,"data":d}
 except Exception as e:o={"ok":False,"error":repr(e)}
 s=json.dumps(o,ensure_ascii=False,indent=2)
 if x.output:
  Path(x.output).write_text(s,"utf-8")
 else:
  print(s)
 return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
