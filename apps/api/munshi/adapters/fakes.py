"""Deterministic fakes. The entire product runs end-to-end with zero accounts."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from ..db import Database
from ..domain import ExecutionResult, Mode
from ..ports import Bill, BillNotFound, PaymentError


@dataclass
class MockLedger:
    """In-memory payment ledger with idempotency and failure injection."""

    name: str = "mock-ledger"
    mode: Mode = Mode.SIMULATED
    fail_next: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _seen: dict[str, ExecutionResult] = field(default_factory=dict, repr=False)
    charges: list[dict] = field(default_factory=list, repr=False)

    def charge(
        self,
        *,
        family_id: str,
        capability: str,
        payee: str,
        amount_paise: int,
        idempotency_key: str,
        description: str,
    ) -> ExecutionResult:
        with self._lock:
            if idempotency_key in self._seen:
                return self._seen[idempotency_key]
            if self.fail_next > 0:
                self.fail_next -= 1
                raise PaymentError("mock ledger declined the charge")
            reference = f"MOCK-{uuid.uuid4().hex[:10].upper()}"
            result = ExecutionResult(
                ok=True,
                reference=reference,
                message=f"{description} charged in mock ledger",
                mode=self.mode,
                raw={"amount_paise": amount_paise, "payee": payee, "family_id": family_id},
            )
            self._seen[idempotency_key] = result
            self.charges.append(
                {
                    "idempotency_key": idempotency_key,
                    "family_id": family_id,
                    "capability": capability,
                    "payee": payee,
                    "amount_paise": amount_paise,
                    "reference": reference,
                }
            )
            return result


@dataclass
class FakeBiller:
    db: Database
    name: str = "fake-biller"

    def fetch_due(self, family_id: str, biller: str) -> Bill:
        row = self.db.bill(family_id, biller)
        if not row:
            raise BillNotFound(f"no unpaid {biller} bill for {family_id}")
        return Bill(
            biller=row["biller"],
            account_no=row["account_no"],
            amount_paise=row["amount_paise"],
            due_date=row["due_date"],
        )

    def mark_paid(self, family_id: str, biller: str) -> None:
        row = self.db.bill(family_id, biller)
        if row:
            self.db.mark_bill_paid(row["id"])


@dataclass
class SimulatorNotifier:
    """Writes the child's voice-note inbox and parent callbacks into SQLite."""

    db: Database
    name: str = "simulator"

    def notify_child(
        self, *, family_id: str, kind: str, body: str, related_txn: str | None = None
    ) -> str:
        from ..clock import iso

        row = self.db.add_notification(
            family_id,
            "child_simulator",
            kind,
            body,
            iso(self.db.clock.now()),
            related_txn=related_txn,
        )
        return row["id"]

    def notify_callback(self, *, family_id: str, kind: str, body: str, related_txn: str | None = None) -> str:
        from ..clock import iso

        row = self.db.add_notification(
            family_id,
            "call_callback",
            kind,
            body,
            iso(self.db.clock.now()),
            related_txn=related_txn,
        )
        return row["id"]


@dataclass
class FlakyNotifier(SimulatorNotifier):
    """Notifier that fails on demand, for graceful-degradation tests."""

    fail: bool = False

    def notify_child(self, **kwargs) -> str:
        if self.fail:
            raise ConnectionError("notifier offline")
        return super().notify_child(**kwargs)
