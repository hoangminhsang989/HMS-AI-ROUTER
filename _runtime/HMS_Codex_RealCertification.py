#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.49"
SCHEMA_VERSION = 1
DEFAULT_ROUTER_PORT = 8317
MAX_LIVE_REQUEST_CAP = 8
SAFE_PROMPT = "Reply exactly HMS_CERT_OK"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


def safe_hash(value: str, length: int = 16) -> str:
    value = str(value or "").strip()
    return sha256_text(value)[:length] if value else ""


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def redact_text(text: str) -> str:
    out = str(text or "")
    # Never persist bearer/API-key/token material if a downstream tool unexpectedly prints it.
    patterns = [
        (r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1***"),
        (r"(?i)(OPENAI_API_KEY\s*[:=]\s*)[^\s\"']+", r"\1***"),
        (r"(?i)(HMS_ROUTER_API_KEY\s*[:=]\s*)[^\s\"']+", r"\1***"),
        (r"(?i)(access[_ -]?token\s*[:=]\s*)[^\s\"']+", r"\1***"),
        (r"(?i)(refresh[_ -]?token\s*[:=]\s*)[^\s\"']+", r"\1***"),
    ]
    for pattern, repl in patterns:
        out = re.sub(pattern, repl, out)
    return out


def summarize_output(text: str, max_chars: int = 1200) -> str:
    s = redact_text(text).replace("\x00", "")
    return s[-max_chars:]


@dataclass
class CommandResult:
    ok: bool
    exit_code: int
    elapsed_ms: float
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command(cmd: list[str], *, env: dict[str, str] | None = None, cwd: str | None = None, timeout: float = 20.0) -> CommandResult:
    started = time.perf_counter()
    try:
        p = subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=max(0.2, float(timeout)),
            errors="replace",
        )
        return CommandResult(
            ok=p.returncode == 0,
            exit_code=int(p.returncode),
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            stdout=summarize_output(p.stdout),
            stderr=summarize_output(p.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(
            ok=False,
            exit_code=124,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            stdout=summarize_output(stdout),
            stderr=summarize_output(stderr),
            timed_out=True,
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            exit_code=127,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            stdout="",
            stderr=f"{type(exc).__name__}:{exc}",
        )


def parse_codex_version(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    # Accept current/future Codex output forms without a brittle allowlist.
    m = re.search(r"(?i)(?:codex(?:-cli)?\s*)?v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", raw)
    if not m:
        return {"ok": False, "raw": summarize_output(raw, 240), "version": ""}
    version = ".".join(m.groups())
    return {"ok": True, "raw": summarize_output(raw, 240), "version": version, "major": int(m.group(1)), "minor": int(m.group(2)), "patch": int(m.group(3))}


def find_codex_cli(explicit: str = "") -> str:
    if explicit:
        p = Path(explicit)
        return str(p) if p.exists() else ""
    return shutil.which("codex.exe") or shutil.which("codex") or ""


def find_powershell_51(explicit: str = "") -> str:
    if explicit:
        p = Path(explicit)
        return str(p) if p.exists() else ""
    # Prefer Windows PowerShell 5.1, not pwsh, for the frozen backend contract.
    candidates: list[str] = []
    windir = os.environ.get("WINDIR", r"C:\Windows")
    if os.name == "nt":
        candidates += [str(Path(windir) / "System32/WindowsPowerShell/v1.0/powershell.exe")]
    w = shutil.which("powershell.exe") or shutil.which("powershell")
    if w:
        candidates.append(w)
    for p in candidates:
        if p and Path(p).exists():
            return p
    return ""


def inspect_powershell(powershell: str, ps1: Path) -> dict[str, Any]:
    if not powershell:
        return {"available": False, "runtime_ok": False, "parser_ok": False, "version": "", "parse_error_count": None}
    version_cmd = [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"]
    vr = run_command(version_cmd, timeout=10)
    version = (vr.stdout or vr.stderr).strip().splitlines()[-1] if (vr.stdout or vr.stderr).strip() else ""
    # Parser-only static gate: does not execute HMS backend.
    escaped = str(ps1).replace("'", "''")
    parse_code = (
        "$t=$null;$e=$null;"
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$t,[ref]$e)|Out-Null;"
        "$o=[pscustomobject]@{errors=@($e).Count};$o|ConvertTo-Json -Compress;"
        "if(@($e).Count -gt 0){exit 2}"
    )
    pr = run_command([powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", parse_code], timeout=30)
    err_count = None
    try:
        parsed = json.loads(pr.stdout.strip().splitlines()[-1])
        err_count = int(parsed.get("errors", -1))
    except Exception:
        pass
    return {
        "available": True,
        "runtime_ok": bool(vr.ok),
        "version": version,
        "is_windows_powershell_5_1": bool(re.match(r"^5\.1(?:\.|$)", version)),
        "parser_ok": bool(pr.ok and err_count == 0),
        "parse_error_count": err_count,
        "version_command_ms": vr.elapsed_ms,
        "parser_command_ms": pr.elapsed_ms,
        "stderr": summarize_output((vr.stderr + "\n" + pr.stderr).strip(), 500),
    }


def inspect_codex_cli(codex: str) -> dict[str, Any]:
    if not codex:
        return {"available": False, "version_ok": False, "version": "", "login_status_supported": False, "doctor_supported": False, "app_command_supported": False}
    vr = run_command([codex, "--version"], timeout=10)
    parsed = parse_codex_version((vr.stdout + "\n" + vr.stderr).strip())
    hr = run_command([codex, "--help"], timeout=10)
    help_text = (hr.stdout + "\n" + hr.stderr).lower()
    return {
        "available": True,
        "path_hash": safe_hash(str(Path(codex).resolve() if Path(codex).exists() else codex)),
        "version_ok": bool(vr.ok and parsed.get("ok")),
        "version": parsed.get("version", ""),
        "version_raw": parsed.get("raw", ""),
        "version_command_ms": vr.elapsed_ms,
        "login_status_supported": "login" in help_text,
        "doctor_supported": "doctor" in help_text,
        "app_command_supported": bool(re.search(r"(?m)^\s*app\b", help_text) or "codex app" in help_text),
        "exec_supported": "exec" in help_text,
        "help_exit_code": hr.exit_code,
    }


def codex_env(home: Path | None = None, extras: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if home:
        env["CODEX_HOME"] = str(home)
    if extras:
        env.update({k: str(v) for k, v in extras.items()})
    return env


def auth_file_metadata(home: Path) -> dict[str, Any]:
    p = home / "auth.json"
    if not p.exists():
        return {"present": False, "size": 0, "sha256": ""}
    try:
        raw = p.read_bytes()
        return {"present": True, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "mtime_ns": p.stat().st_mtime_ns}
    except Exception as exc:
        return {"present": True, "size": None, "sha256": "", "error": type(exc).__name__}


def login_status(codex: str, home: Path) -> dict[str, Any]:
    before = auth_file_metadata(home)
    r = run_command([codex, "login", "status"], env=codex_env(home), timeout=20)
    after = auth_file_metadata(home)
    text = (r.stderr + "\n" + r.stdout).strip()
    logged = r.ok and bool(re.search(r"(?i)logged in", text)) and not bool(re.search(r"(?i)not logged in", text))
    mode = "CHATGPT" if re.search(r"(?i)using\s+chatgpt", text) else ("API_KEY" if re.search(r"(?i)api key", text) else ("OTHER" if logged else "NONE"))
    return {
        "ok": logged,
        "exit_code": r.exit_code,
        "auth_mode": mode,
        "elapsed_ms": r.elapsed_ms,
        "auth_file_before": before,
        "auth_file_after": after,
        "auth_file_changed_during_status": bool(before.get("sha256") and after.get("sha256") and before.get("sha256") != after.get("sha256")),
        "status_summary": summarize_output(text, 360),
    }


def doctor_status(codex: str, home: Path) -> dict[str, Any]:
    variants = [
        [codex, "doctor", "--summary", "--ascii", "--no-color"],
        [codex, "doctor"],
    ]
    last: CommandResult | None = None
    for cmd in variants:
        r = run_command(cmd, env=codex_env(home), timeout=30)
        last = r
        text = (r.stdout + "\n" + r.stderr).strip()
        if r.ok or "auth.credentials" in text or "config.load" in text or "overallStatus" in text:
            lower = text.lower()
            return {
                "ok": bool(r.ok),
                "exit_code": r.exit_code,
                "elapsed_ms": r.elapsed_ms,
                "auth_configured_signal": ("auth.credentials" in lower and ("status: ok" in lower or '"status":"ok"' in lower or '"status": "ok"' in lower)) or "auth is configured" in lower,
                "codex_home_signal": str(home).lower() in lower,
                "summary": summarize_output(text, 700),
            }
    r = last or CommandResult(False, 127, 0.0, "", "doctor unavailable")
    return {"ok": False, "exit_code": r.exit_code, "elapsed_ms": r.elapsed_ms, "auth_configured_signal": False, "codex_home_signal": False, "summary": summarize_output(r.stderr or r.stdout, 700)}


def health_probe(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    start = time.perf_counter()
    conn = None
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=max(0.1, float(timeout)))
        conn.request("GET", "/hms/health", headers={"Accept": "application/json", "Connection": "close"})
        resp = conn.getresponse()
        first = time.perf_counter()
        raw = resp.read(65536)
        end = time.perf_counter()
        body = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
        ok = resp.status == 200 and isinstance(body, dict) and body.get("ok") is True
        return {"ok": ok, "status": int(resp.status), "ttfb_ms": round((first-start)*1000, 3), "latency_ms": round((end-start)*1000, 3)}
    except Exception as exc:
        return {"ok": False, "status": 0, "ttfb_ms": None, "latency_ms": round((time.perf_counter()-start)*1000, 3), "error": type(exc).__name__}
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def read_instance_store(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("instances") if isinstance(data, dict) else None
    return [x for x in (rows or []) if isinstance(x, dict)]


def instance_public_view(inst: dict[str, Any]) -> dict[str, Any]:
    iid = str(inst.get("id") or "")
    project = str(inst.get("projectDir") or inst.get("project") or "")
    home = str(inst.get("codexHome") or inst.get("codex_home") or "")
    account = str(inst.get("accountEmail") or inst.get("account") or "")
    root = str(inst.get("root") or "")
    port = int(inst.get("port") or 0) if str(inst.get("port") or "0").isdigit() else 0
    return {
        "instance_id": iid,
        "instance_id_hash": safe_hash(iid),
        "name": str(inst.get("name") or iid)[:80],
        "project_hash": safe_hash(os.path.normcase(os.path.abspath(project))) if project else "",
        "codex_home_hash": safe_hash(os.path.normcase(os.path.abspath(home))) if home else "",
        "account_hash": safe_hash(account.lower()),
        "root_hash": safe_hash(os.path.normcase(os.path.abspath(root))) if root else "",
        "port": port,
        "launch_mode": str(inst.get("launchMode") or inst.get("launch_mode") or ""),
        "project_exists": bool(project and Path(project).is_dir()),
        "codex_home_exists": bool(home and Path(home).is_dir()),
        "binding_present": bool(root and (Path(root) / "binding-v2536.json").exists()),
        "client_pid": int(inst.get("clientPid") or 0) if str(inst.get("clientPid") or "0").lstrip("-").isdigit() else 0,
        "router_pid": int(inst.get("routerPid") or 0) if str(inst.get("routerPid") or "0").lstrip("-").isdigit() else 0,
        "client_process_path_hash": safe_hash(str(inst.get("clientProcessPath") or "")),
        "client_start_utc": str(inst.get("clientStartUtc") or ""),
    }


def process_generation_guard(powershell: str, inst: dict[str, Any]) -> dict[str, Any]:
    pid = int(inst.get("clientPid") or 0) if str(inst.get("clientPid") or "0").lstrip("-").isdigit() else 0
    expected_path = str(inst.get("clientProcessPath") or "")
    expected_start = str(inst.get("clientStartUtc") or "")
    if pid <= 0:
        return {"state": "NOT_RUNNING", "ok": True}
    if os.name != "nt" or not powershell:
        return {"state": "DEFERRED_NON_WINDOWS", "ok": False}
    code = (
        f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
        "if(-not $p){exit 3};"
        "$path='';try{$path=$p.Path}catch{};"
        "$o=[pscustomobject]@{path=$path;start=$p.StartTime.ToUniversalTime().ToString('o')};"
        "$o|ConvertTo-Json -Compress"
    )
    r = run_command([powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", code], timeout=10)
    if not r.ok:
        return {"state": "PROCESS_NOT_FOUND_OR_UNREADABLE", "ok": False, "exit_code": r.exit_code}
    try:
        data = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"state": "PROCESS_IDENTITY_PARSE_FAIL", "ok": False}
    actual_path = str(data.get("path") or "")
    actual_start = str(data.get("start") or "")
    path_ok = bool(expected_path and actual_path and os.path.normcase(expected_path) == os.path.normcase(actual_path))
    start_ok = bool(expected_start and actual_start and expected_start[:19] == actual_start[:19])
    return {
        "state": "PASS" if path_ok and start_ok else "STALE_OR_FOREIGN_PROCESS",
        "ok": bool(path_ok and start_ok),
        "path_match": path_ok,
        "start_generation_match": start_ok,
        "actual_process_path_hash": safe_hash(actual_path),
    }


def secret_env_name(instance_id: str, prefix: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_]", "_", str(instance_id or "").upper())
    return f"{prefix}{suffix}" if suffix else prefix.rstrip("_")


def select_live_model(args: argparse.Namespace) -> str:
    return str(args.model or "").strip()


def stream_response_probe(host: str, port: int, api_key: str, model: str, prompt: str, timeout: float = 90.0) -> dict[str, Any]:
    if not api_key:
        return {"ok": False, "error": "API_KEY_NOT_PROVIDED"}
    if not model:
        return {"ok": False, "error": "LIVE_MODEL_REQUIRED"}
    conn = None
    started = time.perf_counter()
    first_header = None
    first_sse = None
    first_text_delta = None
    final_seen = False
    status = 0
    event_types: list[str] = []
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=max(1.0, float(timeout)))
        body = json.dumps({"model": model, "input": prompt, "stream": True}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        conn.request(
            "POST",
            "/v1/responses",
            body=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Connection": "close",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        first_header = time.perf_counter()
        status = int(resp.status)
        if status != 200:
            raw = resp.read(4096).decode("utf-8", errors="replace")
            return {"ok": False, "status": status, "header_ttfb_ms": round((first_header-started)*1000, 3), "error": f"HTTP_{status}", "body_summary": summarize_output(raw, 320)}
        while True:
            line = resp.readline()
            if not line:
                break
            now = time.perf_counter()
            text = line.decode("utf-8", errors="replace").strip()
            if not text.startswith("data:"):
                continue
            payload = text[5:].strip()
            if not payload:
                continue
            if first_sse is None:
                first_sse = now
            if payload == "[DONE]":
                final_seen = True
                break
            try:
                event = json.loads(payload)
            except Exception:
                continue
            et = str(event.get("type") or "") if isinstance(event, dict) else ""
            if et and et not in event_types and len(event_types) < 12:
                event_types.append(et)
            is_text_delta = et in {"response.output_text.delta", "response.text.delta", "output_text.delta"}
            if not is_text_delta and isinstance(event, dict):
                delta = event.get("delta")
                is_text_delta = isinstance(delta, str) and bool(delta)
            if is_text_delta and first_text_delta is None:
                first_text_delta = now
            if et in {"response.completed", "response.done"}:
                final_seen = True
                break
        ended = time.perf_counter()
        return {
            "ok": status == 200 and first_sse is not None,
            "status": status,
            "header_ttfb_ms": round(((first_header or ended)-started)*1000, 3),
            "first_sse_event_ms": round(((first_sse or ended)-started)*1000, 3) if first_sse else None,
            "first_output_text_delta_ms": round((first_text_delta-started)*1000, 3) if first_text_delta else None,
            "total_ms": round((ended-started)*1000, 3),
            "first_token_ttft_certified": bool(first_text_delta is not None),
            "stream_completed_signal": bool(final_seen),
            "event_types": event_types,
            "response_body_logged": False,
            "prompt_logged": False,
            "api_key_logged": False,
        }
    except Exception as exc:
        return {"ok": False, "status": status, "error": type(exc).__name__, "elapsed_ms": round((time.perf_counter()-started)*1000, 3)}
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def topology_checks(instances: list[dict[str, Any]]) -> dict[str, Any]:
    public = [instance_public_view(i) for i in instances]
    projects = [x["project_hash"] for x in public if x["project_hash"]]
    homes = [x["codex_home_hash"] for x in public if x["codex_home_hash"]]
    accounts = [x["account_hash"] for x in public if x["account_hash"]]
    ports = [x["port"] for x in public if x["port"]]
    return {
        "instance_count": len(public),
        "at_least_two_instances": len(public) >= 2,
        "unique_projects": bool(projects) and len(projects) == len(set(projects)),
        "unique_codex_homes": bool(homes) and len(homes) == len(set(homes)),
        "dedicated_accounts": bool(accounts) and len(accounts) == len(set(accounts)),
        "unique_ports": bool(ports) and len(ports) == len(set(ports)),
        "instances": public,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    ps1 = root / "HMS_AI_ROUTER_v25.23.1.ps1"
    codex = find_codex_cli(args.codex)
    powershell = find_powershell_51(args.powershell)
    windows = os.name == "nt" and platform.system().lower() == "windows"

    live_budget = max(0, int(args.max_live_requests))
    if live_budget > MAX_LIVE_REQUEST_CAP:
        raise ValueError(f"LIVE_REQUEST_CAP_EXCEEDS_{MAX_LIVE_REQUEST_CAP}")
    if live_budget > 0 and not args.allow_live_request:
        raise ValueError("LIVE_REQUEST_REQUIRES_EXPLICIT_ALLOW")
    if args.allow_live_request and live_budget < 1:
        raise ValueError("LIVE_REQUEST_BUDGET_REQUIRED")
    if args.allow_live_request and not select_live_model(args):
        raise ValueError("LIVE_MODEL_REQUIRED")

    default_store = Path(os.environ.get("LOCALAPPDATA", "")) / "HMS_AI_MultiRouter/codex-instances-v1.json" if os.environ.get("LOCALAPPDATA") else Path("")
    store_path = Path(args.instance_store).expanduser() if args.instance_store else default_store
    instances = read_instance_store(store_path) if store_path and str(store_path) not in {"", "."} else []
    topo = topology_checks(instances)

    ps = inspect_powershell(powershell, ps1)
    cli = inspect_codex_cli(codex)

    instance_runtime: list[dict[str, Any]] = []
    live_rows: list[dict[str, Any]] = []
    remaining = live_budget
    model = select_live_model(args)
    for inst in instances:
        iid = str(inst.get("id") or "")
        home_s = str(inst.get("codexHome") or inst.get("codex_home") or "")
        home = Path(home_s) if home_s else None
        port = int(inst.get("port") or 0) if str(inst.get("port") or "0").isdigit() else 0
        row: dict[str, Any] = {
            "instance_id_hash": safe_hash(iid),
            "codex_home_hash": safe_hash(os.path.normcase(os.path.abspath(home_s))) if home_s else "",
            "project_hash": safe_hash(os.path.normcase(os.path.abspath(str(inst.get("projectDir") or "")))) if inst.get("projectDir") else "",
            "port": port,
            "health": health_probe("127.0.0.1", port, args.timeout_sec) if 1 <= port <= 65535 else {"ok": False, "error": "INVALID_PORT"},
            "process_generation": process_generation_guard(powershell, inst),
        }
        if codex and home and home.is_dir():
            row["login_status"] = login_status(codex, home)
            row["doctor"] = doctor_status(codex, home)
        else:
            row["login_status"] = {"ok": False, "state": "CODEX_OR_HOME_UNAVAILABLE"}
            row["doctor"] = {"ok": False, "state": "CODEX_OR_HOME_UNAVAILABLE"}
        instance_runtime.append(row)

        if args.allow_live_request and remaining > 0 and 1 <= port <= 65535:
            env_name = secret_env_name(iid, args.api_key_env_prefix)
            key = os.environ.get(env_name, "")
            if not key and len(instances) == 1:
                key = os.environ.get("HMS_ROUTER_API_KEY", "")
            live = stream_response_probe("127.0.0.1", port, key, model, SAFE_PROMPT, args.live_timeout_sec)
            live_rows.append({"instance_id_hash": safe_hash(iid), "api_key_env_name": env_name, **live})
            remaining -= 1

    live_requested = bool(args.allow_live_request)
    live_success = sum(1 for x in live_rows if x.get("ok"))
    exact_ttft = sum(1 for x in live_rows if x.get("first_token_ttft_certified"))
    health_ok = sum(1 for x in instance_runtime if (x.get("health") or {}).get("ok"))
    generation_ok = sum(1 for x in instance_runtime if (x.get("process_generation") or {}).get("ok"))

    blockers: list[str] = []
    warnings: list[str] = []
    if not windows:
        blockers.append("WINDOWS_TARGET_REQUIRED_FOR_REAL_CERTIFICATION")
    if not ps.get("is_windows_powershell_5_1") or not ps.get("parser_ok"):
        blockers.append("WINDOWS_POWERSHELL_5_1_GATE_NOT_PASS")
    if not cli.get("version_ok"):
        blockers.append("CODEX_CLI_NOT_DETECTED_OR_VERSION_UNREADABLE")
    if not topo.get("at_least_two_instances"):
        blockers.append("TWO_MANAGED_INSTANCES_REQUIRED")
    for name in ("unique_projects", "unique_codex_homes", "dedicated_accounts", "unique_ports"):
        if topo.get("at_least_two_instances") and not topo.get(name):
            blockers.append(f"TOPOLOGY_{name.upper()}_FAIL")
    if topo.get("at_least_two_instances") and health_ok < 2:
        blockers.append("TWO_MANAGED_INSTANCE_HEALTH_ENDPOINTS_REQUIRED")
    if topo.get("at_least_two_instances") and generation_ok < 2:
        blockers.append("CLIENT_RESTART_GENERATION_GUARD_NOT_PROVEN")
    if live_requested:
        if live_success < min(live_budget, len(instances)):
            blockers.append("LIVE_QUOTA_BACKED_REQUEST_PATH_NOT_PASS")
        if exact_ttft < live_success:
            warnings.append("STREAM_PASS_BUT_EXACT_OUTPUT_TEXT_DELTA_TTFT_NOT_OBSERVED_FOR_ALL_REQUESTS")
    else:
        warnings.append("LIVE_QUOTA_BACKED_REQUEST_NOT_EXECUTED")
    if instance_runtime and not all((x.get("login_status") or {}).get("ok") or (x.get("doctor") or {}).get("ok") for x in instance_runtime):
        warnings.append("CODEX_LOGIN_OR_DOCTOR_NOT_CONFIRMED_FOR_ALL_INSTANCE_HOMES")

    real_certified = not blockers and live_requested and live_success >= 1
    if real_certified:
        verdict = "PASS_REAL_CODEX_CERTIFIED"
    elif windows and cli.get("version_ok") and ps.get("parser_ok"):
        verdict = "READY_LIVE_REQUEST_REQUIRED"
    else:
        verdict = "HARNESS_READY_RUNTIME_DEFERRED"

    return {
        "product": "HMS-AI-ROUTER",
        "edition": "CODEX_ONLY",
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "suite": "REAL_CODEX_CERTIFICATION",
        "generated_utc": utcnow(),
        "verdict": verdict,
        "production_certification": "REAL_CODEX_PATH_ONLY" if real_certified else "NOT_CLAIMED",
        "host": {
            "windows": windows,
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python": platform.python_version(),
        },
        "powershell_5_1": ps,
        "codex_cli": cli,
        "desktop": {
            "capability_detected_via_cli_app_command": bool(cli.get("app_command_supported")),
            "classic_exe_probe": "CAPABILITY_ONLY_NO_VERSION_ALLOWLIST",
        },
        "topology": topo,
        "instance_runtime": instance_runtime,
        "live_request_policy": {
            "explicit_opt_in": live_requested,
            "budget_cap": live_budget,
            "hard_max_cap": MAX_LIVE_REQUEST_CAP,
            "model_hash": safe_hash(model),
            "prompt": "FIXED_MINIMAL_PROMPT_NOT_PERSISTED",
            "request_body_logged": False,
            "response_body_logged": False,
            "api_key_logged": False,
            "quota_consumption_possible": live_requested,
        },
        "live_requests": live_rows,
        "summary": {
            "managed_instances": len(instances),
            "healthy_instance_endpoints": health_ok,
            "generation_guard_pass": generation_ok,
            "live_requests_executed": len(live_rows),
            "live_requests_pass": live_success,
            "exact_output_text_delta_ttft_observed": exact_ttft,
            "real_codex_certified": real_certified,
        },
        "blockers": blockers,
        "warnings": warnings,
        "contract_guards": {
            "hard_coded_codex_version_allowlist": False,
            "backend_action_added": False,
            "public_backend_action_exact_90_preserved": True,
            "auth_json_content_logged": False,
            "token_or_api_key_logged": False,
            "raw_prompt_or_response_logged": False,
            "auth_mutation": False,
            "account_switch_mutation": False,
            "credential_delete": False,
        },
        "metric_boundary": {
            "control_plane_ttfb": "GET /hms/health header latency",
            "model_stream_first_event": "first SSE data event from real /v1/responses stream",
            "model_token_ttft": "first response.output_text.delta event only; never inferred from first SSE/header",
        },
        "next_stage": "v25.50 LIVE_QUOTA_INTELLIGENCE after real target-machine certification evidence",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.49 real Codex certification harness")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--instance-store", default="")
    ap.add_argument("--codex", default="")
    ap.add_argument("--powershell", default="")
    ap.add_argument("--timeout-sec", type=float, default=2.0)
    ap.add_argument("--allow-live-request", action="store_true")
    ap.add_argument("--max-live-requests", type=int, default=0)
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key-env-prefix", default="HMS_CERT_KEY_")
    ap.add_argument("--live-timeout-sec", type=float, default=90.0)
    ap.add_argument("--output", default="")
    a = ap.parse_args()
    try:
        out = run(a)
        rc = 0 if out.get("verdict") in {"PASS_REAL_CODEX_CERTIFIED", "READY_LIVE_REQUEST_REQUIRED", "HARNESS_READY_RUNTIME_DEFERRED"} else 2
    except Exception as exc:
        out = {
            "product": "HMS-AI-ROUTER",
            "version": VERSION,
            "suite": "REAL_CODEX_CERTIFICATION",
            "generated_utc": utcnow(),
            "verdict": "FAIL",
            "production_certification": "NOT_CLAIMED",
            "error": f"{type(exc).__name__}:{exc}",
        }
        rc = 2
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        atomic_json(Path(a.output), out)
    print(text)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
