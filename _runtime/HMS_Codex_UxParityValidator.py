#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import threading
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = "25.52"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("hms_unified_ux_v2552", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def version_tuple(text: str, pattern: str) -> tuple[int, int]:
    m = re.search(pattern, text)
    return tuple(map(int, m.groups())) if m else (0, 0)


def backend_actions(ps: str) -> list[str]:
    m = re.search(r'\[ValidateSet\((.*?)\)\]\s*\[string\]\$BackendAction', ps, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def run(root: Path) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: object = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})

    ps = (root / "HMS_AI_ROUTER_v25.23.1.ps1").read_text(encoding="utf-8-sig", errors="replace")
    gui = (root / "HMS_GUI.pyw").read_text(encoding="utf-8-sig", errors="replace")
    web = (root / "HMS_Codex_UnifiedUX.py").read_text(encoding="utf-8-sig", errors="replace")
    rotation = (root / "HMS_Codex_SeamlessRotationTorture.py").read_text(encoding="utf-8-sig", errors="replace")
    rotation_validator = (root / "HMS_Codex_SeamlessRotationTortureValidator.py").read_text(encoding="utf-8-sig", errors="replace")
    adaptive = (root / "HMS_Codex_AdaptiveRouterPolicy.py").read_text(encoding="utf-8-sig", errors="replace")
    gateway = (root / "HMS_Codex_SmartGateway.py").read_text(encoding="utf-8-sig", errors="replace")
    closed = (root / "HMS_Codex_ClosedLoopRouter.py").read_text(encoding="utf-8-sig", errors="replace")
    contract = json.loads((root / "CODEX_PUBLIC_CONTRACT_V25_46.json").read_text(encoding="utf-8-sig"))

    pver = version_tuple(ps, r'\$script:Version\s*=\s*"(\d+)\.(\d+)"')
    gver = version_tuple(gui, r'APP_VERSION\s*=\s*"(\d+)\.(\d+)"')
    add("powershell_version_at_least_25_52", pver >= (25, 52), pver)
    add("native_gui_version_at_least_25_52", gver >= (25, 52), gver)

    expected = list(contract.get("backend_actions") or [])
    actual = backend_actions(ps)
    add("public_backend_contract_exact", actual == expected, f"expected={len(expected)} actual={len(actual)}")
    add("public_backend_action_count_90", len(actual) == 90, len(actual))
    add("ux_no_new_public_mutation_action", all(x not in actual for x in ("set_ux_filter", "web_action", "rotate_now")), actual[-5:])

    native_tokens = [
        'Operator UX v25.52 · Live Quota v25.50',
        '("route_eligible","ROUTE OK")',
        '("hold","HOLD")',
        '("stale","STALE")',
        '("favorite","FAVORITE")',
        'self.account_filter_var=tk.StringVar(value="TẤT CẢ")',
        'values=["TẤT CẢ","ROUTE OK","HOLD","STALE","FAVORITE"]',
        'ACTIVE ROUTE {active}',
        'HOLD NEW SESSION',
        'WHY HOLD:',
        'def _filtered_account_items(self):',
        'Operator Pulse · ROUTE OK',
    ]
    for token in native_tokens:
        if token == 'Operator UX v25.52 · Live Quota v25.50':
            ok = token in gui or ('Usage & Token Center v25.61' in gui and 'ROUTE OK' in gui and 'HOLD NEW SESSION' in gui)
        else:
            ok = token in gui
        add("native." + re.sub(r"[^a-z0-9]+", "_", token.lower())[:64], ok, token)

    ps_tokens = [
        'route_eligible=[int]$routeEligible', 'hold=[int]$hold', 'stale=[int]$stale',
        'aging=[int]$aging', 'favorite=[int]$favorite', 'active_route_eligible=',
        'Freshness=[string]$liveQuota.freshnessState', 'ReservePct=[double]$liveQuota.reservePct',
        'UsablePct=$liveQuota.usableRemainingPct', 'RouteEligible=[bool]$liveQuota.routingEligible',
        'HoldReasons=@($liveQuota.reasonCodes)', 'quota_routing=$quotaRoute',
        'operator_attention=@($operatorAttention.ToArray())', 'NO_ROUTE_ELIGIBLE_ACCOUNT', 'ACTIVE_ROUTE_HOLD',
    ]
    for token in ps_tokens:
        add("snapshot." + re.sub(r"[^a-z0-9]+", "_", token.lower())[:64], token in ps, token)

    web_tokens = [
        'Unified UX v25.52', 'Route eligible', 'Hold', 'Stale quota',
        'data-filter="ROUTE_OK"', 'data-filter="HOLD"', 'data-filter="STALE"', 'data-filter="FAVORITE"',
        'WHY HOLD:', 'Reserve', 'Usable', 'ACTIVE ROUTE', 'operator_attention',
        'CẦN CHÚ Ý', 'ACCOUNT_FILTER', 'renderAccountGrid',
    ]
    for token in web_tokens:
        add("web." + re.sub(r"[^a-z0-9]+", "_", token.lower())[:64], token in web, token)

    add("web_bind_loopback_only", '("127.0.0.1",a.port)' in web, "read-only web surface remains local-only")
    add("web_post_read_only_405", 'self.send_bytes(405' in web and 'read-only surface; use native HMS console' in web)
    add("web_security_headers", all(x in web for x in ("X-Frame-Options", "Content-Security-Policy", "Referrer-Policy", "X-Content-Type-Options")))
    add("web_no_secret_fields", all(x not in web.lower() for x in ("access_token", "refresh_token", "client_secret")), "HTML/JS must not ask for OAuth secrets")

    # v25.51 safety invariants must remain authoritative while UX evolves.
    add("rotation_engine_stays_25_51", 'VERSION = "25.51"' in rotation)
    add("rotation_validator_forward_version_compatible", "ps_main_version_at_least_25_51" in rotation_validator and "gui_main_version_at_least_25_51" in rotation_validator)
    add("adaptive_real_active_invariant", "REAL active account" in adaptive and "ineligible_active_account_rotates_new_sessions" in adaptive)
    add("gateway_affinity_invariant", "affinity is authoritative across ALL currently eligible targets" in gateway and 'return t,"AFFINITY"' in gateway)
    add("closed_loop_25_51_invariant", 'POLICY_VERSION = "25.51"' in closed and "ineligible_current_rotates_new_sessions" in closed)

    # Runtime web-surface smoke on an ephemeral loopback port.
    try:
        mod = load_module(root / "HMS_Codex_UnifiedUX.py")
        with tempfile.TemporaryDirectory(prefix="hms-v2552-ux-") as td:
            tdir = Path(td)
            sample = {
                "version": VERSION,
                "generatedUtc": datetime.now(timezone.utc).isoformat(),
                "router": {"state": "ONLINE", "pid": 1, "port": 8317},
                "pool": {"total": 2, "ready": 2, "cooldown": 0},
                "quota_routing": {"eligible": 1, "hold": 1, "fresh": 1, "aging": 0, "stale": 1, "unknown": 0},
                "operator_attention": ["STALE_QUOTA=1"],
                "accounts": [
                    {"Account": "a@example.test", "Plan": "PLUS", "Status": "READY", "RouteEligible": True, "Freshness": "FRESH", "ReservePct": 15, "UsablePct": 55, "HourlyValue": 80, "WeeklyValue": 70, "Health": 95, "Circuit": "CLOSED", "Favorite": True},
                    {"Account": "b@example.test", "Plan": "FREE", "Status": "READY", "RouteEligible": False, "Freshness": "STALE", "ReservePct": 25, "UsablePct": 0, "HourlyValue": 20, "WeeklyValue": 10, "Health": 80, "Circuit": "CLOSED", "HoldReasons": ["QUOTA_STALE"]},
                ],
                "instances": [], "incidents": [], "ha": {"accounts": []}, "sla": {"Score": 100, "State": "HEALTHY"},
            }
            (tdir / "snapshot.json").write_text(json.dumps(sample), encoding="utf-8")
            mod.Handler.root = tdir
            srv = mod.ReuseTCPServer(("127.0.0.1", 0), mod.Handler)
            port = srv.server_address[1]
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read().decode("utf-8")
                snap = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/snapshot", timeout=3).read())
                health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3).read())
                add("runtime_html_v25_52_surface", "ROUTE OK" in html and "WHY HOLD" in html and "FAVORITE" in html)
                add("runtime_snapshot_roundtrip", snap.get("quota_routing", {}).get("hold") == 1, snap.get("quota_routing"))
                add("runtime_health_read_only", health.get("ok") is True and health.get("read_only") is True, health)
                req = urllib.request.Request(f"http://127.0.0.1:{port}/api/action", data=b'{"action":"rotate"}', method="POST", headers={"Content-Type":"application/json"})
                try:
                    urllib.request.urlopen(req, timeout=3)
                    post_code = 200
                except urllib.error.HTTPError as exc:
                    post_code = exc.code
                    post_body = exc.read().decode("utf-8", errors="replace")
                add("runtime_post_rejected_405", post_code == 405, post_code)
                add("runtime_post_rejection_message", "read-only surface" in post_body, post_body)
            finally:
                srv.shutdown(); srv.server_close(); th.join(timeout=2)
    except Exception as exc:
        add("runtime_web_smoke_exception", False, f"{type(exc).__name__}: {exc}")

    failed = [x for x in checks if not x["ok"]]
    return {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "suite": "UX_COCKPIT_PARITY_PLUS_VALIDATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS_UX_COCKPIT_PARITY_PLUS_V25_52" if not failed else "FAIL_UX_COCKPIT_PARITY_PLUS_V25_52",
        "summary": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks)},
        "checks": checks,
        "claim_boundary": "UX/control-plane parity gate only. It does not increase real Windows/Codex/quota/LAN production evidence.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--output")
    a = ap.parse_args()
    out = run(Path(a.root))
    text = json.dumps(out, ensure_ascii=False, indent=2)
    target = Path(a.output) if a.output else Path(a.root) / "UX_COCKPIT_PARITY_VALIDATION_V25.52.json"
    target.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if out["summary"]["fail"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
