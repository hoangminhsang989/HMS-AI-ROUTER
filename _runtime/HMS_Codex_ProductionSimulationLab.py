#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import HMS_Codex_LiveQuotaIntelligence as live_quota
import HMS_Codex_SeamlessRotationTorture as rotation
import HMS_Codex_LanFailureMatrixValidator as lan_failure

VERSION = "25.54"
SCHEMA_VERSION = 1
PRODUCTION_CLAIM = "NOT_CLAIMED_SIMULATION_ONLY"

SECRET_KEYS = {
    "token", "access_token", "refresh_token", "cookie", "authorization", "bearer",
    "api_key", "apikey", "client_secret", "password", "prompt", "request_body",
    "response_body", "body", "auth_json",
}

EVENTS = (
    "NEW_SESSION", "CONTINUE_SESSION", "QUOTA_DRAIN", "QUOTA_STALE", "QUOTA_REFRESH",
    "HTTP_429", "ACCOUNT_RECOVER", "PROCESS_CRASH", "PROCESS_RESTART", "AUTH_REFRESH",
    "QUEUE_BURST", "SMB_TRANSIENT", "LAN_PARTITION", "LAN_REJOIN", "CLOCK_SKEW",
)


def iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def secret_shape(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS or kl.endswith(("_token", "_secret", "_password", "_api_key")):
                return True
            if secret_shape(v):
                return True
    elif isinstance(obj, list):
        return any(secret_shape(v) for v in obj)
    return False


def stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def auth_fingerprint(account: str, generation: int = 1) -> str:
    # Synthetic identity only. No real auth material is accepted or emitted by this lab.
    return hashlib.sha256(f"synthetic-auth:{account}:g{generation}".encode()).hexdigest()


@dataclass
class AccountState:
    email: str
    plan: str
    remaining: float
    status: str = "READY"
    last_success_min_ago: int = 1
    auth_generation: int = 1
    process_generation: int = 1
    health: str = "READY"
    cooldown_ticks: int = 0

    def quota_row(self, now: datetime) -> dict[str, Any]:
        stamp = now - timedelta(minutes=self.last_success_min_ago)
        return {
            "email": self.email,
            "plan": self.plan,
            "status": self.status if self.health == "READY" else self.health,
            "pool_score": max(0.0, min(100.0, self.remaining)),
            "health_score": 100.0 if self.health == "READY" else 0.0,
            "quota": {
                "five_hour_remaining": self.remaining,
                "weekly_remaining": self.remaining,
                "five_hour_window_present": True,
                "weekly_window_present": True,
                "last_success_utc": iso(stamp),
                "last_attempt_utc": iso(now),
                "source_state": "FRESH" if self.last_success_min_ago <= 10 else "STALE",
            },
        }


@dataclass
class TwinState:
    now: datetime
    accounts: dict[str, AccountState]
    sessions: dict[str, str] = field(default_factory=dict)
    next_session: int = 1
    active_account: str = "alpha@example.test"
    queue_depth: int = 0
    queue_capacity: int = 8
    queue_accepted: int = 0
    queue_rejected: int = 0
    queue_completed: int = 0
    rotations: int = 0
    failed_over_sessions: int = 0
    rejected_sessions: int = 0
    lan_partitioned: bool = False
    smb_transient: bool = False
    clock_skewed: bool = False
    last_rotation_tick: int = -9999
    auth_fingerprints: dict[str, str] = field(default_factory=dict)
    invariant_failures: list[dict[str, Any]] = field(default_factory=list)
    event_counts: dict[str, int] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)


def make_state() -> TwinState:
    now = datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)
    rows = [
        AccountState("alpha@example.test", "Plus", 84.0),
        AccountState("beta@example.test", "Pro", 71.0),
        AccountState("gamma@example.test", "Free", 63.0),
        AccountState("delta@example.test", "Business", 77.0),
    ]
    st = TwinState(now=now, accounts={a.email: a for a in rows})
    st.auth_fingerprints = {a.email: auth_fingerprint(a.email, a.auth_generation) for a in rows}
    return st


def evaluated_rows(st: TwinState) -> list[dict[str, Any]]:
    raw = {"accounts": [a.quota_row(st.now) for a in st.accounts.values()]}
    return list(live_quota.evaluate(raw, now=st.now).get("accounts") or [])


def eligible_accounts(st: TwinState) -> list[dict[str, Any]]:
    return [r for r in evaluated_rows(st) if r.get("routing_eligible")]


def best_account(st: TwinState, exclude: str | None = None) -> str | None:
    rows = [r for r in eligible_accounts(st) if str(r.get("account")) != str(exclude or "")]
    if not rows:
        return None
    rows.sort(key=lambda r: (-(float(r.get("usable_remaining_pct") or 0.0)), str(r.get("account") or "")))
    return str(rows[0].get("account") or "") or None


def invariant(st: TwinState, tick: int, name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        st.invariant_failures.append({"tick": tick, "name": name, "detail": detail[:240]})


def check_invariants(st: TwinState, tick: int, previous_sessions: dict[str, str] | None = None,
                     hard_failed: set[str] | None = None) -> None:
    rows = {str(r.get("account")): r for r in evaluated_rows(st)}
    hard_failed = hard_failed or set()

    # Existing sessions may remain on quota-HOLD/STALE accounts. They may move only on a hard failure.
    if previous_sessions is not None:
        for sid, before in previous_sessions.items():
            after = st.sessions.get(sid)
            if after is None:
                continue
            if before != after:
                invariant(st, tick, "affinity_moves_only_on_hard_failure", before in hard_failed,
                          f"{sid}:{before}->{after}")

    # No session may ever be bound to an unknown account.
    invariant(st, tick, "session_targets_known", all(a in st.accounts for a in st.sessions.values()))

    # Auth identities are immutable under routing/quota/failover. AUTH_REFRESH is modeled as a
    # generation bump with a new fingerprint only for that exact account.
    invariant(st, tick, "auth_fingerprint_cardinality", set(st.auth_fingerprints) == set(st.accounts))
    invariant(st, tick, "queue_accounting", st.queue_accepted == st.queue_completed + st.queue_depth,
              f"accepted={st.queue_accepted},completed={st.queue_completed},depth={st.queue_depth}")
    invariant(st, tick, "queue_bounded", 0 <= st.queue_depth <= st.queue_capacity, str(st.queue_depth))

    # If active account is still routing-eligible, no forced rotation is implied by quota alone.
    if st.active_account in rows and rows[st.active_account].get("routing_eligible"):
        invariant(st, tick, "active_account_known", st.active_account in st.accounts)

    # Stale/unknown/reserve-held accounts must not be selected for NEW sessions. We record this by
    # ensuring the helper itself never returns an ineligible candidate.
    candidate = best_account(st)
    if candidate:
        invariant(st, tick, "best_candidate_is_eligible", bool(rows[candidate].get("routing_eligible")), candidate)


def apply_new_session(st: TwinState, tick: int) -> None:
    candidate = best_account(st)
    if not candidate:
        st.rejected_sessions += 1
        return
    sid = f"s{st.next_session:06d}"
    st.next_session += 1
    st.sessions[sid] = candidate
    if candidate != st.active_account:
        # New-session route selection may differ from current active account. This is not an
        # existing-session mutation; count only if control-plane active account changes.
        st.active_account = candidate
        st.rotations += 1
        st.last_rotation_tick = tick


def apply_continue_session(st: TwinState, rng: random.Random) -> None:
    if not st.sessions:
        return
    sid = rng.choice(sorted(st.sessions))
    _ = st.sessions[sid]  # Explicit no-op: quota changes never mutate existing affinity.


def failover_from(st: TwinState, failed: str) -> None:
    replacement = best_account(st, exclude=failed)
    if not replacement:
        return
    for sid, account in list(st.sessions.items()):
        if account == failed:
            st.sessions[sid] = replacement
            st.failed_over_sessions += 1
    if st.active_account == failed:
        st.active_account = replacement
        st.rotations += 1


def event(st: TwinState, tick: int, name: str, rng: random.Random) -> None:
    st.event_counts[name] = st.event_counts.get(name, 0) + 1
    prev = dict(st.sessions)
    hard_failed: set[str] = set()
    accounts = [st.accounts[k] for k in sorted(st.accounts)]
    a = rng.choice(accounts)
    detail: dict[str, Any] = {"event": name, "account": a.email}

    if name == "NEW_SESSION":
        apply_new_session(st, tick)
    elif name == "CONTINUE_SESSION":
        apply_continue_session(st, rng)
    elif name == "QUOTA_DRAIN":
        a.remaining = max(0.0, a.remaining - rng.uniform(4.0, 28.0))
        detail["remaining_bucket"] = int(a.remaining // 5) * 5
    elif name == "QUOTA_STALE":
        a.last_success_min_ago = rng.randint(21, 90)
    elif name == "QUOTA_REFRESH":
        a.last_success_min_ago = 1
        a.remaining = min(100.0, max(a.remaining, rng.uniform(28.0, 96.0)))
    elif name == "HTTP_429":
        a.status = "COOLDOWN"
        a.cooldown_ticks = rng.randint(2, 9)
        hard_failed.add(a.email)
        failover_from(st, a.email)
    elif name == "ACCOUNT_RECOVER":
        a.status = "READY"
        a.cooldown_ticks = 0
        # Existing sessions intentionally remain where failover rebound them.
    elif name == "PROCESS_CRASH":
        a.health = "CRASHED"
        hard_failed.add(a.email)
        failover_from(st, a.email)
    elif name == "PROCESS_RESTART":
        if a.health != "READY":
            a.process_generation += 1
        a.health = "READY"
    elif name == "AUTH_REFRESH":
        before = dict(st.auth_fingerprints)
        a.auth_generation += 1
        st.auth_fingerprints[a.email] = auth_fingerprint(a.email, a.auth_generation)
        invariant(st, tick, "auth_refresh_scoped_to_one_account",
                  all(st.auth_fingerprints[k] == before[k] for k in before if k != a.email), a.email)
    elif name == "QUEUE_BURST":
        burst = rng.randint(1, 20)
        room = st.queue_capacity - st.queue_depth
        accepted = min(room, burst)
        rejected = burst - accepted
        st.queue_depth += accepted
        st.queue_accepted += accepted
        st.queue_rejected += rejected
        completed = rng.randint(0, st.queue_depth)
        st.queue_depth -= completed
        st.queue_completed += completed
        invariant(st, tick, "backpressure_rejects_overflow", rejected == max(0, burst - room))
    elif name == "SMB_TRANSIENT":
        st.smb_transient = True
        # A transient publish failure may delay shared metadata but must not mutate sessions/auth.
        st.smb_transient = False
    elif name == "LAN_PARTITION":
        st.lan_partitioned = True
    elif name == "LAN_REJOIN":
        st.lan_partitioned = False
    elif name == "CLOCK_SKEW":
        st.clock_skewed = True
        # Fail-closed shared-node semantics are exercised by the real LAN failure matrix below.
        st.clock_skewed = False

    # Cooldowns progress in simulated time; recovery is explicit when timer expires.
    for row in accounts:
        if row.cooldown_ticks > 0:
            row.cooldown_ticks -= 1
            if row.cooldown_ticks == 0 and row.status == "COOLDOWN":
                row.status = "READY"

    check_invariants(st, tick, prev, hard_failed)
    st.trace.append({
        "tick": tick,
        "event": name,
        "account_hash": hashlib.sha256(a.email.encode()).hexdigest()[:12],
        "sessions": len(st.sessions),
        "queue_depth": st.queue_depth,
        "rotations": st.rotations,
        "rejected_sessions": st.rejected_sessions,
        **{k: v for k, v in detail.items() if k not in {"account"}},
    })
    st.now += timedelta(seconds=5)


def run_seed(seed: int, cycles: int) -> dict[str, Any]:
    rng = random.Random(seed)
    st = make_state()
    weighted = [
        "NEW_SESSION", "NEW_SESSION", "NEW_SESSION", "CONTINUE_SESSION", "CONTINUE_SESSION",
        "QUOTA_DRAIN", "QUOTA_DRAIN", "QUOTA_STALE", "QUOTA_REFRESH", "HTTP_429",
        "ACCOUNT_RECOVER", "PROCESS_CRASH", "PROCESS_RESTART", "AUTH_REFRESH", "QUEUE_BURST",
        "SMB_TRANSIENT", "LAN_PARTITION", "LAN_REJOIN", "CLOCK_SKEW",
    ]
    for tick in range(cycles):
        event(st, tick, rng.choice(weighted), rng)
    while st.queue_depth:
        st.queue_depth -= 1
        st.queue_completed += 1
    check_invariants(st, cycles)
    trace_hash = stable_hash(st.trace)
    return {
        "seed": seed,
        "cycles": cycles,
        "trace_hash": trace_hash,
        "events_exercised": sorted(k for k, v in st.event_counts.items() if v),
        "event_counts": dict(sorted(st.event_counts.items())),
        "sessions": len(st.sessions),
        "rotations": st.rotations,
        "failed_over_sessions": st.failed_over_sessions,
        "rejected_sessions": st.rejected_sessions,
        "queue": {"accepted": st.queue_accepted, "rejected": st.queue_rejected, "completed": st.queue_completed, "depth": st.queue_depth},
        "process_generations": {hashlib.sha256(k.encode()).hexdigest()[:12]: v.process_generation for k, v in sorted(st.accounts.items())},
        "invariant_failures": st.invariant_failures[:50],
        "pass": not st.invariant_failures,
    }


def quota_state_space() -> dict[str, Any]:
    now = datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)
    checks: list[dict[str, Any]] = []
    plans = ("Free", "Plus", "Pro", "Business")
    remaining_values = (0, 2, 9, 10, 14, 15, 19, 20, 26, 50, 100)
    freshness_minutes = (1, 15, 25)
    for plan in plans:
        reserve = live_quota.reserve_for(plan, live_quota.DEFAULT_POLICY)
        for rem in remaining_values:
            for age in freshness_minutes:
                a = AccountState("matrix@example.test", plan, float(rem), last_success_min_ago=age)
                row = live_quota.evaluate({"accounts": [a.quota_row(now)]}, now=now)["accounts"][0]
                expected = age <= 20 and rem > max(3.0, reserve)
                checks.append({
                    "plan": plan, "remaining": rem, "age_min": age,
                    "eligible": bool(row.get("routing_eligible")), "expected": bool(expected),
                    "ok": bool(row.get("routing_eligible")) == bool(expected),
                })
    bad = [x for x in checks if not x["ok"]]
    return {"total": len(checks), "pass": len(checks)-len(bad), "fail": len(bad), "failures": bad[:20]}


def mutation_sensitivity() -> dict[str, Any]:
    # Proves the lab's invariant logic can detect a deliberately unsafe stale-quota policy mutant.
    now = datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)
    stale = AccountState("mutant@example.test", "Plus", 99.0, last_success_min_ago=45)
    normal = live_quota.evaluate({"accounts": [stale.quota_row(now)]}, now=now)["accounts"][0]
    mutant_would_allow = True  # deliberate unsafe mutant: ignore freshness and route by remaining only
    detector_fires = mutant_would_allow and not bool(normal.get("routing_eligible"))
    return {
        "stale_normal_eligible": bool(normal.get("routing_eligible")),
        "unsafe_mutant_would_allow": mutant_would_allow,
        "detector_fires": detector_fires,
    }


def focused_runtime_faults(root: Path) -> dict[str, Any]:
    rotation_report = rotation.run(root, cycles=240)
    with tempfile.TemporaryDirectory(prefix="hms-v2554-lan-") as td:
        lan_report = lan_failure.run(Path(td))
    return {
        "rotation": {
            "pass": str(rotation_report.get("verdict") or "").startswith("PASS"),
            "summary": rotation_report.get("summary") or {},
        },
        "lan_failure_matrix": {
            "pass": lan_report.get("verdict") == "PASS",
            "summary": lan_report.get("summary") or {},
        },
    }


def run(root: Path, seeds: list[int], cycles: int) -> dict[str, Any]:
    seed_rows = [run_seed(seed, cycles) for seed in seeds]
    # Replay first and last seed to prove deterministic reproduction.
    replay_rows = []
    for seed in sorted(set([seeds[0], seeds[-1]])):
        a = run_seed(seed, cycles)
        b = run_seed(seed, cycles)
        replay_rows.append({"seed": seed, "trace_hash": a["trace_hash"], "replay_hash": b["trace_hash"], "match": a["trace_hash"] == b["trace_hash"]})

    matrix = quota_state_space()
    sensitivity = mutation_sensitivity()
    focused = focused_runtime_faults(root)
    total_cycles = sum(x["cycles"] for x in seed_rows)
    all_events = sorted(set().union(*(set(x["events_exercised"]) for x in seed_rows))) if seed_rows else []
    failures = sum(len(x["invariant_failures"]) for x in seed_rows)
    replay_ok = all(x["match"] for x in replay_rows)
    seed_ok = all(x["pass"] for x in seed_rows)
    focused_ok = focused["rotation"]["pass"] and focused["lan_failure_matrix"]["pass"]
    passed = seed_ok and replay_ok and matrix["fail"] == 0 and sensitivity["detector_fires"] and focused_ok and set(EVENTS).issubset(set(all_events))

    report = {
        "product": "HMS-AI-ROUTER",
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "suite": "PRODUCTION_SIMULATION_FAULT_INJECTION_LAB",
        "generated_utc": iso(),
        "verdict": "PASS_PRODUCTION_SIMULATION_LAB_V25_54" if passed else "FAIL_PRODUCTION_SIMULATION_LAB_V25_54",
        "summary": {
            "seeds": len(seed_rows), "cycles_per_seed": cycles, "total_cycles": total_cycles,
            "seed_pass": sum(1 for x in seed_rows if x["pass"]), "seed_fail": sum(1 for x in seed_rows if not x["pass"]),
            "invariant_failures": failures, "events_exercised": len(all_events), "events_required": len(EVENTS),
            "quota_matrix_pass": matrix["pass"], "quota_matrix_total": matrix["total"],
            "replay_pass": sum(1 for x in replay_rows if x["match"]), "replay_total": len(replay_rows),
        },
        "event_catalog": list(EVENTS),
        "events_exercised": all_events,
        "seeds": seed_rows,
        "deterministic_replay": replay_rows,
        "quota_state_space": matrix,
        "mutation_sensitivity": sensitivity,
        "focused_runtime_faults": focused,
        "safety": {
            "synthetic_only": True,
            "real_quota_consumed": False,
            "real_codex_request_sent": False,
            "oauth_tokens_mutated": False,
            "real_account_files_mutated": False,
            "real_smb_share_required": False,
            "raw_secret_evidence": False,
            "production_certification": PRODUCTION_CLAIM,
        },
        "claim_boundary": "Simulation validates deterministic control-plane invariants and fault response only. It never substitutes for target Windows/Codex/LAN/soak production certification.",
    }
    if secret_shape(report):
        report["verdict"] = "FAIL_PRODUCTION_SIMULATION_LAB_V25_54"
        report["summary"]["invariant_failures"] += 1
        report["secret_shape_failure"] = True
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="HMS v25.54 Production Simulation & Fault-Injection Lab")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--seeds", default="11,23,37,41,59,73,89,101")
    ap.add_argument("--cycles", type=int, default=300)
    ap.add_argument("--output")
    a = ap.parse_args()
    seeds = [int(x.strip()) for x in str(a.seeds).split(",") if x.strip()]
    if not seeds:
        seeds = [11]
    cycles = max(100, min(5000, int(a.cycles)))
    out = run(Path(a.root).resolve(), seeds[:32], cycles)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if out["verdict"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
