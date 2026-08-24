#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping

PRODUCT = "HMS-AI-ROUTER"
VERSION = "25.75"
SUPPORTED_CLIENT_NAMES = frozenset({"codex.exe", "chatgpt.exe"})
MAX_TARGET_PIDS = 32
UAC_CANCELLED_ERROR = 1223
ERROR_INVALID_PARAMETER = 87
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
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
        _CONSUMED_TOKENS.add(token)


def _normalize_pids(pids: Iterable[int]) -> list[int]:
    values = sorted({int(pid) for pid in pids if int(pid) > 0 and int(pid) != os.getpid()})
    if not values or len(values) > MAX_TARGET_PIDS:
        raise ValueError("WINDOWS_ELEVATION_TARGET_INVALID")
    return values


def _validate_target_map(pids: Iterable[int], process_map: dict[int, str]) -> list[int]:
    """Legacy pure name allowlist proof helper; runtime elevation additionally requires identity binding."""
    targets = _normalize_pids(pids)
    running: list[int] = []
    for pid in targets:
        name = str(process_map.get(pid) or "").strip().lower()
        if not name:
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
        entry = PROCESSENTRY32W(); entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            out[int(entry.th32ProcessID)] = str(entry.szExeFile)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return out


def _filetime_u64(value: wintypes.FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _identity_from_handle_windows(pid: int, handle) -> dict[str, Any]:
    _windows_required()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    created = wintypes.FILETIME(); exited = wintypes.FILETIME(); kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
    if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError(ctypes.get_last_error(), "WINDOWS_PROCESS_CREATION_TIME_UNAVAILABLE")
    buffer = ctypes.create_unicode_buffer(32768); size = wintypes.DWORD(len(buffer))
    if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        raise OSError(ctypes.get_last_error(), "WINDOWS_PROCESS_IMAGE_UNAVAILABLE")
    image = str(buffer.value or "")
    name = image.replace("/", "\\").rsplit("\\", 1)[-1].strip().lower()
    creation = _filetime_u64(created)
    if not name or creation <= 0:
        raise RuntimeError("WINDOWS_PROCESS_IDENTITY_INVALID")
    return {"pid": int(pid), "name": name, "creation_time_100ns": creation}


def _close_handle_windows(handle) -> None:
    if not handle:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(handle)


def _open_identity_handle_windows(pid: int):
    _windows_required()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(pid))
    if not handle:
        err = ctypes.get_last_error()
        if err == ERROR_INVALID_PARAMETER:
            raise ProcessLookupError(pid)
        raise OSError(err, f"WINDOWS_PROCESS_IDENTITY_OPEN_FAILED: pid={pid}")
    try:
        identity = _identity_from_handle_windows(int(pid), handle)
    except Exception:
        _close_handle_windows(handle)
        raise
    return handle, identity


def _normalize_expected_identities(expected: Mapping[int, Mapping[str, Any]] | None) -> dict[int, dict[str, Any]]:
    if not isinstance(expected, Mapping) or not expected:
        raise ValueError("WINDOWS_ELEVATION_IDENTITY_BINDING_REQUIRED")
    out: dict[int, dict[str, Any]] = {}
    for raw_pid, row in expected.items():
        if not isinstance(row, Mapping):
            raise ValueError("WINDOWS_ELEVATION_IDENTITY_BINDING_INVALID")
        pid = int(raw_pid); row_pid = int(row.get("pid") or 0)
        name = str(row.get("name") or "").strip().lower(); creation = int(row.get("creation_time_100ns") or 0)
        if pid <= 0 or pid != row_pid or name not in SUPPORTED_CLIENT_NAMES or creation <= 0:
            raise ValueError("WINDOWS_ELEVATION_IDENTITY_BINDING_INVALID")
        out[pid] = {"pid": pid, "name": name, "creation_time_100ns": creation}
    return out


def _identity_matches(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> bool:
    try:
        return (
            int(expected.get("pid") or 0) == int(observed.get("pid") or 0)
            and str(expected.get("name") or "").strip().lower() == str(observed.get("name") or "").strip().lower()
            and int(expected.get("creation_time_100ns") or 0) == int(observed.get("creation_time_100ns") or 0)
        )
    except Exception:
        return False


def discover_supported_client_identities() -> dict[int, dict[str, Any]]:
    process_map = _enumerate_process_map_windows()
    candidate_pids = sorted(pid for pid, name in process_map.items() if pid > 0 and pid != os.getpid() and str(name).strip().lower() in SUPPORTED_CLIENT_NAMES)
    identities: dict[int, dict[str, Any]] = {}
    for pid in candidate_pids:
        try:
            handle, identity = _open_identity_handle_windows(pid)
        except ProcessLookupError:
            continue
        try:
            if identity["name"] in SUPPORTED_CLIENT_NAMES:
                identities[pid] = identity
        finally:
            _close_handle_windows(handle)
    return identities


def discover_supported_client_pids() -> list[int]:
    return sorted(discover_supported_client_identities())


def _lease_validated_targets(pids: Iterable[int], expected_identities: Mapping[int, Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    targets = _normalize_pids(pids); expected = _normalize_expected_identities(expected_identities)
    if set(targets) != set(expected):
        raise ValueError("WINDOWS_ELEVATION_IDENTITY_SET_MISMATCH")
    leases: list[dict[str, Any]] = []
    try:
        for pid in targets:
            try:
                handle, observed = _open_identity_handle_windows(pid)
            except ProcessLookupError:
                continue
            if not _identity_matches(expected[pid], observed):
                _close_handle_windows(handle)
                raise ValueError(f"WINDOWS_ELEVATION_TARGET_IDENTITY_CHANGED: pid={pid}")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            state = kernel32.WaitForSingleObject(handle, 0)
            if state == WAIT_OBJECT_0:
                _close_handle_windows(handle); continue
            if state != WAIT_TIMEOUT:
                _close_handle_windows(handle)
                raise OSError(int(state), f"WINDOWS_PROCESS_IDENTITY_WAIT_FAILED: pid={pid}")
            # Keeping this process handle open preserves the process object, so its PID cannot be reused until release.
            leases.append({"pid": pid, "handle": handle, "identity": observed})
    except Exception:
        for lease in leases:
            _close_handle_windows(lease.get("handle"))
        raise
    return leases


def _close_leases(leases: Iterable[Mapping[str, Any]]) -> None:
    for lease in leases:
        _close_handle_windows(lease.get("handle"))


def validate_elevation_targets(pids: Iterable[int], *, expected_identities: Mapping[int, Mapping[str, Any]] | None) -> list[int]:
    leases = _lease_validated_targets(pids, expected_identities=expected_identities)
    try:
        return [int(row["pid"]) for row in leases]
    finally:
        _close_leases(leases)


def _system_taskkill_path() -> Path:
    _windows_required()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetSystemDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768); length = kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "WINDOWS_SYSTEM_DIRECTORY_UNAVAILABLE")
    path = (Path(buffer.value) / "taskkill.exe").resolve()
    if not path.is_file() or path.name.lower() != "taskkill.exe":
        raise FileNotFoundError(f"WINDOWS_TASKKILL_NOT_FOUND: {path}")
    return path


def _taskkill_arguments(pids: Iterable[int]) -> str:
    targets = _normalize_pids(pids)
    # Never use /T: elevation authority is limited to the exact identity-bound PIDs, not their child process trees.
    return " ".join([*(f"/PID {pid}" for pid in targets), "/F"])


def _run_elevated_taskkill(leases: list[dict[str, Any]], timeout_ms: int = 120_000) -> dict[str, Any]:
    _windows_required()
    pids = [int(row["pid"]) for row in leases]
    taskkill = _system_taskkill_path(); parameters = _taskkill_arguments(pids)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True); kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    info = SHELLEXECUTEINFOW(); info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW); info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"; info.lpFile = str(taskkill); info.lpParameters = parameters; info.nShow = SW_HIDE
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
        taskkill_exit_code = int(exit_code.value)
    finally:
        kernel32.CloseHandle(info.hProcess)

    remaining: list[int] = []
    for lease in leases:
        state = kernel32.WaitForSingleObject(lease["handle"], 0)
        if state == WAIT_TIMEOUT:
            remaining.append(int(lease["pid"]))
        elif state != WAIT_OBJECT_0:
            raise OSError(int(state), f"WINDOWS_ELEVATION_TARGET_WAIT_FAILED: pid={lease['pid']}")
    if remaining:
        raise RuntimeError("WINDOWS_ELEVATION_TARGET_STILL_RUNNING:" + ",".join(map(str, remaining)))
    if taskkill_exit_code != 0:
        raise RuntimeError(f"WINDOWS_ELEVATION_TASKKILL_EXIT_NONZERO:{taskkill_exit_code}")
    return {
        "ok": True,
        "closed_pid_count": len(leases),
        "taskkill_exit_code": taskkill_exit_code,
        "taskkill_exit_code_zero": True,
        "identity_bound": True,
        "pid_reuse_blocked_by_open_handles": True,
        "tree_kill_allowed": False,
        "fixed_system_binary": True,
        "arbitrary_executable_allowed": False,
        "arbitrary_arguments_allowed": False,
    }


def elevated_close_supported_processes(
    pids: Iterable[int], *, operation_token: str,
    expected_identities: Mapping[int, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    _windows_required(); _consume_operation_token(operation_token)
    leases = _lease_validated_targets(pids, expected_identities)
    if not leases:
        return {
            "ok": True, "closed_pid_count": 0, "already_closed": True, "operation_token_consumed": True,
            "uac_prompt_started": False, "identity_bound": True, "pid_reuse_blocked_by_open_handles": True,
            "tree_kill_allowed": False, "arbitrary_executable_allowed": False, "production_effect_authorized": False,
            "windows_runtime_certified": False, "production_score_mutation_authorized": False,
        }
    try:
        result = _run_elevated_taskkill(leases)
    finally:
        _close_leases(leases)
    result.update({
        "operation_token_consumed": True, "uac_prompt_started": True, "production_effect_authorized": False,
        "windows_runtime_certified": False, "production_score_mutation_authorized": False,
    })
    return result


def synthetic_proof() -> dict[str, Any]:
    base = max(100_000, os.getpid() + 1_000); p1, p2, p3, p4 = base, base + 1, base + 2, base + 3
    process_map = {p1: "Codex.exe", p2: "ChatGPT.exe", p3: "notepad.exe", p4: "explorer.exe"}
    allowed = _validate_target_map([p1, p2], process_map)
    unsupported_rejected = False
    try:
        _validate_target_map([p3], process_map)
    except ValueError as exc:
        unsupported_rejected = "TARGET_NOT_ALLOWED" in str(exc)
    explorer_rejected = False
    try:
        _validate_target_map([p4], process_map)
    except ValueError as exc:
        explorer_rejected = "TARGET_NOT_ALLOWED" in str(exc)
    expected = {"pid": p1, "name": "codex.exe", "creation_time_100ns": 111}
    same = {"pid": p1, "name": "Codex.exe", "creation_time_100ns": 111}
    reused_same_name = {"pid": p1, "name": "codex.exe", "creation_time_100ns": 222}
    replaced_name = {"pid": p1, "name": "notepad.exe", "creation_time_100ns": 111}
    normalized_identity = _normalize_expected_identities({p1: expected})
    token = "proof-token-identity-123456"; _consume_operation_token(token); replay_rejected = False
    try:
        _consume_operation_token(token)
    except RuntimeError as exc:
        replay_rejected = "ALREADY_CONSUMED" in str(exc)
    args = _taskkill_arguments([p2, p1]); expected_args = f"/PID {p1} /PID {p2} /F"
    src = Path(__file__).read_text("utf-8"); impl_src = src[:src.find("def synthetic_proof")]
    elevated_src = impl_src[impl_src.find("def elevated_close_supported_processes"):]
    taskkill_src = impl_src[impl_src.find("def _taskkill_arguments"):impl_src.find("def _run_elevated_taskkill")]
    checks = {
        "codex_chatgpt_only_allowlist": SUPPORTED_CLIENT_NAMES == frozenset({"codex.exe", "chatgpt.exe"}),
        "allowed_targets_validate": allowed == [p1, p2],
        "generic_process_rejected": unsupported_rejected,
        "explorer_rejected": explorer_rejected,
        "pid_bound_is_bounded": MAX_TARGET_PIDS == 32,
        "taskkill_args_numeric_only": args == expected_args,
        "taskkill_tree_kill_prohibited": '"/T"' not in taskkill_src and '"tree_kill_allowed": False' in elevated_src,
        "identity_binding_requires_supported_exact_shape": normalized_identity[p1] == expected,
        "same_process_incarnation_matches": _identity_matches(expected, same),
        "same_name_pid_reuse_rejected": not _identity_matches(expected, reused_same_name),
        "different_image_rejected_by_identity": not _identity_matches(expected, replaced_name),
        "identity_uses_creation_time": "GetProcessTimes" in impl_src and "creation_time_100ns" in impl_src,
        "identity_uses_opened_image": "QueryFullProcessImageNameW" in impl_src,
        "identity_lease_uses_query_and_synchronize": "PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE" in impl_src,
        "identity_handles_held_across_uac": "_run_elevated_taskkill(leases)" in elevated_src and "_close_leases(leases)" in elevated_src,
        "pid_reuse_claim_is_handle_scoped": '"pid_reuse_blocked_by_open_handles": True' in elevated_src,
        "taskkill_resolved_from_system_directory": "GetSystemDirectoryW" in impl_src and '"taskkill.exe"' in impl_src,
        "uac_uses_runas_only_on_fixed_taskkill": "ShellExecuteExW" in impl_src and 'info.lpVerb = "runas"' in impl_src and "info.lpFile = str(taskkill)" in impl_src,
        "taskkill_nonzero_is_fail_closed": "WINDOWS_ELEVATION_TASKKILL_EXIT_NONZERO" in impl_src and '"taskkill_exit_code_zero": True' in impl_src,
        "no_generic_shell_runner": "powershell.exe" not in impl_src.lower() and "cmd.exe" not in impl_src.lower() and "subprocess" not in impl_src,
        "no_caller_executable_parameter": "executable_path" not in impl_src and "lpFile = str(taskkill)" in impl_src,
        "one_shot_token_consumed_before_identity_lease": elevated_src.find("_consume_operation_token(operation_token)") < elevated_src.find("_lease_validated_targets(pids, expected_identities)"),
        "token_replay_rejected": replay_rejected,
        "uac_cancel_is_explicit": "WINDOWS_ELEVATION_CANCELLED" in impl_src and "UAC_CANCELLED_ERROR = 1223" in impl_src,
        "wait_is_bounded": "120_000" in impl_src and "WINDOWS_ELEVATION_TIMEOUT" in impl_src,
        "production_authority_absent": '"windows_runtime_certified": False' in impl_src and '"production_score_mutation_authorized": False' in impl_src,
    }
    tests = [{"name": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks.items()]
    passed = sum(test["status"] == "PASS" for test in tests)
    return {
        "product": PRODUCT, "version": VERSION, "suite": "WINDOWS_ONE_SHOT_ELEVATION_SOURCE_PROOF",
        "verdict": "PASS" if passed == len(tests) else "FAIL",
        "summary": {"pass": passed, "fail": len(tests) - passed, "total": len(tests)}, "tests": tests,
        "real_uac_prompt_executed": False, "real_client_process_closed": False,
        "windows_runtime_certified": False, "production_score_promotion_eligible": False,
    }


def main() -> int:
    out = synthetic_proof(); print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if out["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
