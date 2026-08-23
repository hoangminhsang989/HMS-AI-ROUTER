#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,shutil
from pathlib import Path
from datetime import datetime
BLOCKS=("model_providers.hms_api_router","model_providers.hms_instance_router","model_providers.hms_multirouter")
def audit(p):
    if not p.exists():return {"exists":False,"issues":["missing config.toml"],"issue_count":1}
    t=p.read_text("utf-8",errors="replace");issues=[]
    hs=list(re.finditer(r"(?m)^\s*model_provider\s*=",t))
    if len(hs)>1:issues.append(f"duplicate root key: model_provider ({len(hs)})")
    for b in BLOCKS:
        n=len(list(re.finditer(rf"(?m)^\[{re.escape(b)}\]\s*$",t)))
        if n>1:issues.append(f"duplicate block: [{b}] ({n})")
    ft=re.search(r"(?m)^\[",t);fk=re.search(r"(?m)^\s*model_provider\s*=",t)
    if ft and fk and fk.start()>ft.start():issues.append("model_provider after table")
    return {"exists":True,"issues":issues,"issue_count":len(issues)}
def sanitize(p):
    before=audit(p)
    if not p.exists():return {"changed":False,"backup":None,"before":before,"after":before}
    t=p.read_text("utf-8",errors="replace");orig=t;stamp=datetime.now().strftime("%Y%m%d-%H%M%S");b=p.with_name(p.name+f".hms-backup-{stamp}");shutil.copy2(p,b)
    vals=re.findall(r'(?m)^\s*model_provider\s*=\s*(.+?)\s*$',t);t=re.sub(r'(?m)^\s*model_provider\s*=.*(?:\r?\n)?',"",t)
    if vals:t=f"model_provider = {vals[-1].strip()}\n"+t.lstrip("\r\n")
    for block in BLOCKS:
        pat=rf"(?ms)^\[{re.escape(block)}\]\s*\r?\n.*?(?=^\[|\Z)";ms=list(re.finditer(pat,t))
        if len(ms)>1:
            keep=ms[-1].group(0).rstrip()+"\n";t=re.sub(pat,"",t);t=t.rstrip()+"\n\n"+keep
    if t!=orig:
        tmp=p.with_suffix(p.suffix+".hms.tmp");tmp.write_text(t,"utf-8");tmp.replace(p)
    return {"changed":t!=orig,"backup":str(b),"before":before,"after":audit(p)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--path",required=True);ap.add_argument("--mode",choices=("audit","sanitize"),default="audit");ap.add_argument("--output")
    a=ap.parse_args();p=Path(a.path)
    try:o={"ok":True,"mode":a.mode,"data":audit(p) if a.mode=="audit" else sanitize(p)}
    except Exception as e:o={"ok":False,"error":repr(e)}
    s=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(s,"utf-8")
    print(s);return 0 if o.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
