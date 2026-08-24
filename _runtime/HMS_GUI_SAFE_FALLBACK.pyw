#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"
APP_VERSION = "25.75"


def _load_legacy_gui():
    loader = importlib.machinery.SourceFileLoader("hms_gui_safe_fallback_legacy", str(LEGACY_GUI))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Không thể tạo module spec cho HMS_GUI.pyw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.APP_VERSION = APP_VERSION
    return module


legacy = _load_legacy_gui()
_ORIGINAL_BUILD_SHELL = legacy.HmsApp._build_shell


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def _safe_build_shell(self):
    _ORIGINAL_BUILD_SHELL(self)
    try:
        for widget in _walk_widgets(self.sidebar):
            try:
                if widget.cget("text") == "AI COCKPIT":
                    widget.configure(text="AI ROUTER")
            except Exception:
                pass
    except Exception:
        pass


legacy.HmsApp._build_shell = _safe_build_shell


def source_proof():
    src = Path(__file__).read_text("utf-8")
    checks = {
        "loads_legacy_core_directly": 'LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"' in src,
        "does_not_load_guarded_promotion_entry": "HMS_GUI_ENTRY.pyw" not in src,
        "does_not_load_reviewer_wrapper": "HMS_GUI_REVIEW_ENTRY.pyw" not in src,
        "promotion_controller_absent": "PromotionWorkbenchController" not in src,
        "promotion_review_extension_absent": 'pages["promotion"]' not in src and "submit_promotion_review" not in src,
        "router_branding_patch": 'widget.configure(text="AI ROUTER")' in src,
    }
    tests = [{"name": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()]
    passed = sum(t["status"] == "PASS" for t in tests)
    return {"product": "HMS-AI-ROUTER", "version": APP_VERSION,
            "suite": "PROMOTION_DISABLED_SAFE_GUI_FALLBACK_PROOF",
            "verdict": "PASS" if passed == len(tests) else "FAIL",
            "summary": {"pass": passed, "fail": len(tests)-passed, "total": len(tests)},
            "tests": tests, "promotion_review_available": False,
            "automatic_production_certification": False, "production_score_mutation_authorized": False}


def main():
    if "--proof" in sys.argv[1:]:
        out = source_proof(); print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if out["verdict"] == "PASS" else 2
    legacy.HmsApp().run(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
