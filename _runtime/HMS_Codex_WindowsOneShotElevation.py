#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Iterable

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
SUPPORTED_CLIENT_NAMES = frozenset({"codex.exe", "chatgpt.exe"})
MAX_TARGET_PIDS = 32
UAC_CANCELLED_ERROR = 1223
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_CONSUMED_TOKENS: set[str] = set()
_TOKEN_LOCK = threading.Lock()


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def _windows_required() -> None:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")


def _consume_operation_token(operation_token: str) -> None:
    token = str(operation_token or "").strip()
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError("WINDOWS_ELEVATION_OPERATION_TOKEN_INVALID")
    with _TOKEN_LOCK:
        if token in _CONSUMED_TOKENS:
            raise RuntimeError("WINDOWS_ELEVATION_OPERATION_TOKEN_ALREADY_CONSUMED")
        # Consume before any UAC prompt. Cancellation/failure must not permit prompt replay.
        _CONSUMED_TOKENS.add(token)


def _normalize_pids(pids: Iterable[int]) -> list[int]:
    values = sorted({int(pid) for pid in pids if int(pid) > 0 and int(pid) != os.getpid()})
    if not values or len(values) > MAX_TARGET_PIDS:
        raise ValueError("WINDOWS_ELEVATION_TARGET_INVALID")
    return values


def _validate_target_map(pids: Iterable[int], process_map: dict[int, str]) -> list[int]:
    targets = _normalize_pids(pids)
    running: list[int] = []
    for pid in targets:
        name = str(process_map.get(pid) or "").strip().lower()
        if not name:
            # Process may have exited after the failed close attempt; treat that PID as already resolved.
            continue
        if name not in SUPPORTED_CLIENT_NAMES:
            raise ValueError(f"WINDOWS_ELEVATION_TARGET_NOT_ALLOWED: pid={pid}, process={name}")
        running.append(pid)
    return running


def _enumerate_process_map_windows() -> dict[int, str]:
    _windows_required()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, 0, INVALID_HANDLE_VALUE):
        raise OSError(ctypes.get_last_error(), "WINDOWS_PROCESS_SNAPSHOT_FAILED")
    out: dict[int, str] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            out[int(entry.th32ProcessID)] = str(entry.szExeFile)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return out


def discover_supported_client_pids() -> list[int]:
    process_map = _enumerate_process_map_windows()
    return sorted(
        pid for pid, name in process_map.items()
        if pid > 0 and pid != os.getpid() and str(name).strip().lower() in SUPPORTED_CLIENT_NAMES
    )


def validate_elevation_targets(pids: Iterable[int]) -> list[int]:
    return _validate_target_map(pids, _enumerate_process_map_windows())


def _system_taskkill_path() -> Path:
    _windows_required()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetSystemDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "WINDOWS_SYSTEM_DIRECTORY_UNAVAILABLE")
    path = (Path(buffer.value) / "taskkill.exe").resolve()
    if not path.is_file() or path.name.lower() != "taskkill.exe":
        raise FileNotFoundError(f"WINDOWS_TASKKILL_NOT_FOUND: {path}")
    return path


def _taskkill_arguments(pids: Iterable[int]) -> str:
    targets = _normalize_pids(pids)
    return " ".join([*(f"/PID {pid}" for pid in targets), "/T", "/F"])


def _run_elevated_taskkill(pids: list[int], timeout_ms: int = 120_000) -> dict[str, Any]:
    _windows_required()
    taskkill = _system_taskkill_path()
    parameters = _taskkill_arguments(pids)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = str(taskkill)
    info.lpParameters = parameters
    info.nShow = SW_HIDE

    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        err = ctypes.get_last_error()
        if err == UAC_CANCELLED_ERROR:
            raise PermissionError("WINDOWS_ELEVATION_CANCELLED")
        raise OSError(err, "WINDOWS_ELEVATION_START_FAILED")
    if not info.hProcess:
        raise RuntimeError("WINDOWS_ELEVATION_PROCESS_HANDLE_MISSING")

    try:
        wait = kernel32.WaitForSingleObject(info.hProcess, max(1, int(timeout_ms)))
        if wait == WAIT_TIMEOUT:
            raise TimeoutError("WINDOWS_ELEVATION_TIMEOUT")
        if wait != WAIT_OBJECT_0:
            raise OSError(int(wait), "WINDOWS_ELEVATION_WAIT_FAILED")
        exit_code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
            raise OSError(ctypes.get_last_error(), "WINDOWS_ELEVATION_EXIT_READ_FAILED")
    finally:
        kernel32.CloseHandle(info.hProcess)

    remaining_map = _enumerate_process_map_windows()
    remaining = [pid for pid in pids if str(remaining_map.get(pid) or "").strip().lower() in SUPPORTED_CLIENT_NAMES]
    if remaining:
        raise RuntimeError("WINDOWS_ELEVATION_TARGET_STILL_RUNNING:" + ",".join(map(str, remaining)))
    return {
        "ok": True,
        "closed_pid_count": len(pids),
        "taskkill_exit_code": int(exit_code.value),
        "fixed_system_binary": True,
        "arbitrary_executable_allowed": False,
        "arbitrary_arguments_allowed": False,
    }


def elevated_close_supported_processes(pids: Iterable[int], *, operation_token: str) -> dict[str, Any]:
    _windows_required()
    _consume_operation_token(operation_token)
    targets = validate_elevation_targets(pids)
    if not targets:
        return {
            "ok": True,
            "closed_pid_count": 0,
            "already_closed": True,
            "operation_token_consumed": True,
            "uac_prompt_started": False,
            "arbitrary_executable_allowed": False,
            "production_effect_authorized": False,
            "windows_runtime_certified": False,
            "production_score_mutation_authorized": False,
        }
    result = _run_elevated_taskkill(targets)
    result.update({
        "operation_token_consumed": True,
        "uac_prompt_started": True,
        "production_effect_authorized": False,
        "windows_runtime_certified": False,
        "production_score_mutation_authorized": False,
    })
    return result


def synthetic_proof() -> dict[str, Any]:
    process_map = {101: "Codex.exe", 102: "ChatGPT.exe", 103: "notepad.exe", 104: "explorer.exe"}
    allowed = _validate_target_map([101, 102], process_map)
    unsupported_rejected = False
    try:
        _validate_target_map([103], process_map)
    except ValueError as exc:
        unsupported_rejected = "TARGET_NOT_ALLOWED" in str(exc)
    explorer_rejected = False
    try:
        _validate_target_map([104], process_map)
    except ValueError as exc:
        explorer_rejected = "TARGET_NOT_ALLOWED" in str(exc)

    token = "proof-token-1234567890"
    _consume_operation_token(token)
    replay_rejected = False
    try:
        _consume_operation_token(token)
    except RuntimeError as exc:
        replay_rejected = "ALREADY_CONSUMED" in str(exc)

    args = _taskkill_arguments([102, 101])
    src = Path(__file__).read_text("utf-8")
    impl_src = src[:src.find("def synthetic_proof")]
    checks = {
        "codex_chatgpt_only_allowlist": SUPPORTED_CLIENT_NAMES == frozenset({"codex.exe", "chatgpt.exe"}),
        "allowed_targets_validate": allowed == [101, 102],
        "generic_process_rejected": unsupported_rejected,
        "explorer_rejected": explorer_rejected,
        "pid_bound_is_bounded": MAX_TARGET_PIDS == 32,
        "taskkill_args_numeric_only": args == "/PID 101 /PID 102 /T /F",
        "taskkill_resolved_from_system_directory": "GetSystemDirectoryW" in impl_src and '"taskkill.exe"' in impl_src,
        "uac_uses_runas_only_on_fixed_taskkill": "ShellExecuteExW" in impl_src and 'info.lpVerb = "runas"' in impl_src and "info.lpFile = str(taskkill)" in impl_src,
        "no_generic_shell_runner": "powershell.exe" not in impl_src.lower() and "cmd.exe" not in impl_src.lower() and "subprocess" not in impl_src,
        "no_caller_executable_parameter": "executable_path" not in impl_src and "lpFile = str(taskkill)" in impl_src,
        "one_shot_token_consumed_before_uac": impl_src.find("_consume_operation_token(operation_token)") < impl_src.find("validate_elevation_targets(pids)"),
        "token_replay_rejected": replay_rejected,
        "uac_cancel_is_explicit": "WINDOWS_ELEVATION_CANCELLED" in impl_src and "UAC_CANCELLED_ERROR = 1223" in impl_src,
        "wait_is_bounded": "120_000" in impl_src and "WINDOWS_ELEVATION_TIMEOUT" in impl_src,
        "production_authority_absent": '"windows_runtime_certified": False' in impl_src and '"production_score_mutation_authorized": False' in impl_src,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT,
        "version": VERSION,
        "suite": "WINDOWS_ONE_SHOT_ELEVATION_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)},
        "tests": tests,
        "real_uac_prompt_executed": False,
        "real_client_process_closed": False,
        "windows_runtime_certified": False,
        "production_score_promotion_eligible": False,
    }


def main() -> int:
    out = synthetic_proof()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
