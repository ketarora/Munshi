"""P-06b: monthly spend rolls over at 00:00 in the family's timezone."""

from __future__ import annotations

from datetime import datetime, timezone

from munshi.clock import iso
from munshi.db import Database
from munshi.domain import TxnState
from munshi.orchestrator import Orchestrator


def test_p06b_month_rollover_in_ist(db: Database, clock, payments) -> None:
    # 2026-11-30 23:59 IST == 18:29 UTC
    clock.current = datetime(2026, 11, 30, 18, 29, tzinfo=timezone.utc)
    orchestrator = Orchestrator(db, clock=clock, payments=payments)
    family = db.family("fam_devi")
    assert family is not None

    db.create_transaction(
        family_id="fam_devi",
        call_id=None,
        idempotency_key="rollover-nov",
        capability="pay_bill",
        resolved_action={
            "capability": "pay_bill",
            "description": "Bijli bill",
            "amount_paise": 124000,
            "payee": "bijli",
            "detail": {},
        },
        amount_paise=124000,
        state=TxnState.SUCCEEDED,
        mode="SIMULATED",
        reason="rollover test",
        created_at=iso(clock.now()),
    )

    today, month = orchestrator._spend(family)
    assert today == 124000
    assert month == 124000

    clock.advance(minutes=2)  # 2026-12-01 00:01 IST
    today, month = orchestrator._spend(family)
    assert month == 0
    assert today == 0
