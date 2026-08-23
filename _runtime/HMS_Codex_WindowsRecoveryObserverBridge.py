#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.64"
SCHEMA_VERSION = 1
EVIDENCE_CLASSES = {"LAB_FIXTURE", "WINDOWS_TARGET_OBSERVER", "REAL_CODEX_EFFECT"}
EFFECT_KINDS = (
    "OFFICIAL_AUTH_REWRITE",
    "CONTROLLED_CODEX_RESTART",
    "ROUTER_STATE_TRANSITION",
    "LAN_LEASE_HANDOFF",
)
PRODUCTION_CLAIM = "NOT_CLAIMED_WINDOWS_TARGET_OBSERVER_EVIDENCE_REQUIRED"
SENSITIVE_KEYS = (
    "token", "secret", "password", "authorization", "cookie", "credential",
    "api_key", "access_key", "email", "account", "prompt", "body",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8", "surrogatepass")
    return hashlib.sha256(value).hexdigest()


def safe_ref(value: str) -> str:
    return "ref-" + sha(value)[:20]


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp-" + sha(raw)[:10])
    with tmp.open("wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text("utf-8-sig"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            k = str(key)
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                out[k] = "<REDACTED>"
            else:
                out[k] = sanitize(value)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, tuple):
        return [sanitize(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 240:
        return obj[:240] + "…"
    return obj


def age_seconds(path: Path) -> float | None:
    try:
        return max(0.0, datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)
    except Exception:
        return None


def freshness(age: float | None, fresh_limit: float = 120.0, stale_limit: float = 900.0) -> str:
    if age is None:
        return "UNKNOWN"
    if age <= fresh_limit:
        return "FRESH"
    if age <= stale_limit:
        return "AGING"
    return "STALE"


@dataclass(frozen=True)
class BridgeObservation:
    effect_kind: str
    observer: str
    available: bool
    observed_hash: str
    evidence_class: str
    freshness_state: str
    observed_utc: str
    source_age_seconds: float | None
    failure_reason: str
    detail: dict[str, Any]

    def public(self) -> dict[str, Any]:
        return sanitize(asdict(self))


class WindowsRecoveryObserverBridge:
    """Secret-safe observer bridge.

    The bridge never serializes raw auth material, command lines, environment variables,
    usernames, account identifiers or LAN owner identities. Keyring auth requires an
    external digest-only provider. If that proof is unavailable the observation fails closed.
    """

    def __init__(
        self,
        data_dir: Path,
        *,
        auth_mode: str = "auto",
        auth_file: Path | None = None,
        keyring_digest_provider: Path | None = None,
        fixture_path: Path | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.auth_mode = str(auth_mode or "auto").lower()
        self.auth_file = Path(auth_file) if auth_file else Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "auth.json"
        self.keyring_digest_provider = Path(keyring_digest_provider) if keyring_digest_provider else None
        self.fixture_path = Path(fixture_path) if fixture_path else None
        self.fixture = read_json(self.fixture_path) if self.fixture_path else {}

    def _unavailable(self, kind: str, observer: str, reason: str, *, detail: dict[str, Any] | None = None) -> BridgeObservation:
        return BridgeObservation(kind, observer, False, "", "WINDOWS_TARGET_OBSERVER", "UNKNOWN", utcnow(), None, reason, detail or {})

    def _fixture(self, kind: str) -> BridgeObservation | None:
        row = (self.fixture.get("effects") or {}).get(kind)
        if not isinstance(row, dict):
            return None
        digest = str(row.get("observed_hash") or "").lower()
        age = float(row.get("source_age_seconds") or 0.0)
        available = bool(HEX64.fullmatch(digest))
        return BridgeObservation(
            kind,
            "LAB_TARGET_OBSERVER_FIXTURE",
            available,
            digest if available else "",
            "LAB_FIXTURE",
            str(row.get("freshness_state") or freshness(age)),
            utcnow(),
            age,
            "" if available else "FIXTURE_DIGEST_INVALID",
            {"fixture": True, "source_ref": safe_ref(str(self.fixture_path or "fixture"))},
        )

    def _auth_file(self) -> BridgeObservation:
        kind = "OFFICIAL_AUTH_REWRITE"
        try:
            raw = self.auth_file.read_bytes()
            stat = self.auth_file.stat()
            age = age_seconds(self.auth_file)
            return BridgeObservation(
                kind,
                "CODEX_AUTH_FILE_RAW_BYTES_SHA256",
                True,
                sha(raw),
                "WINDOWS_TARGET_OBSERVER" if os.name == "nt" else "LAB_FIXTURE",
                freshness(age),
                utcnow(),
                age,
                "",
                {"mode": "file", "exists": True, "size": stat.st_size, "path_ref": safe_ref(str(self.auth_file)), "raw_content_exported": False},
            )
        except Exception as exc:
            return self._unavailable(kind, "CODEX_AUTH_FILE_RAW_BYTES_SHA256", "AUTH_FILE_READ_FAILED", detail={"error_type": type(exc).__name__, "path_ref": safe_ref(str(self.auth_file))})

    def _keyring_digest(self) -> BridgeObservation:
        kind = "OFFICIAL_AUTH_REWRITE"
        if os.name != "nt":
            return self._unavailable(kind, "CODEX_KEYRING_DIGEST_PROVIDER", "WINDOWS_TARGET_REQUIRED", detail={"secret_read_attempted": False})
        provider = self.keyring_digest_provider
        if not provider or not provider.is_file():
            return self._unavailable(kind, "CODEX_KEYRING_DIGEST_PROVIDER", "TARGET_KEYRING_DIGEST_PROVIDER_REQUIRED", detail={"secret_read_attempted": False})
        # Provider contract is digest-only JSON. No secret, username or raw account identity is accepted.
        try:
            p = subprocess.run([str(provider), "--hms-digest-only"], capture_output=True, text=True, timeout=15, creationflags=0x08000000)
            if p.returncode != 0:
                return self._unavailable(kind, "CODEX_KEYRING_DIGEST_PROVIDER", "KEYRING_DIGEST_PROVIDER_FAILED", detail={"exit_code": p.returncode})
            obj = json.loads(p.stdout or "{}")
            digest = str(obj.get("digest_sha256") or "").lower()
            forbidden = stable(obj).lower()
            if not HEX64.fullmatch(digest) or any(k in forbidden for k in ('"token"', '"secret"', '"password"', '"email"', '"account"')):
                return self._unavailable(kind, "CODEX_KEYRING_DIGEST_PROVIDER", "KEYRING_PROVIDER_CONTRACT_REJECTED", detail={"secret_read_attempted": False})
            return BridgeObservation(kind, "CODEX_KEYRING_DIGEST_PROVIDER", True, digest, "WINDOWS_TARGET_OBSERVER", str(obj.get("freshness_state") or "FRESH"), utcnow(), None, "", {"secret_read_attempted": False, "provider_ref": safe_ref(str(provider))})
        except Exception as exc:
            return self._unavailable(kind, "CODEX_KEYRING_DIGEST_PROVIDER", "KEYRING_DIGEST_PROVIDER_EXCEPTION", detail={"error_type": type(exc).__name__, "secret_read_attempted": False})

    def _auth(self) -> BridgeObservation:
        fx = self._fixture("OFFICIAL_AUTH_REWRITE")
        if fx:
            return fx
        if self.auth_mode == "file" or (self.auth_mode == "auto" and self.auth_file.is_file()):
            return self._auth_file()
        return self._keyring_digest()

    def _process_windows(self) -> BridgeObservation:
        kind = "CONTROLLED_CODEX_RESTART"
        if os.name != "nt":
            return self._unavailable(kind, "WINDOWS_CODEX_PROCESS_GENERATION", "WINDOWS_TARGET_REQUIRED")
        ps = (
            "$ErrorActionPreference='Stop';"
            "$r=@(Get-Process -Name codex -ErrorAction SilentlyContinue | ForEach-Object {"
            "$ticks=$null;try{$ticks=$_.StartTime.ToUniversalTime().Ticks}catch{};"
            "[ordered]@{id=$_.Id;name=$_.ProcessName.ToLowerInvariant();start_ticks=$ticks}});"
            "$r|Sort-Object name,id|ConvertTo-Json -Compress -Depth 4"
        )
        try:
            p = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, timeout=15, creationflags=0x08000000)
            if p.returncode != 0:
                return self._unavailable(kind, "WINDOWS_CODEX_PROCESS_GENERATION", "WINDOWS_PROCESS_API_FAILED", detail={"exit_code": p.returncode})
            obj = json.loads((p.stdout or "[]").strip() or "[]")
            rows = obj if isinstance(obj, list) else ([obj] if isinstance(obj, dict) else [])
            safe_rows = []
            for row in rows:
                if isinstance(row, dict):
                    safe_rows.append({"id": int(row.get("id") or 0), "name": str(row.get("name") or "codex").lower(), "start_ticks": row.get("start_ticks")})
            safe_rows.sort(key=lambda x: (x["name"], x["id"]))
            return BridgeObservation(kind, "WINDOWS_CODEX_PROCESS_GENERATION", True, sha(stable(safe_rows)), "WINDOWS_TARGET_OBSERVER", "FRESH", utcnow(), 0.0, "", {"process_count": len(safe_rows), "command_line_collected": False, "environment_collected": False})
        except Exception as exc:
            return self._unavailable(kind, "WINDOWS_CODEX_PROCESS_GENERATION", "WINDOWS_PROCESS_OBSERVER_EXCEPTION", detail={"error_type": type(exc).__name__})

    def _process(self) -> BridgeObservation:
        fx = self._fixture("CONTROLLED_CODEX_RESTART")
        return fx if fx else self._process_windows()

    def _metadata_file(self, kind: str, observer: str, candidates: list[Path], fields: tuple[str, ...], owner_fields: tuple[str, ...] = ()) -> BridgeObservation:
        fx = self._fixture(kind)
        if fx:
            return fx
        for path in candidates:
            obj = read_json(path)
            if not obj:
                continue
            safe: dict[str, Any] = {}
            for field in fields:
                value = obj.get(field)
                if value is not None:
                    safe[field] = value
            for field in owner_fields:
                value = str(obj.get(field) or "")
                if value:
                    safe[field + "_ref"] = safe_ref(value)
            age = age_seconds(path)
            if not safe:
                continue
            return BridgeObservation(kind, observer, True, sha(stable(safe)), "WINDOWS_TARGET_OBSERVER" if os.name == "nt" else "LAB_FIXTURE", freshness(age), utcnow(), age, "", {"source_ref": safe_ref(str(path)), "fields": sorted(safe), "raw_owner_exposed": False})
        return self._unavailable(kind, observer, "RUNTIME_METADATA_NOT_FOUND", detail={"searched": len(candidates)})

    def _router(self) -> BridgeObservation:
        return self._metadata_file(
            "ROUTER_STATE_TRANSITION",
            "LIVE_ROUTER_GENERATION_METADATA",
            [
                self.data_dir / "gateway-state-v20.json",
                self.data_dir / "closed-loop-router" / "closed-loop-router-state-v2531.json",
                self.data_dir / "adaptive-router" / "adaptive-router-state-v2527.json",
            ],
            ("generation", "epoch", "version", "state", "status", "mode", "port", "listen_port", "enabled"),
        )

    def _lease(self) -> BridgeObservation:
        return self._metadata_file(
            "LAN_LEASE_HANDOFF",
            "LIVE_LAN_LEASE_OWNER_EPOCH",
            [
                self.data_dir / "lan-pool" / "lan-pool-latest-v2545.json",
                self.data_dir / "lan-pool" / "local-node-v2545.json",
            ],
            ("epoch", "lease_epoch", "generation", "state", "status", "project_hash"),
            ("owner", "owner_node", "lease_owner"),
        )

    def observe(self, kind: str) -> BridgeObservation:
        if kind == "OFFICIAL_AUTH_REWRITE":
            return self._auth()
        if kind == "CONTROLLED_CODEX_RESTART":
            return self._process()
        if kind == "ROUTER_STATE_TRANSITION":
            return self._router()
        if kind == "LAN_LEASE_HANDOFF":
            return self._lease()
        return self._unavailable(kind, "UNSUPPORTED", "UNSUPPORTED_EFFECT_OBSERVER")

    def snapshot(self) -> dict[str, Any]:
        observations = [self.observe(kind).public() for kind in EFFECT_KINDS]
        available = sum(bool(x.get("available")) for x in observations)
        windows_evidence = os.name == "nt" and all(x.get("evidence_class") == "WINDOWS_TARGET_OBSERVER" for x in observations if x.get("available"))
        verdict = "PASS" if available == len(EFFECT_KINDS) else "DEGRADED_FAIL_CLOSED"
        return {
            "product": "HMS-AI-ROUTER",
            "version": VERSION,
            "schema_version": SCHEMA_VERSION,
            "suite": "WINDOWS_RECOVERY_OBSERVER_BRIDGE",
            "generated_utc": utcnow(),
            "verdict": verdict,
            "summary": {"available": available, "unavailable": len(EFFECT_KINDS) - available, "total": len(EFFECT_KINDS)},
            "host": {
                "windows_target": os.name == "nt",
                "platform_family": "windows" if os.name == "nt" else "non-windows",
                "machine_class_ref": safe_ref(platform.machine() or "unknown"),
            },
            "evidence": {"class": "WINDOWS_TARGET_OBSERVER" if windows_evidence else "LAB_FIXTURE", "production_score_eligible": bool(windows_evidence and available == len(EFFECT_KINDS))},
            "observations": observations,
            "privacy": {"metadata_only": True, "raw_credentials": False, "raw_account_identity": False, "command_line_collected": False},
            "production_certification": PRODUCTION_CLAIM,
        }


def synthetic_proof() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": sanitize(detail)})

    with tempfile.TemporaryDirectory(prefix="hms-v2564-observer-") as td:
        root = Path(td)
        fixture = root / "observer.json"
        effects = {kind: {"observed_hash": sha("v2564:" + kind), "source_age_seconds": i * 30, "freshness_state": "FRESH"} for i, kind in enumerate(EFFECT_KINDS)}
        atomic_json(fixture, {"effects": effects})
        bridge = WindowsRecoveryObserverBridge(root, fixture_path=fixture)
        snap = bridge.snapshot()
        add("fixture_snapshot_pass", snap.get("verdict") == "PASS", snap.get("summary"))
        add("four_effects", len(snap.get("observations") or []) == 4)
        add("all_fixture_class", all(x.get("evidence_class") == "LAB_FIXTURE" for x in snap.get("observations") or []))
        add("freshness_exposed", all(x.get("freshness_state") in {"FRESH", "AGING", "STALE", "UNKNOWN"} for x in snap.get("observations") or []))
        add("failure_reason_field", all("failure_reason" in x for x in snap.get("observations") or []))
        add("privacy_metadata_only", snap.get("privacy", {}).get("metadata_only") is True and snap.get("privacy", {}).get("raw_credentials") is False)
        add("fixture_not_score_eligible", snap.get("evidence", {}).get("production_score_eligible") is False)

        bad = root / "bad.json"
        atomic_json(bad, {"effects": {"OFFICIAL_AUTH_REWRITE": {"observed_hash": "not-a-digest"}}})
        bad_obs = WindowsRecoveryObserverBridge(root, fixture_path=bad).observe("OFFICIAL_AUTH_REWRITE")
        add("invalid_digest_fails_closed", not bad_obs.available and bad_obs.failure_reason == "FIXTURE_DIGEST_INVALID")

        keyring_obs = WindowsRecoveryObserverBridge(root, auth_mode="keyring").observe("OFFICIAL_AUTH_REWRITE")
        add("keyring_never_read_by_bridge", not keyring_obs.available and keyring_obs.detail.get("secret_read_attempted") is False, keyring_obs.public())

    source = Path(__file__).read_text("utf-8")
    add("windows_process_no_cmdline", "command_line_collected\": False" in source and "Get-Process -Name codex" in source)
    process_source = inspect.getsource(WindowsRecoveryObserverBridge._process_windows)
    add("powershell_process_api_no_win32_commandline", "CommandLine" not in process_source and "Win32_Process" not in process_source)
    add("keyring_digest_contract", "--hms-digest-only" in source and "digest_sha256" in source)
    add("production_claim_blocked", PRODUCTION_CLAIM.startswith("NOT_CLAIMED"))
    passed = sum(x["status"] == "PASS" for x in checks)
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION, "suite": "WINDOWS_RECOVERY_OBSERVER_BRIDGE_PROOF",
        "generated_utc": utcnow(), "verdict": "PASS" if passed == len(checks) else "FAIL",
        "summary": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks, "production_certification": PRODUCTION_CLAIM,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("observe", "proof"), default="observe")
    ap.add_argument("--data-dir")
    ap.add_argument("--output")
    ap.add_argument("--auth-mode", choices=("file", "keyring", "auto"), default="auto")
    ap.add_argument("--auth-file")
    ap.add_argument("--keyring-digest-provider")
    ap.add_argument("--fixture")
    args = ap.parse_args()
    if args.mode == "proof":
        out = synthetic_proof()
        rc = 0 if out["verdict"] == "PASS" else 2
    else:
        if not args.data_dir:
            raise SystemExit("--data-dir required")
        bridge = WindowsRecoveryObserverBridge(
            Path(args.data_dir),
            auth_mode=args.auth_mode,
            auth_file=Path(args.auth_file) if args.auth_file else None,
            keyring_digest_provider=Path(args.keyring_digest_provider) if args.keyring_digest_provider else None,
            fixture_path=Path(args.fixture) if args.fixture else None,
        )
        out = bridge.snapshot()
        rc = 0 if out["verdict"] == "PASS" else 3
    if args.output:
        atomic_json(Path(args.output), out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
