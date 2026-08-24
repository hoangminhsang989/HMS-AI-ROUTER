#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
RUNTIME_DIR = Path(__file__).resolve().parent
TARGET_CALL = "elevated_close_supported_processes"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _audit_file(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    calls: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        source = path.read_text("utf-8")
        tree = ast.parse(source, filename=str(path))
    except Exception as exc:
        return [], [f"PARSE_FAILED:{path.name}:{type(exc).__name__}"]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != TARGET_CALL:
            continue
        keyword_names = {kw.arg for kw in node.keywords if kw.arg is not None}
        has_dynamic_kwargs = any(kw.arg is None for kw in node.keywords)
        calls.append({
            "path": path.name,
            "line": int(getattr(node, "lineno", 0) or 0),
            "expected_identities_explicit": "expected_identities" in keyword_names,
            "dynamic_kwargs_present": has_dynamic_kwargs,
        })
    return calls, errors


def source_audit() -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    files = sorted({*RUNTIME_DIR.glob("*.py"), *RUNTIME_DIR.glob("*.pyw")})
    for path in files:
        file_calls, errors = _audit_file(path)
        calls.extend(file_calls)
        parse_errors.extend(errors)

    missing = [row for row in calls if row["expected_identities_explicit"] is not True]
    dynamic_only = [row for row in calls if row["dynamic_kwargs_present"] and row["expected_identities_explicit"] is not True]
    expected_known_paths = {
        "HMS_GUI_RECOVERY_ENTRY.pyw",
        "HMS_Codex_WindowsUACRecoveryValidation.py",
    }
    observed_paths = {row["path"] for row in calls}
    checks = {
        "runtime_python_files_parse_clean": not parse_errors,
        "elevation_call_sites_found": len(calls) > 0,
        "known_gui_and_harness_callers_present": expected_known_paths.issubset(observed_paths),
        "every_call_has_explicit_expected_identities": not missing,
        "dynamic_kwargs_cannot_substitute_identity_binding": not dynamic_only,
        "audit_grants_no_runtime_authority": True,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "WINDOWS_ELEVATION_CALLER_IDENTITY_AUDIT",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "call_site_count": len(calls),
        "call_sites": calls,
        "parse_errors": parse_errors,
        "missing_identity_binding": missing,
        "real_windows_processes_enumerated": False,
        "real_uac_prompt_executed": False,
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
