#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import HMS_Codex_WindowsRecoveryContract as contract

PRODUCT = contract.PRODUCT
VERSION = contract.VERSION


def _location_for(target_path: str) -> Path | None:
    text = str(target_path or "").strip().strip('"')
    if not text:
        return None
    path = Path(text)
    if path.exists() and path.is_dir():
        return path
    if path.exists() and path.is_file():
        return path.parent
    parent = path.parent
    return parent if str(parent) not in ("", ".") else None


def open_location(target_path: str) -> dict[str, Any]:
    location = _location_for(target_path)
    if location is None:
        return {"ok": False, "reason": "RECOVERY_LOCATION_UNAVAILABLE"}
    if os.name != "nt":
        return {"ok": False, "reason": "WINDOWS_REQUIRED", "location": str(location)}
    try:
        os.startfile(str(location))  # type: ignore[attr-defined]
        return {"ok": True, "location": str(location)}
    except Exception as exc:
        return {"ok": False, "reason": "RECOVERY_OPEN_LOCATION_FAILED", "detail": contract.sanitize_detail(exc)}


def copy_error(root, plan: dict[str, Any]) -> dict[str, Any]:
    detail = str(plan.get("sanitized_detail") or "")
    try:
        root.clipboard_clear()
        root.clipboard_append(detail)
        root.update_idletasks()
        return {"ok": True, "copied": True}
    except Exception as exc:
        return {"ok": False, "reason": "RECOVERY_CLIPBOARD_FAILED", "detail": contract.sanitize_detail(exc)}


def show_recovery_dialog(parent, plan: dict[str, Any]) -> str:
    if plan.get("surface_mode") == "QUIET_BACKGROUND":
        return "QUIET"

    import tkinter as tk

    result = {"action": contract.ACTION_CANCEL}
    colors = {
        "bg": "#0f172a", "surface": "#1e293b", "border": "#334155",
        "text": "#f1f5f9", "muted": "#94a3b8", "primary": "#2563eb",
        "warning": "#b7791f", "danger": "#b91c1c", "button": "#334155",
    }

    win = tk.Toplevel(parent)
    win.title("HMS-AI-ROUTER — Windows Recovery")
    win.configure(bg=colors["bg"])
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()

    frame = tk.Frame(win, bg=colors["surface"], highlightbackground=colors["border"], highlightthickness=1)
    frame.pack(fill="both", expand=True, padx=12, pady=12)

    category = str(plan.get("category") or contract.RECOVERY_OTHER)
    operation = str(plan.get("operation") or "UNKNOWN")
    title_map = {
        contract.RECOVERY_ACCESS_DENIED: "Windows từ chối quyền truy cập",
        contract.RECOVERY_FILE_IN_USE: "Tệp hoặc tài nguyên đang được sử dụng",
        contract.RECOVERY_PROGRAM_MISSING: "Không tìm thấy chương trình/tệp cần thiết",
        contract.RECOVERY_OTHER: "Thao tác Windows không hoàn tất",
    }
    tk.Label(frame, text=title_map.get(category, title_map[contract.RECOVERY_OTHER]), bg=colors["surface"],
             fg=colors["text"], font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", padx=14, pady=(12, 3))
    tk.Label(frame, text=f"Operation: {operation}", bg=colors["surface"], fg=colors["muted"],
             font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(0, 8))

    detail_box = tk.Text(frame, width=72, height=8, wrap="word", bg="#111827", fg=colors["text"],
                         insertbackground=colors["text"], relief="flat", font=("Consolas", 8), padx=8, pady=8)
    detail_box.insert("1.0", str(plan.get("sanitized_detail") or "Không có chi tiết lỗi."))
    detail_box.configure(state="disabled")
    detail_box.pack(fill="x", padx=14, pady=(0, 8))

    hint = "HMS không tự bỏ qua lỗi. Hãy thử lại, xử lý nguyên nhân bên ngoài rồi thử lại, hoặc đóng thao tác."
    if plan.get("uac_eligible") is True:
        hint += " UAC chỉ được đề nghị một lần khi caller đã xác nhận đúng client được hỗ trợ."
    tk.Label(frame, text=hint, bg=colors["surface"], fg=colors["muted"], font=("Segoe UI", 8),
             justify="left", wraplength=570, anchor="w").pack(fill="x", padx=14, pady=(0, 10))

    row = tk.Frame(frame, bg=colors["surface"])
    row.pack(fill="x", padx=14, pady=(0, 12))

    def finish(action: str):
        result["action"] = action
        win.destroy()

    def button(text: str, command, *, bg: str | None = None):
        b = tk.Button(row, text=text, command=command, bg=bg or colors["button"], fg=colors["text"],
                      activebackground=colors["primary"], activeforeground=colors["text"], relief="flat",
                      bd=0, padx=10, pady=6, font=("Segoe UI Semibold", 8), cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        return b

    actions = set(plan.get("actions") or [])
    if contract.ACTION_RETRY in actions:
        button("THỬ LẠI", lambda: finish(contract.ACTION_RETRY), bg=colors["primary"])
    if contract.ACTION_MANUAL_RETRY in actions:
        button("ĐÃ XỬ LÝ → THỬ LẠI", lambda: finish(contract.ACTION_MANUAL_RETRY))
    if contract.ACTION_OPEN_LOCATION in actions:
        button("MỞ VỊ TRÍ", lambda: open_location(str(plan.get("target_path") or "")))
    if contract.ACTION_COPY_ERROR in actions:
        button("SAO CHÉP LỖI", lambda: copy_error(win, plan))
    if contract.ACTION_REQUEST_UAC_ONCE in actions:
        button("XIN QUYỀN WINDOWS 1 LẦN", lambda: finish(contract.ACTION_REQUEST_UAC_ONCE), bg=colors["warning"])
    button("ĐÓNG", lambda: finish(contract.ACTION_CANCEL), bg=colors["danger"])

    win.protocol("WM_DELETE_WINDOW", lambda: finish(contract.ACTION_CANCEL))
    try:
        parent.update_idletasks()
        win.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - win.winfo_reqwidth()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - win.winfo_reqheight()) // 2)
        win.geometry(f"+{x}+{y}")
    except Exception:
        pass
    win.wait_window()
    return str(result["action"])


def source_proof() -> dict[str, Any]:
    src = Path(__file__).read_text("utf-8")
    impl_src = src[:src.find("def source_proof")]
    access = contract.build_recovery_plan("Access denied os error 5", operation="CODEX_CLIENT_START",
                                          target_path=r"C:\Program Files\Codex\Codex.exe", supported_client=True)
    quiet = contract.build_recovery_plan("Access denied os error 5", operation="BACKGROUND_PROBE",
                                         background_probe=True)
    checks = {
        "quiet_probe_short_circuits_without_dialog": quiet["surface_mode"] == "QUIET_BACKGROUND" and 'return "QUIET"' in impl_src,
        "retry_action_wired": "ACTION_RETRY" in impl_src,
        "manual_retry_action_wired": "ACTION_MANUAL_RETRY" in impl_src,
        "open_location_action_wired": "ACTION_OPEN_LOCATION" in impl_src and "os.startfile" in impl_src,
        "copy_error_action_wired": "ACTION_COPY_ERROR" in impl_src and "clipboard_append" in impl_src,
        "uac_button_returns_request_only": "ACTION_REQUEST_UAC_ONCE" in impl_src and "ShellExecute" not in impl_src and '"runas"' not in impl_src.lower(),
        "dialog_never_auto_elevates": access["uac_automatic"] is False,
        "sanitized_detail_only": 'plan.get("sanitized_detail")' in impl_src and "raw_detail" not in impl_src,
        "cancel_is_default": '"action": contract.ACTION_CANCEL' in impl_src,
        "no_production_mutation": "production_score" not in impl_src and "windows_runtime_certified" not in impl_src,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "WINDOWS_RECOVERY_DIALOG_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests, "dialog_rendered": False, "uac_executed": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def main() -> int:
    out = source_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
