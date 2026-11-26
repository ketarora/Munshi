"""Medicine refill (SIMULATED). Reorders an existing family item only; no advice."""

from __future__ import annotations

from typing import Any

from ..domain import ExecutionResult, Mode, ResolvedAction
from ..money import speak_amount
from ..rupeepay import MEDICINE_PRICES_PAISE
from .base import CapabilityContext


class RefillMedicine:
    name = "refill_medicine"
    requires_money = True
    supported_languages = ("hi", "hinglish", "en")
    slots_schema = {
        "type": "object",
        "properties": {"item": {"type": "string"}},
        "additionalProperties": False,
    }
    mode = Mode.SIMULATED

    def resolve(self, slots: dict[str, Any], ctx: CapabilityContext) -> ResolvedAction:
        item = str(slots.get("item") or "dawai").lower()
        price = MEDICINE_PRICES_PAISE.get(item, MEDICINE_PRICES_PAISE["dawai"])
        return ResolvedAction(
            capability=self.name,
            description=f"Medicine refill ({item})",
            amount_paise=price,
            payee="dawai",
            detail={"slots": {"item": item}, "roadmap": "Pharmacy fulfilment is simulated."},
        )

    def execute(
        self, resolved: ResolvedAction, *, ctx: CapabilityContext, idempotency_key: str
    ) -> ExecutionResult:
        assert resolved.amount_paise is not None
        result = ctx.payments.charge(
            family_id=ctx.family_id,
            capability=self.name,
            payee=resolved.payee or "dawai",
            amount_paise=resolved.amount_paise,
            idempotency_key=idempotency_key,
            description=resolved.description,
        )
        return ExecutionResult(
            ok=result.ok,
            reference=result.reference,
            message=result.message,
            mode=Mode.SIMULATED,
            raw=result.raw,
        )

    def describe_for_speech(self, resolved: ResolvedAction, lang: str = "hi") -> str:
        amount = speak_amount(resolved.amount_paise or 0, lang)
        if lang.startswith("en"):
            return f"Medicine refill, {amount}. Shall I order it?"
        return f"Dawai ka order, {amount}. Mangwa doon?"
