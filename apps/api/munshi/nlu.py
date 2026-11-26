"""Deterministic understanding for Hindi / Hinglish / English.

This is the live demo path: zero external accounts, no network, fully testable.
It is also the safety floor: text is untrusted, an injection attempt becomes
``unclear``, and a capability is never invented.
"""

from __future__ import annotations

import re
from typing import Any

from .domain import Proposal

AFFIRM = (
    "haan", "han", "ha", "haan ji", "hanji", "haanji", "yes", "yeah", "yep", "ok",
    "okay", "theek hai", "thik hai", "thik", "theek", "bilkul", "sahi hai", "sahi",
    "kar do", "bhar do", "bhar dena", "kar dena", "chalo", "aage badho", "bharo",
    "haan kar do", "haan bhar do", "bhar dijiye", "kar dijiye", "हाँ", "हां", "ठीक है",
)
DENY = (
    "nahi", "nahin", "na", "no", "nope", "mat karo", "mat karna", "cancel",
    "rehne do", "rahne do", "abhi nahi", "nahi chahiye", "band karo", "नहीं", "ना",
    "मत करो",
)
PAUSE_WORDS = ("ruko", "ruk jao", "rukiye", "pause", "rok do", "रुको", "रोक दो")
REPEAT_WORDS = (
    "phir bolo", "phir se bolo", "dobara bolo", "dobara batao", "repeat", "kya kaha",
    "samajh nahi aaya", "phir batao", "phir se batao", "dubara bolo", "फिर बोलो", "दोबारा",
)
HELP_WORDS = ("madad", "help", "kaise karta", "kaise chalta", "kya kar sakte", "मदद", "सहायता")
INJECTION_MARKERS = (
    "ignore", "system prompt", "bypass", "override", "jailbreak", "developer mode",
    "rules mat", "niyam mat", "limit badha", "limit badal", "limit change", "cap badha",
    "झूठ", "jhooth", "jaldi karo", "approval mat", "bina puche", "bina poochhe",
)
TRANSFER_MARKERS = ("bhej", "transfer", "send money", "paisa bhej", "paise bhej", "भेज")
BILLER_WORDS = {
    "bijli": ("bijli", "electricity", "power", "बिजली"),
    "paani": ("paani", "pani", "water", "पानी"),
    "mobile": ("mobile", "phone", "recharge", "मोबाइल", "फोन"),
}
LANG_HINTS = {
    "english": ("the", "bill", "pay", "please", "water", "electricity", "medicine", "message"),
    "roman_hindi": ("hai", "karo", "bhej", "nahi", "haan", "mera", "beta", "dawai", "bijli"),
}


def normalise(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[।!?;:'\"()\[\]{}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    tokens = set(normalise(text).split())
    english = sum(1 for w in LANG_HINTS["english"] if w in tokens)
    roman = sum(1 for w in LANG_HINTS["roman_hindi"] if w in tokens)
    if english and roman:
        return "hinglish"
    if english and not roman:
        return "en"
    return "hi"


class RuleUnderstanding:
    """Deterministic intent parser. Implements the UnderstandingPort protocol."""

    name = "rule-based"

    def understand(self, text: str, language: str = "auto", context: dict[str, Any] | None = None) -> Proposal:
        context = context or {}
        norm = normalise(text)
        lang = detect_language(text)
        awaiting = context.get("awaiting")

        if not norm:
            return Proposal(intent="unclear", confidence=0.0, language_detected=lang)

        if any(marker in norm for marker in INJECTION_MARKERS):
            return Proposal(
                intent="unclear",
                confidence=0.05,
                language_detected=lang,
                injection_suspected=True,
                needs_clarification=True,
                clarification_question="Main sirf ghar ke kaam kar sakta hoon. Kya karna hai — bill, gas ya dawai?",
            )

        # Explicit confirmation first: during a read-back it is the whole turn.
        if awaiting == "readback" and self._is_affirm(norm):
            return Proposal(intent="affirm", confidence=0.98, language_detected=lang)
        if awaiting == "readback" and (self._is_deny(norm) or self._is_pause(norm)):
            return Proposal(intent="deny" if self._is_deny(norm) else "pause", confidence=0.95, language_detected=lang)

        if self._is_pause(norm):
            return Proposal(intent="pause", confidence=0.93, language_detected=lang)

        messaging = any(w in norm for w in ("message", "msg", "bata", "bol", "sandesh", "keh"))
        if any(marker in norm for marker in TRANSFER_MARKERS) and not messaging:
            payee = self._transfer_payee(norm)
            return Proposal(
                intent="unsupported_transfer",
                slots={"payee": payee} if payee else {},
                confidence=0.92,
                language_detected=lang,
            )

        biller = self._biller(norm)
        if biller and ("bill" in norm or "भर" in norm or "pay" in norm):
            return Proposal(
                intent="pay_bill",
                slots={"biller": biller},
                confidence=0.94,
                language_detected=lang,
            )
        if "bill" in norm or "बिल" in norm:
            return Proposal(
                intent="pay_bill",
                slots={},
                confidence=0.55,
                language_detected=lang,
                needs_clarification=True,
                clarification_question="Kaunsa bill bharna hai — bijli, paani ya mobile?",
            )

        if any(w in norm for w in ("cylinder", "gas", "सिलेंडर", "गैस")):
            return Proposal(intent="book_gas_cylinder", confidence=0.93, language_detected=lang)

        if any(w in norm for w in ("dawai", "dawa", "medicine", "tablet", "refill", "दवाई", "दवा")):
            return Proposal(intent="refill_medicine", confidence=0.92, language_detected=lang)

        if any(
            w in norm
            for w in ("bata do", "bol do", "message", "batana", "bata dena", "beta ko", "bete ko",
                      "बेटा", "बता दो", "rohit ko", "message bhejo", "sandesh")
        ):
            return Proposal(
                intent="message_child",
                slots={"message": text.strip()},
                confidence=0.9,
                language_detected=lang,
            )

        if any(w in norm for w in HELP_WORDS):
            return Proposal(intent="help", confidence=0.88, language_detected=lang)

        if any(w in norm for w in REPEAT_WORDS):
            return Proposal(intent="repeat", confidence=0.88, language_detected=lang)

        if self._is_affirm(norm):
            return Proposal(intent="affirm", confidence=0.9, language_detected=lang)
        if self._is_deny(norm):
            return Proposal(intent="deny", confidence=0.9, language_detected=lang)

        return Proposal(intent="unclear", confidence=0.2, language_detected=lang)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _tokens(norm: str) -> set[str]:
        return set(norm.split())

    def _is_affirm(self, norm: str) -> bool:
        if any(phrase == norm for phrase in AFFIRM):
            return True
        tokens = self._tokens(norm)
        if tokens & {"nahi", "nahin", "na", "no", "mat", "नहीं"}:
            return False
        if "theek hai" in norm or "thik hai" in norm or "kar do" in norm or "bhar do" in norm:
            return True
        return bool(tokens & {"haan", "han", "yes", "bilkul", "sahi", "ok", "okay", "हाँ", "हां"})

    def _is_deny(self, norm: str) -> bool:
        if any(phrase == norm for phrase in DENY):
            return True
        tokens = self._tokens(norm)
        return bool(tokens & {"nahi", "nahin", "na", "no", "nah", "नहीं", "ना"})

    def _is_pause(self, norm: str) -> bool:
        return any(w in norm for w in PAUSE_WORDS)

    def _biller(self, norm: str) -> str | None:
        for biller, words in BILLER_WORDS.items():
            if any(word in norm for word in words):
                return biller
        return None

    @staticmethod
    def _transfer_payee(norm: str) -> str | None:
        match = re.search(r"([a-z\u0900-\u097F]{3,})\s+ko\s+(?:\d|paise|paisa|bhej)", norm)
        if match:
            candidate = match.group(1)
            if candidate not in {"usko", "unko", "mujhe", "humein", "amma", "papa"}:
                return candidate
        return None
