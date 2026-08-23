#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path

GLUE_PATTERNS={
    "NOT_GLUE":r'-not\$[A-Za-z_]',
    "VAR_OPERATOR_GLUE":r'\$[A-Za-z_][\w.]*-(?:eq|ne|gt|ge|lt|le|in|notin|and|or|like|notlike)\b',
    "PAREN_OPERATOR_GLUE":r'\)-(?=eq|ne|gt|ge|lt|le|in|notin|and|or)\b',
    "BOOLFUNC_OPERATOR_GLUE":r'\b[A-Za-z_][\w-]*-(?:and|or)\(',
    "CONVERT_JSON_DEPTH":r'ConvertTo-Json-Depth\d+',
    "CMD_PAREN_SWITCH":r'\)(?:-ErrorAction|-Force|-PassThru|-WindowStyle|-ArgumentList|-Depth|-Compress)\b',
    "SWITCH_GLUE":r'-(?:File|Raw|Encoding|Recurse|Wait|WindowStyle|PassThru|Force|ErrorAction|Depth|Compress)-(?:ErrorAction|Force|PassThru|WindowStyle|Wait|Depth|Compress)\b',
    "WORD_SWITCH":r'\b(?:LastWriteTime|Name|FullName|Length)-(?:Descending|Ascending)\b',
}
def masked_lines(text):
    lines=text.splitlines()
    out=[];in_here=None
    for raw in lines:
        chars=list(raw)
        if in_here:
            out.append(" "*len(raw))
            if raw.lstrip().startswith(in_here+"@"):in_here=None
            continue
        quote=None;i=0
        while i<len(raw):
            c=raw[i]
            if quote:
                chars[i]=' '
                if c==quote:
                    if i+1<len(raw) and raw[i+1]==quote:
                        chars[i+1]=' ';i+=2;continue
                    quote=None
                i+=1;continue
            if c in ("'",'"'):
                if i>0 and raw[i-1]=='@':
                    chars[i-1]=' ';chars[i]=' '
                    for j in range(i+1,len(raw)):chars[j]=' '
                    in_here=c;break
                quote=c;chars[i]=' ';i+=1;continue
            if c=='#':
                for j in range(i,len(raw)):chars[j]=' '
                break
            i+=1
        out.append(''.join(chars))
    return out

def audit(path:Path,expected_version=None,expected_manifest=None):
    text=path.read_text("utf-8-sig",errors="replace")
    lines=text.splitlines()
    masks=masked_lines(text)
    findings=[]
    by_code={}
    for code,pat in GLUE_PATTERNS.items():
        rx=re.compile(pat,re.I);c=0
        for i,line in enumerate(masks,1):
            for m in rx.finditer(line):
                c+=1
                findings.append({"code":code,"line":i,"token":m.group(0),"source":lines[i-1].strip()[:500]})
        by_code[code]=c

    refs=set(re.findall(r'\$script:([A-Za-z_][\w]*)',text))
    assigned=set(re.findall(r'\$script:([A-Za-z_][\w]*)\s*=',text))
    missing_vars=sorted(refs-assigned)

    ds=text.find("$script:Defaults = @{")
    de=text.find("\n}",ds) if ds>=0 else -1
    block=text[ds:de if de>=0 else len(text)] if ds>=0 else ""
    defaults=re.findall(r'^\s*([A-Za-z_][\w]*)\s*=',block,re.M)
    default_set=set(defaults)
    duplicates=sorted({x for x in defaults if defaults.count(x)>1})
    settings_refs=set(re.findall(r'\$script:S\.([A-Za-z_][\w]*)',text))
    missing_settings=sorted(settings_refs-default_set)

    vm=re.search(r'\$script:Version\s*=\s*"([^"]+)"',text)
    version=vm.group(1) if vm else None
    version_ok=(expected_version is None or version==expected_version)
    manifest_ok=(expected_manifest is None or expected_manifest in text)
    total=len(findings)
    verdict="PASS" if (total==0 and not missing_vars and not missing_settings and not duplicates and version_ok and manifest_ok) else "FAIL"
    return {
        "verdict":verdict,"version":version,"version_ok":version_ok,"manifest_ok":manifest_ok,
        "glue":{"total":total,"by_code":by_code,"findings":findings},
        "script_variables":{"referenced":len(refs),"assigned":len(assigned),"missing":missing_vars},
        "settings":{"referenced":len(settings_refs),"declared":len(default_set),"missing":missing_settings,"duplicates":duplicates},
        "note":"Static lexical gate only. A real Windows PowerShell 5.1 parse/runtime remains authoritative."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--file",required=True);ap.add_argument("--version");ap.add_argument("--manifest");ap.add_argument("--output")
    a=ap.parse_args()
    try:
        data=audit(Path(a.file),a.version,a.manifest);o={"ok":data["verdict"]=="PASS","data":data}
    except Exception as e:o={"ok":False,"error":repr(e)}
    txt=json.dumps(o,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(txt,"utf-8")
    print(txt)
    return 0 if o.get("ok") else 2
if __name__=="__main__":raise SystemExit(main())
