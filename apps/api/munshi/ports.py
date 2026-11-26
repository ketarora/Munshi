"""Ports (interfaces) for every external dependency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .domain import ExecutionResult, Mode, Proposal


class NotConfigured(RuntimeError):
    """A real adapter has no verified credentials/configuration in this environment."""


class BillNotFound(LookupError):
    """No unpaid bill for this family/biller."""


class PaymentError(RuntimeError):
    """The payment adapter could not complete the charge."""


@dataclass(frozen=True)
class Bill:
    biller: str
    account_no: str
    amount_paise: int
    due_date: str


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float
    language: str = "hi"


class UnderstandingPort(Protocol):
    name: str

    def understand(
        self, text: str, language: str = "auto", context: dict[str, Any] | None = None
    ) -> Proposal: ...


class PaymentsPort(Protocol):
    name: str
    mode: Mode

    def charge(
        self,
        *,
        family_id: str,
        capability: str,
        payee: str,
        amount_paise: int,
        idempotency_key: str,
        description: str,
    ) -> ExecutionResult: ...


class BillerPort(Protocol):
    name: str

    def fetch_due(self, family_id: str, biller: str) -> Bill: ...

    def mark_paid(self, family_id: str, biller: str) -> None: ...


class NotifierPort(Protocol):
    name: str

    def notify_child(
        self, *, family_id: str, kind: str, body: str, related_txn: str | None = None
    ) -> str: ...

    def notify_callback(self, *, family_id: str, kind: str, body: str, related_txn: str | None = None) -> str: ...


class ASRPort(Protocol):
    name: str

    def transcribe(self, audio_ref: str, language: str = "hi") -> Transcript: ...


class TTSPort(Protocol):
    name: str

    def speak(self, text: str, language: str = "hi") -> str: ...
