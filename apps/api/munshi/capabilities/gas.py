"""Gas cylinder booking (SIMULATED). No real LPG integration is claimed."""

from __future__ import annotations

from typing import Any

from ..domain import ExecutionResult, Mode, ResolvedAction
from ..money import speak_amount
from ..rupeepay import GAS_CYLINDER_PAISE
from .base import CapabilityContext


class BookGasCylinder:
    name = "book_gas_cylinder"
    requires_money = True
    supported_languages = ("hi", "hinglish", "en")
    slots_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    mode = Mode.SIMULATED

    def resolve(self, slots: dict[str, Any], ctx: CapabilityContext) -> ResolvedAction:
        return ResolvedAction(
            capability=self.name,
            description="Gas cylinder booking",
            amount_paise=GAS_CYLINDER_PAISE,
            payee="gas",
            detail={"slots": {}, "roadmap": "Real LPG distributor integration is not shipped."},
        )

    def execute(
        self, resolved: ResolvedAction, *, ctx: CapabilityContext, idempotency_key: str
    ) -> ExecutionResult:
        assert resolved.amount_paise is not None
        result = ctx.payments.charge(
            family_id=ctx.family_id,
            capability=self.name,
            payee=resolved.payee or "gas",
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
            return f"Gas cylinder, {amount}. Shall I book it?"
        return f"Gas cylinder, {amount}. Book kar doon?"
