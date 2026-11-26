"""S-01..S-07: transitions, terminal states and approvals."""

from __future__ import annotations

import pytest

from munshi.db import Database
from munshi.domain import TxnState
from munshi.errors import ApprovalExpired, ApprovalNotFound
from munshi.orchestrator import Orchestrator
from munshi.statemachine import TRANSITIONS, TERMINAL, IllegalTransition, assert_transition

from conftest import OTHER_CHILD_TOKEN, start_parent_call


def _all_states() -> list[TxnState]:
    return list(TxnState)


def test_s01_every_legal_transition_succeeds_and_illegal_raises() -> None:
    for current, targets in TRANSITIONS.items():
        for target in targets:
            assert assert_transition(current, target) is target
    for current in _all_states():
        for target in _all_states():
            if target in TRANSITIONS.get(current, frozenset()):
                continue
            with pytest.raises(IllegalTransition):
                assert_transition(current, target)


def test_s02_terminal_states_are_immutable() -> None:
    for terminal in TERMINAL:
        for target in _all_states():
            with pytest.raises(IllegalTransition):
                assert_transition(terminal, target)


def _create_pending_approval(orch: Orchestrator, db: Database) -> dict:
    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "paani ka bill bharna hai")
    assert outcome.approval is not None
    return outcome.approval, outcome.txn


def test_s03_approval_timeout_expires_and_never_auto_approves(
    orch: Orchestrator, db: Database, clock, payments
) -> None:
    approval, txn = _create_pending_approval(orch, db)
    clock.advance(seconds=901)
    expired = orch.expire_approvals("fam_devi")
    assert expired == [approval["id"]]
    assert db.approval(approval["id"])["state"] == "EXPIRED"
    assert db.transaction(txn["id"])["state"] == "EXPIRED"
    assert payments.charges == []
    callbacks = db.notifications("fam_devi", channel="call_callback")
    assert any("jawab nahi aaya" in n["body"] for n in callbacks)


def test_s04_approving_after_expiry_is_rejected(
    orch: Orchestrator, db: Database, clock, payments
) -> None:
    approval, _ = _create_pending_approval(orch, db)
    clock.advance(seconds=901)
    with pytest.raises(ApprovalExpired):
        orch.decide_approval(approval["id"], "approve", family_id="fam_devi")
    assert payments.charges == []


def test_s05_child_denial_cancels(orch: Orchestrator, db: Database, payments) -> None:
    approval, txn = _create_pending_approval(orch, db)
    result = orch.decide_approval(approval["id"], "deny", family_id="fam_devi")
    assert result["status"] == "denied"
    assert db.transaction(txn["id"])["state"] == "CANCELLED"
    assert payments.charges == []
    callbacks = db.notifications("fam_devi", channel="call_callback")
    assert any("mana kar diya" in n["body"] for n in callbacks)


def test_s06_pause_cancels_all_non_terminal_transactions(
    orch: Orchestrator, db: Database, payments
) -> None:
    approval, txn = _create_pending_approval(orch, db)
    result = orch.set_paused("fam_devi", True)
    assert result["paused"] is True
    assert db.transaction(txn["id"])["state"] == "CANCELLED"
    assert db.approval(approval["id"])["state"] == "CANCELLED"
    assert payments.charges == []
    assert db.limits("fam_devi")["paused"] is True

    orch.set_paused("fam_devi", False)
    assert db.limits("fam_devi")["paused"] is False


def test_s07_approval_from_another_family_is_rejected(orch: Orchestrator, db: Database) -> None:
    approval, _ = _create_pending_approval(orch, db)
    with pytest.raises(ApprovalNotFound):
        orch.decide_approval(approval["id"], "approve", family_id="fam_sharma")


def test_s08_approve_executes_exactly_once(orch: Orchestrator, db: Database, payments) -> None:
    approval, txn = _create_pending_approval(orch, db)
    result = orch.decide_approval(approval["id"], "approve", family_id="fam_devi")
    assert result["status"] == "approved"
    assert db.transaction(txn["id"])["state"] == "SUCCEEDED"
    assert len(payments.charges) == 1
    with pytest.raises(Exception):
        orch.decide_approval(approval["id"], "approve", family_id="fam_devi")
    assert len(payments.charges) == 1
