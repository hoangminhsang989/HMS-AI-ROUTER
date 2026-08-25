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
        "evidence_sha256", "manifest_sha256", "package_sha256", "source_certification_report_sha256",
        "reviewer_trust_authority_sha256", "reviewer_release_authority_sha256", "package_version",
    },
    "evaluate": {
        "evidence_sha256", "manifest_sha256", "package_sha256", "source_certification_report_sha256",
        "reviewer_trust_authority_sha256", "reviewer_release_authority_sha256", "package_version",
    },
}
PROOF_FUNCTIONS = {
    "synthetic_proof", "synthetic_e2e_fixtures", "_concurrency_proof", "_approval_set", "_evaluate",
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


class _CallVisitor(ast.NodeVisitor):
    def __init__(self, direct: dict[str, str], modules: set[str]):
        self.direct = direct
        self.modules = modules
        self.function_stack: list[str] = []
        self.rows: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call):
        name = _callee(node.func, self.direct, self.modules)
        if name:
            explicit = {kw.arg for kw in node.keywords if kw.arg is not None}
            dynamic_kwargs = any(kw.arg is None for kw in node.keywords)
            missing = sorted(REQUIRED[name] - explicit)
            function_name = self.function_stack[-1] if self.function_stack else "<module>"
            proof_context = function_name in PROOF_FUNCTIONS
            valid = not missing or (dynamic_kwargs and proof_context)
            self.rows.append({
                "line": int(getattr(node, "lineno", 0) or 0),
                "function": function_name,
                "callee": name,
                "missing_explicit_keywords": missing,
                "dynamic_kwargs_present": dynamic_kwargs,
                "proof_context": proof_context,
                "valid": valid,
            })
        self.generic_visit(node)


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
    visitor = _CallVisitor(direct, modules)
    visitor.visit(tree)
    return [dict(row, path=path.name) for row in visitor.rows], []


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
    dynamic_production = [row for row in calls if row["dynamic_kwargs_present"] and not row["proof_context"]]
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
        "production_calls_supply_full_explicit_provenance": not invalid,
        "dynamic_production_kwargs_rejected": not dynamic_production,
        "audit_has_no_runtime_or_production_authority": True,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "PROMOTION_DECISION_PROVENANCE_CALLER_AUDIT",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests, "call_count": len(calls), "calls": calls, "invalid_calls": invalid,
        "dynamic_production_calls": dynamic_production, "parse_errors": errors,
        "real_windows_runtime_executed": False, "production_evidence_eligible": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
    }


def main() -> int:
    result = source_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
