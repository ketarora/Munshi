"""Message the child. No money moves."""

from __future__ import annotations

from typing import Any

from ..domain import ExecutionResult, Mode, ResolvedAction
from .base import CapabilityContext


class MessageChild:
    name = "message_child"
    requires_money = False
    supported_languages = ("hi", "hinglish", "en")
    slots_schema = {
        "type": "object",
        "required": ["message"],
        "properties": {"message": {"type": "string", "minLength": 1, "maxLength": 500}},
        "additionalProperties": False,
    }
    mode = Mode.SIMULATED

    def resolve(self, slots: dict[str, Any], ctx: CapabilityContext) -> ResolvedAction:
        message = str(slots.get("message") or "").strip()
        return ResolvedAction(
            capability=self.name,
            description="Message to child",
            amount_paise=None,
            payee=None,
            detail={"message": message, "slots": {"message": message}},
        )

    def execute(
        self, resolved: ResolvedAction, *, ctx: CapabilityContext, idempotency_key: str
    ) -> ExecutionResult:
        message = str(resolved.detail.get("message") or "").strip()
        try:
            ctx.notifier.notify_child(
                family_id=ctx.family_id,
                kind="message",
                body=message,
                related_txn=None,
            )
            ok = True
            message_out = "Child notified."
        except Exception as exc:  # adapters may degrade; the call must not hang
            ok = False
            message_out = f"Notifier unavailable: {type(exc).__name__}"
        return ExecutionResult(
            ok=ok,
            reference=f"MSG-{idempotency_key[:8]}",
            message=message_out,
            mode=Mode.SIMULATED,
        )

    def describe_for_speech(self, resolved: ResolvedAction, lang: str = "hi") -> str:
        return "Beta ko bata doon?"
