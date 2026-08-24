#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import HMS_Codex_TargetMachineCertification as engine

PRODUCT="HMS-AI-ROUTER"; VERSION="25.75"; SCHEMA_VERSION=2; SOURCE_CERTIFICATION="TARGET_MACHINE_WINDOWS_CODEX_LAN_SOAK"
ENGINE_VERSION=str(getattr(engine,"VERSION","UNKNOWN")); RUNTIME_DIR=Path(__file__).resolve().parent; ARTIFACT_ROOT=RUNTIME_DIR.parent
BINDING_SCHEMA="HMS_V25_75_TARGET_ARTIFACT_BINDING_V1"
CRITICAL_ARTIFACT_PATHS=(
    "_runtime/HMS_AI_ROUTER_v25.23.1.ps1","_runtime/HMS_Codex_TargetMachineCertificationV2575.py",
    "_runtime/HMS_Codex_TargetMachineCertification.py","_runtime/HMS_Codex_RealCertification.py",
    "_runtime/HMS_Codex_LiveQuotaIntelligence.py","_runtime/HMS_Codex_ExternalWindowsCaseReportExporter.py",
    "_runtime/HMS_Codex_ExternalWindowsEvidenceRunner.py","_runtime/HMS_Codex_ExternalWindowsReviewPacketIngest.py",
)

def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def _sha_bytes(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def _safe_rel(value:Any)->str:
    raw=str(value or "").replace("\\","/")
    if not raw or "\x00" in raw or raw.startswith("/") or ":" in raw:return ""
    p=PurePosixPath(raw)
    if p.is_absolute() or any(part in {"",".",".."} or part.endswith(".") or part.endswith(" ") for part in p.parts):return ""
    return p.as_posix()

def _manifest_index(manifest:dict[str,Any])->tuple[dict[str,dict[str,Any]],list[str]]:
    reasons=[]; rows=manifest.get("files") if isinstance(manifest.get("files"),list) else []
    if manifest.get("version")!=VERSION:reasons.append("ARTIFACT_MANIFEST_VERSION_MISMATCH")
    if str(manifest.get("product") or "")!=PRODUCT:reasons.append("ARTIFACT_MANIFEST_PRODUCT_MISMATCH")
    if int(manifest.get("file_count") or 0)!=len(rows) or not rows:reasons.append("ARTIFACT_MANIFEST_FILE_COUNT_INVALID")
    index={}; windows_keys=set()
    for row in rows:
        if not isinstance(row,dict):reasons.append("ARTIFACT_MANIFEST_ROW_INVALID");continue
        path=_safe_rel(row.get("path")); digest=str(row.get("sha256") or "").lower()
        try:size=int(row.get("size"))
        except (TypeError,ValueError):size=-1
        if not path or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest) or size<0:
            reasons.append("ARTIFACT_MANIFEST_ROW_INVALID");continue
        win_key=path.casefold()
        if path in index or win_key in windows_keys:reasons.append("ARTIFACT_MANIFEST_DUPLICATE_WINDOWS_PATH:"+path);continue
        windows_keys.add(win_key); index[path]={"path":path,"sha256":digest,"size":size}
    return index,sorted(set(reasons))

def _normalize_zip_members(zf:zipfile.ZipFile,manifest_paths:set[str])->tuple[dict[str,zipfile.ZipInfo],list[str]]:
    reasons=[]; files=[info for info in zf.infolist() if not info.is_dir()]; raw_names=[_safe_rel(info.filename) for info in files]
    if any(not name for name in raw_names):reasons.append("ARTIFACT_ZIP_UNSAFE_PATH")
    candidates=[]
    for prefix_parts in (0,1):
        mapped={}; win_keys=set(); ok=True
        for info,name in zip(files,raw_names):
            if not name:ok=False;break
            parts=PurePosixPath(name).parts
            if len(parts)<=prefix_parts:ok=False;break
            rel=PurePosixPath(*parts[prefix_parts:]).as_posix(); win_key=rel.casefold()
            if rel in mapped or win_key in win_keys:ok=False;break
            mapped[rel]=info; win_keys.add(win_key)
        if ok and set(mapped)==manifest_paths:candidates.append(mapped)
    if len(candidates)!=1:
        reasons.append("ARTIFACT_ZIP_FILESET_NOT_EXACT_MANIFEST"); return {},sorted(set(reasons))
    return candidates[0],sorted(set(reasons))

def validate_artifact_binding(runtime_root:Path,release_manifest:Path,package_zip:Path)->dict[str,Any]:
    reasons=[]; runtime_root=runtime_root.resolve(); artifact_root=runtime_root.parent if runtime_root.name.lower()=="_runtime" else runtime_root
    if not release_manifest.is_file():reasons.append("ARTIFACT_RELEASE_MANIFEST_MISSING"); manifest_raw=b""; manifest={}
    else:
        manifest_raw=release_manifest.read_bytes()
        try:
            loaded=json.loads(manifest_raw.decode("utf-8-sig")); manifest=loaded if isinstance(loaded,dict) else {}
            if not isinstance(loaded,dict):reasons.append("ARTIFACT_RELEASE_MANIFEST_INVALID_JSON")
        except Exception:manifest={};reasons.append("ARTIFACT_RELEASE_MANIFEST_INVALID_JSON")
    if not package_zip.is_file():reasons.append("ARTIFACT_PACKAGE_ZIP_MISSING")
    index,manifest_reasons=_manifest_index(manifest); reasons.extend(manifest_reasons); manifest_paths=set(index)
    for critical in CRITICAL_ARTIFACT_PATHS:
        if critical not in index:reasons.append("ARTIFACT_MANIFEST_CRITICAL_PATH_MISSING:"+critical)
    local_verified=[]
    for rel,row in index.items():
        local=artifact_root/Path(rel)
        try:resolved=local.resolve(); resolved.relative_to(artifact_root.resolve())
        except Exception:reasons.append("ARTIFACT_RUNTIME_PATH_ESCAPE:"+rel);continue
        if not local.is_file():reasons.append("ARTIFACT_RUNTIME_FILE_MISSING:"+rel);continue
        if local.stat().st_size!=row["size"]:reasons.append("ARTIFACT_RUNTIME_SIZE_MISMATCH:"+rel)
        if _sha_file(local)!=row["sha256"]:reasons.append("ARTIFACT_RUNTIME_SHA256_MISMATCH:"+rel)
        else:local_verified.append(rel)
    zip_verified=[]; zip_members={}
    if package_zip.is_file():
        try:
            with zipfile.ZipFile(package_zip,"r") as zf:
                zip_members,zip_reasons=_normalize_zip_members(zf,manifest_paths); reasons.extend(zip_reasons)
                for rel,row in index.items():
                    info=zip_members.get(rel)
                    if info is None:continue
                    if int(info.file_size)!=row["size"]:reasons.append("ARTIFACT_ZIP_SIZE_MISMATCH:"+rel)
                    with zf.open(info,"r") as fh:digest=_sha_bytes(fh.read())
                    if digest!=row["sha256"]:reasons.append("ARTIFACT_ZIP_SHA256_MISMATCH:"+rel)
                    else:zip_verified.append(rel)
        except (OSError,zipfile.BadZipFile,RuntimeError) as exc:reasons.append("ARTIFACT_ZIP_INVALID:"+type(exc).__name__)
    reasons=sorted(set(reasons)); all_count=len(index); full_local=len(local_verified)==all_count; full_zip=len(zip_verified)==all_count and len(zip_members)==all_count
    return {"pass":not reasons and all_count>0 and full_local and full_zip,"binding_schema":BINDING_SCHEMA,
            "release_manifest_sha256":_sha_bytes(manifest_raw) if manifest_raw else "","package_zip_sha256":_sha_file(package_zip) if package_zip.is_file() else "",
            "manifest_version":str(manifest.get("version") or ""),"manifest_product":str(manifest.get("product") or ""),"manifest_file_count":all_count,
            "filesystem_files_verified":len(local_verified),"zip_files_verified":len(zip_verified),"exact_zip_manifest_fileset":full_zip,
            "critical_files_required":len(CRITICAL_ARTIFACT_PATHS),"critical_files_verified":sum(1 for x in CRITICAL_ARTIFACT_PATHS if x in local_verified and x in zip_verified),
            "reasons":reasons,"runtime_root_ref":"artifact-root-relative-only"}

def run(args:argparse.Namespace)->dict[str,Any]:
    base=engine.run(args); binding=validate_artifact_binding(Path(args.root).resolve(),Path(args.release_manifest),Path(args.package_zip))
    stages=base.get("stages") if isinstance(base.get("stages"),dict) else {}; exact_seven=tuple(stages.keys())==tuple(engine.SAFE_STAGES) and all(isinstance(stages.get(cid),dict) and stages[cid].get("pass") is True for cid in engine.SAFE_STAGES)
    production_pass=base.get("verdict")=="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" and exact_seven and binding.get("pass") is True
    verdict="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" if production_pass else ("TARGET_MACHINE_ARTIFACT_BINDING_REQUIRED" if exact_seven else str(base.get("verdict") or "BLOCKED_FAIL_CLOSED"))
    blockers=list(base.get("blockers") or []); blockers+=[] if binding.get("pass") is True else ["ARTIFACT_BINDING"]
    return {"product":PRODUCT,"edition":"CODEX_ONLY","version":VERSION,"schema_version":SCHEMA_VERSION,"suite":"TARGET_MACHINE_CERTIFICATION","generated_utc":utcnow(),"verdict":verdict,
            "production_certification":SOURCE_CERTIFICATION if production_pass else "NOT_CLAIMED","summary":{"stages_pass":sum(1 for cid in engine.SAFE_STAGES if isinstance(stages.get(cid),dict) and stages[cid].get("pass") is True),"stages_total":len(engine.SAFE_STAGES),"production_certified":production_pass,"artifact_binding_pass":binding.get("pass") is True},
            "stages":stages,"artifact_binding":binding,"certification_engine":{"module":"HMS_Codex_TargetMachineCertification.py","engine_version":ENGINE_VERSION,"wrapper_version":VERSION,"legacy_engine_verdict":str(base.get("verdict") or "")},
            "blockers":sorted(set(str(x) for x in blockers if str(x))),"safety":dict(base.get("safety") or {}),
            "claim_boundary":"v25.75 production PASS requires the seven real target-machine stages plus exact release identity: every manifest file must match the target filesystem and ZIP by Windows-safe relative path, size and SHA-256; ZIP file-set must equal manifest file-set with at most one enclosing package-root prefix; package/manifest digests are bound downstream. No v25.53 report is relabeled as v25.75."}

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(name,ok):tests.append({"name":name,"status":"PASS" if ok else "FAIL"})
    with tempfile.TemporaryDirectory(prefix="hms-v2575-artifact-bind-") as td:
        temp=Path(td); rows=[]
        for rel in CRITICAL_ARTIFACT_PATHS:
            src=ARTIFACT_ROOT/rel; rows.append({"path":rel,"size":src.stat().st_size,"sha256":_sha_file(src)})
        manifest={"product":PRODUCT,"version":VERSION,"file_count":len(rows),"files":rows}; mp=temp/"manifest.json"; mp.write_text(json.dumps(manifest),"utf-8")
        package=temp/"package.zip"
        with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in CRITICAL_ARTIFACT_PATHS:zf.write(ARTIFACT_ROOT/rel,arcname="HMS-AI-ROUTER/"+rel)
        good=validate_artifact_binding(RUNTIME_DIR,mp,package); add("exact_manifest_filesystem_zip_binding_passes",good["pass"] is True); add("exact_zip_fileset_verified",good["exact_zip_manifest_fileset"] is True)
        old=dict(manifest); old["version"]="25.53"; op=temp/"old.json"; op.write_text(json.dumps(old),"utf-8"); oldr=validate_artifact_binding(RUNTIME_DIR,op,package); add("old_manifest_version_rejected","ARTIFACT_MANIFEST_VERSION_MISMATCH" in oldr["reasons"])
        badzip=temp/"bad.zip"
        with zipfile.ZipFile(badzip,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in CRITICAL_ARTIFACT_PATHS:
                if rel==CRITICAL_ARTIFACT_PATHS[0]:zf.writestr("HMS-AI-ROUTER/"+rel,b"tampered")
                else:zf.write(ARTIFACT_ROOT/rel,arcname="HMS-AI-ROUTER/"+rel)
        badr=validate_artifact_binding(RUNTIME_DIR,mp,badzip); add("tampered_package_file_rejected",any(x.startswith("ARTIFACT_ZIP_") for x in badr["reasons"]))
        extra=temp/"extra.zip"
        with zipfile.ZipFile(extra,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in CRITICAL_ARTIFACT_PATHS:zf.write(ARTIFACT_ROOT/rel,arcname="HMS-AI-ROUTER/"+rel)
            zf.writestr("HMS-AI-ROUTER/extra-unmanifested.txt",b"extra")
        extrar=validate_artifact_binding(RUNTIME_DIR,mp,extra); add("unmanifested_extra_zip_file_rejected","ARTIFACT_ZIP_FILESET_NOT_EXACT_MANIFEST" in extrar["reasons"])
        def unsafe_manifest(path_value):
            u=dict(manifest); u["files"]=list(manifest["files"])+[{"path":path_value,"size":1,"sha256":"a"*64}]; u["file_count"]=len(u["files"]); p=temp/(hashlib.sha256(path_value.encode()).hexdigest()[:8]+".json"); p.write_text(json.dumps(u),"utf-8"); return validate_artifact_binding(RUNTIME_DIR,p,package)
        add("manifest_parent_escape_rejected","ARTIFACT_MANIFEST_ROW_INVALID" in unsafe_manifest("../escape.txt")["reasons"])
        add("manifest_absolute_path_rejected","ARTIFACT_MANIFEST_ROW_INVALID" in unsafe_manifest("/absolute.txt")["reasons"])
        add("manifest_drive_or_ads_path_rejected","ARTIFACT_MANIFEST_ROW_INVALID" in unsafe_manifest("C:/escape.txt")["reasons"] and "ARTIFACT_MANIFEST_ROW_INVALID" in unsafe_manifest("file.txt:ads")["reasons"])
        collision=dict(manifest); first=dict(collision["files"][0]); first["path"]=str(first["path"]).swapcase(); collision["files"]=list(collision["files"])+[first]; collision["file_count"]=len(collision["files"]); cp=temp/"case-collision.json"; cp.write_text(json.dumps(collision),"utf-8"); cr=validate_artifact_binding(RUNTIME_DIR,cp,package); add("manifest_case_insensitive_collision_rejected",any(x.startswith("ARTIFACT_MANIFEST_DUPLICATE_WINDOWS_PATH:") for x in cr["reasons"]))
        add("proof_grants_no_production_authority",True)
    failed=[x for x in tests if x["status"]!="PASS"]; return {"product":PRODUCT,"version":VERSION,"suite":"TARGET_MACHINE_CERTIFICATION_V2575_ARTIFACT_BINDING_PROOF","verdict":"PASS" if not failed else "FAIL","summary":{"pass":len(tests)-len(failed),"fail":len(failed),"total":len(tests)},"tests":tests,"synthetic_fixture_only":True,"real_target_certification_executed":False,"windows_runtime_certified":False,"production_score_promotion_eligible":False}

def main()->int:
    ap=argparse.ArgumentParser(description="HMS v25.75 artifact-bound Target-Machine Certification Runner"); ap.add_argument("--proof",action="store_true"); ap.add_argument("--root",default=str(RUNTIME_DIR)); ap.add_argument("--data-dir",default=str(Path(os.environ.get("LOCALAPPDATA") or ".")/"HMS_AI_MultiRouter")); ap.add_argument("--instance-store",default=""); ap.add_argument("--codex",default=""); ap.add_argument("--powershell",default=""); ap.add_argument("--timeout-sec",type=float,default=2.0); ap.add_argument("--quota-snapshot",default=""); ap.add_argument("--lan-snapshot",default=""); ap.add_argument("--shared",default=""); ap.add_argument("--real-cert-evidence",default=""); ap.add_argument("--failover-evidence",default=""); ap.add_argument("--failover-max-age-hours",type=float,default=168.0); ap.add_argument("--soak-state-dir",default=""); ap.add_argument("--soak6-evidence",default=""); ap.add_argument("--soak24-evidence",default=""); ap.add_argument("--release-manifest",default=""); ap.add_argument("--package-zip",default=""); ap.add_argument("--output",default=""); a=ap.parse_args()
    if a.proof:out=synthetic_proof(); code=0 if out["verdict"]=="PASS" else 2
    else:
        try:out=run(a); code=0 if out.get("verdict")=="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" else 2
        except Exception as exc:out={"product":PRODUCT,"version":VERSION,"suite":"TARGET_MACHINE_CERTIFICATION","generated_utc":utcnow(),"verdict":"BLOCKED_FAIL_CLOSED","production_certification":"NOT_CLAIMED","error":type(exc).__name__,"detail":str(exc),"windows_runtime_certified":False,"production_score_promotion_eligible":False}; code=2
    if a.output:engine.atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code
if __name__=="__main__":raise SystemExit(main())
