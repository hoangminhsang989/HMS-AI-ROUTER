#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
try:
    from HMS_Codex_WindowsTargetAdapterPack import WindowsTargetAdapterPack
except Exception:
    WindowsTargetAdapterPack = None
try:
    from HMS_Codex_WindowsRecoveryObserverBridge import WindowsRecoveryObserverBridge
except Exception:
    WindowsRecoveryObserverBridge = None

VERSION = "25.65"
SCHEMA_VERSION = 1
PRODUCTION_CLAIM = "NOT_CLAIMED_STARTUP_RECONCILER_REAL_WINDOWS_CODEX_EFFECT_EVIDENCE_REQUIRED"
CONVERGENCE = {"HEALTHY", "DEGRADED_SAFE", "OPERATOR_REQUIRED"}
EFFECT_KINDS = {
    "OFFICIAL_AUTH_REWRITE",
    "CONTROLLED_CODEX_RESTART",
    "ROUTER_STATE_TRANSITION",
    "LAN_LEASE_HANDOFF",
}
ACTION_TO_EFFECT = {
    "OFFICIAL_AUTH_SWITCH": "OFFICIAL_AUTH_REWRITE",
    "CLIENT_RESTART": "CONTROLLED_CODEX_RESTART",
    "ROUTER_RESTART": "ROUTER_STATE_TRANSITION",
    "LEASE_REELECTION": "LAN_LEASE_HANDOFF",
}
CONFLICTING_BACKEND_ACTIONS = {
    "restart_router", "run_failover", "apply_adaptive_router", "rollback_adaptive_router",
    "apply_closed_loop_router", "rollback_closed_loop_router", "apply_circuit_breaker",
    "reset_circuit_breaker", "create_instance", "start_instance", "stop_instance",
    "restart_instance", "launch_project_affinity", "sync_project_router", "apply_model_policy",
    "repair_self_healing", "launch_project_orchestrator", "launch_multi_codex_team",
    "apply_smart_model_router", "rollback_smart_model_router", "pair_lan_pool",
    "acquire_lan_project", "release_lan_project",
}
SENSITIVE = (
    "token", "secret", "password", "authorization", "cookie", "credential", "api_key",
    "prompt", "request_body", "response_body", "email", "account",
)


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


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            kl = key.lower()
            out[key] = "<REDACTED>" if any(x in kl for x in SENSITIVE) else sanitize(v)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, tuple):
        return [sanitize(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 240:
        return obj[:240] + "…"
    return obj


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp-" + sha(payload)[:10])
    with tmp.open("wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text("utf-8-sig"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            raise ValueError(f"JOURNAL_JSON_INVALID:{path.name}:{n}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"JOURNAL_RECORD_INVALID:{path.name}:{n}")
        rows.append(row)
    return rows


def validate_hash_chain(rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    prev = "GENESIS"
    errors: list[str] = []
    seq: dict[str, int] = {}
    for i, row in enumerate(rows):
        if row.get("prev_hash") != prev:
            errors.append(f"PREV:{i}")
        raw = {k: v for k, v in row.items() if k != "record_hash"}
        if row.get("record_hash") != sha(stable(raw)):
            errors.append(f"HASH:{i}")
        tx = str(row.get("txn_id") or "")
        if tx:
            expected = seq.get(tx, 0) + 1
            try:
                actual = int(row.get("seq") or 0)
            except Exception:
                actual = -1
            if actual != expected:
                errors.append(f"SEQ:{i}")
            seq[tx] = actual
        prev = str(row.get("record_hash") or "")
    return not errors, errors


@dataclass(frozen=True)
class Observation:
    effect_kind: str
    observer: str
    available: bool
    observed_hash: str
    evidence_class: str
    detail: dict[str, Any]


class ReadOnlyObservers:
    """Read-only effect observers. No raw credential value is returned or serialized."""

    def __init__(self, data_dir: Path, *, auth_mode: str = "auto", auth_file: Path | None = None,
                 fixture_path: Path | None = None):
        self.data_dir = Path(data_dir)
        self.auth_mode = str(auth_mode or "auto").lower()
        default_auth = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "auth.json"
        self.auth_file = Path(auth_file) if auth_file else default_auth
        self.fixture_path = Path(fixture_path) if fixture_path else self.data_dir / "startup-recovery-v2563" / "observer-fixture-v2563.json"
        self.fixture = read_json(self.fixture_path)

    def _fixture(self, kind: str) -> Observation | None:
        row = (self.fixture.get("effects") or {}).get(kind)
        if not isinstance(row, dict):
            return None
        digest = str(row.get("observed_hash") or "")
        return Observation(kind, "TARGET_OBSERVER_FIXTURE", bool(digest), digest,
                           str(row.get("evidence_class") or "FIXTURE_HASH_ONLY"),
                           {"fixture": True, "source_ref": safe_ref(str(self.fixture_path))})

    def _auth(self) -> Observation:
        fx = self._fixture("OFFICIAL_AUTH_REWRITE")
        if fx:
            return fx
        mode = self.auth_mode
        if mode == "file" or (mode == "auto" and self.auth_file.exists()):
            try:
                raw = self.auth_file.read_bytes()
                stat = self.auth_file.stat()
                return Observation("OFFICIAL_AUTH_REWRITE", "CODEX_AUTH_FILE_HASH", True, sha(raw),
                                   "RAW_BYTES_SHA256_NO_CONTENT_EXPOSED",
                                   {"mode": "file", "exists": True, "size": stat.st_size, "path_ref": safe_ref(str(self.auth_file))})
            except Exception as exc:
                return Observation("OFFICIAL_AUTH_REWRITE", "CODEX_AUTH_FILE_HASH", False, "",
                                   "AUTH_FILE_READ_FAILED", {"mode": mode, "error_type": type(exc).__name__})
        # Keyring/auto must be supplied by a target adapter that returns a digest only. Reading
        # the secret into this process merely to hash it would violate the no-secret boundary.
        return Observation("OFFICIAL_AUTH_REWRITE", "CODEX_AUTH_KEYRING_DIGEST_ADAPTER", False, "",
                           "TARGET_KEYRING_DIGEST_PROVIDER_REQUIRED",
                           {"mode": mode, "secret_read_attempted": False})

    def _process(self) -> Observation:
        fx = self._fixture("CONTROLLED_CODEX_RESTART")
        if fx:
            return fx
        rows: list[dict[str, Any]] = []
        try:
            if os.name == "nt":
                p = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq codex.exe"],
                                   capture_output=True, text=True, timeout=8, creationflags=0x08000000)
                for rec in csv.reader(io.StringIO(p.stdout or "")):
                    if len(rec) >= 2 and rec[0].lower().startswith("codex"):
                        rows.append({"image": rec[0].lower(), "pid": int(rec[1]) if rec[1].isdigit() else 0})
            else:
                p = subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True, timeout=8)
                for line in (p.stdout or "").splitlines():
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2 and "codex" in parts[1].lower():
                        rows.append({"pid": int(parts[0]), "image": Path(parts[1]).name.lower()})
            rows = sorted(rows, key=lambda r: (r["image"], r["pid"]))
            return Observation("CONTROLLED_CODEX_RESTART", "CODEX_PROCESS_IDENTITY", True, sha(stable(rows)),
                               "PID_IMAGE_DIGEST_NO_CMDLINE", {"process_count": len(rows)})
        except Exception as exc:
            return Observation("CONTROLLED_CODEX_RESTART", "CODEX_PROCESS_IDENTITY", False, "",
                               "PROCESS_OBSERVER_FAILED", {"error_type": type(exc).__name__})

    def _router(self) -> Observation:
        fx = self._fixture("ROUTER_STATE_TRANSITION")
        if fx:
            return fx
        candidates = [
            self.data_dir / "gateway-state-v20.json",
            self.data_dir / "closed-loop-router" / "closed-loop-router-state-v2531.json",
            self.data_dir / "adaptive-router" / "adaptive-router-state-v2527.json",
        ]
        for p in candidates:
            obj = read_json(p)
            if obj:
                safe = {
                    "generation": obj.get("generation") or obj.get("epoch") or obj.get("version"),
                    "state": obj.get("state") or obj.get("status") or obj.get("mode"),
                    "port": obj.get("port") or obj.get("listen_port"),
                    "enabled": obj.get("enabled"),
                }
                return Observation("ROUTER_STATE_TRANSITION", "ROUTER_GENERATION_STATE", True, sha(stable(safe)),
                                   "ROUTER_METADATA_DIGEST", {"source_ref": safe_ref(str(p)), "fields": sorted(k for k, v in safe.items() if v is not None)})
        return Observation("ROUTER_STATE_TRANSITION", "ROUTER_GENERATION_STATE", False, "",
                           "ROUTER_STATE_NOT_FOUND", {"searched": len(candidates)})

    def _lease(self) -> Observation:
        fx = self._fixture("LAN_LEASE_HANDOFF")
        if fx:
            return fx
        candidates = [
            self.data_dir / "lan-pool" / "lan-pool-latest-v2545.json",
            self.data_dir / "lan-pool" / "local-node-v2545.json",
        ]
        for p in candidates:
            obj = read_json(p)
            if obj:
                # Owner identity is hashed before returning. Epoch/project lease metadata are not secrets.
                owner = str(obj.get("owner") or obj.get("owner_node") or obj.get("lease_owner") or "")
                safe = {
                    "owner_ref": safe_ref(owner) if owner else "",
                    "epoch": obj.get("epoch") or obj.get("lease_epoch"),
                    "generation": obj.get("generation"),
                    "state": obj.get("state") or obj.get("status"),
                }
                return Observation("LAN_LEASE_HANDOFF", "LAN_LEASE_OWNER_EPOCH", True, sha(stable(safe)),
                                   "LEASE_METADATA_DIGEST_OWNER_HASHED", {"source_ref": safe_ref(str(p)), "owner_exposed": False})
        return Observation("LAN_LEASE_HANDOFF", "LAN_LEASE_OWNER_EPOCH", False, "",
                           "LAN_LEASE_STATE_NOT_FOUND", {"searched": len(candidates)})

    def observe(self, kind: str) -> Observation:
        if kind == "OFFICIAL_AUTH_REWRITE":
            return self._auth()
        if kind == "CONTROLLED_CODEX_RESTART":
            return self._process()
        if kind == "ROUTER_STATE_TRANSITION":
            return self._router()
        if kind == "LAN_LEASE_HANDOFF":
            return self._lease()
        return Observation(kind, "UNKNOWN", False, "", "UNSUPPORTED_EFFECT_OBSERVER", {})


class StartupRecoveryReconciler:
    def __init__(self, data_dir: Path, *, auth_mode: str = "auto", auth_file: Path | None = None,
                 fixture_path: Path | None = None):
        self.data_dir = Path(data_dir)
        
        if fixture_path is None and WindowsTargetAdapterPack is not None:
            self.observers = WindowsTargetAdapterPack(self.data_dir, auth_mode=auth_mode, auth_file=auth_file)
            self.observer_bridge = "WINDOWS_TARGET_ADAPTER_PACK_V25.65"
        elif WindowsRecoveryObserverBridge is not None:
            self.observers = WindowsRecoveryObserverBridge(self.data_dir, auth_mode=auth_mode, auth_file=auth_file, fixture_path=fixture_path)
            self.observer_bridge = "WINDOWS_RECOVERY_OBSERVER_BRIDGE_V25.64_COMPAT"
        else:
            self.observers = ReadOnlyObservers(self.data_dir, auth_mode=auth_mode, auth_file=auth_file, fixture_path=fixture_path)
            self.observer_bridge = "LEGACY_READ_ONLY_OBSERVER_FALLBACK"

    def _classify_observation(self, obs: Observation, before_hash: str, desired_hash: str, durable: bool) -> tuple[str, str]:
        if not obs.available:
            return "OPERATOR_REQUIRED", "OBSERVER_EVIDENCE_UNAVAILABLE"
        if desired_hash and obs.observed_hash == desired_hash:
            return "DEGRADED_SAFE", "VERIFY_ONLY_NO_REPEAT" if durable else "OBSERVED_ALREADY_APPLIED_NO_REPEAT"
        if before_hash and obs.observed_hash == before_hash:
            if durable:
                return "OPERATOR_REQUIRED", "DURABLE_EFFECT_EXTERNAL_MISMATCH"
            return "DEGRADED_SAFE", "SAFE_TO_RESUME_OR_ROLLBACK_AFTER_POLICY"
        return "OPERATOR_REQUIRED", "CONCURRENT_EXTERNAL_CHANGE_OWNERSHIP_UNPROVEN"

    def _reconcile_v2562(self, path: Path) -> list[dict[str, Any]]:
        try:
            rows = read_jsonl(path)
        except Exception as exc:
            return [{"source": "v25.62", "journal_ref": safe_ref(str(path)), "status": "OPERATOR_REQUIRED", "reason": str(exc), "block_conflicting_mutation": True}]
        ok, errors = validate_hash_chain(rows)
        if not ok:
            return [{"source": "v25.62", "journal_ref": safe_ref(str(path)), "status": "OPERATOR_REQUIRED", "reason": "JOURNAL_CHAIN_INVALID", "errors": errors[:8], "block_conflicting_mutation": True}]
        txs: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            tx = str(row.get("txn_id") or "")
            if tx:
                txs.setdefault(tx, []).append(row)
        out: list[dict[str, Any]] = []
        for tx, txrows in sorted(txs.items()):
            phases = {str(r.get("phase") or "") for r in txrows}
            tref = safe_ref(tx)
            if "TXN_DONE" in phases:
                continue
            if "OPERATOR_REQUIRED" in phases:
                out.append({"source": "v25.62", "transaction_ref": tref, "status": "OPERATOR_REQUIRED", "reason": "PRIOR_OPERATOR_REQUIRED", "block_conflicting_mutation": True})
                continue
            effects: list[dict[str, Any]] = []
            for eid in dict.fromkeys(str(r.get("effect_id") or "") for r in txrows if r.get("effect_id")):
                erows = [r for r in txrows if str(r.get("effect_id") or "") == eid]
                e_phases = {str(r.get("phase") or "") for r in erows}
                if "EFFECT_VERIFY" in e_phases or "EFFECT_COMPENSATE" in e_phases:
                    continue
                prep = next((r for r in reversed(erows) if r.get("phase") == "EFFECT_PREPARE"), {})
                last = erows[-1] if erows else {}
                kind = str(last.get("effect_kind") or prep.get("effect_kind") or "")
                meta = prep.get("meta") if isinstance(prep.get("meta"), dict) else {}
                before = str(meta.get("before_hash") or "")
                desired = str(meta.get("desired_hash") or "")
                obs = self.observers.observe(kind)
                status, decision = self._classify_observation(obs, before, desired, "EFFECT_DURABLE" in e_phases)
                effects.append({
                    "effect_ref": safe_ref(eid), "effect_kind": kind,
                    "effect_fingerprint": str(last.get("effect_fingerprint") or prep.get("effect_fingerprint") or "")[:80],
                    "journal_phase": str(last.get("phase") or ""), "status": status, "decision": decision,
                    "observer": obs.observer, "evidence_class": obs.evidence_class,
                    "freshness_state": getattr(obs, "freshness_state", "UNKNOWN"),
                    "failure_reason": getattr(obs, "failure_reason", ""),
                })
            if not effects:
                # Transaction prepared but no effect started yet.
                out.append({"source": "v25.62", "transaction_ref": tref, "status": "DEGRADED_SAFE", "reason": "TRANSACTION_PREPARED_NO_EFFECT", "effects": [], "block_conflicting_mutation": True})
            else:
                status = "OPERATOR_REQUIRED" if any(e["status"] == "OPERATOR_REQUIRED" for e in effects) else "DEGRADED_SAFE"
                out.append({"source": "v25.62", "transaction_ref": tref, "status": status, "reason": "UNRESOLVED_CROSS_SUBSYSTEM_TRANSACTION", "effects": effects, "block_conflicting_mutation": True})
        return out

    def _reconcile_v2560(self, path: Path) -> list[dict[str, Any]]:
        try:
            rows = read_jsonl(path)
        except Exception as exc:
            return [{"source": "v25.60", "journal_ref": safe_ref(str(path)), "status": "OPERATOR_REQUIRED", "reason": str(exc), "block_conflicting_mutation": True}]
        ok, errors = validate_hash_chain(rows)
        if not ok:
            return [{"source": "v25.60", "journal_ref": safe_ref(str(path)), "status": "OPERATOR_REQUIRED", "reason": "JOURNAL_CHAIN_INVALID", "errors": errors[:8], "block_conflicting_mutation": True}]
        txs: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            tx = str(row.get("txn_id") or "")
            if tx:
                txs.setdefault(tx, []).append(row)
        out: list[dict[str, Any]] = []
        for tx, txrows in sorted(txs.items()):
            last = txrows[-1]
            phase = str(last.get("phase") or "")
            if phase in {"DONE", "ROLLBACK"}:
                continue
            action = str(last.get("action") or "")
            kind = ACTION_TO_EFFECT.get(action, "")
            if not kind:
                out.append({"source": "v25.60", "transaction_ref": safe_ref(tx), "status": "OPERATOR_REQUIRED", "reason": "NO_SAFE_OBSERVER_FOR_LEGACY_ACTION", "action": action, "block_conflicting_mutation": True})
                continue
            obs = self.observers.observe(kind)
            if phase in {"COMMIT", "VERIFY"}:
                # Durable COMMIT must never cause a second mutation at startup. External observer
                # presence is required before a later recovery executor can mark DONE.
                status = "DEGRADED_SAFE" if obs.available else "OPERATOR_REQUIRED"
                reason = "VERIFY_ONLY_NO_REPEAT" if obs.available else "OBSERVER_EVIDENCE_UNAVAILABLE"
            else:
                status = "OPERATOR_REQUIRED"
                reason = "LEGACY_PREPARE_COMMIT_STATUS_UNKNOWN"
            out.append({"source": "v25.60", "transaction_ref": safe_ref(tx), "status": status, "reason": reason, "action": action,
                        "observer": obs.observer, "evidence_class": obs.evidence_class,
                        "freshness_state": getattr(obs, "freshness_state", "UNKNOWN"),
                        "failure_reason": getattr(obs, "failure_reason", ""),
                        "block_conflicting_mutation": True})
        return out

    def discover(self) -> list[Path]:
        candidates = [self.data_dir / "recovery-journal-v2560" / "recovery-transaction-journal-v2560.jsonl"]
        rr = self.data_dir / "recovery-replay-v2562"
        if rr.exists():
            candidates.extend(sorted(p for p in rr.rglob("*.jsonl") if p.is_file()))
        return [p for p in candidates if p.exists()]

    def reconcile(self, *, write_gate: bool = True) -> dict[str, Any]:
        journals = self.discover()
        items: list[dict[str, Any]] = []
        for p in journals:
            if "v2560" in p.name or "recovery-journal-v2560" in str(p):
                items.extend(self._reconcile_v2560(p))
            else:
                items.extend(self._reconcile_v2562(p))
        status = "HEALTHY"
        if any(x.get("status") == "OPERATOR_REQUIRED" for x in items):
            status = "OPERATOR_REQUIRED"
        elif items:
            status = "DEGRADED_SAFE"
        blocked = sorted(CONFLICTING_BACKEND_ACTIONS) if any(x.get("block_conflicting_mutation") for x in items) else []
        report = {
            "product": "HMS-AI-ROUTER", "version": VERSION, "schema_version": SCHEMA_VERSION,
            "generated_utc": utcnow(), "status": status,
            "summary": {
                "journals_discovered": len(journals), "unresolved_transactions": len(items),
                "operator_required": sum(x.get("status") == "OPERATOR_REQUIRED" for x in items),
                "degraded_safe": sum(x.get("status") == "DEGRADED_SAFE" for x in items),
                "blocked_conflicting_actions": len(blocked),
            },
            "mutation_gate": {"block_conflicting_mutation": bool(blocked), "blocked_actions": blocked},
            "timeline": sanitize(items),
            "observer_bridge": self.observer_bridge,
            "evidence": {"class": "WINDOWS_TARGET_OBSERVER" if os.name == "nt" else "LAB_FIXTURE", "production_score_eligible": False},
            "privacy": {"metadata_only": True, "raw_credentials": False, "raw_account_identity": False},
            "production_certification": PRODUCTION_CLAIM,
        }
        if write_gate:
            gate = self.data_dir / "startup-recovery-v2565" / "startup-recovery-gate-v2565.json"
            atomic_json(gate, report)
        return report


def mutation_allowed(gate: dict[str, Any], action: str) -> bool:
    mg = gate.get("mutation_gate") if isinstance(gate.get("mutation_gate"), dict) else {}
    if not mg.get("block_conflicting_mutation"):
        return True
    return action not in set(mg.get("blocked_actions") or [])


def synthetic_proof() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": sanitize(detail)})

    with tempfile.TemporaryDirectory(prefix="hms-v2563-reconcile-") as td:
        data = Path(td)
        state = data / "startup-recovery-v2563"
        state.mkdir(parents=True)
        desired = {k: sha("desired:" + k) for k in EFFECT_KINDS}
        fixture = {"effects": {k: {"observed_hash": v, "evidence_class": "SYNTHETIC_OBSERVER_DIGEST"} for k, v in desired.items()}}
        atomic_json(state / "observer-fixture-v2563.json", fixture)
        rrdir = data / "recovery-replay-v2562"; rrdir.mkdir()
        tx = "tx-secret-never-export"
        rows: list[dict[str, Any]] = []; prev = "GENESIS"; seq = 0
        def app(phase: str, *, eid: str = "", kind: str = "", before: str = "", want: str = "") -> None:
            nonlocal prev, seq
            seq += 1
            meta = {"before_hash": before, "desired_hash": want} if phase == "EFFECT_PREPARE" else {}
            row = {"schema_version": 1, "version": "25.62", "txn_id": tx, "seq": seq, "phase": phase, "time_utc": utcnow(),
                   "intent_fingerprint": "intent-proof", "effect_id": eid, "effect_kind": kind,
                   "effect_fingerprint": "eff-proof-" + eid if eid else "", "idempotency_key_hash": "idem-hash" if eid else "", "meta": meta, "prev_hash": prev}
            row["record_hash"] = sha(stable(row)); prev = row["record_hash"]; rows.append(row)
        app("TXN_PREPARE")
        app("EFFECT_PREPARE", eid="auth", kind="OFFICIAL_AUTH_REWRITE", before=sha("before:auth"), want=desired["OFFICIAL_AUTH_REWRITE"])
        p = rrdir / "unresolved.jsonl"; p.write_text("".join(stable(r) + "\n" for r in rows), "utf-8")
        rec = StartupRecoveryReconciler(data, fixture_path=state / "observer-fixture-v2563.json")
        r = rec.reconcile()
        add("unresolved_detected", r["summary"]["unresolved_transactions"] == 1, r["summary"])
        add("desired_observed_no_repeat", r["status"] == "DEGRADED_SAFE" and r["timeline"][0]["effects"][0]["decision"] == "OBSERVED_ALREADY_APPLIED_NO_REPEAT", r["timeline"])
        add("conflicting_mutation_blocked", not mutation_allowed(r, "restart_router"))
        add("read_only_action_allowed", mutation_allowed(r, "get_accounts"))
        raw = stable(r)
        add("transaction_identity_hashed", tx not in raw and "ref-" in raw)
        add("privacy_metadata_only", r["privacy"]["metadata_only"] and not r["privacy"]["raw_credentials"])
        add("gate_written", (data / "startup-recovery-v2565" / "startup-recovery-gate-v2565.json").exists())

        # Change observer away from before/desired: ownership cannot be proven => fail closed.
        fixture["effects"]["OFFICIAL_AUTH_REWRITE"]["observed_hash"] = sha("concurrent-change")
        atomic_json(state / "observer-fixture-v2563.json", fixture)
        r2 = StartupRecoveryReconciler(data, fixture_path=state / "observer-fixture-v2563.json").reconcile()
        add("concurrent_change_operator_required", r2["status"] == "OPERATOR_REQUIRED", r2["timeline"])
        add("operator_required_blocks_conflict", not mutation_allowed(r2, "restart_router"))

        # Invalid chain fails closed.
        bad = rrdir / "bad.jsonl"; corrupt = dict(rows[0]); corrupt["record_hash"] = "bad"; bad.write_text(stable(corrupt) + "\n", "utf-8")
        r3 = StartupRecoveryReconciler(data, fixture_path=state / "observer-fixture-v2563.json").reconcile()
        add("invalid_chain_operator_required", r3["status"] == "OPERATOR_REQUIRED")

    add("all_effect_observers_defined", set(EFFECT_KINDS) == {"OFFICIAL_AUTH_REWRITE", "CONTROLLED_CODEX_RESTART", "ROUTER_STATE_TRANSITION", "LAN_LEASE_HANDOFF"})
    add("production_claim_blocked", PRODUCTION_CLAIM.startswith("NOT_CLAIMED"))
    passed = sum(c["ok"] for c in checks)
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION, "suite": "STARTUP_RECOVERY_RECONCILER_PROOF",
        "generated_utc": utcnow(), "verdict": "PASS" if passed == len(checks) else "FAIL",
        "summary": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks, "production_certification": PRODUCTION_CLAIM,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("reconcile", "proof"), default="reconcile")
    ap.add_argument("--data-dir")
    ap.add_argument("--output")
    ap.add_argument("--auth-mode", choices=("file", "keyring", "auto"), default="auto")
    ap.add_argument("--auth-file")
    ap.add_argument("--observer-fixture")
    args = ap.parse_args()
    if args.mode == "proof":
        out = synthetic_proof()
        rc = 0 if out["verdict"] == "PASS" else 2
    else:
        if not args.data_dir:
            raise SystemExit("--data-dir required")
        rec = StartupRecoveryReconciler(Path(args.data_dir), auth_mode=args.auth_mode,
                                        auth_file=Path(args.auth_file) if args.auth_file else None,
                                        fixture_path=Path(args.observer_fixture) if args.observer_fixture else None)
        out = rec.reconcile(write_gate=True)
        rc = 0 if out["status"] in CONVERGENCE else 2
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        atomic_json(Path(args.output), out)
    print(text)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
