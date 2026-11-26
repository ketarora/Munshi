"""Bill payment.

The amount ALWAYS comes from the biller, never from speech, never from slots.
"""

from __future__ import annotations

from typing import Any

from ..domain import ExecutionResult, Mode, ResolvedAction
from ..money import speak_amount
from ..ports import BillNotFound
from .base import CapabilityContext

BILLER_LABELS = {"bijli": "Bijli", "paani": "Paani", "mobile": "Mobile"}


class PayBill:
    name = "pay_bill"
    requires_money = True
    supported_languages = ("hi", "hinglish", "en")
    slots_schema = {
        "type": "object",
        "required": ["biller"],
        "properties": {"biller": {"type": "string", "enum": ["bijli", "paani", "mobile"]}},
        "additionalProperties": False,
    }

    @property
    def mode(self) -> Mode:
        # Resolved per call from the payments adapter; default is honest.
        return Mode.SIMULATED

    def resolve(self, slots: dict[str, Any], ctx: CapabilityContext) -> ResolvedAction:
        biller = str(slots.get("biller") or "").strip().lower()
        if not biller:
            raise BillNotFound("no biller selected")
        bill = ctx.biller.fetch_due(ctx.family_id, biller)
        row = ctx.db.bill(ctx.family_id, biller)
        return ResolvedAction(
            capability=self.name,
            description=f"{BILLER_LABELS.get(biller, biller)} bill",
            amount_paise=bill.amount_paise,
            payee=biller,
            detail={
                "account_no": bill.account_no,
                "due_date": bill.due_date,
                "bill_id": row["id"] if row else None,
                "slots": {"biller": biller},
            },
        )

    def execute(
        self, resolved: ResolvedAction, *, ctx: CapabilityContext, idempotency_key: str
    ) -> ExecutionResult:
        assert resolved.amount_paise is not None and resolved.payee is not None
        result = ctx.payments.charge(
            family_id=ctx.family_id,
            capability=self.name,
            payee=resolved.payee,
            amount_paise=resolved.amount_paise,
            idempotency_key=idempotency_key,
            description=resolved.description,
        )
        if result.ok:
            ctx.biller.mark_paid(ctx.family_id, resolved.payee)
        return result

    def describe_for_speech(self, resolved: ResolvedAction, lang: str = "hi") -> str:
        amount = speak_amount(resolved.amount_paise or 0, lang)
        label = BILLER_LABELS.get(resolved.payee or "", resolved.description)
        if lang.startswith("en"):
            return f"{label} bill, {amount}. Shall I pay it?"
        return f"{label} ka bill, {amount}. Bhar doon?"
