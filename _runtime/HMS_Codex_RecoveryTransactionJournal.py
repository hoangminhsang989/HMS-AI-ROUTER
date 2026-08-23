#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION = "25.60"
SCHEMA_VERSION = 1
PHASES = ("PREPARE", "COMMIT", "VERIFY", "ROLLBACK", "DONE")
TERMINAL = {"DONE", "ROLLBACK"}
PRODUCTION_CLAIM = "NOT_CLAIMED_RECOVERY_JOURNAL_SYNTHETIC_ONLY"
SENSITIVE_KEYS = {
    "token", "access_token", "refresh_token", "id_token", "api_key", "authorization",
    "cookie", "password", "secret", "prompt", "request_body", "response_body", "payload",
}
ACTION_POLICIES: dict[str, dict[str, Any]] = {
    "OFFICIAL_AUTH_SWITCH": {"duplicate_commit_forbidden": True, "resume_after_commit": "VERIFY", "rollback_required": True},
    "ROUTER_RESTART": {"duplicate_commit_forbidden": True, "resume_after_commit": "VERIFY", "rollback_required": False},
    "CLIENT_RESTART": {"duplicate_commit_forbidden": True, "resume_after_commit": "VERIFY", "rollback_required": False},
    "CONFIG_REPAIR": {"duplicate_commit_forbidden": True, "resume_after_commit": "VERIFY", "rollback_required": True},
    "LEASE_REELECTION": {"duplicate_commit_forbidden": True, "resume_after_commit": "VERIFY", "rollback_required": False},
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8", "surrogatepass")
    return hashlib.sha256(value).hexdigest()


def sanitize_meta(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SENSITIVE_KEYS or kl.endswith(("_token", "_secret", "_password", "_api_key")):
                out[str(k)] = "<REDACTED>"
            else:
                out[str(k)] = sanitize_meta(v)
        return out
    if isinstance(obj, list):
        return [sanitize_meta(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 512:
        return obj[:512] + "…"
    return obj


def has_secret_shape(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SENSITIVE_KEYS or kl.endswith(("_token", "_secret", "_password", "_api_key")):
                if v not in (None, "", "<REDACTED>"):
                    return True
            if has_secret_shape(v):
                return True
    elif isinstance(obj, list):
        return any(has_secret_shape(x) for x in obj)
    return False


@dataclass(frozen=True)
class RecoveryDecision:
    txn_id: str
    action: str
    next_step: str
    reason: str
    committed: bool
    verified: bool
    terminal: bool
    duplicate_commit_allowed: bool = False


class JournalError(RuntimeError):
    pass


class RecoveryJournal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8-sig") as fh:
            for ln, line in enumerate(fh, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                except Exception as exc:
                    raise JournalError(f"JOURNAL_JSON_INVALID_LINE_{ln}") from exc
                if not isinstance(row, dict):
                    raise JournalError(f"JOURNAL_RECORD_INVALID_LINE_{ln}")
                rows.append(row)
        return rows

    def validate_chain(self) -> dict[str, Any]:
        rows = self._records()
        prev = "GENESIS"
        seen: dict[str, int] = {}
        errors: list[str] = []
        for idx, row in enumerate(rows):
            if row.get("schema_version") != SCHEMA_VERSION:
                errors.append(f"SCHEMA:{idx}")
            if row.get("prev_hash") != prev:
                errors.append(f"PREV_HASH:{idx}")
            raw = {k: v for k, v in row.items() if k != "record_hash"}
            expected = sha256(stable_json(raw))
            if row.get("record_hash") != expected:
                errors.append(f"RECORD_HASH:{idx}")
            if has_secret_shape(row.get("meta") or {}):
                errors.append(f"SECRET_META:{idx}")
            txn = str(row.get("txn_id") or "")
            seq = int(row.get("seq") or 0)
            if txn:
                if seq != seen.get(txn, 0) + 1:
                    errors.append(f"SEQ:{txn}:{idx}")
                seen[txn] = seq
            prev = str(row.get("record_hash") or "")
        return {"ok": not errors, "records": len(rows), "head_hash": prev, "errors": errors}

    def append(self, txn_id: str, action: str, phase: str, *, meta: dict[str, Any] | None = None,
               idempotency_key: str = "", result_hash: str = "", timestamp_utc: str | None = None) -> dict[str, Any]:
        if phase not in PHASES:
            raise JournalError("INVALID_PHASE")
        if action not in ACTION_POLICIES:
            raise JournalError("INVALID_ACTION")
        clean_meta = sanitize_meta(meta or {})
        if has_secret_shape(clean_meta):
            raise JournalError("SENSITIVE_META_REJECTED")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            rows = self._records()
            prev = rows[-1]["record_hash"] if rows else "GENESIS"
            prior = [r for r in rows if r.get("txn_id") == txn_id]
            seq = len(prior) + 1
            if prior and prior[-1].get("phase") in TERMINAL:
                raise JournalError("TRANSACTION_ALREADY_TERMINAL")
            if prior:
                allowed = {
                    "PREPARE": {"COMMIT", "ROLLBACK"},
                    "COMMIT": {"VERIFY", "ROLLBACK"},
                    "VERIFY": {"DONE", "ROLLBACK"},
                    "ROLLBACK": set(),
                    "DONE": set(),
                }[str(prior[-1].get("phase"))]
                if phase not in allowed:
                    raise JournalError(f"INVALID_TRANSITION:{prior[-1].get('phase')}->{phase}")
            elif phase != "PREPARE":
                raise JournalError("TRANSACTION_MUST_START_PREPARE")
            row = {
                "schema_version": SCHEMA_VERSION,
                "version": VERSION,
                "txn_id": txn_id,
                "seq": seq,
                "action": action,
                "phase": phase,
                "time_utc": timestamp_utc or utcnow(),
                "idempotency_key_hash": sha256(idempotency_key) if idempotency_key else "",
                "result_hash": result_hash or "",
                "meta": clean_meta,
                "prev_hash": prev,
            }
            row["record_hash"] = sha256(stable_json(row))
            payload = stable_json(row) + "\n"
            # Append + fsync: a record is either absent or complete. Truncated tail is treated as invalid/tampered.
            with self.path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            return row

    def transactions(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for row in self._records():
            out.setdefault(str(row.get("txn_id") or ""), []).append(row)
        return {k: v for k, v in out.items() if k}

    def decision(self, txn_id: str) -> RecoveryDecision:
        tx = self.transactions().get(txn_id) or []
        if not tx:
            raise JournalError("TRANSACTION_NOT_FOUND")
        action = str(tx[-1].get("action") or "")
        phases = [str(x.get("phase") or "") for x in tx]
        last = phases[-1]
        if last == "DONE":
            return RecoveryDecision(txn_id, action, "NOOP", "ALREADY_DONE", True, True, True)
        if last == "ROLLBACK":
            return RecoveryDecision(txn_id, action, "NOOP", "ALREADY_ROLLED_BACK", "COMMIT" in phases, False, True)
        if last == "PREPARE":
            # A crash may have happened after the external side effect but before the COMMIT
            # record reached disk. Never blindly repeat the mutation. First compare the
            # external target with the PREPARE desired-result hash; only commit if absent.
            return RecoveryDecision(txn_id, action, "VERIFY_EXTERNAL_THEN_COMMIT", "PREPARED_COMMIT_STATUS_UNKNOWN", False, False, False)
        if last == "COMMIT":
            # Critical invariant: never repeat mutation/restart/reelection after committed evidence.
            return RecoveryDecision(txn_id, action, "VERIFY", "COMMIT_ALREADY_DURABLE", True, False, False)
        if last == "VERIFY":
            return RecoveryDecision(txn_id, action, "DONE", "VERIFY_ALREADY_DURABLE", True, True, False)
        raise JournalError("UNKNOWN_TRANSACTION_STATE")

    def resume_all(self) -> list[RecoveryDecision]:
        chain = self.validate_chain()
        if not chain["ok"]:
            raise JournalError("JOURNAL_CHAIN_INVALID")
        return [self.decision(txn) for txn in sorted(self.transactions())]


def new_txn_id(action: str, scope: str, nonce: str | None = None) -> str:
    seed = f"{VERSION}|{action}|{scope}|{nonce or uuid.uuid4().hex}"
    return "rtx-" + sha256(seed)[:24]


def simulate_crash_matrix() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    actions = list(ACTION_POLICIES)
    # Crash after durable phase; expected resume must never duplicate COMMIT.
    crash_after = ("PREPARE", "EFFECT_UNJOURNALED", "COMMIT", "VERIFY", "DONE")
    with tempfile.TemporaryDirectory(prefix="hms-v2560-journal-") as td:
        for action in actions:
            for stop in crash_after:
                path = Path(td) / f"{action}-{stop}.jsonl"
                j = RecoveryJournal(path)
                txn = new_txn_id(action, "synthetic", f"{action}:{stop}")
                j.append(txn, action, "PREPARE", idempotency_key=f"idem:{txn}", meta={"scope_hash": sha256("synthetic")})
                # EFFECT_UNJOURNALED models the dangerous crash window: side effect may
                # already exist but COMMIT record is absent. Journal state remains PREPARE.
                if stop in {"COMMIT", "VERIFY", "DONE"}:
                    j.append(txn, action, "COMMIT", idempotency_key=f"idem:{txn}", result_hash=sha256(f"effect:{txn}"))
                if stop in {"VERIFY", "DONE"}:
                    j.append(txn, action, "VERIFY", idempotency_key=f"idem:{txn}", result_hash=sha256(f"verified:{txn}"))
                if stop == "DONE":
                    j.append(txn, action, "DONE", idempotency_key=f"idem:{txn}")
                d = j.decision(txn)
                commit_count = sum(1 for x in j.transactions()[txn] if x["phase"] == "COMMIT")
                ok = commit_count <= 1 and d.next_step != "COMMIT"
                cases.append({"action": action, "crash_after": stop, "resume": d.next_step, "commit_count": commit_count, "ok": ok})
    return {"cases": cases, "pass": sum(1 for x in cases if x["ok"]), "total": len(cases)}


def synthetic_proof() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: Any = None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory(prefix="hms-v2560-proof-") as td:
        path = Path(td) / "journal.jsonl"
        j = RecoveryJournal(path)
        txn = new_txn_id("OFFICIAL_AUTH_SWITCH", "acct-hash", "proof")
        j.append(txn, "OFFICIAL_AUTH_SWITCH", "PREPARE", idempotency_key="switch-proof", meta={"target_hash": sha256("acct")})
        add("prepared_requires_external_verify", j.decision(txn).next_step == "VERIFY_EXTERNAL_THEN_COMMIT")
        j.append(txn, "OFFICIAL_AUTH_SWITCH", "COMMIT", idempotency_key="switch-proof", result_hash=sha256("auth-written"))
        d = j.decision(txn)
        add("committed_resumes_verify_never_commit", d.next_step == "VERIFY" and d.committed)
        j.append(txn, "OFFICIAL_AUTH_SWITCH", "VERIFY", idempotency_key="switch-proof", result_hash=sha256("readback"))
        add("verified_resumes_done", j.decision(txn).next_step == "DONE")
        j.append(txn, "OFFICIAL_AUTH_SWITCH", "DONE", idempotency_key="switch-proof")
        add("done_is_terminal_noop", j.decision(txn).next_step == "NOOP" and j.decision(txn).terminal)
        add("hash_chain_valid", j.validate_chain()["ok"], j.validate_chain())
        raw = path.read_text("utf-8")
        add("journal_contains_no_raw_scope", "acct-hash" not in raw and "switch-proof" not in raw)

        rollback_tx = new_txn_id("CONFIG_REPAIR", "config", "rollback")
        j.append(rollback_tx, "CONFIG_REPAIR", "PREPARE", idempotency_key="repair", meta={"backup_hash": sha256("backup")})
        j.append(rollback_tx, "CONFIG_REPAIR", "ROLLBACK", idempotency_key="repair", result_hash=sha256("restored"))
        add("rollback_terminal_noop", j.decision(rollback_tx).next_step == "NOOP")

        # Tamper must fail closed.
        tampered = Path(td) / "tampered.jsonl"
        tampered.write_text(raw.replace('"phase":"COMMIT"', '"phase":"PREPARE"', 1), "utf-8")
        add("tamper_detected", not RecoveryJournal(tampered).validate_chain()["ok"])

        # Secret-shaped metadata is redacted before durable write.
        sec = Path(td) / "secret.jsonl"
        sj = RecoveryJournal(sec)
        st = new_txn_id("ROUTER_RESTART", "router", "secret")
        sj.append(st, "ROUTER_RESTART", "PREPARE", meta={"access_token": "TOP_SECRET", "prompt": "hello", "safe": "ok"})
        sraw = sec.read_text("utf-8")
        add("secret_metadata_redacted", "TOP_SECRET" not in sraw and '"access_token":"<REDACTED>"' in sraw and '"prompt":"<REDACTED>"' in sraw)

    matrix = simulate_crash_matrix()
    add("crash_matrix_all_pass", matrix["pass"] == matrix["total"], matrix)
    add("crash_matrix_25_cases", matrix["total"] == 25, matrix["total"])
    add("all_actions_duplicate_commit_forbidden", all(v["duplicate_commit_forbidden"] for v in ACTION_POLICIES.values()))
    add("all_committed_resume_verify", all(v["resume_after_commit"] == "VERIFY" for v in ACTION_POLICIES.values()))
    add("production_never_claimed", PRODUCTION_CLAIM.endswith("SYNTHETIC_ONLY"))

    passed = sum(1 for x in checks if x["ok"])
    return {
        "product": "HMS-AI-ROUTER", "version": VERSION,
        "suite": "RECOVERY_TRANSACTION_JOURNAL_CRASH_CONSISTENCY_PROOF",
        "generated_utc": utcnow(),
        "verdict": "PASS" if passed == len(checks) else "FAIL",
        "summary": {"pass": passed, "fail": len(checks)-passed, "total": len(checks), "crash_cases": matrix["total"]},
        "checks": checks,
        "crash_matrix": matrix,
        "safety": {"production_certification": PRODUCTION_CLAIM, "raw_secret_storage": False, "duplicate_commit_allowed": False},
    }


def cli_append(args: argparse.Namespace) -> dict[str, Any]:
    j = RecoveryJournal(Path(args.journal))
    meta = json.loads(args.meta_json) if args.meta_json else {}
    row = j.append(args.txn_id, args.action, args.phase, meta=meta, idempotency_key=args.idempotency_key or "", result_hash=args.result_hash or "")
    return {"ok": True, "version": VERSION, "record": {k: v for k, v in row.items() if k != "meta"}, "chain": j.validate_chain()}


def cli_resume(args: argparse.Namespace) -> dict[str, Any]:
    j = RecoveryJournal(Path(args.journal))
    chain = j.validate_chain()
    decisions = [d.__dict__ for d in j.resume_all()] if chain["ok"] else []
    return {"ok": chain["ok"], "version": VERSION, "chain": chain, "decisions": decisions,
            "production_certification": PRODUCTION_CLAIM}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["proof", "append", "resume", "validate"], default="proof")
    ap.add_argument("--journal")
    ap.add_argument("--txn-id")
    ap.add_argument("--action", choices=sorted(ACTION_POLICIES))
    ap.add_argument("--phase", choices=PHASES)
    ap.add_argument("--idempotency-key")
    ap.add_argument("--result-hash")
    ap.add_argument("--meta-json")
    ap.add_argument("--output")
    a = ap.parse_args()
    if a.mode == "proof":
        data = synthetic_proof()
    elif a.mode == "append":
        if not all([a.journal, a.txn_id, a.action, a.phase]):
            raise SystemExit("--journal --txn-id --action --phase required")
        data = cli_append(a)
    elif a.mode == "resume":
        if not a.journal: raise SystemExit("--journal required")
        data = cli_resume(a)
    else:
        if not a.journal: raise SystemExit("--journal required")
        c = RecoveryJournal(Path(a.journal)).validate_chain()
        data = {"ok": c["ok"], "version": VERSION, "chain": c, "production_certification": PRODUCTION_CLAIM}
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(txt + "\n", "utf-8")
    print(txt)
    return 0 if data.get("verdict", "PASS") == "PASS" and data.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
