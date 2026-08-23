#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
LEGACY_GUI = RUNTIME_DIR / "HMS_GUI.pyw"
APP_VERSION = "25.75"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))


def _load_legacy_gui():
    loader = importlib.machinery.SourceFileLoader("hms_gui_legacy", str(LEGACY_GUI))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Không thể tạo module spec cho HMS_GUI.pyw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.APP_VERSION = APP_VERSION
    return module


legacy = _load_legacy_gui()

from HMS_Codex_CockpitLiveBaselineProvider import CockpitLiveBaselineProvider, LiveBaselineError
from HMS_Codex_ExternalWindowsReviewPacketIngest import COCKPIT_BASELINE
from HMS_Codex_WindowsPromotionWorkbenchController import PromotionWorkbenchController

_ORIGINAL_BUILD_SHELL = legacy.HmsApp._build_shell
_ORIGINAL_BUILD_PAGES = legacy.HmsApp._build_pages
_ORIGINAL_SHOW_PAGE = legacy.HmsApp.show_page


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def _promotion_state_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return root / "HMS-AI-ROUTER" / "promotion-review"


def _safe_json(path: Path, default):
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError, TypeError):
        return default


def _patch_visible_branding(app):
    # Only mutate user-visible branding. Do not touch legacy AppUserModelID,
    # parity/evidence strings, or compatibility identifiers containing Cockpit.
    for widget in _walk_widgets(app.sidebar):
        try:
            if widget.cget("text") == "AI COCKPIT":
                widget.configure(text="AI ROUTER")
        except Exception:
            pass


def _extended_build_shell(self):
    _ORIGINAL_BUILD_SHELL(self)
    _patch_visible_branding(self)
    nav_parent = self.nav["settings"].master
    item = legacy.NavItem(
        nav_parent,
        "Promotion review",
        "security",
        lambda: self.show_page("promotion"),
        width=184,
        height=40,
    )
    item.pack(fill="x", pady=2)
    self.nav["promotion"] = item


def _extended_build_pages(self):
    _ORIGINAL_BUILD_PAGES(self)
    tk = legacy.tk
    C = legacy.C

    page = tk.Frame(self.content, bg=C["bg"])
    self.pages["promotion"] = page

    header = tk.Frame(page, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
    header.pack(fill="x", pady=(0, 10), ipady=10)
    tk.Label(
        header,
        text="Windows Promotion Review Workbench",
        bg=C["surface"],
        fg=C["text"],
        font=("Segoe UI Semibold", 11),
    ).pack(anchor="w", padx=16, pady=(2, 2))
    tk.Label(
        header,
        text="Review-only · không tự certify · không tự sửa production score · baseline drift = fail-closed",
        bg=C["surface"],
        fg=C["text2"],
        font=("Segoe UI", 8),
    ).pack(anchor="w", padx=16)

    body = tk.Frame(page, bg=C["bg"])
    body.pack(fill="both", expand=True)

    card = tk.Frame(body, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
    card.pack(fill="x", pady=(0, 10), ipady=8)

    self.promotion_baseline_label = tk.Label(card, bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 9), anchor="w")
    self.promotion_baseline_label.pack(fill="x", padx=16, pady=(5, 2))
    self.promotion_live_label = tk.Label(card, bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold", 8), anchor="w")
    self.promotion_live_label.pack(fill="x", padx=16, pady=2)
    self.promotion_packet_label = tk.Label(card, bg=C["surface"], fg=C["text2"], font=("Segoe UI", 8), anchor="w")
    self.promotion_packet_label.pack(fill="x", padx=16, pady=2)
    self.promotion_ledger_label = tk.Label(card, bg=C["surface"], fg=C["text2"], font=("Segoe UI", 8), anchor="w")
    self.promotion_ledger_label.pack(fill="x", padx=16, pady=2)
    self.promotion_gate_label = tk.Label(card, bg=C["surface"], fg=C["warning"], font=("Segoe UI Semibold", 8), anchor="w", wraplength=760, justify="left")
    self.promotion_gate_label.pack(fill="x", padx=16, pady=(2, 7))

    actions = tk.Frame(body, bg=C["bg"])
    actions.pack(fill="x")
    refresh = legacy.HoverButton(
        actions,
        "LÀM MỚI REVIEW",
        self.refresh_promotion_review,
        width=138,
        height=32,
        bg=C["surface3"],
        hover=C["hover"],
        outline=C["border"],
        font=("Segoe UI Semibold", 8),
    )
    refresh.pack(side="left")

    tk.Label(
        body,
        text=(
            "APPROVE / REJECT / INVALIDATE vẫn khóa ở bước này. Trusted live baseline đã có, nhưng GUI chỉ mở reviewer action "
            "sau khi form evidence + reviewer identity/salt + lane được ràng buộc đầy đủ."
        ),
        bg=C["bg"],
        fg=C["muted"],
        font=("Segoe UI", 8),
        justify="left",
        wraplength=790,
    ).pack(anchor="w", pady=(12, 0))

    self._promotion_controller = PromotionWorkbenchController(_promotion_state_dir())
    self._promotion_live_provider = CockpitLiveBaselineProvider()
    self._promotion_live_observation = None
    self._promotion_live_check_busy = False
    self.refresh_promotion_review()


def _apply_promotion_live_result(self, observation=None, error=None):
    C = legacy.C
    self._promotion_live_check_busy = False
    if error is not None:
        self._promotion_live_observation = None
        self.promotion_live_label.configure(text=f"Live baseline: ERROR · {error}", fg=C["danger"])
        self.promotion_gate_label.configure(
            text="LIVE BASELINE GATE: không xác minh được upstream → reviewer action bị khóa (fail-closed).",
            fg=C["danger"],
        )
        return
    self._promotion_live_observation = observation
    live = str((observation or {}).get("baseline") or "")
    checked = str((observation or {}).get("checked_utc") or "")
    matched = live == COCKPIT_BASELINE
    self.promotion_live_label.configure(
        text=f"Live baseline: {live or '—'} · {'MATCH' if matched else 'DRIFT'} · checked {checked}",
        fg=C["success"] if matched else C["danger"],
    )
    if matched:
        self.promotion_gate_label.configure(
            text="LIVE BASELINE GATE: MATCH. Reviewer actions vẫn khóa cho tới khi evidence/reviewer/lane form được ràng buộc đầy đủ.",
            fg=C["success"],
        )
    else:
        self.promotion_gate_label.configure(
            text=f"LIVE BASELINE GATE: DRIFT {COCKPIT_BASELINE} → {live or 'unknown'} · mọi substantive reviewer action phải fail-closed.",
            fg=C["danger"],
        )


def _start_promotion_live_check(self):
    if getattr(self, "_promotion_live_check_busy", False):
        return
    provider = getattr(self, "_promotion_live_provider", None)
    if provider is None:
        return
    self._promotion_live_check_busy = True
    self.promotion_live_label.configure(text="Live baseline: đang kiểm tra GitHub Releases…", fg=legacy.C["muted"])

    def worker():
        try:
            observation = provider.observe()
            self.root.after(0, lambda: self._apply_promotion_live_result(observation=observation))
        except LiveBaselineError as exc:
            self.root.after(0, lambda e=str(exc): self._apply_promotion_live_result(error=e))
        except Exception as exc:
            self.root.after(0, lambda e=f"unexpected provider error: {exc}": self._apply_promotion_live_result(error=e))

    threading.Thread(target=worker, daemon=True).start()


def _refresh_promotion_review(self):
    C = legacy.C
    ctl = getattr(self, "_promotion_controller", None)
    if ctl is None:
        return
    report = _safe_json(ctl.report_path, {})
    ledger = []
    try:
        from HMS_Codex_WindowsPromotionDecisionLedger import read_ledger
        ledger = read_ledger(ctl.ledger_path)
    except Exception:
        ledger = []

    verified = report.get("real_packet_verified") is True
    self.promotion_baseline_label.configure(text=f"Frozen parity authority: Cockpit Tools {COCKPIT_BASELINE}")
    self.promotion_packet_label.configure(
        text=("External Windows packet: VERIFIED" if verified else "External Windows packet: chưa có verified packet"),
        fg=C["success"] if verified else C["text2"],
    )
    self.promotion_ledger_label.configure(text=f"Decision ledger: {len(ledger)} record(s) · raw reviewer identity không được lưu")
    self.promotion_gate_label.configure(
        text="LIVE BASELINE GATE: đang xác minh upstream; reviewer action khóa cho tới khi có kết quả.",
        fg=C["warning"],
    )
    self._start_promotion_live_check()


def _extended_show_page(self, name, animate=True):
    if name != "promotion":
        return _ORIGINAL_SHOW_PAGE(self, name, animate=animate)
    if name not in self.pages:
        return
    old = self.pages.get(self.current_page)
    new = self.pages[name]
    if old is new and new.winfo_ismapped():
        self.refresh_promotion_review()
        return
    for key, item in self.nav.items():
        item.set_active(key == name)
    self.page_title.configure(text="Promotion review")
    self.page_subtitle.configure(text="Windows evidence · two-reviewer ledger · trusted live-baseline fail-closed gate")
    if old and old.winfo_ismapped():
        old.place_forget()
    self.current_page = name
    self.refresh_promotion_review()
    if not animate:
        new.place(x=0, y=0, relwidth=1, relheight=1)
        return
    new.place(x=18, y=0, relwidth=1, relheight=1)
    steps = 7

    def step(i=0):
        if i >= steps:
            new.place(x=0, y=0, relwidth=1, relheight=1)
            return
        x = int(18 * (1 - (i + 1) / steps))
        new.place(x=x, y=0, relwidth=1, relheight=1)
        self.root.after(18, lambda: step(i + 1))

    step()


legacy.HmsApp._build_shell = _extended_build_shell
legacy.HmsApp._build_pages = _extended_build_pages
legacy.HmsApp.show_page = _extended_show_page
legacy.HmsApp.refresh_promotion_review = _refresh_promotion_review
legacy.HmsApp._start_promotion_live_check = _start_promotion_live_check
legacy.HmsApp._apply_promotion_live_result = _apply_promotion_live_result


def extension_proof():
    checks = {
        "wrapper_version_25_75": legacy.APP_VERSION == APP_VERSION == "25.75",
        "promotion_page_hook_installed": legacy.HmsApp._build_pages is _extended_build_pages,
        "promotion_navigation_hook_installed": legacy.HmsApp.show_page is _extended_show_page,
        "controller_live_recheck_gate_available": hasattr(PromotionWorkbenchController, "record_review_action"),
        "trusted_live_provider_available": hasattr(CockpitLiveBaselineProvider, "get_live_baseline"),
        "review_actions_still_not_exposed": "record_review_action" not in _extended_build_pages.__code__.co_names,
    }
    tests = [{"name": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": "HMS-AI-ROUTER",
        "version": APP_VERSION,
        "suite": "GUI_PROMOTION_REVIEW_EXTENSION_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "automatic_production_certification": False,
        "production_score_mutation_authorized": False,
    }


def main():
    if "--proof" in sys.argv[1:]:
        result = extension_proof()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["verdict"] == "PASS" else 2
    legacy.HmsApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
