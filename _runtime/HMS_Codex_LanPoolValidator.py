#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, tempfile
from pathlib import Path
import HMS_Codex_LanPool as lp


def run(root: Path):
    shared = root / "shared"
    a_state, b_state = root / "a-node.json", root / "b-node.json"
    key = lp.derive_pairing_key("PAIR-2026-SECURE")
    a = lp.ensure_node(a_state, "PC-A")
    b = lp.ensure_node(b_state, "PC-B")
    origin = "https://github.com/acme/HMS-QR.git"
    p_a = {"project_dir": r"C:\Work\HMS-QR", "git_origin": origin, "project_label": "HMS QR"}
    p_b = {"project_dir": r"D:\Repos\HMS-QR", "git_origin": "HTTPS://github.com/acme/HMS-QR", "project_label": "HMS QR"}
    fp_a = lp.project_fingerprint(p_a["project_dir"], p_a["git_origin"])
    fp_b = lp.project_fingerprint(p_b["project_dir"], p_b["git_origin"])
    lp.heartbeat(shared, key, a, {"health":"READY","capacity":4,"running_instances":1,"project_fingerprints":[fp_a["fingerprint"]],"account_hashes":["sha256:a"]}, 45)
    lp.heartbeat(shared, key, b, {"health":"READY","capacity":2,"running_instances":0,"project_fingerprints":[],"account_hashes":["sha256:b"]}, 45)
    first = lp.acquire_lease(shared, key, a, p_a, 45)
    blocked = lp.acquire_lease(shared, key, b, p_b, 45)
    rel_bad = lp.release_lease(shared, key, b, p_b)
    rel_ok = lp.release_lease(shared, key, a, p_a)
    takeover = lp.acquire_lease(shared, key, b, p_b, 45)
    st = lp.status(shared, key, b, [p_b])
    # Tamper with node A heartbeat; signature must fail closed.
    node_file = lp.node_file(shared, a["node_id"])
    obj = lp.read_json(node_file, {})
    obj["payload"]["capacity"] = 999
    lp.atomic_json(node_file, obj)
    tampered = lp.read_nodes(shared, key)
    bad_a = next(x for x in tampered if x.get("node_id") == a["node_id"])
    # Expired lease takeover increments epoch.
    lease_path = lp.lease_file(shared, takeover["fingerprint"])
    wrapper = lp.read_json(lease_path, {})
    now = lp.epoch_now()
    wrapper["payload"]["renewed_epoch"] = now - 60
    wrapper["payload"]["expires_epoch"] = now - 15
    wrapper["payload"]["acquired_epoch"] = min(int(wrapper["payload"].get("acquired_epoch") or now - 60), now - 60)
    wrapper["signature"] = lp.sign_payload(wrapper["payload"], key)
    lp.atomic_json(lease_path, wrapper)
    expired_takeover = lp.acquire_lease(shared, key, a, p_a, 45)
    checks = {
        "same_git_origin_same_cross_pc_fingerprint": fp_a["fingerprint"] == fp_b["fingerprint"] and fp_a["scope"] == "CROSS_PC",
        "first_node_acquires_lease": first["ok"] and first["status"] == "ACQUIRED",
        "second_node_blocked_while_lease_active": (not blocked["ok"]) and blocked["status"] == "BLOCKED_OWNED_BY_OTHER_NODE",
        "non_owner_cannot_release": (not rel_bad["ok"]) and rel_bad["status"] == "BLOCKED_NOT_OWNER",
        "owner_can_release": rel_ok["ok"] and rel_ok["status"] == "RELEASED",
        "other_node_can_acquire_after_release": takeover["ok"],
        "epoch_nonce_present": int(takeover["lease"]["epoch"]) >= 1 and len(takeover["lease"]["nonce"]) == 32,
        "signed_node_registry": st["summary"]["nodes"] == 2 and all(x.get("signature_ok") for x in st["nodes"]),
        "failover_candidate_visible": any(x.get("node_id") == a["node_id"] for x in st["failover_candidates"]),
        "tampered_heartbeat_rejected": bad_a.get("state") == "INVALID_SIGNATURE" and not bad_a.get("signature_ok"),
        "expired_lease_takeover_allowed": expired_takeover["ok"] and expired_takeover["status"] == "TAKEOVER_EXPIRED" and int(expired_takeover["lease"]["epoch"]) > int(takeover["lease"]["epoch"]),
        "shared_payload_has_no_secret_fields": not lp.secret_scan(st),
        "raw_credentials_not_shared_contract": st["security"]["credential_sharing"] is False and st["security"]["raw_token_sharing"] is False,
        "pairing_key_not_written_to_shared_registry": all("pair" not in json.dumps(lp.read_json(p, {})).lower() for p in shared.rglob("*.json")),
        "local_path_fallback_marked_non_cross_pc": lp.project_fingerprint(r"C:\x", "")["scope"] == "LOCAL_PATH_FALLBACK",
    }
    passed = sum(bool(v) for v in checks.values())
    return {"product":"HMS-AI-ROUTER","version":"25.47","tranche":"LAN_POOL_RELIABILITY_REGRESSION","verdict":"PASS" if passed == len(checks) else "FAIL","summary":{"pass":passed,"fail":len(checks)-passed,"total":len(checks)},"checks":checks,"runtime_windows_multi_pc":"DEFERRED_BY_OPERATOR","soak":"NOT_YET"}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--temp"); ap.add_argument("--output"); a=ap.parse_args()
    temp_created=not bool(a.temp); root=Path(a.temp) if a.temp else Path(tempfile.mkdtemp(prefix="hms-lanpool-v2546-"))
    try: out=run(root)
    finally:
        if temp_created: shutil.rmtree(root, ignore_errors=True)
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(txt+"\n",encoding="utf-8")
    print(txt); return 0 if out["verdict"]=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
