"""C-01..C-10: the journeys become executable tests."""

from __future__ import annotations

from munshi.adapters.fakes import MockLedger
from munshi.config import Settings
from munshi.db import Database
from munshi.domain import TxnState
from munshi.orchestrator import Orchestrator

from conftest import PARENT_NUMBER, start_parent_call


def test_c01_happy_path_bill_payment(orch: Orchestrator, db: Database, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    readback = orch.handle_turn(call_id, "bijli ka bill bharna hai")
    assert readback.decision == "AUTO_EXECUTE"
    assert "1,240 rupaye" in readback.reply

    done = orch.handle_turn(call_id, "haan")
    assert done.decision == "AUTO_EXECUTE"
    assert "Ho gaya" in done.reply

    txns = db.transactions("fam_devi")
    assert len(txns) == 1
    assert txns[0]["state"] == "SUCCEEDED"
    assert len(payments.charges) == 1
    child_notes = db.notifications("fam_devi", channel="child_simulator")
    assert len(child_notes) == 1
    assert "Ho gaya" in child_notes[0]["body"]


def test_c02_child_approval_round_trip_approve(orch: Orchestrator, db: Database, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "paani ka bill bharna hai")
    assert outcome.decision == "REQUIRE_CHILD_APPROVAL"
    approval = outcome.approval
    assert approval is not None

    result = orch.decide_approval(approval["id"], "approve", family_id="fam_devi")
    assert result["status"] == "approved"
    assert len(payments.charges) == 1
    assert db.transaction(outcome.txn["id"])["state"] == "SUCCEEDED"
    # The parent must not be left waiting after the child decides.
    assert db.call(call_id)["meta"]["awaiting"] is None
    callbacks = db.notifications("fam_devi", channel="call_callback")
    assert any("Manzoori ke baad" in n["body"] for n in callbacks)


def test_c02b_child_approval_round_trip_deny(orch: Orchestrator, db: Database, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "paani ka bill bharna hai")
    result = orch.decide_approval(outcome.approval["id"], "deny", family_id="fam_devi")
    assert result["status"] == "denied"
    assert payments.charges == []
    assert db.transaction(outcome.txn["id"])["state"] == "CANCELLED"
    assert db.call(call_id)["meta"]["awaiting"] is None


def test_c03_unsupported_transfer_creates_no_transaction(orch: Orchestrator, db: Database) -> None:
    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "ramu ko 5000 bhej de")
    assert outcome.decision == "REJECT"
    assert "kisi ko paise bhej nahi sakta" in outcome.reply
    assert db.transactions("fam_devi") == []
    notes = db.notifications("fam_devi", channel="child_simulator")
    assert any(n["kind"] == "unsupported_request" for n in notes)


def test_c04_two_clarifications_then_escalate(orch: Orchestrator, db: Database) -> None:
    call_id = start_parent_call(orch)
    assert orch.handle_turn(call_id, "uuuu").decision == "CLARIFY"
    assert orch.handle_turn(call_id, "aaaa").decision == "CLARIFY"
    third = orch.handle_turn(call_id, "hmmm kuch bhi")
    assert third.decision == "ESCALATE_TO_CHILD"
    assert "beta ko bata" in third.reply
    assert db.transactions("fam_devi") == []
    notes = db.notifications("fam_devi", channel="child_simulator")
    assert any(n["kind"] == "clarify_escalation" for n in notes)


def test_c05_silence_reprompts_then_closes(orch: Orchestrator, db: Database) -> None:
    call_id = start_parent_call(orch)
    first = orch.handle_turn(call_id, None, silence=True)
    assert first.decision == "CLARIFY"
    assert not first.done
    second = orch.handle_turn(call_id, None, silence=True)
    assert second.done is True
    assert db.call(call_id)["status"] == "ended"
    assert db.transactions("fam_devi") == []


def test_c06_barge_in_repeat_does_not_corrupt_state(orch: Orchestrator, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    orch.handle_turn(call_id, "bijli ka bill bharna hai")
    repeated = orch.handle_turn(call_id, "phir bolo", interrupt=True)
    assert repeated.decision == "CLARIFY"
    assert repeated.txn is not None and repeated.txn["state"] == "AWAITING_READBACK"
    final = orch.handle_turn(call_id, "haan")
    assert final.decision == "AUTO_EXECUTE"
    assert len(payments.charges) == 1


def test_c07_parent_cancels_at_readback(orch: Orchestrator, db: Database, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "bijli ka bill bharna hai")
    cancelled = orch.handle_turn(call_id, "ruko")
    assert "nahi kar raha" in cancelled.reply
    assert db.transaction(outcome.txn["id"])["state"] == "CANCELLED"
    assert payments.charges == []


def test_c08_dropped_call_is_recoverable_and_truthful(orch: Orchestrator, db: Database, payments: MockLedger) -> None:
    call_id = start_parent_call(orch)
    first = orch.handle_turn(call_id, "bijli ka bill bharna hai")
    orch.end_call(call_id, reason="dropped")
    assert payments.charges == []
    assert db.transaction(first.txn["id"])["state"] == "AWAITING_READBACK"

    resumed = orch.start_call(PARENT_NUMBER)
    assert "Pichhli baar ka kaam ruka tha" in resumed["greeting"]
    assert "1,240 rupaye" in resumed["greeting"]
    final = orch.handle_turn(resumed["call_id"], "haan")
    assert final.decision == "AUTO_EXECUTE"
    assert len(payments.charges) == 1


def test_c09_max_turn_cap_closes_politely(db, clock, payments) -> None:
    settings = Settings(max_turns_per_call=2)
    orchestrator = Orchestrator(db, clock=clock, payments=payments, settings=settings)
    call_id = start_parent_call(orchestrator)
    orchestrator.handle_turn(call_id, "hello")
    orchestrator.handle_turn(call_id, "hello again")
    third = orchestrator.handle_turn(call_id, "hello third")
    assert third.done is True
    assert db.call(call_id)["status"] == "ended"
    assert payments.charges == []


def test_c10_overlapping_calls_do_not_double_execute(orch: Orchestrator, payments: MockLedger) -> None:
    first = orch.start_call(PARENT_NUMBER)
    orch.handle_turn(first["call_id"], "bijli ka bill bharna hai")
    second = orch.start_call(PARENT_NUMBER)
    assert second["call_id"] == first["call_id"]
    orch.handle_turn(second["call_id"], "haan")
    orch.handle_turn(second["call_id"], "haan")
    assert len(payments.charges) == 1
