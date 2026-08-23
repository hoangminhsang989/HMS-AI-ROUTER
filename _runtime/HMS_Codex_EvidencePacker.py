#!/usr/bin/env python3
import argparse,json,re,zipfile,hashlib,shutil
from pathlib import Path
from datetime import datetime
def red(s):
 s=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}',r'\1[REDACTED]',s)
 s=re.sub(r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}','[JWT_REDACTED]',s)
 s=re.sub(r'(?i)(access[_-]?token|refresh[_-]?token|api[_-]?key|authorization)\s*[:=]\s*["\']?([^"\'\s,}]+)',r'\1=[REDACTED]',s)
 return s
def main():
 a=argparse.ArgumentParser();a.add_argument("--report",required=True);a.add_argument("--out-dir",required=True);a.add_argument("--output");x=a.parse_args()
 out=Path(x.out_dir);out.mkdir(parents=True,exist_ok=True);stamp=datetime.now().strftime("%Y%m%d-%H%M%S");stage=out/f"stage-{stamp}";stage.mkdir()
 p=stage/"validation-report.json";p.write_text(red(Path(x.report).read_text("utf-8-sig")),"utf-8")
 (stage/"manifest.json").write_text(json.dumps({"contains_raw_oauth":False,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()},indent=2),"utf-8")
 zpath=out/f"HMS_validation_evidence_{stamp}.zip"
 with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
  for f in stage.iterdir():z.write(f,f.name)
 with zipfile.ZipFile(zpath) as z:
  if z.testzip():raise RuntimeError("zip integrity")
 o={"ok":True,"zip":str(zpath)};s=json.dumps(o,indent=2)
 if x.output:Path(x.output).write_text(s,"utf-8")
 print(s)
if __name__=="__main__":main()
