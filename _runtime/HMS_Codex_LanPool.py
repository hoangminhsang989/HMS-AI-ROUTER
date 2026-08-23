#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import secrets
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_VERSION = "25.47"
SCHEMA_VERSION = 1
MAX_FUTURE_SKEW_SEC = 120
MAX_HEARTBEAT_TTL_SEC = 300
MAX_LEASE_TTL_SEC = 300
FS_RETRY_ATTEMPTS = 3
SECRET_KEYS = ("token", "secret", "password", "cookie", "authorization", "api_key", "access_token", "refresh_token", "client_secret", "credential")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def epoch_now() -> int:
    return int(time.time())


def norm(v: Any) -> str:
    return str(v or "").strip()


def safe_name(v: Any) -> str:
    s = "".join(c if c.isalnum() or c in "-_." else "-" for c in norm(v))
    return (s.strip("-._") or "node")[:80]


def atomic_json(path: Path, obj: Any) -> None:
    """Atomic JSON publish with bounded retry for transient SMB/NAS reconnects."""
    last: OSError | None = None
    for attempt in range(FS_RETRY_ATTEMPTS):
        tmp = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
            return
        except OSError as exc:
            last = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            if attempt + 1 < FS_RETRY_ATTEMPTS:
                time.sleep(0.08 * (attempt + 1))
    if last is not None:
        raise last
    raise OSError("LAN_POOL_ATOMIC_JSON_FAILED")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def stable_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict[str, Any], key: bytes) -> str:
    return hmac.new(key, stable_json(payload), hashlib.sha256).hexdigest()


def signed(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    return {"payload": payload, "signature": sign_payload(payload, key), "algorithm": "HMAC-SHA256"}


def verify_signed(wrapper: Any, key: bytes) -> bool:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("payload"), dict):
        return False
    sig = norm(wrapper.get("signature"))
    return bool(sig) and hmac.compare_digest(sig, sign_payload(wrapper["payload"], key))


def derive_pairing_key(code: str) -> bytes:
    code = norm(code)
    if len(code) < 8:
        raise ValueError("LAN_PAIRING_CODE_TOO_SHORT")
    return hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), b"HMS-AI-Cockpit-LAN-Pool-v25.45", 180_000, dklen=32)


def key_from_hex(value: str) -> bytes:
    raw = bytes.fromhex(norm(value))
    if len(raw) != 32:
        raise ValueError("LAN_PAIRING_KEY_INVALID")
    return raw


def secret_scan(obj: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower().replace("-", "_")
            p = f"{prefix}.{k}"
            safe_meta = lk in {"secret_values_excluded", "credential_sharing", "raw_token_sharing"} and isinstance(v, bool)
            if any(t in lk for t in SECRET_KEYS) and not safe_meta:
                hits.append(p)
            else:
                hits.extend(secret_scan(v, p))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            hits.extend(secret_scan(v, f"{prefix}[{idx}]"))
    return hits


def normalize_origin(origin: str) -> str:
    s = norm(origin).replace("\\", "/").strip().rstrip("/")
    if not s:
        return ""
    if s.startswith("git@") and ":" in s:
        left, right = s.split(":", 1)
        host = left.split("@", 1)[1].lower()
        s = f"ssh://{host}/{right}"
    if "://" in s:
        scheme, rest = s.split("://", 1)
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        host, sep, tail = rest.partition("/")
        s = f"{scheme.lower()}://{host.lower()}/{tail}"
    if s.lower().endswith(".git"):
        s = s[:-4]
    return s.lower().rstrip("/")


def project_fingerprint(project_dir: str, git_origin: str = "", logical_id: str = "") -> dict[str, Any]:
    origin = normalize_origin(git_origin)
    if origin:
        basis = "git-origin:" + origin
        scope = "CROSS_PC"
    elif norm(logical_id):
        basis = "logical-id:" + norm(logical_id).lower()
        scope = "CROSS_PC"
    else:
        p = os.path.normcase(os.path.abspath(os.path.normpath(norm(project_dir)))).replace("\\", "/").lower()
        basis = "local-path:" + p
        scope = "LOCAL_PATH_FALLBACK"
    return {"fingerprint": hashlib.sha256(basis.encode("utf-8")).hexdigest(), "basis_kind": basis.split(":", 1)[0], "scope": scope}


def default_node(node_id: str = "", node_name: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "node_id": norm(node_id) or str(uuid.uuid4()),
        "node_name": norm(node_name) or platform.node() or socket.gethostname() or "HMS-NODE",
        "machine": platform.node() or socket.gethostname(),
        "created_utc": utcnow(),
    }


def ensure_node(local_state: Path, node_name: str = "") -> dict[str, Any]:
    node = read_json(local_state, {}) or {}
    if not node.get("node_id"):
        node = default_node(node_name=node_name)
        atomic_json(local_state, node)
    elif node_name and node.get("node_name") != node_name:
        node["node_name"] = node_name
        atomic_json(local_state, node)
    return node


def lock_path(shared: Path, name: str) -> Path:
    return shared / "locks" / f"{safe_name(name)}.lock"


class FileLock:
    def __init__(self, path: Path, stale_sec: int = 30, timeout_sec: float = 5.0):
        self.path, self.stale_sec, self.timeout_sec = path, stale_sec, timeout_sec
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        end = time.time() + self.timeout_sec
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"{os.getpid()}|{epoch_now()}".encode())
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale_sec:
                        self.path.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                if time.time() >= end:
                    raise TimeoutError("LAN_POOL_LOCK_TIMEOUT")
                time.sleep(.08)

    def __exit__(self, *_):
        try:
            if self.fd is not None:
                os.close(self.fd)
        finally:
            try:
                self.path.unlink(missing_ok=True)
            except Exception:
                pass


def node_file(shared: Path, node_id: str) -> Path:
    return shared / "nodes" / f"{safe_name(node_id)}.json"


def lease_file(shared: Path, fingerprint: str) -> Path:
    return shared / "leases" / f"{fingerprint}.json"


def heartbeat(shared: Path, key: bytes, node: dict[str, Any], snapshot: dict[str, Any], ttl_sec: int = 45) -> dict[str, Any]:
    shared.mkdir(parents=True, exist_ok=True)
    project_fps = list(snapshot.get("project_fingerprints") or [])
    if not project_fps:
        for pr in snapshot.get("projects") or []:
            if isinstance(pr, dict):
                project_fps.append(project_fingerprint(pr.get("project_dir", ""), pr.get("git_origin", ""), pr.get("logical_id", ""))["fingerprint"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "node_id": node["node_id"],
        "node_name": node.get("node_name") or "",
        "machine": node.get("machine") or "",
        "time_utc": utcnow(),
        "time_epoch": epoch_now(),
        "ttl_sec": min(MAX_HEARTBEAT_TTL_SEC, max(15, int(ttl_sec))),
        "health": norm(snapshot.get("health")) or "READY",
        "capacity": max(0, int(snapshot.get("capacity") or 0)),
        "running_instances": max(0, int(snapshot.get("running_instances") or 0)),
        "project_fingerprints": sorted(set(str(x) for x in project_fps if x)),
        "account_hashes": sorted(set(str(x) for x in (snapshot.get("account_hashes") or []) if x)),
        "features": ["PROJECT_LEASE", "SIGNED_HEARTBEAT", "FAILOVER_METADATA", "NO_RAW_CREDENTIAL_SHARING"],
        "secret_values_excluded": True,
    }
    if secret_scan(payload):
        raise ValueError("LAN_HEARTBEAT_SECRET_FIELD_REJECTED")
    wrapper = signed(payload, key)
    atomic_json(node_file(shared, node["node_id"]), wrapper)
    return payload


def read_nodes(shared: Path, key: bytes, now_epoch: int | None = None) -> list[dict[str, Any]]:
    now_epoch = epoch_now() if now_epoch is None else int(now_epoch)
    rows: list[dict[str, Any]] = []
    nd = shared / "nodes"
    if not nd.exists():
        return rows
    for p in sorted(nd.glob("*.json")):
        w = read_json(p, {}) or {}
        if not verify_signed(w, key):
            rows.append({"node_id": p.stem, "signature_ok": False, "payload_ok": False, "state": "INVALID_SIGNATURE", "fresh": False})
            continue
        try:
            x = dict(w["payload"])
            node_id = norm(x.get("node_id"))
            if not node_id or int(x.get("schema_version") or 0) != SCHEMA_VERSION:
                raise ValueError("NODE_SCHEMA_OR_ID_INVALID")
            stamp = int(x.get("time_epoch"))
            ttl = int(x.get("ttl_sec"))
            if ttl < 15 or ttl > MAX_HEARTBEAT_TTL_SEC:
                raise ValueError("NODE_TTL_OUT_OF_RANGE")
            future_skew = stamp - now_epoch
            if future_skew > MAX_FUTURE_SKEW_SEC:
                x.update({"signature_ok": True, "payload_ok": False, "age_sec": 0, "future_skew_sec": future_skew, "fresh": False, "state": "CLOCK_SKEW_FUTURE"})
            else:
                age = max(0, now_epoch - stamp)
                x.update({"signature_ok": True, "payload_ok": True, "age_sec": age, "future_skew_sec": max(0, future_skew), "fresh": age <= ttl, "state": "ONLINE" if age <= ttl else "STALE"})
            x["_registry_file"] = p.name
            rows.append(x)
        except Exception:
            rows.append({"node_id": p.stem, "signature_ok": True, "payload_ok": False, "state": "MALFORMED_PAYLOAD", "fresh": False, "_registry_file": p.name})

    # A node id must map to one registry object. Duplicates are not ranked for failover.
    counts: dict[str, int] = {}
    for x in rows:
        nid = norm(x.get("node_id"))
        if nid:
            counts[nid] = counts.get(nid, 0) + 1
    for x in rows:
        nid = norm(x.get("node_id"))
        if nid and counts.get(nid, 0) > 1:
            x.update({"payload_ok": False, "fresh": False, "state": "DUPLICATE_NODE_ID", "duplicate_count": counts[nid]})
        x.pop("_registry_file", None)
    return rows

def read_lease(shared: Path, key: bytes, fingerprint: str, stale_sec: int = 45, now_epoch: int | None = None) -> dict[str, Any] | None:
    p = lease_file(shared, fingerprint)
    if not p.exists():
        return None
    w = read_json(p, {}) or {}
    if not verify_signed(w, key):
        return {"fingerprint": fingerprint, "signature_ok": False, "payload_ok": False, "state": "INVALID_SIGNATURE", "active": True}
    try:
        x = dict(w["payload"])
        now_epoch = epoch_now() if now_epoch is None else int(now_epoch)
        acquired = int(x.get("acquired_epoch"))
        renewed = int(x.get("renewed_epoch"))
        expires = int(x.get("expires_epoch"))
        epoch = int(x.get("epoch"))
        nonce = norm(x.get("nonce"))
        if int(x.get("schema_version") or 0) != SCHEMA_VERSION or norm(x.get("fingerprint")) != fingerprint:
            raise ValueError("LEASE_SCHEMA_OR_FINGERPRINT_INVALID")
        if not norm(x.get("node_id")) or epoch < 1 or len(nonce) != 32:
            raise ValueError("LEASE_IDENTITY_INVALID")
        int(nonce, 16)
        if acquired > renewed or renewed > expires:
            raise ValueError("LEASE_TIME_ORDER_INVALID")
        ttl = expires - renewed
        if ttl < 15 or ttl > MAX_LEASE_TTL_SEC:
            raise ValueError("LEASE_TTL_OUT_OF_RANGE")
        future_skew = renewed - now_epoch
        if future_skew > MAX_FUTURE_SKEW_SEC:
            x.update({"signature_ok": True, "payload_ok": False, "active": True, "state": "CLOCK_SKEW_FUTURE", "future_skew_sec": future_skew})
            return x
        active = now_epoch <= expires
        x.update({"signature_ok": True, "payload_ok": True, "active": active, "state": "ACTIVE" if active else "EXPIRED", "future_skew_sec": max(0, future_skew), "age_sec": max(0, now_epoch - renewed)})
        return x
    except Exception:
        payload = dict(w.get("payload") or {})
        payload.update({"fingerprint": fingerprint, "signature_ok": True, "payload_ok": False, "state": "MALFORMED_PAYLOAD", "active": True})
        return payload

def acquire_lease(shared: Path, key: bytes, node: dict[str, Any], project: dict[str, Any], ttl_sec: int = 45) -> dict[str, Any]:
    fp_meta = project_fingerprint(project.get("project_dir", ""), project.get("git_origin", ""), project.get("logical_id", ""))
    fp = fp_meta["fingerprint"]
    with FileLock(lock_path(shared, "lease-" + fp[:24]), stale_sec=max(30, ttl_sec * 2)):
        old = read_lease(shared, key, fp, ttl_sec)
        if old and not old.get("signature_ok", True):
            return {"ok": False, "status": "BLOCKED_INVALID_SIGNATURE", "fingerprint": fp, "lease": old, "fingerprint_meta": fp_meta}
        if old and not old.get("payload_ok", True):
            return {"ok": False, "status": "BLOCKED_INVALID_PAYLOAD", "fingerprint": fp, "lease": old, "fingerprint_meta": fp_meta}
        if old and old.get("active") and old.get("node_id") != node["node_id"]:
            return {"ok": False, "status": "BLOCKED_OWNED_BY_OTHER_NODE", "fingerprint": fp, "lease": old, "fingerprint_meta": fp_meta}
        epoch = int((old or {}).get("epoch") or 0) + (1 if old and old.get("node_id") != node["node_id"] else 0)
        if epoch <= 0:
            epoch = 1
        now = epoch_now()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "fingerprint": fp,
            "fingerprint_scope": fp_meta["scope"],
            "basis_kind": fp_meta["basis_kind"],
            "node_id": node["node_id"],
            "node_name": node.get("node_name") or "",
            "epoch": epoch,
            "nonce": secrets.token_hex(16),
            "acquired_epoch": int((old or {}).get("acquired_epoch") or now) if old and old.get("node_id") == node["node_id"] else now,
            "renewed_epoch": now,
            "expires_epoch": now + min(MAX_LEASE_TTL_SEC, max(15, int(ttl_sec))),
            "project_label": norm(project.get("project_label"))[:120],
            "secret_values_excluded": True,
        }
        if secret_scan(payload):
            raise ValueError("LAN_LEASE_SECRET_FIELD_REJECTED")
        atomic_json(lease_file(shared, fp), signed(payload, key))
        return {"ok": True, "status": "RENEWED" if old and old.get("node_id") == node["node_id"] else ("TAKEOVER_EXPIRED" if old else "ACQUIRED"), "fingerprint": fp, "lease": payload, "fingerprint_meta": fp_meta}


def release_lease(shared: Path, key: bytes, node: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    fp = project_fingerprint(project.get("project_dir", ""), project.get("git_origin", ""), project.get("logical_id", ""))["fingerprint"]
    with FileLock(lock_path(shared, "lease-" + fp[:24])):
        old = read_lease(shared, key, fp)
        if not old:
            return {"ok": True, "status": "ALREADY_FREE", "fingerprint": fp}
        if not old.get("signature_ok", True):
            return {"ok": False, "status": "BLOCKED_INVALID_SIGNATURE", "fingerprint": fp}
        if not old.get("payload_ok", True):
            return {"ok": False, "status": "BLOCKED_INVALID_PAYLOAD", "fingerprint": fp}
        if old.get("node_id") != node["node_id"]:
            return {"ok": False, "status": "BLOCKED_NOT_OWNER", "fingerprint": fp, "owner_node_id": old.get("node_id")}
        lease_file(shared, fp).unlink(missing_ok=True)
        return {"ok": True, "status": "RELEASED", "fingerprint": fp, "epoch": old.get("epoch")}


def failover_candidates(nodes: list[dict[str, Any]], owner_node_id: str = "") -> list[dict[str, Any]]:
    good = [x for x in nodes if x.get("signature_ok") and x.get("payload_ok", True) and x.get("fresh") and x.get("node_id") != owner_node_id and x.get("health") in ("READY", "HEALTHY", "OK")]
    good.sort(key=lambda x: (-int(x.get("capacity") or 0), int(x.get("running_instances") or 0), str(x.get("node_name") or "")))
    return [{"node_id": x.get("node_id"), "node_name": x.get("node_name"), "capacity": x.get("capacity"), "running_instances": x.get("running_instances")} for x in good]


def status(shared: Path, key: bytes, node: dict[str, Any], projects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    nodes = read_nodes(shared, key)
    leases: list[dict[str, Any]] = []
    ld = shared / "leases"
    if ld.exists():
        for p in sorted(ld.glob("*.json")):
            fp = p.stem
            l = read_lease(shared, key, fp)
            if l:
                leases.append(l)
    selected: list[dict[str, Any]] = []
    for pr in projects or []:
        meta = project_fingerprint(pr.get("project_dir", ""), pr.get("git_origin", ""), pr.get("logical_id", ""))
        lease = next((x for x in leases if x.get("fingerprint") == meta["fingerprint"]), None)
        selected.append({"project_dir": pr.get("project_dir", ""), "project_label": pr.get("project_label", ""), **meta, "lease": lease})
    invalid_sig = sum(1 for x in nodes if not x.get("signature_ok")) + sum(1 for x in leases if not x.get("signature_ok", True))
    invalid_payload = sum(1 for x in nodes if x.get("signature_ok") and not x.get("payload_ok", True)) + sum(1 for x in leases if x.get("signature_ok", True) and not x.get("payload_ok", True))
    invalid = invalid_sig + invalid_payload
    online = sum(1 for x in nodes if x.get("fresh") and x.get("signature_ok") and x.get("payload_ok", True))
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_utc": utcnow(),
        "local_node": {"node_id": node.get("node_id"), "node_name": node.get("node_name"), "machine": node.get("machine")},
        "nodes": nodes,
        "leases": leases,
        "projects": selected,
        "failover_candidates": failover_candidates(nodes, node.get("node_id", "")),
        "summary": {"nodes": len(nodes), "online": online, "stale": sum(1 for x in nodes if x.get("state") == "STALE"), "leases": sum(1 for x in leases if x.get("active") and x.get("payload_ok", True)), "invalid_signatures": invalid_sig, "invalid_payloads": invalid_payload, "invalid_registry_entries": invalid},
        "security": {"signed_registry": True, "credential_sharing": False, "raw_token_sharing": False, "secret_values_excluded": True},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["status", "heartbeat", "acquire", "release", "pair-key"], default="status")
    ap.add_argument("--shared", required=False, default="")
    ap.add_argument("--local-state", required=False, default="")
    ap.add_argument("--key-hex", default="")
    ap.add_argument("--pairing-code", default="")
    ap.add_argument("--node-name", default="")
    ap.add_argument("--input", default="")
    ap.add_argument("--ttl", type=int, default=45)
    a = ap.parse_args()
    if a.mode == "pair-key":
        print(json.dumps({"ok": True, "key_hex": derive_pairing_key(a.pairing_code).hex()}, ensure_ascii=False))
        return 0
    shared = Path(a.shared)
    if not a.shared:
        raise SystemExit("LAN_SHARED_PATH_MISSING")
    local_state = Path(a.local_state) if a.local_state else Path.home() / ".hms-lan-pool-node-v2545.json"
    key = key_from_hex(a.key_hex or os.environ.get("HMS_LAN_POOL_KEY_HEX", ""))
    node = ensure_node(local_state, a.node_name)
    payload = read_json(Path(a.input), {}) if a.input else {}
    if a.mode == "heartbeat":
        data = heartbeat(shared, key, node, payload or {}, a.ttl)
        out = {"ok": True, "heartbeat": data, "lan_pool": status(shared, key, node, (payload or {}).get("projects") or [])}
    elif a.mode == "acquire":
        r = acquire_lease(shared, key, node, payload or {}, a.ttl)
        out = {"ok": bool(r.get("ok")), "lease_result": r, "lan_pool": status(shared, key, node, [payload or {}])}
    elif a.mode == "release":
        r = release_lease(shared, key, node, payload or {})
        out = {"ok": bool(r.get("ok")), "lease_result": r, "lan_pool": status(shared, key, node, [payload or {}])}
    else:
        out = {"ok": True, "lan_pool": status(shared, key, node, (payload or {}).get("projects") or [])}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
