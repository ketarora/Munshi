"""Measure in-process turn latency and demo reset time. No network, no accounts.

Usage: python scripts/measure_latency.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from munshi.adapters.fakes import MockLedger  # noqa: E402
from munshi.clock import FixedClock  # noqa: E402
from munshi.db import Database  # noqa: E402
from munshi.orchestrator import Orchestrator  # noqa: E402


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[index]


def main() -> None:
    clock = FixedClock()
    db = Database(clock=clock)
    db.seed_demo()
    db.update_limits(
        "fam_devi",
        per_txn_cap=10**9,
        daily_cap=10**9,
        monthly_cap=10**9,
        hard_ceiling=10**9,
    )
    orchestrator = Orchestrator(db, clock=clock, payments=MockLedger())

    turn_samples: list[float] = []
    turn_count = 50
    for _ in range(turn_count):
        call_id = orchestrator.start_call("9812345678")["call_id"]
        started = time.perf_counter()
        first = orchestrator.handle_turn(call_id, "dawai mangwa do")
        orchestrator.handle_turn(call_id, "haan")
        turn_samples.append((time.perf_counter() - started) * 1000)
        assert first.decision == "AUTO_EXECUTE"
        orchestrator.end_call(call_id)

    reset_samples = []
    for _ in range(3):
        started = time.perf_counter()
        db.reset()
        reset_samples.append((time.perf_counter() - started) * 1000)
        db.update_limits(
            "fam_devi",
            per_txn_cap=10**9,
            daily_cap=10**9,
            monthly_cap=10**9,
            hard_ceiling=10**9,
        )

    report = {
        "turns_measured": turn_count,
        "turn_two_turns_p50_ms": round(percentile(turn_samples, 50), 2),
        "turn_two_turns_p95_ms": round(percentile(turn_samples, 95), 2),
        "reset_p50_ms": round(percentile(reset_samples, 50), 2),
        "reset_max_ms": round(max(reset_samples), 2),
        "audit_ok": db.verify_audit().ok,
        "audit_entries": db.verify_audit().entries,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
