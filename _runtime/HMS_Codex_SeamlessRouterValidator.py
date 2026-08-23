#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

SECRET_KEYS = {"api_key","apikey","token","access_token","refresh_token","cookie","authorization","bearer","client_secret"}


def _norm_email(v: object) -> str:
    return str(v or "").strip().lower()


def _contains_secret(obj: object, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{path}.{k}" if path else str(k)
            kl = str(k).lower()
            if kl in SECRET_KEYS or any(x in kl for x in ("access_token","refresh_token","client_secret")):
                hits.append(kp)
            hits.extend(_contains_secret(v, kp))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_contains_secret(v, f"{path}[{i}]"))
    return hits


def validate(manifest: dict, instance: dict, affinity: dict, known_accounts: list[str], config_text: str = "") -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    known = {_norm_email(x) for x in known_accounts}
    iid = str(instance.get("id") or "")
    port = int(instance.get("port") or 0)
    primary = _norm_email(instance.get("accountEmail") or instance.get("account_email"))
    endpoint = f"http://127.0.0.1:{port}/v1"

    if str(manifest.get("version")) not in ("25.30", "25.31"):
        errors.append("manifest version must be 25.30 or 25.31")
    if str(manifest.get("instance_id") or "") != iid:
        errors.append("instance_id mismatch")
    if str(manifest.get("stable_endpoint") or "") != endpoint:
        errors.append("stable endpoint mismatch")
    if manifest.get("secret_fields_excluded") is not True:
        errors.append("secret_fields_excluded must be true")
    secret_hits = _contains_secret(manifest)
    if secret_hits:
        errors.append("secret-like fields present: " + ", ".join(secret_hits))

    accounts = manifest.get("accounts") or []
    if not accounts:
        errors.append("router pool empty")
    else:
        first = _norm_email(accounts[0].get("email"))
        if first != primary:
            errors.append("primary must be slot 0")
        if str(accounts[0].get("role") or "").upper() != "PRIMARY":
            errors.append("slot 0 role must be PRIMARY")

    seen: set[str] = set()
    for idx, row in enumerate(accounts):
        email = _norm_email(row.get("email"))
        if not email:
            errors.append(f"account[{idx}] email missing")
            continue
        if email in seen:
            errors.append(f"duplicate pool account: {email}")
        seen.add(email)
        if known and email not in known:
            warnings.append(f"account not in current pool: {email}")
        if int(row.get("slot", -1)) != idx:
            errors.append(f"slot mismatch at index {idx}")
        role = str(row.get("role") or "").upper()
        if idx > 0 and role != "FALLBACK":
            errors.append(f"account[{idx}] must be FALLBACK")
        sha = str(row.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            errors.append(f"account[{idx}] sha256 invalid")
        if not str(row.get("file") or "").lower().startswith("codex-"):
            warnings.append(f"account[{idx}] filename is not codex-* pattern")

    aff_primary = _norm_email(affinity.get("preferredAccount") or affinity.get("preferred_account"))
    if aff_primary and aff_primary != primary:
        errors.append("affinity primary differs from isolated instance primary")
    fallbacks = [_norm_email(x) for x in (affinity.get("fallbackAccounts") or affinity.get("fallback_accounts") or []) if _norm_email(x)]
    expected = [primary] + [x for x in fallbacks if x != primary]
    actual = [_norm_email(x.get("email")) for x in accounts]
    if actual != expected[: len(actual)]:
        errors.append("manifest account ordering does not follow primary + affinity fallbacks")

    if config_text:
        if f'port: {port}' not in config_text:
            errors.append("config port mismatch")
        if 'session-affinity: true' not in config_text.lower():
            warnings.append("session affinity not enabled in config")
        m = re.search(r"max-retry-credentials:\s*(\d+)", config_text)
        if not m:
            errors.append("max-retry-credentials missing")
        elif int(m.group(1)) > max(0, len(accounts) - 1):
            errors.append("max-retry-credentials exceeds fallback count")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "instance_id": iid,
        "stable_endpoint": endpoint,
        "pool_count": len(accounts),
        "primary": primary,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--affinity", required=True)
    ap.add_argument("--accounts", required=True)
    ap.add_argument("--config")
    ap.add_argument("--output")
    a = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text("utf-8-sig"))
    config_text = Path(a.config).read_text("utf-8-sig") if a.config else ""
    out = validate(load(a.manifest), load(a.instance), load(a.affinity), load(a.accounts), config_text)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
