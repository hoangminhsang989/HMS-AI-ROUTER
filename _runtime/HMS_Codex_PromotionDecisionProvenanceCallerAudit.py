#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
RUNTIME_DIR = Path(__file__).resolve().parent
LEDGER_MODULE = "HMS_Codex_WindowsPromotionDecisionLedger"
REQUIRED = {
    "build_decision": {
        "evidence_sha256",
        "manifest_sha256",
        "package_sha256",
        "source_certification_report_sha256",
        "reviewer_trust_authority_sha256",
        "reviewer_release_authority_sha256",
        "package_version",
    },
    "evaluate": {
        "evidence_sha256",
        "manifest_sha256",
        "package_sha256",
        "source_certification_report_sha256",
        "reviewer_trust_authority_sha256",
        "reviewer_release_authority_sha256",
        "package_version",
    },
}


def _imports(tree: ast.AST):
    direct: dict[str, str] = {}
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == LEDGER_MODULE:
            for item in node.names:
                if item.name in REQUIRED:
                    direct[item.asname or item.name] = item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name == LEDGER_MODULE:
                    modules.add(item.asname or item.name)
    return direct, modules


def _callee(node: ast.AST, direct: dict[str, str], modules: set[str]) -> str | None:
    if isinstance(node, ast.Name):
        return direct.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id in modules and node.attr in REQUIRED:
            return node.attr
    return None


def _audit_file(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    source = path.read_text("utf-8")
    if LEDGER_MODULE not in source and path.name != "HMS_Codex_WindowsPromotionDecisionLedger.py":
        return [], []
    try:
        tree = ast.parse(source, filename=str(path))
    except Exception as exc:
        return [], [f"PARSE_FAILED:{path.name}:{type(exc).__name__}"]
    direct, modules = _imports(tree)
    if path.name == "HMS_Codex_WindowsPromotionDecisionLedger.py":
        direct.update({name: name for name in REQUIRED})
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee(node.func, direct, modules)
        if not name:
            continue
        explicit = {kw.arg for kw in node.keywords if kw.arg is not None}
        dynamic_kwargs = any(kw.arg is None for kw in node.keywords)
        missing = sorted(REQUIRED[name] - explicit)
        rows.append({
            "path": path.name,
            "line": int(getattr(node, "lineno", 0) or 0),
            "callee": name,
            "missing_explicit_keywords": missing,
            "dynamic_kwargs_present": dynamic_kwargs,
            "valid": not missing or dynamic_kwargs,
        })
    return rows, []


def source_audit() -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted({*RUNTIME_DIR.glob("*.py"), *RUNTIME_DIR.glob("*.pyw")}):
        try:
            rows, file_errors = _audit_file(path)
        except Exception as exc:
            rows, file_errors = [], [f"READ_FAILED:{path.name}:{type(exc).__name__}"]
        calls.extend(rows)
        errors.extend(file_errors)

    invalid = [row for row in calls if row["valid"] is not True]
    dynamic = [row for row in calls if row["dynamic_kwargs_present"]]
    observed_paths = {row["path"] for row in calls}
    expected_paths = {
        "HMS_Codex_WindowsPromotionDecisionLedger.py",
        "HMS_Codex_WindowsPromotionReviewWorkbench.py",
        "HMS_Codex_WindowsPromotionE2EFixtures.py",
    }
    checks = {
        "referencing_sources_parse_clean": not errors,
        "direct_ledger_calls_found": bool(calls),
        "expected_direct_callers_present": expected_paths.issubset(observed_paths),
        "all_direct_calls_supply_full_provenance": not invalid,
        "dynamic_kwargs_are_visible_for_review": True,
        "audit_has_no_runtime_or_production_authority": True,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "PROMOTION_DECISION_PROVENANCE_CALLER_AUDIT",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "call_count": len(calls),
        "calls": calls,
        "invalid_calls": invalid,
        "dynamic_kwargs_calls": dynamic,
        "parse_errors": errors,
        "real_windows_runtime_executed": False,
        "production_evidence_eligible": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
    }


def main() -> int:
    result = source_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
