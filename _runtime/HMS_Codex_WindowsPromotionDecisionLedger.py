#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = "25.75"
COCKPIT_BASELINE = "1.3.28"
GENESIS = "0" * 64
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DECISIONS = {"APPROVE", "REJECT", "INVALIDATE"}
LANES = {"TERMINAL_PTY", "PROJECT_RESUME", "OPTIONAL_GPU"}
LOCK_WAIT_SECONDS = 2.0
LOCK_POLL_SECONDS = 0.02
PROVENANCE_DIGEST_FIELDS = (
    "evidence_sha256",
    "manifest_sha256",
    "package_sha256",
    "source_certification_report_sha256",
    "reviewer_trust_authority_sha256",
    "reviewer_release_authority_sha256",
)


def _stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hex(value) -> bool:
    return HEX64.fullmatch(str(value or "").lower()) is not None


def reviewer_ref(identity, salt):
    if len(identity.strip()) < 2 or len(salt) < 16:
        raise ValueError("identity/salt too short")
    return "rvw_" + _sha(("reviewer\0" + salt + "\0" + identity.strip()).encode())[:32]


def _hash(record):
    return _sha(_stable({k: v for k, v in record.items() if k != "decision_sha256"}))


def read_ledger(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {i} is not object")
            out.append(value)
    return out


def validate_ledger(records):
    reasons = []
    prev = GENESIS
    epoch = 0
    for pos, record in enumerate(records, 1):
        if record.get("index") != pos:
            reasons.append(f"INDEX_SEQUENCE_INVALID:{pos}")
        if record.get("product") != "HMS-AI-ROUTER" or record.get("version") != VERSION:
            reasons.append(f"AUTHORITY_INVALID:{pos}")
        if str(record.get("package_version") or "") != VERSION:
            reasons.append(f"PACKAGE_VERSION_AUTHORITY_INVALID:{pos}")
        if record.get("decision") not in DECISIONS or record.get("lane") not in LANES:
            reasons.append(f"DECISION_OR_LANE_INVALID:{pos}")
        if not re.fullmatch(r"rvw_[0-9a-f]{32}", str(record.get("reviewer_ref") or "")):
            reasons.append(f"REVIEWER_REF_INVALID:{pos}")
        for field in PROVENANCE_DIGEST_FIELDS:
            if not _hex(record.get(field)):
                reasons.append(f"PROVENANCE_DIGEST_INVALID:{field}:{pos}")
        if record.get("previous_decision_sha256") != prev or record.get("decision_sha256") != _hash(record):
            reasons.append(f"HASH_CHAIN_INVALID:{pos}")
        current_epoch = record.get("epoch")
        if not isinstance(current_epoch, int) or current_epoch < 1 or current_epoch < epoch or current_epoch > epoch + 1:
            reasons.append(f"EPOCH_INVALID:{pos}")
        else:
            epoch = max(epoch, current_epoch)
        prev = str(record.get("decision_sha256") or "")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "record_count": len(records),
        "ledger_tail_sha256": prev,
        "current_epoch": epoch,
    }


def build_decision(
    records,
    *,
    decision,
    reviewer_ref,
    evidence_sha256,
    manifest_sha256,
    package_sha256,
    source_certification_report_sha256,
    reviewer_trust_authority_sha256,
    reviewer_release_authority_sha256,
    package_version,
    cockpit_baseline,
    lane,
    reason_codes=None,
    note_vi="",
):
    decision = decision.upper()
    lane = lane.upper()
    package_version = str(package_version or "")
    if decision not in DECISIONS or lane not in LANES:
        raise ValueError("decision/lane invalid")
    if package_version != VERSION:
        raise ValueError("package version authority mismatch")
    if not re.fullmatch(r"rvw_[0-9a-f]{32}", reviewer_ref):
        raise ValueError("pseudonymous reviewer_ref required")
    provenance = {
        "evidence_sha256": evidence_sha256,
        "manifest_sha256": manifest_sha256,
        "package_sha256": package_sha256,
        "source_certification_report_sha256": source_certification_report_sha256,
        "reviewer_trust_authority_sha256": reviewer_trust_authority_sha256,
        "reviewer_release_authority_sha256": reviewer_release_authority_sha256,
    }
    if any(not _hex(value) for value in provenance.values()):
        raise ValueError("full evidence provenance sha256 required")
    if decision != "INVALIDATE" and cockpit_baseline != COCKPIT_BASELINE:
        raise ValueError("baseline drift")
    if decision == "INVALIDATE" and not str(cockpit_baseline).strip():
        raise ValueError("observed baseline required for invalidation")
    valid = validate_ledger(records)
    if not valid["valid"]:
        raise ValueError("existing ledger invalid")
    current = valid["current_epoch"] or 1
    if records and records[-1].get("decision") == "INVALIDATE" and decision != "INVALIDATE":
        current += 1
    record = {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "index": len(records) + 1,
        "epoch": current,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "lane": lane,
        "reviewer_ref": reviewer_ref,
        **{key: str(value).lower() for key, value in provenance.items()},
        "package_version": package_version,
        "cockpit_baseline": cockpit_baseline,
        "reason_codes": sorted({str(x) for x in (reason_codes or []) if str(x)}),
        "note_vi": str(note_vi)[:1000],
        "previous_decision_sha256": records[-1]["decision_sha256"] if records else GENESIS,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
        "automatic_upstream_merge_authorized": False,
        "automatic_real_effect_rearm_authorized": False,
    }
    record["decision_sha256"] = _hash(record)
    return record


@contextmanager
def _exclusive_ledger_lock(path, timeout_seconds=LOCK_WAIT_SECONDS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(path) + ".lock")
    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    fd = None
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    while fd is None:
        try:
            fd = os.open(lock_path, flags, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("ledger lock busy; append aborted fail-closed")
            time.sleep(LOCK_POLL_SECONDS)
    try:
        payload = json.dumps({"pid": os.getpid(), "created_utc": datetime.now(timezone.utc).isoformat()}, sort_keys=True).encode() + b"\n"
        os.write(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        yield lock_path
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def append_decision(path, record, *, lock_timeout_seconds=LOCK_WAIT_SECONDS):
    path = Path(path)
    with _exclusive_ledger_lock(path, timeout_seconds=lock_timeout_seconds):
        records = read_ledger(path)
        valid = validate_ledger(records)
        if not valid["valid"] or record.get("index") != len(records) + 1:
            raise ValueError("append precondition failed; rebuild against current ledger")
        expected_tail = records[-1]["decision_sha256"] if records else GENESIS
        if record.get("previous_decision_sha256") != expected_tail:
            raise ValueError("tail changed; rebuild decision")
        if record.get("decision_sha256") != _hash(record):
            raise ValueError("record digest invalid")
        if str(record.get("package_version") or "") != VERSION:
            raise ValueError("package version authority mismatch")
        for field in PROVENANCE_DIGEST_FIELDS:
            if not _hex(record.get(field)):
                raise ValueError("full evidence provenance required:" + field)
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, _stable(record) + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)


def evaluate(
    records,
    *,
    evidence_sha256,
    manifest_sha256,
    package_sha256,
    source_certification_report_sha256,
    reviewer_trust_authority_sha256,
    reviewer_release_authority_sha256,
    package_version,
    current_cockpit_baseline=COCKPIT_BASELINE,
    optional_gpu_required=False,
):
    valid = validate_ledger(records)
    reasons = list(valid["reasons"])
    package_version = str(package_version or "")
    expected = {
        "evidence_sha256": str(evidence_sha256 or "").lower(),
        "manifest_sha256": str(manifest_sha256 or "").lower(),
        "package_sha256": str(package_sha256 or "").lower(),
        "source_certification_report_sha256": str(source_certification_report_sha256 or "").lower(),
        "reviewer_trust_authority_sha256": str(reviewer_trust_authority_sha256 or "").lower(),
        "reviewer_release_authority_sha256": str(reviewer_release_authority_sha256 or "").lower(),
    }
    for field, value in expected.items():
        if not _hex(value):
            reasons.append("EXPECTED_PROVENANCE_DIGEST_INVALID:" + field)
    if package_version != VERSION:
        reasons.append("PACKAGE_VERSION_AUTHORITY_MISMATCH")
    if current_cockpit_baseline != COCKPIT_BASELINE:
        reasons.append("FROZEN_BASELINE_DRIFT")
    epoch = valid["current_epoch"]
    current = [r for r in records if r.get("epoch") == epoch]
    if any(r.get("decision") == "INVALIDATE" for r in current):
        reasons.append("CURRENT_EPOCH_INVALIDATED")
    if any(r.get("decision") == "REJECT" for r in current):
        reasons.append("CURRENT_EPOCH_REJECTED")
    lanes = ["TERMINAL_PTY", "PROJECT_RESUME"] + (["OPTIONAL_GPU"] if optional_gpu_required else [])
    summary = {}
    all_reviewers = set()
    for lane in lanes:
        rows = [
            r for r in current
            if r.get("lane") == lane
            and r.get("decision") == "APPROVE"
            and all(str(r.get(field) or "").lower() == value for field, value in expected.items())
            and r.get("package_version") == package_version
            and r.get("cockpit_baseline") == current_cockpit_baseline
        ]
        reviewers = {r["reviewer_ref"] for r in rows}
        all_reviewers |= reviewers
        if len(reviewers) < 2:
            reasons.append("DUAL_REVIEW_INCOMPLETE:" + lane)
        summary[lane] = {
            "approval_count": len(rows),
            "distinct_reviewer_count": len(reviewers),
            "reviewer_refs": sorted(reviewers),
            "dual_review_complete": len(reviewers) >= 2,
        }
    ok = not reasons
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_PROMOTION_DECISION_LEDGER",
        "ledger_valid": valid["valid"],
        "ledger_tail_sha256": valid["ledger_tail_sha256"],
        "current_epoch": epoch,
        "lane_summary": summary,
        "distinct_reviewer_count": len(all_reviewers),
        "dual_review_complete": ok,
        "promotion_eligible": ok,
        "reasons": sorted(set(reasons)),
        "package_version": package_version,
        **expected,
        "cockpit_baseline": current_cockpit_baseline,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
        "automatic_upstream_merge_authorized": False,
        "automatic_real_effect_rearm_authorized": False,
    }


def _concurrency_proof(ev, man, pkg, src, trust, release, rvw):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "ledger.jsonl"
        base = []
        kwargs = dict(
            evidence_sha256=ev,
            manifest_sha256=man,
            package_sha256=pkg,
            source_certification_report_sha256=src,
            reviewer_trust_authority_sha256=trust,
            reviewer_release_authority_sha256=release,
            package_version=VERSION,
            cockpit_baseline=COCKPIT_BASELINE,
        )
        stale = build_decision(base, decision="APPROVE", reviewer_ref=rvw, lane="TERMINAL_PTY", **kwargs)
        results = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=2)
                append_decision(path, dict(stale))
                results.append("OK")
            except Exception:
                results.append("BLOCKED")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        [t.start() for t in threads]
        [t.join(timeout=4) for t in threads]
        records = read_ledger(path)
        valid = validate_ledger(records)
        rebuilt = build_decision(records, decision="APPROVE", reviewer_ref=rvw, lane="PROJECT_RESUME", **kwargs)
        append_decision(path, rebuilt)
        final = validate_ledger(read_ledger(path))
        return {
            "one_stale_writer_wins": results.count("OK") == 1 and results.count("BLOCKED") == 1,
            "concurrent_append_keeps_chain_valid": valid["valid"] and valid["record_count"] == 1,
            "rebuild_after_tail_change_succeeds": final["valid"] and final["record_count"] == 2,
            "lock_file_released": not Path(str(path) + ".lock").exists(),
        }


def synthetic_proof():
    ev = "a" * 64
    man = "b" * 64
    pkg = "c" * 64
    src = "d" * 64
    trust = "e" * 64
    release = "f" * 64
    records = []
    a = reviewer_ref("reviewer-a", "proof-salt-00000001")
    b = reviewer_ref("reviewer-b", "proof-salt-00000001")
    common = dict(
        evidence_sha256=ev,
        manifest_sha256=man,
        package_sha256=pkg,
        source_certification_report_sha256=src,
        reviewer_trust_authority_sha256=trust,
        reviewer_release_authority_sha256=release,
        package_version=VERSION,
        cockpit_baseline=COCKPIT_BASELINE,
    )
    for lane in ("TERMINAL_PTY", "PROJECT_RESUME"):
        for rvw in (a, b):
            records.append(build_decision(records, decision="APPROVE", reviewer_ref=rvw, lane=lane, **common))
    state = evaluate(records, current_cockpit_baseline=COCKPIT_BASELINE, optional_gpu_required=False, **{
        k: v for k, v in common.items() if k != "cockpit_baseline"
    })
    wrong_source = evaluate(records, evidence_sha256=ev, manifest_sha256=man, package_sha256=pkg,
        source_certification_report_sha256="9" * 64, reviewer_trust_authority_sha256=trust,
        reviewer_release_authority_sha256=release, package_version=VERSION)
    wrong_release = evaluate(records, evidence_sha256=ev, manifest_sha256=man, package_sha256=pkg,
        source_certification_report_sha256=src, reviewer_trust_authority_sha256=trust,
        reviewer_release_authority_sha256="8" * 64, package_version=VERSION)
    wrong_version = evaluate(records, evidence_sha256=ev, manifest_sha256=man, package_sha256=pkg,
        source_certification_report_sha256=src, reviewer_trust_authority_sha256=trust,
        reviewer_release_authority_sha256=release, package_version="25.74")
    build_wrong_blocked = False
    try:
        build_decision(records, decision="APPROVE", reviewer_ref=a, lane="TERMINAL_PTY",
            package_version="25.74", **{k: v for k, v in common.items() if k not in ("package_version",)})
    except ValueError:
        build_wrong_blocked = True
    tampered = json.loads(json.dumps(records))
    tampered[0]["source_certification_report_sha256"] = "9" * 64
    tampered[0]["decision_sha256"] = _hash(tampered[0])
    tampered_ledger = validate_ledger(tampered)
    invalidation = build_decision(records, decision="INVALIDATE", reviewer_ref=a, lane="TERMINAL_PTY",
        reason_codes=["BASELINE_DRIFT"], cockpit_baseline="1.3.29", **{
            k: v for k, v in common.items() if k != "cockpit_baseline"
        })
    records.append(invalidation)
    frozen = evaluate(records, current_cockpit_baseline=COCKPIT_BASELINE, **{
        k: v for k, v in common.items() if k != "cockpit_baseline"
    })
    nxt = build_decision(records, decision="APPROVE", reviewer_ref=a, lane="TERMINAL_PTY", **common)
    checks = {
        "hash_chain_valid": validate_ledger(records)["valid"],
        "dual_review_two_lanes_complete": state["promotion_eligible"],
        "two_distinct_reviewers": state["distinct_reviewer_count"] == 2,
        "source_certification_mismatch_blocks_reuse": not wrong_source["promotion_eligible"],
        "release_authority_mismatch_blocks_reuse": not wrong_release["promotion_eligible"],
        "wrong_package_version_evaluation_blocked": "PACKAGE_VERSION_AUTHORITY_MISMATCH" in wrong_version["reasons"],
        "wrong_package_version_build_blocked": build_wrong_blocked,
        "tampered_source_provenance_breaks_chain": any(x.startswith("HASH_CHAIN_INVALID:") for x in tampered_ledger["reasons"]),
        "invalidate_freezes_epoch": not frozen["promotion_eligible"],
        "drift_invalidation_records_observed_baseline": invalidation["cockpit_baseline"] == "1.3.29",
        "new_epoch_after_invalidate": nxt["epoch"] == 2,
        "no_automatic_authority": not state["production_score_mutation_authorized"],
    }
    checks.update(_concurrency_proof(ev, man, pkg, src, trust, release, a))
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_PROMOTION_DECISION_LEDGER_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "production_score_promotion_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("proof")
    check = sub.add_parser("check")
    check.add_argument("--ledger", required=True)
    evaluate_cmd = sub.add_parser("evaluate")
    evaluate_cmd.add_argument("--ledger", required=True)
    evaluate_cmd.add_argument("--evidence-sha256", required=True)
    evaluate_cmd.add_argument("--manifest-sha256", required=True)
    evaluate_cmd.add_argument("--package-sha256", required=True)
    evaluate_cmd.add_argument("--source-certification-report-sha256", required=True)
    evaluate_cmd.add_argument("--reviewer-trust-authority-sha256", required=True)
    evaluate_cmd.add_argument("--reviewer-release-authority-sha256", required=True)
    evaluate_cmd.add_argument("--package-version", required=True)
    evaluate_cmd.add_argument("--cockpit-baseline", default=COCKPIT_BASELINE)
    evaluate_cmd.add_argument("--optional-gpu-required", action="store_true")
    args = parser.parse_args()
    if args.cmd == "proof":
        out = synthetic_proof()
        code = 0 if out["verdict"] == "PASS" else 2
    elif args.cmd == "check":
        out = validate_ledger(read_ledger(Path(args.ledger)))
        code = 0 if out["valid"] else 3
    else:
        out = evaluate(
            read_ledger(Path(args.ledger)),
            evidence_sha256=args.evidence_sha256,
            manifest_sha256=args.manifest_sha256,
            package_sha256=args.package_sha256,
            source_certification_report_sha256=args.source_certification_report_sha256,
            reviewer_trust_authority_sha256=args.reviewer_trust_authority_sha256,
            reviewer_release_authority_sha256=args.reviewer_release_authority_sha256,
            package_version=args.package_version,
            current_cockpit_baseline=args.cockpit_baseline,
            optional_gpu_required=args.optional_gpu_required,
        )
        code = 0 if out["promotion_eligible"] else 4
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
