"""R-01..R-05: latency, soak, chaos, reset, fresh-clone readiness."""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from munshi.adapters.fakes import MockLedger
from munshi.db import Database
from munshi.orchestrator import Orchestrator

from conftest import PARENT_NUMBER, start_parent_call

ROOT = Path(__file__).resolve().parents[1]


def test_r01_pipeline_latency_is_recorded(orch: Orchestrator, db, payments: MockLedger) -> None:
    stage_samples: list[float] = []
    for _ in range(3):
        call_id = start_parent_call(orch)
        first = orch.handle_turn(call_id, "dawai mangwa do")
        assert first.trace["stages"], "every turn must record stage latencies"
        stage_samples.extend(stage["ms"] for stage in first.trace["stages"])
        second = orch.handle_turn(call_id, "haan")
        assert second.decision == "AUTO_EXECUTE"
        orch.end_call(call_id)
    assert all(value >= 0 for value in stage_samples)
    ordered = sorted(stage_samples)
    p50 = statistics.median(ordered)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    assert p50 < 2500 and p95 < 2500


def test_r02_soak_two_hundred_calls(db: Database, clock, payments: MockLedger) -> None:
    orchestrator = Orchestrator(db, clock=clock, payments=payments)
    for _ in range(200):
        call_id = start_parent_call(orchestrator)
        outcome = orchestrator.handle_turn(call_id, "beta ko bata do sab theek hai")
        assert outcome.decision == "AUTO_EXECUTE"
        orchestrator.end_call(call_id)
    assert db.verify_audit().ok is True
    assert db.transactions("fam_devi", limit=10) == []
    assert len(db.notifications("fam_devi", limit=300)) == 200


def test_r03_chaos_payment_adapter_failure_then_recovery(db: Database, clock, payments: MockLedger) -> None:
    orchestrator = Orchestrator(db, clock=clock, payments=payments)
    call_id = start_parent_call(orchestrator)
    orchestrator.handle_turn(call_id, "bijli ka bill bharna hai")
    payments.fail_next = 1
    failed = orchestrator.handle_turn(call_id, "haan")
    assert failed.txn["state"] == "FAILED"
    assert db.verify_audit().ok is True
    orchestrator.end_call(call_id)

    recovered = orchestrator.start_call(PARENT_NUMBER)
    orchestrator.handle_turn(recovered["call_id"], "bijli ka bill bharna hai")
    done = orchestrator.handle_turn(recovered["call_id"], "haan")
    assert done.decision == "AUTO_EXECUTE"
    assert len(payments.charges) == 1
    assert db.verify_audit().ok is True


def test_r04_reset_demo_is_fast_and_idempotent(db: Database) -> None:
    db.audit("test", "noise.before_reset", {})
    started = time.perf_counter()
    db.reset()
    first = time.perf_counter() - started
    started = time.perf_counter()
    db.reset()
    second = time.perf_counter() - started
    assert first < 5 and second < 5
    assert db.limits("fam_devi")["monthly_cap"] == 500000
    assert db.bill("fam_devi", "bijli")["amount_paise"] == 124000
    assert db.verify_audit().ok is True


def test_r05_repo_has_a_fresh_clone_path() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker compose up" in readme or "make dev" in readme
    assert (ROOT / "Makefile").exists()
    assert (ROOT / "docker-compose.yml").exists()
    assert (ROOT / "docs" / "LIMITATIONS.md").exists()
    assert (ROOT / "docs" / "DESIGN_RATIONALE.md").exists()
