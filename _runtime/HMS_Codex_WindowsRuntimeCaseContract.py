#!/usr/bin/env python3
from __future__ import annotations

VERSION = "25.75"

# Canonical real Windows/current-Codex runtime evidence contract.
# Authority lineage: HMS_Codex_TargetMachineCertification.py v25.53 SAFE_STAGES.
REQUIRED_RUNTIME_CASE_IDS = (
    "host",
    "codex",
    "quota",
    "failover",
    "lan",
    "soak_6h",
    "soak_24h",
)
REQUIRED_RUNTIME_CASE_SET = frozenset(REQUIRED_RUNTIME_CASE_IDS)

CASE_DESCRIPTIONS_VI = {
    "host": "Máy đích Windows + PowerShell 5.1 + Codex CLI hiện hành.",
    "codex": "Codex thật với topology cô lập và tối thiểu hai managed instance khỏe.",
    "quota": "Quota thật từ tối thiểu hai nguồn/tài khoản, đủ cửa sổ chính và còn mới.",
    "failover": "Failover thật sang tài khoản khác, probe đạt và trạng thái được phục hồi.",
    "lan": "Tối thiểu hai node LAN online, chữ ký hợp lệ, metadata-only và shared roundtrip đạt.",
    "soak_6h": "Soak thật 6 giờ active-process-time với coverage đầy đủ.",
    "soak_24h": "Soak thật 24 giờ active-process-time với coverage đầy đủ.",
}


def validate_case_ids(case_ids):
    ids = [str(x or "") for x in case_ids]
    got = set(ids)
    missing = sorted(REQUIRED_RUNTIME_CASE_SET - got)
    unexpected = sorted(got - REQUIRED_RUNTIME_CASE_SET)
    duplicates = sorted({x for x in ids if ids.count(x) > 1 and x})
    return {
        "valid": len(ids) == len(REQUIRED_RUNTIME_CASE_IDS) and not missing and not unexpected and not duplicates,
        "required": list(REQUIRED_RUNTIME_CASE_IDS),
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
    }


def synthetic_proof():
    good = validate_case_ids(REQUIRED_RUNTIME_CASE_IDS)
    fake = validate_case_ids([f"case-{i}" for i in range(7)])
    dup = validate_case_ids(["host", "host", "quota", "failover", "lan", "soak_6h", "soak_24h"])
    checks = {
        "canonical_7_accepts": good["valid"],
        "arbitrary_7_rejected": not fake["valid"] and len(fake["unexpected"]) == 7,
        "missing_host_detected": "host" in fake["missing"],
        "duplicate_rejected": not dup["valid"] and "host" in dup["duplicates"],
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(x["status"] == "PASS" for x in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "WINDOWS_RUNTIME_CASE_CONTRACT_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
        "required_case_ids": list(REQUIRED_RUNTIME_CASE_IDS),
        "tests": tests,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(synthetic_proof(), ensure_ascii=False, indent=2))
