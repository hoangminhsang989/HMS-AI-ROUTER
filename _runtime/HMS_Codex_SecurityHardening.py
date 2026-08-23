#!/usr/bin/env python3
"""HMS-AI-ROUTER v25.40 - Codex Security Hardening auditor/planner.

Metadata-only by design. The engine never receives or serializes secret values. It audits
secret-at-rest posture, ACL posture, reparse-point boundaries, integrity seals, update-key
presence and redaction policy. Actual Windows DPAPI/Credential Manager and ACL mutations are
performed by the PowerShell authority after this engine emits an AUTO_SAFE plan.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "25.40"
SECRET_RX = re.compile(r"(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|client[_-]?secret|password|cookie|authorization|bearer|secret_value|plaintext_secret)")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("SNAPSHOT_NOT_OBJECT")
    return obj


def scan_secret_keys(obj: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            lk = str(k).lower()
            # Explicit metadata flags may reference secret *presence* without carrying the value.
            allowed = lk.endswith(("_present", "_stored", "_excluded", "_match", "_count", "_refs", "_ref"))
            if SECRET_RX.search(str(k)) and not allowed:
                hits.append(p)
            hits.extend(scan_secret_keys(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(scan_secret_keys(v, f"{prefix}[{i}]"))
    return hits


def issue(code: str, severity: str, detail: str, action: str | None = None, auto_safe: bool = False) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "detail": detail,
        "action": action,
        "auto_safe": bool(auto_safe),
    }


def audit(snapshot: dict[str, Any]) -> dict[str, Any]:
    secret_hits = scan_secret_keys(snapshot)
    if secret_hits:
        raise ValueError("SECURITY_SNAPSHOT_CONTAINS_SECRET_FIELDS: " + ", ".join(secret_hits[:12]))

    issues: list[dict[str, Any]] = []
    vault = snapshot.get("vault") or {}
    acl = snapshot.get("acl") or {}
    reparse = snapshot.get("reparse") or {}
    seals = snapshot.get("seals") or {}
    redaction = snapshot.get("redaction") or {}
    update = snapshot.get("update") or {}

    if vault.get("settings_plain_local_key_present"):
        issues.append(issue(
            "PLAINTEXT_GLOBAL_LOCAL_KEY", "HIGH",
            "Local HMS Router key còn nằm trong settings JSON.",
            "MIGRATE_GLOBAL_SECRET", True,
        ))
    if int(vault.get("instance_plain_keys_count") or 0) > 0:
        issues.append(issue(
            "PLAINTEXT_INSTANCE_KEYS", "HIGH",
            f"Có {int(vault.get('instance_plain_keys_count') or 0)} instance còn lưu API key trực tiếp trong instance store.",
            "MIGRATE_INSTANCE_SECRETS", True,
        ))
    if not vault.get("global_secret_ref_present"):
        issues.append(issue(
            "GLOBAL_SECRET_REF_MISSING", "HIGH",
            "Credential Manager/DPAPI reference cho Router global chưa tồn tại.",
            "MIGRATE_GLOBAL_SECRET", True,
        ))
    if int(vault.get("instance_secret_refs_missing") or 0) > 0:
        issues.append(issue(
            "INSTANCE_SECRET_REFS_MISSING", "HIGH",
            "Một hoặc nhiều instance chưa có protected secret reference.",
            "MIGRATE_INSTANCE_SECRETS", True,
        ))

    if not acl.get("security_dir_hardened"):
        issues.append(issue("SECURITY_DIR_ACL_WEAK", "MEDIUM", "ACL thư mục security chưa ở current-user + SYSTEM only.", "HARDEN_SECURITY_ACL", True))
    weak_sensitive = int(acl.get("sensitive_files_weak") or 0)
    if weak_sensitive:
        issues.append(issue("SENSITIVE_FILE_ACL_WEAK", "MEDIUM", f"Có {weak_sensitive} file state nhạy cảm có ACL rộng.", "HARDEN_SENSITIVE_ACL", True))
    weak_instance = int(acl.get("instance_paths_weak") or 0)
    if weak_instance:
        issues.append(issue("INSTANCE_ACL_WEAK", "MEDIUM", f"Có {weak_instance} instance path chưa được ACL harden.", "HARDEN_INSTANCE_ACL", True))

    weak_runtime = int(acl.get("runtime_materializations_weak") or 0)
    if weak_runtime:
        issues.append(issue(
            "RUNTIME_KEY_MATERIALIZATION_ACL_WEAK", "HIGH",
            f"Có {weak_runtime} runtime Router/API config chứa key materialization nhưng ACL còn rộng.",
            "HARDEN_SENSITIVE_ACL", True,
        ))

    detected = list(reparse.get("detected") or [])
    if detected:
        issues.append(issue(
            "REPARSE_POINT_IN_SECURITY_BOUNDARY", "CRITICAL",
            "Phát hiện symlink/junction/reparse point trong boundary nhạy cảm; không auto-repair để tránh phá dữ liệu.",
            None, False,
        ))

    if not seals.get("key_protected"):
        issues.append(issue("INTEGRITY_SEAL_KEY_MISSING", "MEDIUM", "Integrity HMAC key chưa có protected storage.", "CREATE_SEAL_KEY", True))
    if int(seals.get("tracked") or 0) == 0 or int(seals.get("missing") or 0) > 0:
        issues.append(issue("INTEGRITY_SEALS_INCOMPLETE", "MEDIUM", "Integrity seal baseline chưa đầy đủ.", "CREATE_MISSING_SEALS", True))
    mismatches = list(seals.get("mismatches") or [])
    if mismatches:
        issues.append(issue(
            "INTEGRITY_SEAL_MISMATCH", "CRITICAL",
            "Hash/HMAC của file đã seal không còn khớp. Không tự reseal một mismatch vì có thể chấp nhận tampering.",
            None, False,
        ))

    if not redaction.get("strict"):
        issues.append(issue("STRICT_REDACTION_DISABLED", "HIGH", "Unified strict redaction đang OFF.", "ENABLE_STRICT_REDACTION", True))
    if int(redaction.get("unsafe_artifacts") or 0) > 0:
        issues.append(issue("UNSAFE_DIAGNOSTIC_ARTIFACT", "HIGH", "Phát hiện artifact chẩn đoán có dấu hiệu secret chưa redact.", None, False))

    if not update.get("public_key_present"):
        issues.append(issue("UPDATE_PUBLIC_KEY_MISSING", "HIGH", "Public key xác minh signed update bị thiếu.", None, False))

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "auto_safe": 0, "operator": 0}
    for x in issues:
        sev = str(x["severity"]).lower()
        counts[sev] = counts.get(sev, 0) + 1
        counts["auto_safe" if x.get("auto_safe") else "operator"] += 1
    verdict = "PASS" if not issues else ("BLOCKED" if counts["critical"] else "HARDENING_REQUIRED")
    return {
        "version": VERSION,
        "generated_utc": now_utc(),
        "verdict": verdict,
        "summary": {"issues": len(issues), **counts},
        "issues": issues,
        "invariants": {
            "no_secret_values_in_snapshot": True,
            "canonical_secret_source_protected": True,
            "runtime_key_materialization_requires_hardened_acl": True,
            "sensitive_rollback_backups_dpapi": True,
            "no_auto_reseal_on_mismatch": True,
            "no_auto_delete": True,
            "no_auto_reparse_repair": True,
            "current_user_isolation": True,
        },
    }


def plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    a = audit(snapshot)
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    order = [
        "MIGRATE_GLOBAL_SECRET", "MIGRATE_INSTANCE_SECRETS", "CREATE_SEAL_KEY",
        "HARDEN_SECURITY_ACL", "HARDEN_SENSITIVE_ACL", "HARDEN_INSTANCE_ACL",
        "ENABLE_STRICT_REDACTION", "CREATE_MISSING_SEALS",
    ]
    found = {str(x.get("action")): x for x in a["issues"] if x.get("action") and x.get("auto_safe")}
    for act in order:
        x = found.get(act)
        if not x or act in seen:
            continue
        seen.add(act)
        actions.append({"action": act, "reason": x["code"], "auto_safe": True})
    return {
        "version": VERSION,
        "generated_utc": now_utc(),
        "audit": a,
        "actions": actions,
        "action_count": len(actions),
        "requires_operator": a["summary"]["operator"] > 0,
    }


def synthetic() -> dict[str, Any]:
    base = {
        "vault": {
            "settings_plain_local_key_present": False,
            "instance_plain_keys_count": 0,
            "global_secret_ref_present": True,
            "instance_secret_refs_missing": 0,
        },
        "acl": {"security_dir_hardened": True, "sensitive_files_weak": 0, "instance_paths_weak": 0, "runtime_materializations_weak": 0},
        "reparse": {"detected": []},
        "seals": {"key_protected": True, "tracked": 8, "missing": 0, "mismatches": []},
        "redaction": {"strict": True, "unsafe_artifacts": 0},
        "update": {"public_key_present": True},
    }
    checks: list[tuple[str, bool]] = []
    checks.append(("clean_snapshot_passes", audit(base)["verdict"] == "PASS"))

    plain = json.loads(json.dumps(base)); plain["vault"]["settings_plain_local_key_present"] = True
    p = plan(plain)
    checks.append(("global_secret_migration_planned", any(x["action"] == "MIGRATE_GLOBAL_SECRET" for x in p["actions"])))

    inst = json.loads(json.dumps(base)); inst["vault"].update({"instance_plain_keys_count": 2, "instance_secret_refs_missing": 2})
    p = plan(inst)
    checks.append(("instance_secret_migration_planned", any(x["action"] == "MIGRATE_INSTANCE_SECRETS" for x in p["actions"])))

    rep = json.loads(json.dumps(base)); rep["reparse"]["detected"] = ["instance/A/router"]
    a = audit(rep)
    checks.append(("reparse_is_fail_closed", a["verdict"] == "BLOCKED" and a["summary"]["operator"] > 0))

    mismatch = json.loads(json.dumps(base)); mismatch["seals"]["mismatches"] = ["config.toml"]
    p = plan(mismatch)
    checks.append(("seal_mismatch_never_auto_resealed", p["audit"]["verdict"] == "BLOCKED" and not any(x["action"] == "CREATE_MISSING_SEALS" for x in p["actions"])))

    weak = json.loads(json.dumps(base)); weak["acl"].update({"security_dir_hardened": False, "instance_paths_weak": 3})
    p = plan(weak)
    acts = {x["action"] for x in p["actions"]}
    checks.append(("acl_hardening_planned", {"HARDEN_SECURITY_ACL", "HARDEN_INSTANCE_ACL"}.issubset(acts)))

    runtime_acl = json.loads(json.dumps(base)); runtime_acl["acl"]["runtime_materializations_weak"] = 2
    p = plan(runtime_acl)
    checks.append(("runtime_materialization_acl_hardening_planned", any(x["action"] == "HARDEN_SENSITIVE_ACL" for x in p["actions"])))

    red = json.loads(json.dumps(base)); red["redaction"]["strict"] = False
    checks.append(("strict_redaction_planned", any(x["action"] == "ENABLE_STRICT_REDACTION" for x in plan(red)["actions"])))

    secret = json.loads(json.dumps(base)); secret["vault"]["api_key"] = "MUST_NOT_APPEAR"
    rejected = False
    try:
        audit(secret)
    except ValueError:
        rejected = True
    checks.append(("secret_values_rejected_from_snapshot", rejected))

    return {
        "version": VERSION,
        "checks": [{"name": n, "ok": ok} for n, ok in checks],
        "pass": sum(1 for _, ok in checks if ok),
        "total": len(checks),
        "verdict": "PASS" if all(ok for _, ok in checks) else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("audit", "plan", "synthetic"), default="audit")
    ap.add_argument("--snapshot")
    ap.add_argument("--output")
    args = ap.parse_args()
    try:
        if args.mode == "synthetic":
            data = synthetic()
        else:
            if not args.snapshot:
                raise ValueError("--snapshot required")
            snap = load_json(args.snapshot)
            data = audit(snap) if args.mode == "audit" else plan(snap)
        out = {"ok": data.get("verdict") != "FAIL", "mode": args.mode, "data": data}
    except Exception as e:
        out = {"ok": False, "mode": args.mode, "error": repr(e)}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
