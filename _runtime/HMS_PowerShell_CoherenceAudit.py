#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path

def audit(path:Path,expected_version=None,expected_manifest=None):
    s=path.read_text("utf-8-sig",errors="replace")
    assignments=set(re.findall(r'\$script:([A-Za-z_][\w]*)\s*=',s))
    refs=set(re.findall(r'\$script:([A-Za-z_][\w]*)',s))
    missing_vars=sorted(refs-assignments)

    start=s.find("$script:Defaults = @{")
    if start<0:
        defaults=set()
    else:
        end=s.find("\n}",start)
        block=s[start:end if end>=0 else len(s)]
        defaults=set(re.findall(r'^\s*([A-Za-z_][\w]*)\s*=',block,re.M))
    setting_refs=set(re.findall(r'\$script:S\.([A-Za-z_][\w]*)',s))
    missing_settings=sorted(setting_refs-defaults)

    ver=re.search(r'\$script:Version\s*=\s*"([^"]+)"',s)
    version=ver.group(1) if ver else None
    version_ok=(expected_version is None or version==expected_version)
    manifest_ok=(expected_manifest is None or expected_manifest in s)

    high_conf=[]
    patterns={
        "COMMAND_GLUE":r'\b(?:Get-Date|Test-Path|Get-Process|Get-Content|Copy-Item|Move-Item|Remove-Item|Join-Path|Start-Process|Stop-Process)-[A-Za-z]',
        "PAREN_OPERATOR_GLUE":r'\)-(?=eq|ne|gt|ge|lt|le|in|notin|and|or)',
    }
    for code,pat in patterns.items():
        for m in re.finditer(pat,s):
            line=s.count("\n",0,m.start())+1
            high_conf.append({"code":code,"line":line,"token":m.group(0)})

    verdict="PASS" if not missing_vars and not missing_settings and version_ok and manifest_ok else "FAIL"
    return {
        "verdict":verdict,"version":version,"version_ok":version_ok,"manifest_ok":manifest_ok,
        "script_variables":{"referenced":len(refs),"assigned":len(assignments),"missing":missing_vars},
        "settings":{"referenced":len(setting_refs),"declared":len(defaults),"missing":missing_settings},
        "high_confidence_compact_syntax_findings":high_conf,
        "note":"Compact-syntax findings are advisory unless they match high-confidence command/operator glue. A real Windows PowerShell parser/runtime remains the final authority."
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--file",required=True);ap.add_argument("--version");ap.add_argument("--manifest");ap.add_argument("--output")
    a=ap.parse_args()
    try:o={"ok":True,"data":audit(Path(a.file),a.version,a.manifest)}
    except Exception as e:o={"ok":False,"error":repr(e)}
    txt=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt);return 0 if o.get("ok") and o["data"]["verdict"]=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
