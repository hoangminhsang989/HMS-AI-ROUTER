#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from HMS_Codex_OfficialAuthCompatibility import normalize_target_auth

VERSION = "25.72"
CONFIRMATION = "EXPORT OFFICIAL CODEX AUTH.JSON"
ROUTER_ONLY_FIELDS = {
    "priority", "weight", "websockets", "quota", "quota_remaining", "reset_time",
    "disabled", "favorite", "tag", "note", "router_metadata", "hms_metadata",
}


def read_object(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError("AUTH_OBJECT_REQUIRED")
    return obj


def official_projection(auth: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_target_auth(auth)
    return {k: v for k, v in normalized.items() if str(k).lower() not in ROUTER_ONLY_FIELDS}


def assert_destination(destination: Path, export_root: Path) -> None:
    root = export_root.expanduser().resolve(strict=False)
    dest = destination.expanduser().resolve(strict=False)
    if root == dest or root not in dest.parents:
        raise ValueError("EXPORT_DESTINATION_OUTSIDE_APPROVED_ROOT")
    if destination.name.lower() != "auth.json":
        raise ValueError("EXPORT_FILENAME_MUST_BE_AUTH_JSON")
    # Never follow a pre-existing symlink/reparse-like filesystem object.
    if destination.exists() and destination.is_symlink():
        raise ValueError("EXPORT_DESTINATION_SYMLINK_BLOCKED")


def atomic_sensitive_write(destination: Path, data: dict[str, Any], overwrite: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError("EXPORT_DESTINATION_EXISTS")
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".auth-export-", suffix=".tmp", dir=str(destination.parent))
    tmp = Path(tmp_name)
    try:
        try:
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        with os.fdopen(fd, "wb", closefd=True) as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, destination)
        try:
            os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def export_auth(*, source: Path, destination: Path, export_root: Path, enabled: bool,
                confirmation: str, overwrite: bool = False) -> dict[str, Any]:
    if not enabled:
        raise PermissionError("OFFICIAL_AUTH_EXPORT_DISABLED_BY_DEFAULT")
    if confirmation != CONFIRMATION:
        raise PermissionError("OFFICIAL_AUTH_EXPORT_CONFIRMATION_REQUIRED")
    assert_destination(destination, export_root)
    src = read_object(source)
    projected = official_projection(src)
    atomic_sensitive_write(destination, projected, overwrite)
    return {
        "ok": True,
        "version": VERSION,
        "destination": str(destination),
        "contains_sensitive_credentials": True,
        "diagnostics_export_allowed": False,
        "automatic_export": False,
        "router_only_fields_stripped": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Manual, security-gated official Codex auth.json export")
    ap.add_argument("--source", required=True)
    ap.add_argument("--destination", required=True)
    ap.add_argument("--export-root", required=True)
    ap.add_argument("--enable-sensitive-export", action="store_true")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    try:
        result = export_auth(
            source=Path(args.source), destination=Path(args.destination), export_root=Path(args.export_root),
            enabled=args.enable_sensitive_export, confirmation=args.confirm, overwrite=args.overwrite,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "version": VERSION, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
