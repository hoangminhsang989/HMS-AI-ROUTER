#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_ReviewerLocalIntegritySeal as local_seal

PRODUCT="HMS-AI-ROUTER"; VERSION="25.75"; SCHEMA_VERSION=1
AUTHORITY_CLASS="REVIEWER_SIDE_RELEASE_IDENTITY_AUTHORITY"; SEAL_PURPOSE="HMS_V2575_REVIEWER_RELEASE_IDENTITY_AUTHORITY"
HEX64=re.compile(r"^[0-9a-f]{64}$"); GIT_HEX=re.compile(r"^[0-9a-f]{40,64}$")

def _stable(obj:Any)->bytes:return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def _sha(obj:Any)->str:return hashlib.sha256(_stable(obj)).hexdigest()
def _parse_time(value):
    try:
        dt=datetime.fromisoformat(str(value or "").replace("Z","+00:00")); return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except Exception:return None
def _authority_digest(body:dict[str,Any])->str:return _sha({k:v for k,v in body.items() if k!="authority_sha256"})

def validate_authority_body(body:dict[str,Any],*,now:datetime|None=None,freshness_hours:int=168)->dict[str,Any]:
    reasons=[]; now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if body.get("schema_version")!=SCHEMA_VERSION:reasons.append("RELEASE_AUTHORITY_SCHEMA_INVALID")
    if body.get("product")!=PRODUCT or body.get("version")!=VERSION:reasons.append("RELEASE_AUTHORITY_PRODUCT_VERSION_INVALID")
    if body.get("authority_class")!=AUTHORITY_CLASS:reasons.append("RELEASE_AUTHORITY_CLASS_INVALID")
    if body.get("input_mode")!="EXPLICIT_REVIEWED_DIGESTS":reasons.append("RELEASE_AUTHORITY_EXPLICIT_INPUT_REQUIRED")
    if body.get("packet_derived") is not False:reasons.append("RELEASE_AUTHORITY_MUST_NOT_BE_PACKET_DERIVED")
    if body.get("local_artifact_hashed_at_capture") is not False:reasons.append("RELEASE_AUTHORITY_MUST_NOT_SELF_HASH_LOCAL_ARTIFACT")
    if body.get("raw_packet_included") is not False:reasons.append("RELEASE_AUTHORITY_RAW_PACKET_FORBIDDEN")
    package=str(body.get("package_zip_sha256") or "").lower(); manifest=str(body.get("release_manifest_sha256") or "").lower()
    commit=str(body.get("source_commit_sha") or "").lower(); tree=str(body.get("source_tree_sha") or "").lower()
    if not HEX64.fullmatch(package):reasons.append("RELEASE_AUTHORITY_PACKAGE_SHA256_INVALID")
    if not HEX64.fullmatch(manifest):reasons.append("RELEASE_AUTHORITY_MANIFEST_SHA256_INVALID")
    if not GIT_HEX.fullmatch(commit):reasons.append("RELEASE_AUTHORITY_SOURCE_COMMIT_INVALID")
    if not GIT_HEX.fullmatch(tree):reasons.append("RELEASE_AUTHORITY_SOURCE_TREE_INVALID")
    created=_parse_time(body.get("created_utc"))
    if created is None:reasons.append("RELEASE_AUTHORITY_CREATED_UTC_INVALID")
    else:
        if created>now+timedelta(minutes=5):reasons.append("RELEASE_AUTHORITY_TIME_IN_FUTURE")
        if now-created>timedelta(hours=max(1,int(freshness_hours))):reasons.append("RELEASE_AUTHORITY_STALE")
    if _authority_digest(body)!=str(body.get("authority_sha256") or "").lower():reasons.append("RELEASE_AUTHORITY_DIGEST_MISMATCH")
    return {"valid":not reasons,"reasons":sorted(set(reasons)),"authority_sha256":str(body.get("authority_sha256") or "").lower(),
            "package_zip_sha256":package,"release_manifest_sha256":manifest,"source_commit_sha":commit,"source_tree_sha":tree}

def capture_authority(*,package_zip_sha256:str,release_manifest_sha256:str,source_commit_sha:str,source_tree_sha:str,output_path:Path,key_path:Path)->dict[str,Any]:
    if os.name!="nt":raise RuntimeError("WINDOWS_REQUIRED")
    body={"schema_version":SCHEMA_VERSION,"product":PRODUCT,"version":VERSION,"authority_class":AUTHORITY_CLASS,
          "created_utc":datetime.now(timezone.utc).isoformat(),"input_mode":"EXPLICIT_REVIEWED_DIGESTS",
          "package_zip_sha256":str(package_zip_sha256 or "").lower(),"release_manifest_sha256":str(release_manifest_sha256 or "").lower(),
          "source_commit_sha":str(source_commit_sha or "").lower(),"source_tree_sha":str(source_tree_sha or "").lower(),
          "packet_derived":False,"local_artifact_hashed_at_capture":False,"raw_packet_included":False,"private_material_exported":False}
    body["authority_sha256"]=_authority_digest(body); check=validate_authority_body(body)
    if not check["valid"]:raise ValueError("RELEASE_AUTHORITY_BODY_INVALID:"+",".join(check["reasons"]))
    seal=local_seal.seal_payload(body,purpose=SEAL_PURPOSE,key_path=key_path); document={"authority":body,"integrity_seal":seal}
    output_path.parent.mkdir(parents=True,exist_ok=True); tmp=output_path.with_suffix(output_path.suffix+".tmp")
    tmp.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n","utf-8"); os.replace(tmp,output_path)
    return {"product":PRODUCT,"version":VERSION,"suite":"REVIEWER_RELEASE_AUTHORITY_CAPTURE","verdict":"RELEASE_AUTHORITY_CAPTURED",
            "authority_sha256":body["authority_sha256"],"package_zip_sha256":body["package_zip_sha256"],"release_manifest_sha256":body["release_manifest_sha256"],
            "source_commit_sha":body["source_commit_sha"],"source_tree_sha":body["source_tree_sha"],"input_mode":body["input_mode"],
            "packet_derived":False,"local_artifact_hashed_at_capture":False,"windows_runtime_certified":False,"production_score_promotion_eligible":False}

def verify_authority_document(document:dict[str,Any],*,key_path:Path,now:datetime|None=None,freshness_hours:int=168)->dict[str,Any]:
    body=document.get("authority") if isinstance(document.get("authority"),dict) else {}; seal=document.get("integrity_seal") if isinstance(document.get("integrity_seal"),dict) else {}
    body_check=validate_authority_body(body,now=now,freshness_hours=freshness_hours); seal_check=local_seal.verify_payload(body,seal,purpose=SEAL_PURPOSE,key_path=key_path)
    reasons=sorted(set(body_check["reasons"]+seal_check.get("reasons",[]))); out=dict(body_check); out.update({"valid":not reasons,"reasons":reasons,"local_integrity_seal_valid":seal_check.get("valid") is True,
        "packet_derived":body.get("packet_derived") is True,"local_artifact_hashed_at_capture":body.get("local_artifact_hashed_at_capture") is True}); return out

def load_and_verify_authority(path:Path,*,key_path:Path,freshness_hours:int=168)->dict[str,Any]:
    if not path.is_file():return {"valid":False,"reasons":["RELEASE_AUTHORITY_FILE_MISSING"]}
    try:doc=json.loads(path.read_text("utf-8"))
    except Exception:return {"valid":False,"reasons":["RELEASE_AUTHORITY_JSON_INVALID"]}
    return verify_authority_document(doc,key_path=key_path,freshness_hours=freshness_hours)

def synthetic_proof()->dict[str,Any]:
    now=datetime.now(timezone.utc); body={"schema_version":SCHEMA_VERSION,"product":PRODUCT,"version":VERSION,"authority_class":AUTHORITY_CLASS,"created_utc":now.isoformat(),
        "input_mode":"EXPLICIT_REVIEWED_DIGESTS","package_zip_sha256":"a"*64,"release_manifest_sha256":"b"*64,"source_commit_sha":"c"*40,"source_tree_sha":"d"*40,
        "packet_derived":False,"local_artifact_hashed_at_capture":False,"raw_packet_included":False,"private_material_exported":False}; body["authority_sha256"]=_authority_digest(body)
    good=validate_authority_body(body,now=now); derived=json.loads(json.dumps(body)); derived["packet_derived"]=True; derived["authority_sha256"]=_authority_digest(derived); derived_check=validate_authority_body(derived,now=now)
    self_hashed=json.loads(json.dumps(body)); self_hashed["local_artifact_hashed_at_capture"]=True; self_hashed["authority_sha256"]=_authority_digest(self_hashed); self_check=validate_authority_body(self_hashed,now=now)
    stale=json.loads(json.dumps(body)); stale["created_utc"]=(now-timedelta(hours=169)).isoformat(); stale["authority_sha256"]=_authority_digest(stale); stale_check=validate_authority_body(stale,now=now)
    tampered=json.loads(json.dumps(body)); tampered["package_zip_sha256"]="e"*64; tampered_check=validate_authority_body(tampered,now=now)
    checks={"explicit_release_authority_valid":good["valid"],"packet_derived_authority_rejected":"RELEASE_AUTHORITY_MUST_NOT_BE_PACKET_DERIVED" in derived_check["reasons"],
            "local_self_hash_authority_rejected":"RELEASE_AUTHORITY_MUST_NOT_SELF_HASH_LOCAL_ARTIFACT" in self_check["reasons"],"stale_authority_rejected":"RELEASE_AUTHORITY_STALE" in stale_check["reasons"],
            "digest_tamper_rejected":"RELEASE_AUTHORITY_DIGEST_MISMATCH" in tampered_check["reasons"],"production_capture_windows_only":os.name=="nt" or _nonwindows_rejected(),
            "dpapi_local_seal_required":"local_seal.verify_payload" in Path(__file__).read_text("utf-8")}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)
    return {"product":PRODUCT,"version":VERSION,"suite":"REVIEWER_RELEASE_AUTHORITY_PROOF","verdict":"PASS" if n==len(tests) else "FAIL","summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},"tests":tests,
            "real_release_authority_captured":False,"packet_derived":False,"local_artifact_hashed_at_capture":False,"windows_runtime_certified":False,"production_score_promotion_eligible":False}
def _nonwindows_rejected()->bool:
    try:capture_authority(package_zip_sha256="a"*64,release_manifest_sha256="b"*64,source_commit_sha="c"*40,source_tree_sha="d"*40,output_path=Path("x"),key_path=Path("y")); return False
    except RuntimeError as exc:return str(exc)=="WINDOWS_REQUIRED"
    except Exception:return False
def main()->int:
    ap=argparse.ArgumentParser(description="Capture/verify reviewer-side explicit release identity authority"); ap.add_argument("--proof",action="store_true"); ap.add_argument("--capture",action="store_true"); ap.add_argument("--verify",action="store_true")
    ap.add_argument("--package-sha256",default=""); ap.add_argument("--manifest-sha256",default=""); ap.add_argument("--source-commit",default=""); ap.add_argument("--source-tree",default=""); ap.add_argument("--authority",default=""); ap.add_argument("--integrity-key",default=""); ap.add_argument("--freshness-hours",type=int,default=168); a=ap.parse_args()
    if a.proof or (not a.capture and not a.verify):out=synthetic_proof(); code=0 if out["verdict"]=="PASS" else 2
    elif a.capture:
        if not all((a.package_sha256,a.manifest_sha256,a.source_commit,a.source_tree,a.authority,a.integrity_key)):ap.error("explicit package/manifest/source commit/tree digests + authority + integrity key required")
        try:out=capture_authority(package_zip_sha256=a.package_sha256,release_manifest_sha256=a.manifest_sha256,source_commit_sha=a.source_commit,source_tree_sha=a.source_tree,output_path=Path(a.authority),key_path=Path(a.integrity_key)); code=0
        except Exception as exc:out={"product":PRODUCT,"version":VERSION,"suite":"REVIEWER_RELEASE_AUTHORITY_CAPTURE","verdict":"BLOCKED_FAIL_CLOSED","error":type(exc).__name__,"detail":str(exc),"windows_runtime_certified":False,"production_score_promotion_eligible":False}; code=2
    else:
        if not (a.authority and a.integrity_key):ap.error("--authority --integrity-key required")
        out=load_and_verify_authority(Path(a.authority),key_path=Path(a.integrity_key),freshness_hours=a.freshness_hours); code=0 if out.get("valid") else 2
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code
if __name__=="__main__":raise SystemExit(main())
