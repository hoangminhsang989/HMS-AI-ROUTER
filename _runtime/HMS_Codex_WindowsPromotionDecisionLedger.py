#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path

VERSION="25.75"; COCKPIT_BASELINE="1.3.28"; GENESIS="0"*64
HEX64=re.compile(r"^[0-9a-f]{64}$"); DECISIONS={"APPROVE","REJECT","INVALIDATE"}
LANES={"TERMINAL_PTY","PROJECT_RESUME","OPTIONAL_GPU"}

def _stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _sha(v): return hashlib.sha256(v).hexdigest()
def _hex(v): return HEX64.fullmatch(str(v or "").lower()) is not None
def reviewer_ref(identity,salt):
    if len(identity.strip())<2 or len(salt)<16: raise ValueError("identity/salt too short")
    return "rvw_"+_sha(("reviewer\0"+salt+"\0"+identity.strip()).encode())[:32]
def _hash(r): return _sha(_stable({k:v for k,v in r.items() if k!="decision_sha256"}))

def read_ledger(path):
    if not path.exists(): return []
    out=[]
    for i,line in enumerate(path.read_text("utf-8").splitlines(),1):
        if line.strip():
            v=json.loads(line)
            if not isinstance(v,dict): raise ValueError(f"line {i} is not object")
            out.append(v)
    return out

def validate_ledger(records):
    reasons=[]; prev=GENESIS; epoch=0
    for pos,r in enumerate(records,1):
        if r.get("index")!=pos: reasons.append(f"INDEX_SEQUENCE_INVALID:{pos}")
        if r.get("product")!="HMS-AI-ROUTER" or r.get("version")!=VERSION: reasons.append(f"AUTHORITY_INVALID:{pos}")
        if r.get("decision") not in DECISIONS or r.get("lane") not in LANES: reasons.append(f"DECISION_OR_LANE_INVALID:{pos}")
        if not re.fullmatch(r"rvw_[0-9a-f]{32}",str(r.get("reviewer_ref") or "")): reasons.append(f"REVIEWER_REF_INVALID:{pos}")
        if not _hex(r.get("evidence_sha256")) or not _hex(r.get("manifest_sha256")): reasons.append(f"DIGEST_INVALID:{pos}")
        if r.get("previous_decision_sha256")!=prev or r.get("decision_sha256")!=_hash(r): reasons.append(f"HASH_CHAIN_INVALID:{pos}")
        e=r.get("epoch")
        if not isinstance(e,int) or e<1 or e<epoch or e>epoch+1: reasons.append(f"EPOCH_INVALID:{pos}")
        else: epoch=max(epoch,e)
        prev=str(r.get("decision_sha256") or "")
    return {"valid":not reasons,"reasons":reasons,"record_count":len(records),"ledger_tail_sha256":prev,"current_epoch":epoch}

def build_decision(records,*,decision,reviewer_ref,evidence_sha256,manifest_sha256,package_version,
                   cockpit_baseline,lane,reason_codes=None,note_vi=""):
    decision=decision.upper(); lane=lane.upper()
    if decision not in DECISIONS or lane not in LANES: raise ValueError("decision/lane invalid")
    if not re.fullmatch(r"rvw_[0-9a-f]{32}",reviewer_ref): raise ValueError("pseudonymous reviewer_ref required")
    if not _hex(evidence_sha256) or not _hex(manifest_sha256): raise ValueError("sha256 required")
    if decision!="INVALIDATE" and cockpit_baseline!=COCKPIT_BASELINE: raise ValueError("baseline drift")
    if decision=="INVALIDATE" and not str(cockpit_baseline).strip(): raise ValueError("observed baseline required for invalidation")
    valid=validate_ledger(records)
    if not valid["valid"]: raise ValueError("existing ledger invalid")
    current=valid["current_epoch"] or 1
    if records and records[-1].get("decision")=="INVALIDATE" and decision!="INVALIDATE": current+=1
    r={"product":"HMS-AI-ROUTER","version":VERSION,"index":len(records)+1,"epoch":current,
       "created_utc":datetime.now(timezone.utc).isoformat(),"decision":decision,"lane":lane,
       "reviewer_ref":reviewer_ref,"evidence_sha256":evidence_sha256.lower(),"manifest_sha256":manifest_sha256.lower(),
       "package_version":str(package_version),"cockpit_baseline":cockpit_baseline,
       "reason_codes":sorted({str(x) for x in (reason_codes or []) if str(x)}),"note_vi":str(note_vi)[:1000],
       "previous_decision_sha256":records[-1]["decision_sha256"] if records else GENESIS,
       "automatic_production_certification":False,"production_score_mutation_authorized":False,
       "automatic_upstream_merge_authorized":False,"automatic_real_effect_rearm_authorized":False}
    r["decision_sha256"]=_hash(r); return r

def append_decision(path,record):
    records=read_ledger(path); valid=validate_ledger(records)
    if not valid["valid"] or record.get("index")!=len(records)+1: raise ValueError("append precondition failed")
    if record.get("previous_decision_sha256")!=(records[-1]["decision_sha256"] if records else GENESIS): raise ValueError("tail changed")
    if record.get("decision_sha256")!=_hash(record): raise ValueError("record digest invalid")
    path.parent.mkdir(parents=True,exist_ok=True); flags=os.O_APPEND|os.O_CREAT|os.O_WRONLY
    if hasattr(os,"O_BINARY"): flags|=os.O_BINARY
    fd=os.open(path,flags,0o600)
    try: os.write(fd,_stable(record)+b"\n"); os.fsync(fd)
    finally: os.close(fd)

def evaluate(records,*,evidence_sha256,manifest_sha256,package_version,current_cockpit_baseline=COCKPIT_BASELINE,optional_gpu_required=False):
    valid=validate_ledger(records); reasons=list(valid["reasons"])
    if current_cockpit_baseline!=COCKPIT_BASELINE: reasons.append("FROZEN_BASELINE_DRIFT")
    epoch=valid["current_epoch"]; current=[r for r in records if r.get("epoch")==epoch]
    if any(r.get("decision")=="INVALIDATE" for r in current): reasons.append("CURRENT_EPOCH_INVALIDATED")
    if any(r.get("decision")=="REJECT" for r in current): reasons.append("CURRENT_EPOCH_REJECTED")
    lanes=["TERMINAL_PTY","PROJECT_RESUME"]+(["OPTIONAL_GPU"] if optional_gpu_required else [])
    summary={}; all_reviewers=set()
    for lane in lanes:
        rows=[r for r in current if r.get("lane")==lane and r.get("decision")=="APPROVE"
              and r.get("evidence_sha256")==evidence_sha256.lower() and r.get("manifest_sha256")==manifest_sha256.lower()
              and r.get("package_version")==package_version and r.get("cockpit_baseline")==current_cockpit_baseline]
        reviewers={r["reviewer_ref"] for r in rows}; all_reviewers|=reviewers
        if len(reviewers)<2: reasons.append("DUAL_REVIEW_INCOMPLETE:"+lane)
        summary[lane]={"approval_count":len(rows),"distinct_reviewer_count":len(reviewers),
                       "reviewer_refs":sorted(reviewers),"dual_review_complete":len(reviewers)>=2}
    ok=not reasons
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_DECISION_LEDGER",
            "ledger_valid":valid["valid"],"ledger_tail_sha256":valid["ledger_tail_sha256"],"current_epoch":epoch,
            "lane_summary":summary,"distinct_reviewer_count":len(all_reviewers),"dual_review_complete":ok,
            "promotion_eligible":ok,"reasons":sorted(set(reasons)),"package_version":package_version,
            "manifest_sha256":manifest_sha256.lower(),"evidence_sha256":evidence_sha256.lower(),
            "cockpit_baseline":current_cockpit_baseline,"automatic_production_certification":False,
            "production_score_mutation_authorized":False,"automatic_upstream_merge_authorized":False,
            "automatic_real_effect_rearm_authorized":False}

def synthetic_proof():
    ev="a"*64; man="b"*64; rs=[]; a=reviewer_ref("reviewer-a","proof-salt-00000001"); b=reviewer_ref("reviewer-b","proof-salt-00000001")
    for lane in ("TERMINAL_PTY","PROJECT_RESUME"):
        for rvw in (a,b): rs.append(build_decision(rs,decision="APPROVE",reviewer_ref=rvw,evidence_sha256=ev,
            manifest_sha256=man,package_version=VERSION,cockpit_baseline=COCKPIT_BASELINE,lane=lane))
    state=evaluate(rs,evidence_sha256=ev,manifest_sha256=man,package_version=VERSION)
    inv=build_decision(rs,decision="INVALIDATE",reviewer_ref=a,evidence_sha256=ev,manifest_sha256=man,
        package_version=VERSION,cockpit_baseline="1.3.29",lane="TERMINAL_PTY",reason_codes=["BASELINE_DRIFT"]); rs.append(inv)
    frozen=evaluate(rs,evidence_sha256=ev,manifest_sha256=man,package_version=VERSION)
    nxt=build_decision(rs,decision="APPROVE",reviewer_ref=a,evidence_sha256=ev,manifest_sha256=man,
        package_version=VERSION,cockpit_baseline=COCKPIT_BASELINE,lane="TERMINAL_PTY")
    checks={"hash_chain_valid":validate_ledger(rs)["valid"],"dual_review_two_lanes_complete":state["promotion_eligible"],
            "two_distinct_reviewers":state["distinct_reviewer_count"]==2,"invalidate_freezes_epoch":not frozen["promotion_eligible"],
            "drift_invalidation_records_observed_baseline":inv["cockpit_baseline"]=="1.3.29","new_epoch_after_invalidate":nxt["epoch"]==2,"no_automatic_authority":not state["production_score_mutation_authorized"]}
    tests=[{"name":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]; n=sum(x["status"]=="PASS" for x in tests)
    return {"product":"HMS-AI-ROUTER","version":VERSION,"suite":"WINDOWS_PROMOTION_DECISION_LEDGER_PROOF",
            "verdict":"PASS" if n==len(tests) else "FAIL","summary":{"pass":n,"fail":len(tests)-n,"total":len(tests)},
            "tests":tests,"production_score_promotion_eligible":False}

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True); sub.add_parser("proof")
    c=sub.add_parser("check"); c.add_argument("--ledger",required=True)
    e=sub.add_parser("evaluate"); e.add_argument("--ledger",required=True); e.add_argument("--evidence-sha256",required=True)
    e.add_argument("--manifest-sha256",required=True); e.add_argument("--package-version",required=True)
    e.add_argument("--cockpit-baseline",default=COCKPIT_BASELINE); e.add_argument("--optional-gpu-required",action="store_true")
    a=ap.parse_args()
    if a.cmd=="proof": out=synthetic_proof(); code=0 if out["verdict"]=="PASS" else 2
    elif a.cmd=="check": out=validate_ledger(read_ledger(Path(a.ledger))); code=0 if out["valid"] else 3
    else:
        out=evaluate(read_ledger(Path(a.ledger)),evidence_sha256=a.evidence_sha256,manifest_sha256=a.manifest_sha256,
                     package_version=a.package_version,current_cockpit_baseline=a.cockpit_baseline,
                     optional_gpu_required=a.optional_gpu_required); code=0 if out["promotion_eligible"] else 4
    print(json.dumps(out,ensure_ascii=False,indent=2)); return code
if __name__=="__main__": raise SystemExit(main())
