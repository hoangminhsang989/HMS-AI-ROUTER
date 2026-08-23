#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def which_any(names: list[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def normalize_root(root: Path) -> Path:
    root = root.resolve()
    return root.parent if root.name.lower() == '_runtime' else root


def version_key(version: str) -> tuple[int, ...]:
    parts = []
    for bit in str(version).strip().lstrip('vV').split('.'):
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def manifests(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    runtime = root / '_runtime'
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not runtime.exists():
        return rows
    for path in runtime.glob('RELEASE_MANIFEST_V*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(data, dict) and data.get('version'):
                rows.append((path, data))
        except Exception:
            continue
    rows.sort(key=lambda x: version_key(str(x[1].get('version'))), reverse=True)
    return rows


def select_manifest(root: Path, requested_version: str | None = None) -> tuple[Path | None, dict[str, Any] | None]:
    all_rows = manifests(root)
    if requested_version:
        normalized = str(requested_version).lstrip('vV')
        for path, data in all_rows:
            if str(data.get('version')).lstrip('vV') == normalized:
                return path, data
    return all_rows[0] if all_rows else (None, None)


def verify_manifest(root: Path, version: str | None = None) -> dict[str, Any]:
    root = normalize_root(root)
    manifest_path, manifest = select_manifest(root, version)
    if manifest_path is None or manifest is None:
        return {'ok': False, 'error': 'missing release manifest', 'files': [], 'root': str(root)}
    rows = []
    ok = True
    for entry in manifest.get('files', []):
        rel = str(entry.get('path') or '').replace('\\', '/')
        file_path = root / Path(rel)
        exists = file_path.exists() and file_path.is_file()
        got = sha256(file_path) if exists else None
        same = exists and got == entry.get('sha256')
        rows.append({'path': rel, 'exists': exists, 'hash_ok': same})
        ok = ok and same
    return {
        'ok': ok,
        'version': str(manifest.get('version')),
        'manifest': str(manifest_path),
        'root': str(root),
        'files': rows,
        'file_count': len(rows),
        'runtime_tests': manifest.get('runtime_tests', 'UNKNOWN'),
    }


def detect(root: Path) -> dict[str, Any]:
    system = platform.system()
    powershell = which_any(['powershell.exe', 'powershell', 'pwsh.exe', 'pwsh'])
    return {
        'os': {'name': system, 'platform': platform.platform(), 'is_windows': system == 'Windows'},
        'python': {'ok': bool(sys.executable and Path(sys.executable).exists()), 'path': sys.executable, 'version': platform.python_version()},
        'powershell': {'ok': bool(powershell), 'path': powershell},
        'git': {'ok': bool(which_any(['git.exe', 'git'])), 'path': which_any(['git.exe', 'git'])},
        'codex_cli': {'ok': bool(which_any(['codex.exe', 'codex'])), 'path': which_any(['codex.exe', 'codex'])},
        'chrome': {'ok': any(p.exists() for p in [
            Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe',
        ])},
    }


def preflight(root: Path, version: str | None = None) -> dict[str, Any]:
    root = normalize_root(root)
    env = detect(root)
    manifest = verify_manifest(root, version)
    missing_required = []
    if not env['python']['ok']:
        missing_required.append('python')
    if env['os']['is_windows'] and not env['powershell']['ok']:
        missing_required.append('powershell')
    score = 100
    if missing_required:
        score -= 40 * len(missing_required)
    if not manifest.get('ok'):
        score -= 35
    score = max(0, score)
    return {
        'score': score,
        'grade': 'PASS' if score >= 90 else ('WARN' if score >= 70 else 'FAIL'),
        'environment': env,
        'manifest': manifest,
        'missing_required': missing_required,
        'note': 'Preflight này chỉ là static/local release check; không chứng nhận Codex/Antigravity runtime thật.',
    }


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_bootstrap(install_root: Path) -> Path:
    bootstrap = install_root / 'HMS_AI_ROUTER.vbs'
    content = r'''Option Explicit
Dim fso, sh, base, statePath, ps
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
statePath = fso.BuildPath(base, "state\current.json")
If Not fso.FileExists(statePath) Then
  MsgBox "HMS chưa có release ACTIVE. Hãy mở bản portable và chọn ĐĂNG KÝ BẢN NÀY.", 48, "HMS-AI-ROUTER"
  WScript.Quit 2
End If
ps = "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command ""$j=Get-Content -Raw -LiteralPath '" & Replace(statePath, "'", "''") & "'|ConvertFrom-Json;$v=Join-Path $j.release_dir 'HMS_AI_ROUTER.vbs';Start-Process -FilePath 'wscript.exe' -ArgumentList @('//nologo',$v)"""
sh.Run ps, 0, False
'''
    install_root.mkdir(parents=True, exist_ok=True)
    bootstrap.write_text(content, encoding='utf-8-sig')
    return bootstrap


def list_releases(install_root: Path) -> list[dict[str, Any]]:
    releases_dir = install_root / 'releases'
    result = []
    if releases_dir.exists():
        for d in sorted((x for x in releases_dir.iterdir() if x.is_dir()), key=lambda p: p.name.lower()):
            check = verify_manifest(d)
            result.append({'name': d.name, 'path': str(d), 'verified': bool(check.get('ok')), 'version': check.get('version')})
    return result


def status(root: Path, install_root: Path, version: str | None = None) -> dict[str, Any]:
    root = normalize_root(root)
    state_dir = install_root / 'state'
    current = read_json(state_dir / 'current.json')
    previous = read_json(state_dir / 'previous.json')
    check = verify_manifest(root, version)
    resolved = str(root).lower()
    active_dir = str((current or {}).get('release_dir') or '').lower()
    return {
        'this_release': check,
        'install_root': str(install_root),
        'current': current,
        'previous': previous,
        'releases': list_releases(install_root),
        'current_is_this': bool(active_dir and active_dir == resolved),
        'bootstrap': str(install_root / 'HMS_AI_ROUTER.vbs'),
        'bootstrap_exists': (install_root / 'HMS_AI_ROUTER.vbs').exists(),
        'update_mode': 'LOCAL_VERSIONED_ACTIVATION + SIGNED_STAGING',
        'online_feed': 'SUPPORTED_BY_HMS_UpdateChannel',
    }


def install(root: Path, install_root: Path, version: str | None = None) -> dict[str, Any]:
    root = normalize_root(root)
    pf = preflight(root, version)
    if pf['missing_required'] or not pf['manifest'].get('ok'):
        raise RuntimeError('preflight failed; activation aborted')
    release_version = str(pf['manifest'].get('version'))
    releases = install_root / 'releases'
    state = install_root / 'state'
    releases.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    target = releases / f'v{release_version}'
    if target.exists():
        check = verify_manifest(target, release_version)
        if not check.get('ok'):
            raise FileExistsError(f'existing target is not a verified v{release_version}: {target}')
    else:
        shutil.copytree(root, target)
        check = verify_manifest(target, release_version)
        if not check.get('ok'):
            quarantine = releases / f'v{release_version}.failed-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}'
            try:
                os.replace(target, quarantine)
            except Exception:
                quarantine = target
            raise RuntimeError(f'post-copy verification failed; activation aborted; unverified copy preserved at {quarantine}')
    current_path = state / 'current.json'
    current = read_json(current_path)
    if current and str(current.get('release_dir') or '').lower() != str(target).lower():
        atomic_json(state / 'previous.json', current)
    active = {
        'version': release_version,
        'release_dir': str(target),
        'activated_utc': now_utc(),
        'source_portable': str(root),
        'verified': True,
    }
    atomic_json(current_path, active)
    bootstrap = write_bootstrap(install_root)
    return {
        'installed': str(target),
        'active': active,
        'previous': read_json(state / 'previous.json'),
        'bootstrap': str(bootstrap),
        'note': 'Release cũ không bị xóa. Bootstrap ổn định sẽ mở release ACTIVE.',
    }


def rollback(install_root: Path) -> dict[str, Any]:
    state = install_root / 'state'
    current_path = state / 'current.json'
    previous_path = state / 'previous.json'
    current = read_json(current_path)
    previous = read_json(previous_path)
    if previous is None:
        raise RuntimeError('no previous release recorded')
    previous_dir = Path(str(previous.get('release_dir') or ''))
    if not previous_dir.exists():
        raise RuntimeError('previous release directory is missing')
    check = verify_manifest(previous_dir, str(previous.get('version') or '') or None)
    if not check.get('ok'):
        raise RuntimeError('previous release manifest verification failed')
    activated = dict(previous)
    activated['activated_utc'] = now_utc()
    activated['rollback'] = True
    atomic_json(current_path, activated)
    if current:
        atomic_json(previous_path, current)
    bootstrap = write_bootstrap(install_root)
    return {
        'active': activated,
        'previous': current,
        'bootstrap': str(bootstrap),
        'note': 'Rollback chỉ đổi ACTIVE pointer; không xóa release.',
    }


def certificate(root: Path, version: str | None = None) -> dict[str, Any]:
    pf = preflight(root, version)
    ver = str(pf['manifest'].get('version') or version or 'unknown')
    return {
        'generated_utc': now_utc(),
        'product': 'HMS-AI-ROUTER',
        'version': ver,
        'preflight_grade': pf['grade'],
        'preflight_score': pf['score'],
        'manifest_ok': bool(pf['manifest'].get('ok')),
        'required_ready': not pf['missing_required'],
        'runtime_tests': pf['manifest'].get('runtime_tests', 'UNKNOWN'),
        'verdict': 'RELEASE_READY_STATIC' if pf['manifest'].get('ok') and not pf['missing_required'] else 'RELEASE_BLOCKED',
        'note': 'Không phải chứng nhận runtime thật.',
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('preflight', 'install', 'rollback', 'certificate', 'status'), required=True)
    ap.add_argument('--root', required=True)
    ap.add_argument('--install-root')
    ap.add_argument('--version')
    ap.add_argument('--output')
    args = ap.parse_args()
    root = normalize_root(Path(args.root))
    try:
        if args.mode == 'preflight':
            data = preflight(root, args.version)
        elif args.mode == 'certificate':
            data = certificate(root, args.version)
        elif args.mode == 'status':
            if not args.install_root:
                raise ValueError('--install-root required')
            data = status(root, Path(args.install_root), args.version)
        elif args.mode == 'install':
            if not args.install_root:
                raise ValueError('--install-root required')
            data = install(root, Path(args.install_root), args.version)
        else:
            if not args.install_root:
                raise ValueError('--install-root required')
            data = rollback(Path(args.install_root))
        out = {'ok': True, 'mode': args.mode, 'data': data}
    except Exception as exc:
        out = {'ok': False, 'mode': args.mode, 'error': f'{type(exc).__name__}: {exc}'}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    print(text)
    return 0 if out.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
