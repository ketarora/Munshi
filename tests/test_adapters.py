"""A-01..A-04: adapters behave and fail honestly."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from munshi.adapters.fakes import FakeBiller, FlakyNotifier, MockLedger, SimulatorNotifier
from munshi.adapters.understanding import SchemaGuardedUnderstanding
from munshi.nlu import RuleUnderstanding
from munshi.orchestrator import Orchestrator
from munshi.ports import BillNotFound

from conftest import auth, start_parent_call


class ExplodingUnderstanding:
    name = "exploding"

    def understand(self, text, language="auto", context=None):
        raise TimeoutError("model timeout")


def test_a01_fake_adapters_honour_their_contracts(db, clock, payments: MockLedger) -> None:
    guard = SchemaGuardedUnderstanding(RuleUnderstanding())
    for utterance in ("bijli ka bill bharna hai", "haan", "gas book kar do", "beta ko bata do"):
        assert guard.understand(utterance).intent in {
            "pay_bill", "affirm", "book_gas_cylinder", "message_child",
        }

    biller = FakeBiller(db)
    bill = biller.fetch_due("fam_devi", "bijli")
    assert bill.amount_paise == 124000
    biller.mark_paid("fam_devi", "bijli")
    with pytest.raises(BillNotFound):
        biller.fetch_due("fam_devi", "bijli")

    notifier = SimulatorNotifier(db)
    notification_id = notifier.notify_child(family_id="fam_devi", kind="test", body="hello")
    assert notification_id.startswith("ntf_")

    result = payments.charge(
        family_id="fam_devi", capability="pay_bill", payee="bijli", amount_paise=100,
        idempotency_key="a01", description="test",
    )
    assert result.ok and result.reference.startswith("MOCK-")


def test_a02_notifier_failure_does_not_break_the_payment(db, clock, payments: MockLedger) -> None:
    notifier = FlakyNotifier(db=db, fail=True)
    orchestrator = Orchestrator(db, clock=clock, payments=payments, notifier=notifier)
    call_id = start_parent_call(orchestrator)
    orchestrator.handle_turn(call_id, "bijli ka bill bharna hai")
    outcome = orchestrator.handle_turn(call_id, "haan")
    assert outcome.decision == "AUTO_EXECUTE"
    assert len(payments.charges) == 1
    events = [row["event"] for row in db.audit_rows()]
    assert "notify.degraded" in events


def test_a02b_understanding_failure_degrades_to_unclear(db, clock, payments: MockLedger) -> None:
    orchestrator = Orchestrator(db, clock=clock, payments=payments, understanding=ExplodingUnderstanding())
    call_id = start_parent_call(orchestrator)
    outcome = orchestrator.handle_turn(call_id, "bijli ka bill bharna hai")
    assert outcome.decision == "CLARIFY"
    assert outcome.trace["degraded"] is True
    assert payments.charges == []


def test_a02c_payment_failure_is_honest_and_single_attempt(db, clock, payments: MockLedger) -> None:
    payments.fail_next = 1
    orchestrator = Orchestrator(db, clock=clock, payments=payments)
    call_id = start_parent_call(orchestrator)
    orchestrator.handle_turn(call_id, "bijli ka bill bharna hai")
    outcome = orchestrator.handle_turn(call_id, "haan")
    assert outcome.txn is not None and outcome.txn["state"] == "FAILED"
    assert "Paise nahi kate" in outcome.reply
    assert payments.charges == []
    notes = db.notifications("fam_devi", channel="child_simulator")
    assert any(n["kind"] == "payment_failed" for n in notes)
    again = orchestrator.handle_turn(call_id, "haan")
    assert again.txn is None or again.txn["state"] == "FAILED"
    assert payments.charges == []


def test_a03_webhook_requires_a_valid_signature_and_is_replay_safe(client) -> None:
    body = json.dumps({"event_id": "evt_1", "event": "payment.settled", "txn_id": "txn_x"}).encode()
    assert client.post("/api/webhooks/payments", content=body).status_code == 401
    assert client.post(
        "/api/webhooks/payments", content=body, headers={"X-Munshi-Signature": "sha256=deadbeef"}
    ).status_code == 401

    signature = hmac.new(b"whsec_demo_munshi_sandbox", body, hashlib.sha256).hexdigest()
    headers = {"X-Munshi-Signature": f"sha256={signature}", "content-type": "application/json"}
    first = client.post("/api/webhooks/payments", content=body, headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "accepted"
    replay = client.post("/api/webhooks/payments", content=body, headers=headers)
    assert replay.json()["status"] == "duplicate"


def test_a04_provider_failure_after_readback_never_double_pays(db, clock, payments: MockLedger) -> None:
    orchestrator = Orchestrator(db, clock=clock, payments=payments)
    call_id = start_parent_call(orchestrator)
    orchestrator.handle_turn(call_id, "bijli ka bill bharna hai")
    payments.fail_next = 1
    outcome = orchestrator.handle_turn(call_id, "haan")
    assert outcome.txn["state"] == "FAILED"
    assert len(payments.charges) == 0
    orchestrator.handle_turn(call_id, "haan")
    assert len(payments.charges) == 0
