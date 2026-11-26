"""Pure domain types shared by the engine, adapters and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    REQUIRE_CHILD_APPROVAL = "REQUIRE_CHILD_APPROVAL"
    CLARIFY = "CLARIFY"
    ESCALATE_TO_CHILD = "ESCALATE_TO_CHILD"
    REJECT = "REJECT"
    NO_OP = "NO_OP"


class TxnState(str, Enum):
    PROPOSED = "PROPOSED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    AWAITING_READBACK = "AWAITING_READBACK"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Mode(str, Enum):
    LIVE = "LIVE"
    SANDBOX = "SANDBOX"
    SIMULATED = "SIMULATED"


class Role(str, Enum):
    PARENT = "parent"
    CHILD = "child"


@dataclass(frozen=True)
class Proposal:
    intent: str
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    language_detected: str = "hi"
    needs_clarification: bool = False
    clarification_question: str | None = None
    injection_suspected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "slots": self.slots,
            "confidence": round(self.confidence, 3),
            "language_detected": self.language_detected,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "injection_suspected": self.injection_suspected,
        }


@dataclass(frozen=True)
class ResolvedAction:
    capability: str
    description: str
    amount_paise: int | None = None
    payee: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    reference: str
    message: str
    mode: Mode = Mode.SIMULATED
    raw: dict[str, Any] = field(default_factory=dict)
