"""M-01..M-06: money handling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from munshi.adapters.fakes import MockLedger
from munshi.capabilities import default_registry
from munshi.db import Database
from munshi.money import (
    MoneyError,
    amount_words,
    format_indian,
    rupees_to_paise,
    speak_amount,
    validate_paise,
)
from munshi.orchestrator import Orchestrator

from conftest import start_parent_call


def test_m01_floats_and_bools_are_rejected() -> None:
    for bad in (1.0, 12.5, True):
        with pytest.raises(MoneyError):
            rupees_to_paise(bad)  # type: ignore[arg-type]
        with pytest.raises(MoneyError):
            validate_paise(bad)  # type: ignore[arg-type]
    assert rupees_to_paise(5000) == 500000


def test_m02_indian_grouping_and_readback() -> None:
    assert format_indian(1) == "1"
    assert format_indian(100) == "100"
    assert format_indian(1240) == "1,240"
    assert format_indian(5000) == "5,000"
    assert format_indian(50000) == "50,000"
    assert format_indian(100000) == "1,00,000"
    assert format_indian(12345678) == "1,23,45,678"

    assert speak_amount(100, "hi") == "1 rupaye"
    assert speak_amount(9900, "hi") == "99 rupaye"
    assert speak_amount(10000, "hi") == "100 rupaye"
    assert speak_amount(124000, "hi") == "1,240 rupaye"
    assert speak_amount(500000, "hi") == "5,000 rupaye"
    assert speak_amount(5000000, "hi") == "50,000 rupaye"
    assert speak_amount(10000000, "hi") == "1,00,000 rupaye"
    assert speak_amount(10000000, "en") == "1,00,000 rupees"

    assert amount_words(124000, "hi") == "ek hazaar do sau chalees rupaye"
    assert amount_words(10000000, "hi") == "ek lakh rupaye"
    assert amount_words(10000000, "en") == "one lakh rupees"


def test_m03_amount_change_between_readback_and_execute_voids_confirmation(
    db: Database, clock, orch: Orchestrator, payments: MockLedger
) -> None:
    call_id = start_parent_call(orch)
    first = orch.handle_turn(call_id, "bijli ka bill bharna hai")
    assert first.txn is not None and first.txn["state"] == "AWAITING_READBACK"
    assert first.txn["amount_paise"] == 124000

    db.conn.execute("UPDATE bills SET amount_paise = 140000 WHERE biller = 'bijli'")
    db.conn.commit()

    outcome = orch.handle_turn(call_id, "haan")
    assert payments.charges == []
    old = db.transaction(first.txn["id"])
    assert old is not None and old["state"] == "CANCELLED"
    assert outcome.txn is not None
    assert outcome.txn["state"] == "AWAITING_READBACK"
    assert outcome.txn["amount_paise"] == 140000
    assert "1,400" in outcome.reply


def test_m04_amount_never_comes_from_speech(db: Database, orch: Orchestrator, payments: MockLedger) -> None:
    registry = default_registry()
    for name in ("pay_bill", "book_gas_cylinder", "refill_medicine"):
        properties = registry.get(name).slots_schema.get("properties", {})
        assert "amount" not in properties

    call_id = start_parent_call(orch)
    outcome = orch.handle_turn(call_id, "bijli ka bill 50000 rupaye bharna hai")
    assert outcome.txn is not None
    assert outcome.txn["amount_paise"] == 124000  # biller's due amount, not 50,000
    assert payments.charges == []


def test_m05_idempotent_execution(payments: MockLedger) -> None:
    kwargs = dict(
        family_id="fam_devi", capability="pay_bill", payee="bijli",
        amount_paise=124000, idempotency_key="fixed-key", description="Bijli bill",
    )
    first = payments.charge(**kwargs)
    second = payments.charge(**kwargs)
    assert first.reference == second.reference
    assert len(payments.charges) == 1


def test_m06_concurrent_duplicates_charge_once(payments: MockLedger) -> None:
    kwargs = dict(
        family_id="fam_devi", capability="pay_bill", payee="bijli",
        amount_paise=124000, idempotency_key="race-key", description="Bijli bill",
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: payments.charge(**kwargs), range(16)))
    assert len({r.reference for r in results}) == 1
    assert len(payments.charges) == 1
