#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, json, os, re, tempfile, threading, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

VERSION = "25.74"
# Cockpit Tools v1.3.27 compatibility baseline (2026-08-23). v1.3.27 restores the stable official-client close/launch path on Windows; HMS already uses ownership-checked stable client lifecycle and never calls WindowsApps internal daemon-stop directly.
# Cockpit v1.3.24 uses the Codex VS Code OAuth originator. Official Codex CLI itself
# uses a different first-party originator. Keep both profiles explicit so HMS never
# confuses a surface identity with a fixed product-wide constant.
COCKPIT_V1327_ORIGINATOR = "codex_vscode"
# Backward-compatible alias for older validators.
COCKPIT_V1324_ORIGINATOR = COCKPIT_V1327_ORIGINATOR
OFFICIAL_CODEX_CLI_ORIGINATOR = "codex_cli_rs"
OFFICIAL_ORIGINATOR = COCKPIT_V1327_ORIGINATOR
# Compatibility fallback only. Runtime callers should derive/override this from the
# installed Codex client version rather than treating 0.146.0 as permanent.
OFFICIAL_AUTH_USER_AGENT_BASELINE = "codex_vscode/0.146.0"
KEYRING_SERVICE = "Codex Auth"
SUPPORTED_STORE_MODES = {"file", "keyring", "auto"}
# Credential/account-identity fields are replaced, never inherited from the old account.
STALE_AUTH_KEYS = {
    "access_token", "refresh_token", "id_token", "session_id", "expired", "last_refresh",
    "expires_in", "timestamp", "token_type", "user_code", "verification_uri",
    "verification_uri_complete", "openai_api_key", "personal_access_token", "tokens",
    "agent_identity", "agentidentity", "auth_mode", "authmode", "base_url", "api_base_url",
    "apibaseurl", "email", "account_email", "accountemail", "account_name", "accountname",
    "account_id", "accountid", "chatgpt_account_id", "chatgptaccountid", "chatgpt_user_id",
    "chatgptuserid", "user_id", "userid", "type",
}
SECRET_KEYS = {
    "access_token", "refresh_token", "id_token", "openai_api_key", "api_key", "token",
    "credential", "personal_access_token", "authorization", "request_body", "response_body", "prompt",
}

class AuthCompatibilityError(RuntimeError):
    pass

class KeyringAdapter(Protocol):
    def load(self, service: str, key: str) -> str | None: ...
    def save(self, service: str, key: str, value: str) -> None: ...
    def delete(self, service: str, key: str) -> bool: ...

@dataclass
class MemoryKeyring:
    values: dict[tuple[str, str], str]
    def load(self, service: str, key: str) -> str | None:
        return self.values.get((service, key))
    def save(self, service: str, key: str, value: str) -> None:
        self.values[(service, key)] = value
    def delete(self, service: str, key: str) -> bool:
        return self.values.pop((service, key), None) is not None

def safe_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogatepass")
    return hashlib.sha256(data).hexdigest()

def resolve_codex_home(value: str | os.PathLike[str] | None = None) -> Path:
    raw = str(value or os.environ.get("CODEX_HOME") or "").strip().strip('"').strip("'")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"

def store_key(codex_home: Path) -> str:
    # Same account shape used by Codex keychain integrations: cli|sha256(canonical CODEX_HOME)[:16].
    try:
        canonical = codex_home.resolve(strict=False)
    except Exception:
        canonical = codex_home
    return "cli|" + safe_hash(str(canonical))[:16]

def parse_store_mode(config_text: str) -> str:
    m = re.search(r'(?m)^\s*cli_auth_credentials_store\s*=\s*["\'](file|keyring|auto|ephemeral)["\']\s*(?:#.*)?$', config_text or "", re.I)
    return m.group(1).lower() if m else "file"

def read_store_mode(codex_home: Path) -> str:
    try:
        return parse_store_mode((codex_home / "config.toml").read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return "file"

def parse_secret_auth_storage(config_text: str) -> bool:
    """Mirror Codex's SecretAuthStorage feature for auth keyring backend selection.

    Current Codex selects the encrypted Secrets backend when
    [features].secret_auth_storage is enabled; otherwise direct keyring storage is used.
    """
    text = config_text or ""
    # Good-enough TOML fixture parser: only honor an explicit boolean assignment.
    m = re.search(r'(?im)^\s*secret_auth_storage\s*=\s*(true|false)\s*(?:#.*)?$', text)
    return bool(m and m.group(1).lower() == "true")

def keyring_backend_kind(config_text: str) -> str:
    return "secrets" if parse_secret_auth_storage(config_text) else "direct"

def read_keyring_backend_kind(codex_home: Path) -> str:
    try:
        return keyring_backend_kind((codex_home / "config.toml").read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return "direct"

def _ensure_direct_keyring_backend(codex_home: Path, backend: str | None = None) -> str:
    selected = (backend or read_keyring_backend_kind(codex_home)).lower()
    if selected == "secrets":
        # The encrypted Secrets backend is owned by Codex's SecretsManager. Writing raw
        # generic credentials would create a shadow/stale credential and is unsafe.
        raise AuthCompatibilityError("KEYRING_SECRETS_BACKEND_REQUIRES_OFFICIAL_CODEX_HELPER")
    if selected != "direct":
        raise AuthCompatibilityError("UNKNOWN_KEYRING_BACKEND")
    return selected

def _load_json_text(raw: str) -> dict[str, Any]:
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise AuthCompatibilityError("AUTH_NOT_OBJECT")
    return obj

def load_auth(codex_home: Path, mode: str | None = None, keyring: KeyringAdapter | None = None, keyring_backend: str | None = None) -> tuple[dict[str, Any] | None, str]:
    mode = (mode or read_store_mode(codex_home)).lower()
    path = codex_home / "auth.json"
    key = store_key(codex_home)
    def from_file():
        return _load_json_text(path.read_text(encoding="utf-8-sig")) if path.exists() else None
    def from_keyring():
        _ensure_direct_keyring_backend(codex_home, keyring_backend)
        if keyring is None:
            raise AuthCompatibilityError("KEYRING_ADAPTER_REQUIRED")
        raw = keyring.load(KEYRING_SERVICE, key)
        return _load_json_text(raw) if raw else None
    if mode == "file":
        return from_file(), "file"
    if mode == "keyring":
        return from_keyring(), "keyring"
    if mode == "auto":
        try:
            obj = from_keyring()
            if obj is not None:
                return obj, "keyring"
        except Exception:
            pass
        return from_file(), "file"
    if mode == "ephemeral":
        raise AuthCompatibilityError("EPHEMERAL_NOT_SWITCHABLE")
    raise AuthCompatibilityError("UNSUPPORTED_STORE_MODE")

def auth_kind(auth: dict[str, Any]) -> str:
    mode = str(auth.get("auth_mode") or "").strip().lower()
    if mode in {"apikey", "api_key"} or auth.get("OPENAI_API_KEY"):
        return "apikey"
    if isinstance(auth.get("tokens"), dict):
        return "chatgpt"
    return mode or "unknown"

def normalize_target_auth(target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise AuthCompatibilityError("AUTH_OBJECT_REQUIRED")
    nxt = copy.deepcopy(target)
    kind = auth_kind(nxt)
    if kind == "chatgpt":
        tokens = nxt.get("tokens")
        if not isinstance(tokens, dict) or not str(tokens.get("access_token") or "").strip():
            raise AuthCompatibilityError("OAUTH_ACCESS_TOKEN_REQUIRED")
        # Codex/Cockpit compatibility: an OAuth record may legitimately carry an empty
        # refresh_token, but the key itself must survive rewriting so official clients do
        # not interpret the schema as a different/legacy auth shape.
        tokens.setdefault("refresh_token", "")
        nxt["auth_mode"] = "chatgpt"
        nxt["type"] = "codex"
        # Official-style OAuth file explicitly clears stale API-key credentials.
        nxt["OPENAI_API_KEY"] = None
        # Top-level token aliases are stale; account-specific agent_identity, when the
        # target snapshot owns one, is intentionally preserved from the TARGET only.
        for k in ["access_token", "refresh_token", "id_token", "personal_access_token"]:
            nxt.pop(k, None)
    elif kind == "apikey":
        key = str(nxt.get("OPENAI_API_KEY") or "").strip()
        if not key:
            raise AuthCompatibilityError("API_KEY_REQUIRED")
        nxt["auth_mode"] = "apikey"
        nxt.pop("tokens", None)
        for k in ["access_token", "refresh_token", "id_token", "personal_access_token", "agent_identity", "last_refresh"]:
            nxt.pop(k, None)
    else:
        raise AuthCompatibilityError("UNKNOWN_AUTH_KIND")
    return nxt

def rewrite_preserving_fields(current: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(current, dict) or not isinstance(target, dict):
        raise AuthCompatibilityError("AUTH_OBJECT_REQUIRED")
    # Preserve unrelated/custom fields from the live auth object, but never old credentials/account identity.
    merged = {k: copy.deepcopy(v) for k, v in current.items() if k.lower() not in STALE_AUTH_KEYS}
    nxt = normalize_target_auth(target)
    for k, v in nxt.items():
        merged[k] = copy.deepcopy(v)
    return merged

# Compatibility alias retained for fixtures and older internal callers.
merge_auth = rewrite_preserving_fields

def credential_projection(auth: dict[str, Any]) -> dict[str, Any]:
    kind = auth_kind(auth)
    if kind == "chatgpt":
        t = auth.get("tokens") or {}
        return {"kind": kind, "account_id": str(t.get("account_id") or ""), "access": bool(t.get("access_token")), "refresh": bool(t.get("refresh_token")), "id": bool(t.get("id_token"))}
    return {"kind": kind, "api_key": bool(auth.get("OPENAI_API_KEY"))}

def auth_metadata(auth: dict[str, Any] | None, source: str = "") -> dict[str, Any]:
    if auth is None:
        return {"present": False, "source": source, "sha256": ""}
    raw = json.dumps(auth, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "present": True, "source": source, "sha256": safe_hash(raw), "auth_mode": str(auth.get("auth_mode") or ""),
        "field_names": sorted(auth.keys()), "credential_projection": credential_projection(auth),
    }

def auth_fingerprint(auth: dict[str, Any]) -> str:
    return auth_metadata(auth).get("sha256", "")

def snapshot_current(codex_home: Path, mode: str | None = None, keyring: KeyringAdapter | None = None, keyring_backend: str | None = None) -> dict[str, Any]:
    auth, source = load_auth(codex_home, mode, keyring, keyring_backend)
    if auth is None:
        raise AuthCompatibilityError("NO_CURRENT_AUTH")
    # Raw auth is internal rollback material only; audit_payload never emits it.
    return {"schema": "HMS_CODEX_AUTH_SNAPSHOT_V2", "created_ns": time.time_ns(), "store_mode": mode or read_store_mode(codex_home), "resolved_source": source, "store_key": store_key(codex_home), "auth": copy.deepcopy(auth), "metadata": auth_metadata(auth, source)}

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".hms-", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tp = Path(tmp)
    try:
        tp.write_text(text, encoding="utf-8", newline="\n")
        with tp.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(tp, path)
    finally:
        try:
            tp.unlink(missing_ok=True)
        except Exception:
            pass

def save_auth(codex_home: Path, auth: dict[str, Any], mode: str | None = None, keyring: KeyringAdapter | None = None, keyring_backend: str | None = None) -> str:
    mode = (mode or read_store_mode(codex_home)).lower()
    raw = json.dumps(auth, ensure_ascii=False, indent=2) + "\n"
    path = codex_home / "auth.json"
    key = store_key(codex_home)
    if mode == "file":
        _atomic_write(path, raw)
        return "file"
    if mode == "keyring":
        _ensure_direct_keyring_backend(codex_home, keyring_backend)
        if keyring is None:
            raise AuthCompatibilityError("KEYRING_ADAPTER_REQUIRED")
        keyring.save(KEYRING_SERVICE, key, json.dumps(auth, ensure_ascii=False, separators=(",", ":")))
        path.unlink(missing_ok=True)
        return "keyring"
    if mode == "auto":
        # In Secrets mode HMS must not manufacture a direct generic credential. Auto
        # therefore fails closed if keyring authority is encrypted/official-owned.
        _ensure_direct_keyring_backend(codex_home, keyring_backend)
        if keyring is not None:
            try:
                keyring.save(KEYRING_SERVICE, key, json.dumps(auth, ensure_ascii=False, separators=(",", ":")))
                path.unlink(missing_ok=True)
                return "keyring"
            except Exception:
                pass
        _atomic_write(path, raw)
        return "file"
    raise AuthCompatibilityError("STORE_MODE_NOT_PERSISTABLE")

def verify_saved(codex_home: Path, expected: dict[str, Any], mode: str, keyring: KeyringAdapter | None, keyring_backend: str | None = None) -> tuple[bool, str]:
    got, src = load_auth(codex_home, mode, keyring, keyring_backend)
    return got == expected, src

_GLOBAL_LOCK = threading.Lock()

def switch_auth(codex_home: Path, target: dict[str, Any], mode: str | None = None, keyring: KeyringAdapter | None = None, verify: bool = True, hold_seconds: float = 0, keyring_backend: str | None = None) -> dict[str, Any]:
    if not _GLOBAL_LOCK.acquire(timeout=10):
        raise AuthCompatibilityError("SWITCH_BUSY")
    try:
        snap = snapshot_current(codex_home, mode, keyring, keyring_backend)
        resolved_mode = str(mode or snap["store_mode"])
        current = copy.deepcopy(snap["auth"])
        merged = rewrite_preserving_fields(current, target)
        before = auth_metadata(current, snap["resolved_source"])
        target_meta = auth_metadata(normalize_target_auth(target), "managed-account")
        committed = False
        source = ""
        try:
            source = save_auth(codex_home, merged, resolved_mode, keyring, keyring_backend)
            committed = True
            if hold_seconds > 0:
                time.sleep(hold_seconds)
            if verify:
                ok, read_src = verify_saved(codex_home, merged, resolved_mode, keyring, keyring_backend)
                if not ok:
                    raise AuthCompatibilityError("AUTH_READBACK_MISMATCH")
            else:
                read_src = source
        except Exception:
            if committed:
                save_auth(codex_home, current, resolved_mode, keyring, keyring_backend)
            raise
        return {
            "ok": True, "version": VERSION, "store_mode": resolved_mode, "resolved_source": source,
            "readback_source": read_src, "before": before, "target": target_meta,
            "after": auth_metadata(merged, source), "rollback_available": True,
            "restart_codex_app_required": True, "serialized": True,
            "secret_material_emitted": False,
        }
    finally:
        _GLOBAL_LOCK.release()

def derive_codex_user_agent(codex_version: str | None = None, originator: str | None = None) -> str:
    origin = (originator or COCKPIT_V1324_ORIGINATOR).strip()
    raw = str(codex_version or "").strip()
    # Accept common `codex-cli X`, `codex X` and bare version outputs.
    m = re.search(r"(?i)(?:codex(?:-cli)?\s+)?([0-9]+(?:\.[0-9A-Za-z-]+)+)", raw)
    version = m.group(1) if m else OFFICIAL_AUTH_USER_AGENT_BASELINE.split("/", 1)[-1]
    return f"{origin}/{version}"

def official_http_identity(user_agent: str | None = None, originator: str | None = None, codex_version: str | None = None) -> dict[str, str]:
    origin = (originator or COCKPIT_V1324_ORIGINATOR).strip()
    ua = (user_agent or derive_codex_user_agent(codex_version, origin)).strip()
    return {"originator": origin, "User-Agent": ua}

def identity_profiles(codex_version: str | None = None) -> dict[str, dict[str, str]]:
    return {
        "cockpit_v1_3_24_oauth": official_http_identity(originator=COCKPIT_V1324_ORIGINATOR, codex_version=codex_version),
        "official_codex_cli": official_http_identity(originator=OFFICIAL_CODEX_CLI_ORIGINATOR, codex_version=codex_version),
    }

def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k.lower() in SECRET_KEYS:
                out[k] = "<redacted>"
            elif k == "auth":
                out[k] = {"sha256": safe_hash(json.dumps(v, sort_keys=True, default=str)), "redacted": True}
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

def audit_payload(codex_home: Path, mode: str | None = None, keyring: KeyringAdapter | None = None) -> dict[str, Any]:
    try:
        auth, source = load_auth(codex_home, mode, keyring)
        selected = mode or read_store_mode(codex_home)
        return {"ok": auth is not None, "version": VERSION, "store_mode": selected, "resolved_source": source, "keyring_backend": read_keyring_backend_kind(codex_home), "store_key_hash": safe_hash(store_key(codex_home)), "auth": auth_metadata(auth, source), "oauth_identity": official_http_identity(), "identity_profiles": identity_profiles(), "claim_boundary": "COMPATIBILITY_AUDIT_ONLY_NO_LIVE_CODEX_CLAIM"}
    except Exception as exc:
        return {"ok": False, "version": VERSION, "error_code": type(exc).__name__, "claim_boundary": "COMPATIBILITY_AUDIT_ONLY_NO_LIVE_CODEX_CLAIM"}
