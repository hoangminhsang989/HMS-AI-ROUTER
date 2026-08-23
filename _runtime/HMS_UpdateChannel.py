#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRODUCT = "HMS-AI-ROUTER"
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
RSA_SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def version_key(value: str) -> tuple[int, ...]:
    out = []
    for bit in str(value or "").strip().lstrip("vV").split("."):
        try:
            out.append(int(bit))
        except Exception:
            out.append(0)
    return tuple(out)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def canonical_message(feed: dict[str, Any]) -> bytes:
    fields = [
        str(feed.get("product") or ""),
        str(feed.get("channel") or ""),
        str(feed.get("version") or ""),
        str(feed.get("package_url") or ""),
        str(feed.get("sha256") or "").lower(),
        str(int(feed.get("size") or 0)),
    ]
    return "\n".join(fields).encode("utf-8")


def verify_rsa_pkcs1_sha256(message: bytes, signature_b64: str, key: dict[str, Any]) -> bool:
    if str(key.get("alg") or "") != "RSA-PKCS1-v1_5-SHA256":
        return False
    try:
        n = int(str(key["n_hex"]), 16)
        e = int(key.get("e") or 65537)
        sig = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False
    s = int.from_bytes(sig, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    digest = hashlib.sha256(message).digest()
    t = RSA_SHA256_DIGESTINFO_PREFIX + digest
    if len(t) + 11 > k:
        return False
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hashlib.compare_digest(em, expected) if hasattr(hashlib, "compare_digest") else em == expected


def validate_feed(feed: dict[str, Any], key: dict[str, Any], channel: str) -> dict[str, Any]:
    errors = []
    if feed.get("product") != PRODUCT:
        errors.append("PRODUCT_MISMATCH")
    if str(feed.get("channel") or "") != channel:
        errors.append("CHANNEL_MISMATCH")
    version = str(feed.get("version") or "").strip().lstrip("vV")
    if not version:
        errors.append("VERSION_MISSING")
    url = str(feed.get("package_url") or "").strip()
    if not url:
        errors.append("PACKAGE_URL_MISSING")
    digest = str(feed.get("sha256") or "").lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        errors.append("SHA256_INVALID")
    try:
        size = int(feed.get("size") or 0)
        if size <= 0 or size > MAX_DOWNLOAD_BYTES:
            errors.append("SIZE_INVALID")
    except Exception:
        errors.append("SIZE_INVALID")
    sig = str(feed.get("signature_b64") or "")
    signature_ok = bool(sig) and verify_rsa_pkcs1_sha256(canonical_message(feed), sig, key)
    if not signature_ok:
        errors.append("SIGNATURE_INVALID")
    if str(feed.get("kid") or "") and str(feed.get("kid")) != str(key.get("kid") or ""):
        errors.append("KEY_ID_MISMATCH")
    return {
        "ok": not errors,
        "errors": errors,
        "signature_ok": signature_ok,
        "version": version,
        "package_url": url,
        "sha256": digest,
        "size": int(feed.get("size") or 0) if str(feed.get("size") or "").isdigit() else 0,
        "kid": str(key.get("kid") or ""),
    }


def open_url(url: str, timeout: int, allow_local: bool = False):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        req = urllib.request.Request(url, headers={"User-Agent": "HMS-AI-Update/25.27"})
        return urllib.request.urlopen(req, timeout=timeout)
    if allow_local and parsed.scheme in ("file", ""):
        path = Path(urllib.request.url2pathname(parsed.path) if parsed.scheme == "file" else url)
        return path.open("rb")
    raise RuntimeError("UPDATE_URL_REQUIRES_HTTPS")


def fetch_json(url: str, timeout: int, allow_local: bool) -> dict[str, Any]:
    with open_url(url, timeout, allow_local) as fh:
        raw = fh.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("FEED_TOO_LARGE")
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise RuntimeError("FEED_NOT_OBJECT")
    return data


def download(url: str, path: Path, expected_size: int, timeout: int, allow_local: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part-" + uuid.uuid4().hex[:8])
    total = 0
    with open_url(url, timeout, allow_local) as src, tmp.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise RuntimeError("PACKAGE_TOO_LARGE")
            dst.write(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    if total != expected_size:
        raise RuntimeError(f"SIZE_MISMATCH:{total}!={expected_size}")
    os.replace(tmp, path)


def safe_extract(zip_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if not infos:
            raise RuntimeError("EMPTY_ZIP")
        total = 0
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts:
                raise RuntimeError("ZIP_PATH_TRAVERSAL")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise RuntimeError("ZIP_SYMLINK_BLOCKED")
            total += int(info.file_size)
            if total > MAX_DOWNLOAD_BYTES * 3:
                raise RuntimeError("ZIP_EXPANDED_TOO_LARGE")
        zf.extractall(dest)
    children = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return dest


def import_release_manager(runtime_dir: Path):
    sys.path.insert(0, str(runtime_dir))
    try:
        import HMS_Codex_ReleaseManager as rm
        return rm
    finally:
        try:
            sys.path.remove(str(runtime_dir))
        except ValueError:
            pass


def check(feed_url: str, key_path: Path, channel: str, current_version: str, timeout: int, allow_local: bool) -> dict[str, Any]:
    if not feed_url:
        return {"configured": False, "update_available": False, "message": "Chưa cấu hình Update Feed URL."}
    key = read_json(key_path, {}) or {}
    if not key.get("n_hex"):
        raise RuntimeError("PINNED_PUBLIC_KEY_MISSING")
    feed = fetch_json(feed_url, timeout, allow_local)
    validation = validate_feed(feed, key, channel)
    if not validation["ok"]:
        raise RuntimeError("FEED_VERIFY_FAIL:" + ",".join(validation["errors"]))
    available = version_key(validation["version"]) > version_key(current_version)
    return {
        "configured": True,
        "feed_url": feed_url,
        "channel": channel,
        "current_version": current_version,
        "latest_version": validation["version"],
        "update_available": available,
        "signature_ok": validation["signature_ok"],
        "kid": validation["kid"],
        "feed": feed,
        "message": (f"Có bản v{validation['version']}" if available else "Đang ở bản mới nhất theo feed."),
    }


def stage(feed_url: str, key_path: Path, channel: str, current_version: str, install_root: Path,
          runtime_dir: Path, timeout: int, allow_local: bool) -> dict[str, Any]:
    chk = check(feed_url, key_path, channel, current_version, timeout, allow_local)
    if not chk.get("configured"):
        raise RuntimeError("UPDATE_FEED_NOT_CONFIGURED")
    feed = chk["feed"]
    version = str(feed["version"]).lstrip("vV")
    staging = install_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    zip_path = staging / f"v{version}.zip"
    if not zip_path.exists() or sha256_file(zip_path) != str(feed["sha256"]).lower():
        download(str(feed["package_url"]), zip_path, int(feed["size"]), timeout, allow_local)
    got = sha256_file(zip_path)
    if got != str(feed["sha256"]).lower():
        raise RuntimeError("PACKAGE_SHA256_MISMATCH")
    # Never overwrite an existing staged tree. Verified existing stage can be reused.
    final_stage = staging / f"v{version}"
    rm = import_release_manager(runtime_dir)
    if final_stage.exists():
        existing = rm.verify_manifest(final_stage, version)
        if not existing.get("ok"):
            raise RuntimeError("EXISTING_STAGE_UNVERIFIED")
        package_root = final_stage
        manifest = existing
    else:
        temp_stage = staging / f"v{version}.stage-{uuid.uuid4().hex[:8]}"
        package_root = safe_extract(zip_path, temp_stage)
        manifest = rm.verify_manifest(package_root, version)
        if not manifest.get("ok"):
            raise RuntimeError("STAGED_MANIFEST_VERIFY_FAIL")
        if package_root != temp_stage:
            # Keep the top-level package directory structure as the final stage root.
            os.replace(package_root, final_stage)
        else:
            os.replace(temp_stage, final_stage)
        package_root = final_stage
        manifest = rm.verify_manifest(package_root, version)
        if not manifest.get('ok'):
            raise RuntimeError('FINAL_STAGE_MANIFEST_VERIFY_FAIL')
    state = {
        "staged_utc": now_utc(),
        "version": version,
        "stage_dir": str(package_root),
        "zip_path": str(zip_path),
        "sha256": got,
        "signature_ok": True,
        "kid": chk.get("kid"),
        "manifest_ok": bool(manifest.get("ok")),
        "activation": "NOT_YET_ACTIVATED",
    }
    atomic_json(install_root / "state" / "staged-update.json", state)
    return {"check": chk, "stage": state, "manifest": manifest}


def activate(install_root: Path, runtime_dir: Path) -> dict[str, Any]:
    staged = read_json(install_root / "state" / "staged-update.json", {}) or {}
    stage_dir = Path(str(staged.get("stage_dir") or ""))
    version = str(staged.get("version") or "")
    if not stage_dir.exists() or not version:
        raise RuntimeError("NO_STAGED_UPDATE")
    rm = import_release_manager(runtime_dir)
    verify = rm.verify_manifest(stage_dir, version)
    if not verify.get("ok"):
        raise RuntimeError("STAGED_MANIFEST_VERIFY_FAIL")
    result = rm.install(stage_dir, install_root, version)
    staged["activated_utc"] = now_utc()
    staged["activation"] = "ACTIVE_POINTER_UPDATED"
    atomic_json(install_root / "state" / "staged-update.json", staged)
    return {"activated": result, "staged": staged}


def status(install_root: Path) -> dict[str, Any]:
    return {
        "staged": read_json(install_root / "state" / "staged-update.json", {}) or {},
        "current": read_json(install_root / "state" / "current.json", {}) or {},
        "previous": read_json(install_root / "state" / "previous.json", {}) or {},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("status", "check", "stage", "activate"), required=True)
    ap.add_argument("--feed-url", default="")
    ap.add_argument("--public-key", required=True)
    ap.add_argument("--channel", default="stable")
    ap.add_argument("--current-version", required=True)
    ap.add_argument("--install-root", required=True)
    ap.add_argument("--runtime-dir", required=True)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--allow-local", action="store_true", help="Build/test only: allow file:// or local path feeds")
    args = ap.parse_args()
    try:
        root = Path(args.install_root)
        runtime = Path(args.runtime_dir)
        key = Path(args.public_key)
        if args.mode == "status":
            data = status(root)
        elif args.mode == "check":
            data = check(args.feed_url, key, args.channel, args.current_version, args.timeout, args.allow_local)
        elif args.mode == "stage":
            data = stage(args.feed_url, key, args.channel, args.current_version, root, runtime, args.timeout, args.allow_local)
        else:
            data = activate(root, runtime)
        out = {"ok": True, "mode": args.mode, "data": data}
    except Exception as exc:
        out = {"ok": False, "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
