# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import datetime
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk, filedialog

APP_VERSION = "25.74"
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "HMS_AI_ROUTER_v25.23.1.ps1"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Clean-room parity palette based on Cockpit's public design system.
C = {
    "bg": "#0f172a",
    "bg2": "#111827",
    "surface": "#1e293b",
    "surface2": "#243247",
    "surface3": "#334155",
    "hover": "#2a3a50",
    "border": "#36465d",
    "border_soft": "#2b3b50",
    "primary": "#3b82f6",
    "primary_hover": "#2563eb",
    "accent": "#14b8a6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "text": "#f1f5f9",
    "text2": "#94a3b8",
    "muted": "#64748b",
    "shadow": "#090f1c",
}

TRACE_DIR = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "HMS_AI_MultiRouter"
TRACE_FILE = TRACE_DIR / "gui-v2529-startup.log"


def trace(message: str) -> None:
    try:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        with TRACE_FILE.open("a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def windows_chrome(root) -> None:
    """Best-effort Windows 11 polish: dark title bar, rounded corners and app id."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "HMS.AI.Cockpit.Native"
        )
    except Exception:
        pass
    try:
        root.update_idletasks()
        hwnd = root.winfo_id()
        value = ctypes.c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
                break
            except Exception:
                pass
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
        corner = ctypes.c_int(2)
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner)
            )
        except Exception:
            pass
    except Exception:
        pass


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def rgb_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    ar = hex_rgb(a)
    br = hex_rgb(b)
    return rgb_hex(tuple(ar[i] + (br[i] - ar[i]) * t for i in range(3)))


def rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
                 radius: int, **kwargs):
    r = max(2, min(radius, (x2-x1)//2, (y2-y1)//2))
    points = [
        x1+r, y1, x2-r, y1,
        x2, y1, x2, y1+r,
        x2, y2-r, x2, y2,
        x2-r, y2, x1+r, y2,
        x1, y2, x1, y2-r,
        x1, y1+r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


def draw_line_icon(canvas, name, cx, cy, color, scale=1.0, tag="icon"):
    """Small HMS vector icon set; avoids platform-dependent Unicode glyphs."""
    s = 7.0 * scale
    w = max(1, int(round(1.4 * scale)))
    kw = dict(fill=color, width=w, capstyle=tk.ROUND, joinstyle=tk.ROUND, tags=tag)
    if name == "home":
        canvas.create_line(cx-s, cy, cx, cy-s, cx+s, cy, **kw)
        canvas.create_line(cx-s*0.72, cy-0.3, cx-s*0.72, cy+s*0.8,
                           cx+s*0.72, cy+s*0.8, cx+s*0.72, cy-0.3, **kw)
    elif name == "accounts":
        canvas.create_oval(cx-s*0.42, cy-s, cx+s*0.42, cy-s*0.16,
                           outline=color, width=w, tags=tag)
        canvas.create_arc(cx-s, cy-s*0.05, cx+s, cy+s*1.25,
                          start=20, extent=140, style="arc",
                          outline=color, width=w, tags=tag)
    elif name == "logs":
        for dy in (-s*0.68, 0, s*0.68):
            canvas.create_oval(cx-s, cy+dy-1, cx-s+2, cy+dy+1,
                               fill=color, outline=color, tags=tag)
            canvas.create_line(cx-s*0.45, cy+dy, cx+s, cy+dy, **kw)
    elif name == "settings":
        canvas.create_oval(cx-s*0.38, cy-s*0.38, cx+s*0.38, cy+s*0.38,
                           outline=color, width=w, tags=tag)
        for angle in range(0, 360, 45):
            import math as _m
            a = _m.radians(angle)
            x1 = cx + _m.cos(a)*s*0.62
            y1 = cy + _m.sin(a)*s*0.62
            x2 = cx + _m.cos(a)*s
            y2 = cy + _m.sin(a)*s
            canvas.create_line(x1, y1, x2, y2, **kw)
    elif name == "refresh":
        canvas.create_arc(cx-s, cy-s, cx+s, cy+s, start=30, extent=285,
                          style="arc", outline=color, width=w, tags=tag)
        canvas.create_line(cx+s*0.62, cy-s*0.67, cx+s, cy-s*0.74,
                           cx+s*0.82, cy-s*0.38, **kw)
    elif name == "play":
        canvas.create_polygon(cx-s*0.5, cy-s*0.72, cx+s*0.72, cy,
                              cx-s*0.5, cy+s*0.72, fill=color, outline=color, tags=tag)
    elif name == "power":
        canvas.create_arc(cx-s*0.8, cy-s*0.6, cx+s*0.8, cy+s,
                          start=40, extent=280, style="arc",
                          outline=color, width=w, tags=tag)
        canvas.create_line(cx, cy-s, cx, cy+s*0.05, **kw)
    elif name == "copy":
        canvas.create_rectangle(cx-s*0.35, cy-s*0.72, cx+s*0.72, cy+s*0.38,
                                outline=color, width=w, tags=tag)
        canvas.create_rectangle(cx-s*0.72, cy-s*0.35, cx+s*0.35, cy+s*0.72,
                                outline=color, width=w, tags=tag)
    elif name == "route":
        canvas.create_line(cx-s, cy-s*0.45, cx+s*0.45, cy-s*0.45, **kw)
        canvas.create_line(cx+s*0.2, cy-s*0.72, cx+s*0.65, cy-s*0.45,
                           cx+s*0.2, cy-s*0.18, **kw)
        canvas.create_line(cx+s, cy+s*0.45, cx-s*0.45, cy+s*0.45, **kw)
        canvas.create_line(cx-s*0.2, cy+s*0.72, cx-s*0.65, cy+s*0.45,
                           cx-s*0.2, cy+s*0.18, **kw)
    else:
        canvas.create_oval(cx-s*0.55, cy-s*0.55, cx+s*0.55, cy+s*0.55,
                           outline=color, width=w, tags=tag)


def draw_hms_mark(canvas, cx, cy, size=28):
    s = size / 2
    rounded_rect(canvas, int(cx-s), int(cy-s), int(cx+s), int(cy+s),
                 max(6, int(size*0.28)), fill="#1b3560", outline="#315b96", width=1)
    canvas.create_line(cx-s*0.42, cy-s*0.47, cx-s*0.42, cy+s*0.47,
                       fill="#f1f5f9", width=max(2, int(size*0.13)), capstyle=tk.ROUND)
    canvas.create_line(cx+s*0.42, cy-s*0.47, cx+s*0.42, cy+s*0.47,
                       fill="#f1f5f9", width=max(2, int(size*0.13)), capstyle=tk.ROUND)
    canvas.create_line(cx-s*0.32, cy, cx+s*0.32, cy,
                       fill=C["accent"], width=max(2, int(size*0.13)), capstyle=tk.ROUND)



class ToolTip:
    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.job = None
        self.win = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self.job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.job:
            try:
                self.widget.after_cancel(self.job)
            except Exception:
                pass
            self.job = None

    def _show(self):
        if self.win or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            self.win = tk.Toplevel(self.widget)
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.configure(bg=C["border"])
            frame = tk.Frame(self.win, bg="#162033")
            frame.pack(padx=1, pady=1)
            tk.Label(
                frame, text=self.text, bg="#162033", fg=C["text2"],
                font=("Segoe UI", 8), padx=9, pady=6,
                justify="left", wraplength=280
            ).pack()
            self.win.geometry(f"+{x}+{y}")
        except Exception:
            self.win = None

    def _hide(self, _=None):
        self._cancel()
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


class HoverButton(tk.Canvas):
    def __init__(self, master, text, command, width=130, height=36,
                 bg=C["surface3"], hover=C["hover"], fg=C["text"],
                 radius=10, font=("Segoe UI Semibold", 10),
                 icon="", icon_name="", outline="", tooltip="", **kwargs):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2", **kwargs)
        self.w = width
        self.h = height
        self.radius = radius
        self.base = bg
        self.hover = hover
        self.fg = fg
        self.command = command
        self.current = bg
        self.target = bg
        self.animating = False
        self.enabled = True
        self.outline = outline
        self.rect = rounded_rect(self, 1, 1, width-1, height-1, radius,
                                 fill=bg, outline=outline or bg, width=1)
        self.icon_name = icon_name
        label = (icon + "  " + text).strip() if not icon_name else text
        text_x = width//2 + (7 if icon_name else 0)
        self.text_id = self.create_text(text_x, height//2, text=label,
                                        fill=fg, font=font)
        if icon_name:
            draw_line_icon(self, icon_name, max(16, width//2 - 34), height//2,
                           fg, 0.75, "btnicon")
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.tag_bind(self.rect, "<ButtonRelease-1>", self._release)
        self.tag_bind(self.text_id, "<ButtonRelease-1>", self._release)
        self.tooltip = ToolTip(self, tooltip) if tooltip else None

    def _enter(self, _=None):
        if self.enabled:
            self.target = self.hover
            self._animate()

    def _leave(self, _=None):
        self.target = self.base
        self._animate()

    def _press(self, event=None):
        if self.enabled:
            self.move(self.text_id, 0, 1)
            if event is not None:
                self._ripple(event.x, event.y)

    def _ripple(self, x, y):
        color = mix(self.current, "#ffffff", 0.22)
        ripple = self.create_oval(x-2, y-2, x+2, y+2,
                                  outline=color, width=1, tags="ripple")
        steps = 8
        max_r = max(self.w, self.h) * 0.58
        def step(i=0):
            if not self.winfo_exists():
                return
            if i >= steps:
                self.delete(ripple)
                return
            r = max_r * ((i+1)/steps)
            self.coords(ripple, x-r, y-r, x+r, y+r)
            self.after(16, lambda: step(i+1))
        step()

    def _release(self, _=None):
        if not self.enabled:
            return
        self.move(self.text_id, 0, -1)
        if self.command:
            self.command()

    def _animate(self):
        if self.animating:
            return
        self.animating = True

        def step():
            if not self.winfo_exists():
                return
            a = hex_rgb(self.current)
            b = hex_rgb(self.target)
            dist = max(abs(a[i]-b[i]) for i in range(3))
            if dist <= 4:
                self.current = self.target
                self.itemconfigure(self.rect, fill=self.current,
                                   outline=self.outline or self.current)
                self.animating = False
                return
            self.current = mix(self.current, self.target, 0.32)
            self.itemconfigure(self.rect, fill=self.current,
                               outline=self.outline or self.current)
            self.after(18, step)
        step()

    def set_text(self, text, icon=""):
        label = (icon + "  " + text).strip()
        self.itemconfigure(self.text_id, text=label)

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.itemconfigure(self.text_id, fill=self.fg if enabled else C["muted"])

    def set_colors(self, bg, hover=None, fg=None):
        self.base = bg
        self.target = bg
        self.current = bg
        self.hover = hover or bg
        if fg:
            self.fg = fg
            self.itemconfigure(self.text_id, fill=fg)
            if self.icon_name:
                self.delete("btnicon")
                draw_line_icon(self, self.icon_name, max(16, self.w//2 - 34),
                               self.h//2, fg, 0.75, "btnicon")
        self.itemconfigure(self.rect, fill=bg, outline=self.outline or bg)


class NavItem(tk.Canvas):
    def __init__(self, master, text, icon, command, width=190, height=42):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.w = width
        self.h = height
        self.command = command
        self.icon_name = icon
        self.active = False
        self.badge_on = False
        self.badge_color = C["warning"]
        self.bg_rect = rounded_rect(self, 0, 0, width, height, 10,
                                    fill=master.cget("bg"), outline=master.cget("bg"))
        self.bar = rounded_rect(self, 0, 9, 3, height-9, 2,
                                fill=master.cget("bg"), outline=master.cget("bg"))
        self.text_id = self.create_text(43, height//2, anchor="w", text=text,
                                        fill=C["text2"], font=("Segoe UI Semibold", 9))
        self.badge = self.create_oval(width-16, height//2-3, width-10, height//2+3,
                                      fill=master.cget("bg"), outline=master.cget("bg"))
        self._draw_icon(C["text2"])
        for tag in (self.bg_rect, self.bar, self.text_id, self.badge):
            self.tag_bind(tag, "<ButtonRelease-1>", self._click)
        self.tag_bind("navicon", "<ButtonRelease-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _draw_icon(self, color):
        self.delete("navicon")
        draw_line_icon(self, self.icon_name, 20, self.h//2, color, 0.92, "navicon")

    def _click(self, _=None):
        if self.command:
            self.command()

    def _enter(self, _=None):
        if not self.active:
            self.itemconfigure(self.bg_rect, fill=C["hover"], outline=C["hover"])
            self.itemconfigure(self.text_id, fill=C["text"])
            self._draw_icon(C["text"])

    def _leave(self, _=None):
        if not self.active:
            bg = self.master.cget("bg")
            self.itemconfigure(self.bg_rect, fill=bg, outline=bg)
            self.itemconfigure(self.text_id, fill=C["text2"])
            self._draw_icon(C["text2"])
            self._update_badge()

    def set_active(self, active: bool):
        self.active = active
        bg = "#1d3457" if active else self.master.cget("bg")
        self.itemconfigure(self.bg_rect, fill=bg, outline=bg)
        self.itemconfigure(self.bar, fill=C["primary"] if active else bg,
                           outline=C["primary"] if active else bg)
        color = C["primary"] if active else C["text2"]
        self.itemconfigure(self.text_id, fill=color)
        self._draw_icon(color)
        self._update_badge()

    def set_badge(self, enabled: bool, color=None):
        self.badge_on = bool(enabled)
        if color:
            self.badge_color = color
        self._update_badge()

    def _update_badge(self):
        bg = self.badge_color if self.badge_on else ("#1d3457" if self.active else self.master.cget("bg"))
        self.itemconfigure(self.badge, fill=bg, outline=bg)


class Card(tk.Canvas):
    def __init__(self, master, width, height, bg=C["surface"], radius=16,
                 hover_border=False):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, bd=0)
        self.w = width
        self.h = height
        self.bg = bg
        self.hover_border = hover_border
        self.shadow = rounded_rect(self, 5, 7, width-1, height-1, radius,
                                   fill=C["shadow"], outline=C["shadow"])
        self.rect = rounded_rect(self, 1, 1, width-6, height-7, radius,
                                 fill=bg, outline=C["border_soft"], width=1)
        if hover_border:
            self.bind("<Enter>", self._enter)
            self.bind("<Leave>", self._leave)

    def _enter(self, _=None):
        self.itemconfigure(self.rect, outline=mix(C["border"], C["primary"], .55), width=1)
        self.itemconfigure(self.shadow, fill="#07101f")

    def _leave(self, _=None):
        self.itemconfigure(self.rect, outline=C["border_soft"], width=1)
        self.itemconfigure(self.shadow, fill=C["shadow"])


class Pill(tk.Canvas):
    def __init__(self, master, text, mode="neutral", width=100, height=24):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, bd=0)
        self.w = width
        self.h = height
        colors = {
            "success": ("#153d2a", C["success"]),
            "warning": ("#453315", C["warning"]),
            "danger": ("#4a2227", C["danger"]),
            "primary": ("#1c335d", C["primary"]),
            "neutral": ("#273548", C["text2"]),
        }
        bg, fg = colors.get(mode, colors["neutral"])
        self.rect = rounded_rect(self, 0, 0, width, height, height//2,
                                 fill=bg, outline=mix(bg, fg, .35), width=1)
        self.text_id = self.create_text(width//2, height//2, text=text, fill=fg,
                                        font=("Segoe UI Semibold", 8))
    def set(self, text, mode):
        colors = {
            "success": ("#153d2a", C["success"]),
            "warning": ("#453315", C["warning"]),
            "danger": ("#4a2227", C["danger"]),
            "primary": ("#1c335d", C["primary"]),
            "neutral": ("#273548", C["text2"]),
        }
        bg, fg = colors.get(mode, colors["neutral"])
        self.itemconfigure(self.rect, fill=bg, outline=mix(bg, fg, .35))
        self.itemconfigure(self.text_id, text=text, fill=fg)



class ToggleSwitch(tk.Canvas):
    def __init__(self, master, variable=None, command=None, width=46, height=24):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.variable = variable or tk.BooleanVar(value=False)
        self.command = command
        self.w = width
        self.h = height
        self.pos = 1.0 if bool(self.variable.get()) else 0.0
        self.target = self.pos
        self.animating = False
        self.bind("<ButtonRelease-1>", self._toggle)
        self.variable.trace_add("write", lambda *_: self._on_var())
        self.draw()

    def _toggle(self, _=None):
        self.variable.set(not bool(self.variable.get()))
        if self.command:
            self.command()

    def _on_var(self):
        self.target = 1.0 if bool(self.variable.get()) else 0.0
        self._animate()

    def _animate(self):
        if self.animating:
            return
        self.animating = True

        def step():
            if not self.winfo_exists():
                return
            delta = self.target - self.pos
            if abs(delta) < 0.04:
                self.pos = self.target
                self.draw()
                self.animating = False
                return
            self.pos += delta * 0.34
            self.draw()
            self.after(16, step)
        step()

    def draw(self):
        self.delete("all")
        bg = mix("#3b4657", C["primary"], self.pos)
        rounded_rect(self, 0, 0, self.w, self.h, self.h//2,
                     fill=bg, outline=bg)
        knob = self.h - 6
        x_off = 3 + (self.w - knob - 6) * self.pos
        self.create_oval(x_off, 3, x_off + knob, 3 + knob,
                         fill="#ffffff", outline="#ffffff")


class ScrollableSettings(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=C["bg"])
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._sync_region)
        self.canvas.bind("<Configure>", self._sync_width)
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _sync_region(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event):
        self.canvas.itemconfigure(self.win, width=event.width)

    def _wheel(self, event):
        try:
            if self.winfo_ismapped():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass


class SettingGroup(tk.Frame):
    def __init__(self, master, title, desc=""):
        super().__init__(master, bg=C["bg"])
        head = tk.Frame(self, bg=C["bg"], height=38)
        head.pack(fill="x", padx=2)
        head.pack_propagate(False)
        tk.Frame(head, bg=C["primary"], width=4, height=18).place(x=0, y=10)
        tk.Label(head, text=title, bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 11)).place(x=14, y=7)
        if desc:
            tk.Label(head, text=desc, bg=C["bg"], fg=C["muted"],
                     font=("Segoe UI", 8)).place(relx=1, x=-2, y=11, anchor="ne")
        self.card = tk.Frame(self, bg=C["surface"],
                             highlightbackground=C["border_soft"],
                             highlightthickness=1)
        self.card.pack(fill="x")
        self.rows = 0

    def add_row(self, title, desc, control, danger=False, height=66):
        row = tk.Frame(self.card, bg=C["surface"], height=height)
        row.pack(fill="x")
        row.pack_propagate(False)
        if self.rows:
            tk.Frame(row, bg=C["border_soft"], height=1).pack(fill="x", side="top")
        label = tk.Frame(row, bg=C["surface"])
        label.pack(side="left", fill="both", expand=True, padx=(18, 10), pady=11)
        tk.Label(label, text=title, bg=C["surface"],
                 fg=C["danger"] if danger else C["text"],
                 font=("Segoe UI Semibold", 9), anchor="w").pack(anchor="w")
        tk.Label(label, text=desc, bg=C["surface"], fg=C["text2"],
                 font=("Segoe UI", 8), anchor="w", justify="left",
                 wraplength=460).pack(anchor="w", pady=(3, 0))
        right = tk.Frame(row, bg=C["surface"], width=230)
        right.pack(side="right", fill="y", padx=(8, 18))
        right.pack_propagate(False)
        control.pack(in_=right, side="right", pady=(height - control.winfo_reqheight())//2)
        for widget in (row, label, right):
            widget.bind("<Enter>", lambda e, r=row: r.configure(bg=C["hover"]))
            widget.bind("<Leave>", lambda e, r=row: r.configure(bg=C["surface"]))
        self.rows += 1
        return row


class HmsApp:
    def __init__(self):
        dpi_awareness()
        trace("START v25.66 HMS_GUI.pyw")
        self.root = tk.Tk()
        self.root.title(f"HMS-AI-ROUTER v{APP_VERSION}")
        self.root.configure(bg=C["bg"])
        try:
            self.root.iconbitmap(str(ROOT / "HMS_AI_ROUTER.ico"))
        except Exception:
            pass
        self.root.geometry("1080x700")
        self.root.minsize(1040, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.attributes("-alpha", 0.0)
        windows_chrome(self.root)
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure(
            "HMS.TCombobox",
            fieldbackground=C["surface3"], background=C["surface3"],
            foreground=C["text"], arrowcolor=C["text2"],
            bordercolor=C["border"], lightcolor=C["border"],
            darkcolor=C["border"], padding=6
        )
        self.style.map(
            "HMS.TCombobox",
            fieldbackground=[("readonly", C["surface3"])],
            foreground=[("readonly", C["text"])]
        )
        self.style.configure(
            "HMS.Vertical.TScrollbar",
            background=C["surface3"], troughcolor=C["bg"],
            bordercolor=C["bg"], arrowcolor=C["text2"]
        )
        self.busy = False
        self.status_data = {}
        self.settings_data = {}
        self.settings_vars = {}
        self.settings_loaded = False
        self.settings_dirty = False
        self.settings_current_tab = "general"
        self.first_status_loaded = False
        self.pulse_phase = 0
        self.last_sync_text = "Chưa đồng bộ"
        self.account_center_data = {}
        self.instances_data = {}
        self.project_affinity_data = {}
        self.model_manager_data = {}
        self.smart_model_router_data = {}
        self.usage_data = {}
        self.quota_center_data = {}
        self.release_data = {}
        self.logs_data = {}
        self.service_data = {}
        self.service_current_tab = "service"
        self.current_page = "overview"
        self.maintenance_busy = False
        self.maintenance_data = {}
        self.last_maintenance_text = "Automation đang khởi tạo"
        self.pages = {}
        self.nav = {}
        self._build_shell()
        self._build_pages()
        self.show_page("overview", animate=False)
        self._start_status_pulse()
        self._center()
        self.root.deiconify()
        self.root.lift()
        self.root.after(40, self._fade_in)
        self.root.bind("<Control-r>", lambda e: self.refresh_async())
        self.root.bind("<Control-comma>", lambda e: self.show_page("settings"))
        self.root.bind("<Control-o>", lambda e: self.open_codex())
        self.root.after(120, self.startup_recovery_reconcile_async)
        self.root.after(300, self.refresh_async)
        self.root.after(3500, self._maintenance_periodic)
        self.root.after(6000, self._periodic)
        trace("GUI VISIBLE; BACKEND + NATIVE AUTOMATION SCHEDULED")

    def _center(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(1080, max(1040, sw - 120))
        h = min(700, max(680, sh - 120))
        x = max(0, (sw-w)//2)
        y = max(0, (sh-h)//2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _fade_in(self):
        try:
            a = float(self.root.attributes("-alpha"))
            if a < 1:
                self.root.attributes("-alpha", min(1, a + .11))
                self.root.after(18, self._fade_in)
            else:
                self.root.attributes("-topmost", True)
                self.root.after(180, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def _build_shell(self):
        self.bg_canvas = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0, bd=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        # Very subtle ambient glow; kept low contrast like Cockpit's modern pages.
        self.bg_canvas.create_oval(-240, -250, 470, 340, fill="#122348", outline="")
        self.bg_canvas.create_oval(790, -240, 1390, 300, fill="#10343e", outline="")

        self.sidebar = tk.Frame(self.root, bg="#151e30", width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg="#151e30", height=88)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        badge = tk.Canvas(brand, width=36, height=36, bg="#151e30",
                          highlightthickness=0, bd=0)
        badge.place(x=17, y=18)
        draw_hms_mark(badge, 18, 18, 34)
        tk.Label(brand, text="HMS", bg="#151e30", fg=C["text"],
                 font=("Segoe UI Semibold", 15)).place(x=61, y=18)
        tk.Label(brand, text="AI COCKPIT", bg="#151e30", fg=C["muted"],
                 font=("Segoe UI Semibold", 7)).place(x=62, y=46)

        nav_frame = tk.Frame(self.sidebar, bg="#151e30")
        nav_frame.pack(fill="x", padx=12)
        items = [
            ("overview", "Tổng quan", "home"),
            ("accounts", "Tài khoản", "accounts"),
            ("quota", "Quota", "accounts"),
            ("usage", "Sử dụng", "logs"),
            ("analytics", "Phân tích", "logs"),
            ("modelmgr", "Models Codex", "route"),
            ("smartmodel", "Smart Router", "route"),
            ("lanpool", "LAN Pool", "route"),
            ("orchestrator", "Điều phối Project", "route"),
            ("team", "Đội Codex", "route"),
            ("projects", "Dự án Codex", "route"),
            ("instances", "Codex Instances", "route"),
            ("selfheal", "Tự sửa Codex", "settings"),
            ("security", "Bảo mật", "settings"),
            ("diagnostics", "Chẩn đoán", "logs"),
            ("logs", "Nhật ký", "logs"),
            ("settings", "Cài đặt", "settings"),
        ]
        for key, text, icon in items:
            item = NavItem(nav_frame, text, icon, lambda k=key: self.show_page(k),
                           width=184, height=40)
            item.pack(fill="x", pady=2)
            self.nav[key] = item

        spacer = tk.Frame(self.sidebar, bg="#151e30")
        spacer.pack(fill="both", expand=True)

        foot = tk.Frame(self.sidebar, bg="#151e30", height=72)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        tk.Frame(foot, bg=C["border_soft"], height=1).pack(fill="x", padx=14, pady=(0, 11))
        self.sidebar_status = tk.Label(
            foot, text="●  Đang kiểm tra", bg="#151e30", fg=C["muted"],
            font=("Segoe UI Semibold", 8)
        )
        self.sidebar_status.pack(anchor="w", padx=18)
        tk.Label(foot, text=f"v{APP_VERSION}", bg="#151e30", fg="#4f6075",
                 font=("Segoe UI", 7)).pack(anchor="w", padx=18, pady=(3, 0))

        self.main = tk.Frame(self.root, bg=C["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self.topbar = tk.Frame(self.main, bg=C["bg"], height=62)
        self.topbar.pack(fill="x", padx=24, pady=(14, 0))
        self.topbar.pack_propagate(False)

        self.page_title = tk.Label(
            self.topbar, text="Tổng quan", bg=C["bg"], fg=C["text"],
            font=("Segoe UI Semibold", 16)
        )
        self.page_title.place(x=0, y=4)
        self.page_subtitle = tk.Label(
            self.topbar,
            text="Codex-only · Smart Model Router · Multi-Codex Team · closed-loop · security hardened",
            bg=C["bg"], fg=C["text2"], font=("Segoe UI", 8)
        )
        self.page_subtitle.place(x=1, y=32)

        self.sync_label = tk.Label(
            self.topbar, text="Chưa đồng bộ", bg=C["bg"], fg=C["muted"],
            font=("Segoe UI", 7)
        )
        self.sync_label.place(relx=1.0, x=-108, y=15, anchor="ne")
        self.refresh_btn = HoverButton(
            self.topbar, "Làm mới", self.refresh_async, width=96, height=30,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"],
            font=("Segoe UI Semibold", 8), icon_name="refresh",
            tooltip="Làm mới trạng thái Router, Codex và tài khoản."
        )
        self.refresh_btn.place(relx=1.0, x=-2, y=6, anchor="ne")

        self.content = tk.Frame(self.main, bg=C["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 20))
    def _build_pages(self):
        self._build_overview()
        self._build_accounts()
        self._build_quota_center()
        self._build_usage()
        self._build_account_analytics()
        self._build_model_manager()
        self._build_smart_model_router()
        self._build_lan_pool()
        self._build_project_orchestrator()
        self._build_multi_codex_team()
        self._build_projects()
        self._build_instances()
        self._build_self_healing()
        self._build_security_hardening()
        self._build_unified_diagnostics()
        self._build_logs()
        self._build_settings()

    def _build_overview(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["overview"] = page

        tabs = tk.Frame(page, bg=C["surface"],
                        highlightbackground=C["border_soft"], highlightthickness=1)
        tabs.pack(anchor="w", pady=(0, 10), ipady=3, ipadx=3)
        self.service_tab_buttons = {}
        for key, text in [
            ("service", "Dịch vụ"),
            ("models", "Models"),
            ("keys", "API Keys"),
            ("routing", "Routing"),
            ("compat", "API Compat"),
            ("failover", "Failover"),
        ]:
            btn = HoverButton(
                tabs, text, lambda k=key: self.show_service_tab(k),
                width=92 if key != "failover" else 96, height=29,
                bg=C["surface"], hover=C["hover"], outline="",
                font=("Segoe UI Semibold", 8)
            )
            btn.pack(side="left", padx=2)
            self.service_tab_buttons[key] = btn

        self.service_body = tk.Frame(page, bg=C["bg"])
        self.service_body.pack(fill="both", expand=True)
        self.service_views = {}
        for key in ("service","models","keys","routing","compat","failover"):
            self.service_views[key] = tk.Frame(self.service_body, bg=C["bg"])

        self._build_service_overview(self.service_views["service"])
        self._build_models_view(self.service_views["models"])
        self._build_keys_view(self.service_views["keys"])
        self._build_routing_view(self.service_views["routing"])
        self._build_compat_view(self.service_views["compat"])
        self._build_failover_view(self.service_views["failover"])
        self.show_service_tab("service", refresh=False)

    def _build_service_overview(self, page):
        hero = Card(page, 820, 82, bg=C["surface"], radius=12)
        hero.pack(fill="x", pady=(0, 10))
        self.hero_card = hero

        icon = tk.Canvas(hero, width=30, height=30, bg=C["surface"],
                         highlightthickness=0, bd=0)
        rounded_rect(icon, 1, 1, 29, 29, 9,
                     fill="#1a3562", outline="#2e5a95", width=1)
        draw_line_icon(icon, "route", 15, 15, "#6ca2ff", 0.9, "serviceicon")
        hero.create_window(14, 14, window=icon, anchor="nw")
        hero.create_text(54, 15, anchor="nw", text="Codex API Service",
                         fill=C["text"], font=("Segoe UI Semibold", 11))
        hero.create_text(
            54, 39, anchor="nw",
            text="OAuth pool · session affinity · failover · native control center",
            fill=C["text2"], font=("Segoe UI", 8)
        )
        self.status_pill = Pill(hero, "ĐANG KIỂM TRA", "neutral", 110, 22)
        hero.create_window(54, 57, window=self.status_pill, anchor="nw")

        self.open_codex_btn = HoverButton(
            hero, "MỞ CODEX", self.open_codex, width=118, height=31,
            bg=C["surface3"], hover=C["hover"], outline=C["border"],
            icon_name="play", font=("Segoe UI Semibold", 8),
            tooltip="Mở hoặc đưa Codex/ChatGPT Desktop lên trước bằng HMS Router."
        )
        hero.create_window(654, 12, window=self.open_codex_btn, anchor="nw")
        self.toggle_btn = HoverButton(
            hero, "BẬT HMS", self.toggle, width=118, height=31,
            bg=C["primary"], hover=C["primary_hover"], icon_name="power",
            font=("Segoe UI Semibold", 8),
            tooltip="Một nút tự xử lý Router, Codex reload, Watchdog và rollback."
        )
        hero.create_window(654, 47, window=self.toggle_btn, anchor="nw")

        stats = tk.Frame(page, bg=C["bg"])
        stats.pack(fill="x", pady=(0, 10))
        self.stat_cards = {}
        for i,(key,title,val,icon_text) in enumerate([
            ("accounts","TÀI KHOẢN","—","◉"),
            ("ready","READY / COOLDOWN","—","✓"),
            ("router","ROUTER","—","↔"),
            ("mode","MODE","—","◆"),
        ]):
            card=Card(stats,196,72,bg=C["surface"],radius=12,hover_border=True)
            card.grid(row=0,column=i,padx=(0 if i==0 else 5,5 if i<3 else 0),sticky="nsew")
            stats.grid_columnconfigure(i,weight=1)
            card.create_text(14,12,anchor="nw",text=icon_text,fill=C["muted"],font=("Segoe UI Symbol",8))
            card.create_text(31,12,anchor="nw",text=title,fill=C["muted"],font=("Segoe UI Semibold",7))
            value_id=card.create_text(14,37,anchor="nw",text=val,fill=C["text"],font=("Segoe UI Semibold",14))
            self.stat_cards[key]=(card,value_id)

        live=Card(page,820,58,bg=C["surface"],radius=12,hover_border=True)
        live.pack(fill="x",pady=(0,10))
        live.create_text(15,10,anchor="nw",text="Route gần nhất",
                         fill=C["muted"],font=("Segoe UI Semibold",7))
        self.live_account_id=live.create_text(15,28,anchor="nw",text="Chưa có request được nhận diện",
                                              fill=C["text"],font=("Segoe UI Semibold",10))
        self.live_detail_id=live.create_text(260,30,anchor="nw",text="CONFIDENCE — · chờ dữ liệu router",
                                             fill=C["text2"],font=("Segoe UI",7),width=420)
        self.live_auto_id=live.create_text(790,29,anchor="ne",text="AUTO · khởi tạo",
                                           fill=C["muted"],font=("Segoe UI Semibold",7))
        self.live_card=live

        gateway=Card(page,820,96,bg=C["surface"],radius=12)
        gateway.pack(fill="x",pady=(0,10))
        gateway.create_text(15,12,anchor="nw",text="Gateway",fill=C["text"],font=("Segoe UI Semibold",9))
        gateway.create_text(15,33,anchor="nw",text="Base URL",fill=C["muted"],font=("Segoe UI",7))
        self.base_var=tk.StringVar(value="http://127.0.0.1:8317/v1")
        base=tk.Entry(gateway,textvariable=self.base_var,state="readonly",readonlybackground="#172033",
                      fg=C["text2"],relief="flat",bd=0,font=("Consolas",8))
        gateway.create_window(15,51,width=590,height=25,window=base,anchor="nw")
        copy=HoverButton(gateway,"COPY",self.copy_base,width=72,height=25,bg=C["surface3"],
                         hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7),
                         icon_name="copy",tooltip="Sao chép Base URL của HMS Router.")
        gateway.create_window(617,51,window=copy,anchor="nw")
        self.gateway_note_id=gateway.create_text(15,80,anchor="nw",text="Đang đọc routing...",
                                                 fill=C["text2"],font=("Segoe UI",7))
        self.gateway_card=gateway

        accounts=Card(page,820,165,bg=C["surface"],radius=12)
        accounts.pack(fill="x")
        accounts.create_text(15,12,anchor="nw",text="Tài khoản đang hoạt động",
                             fill=C["text"],font=("Segoe UI Semibold",9))
        accounts.create_text(791,13,anchor="ne",text="quota / trạng thái",
                             fill=C["muted"],font=("Segoe UI",7))
        self.overview_accounts=tk.Frame(accounts,bg=C["surface"])
        accounts.create_window(14,37,width=786,height=112,window=self.overview_accounts,anchor="nw")
        self._render_loading_accounts()

    def _build_models_view(self, page):
        head=tk.Frame(page,bg=C["bg"],height=42);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="Models khả dụng",bg=C["bg"],fg=C["text"],
                 font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        test=HoverButton(head,"TEST /v1/models",self.test_api_async,width=132,height=30,
                         bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],
                         font=("Segoe UI Semibold",8))
        test.pack(side="right",pady=4)
        self.models_status=tk.Label(page,text="Đang chờ dữ liệu service...",
                                    bg=C["bg"],fg=C["muted"],font=("Segoe UI",7))
        self.models_status.pack(anchor="w",pady=(0,6))
        self.models_scroll=ScrollableSettings(page);self.models_scroll.pack(fill="both",expand=True)
        self.models_list=self.models_scroll.inner

    def _build_keys_view(self, page):
        head=tk.Frame(page,bg=C["bg"],height=42);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="API Keys",bg=C["bg"],fg=C["text"],
                 font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        create=HoverButton(head,"TẠO CLIENT KEY",self.show_create_client_key,
                           width=132,height=30,bg=C["primary"],hover=C["primary_hover"],
                           font=("Segoe UI Semibold",8),
                           tooltip="Tạo client key cho HMS Smart Gateway. Secret chỉ hiện một lần.")
        create.pack(side="right",pady=4)
        self.keys_status=tk.Label(page,text="Local router key được ẩn; chỉ hiển thị fingerprint.",
                                  bg=C["bg"],fg=C["muted"],font=("Segoe UI",7))
        self.keys_status.pack(anchor="w",pady=(0,6))
        self.keys_scroll=ScrollableSettings(page);self.keys_scroll.pack(fill="both",expand=True)
        self.keys_list=self.keys_scroll.inner

    def _build_routing_view(self, page):
        self.routing_card=Card(page,820,220,bg=C["surface"],radius=12)
        self.routing_card.pack(fill="x",pady=(0,10))
        self.routing_card.create_text(16,14,anchor="nw",text="Routing & Router Control",
                                      fill=C["text"],font=("Segoe UI Semibold",11))
        self.routing_summary_id=self.routing_card.create_text(
            16,48,anchor="nw",text="Đang tải...",fill=C["text2"],font=("Segoe UI",9),width=750
        )
        restart=HoverButton(self.routing_card,"RESTART ROUTER",self.restart_router_async,
                            width=132,height=31,bg=C["surface3"],hover=C["hover"],
                            outline=C["border"],font=("Segoe UI Semibold",8))
        self.routing_card.create_window(16,154,window=restart,anchor="nw")
        settings=HoverButton(self.routing_card,"MỞ SETTINGS",lambda:self.show_page("settings"),
                             width=120,height=31,bg=C["surface3"],hover=C["hover"],
                             outline=C["border"],font=("Segoe UI Semibold",8))
        self.routing_card.create_window(158,154,window=settings,anchor="nw")
        accounts=HoverButton(self.routing_card,"ACCOUNT CENTER",lambda:self.show_page("accounts"),
                             width=132,height=31,bg=C["surface3"],hover=C["hover"],
                             outline=C["border"],font=("Segoe UI Semibold",8))
        self.routing_card.create_window(288,154,window=accounts,anchor="nw")
        self.routing_diag=tk.Text(page,bg="#111827",fg=C["text2"],relief="flat",bd=0,
                                  font=("Consolas",8),wrap="word",height=15)
        self.routing_diag.pack(fill="both",expand=True)
        self.routing_diag.insert("1.0","Diagnostics sẽ hiện tại đây.")
        self.routing_diag.configure(state="disabled")

    def _build_compat_view(self, page):
        card=Card(page,820,188,bg=C["surface"],radius=12);card.pack(fill="x",pady=(0,10))
        card.create_text(16,14,anchor="nw",text="Full Codex API Compatibility v25.38",fill=C["text"],font=("Segoe UI Semibold",11))
        card.create_text(16,39,anchor="nw",text="Stable HMS endpoint · body-preserving pass-through · SSE · tools/MCP/search/image/structured output · OpenAI-shaped gateway errors",fill=C["text2"],font=("Segoe UI",8),width=625)
        self.compat_status_id=card.create_text(16,73,anchor="nw",text="Chưa đọc compatibility audit.",fill=C["muted"],font=("Segoe UI Semibold",8),width=600)
        self.compat_live_id=card.create_text(16,99,anchor="nw",text="Live contract: —",fill=C["muted"],font=("Segoe UI",8),width=600)
        self.compat_audit_btn=HoverButton(card,"AUDIT API",self.run_api_compat_async,width=120,height=31,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",8),tooltip="Chạy synthetic compatibility audit cục bộ; không gửi prompt/OAuth ra ngoài.")
        card.create_window(675,20,window=self.compat_audit_btn,anchor="nw")
        self.compat_matrix=tk.Text(page,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",8),wrap="none",height=16)
        self.compat_matrix.pack(fill="both",expand=True);self.compat_matrix.insert("1.0","Đang chờ API compatibility data...");self.compat_matrix.configure(state="disabled")

    def _build_failover_view(self, page):
        card=Card(page,820,244,bg=C["surface"],radius=12)
        card.pack(fill="x",pady=(0,10))
        card.create_text(16,14,anchor="nw",text="Live Failover",
                         fill=C["text"],font=("Segoe UI Semibold",11))
        card.create_text(16,39,anchor="nw",
                         text="Bounded test: tạm disable đúng 1 account, gửi 1 request nhỏ, xác minh account khác xử lý rồi restore.",
                         fill=C["text2"],font=("Segoe UI",8),width=760)
        tk.Label(card,text="Account test",bg=C["surface"],fg=C["muted"],
                 font=("Segoe UI Semibold",8)).place(x=16,y=82)
        self.failover_account_var=tk.StringVar(value="")
        self.failover_combo=ttk.Combobox(card,textvariable=self.failover_account_var,
                                         values=[],state="readonly",width=42,style="HMS.TCombobox")
        card.create_window(16,105,width=360,height=30,window=self.failover_combo,anchor="nw")
        self.request_log_btn=HoverButton(card,"REQUEST LOG: —",self.toggle_request_log_async,
                                         width=150,height=30,bg=C["surface3"],hover=C["hover"],
                                         outline=C["border"],font=("Segoe UI Semibold",8))
        card.create_window(394,105,window=self.request_log_btn,anchor="nw")
        run=HoverButton(card,"CHẠY FAILOVER TEST",self.run_failover_async,
                        width=158,height=31,bg="#245844",hover="#2f7157",
                        font=("Segoe UI Semibold",8))
        card.create_window(562,104,window=run,anchor="nw")
        self.failover_note_id=card.create_text(
            16,153,anchor="nw",text="Request Log phải ON để xác minh account được chọn từ request log.",
            fill=C["muted"],font=("Segoe UI",8),width=760
        )
        self.failover_result=tk.Text(page,bg="#111827",fg=C["text2"],relief="flat",bd=0,
                                     font=("Consolas",8),wrap="word",height=15)
        self.failover_result.pack(fill="both",expand=True)
        self.failover_result.insert("1.0","Chưa chạy failover test.")
        self.failover_result.configure(state="disabled")

    def _build_accounts(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["accounts"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x")
        heading.pack_propagate(False)
        tk.Label(
            heading, text="Account Center · Usage & Token Center v25.61 · Official Auth v25.59", bg=C["bg"], fg=C["text"],
            font=("Segoe UI Semibold", 12)
        ).pack(side="left", pady=7)

        self.add_account_btn = HoverButton(
            heading, "THÊM TÀI KHOẢN", self.add_codex_account,
            width=140, height=31, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8),
            tooltip="Mở OAuth Codex trong trình duyệt và thêm credential vào pool HMS."
        )
        self.add_account_btn.pack(side="right", pady=4)

        self.refresh_quota_btn = HoverButton(
            heading, "LÀM MỚI QUOTA", self.refresh_quota_async,
            width=132, height=31, bg=C["surface"], hover=C["surface3"],
            outline=C["border_soft"], font=("Segoe UI Semibold", 8),
            tooltip="Đọc quota trực tiếp cho toàn bộ Codex OAuth account."
        )
        self.refresh_quota_btn.pack(side="right", padx=(0, 7), pady=4)

        self.account_summary = tk.Frame(page, bg=C["bg"], height=58)
        self.account_summary.pack(fill="x", pady=(2, 8))
        self.account_summary.pack_propagate(False)
        self.account_summary_labels = {}
        for key, title in (("total","TỔNG"),("ready","READY"),("route_eligible","ROUTE OK"),("hold","HOLD"),("stale","STALE"),("favorite","FAVORITE")):
            box = tk.Frame(
                self.account_summary, bg=C["surface"],
                highlightbackground=C["border_soft"], highlightthickness=1
            )
            box.pack(side="left", fill="both", expand=True, padx=(0, 6))
            tk.Label(box, text=title, bg=C["surface"], fg=C["muted"],
                     font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(box, text="—", bg=C["surface"], fg=C["text"],
                             font=("Segoe UI Semibold", 13))
            value.pack(anchor="w", padx=10, pady=(0, 4))
            self.account_summary_labels[key] = value

        filter_bar=tk.Frame(page,bg=C["bg"],height=38)
        filter_bar.pack(fill="x",pady=(0,6));filter_bar.pack_propagate(False)
        tk.Label(filter_bar,text="HIỂN THỊ",bg=C["bg"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(side="left",pady=8)
        self.account_filter_var=tk.StringVar(value="TẤT CẢ")
        self.account_filter_combo=ttk.Combobox(filter_bar,textvariable=self.account_filter_var,
            values=["TẤT CẢ","ROUTE OK","HOLD","STALE","FAVORITE"],state="readonly",width=15,style="HMS.TCombobox")
        self.account_filter_combo.pack(side="left",padx=(8,12),pady=4)
        self.account_filter_combo.bind("<<ComboboxSelected>>",lambda _e:self._render_account_center(self._filtered_account_items()))
        tk.Label(filter_bar,text="TÌM",bg=C["bg"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(side="left",pady=8)
        self.account_search_var=tk.StringVar(value="")
        self.account_search_entry=tk.Entry(filter_bar,textvariable=self.account_search_var,bg=C["surface"],fg=C["text"],
            insertbackground=C["text"],relief="flat",font=("Segoe UI",8),width=34)
        self.account_search_entry.pack(side="left",padx=(8,12),pady=5,ipady=4)
        self.account_search_var.trace_add("write",lambda *_:self._render_account_center(self._filtered_account_items()))
        self.account_route_banner=tk.Label(filter_bar,text="ACTIVE ROUTE —",bg=C["bg"],fg=C["text2"],font=("Segoe UI Semibold",8))
        self.account_route_banner.pack(side="right",pady=8)

        self.account_center_status = tk.Label(
            page,
            text="v25.61 · Usage & Token: reset countdown + absolute time · package/OAuth lifecycle tách biệt · AFTER RESET = SCENARIO ONLY.",
            bg=C["bg"], fg=C["muted"], font=("Segoe UI", 7)
        )
        self.account_center_status.pack(anchor="w", pady=(0, 6))

        self.account_scroll = ScrollableSettings(page)
        self.account_scroll.pack(fill="both", expand=True)
        self.accounts_grid = self.account_scroll.inner

    def _build_quota_center(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["quota"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Advanced Quota Center", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.quota_sync_btn = HoverButton(
            heading, "ĐỒNG BỘ QUOTA", self.sync_quota_center_async,
            width=132, height=31, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8),
            tooltip="Ghi snapshot quota metadata vào SQLite, cập nhật freshness/reset timeline và forecast accuracy."
        )
        self.quota_sync_btn.pack(side="right", pady=4)
        HoverButton(
            heading, "DỰ BÁO", self.evaluate_predictive_quota_async,
            width=92, height=31, bg=C["surface"], hover=C["surface3"], outline=C["border_soft"],
            font=("Segoe UI Semibold", 8)
        ).pack(side="right", padx=(0,7), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.quota_summary_labels = {}
        for key, title in (("accounts","ACCOUNT"),("fresh","FRESH"),("alerts","CẢNH BÁO"),("accuracy","FORECAST ĐÃ ĐỐI CHIẾU")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="—",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12))
            val.pack(anchor="w",padx=10,pady=(1,4)); self.quota_summary_labels[key]=val

        self.quota_center_status = tk.Label(
            page, text="Quota live vẫn là dữ liệu authoritative · history/forecast chỉ là telemetry hỗ trợ routing.",
            bg=C["bg"], fg=C["muted"], font=("Segoe UI",7), anchor="w"
        )
        self.quota_center_status.pack(fill="x", pady=(0,6))
        self.quota_scroll=ScrollableSettings(page); self.quota_scroll.pack(fill="both",expand=True)
        self.quota_grid=self.quota_scroll.inner

    def _quota_sparkline(self, parent, series, width=300, height=54):
        cv=tk.Canvas(parent,width=width,height=height,bg="#111827",highlightthickness=0,bd=0)
        vals=[]
        for pt in series or []:
            try: vals.append(float(pt.get("v")))
            except Exception: pass
        # reference grid 0/50/100; scale remains quota-percent, never autoscaled to hide depletion.
        for pct in (0,50,100):
            y=height-5-(height-10)*(pct/100.0)
            cv.create_line(3,y,width-3,y,fill="#202d42",width=1)
        if len(vals)>=2:
            pts=[]
            for i,v in enumerate(vals):
                x=5+(width-10)*(i/(len(vals)-1))
                y=height-5-(height-10)*(max(0,min(100,v))/100.0)
                pts.extend([x,y])
            cv.create_line(*pts,fill=C["primary"],width=2,smooth=True)
            cv.create_oval(pts[-2]-2,pts[-1]-2,pts[-2]+2,pts[-1]+2,fill=C["primary"],outline="")
        elif len(vals)==1:
            y=height-5-(height-10)*(max(0,min(100,vals[0]))/100.0)
            cv.create_oval(width-9,y-2,width-5,y+2,fill=C["primary"],outline="")
        else:
            cv.create_text(width/2,height/2,text="chưa đủ lịch sử",fill=C["muted"],font=("Segoe UI",7))
        return cv

    def _quota_reset_text(self, obj):
        if not obj or obj.get("reset_utc") is None:
            return "đặt lại —"
        h=obj.get("reset_in_hours")
        absolute="—"
        try:
            dt=datetime.datetime.fromisoformat(str(obj.get("reset_utc")).replace("Z","+00:00")).astimezone()
            absolute=dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
        if h is None: return f"Đặt lại lúc {absolute}"
        try:
            h=float(h)
            if h < 0: return f"Đã tới hạn · {absolute}"
            if h < 1: return f"sau {max(0,h*60):.0f} phút · lúc {absolute}"
            if h < 24: return f"sau {h:.1f}h · lúc {absolute}"
            d=int(h//24); rem=int(h%24)
            return f"sau {d}d {rem}h · lúc {absolute}"
        except Exception:
            return f"Đặt lại lúc {absolute}"

    def _render_quota_center(self, report):
        for w in self.quota_grid.winfo_children(): w.destroy()
        rows=report.get("accounts") or []
        if not rows:
            tk.Label(self.quota_grid,text="Chưa có snapshot quota. Bấm ĐỒNG BỘ QUOTA hoặc chờ automation nền.",bg=C["bg"],fg=C["muted"],font=("Segoe UI",9)).pack(anchor="w",pady=16)
            return
        for row in rows:
            card=tk.Frame(self.quota_grid,bg=C["surface"],height=214,highlightbackground=C["border_soft"],highlightthickness=1)
            card.pack(fill="x",padx=(2,12),pady=6); card.pack_propagate(False)
            acct=row.get("account") or "—"
            risk=((row.get("predictive") or {}).get("risk") or "UNKNOWN")
            fresh=((row.get("freshness") or {}).get("state") or "UNKNOWN")
            color=C["danger"] if risk=="EMERGENCY" or fresh=="STALE" else (C["warning"] if risk in ("HIGH","MEDIUM") or fresh in ("AGING","UNKNOWN") else C["success"])
            tk.Label(card,text=acct,bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",10)).place(x=14,y=10)
            tk.Label(card,text=f"{risk} · SOURCE {fresh}",bg=C["surface"],fg=color,font=("Segoe UI Semibold",7)).place(relx=1,x=-14,y=13,anchor="ne")
            five=row.get("five_hour_remaining"); week=row.get("weekly_remaining")
            ftxt="—" if five is None else f"{float(five):.1f}%"
            wtxt="—" if week is None else f"{float(week):.1f}%"
            tk.Label(card,text="5 GIỜ",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=14,y=39)
            tk.Label(card,text=ftxt,bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",13)).place(x=14,y=54)
            tk.Label(card,text=self._quota_reset_text(row.get("five_hour_reset") or {}),bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=78,y=59)
            tk.Label(card,text="7 NGÀY",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=430,y=39)
            tk.Label(card,text=wtxt,bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",13)).place(x=430,y=54)
            tk.Label(card,text=self._quota_reset_text(row.get("weekly_reset") or {}),bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=494,y=59)
            h=row.get("history") or {}
            self._quota_sparkline(card,h.get("five_hour") or [],370,58).place(x=14,y=84)
            self._quota_sparkline(card,h.get("weekly") or [],370,58).place(x=430,y=84)
            acc=row.get("accuracy") or {}; a5=acc.get("five_hour") or {}; aw=acc.get("weekly") or {}
            a5t="—" if a5.get("mae_pct") is None else f"MAE {a5.get('mae_pct')}% · n={a5.get('samples',0)}"
            awt="—" if aw.get("mae_pct") is None else f"MAE {aw.get('mae_pct')}% · n={aw.get('samples',0)}"
            tk.Label(card,text=f"Forecast accuracy 5h: {a5t}",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=14,y=149)
            tk.Label(card,text=f"Forecast accuracy 7d: {awt}",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=430,y=149)
            extras=row.get("additional_windows") or []
            if extras:
                ex=[]
                for q in extras[:3]:
                    rem=q.get("remaining_pct"); remt="—" if rem is None else f"{float(rem):.0f}%"
                    ex.append(f"{str(q.get('name') or q.get('label') or 'extra')[:20]} {remt}")
                tk.Label(card,text="Extra: "+" · ".join(ex),bg=C["surface"],fg=C["accent"],font=("Segoe UI",7),anchor="w").place(x=14,y=166)
            alerts=row.get("alerts") or []
            source=row.get("freshness") or {}; age=source.get("age_seconds")
            age_text="—" if age is None else (f"{float(age)/60:.0f} phút")
            footer=f"Source: {source.get('source') or '—'} · age {age_text}"
            if alerts: footer += " · " + ", ".join(str(x) for x in alerts[:4])
            tk.Label(card,text=footer[:150],bg=C["surface"],fg=C["warning"] if alerts else C["muted"],font=("Segoe UI",7),anchor="w").place(x=14,y=182)

    def _build_usage(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["usage"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Usage Ledger", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.usage_diag_btn = HoverButton(
            heading, "GÓI CHẨN ĐOÁN", self.diagnostics_bundle_async,
            width=132, height=31, bg=C["surface"], hover=C["surface3"],
            outline=C["border_soft"], font=("Segoe UI Semibold", 8),
            tooltip="Tạo ZIP chẩn đoán đã redact; không chứa raw OAuth/request body/API key/cookie."
        )
        self.usage_diag_btn.pack(side="right", pady=4)
        self.usage_sync_btn = HoverButton(
            heading, "ĐỒNG BỘ", self.sync_usage_async,
            width=104, height=31, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8),
            tooltip="Đồng bộ request trace an toàn vào SQLite Usage Ledger."
        )
        self.usage_sync_btn.pack(side="right", padx=(0, 7), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2, 8)); summary.pack_propagate(False)
        self.usage_summary_labels = {}
        for key, title in (("day", "REQUEST 24H"), ("week", "REQUEST 7 NGÀY"),
                           ("tokens", "TOKEN 7 NGÀY"), ("success", "SUCCESS 7 NGÀY")):
            box = tk.Frame(summary, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
            box.pack(side="left", fill="both", expand=True, padx=(0, 6))
            tk.Label(box, text=title, bg=C["surface"], fg=C["muted"],
                     font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=10, pady=(7, 0))
            v = tk.Label(box, text="—", bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 12))
            v.pack(anchor="w", padx=10, pady=(1, 4)); self.usage_summary_labels[key] = v

        advisory = tk.Frame(page, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1, height=118)
        advisory.pack(fill="x", pady=(0, 8)); advisory.pack_propagate(False)
        tk.Label(advisory, text="MODEL/REASONING + IDENTITY + CLOSED-LOOP v25.37", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI Semibold", 7)).place(x=12, y=9)
        self.usage_advisory = tk.Label(advisory, text="Đang chờ đánh giá pool", bg=C["surface"], fg=C["text"],
                                       font=("Segoe UI Semibold", 9), anchor="w")
        self.usage_advisory.place(x=12, y=29, relwidth=.58)
        self.adaptive_eval_btn = HoverButton(advisory, "ĐÁNH GIÁ", self.evaluate_closed_loop_async,
                                              width=92, height=29, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7))
        self.adaptive_eval_btn.place(relx=.62, y=26)
        self.adaptive_apply_btn = HoverButton(advisory, "ÁP DỤNG", self.apply_closed_loop_async,
                                               width=86, height=29, bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 7))
        self.adaptive_apply_btn.place(relx=.75, y=26)
        self.adaptive_rollback_btn = HoverButton(advisory, "HOÀN TÁC", self.rollback_closed_loop_async,
                                                  width=92, height=29, bg="#5a3a42", hover="#70464f", outline=C["border"], font=("Segoe UI Semibold", 7))
        self.adaptive_rollback_btn.place(relx=.87, y=26)
        self.circuit_summary = tk.Label(advisory, text="CIRCUIT · đang chờ trạng thái", bg=C["surface"], fg=C["muted"],
                                        font=("Segoe UI", 7), anchor="w")
        self.circuit_summary.place(x=12, y=58, relwidth=.70)
        self.predictive_eval_btn = HoverButton(advisory, "DỰ BÁO", self.evaluate_predictive_quota_async,
                                               width=88, height=25, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7))
        self.predictive_eval_btn.place(relx=.82, y=55)
        self.predictive_summary = tk.Label(advisory, text="PREDICTIVE · đang chờ quota history", bg=C["surface"], fg=C["muted"],
                                           font=("Segoe UI", 7), anchor="w")
        self.predictive_summary.place(x=12, y=82, relwidth=.94)
        self.usage_status = tk.Label(page, text="Ledger chỉ lưu metadata Router đã chuẩn hoá; không lưu prompt/body/secret.",
                                     bg=C["bg"], fg=C["muted"], font=("Segoe UI", 7), anchor="w")
        self.usage_status.pack(fill="x", pady=(0, 6))

        split = tk.Frame(page, bg=C["bg"], height=178)
        split.pack(fill="x", pady=(0, 7)); split.pack_propagate(False)
        left = tk.Frame(split, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        right = tk.Frame(split, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
        right.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(left, text="THEO ACCOUNT · 7 NGÀY", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=10, pady=(8, 3))
        tk.Label(right, text="THEO MODEL · 7 NGÀY", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=10, pady=(8, 3))
        self.usage_accounts_text = tk.Text(left, bg="#111827", fg=C["text2"], relief="flat", bd=0,
                                           font=("Consolas", 7), wrap="none", height=10)
        self.usage_accounts_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.usage_models_text = tk.Text(right, bg="#111827", fg=C["text2"], relief="flat", bd=0,
                                         font=("Consolas", 7), wrap="none", height=10)
        self.usage_models_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.usage_accounts_text.configure(state="disabled"); self.usage_models_text.configure(state="disabled")

        recent = tk.Frame(page, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
        recent.pack(fill="both", expand=True)
        tk.Label(recent, text="REQUEST GẦN NHẤT · METADATA AN TOÀN", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=10, pady=(8, 3))
        self.usage_recent_text = tk.Text(recent, bg="#111827", fg=C["text2"], relief="flat", bd=0,
                                         font=("Consolas", 7), wrap="none", height=8)
        self.usage_recent_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.usage_recent_text.configure(state="disabled")

    def _build_account_analytics(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["analytics"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Account Analytics", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.analytics_sync_btn = HoverButton(
            heading, "PHÂN TÍCH", self.sync_account_analytics_async,
            width=112, height=31, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8),
            tooltip="Cập nhật quality score từ Usage Ledger + quota + circuit + predictive. Không đọc prompt/body/secret."
        )
        self.analytics_sync_btn.pack(side="right", pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2, 8)); summary.pack_propagate(False)
        self.analytics_summary_labels = {}
        for key, title in (("accounts","ACCOUNT"),("healthy","KHỎE"),("attention","CẦN CHÚ Ý"),("best","BEST SCORE")):
            box = tk.Frame(summary, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
            box.pack(side="left", fill="both", expand=True, padx=(0, 6))
            tk.Label(box, text=title, bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold",7)).pack(anchor="w", padx=10, pady=(7,0))
            val = tk.Label(box, text="—", bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold",12))
            val.pack(anchor="w", padx=10, pady=(1,4)); self.analytics_summary_labels[key]=val

        self.analytics_status = tk.Label(
            page, text="Quality score là telemetry có confidence; Closed-loop chỉ nhận bounded signal ±8 điểm.",
            bg=C["bg"], fg=C["muted"], font=("Segoe UI",7), anchor="w")
        self.analytics_status.pack(fill="x", pady=(0,6))

        accounts = tk.Frame(page, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1, height=218)
        accounts.pack(fill="x", pady=(0,8)); accounts.pack_propagate(False)
        tk.Label(accounts, text="ACCOUNT QUALITY · 7 NGÀY + LIVE PRESSURE", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI Semibold",7)).pack(anchor="w", padx=10, pady=(8,3))
        self.analytics_accounts_text = tk.Text(accounts, bg="#111827", fg=C["text2"], relief="flat", bd=0,
                                               font=("Consolas",7), wrap="none", height=12)
        self.analytics_accounts_text.pack(fill="both", expand=True, padx=8, pady=(0,8)); self.analytics_accounts_text.configure(state="disabled")

        split = tk.Frame(page, bg=C["bg"])
        split.pack(fill="both", expand=True)
        left = tk.Frame(split, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0,4))
        right = tk.Frame(split, bg=C["surface"], highlightbackground=C["border_soft"], highlightthickness=1)
        right.pack(side="left", fill="both", expand=True, padx=(4,0))
        tk.Label(left, text="ACCOUNT × MODEL · TOP QUALITY", bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold",7)).pack(anchor="w", padx=10, pady=(8,3))
        tk.Label(right, text="ACCOUNT × WORKLOAD", bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold",7)).pack(anchor="w", padx=10, pady=(8,3))
        self.analytics_models_text = tk.Text(left, bg="#111827", fg=C["text2"], relief="flat", bd=0, font=("Consolas",7), wrap="none", height=10)
        self.analytics_models_text.pack(fill="both", expand=True, padx=8, pady=(0,8)); self.analytics_models_text.configure(state="disabled")
        self.analytics_workloads_text = tk.Text(right, bg="#111827", fg=C["text2"], relief="flat", bd=0, font=("Consolas",7), wrap="none", height=10)
        self.analytics_workloads_text.pack(fill="both", expand=True, padx=8, pady=(0,8)); self.analytics_workloads_text.configure(state="disabled")

    def load_account_analytics_async(self):
        if hasattr(self,"analytics_status"):
            self.analytics_status.configure(text="Đang đọc Account Analytics...", fg=C["muted"])
        def worker():
            data=self.backend("get_account_analytics",70)
            self.root.after(0,lambda:self._apply_account_analytics(data))
        threading.Thread(target=worker,daemon=True).start()

    def sync_account_analytics_async(self):
        if self.busy: return
        self.busy=True
        if hasattr(self,"analytics_sync_btn"): self.analytics_sync_btn.set_enabled(False)
        if hasattr(self,"analytics_status"): self.analytics_status.configure(text="Đang tổng hợp Usage + quota + circuit + predictive...",fg=C["warning"])
        def worker():
            data=self.backend("sync_account_analytics",120)
            self.root.after(0,lambda:self._finish_account_analytics(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_account_analytics(self,data):
        self.busy=False
        if hasattr(self,"analytics_sync_btn"): self.analytics_sync_btn.set_enabled(True)
        self._apply_account_analytics(data)
        self.toast(data.get("message","Account Analytics đã cập nhật.") if data.get("ok") else data.get("error","Account Analytics lỗi."), "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(180,self.load_closed_loop_async)

    def _apply_account_analytics(self,data):
        self.account_analytics_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"analytics_status"): self.analytics_status.configure(text=data.get("error","Không đọc được Account Analytics."),fg=C["danger"])
            return
        aa=data.get("account_analytics") or {}
        payload=aa.get("data") if isinstance(aa.get("data"),dict) else aa
        summary=(payload or {}).get("summary") or {}
        if hasattr(self,"analytics_summary_labels"):
            self.analytics_summary_labels["accounts"].configure(text=str(summary.get("accounts",0)))
            self.analytics_summary_labels["healthy"].configure(text=str(summary.get("healthy",0)),fg=C["success"] if summary.get("healthy") else C["text"])
            self.analytics_summary_labels["attention"].configure(text=str(summary.get("attention",0)),fg=C["warning"] if summary.get("attention") else C["text"])
            self.analytics_summary_labels["best"].configure(text=f"{float(summary.get('best_score',0) or 0):.1f}")
        generated=str((payload or {}).get("generated_utc") or "—")[:19].replace("T"," ")
        best=summary.get("best_account") or "—"
        if hasattr(self,"analytics_status"):
            self.analytics_status.configure(text=f"Best: {best} · {summary.get('model_profiles',0)} model profile · cập nhật {generated} · bounded Router signal",fg=C["text2"])
        lines=["ACCOUNT                         SCORE GRADE       CONF      REQ7   OK%    P95  RETRY 429 CIRCUIT  Q%   RISK TREND"]
        for x in (payload or {}).get("accounts",[])[:30]:
            q=x.get("quota_floor_pct"); qtxt="—" if q is None else f"{float(q):.0f}"
            trend=(x.get("trend") or {}).get("direction") or "—"
            lines.append(f"{str(x.get('account','—'))[:30]:30} {float(x.get('quality_score',0)):5.1f} {str(x.get('grade',''))[:11]:11} {str(x.get('confidence',''))[:9]:9} {int(x.get('requests_7d',0)):5d} {float(x.get('success_rate_7d',0)):6.1f} {float(x.get('latency_p95_7d',0)):6.0f} {float(x.get('retry_rate_7d',0)):5.1f} {int(x.get('http_429_7d',0)):3d} {str(x.get('circuit_state',''))[:8]:8} {qtxt:>3} {str(x.get('predictive_risk',''))[:7]:7} {trend:6}")
        mlines=["ACCOUNT                    MODEL                    SCORE REQ   OK%    P95 CONF"]
        for x in (payload or {}).get("model_profiles",[])[:24]:
            mlines.append(f"{str(x.get('account','—'))[:25]:25} {str(x.get('model','—'))[:24]:24} {float(x.get('quality_score',0)):5.1f} {int(x.get('requests',0)):4d} {float(x.get('success_rate_pct',0)):6.1f} {float(x.get('latency_p95_ms',0)):6.0f} {str(x.get('confidence',''))[:6]:6}")
        wlines=["ACCOUNT                    WORKLOAD        SCORE REQ   OK%    P95 RETRY"]
        for x in (payload or {}).get("workload_profiles",[])[:24]:
            wlines.append(f"{str(x.get('account','—'))[:25]:25} {str(x.get('request_type','—'))[:14]:14} {float(x.get('quality_score',0)):5.1f} {int(x.get('requests',0)):4d} {float(x.get('success_rate_pct',0)):6.1f} {float(x.get('latency_p95_ms',0)):6.0f} {float(x.get('retry_rate_pct',0)):5.1f}")
        self._set_text_readonly(self.analytics_accounts_text,"\n".join(lines))
        self._set_text_readonly(self.analytics_models_text,"\n".join(mlines))
        self._set_text_readonly(self.analytics_workloads_text,"\n".join(wlines))

    def load_model_manager_async(self):
        if hasattr(self,"model_status"): self.model_status.configure(text="Đang đọc model catalog + project policies...",fg=C["muted"])
        def worker():
            data=self.backend("get_model_manager",90);self.root.after(0,lambda:self._apply_model_manager(data))
        threading.Thread(target=worker,daemon=True).start()

    def discover_models_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"model_scan_btn"):self.model_scan_btn.set_enabled(False)
        if hasattr(self,"model_status"):self.model_status.configure(text="Đang quét /v1/models từ Router đang online...",fg=C["warning"])
        def worker():
            data=self.backend("discover_models",90);self.root.after(0,lambda:self._finish_model_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_model_action(self,data):
        self.busy=False
        if hasattr(self,"model_scan_btn"):self.model_scan_btn.set_enabled(True)
        self._apply_model_manager(data)
        self.toast(data.get("message","Model Manager đã cập nhật.") if data.get("ok") else data.get("error","Model Manager lỗi."),"success" if data.get("ok") else "danger")

    def _model_payload(self):
        display=self.model_project_var.get().strip();project=display.split("  ·  ",1)[0].strip() if display else ""
        return {"project_dir":project,"model":self.model_var.get().strip(),"reasoning":self.reasoning_var.get().strip(),"profile":self.model_profile_var.get().strip()}

    def save_model_policy_async(self):
        if self.busy:return
        payload=self._model_payload()
        if not payload["project_dir"] or not payload["model"]:
            self.toast("Chọn project và model trước.","warning");return
        self.busy=True;self.model_status.configure(text="Đang lưu project model policy...",fg=C["warning"])
        def worker():
            data=self.backend("save_model_policy",75,payload=payload);self.root.after(0,lambda:self._finish_model_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def apply_model_policy_async(self):
        if self.busy:return
        payload=self._model_payload()
        if not payload["project_dir"]:
            self.toast("Chọn project trước.","warning");return
        self.busy=True;self.model_status.configure(text="Đang áp dụng vào isolated Codex config...",fg=C["warning"])
        def worker():
            data=self.backend("apply_model_policy",90,payload={"project_dir":payload["project_dir"]});self.root.after(0,lambda:self._finish_model_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def _select_model_project(self):
        display=self.model_project_var.get().strip();project=display.split("  ·  ",1)[0].strip() if display else ""
        mm=(self.model_manager_data or {}).get("model_manager") or {}
        for row in mm.get("projects",[]) or []:
            if str(row.get("project_dir") or "")==project:
                if row.get("model"):self.model_var.set(str(row.get("model")))
                self.reasoning_var.set(str(row.get("reasoning") or "medium"));self.model_profile_var.set(str(row.get("profile") or "BALANCED"));break

    def _apply_model_manager(self,data):
        self.model_manager_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"model_status"):self.model_status.configure(text=data.get("error","Không đọc được Model Manager."),fg=C["danger"])
            return
        mm=data.get("model_manager") or {};summary=mm.get("summary") or {};models=mm.get("models") or [];projects=mm.get("projects") or []
        if hasattr(self,"model_summary_labels"):
            self.model_summary_labels["models"].configure(text=str(summary.get("models",0)))
            self.model_summary_labels["projects"].configure(text=str(summary.get("projects",0)))
            self.model_summary_labels["configured"].configure(text=str(summary.get("configured_projects",0)))
            self.model_summary_labels["live"].configure(text="YES" if summary.get("live_catalog") else "NO",fg=C["success"] if summary.get("live_catalog") else C["warning"])
        project_values=[f"{str(x.get('project_dir',''))}  ·  {str(x.get('instance_id',''))}" for x in projects]
        model_values=[str(x.get("id")) for x in models]
        if hasattr(self,"model_project_combo"):self.model_project_combo.configure(values=project_values)
        if hasattr(self,"model_combo"):self.model_combo.configure(values=model_values)
        if project_values and self.model_project_var.get() not in project_values:self.model_project_var.set(project_values[0]);self._select_model_project()
        plines=["PROJECT                               MODEL                     REASON  PROFILE   INSTANCE"]
        for x in projects[:30]:
            plines.append(f"{str(x.get('name') or x.get('project_dir',''))[:36]:36} {str(x.get('model') or '—')[:25]:25} {str(x.get('reasoning') or '—')[:7]:7} {str(x.get('profile') or '')[:9]:9} {str(x.get('instance_id') or '')[:10]}")
        mlines=["MODEL                           REASONING                  ANALYTICS BEST"]
        for x in models[:40]:
            efforts=','.join(x.get('reasoning_efforts') or [])
            rec=str(x.get('recommended_account') or '—')
            mlines.append(f"{str(x.get('id',''))[:31]:31} {efforts[:27]:27} {rec[:28]}")
        self._set_text_readonly(self.model_projects_text,"\n".join(plines));self._set_text_readonly(self.model_catalog_text,"\n".join(mlines))
        self.model_status.configure(text=f"{summary.get('models',0)} model · {summary.get('configured_projects',0)}/{summary.get('projects',0)} project configured · stable endpoint/provider bất biến",fg=C["text2"])

    def _build_model_manager(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["modelmgr"] = page
        heading=tk.Frame(page,bg=C["bg"],height=44);heading.pack(fill="x");heading.pack_propagate(False)
        tk.Label(heading,text="Codex Model & Reasoning Manager",bg=C["bg"],fg=C["text"],font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        self.model_scan_btn=HoverButton(heading,"QUÉT MODELS",self.discover_models_async,width=112,height=31,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",8),tooltip="Đọc /v1/models từ Router đang online; không đọc OAuth/API key vào state.")
        self.model_scan_btn.pack(side="right",pady=4)
        summary=tk.Frame(page,bg=C["bg"],height=62);summary.pack(fill="x",pady=(2,8));summary.pack_propagate(False)
        self.model_summary_labels={}
        for key,title in (("models","MODELS"),("projects","PROJECTS"),("configured","ĐÃ GÁN"),("live","LIVE CATALOG")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="—",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12));val.pack(anchor="w",padx=10,pady=(1,4));self.model_summary_labels[key]=val
        editor=Card(page,820,154,bg=C["surface"],radius=12);editor.pack(fill="x",pady=(0,8))
        editor.create_text(14,12,anchor="nw",text="PROJECT MODEL POLICY",fill=C["muted"],font=("Segoe UI Semibold",7))
        self.model_project_var=tk.StringVar();self.model_var=tk.StringVar();self.reasoning_var=tk.StringVar(value="medium");self.model_profile_var=tk.StringVar(value="BALANCED")
        self.model_project_combo=ttk.Combobox(editor,textvariable=self.model_project_var,state="readonly",style="HMS.TCombobox")
        self.model_combo=ttk.Combobox(editor,textvariable=self.model_var,state="readonly",style="HMS.TCombobox")
        self.reasoning_combo=ttk.Combobox(editor,textvariable=self.reasoning_var,state="readonly",values=["auto","none","low","medium","high","xhigh","max"],style="HMS.TCombobox")
        self.model_profile_combo=ttk.Combobox(editor,textvariable=self.model_profile_var,state="readonly",values=["BALANCED","FAST","DEEP","REVIEW","TEST"],style="HMS.TCombobox")
        editor.create_text(14,38,anchor="nw",text="Project",fill=C["muted"],font=("Segoe UI",7));editor.create_window(14,56,width=310,height=29,window=self.model_project_combo,anchor="nw")
        editor.create_text(338,38,anchor="nw",text="Model",fill=C["muted"],font=("Segoe UI",7));editor.create_window(338,56,width=250,height=29,window=self.model_combo,anchor="nw")
        editor.create_text(602,38,anchor="nw",text="Reasoning",fill=C["muted"],font=("Segoe UI",7));editor.create_window(602,56,width=96,height=29,window=self.reasoning_combo,anchor="nw")
        editor.create_text(710,38,anchor="nw",text="Profile",fill=C["muted"],font=("Segoe UI",7));editor.create_window(710,56,width=96,height=29,window=self.model_profile_combo,anchor="nw")
        save=HoverButton(editor,"LƯU POLICY",self.save_model_policy_async,width=106,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7));editor.create_window(14,103,window=save,anchor="nw")
        apply=HoverButton(editor,"ÁP DỤNG",self.apply_model_policy_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7));editor.create_window(130,103,window=apply,anchor="nw")
        editor.create_text(242,110,anchor="nw",text="Apply chỉ sửa model/model_reasoning_effort trong isolated config.toml; provider + stable endpoint giữ nguyên.",fill=C["text2"],font=("Segoe UI",7),width=550)
        self.model_project_combo.bind("<<ComboboxSelected>>",lambda e:self._select_model_project())
        self.model_status=tk.Label(page,text="Model capability matrix là conservative; runtime acceptance của Codex vẫn authoritative.",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w");self.model_status.pack(fill="x",pady=(0,6))
        split=tk.Frame(page,bg=C["bg"]);split.pack(fill="both",expand=True)
        left=tk.Frame(split,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);left.pack(side="left",fill="both",expand=True,padx=(0,4))
        right=tk.Frame(split,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);right.pack(side="left",fill="both",expand=True,padx=(4,0))
        tk.Label(left,text="PROJECT POLICIES",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        tk.Label(right,text="LIVE MODEL CATALOG",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.model_projects_text=tk.Text(left,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",7),wrap="none",height=12);self.model_projects_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.model_projects_text.configure(state="disabled")
        self.model_catalog_text=tk.Text(right,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",7),wrap="none",height=12);self.model_catalog_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.model_catalog_text.configure(state="disabled")

    def _smart_model_payload(self):
        project = self.smart_project_var.get().strip() if hasattr(self, "smart_project_var") else ""
        role = self.smart_role_var.get().strip() if hasattr(self, "smart_role_var") else ""
        if project == "TẤT CẢ":
            project = ""
        if role == "TẤT CẢ":
            role = ""
        return {"project_dir": project, "role": role}

    def load_smart_model_router_async(self):
        if hasattr(self, "smart_status"):
            self.smart_status.configure(text="Đang đọc recommendation + sticky guards...", fg=C["muted"])
        def worker():
            data = self.backend("get_smart_model_router", 120)
            self.root.after(0, lambda: self._apply_smart_model_router(data))
        threading.Thread(target=worker, daemon=True).start()

    def smart_model_action_async(self, action):
        if self.busy:
            return
        payload = self._smart_model_payload()
        if action == "apply_smart_model_router":
            if not messagebox.askyesno(
                "Áp dụng Smart Model Router",
                "Chỉ các managed Codex instance đang DỪNG và đủ hard gate mới được đổi model/reasoning.\n\n"
                "Session đang chạy giữ sticky model/account. Account affinity chỉ là tín hiệu bounded cho Closed-loop.\n\nTiếp tục?"
            ):
                return
        if action == "rollback_smart_model_router":
            if not messagebox.askyesno("Rollback Smart Router", "Khôi phục model policy/config từ snapshot Smart Router gần nhất?\n\nCredential và stable endpoint không bị thay đổi."):
                return
        self.busy = True
        if hasattr(self, "smart_status"):
            self.smart_status.configure(text="Đang xử lý Smart Model Router...", fg=C["warning"])
        def worker():
            data = self.backend(action, 150, payload=payload if action != "rollback_smart_model_router" else None)
            self.root.after(0, lambda: self._finish_smart_model_action(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_smart_model_action(self, data):
        self.busy = False
        self._apply_smart_model_router(data)
        self.toast(data.get("message", "Smart Model Router đã cập nhật.") if data.get("ok") else data.get("error", "Smart Model Router lỗi."), "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(300, self.load_smart_model_router_async)

    def _apply_smart_model_router(self, data):
        self.smart_model_router_data = data or {}
        if not data.get("ok"):
            if hasattr(self, "smart_status"):
                self.smart_status.configure(text=data.get("error", "Không đọc được Smart Model Router."), fg=C["danger"])
            return
        d = data.get("smart_model_router") or {}
        # status returns state; evaluate/apply returns plan directly.
        plan = d.get("plan") if isinstance(d.get("plan"), dict) else d.get("last_plan") if isinstance(d.get("last_plan"), dict) else {}
        summary = (plan or {}).get("summary") or d.get("summary") or {}
        recs = (plan or {}).get("recommendations") or []
        mode = str(data.get("mode") or (plan or {}).get("mode") or "OBSERVE")
        if hasattr(self, "smart_summary_labels"):
            vals = {
                "scopes": summary.get("scopes", 0),
                "models": summary.get("live_models", 0),
                "ready": summary.get("apply_ready", 0),
                "sticky": summary.get("sticky_guarded", 0),
                "blocked": summary.get("blocked", 0),
            }
            for k, v in vals.items():
                fg = C["danger"] if k == "blocked" and int(v or 0) else C["warning"] if k == "sticky" and int(v or 0) else C["success"] if k == "ready" and int(v or 0) else C["text"]
                self.smart_summary_labels[k].configure(text=str(v), fg=fg)
        projects = ["TẤT CẢ"] + sorted({str(x.get("project_dir") or "") for x in recs if x.get("project_dir")})
        if hasattr(self, "smart_project_combo"):
            self.smart_project_combo.configure(values=projects)
            if self.smart_project_var.get() not in projects:
                self.smart_project_var.set("TẤT CẢ")
        lines = ["PROJECT                         ROLE      STATUS        CURRENT MODEL          → RECOMMENDED              REASON    ACCOUNT                    SCORE Δ   CONF"]
        for x in recs[:80]:
            project = Path(str(x.get("project_dir") or "")).name or str(x.get("project_dir") or "—")
            cur = str(x.get("current_model") or "—")
            rec = str(x.get("recommended_model") or "—")
            reasoning = str(x.get("recommended_reasoning") or "—")
            acc = str(x.get("recommended_account") or "—")
            lines.append(f"{project[:30]:30} {str(x.get('team_role','SOLO'))[:9]:9} {str(x.get('status',''))[:13]:13} {cur[:22]:22} → {rec[:24]:24} {reasoning[:8]:8} {acc[:26]:26} {float(x.get('recommended_score',0) or 0):5.1f} {float(x.get('score_delta',0) or 0):5.1f} {str(x.get('confidence',''))[:8]}")
            blockers = x.get("blockers") or []
            if blockers:
                lines.append("    BLOCK: " + ", ".join(map(str, blockers)))
        if hasattr(self, "smart_recommendations_text"):
            self._set_text_readonly(self.smart_recommendations_text, "\n".join(lines))
        if hasattr(self, "smart_status"):
            self.smart_status.configure(
                text=f"Mode {mode} · {summary.get('scopes',0)} scope · {summary.get('apply_ready',0)} apply-ready · {summary.get('sticky_guarded',0)} sticky guard · account signal bounded ≤8",
                fg=C["warning"] if str(mode).upper() == "OBSERVE" else C["success"]
            )

    def _build_smart_model_router(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["smartmodel"] = page
        heading = tk.Frame(page, bg=C["bg"], height=44); heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Codex Smart Model Router", bg=C["bg"], fg=C["text"], font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        HoverButton(heading, "LÀM MỚI", self.load_smart_model_router_async, width=96, height=31, bg=C["surface"], hover=C["surface3"], outline=C["border_soft"], font=("Segoe UI Semibold", 8)).pack(side="right", pady=4)
        summary = tk.Frame(page, bg=C["bg"], height=62); summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.smart_summary_labels = {}
        for key, title in (("scopes","SCOPES"),("models","LIVE MODELS"),("ready","APPLY READY"),("sticky","STICKY GUARD"),("blocked","BLOCKED")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(side="left",fill="both",expand=True,padx=(0,5))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=9,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12));val.pack(anchor="w",padx=9,pady=(1,4));self.smart_summary_labels[key]=val
        control=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=105);control.pack(fill="x",pady=(0,8));control.pack_propagate(False)
        self.smart_project_var=tk.StringVar(value="TẤT CẢ");self.smart_role_var=tk.StringVar(value="TẤT CẢ")
        self.smart_project_combo=ttk.Combobox(control,textvariable=self.smart_project_var,state="readonly",values=["TẤT CẢ"],style="HMS.TCombobox");self.smart_project_combo.place(x=12,y=31,width=360,height=29)
        ttk.Combobox(control,textvariable=self.smart_role_var,state="readonly",values=["TẤT CẢ","CODER","REVIEWER","TESTER","SOLO"],style="HMS.TCombobox").place(x=382,y=31,width=125,height=29)
        tk.Label(control,text="Project / Role scope",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=12,y=9)
        HoverButton(control,"ĐÁNH GIÁ",lambda:self.smart_model_action_async("evaluate_smart_model_router"),width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=520,y=31)
        HoverButton(control,"ÁP DỤNG",lambda:self.smart_model_action_async("apply_smart_model_router"),width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=626,y=31)
        HoverButton(control,"HOÀN TÁC",lambda:self.smart_model_action_async("rollback_smart_model_router"),width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=732,y=31)
        tk.Label(control,text="Không hot-switch client đang chạy. Account affinity chỉ là bounded signal cho Closed-loop; Circuit/Quota/Identity/Security vẫn authoritative.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w").place(x=12,y=70,width=815,height=20)
        self.smart_status=tk.Label(page,text="Smart Model Router v25.44 · OBSERVE mặc định · Windows runtime deferred",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w");self.smart_status.pack(fill="x",pady=(0,5))
        box=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(fill="both",expand=True)
        tk.Label(box,text="RECOMMENDATIONS · PROJECT + ROLE + WORKLOAD → MODEL / REASONING / ACCOUNT SIGNAL",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.smart_recommendations_text=tk.Text(box,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",7),wrap="none",height=18);self.smart_recommendations_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.smart_recommendations_text.configure(state="disabled")

    def _build_lan_pool(self):
        page=tk.Frame(self.content,bg=C["bg"]);self.pages["lanpool"]=page
        heading=tk.Frame(page,bg=C["bg"],height=44);heading.pack(fill="x");heading.pack_propagate(False)
        tk.Label(heading,text="Cross-PC / LAN Codex Pool",bg=C["bg"],fg=C["text"],font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        HoverButton(heading,"HEARTBEAT",self.heartbeat_lan_pool_async,width=104,height=31,bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],font=("Segoe UI Semibold",8)).pack(side="right",pady=4)
        HoverButton(heading,"LÀM MỚI",self.load_lan_pool_async,width=96,height=31,bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],font=("Segoe UI Semibold",8)).pack(side="right",padx=(0,8),pady=4)
        pair=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=102);pair.pack(fill="x",pady=(2,8));pair.pack_propagate(False)
        tk.Label(pair,text="PAIR NODE · shared SMB/NAS metadata only",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=8)
        self.lan_shared_var=tk.StringVar();self.lan_pair_var=tk.StringVar();self.lan_node_var=tk.StringVar(value=os.environ.get("COMPUTERNAME", ""))
        tk.Entry(pair,textvariable=self.lan_shared_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=12,y=31,width=330,height=28)
        tk.Label(pair,text="Shared path",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=14,y=62)
        tk.Entry(pair,textvariable=self.lan_node_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=352,y=31,width=150,height=28)
        tk.Label(pair,text="Node name",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=354,y=62)
        tk.Entry(pair,textvariable=self.lan_pair_var,show="•",bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=512,y=31,width=185,height=28)
        tk.Label(pair,text="Pairing code ≥16 ký tự · không ghi vào share",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=514,y=62)
        HoverButton(pair,"PAIR",self.pair_lan_pool_async,width=92,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",8)).place(x=707,y=31)
        summary=tk.Frame(page,bg=C["bg"],height=62);summary.pack(fill="x",pady=(0,8));summary.pack_propagate(False)
        self.lan_summary_labels={}
        for key,title in (("nodes","NODES"),("online","ONLINE"),("leases","LEASES"),("invalid_signatures","SIGNATURE ERR")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            v=tk.Label(box,text="—",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12));v.pack(anchor="w",padx=10,pady=(1,4));self.lan_summary_labels[key]=v
        self.lan_status=tk.Label(page,text="LAN Pool chưa pair · raw Codex credentials không bao giờ được ghi vào share.",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w");self.lan_status.pack(fill="x",pady=(0,5))
        soak=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);soak.pack(fill="x",pady=(0,8));soak.pack_propagate(False)
        tk.Label(soak,text="RELIABILITY / SOAK v25.47",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.lan_soak_status=tk.Label(soak,text="Chưa có soak run · 6h/24h chỉ PASS khi có Router + ≥2 instance + shared LAN.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.lan_soak_status.place(x=10,y=28,width=465)
        HoverButton(soak,"SMOKE",lambda:self.start_reliability_soak_async("smoke"),width=68,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=490,y=15)
        HoverButton(soak,"6H",lambda:self.start_reliability_soak_async("6h"),width=58,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=564,y=15)
        HoverButton(soak,"24H",lambda:self.start_reliability_soak_async("24h"),width=58,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=628,y=15)
        HoverButton(soak,"TIẾP TỤC",self.resume_reliability_soak_async,width=82,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=692,y=15)
        HoverButton(soak,"DỪNG",self.stop_reliability_soak_async,width=62,height=29,bg=C["surface3"],hover=C["danger"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=780,y=15)
        perf=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);perf.pack(fill="x",pady=(0,8));perf.pack_propagate(False)
        tk.Label(perf,text="PERFORMANCE / SCALE v25.48",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.lan_perf_status=tk.Label(perf,text="Chưa benchmark · đo control-plane TTFB/latency, throughput, backpressure, reconnect storm và LAN contention.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.lan_perf_status.place(x=10,y=28,width=700)
        HoverButton(perf,"BENCHMARK",self.start_performance_scale_async,width=112,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        cert=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=72);cert.pack(fill="x",pady=(0,8));cert.pack_propagate(False)
        tk.Label(cert,text="REAL CODEX CERTIFICATION v25.49",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.real_cert_status=tk.Label(cert,text="Chưa kiểm tra · KIỂM TRA không tốn quota; LIVE 1 gửi đúng 1 request thật sau xác nhận.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.real_cert_status.place(x=10,y=28,width=490)
        self.real_cert_model_var=tk.StringVar(value="")
        tk.Entry(cert,textvariable=self.real_cert_model_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",7)).place(x=505,y=14,width=125,height=27)
        tk.Label(cert,text="model cho LIVE 1",bg=C["surface"],fg=C["muted"],font=("Segoe UI",6)).place(x=507,y=44)
        HoverButton(cert,"KIỂM TRA",self.start_real_codex_cert_async,width=92,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=638,y=14)
        HoverButton(cert,"LIVE 1",self.start_real_codex_live_cert_async,width=92,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=738,y=14)
        rotation=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);rotation.pack(fill="x",pady=(0,8));rotation.pack_propagate(False)
        tk.Label(rotation,text="ROTATION TORTURE v25.51",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.rotation_torture_status=tk.Label(rotation,text="Chưa chạy · synthetic 1000 cycle · quota depletion / 429 / stale recovery / auth isolation / LAN rejoin.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.rotation_torture_status.place(x=10,y=28,width=690)
        HoverButton(rotation,"ROTATION TEST",self.start_rotation_torture_async,width=126,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=710,y=15)
        simulation=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);simulation.pack(fill="x",pady=(0,8));simulation.pack_propagate(False)
        tk.Label(simulation,text="PRODUCTION SIMULATION LAB v25.54",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.production_sim_status=tk.Label(simulation,text="Chưa chạy · digital twin synthetic-only · 8 seed / quota+429+crash+auth+SMB+LAN+clock-skew / deterministic replay.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.production_sim_status.place(x=10,y=28,width=590)
        HoverButton(simulation,"SIM LAB",lambda:self.start_production_simulation_async(False),width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(simulation,"REPLAY",lambda:self.start_production_simulation_async(True),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        twin=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);twin.pack(fill="x",pady=(0,8));twin.pack_propagate(False)
        tk.Label(twin,text="AUTONOMOUS ROUTER DIGITAL TWIN v25.55",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.router_twin_status=tk.Label(twin,text="Chưa chạy · 32 account / 12 instance / 24 project · dynamic weights · model check 3,072 states · trace minimization.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.router_twin_status.place(x=10,y=28,width=590)
        HoverButton(twin,"TWIN RUN",lambda:self.start_autonomous_router_twin_async(False),width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(twin,"MODEL CHECK",lambda:self.start_autonomous_router_twin_async(True),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        chaos=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);chaos.pack(fill="x",pady=(0,8));chaos.pack_propagate(False)
        tk.Label(chaos,text="PROTOCOL CHAOS / API FUZZ v25.56",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.protocol_chaos_status=tk.Label(chaos,text="Chưa chạy · 300 deterministic fuzz case · SSE/WS/JSON/chunked/retry/early-EOF · synthetic-only.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.protocol_chaos_status.place(x=10,y=28,width=590)
        HoverButton(chaos,"FUZZ 300",self.start_protocol_chaos_async,width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(chaos,"MỞ EVIDENCE",self.open_protocol_chaos_evidence,width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        recovery=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);recovery.pack(fill="x",pady=(0,8));recovery.pack_propagate(False)
        tk.Label(recovery,text="RECOVERY PLANNER / SELF-HEALING PROOF v25.57",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.recovery_planner_status=tk.Label(recovery,text="Chưa chạy · cause-aware recovery · bounded restart/retry · loop breaker · rollback proof · model check 9,216 states.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.recovery_planner_status.place(x=10,y=28,width=590)
        HoverButton(recovery,"PROOF",lambda:self.start_recovery_planner_async(False),width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(recovery,"MODEL CHECK",lambda:self.start_recovery_planner_async(True),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        compound=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);compound.pack(fill="x",pady=(0,8));compound.pack_propagate(False)
        tk.Label(compound,text="COMPOUND-FAULT CONVERGENCE v25.58",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.compound_fault_status=tk.Label(compound,text="Chưa chạy · recovery DAG + global budget · quota/process/config/LAN compound faults · 72k+ state model check.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.compound_fault_status.place(x=10,y=28,width=590)
        HoverButton(compound,"CONVERGENCE",lambda:self.start_compound_fault_recovery_async(False),width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(compound,"MODEL 72K",lambda:self.start_compound_fault_recovery_async(True),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        journal=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);journal.pack(fill="x",pady=(0,8));journal.pack_propagate(False)
        tk.Label(journal,text="RECOVERY TRANSACTION JOURNAL v25.60 · REPLAY v25.62",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.recovery_journal_status=tk.Label(journal,text="Hash-chain PREPARE → COMMIT → VERIFY → DONE/ROLLBACK · crash resume không lặp mutation/restart/reelection.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.recovery_journal_status.place(x=10,y=28,width=590)
        HoverButton(journal,"PROOF",self.start_recovery_journal_proof_async,width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(journal,"RESUME AUDIT",self.start_recovery_journal_resume_async,width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        startup=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=62);startup.pack(fill="x",pady=(0,8));startup.pack_propagate(False)
        tk.Label(startup,text="STARTUP RECOVERY v25.74 · WINDOWS TARGET ADAPTER PACK",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.startup_recovery_status=tk.Label(startup,text="Đang chờ startup audit · journal → live observer class/freshness → fail-closed mutation gate.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.startup_recovery_status.place(x=10,y=30,width=590)
        HoverButton(startup,"RECONCILE",self.startup_recovery_reconcile_async,width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=17)
        HoverButton(startup,"WIN OBS",self.start_windows_recovery_observer_async,width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=17)
        realcert=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);realcert.pack(fill="x",pady=(0,8));realcert.pack_propagate(False)
        tk.Label(realcert,text="REAL CODEX EFFECT CRASH CERT v25.74 · DISARMED DEFAULT",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.real_effect_cert_status=tk.Label(realcert,text="PREFLIGHT only · real run cần Windows + ARM + operator phrase + environment gate + adapter witness.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.real_effect_cert_status.place(x=10,y=28,width=590)
        HoverButton(realcert,"PREFLIGHT",self.start_real_effect_preflight_async,width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(realcert,"LAB CRASH",self.start_target_crash_harness_async,width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        attest=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=62);attest.pack(fill="x",pady=(0,8));attest.pack_propagate(False)
        tk.Label(attest,text="ATTESTED TARGET EVIDENCE v25.74 · NO AUTO PROMOTION",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.attested_evidence_status=tk.Label(attest,text="Adapter pack + anti-replay attestation + promotion gate + timeline tiếng Việt · REAL effect vẫn DISARMED mặc định.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.attested_evidence_status.place(x=10,y=30,width=500)
        HoverButton(attest,"ADAPTER",self.start_v2565_adapter_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=520,y=17)
        HoverButton(attest,"PROMOTION",self.start_v2565_promotion_gate_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=625,y=17)
        HoverButton(attest,"TIMELINE",self.start_v2565_timeline_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=17)
        signed=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=62);signed.pack(fill="x",pady=(0,8));signed.pack_propagate(False)
        tk.Label(signed,text="SIGNED TARGET CERT v25.74 · ONE-SHOT / AUTO-DISARM",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.signed_cert_status=tk.Label(signed,text="Cryptographic signer + controlled runbook + evidence exchange · proof-only trên host này · REAL effect DISARMED.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.signed_cert_status.place(x=10,y=30,width=500)
        HoverButton(signed,"SIGNER",self.start_v2566_signer_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=520,y=17)
        HoverButton(signed,"RUNBOOK",self.start_v2566_runbook_proof_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=625,y=17)
        HoverButton(signed,"EVIDENCE",self.start_v2566_exchange_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=17)
        trustcamp=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=62);trustcamp.pack(fill="x",pady=(0,8));trustcamp.pack_propagate(False)
        tk.Label(trustcamp,text="TRUST STORE + CERT CAMPAIGN v25.74 · RESUMABLE / NO SILENT REPEAT",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.trust_campaign_status=tk.Label(trustcamp,text="Certificate pin/rotate/revoke + DPAPI lifecycle + offline verifier + 4×3 campaign · mỗi case phải arm riêng · production auto-promotion=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.trust_campaign_status.place(x=10,y=30,width=500)
        HoverButton(trustcamp,"TRUST",self.start_v2567_trust_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=520,y=17)
        HoverButton(trustcamp,"OFFLINE",self.start_v2567_offline_proof_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=625,y=17)
        HoverButton(trustcamp,"CAMPAIGN",self.start_v2567_campaign_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=17)
        exec_review=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);exec_review.pack(fill="x",pady=(0,8));exec_review.pack_propagate(False)
        tk.Label(exec_review,text="TARGET CAMPAIGN EXECUTOR + PROMOTION REVIEW v25.74 · ONE CASE / HUMAN REVIEW",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2568_campaign_review_status=tk.Label(exec_review,text="Windows-only one-case executor · frozen manifest/trust · idempotency witness · AUTO-DISARM · review đủ 12 signed reports · auto-cert=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2568_campaign_review_status.place(x=10,y=31,width=500)
        HoverButton(exec_review,"EXECUTOR",self.start_v2568_executor_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(exec_review,"REVIEW",self.start_v2568_review_proof_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(exec_review,"OFFLINE",self.start_v2568_offline_bundle_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        evidence_ledger=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);evidence_ledger.pack(fill="x",pady=(0,8));evidence_ledger.pack_propagate(False)
        tk.Label(evidence_ledger,text="EVIDENCE INBOX + PROMOTION LEDGER v25.74 · READ-ONLY INGEST / DUAL REVIEW",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2569_evidence_ledger_status=tk.Label(evidence_ledger,text="Ingest chỉ verify/quarantine · ledger append-only hash-chain · 2 reviewer khác nhau · promotion ≠ score mutation · auto-cert=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2569_evidence_ledger_status.place(x=10,y=31,width=500)
        HoverButton(evidence_ledger,"INGEST",self.start_v2569_ingest_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(evidence_ledger,"LEDGER",self.start_v2569_ledger_proof_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(evidence_ledger,"INBOX",self.start_v2569_inbox_proof_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        parity1327=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);parity1327.pack(fill="x",pady=(0,8));parity1327.pack_propagate(False)
        tk.Label(parity1327,text="COCKPIT TOOLS v1.3.27 PARITY RESET · HMS v25.74 · CODEX-ONLY",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2570_cockpit_parity_status=tk.Label(parity1327,text="P0: port auto-rebind / account occupancy / client-vs-API state / official-ID usage / stream identity · production score không tự tăng.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2570_cockpit_parity_status.place(x=10,y=31,width=500)
        HoverButton(parity1327,"PARITY",self.start_v2570_cockpit_parity_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(parity1327,"SOURCE",self.start_v2570_cockpit_source_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(parity1327,"AUDITOR",self.start_v2570_cockpit_auditor_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        runtime1327=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);runtime1327.pack(fill="x",pady=(0,8));runtime1327.pack_propagate(False)
        tk.Label(runtime1327,text="COCKPIT v1.3.27 WINDOWS RUNTIME CERT · HMS v25.74 · TARGET EVIDENCE ONLY",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2571_runtime_cert_status=tk.Label(runtime1327,text="7 parity case · Windows/Codex thật + signed observer/effect evidence · auditor chỉ đề xuất, score-mutation=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2571_runtime_cert_status.place(x=10,y=31,width=500)
        HoverButton(runtime1327,"CERTIFY",self.start_v2571_runtime_cert_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(runtime1327,"AUDIT",self.start_v2571_promotion_auditor_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(runtime1327,"EVIDENCE",self.start_v2571_runtime_diagnostics_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        capture72=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);capture72.pack(fill="x",pady=(0,8));capture72.pack_propagate(False)
        tk.Label(capture72,text="WINDOWS TARGET EVIDENCE CAPTURE KIT · HMS v25.72 · DISARMED / BASELINE WATCH",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2572_capture_status=tk.Label(capture72,text="7 parity case · exact ZIP/manifest/Codex binding · one-case executor reuse · Cockpit >1.3.27 => FREEZE promotion · score-mutation=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2572_capture_status.place(x=10,y=31,width=500)
        HoverButton(capture72,"CAPTURE KIT",self.start_v2572_capture_kit_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(capture72,"BASELINE",self.start_v2572_baseline_watch_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(capture72,"PRIVACY",self.start_v2572_capture_privacy_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        import73=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);import73.pack(fill="x",pady=(0,8));import73.pack_propagate(False)
        tk.Label(import73,text="WINDOWS EVIDENCE IMPORT REVIEW · HMS v25.74 · TWO BASELINE CHECKPOINTS / DUAL REVIEW",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2573_import_review_status=tk.Label(import73,text="Read-only 7-case signed import · replay/quarantine · before-import + before-review baseline watch · score-mutation=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2573_import_review_status.place(x=10,y=31,width=500)
        HoverButton(import73,"IMPORT",self.start_v2573_import_review_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(import73,"DELTA WATCH",self.start_v2573_delta_watch_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(import73,"DIAGNOSTICS",self.start_v2573_import_diagnostics_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        review74=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=64);review74.pack(fill="x",pady=(0,8));review74.pack_propagate(False)
        tk.Label(review74,text="EXTERNAL WINDOWS EVIDENCE REVIEW PACKET · HMS v25.74 · IMMUTABLE / BASELINE RECONCILE",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.v2574_review_packet_status=tk.Label(review74,text="Raw evidence chỉ tham chiếu SHA-256 · packet hash-chain · baseline drift => superseding INVALIDATE · new dual-review epoch · score-mutation=FALSE.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.v2574_review_packet_status.place(x=10,y=31,width=500)
        HoverButton(review74,"PACKET",self.start_v2574_review_packet_async,width=96,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=520,y=18)
        HoverButton(review74,"RECONCILE",self.start_v2574_reconcile_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=625,y=18)
        HoverButton(review74,"DIAGNOSTICS",self.start_v2574_review_diagnostics_async,width=96,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=730,y=18)
        replay=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);replay.pack(fill="x",pady=(0,8));replay.pack_propagate(False)
        tk.Label(replay,text="RECOVERY REPLAY v25.62 · CROSS-SUBSYSTEM",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.recovery_replay_status=tk.Label(replay,text="Auth rewrite → Codex restart → Router transition → LAN lease · at-most-once · ownership proof · HEALTHY/DEGRADED_SAFE/OPERATOR_REQUIRED.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.recovery_replay_status.place(x=10,y=28,width=590)
        HoverButton(replay,"REPLAY PROOF",self.start_recovery_replay_proof_async,width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=610,y=15)
        HoverButton(replay,"MỞ EVIDENCE",self.open_recovery_replay_evidence,width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=724,y=15)
        authc=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=58);authc.pack(fill="x",pady=(0,8));authc.pack_propagate(False)
        tk.Label(authc,text="OFFICIAL AUTH COMPAT v25.59 · P0",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.official_auth_status=tk.Label(authc,text="file / keyring / auto · snapshot trước switch · field-preserving rewrite · official OAuth identity · controlled restart.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.official_auth_status.place(x=10,y=28,width=690)
        HoverButton(authc,"AUTH AUDIT",self.start_official_auth_compat_async,width=126,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=710,y=15)
        target_cert=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=62);target_cert.pack(fill="x",pady=(0,8));target_cert.pack_propagate(False)
        tk.Label(target_cert,text="TARGET-MACHINE CERTIFICATION v25.53",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=10,y=7)
        self.target_machine_cert_status=tk.Label(target_cert,text="Chưa đánh giá · 7 stage: Host / Codex / Quota / Failover / LAN / Soak 6h / Soak 24h.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.target_machine_cert_status.place(x=10,y=30,width=585)
        HoverButton(target_cert,"PREFLIGHT",lambda:self.start_target_machine_cert_async(False),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border_soft"],font=("Segoe UI Semibold",7)).place(x=610,y=17)
        HoverButton(target_cert,"ĐÁNH GIÁ",lambda:self.start_target_machine_cert_async(True),width=104,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=724,y=17)
        card=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);card.pack(fill="both",expand=True)
        tk.Label(card,text="SIGNED NODE REGISTRY · PROJECT LEASE / EPOCH · FAILOVER METADATA",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.lan_text=tk.Text(card,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",8),wrap="word");self.lan_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.lan_text.configure(state="disabled")

    def load_lan_pool_async(self):
        if hasattr(self,"lan_status"):self.lan_status.configure(text="Đang đọc signed LAN registry...",fg=C["muted"])
        def worker():
            data=self.backend("get_lan_pool",90);self.root.after(0,lambda:self._apply_lan_pool(data))
        threading.Thread(target=worker,daemon=True).start()

    def pair_lan_pool_async(self):
        if self.busy:return
        shared=self.lan_shared_var.get().strip();code=self.lan_pair_var.get().strip();node=self.lan_node_var.get().strip()
        if not shared:self.toast("Chưa nhập SMB/NAS shared path.","warning");return
        if len(code)<16:self.toast("Pairing code cần ít nhất 16 ký tự.","warning");return
        self.busy=True;self.lan_status.configure(text="Đang pair node + tạo signed heartbeat...",fg=C["warning"])
        def worker():
            data=self.backend("pair_lan_pool",120,payload={"shared_path":shared,"pairing_code":code,"node_name":node});self.root.after(0,lambda:self._finish_lan_pool_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def heartbeat_lan_pool_async(self):
        if self.busy:return
        self.busy=True;self.lan_status.configure(text="Đang heartbeat + renew lease project đang chạy...",fg=C["warning"])
        def worker():
            data=self.backend("heartbeat_lan_pool",120);self.root.after(0,lambda:self._finish_lan_pool_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def _soak_state_dir(self):
        return TRACE_DIR / "reliability-soak-v2547"

    def _soak_gui_marker_path(self):
        return self._soak_state_dir() / "soak-gui-current-v2547.json"

    def _read_soak_gui_marker(self):
        try:
            p=self._soak_gui_marker_path()
            return json.loads(p.read_text("utf-8-sig")) if p.exists() else None
        except Exception:
            return None

    def _write_soak_gui_marker(self,row):
        d=self._soak_state_dir();d.mkdir(parents=True,exist_ok=True)
        p=self._soak_gui_marker_path();tmp=p.with_suffix(".tmp")
        tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.replace(tmp,p)

    def _soak_checkpoint_for(self,run_id):
        return self._soak_state_dir()/f"soak-checkpoint-v2547-{run_id}.json"

    def _soak_lock_for(self,run_id):
        return self._soak_state_dir()/f"soak-run-v2547-{run_id}.lock"

    def _launch_soak_process(self,marker):
        tool=ROOT/"HMS_Codex_ReliabilitySoak.py"
        if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_ReliabilitySoak.py")
        run_id=str(marker.get("run_id") or "");profile=str(marker.get("profile") or "smoke")
        cmd=[sys.executable,str(tool),"--mode","run","--profile",profile,"--state-dir",str(self._soak_state_dir()),"--run-id",run_id,"--interval-sec","5"]
        shared=str(marker.get("shared") or "").strip()
        if shared:cmd += ["--shared",shared]
        router=str(marker.get("router_target") or "").strip()
        if router:cmd += ["--router-target",router]
        for target in marker.get("instance_targets") or []:
            if str(target).strip():cmd += ["--instance-target",str(target).strip()]
        flags=CREATE_NO_WINDOW | (getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
        log=self._soak_state_dir()/f"soak-process-v2547-{run_id}.log"
        self._soak_state_dir().mkdir(parents=True,exist_ok=True)
        fh=log.open("ab")
        try:
            proc=subprocess.Popen(cmd,cwd=str(ROOT),stdout=fh,stderr=subprocess.STDOUT,creationflags=flags)
        finally:
            fh.close()
        marker=dict(marker);marker["pid"]=proc.pid;marker["launched_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat();self._write_soak_gui_marker(marker)
        return proc.pid

    def start_reliability_soak_async(self,profile):
        if self.busy:return
        shared=self.lan_shared_var.get().strip() if hasattr(self,"lan_shared_var") else ""
        if profile in ("6h","24h") and not shared:
            self.toast("Soak 6h/24h cần shared SMB/NAS path.","warning");return
        current=self._read_soak_gui_marker()
        if current:
            rid=str(current.get("run_id") or "");cp=self._soak_checkpoint_for(rid)
            try:state=json.loads(cp.read_text("utf-8-sig")) if cp.exists() else {}
            except Exception:state={}
            if state and state.get("state") not in ("PASS","FAIL") and float(state.get("active_elapsed_sec") or 0)<float(state.get("target_duration_sec") or 1):
                self.toast("Đang có soak chưa hoàn tất. Dùng TIẾP TỤC hoặc DỪNG trước khi tạo run mới.","warning");self._apply_reliability_soak_status();return
        self.busy=True;self.lan_soak_status.configure(text="Đang kiểm tra Router + managed instance trước khi khởi chạy soak...",fg=C["warning"])
        def worker():
            try:
                data=self.backend("get_instances",60);instances=(data.get("instances") or []) if data.get("ok") else []
                ports=[]
                for item in instances:
                    try:
                        port=int(item.get("port") or 0)
                        if 1<=port<=65535 and port not in ports:ports.append(port)
                    except Exception:pass
                if profile in ("6h","24h") and len(ports)<2:
                    raise RuntimeError("Soak 6h/24h cần ít nhất 2 managed Codex instance đã cấu hình.")
                stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                marker={"version":"25.47","run_id":f"gui-{profile}-{stamp}","profile":profile,"shared":shared,"router_target":"127.0.0.1:8317","instance_targets":[f"127.0.0.1:{p}" for p in ports],"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
                pid=self._launch_soak_process(marker)
                self.root.after(0,lambda:self._finish_soak_start(True,f"Đã khởi chạy soak {profile.upper()} · PID {pid}. Có checkpoint/resume; đóng GUI không làm mất tiến độ."))
            except Exception as exc:
                self.root.after(0,lambda e=str(exc):self._finish_soak_start(False,e))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_soak_start(self,ok,msg):
        self.busy=False;self.toast(msg,"success" if ok else "danger");self._apply_reliability_soak_status()

    def resume_reliability_soak_async(self):
        if self.busy:return
        marker=self._read_soak_gui_marker()
        if not marker:self.toast("Chưa có soak checkpoint để tiếp tục.","warning");return
        rid=str(marker.get("run_id") or "")
        if self._soak_lock_for(rid).exists():self.toast("Soak hiện vẫn đang chạy.","warning");self._apply_reliability_soak_status();return
        self.busy=True
        def worker():
            try:
                pid=self._launch_soak_process(marker);self.root.after(0,lambda:self._finish_soak_start(True,f"Đã resume soak · PID {pid}. Downtime không được cộng vào active time."))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_soak_start(False,e))
        threading.Thread(target=worker,daemon=True).start()

    def stop_reliability_soak_async(self):
        marker=self._read_soak_gui_marker()
        if not marker:self.toast("Chưa có soak run để dừng.","warning");return
        rid=str(marker.get("run_id") or "");tool=ROOT/"HMS_Codex_ReliabilitySoak.py"
        def worker():
            try:
                p=subprocess.run([sys.executable,str(tool),"--mode","stop","--state-dir",str(self._soak_state_dir()),"--run-id",rid],cwd=str(ROOT),text=True,capture_output=True,timeout=20,creationflags=CREATE_NO_WINDOW)
                ok=p.returncode==0;msg="Đã yêu cầu soak checkpoint + pause an toàn; không kill process." if ok else ((p.stderr or p.stdout or "Không dừng được soak.")[-240:])
                self.root.after(0,lambda:self._finish_soak_start(ok,msg))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_soak_start(False,e))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_reliability_soak_status(self):
        if not hasattr(self,"lan_soak_status"):return
        marker=self._read_soak_gui_marker()
        if not marker:
            self.lan_soak_status.configure(text="Chưa có soak run · 6h/24h chỉ PASS khi có Router + ≥2 instance + shared LAN.",fg=C["text2"]);return
        rid=str(marker.get("run_id") or "");cp_path=self._soak_checkpoint_for(rid)
        try:cp=json.loads(cp_path.read_text("utf-8-sig")) if cp_path.exists() else {}
        except Exception:cp={}
        if not cp:
            self.lan_soak_status.configure(text=f"{rid} · đang khởi tạo checkpoint...",fg=C["warning"]);return
        active=float(cp.get("active_elapsed_sec") or 0);target=max(0.001,float(cp.get("target_duration_sec") or 1));pct=min(100.0,active/target*100.0);state=str(cp.get("state") or "IN_PROGRESS");running=self._soak_lock_for(rid).exists()
        cov=cp.get("coverage") or {};health=cp.get("health") or {}
        text=f"{str(marker.get('profile') or '').upper()} · {pct:.2f}% · active {active/3600:.2f}h/{target/3600:.2f}h · cycles {cp.get('cycle_count',0)} · sessions {cp.get('session_count',0)} · {'RUNNING' if running else state} · recovery {cov.get('transient_fault_recovered',0)}"
        color=C["success"] if state=="PASS" else (C["danger"] if state=="FAIL" or health.get("recovery_budget_violation_count") else (C["warning"] if running else C["text2"]))
        self.lan_soak_status.configure(text=text,fg=color)

    def _perf_state_dir(self):
        return TRACE_DIR / "performance-scale-v2548"

    def _perf_latest_path(self):
        return self._perf_state_dir() / "performance-scale-latest-v2548.json"

    def start_performance_scale_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"lan_perf_status"):self.lan_perf_status.configure(text="Đang benchmark Router + managed instances + backpressure/reconnect/LAN contention...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_PerformanceScale.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_PerformanceScale.py")
                data=self.backend("get_instances",60);instances=(data.get("instances") or []) if data.get("ok") else []
                ports=[]
                for item in instances:
                    try:
                        port=int(item.get("port") or 0)
                        if 1<=port<=65535 and port not in ports:ports.append(port)
                    except Exception:pass
                out=self._perf_latest_path();out.parent.mkdir(parents=True,exist_ok=True)
                stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                cmd=[sys.executable,str(tool),"--router-target","127.0.0.1:8317","--run-id",f"gui-{stamp}","--output",str(out)]
                for port in ports:cmd += ["--instance-target",f"127.0.0.1:{port}"]
                shared=self.lan_shared_var.get().strip() if hasattr(self,"lan_shared_var") else ""
                if shared:cmd += ["--shared",shared]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Benchmark không có output")[-300:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_performance_scale(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_performance_scale(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_performance_scale(self,ok,result):
        self.busy=False;self._apply_performance_scale_status(result)
        if ok:self.toast("Performance / Scale benchmark hoàn tất. Model TTFT thật chưa được đo để tránh tiêu quota.","success")
        else:self.toast(str(result.get("error") or result.get("failures") or "Performance benchmark lỗi.")[:260],"danger")

    def _apply_performance_scale_status(self,result=None):
        if not hasattr(self,"lan_perf_status"):return
        if result is None:
            try:result=json.loads(self._perf_latest_path().read_text("utf-8-sig")) if self._perf_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.lan_perf_status.configure(text="Chưa benchmark · đo control-plane TTFB/latency, throughput, backpressure, reconnect storm và LAN contention.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        text=f"{verdict} · targets {result.get('topology',{}).get('target_count','—')} · P95 {sm.get('max_latency_p95_ms','—')}ms · TTFB {sm.get('max_control_plane_ttfb_p95_ms','—')}ms · peak c={sm.get('peak_concurrency','—')} {sm.get('max_throughput_rps','—')} rps · retain {sm.get('high_concurrency_retention','—')}"
        color=C["danger"] if verdict=="FAIL" else (C["warning"] if "WARNING" in verdict or result.get("warnings") else C["success"])
        self.lan_perf_status.configure(text=text,fg=color)

    def _real_cert_state_dir(self):
        return TRACE_DIR / "real-codex-cert-v2549"

    def _real_cert_latest_path(self):
        return self._real_cert_state_dir() / "real-codex-cert-latest-v2549.json"

    def _real_cert_instance_store(self):
        return TRACE_DIR / "codex-instances-v1.json"

    def start_real_codex_cert_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"real_cert_status"):self.real_cert_status.configure(text="Đang kiểm tra Windows PowerShell 5.1 + Codex capability + 2 managed instance...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RealCertification.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_RealCertification.py")
                out=self._real_cert_latest_path();out.parent.mkdir(parents=True,exist_ok=True)
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--instance-store",str(self._real_cert_instance_store()),"--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Real Codex certification không có output")[-400:])}
                ok=p.returncode==0 and str(result.get("verdict") or "")!="FAIL"
                self.root.after(0,lambda:self._finish_real_codex_cert(ok,result,False))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_real_codex_cert(False,{"verdict":"FAIL","error":e},False))
        threading.Thread(target=worker,daemon=True).start()

    def start_real_codex_live_cert_async(self):
        if self.busy:return
        if os.name!="nt":self.toast("LIVE certification chỉ chạy trên Windows target.","warning");return
        model=self.real_cert_model_var.get().strip() if hasattr(self,"real_cert_model_var") else ""
        if not model:self.toast("Nhập model đang dùng thực tế trước khi chạy LIVE 1.","warning");return
        if not messagebox.askyesno("HMS Real Codex Certification","LIVE 1 sẽ gửi đúng 1 request model thật và có thể tiêu quota.\n\nTiếp tục?"):return
        self.busy=True
        if hasattr(self,"real_cert_status"):self.real_cert_status.configure(text="LIVE 1 đang chạy · request cap=1 · không ghi prompt/response/key vào evidence...",fg=C["warning"])
        def worker():
            try:
                bridge=ROOT/"HMS_Codex_RealCertificationBridge.ps1"
                if not bridge.exists():raise RuntimeError("Thiếu HMS_Codex_RealCertificationBridge.ps1")
                out=self._real_cert_latest_path();out.parent.mkdir(parents=True,exist_ok=True)
                ps=os.path.join(os.environ.get("WINDIR",r"C:\Windows"),r"System32\WindowsPowerShell\v1.0\powershell.exe")
                cmd=[ps,"-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",str(bridge),"-Root",str(ROOT),"-Model",model,"-MaxLiveRequests","1","-InstanceStore",str(self._real_cert_instance_store()),"-Output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "LIVE certification không có output")[-400:])}
                ok=p.returncode==0 and str(result.get("verdict") or "")!="FAIL"
                self.root.after(0,lambda:self._finish_real_codex_cert(ok,result,True))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_real_codex_cert(False,{"verdict":"FAIL","error":e},True))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_real_codex_cert(self,ok,result,live):
        self.busy=False;self._apply_real_codex_cert_status(result)
        if ok:
            verdict=str(result.get("verdict") or "")
            self.toast(("LIVE 1 hoàn tất · "+verdict) if live else ("Real Codex preflight hoàn tất · "+verdict),"success" if "PASS_REAL" in verdict else "warning")
        else:self.toast(str(result.get("error") or result.get("blockers") or "Real Codex certification lỗi.")[:300],"danger")

    def _apply_real_codex_cert_status(self,result=None):
        if not hasattr(self,"real_cert_status"):return
        if result is None:
            try:result=json.loads(self._real_cert_latest_path().read_text("utf-8-sig")) if self._real_cert_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.real_cert_status.configure(text="Chưa kiểm tra · KIỂM TRA không tốn quota; LIVE 1 gửi đúng 1 request thật sau xác nhận.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—");cli=result.get("codex_cli") or {};ps=result.get("powershell_5_1") or {}
        text=f"{verdict} · Codex {cli.get('version') or '—'} · PS5.1 {'PASS' if ps.get('is_windows_powershell_5_1') and ps.get('parser_ok') else '—'} · inst {sm.get('healthy_instance_endpoints','—')}/{sm.get('managed_instances','—')} · live {sm.get('live_requests_pass','—')}/{sm.get('live_requests_executed','—')} · TTFTΔ {sm.get('exact_output_text_delta_ttft_observed','—')}"
        color=C["success"] if verdict=="PASS_REAL_CODEX_CERTIFIED" else (C["danger"] if verdict=="FAIL" else C["warning"])
        self.real_cert_status.configure(text=text,fg=color)

    def _rotation_torture_latest_path(self):
        return TRACE_DIR / "seamless-rotation-torture-v2551-latest.json"

    def start_rotation_torture_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"rotation_torture_status"):self.rotation_torture_status.configure(text="Đang torture 1000 cycle · không gọi model thật / không tiêu quota...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_SeamlessRotationTorture.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_SeamlessRotationTorture.py")
                out=self._rotation_torture_latest_path();out.parent.mkdir(parents=True,exist_ok=True)
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--cycles","1000","--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Rotation torture không có output")[-400:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_rotation_torture(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_rotation_torture(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_rotation_torture(self,ok,result):
        self.busy=False;self._apply_rotation_torture_status(result)
        self.toast("Seamless Rotation Torture PASS." if ok else str(result.get("error") or result.get("verdict") or "Rotation torture FAIL")[:260],"success" if ok else "danger")

    def _apply_rotation_torture_status(self,result=None):
        if not hasattr(self,"rotation_torture_status"):return
        if result is None:
            try:result=json.loads(self._rotation_torture_latest_path().read_text("utf-8-sig")) if self._rotation_torture_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.rotation_torture_status.configure(text="Chưa chạy · synthetic 1000 cycle · quota depletion / 429 / stale recovery / auth isolation / LAN rejoin.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        text=f"{verdict} · {sm.get('pass','—')}/{sm.get('total','—')} · cycles {sm.get('cycles','—')} · no ping-pong · sticky session · auth isolation · lease epoch"
        self.rotation_torture_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def _production_sim_state_dir(self):
        return TRACE_DIR / "production-simulation-v2554"

    def _production_sim_latest_path(self, replay=False):
        return self._production_sim_state_dir() / ("production-simulation-replay-v2554.json" if replay else "production-simulation-latest-v2554.json")

    def start_production_simulation_async(self, replay=False):
        if self.busy:return
        self.busy=True
        if hasattr(self,"production_sim_status"):
            self.production_sim_status.configure(text=("Đang deterministic REPLAY seed 991..." if replay else "Đang chạy 8-seed Production Simulation Lab..."),fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_ProductionSimulationLab.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_ProductionSimulationLab.py")
                state=self._production_sim_state_dir();state.mkdir(parents=True,exist_ok=True)
                out=self._production_sim_latest_path(replay)
                seeds="991" if replay else "11,23,37,41,59,73,89,101"
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--seeds",seeds,"--cycles","300","--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Simulation Lab không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_production_simulation(ok,result,replay))
            except Exception as exc:
                self.root.after(0,lambda e=str(exc):self._finish_production_simulation(False,{"verdict":"FAIL","error":e},replay))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_production_simulation(self,ok,result,replay=False):
        self.busy=False;self._apply_production_sim_status(result)
        verdict=str(result.get("verdict") or "FAIL")
        if ok:self.toast(("Replay" if replay else "Simulation Lab")+" · "+verdict,"success")
        else:self.toast(str(result.get("error") or "Production Simulation Lab lỗi")[:300],"danger")

    def _apply_production_sim_status(self,result=None):
        if not hasattr(self,"production_sim_status"):return
        if result is None:
            try:result=json.loads(self._production_sim_latest_path(False).read_text("utf-8-sig")) if self._production_sim_latest_path(False).exists() else None
            except Exception:result=None
        if not result:
            self.production_sim_status.configure(text="Chưa chạy · digital twin synthetic-only · 8 seed / fault injection / deterministic replay.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        text=f"{verdict} · seed {sm.get('seed_pass','—')}/{sm.get('seeds','—')} · cycles {sm.get('total_cycles','—')} · invariants {sm.get('invariant_failures','—')} fail · replay {sm.get('replay_pass','—')}/{sm.get('replay_total','—')}"
        self.production_sim_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def _autonomous_router_twin_state_dir(self):
        return TRACE_DIR / "autonomous-router-twin-v2555"

    def _autonomous_router_twin_latest_path(self, model_check=False):
        return self._autonomous_router_twin_state_dir() / ("autonomous-router-model-check-v2555.json" if model_check else "autonomous-router-twin-latest-v2555.json")

    def start_autonomous_router_twin_async(self, model_check=False):
        if self.busy:return
        self.busy=True
        if hasattr(self,"router_twin_status"):
            self.router_twin_status.configure(text=("Đang bounded MODEL CHECK + trace minimization..." if model_check else "Đang chạy Autonomous Router Digital Twin 32/12/24..."),fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_AutonomousRouterDigitalTwin.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_AutonomousRouterDigitalTwin.py")
                state=self._autonomous_router_twin_state_dir();state.mkdir(parents=True,exist_ok=True)
                out=self._autonomous_router_twin_latest_path(model_check)
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                if model_check:cmd += ["--seeds","2555,2556","--cycles","160","--accounts","16","--instances","8","--projects","12"]
                else:cmd += ["--seeds","13,29,47,61,79,97","--cycles","300","--accounts","32","--instances","12","--projects","24"]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Router Twin không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_autonomous_router_twin(ok,result,model_check))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_autonomous_router_twin(False,{"verdict":"FAIL","error":e},model_check))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_autonomous_router_twin(self,ok,result,model_check=False):
        self.busy=False;self._apply_autonomous_router_twin_status(result)
        self.toast(("Model Check" if model_check else "Router Twin")+" · "+str(result.get("verdict") or "FAIL"),"success" if ok else "danger")

    def _apply_autonomous_router_twin_status(self,result=None):
        if not hasattr(self,"router_twin_status"):return
        if result is None:
            try:result=json.loads(self._autonomous_router_twin_latest_path(False).read_text("utf-8-sig")) if self._autonomous_router_twin_latest_path(False).exists() else None
            except Exception:result=None
        if not result:
            self.router_twin_status.configure(text="Chưa chạy · 32 account / 12 instance / 24 project · dynamic weights · model check · trace minimization.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        text=f"{verdict} · seed {sm.get('seed_pass','—')}/{sm.get('seed_total','—')} · cycles {sm.get('total_cycles','—')} · states {sm.get('model_states_checked','—')} · trace {sm.get('trace_minimized_from','—')}→{sm.get('trace_minimized_to','—')}"
        self.router_twin_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def _protocol_chaos_state_dir(self):
        return TRACE_DIR / "protocol-chaos-v2556"

    def _protocol_chaos_latest_path(self):
        return self._protocol_chaos_state_dir() / "protocol-chaos-latest-v2556.json"

    def start_protocol_chaos_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"protocol_chaos_status"):
            self.protocol_chaos_status.configure(text="Đang fuzz 300 case · SSE / WebSocket / JSON / chunked / retry...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_ProtocolChaosFuzzer.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_ProtocolChaosFuzzer.py")
                state=self._protocol_chaos_state_dir();state.mkdir(parents=True,exist_ok=True)
                out=self._protocol_chaos_latest_path()
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--seed","2556","--cases","300","--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Protocol Chaos không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_protocol_chaos(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_protocol_chaos(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_protocol_chaos(self,ok,result):
        self.busy=False;self._apply_protocol_chaos_status(result)
        self.toast("Protocol Chaos · "+str(result.get("verdict") or "FAIL"),"success" if ok else "danger")

    def _apply_protocol_chaos_status(self,result=None):
        if not hasattr(self,"protocol_chaos_status"):return
        if result is None:
            try:result=json.loads(self._protocol_chaos_latest_path().read_text("utf-8-sig")) if self._protocol_chaos_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.protocol_chaos_status.configure(text="Chưa chạy · 300 deterministic fuzz case · SSE/WS/JSON/chunked/retry/early-EOF · synthetic-only.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        text=f"{verdict} · {sm.get('pass','—')}/{sm.get('total','—')} · fuzz {sm.get('fuzz_cases','—')} · seed {sm.get('seed','—')} · no midstream replay"
        self.protocol_chaos_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def open_protocol_chaos_evidence(self):
        state=self._protocol_chaos_state_dir();state.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt":os.startfile(str(state))
        except Exception as exc:self.toast(str(exc),"danger")

    def _recovery_planner_state_dir(self):
        return TRACE_DIR / "recovery-planner-v2557"

    def _recovery_planner_latest_path(self):
        return self._recovery_planner_state_dir() / "recovery-planner-latest-v2557.json"

    def start_recovery_planner_async(self, model_check=False):
        if self.busy:return
        self.busy=True
        if hasattr(self,"recovery_planner_status"):
            self.recovery_planner_status.configure(text=("Đang model-check 9,216 trạng thái recovery..." if model_check else "Đang chứng minh decision policy / loop breaker / rollback..."),fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RecoveryPlanner.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_RecoveryPlanner.py")
                state=self._recovery_planner_state_dir();state.mkdir(parents=True,exist_ok=True)
                out=self._recovery_planner_latest_path()
                cmd=[sys.executable,str(tool),"--mode","model-check" if model_check else "proof","--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Recovery Planner không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_recovery_planner(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_recovery_planner(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_recovery_planner(self,ok,result):
        self.busy=False;self._apply_recovery_planner_status(result)
        self.toast("Recovery Planner · "+str(result.get("verdict") or "FAIL"),"success" if ok else "danger")

    def _apply_recovery_planner_status(self,result=None):
        if not hasattr(self,"recovery_planner_status"):return
        if result is None:
            try:result=json.loads(self._recovery_planner_latest_path().read_text("utf-8-sig")) if self._recovery_planner_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.recovery_planner_status.configure(text="Chưa chạy · cause-aware recovery · bounded restart/retry · loop breaker · rollback proof · model check 9,216 states.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        states=sm.get("model_states") or ((result.get("model_check") or {}).get("states_checked")) or "—"
        text=f"{verdict} · {sm.get('pass','—')}/{sm.get('total','—')} · model states {states} · no unowned restart / quota restart / unsafe takeover"
        self.recovery_planner_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def open_recovery_planner_evidence(self):
        state=self._recovery_planner_state_dir();state.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt":os.startfile(str(state))
        except Exception as exc:self.toast(str(exc),"danger")

    def _compound_fault_state_dir(self):
        return TRACE_DIR / "compound-fault-recovery-v2558"

    def _compound_fault_latest_path(self):
        return self._compound_fault_state_dir() / "compound-fault-recovery-latest-v2558.json"

    def start_compound_fault_recovery_async(self, model_check=False):
        if self.busy:return
        self.busy=True
        if hasattr(self,"compound_fault_status"):
            self.compound_fault_status.configure(text=("Đang model-check 72k+ trạng thái compound recovery..." if model_check else "Đang chứng minh recovery DAG / global budget / convergence..."),fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_CompoundFaultRecovery.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_CompoundFaultRecovery.py")
                state=self._compound_fault_state_dir();state.mkdir(parents=True,exist_ok=True)
                out=self._compound_fault_latest_path()
                cmd=[sys.executable,str(tool),"--mode","model-check" if model_check else "proof","--output",str(out)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Compound Fault Lab không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "").startswith("PASS")
                self.root.after(0,lambda:self._finish_compound_fault_recovery(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_compound_fault_recovery(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_compound_fault_recovery(self,ok,result):
        self.busy=False;self._apply_compound_fault_status(result)
        self.toast("Compound Fault Convergence · "+str(result.get("verdict") or "FAIL"),"success" if ok else "danger")

    def _apply_compound_fault_status(self,result=None):
        if not hasattr(self,"compound_fault_status"):return
        if result is None:
            try:result=json.loads(self._compound_fault_latest_path().read_text("utf-8-sig")) if self._compound_fault_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.compound_fault_status.configure(text="Chưa chạy · recovery DAG + global budget · compound faults · convergence HEALTHY / DEGRADED_SAFE / OPERATOR_REQUIRED.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—")
        states=sm.get("model_states") or ((result.get("model_check") or {}).get("states_checked")) or "—"
        text=f"{verdict} · {sm.get('pass','—')}/{sm.get('total','—')} · states {states} · DAG/budget/convergence safe terminals"
        self.compound_fault_status.configure(text=text,fg=C["success"] if verdict.startswith("PASS") else C["danger"])

    def open_compound_fault_evidence(self):
        state=self._compound_fault_state_dir();state.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt":os.startfile(str(state))
        except Exception as exc:self.toast(str(exc),"danger")


    def _recovery_journal_state_dir(self):
        return TRACE_DIR / "recovery-journal-v2560"

    def _recovery_journal_path(self):
        return self._recovery_journal_state_dir() / "recovery-transaction-journal-v2560.jsonl"

    def _recovery_journal_latest_path(self):
        return self._recovery_journal_state_dir() / "recovery-journal-latest-v2560.json"

    def start_recovery_journal_proof_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"recovery_journal_status"):self.recovery_journal_status.configure(text="Đang fault-inject mọi crash point của journal...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RecoveryTransactionJournal.py";state=self._recovery_journal_state_dir();state.mkdir(parents=True,exist_ok=True);out=self._recovery_journal_latest_path()
                p=subprocess.run([sys.executable,str(tool),"--mode","proof","--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Journal proof không có output")[-500:])}
                ok=p.returncode==0 and r.get("verdict")=="PASS";self.root.after(0,lambda:self._finish_recovery_journal(ok,r,"PROOF"))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_recovery_journal(False,{"error":e},"PROOF"))
        threading.Thread(target=worker,daemon=True).start()

    def start_recovery_journal_resume_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"recovery_journal_status"):self.recovery_journal_status.configure(text="Đang audit hash-chain + crash-resume decisions...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RecoveryTransactionJournal.py";state=self._recovery_journal_state_dir();state.mkdir(parents=True,exist_ok=True);jp=self._recovery_journal_path()
                if not jp.exists():
                    r={"ok":True,"version":"25.60","chain":{"ok":True,"records":0,"head_hash":"GENESIS"},"decisions":[]}
                else:
                    p=subprocess.run([sys.executable,str(tool),"--mode","resume","--journal",str(jp)],cwd=str(ROOT),text=True,capture_output=True,timeout=60,creationflags=CREATE_NO_WINDOW)
                    try:r=json.loads(p.stdout)
                    except Exception:r={"ok":False,"error":((p.stderr or p.stdout or "Resume audit không có output")[-500:])}
                self.root.after(0,lambda:self._finish_recovery_journal(bool(r.get("ok")),r,"RESUME"))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_recovery_journal(False,{"error":e},"RESUME"))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_recovery_journal(self,ok,result,mode):
        self.busy=False
        if hasattr(self,"recovery_journal_status"):
            if mode=="PROOF":
                sm=result.get("summary") or {};text=f"{result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · crash cases {sm.get('crash_cases','—')} · duplicate commit forbidden"
            else:
                chain=result.get("chain") or {};dec=result.get("decisions") or [];pending=sum(1 for x in dec if not x.get("terminal"));text=f"{'PASS' if ok else 'FAIL'} · records {chain.get('records','—')} · pending resume {pending} · chain {'OK' if chain.get('ok') else 'INVALID'}"
            self.recovery_journal_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast("Recovery Journal · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _startup_recovery_state_dir(self):
        return TRACE_DIR / "startup-recovery-v2565"

    def _startup_recovery_latest_path(self):
        return self._startup_recovery_state_dir() / "startup-recovery-latest-v2565.json"

    def startup_recovery_reconcile_async(self):
        if getattr(self,"startup_recovery_busy",False):return
        self.startup_recovery_busy=True
        if hasattr(self,"startup_recovery_status"):
            self.startup_recovery_status.configure(text="Đang kiểm journal + observer read-only trước mutation...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_StartupRecoveryReconciler.py";state=self._startup_recovery_state_dir();state.mkdir(parents=True,exist_ok=True);out=self._startup_recovery_latest_path()
                p=subprocess.run([sys.executable,str(tool),"--mode","reconcile","--data-dir",str(TRACE_DIR),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"status":"OPERATOR_REQUIRED","error":((p.stderr or p.stdout or "Startup recovery không có output")[-500:])}
                self.root.after(0,lambda:self._finish_startup_recovery(r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_startup_recovery({"status":"OPERATOR_REQUIRED","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_startup_recovery(self,result):
        self.startup_recovery_busy=False
        status=str(result.get("status") or "OPERATOR_REQUIRED");sm=result.get("summary") or {};blocked=int(sm.get("blocked_conflicting_actions",0) or 0)
        timeline=result.get("timeline") or [];extra=""
        if timeline:
            item=timeline[0] if isinstance(timeline[0],dict) else {};effects=item.get("effects") or []
            probe=effects[0] if effects and isinstance(effects[0],dict) else item
            observer=str(probe.get("observer") or "—");eclass=str(probe.get("evidence_class") or "—");fresh=str(probe.get("freshness_state") or "UNKNOWN");reason=str(probe.get("failure_reason") or probe.get("reason") or "")
            extra=f" · {observer}/{eclass}/{fresh}"+(f" · {reason}" if reason else "")
        text=f"{status} · journals {sm.get('journals_discovered','—')} · unresolved {sm.get('unresolved_transactions','—')} · operator {sm.get('operator_required','—')} · blocked {blocked}{extra}"
        color=C["success"] if status=="HEALTHY" else (C["warning"] if status=="DEGRADED_SAFE" else C["danger"])
        if hasattr(self,"startup_recovery_status"):self.startup_recovery_status.configure(text=text,fg=color)
        if status=="OPERATOR_REQUIRED":self.toast("Startup Recovery cần người vận hành xử lý trước mutation xung đột.","danger")

    def start_windows_recovery_observer_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"startup_recovery_status"):self.startup_recovery_status.configure(text="Đang đọc Windows observer class/freshness/failure reason...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_WindowsTargetAdapterPack.py";state=self._startup_recovery_state_dir();state.mkdir(parents=True,exist_ok=True);out=state/"windows-target-adapter-latest-v2565.json"
                p=subprocess.run([sys.executable,str(tool),"--mode","observe","--data-dir",str(TRACE_DIR),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"DEGRADED_FAIL_CLOSED","error":((p.stderr or p.stdout or "Observer bridge không có output")[-500:])}
                self.root.after(0,lambda:self._finish_windows_recovery_observer(r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_windows_recovery_observer({"verdict":"DEGRADED_FAIL_CLOSED","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_windows_recovery_observer(self,result):
        self.busy=False;sm=result.get("summary") or {};e=result.get("evidence") or {};verdict=str(result.get("verdict") or "DEGRADED_FAIL_CLOSED")
        eclass=result.get("evidence_class") or e.get("class") or "—"
        eligible=bool(result.get("production_score_eligible") or e.get("production_score_eligible"))
        text=f"{verdict} · adapter {sm.get('available','—')}/{sm.get('total','—')} · class {eclass} · score eligible={eligible}"
        color=C["success"] if verdict=="PASS" else C["warning"]
        if hasattr(self,"startup_recovery_status"):self.startup_recovery_status.configure(text=text,fg=color)
        self.toast("Windows Target Adapter · "+verdict,"success" if verdict=="PASS" else "warning")

    def start_real_effect_preflight_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"real_effect_cert_status"):self.real_effect_cert_status.configure(text="Đang kiểm 5 arming gates · không chạy real effect...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RealEffectCrashCertification.py";manifest=ROOT/"REAL_EFFECT_ADAPTER_MANIFEST_TEMPLATE_V25.66.json";state=self._startup_recovery_state_dir();state.mkdir(parents=True,exist_ok=True);out=state/"real-effect-preflight-latest-v2565.json"
                p=subprocess.run([sys.executable,str(tool),"--mode","preflight","--manifest",str(manifest),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=30,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"DEFERRED_NOT_ARMED","error":((p.stderr or p.stdout or "Preflight không có output")[-500:])}
                self.root.after(0,lambda:self._finish_real_effect_preflight(r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_real_effect_preflight({"verdict":"DEFERRED_NOT_ARMED","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_real_effect_preflight(self,result):
        self.busy=False;arming=result.get("arming") or {};g=arming.get("gates") or {};ready=bool(arming.get("armed"));passed=sum(bool(v) for v in g.values())
        text=f"{result.get('verdict','DEFERRED_NOT_ARMED')} · arming {passed}/{len(g) or 5} · real effects executed=False · production score eligible=False"
        if hasattr(self,"real_effect_cert_status"):self.real_effect_cert_status.configure(text=text,fg=C["success"] if ready else C["warning"])
        self.toast("Real Effect Crash Cert · "+("ARMED" if ready else "DISARMED"),"success" if ready else "warning")

    def _v2565_state_path(self,name):
        state=self._startup_recovery_state_dir();state.mkdir(parents=True,exist_ok=True);return state/name

    def start_v2565_adapter_proof_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"attested_evidence_status"):self.attested_evidence_status.configure(text="Đang kiểm Windows Target Adapter Pack v25.66 (probe-only proof)...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_WindowsTargetAdapterPackValidator.py";out=self._v2565_state_path("windows-target-adapter-proof-latest-v2565.json")
                p=subprocess.run([sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
                r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                self.root.after(0,lambda:self._finish_v2565_control_plane("ADAPTER",p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2565_control_plane("ADAPTER",False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2565_promotion_gate_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"attested_evidence_status"):self.attested_evidence_status.configure(text="Đang kiểm anti-replay / mixed-version / signer / 4×3 crash promotion gate...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_AttestedEvidencePromotionGateValidator.py";out=self._v2565_state_path("attested-evidence-promotion-latest-v2565.json")
                p=subprocess.run([sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
                r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                self.root.after(0,lambda:self._finish_v2565_control_plane("PROMOTION",p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2565_control_plane("PROMOTION",False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2565_timeline_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"attested_evidence_status"):self.attested_evidence_status.configure(text="Đang dựng recovery timeline tiếng Việt · metadata-only...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RecoveryOperatorTimeline.py";src=self._startup_recovery_latest_path();out=self._v2565_state_path("recovery-operator-timeline-latest-v2565.json")
                if src.exists():args=[sys.executable,str(tool),"--mode","build","--input",str(src),"--output",str(out)]
                else:args=[sys.executable,str(tool),"--mode","proof","--output",str(out)]
                p=subprocess.run(args,cwd=str(ROOT),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
                r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                self.root.after(0,lambda:self._finish_v2565_control_plane("TIMELINE",p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2565_control_plane("TIMELINE",False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_v2565_control_plane(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {}
        text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass',sm.get('events','—'))}/{sm.get('total','—')} · production auto-promotion=FALSE"
        if hasattr(self,"attested_evidence_status"):self.attested_evidence_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.67 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _v2566_state_path(self,name):
        state=self._startup_recovery_state_dir()/"v2566";state.mkdir(parents=True,exist_ok=True);return state/name

    def _start_v2566_proof(self,kind,validator,filename):
        if self.busy:return
        self.busy=True
        if hasattr(self,"signed_cert_status"):self.signed_cert_status.configure(text=f"Đang chạy {kind} proof · không arm real effect...",fg=C["warning"])
        def worker():
            try:
                out=self._v2566_state_path(filename);tool=ROOT/validator
                p=subprocess.run([sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=60,creationflags=CREATE_NO_WINDOW)
                r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                self.root.after(0,lambda:self._finish_v2566_proof(kind,p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2566_proof(kind,False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2566_signer_proof_async(self):self._start_v2566_proof("SIGNER","HMS_Codex_WindowsAttestationSignerValidator.py","windows-attestation-signer-latest-v2566.json")
    def start_v2566_runbook_proof_async(self):self._start_v2566_proof("RUNBOOK","HMS_Codex_TargetCertificationRunbookValidator.py","target-cert-runbook-latest-v2566.json")
    def start_v2566_exchange_proof_async(self):self._start_v2566_proof("EVIDENCE","HMS_Codex_AttestationExchangeValidator.py","attestation-exchange-latest-v2566.json")

    def _finish_v2566_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · REAL effect executed=FALSE · auto-cert=FALSE"
        if hasattr(self,"signed_cert_status"):self.signed_cert_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.67 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _v2567_state_path(self,name):
        state=self._startup_recovery_state_dir()/"v2567";state.mkdir(parents=True,exist_ok=True);return state/name

    def _start_v2567_proof(self,kind,validator,filename):
        if self.busy:return
        self.busy=True
        if hasattr(self,"trust_campaign_status"):self.trust_campaign_status.configure(text=f"Đang chạy {kind} proof · REAL effect vẫn DISARMED...",fg=C["warning"])
        def worker():
            try:
                out=self._v2567_state_path(filename);tool=ROOT/validator
                p=subprocess.run([sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=60,creationflags=CREATE_NO_WINDOW)
                r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                self.root.after(0,lambda:self._finish_v2567_proof(kind,p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2567_proof(kind,False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2567_trust_proof_async(self):self._start_v2567_proof("TRUST","HMS_Codex_AttestationTrustStoreValidator.py","attestation-trust-store-latest-v2567.json")
    def start_v2567_offline_proof_async(self):self._start_v2567_proof("OFFLINE","HMS_Codex_OfflineAttestationVerifierValidator.py","offline-attestation-verifier-latest-v2567.json")
    def start_v2567_campaign_proof_async(self):self._start_v2567_proof("CAMPAIGN","HMS_Codex_TargetCertificationCampaignValidator.py","target-cert-campaign-latest-v2567.json")

    def _finish_v2567_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · DISARMED · silent-repeat=FALSE · auto-cert=FALSE"
        if hasattr(self,"trust_campaign_status"):self.trust_campaign_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.67 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2568_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2568_campaign_review_status"):self.v2568_campaign_review_status.configure(text=f"Đang chạy {kind} proof v25.68 · target effect vẫn DISARMED...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"startup-recovery-v2565"/"v2568";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool)]
                if "Validator" in tool_name:argv += ["--root",str(ROOT),"--output",str(out)]
                else:argv += ["--proof","--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Proof không có output")[-500:])}
                self.root.after(0,lambda:self._finish_v2568_proof(kind,p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2568_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2568_executor_proof_async(self):self._start_v2568_proof("EXECUTOR","HMS_Codex_TargetCampaignExecutorValidator.py","target-campaign-executor-latest-v2568.json")
    def start_v2568_review_proof_async(self):self._start_v2568_proof("REVIEW","HMS_Codex_AttestedPromotionReviewConsoleValidator.py","attested-promotion-review-latest-v2568.json")
    def start_v2568_offline_bundle_proof_async(self):self._start_v2568_proof("OFFLINE REVIEW","HMS_Codex_AttestedPromotionReviewConsole.py","attested-promotion-review-bundle-proof-v2568.json")

    def _finish_v2568_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · one-case=AUTO-DISARM · human-review=TRUE · auto-cert=FALSE"
        if hasattr(self,"v2568_campaign_review_status"):self.v2568_campaign_review_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.68 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2569_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2569_evidence_ledger_status"):self.v2569_evidence_ledger_status.configure(text=f"Đang chạy {kind} proof v25.69 · ingest không execute effect · auto-cert=FALSE...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"startup-recovery-v2565"/"v2569";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Proof không có output")[-500:])}
                self.root.after(0,lambda:self._finish_v2569_proof(kind,p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2569_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2569_ingest_proof_async(self):self._start_v2569_proof("INGEST","HMS_Codex_TargetCertificationEvidenceIngestValidator.py","target-cert-evidence-ingest-latest-v2569.json")
    def start_v2569_ledger_proof_async(self):self._start_v2569_proof("LEDGER","HMS_Codex_PromotionDecisionLedgerValidator.py","promotion-decision-ledger-latest-v2569.json")
    def start_v2569_inbox_proof_async(self):self._start_v2569_proof("INBOX","HMS_Codex_UnifiedDiagnosticsEvidenceLedgerValidator.py","evidence-inbox-diagnostics-latest-v2569.json")

    def _finish_v2569_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · read-only ingest=TRUE · dual-review=REQUIRED · score-mutation=FALSE"
        if hasattr(self,"v2569_evidence_ledger_status"):self.v2569_evidence_ledger_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.69 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2570_cockpit_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2570_cockpit_parity_status"):self.v2570_cockpit_parity_status.configure(text=f"Đang chạy {kind} v25.70 · baseline Cockpit 1.3.27 · synthetic/control-plane only...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"cockpit-parity-v2570";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Parity proof không có output")[-500:])}
                ok=(p.returncode==0 and ((r.get("summary") or {}).get("fail",1)==0 or (r.get("data") or {}).get("hms",{}).get("verdict") in ("FEATURE_PARITY_CANDIDATE","PASS")))
                self.root.after(0,lambda:self._finish_v2570_cockpit_proof(kind,ok,r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2570_cockpit_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2570_cockpit_parity_async(self):self._start_v2570_cockpit_proof("PARITY","HMS_Codex_Cockpit1327ParityResetValidator.py","cockpit-1327-parity-latest-v2570.json")
    def start_v2570_cockpit_source_async(self):self._start_v2570_cockpit_proof("SOURCE","HMS_Codex_Cockpit1327SourceIntegrationValidator.py","cockpit-1327-source-latest-v2570.json")
    def start_v2570_cockpit_auditor_async(self):self._start_v2570_cockpit_proof("AUDITOR","HMS_Cockpit_ParityAuditor.py","cockpit-parity-audit-latest-v2570.json")

    def _finish_v2570_cockpit_proof(self,kind,ok,result):
        self.busy=False
        sm=result.get("summary") or (result.get("data") or {}).get("summary") or {}
        text=f"{kind} · {'PASS' if ok else 'FAIL'} · Cockpit baseline=1.3.27 · {sm.get('pass','—')}/{sm.get('total','—')} · Windows runtime certification vẫn riêng biệt"
        if hasattr(self,"v2570_cockpit_parity_status"):self.v2570_cockpit_parity_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.70 Cockpit 1.3.27 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2571_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2571_runtime_cert_status"):self.v2571_runtime_cert_status.configure(text=f"Đang chạy {kind} v25.72 · Cockpit 1.3.27 · target evidence contract · auto-score=FALSE...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"cockpit-parity-v2571";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "v25.71 proof không có output")[-500:])}
                ok=(p.returncode==0 and r.get("verdict")=="PASS")
                self.root.after(0,lambda:self._finish_v2571_proof(kind,ok,r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2571_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2571_runtime_cert_async(self):self._start_v2571_proof("CERTIFY","HMS_Codex_Cockpit1327WindowsRuntimeCertificationValidator.py","cockpit-1327-windows-runtime-v2571.json")
    def start_v2571_promotion_auditor_async(self):self._start_v2571_proof("AUDIT","HMS_Codex_ProductionEvidencePromotionAuditorValidator.py","production-evidence-auditor-v2571.json")
    def start_v2571_runtime_diagnostics_async(self):self._start_v2571_proof("EVIDENCE","HMS_Codex_UnifiedDiagnosticsParityRuntimeValidator.py","unified-parity-runtime-v2571.json")

    def _finish_v2571_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · Windows certified=FALSE trên host này · human score review only"
        if hasattr(self,"v2571_runtime_cert_status"):self.v2571_runtime_cert_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.71 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")


    def _start_v2572_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2572_capture_status"):self.v2572_capture_status.configure(text=f"Đang chạy {kind} v25.72 · capture-only / baseline-watch · REAL effect không tự arm...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"target-evidence-capture-v2572";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "v25.72 proof không có output")[-500:])}
                ok=(p.returncode==0 and r.get("verdict")=="PASS")
                self.root.after(0,lambda:self._finish_v2572_proof(kind,ok,r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2572_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2572_capture_kit_async(self):self._start_v2572_proof("CAPTURE KIT","HMS_Codex_WindowsTargetEvidenceCaptureKitValidator.py","windows-target-capture-kit-latest-v2572.json")
    def start_v2572_baseline_watch_async(self):self._start_v2572_proof("BASELINE","HMS_Codex_CockpitBaselineWatchGateValidator.py","cockpit-baseline-watch-latest-v2572.json")
    def start_v2572_capture_privacy_async(self):self._start_v2572_proof("PRIVACY","HMS_DiagnosticsBundlePrivacyValidatorV2572.py","capture-privacy-latest-v2572.json")

    def _finish_v2572_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · baseline=1.3.27 · DISARMED default · production score giữ nguyên"
        if hasattr(self,"v2572_capture_status"):self.v2572_capture_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.72 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2573_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2573_import_review_status"):self.v2573_import_review_status.configure(text=f"Đang chạy {kind} v25.74 · read-only import / dual-review / baseline checkpoints · auto-score=FALSE...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"target-evidence-import-v2573";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "v25.74 proof không có output")[-500:])}
                ok=(p.returncode==0 and r.get("verdict")=="PASS")
                self.root.after(0,lambda:self._finish_v2573_proof(kind,ok,r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2573_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2573_import_review_async(self):self._start_v2573_proof("IMPORT","HMS_Codex_WindowsTargetEvidenceImportReviewValidator.py","windows-target-import-review-latest-v2573.json")
    def start_v2573_delta_watch_async(self):self._start_v2573_proof("DELTA WATCH","HMS_Codex_BaselineDeltaWatchAutomationValidator.py","baseline-delta-watch-latest-v2573.json")
    def start_v2573_import_diagnostics_async(self):self._start_v2573_proof("DIAGNOSTICS","HMS_Codex_UnifiedDiagnosticsImportReviewValidator.py","unified-import-review-latest-v2573.json")

    def _finish_v2573_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · baseline 1.3.27 ×2 · dual-review=REQUIRED · score-mutation=FALSE"
        if hasattr(self,"v2573_import_review_status"):self.v2573_import_review_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.74 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _start_v2574_proof(self,kind,tool_name,out_name):
        if self.busy:return
        self.busy=True
        if hasattr(self,"v2574_review_packet_status"):self.v2574_review_packet_status.configure(text=f"Đang chạy {kind} v25.74 · immutable review packet / baseline reconciliation · auto-score=FALSE...",fg=C["warning"])
        def worker():
            try:
                state=TRACE_DIR/"external-review-packet-v2574";state.mkdir(parents=True,exist_ok=True);out=state/out_name;tool=ROOT/tool_name
                argv=[sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)]
                p=subprocess.run(argv,cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "v25.74 proof không có output")[-500:])}
                ok=(p.returncode==0 and r.get("verdict")=="PASS")
                self.root.after(0,lambda:self._finish_v2574_proof(kind,ok,r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_v2574_proof(kind,False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def start_v2574_review_packet_async(self):self._start_v2574_proof("PACKET","HMS_Codex_ExternalWindowsEvidenceReviewPacketValidator.py","external-windows-review-packet-latest-v2574.json")
    def start_v2574_reconcile_async(self):self._start_v2574_proof("RECONCILE","HMS_Codex_BaselineDriftReconciliationValidator.py","baseline-drift-reconciliation-latest-v2574.json")
    def start_v2574_review_diagnostics_async(self):self._start_v2574_proof("DIAGNOSTICS","HMS_Codex_UnifiedDiagnosticsReviewPacketValidator.py","unified-review-packet-latest-v2574.json")

    def _finish_v2574_proof(self,kind,ok,result):
        self.busy=False;sm=result.get("summary") or {};text=f"{kind} · {result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · immutable raw evidence · new review epoch on drift · score-mutation=FALSE"
        if hasattr(self,"v2574_review_packet_status"):self.v2574_review_packet_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast(f"v25.74 {kind} · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def start_target_crash_harness_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"startup_recovery_status"):self.startup_recovery_status.configure(text="Đang chạy subprocess kill / cold-start crash lab v25.63 (LAB_PROCESS_KILL)...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_TargetCrashHarness.py";state=self._startup_recovery_state_dir();state.mkdir(parents=True,exist_ok=True);out=state/"target-crash-harness-latest-v2563.json"
                p=subprocess.run([sys.executable,str(tool),"--proof","--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Crash harness không có output")[-500:])}
                self.root.after(0,lambda:self._finish_target_crash_harness(p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_target_crash_harness(False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_target_crash_harness(self,ok,result):
        self.busy=False;sm=result.get("summary") or {};host=result.get("host") or {}
        label="WINDOWS TARGET" if host.get("windows_target_evidence") else "LAB HOST"
        text=f"{result.get('verdict','FAIL')} · crash {sm.get('pass','—')}/{sm.get('total','—')} · cold-start PID mới · at-most-once · {label}"
        if hasattr(self,"startup_recovery_status"):self.startup_recovery_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast("Crash Injection Harness · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def _recovery_replay_state_dir(self):
        return TRACE_DIR / "recovery-replay-v2562"

    def _recovery_replay_latest_path(self):
        return self._recovery_replay_state_dir() / "recovery-replay-latest-v2562.json"

    def start_recovery_replay_proof_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"recovery_replay_status"):
            self.recovery_replay_status.configure(text="Đang fault-inject cross-subsystem replay + ownership proof...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_RecoveryTransactionReplay.py";state=self._recovery_replay_state_dir();state.mkdir(parents=True,exist_ok=True);out=self._recovery_replay_latest_path()
                p=subprocess.run([sys.executable,str(tool),"--mode","proof","--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:r=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:r={"verdict":"FAIL","error":((p.stderr or p.stdout or "Replay proof không có output")[-500:])}
                self.root.after(0,lambda:self._finish_recovery_replay(p.returncode==0 and r.get("verdict")=="PASS",r))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_recovery_replay(False,{"error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_recovery_replay(self,ok,result):
        self.busy=False
        sm=result.get("summary") or {}
        text=f"{result.get('verdict','FAIL')} · {sm.get('pass','—')}/{sm.get('total','—')} · crash {sm.get('crash_cases','—')} · at-most-once + ownership proof"
        if hasattr(self,"recovery_replay_status"):self.recovery_replay_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast("Recovery Replay · "+("PASS" if ok else "FAIL"),"success" if ok else "danger")

    def open_recovery_replay_evidence(self):
        state=self._recovery_replay_state_dir();state.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt":os.startfile(str(state))
        except Exception as exc:self.toast(str(exc),"danger")

    def _official_auth_state_dir(self):
        return TRACE_DIR / "official-auth-compat-v2559"

    def _official_auth_latest_path(self):
        return self._official_auth_state_dir() / "official-auth-compat-latest-v2559.json"

    def start_official_auth_compat_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"official_auth_status"):
            self.official_auth_status.configure(text="Đang audit Official Auth Compatibility · không dùng auth thật / không tiêu quota...",fg=C["warning"])
        def worker():
            try:
                tool=ROOT/"HMS_Codex_OfficialAuthCompatibilityValidator.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_OfficialAuthCompatibilityValidator.py")
                state=self._official_auth_state_dir();state.mkdir(parents=True,exist_ok=True);out=self._official_auth_latest_path()
                p=subprocess.run([sys.executable,str(tool),"--root",str(ROOT),"--output",str(out)],cwd=str(ROOT),text=True,capture_output=True,timeout=120,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Auth audit không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "")=="PASS"
                self.root.after(0,lambda:self._finish_official_auth_compat(ok,result))
            except Exception as exc:self.root.after(0,lambda e=str(exc):self._finish_official_auth_compat(False,{"verdict":"FAIL","error":e}))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_official_auth_compat(self,ok,result):
        self.busy=False
        sm=result.get("summary") or {}; verdict=str(result.get("verdict") or "FAIL")
        if hasattr(self,"official_auth_status"):
            text=f"{verdict} · {sm.get('pass','—')}/{sm.get('total','—')} · file/keyring/auto · serialized + rollback + field-preserving"
            self.official_auth_status.configure(text=text,fg=C["success"] if ok else C["danger"])
        self.toast("Official Auth Compatibility · "+verdict,"success" if ok else "danger")

    def _target_machine_cert_state_dir(self):
        return TRACE_DIR / "target-machine-cert-v2553"

    def _target_machine_cert_latest_path(self):
        return self._target_machine_cert_state_dir() / "target-machine-cert-latest-v2553.json"

    def start_target_machine_cert_async(self, include_live=True):
        if self.busy:return
        self.busy=True
        if hasattr(self,"target_machine_cert_status"):
            self.target_machine_cert_status.configure(text=("Đang tổng hợp evidence thật từ 7 stage..." if include_live else "Đang PREFLIGHT · không gửi model request / không tiêu quota..."),fg=C["warning"])
        def worker():
            quota_tmp=None;lan_tmp=None
            try:
                tool=ROOT/"HMS_Codex_TargetMachineCertification.py"
                if not tool.exists():raise RuntimeError("Thiếu HMS_Codex_TargetMachineCertification.py")
                state=self._target_machine_cert_state_dir();state.mkdir(parents=True,exist_ok=True)
                quota=self.backend("get_accounts",60)
                lan=self.backend("get_lan_pool",90)
                if not quota.get("ok"):raise RuntimeError(quota.get("error") or "Không đọc được Account/Quota snapshot")
                if not lan.get("ok"):raise RuntimeError(lan.get("error") or "Không đọc được LAN snapshot")
                fd,qname=tempfile.mkstemp(prefix="hms-v2553-quota-",suffix=".json");os.close(fd);quota_tmp=Path(qname)
                fd,lname=tempfile.mkstemp(prefix="hms-v2553-lan-",suffix=".json");os.close(fd);lan_tmp=Path(lname)
                quota_tmp.write_text(json.dumps(quota,ensure_ascii=False),encoding="utf-8")
                lan_tmp.write_text(json.dumps(lan,ensure_ascii=False),encoding="utf-8")
                out=self._target_machine_cert_latest_path()
                cmd=[sys.executable,str(tool),"--root",str(ROOT),"--data-dir",str(TRACE_DIR),"--instance-store",str(self._real_cert_instance_store()),"--quota-snapshot",str(quota_tmp),"--lan-snapshot",str(lan_tmp),"--soak-state-dir",str(self._soak_state_dir()),"--output",str(out)]
                shared=self.lan_shared_var.get().strip() if hasattr(self,"lan_shared_var") else ""
                if shared:cmd += ["--shared",shared]
                real=self._real_cert_latest_path()
                if include_live and real.exists():cmd += ["--real-cert-evidence",str(real)]
                p=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True,timeout=180,creationflags=CREATE_NO_WINDOW)
                try:result=json.loads(out.read_text("utf-8-sig")) if out.exists() else json.loads(p.stdout)
                except Exception:result={"verdict":"FAIL","error":((p.stderr or p.stdout or "Target certification không có output")[-500:])}
                ok=p.returncode==0 and str(result.get("verdict") or "")!="FAIL"
                self.root.after(0,lambda:self._finish_target_machine_cert(ok,result))
            except Exception as exc:
                self.root.after(0,lambda e=str(exc):self._finish_target_machine_cert(False,{"verdict":"FAIL","error":e}))
            finally:
                for fp in (quota_tmp,lan_tmp):
                    try:
                        if fp:fp.unlink(missing_ok=True)
                    except Exception:pass
        threading.Thread(target=worker,daemon=True).start()

    def _finish_target_machine_cert(self,ok,result):
        self.busy=False;self._apply_target_machine_cert_status(result)
        verdict=str(result.get("verdict") or "FAIL")
        if ok:
            self.toast("Target certification · "+verdict,"success" if verdict=="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" else "warning")
        else:self.toast(str(result.get("error") or "Target-machine certification lỗi")[:300],"danger")

    def _apply_target_machine_cert_status(self,result=None):
        if not hasattr(self,"target_machine_cert_status"):return
        if result is None:
            try:result=json.loads(self._target_machine_cert_latest_path().read_text("utf-8-sig")) if self._target_machine_cert_latest_path().exists() else None
            except Exception:result=None
        if not result:
            self.target_machine_cert_status.configure(text="Chưa đánh giá · 7 stage: Host / Codex / Quota / Failover / LAN / Soak 6h / Soak 24h.",fg=C["text2"]);return
        sm=result.get("summary") or {};verdict=str(result.get("verdict") or "—");blockers=result.get("blockers") or []
        suffix=(" · thiếu "+",".join(str(x) for x in blockers[:4])) if blockers else " · đủ 7/7 production evidence"
        text=f"{verdict} · stage {sm.get('stages_pass','—')}/{sm.get('stages_total','—')}{suffix}"
        color=C["success"] if verdict=="PASS_TARGET_MACHINE_PRODUCTION_CERTIFIED" else (C["danger"] if verdict=="FAIL" else C["warning"])
        self.target_machine_cert_status.configure(text=text,fg=color)

    def _finish_lan_pool_action(self,data):
        self.busy=False;self._apply_lan_pool(data)
        self.toast(data.get("message","LAN Pool đã cập nhật.") if data.get("ok") else data.get("error","LAN Pool lỗi."),"success" if data.get("ok") else "danger")

    def _apply_lan_pool(self,data):
        if not data.get("ok"):
            if hasattr(self,"lan_status"):self.lan_status.configure(text=data.get("error","Không đọc được LAN Pool."),fg=C["danger"])
            return
        d=data.get("lan_pool") or {};summary=d.get("summary") or {}
        if data.get("shared_path") and not self.lan_shared_var.get().strip():self.lan_shared_var.set(str(data.get("shared_path")))
        for key,label in getattr(self,"lan_summary_labels",{}).items():
            val=int(summary.get(key,0) or 0);label.configure(text=str(val),fg=C["danger"] if key=="invalid_signatures" and val else (C["success"] if key=="online" and val else C["text"]))
        enabled=bool(data.get("enabled",d.get("enabled",False)));paired=bool(data.get("paired",False));local=d.get("local_node") or {}
        self.lan_status.configure(text=f"v25.51 · {'ENABLED' if enabled else 'DISABLED'} · {'PAIRED' if paired else 'UNPAIRED'} · node {local.get('node_name') or '—'} · signed registry · NO RAW CREDENTIAL SHARING",fg=C["success"] if enabled and paired and not summary.get("invalid_signatures") else C["warning"])
        self._apply_performance_scale_status()
        self._apply_real_codex_cert_status()
        self._apply_rotation_torture_status()
        self._apply_production_sim_status()
        self._apply_target_machine_cert_status()
        lines=["NODE                STATE      AGE    CAP  RUN  SIGNATURE","-"*86]
        for x in d.get("nodes") or []:
            lines.append(f"{str(x.get('node_name') or x.get('node_id'))[:18]:18} {str(x.get('state') or '—')[:10]:10} {str(x.get('age_sec','—')):>5}  {str(x.get('capacity','—')):>3}  {str(x.get('running_instances','—')):>3}  {'PASS' if x.get('signature_ok') else 'FAIL'}")
        if not (d.get("nodes") or []):lines.append("Chưa có heartbeat node nào trong shared registry.")
        lines += ["","ACTIVE PROJECT LEASES","-"*86]
        for x in d.get("leases") or []:
            lines.append(f"{str(x.get('project_label') or x.get('fingerprint',''))[:28]:28} node={str(x.get('node_name') or x.get('node_id'))[:18]:18} epoch={x.get('epoch','—')} {x.get('state','—')}")
        if not (d.get("leases") or []):lines.append("Không có project lease active.")
        lines += ["","FAILOVER CANDIDATES", "-"*86]
        for x in d.get("failover_candidates") or []:lines.append(f"{x.get('node_name') or x.get('node_id')} · capacity={x.get('capacity')} · running={x.get('running_instances')}")
        lines += ["","Security invariant: shared path chỉ có signed metadata; OAuth/API key/token/cookie/CODEX_HOME credentials ở lại máy sở hữu.","Project lease dựa trên normalized Git origin khi có, nên C:\\Project và D:\\Repo trên hai PC vẫn có cùng ownership domain."]
        self._set_text_readonly(self.lan_text,"\n".join(lines))
        self._apply_reliability_soak_status()

    def _build_project_orchestrator(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["orchestrator"] = page

        heading=tk.Frame(page,bg=C["bg"],height=44);heading.pack(fill="x");heading.pack_propagate(False)
        tk.Label(heading,text="Codex Project Orchestrator",bg=C["bg"],fg=C["text"],font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        HoverButton(heading,"LÀM MỚI",self.load_project_orchestrator_async,width=104,height=31,bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],font=("Segoe UI Semibold",8)).pack(side="right",pady=4)

        summary=tk.Frame(page,bg=C["bg"],height=62);summary.pack(fill="x",pady=(2,8));summary.pack_propagate(False)
        self.orch_summary_labels={}
        for key,title in (("projects","PROJECT"),("running","ĐANG CHẠY"),("ready","ONE-CLICK READY"),("blocked","BLOCKED")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12));val.pack(anchor="w",padx=10,pady=(1,4));self.orch_summary_labels[key]=val

        control=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=132);control.pack(fill="x",pady=(0,8));control.pack_propagate(False)
        tk.Label(control,text="ONE-CLICK PROJECT ENVIRONMENT",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=9)
        self.orch_project_var=tk.StringVar()
        self.orch_project_combo=ttk.Combobox(control,textvariable=self.orch_project_var,state="readonly",style="HMS.TCombobox")
        self.orch_project_combo.place(x=12,y=32,width=500,height=29)
        HoverButton(control,"PRE-FLIGHT",self.preflight_project_orchestrator_async,width=112,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=526,y=32)
        HoverButton(control,"MỞ MÔI TRƯỜNG",self.launch_project_orchestrator_async,width=148,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=650,y=32)
        self.orch_selected_status=tk.Label(control,text="Chọn project để HMS resolve Instance → Account → Model → Router → Workspace.",bg=C["surface"],fg=C["text2"],font=("Segoe UI Semibold",8),anchor="w")
        self.orch_selected_status.place(x=12,y=72,width=786,height=22)
        self.orch_plan_label=tk.Label(control,text="Identity Isolation + Security Hardening là hard gate. HMS không kill process không chứng minh ownership.",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7),anchor="w")
        self.orch_plan_label.place(x=12,y=99,width=786,height=22)

        self.orch_status=tk.Label(page,text="Project Orchestrator v25.42 · read-only status cho tới khi bấm MỞ MÔI TRƯỜNG",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w")
        self.orch_status.pack(fill="x",pady=(0,5))
        self.orch_scroll=ScrollableSettings(page);self.orch_scroll.pack(fill="both",expand=True);self.orch_grid=self.orch_scroll.inner

    def load_project_orchestrator_async(self):
        if hasattr(self,"orch_status"):self.orch_status.configure(text="Đang resolve toàn bộ project environment...",fg=C["muted"])
        def worker():
            data=self.backend("get_project_orchestrator",120);self.root.after(0,lambda:self._apply_project_orchestrator(data))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_project_orchestrator(self,data):
        self.project_orchestrator_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"orch_status"):self.orch_status.configure(text=data.get("error","Không đọc được Project Orchestrator."),fg=C["danger"])
            return
        d=data.get("project_orchestrator") or {};summary=d.get("summary") or {};projects=d.get("projects") or []
        for key in ("projects","running","ready","blocked"):
            if key in getattr(self,"orch_summary_labels",{}):
                v=int(summary.get(key,0) or 0);fg=C["danger"] if key=="blocked" and v else (C["success"] if key in ("running","ready") and v else C["text"])
                self.orch_summary_labels[key].configure(text=str(v),fg=fg)
        self.orch_project_choices={}
        labels=[]
        for row in projects:
            label=f"{row.get('name') or Path(str(row.get('project_dir') or 'project')).name}  ·  {row.get('readiness','—')}"
            labels.append(label);self.orch_project_choices[label]=row
        self.orch_project_combo["values"]=labels
        if labels and self.orch_project_var.get() not in labels:self.orch_project_var.set(labels[0])
        self.orch_status.configure(text=f"v25.42 · {summary.get('projects',0)} project · running {summary.get('running',0)} · ready {summary.get('ready',0)} · blocked {summary.get('blocked',0)} · RUNTIME Windows deferred",fg=C["warning"] if summary.get("blocked") else C["success"])
        self._render_project_orchestrator(projects)
        selected=d.get("selected")
        if selected:self._show_project_orchestrator_selected(selected)

    def _render_project_orchestrator(self,projects):
        for w in self.orch_grid.winfo_children():w.destroy()
        if not projects:
            tk.Label(self.orch_grid,text="Chưa có project được bind. Tạo Codex Instance / Project Affinity trước.",bg=C["bg"],fg=C["text2"],font=("Segoe UI Semibold",9)).pack(anchor="w",padx=8,pady=18);return
        for row in projects:
            card=tk.Frame(self.orch_grid,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=132);card.pack(fill="x",padx=(2,12),pady=5);card.pack_propagate(False)
            readiness=str(row.get("readiness") or "—");color=C["success"] if readiness in ("READY","RUNNING") else (C["warning"] if readiness=="ATTENTION" else C["danger"])
            tk.Label(card,text=str(row.get("name") or "Project"),bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",10)).place(x=14,y=10)
            tk.Label(card,text=f"{readiness} · {row.get('account') or '—'} · Health {row.get('account_health') if row.get('account_health') is not None else '—'} · 5h {row.get('hourly_remaining') if row.get('hourly_remaining') is not None else '—'}% · 7d {row.get('weekly_remaining') if row.get('weekly_remaining') is not None else '—'}%",bg=C["surface"],fg=color,font=("Segoe UI Semibold",8)).place(x=14,y=35)
            model=row.get("model") or "existing/default";reason=row.get("reasoning") or "—";profile=row.get("profile") or "BALANCED"
            tk.Label(card,text=f"INSTANCE  {row.get('instance_name') or row.get('instance_id') or '—'}  ·  MODEL {model} / {reason} / {profile}",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=14,y=59)
            blockers=", ".join(str(x) for x in (row.get("blockers") or []));warnings=", ".join(str(x) for x in (row.get("warnings") or []))
            detail=("BLOCK: "+blockers) if blockers else (("WARN: "+warnings) if warnings else "Hard gates PASS · stable endpoint/session affinity preserved")
            tk.Label(card,text=detail[:120],bg=C["surface"],fg=C["danger"] if blockers else (C["warning"] if warnings else C["muted"]),font=("Segoe UI",7)).place(x=14,y=81)
            tk.Label(card,text=str(row.get("project_dir") or "—")[:112],bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=14,y=105)
            project=str(row.get("project_dir") or "")
            HoverButton(card,"PREFLIGHT",lambda p=project:self.preflight_project_orchestrator_async(p),width=88,height=27,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(relx=1,x=-206,y=15)
            b=HoverButton(card,"MỞ",lambda p=project:self.launch_project_orchestrator_async(p),width=92,height=27,bg=C["primary"] if row.get("one_click_ready") else C["surface3"],hover=C["primary_hover"] if row.get("one_click_ready") else C["hover"],outline="" if row.get("one_click_ready") else C["border"],font=("Segoe UI Semibold",7))
            b.place(relx=1,x=-106,y=15);b.set_enabled(bool(row.get("one_click_ready")))

    def _current_orchestrator_project(self):
        label=self.orch_project_var.get().strip();row=getattr(self,"orch_project_choices",{}).get(label) or {}
        return str(row.get("project_dir") or "")

    def preflight_project_orchestrator_async(self,project=None):
        if self.busy:return
        project=(project or self._current_orchestrator_project()).strip()
        if not project:self.toast("Chưa chọn project.","warning");return
        self.busy=True;self.orch_selected_status.configure(text="Đang chạy hard-gate preflight...",fg=C["warning"])
        def worker():
            data=self.backend("preflight_project_orchestrator",120,payload={"project_dir":project});self.root.after(0,lambda:self._finish_project_orchestrator_action(data,False))
        threading.Thread(target=worker,daemon=True).start()

    def launch_project_orchestrator_async(self,project=None):
        if self.busy:return
        project=(project or self._current_orchestrator_project()).strip()
        if not project:self.toast("Chưa chọn project.","warning");return
        self.busy=True;self.orch_selected_status.configure(text="Đang mở nguyên môi trường Codex managed...",fg=C["warning"])
        def worker():
            data=self.backend("launch_project_orchestrator",180,payload={"project_dir":project});self.root.after(0,lambda:self._finish_project_orchestrator_action(data,True))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_project_orchestrator_action(self,data,launched=False):
        self.busy=False
        self._apply_project_orchestrator(data)
        if data.get("ok"):
            d=data.get("project_orchestrator") or {};selected=d.get("selected")
            if selected:self._show_project_orchestrator_selected(selected)
            self.toast(data.get("message","Project Orchestrator hoàn tất."),"success" if (not selected or selected.get("one_click_ready")) else "warning")
            if launched:
                self.root.after(180,self.load_instances_async);self.root.after(260,self.load_project_affinity_async)
        else:
            self.orch_selected_status.configure(text=data.get("error","Project Orchestrator lỗi."),fg=C["danger"]);self.toast(data.get("error","Project Orchestrator lỗi."),"danger")

    def _show_project_orchestrator_selected(self,row):
        blockers=row.get("blockers") or [];warnings=row.get("warnings") or []
        if blockers:
            self.orch_selected_status.configure(text="BLOCKED · "+", ".join(str(x) for x in blockers),fg=C["danger"])
        else:
            self.orch_selected_status.configure(text=f"{row.get('readiness','READY')} · {row.get('instance_name') or row.get('instance_id')} · {row.get('account')} · {row.get('model') or 'existing/default'} / {row.get('reasoning') or '—'}",fg=C["success"] if not warnings else C["warning"])
        steps=" → ".join(str(x.get("step")) for x in (row.get("plan") or [])) or "Không có mutation plan"
        self.orch_plan_label.configure(text=(steps+((" · WARN: "+", ".join(str(x) for x in warnings)) if warnings else ""))[:150])

    def _build_multi_codex_team(self):
        page=tk.Frame(self.content,bg=C["bg"]);self.pages["team"]=page
        heading=tk.Frame(page,bg=C["bg"],height=44);heading.pack(fill="x");heading.pack_propagate(False)
        tk.Label(heading,text="Multi-Codex Team",bg=C["bg"],fg=C["text"],font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        HoverButton(heading,"LÀM MỚI",self.load_multi_codex_team_async,width=104,height=31,bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],font=("Segoe UI Semibold",8)).pack(side="right",pady=4)

        summary=tk.Frame(page,bg=C["bg"],height=62);summary.pack(fill="x",pady=(2,8));summary.pack_propagate(False)
        self.team_summary_labels={}
        for key,title in (("teams","TEAM"),("members","MEMBER"),("ready","READY"),("blocked","BLOCKED")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1);box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12));val.pack(anchor="w",padx=10,pady=(1,4));self.team_summary_labels[key]=val

        editor=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=190);editor.pack(fill="x",pady=(0,8));editor.pack_propagate(False)
        tk.Label(editor,text="TEAM TOPOLOGY · Coder dùng project chính · Reviewer/Tester phải dùng workspace/worktree riêng",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=8)
        self.team_project_var=tk.StringVar();self.team_name_var=tk.StringVar();self.team_coder_var=tk.StringVar();self.team_reviewer_var=tk.StringVar();self.team_tester_var=tk.StringVar()
        self.team_project_combo=ttk.Combobox(editor,textvariable=self.team_project_var,state="readonly",style="HMS.TCombobox");self.team_project_combo.place(x=12,y=31,width=386,height=29)
        tk.Entry(editor,textvariable=self.team_name_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=410,y=31,width=388,height=29)
        tk.Label(editor,text="Project",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=12,y=62)
        tk.Label(editor,text="Tên team",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=410,y=62)
        tk.Label(editor,text="CODER",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=83)
        tk.Label(editor,text="REVIEWER",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=280,y=83)
        tk.Label(editor,text="TESTER",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=548,y=83)
        self.team_coder_combo=ttk.Combobox(editor,textvariable=self.team_coder_var,state="readonly",style="HMS.TCombobox");self.team_coder_combo.place(x=12,y=102,width=250,height=29)
        self.team_reviewer_combo=ttk.Combobox(editor,textvariable=self.team_reviewer_var,state="readonly",style="HMS.TCombobox");self.team_reviewer_combo.place(x=280,y=102,width=250,height=29)
        self.team_tester_combo=ttk.Combobox(editor,textvariable=self.team_tester_var,state="readonly",style="HMS.TCombobox");self.team_tester_combo.place(x=548,y=102,width=250,height=29)
        HoverButton(editor,"LƯU TEAM",self.save_multi_codex_team_async,width=110,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=12,y=145)
        HoverButton(editor,"PREFLIGHT",self.preflight_multi_codex_team_async,width=105,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=132,y=145)
        HoverButton(editor,"MỞ TEAM",self.launch_multi_codex_team_async,width=112,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=247,y=145)
        self.team_selected_status=tk.Label(editor,text="Role rebind chỉ được phép khi các instance liên quan đã dừng; topology change tăng epoch, không silent takeover.",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7),anchor="w");self.team_selected_status.place(x=375,y=145,width=423,height=29)
        self.team_project_combo.bind("<<ComboboxSelected>>",lambda e:self._select_multi_codex_team_project())

        self.team_status=tk.Label(page,text="Multi-Codex Team v25.43 · distinct account/workspace · Identity + Security hard gates · Windows runtime deferred",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w");self.team_status.pack(fill="x",pady=(0,5))
        self.team_scroll=ScrollableSettings(page);self.team_scroll.pack(fill="both",expand=True);self.team_grid=self.team_scroll.inner

    def load_multi_codex_team_async(self):
        if hasattr(self,"team_status"):self.team_status.configure(text="Đang resolve team topology + worktree ownership...",fg=C["muted"])
        def worker():
            data=self.backend("get_multi_codex_team",120);self.root.after(0,lambda:self._apply_multi_codex_team(data))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_multi_codex_team(self,data):
        self.multi_codex_team_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"team_status"):self.team_status.configure(text=data.get("error","Không đọc được Multi-Codex Team."),fg=C["danger"])
            return
        d=data.get("multi_codex_team") or {};summary=d.get("summary") or {};teams=d.get("teams") or []
        for key in ("teams","members","ready","blocked"):
            if key in getattr(self,"team_summary_labels",{}):
                v=int(summary.get(key,0) or 0);self.team_summary_labels[key].configure(text=str(v),fg=C["danger"] if key=="blocked" and v else (C["success"] if key=="ready" and v else C["text"]))
        self.team_project_choices={};project_labels=[]
        for row in d.get("project_catalog") or []:
            label=f"{row.get('name') or Path(str(row.get('project_dir') or 'project')).name} · {row.get('project_dir')}";project_labels.append(label);self.team_project_choices[label]=row
        self.team_project_combo["values"]=project_labels
        self.team_instance_choices={};inst_labels=[]
        for row in d.get("instance_catalog") or []:
            label=f"{row.get('name') or row.get('id')} · {row.get('account')} · {Path(str(row.get('project_dir') or 'workspace')).name}";inst_labels.append(label);self.team_instance_choices[label]=row
        choices=[""]+inst_labels
        for combo in (self.team_coder_combo,self.team_reviewer_combo,self.team_tester_combo):combo["values"]=choices
        if project_labels and self.team_project_var.get() not in project_labels:self.team_project_var.set(project_labels[0])
        self.team_existing_by_project={str(x.get("project_dir") or "").lower():x for x in teams}
        self._select_multi_codex_team_project()
        self.team_status.configure(text=f"v25.43 · {summary.get('teams',0)} team · {summary.get('members',0)} member · ready {summary.get('ready',0)} · blocked {summary.get('blocked',0)} · runtime deferred",fg=C["warning"] if summary.get("blocked") else C["success"])
        self._render_multi_codex_team(teams)
        selected=d.get("selected")
        if selected:self._show_multi_codex_team_selected(selected)

    def _team_label_for_instance(self,instance_id):
        iid=str(instance_id or "")
        for label,row in getattr(self,"team_instance_choices",{}).items():
            if str(row.get("id") or "")==iid:return label
        return ""

    def _select_multi_codex_team_project(self):
        label=self.team_project_var.get().strip();p=(getattr(self,"team_project_choices",{}).get(label) or {}).get("project_dir") or ""
        existing=getattr(self,"team_existing_by_project",{}).get(str(p).lower())
        if existing:
            self.team_name_var.set(str(existing.get("name") or ""));roles={str(m.get("role") or ""):m for m in existing.get("members") or []}
            self.team_coder_var.set(self._team_label_for_instance((roles.get("CODER") or {}).get("instance_id")))
            self.team_reviewer_var.set(self._team_label_for_instance((roles.get("REVIEWER") or {}).get("instance_id")))
            self.team_tester_var.set(self._team_label_for_instance((roles.get("TESTER") or {}).get("instance_id")))
            self._show_multi_codex_team_selected(existing)
        else:
            self.team_name_var.set((Path(str(p)).name+" Codex Team") if p else "");self.team_coder_var.set("");self.team_reviewer_var.set("");self.team_tester_var.set("")
            self.team_selected_status.configure(text="Chọn CODER + ít nhất REVIEWER hoặc TESTER. Mỗi role phải dùng instance/workspace riêng.",fg=C["muted"])

    def _current_multi_codex_team_project(self):
        return str((getattr(self,"team_project_choices",{}).get(self.team_project_var.get().strip()) or {}).get("project_dir") or "")

    def _team_instance_id(self,var):
        return str((getattr(self,"team_instance_choices",{}).get(var.get().strip()) or {}).get("id") or "")

    def save_multi_codex_team_async(self):
        if self.busy:return
        project=self._current_multi_codex_team_project()
        if not project:self.toast("Chưa chọn project.","warning");return
        payload={"project_dir":project,"name":self.team_name_var.get().strip(),"coder_instance_id":self._team_instance_id(self.team_coder_var),"reviewer_instance_id":self._team_instance_id(self.team_reviewer_var),"tester_instance_id":self._team_instance_id(self.team_tester_var)}
        self.busy=True;self.team_selected_status.configure(text="Đang validate topology + explicit epoch...",fg=C["warning"])
        def worker():
            data=self.backend("save_multi_codex_team",120,payload=payload);self.root.after(0,lambda:self._finish_multi_codex_team_action(data,False))
        threading.Thread(target=worker,daemon=True).start()

    def preflight_multi_codex_team_async(self,project=None):
        if self.busy:return
        project=(project or self._current_multi_codex_team_project()).strip()
        if not project:self.toast("Chưa chọn project/team.","warning");return
        self.busy=True;self.team_selected_status.configure(text="Đang preflight role/workspace/ownership...",fg=C["warning"])
        def worker():
            data=self.backend("preflight_multi_codex_team",120,payload={"project_dir":project});self.root.after(0,lambda:self._finish_multi_codex_team_action(data,False))
        threading.Thread(target=worker,daemon=True).start()

    def launch_multi_codex_team_async(self,project=None):
        if self.busy:return
        project=(project or self._current_multi_codex_team_project()).strip()
        if not project:self.toast("Chưa chọn project/team.","warning");return
        self.busy=True;self.team_selected_status.configure(text="Đang mở Coder / Reviewer / Tester theo ownership guard...",fg=C["warning"])
        def worker():
            data=self.backend("launch_multi_codex_team",240,payload={"project_dir":project});self.root.after(0,lambda:self._finish_multi_codex_team_action(data,True))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_multi_codex_team_action(self,data,launched=False):
        self.busy=False;self._apply_multi_codex_team(data)
        if data.get("ok"):
            d=data.get("multi_codex_team") or {};selected=d.get("selected")
            if selected:self._show_multi_codex_team_selected(selected)
            self.toast(data.get("message","Multi-Codex Team hoàn tất."),"success" if (not selected or selected.get("one_click_ready")) else "warning")
            if launched:self.root.after(180,self.load_instances_async);self.root.after(260,self.load_project_orchestrator_async)
        else:
            self.team_selected_status.configure(text=data.get("error","Multi-Codex Team lỗi."),fg=C["danger"]);self.toast(data.get("error","Multi-Codex Team lỗi."),"danger")

    def _show_multi_codex_team_selected(self,row):
        blockers=row.get("blockers") or [];warnings=row.get("warnings") or []
        roles=" · ".join(f"{m.get('role')}={m.get('instance_name') or m.get('instance_id')}" for m in row.get("members") or [])
        if blockers:self.team_selected_status.configure(text=("BLOCKED · "+", ".join(str(x) for x in blockers))[:115],fg=C["danger"])
        else:self.team_selected_status.configure(text=(f"{row.get('readiness','READY')} · epoch {row.get('epoch',1)} · {roles}")[:115],fg=C["success"] if not warnings else C["warning"])

    def _render_multi_codex_team(self,teams):
        for w in self.team_grid.winfo_children():w.destroy()
        if not teams:
            tk.Label(self.team_grid,text="Chưa có team. Chuẩn bị các Codex instance/worktree riêng rồi bind Coder + Reviewer/Tester ở phía trên.",bg=C["bg"],fg=C["text2"],font=("Segoe UI Semibold",9)).pack(anchor="w",padx=8,pady=18);return
        for row in teams:
            card=tk.Frame(self.team_grid,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=142);card.pack(fill="x",padx=(2,12),pady=5);card.pack_propagate(False)
            readiness=str(row.get("readiness") or "—");color=C["success"] if readiness in ("READY","RUNNING","PARTIAL_RUNNING") else C["danger"]
            tk.Label(card,text=str(row.get("name") or "Codex Team"),bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",10)).place(x=14,y=10)
            tk.Label(card,text=f"{readiness} · epoch {row.get('epoch',1)} · {row.get('running_members',0)}/{row.get('member_count',0)} running · topology {str(row.get('topology_hash') or '')[:10]}",bg=C["surface"],fg=color,font=("Segoe UI Semibold",8)).place(x=14,y=35)
            y=59
            for m in row.get("members") or []:
                line=f"{m.get('role','—'):8}  {m.get('instance_name') or m.get('instance_id')} · {m.get('account')} · {Path(str(m.get('workspace') or 'workspace')).name} · {'RUNNING' if m.get('client_running') else 'OFF'}"
                tk.Label(card,text=line[:112],bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=14,y=y);y+=18
            detail=", ".join(str(x) for x in (row.get("blockers") or [])) or (", ".join(str(x) for x in (row.get("warnings") or [])) or "Role isolation PASS · no shared workspace · no silent takeover")
            tk.Label(card,text=detail[:110],bg=C["surface"],fg=C["danger"] if row.get("blockers") else (C["warning"] if row.get("warnings") else C["muted"]),font=("Segoe UI",7)).place(x=14,y=116)
            project=str(row.get("project_dir") or "")
            HoverButton(card,"PREFLIGHT",lambda p=project:self.preflight_multi_codex_team_async(p),width=88,height=27,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(relx=1,x=-206,y=15)
            b=HoverButton(card,"MỞ TEAM",lambda p=project:self.launch_multi_codex_team_async(p),width=92,height=27,bg=C["primary"] if row.get("one_click_ready") else C["surface3"],hover=C["primary_hover"] if row.get("one_click_ready") else C["hover"],outline="" if row.get("one_click_ready") else C["border"],font=("Segoe UI Semibold",7));b.place(relx=1,x=-106,y=15);b.set_enabled(bool(row.get("one_click_ready")))

    def _build_projects(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["projects"] = page

        heading=tk.Frame(page,bg=C["bg"],height=44); heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading,text="Codex Project Affinity",bg=C["bg"],fg=C["text"],font=("Segoe UI Semibold",12)).pack(side="left",pady=7)
        HoverButton(heading,"LÀM MỚI",self.load_project_affinity_async,width=106,height=31,bg=C["surface"],hover=C["surface3"],outline=C["border_soft"],font=("Segoe UI Semibold",8)).pack(side="right",pady=4)

        summary=tk.Frame(page,bg=C["bg"],height=62); summary.pack(fill="x",pady=(2,8)); summary.pack_propagate(False)
        self.project_summary_labels={}
        for key,title in (("total","PROJECT"),("running","ĐANG CHẠY"),("healthy","READY"),("attention","CẦN XỬ LÝ")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1); box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12)); val.pack(anchor="w",padx=10,pady=(1,4)); self.project_summary_labels[key]=val

        editor=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=146); editor.pack(fill="x",pady=(0,8)); editor.pack_propagate(False)
        tk.Label(editor,text="PROJECT → INSTANCE → PRIMARY ACCOUNT → FALLBACK",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=8)
        self.project_path_var=tk.StringVar(); self.project_instance_var=tk.StringVar(); self.project_fallback_var=tk.StringVar(); self.project_name_var=tk.StringVar()
        tk.Entry(editor,textvariable=self.project_path_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=12,y=31,width=360,height=28)
        HoverButton(editor,"CHỌN PROJECT",self.browse_affinity_project,width=112,height=28,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=380,y=31)
        self.project_instance_combo=ttk.Combobox(editor,textvariable=self.project_instance_var,state="readonly",style="HMS.TCombobox"); self.project_instance_combo.place(x=500,y=31,width=305,height=28)
        tk.Label(editor,text="Fallback ACC (phân cách bằng dấu phẩy)",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=12,y=68)
        tk.Entry(editor,textvariable=self.project_fallback_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8)).place(x=12,y=87,width=430,height=28)
        HoverButton(editor,"LƯU AFFINITY",self.save_project_affinity_async,width=128,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).place(x=454,y=86)
        HoverButton(editor,"INSTANCE MỚI",self.project_to_new_instance,width=118,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=590,y=86)
        tk.Label(editor,text="Primary + fallback nằm phía sau stable endpoint của instance. Đổi account không cần đổi Codex config; runtime thật sẽ được chứng nhận sau.",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=12,y=120)

        self.project_status=tk.Label(page,text="Project Affinity + Seamless Router · stable endpoint · session affinity · fail-closed",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7)); self.project_status.pack(anchor="w",pady=(0,6))
        self.projects_scroll=ScrollableSettings(page); self.projects_scroll.pack(fill="both",expand=True); self.projects_grid=self.projects_scroll.inner

    def _build_instances(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["instances"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Codex Multi-Instance", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.instances_refresh_btn = HoverButton(
            heading, "LÀM MỚI", self.load_instances_async, width=106, height=31,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"],
            font=("Segoe UI Semibold", 8))
        self.instances_refresh_btn.pack(side="right", pady=4)
        self.instances_audit_btn = HoverButton(
            heading, "AUDIT ISOLATION", self.audit_identity_async, width=132, height=31,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"],
            font=("Segoe UI Semibold", 8))
        self.instances_audit_btn.pack(side="right", padx=(0,8), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.instance_summary_labels = {}
        for key,title in (("total","INSTANCE"),("running","ĐANG CHẠY"),("ready","ISOLATION PASS"),("conflicts","BLOCKED")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12))
            val.pack(anchor="w",padx=10,pady=(1,4)); self.instance_summary_labels[key]=val

        create=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=118)
        create.pack(fill="x",pady=(0,8)); create.pack_propagate(False)
        tk.Label(create,text="TẠO INSTANCE CÔ LẬP",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).place(x=12,y=8)
        self.instance_name_var=tk.StringVar()
        self.instance_project_var=tk.StringVar()
        self.instance_account_var=tk.StringVar()
        self.instance_mode_var=tk.StringVar(value="cli")
        self.instance_name_entry=tk.Entry(create,textvariable=self.instance_name_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8))
        self.instance_name_entry.place(x=12,y=31,width=150,height=28)
        self.instance_project_entry=tk.Entry(create,textvariable=self.instance_project_var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",8))
        self.instance_project_entry.place(x=172,y=31,width=300,height=28)
        HoverButton(create,"CHỌN PROJECT",self.browse_instance_project,width=112,height=28,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(x=480,y=31)
        self.instance_account_combo=ttk.Combobox(create,textvariable=self.instance_account_var,state="readonly",style="HMS.TCombobox",width=28)
        self.instance_account_combo.place(x=600,y=31,width=205,height=28)
        self.instance_mode_combo=ttk.Combobox(create,textvariable=self.instance_mode_var,values=["cli","desktop"],state="readonly",style="HMS.TCombobox",width=10)
        self.instance_mode_combo.place(x=12,y=72,width=110,height=28)
        HoverButton(create,"TẠO INSTANCE",self.create_instance_async,width=142,height=30,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",8)).place(x=132,y=71)
        tk.Label(create,text="Mỗi instance khóa Project + identity chính; Router port/endpoint giữ cố định và có thể chứa fallback pool an toàn. Không có nút xóa destructive.",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=286,y=78)

        self.instances_status=tk.Label(page,text="CODEX-ONLY · identity fingerprint · prelaunch isolation audit · credential snapshot sync",bg=C["bg"],fg=C["muted"],font=("Segoe UI",7))
        self.instances_status.pack(anchor="w",pady=(0,6))
        self.instances_scroll=ScrollableSettings(page); self.instances_scroll.pack(fill="both",expand=True)
        self.instances_grid=self.instances_scroll.inner

    def _build_self_healing(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["selfheal"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Codex Self-Healing", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.selfheal_repair_btn = HoverButton(
            heading, "SỬA AN TOÀN", self.repair_self_healing_async, width=126, height=31,
            bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 8),
            tooltip="Chỉ áp dụng repair được đánh dấu auto-safe. Không kill process nếu ownership chưa được chứng minh."
        )
        self.selfheal_repair_btn.pack(side="right", pady=4)
        self.selfheal_audit_btn = HoverButton(
            heading, "AUDIT", self.audit_self_healing_async, width=92, height=31,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"], font=("Segoe UI Semibold", 8))
        self.selfheal_audit_btn.pack(side="right", padx=(0,8), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.selfheal_summary_labels={}
        for key,title in (("issues","ISSUES"),("safe","AUTO-SAFE"),("operator","OPERATOR"),("verdict","VERDICT")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="—",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12))
            val.pack(anchor="w",padx=10,pady=(1,4));self.selfheal_summary_labels[key]=val

        self.selfheal_status=tk.Label(page,text="Evidence trước sửa · readback sau sửa · rollback khi action lỗi · không kill process lạ.",
                                     bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w")
        self.selfheal_status.pack(fill="x",pady=(0,6))

        card=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        card.pack(fill="both",expand=True)
        tk.Label(card,text="SELF-HEALING FINDINGS · v25.39",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.selfheal_text=tk.Text(card,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",8),wrap="word")
        self.selfheal_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.selfheal_text.configure(state="disabled")

    def load_self_healing_async(self):
        if hasattr(self,"selfheal_status"): self.selfheal_status.configure(text="Đang đọc Self-Healing state...",fg=C["muted"])
        def worker():
            data=self.backend("get_self_healing",90);self.root.after(0,lambda:self._apply_self_healing(data))
        threading.Thread(target=worker,daemon=True).start()

    def audit_self_healing_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"selfheal_audit_btn"):self.selfheal_audit_btn.set_enabled(False)
        if hasattr(self,"selfheal_status"):self.selfheal_status.configure(text="Đang audit Router/port/PID/config/binding/credential/model policy...",fg=C["warning"])
        def worker():
            data=self.backend("audit_self_healing",120);self.root.after(0,lambda:self._finish_self_healing(data))
        threading.Thread(target=worker,daemon=True).start()

    def repair_self_healing_async(self):
        if self.busy:return
        if not messagebox.askyesno("Codex Self-Healing",
            "Áp dụng các repair được đánh dấu AUTO-SAFE?\n\nHMS sẽ tạo evidence trước sửa, readback sau sửa và không kill process nếu chưa chứng minh ownership.",parent=self.root):return
        self.busy=True
        if hasattr(self,"selfheal_repair_btn"):self.selfheal_repair_btn.set_enabled(False)
        if hasattr(self,"selfheal_status"):self.selfheal_status.configure(text="Đang sửa an toàn + readback + rollback khi cần...",fg=C["warning"])
        def worker():
            data=self.backend("repair_self_healing",180);self.root.after(0,lambda:self._finish_self_healing(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_self_healing(self,data):
        self.busy=False
        if hasattr(self,"selfheal_audit_btn"):self.selfheal_audit_btn.set_enabled(True)
        if hasattr(self,"selfheal_repair_btn"):self.selfheal_repair_btn.set_enabled(True)
        self._apply_self_healing(data)
        self.toast(data.get("message","Self-Healing hoàn tất.") if data.get("ok") else data.get("error","Self-Healing lỗi."),"success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(180,self.load_instances_async)
            self.root.after(260,self.load_project_affinity_async)

    def _apply_self_healing(self,data):
        self.self_healing_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"selfheal_status"):self.selfheal_status.configure(text=data.get("error","Không đọc được Self-Healing."),fg=C["danger"])
            return
        d=data.get("self_healing") or {}
        summary=d.get("summary") or {};verdict=str(d.get("verdict") or "NOT_AUDITED")
        if hasattr(self,"selfheal_summary_labels"):
            self.selfheal_summary_labels["issues"].configure(text=str(summary.get("issues",0)))
            self.selfheal_summary_labels["safe"].configure(text=str(summary.get("auto_safe",0)),fg=C["success"] if summary.get("auto_safe") else C["text"])
            self.selfheal_summary_labels["operator"].configure(text=str(summary.get("operator",0)),fg=C["warning"] if summary.get("operator") else C["text"])
            vcolor=C["success"] if verdict=="PASS" else (C["danger"] if verdict=="BLOCKED" else C["warning"])
            self.selfheal_summary_labels["verdict"].configure(text=verdict,fg=vcolor)
        evidence=d.get("evidence_dir") or "—"
        actions=d.get("actions") or []
        if hasattr(self,"selfheal_status"):
            self.selfheal_status.configure(text=f"{verdict} · issue {summary.get('issues',0)} · action {len(actions)} · evidence: {evidence}",fg=C["success"] if verdict=="PASS" else C["warning"])
        lines=["SEV      SCOPE                    CODE                         ACTION / DETAIL","-"*104]
        for x in d.get("issues") or []:
            sev=str(x.get("severity",""));scope=str(x.get("scope",""));code=str(x.get("code",""));act=str(x.get("action") or "OPERATOR")
            lines.append(f"{sev:<8} {scope[:24]:24} {code[:28]:28} {act}")
            lines.append("         "+str(x.get("detail") or "")[:180])
        if not (d.get("issues") or []):lines.append("PASS · Không phát hiện runtime drift trong snapshot hiện tại.")
        if actions:
            lines += ["","ACTIONS APPLIED","-"*104]
            for a in actions:
                lines.append(f"{'PASS' if a.get('ok') else 'FAIL':<5} {str(a.get('scope','')):24} {str(a.get('action','')):28} {str(a.get('message') or a.get('error') or '')[:180]}")
        lines += ["", "Invariant: process không chứng minh ownership => KHÔNG KILL. Không có destructive delete action.",
                  "Windows Codex runtime truth vẫn là DEFERRED_BY_OPERATOR cho tới khi test thật."]
        self._set_text_readonly(self.selfheal_text,"\n".join(lines))

    def _build_security_hardening(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["security"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Codex Security Hardening", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.security_harden_btn = HoverButton(
            heading, "HARDEN", self.harden_security_async, width=104, height=31,
            bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 8),
            tooltip="Migrate plaintext key sang protected storage, harden ACL và tạo missing integrity seals. Không auto-reseal mismatch."
        )
        self.security_harden_btn.pack(side="right", pady=4)
        self.security_audit_btn = HoverButton(
            heading, "AUDIT", self.audit_security_async, width=88, height=31,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"], font=("Segoe UI Semibold", 8))
        self.security_audit_btn.pack(side="right", padx=(0,8), pady=4)
        self.security_seal_btn = HoverButton(
            heading, "RESEAL", self.reseal_security_async, width=88, height=31,
            bg=C["surface"], hover=C["surface3"], outline=C["border_soft"], font=("Segoe UI Semibold", 8),
            tooltip="Operator-only. Chỉ reseal sau khi đã xác minh file mismatch là thay đổi hợp lệ."
        )
        self.security_seal_btn.pack(side="right", padx=(0,8), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.security_summary_labels={}
        for key,title in (("issues","ISSUES"),("safe","AUTO-SAFE"),("operator","OPERATOR"),("verdict","VERDICT")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="—",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12))
            val.pack(anchor="w",padx=10,pady=(1,4));self.security_summary_labels[key]=val

        self.security_status=tk.Label(
            page,text="Credential Manager/DPAPI · ACL current-user isolation · reparse guard · HMAC integrity seal · strict redaction",
            bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w")
        self.security_status.pack(fill="x",pady=(0,6))

        card=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        card.pack(fill="both",expand=True)
        tk.Label(card,text="SECURITY FINDINGS · v25.40",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.security_text=tk.Text(card,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",8),wrap="word")
        self.security_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.security_text.configure(state="disabled")

    def load_security_async(self):
        if hasattr(self,"security_status"):self.security_status.configure(text="Đang đọc Security state...",fg=C["muted"])
        def worker():
            data=self.backend("get_security",90);self.root.after(0,lambda:self._apply_security(data))
        threading.Thread(target=worker,daemon=True).start()

    def audit_security_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"security_audit_btn"):self.security_audit_btn.set_enabled(False)
        if hasattr(self,"security_status"):self.security_status.configure(text="Đang audit protected secrets / ACL / reparse / integrity seals...",fg=C["warning"])
        def worker():
            data=self.backend("audit_security",120);self.root.after(0,lambda:self._finish_security(data))
        threading.Thread(target=worker,daemon=True).start()

    def harden_security_async(self):
        if self.busy:return
        if not messagebox.askyesno("Codex Security Hardening",
            "Áp dụng các action AUTO-SAFE?\n\nHMS sẽ migrate Router key khỏi JSON plaintext sang Windows protected storage, harden ACL và tạo seal còn thiếu.\n\nIntegrity mismatch và reparse point KHÔNG được tự chấp nhận/sửa.",parent=self.root):return
        self.busy=True
        if hasattr(self,"security_harden_btn"):self.security_harden_btn.set_enabled(False)
        if hasattr(self,"security_status"):self.security_status.configure(text="Đang harden protected storage + ACL + missing seals...",fg=C["warning"])
        def worker():
            data=self.backend("harden_security",180);self.root.after(0,lambda:self._finish_security(data))
        threading.Thread(target=worker,daemon=True).start()

    def reseal_security_async(self):
        if self.busy:return
        if not messagebox.askyesno("RESEAL Integrity Baseline",
            "RESEAL sẽ chấp nhận trạng thái file hiện tại làm baseline integrity mới.\n\nChỉ bấm CÓ nếu bạn đã xác minh mọi file mismatch là thay đổi hợp lệ do HMS/người vận hành tạo ra.\n\nHMS không tự thực hiện hành động này.",parent=self.root):return
        self.busy=True
        if hasattr(self,"security_seal_btn"):self.security_seal_btn.set_enabled(False)
        def worker():
            data=self.backend("seal_security",180);self.root.after(0,lambda:self._finish_security(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_security(self,data):
        self.busy=False
        for n in ("security_audit_btn","security_harden_btn","security_seal_btn"):
            if hasattr(self,n):getattr(self,n).set_enabled(True)
        self._apply_security(data)
        self.toast(data.get("message","Security action hoàn tất.") if data.get("ok") else data.get("error","Security action lỗi."),"success" if data.get("ok") else "danger")

    def _apply_security(self,data):
        self.security_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"security_status"):self.security_status.configure(text=data.get("error","Không đọc được Security state."),fg=C["danger"])
            return
        d=data.get("security") or {};summary=d.get("summary") or {};verdict=str(d.get("verdict") or "NOT_AUDITED")
        if hasattr(self,"security_summary_labels"):
            self.security_summary_labels["issues"].configure(text=str(summary.get("issues",0)))
            self.security_summary_labels["safe"].configure(text=str(summary.get("auto_safe",0)),fg=C["success"] if summary.get("auto_safe") else C["text"])
            self.security_summary_labels["operator"].configure(text=str(summary.get("operator",0)),fg=C["warning"] if summary.get("operator") else C["text"])
            vcolor=C["success"] if verdict=="PASS" else (C["danger"] if verdict=="BLOCKED" else C["warning"])
            self.security_summary_labels["verdict"].configure(text=verdict,fg=vcolor)
        evidence=d.get("evidence_dir") or "—";actions=d.get("actions") or []
        if hasattr(self,"security_status"):
            self.security_status.configure(text=f"{verdict} · issue {summary.get('issues',0)} · action {len(actions)} · evidence: {evidence}",fg=C["success"] if verdict=="PASS" else C["warning"])
        lines=["SEV      CODE                              ACTION / DETAIL","-"*104]
        for x in d.get("issues") or []:
            sev=str(x.get("severity",""));code=str(x.get("code",""));act=str(x.get("action") or "OPERATOR")
            lines.append(f"{sev:<8} {code[:34]:34} {act}")
            lines.append("         "+str(x.get("detail") or "")[:190])
        if not (d.get("issues") or []):lines.append("PASS · Protected secret refs, ACL, reparse guard, seals và redaction đều đạt audit hiện tại.")
        if actions:
            lines += ["","ACTIONS APPLIED","-"*104]
            for a in actions:lines.append(f"{'PASS' if a.get('ok') else 'FAIL':<5} {str(a.get('action','')):30} {str(a.get('message') or a.get('error') or '')[:190]}")
        lines += ["","Invariant: integrity mismatch KHÔNG auto-reseal; reparse point KHÔNG auto-delete; secret value KHÔNG xuất hiện trong snapshot/evidence.",
                  "Runtime Windows Codex vẫn DEFERRED_BY_OPERATOR cho tới khi test thật."]
        self._set_text_readonly(self.security_text,"\n".join(lines))

    def _build_unified_diagnostics(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["diagnostics"] = page

        heading = tk.Frame(page, bg=C["bg"], height=44)
        heading.pack(fill="x"); heading.pack_propagate(False)
        tk.Label(heading, text="Unified Diagnostics", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(side="left", pady=7)
        self.unified_diag_refresh_btn = HoverButton(
            heading, "LÀM MỚI TIMELINE", self.refresh_unified_diagnostics_async,
            width=144, height=31, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8),
            tooltip="Hợp nhất request/router/quota/circuit/self-healing/security metadata. Không đọc prompt/request body/secret."
        )
        self.unified_diag_refresh_btn.pack(side="right", pady=4)
        self.unified_diag_bundle_btn = HoverButton(
            heading, "GÓI CHẨN ĐOÁN", self.diagnostics_bundle_async,
            width=132, height=31, bg=C["surface"], hover=C["surface3"],
            outline=C["border_soft"], font=("Segoe UI Semibold", 8)
        )
        self.unified_diag_bundle_btn.pack(side="right", padx=(0,7), pady=4)

        summary = tk.Frame(page, bg=C["bg"], height=62)
        summary.pack(fill="x", pady=(2,8)); summary.pack_propagate(False)
        self.unified_diag_summary_labels = {}
        for key,title in (("requests","REQUEST"),("errors","ERROR"),("failovers","FAILOVER"),("circuit","CIRCUIT OPEN")):
            box=tk.Frame(summary,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=(0,6))
            tk.Label(box,text=title,bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(7,0))
            val=tk.Label(box,text="0",bg=C["surface"],fg=C["text"],font=("Segoe UI Semibold",12))
            val.pack(anchor="w",padx=10,pady=(1,4));self.unified_diag_summary_labels[key]=val

        self.unified_diag_status=tk.Label(
            page,text="METADATA ONLY · prompt/request body/tool arguments/secret không được đưa vào timeline",
            bg=C["bg"],fg=C["muted"],font=("Segoe UI",7),anchor="w"
        )
        self.unified_diag_status.pack(fill="x",pady=(0,6))

        upper=tk.Frame(page,bg=C["bg"],height=118);upper.pack(fill="x",pady=(0,8));upper.pack_propagate(False)
        layer_card=tk.Frame(upper,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        layer_card.pack(side="left",fill="both",expand=True,padx=(0,6))
        tk.Label(layer_card,text="LAYER HEALTH",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.unified_diag_layers=tk.Label(layer_card,text="—",bg=C["surface"],fg=C["text2"],font=("Consolas",8),justify="left",anchor="nw")
        self.unified_diag_layers.pack(fill="both",expand=True,padx=10,pady=(0,8))
        account_card=tk.Frame(upper,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        account_card.pack(side="left",fill="both",expand=True)
        tk.Label(account_card,text="ACCOUNT SIGNALS",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.unified_diag_accounts=tk.Label(account_card,text="—",bg=C["surface"],fg=C["text2"],font=("Consolas",8),justify="left",anchor="nw")
        self.unified_diag_accounts.pack(fill="both",expand=True,padx=10,pady=(0,8))

        card=tk.Frame(page,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        card.pack(fill="both",expand=True)
        tk.Label(card,text="UNIFIED REQUEST / ROUTER TIMELINE · v25.41",bg=C["surface"],fg=C["muted"],font=("Segoe UI Semibold",7)).pack(anchor="w",padx=10,pady=(8,3))
        self.unified_diag_text=tk.Text(card,bg="#111827",fg=C["text2"],relief="flat",bd=0,font=("Consolas",8),wrap="none")
        self.unified_diag_text.pack(fill="both",expand=True,padx=8,pady=(0,8));self.unified_diag_text.configure(state="disabled")

    def load_unified_diagnostics_async(self):
        if hasattr(self,"unified_diag_status"):
            self.unified_diag_status.configure(text="Đang đọc Unified Diagnostics...",fg=C["muted"])
        def worker():
            data=self.backend("get_unified_diagnostics",90);self.root.after(0,lambda:self._apply_unified_diagnostics(data))
        threading.Thread(target=worker,daemon=True).start()

    def refresh_unified_diagnostics_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"unified_diag_refresh_btn"):self.unified_diag_refresh_btn.set_enabled(False)
        if hasattr(self,"unified_diag_status"):self.unified_diag_status.configure(text="Đang hợp nhất timeline request/router/quota/circuit/self-healing/security...",fg=C["warning"])
        def worker():
            data=self.backend("refresh_unified_diagnostics",120);self.root.after(0,lambda:self._finish_unified_diagnostics(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_unified_diagnostics(self,data):
        self.busy=False
        if hasattr(self,"unified_diag_refresh_btn"):self.unified_diag_refresh_btn.set_enabled(True)
        self._apply_unified_diagnostics(data)
        self.toast(data.get("message","Unified Diagnostics đã làm mới.") if data.get("ok") else data.get("error","Unified Diagnostics lỗi."),"success" if data.get("ok") else "danger")

    def _apply_unified_diagnostics(self,data):
        self.unified_diagnostics_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"unified_diag_status"):self.unified_diag_status.configure(text=data.get("error","Không đọc được Unified Diagnostics."),fg=C["danger"])
            return
        d=data.get("unified_diagnostics") or {};summary=d.get("summary") or {};layers=d.get("layers") or {}
        if hasattr(self,"unified_diag_summary_labels"):
            vals={"requests":summary.get("requests",0),"errors":summary.get("errors",0),"failovers":summary.get("failovers",0),"circuit":summary.get("circuit_open",0)}
            for k,v in vals.items():
                fg=C["danger"] if k in ("errors","circuit") and v else (C["warning"] if k=="failovers" and v else C["text"])
                self.unified_diag_summary_labels[k].configure(text=str(v),fg=fg)
        generated=str(d.get("generated_utc") or "—")
        if hasattr(self,"unified_diag_status"):
            self.unified_diag_status.configure(text=f"Unified Diagnostics v25.41 · {summary.get('total',0)} event · generated {generated[:19]} · METADATA ONLY",fg=C["success"] if not summary.get("errors") else C["warning"])
        layer_lines=[]
        for k in ("request","routing","circuit","self_healing","security","rotation_torture"):
            layer_lines.append(f"{k:<14} {str(layers.get(k,'NO_DATA'))}")
        if hasattr(self,"unified_diag_layers"):self.unified_diag_layers.configure(text="\n".join(layer_lines))
        acct_lines=[]
        for r in (d.get("accounts") or [])[:5]:
            acct_lines.append(f"{str(r.get('account') or '—')[:25]:25} E{int(r.get('errors',0)):02d} W{int(r.get('warnings',0)):02d} R{int(r.get('requests',0)):03d}")
        if not acct_lines:acct_lines=["Chưa có account telemetry"]
        if hasattr(self,"unified_diag_accounts"):self.unified_diag_accounts.configure(text="\n".join(acct_lines))
        lines=["TIME (UTC)           SEV      SOURCE             KIND                 ACCOUNT / MODEL / STATUS","-"*128]
        for ev in (d.get("timeline") or [])[:220]:
            t=str(ev.get("time_utc") or "")[:19].replace("T"," ")
            sev=str(ev.get("severity") or "INFO")[:8]
            src=str(ev.get("source") or "")[:18]
            kind=str(ev.get("kind") or "")[:20]
            acct=str(ev.get("account") or "—")[:27]
            model=str(ev.get("model") or "—")[:20]
            status=str(ev.get("status") or "—")[:12]
            lines.append(f"{t:19}  {sev:<8} {src:<18} {kind:<20} {acct} / {model} / {status}")
            msg=str(ev.get("message") or "").strip()
            rid=str(ev.get("request_id") or "").strip()
            iid=str(ev.get("instance_id") or "").strip()
            if msg or rid or iid:
                meta=[]
                if rid:meta.append("REQ="+rid[:28])
                if iid:meta.append("INST="+iid[:18])
                if ev.get("latency_ms") is not None:meta.append("LAT="+str(ev.get("latency_ms"))+"ms")
                lines.append(" "*22+(" · ".join(meta)+(": " if meta and msg else "")+msg[:180]))
        if len(lines)==2:lines.append("Chưa có telemetry để hợp nhất. HMS sẽ cập nhật khi Codex/Router tạo request metadata.")
        self._set_text_readonly(self.unified_diag_text,"\n".join(lines))

    def _build_logs(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["logs"] = page

        heading = tk.Frame(page, bg=C["bg"], height=42)
        heading.pack(fill="x")
        heading.pack_propagate(False)
        tk.Label(
            heading, text="Nhật ký nội bộ", bg=C["bg"], fg=C["text"],
            font=("Segoe UI Semibold", 12)
        ).pack(side="left", pady=7)
        self.logs_refresh_btn = HoverButton(
            heading, "LÀM MỚI LOG", self.load_logs_async,
            width=116, height=30, bg=C["surface"], hover=C["surface3"],
            outline=C["border_soft"], font=("Segoe UI Semibold", 8)
        )
        self.logs_refresh_btn.pack(side="right", pady=4)

        note = tk.Label(
            page,
            text="HMS không hiển thị raw request body/token/cookie. Request log chỉ hiện metadata an toàn.",
            bg=C["bg"], fg=C["muted"], font=("Segoe UI", 7)
        )
        note.pack(anchor="w", pady=(0, 6))

        card = Card(page, 820, 505, bg=C["surface"], radius=12)
        card.pack(fill="both", expand=True)
        self.diag = tk.Text(
            card, bg="#111827", fg=C["text2"], insertbackground=C["text"],
            relief="flat", bd=0, font=("Consolas", 8), wrap="word"
        )
        card.create_window(14, 14, width=790, height=472, window=self.diag, anchor="nw")
        self.diag.insert("1.0", "Đang chờ dữ liệu...")
        self.diag.configure(state="disabled")

    def _build_settings(self):
        page = tk.Frame(self.content, bg=C["bg"])
        self.pages["settings"] = page

        # Cockpit-like centered pill tabs.
        tab_shell = tk.Frame(page, bg=C["surface"],
                             highlightbackground=C["border_soft"], highlightthickness=1)
        tab_shell.pack(anchor="center", pady=(2, 14), ipady=4, ipadx=4)
        self.settings_tab_buttons = {}
        tabs = [
            ("general", "Chung"),
            ("codex", "Codex"),
            ("router", "Router"),
            ("proxy", "Proxy"),
            ("instances", "Instances"),
            ("projects", "Dự án"),
            ("advanced", "Nâng cao"),
        ]
        for key, text in tabs:
            btn = HoverButton(
                tab_shell, text, lambda k=key: self.show_settings_tab(k),
                width=105 if key != "advanced" else 118, height=32,
                bg=C["surface"], hover=C["hover"], outline="",
                font=("Segoe UI Semibold", 8)
            )
            btn.pack(side="left", padx=2)
            self.settings_tab_buttons[key] = btn

        self.settings_body = tk.Frame(page, bg=C["bg"])
        self.settings_body.pack(fill="both", expand=True)
        self.settings_tabs = {}

        for key, _ in tabs:
            scroller = ScrollableSettings(self.settings_body)
            self.settings_tabs[key] = scroller

        self._build_settings_general(self.settings_tabs["general"].inner)
        self._build_settings_codex(self.settings_tabs["codex"].inner)
        self._build_settings_router(self.settings_tabs["router"].inner)
        self._build_settings_proxy(self.settings_tabs["proxy"].inner)
        self._build_settings_instances(self.settings_tabs["instances"].inner)
        self._build_settings_projects(self.settings_tabs["projects"].inner)
        self._build_settings_advanced(self.settings_tabs["advanced"].inner)

        save_bar = tk.Frame(page, bg=C["bg"], height=56)
        save_bar.pack(fill="x", pady=(10, 0))
        save_bar.pack_propagate(False)
        self.settings_status = tk.Label(
            save_bar, text="Đang tải cài đặt...",
            bg=C["bg"], fg=C["muted"], font=("Segoe UI", 8)
        )
        self.settings_status.pack(side="left", padx=(3, 0))
        self.settings_reload_btn = HoverButton(
            save_bar, "HOÀN TÁC", self.load_settings_async,
            width=112, height=34, bg=C["surface"], hover=C["surface3"],
            outline=C["border_soft"], font=("Segoe UI Semibold", 8), icon="↶"
        )
        self.settings_reload_btn.pack(side="right", padx=(8, 0))
        self.settings_save_btn = HoverButton(
            save_bar, "LƯU THAY ĐỔI", self.save_settings_async,
            width=150, height=34, bg=C["primary"], hover=C["primary_hover"],
            font=("Segoe UI Semibold", 8), icon="✓"
        )
        self.settings_save_btn.pack(side="right")

        self.show_settings_tab("general")

    def _setting_bool(self, key, default=False):
        var = tk.BooleanVar(value=default)
        var.trace_add("write", lambda *_: self._settings_changed())
        self.settings_vars[key] = var
        return var

    def _setting_str(self, key, default=""):
        var = tk.StringVar(value=default)
        var.trace_add("write", lambda *_: self._settings_changed())
        self.settings_vars[key] = var
        return var

    def _settings_changed(self):
        if self.settings_loaded:
            self.settings_dirty = True
            if "settings" in self.nav:
                self.nav["settings"].set_badge(True, C["warning"])
            if hasattr(self, "settings_status"):
                self.settings_status.configure(text="Có thay đổi chưa lưu", fg=C["warning"])

    def _switch(self, parent, key, default=False):
        return ToggleSwitch(parent, self._setting_bool(key, default))

    def _entry(self, parent, key, default="", width=18):
        var = self._setting_str(key, default)
        e = tk.Entry(
            parent, textvariable=var, width=width,
            bg=C["surface3"], fg=C["text"], insertbackground=C["text"],
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=C["border"], highlightcolor=C["primary"],
            font=("Segoe UI", 9)
        )
        return e

    def _combo(self, parent, key, values, default):
        var = self._setting_str(key, default)
        c = ttk.Combobox(
            parent, textvariable=var, values=values,
            state="readonly", width=18, style="HMS.TCombobox"
        )
        return c

    def _group(self, parent, title, desc=""):
        group = SettingGroup(parent, title, desc)
        group.pack(fill="x", padx=(2, 12), pady=(0, 18))
        return group

    def _build_settings_general(self, parent):
        group = self._group(parent, "Khởi chạy & Codex", "thao tác hằng ngày")
        group.add_row(
            "Tự mở Codex khi BẬT HMS",
            "Bật Router xong HMS sẽ tự mở Codex/ChatGPT Desktop.",
            self._switch(group.card, "OpenCodexOnEnable", True)
        )
        group.add_row(
            "Restart Codex khi chuyển Router",
            "Đảm bảo process mới nhận provider và environment HMS.",
            self._switch(group.card, "RestartCodexOnSwitch", True)
        )
        group.add_row(
            "Force-close nếu Codex không chịu đóng",
            "Khuyến nghị bật để tránh process cũ giữ environment trước HMS.",
            self._switch(group.card, "ForceCloseIfNeeded", True)
        )

        safe = self._group(parent, "An toàn", "invariant của GUI-only")
        fixed1 = tk.Label(safe.card, text="LUÔN BẬT", bg=C["surface3"], fg=C["success"],
                          font=("Segoe UI Semibold", 8), padx=10, pady=5)
        safe.add_row(
            "Restore cấu hình Codex khi TẮT HMS",
            "Được khóa ON để tránh để Codex mắc kẹt ở provider HMS.",
            fixed1
        )
        fixed2 = tk.Label(safe.card, text="TẮT", bg=C["surface3"], fg=C["text2"],
                          font=("Segoe UI Semibold", 8), padx=10, pady=5)
        safe.add_row(
            "Minimize-to-tray của PowerShell UI cũ",
            "Native GUI dùng taskbar bình thường; legacy tray-hide bị vô hiệu hóa.",
            fixed2
        )

        tools = self._group(parent, "Công cụ nhanh")
        quota = HoverButton(
            tools.card, "ACCOUNT CENTER", lambda: self.show_page("accounts"),
            width=145, height=34, bg=C["surface3"], hover=C["hover"],
            outline=C["border"], font=("Segoe UI Semibold", 8)
        )
        tools.add_row(
            "Tài khoản & quota",
            "Xem 5 giờ, tuần, reset time, trạng thái và thao tác account ngay trong HMS.",
            quota
        )

    def _build_settings_codex(self, parent):
        route = self._group(parent, "Routing Codex", "session & retry")
        route.add_row(
            "Chiến lược routing",
            "ỔN ĐỊNH giữ session affinity; CHIA ĐỀU bỏ sticky; fill-first ưu tiên một account.",
            self._combo(route.card, "CodexRoutingProfile",
                        ["stable", "balanced", "fill-first"], "stable")
        )
        route.add_row(
            "Session affinity TTL",
            "Thời gian một session ưu tiên giữ cùng account.",
            self._combo(route.card, "CodexSessionAffinityTtl",
                        ["30m", "1h", "2h", "4h", "8h", "24h"], "1h")
        )
        route.add_row(
            "Request retry",
            "Số lần CLIProxy retry request lỗi có thể phục hồi.",
            self._entry(route.card, "CodexRequestRetry", "3", 10)
        )
        route.add_row(
            "Max retry interval (giây)",
            "Giới hạn khoảng chờ retry credential/request.",
            self._entry(route.card, "CodexMaxRetryInterval", "12", 10)
        )
        route.add_row(
            "Optimize multi-agent V2",
            "Giữ tối ưu multi-agent hiện tại của HMS.",
            self._switch(route.card, "CodexOptimizeMultiAgentV2", True)
        )
        route.add_row(
            "Lưu cooldown status",
            "Giữ trạng thái cooldown credential qua CLIProxyAPI.",
            self._switch(route.card, "CodexSaveCooldownStatus", True)
        )

        health = self._group(parent, "Theo dõi & phục hồi")
        health.add_row(
            "Watchdog Codex Router",
            "Theo dõi Router và kích hoạt recovery khi HMS-owned Router rơi.",
            self._switch(health.card, "CodexWatchdogEnabled", True)
        )
        health.add_row(
            "Chu kỳ Watchdog (giây)",
            "Mặc định 15 giây; không nên đặt quá thấp.",
            self._entry(health.card, "CodexWatchdogIntervalSec", "15", 10)
        )
        health.add_row(
            "Tự phục hồi Router",
            "Cho Watchdog tự khởi động lại HMS-owned Router khi an toàn.",
            self._switch(health.card, "CodexAutoRecoverRouter", True)
        )
        health.add_row(
            "Config Doctor",
            "Kiểm tra cấu hình Codex trước các thao tác quan trọng.",
            self._switch(health.card, "CodexConfigDoctorEnabled", True)
        )
        health.add_row(
            "Auto sanitize trước launch",
            "Dọn cấu hình HMS-generated không hợp lệ trước khi mở Codex.",
            self._switch(health.card, "CodexAutoSanitizeBeforeLaunch", True)
        )

        quota = self._group(parent, "Quota & Telemetry")
        quota.add_row(
            "Tự refresh quota",
            "Tự cập nhật quota account theo chu kỳ.",
            self._switch(quota.card, "CodexAutoQuotaRefresh", False)
        )
        quota.add_row(
            "Chu kỳ auto quota (phút)",
            "Áp dụng khi auto refresh quota được bật.",
            self._entry(quota.card, "CodexAutoQuotaRefreshMinutes", "10", 10)
        )
        quota.add_row(
            "Telemetry nội bộ",
            "Thu thập telemetry runtime HMS cục bộ.",
            self._switch(quota.card, "CodexTelemetryEnabled", True)
        )
        quota.add_row(
            "Chu kỳ telemetry (giây)",
            "Tần suất lấy telemetry nội bộ.",
            self._entry(quota.card, "CodexTelemetryIntervalSec", "5", 10)
        )

    def _build_settings_router(self, parent):
        network = self._group(parent, "CLIProxyAPI", "local gateway")
        network.add_row(
            "Thư mục CLIProxyAPI",
            "Đường dẫn chứa cli-proxy-api.exe và config.yaml.",
            self._entry(network.card, "ProxyDir", r"C:\CLIProxyAPI", 34),
            height=72
        )
        network.add_row(
            "Port HMS Router",
            "Nếu port bị Cockpit/ứng dụng khác chiếm, One-Click vẫn có thể chọn port dự phòng.",
            self._entry(network.card, "ProxyPort", "8317", 10)
        )

        behavior = self._group(parent, "Hành vi Router")
        behavior.add_row(
            "Refresh quota cơ bản (phút)",
            "Chu kỳ chuẩn cho dữ liệu quota trực tiếp.",
            self._entry(behavior.card, "CodexQuotaRefreshMinutes", "5", 10)
        )
        behavior.add_row(
            "API parity audit tự động",
            "Chạy kiểm tra parity/evidence theo chính sách HMS.",
            self._switch(behavior.card, "ApiParityAutoAudit", True)
        )

    def _build_settings_proxy(self, parent):
        affinity = self._group(parent, "Proxy Affinity", "sticky theo account/group")
        affinity.add_row(
            "Bật Proxy Affinity",
            "Gắn account/group với proxy ổn định thay vì random theo request.",
            self._switch(affinity.card, "ProxyAffinityEnabled", True)
        )
        affinity.add_row(
            "Chế độ",
            "STRICT = fail-closed; STICKY_FAILOVER = failover sticky; DIRECT_FALLBACK = có thể về direct.",
            self._combo(affinity.card, "ProxyAffinityMode",
                        ["STRICT", "STICKY_FAILOVER", "DIRECT_FALLBACK"], "STRICT")
        )
        affinity.add_row(
            "Số account / proxy",
            "Mặc định 5 account cho một proxy group.",
            self._entry(affinity.card, "ProxyAccountsPerProxy", "5", 10)
        )
        affinity.add_row(
            "Yêu cầu proxy health trước start",
            "Không start sidecar/group nếu proxy chưa qua health gate.",
            self._switch(affinity.card, "ProxyHealthRequiredBeforeStart", True)
        )

        egress = self._group(parent, "Egress Integrity")
        egress.add_row(
            "Public IP probe",
            "Kiểm tra IP public của egress proxy.",
            self._switch(egress.card, "ProxyPublicIpProbeEnabled", False)
        )
        egress.add_row(
            "Egress probe",
            "Bật kiểm tra egress integrity trước/đang chạy.",
            self._switch(egress.card, "ProxyEgressProbeEnabled", True)
        )
        egress.add_row(
            "Yêu cầu IP ổn định",
            "Nếu IP drift khỏi baseline thì có thể quarantine group.",
            self._switch(egress.card, "ProxyEgressRequireStableIp", True)
        )
        egress.add_row(
            "Cho phép Direct fallback",
            "CẢNH BÁO: có thể làm account ra Internet không qua proxy đã gắn.",
            self._switch(egress.card, "ProxyDirectFallbackAllowed", False),
            danger=True
        )

    def _build_settings_instances(self, parent):
        isolation = self._group(parent, "Codex Multi-Instance", "account/project isolation")
        isolation.add_row("Ép isolation trước start", "Block start nếu binding/project/account/auth snapshot không khớp.", self._switch(isolation.card, "CodexInstanceEnforceIsolation", True))
        isolation.add_row("Project duy nhất", "Một project chỉ được bind với một managed instance.", self._switch(isolation.card, "CodexInstanceRequireUniqueProject", True))
        isolation.add_row("Account riêng cho instance", "Mặc định một account chỉ bind một instance để tránh cross-identity.", self._switch(isolation.card, "CodexInstanceRequireDedicatedAccount", True))
        isolation.add_row("Bắt buộc project", "Không cho tạo managed instance không có project root.", self._switch(isolation.card, "CodexInstanceProjectRequired", True))
        isolation.add_row("Sync credential trước start", "Khi instance STOP, refresh dedicated auth snapshot từ account pool và verify SHA-256.", self._switch(isolation.card, "CodexInstanceSyncCredentialOnStart", True))
        isolation.add_row("Identity Isolation v25.36", "Fingerprint + fleet boundary audit cho CODEX_HOME/profile/app-data/config/auth.", self._switch(isolation.card, "CodexIdentityIsolationEnabled", True))
        isolation.add_row("Audit trước launch", "Fail-closed nếu identity/project/account/port/boundary không khớp trước khi mở Codex.", self._switch(isolation.card, "CodexIdentityAuditBeforeLaunch", True))
        isolation.add_row("Fingerprint strict", "Bắt buộc fingerprint hợp lệ; fingerprint không chứa OAuth/API secret.", self._switch(isolation.card, "CodexIdentityFingerprintStrict", True))
        isolation.add_row("Path nằm trong root", "CODEX_HOME, app-data và Router phải nằm dưới root riêng của instance.", self._switch(isolation.card, "CodexIdentityRequirePathsUnderRoot", True))

        modelmgr = self._group(parent, "Codex Model & Reasoning v25.37", "Project model policy · live catalog · isolated config.toml")
        modelmgr.add_row("Bật Model Manager", "Quản lý model/reasoning theo project; không đổi stable endpoint/provider/account binding.", self._switch(modelmgr.card, "ModelManagerEnabled", True))
        modelmgr.add_row("Auto discover", "Đọc /v1/models khi mở trang Models Codex.", self._switch(modelmgr.card, "ModelManagerAutoDiscover", True))
        modelmgr.add_row("Require live model", "Khi live catalog có dữ liệu, chỉ cho apply model đang xuất hiện trong catalog.", self._switch(modelmgr.card, "ModelManagerRequireLiveModel", True))
        modelmgr.add_row("Apply trước launch", "Nếu project đã có policy, ghi model/reasoning vào isolated config trước khi mở Codex.", self._switch(modelmgr.card, "ModelManagerApplyBeforeLaunch", True))
        modelmgr.add_row("Reasoning mặc định", "auto bỏ override; các mức còn lại ghi model_reasoning_effort.", self._combo(modelmgr.card, "ModelManagerDefaultReasoning", ["auto","none","low","medium","high","xhigh","max"], "medium"))
        modelmgr.add_row("Profile mặc định", "Metadata workload để chuẩn bị Smart Model Router; chưa tự đổi account.", self._combo(modelmgr.card, "ModelManagerDefaultProfile", ["BALANCED","FAST","DEEP","REVIEW","TEST"], "BALANCED"))

        smart = self._group(parent, "Smart Model Router v25.44", "Project + role + workload → model/reasoning + bounded account affinity")
        smart.add_row("Bật Smart Router", "Đánh giá model/account cho session mới; Circuit/Quota/Identity/Security vẫn là hard gate.", self._switch(smart.card, "SmartModelRouterEnabled", True))
        smart.add_row("Mode", "OBSERVE chỉ khuyến nghị; GUARDED_AUTO chỉ apply lên instance đang dừng và đủ hard gate.", self._combo(smart.card, "SmartModelRouterMode", ["OBSERVE","GUARDED_AUTO"], "OBSERVE"))
        smart.add_row("Apply trước launch", "Chỉ hoạt động trong GUARDED_AUTO; active sticky session không bị đổi.", self._switch(smart.card, "SmartModelRouterApplyBeforeLaunch", True))
        smart.add_row("Require live model", "Không đề xuất model nếu Router chưa chứng minh model đó trong live catalog.", self._switch(smart.card, "SmartModelRouterRequireLiveModel", True))
        smart.add_row("Bảo vệ session đang chạy", "Block hot-switch model/reasoning khi managed client đang chạy.", self._switch(smart.card, "SmartModelRouterProtectRunningSessions", True))
        smart.add_row("Min score delta", "Độ chênh tối thiểu để policy hiện tại được coi là đáng thay đổi.", self._entry(smart.card, "SmartModelRouterMinScoreDelta", "5", 10))
        smart.add_row("Max account adjustment", "Bounded signal cho Closed-loop; hard cap backend = 8 điểm.", self._entry(smart.card, "SmartModelRouterMaxAccountAdjustment", "6", 10))
        smart.add_row("Coder profile", "Profile model mặc định của role CODER.", self._combo(smart.card, "SmartModelRouterCoderProfile", ["BALANCED","FAST","DEEP","REVIEW","TEST"], "BALANCED"))
        smart.add_row("Reviewer profile", "Profile model mặc định của role REVIEWER.", self._combo(smart.card, "SmartModelRouterReviewerProfile", ["BALANCED","FAST","DEEP","REVIEW","TEST"], "REVIEW"))
        smart.add_row("Tester profile", "Profile model mặc định của role TESTER.", self._combo(smart.card, "SmartModelRouterTesterProfile", ["BALANCED","FAST","DEEP","REVIEW","TEST"], "TEST"))

        runtime = self._group(parent, "Instance Runtime")
        runtime.add_row("Base port", "Port đầu tiên cho isolated per-instance Router; HMS tự chọn port kế tiếp còn trống.", self._entry(runtime.card, "CodexInstanceBasePort", "8400", 10))
        runtime.add_row("Launch mode mặc định", "CLI ổn định hơn cho isolation; Desktop vẫn giữ để thử runtime khi cần.", self._combo(runtime.card, "CodexInstanceDefaultLaunchMode", ["cli","desktop"], "cli"))
        runtime.add_row("Max instance / account", "v25.36 khóa primary identity bằng fingerprint; Router fallback vẫn nằm phía sau stable endpoint.", self._entry(runtime.card, "CodexFleetMaxInstancesPerAccount", "1", 10))
        runtime.add_row("Watchdog Router instance", "Nếu client managed còn chạy nhưng Router riêng rơi, HMS phục hồi Router của chính instance đó.", self._switch(runtime.card, "CodexInstanceRouterWatchdog", True))

        tools = self._group(parent, "Điều khiển nhanh")
        btn = HoverButton(tools.card, "CODEX INSTANCES", lambda: self.show_page("instances"), width=145, height=34, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 8))
        tools.add_row("Multi-Instance Control", "Tạo/start/stop/focus từng Codex instance ngay trong GUI HMS.", btn)

    def _build_settings_projects(self, parent):
        grp=self._group(parent,"Project Affinity Engine","project → instance → account")
        grp.add_row("Bật Project Affinity","Nhớ project và isolated Codex instance tương ứng.",self._switch(grp.card,"CodexProjectAffinityEnabled",True))
        grp.add_row("Auto-register instance","Instance có project sẽ tự xuất hiện trong trang Dự án Codex.",self._switch(grp.card,"CodexProjectAutoRegisterInstances",True))
        grp.add_row("Block primary không healthy","Nếu primary không READY, chỉ cho mở khi Seamless Router có fallback hợp lệ; nếu không thì block.",self._switch(grp.card,"CodexProjectBlockUnhealthyPrimary",True))
        grp.add_row("Focus nếu đang chạy","Bấm MỞ PROJECT sẽ đưa instance hiện tại lên trước thay vì mở trùng.",self._switch(grp.card,"CodexProjectFocusIfRunning",True))
        limits=self._group(parent,"Affinity Limits")
        limits.add_row("Fallback tối đa","Số account dự phòng được nhớ cho mỗi project.",self._entry(limits.card,"CodexProjectFallbackMax","3",10))
        limits.add_row("Sticky window (phút)","Giữ session affinity theo project; không ép đổi account giữa một session đang chạy.",self._entry(limits.card,"CodexProjectStickyMinutes","180",10))
        seamless=self._group(parent,"Seamless Codex Router","stable endpoint · primary + fallback")
        seamless.add_row("Bật Seamless Router","Primary/fallback dùng chung endpoint cố định của instance; không đổi Codex config khi pool thay đổi.",self._switch(seamless.card,"CodexSeamlessRouterEnabled",True))
        seamless.add_row("Live pool sync","Lưu Affinity sẽ reconcile credential snapshot bằng SHA-256; credential cũ được archive, không xóa.",self._switch(seamless.card,"CodexSeamlessLivePoolSync",True))
        seamless.add_row("Session affinity","Giữ một session trên cùng credential khi Router còn healthy.",self._switch(seamless.card,"CodexSeamlessSessionAffinity",True))
        seamless.add_row("TTL affinity (giờ)","Thời gian sticky mặc định cho Router instance.",self._entry(seamless.card,"CodexSeamlessSessionTtlHours","24",10))
        seamless.add_row("Retry credential tối đa","Số fallback credential Router được phép thử cho một request.",self._entry(seamless.card,"CodexSeamlessMaxRetryCredentials","3",10))
        tools=self._group(parent,"Điều khiển nhanh")
        btn=HoverButton(tools.card,"DỰ ÁN CODEX",lambda:self.show_page("projects"),width=145,height=34,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",8))
        tools.add_row("Project Affinity","Xem mapping project/account/instance và mở đúng Codex bằng một nút.",btn)

    def _build_settings_advanced(self, parent):
        kernel = self._group(parent, "Policy Kernel", "automation an toàn")
        kernel.add_row(
            "Bật Policy Kernel",
            "Cho phép kernel đánh giá trạng thái và khuyến nghị/hành động theo mode.",
            self._switch(kernel.card, "PolicyKernelEnabled", True)
        )
        kernel.add_row(
            "Mode",
            "OBSERVE chỉ quan sát; SAFE_AUTO chỉ thực hiện action an toàn đã cho phép.",
            self._combo(kernel.card, "PolicyKernelMode", ["OBSERVE", "SAFE_AUTO"], "OBSERVE")
        )

        automation = self._group(parent, "Automation nền", "native GUI runtime")
        automation.add_row(
            "Theo dõi route/request",
            "Phân tích log an toàn để hiện account vừa phục vụ request và confidence.",
            self._switch(automation.card, "CodexOpsEnabled", True)
        )
        automation.add_row(
            "Legacy High Availability",
            "Giữ làm fallback tương thích; v25.35 tự bỏ qua engine cũ khi Circuit Breaker mới đang ON.",
            self._switch(automation.card, "CodexHaEnabled", True)
        )

        automation.add_row("Smart Model interval (giây)", "Chu kỳ evaluate/apply nền; apply nền chỉ khi mode GUARDED_AUTO.", self._entry(automation.card, "SmartModelRouterIntervalSec", "90", 10))
        automation.add_row("Smart Model min samples", "Mẫu analytics tối thiểu trước khi model/account affinity được tin cậy.", self._entry(automation.card, "SmartModelRouterMinModelSamples", "3", 10))

        selfheal = self._group(parent, "Codex Self-Healing v25.39", "evidence + readback + rollback · ownership guard")
        selfheal.add_row("Bật Self-Healing", "Audit Router/port/PID/provider/endpoint/binding/credential/model policy drift.", self._switch(selfheal.card, "CodexSelfHealingEnabled", True))
        selfheal.add_row("Auto audit", "Chạy audit nền trong GUI; không tự sửa nếu Auto repair safe đang OFF.", self._switch(selfheal.card, "CodexSelfHealingAutoAudit", True))
        selfheal.add_row("Auto repair safe", "Mặc định OFF. Khi ON chỉ áp dụng action engine đánh dấu auto-safe; không kill process lạ.", self._switch(selfheal.card, "CodexSelfHealingAutoRepairSafe", False))
        selfheal.add_row("Chu kỳ (giây)", "15..3600 giây. Evidence được lưu theo từng lần audit/repair.", self._entry(selfheal.card, "CodexSelfHealingIntervalSec", "60", 10))
        selfheal.add_row("Safe repairs only", "Không tự làm action cần operator/restart/quyết định phá vỡ session.", self._switch(selfheal.card, "CodexSelfHealingSafeRepairsOnly", True))
        sh_actions=tk.Frame(selfheal.card,bg=C["surface"])
        HoverButton(sh_actions,"MỞ SELF-HEAL",lambda:self.show_page("selfheal"),width=116,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(sh_actions,"AUDIT",self.audit_self_healing_async,width=76,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left",padx=6)
        selfheal.add_row("Điều khiển", "Sửa an toàn cần người dùng bấm nút trên trang Tự sửa Codex nếu auto repair chưa bật.", sh_actions)

        security = self._group(parent, "Codex Security Hardening v25.40", "Credential Manager/DPAPI · ACL · reparse guard · HMAC seals")
        security.add_row("Bật Security Hardening", "Bật protected-secret migration, security audit và prelaunch integrity guard.", self._switch(security.card, "CodexSecurityHardeningEnabled", True))
        security.add_row("Credential Manager", "Ưu tiên Windows Credential Manager cho Router keys; không lưu key trong settings/instance JSON.", self._switch(security.card, "CodexSecurityCredentialManagerEnabled", True))
        security.add_row("DPAPI fallback", "Nếu Credential Manager không khả dụng, lưu ciphertext DPAPI CurrentUser trong security vault.", self._switch(security.card, "CodexSecurityDpapiFallbackEnabled", True))
        security.add_row("ACL hardening", "Harden security/sensitive instance paths về current-user + SYSTEM khi bấm HARDEN.", self._switch(security.card, "CodexSecurityAclHardeningEnabled", True))
        security.add_row("Integrity seals", "HMAC-SHA256 cho authority/config ổn định; mismatch fail-closed và không auto-reseal.", self._switch(security.card, "CodexSecurityIntegritySealsEnabled", True))
        security.add_row("Block reparse points", "Chặn launch nếu boundary chứa symlink/junction/reparse point chưa được operator xử lý.", self._switch(security.card, "CodexSecurityBlockReparsePoints", True))
        security.add_row("Strict redaction", "Giữ secret/prompt body khỏi security snapshot/evidence và backend error output.", self._switch(security.card, "CodexSecurityStrictRedaction", True))
        security.add_row("Auto audit", "Audit nền; không auto-HARDEN và không auto-RESEAL.", self._switch(security.card, "CodexSecurityAutoAudit", True))
        security.add_row("Chu kỳ audit (giây)", "30..3600 giây.", self._entry(security.card, "CodexSecurityIntervalSec", "120", 10))
        sec_actions=tk.Frame(security.card,bg=C["surface"])
        HoverButton(sec_actions,"MỞ BẢO MẬT",lambda:self.show_page("security"),width=116,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(sec_actions,"AUDIT",self.audit_security_async,width=76,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left",padx=6)
        security.add_row("Điều khiển", "HARDEN và RESEAL cần thao tác rõ ràng trên trang Bảo mật.", sec_actions)

        diagnostics = self._group(parent, "Unified Diagnostics v25.41", "request/router/quota/circuit/self-healing/security timeline · metadata only")
        diagnostics.add_row("Bật Unified Diagnostics", "Hợp nhất telemetry an toàn thành timeline duy nhất; không đọc prompt/request body/tool arguments/secret.", self._switch(diagnostics.card, "UnifiedDiagnosticsEnabled", True))
        diagnostics.add_row("Auto refresh", "Làm mới timeline trong maintenance tick; chỉ đọc metadata đã được HMS sinh ra.", self._switch(diagnostics.card, "UnifiedDiagnosticsAutoRefresh", True))
        diagnostics.add_row("Chu kỳ (giây)", "Tối thiểu 30 giây để tránh tăng IO không cần thiết.", self._entry(diagnostics.card, "UnifiedDiagnosticsIntervalSec", "60", 10))
        diagnostics.add_row("Số event tối đa", "Giới hạn timeline trong memory/report; history compact vẫn append metadata summary.", self._entry(diagnostics.card, "UnifiedDiagnosticsMaxEvents", "600", 10))
        diag_actions=tk.Frame(diagnostics.card,bg=C["surface"])
        HoverButton(diag_actions,"MỞ CHẨN ĐOÁN",lambda:self.show_page("diagnostics"),width=124,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(diag_actions,"LÀM MỚI",self.refresh_unified_diagnostics_async,width=86,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left",padx=6)
        diagnostics.add_row("Điều khiển", "Timeline hợp nhất hỗ trợ xác định request/account/router layer gây lỗi trước khi mở log thô.", diag_actions)

        ledger = self._group(parent, "Usage Ledger", "SQLite bền vững · metadata-only")
        ledger.add_row(
            "Bật Usage Ledger",
            "Đồng bộ request metadata từ Smart Gateway vào SQLite; không lưu request body/secret.",
            self._switch(ledger.card, "UsageLedgerEnabled", True)
        )
        ledger.add_row(
            "Chu kỳ đồng bộ (giây)",
            "GUI chạy nền; giá trị hợp lệ 10..3600 giây.",
            self._entry(ledger.card, "UsageLedgerSyncSec", "30", 10)
        )
        ledger.add_row(
            "Historical pool signal",
            "Usage Ledger cung cấp feedback 1h/24h/7d; Closed-loop Router dùng làm tín hiệu thực tế.",
            self._switch(ledger.card, "AdaptivePoolAdvisoryEnabled", True)
        )

        quota_center = self._group(parent, "Advanced Quota Center v25.35", "SQLite quota history · source freshness · reset timeline · forecast accuracy")
        quota_center.add_row("Bật Quota Center", "Lưu metadata quota 5h/7d bền vững; không lưu prompt, request body, OAuth token hoặc cookie.", self._switch(quota_center.card, "QuotaCenterEnabled", True))
        quota_center.add_row("Chu kỳ (giây)", "Automation nền snapshot và đối chiếu forecast; live quota vẫn là dữ liệu authoritative.", self._entry(quota_center.card, "QuotaCenterIntervalSec", "60", 10))
        quota_center.add_row("Lưu lịch sử (ngày)", "Retention SQLite cho quota snapshot; prune chỉ telemetry cũ, không đụng credential/account.", self._entry(quota_center.card, "QuotaCenterRetentionDays", "45", 10))
        quota_center.add_row("Fresh / stale (phút)", "Source freshness được gắn FRESH / AGING / STALE thay vì hiển thị quota cũ như dữ liệu mới.", self._entry(quota_center.card, "QuotaCenterFreshMinutes", "10", 10))
        quota_center.add_row("Stale threshold (phút)", "Quá ngưỡng này sẽ cảnh báo QUOTA_SOURCE_STALE.", self._entry(quota_center.card, "QuotaCenterStaleMinutes", "30", 10))
        quota_center.add_row("Forecast accuracy horizon", "Đối chiếu dự báo remaining sau N phút với quota quan sát sau đó để tính MAE/bias.", self._entry(quota_center.card, "QuotaCenterAccuracyHorizonMinutes", "60", 10))
        quota_center.add_row("Chart history (giờ)", "Số giờ quota history dùng cho sparkline 5h/7d trong GUI.", self._entry(quota_center.card, "QuotaCenterChartHistoryHours", "168", 10))
        quota_actions=tk.Frame(quota_center.card,bg=C["surface"])
        HoverButton(quota_actions,"MỞ QUOTA",lambda:self.show_page("quota"),width=100,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(quota_actions,"ĐỒNG BỘ",self.sync_quota_center_async,width=92,height=29,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",7)).pack(side="left",padx=6)
        quota_center.add_row("Điều khiển", "History/accuracy chỉ cấp telemetry cho operator; không tự thay quota live hay credential.", quota_actions)

        analytics = self._group(parent, "Account Analytics v25.35", "quality score · model/workload profile · bounded Router signal")
        analytics.add_row("Bật Account Analytics", "Tổng hợp metadata Usage Ledger + quota + circuit + predictive; không đọc prompt/body/OAuth/API key/cookie.", self._switch(analytics.card, "AccountAnalyticsEnabled", True))
        analytics.add_row("Chu kỳ (giây)", "Automation nền cập nhật hồ sơ account trước Closed-loop Router.", self._entry(analytics.card, "AccountAnalyticsIntervalSec", "90", 10))
        analytics.add_row("Lưu lịch sử (ngày)", "Giữ snapshot quality score để nhận biết trend; chỉ telemetry đã chuẩn hoá.", self._entry(analytics.card, "AccountAnalyticsRetentionDays", "180", 10))
        analytics.add_row("Mẫu tối thiểu", "Ngưỡng dùng cho model recommendation. Account score vẫn gắn confidence khi ít mẫu.", self._entry(analytics.card, "AccountAnalyticsMinSamples", "5", 10))
        aa_actions=tk.Frame(analytics.card,bg=C["surface"])
        HoverButton(aa_actions,"PHÂN TÍCH NGAY",self.sync_account_analytics_async,width=118,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).pack(side="left")
        analytics.add_row("Điều khiển", "Router chỉ nhận bounded quality signal; stable endpoint và session affinity không đổi.", aa_actions)

        predictive = self._group(parent, "Predictive Quota v25.35", "velocity + runway + reset-aware pressure · forecast ≠ quota live")
        predictive.add_row("Bật Predictive Quota", "Dự báo tốc độ tiêu thụ theo account và cấp tín hiệu cho Closed-loop Router; không sửa credential/quota.", self._switch(predictive.card, "PredictiveQuotaEnabled", True))
        predictive.add_row("Chu kỳ (giây)", "Snapshot quota history + tính runway. History cũ không có reset vẫn được đọc tương thích.", self._entry(predictive.card, "PredictiveQuotaIntervalSec", "60", 10))
        predictive.add_row("Lookback 5h (giờ)", "Chỉ dùng quota epoch mới nhất; quota tăng mạnh được coi là reset/replenishment boundary.", self._entry(predictive.card, "PredictiveQuotaHourlyLookbackHours", "8", 10))
        predictive.add_row("Lookback tuần (giờ)", "Cửa sổ dài hơn để ước lượng velocity tuần nhưng vẫn ưu tiên epoch mới nhất.", self._entry(predictive.card, "PredictiveQuotaWeeklyLookbackHours", "72", 10))
        predictive.add_row("Mẫu tối thiểu theo thời gian", "Forecast có confidence LOW/MEDIUM/HIGH; live remaining vẫn là dữ liệu authoritative.", self._entry(predictive.card, "PredictiveQuotaMinSpanMinutes", "20", 10))
        predictive.add_row("Reserve trigger (%)", "Bắt đầu giảm tải session mới khi remaining/forecast tiến vào vùng áp lực.", self._entry(predictive.card, "PredictiveQuotaReserveTriggerPct", "15", 10))
        predictive.add_row("Emergency (%)", "Đánh dấu current critical để Closed-loop có thể bypass hysteresis/hold và chuyển new-session preference.", self._entry(predictive.card, "PredictiveQuotaEmergencyPct", "3", 10))
        predictive.add_row("Runway chủ động (phút)", "Nếu dự báo cạn trước reset trong khoảng này, account chuyển EMERGENCY và drain session mới.", self._entry(predictive.card, "PredictiveQuotaProactiveRunwayMinutes", "90", 10))
        predictive.add_row("Runway cảnh báo (phút)", "Giảm weight sớm hơn trước khi tới vùng critical.", self._entry(predictive.card, "PredictiveQuotaWarningRunwayMinutes", "240", 10))
        predictive_actions = tk.Frame(predictive.card, bg=C["surface"])
        HoverButton(predictive_actions, "DỰ BÁO NGAY", self.evaluate_predictive_quota_async, width=112, height=29, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold",7)).pack(side="left")
        predictive.add_row("Điều khiển", "Chỉ cập nhật plan/state forecast. Việc đổi priority/weight vẫn do Closed-loop GUARDED_AUTO thực hiện.", predictive_actions)

        breaker = self._group(parent, "Circuit Breaker v25.35", "CLOSED → OPEN → HALF_OPEN → CLOSED · per-instance/account")
        breaker.add_row("Bật Circuit Breaker", "Phân loại 401/403, 429, 5xx, timeout/network và quarantine account lỗi theo từng Codex instance.", self._switch(breaker.card, "CircuitBreakerEnabled", True))
        breaker.add_row("Mode", "OBSERVE chỉ tính trạng thái; GUARDED_AUTO mới thay disabled flag để OPEN account không nhận session mới.", self._combo(breaker.card, "CircuitBreakerMode", ["OBSERVE", "GUARDED_AUTO"], "OBSERVE"))
        breaker.add_row("Chu kỳ (giây)", "Chạy trước Closed-loop Router; không thay stable endpoint hoặc session affinity.", self._entry(breaker.card, "CircuitBreakerIntervalSec", "20", 10))
        breaker.add_row("Lỗi liên tiếp", "Mở circuit khi chuỗi lỗi đủ dài; success mới sẽ cắt chuỗi.", self._entry(breaker.card, "CircuitBreakerConsecutiveFailures", "3", 10))
        breaker.add_row("Ngưỡng HTTP 429", "Rate-limit có cooldown riêng và exponential backoff nếu tái phát.", self._entry(breaker.card, "CircuitBreakerRateLimitThreshold", "2", 10))
        breaker.add_row("Ngưỡng Auth 401/403", "Auth lỗi mặc định mở circuit ngay và giữ lâu hơn để tránh retry storm.", self._entry(breaker.card, "CircuitBreakerAuthThreshold", "1", 10))
        breaker.add_row("Open cơ bản (giây)", "Cooldown cho lỗi chung/server; lần tái mở liên tiếp sẽ backoff có giới hạn.", self._entry(breaker.card, "CircuitBreakerBaseOpenSec", "120", 10))
        breaker.add_row("Auth open (giây)", "401/403 dùng cooldown riêng; không tự sửa token ở tranche này.", self._entry(breaker.card, "CircuitBreakerAuthOpenSec", "900", 10))
        breaker.add_row("Half-open success", "Số request thành công sau HALF_OPEN cần để quay về CLOSED.", self._entry(breaker.card, "CircuitBreakerHalfOpenSuccesses", "1", 10))
        breaker_actions = tk.Frame(breaker.card, bg=C["surface"])
        HoverButton(breaker_actions, "ĐÁNH GIÁ", self.evaluate_circuit_breaker_async, width=90, height=29, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(breaker_actions, "ÁP DỤNG", self.apply_circuit_breaker_async, width=86, height=29, bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold",7)).pack(side="left", padx=6)
        HoverButton(breaker_actions, "RESET", self.reset_circuit_breaker_async, width=80, height=29, bg="#5a3a42", hover="#70464f", outline=C["border"], font=("Segoe UI Semibold",7)).pack(side="left")
        breaker.add_row("Điều khiển", "RESET chỉ hoàn tác quarantine do HMS sở hữu và khôi phục disabled state trước đó; không xóa credential.", breaker_actions)

        closed = self._group(parent, "Closed-loop Router v25.35", "feedback + live quota + predictive pressure + circuit state · per-instance")
        closed.add_row("Bật Closed-loop", "Khi ON, controller này thay Adaptive Router legacy trong automation nền.", self._switch(closed.card, "ClosedLoopRouterEnabled", True))
        closed.add_row("Mode", "OBSERVE chỉ tính plan; GUARDED_AUTO mới ghi priority/weight trong auth pool của từng instance.", self._combo(closed.card, "ClosedLoopRouterMode", ["OBSERVE", "GUARDED_AUTO"], "OBSERVE"))
        closed.add_row("Chu kỳ (giây)", "Đọc feedback 1h/24h/7d + predictive runway. Existing session affinity không bị thay đổi.", self._entry(closed.card, "ClosedLoopRouterIntervalSec", "45", 10))
        closed.add_row("Mẫu tối thiểu", "Không tự promote account từ quá ít request, trừ khi current account critical.", self._entry(closed.card, "ClosedLoopRouterMinSamples", "5", 10))
        closed.add_row("Chênh score tối thiểu", "Hysteresis theo từng Codex instance để chống ping-pong.", self._entry(closed.card, "ClosedLoopRouterMinScoreDelta", "8", 10))
        closed.add_row("Giữ ưu tiên tối thiểu (phút)", "Chỉ đổi new-session preference sau hold time; session đang chạy vẫn sticky.", self._entry(closed.card, "ClosedLoopRouterHoldMinutes", "20", 10))
        closed.add_row("Cooldown apply (giây)", "Giới hạn tốc độ thay policy giữa các lần apply.", self._entry(closed.card, "ClosedLoopRouterCooldownSec", "120", 10))
        closed.add_row("Quota floor (%)", "Phạt score theo quota live; Predictive Quota bổ sung pressure penalty riêng.", self._entry(closed.card, "ClosedLoopRouterQuotaFloor", "10", 10))
        closed.add_row("Emergency quota (%)", "Cho phép bypass hysteresis/hold khi current account ở mức critical.", self._entry(closed.card, "ClosedLoopRouterEmergencyQuota", "3", 10))
        closed_actions = tk.Frame(closed.card, bg=C["surface"])
        HoverButton(closed_actions, "ĐÁNH GIÁ", self.evaluate_closed_loop_async, width=90, height=29, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold",7)).pack(side="left")
        HoverButton(closed_actions, "ÁP DỤNG", self.apply_closed_loop_async, width=86, height=29, bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold",7)).pack(side="left", padx=6)
        HoverButton(closed_actions, "HOÀN TÁC", self.rollback_closed_loop_async, width=90, height=29, bg="#5a3a42", hover="#70464f", outline=C["border"], font=("Segoe UI Semibold",7)).pack(side="left")
        closed.add_row("Điều khiển", "Apply chỉ thay priority/weight + cập nhật hash manifest; không đổi endpoint/project/session binding.", closed_actions)

        adaptive = self._group(parent, "Adaptive Router (legacy)", "compatibility only · background skipped when Closed-loop ON")
        adaptive.add_row("Bật đánh giá adaptive", "OBSERVE an toàn theo mặc định; không sửa routing khi chưa chọn GUARDED_AUTO.", self._switch(adaptive.card, "AdaptiveRouterEnabled", True))
        adaptive.add_row("Mode", "OBSERVE chỉ tính plan; GUARDED_AUTO mới cho phép ghi priority/weight sau đủ gate.", self._combo(adaptive.card, "AdaptiveRouterMode", ["OBSERVE", "GUARDED_AUTO"], "OBSERVE"))
        adaptive.add_row("Chu kỳ (giây)", "Đánh giá pool nền. Existing session affinity không bị Adaptive Router thay đổi.", self._entry(adaptive.card, "AdaptiveRouterIntervalSec", "60", 10))
        adaptive.add_row("Mẫu tối thiểu", "Giảm nguy cơ đổi account từ vài request may mắn.", self._entry(adaptive.card, "AdaptiveRouterMinSamples", "5", 10))
        adaptive.add_row("Chênh score tối thiểu", "Hysteresis để chống nhảy account qua lại.", self._entry(adaptive.card, "AdaptiveRouterMinScoreDelta", "10", 10))
        adaptive.add_row("Giữ account tối thiểu (phút)", "Trừ khi current account critical/quota emergency.", self._entry(adaptive.card, "AdaptiveRouterHoldMinutes", "30", 10))
        adaptive_actions = tk.Frame(adaptive.card, bg=C["surface"])
        HoverButton(adaptive_actions, "ĐÁNH GIÁ", self.evaluate_adaptive_async, width=92, height=30, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7)).pack(side="left", padx=(0,5))
        HoverButton(adaptive_actions, "ÁP DỤNG", self.apply_adaptive_async, width=86, height=30, bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 7)).pack(side="left", padx=(0,5))
        HoverButton(adaptive_actions, "HOÀN TÁC", self.rollback_adaptive_async, width=92, height=30, bg="#5a3a42", hover="#70464f", outline=C["border"], font=("Segoe UI Semibold", 7)).pack(side="left")
        adaptive.add_row("Điều khiển", "ÁP DỤNG chỉ PASS khi setting đã lưu ở GUARDED_AUTO và plan đủ gate.", adaptive_actions)

        release = self._group(parent, "Release Manager", "local versioned activation · no-delete rollback")
        self.release_status_label = tk.Label(release.card, text="Chưa đọc trạng thái", bg=C["surface"], fg=C["muted"],
                                             font=("Segoe UI Semibold", 7), anchor="e")
        status_btn = HoverButton(release.card, "TRẠNG THÁI", self.load_release_async, width=108, height=32,
                                 bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7))
        release.add_row("Release hiện tại", "Kiểm tra ACTIVE/PREV và manifest của bản portable này.", status_btn)
        release.add_row("ACTIVE / PREV", "Chỉ đổi version pointer; không tự xóa release cũ.", self.release_status_label)
        release_actions = tk.Frame(release.card, bg=C["surface"])
        HoverButton(release_actions, "ĐĂNG KÝ", self.release_install_async, width=92, height=32,
                    bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 7)).pack(side="left", padx=(0,5))
        HoverButton(release_actions, "ROLLBACK", self.release_rollback_async, width=92, height=32,
                    bg="#5a3a42", hover="#70464f", outline=C["border"], font=("Segoe UI Semibold", 7)).pack(side="left")
        release.add_row("Quản lý local release", "ĐĂNG KÝ copy + verify trước activation; ROLLBACK cần xác nhận.", release_actions)

        updates = self._group(parent, "Signed Update Channel", "HTTPS feed · RSA/SHA-256 · stage trước · không auto-activate")
        updates.add_row("Bật kiểm tra cập nhật", "Mặc định OFF. Chỉ HTTPS; feed/chữ ký sai sẽ fail-closed.", self._switch(updates.card, "UpdateChannelEnabled", False))
        updates.add_row("Kênh", "stable hoặc beta.", self._combo(updates.card, "UpdateChannelName", ["stable", "beta"], "stable"))
        updates.add_row("Feed URL", "URL JSON HTTPS do HMS phát hành. Public key được pin trong package.", self._entry(updates.card, "UpdateFeedUrl", "", 42))
        updates.add_row("Tự kiểm tra mỗi (giờ)", "Chỉ CHECK; không tự activate release tải về.", self._entry(updates.card, "UpdateAutoCheckHours", "24", 10))
        updates.add_row("Tự tải vào STAGED", "Nếu bật, background chỉ tải + verify; vẫn cần người dùng kích hoạt.", self._switch(updates.card, "UpdateAutoStage", False))
        self.update_status_label = tk.Label(updates.card, text="Chưa kiểm tra", bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold", 7), anchor="e")
        update_actions = tk.Frame(updates.card, bg=C["surface"])
        HoverButton(update_actions, "CHECK", self.update_check_async, width=78, height=30, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7)).pack(side="left", padx=(0,5))
        HoverButton(update_actions, "STAGE", self.update_stage_async, width=78, height=30, bg=C["surface3"], hover=C["hover"], outline=C["border"], font=("Segoe UI Semibold", 7)).pack(side="left", padx=(0,5))
        HoverButton(update_actions, "KÍCH HOẠT", self.update_activate_async, width=96, height=30, bg=C["primary"], hover=C["primary_hover"], font=("Segoe UI Semibold", 7)).pack(side="left")
        updates.add_row("Trạng thái update", "STAGE bắt buộc SHA + RSA signature + release manifest PASS trước khi có thể activate.", update_actions)
        updates.add_row("Kết quả", "ACTIVE/PREV vẫn do Release Manager giữ để rollback.", self.update_status_label)

        evidence = self._group(parent, "Evidence & Reliability")
        evidence.add_row(
            "Soak monitor",
            "Thu thập reliability samples cho các vòng soak.",
            self._switch(evidence.card, "SoakEnabled", True)
        )
        evidence.add_row(
            "Performance analytics",
            "Thu thập latency/SLA/RAM trend cục bộ.",
            self._switch(evidence.card, "PerformanceEnabled", True)
        )

        tools = self._group(parent, "Công cụ kỹ thuật")
        diag = HoverButton(tools.card, "CHẨN ĐOÁN", lambda: self.show_page("logs"),
                           width=125, height=34, bg=C["surface3"], hover=C["hover"],
                           outline=C["border"], font=("Segoe UI Semibold", 8))
        tools.add_row(
            "Diagnostics",
            "Xem JSON trạng thái backend hiện tại.",
            diag
        )
        runtime_btn = HoverButton(tools.card, "MỞ RUNTIME", self.open_runtime,
                                  width=125, height=34, bg=C["surface3"], hover=C["hover"],
                                  outline=C["border"], font=("Segoe UI Semibold", 8))
        tools.add_row(
            "Runtime folder",
            "Mở thư mục nội bộ của HMS để kiểm tra evidence khi cần.",
            runtime_btn
        )

    def show_settings_tab(self, key):
        if not hasattr(self, "settings_tabs") or key not in self.settings_tabs:
            return
        self.settings_current_tab = key
        for name, frame in self.settings_tabs.items():
            frame.pack_forget()
        self.settings_tabs[key].pack(fill="both", expand=True)
        for name, btn in self.settings_tab_buttons.items():
            if name == key:
                btn.set_colors("#e8edf5", "#ffffff", "#0f172a")
            else:
                btn.set_colors(C["surface"], C["hover"], C["text2"])

    def load_settings_async(self):
        if self.busy:
            return
        if hasattr(self, "settings_status"):
            self.settings_status.configure(text="Đang tải cài đặt...", fg=C["muted"])
            self.settings_save_btn.set_enabled(False)
            self.settings_reload_btn.set_enabled(False)

        def worker():
            data = self.backend("get_settings", 35)
            self.root.after(0, lambda: self._apply_settings(data))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_settings(self, data):
        if hasattr(self, "settings_save_btn"):
            self.settings_save_btn.set_enabled(True)
            self.settings_reload_btn.set_enabled(True)
        if not data.get("ok"):
            if hasattr(self, "settings_status"):
                self.settings_status.configure(
                    text=data.get("error", "Không tải được cài đặt."), fg=C["danger"]
                )
            return
        settings = data.get("settings") or {}
        self.settings_loaded = False
        for key, var in self.settings_vars.items():
            if key in settings:
                try:
                    if isinstance(var, tk.BooleanVar):
                        var.set(bool(settings[key]))
                    else:
                        var.set(str(settings[key]))
                except Exception:
                    pass
        self.settings_data = settings
        self.settings_loaded = True
        self.settings_dirty = False
        if "settings" in self.nav:
            self.nav["settings"].set_badge(False)
        if hasattr(self, "settings_status"):
            self.settings_status.configure(text="Đã đồng bộ với HMS backend", fg=C["success"])
        if hasattr(self, "release_status_label"):
            self.root.after(60, self.load_release_async)
        if hasattr(self, "update_status_label"):
            self.root.after(120, self.load_update_async)

    def save_settings_async(self):
        if self.busy or not self.settings_loaded:
            return
        payload = {}
        for key, var in self.settings_vars.items():
            payload[key] = var.get()
        self.settings_save_btn.set_enabled(False)
        self.settings_reload_btn.set_enabled(False)
        self.settings_status.configure(text="Đang lưu...", fg=C["warning"])

        def worker():
            data = self.backend("save_settings", 45, payload=payload)
            self.root.after(0, lambda: self._finish_save_settings(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_save_settings(self, data):
        self.settings_save_btn.set_enabled(True)
        self.settings_reload_btn.set_enabled(True)
        if not data.get("ok"):
            err = data.get("error", "Không lưu được cài đặt.")
            self.settings_status.configure(text=err, fg=C["danger"])
            self.toast(err, "danger")
            return
        self.settings_loaded = False
        self._apply_settings(data)
        restart = data.get("restart_required") or []
        if restart:
            msg = "Đã lưu · một số thay đổi áp dụng khi BẬT HMS lại"
            self.settings_status.configure(text=msg, fg=C["warning"])
            self.toast(msg, "warning")
        else:
            self.settings_status.configure(text="Đã lưu cài đặt HMS", fg=C["success"])
            self.toast("Đã lưu cài đặt HMS", "success")
        self.refresh_async()

    def toast(self, text, kind="success"):
        color = {
            "success": C["success"], "warning": C["warning"],
            "danger": C["danger"], "primary": C["primary"]
        }.get(kind, C["primary"])
        icon = {
            "success": "✓", "warning": "!", "danger": "×", "primary": "i"
        }.get(kind, "i")
        try:
            if getattr(self, "_toast", None) and self._toast.winfo_exists():
                self._toast.destroy()
        except Exception:
            pass

        toast = tk.Toplevel(self.root)
        self._toast = toast
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=C["border_soft"])

        w, h = 370, 66
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + self.root.winfo_width() - w - 22
        y = self.root.winfo_rooty() + self.root.winfo_height() - h - 30
        toast.geometry(f"{w}x{h}+{x+34}+{y}")

        card = tk.Frame(toast, bg="#182235")
        card.pack(fill="both", expand=True, padx=1, pady=1)
        icon_box = tk.Label(
            card, text=icon, bg=mix("#182235", color, .18), fg=color,
            font=("Segoe UI Semibold", 11), width=2
        )
        icon_box.pack(side="left", padx=(10, 8), pady=12, fill="y")
        tk.Label(
            card, text=text, bg="#182235", fg=C["text"],
            font=("Segoe UI Semibold", 8), wraplength=290,
            justify="left", anchor="w"
        ).pack(side="left", fill="both", expand=True, padx=(0, 12), pady=10)

        steps = 7
        def slide(i=0):
            if not toast.winfo_exists():
                return
            if i >= steps:
                toast.after(2600, toast.destroy)
                return
            eased = 1 - (1 - (i+1)/steps) ** 3
            nx = x + int(34 * (1 - eased))
            toast.geometry(f"{w}x{h}+{nx}+{y}")
            toast.after(18, lambda: slide(i+1))
        slide()

    def show_page(self, name, animate=True):
        if name not in self.pages:
            return
        old = self.pages.get(self.current_page)
        new = self.pages[name]
        if old is new and new.winfo_ismapped():
            return
        for key, item in self.nav.items():
            item.set_active(key == name)
        titles = {
            "overview": ("Tổng quan", "Codex API Service · local authenticated gateway"),
            "accounts": ("Tài khoản", "Pool intelligence · quota · reset · health · usage signals"),
            "quota": ("Quota", "lịch sử 5h/7d · reset timeline · freshness · forecast accuracy"),
            "usage": ("Sử dụng", "Usage Ledger · predictive quota · circuit breaker · closed-loop routing"),
            "analytics": ("Phân tích", "account quality · model/workload profile · long-term reliability"),
            "modelmgr": ("Models Codex", "project model policy · reasoning effort · live catalog · isolated config"),
            "smartmodel": ("Smart Router", "project + role + workload → model/reasoning + bounded account affinity"),
            "lanpool": ("LAN Pool", "cross-PC ownership · signed heartbeat · project lease/epoch · no raw credential sharing"),
            "orchestrator": ("Điều phối Project", "one-click project → instance → account → model → router → workspace"),
            "team": ("Đội Codex", "Coder · Reviewer · Tester · isolated workspaces · explicit epoch · ownership guard"),
            "projects": ("Dự án Codex", "project affinity · remembered instance · primary/fallback account"),
            "instances": ("Codex Instances", "multi-instance · identity fingerprint · prelaunch isolation audit · isolated router"),
            "selfheal": ("Tự sửa Codex", "evidence · safe repair · readback · rollback · ownership guard"),
            "security": ("Bảo mật", "protected secrets · ACL isolation · reparse guard · integrity seals · redaction"),
            "diagnostics": ("Chẩn đoán", "request timeline · router decisions · quota/circuit · failover · self-healing evidence"),
            "logs": ("Nhật ký", "Router log an toàn · request metadata · diagnostics"),
            "settings": ("Cài đặt", "Codex · Router · Proxy · Policy"),
        }
        title, sub = titles[name]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=sub)
        if old and old.winfo_ismapped():
            old.place_forget()
        self.current_page = name
        if name == "overview":
            self.root.after(80, self.load_service_async)
        elif name == "settings" and not self.settings_loaded:
            self.root.after(80, self.load_settings_async)
        elif name == "accounts":
            self.root.after(80, self.load_accounts_async)
        elif name == "quota":
            self.root.after(80, self.load_quota_center_async)
        elif name == "usage":
            self.root.after(80, self.load_usage_async)
            self.root.after(145, self.load_predictive_quota_async)
            self.root.after(210, self.load_circuit_breaker_async)
            self.root.after(285, self.load_closed_loop_async)
        elif name == "analytics":
            self.root.after(80, self.load_account_analytics_async)
        elif name == "modelmgr":
            self.root.after(80, self.load_model_manager_async)
        elif name == "smartmodel":
            self.root.after(80, self.load_smart_model_router_async)
        elif name == "lanpool":
            self.root.after(80, self.load_lan_pool_async)
        elif name == "orchestrator":
            self.root.after(80, self.load_project_orchestrator_async)
        elif name == "team":
            self.root.after(80, self.load_multi_codex_team_async)
        elif name == "projects":
            self.root.after(80, self.load_project_affinity_async)
        elif name == "instances":
            self.root.after(80, self.load_instances_async)
        elif name == "selfheal":
            self.root.after(80, self.load_self_healing_async)
        elif name == "security":
            self.root.after(80, self.load_security_async)
        elif name == "diagnostics":
            self.root.after(80, self.load_unified_diagnostics_async)
        elif name == "logs":
            self.root.after(80, self.load_logs_async)
        if not animate:
            new.place(x=0, y=0, relwidth=1, relheight=1)
            return
        new.place(x=18, y=0, relwidth=1, relheight=1)
        steps = 7
        def step(i=0):
            if i >= steps:
                new.place(x=0, y=0, relwidth=1, relheight=1)
                return
            x = int(18 * (1 - (i+1)/steps))
            new.place(x=x, y=0, relwidth=1, relheight=1)
            self.root.after(18, lambda: step(i+1))
        step()

    def _periodic(self):
        if not self.busy:
            self.refresh_async()
        self.root.after(6000, self._periodic)

    def _maintenance_periodic(self):
        """Keep automation alive for the native Tk GUI without showing legacy WinForms."""
        if not self.maintenance_busy:
            self.maintenance_busy = True
            def worker():
                data = self.backend("maintenance_tick", 90)
                self.root.after(0, lambda: self._finish_maintenance(data))
            threading.Thread(target=worker, daemon=True).start()
        self.root.after(15000, self._maintenance_periodic)

    def _finish_maintenance(self, data):
        self.maintenance_busy = False
        self.maintenance_data = data or {}
        if data.get("ok"):
            actions = data.get("actions") or []
            errors = data.get("errors") or []
            if errors:
                self.last_maintenance_text = f"AUTO · {len(errors)} cảnh báo"
            elif actions:
                self.last_maintenance_text = "AUTO · " + ", ".join(str(x) for x in actions[:2])
            else:
                self.last_maintenance_text = "AUTO · nền ổn định"
            activity = data.get("activity") or {}
            if activity:
                self._render_live_activity(activity)
            if self.current_page == "quota" and "Quota center" in actions:
                self.root.after(120, self.load_quota_center_async)
            if self.current_page == "analytics" and "Account analytics" in actions:
                self.root.after(120, self.load_account_analytics_async)
            if self.current_page == "smartmodel" and any(str(x).startswith("Smart model") for x in actions):
                self.root.after(120, self.load_smart_model_router_async)
            if self.current_page == "lanpool" and any(str(x).startswith("LAN pool") for x in actions):
                self.root.after(120, self.load_lan_pool_async)
            if self.current_page == "selfheal" and any(str(x).startswith("Self-heal") for x in actions):
                self.root.after(120, self.load_self_healing_async)
            if self.current_page == "security" and any(str(x).startswith("Security") for x in actions):
                self.root.after(140, self.load_security_async)
            if self.current_page == "diagnostics" and "Unified diagnostics" in actions:
                self.root.after(140, self.load_unified_diagnostics_async)
        else:
            self.last_maintenance_text = "AUTO · backend lỗi"
        if hasattr(self, "live_auto_id"):
            try:
                self.live_card.itemconfigure(
                    self.live_auto_id, text=self.last_maintenance_text,
                    fill=C["warning"] if (data.get("errors") or not data.get("ok")) else C["success"]
                )
            except Exception:
                pass

    def backend(self, action, timeout=60, payload=None):
        if not BACKEND.exists():
            return {"ok": False, "error": f"Thiếu backend: {BACKEND}"}
        fd, name = tempfile.mkstemp(prefix="hms-v2529-", suffix=".json")
        os.close(fd)
        rp = Path(name)
        input_path = None
        try:
            cmd = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                "-File", str(BACKEND),
                "-BackendAction", action,
                "-BackendResultPath", str(rp),
            ]
            if payload is not None:
                fd2, input_name = tempfile.mkstemp(prefix="hms-v2529-input-", suffix=".json")
                os.close(fd2)
                input_path = Path(input_name)
                input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                cmd.extend(["-BackendInputPath", str(input_path)])
            p = subprocess.run(
                cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW,
                timeout=timeout, check=False
            )
            if rp.exists() and rp.stat().st_size:
                try:
                    return json.loads(rp.read_text(encoding="utf-8-sig", errors="replace"))
                except Exception as e:
                    return {"ok": False, "error": f"Backend JSON lỗi: {e}",
                            "exit_code": p.returncode}
            return {"ok": False,
                    "error": f"Backend không tạo result.json (exit={p.returncode}).",
                    "exit_code": p.returncode}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Backend timeout khi chạy {action}."}
        except Exception as e:
            return {"ok": False, "error": f"Không thể gọi backend: {e}"}
        finally:
            try:
                rp.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                if input_path is not None:
                    input_path.unlink(missing_ok=True)
            except Exception:
                pass

    def refresh_async(self):
        if self.busy:
            return
        self.refresh_btn.set_enabled(False)
        if not self.first_status_loaded:
            self.status_pill.set("ĐANG TẢI", "primary")
            self._render_loading_accounts()
        def worker():
            data = self.backend("status", 30)
            self.root.after(0, lambda: self._finish_refresh(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_refresh(self, data):
        self.refresh_btn.set_enabled(True)
        self.first_status_loaded = True
        self.apply_status(data)
        if self.current_page == "overview":
            self.root.after(60, self.load_service_async)

    def apply_status(self, data):
        self.status_data = data or {}
        self._update_diag()
        if not data.get("ok"):
            if hasattr(self, "sync_label"):
                self.sync_label.configure(text="Đồng bộ lỗi", fg=C["danger"])
            self.sidebar_status.configure(text="●  Backend lỗi", fg=C["danger"])
            self.status_pill.set("BACKEND LỖI", "danger")
            self.toggle_btn.set_text("BẬT HMS")
            self.toggle_btn.set_colors(C["primary"], C["primary_hover"])
            self.open_codex_btn.set_enabled(False)
            self._set_stat("accounts", "—")
            self._set_stat("ready", "—")
            self._set_stat("router", "LỖI", C["danger"])
            self._set_stat("mode", "—")
            self._render_accounts([])
            return

        active = bool(data.get("active"))
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.last_sync_text = f"Đồng bộ {now}"
        if hasattr(self, "sync_label"):
            self.sync_label.configure(text=self.last_sync_text)
        acc = data.get("accounts") or {}
        records = acc.get("records") or []
        activity = data.get("activity") or {}
        self._render_live_activity(activity)
        self.base_var.set(f"http://127.0.0.1:{data.get('port',8317)}/v1")
        self.gateway_card.itemconfigure(
            self.gateway_note_id,
            text=data.get("routing") or "ỔN ĐỊNH — round-robin + session affinity"
        )
        self._animate_stat_value("accounts", str(acc.get("total", 0)))
        self._set_stat("ready", f"{acc.get('ready',0)} / {acc.get('cooldown',0)}")
        if hasattr(self, "account_summary_labels"):
            for key in ("total", "ready", "cooldown", "free"):
                self.account_summary_labels[key].configure(text=str(acc.get(key, 0)))
        if active:
            self.sidebar_status.configure(text="●  HMS đang chạy", fg=C["success"])
            self.status_pill.set("ĐANG CHẠY", "success")
            self.toggle_btn.set_text("TẮT HMS")
            self.toggle_btn.set_colors("#7f3138", "#963b44")
            self.open_codex_btn.set_enabled(True)
            self._set_stat("router", "ONLINE", C["success"])
            self._set_stat("mode", "API", C["primary"])
        else:
            if data.get("foreign_listener"):
                self.sidebar_status.configure(text="●  Port đang bận", fg=C["warning"])
            else:
                self.sidebar_status.configure(text="●  HMS đã dừng", fg=C["muted"])
            self.status_pill.set("ĐÃ DỪNG", "neutral" if not data.get("foreign_listener") else "warning")
            self.toggle_btn.set_text("BẬT HMS")
            self.toggle_btn.set_colors(C["primary"], C["primary_hover"])
            self.open_codex_btn.set_enabled(False)
            self._set_stat("router", "FOREIGN" if data.get("foreign_listener") else "OFFLINE",
                           C["warning"] if data.get("foreign_listener") else C["text2"])
            self._set_stat("mode", "DIRECT", C["text2"])
        self._render_accounts(records, activity.get("account") or "")

    def _animate_stat_value(self, key, new_text, color=None):
        card, value_id = self.stat_cards[key]
        old = str(card.itemcget(value_id, "text"))
        try:
            start = int(old)
            end = int(str(new_text))
        except Exception:
            card.itemconfigure(value_id, text=new_text, fill=color or C["text"])
            return
        steps = 8
        def step(i=0):
            if i >= steps:
                card.itemconfigure(value_id, text=str(end), fill=color or C["text"])
                return
            eased = 1 - (1 - (i+1)/steps) ** 3
            val = round(start + (end-start)*eased)
            card.itemconfigure(value_id, text=str(val), fill=color or C["text"])
            card.after(18, lambda: step(i+1))
        step()

    def _set_stat(self, key, text, color=None):
        card, value_id = self.stat_cards[key]
        card.itemconfigure(value_id, text=text, fill=color or C["text"])

    def _render_loading_accounts(self):
        if not hasattr(self, "overview_accounts"):
            return
        for w in self.overview_accounts.winfo_children():
            w.destroy()
        for i in range(3):
            row = tk.Frame(self.overview_accounts, bg=C["surface"], height=30)
            row.pack(fill="x", pady=3)
            row.pack_propagate(False)
            dot = tk.Frame(row, bg=C["surface3"], width=8, height=8)
            dot.pack(side="left", padx=(3, 10))
            line1 = tk.Frame(row, bg=C["surface3"], width=230, height=8)
            line1.pack(side="left")
            line2 = tk.Frame(row, bg="#28374c", width=74, height=8)
            line2.pack(side="left", padx=(10, 0))
            q = tk.Frame(row, bg="#28374c", width=62, height=8)
            q.pack(side="right", padx=(0, 7))

    def _animate_quota_fill(self, widget, pct, steps=10):
        pct = max(0, min(100, int(pct)))
        def step(i=0):
            if not widget.winfo_exists():
                return
            if i >= steps:
                widget.place_configure(relwidth=pct/100)
                return
            eased = 1 - (1 - (i+1)/steps) ** 3
            widget.place_configure(relwidth=(pct/100)*eased)
            widget.after(18, lambda: step(i+1))
        step()

    def _start_status_pulse(self):
        def pulse():
            if not self.root.winfo_exists():
                return
            active = bool(self.status_data.get("active"))
            if active:
                self.pulse_phase = (self.pulse_phase + 1) % 24
                t = (math.sin(self.pulse_phase / 24 * math.tau) + 1) / 2
                color = mix("#176b3a", C["success"], .35 + .35*t)
                try:
                    self.sidebar_status.configure(fg=color)
                except Exception:
                    pass
            self.root.after(90, pulse)
        pulse()

    def _render_live_activity(self, activity):
        if not hasattr(self, "live_card"):
            return
        account = (activity or {}).get("account") or ""
        confidence = ((activity or {}).get("confidence") or "—").upper()
        evidence = (activity or {}).get("evidence") or ""
        if account:
            title = account
            color = C["success"] if confidence == "CONFIRMED" else C["warning"]
            detail = f"CONFIDENCE {confidence}"
            if evidence:
                detail += " · " + str(evidence).replace("\n", " ")[:88]
        else:
            title = "Chưa có request được nhận diện"
            color = C["text2"]
            detail = "CONFIDENCE — · Router sẽ cập nhật sau request đầu tiên"
        try:
            self.live_card.itemconfigure(self.live_account_id, text=title, fill=color)
            self.live_card.itemconfigure(self.live_detail_id, text=detail)
            self.live_card.itemconfigure(self.live_auto_id, text=self.last_maintenance_text)
        except Exception:
            pass

    def _render_accounts(self, records, recent_account=""):
        for w in self.overview_accounts.winfo_children():
            w.destroy()
        if not records:
            empty = tk.Frame(self.overview_accounts, bg=C["surface"])
            empty.pack(fill="both", expand=True)
            tk.Label(
                empty, text="Không có account khớp bộ lọc",
                bg=C["surface"], fg=C["text2"],
                font=("Segoe UI Semibold", 9)
            ).pack(anchor="w", padx=4, pady=(16, 2))
            tk.Label(
                empty, text="Mở Tài khoản rồi bấm THÊM TÀI KHOẢN để thêm OAuth credential ngay trong HMS.",
                bg=C["surface"], fg=C["muted"],
                font=("Segoe UI", 7)
            ).pack(anchor="w", padx=4)
            return
        for item in records[:3]:
            is_recent = bool(recent_account and (item.get("email") or "").lower() == recent_account.lower())
            row_bg = C["surface2"] if is_recent else C["surface"]
            row = tk.Frame(self.overview_accounts, bg=row_bg, height=34)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            status = item.get("status") or "—"
            ready = "READY" in status.upper() or "ACTIVE" in status.upper()
            color = C["success"] if ready else C["warning"]
            tk.Label(row, text="●", bg=row_bg, fg=color,
                     font=("Segoe UI", 8)).pack(side="left", padx=(3, 9))
            tk.Label(
                row, text=item.get("email") or "—", bg=row_bg, fg=C["text"],
                font=("Segoe UI Semibold", 8)
            ).pack(side="left")
            plan = (item.get("plan") or "—").upper()
            plan_label = tk.Label(
                row, text=plan, bg="#26364b", fg=C["text2"],
                font=("Segoe UI Semibold", 7), padx=7, pady=2
            )
            plan_label.pack(side="left", padx=(9, 0))
            if is_recent:
                tk.Label(
                    row, text="ROUTE GẦN NHẤT", bg="#1d4e78", fg="#bfdbfe",
                    font=("Segoe UI Semibold", 6), padx=6, pady=2
                ).pack(side="left", padx=(7, 0))
            quota = item.get("quota") or "—"
            tk.Label(
                row, text=quota, bg=row_bg, fg=C["text2"],
                font=("Segoe UI Semibold", 8)
            ).pack(side="right", padx=(0, 7))
    def show_service_tab(self, key, refresh=True):
        if key not in getattr(self, "service_views", {}):
            return
        self.service_current_tab = key
        for name, frame in self.service_views.items():
            frame.pack_forget()
        self.service_views[key].pack(fill="both", expand=True)
        for name, btn in self.service_tab_buttons.items():
            if name == key:
                btn.set_colors("#e8edf5", "#ffffff", "#0f172a")
            else:
                btn.set_colors(C["surface"], C["hover"], C["text2"])
        if refresh:
            if key == "compat": self.load_api_compat_async()
            else: self.load_service_async()

    def load_api_compat_async(self):
        def worker():
            data=self.backend("get_api_compatibility",60);self.root.after(0,lambda:self._apply_api_compat(data))
        threading.Thread(target=worker,daemon=True).start()

    def run_api_compat_async(self):
        if self.busy:return
        self.busy=True
        if hasattr(self,"compat_audit_btn"):self.compat_audit_btn.set_enabled(False)
        def worker():
            data=self.backend("run_api_compatibility",120);self.root.after(0,lambda:self._finish_api_compat(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_api_compat(self,data):
        self.busy=False
        if hasattr(self,"compat_audit_btn"):self.compat_audit_btn.set_enabled(True)
        self._apply_api_compat(data)
        self.toast(data.get("message","API Compatibility audit hoàn tất.") if data.get("ok") else data.get("error","API Compatibility audit lỗi."),"success" if data.get("ok") else "danger")

    def _apply_api_compat(self,data):
        if not hasattr(self,"compat_matrix"):return
        if not data.get("ok"):
            self.service_views["compat"].winfo_children()[0].itemconfigure(self.compat_status_id,text=data.get("error","Không đọc được API Compatibility."),fill=C["danger"]);return
        a=data.get("api_compatibility") or {};summary=a.get("summary") or {};verdict=a.get("verdict") or "NOT_AUDITED";matrix=a.get("matrix") or {}
        color=C["success"] if verdict=="PASS" else C["warning"]
        self.service_views["compat"].winfo_children()[0].itemconfigure(self.compat_status_id,text=f"Synthetic: {verdict} · {summary.get('pass',0)}/{summary.get('total',0)} · Windows Codex runtime: {a.get('runtime_windows_codex','DEFERRED')}",fill=color)
        live=data.get("live_contracts") or [];live_ok=sum(1 for x in live if x.get("ok"));self.service_views["compat"].winfo_children()[0].itemconfigure(self.compat_live_id,text=f"Live contract: {live_ok}/{len(live)} endpoint expose /hms/compatibility · runtime cũ vẫn được phép nhưng chưa LIVE VERIFIED",fill=C["text2"] if live else C["muted"])
        order=[("models","/v1/models"),("responses","/v1/responses"),("chat_completions","/v1/chat/completions"),("streaming_sse","Streaming / SSE"),("tool_calls","Tool calls"),("mcp","MCP tools"),("web_search","Web/Search"),("image_input","Image input"),("attachments","Attachments"),("structured_output","Structured output"),("reasoning","Reasoning"),("chunked_request","Chunked request"),("patch","PATCH transport"),("error_mapping","Error mapping"),("privacy","No-body logging")]
        lines=["CAPABILITY                 LEVEL","-"*54]
        for k,label in order:lines.append(f"{label:<27} {matrix.get(k,'NOT_AUDITED')}")
        lines += ["","Runtime truth: synthetic PASS không thay thế Windows Codex real request/stream/tool/MCP verification."]
        self._set_text_readonly(self.compat_matrix,"\n".join(lines))

    def load_service_async(self):
        if self.busy:
            return
        def worker():
            data=self.backend("get_service",45)
            self.root.after(0,lambda:self._apply_service(data))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_service(self, data):
        self.service_data=data or {}
        if not data.get("ok"):
            msg=data.get("error","Không đọc được Service Center.")
            if hasattr(self,"models_status"): self.models_status.configure(text=msg,fg=C["danger"])
            if hasattr(self,"keys_status"): self.keys_status.configure(text=msg,fg=C["danger"])
            return
        svc=data.get("service") or {}
        models=data.get("models") or []
        keys=data.get("client_keys") or []
        pool=data.get("pool") or {}
        sg=data.get("smart_gateway") or {}

        if hasattr(self,"models_status"):
            self.models_status.configure(
                text=f"Router {'ONLINE' if svc.get('router_online') else 'OFFLINE'} · HTTP {svc.get('api_http',0)} · {len(models)} models",
                fg=C["success"] if svc.get("api_ok") else C["warning"]
            )
        self._render_models(models)

        fp=svc.get("local_api_key_fingerprint") or "—"
        match="OK" if svc.get("local_api_key_config_match") else "MISMATCH"
        if hasattr(self,"keys_status"):
            self.keys_status.configure(
                text=f"Local router key: fingerprint {fp} · config {match} · Client keys: {len(keys)}",
                fg=C["success"] if svc.get("local_api_key_config_match") else C["warning"]
            )
        self._render_client_keys(keys)

        if hasattr(self,"routing_card"):
            text=(
                f"Pool: {pool.get('total',0)} total · {pool.get('ready',0)} ready · {pool.get('cooldown',0)} cooldown · {pool.get('free',0)} free\n"
                f"Codex routing: {pool.get('routing','—')}\n"
                f"Smart Gateway: {sg.get('strategy','—')} · affinity={sg.get('session_affinity')} · TTL={sg.get('session_ttl_sec',0)}s · "
                f"failover={sg.get('max_failover_attempts',0)} · websocket={sg.get('websocket_enabled')}\n"
                f"Router: {'ONLINE' if svc.get('router_online') else 'OFFLINE'} PID {svc.get('listener_pid',0)} · port {svc.get('port',0)} · Codex API mode={svc.get('codex_mode')}"
            )
            self.routing_card.itemconfigure(self.routing_summary_id,text=text)
            self.routing_diag.configure(state="normal");self.routing_diag.delete("1.0","end")
            self.routing_diag.insert("1.0",data.get("diagnostics") or "—");self.routing_diag.configure(state="disabled")

        accounts=data.get("failover_accounts") or []
        emails=[x.get("email") for x in accounts if x.get("email")]
        if hasattr(self,"failover_combo"):
            self.failover_combo.configure(values=emails)
            if emails and self.failover_account_var.get() not in emails:
                self.failover_account_var.set(emails[0])
        req=bool(svc.get("request_log_enabled"))
        if hasattr(self,"request_log_btn"):
            self.request_log_btn.set_text("REQUEST LOG: ON" if req else "REQUEST LOG: OFF")
            self.request_log_btn.set_colors("#245844" if req else "#59383b",
                                            "#2f7157" if req else "#70464a")
        if hasattr(self,"failover_note_id"):
            self.service_views["failover"].winfo_children()[0].itemconfigure(
                self.failover_note_id,
                text=("Request Log ON · sẵn sàng chạy bounded live failover test."
                      if req else "Request Log OFF · bấm nút REQUEST LOG để bật ngay trong HMS trước khi test.")
            )

    def _render_models(self, models):
        if not hasattr(self,"models_list"): return
        for w in self.models_list.winfo_children():w.destroy()
        if not models:
            tk.Label(self.models_list,text="Chưa có model. Bật HMS Router rồi TEST /v1/models.",
                     bg=C["bg"],fg=C["text2"],font=("Segoe UI",9)).pack(anchor="w",pady=14)
            return
        for i,m in enumerate(models):
            row=tk.Frame(self.models_list,bg=C["surface"],
                         highlightbackground=C["border_soft"],highlightthickness=1,height=48)
            row.pack(fill="x",padx=(2,12),pady=3);row.pack_propagate(False)
            tk.Label(row,text=m.get("id") or "—",bg=C["surface"],fg=C["text"],
                     font=("Segoe UI Semibold",9)).pack(side="left",padx=14)
            if m.get("owned_by"):
                tk.Label(row,text=m.get("owned_by"),bg="#27374b",fg=C["text2"],
                         font=("Segoe UI Semibold",7),padx=7,pady=2).pack(side="right",padx=12)

    def _render_client_keys(self, keys):
        if not hasattr(self,"keys_list"):return
        for w in self.keys_list.winfo_children():w.destroy()
        if not keys:
            tk.Label(self.keys_list,text="Chưa có client key. Bấm TẠO CLIENT KEY để tạo key đầu tiên.",
                     bg=C["bg"],fg=C["text2"],font=("Segoe UI",9)).pack(anchor="w",pady=14)
            return
        for k in keys:
            row=tk.Frame(self.keys_list,bg=C["surface"],
                         highlightbackground=C["border_soft"],highlightthickness=1,height=76)
            row.pack(fill="x",padx=(2,12),pady=4);row.pack_propagate(False)
            tk.Label(row,text=k.get("name") or "Unnamed",bg=C["surface"],fg=C["text"],
                     font=("Segoe UI Semibold",9)).place(x=14,y=11)
            tk.Label(row,text="ID "+str(k.get("id") or "—"),bg=C["surface"],fg=C["muted"],
                     font=("Segoe UI",7)).place(x=14,y=35)
            tk.Label(row,text=str(k.get("strategy") or "stable-round-robin"),
                     bg="#27374b",fg=C["text2"],font=("Segoe UI Semibold",7),
                     padx=7,pady=2).place(x=250,y=12)
            tk.Label(row,text=f"Reserve {k.get('quota_reserve_pct',0)}%",
                     bg=C["surface"],fg=C["text2"],font=("Segoe UI",8)).place(x=250,y=39)
            allow=", ".join(k.get("target_allow") or ["*"])
            tk.Label(row,text="Targets: "+allow[:46],bg=C["surface"],fg=C["muted"],
                     font=("Segoe UI",7)).place(relx=1,x=-14,y=35,anchor="ne")

    def show_create_client_key(self):
        win=tk.Toplevel(self.root);win.title("Tạo HMS Client Key");win.geometry("500x330")
        win.configure(bg=C["bg"]);win.transient(self.root);win.grab_set()
        tk.Label(win,text="Tạo Client Key",bg=C["bg"],fg=C["text"],
                 font=("Segoe UI Semibold",15)).pack(anchor="w",padx=22,pady=(18,4))
        tk.Label(win,text="Secret chỉ được hiển thị một lần sau khi tạo.",
                 bg=C["bg"],fg=C["warning"],font=("Segoe UI",8)).pack(anchor="w",padx=22)
        form=tk.Frame(win,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1)
        form.pack(fill="x",padx=22,pady=16)
        name=tk.StringVar(value="HMS Client")
        strategy=tk.StringVar(value="stable-round-robin")
        reserve=tk.StringVar(value="0")
        for label,var,y in [("Tên",name,18),("Strategy",strategy,76),("Quota reserve %",reserve,134)]:
            tk.Label(form,text=label,bg=C["surface"],fg=C["text2"],
                     font=("Segoe UI Semibold",8)).place(x=16,y=y)
        tk.Entry(form,textvariable=name,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],
                 relief="flat",font=("Segoe UI",9)).place(x=145,y=14,width=300,height=28)
        combo=ttk.Combobox(form,textvariable=strategy,state="readonly",style="HMS.TCombobox",
                           values=["stable-round-robin","random","auto","quota-first","plan-first","expiry-soon","weighted","reset-aware","fill-first"])
        combo.place(x=145,y=72,width=300,height=30)
        tk.Entry(form,textvariable=reserve,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],
                 relief="flat",font=("Segoe UI",9)).place(x=145,y=130,width=120,height=28)
        form.configure(height=180);form.pack_propagate(False)
        def submit():
            try:r=float(reserve.get())
            except Exception:
                messagebox.showwarning("Client Key","Quota reserve phải là số.",parent=win);return
            win.destroy();self.create_client_key_async(name.get(),strategy.get(),r)
        b=HoverButton(win,"TẠO KEY",submit,width=120,height=34,bg=C["primary"],
                      hover=C["primary_hover"],font=("Segoe UI Semibold",8))
        b.pack(side="right",padx=22,pady=(0,16))

    def create_client_key_async(self, name, strategy, reserve):
        if self.busy:return
        self.busy=True
        def worker():
            data=self.backend("create_client_key",60,payload={"name":name,"strategy":strategy,"quota_reserve_pct":reserve})
            self.root.after(0,lambda:self._finish_create_client_key(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_create_client_key(self,data):
        self.busy=False;self._apply_service(data)
        if not data.get("ok"):
            self.toast(data.get("error","Không tạo được client key."),"danger");return
        secret=data.get("created_client_key")
        if secret:self._show_one_time_secret(secret,data.get("created_client_key_id"))
        self.toast(data.get("message","Đã tạo client key."),"success")

    def _show_one_time_secret(self, secret, key_id):
        win=tk.Toplevel(self.root);win.title("Client Key — hiển thị một lần");win.geometry("620x245")
        win.configure(bg=C["bg"]);win.transient(self.root);win.grab_set()
        tk.Label(win,text="CLIENT KEY ĐÃ TẠO",bg=C["bg"],fg=C["success"],
                 font=("Segoe UI Semibold",14)).pack(anchor="w",padx=22,pady=(18,4))
        tk.Label(win,text="Sao chép ngay. HMS không hiển thị lại plaintext secret sau khi đóng cửa sổ này.",
                 bg=C["bg"],fg=C["warning"],font=("Segoe UI",8)).pack(anchor="w",padx=22)
        var=tk.StringVar(value=secret)
        e=tk.Entry(win,textvariable=var,state="readonly",readonlybackground="#172033",
                   fg=C["text"],font=("Consolas",9),relief="flat")
        e.pack(fill="x",padx=22,pady=18,ipady=8)
        def copy():
            self.root.clipboard_clear();self.root.clipboard_append(secret)
            self.toast("Đã sao chép client key.","success")
        HoverButton(win,"COPY",copy,width=96,height=32,bg=C["primary"],
                    hover=C["primary_hover"],font=("Segoe UI Semibold",8)).pack(side="right",padx=22,pady=(0,18))

    def test_api_async(self):
        if self.busy:return
        self.busy=True
        def worker():
            data=self.backend("test_api",45)
            self.root.after(0,lambda:self._finish_service_action(data,"test_api"))
        threading.Thread(target=worker,daemon=True).start()

    def restart_router_async(self):
        if self.busy:return
        self.busy=True
        def worker():
            data=self.backend("restart_router",70)
            self.root.after(0,lambda:self._finish_service_action(data,"restart"))
        threading.Thread(target=worker,daemon=True).start()

    def toggle_request_log_async(self):
        if self.busy:return
        current=bool((self.service_data.get("service") or {}).get("request_log_enabled"))
        self.busy=True
        def worker():
            data=self.backend("set_request_log",70,payload={"enabled":not current})
            self.root.after(0,lambda:self._finish_service_action(data,"request_log"))
        threading.Thread(target=worker,daemon=True).start()

    def run_failover_async(self):
        if self.busy:return
        email=self.failover_account_var.get().strip()
        if not email:
            self.toast("Chưa chọn account failover.","warning");return
        if not bool((self.service_data.get("service") or {}).get("request_log_enabled")):
            self.toast("Bật Request Log trước khi chạy failover test.","warning");return
        if not messagebox.askyesno("Live Failover",
            f"HMS sẽ tạm disable {email}, gửi đúng 1 request nhỏ rồi tự restore. Tiếp tục?",parent=self.root):
            return
        self.busy=True
        self.failover_result.configure(state="normal");self.failover_result.delete("1.0","end")
        self.failover_result.insert("1.0","Đang chạy bounded failover test...");self.failover_result.configure(state="disabled")
        def worker():
            data=self.backend("run_failover",120,payload={"email":email})
            self.root.after(0,lambda:self._finish_service_action(data,"failover"))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_service_action(self,data,kind):
        self.busy=False
        if data.get("ok"): self._apply_service(data)
        if kind=="failover" and hasattr(self,"failover_result"):
            r=data.get("failover_result") or {}
            text=(f"VERDICT: {r.get('verdict','FAIL')}\nHTTP: {r.get('http',0)}\n"
                  f"TARGET: {r.get('target','—')}\nSELECTED: {r.get('selected','—')}\n"
                  f"RESTORED: {r.get('restored',False)}\n\n{r.get('detail') or data.get('error','')}")
            self.failover_result.configure(state="normal");self.failover_result.delete("1.0","end")
            self.failover_result.insert("1.0",text);self.failover_result.configure(state="disabled")
        msg=data.get("message") or data.get("error") or "Hoàn tất."
        self.toast(msg,"success" if data.get("ok") else "danger")
        self.refresh_async()

    def load_accounts_async(self):
        if self.busy:
            return
        if hasattr(self, "account_center_status"):
            self.account_center_status.configure(text="Đang đọc Account Center...", fg=C["muted"])
        def worker():
            data = self.backend("get_accounts", 40)
            self.root.after(0, lambda: self._apply_account_center(data))
        threading.Thread(target=worker, daemon=True).start()

    def refresh_quota_async(self):
        if self.busy:
            return
        self.busy = True
        self.refresh_quota_btn.set_enabled(False)
        self.add_account_btn.set_enabled(False)
        self.account_center_status.configure(
            text="Đang đọc quota trực tiếp cho toàn bộ account...", fg=C["warning"]
        )
        def worker():
            data = self.backend("refresh_quota", 120)
            self.root.after(0, lambda: self._finish_quota_refresh(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_quota_refresh(self, data):
        self.busy = False
        self.refresh_quota_btn.set_enabled(True)
        self.add_account_btn.set_enabled(True)
        self._apply_account_center(data)
        if data.get("ok"):
            self.toast(data.get("message", "Đã làm mới quota."), "success")
            self.refresh_async()
        else:
            self.toast(data.get("error", "Làm mới quota thất bại."), "danger")

    def add_codex_account(self):
        if self.busy:
            return
        self.busy = True
        self.add_account_btn.set_enabled(False)
        self.refresh_quota_btn.set_enabled(False)
        self.account_center_status.configure(
            text="Đang mở OAuth Codex. Hoàn tất đăng nhập trong trình duyệt...", fg=C["primary"]
        )
        def worker():
            data = self.backend("add_codex", 270)
            self.root.after(0, lambda: self._finish_add_codex(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_add_codex(self, data):
        self.busy = False
        self.add_account_btn.set_enabled(True)
        self.refresh_quota_btn.set_enabled(True)
        self._apply_account_center(data)
        if data.get("ok"):
            self.toast(data.get("message", "OAuth hoàn tất."), "success")
            self.refresh_async()
        else:
            self.toast(data.get("error", "OAuth thất bại."), "danger")

    def official_auth_switch_async(self, email):
        if self.busy or not email:
            return
        if not messagebox.askyesno(
            "Chuyển Official Codex Auth",
            f"Chuyển Codex sang tài khoản {email}?\n\nHMS sẽ snapshot auth hiện tại, serialize switch, verify readback và chỉ restart Codex sau khi commit hợp lệ.",
            parent=self.root
        ):
            return
        self.busy = True
        self.account_center_status.configure(text=f"Đang chuyển Official Auth → {email}...", fg=C["warning"])
        def worker():
            fd, name = tempfile.mkstemp(prefix="hms-v2559-auth-switch-", suffix=".json")
            os.close(fd); rp = Path(name)
            try:
                cmd=["powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-WindowStyle","Hidden",
                     "-File",str(BACKEND),"-OfficialAuthSwitchEmail",email,"-OfficialAuthSwitchResultPath",str(rp)]
                p=subprocess.run(cmd,cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=CREATE_NO_WINDOW,timeout=90,check=False)
                if rp.exists() and rp.stat().st_size:
                    try: data=json.loads(rp.read_text(encoding="utf-8-sig",errors="replace"))
                    except Exception as e: data={"ok":False,"error":f"Official Auth result JSON lỗi: {e}","exit_code":p.returncode}
                else:
                    data={"ok":False,"error":f"Official Auth switch không tạo result (exit={p.returncode})."}
            except subprocess.TimeoutExpired:
                data={"ok":False,"error":"Official Auth switch timeout; auth snapshot/rollback guard vẫn được backend giữ."}
            except Exception as e:
                data={"ok":False,"error":f"Không thể gọi Official Auth switch: {e}"}
            finally:
                try: rp.unlink(missing_ok=True)
                except Exception: pass
            self.root.after(0, lambda: self._finish_official_auth_switch(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_official_auth_switch(self, data):
        self.busy=False
        if data.get("ok"):
            self.toast(data.get("message","Đã chuyển Official Codex auth."),"success")
            self.account_center_status.configure(text=data.get("message","Official Auth switch PASS"),fg=C["success"])
            self.refresh_async()
        else:
            err=data.get("error","Official Auth switch thất bại.")
            self.toast(err,"danger")
            self.account_center_status.configure(text=err,fg=C["danger"])

    def set_account_disabled_async(self, email, disabled):
        if self.busy:
            return
        self.busy = True
        self.account_center_status.configure(
            text=("Đang tạm dừng " if disabled else "Đang kích hoạt ") + email + "...",
            fg=C["warning"]
        )
        def worker():
            data = self.backend(
                "set_account_disabled", 45,
                payload={"email": email, "disabled": bool(disabled)}
            )
            self.root.after(0, lambda: self._finish_account_toggle(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_account_toggle(self, data):
        self.busy = False
        self._apply_account_center(data)
        if data.get("ok"):
            self.toast(data.get("message", "Đã cập nhật account."), "success")
            self.refresh_async()
        else:
            self.toast(data.get("error", "Không cập nhật được account."), "danger")

    def _apply_account_center(self, data):
        self.account_center_data = data or {}
        if not data.get("ok"):
            if hasattr(self, "account_center_status"):
                self.account_center_status.configure(
                    text=data.get("error", "Không đọc được Account Center."), fg=C["danger"]
                )
            return

        summary = data.get("summary") or {}
        if hasattr(self, "account_summary_labels"):
            for key in ("total", "ready", "route_eligible", "hold", "stale", "favorite"):
                self.account_summary_labels[key].configure(text=str(summary.get(key, 0)))
            self.account_summary_labels["route_eligible"].configure(fg=C["success"] if summary.get("route_eligible",0) else C["danger"])
            self.account_summary_labels["hold"].configure(fg=C["warning"] if summary.get("hold",0) else C["text"])
            self.account_summary_labels["stale"].configure(fg=C["danger"] if summary.get("stale",0) else C["text"])
        if hasattr(self,"account_route_banner"):
            active=summary.get("active_route") or "—"
            eligible=summary.get("active_route_eligible")
            self.account_route_banner.configure(
                text=f"ACTIVE ROUTE {active} · {'ROUTE OK' if eligible is True else ('HOLD' if eligible is False else '—')}",
                fg=C["success"] if eligible is True else (C["warning"] if eligible is False else C["text2"])
            )

        accounts = data.get("accounts") or []
        direct = "ON" if data.get("quota_direct_enabled") else "OFF"
        autoq = "AUTO" if data.get("quota_auto_enabled") else "MANUAL"
        top = summary.get("top_account") or "—"
        top_score = summary.get("top_score", 0)
        route_ok=summary.get("route_eligible",0); hold=summary.get("hold",0); stale=summary.get("stale",0); aging=summary.get("aging",0)
        utc=data.get("usage_token_center") or {}
        usm=utc.get("summary") or {}
        usage_note=(f" · Usage/Token {usm.get('cards',0)} card · RESET PREVIEW SCENARIO ONLY" if utc else " · Usage/Token unavailable")
        self.account_center_status.configure(
            text=f"Operator Pulse · ROUTE OK {route_ok} · HOLD {hold} · STALE {stale} · AGING {aging} · TOP {top} ({top_score}/100) · Direct quota {direct} · {autoq}{usage_note}",
            fg=C["success"] if route_ok and not stale else (C["warning"] if route_ok else C["danger"])
        )
        self._render_account_center(self._filtered_account_items())

    def _usage_account_ref(self, email):
        value=str(email or "").strip().lower()
        return "acct-"+hashlib.sha256(value.encode("utf-8",errors="replace")).hexdigest()[:16] if value else "acct-unknown"

    def _usage_card_for(self, email):
        center=(self.account_center_data or {}).get("usage_token_center") or {}
        ref=self._usage_account_ref(email)
        for card in center.get("cards") or []:
            if str(card.get("account_ref") or "")==ref:
                return card
        return {}

    def _usage_preview_for(self, email):
        center=(self.account_center_data or {}).get("usage_token_center") or {}
        preview=center.get("router_preview") or {}
        ref=self._usage_account_ref(email)
        now_row=next((x for x in preview.get("now") or [] if str(x.get("account_ref") or "")==ref),{})
        after_row=next((x for x in preview.get("after_next_reset") or [] if str(x.get("account_ref") or "")==ref),{})
        return now_row,after_row,preview

    def _filtered_account_items(self):
        accounts=list((self.account_center_data or {}).get("accounts") or [])
        mode=self.account_filter_var.get().strip().upper() if hasattr(self,"account_filter_var") else "TẤT CẢ"
        query=self.account_search_var.get().strip().lower() if hasattr(self,"account_search_var") else ""
        out=[]
        for item in accounts:
            quota=item.get("quota") or {}
            fresh=str(quota.get("freshness_state") or "UNKNOWN").upper()
            route_ok=bool(quota.get("routing_eligible"))
            if mode=="ROUTE OK" and not route_ok: continue
            if mode=="HOLD" and route_ok: continue
            if mode=="STALE" and fresh not in ("STALE","UNKNOWN"): continue
            if mode=="FAVORITE" and not bool(item.get("favorite")): continue
            if query:
                hay=" ".join(str(item.get(k) or "") for k in ("email","alias","group","plan","status","pool_role")).lower()
                if query not in hay: continue
            out.append(item)
        return out

    def _quota_bar(self, parent, label, remaining, reset_text, reset_at_text, y):
        if remaining is None:
            tk.Label(
                parent, text=f"{label}: chưa có dữ liệu",
                bg=C["surface"], fg=C["muted"], font=("Segoe UI", 8)
            ).place(x=16, y=y)
            return
        remaining = max(0, min(100, int(remaining)))
        color = C["success"] if remaining >= 35 else (
            C["warning"] if remaining >= 15 else C["danger"]
        )
        tk.Label(
            parent, text=label, bg=C["surface"], fg=C["text2"],
            font=("Segoe UI Semibold", 8)
        ).place(x=16, y=y)
        tk.Label(
            parent, text=f"{remaining}% còn lại", bg=C["surface"], fg=color,
            font=("Segoe UI Semibold", 9)
        ).place(x=135, y=y-1)
        tk.Label(
            parent, text=f"Đặt lại sau {reset_text or '—'} · Đặt lại lúc {reset_at_text or '—'}", bg=C["surface"], fg=C["muted"],
            font=("Segoe UI", 7)
        ).place(relx=1, x=-16, y=y+1, anchor="ne")
        bar_bg = tk.Frame(parent, bg="#2c394c", height=5)
        bar_bg.place(x=16, y=y+23, relwidth=1, width=-32)
        bar_fill = tk.Frame(bar_bg, bg=color, height=5)
        bar_fill.place(x=0, y=0, relwidth=0, relheight=1)
        self._animate_quota_fill(bar_fill, remaining)

    def _render_account_center(self, accounts):
        for w in self.accounts_grid.winfo_children():
            w.destroy()

        if not accounts:
            empty = tk.Frame(
                self.accounts_grid, bg=C["surface"],
                highlightbackground=C["border_soft"], highlightthickness=1
            )
            empty.pack(fill="x", padx=(2, 12), pady=8)
            tk.Label(
                empty, text="Chưa có tài khoản Codex",
                bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 11)
            ).pack(anchor="w", padx=18, pady=(18, 4))
            tk.Label(
                empty, text="Đổi bộ lọc/từ khóa, hoặc bấm THÊM TÀI KHOẢN nếu pool đang trống.",
                bg=C["surface"], fg=C["text2"], font=("Segoe UI", 8)
            ).pack(anchor="w", padx=18, pady=(0, 18))
            return

        for item in accounts:
            quota = item.get("quota") or {}
            code_review = quota.get("code_review") or {}
            additional = quota.get("additional_windows") or []
            monthly = quota.get("monthly_credits") or {}
            reset_credits = quota.get("reset_credits_available")
            usage_card = self._usage_card_for(item.get("email"))
            preview_now, preview_after, preview_meta = self._usage_preview_for(item.get("email"))

            extra_rows = 1 if usage_card else 0
            if code_review:
                extra_rows += 1
            if monthly:
                extra_rows += 1
            if reset_credits is not None:
                extra_rows += 1
            if quota.get("package_expiry_utc"):
                extra_rows += 1
            extra_rows += min(6, len(additional))
            height = 233 + extra_rows * 34

            card = tk.Frame(
                self.accounts_grid, bg=C["surface"],
                highlightbackground=C["border_soft"], highlightthickness=1,
                height=height
            )
            card.pack(fill="x", padx=(2, 12), pady=7)
            card.pack_propagate(False)

            email = item.get("email") or "—"
            plan = item.get("plan") or "—"
            status = item.get("status") or "—"
            disabled = bool(item.get("disabled"))
            health_score = item.get("health_score", 0)
            health_grade = item.get("health_grade") or "—"

            avatar = tk.Canvas(card, width=38, height=38, bg=C["surface"],
                               highlightthickness=0, bd=0)
            rounded_rect(avatar, 1, 1, 37, 37, 11,
                         fill="#1c355e", outline="#315887", width=1)
            avatar.create_text(19, 19, text=email[:1].upper(),
                               fill="#79a8ff", font=("Segoe UI Semibold", 13))
            avatar.place(x=16, y=14)

            tk.Label(card, text=email, bg=C["surface"], fg=C["text"],
                     font=("Segoe UI Semibold", 10)).place(x=64, y=13)
            tk.Label(card, text=plan, bg="#27374b", fg=C["text2"],
                     font=("Segoe UI Semibold", 7), padx=7, pady=2).place(x=64, y=39)

            status_color = C["success"] if status == "READY" else (
                C["warning"] if status in ("COOLDOWN", "DISABLED") else C["danger"]
            )
            tk.Label(
                card, text="● " + status, bg=C["surface"], fg=status_color,
                font=("Segoe UI Semibold", 8)
            ).place(x=210, y=18)
            tk.Label(
                card, text=f"Health {health_grade} · {health_score}/100",
                bg=C["surface"], fg=C["text2"], font=("Segoe UI Semibold", 8)
            ).place(x=210, y=42)
            if item.get("is_recent_route"):
                tk.Label(
                    card, text="ROUTE GẦN NHẤT", bg="#1d4e78", fg="#bfdbfe",
                    font=("Segoe UI Semibold", 7), padx=7, pady=2
                ).place(x=370, y=17)

            usage = item.get("usage") or {}
            role_map = {"preferred":"ƯU TIÊN", "reserve":"DỰ PHÒNG", "auto":"AUTO"}
            role = role_map.get(str(item.get("pool_role") or "auto").lower(), "AUTO")
            pool_text = (f"#{item.get('pool_rank','—')} · {role} · HMS Score {item.get('pool_score',0)}/100"
                         f" · REQ {usage.get('request_signals',0)} · ROUTE {usage.get('route_signals',0)}")
            tk.Label(card, text=pool_text, bg=C["surface"], fg=C["accent"],
                     font=("Segoe UI Semibold", 8)).place(x=16, y=67)
            fresh = str(quota.get("freshness_state") or "UNKNOWN").upper()
            reserve = quota.get("reserve_pct")
            usable = quota.get("usable_remaining_pct")
            route_ok = bool(quota.get("routing_eligible"))
            live_color = C["success"] if route_ok and fresh == "FRESH" else (C["warning"] if fresh == "AGING" else C["danger"])
            live_text = f"LIVE {fresh} · RESERVE {reserve if reserve is not None else '—'}% · USABLE {usable if usable is not None else '—'}% · {'ROUTE OK' if route_ok else 'HOLD NEW SESSION'}"
            tk.Label(card, text=live_text, bg=C["surface"], fg=live_color,
                     font=("Segoe UI Semibold", 7)).place(relx=1, x=-16, y=68, anchor="ne")
            reasons=quota.get("reason_codes") or []
            if (not route_ok) and reasons:
                tk.Label(card,text="WHY HOLD: "+" · ".join(str(x) for x in reasons[:3]),bg=C["surface"],fg=C["warning"],
                         font=("Segoe UI",7)).place(relx=1,x=-16,y=82,anchor="ne")
            alias = item.get("alias") or ""
            group = item.get("group") or ""
            if alias or group:
                tk.Label(card, text=("Tên: " + alias if alias else "") + ((" · Nhóm: " + group) if group else ""),
                         bg=C["surface"], fg=C["muted"], font=("Segoe UI", 7)).place(x=390, y=68)

            auth_switch = HoverButton(
                card, "CHUYỂN AUTH", lambda e=email: self.official_auth_switch_async(e),
                width=98, height=29, bg="#28496f", hover="#32608f", outline=C["border"],
                font=("Segoe UI Semibold", 7),
                tooltip="Official Auth v25.59: snapshot → serialized switch → readback → rollback guard → controlled Codex restart."
            )
            auth_switch.place(relx=1, x=-332, y=15)

            policy = HoverButton(
                card, "CHÍNH SÁCH", lambda it=item: self.show_account_policy_dialog(it),
                width=96, height=29, bg=C["surface3"], hover=C["hover"], outline=C["border"],
                font=("Segoe UI Semibold", 7),
                tooltip="Đặt alias, group, vai trò ưu tiên/dự phòng và favorite trong HMS. Không sửa/xóa token."
            )
            policy.place(relx=1, x=-226, y=15)

            toggle = HoverButton(
                card,
                "KÍCH HOẠT" if disabled else "TẠM DỪNG",
                lambda e=email, d=not disabled: self.set_account_disabled_async(e, d),
                width=104, height=29,
                bg="#245844" if disabled else "#59383b",
                hover="#2f7157" if disabled else "#70464a",
                font=("Segoe UI Semibold", 7),
                tooltip="Chỉ thay đổi trạng thái disabled của credential; không xóa token."
            )
            toggle.place(relx=1, x=-120, y=15)

            # Main OAuth rate-limit windows (Cockpit-style 5h / Weekly).
            self._quota_bar(
                card, "5 giờ",
                quota.get("five_hour_remaining"),
                quota.get("five_hour_reset_text"), quota.get("five_hour_reset_at_text"), 96
            )
            self._quota_bar(
                card, "Tuần",
                quota.get("weekly_remaining"),
                quota.get("weekly_reset_text"), quota.get("weekly_reset_at_text"), 142
            )

            y = 191
            if usage_card:
                nr=preview_now.get("rank","—"); ar=preview_after.get("rank","—")
                scenario=str(preview_meta.get("after_reset_label") or "SCENARIO ONLY")
                src=usage_card.get("source") or "UNKNOWN"; fresh=usage_card.get("freshness_state") or "UNKNOWN"
                tk.Label(card,text="ROUTER PREVIEW",bg=C["surface"],fg=C["text2"],font=("Segoe UI Semibold",8)).place(x=16,y=y)
                tk.Label(card,text=f"NOW #{nr} · AFTER RESET #{ar} · {scenario} · {src}/{fresh}",bg=C["surface"],fg=C["warning"],font=("Segoe UI Semibold",7)).place(x=135,y=y+1)
                y += 34
            if quota.get("package_expiry_utc"):
                tk.Label(card,text="HẾT HẠN GÓI",bg=C["surface"],fg=C["text2"],font=("Segoe UI Semibold",8)).place(x=16,y=y)
                pkg=f"còn {quota.get('package_remaining_text') or '—'} · {quota.get('package_expiry_text') or '—'}"
                tk.Label(card,text=pkg,bg=C["surface"],fg=C["accent"],font=("Segoe UI Semibold",8)).place(x=135,y=y)
                y += 34
            # Code review quota, when upstream exposes it.
            if code_review:
                primary = code_review.get("primary_remaining")
                secondary = code_review.get("secondary_remaining")
                values = []
                if primary is not None:
                    values.append(f"Primary {primary}%")
                if secondary is not None:
                    values.append(f"Secondary {secondary}%")
                text = " · ".join(values) if values else "có dữ liệu"
                tk.Label(
                    card, text="Code Review", bg=C["surface"], fg=C["text2"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=16, y=y)
                tk.Label(
                    card, text=text, bg=C["surface"], fg=C["primary"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=135, y=y)
                y += 34

            # Business/monthly credit or credit-balance payload.
            if monthly:
                mode = monthly.get("mode")
                if monthly.get("unlimited"):
                    text = "Không giới hạn"
                elif monthly.get("remaining_percent") is not None:
                    text = (
                        f"{monthly.get('remaining_percent')}% còn lại"
                        f" · {monthly.get('remaining','—')}/{monthly.get('total','—')}"
                    )
                elif monthly.get("balance") not in (None, ""):
                    text = f"Balance {monthly.get('balance')}"
                else:
                    text = "Có dữ liệu credits"
                tk.Label(
                    card, text="Monthly / Credits", bg=C["surface"], fg=C["text2"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=16, y=y)
                tk.Label(
                    card, text=text, bg=C["surface"], fg=C["accent"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=135, y=y)
                y += 34

            if reset_credits is not None:
                tk.Label(
                    card, text="Reset credits", bg=C["surface"], fg=C["text2"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=16, y=y)
                tk.Label(
                    card, text=f"{reset_credits} lượt khả dụng",
                    bg=C["surface"], fg=C["primary"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=135, y=y)
                y += 34

            # Additional model-specific windows (e.g. Codex Spark).
            for window in additional[:6]:
                name = window.get("limit_name") or window.get("metered_feature") or "Quota bổ sung"
                label = window.get("label") or "Window"
                rem = window.get("remaining")
                reset = window.get("reset_text") or "—"
                reset_at = window.get("reset_at_text") or "—"
                tk.Label(
                    card, text=str(name)[:32], bg=C["surface"], fg=C["text2"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=16, y=y)
                value = f"{label}: {rem}% còn lại" if rem is not None else f"{label}: —"
                tk.Label(
                    card, text=value, bg=C["surface"], fg=C["primary"],
                    font=("Segoe UI Semibold", 8)
                ).place(x=230, y=y)
                tk.Label(
                    card, text=f"reset {reset} · lúc {reset_at}", bg=C["surface"], fg=C["muted"],
                    font=("Segoe UI", 7)
                ).place(relx=1, x=-16, y=y+1, anchor="ne")
                y += 34

            refreshed = quota.get("refreshed_utc") or "chưa refresh"
            if refreshed and refreshed != "chưa refresh":
                try:
                    refreshed = datetime.datetime.fromisoformat(
                        str(refreshed).replace("Z", "+00:00")
                    ).astimezone().strftime("%d/%m %H:%M")
                except Exception:
                    refreshed = str(refreshed)

            footer_y = height - 24
            footer = (
                f"OAuth/token hết hạn: {item.get('token_expiry') or '—'}"
                f"   ·   P/W: {item.get('priority',0)}/{item.get('weight',1)}"
                f"   ·   Quota cập nhật: {refreshed}"
            )
            tk.Label(
                card, text=footer, bg=C["surface"], fg=C["muted"],
                font=("Segoe UI", 7)
            ).place(x=16, y=footer_y)

            qerr = quota.get("error")
            if qerr:
                tk.Label(
                    card, text="Quota lỗi: " + str(qerr)[:70],
                    bg=C["surface"], fg=C["danger"], font=("Segoe UI", 7)
                ).place(relx=1, x=-16, y=footer_y, anchor="ne")

            def enter(_=None, frame=card):
                frame.configure(highlightbackground=mix(C["border"], C["primary"], .55))
            def leave(_=None, frame=card):
                frame.configure(highlightbackground=C["border_soft"])
            card.bind("<Enter>", enter)
            card.bind("<Leave>", leave)

    def _update_diag(self):
        if not hasattr(self, "diag"):
            return
        self.diag.configure(state="normal")
        self.diag.delete("1.0", "end")
        self.diag.insert("1.0", json.dumps(self.status_data, ensure_ascii=False, indent=2))
        self.diag.configure(state="disabled")

    def show_account_policy_dialog(self, item):
        if self.busy:
            return
        win = tk.Toplevel(self.root); win.title("Chính sách Account Pool")
        win.configure(bg=C["bg2"]); win.resizable(False, False); win.transient(self.root); win.grab_set()
        try: win.attributes("-topmost", True)
        except Exception: pass
        win.geometry("500x355")
        tk.Label(win, text=item.get("email") or "—", bg=C["bg2"], fg=C["text"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=22, pady=(20,4))
        tk.Label(win, text="Metadata HMS độc lập với OAuth token. Vai trò này điều khiển HMS Rank/advisory pool.",
                 bg=C["bg2"], fg=C["muted"], font=("Segoe UI",7)).pack(anchor="w", padx=22, pady=(0,14))
        form=tk.Frame(win,bg=C["bg2"]); form.pack(fill="x",padx=22)
        alias=tk.StringVar(value=item.get("alias") or "")
        group=tk.StringVar(value=item.get("group") or "")
        role=tk.StringVar(value=str(item.get("pool_role") or "auto").lower())
        fav=tk.BooleanVar(value=bool(item.get("favorite")))
        for label,var,row in (("Tên gợi nhớ",alias,0),("Nhóm",group,1)):
            tk.Label(form,text=label,bg=C["bg2"],fg=C["text2"],font=("Segoe UI Semibold",8)).grid(row=row,column=0,sticky="w",pady=6)
            e=tk.Entry(form,textvariable=var,bg=C["surface3"],fg=C["text"],insertbackground=C["text"],relief="flat",font=("Segoe UI",9))
            e.grid(row=row,column=1,sticky="ew",padx=(14,0),pady=6,ipady=6)
        tk.Label(form,text="Vai trò",bg=C["bg2"],fg=C["text2"],font=("Segoe UI Semibold",8)).grid(row=2,column=0,sticky="w",pady=6)
        combo=ttk.Combobox(form,textvariable=role,values=["auto","preferred","reserve"],state="readonly",style="HMS.TCombobox")
        combo.grid(row=2,column=1,sticky="ew",padx=(14,0),pady=6)
        cb=tk.Checkbutton(form,text="Favorite / tăng ưu tiên mềm",variable=fav,bg=C["bg2"],fg=C["text2"],selectcolor=C["surface3"],activebackground=C["bg2"],activeforeground=C["text"],font=("Segoe UI",8))
        cb.grid(row=3,column=1,sticky="w",padx=(10,0),pady=6)
        form.grid_columnconfigure(1,weight=1)
        actions=tk.Frame(win,bg=C["bg2"]); actions.pack(fill="x",padx=22,pady=(18,0))
        HoverButton(actions,"HỦY",win.destroy,width=92,height=31,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",8)).pack(side="right")
        def save():
            win.destroy(); self.set_account_meta_async(item.get("email") or "", alias.get(), group.get(), role.get(), fav.get())
        HoverButton(actions,"LƯU CHÍNH SÁCH",save,width=132,height=31,bg=C["primary"],hover=C["primary_hover"],font=("Segoe UI Semibold",8)).pack(side="right",padx=(0,8))

    def set_account_meta_async(self, email, alias, group, role, favorite):
        if self.busy: return
        self.busy=True
        self.account_center_status.configure(text=f"Đang cập nhật Pool Policy cho {email}...",fg=C["warning"])
        def worker():
            data=self.backend("set_account_meta",45,payload={"email":email,"alias":alias,"group":group,"role":role,"favorite":bool(favorite)})
            self.root.after(0,lambda:self._finish_account_meta(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_account_meta(self, data):
        self.busy=False; self._apply_account_center(data)
        self.toast(data.get("message") if data.get("ok") else data.get("error","Không lưu được Pool Policy."), "success" if data.get("ok") else "danger")
        if data.get("ok"): self.refresh_async()

    @staticmethod
    def _human_int(value):
        try:
            n = int(value or 0)
        except Exception:
            return "0"
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}B"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)

    def load_quota_center_async(self):
        if hasattr(self,"quota_center_status"):
            self.quota_center_status.configure(text="Đang đọc Advanced Quota Center...",fg=C["muted"])
        def worker():
            data=self.backend("get_quota_center",55)
            self.root.after(0,lambda:self._apply_quota_center(data))
        threading.Thread(target=worker,daemon=True).start()

    def sync_quota_center_async(self):
        if self.busy: return
        self.busy=True
        if hasattr(self,"quota_sync_btn"): self.quota_sync_btn.set_enabled(False)
        if hasattr(self,"quota_center_status"):
            self.quota_center_status.configure(text="Đang snapshot quota → SQLite + đối chiếu forecast...",fg=C["warning"])
        def worker():
            data=self.backend("sync_quota_center",120)
            self.root.after(0,lambda:self._finish_quota_center_sync(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_quota_center_sync(self,data):
        self.busy=False
        if hasattr(self,"quota_sync_btn"): self.quota_sync_btn.set_enabled(True)
        self._apply_quota_center(data)
        self.toast(data.get("message","Quota Center đã đồng bộ.") if data.get("ok") else data.get("error","Quota Center lỗi."),"success" if data.get("ok") else "danger")

    def _apply_quota_center(self,data):
        self.quota_center_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"quota_center_status"):
                self.quota_center_status.configure(text=data.get("error","Không đọc được Quota Center."),fg=C["danger"])
            return
        qc=data.get("quota_center") or {}
        payload=qc.get("data") if isinstance(qc.get("data"),dict) else qc
        rep=(payload or {}).get("report") or {}
        state=(payload or {}).get("state") or {}
        summary=rep.get("summary") or {}
        fresh=(summary.get("freshness") or {}).get("FRESH",0)
        resolved=summary.get("resolved_forecasts",0)
        if hasattr(self,"quota_summary_labels"):
            self.quota_summary_labels["accounts"].configure(text=str(summary.get("accounts",0)))
            self.quota_summary_labels["fresh"].configure(text=str(fresh),fg=C["success"] if fresh else C["text"])
            self.quota_summary_labels["alerts"].configure(text=str(summary.get("alerts",0)),fg=C["warning"] if summary.get("alerts") else C["text"])
            self.quota_summary_labels["accuracy"].configure(text=str(resolved))
        if hasattr(self,"quota_center_status"):
            updated=state.get("updated_utc") or rep.get("generated_utc") or "—"
            self.quota_center_status.configure(text=f"SQLite {summary.get('snapshots',0)} snapshot · {summary.get('forecasts',0)} forecast · cập nhật {str(updated)[:19].replace('T',' ')}",fg=C["text2"])
        if hasattr(self,"quota_grid"):
            self._render_quota_center(rep)

    def load_usage_async(self):
        if hasattr(self, "usage_status"):
            self.usage_status.configure(text="Đang đọc Usage Ledger...", fg=C["muted"])
        def worker():
            data = self.backend("get_usage", 55)
            self.root.after(0, lambda: self._apply_usage(data))
        threading.Thread(target=worker, daemon=True).start()

    def sync_usage_async(self):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "usage_sync_btn"):
            self.usage_sync_btn.set_enabled(False)
        self.usage_status.configure(text="Đang đồng bộ request trace → SQLite...", fg=C["warning"])
        def worker():
            data = self.backend("sync_usage", 90)
            self.root.after(0, lambda: self._finish_usage_sync(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_usage_sync(self, data):
        self.busy = False
        if hasattr(self, "usage_sync_btn"):
            self.usage_sync_btn.set_enabled(True)
        self._apply_usage(data)
        self.toast(data.get("message", "Usage Ledger đã đồng bộ.") if data.get("ok") else data.get("error", "Đồng bộ Usage Ledger lỗi."),
                   "success" if data.get("ok") else "danger")

    def _set_text_readonly(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _apply_usage(self, data):
        self.usage_data = data or {}
        if not data.get("ok"):
            if hasattr(self, "usage_status"):
                self.usage_status.configure(text=data.get("error", "Không đọc được Usage Ledger."), fg=C["danger"])
            return
        usage = data.get("usage") or {}
        windows = usage.get("windows") or {}
        day = ((windows.get("day") or {}).get("total") or {})
        week = ((windows.get("week") or {}).get("total") or {})
        if hasattr(self, "usage_summary_labels"):
            self.usage_summary_labels["day"].configure(text=self._human_int(day.get("requests", 0)))
            self.usage_summary_labels["week"].configure(text=self._human_int(week.get("requests", 0)))
            self.usage_summary_labels["tokens"].configure(text=self._human_int(week.get("total_tokens", 0)))
            self.usage_summary_labels["success"].configure(text=f"{float(week.get('success_rate_pct',0) or 0):.1f}%")
        sync = usage.get("sync") or {}
        rows = ((windows.get("all") or {}).get("total") or {}).get("requests", 0)
        token_cov = float(week.get("token_coverage_pct", 0) or 0)
        status = f"Ledger {rows} request · token coverage 7d {token_cov:.1f}%"
        if sync:
            status += f" · sync +{sync.get('added',0)} / ~{sync.get('updated',0)}"
        self.usage_status.configure(text=status, fg=C["text2"])
        if not (getattr(self, "usage_advisory", None) and self.usage_advisory.cget("text").startswith(("OBSERVE", "GUARDED_AUTO"))):
            self.usage_advisory.configure(text="Đang chờ Closed-loop Router đánh giá feedback theo từng instance...", fg=C["text2"])
        account_lines = ["ACCOUNT                              REQ   OK%    P95ms   TOKENS"]
        for x in (usage.get("by_account_week") or [])[:18]:
            account_lines.append(f"{str(x.get('name','—'))[:34]:34} {int(x.get('requests',0)):5d} {float(x.get('success_rate_pct',0)):6.1f} {float(x.get('latency_p95_ms',0)):8.0f} {int(x.get('total_tokens',0)):8d}")
        model_lines = ["MODEL                                REQ   OK%    P95ms   TOKENS"]
        for x in (usage.get("by_model_week") or [])[:18]:
            model_lines.append(f"{str(x.get('name','—'))[:34]:34} {int(x.get('requests',0)):5d} {float(x.get('success_rate_pct',0)):6.1f} {float(x.get('latency_p95_ms',0)):8.0f} {int(x.get('total_tokens',0)):8d}")
        recent_lines = ["TIME                 HTTP  LAT(ms) TOKENS  ACCOUNT / MODEL"]
        for x in (usage.get("recent") or [])[:40]:
            t = str(x.get("time") or "")[:19].replace("T", " ")
            recent_lines.append(f"{t:19} {int(x.get('status',0)):4d} {float(x.get('latency_ms',0) or 0):7.0f} {int(x.get('total_tokens',0)):6d}  {str(x.get('account') or '—')[:28]} / {str(x.get('model') or '—')[:24]}")
        self._set_text_readonly(self.usage_accounts_text, "\n".join(account_lines))
        self._set_text_readonly(self.usage_models_text, "\n".join(model_lines))
        self._set_text_readonly(self.usage_recent_text, "\n".join(recent_lines))

    def diagnostics_bundle_async(self):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "usage_diag_btn"):
            self.usage_diag_btn.set_enabled(False)
        self.usage_status.configure(text="Đang tạo gói chẩn đoán đã redact...", fg=C["warning"])
        def worker():
            data = self.backend("diagnostics_bundle", 90)
            self.root.after(0, lambda: self._finish_diagnostics_bundle(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_diagnostics_bundle(self, data):
        self.busy = False
        if hasattr(self, "usage_diag_btn"):
            self.usage_diag_btn.set_enabled(True)
        if data.get("ok"):
            short = str(data.get("sha256") or "")[:12]
            self.usage_status.configure(text=f"Gói chẩn đoán: {data.get('path','')} · SHA {short}", fg=C["success"])
            self.toast("Đã tạo gói chẩn đoán an toàn.", "success")
        else:
            self.usage_status.configure(text=data.get("error", "Tạo gói chẩn đoán lỗi."), fg=C["danger"])
            self.toast(data.get("error", "Tạo gói chẩn đoán lỗi."), "danger")

    def load_circuit_breaker_async(self):
        def worker():
            data = self.backend("get_circuit_breaker", 45)
            self.root.after(0, lambda: self._apply_circuit_breaker(data))
        threading.Thread(target=worker, daemon=True).start()

    def evaluate_circuit_breaker_async(self):
        self._circuit_breaker_action_async("evaluate_circuit_breaker", 90)

    def apply_circuit_breaker_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Circuit Breaker",
                                   "Áp dụng quarantine cho account OPEN?\n\nChỉ chạy khi Mode đã lưu là GUARDED_AUTO. HMS chỉ đổi disabled flag có readback; không sửa OAuth token, endpoint hoặc session affinity.",
                                   parent=self.root):
            return
        self._circuit_breaker_action_async("apply_circuit_breaker", 120)

    def reset_circuit_breaker_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Circuit Breaker",
                                   "RESET toàn bộ circuit-owned quarantine?\n\nHMS sẽ khôi phục disabled state trước khi circuit nắm quyền. Credential không bị xóa.",
                                   parent=self.root):
            return
        self._circuit_breaker_action_async("reset_circuit_breaker", 120)

    def _circuit_breaker_action_async(self, action, timeout):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "circuit_summary"):
            self.circuit_summary.configure(text="CIRCUIT · đang phân tích failover state...", fg=C["warning"])
        def worker():
            data = self.backend(action, timeout)
            self.root.after(0, lambda: self._finish_circuit_breaker(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_circuit_breaker(self, data):
        self.busy = False
        self._apply_circuit_breaker(data)
        self.toast(data.get("message", "Circuit Breaker hoàn tất.") if data.get("ok") else data.get("error", "Circuit Breaker lỗi."),
                   "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(120, self.load_accounts_async)
            self.root.after(220, self.load_closed_loop_async)

    def _apply_circuit_breaker(self, data):
        if not hasattr(self, "circuit_summary"):
            return
        if not data.get("ok"):
            self.circuit_summary.configure(text="CIRCUIT · " + data.get("error", "lỗi"), fg=C["danger"])
            return
        cb = data.get("circuit_breaker") or {}
        payload = cb.get("data") if isinstance(cb.get("data"), dict) else cb
        plan = (payload or {}).get("plan") or ((payload or {}).get("state") or {}).get("last_plan") or {}
        if not plan:
            self.circuit_summary.configure(text=f"CIRCUIT · {data.get('mode','OBSERVE')} · chưa có plan", fg=C["muted"])
            return
        summary = plan.get("summary") or {}
        mode = plan.get("mode") or data.get("mode") or "OBSERVE"
        text = (f"CIRCUIT {mode} · CLOSED {summary.get('closed',0)} · OPEN {summary.get('open',0)} · "
                f"HALF_OPEN {summary.get('half_open',0)} · transition {summary.get('transitions',0)}")
        color = C["danger"] if summary.get("open") else (C["warning"] if summary.get("half_open") else C["success"])
        self.circuit_summary.configure(text=text[:180], fg=color)

    def load_predictive_quota_async(self):
        def worker():
            data = self.backend("get_predictive_quota", 45)
            self.root.after(0, lambda: self._apply_predictive_quota(data))
        threading.Thread(target=worker, daemon=True).start()

    def evaluate_predictive_quota_async(self):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "predictive_summary"):
            self.predictive_summary.configure(text="PREDICTIVE · đang tính velocity/runway...", fg=C["warning"])
        def worker():
            data = self.backend("evaluate_predictive_quota", 90)
            self.root.after(0, lambda: self._finish_predictive_quota(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_predictive_quota(self, data):
        self.busy = False
        self._apply_predictive_quota(data)
        self.toast(data.get("message", "Predictive Quota hoàn tất.") if data.get("ok") else data.get("error", "Predictive Quota lỗi."),
                   "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(140, self.load_closed_loop_async)

    def _apply_predictive_quota(self, data):
        if not hasattr(self, "predictive_summary"):
            return
        if not data.get("ok"):
            self.predictive_summary.configure(text="PREDICTIVE · " + data.get("error", "lỗi"), fg=C["danger"])
            return
        pq = data.get("predictive_quota") or {}
        payload = pq.get("data") if isinstance(pq.get("data"), dict) else pq
        plan = (payload or {}).get("plan") or ((payload or {}).get("state") or {}).get("last_plan") or {}
        if not plan:
            self.predictive_summary.configure(text="PREDICTIVE · chưa có forecast; bấm DỰ BÁO hoặc chờ automation nền", fg=C["muted"])
            return
        summary = plan.get("summary") or {}
        rows = plan.get("accounts") or []
        top = rows[0] if rows else None
        if top:
            acct = top.get("account") or "—"
            risk = top.get("risk") or "UNKNOWN"
            h = top.get("five_hour") or {}
            eta = h.get("eta_zero_hours")
            burn = h.get("burn_pct_per_hour")
            eta_text = "—" if eta is None else f"{eta}h"
            burn_text = "—" if burn is None else f"{burn}%/h"
            text = (f"PREDICTIVE · {risk} · {acct} · burn5h {burn_text} · runway {eta_text} · "
                    f"E/H/M {summary.get('emergency',0)}/{summary.get('high',0)}/{summary.get('medium',0)}")
            color = C["danger"] if risk == "EMERGENCY" else (C["warning"] if risk in ("HIGH", "MEDIUM") else C["success"])
        else:
            text = "PREDICTIVE · chưa có account/quota để đánh giá"
            color = C["muted"]
        self.predictive_summary.configure(text=text[:190], fg=color)

    def load_closed_loop_async(self):
        def worker():
            data = self.backend("get_closed_loop_router", 45)
            self.root.after(0, lambda: self._apply_closed_loop(data))
        threading.Thread(target=worker, daemon=True).start()

    def evaluate_closed_loop_async(self):
        self._closed_loop_action_async("evaluate_closed_loop_router", 90)

    def apply_closed_loop_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Closed-loop Router",
                                   "Áp dụng priority/weight theo feedback thật cho từng Codex instance?\n\nChỉ chạy khi Mode đã lưu là GUARDED_AUTO. Stable endpoint, project binding và session affinity không đổi.",
                                   parent=self.root):
            return
        self._closed_loop_action_async("apply_closed_loop_router", 120)

    def rollback_closed_loop_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Closed-loop Router",
                                   "Hoàn tác priority/weight về snapshot Closed-loop gần nhất?\n\nKhông xóa credential và không đổi endpoint/project.",
                                   parent=self.root):
            return
        self._closed_loop_action_async("rollback_closed_loop_router", 120)

    def _closed_loop_action_async(self, action, timeout):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "usage_advisory"):
            self.usage_advisory.configure(text="Closed-loop Router đang xử lý feedback...", fg=C["warning"])
        def worker():
            data = self.backend(action, timeout)
            self.root.after(0, lambda: self._finish_closed_loop(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_closed_loop(self, data):
        self.busy = False
        self._apply_closed_loop(data)
        self.toast(data.get("message", "Closed-loop Router hoàn tất.") if data.get("ok") else data.get("error", "Closed-loop Router lỗi."),
                   "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(100, self.load_accounts_async)
            self.root.after(120, self.load_predictive_quota_async)
            self.root.after(180, self.load_circuit_breaker_async)
            self.root.after(240, self.load_project_affinity_async)

    def _apply_closed_loop(self, data):
        if not hasattr(self, "usage_advisory"):
            return
        if not data.get("ok"):
            self.usage_advisory.configure(text=data.get("error", "Closed-loop Router lỗi."), fg=C["danger"])
            return
        closed = data.get("closed_loop") or {}
        payload = closed.get("data") if isinstance(closed.get("data"), dict) else closed
        plan = (payload or {}).get("plan") or ((payload or {}).get("state") or {}).get("last_plan") or {}
        if not plan:
            self.usage_advisory.configure(text=f"{data.get('mode','OBSERVE')} · chưa có plan Closed-loop", fg=C["muted"])
            return
        summary = plan.get("summary") or {}
        instances = plan.get("instances") or []
        top = next((x for x in instances if x.get("can_switch")), instances[0] if instances else None)
        if top:
            cur = top.get("current_account") or "—"
            rec = top.get("recommended_account") or "—"
            delta = top.get("score_delta", 0)
            mode = plan.get("mode") or data.get("mode") or "OBSERVE"
            suffix = f" · {top.get('instance_name','')}" if top.get("instance_name") else ""
            if top.get("can_switch"):
                text = f"{mode} · {cur} → {rec} · Δ {delta}{suffix} · switchable {summary.get('switchable',0)}/{summary.get('instances',0)}"
                color = C["warning"]
            else:
                text = f"{mode} · giữ {cur} · best {rec} · Δ {delta}{suffix} · critical {summary.get('critical',0)}"
                color = C["success"] if not summary.get("critical") else C["warning"]
        else:
            text = f"{plan.get('mode','OBSERVE')} · chưa có managed instance/pool để đánh giá"
            color = C["muted"]
        self.usage_advisory.configure(text=text[:180], fg=color)

    def load_adaptive_async(self):
        def worker():
            data = self.backend("get_adaptive_router", 45)
            self.root.after(0, lambda: self._apply_adaptive(data))
        threading.Thread(target=worker, daemon=True).start()

    def evaluate_adaptive_async(self):
        self._adaptive_action_async("evaluate_adaptive_router", 75)

    def apply_adaptive_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Adaptive Router",
                                   "Áp dụng routing priority/weight theo plan hiện tại?\\n\\nChỉ chạy khi Mode đã lưu là GUARDED_AUTO và đủ hysteresis/gate. OAuth token không bị sửa.",
                                   parent=self.root):
            return
        self._adaptive_action_async("apply_adaptive_router", 90)

    def rollback_adaptive_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Adaptive Router",
                                   "Hoàn tác priority/weight về snapshot trước lần Adaptive apply gần nhất?\\n\\nKhông xóa account/token.",
                                   parent=self.root):
            return
        self._adaptive_action_async("rollback_adaptive_router", 90)

    def _adaptive_action_async(self, action, timeout):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "usage_advisory"):
            self.usage_advisory.configure(text="Adaptive Router đang xử lý...", fg=C["warning"])
        def worker():
            data = self.backend(action, timeout)
            self.root.after(0, lambda: self._finish_adaptive(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_adaptive(self, data):
        self.busy = False
        self._apply_adaptive(data)
        self.toast(data.get("message", "Adaptive Router hoàn tất.") if data.get("ok") else data.get("error", "Adaptive Router lỗi."),
                   "success" if data.get("ok") else "danger")
        if data.get("ok"):
            self.root.after(100, self.load_accounts_async)

    def _apply_adaptive(self, data):
        if not hasattr(self, "usage_advisory"):
            return
        if not data.get("ok"):
            self.usage_advisory.configure(text=data.get("error", "Adaptive Router lỗi."), fg=C["danger"])
            return
        adaptive = data.get("adaptive") or {}
        plan = adaptive.get("plan") or ((adaptive.get("data") or {}).get("plan") if isinstance(adaptive.get("data"), dict) else {}) or {}
        if not plan and isinstance(adaptive.get("last_plan"), dict):
            plan = adaptive.get("last_plan")
        if not plan and isinstance(adaptive.get("state"), dict):
            plan = (adaptive.get("state") or {}).get("last_plan") or {}
        mode = plan.get("mode") or data.get("mode") or "OBSERVE"
        rec = plan.get("recommended_account") or "—"
        cur = plan.get("current_account") or "—"
        delta = plan.get("score_delta", 0)
        reasons = ", ".join(plan.get("reason_codes") or [])
        if plan.get("apply_allowed"):
            text = f"{mode} · có thể chuyển {cur} → {rec} · Δ {delta}"
            color = C["warning"]
        elif rec != "—":
            text = f"{mode} · current {cur} · đề xuất {rec} · Δ {delta}" + (f" · {reasons}" if reasons else "")
            color = C["text"]
        else:
            text = f"{mode} · chưa có plan"
            color = C["muted"]
        self.usage_advisory.configure(text=text[:170], fg=color)

    def load_update_async(self):
        if hasattr(self, "update_status_label"):
            self.update_status_label.configure(text="Đang đọc...", fg=C["muted"])
        def worker():
            data = self.backend("update_status", 45)
            self.root.after(0, lambda: self._apply_update(data))
        threading.Thread(target=worker, daemon=True).start()

    def update_check_async(self):
        self._update_action_async("update_check", 60, False)

    def update_stage_async(self):
        self._update_action_async("update_stage", 240, False)

    def update_activate_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("Signed Update",
                                   "Kích hoạt release STAGED đã verify?\\n\\nHMS sẽ đổi ACTIVE pointer và giữ PREV để rollback. Không xóa release cũ.",
                                   parent=self.root):
            return
        self._update_action_async("update_activate", 180, True)

    def _update_action_async(self, action, timeout, activation):
        if self.busy:
            return
        self.busy = True
        if hasattr(self, "update_status_label"):
            self.update_status_label.configure(text="Đang xử lý...", fg=C["warning"])
        def worker():
            data = self.backend(action, timeout)
            self.root.after(0, lambda: self._finish_update_action(data, activation))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_action(self, data, activation=False):
        self.busy = False
        if data.get("ok"):
            self.toast(data.get("message", "Update action hoàn tất."), "success")
            self.load_update_async()
            if activation:
                self.load_release_async()
        else:
            if hasattr(self, "update_status_label"):
                self.update_status_label.configure(text="LỖI", fg=C["danger"])
            self.toast(data.get("error", "Update action lỗi."), "danger")

    def _apply_update(self, data):
        if not hasattr(self, "update_status_label"):
            return
        if not data.get("ok"):
            self.update_status_label.configure(text="LỖI", fg=C["danger"])
            return
        u = data.get("update") or {}
        staged = u.get("staged") or ((u.get("stage") or {}) if isinstance(u.get("stage"), dict) else {})
        current = u.get("current") or {}
        last = data.get("last_check") or {}
        last_data = (last.get("data") or {}) if isinstance(last, dict) else {}
        if staged.get("version"):
            text = f"STAGED v{staged.get('version')} · signature {'PASS' if staged.get('signature_ok') else '—'}"
            color = C["warning"]
        elif last_data.get("latest_version"):
            text = f"Feed v{last_data.get('latest_version')} · {'CÓ BẢN MỚI' if last_data.get('update_available') else 'mới nhất'}"
            color = C["warning"] if last_data.get("update_available") else C["success"]
        elif current.get("version"):
            text = f"ACTIVE v{current.get('version')} · chưa có staged update"
            color = C["text2"]
        else:
            text = "Chưa cấu hình/check update"
            color = C["muted"]
        self.update_status_label.configure(text=text, fg=color)

    def load_release_async(self):
        if hasattr(self, "release_status_label"):
            self.release_status_label.configure(text="Đang đọc...", fg=C["muted"])
        def worker():
            data = self.backend("get_release", 60)
            self.root.after(0, lambda: self._apply_release(data))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_release(self, data):
        self.release_data = data or {}
        if not hasattr(self, "release_status_label"):
            return
        if not data.get("ok"):
            self.release_status_label.configure(text="LỖI", fg=C["danger"])
            self.toast(data.get("error", "Release status lỗi."), "danger")
            return
        release = data.get("release") or {}
        cur = release.get("current") or {}
        prev = release.get("previous") or {}
        cur_v = cur.get("version") or "—"
        prev_v = prev.get("version") or "—"
        count = len(release.get("releases") or [])
        self.release_status_label.configure(text=f"ACTIVE {cur_v} · PREV {prev_v} · {count} bản", fg=C["success"] if cur.get("version") else C["text2"])

    def release_install_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("HMS Release Manager",
                                   "Đăng ký bản v25.51 vào kho release local?\n\nHMS sẽ copy + kiểm tra SHA trước khi đổi ACTIVE. Không xóa bản cũ.",
                                   parent=self.root):
            return
        self._release_action_async("release_install", 180, "Đang copy + verify + activate v25.51...")

    def release_rollback_async(self):
        if self.busy:
            return
        if not messagebox.askyesno("HMS Release Manager",
                                   "Rollback về release PREV?\n\nChỉ đổi ACTIVE pointer; không xóa bất kỳ release nào.",
                                   parent=self.root):
            return
        self._release_action_async("release_rollback", 120, "Đang rollback ACTIVE pointer...")

    def _release_action_async(self, action, timeout, text):
        self.busy = True
        if hasattr(self, "release_status_label"):
            self.release_status_label.configure(text=text, fg=C["warning"])
        def worker():
            data = self.backend(action, timeout)
            self.root.after(0, lambda: self._finish_release_action(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_release_action(self, data):
        self.busy = False
        if data.get("ok"):
            self.toast(data.get("message", "Release action hoàn tất."), "success")
            self.load_release_async()
        else:
            if hasattr(self, "release_status_label"):
                self.release_status_label.configure(text="LỖI", fg=C["danger"])
            self.toast(data.get("error", "Release action lỗi."), "danger")

    def browse_affinity_project(self):
        path=filedialog.askdirectory(title="Chọn project cho Project Affinity",parent=self.root)
        if path:
            self.project_path_var.set(path)
            self._select_matching_project_instance(path)

    def _select_matching_project_instance(self, path):
        norm=os.path.normcase(os.path.abspath(path)) if path else ""
        for label,meta in getattr(self,"project_instance_choices",{}).items():
            p=os.path.normcase(os.path.abspath(str(meta.get("project_dir") or ""))) if meta.get("project_dir") else ""
            if p==norm:
                self.project_instance_var.set(label); return

    def project_to_new_instance(self):
        path=self.project_path_var.get().strip()
        if not path:
            self.toast("Hãy chọn project trước.","warning"); return
        self.instance_project_var.set(path)
        if not self.instance_name_var.get().strip(): self.instance_name_var.set(Path(path).name[:48] or "Codex Project")
        self.show_page("instances")

    def load_project_affinity_async(self):
        if self.busy: return
        if hasattr(self,"project_status"): self.project_status.configure(text="Đang đọc Project Affinity...",fg=C["muted"])
        def worker():
            data=self.backend("get_project_affinity",60)
            self.root.after(0,lambda:self._apply_project_affinity(data))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_project_affinity(self,data):
        self.project_affinity_data=data or {}
        if not data.get("ok"):
            self.project_status.configure(text=data.get("error","Không đọc được Project Affinity."),fg=C["danger"]); return
        summary=data.get("summary") or {}
        for key in ("total","running","healthy","attention"):
            if key in self.project_summary_labels:
                val=int(summary.get(key,0) or 0); color=C["danger"] if key=="attention" and val else (C["success"] if key in ("running","healthy") and val else C["text"])
                self.project_summary_labels[key].configure(text=str(val),fg=color)
        self.project_instance_choices={}
        labels=[]
        for i in data.get("instances") or []:
            label=f"{i.get('name') or i.get('id')}  ·  {i.get('account_email','—')}"
            labels.append(label); self.project_instance_choices[label]=i
        self.project_instance_combo["values"]=labels
        if labels and self.project_instance_var.get() not in labels: self.project_instance_var.set(labels[0])
        s=data.get("settings") or {}
        self.project_status.configure(text=f"Affinity {'ON' if s.get('enabled') else 'OFF'} · Seamless {'ON' if s.get('seamless_router') else 'OFF'} · TTL {s.get('seamless_ttl_hours','—')}h · retry {s.get('seamless_retry','—')} · fallback max {s.get('fallback_max','—')}",fg=C["success"] if not int(summary.get("attention",0) or 0) else C["warning"])
        self._render_projects(data.get("projects") or [])

    def _render_projects(self,projects):
        for w in self.projects_grid.winfo_children(): w.destroy()
        if not projects:
            tk.Label(self.projects_grid,text="Chưa có Project Affinity. Tạo Codex Instance trước; HMS sẽ auto-register project.",bg=C["bg"],fg=C["text2"],font=("Segoe UI Semibold",9)).pack(anchor="w",padx=8,pady=18); return
        for item in projects:
            card=tk.Frame(self.projects_grid,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=158); card.pack(fill="x",padx=(2,12),pady=6); card.pack_propagate(False)
            state=str(item.get("state") or "—"); running=bool(item.get("running")); color=C["success"] if state in ("RUNNING","READY","SEAMLESS_FALLBACK_READY") else (C["warning"] if state=="FALLBACK_RECOMMENDED" else C["danger"])
            tk.Label(card,text=str(item.get("name") or Path(str(item.get("project_dir") or "project")).name),bg=C["surface"],fg=C["success"] if running else C["text"],font=("Segoe UI Semibold",10)).place(x=16,y=12)
            tk.Label(card,text=f"{state} · Health {item.get('primary_health','—')}/100 · 5h {item.get('hourly_remaining') if item.get('hourly_remaining') is not None else '—'}% · 7d {item.get('weekly_remaining') if item.get('weekly_remaining') is not None else '—'}%",bg=C["surface"],fg=color,font=("Segoe UI Semibold",8)).place(x=16,y=39)
            tk.Label(card,text=f"PRIMARY  {item.get('preferred_account','—')}  ·  {item.get('primary_status','—')}",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=16,y=65)
            fall=", ".join(str(x) for x in (item.get("fallback_accounts") or [])) or "—"
            reco=item.get("fallback_recommended") or "—"
            tk.Label(card,text=f"FALLBACK  {fall}  ·  đề xuất {reco}",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=16,y=84)
            tk.Label(card,text=f"ROUTER  {item.get('router_endpoint') or '—'}  ·  pool {item.get('router_pool_count',0)}  ·  {'ONLINE' if item.get('router_online') else 'OFFLINE'}",bg=C["surface"],fg=C["primary"] if item.get('seamless_enabled') else C["muted"],font=("Segoe UI",7)).place(x=16,y=103)
            tk.Label(card,text=f"PROJECT  {item.get('project_dir','—')}",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=16,y=121)
            tk.Label(card,text=str(item.get("reason") or "")[:110],bg=C["surface"],fg=C["muted"] if state in ("RUNNING","READY","SEAMLESS_FALLBACK_READY") else C["warning"],font=("Segoe UI",7)).place(x=16,y=139)
            project=str(item.get("project_dir") or "")
            HoverButton(card,"SỬA",lambda x=item:self.edit_project_affinity(x),width=58,height=27,bg=C["surface3"],hover=C["hover"],font=("Segoe UI Semibold",7)).place(relx=1,x=-292,y=18)
            HoverButton(card,"SYNC ROUTER",lambda p=project:self.sync_project_router_async(p),width=104,height=29,bg=C["surface3"],hover=C["hover"],outline=C["border"],font=("Segoe UI Semibold",7)).place(relx=1,x=-228,y=18)
            HoverButton(card,"MỞ PROJECT",lambda p=project:self.launch_project_affinity_async(p),width=104,height=29,bg="#245844",hover="#2f7157",font=("Segoe UI Semibold",7)).place(relx=1,x=-112,y=18)

    def edit_project_affinity(self,item):
        self.project_path_var.set(str(item.get("project_dir") or "")); self.project_fallback_var.set(", ".join(str(x) for x in (item.get("fallback_accounts") or [])))
        iid=str(item.get("instance_id") or "")
        for label,meta in getattr(self,"project_instance_choices",{}).items():
            if str(meta.get("id") or "")==iid: self.project_instance_var.set(label); break

    def save_project_affinity_async(self):
        if self.busy: return
        project=self.project_path_var.get().strip(); label=self.project_instance_var.get().strip(); meta=getattr(self,"project_instance_choices",{}).get(label)
        if not project or not meta:
            self.toast("Cần project và isolated instance tương ứng.","warning"); return
        fallbacks=[x.strip() for x in re.split(r"[,;\n]+",self.project_fallback_var.get()) if x.strip()]
        payload={"project_dir":project,"instance_id":str(meta.get("id") or ""),"name":Path(project).name,"fallback_accounts":fallbacks}
        self.busy=True; self.project_status.configure(text="Đang lưu Project Affinity...",fg=C["warning"])
        def worker():
            data=self.backend("save_project_affinity",60,payload=payload); self.root.after(0,lambda:self._finish_project_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def sync_project_router_async(self,project):
        if self.busy: return
        self.busy=True; self.project_status.configure(text="Đang đồng bộ Seamless Router pool...",fg=C["warning"])
        def worker():
            data=self.backend("sync_project_router",90,payload={"project_dir":project}); self.root.after(0,lambda:self._finish_project_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def launch_project_affinity_async(self,project):
        if self.busy: return
        self.busy=True; self.project_status.configure(text="Đang resolve Project → Instance → Account...",fg=C["warning"])
        def worker():
            data=self.backend("launch_project_affinity",120,payload={"project_dir":project}); self.root.after(0,lambda:self._finish_project_action(data))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_project_action(self,data):
        self.busy=False
        if data.get("ok"):
            self.toast(data.get("message","Project Affinity hoàn tất."),"success"); self._apply_project_affinity(data)
        else:
            self.project_status.configure(text=data.get("error","Project Affinity lỗi."),fg=C["danger"]); self.toast(data.get("error","Project Affinity lỗi."),"danger")

    def browse_instance_project(self):
        path=filedialog.askdirectory(title="Chọn project cho Codex instance", parent=self.root)
        if not path:
            return
        self.instance_project_var.set(path)
        if not self.instance_name_var.get().strip():
            self.instance_name_var.set(Path(path).name[:48] or "Codex Project")

    def load_instances_async(self):
        if self.busy:
            return
        if hasattr(self,"instances_status"):
            self.instances_status.configure(text="Đang đọc Codex instances...",fg=C["muted"])
        def worker():
            data=self.backend("get_instances",45)
            self.root.after(0,lambda:self._apply_instances(data))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_instances(self, data):
        self.instances_data=data or {}
        if not data.get("ok"):
            if hasattr(self,"instances_status"):
                self.instances_status.configure(text=data.get("error","Không đọc được instances."),fg=C["danger"])
            return
        summary=data.get("summary") or {}
        for key in ("total","running","ready","conflicts"):
            if key in self.instance_summary_labels:
                color=C["danger"] if key=="conflicts" and int(summary.get(key,0) or 0)>0 else (C["success"] if key in ("running","ready") and int(summary.get(key,0) or 0)>0 else C["text"])
                self.instance_summary_labels[key].configure(text=str(summary.get(key,0)),fg=color)
        accounts=[str(x.get("email")) for x in (data.get("accounts") or []) if x.get("email")]
        self.instance_account_combo["values"]=accounts
        if accounts and self.instance_account_var.get() not in accounts:
            self.instance_account_var.set(accounts[0])
        settings=data.get("settings") or {}
        if settings.get("default_launch_mode") in ("cli","desktop") and not self.instances_data.get("_mode_touched"):
            self.instance_mode_var.set(settings.get("default_launch_mode"))
        self.instances_status.configure(text=f"CODEX-ONLY · isolation {'ON' if settings.get('enforce_isolation') else 'OFF'} · identity {'ON' if settings.get('identity_isolation') else 'OFF'} · prelaunch audit {'ON' if settings.get('identity_audit_before_launch') else 'OFF'} · base port {settings.get('base_port','—')}",fg=C["success"] if not summary.get("conflicts") else C["warning"])
        self._render_instances(data.get("instances") or [])

    def _render_instances(self, instances):
        for w in self.instances_grid.winfo_children():
            w.destroy()
        if not instances:
            tk.Label(self.instances_grid,text="Chưa có managed Codex instance. Chọn project + account ở phía trên để tạo.",bg=C["bg"],fg=C["text2"],font=("Segoe UI Semibold",9)).pack(anchor="w",padx=8,pady=18)
            return
        for item in instances:
            card=tk.Frame(self.instances_grid,bg=C["surface"],highlightbackground=C["border_soft"],highlightthickness=1,height=146)
            card.pack(fill="x",padx=(2,12),pady=6); card.pack_propagate(False)
            state=item.get("state") or "—"; ok=bool(item.get("isolation_ok")); running=bool(item.get("client_running")); router=bool(item.get("router_online"))
            tk.Label(card,text=str(item.get("name") or item.get("id")),bg=C["surface"],fg=C["success"] if running else C["text"],font=("Segoe UI Semibold",10)).place(x=16,y=12)
            tk.Label(card,text=f"{state} · Isolation {'PASS' if ok else 'BLOCKED'} · Router {'ONLINE' if router else 'OFF'} · Port {item.get('port','—')}",bg=C["surface"],fg=C["success"] if ok else C["danger"],font=("Segoe UI Semibold",8)).place(x=16,y=39)
            tk.Label(card,text=f"ACC  {item.get('account_email','—')}",bg=C["surface"],fg=C["text2"],font=("Segoe UI",7)).place(x=16,y=64)
            tk.Label(card,text=f"PROJECT  {item.get('project_dir','—')}",bg=C["surface"],fg=C["muted"],font=("Segoe UI",7)).place(x=16,y=84)
            issues=", ".join(str(x) for x in (item.get("isolation_issues") or []))
            fp=str(item.get("identity_fingerprint") or "")[:12]
            identity_ok=bool(item.get("identity_ok"))
            identity_text=f"Identity {'PASS' if identity_ok else 'BLOCKED'} · FP {fp or '—'}"
            tk.Label(card,text=identity_text,bg=C["surface"],fg=C["success"] if identity_ok else C["warning"],font=("Segoe UI Semibold",7)).place(x=16,y=104)
            tk.Label(card,text=("Isolation clean" if not issues else issues[:110]),bg=C["surface"],fg=C["muted"] if not issues else C["warning"],font=("Segoe UI",7)).place(x=16,y=123)
            iid=str(item.get("id") or "")
            x=0
            if running:
                HoverButton(card,"FOCUS",lambda i=iid:self.instance_action_async("focus_instance",i),width=72,height=27,bg=C["surface3"],hover=C["hover"],font=("Segoe UI Semibold",7)).place(relx=1,x=-318,y=18)
                HoverButton(card,"RESTART",lambda i=iid:self.instance_action_async("restart_instance",i),width=82,height=27,bg="#5a481d",hover="#725c25",font=("Segoe UI Semibold",7)).place(relx=1,x=-238,y=18)
                HoverButton(card,"STOP",lambda i=iid:self.instance_action_async("stop_instance",i),width=72,height=27,bg="#5b2530",hover="#75303e",font=("Segoe UI Semibold",7)).place(relx=1,x=-146,y=18)
            else:
                HoverButton(card,"START",lambda i=iid:self.instance_action_async("start_instance",i),width=92,height=29,bg="#245844",hover="#2f7157",font=("Segoe UI Semibold",7)).place(relx=1,x=-108,y=18)

    def audit_identity_async(self):
        if self.busy:
            return
        self.busy=True
        self.instances_status.configure(text="Đang chạy Isolation Audit v25.36...",fg=C["warning"])
        def worker():
            data=self.backend("audit_identity",120,payload={})
            self.root.after(0,lambda:self._finish_instance_action(data,created=False))
        threading.Thread(target=worker,daemon=True).start()

    def create_instance_async(self):
        if self.busy:
            return
        payload={"name":self.instance_name_var.get().strip(),"project_dir":self.instance_project_var.get().strip(),"account_email":self.instance_account_var.get().strip(),"launch_mode":self.instance_mode_var.get().strip() or "cli"}
        if not payload["name"] or not payload["project_dir"] or not payload["account_email"]:
            self.toast("Cần tên instance, project và Codex account.","warning"); return
        self.busy=True; self.instances_status.configure(text="Đang tạo isolated instance...",fg=C["warning"])
        def worker():
            data=self.backend("create_instance",90,payload=payload)
            self.root.after(0,lambda:self._finish_instance_action(data,created=True))
        threading.Thread(target=worker,daemon=True).start()

    def instance_action_async(self, action, instance_id):
        if self.busy:
            return
        if action=="stop_instance" and not messagebox.askyesno("Dừng Codex instance","Dừng client + Router của instance này? Dữ liệu project/profile vẫn được giữ.",parent=self.root):
            return
        self.busy=True; self.instances_status.configure(text=f"Đang xử lý {action}...",fg=C["warning"])
        def worker():
            data=self.backend(action,120,payload={"id":instance_id})
            self.root.after(0,lambda:self._finish_instance_action(data,created=False))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_instance_action(self, data, created=False):
        self.busy=False
        if data.get("ok"):
            if created:
                self.instance_name_var.set("")
            self.toast(data.get("message","Instance action hoàn tất."),"success")
            self._apply_instances(data)
        else:
            self.instances_status.configure(text=data.get("error","Instance action lỗi."),fg=C["danger"])
            self.toast(data.get("error","Instance action lỗi."),"danger")

    def load_logs_async(self):
        if self.busy:
            return
        if hasattr(self, "logs_refresh_btn"):
            self.logs_refresh_btn.set_enabled(False)
        def worker():
            data = self.backend("get_logs", 40)
            self.root.after(0, lambda: self._apply_logs(data))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_logs(self, data):
        self.logs_data = data or {}
        if hasattr(self, "logs_refresh_btn"):
            self.logs_refresh_btn.set_enabled(True)
        if not hasattr(self, "diag"):
            return
        self.diag.configure(state="normal")
        self.diag.delete("1.0", "end")
        if not data.get("ok"):
            self.diag.insert("1.0", data.get("error", "Không đọc được log."))
            self.diag.configure(state="disabled")
            return

        lines = []
        lines.append("=== HMS / CLIProxy LOG AN TOÀN ===")
        lines.append(data.get("note", ""))
        activity = data.get("activity") or {}
        if activity.get("account"):
            lines.append("")
            lines.append("--- ROUTE GẦN NHẤT ---")
            lines.append(f"Account: {activity.get('account')}  |  Confidence: {activity.get('confidence','—')}")
            if activity.get("evidence"):
                lines.append("Evidence: " + str(activity.get("evidence"))[:500])
        events = data.get("route_events") or []
        if events:
            lines.append("")
            lines.append("--- ROUTE / FAILOVER SIGNALS ---")
            for event in events[:30]:
                lines.append(
                    f"[{event.get('type','INFO')}] {event.get('account') or '—'}  {event.get('message','')}"
                )
        lines.append("")
        router_lines = data.get("router_lines") or []
        if router_lines:
            lines.append("--- Router / HMS log gần nhất ---")
            lines.extend(str(x) for x in router_lines)
        else:
            lines.append("Chưa có router log an toàn để hiển thị.")

        req = data.get("request_logs") or []
        lines.append("")
        lines.append(f"--- Request log metadata: {len(req)} file ---")
        for item in req[:80]:
            lines.append(
                f"{item.get('updated','')}  {item.get('size',0):>9} B  {item.get('file','')}"
            )
        self.diag.insert("1.0", "\n".join(lines))
        self.diag.configure(state="disabled")

    def toggle(self):
        if self.busy:
            return
        active = bool(self.status_data.get("active"))
        action = "disable" if active else "enable"
        self.busy = True
        self.toggle_btn.set_enabled(False)
        self.open_codex_btn.set_enabled(False)
        self.status_pill.set("ĐANG TẮT..." if active else "ĐANG BẬT...", "warning")
        def worker():
            data = self.backend(action, 150)
            self.root.after(0, lambda: self._finish_action(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_action(self, data):
        self.busy = False
        self.toggle_btn.set_enabled(True)
        if not data.get("ok"):
            self.apply_status(data)
            err = data.get("error", "Lỗi backend không xác định.")
            messagebox.showwarning("HMS One-Click", err, parent=self.root)
            self.root.after(500, self.refresh_async)
            return
        self.apply_status(data)

    def open_codex(self):
        if self.busy:
            return
        if not self.status_data.get("active"):
            messagebox.showinfo("HMS", "Bấm BẬT HMS trước.", parent=self.root)
            return
        self.busy = True
        self.open_codex_btn.set_enabled(False)
        self.status_pill.set("ĐANG MỞ CODEX", "primary")
        def worker():
            data = self.backend("open_codex", 90)
            self.root.after(0, lambda: self._finish_open_codex(data))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_open_codex(self, data):
        self.busy = False
        if not data.get("ok"):
            self.open_codex_btn.set_enabled(True)
            err = data.get("error", "Không mở được Codex.")
            messagebox.showwarning("MỞ CODEX", err, parent=self.root)
            self.refresh_async()
            return
        self.apply_status(data)

    def copy_base(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.base_var.get())
        except Exception:
            pass

    def open_management(self):
        # v25.24 compatibility alias: management is native inside HMS.
        self.show_page("accounts")

    def open_runtime(self):
        try:
            os.startfile(str(ROOT))
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def _fatal_startup(exc):
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        trace("FATAL STARTUP CRASH\n" + detail)
    except Exception:
        pass
    try:
        crash_root = tk.Tk()
        crash_root.withdraw()
        messagebox.showerror(
            "HMS-AI-ROUTER — Startup Error",
            "HMS không thể dựng giao diện.\n\n"
            + str(exc)
            + "\n\nChi tiết đã ghi tại:\n"
            + str(TRACE_FILE),
            parent=crash_root,
        )
        crash_root.destroy()
    except Exception:
        pass

if __name__ == "__main__":
    try:
        HmsApp().run()
    except Exception as exc:
        _fatal_startup(exc)
