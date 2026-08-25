#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "_runtime"

LAUNCHER = ROOT / "HMS_AI_ROUTER.vbs"
RECOVERY = RUNTIME / "HMS_GUI_RECOVERY_ENTRY.pyw"
REVIEW = RUNTIME / "HMS_GUI_REVIEW_ENTRY.pyw"
GUARDED = RUNTIME / "HMS_GUI_ENTRY.pyw"
SAFE = RUNTIME / "HMS_GUI_SAFE_FALLBACK.pyw"

RECOVERY_PATCHES = {
    "backend",
    "official_auth_switch_async",
    "_finish_official_auth_switch",
}
REVIEW_PATCHES = {
    "refresh_promotion_review",
    "_refresh_promotion_gate_matrix",
    "_update_promotion_action_buttons",
    "submit_promotion_review",
    "_apply_promotion_live_result",
}


def _read(path: Path) -> str:
    return path.read_text("utf-8")


def _implementation(source: str, proof_name: str) -> str:
    marker = f"def {proof_name}"
    pos = source.find(marker)
    return source if pos < 0 else source[:pos]


def _attr_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def _patched_hmsapp_methods(source: str, filename: str) -> set[str]:
    tree = ast.parse(source, filename=filename)
    methods: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            chain = _attr_chain(target)
            if len(chain) == 3 and chain[:2] == ["legacy", "HmsApp"]:
                methods.add(chain[2])
    return methods


def _ordered_positions(source: str, needles: list[str]) -> bool:
    cursor = -1
    for needle in needles:
        pos = source.find(needle, cursor + 1)
        if pos < 0:
            return False
        cursor = pos
    return True


def source_proof() -> dict[str, Any]:
    launcher = _read(LAUNCHER)
    recovery = _read(RECOVERY)
    review = _read(REVIEW)
    guarded = _read(GUARDED)
    safe = _read(SAFE)

    recovery_impl = _implementation(recovery, "extension_proof")
    review_impl = _implementation(review, "extension_proof")
    safe_impl = _implementation(safe, "source_proof")

    parse_errors: list[str] = []
    patch_sets: dict[str, set[str]] = {"recovery": set(), "review": set()}
    for key, source, filename in (
        ("recovery", recovery, RECOVERY.name),
        ("review", review, REVIEW.name),
    ):
        try:
            patch_sets[key] = _patched_hmsapp_methods(source, filename)
        except Exception as exc:
            parse_errors.append(f"{filename}:{type(exc).__name__}")

    recovery_patches = patch_sets["recovery"]
    review_patches = patch_sets["review"]

    checks = {
        "wrapper_sources_parse_clean": not parse_errors,
        "launcher_prefers_recovery_wrapper": 'gui = base & "\\_runtime\\HMS_GUI_RECOVERY_ENTRY.pyw"' in launcher,
        "launcher_fallback_order_is_recovery_review_safe_legacy": _ordered_positions(
            launcher,
            [
                'gui = base & "\\_runtime\\HMS_GUI_RECOVERY_ENTRY.pyw"',
                'reviewGui = base & "\\_runtime\\HMS_GUI_REVIEW_ENTRY.pyw"',
                'safeGui = base & "\\_runtime\\HMS_GUI_SAFE_FALLBACK.pyw"',
                'legacyGui = base & "\\_runtime\\HMS_GUI.pyw"',
                "If Not fso.FileExists(gui) Then gui = reviewGui",
                "If Not fso.FileExists(gui) Then gui = safeGui",
                "If Not fso.FileExists(gui) Then gui = legacyGui",
            ],
        ),
        "launcher_never_targets_guarded_entry_directly": 'base & "\\_runtime\\HMS_GUI_ENTRY.pyw"' not in launcher,
        "recovery_loads_reviewer_wrapper": 'REVIEW_ENTRY = RUNTIME_DIR / "HMS_GUI_REVIEW_ENTRY.pyw"' in recovery_impl,
        "recovery_reuses_reviewer_legacy_object": "legacy = review.legacy" in recovery_impl,
        "review_loads_guarded_entry": 'BASE_ENTRY = RUNTIME_DIR / "HMS_GUI_ENTRY.pyw"' in review_impl,
        "review_reuses_guarded_legacy_object": "legacy = base.legacy" in review_impl,
        "guarded_entry_loads_legacy_core": 'LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"' in guarded,
        "safe_fallback_loads_legacy_core_directly": 'LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"' in safe_impl,
        "safe_fallback_has_no_promotion_controller": "PromotionWorkbenchController" not in safe_impl,
        "safe_fallback_has_no_review_action": "submit_promotion_review" not in safe_impl,
        "recovery_patch_set_is_exact": recovery_patches == RECOVERY_PATCHES,
        "review_patch_set_is_exact": review_patches == REVIEW_PATCHES,
        "recovery_and_review_patch_sets_are_disjoint": recovery_patches.isdisjoint(review_patches),
        "review_wrapper_precedes_recovery_original_capture": _ordered_positions(
            recovery_impl,
            [
                "review = _load_review_entry()",
                "legacy = review.legacy",
                "_ORIGINAL_BACKEND = legacy.HmsApp.backend",
                "_ORIGINAL_OFFICIAL_SWITCH = legacy.HmsApp.official_auth_switch_async",
                "_ORIGINAL_FINISH_OFFICIAL_SWITCH = legacy.HmsApp._finish_official_auth_switch",
            ],
        ),
        "review_requires_sealed_controller_loader": "load_verified_report" in review_impl,
        "review_visual_gate_requires_release_authority": all(
            token in review_impl
            for token in (
                "reviewer_release_authority",
                "local_integrity_seal_valid",
                "local_artifact_hashed_at_capture",
                "package_zip_sha256",
                "release_manifest_sha256",
            )
        ),
        "recovery_wrapper_does_not_construct_promotion_controller": "PromotionWorkbenchController" not in recovery_impl,
        "recovery_wrapper_preserves_no_auto_authority": (
            '"windows_runtime_certified": True' not in recovery_impl
            and '"production_score_mutation_authorized": True' not in recovery_impl
        ),
        "review_wrapper_preserves_no_auto_authority": (
            '"automatic_production_certification": True' not in review_impl
            and '"production_score_mutation_authorized": True' not in review_impl
        ),
    }

    tests = [
        {"name": name, "status": "PASS" if ok else "FAIL"}
        for name, ok in checks.items()
    ]
    failed = [row for row in tests if row["status"] != "PASS"]
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "INTEGRATED_WINDOWS_WRAPPER_CHAIN_PROOF",
        "verdict": "PASS" if not failed else "FAIL",
        "summary": {"pass": len(tests) - len(failed), "fail": len(failed), "total": len(tests)},
        "tests": tests,
        "parse_errors": parse_errors,
        "recovery_patch_methods": sorted(recovery_patches),
        "review_patch_methods": sorted(review_patches),
        "real_windows_runtime_executed": False,
        "real_uac_prompt_executed": False,
        "production_evidence_eligible": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
        "production_score_mutation_authorized": False,
    }


def main() -> int:
    result = source_proof()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
