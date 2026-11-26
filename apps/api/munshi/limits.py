"""Onboarding-by-voice-note limit parsing.

Spoken amounts ARE allowed here (the child is setting limits), but nothing is
saved without a read-back and an explicit confirmation, and any increase needs a
second factor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .money import format_indian

_UNITS = {
    "shunya": 0, "ek": 1, "do": 2, "teen": 3, "chaar": 4, "paanch": 5, "panch": 5,
    "chhah": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "bees": 20,
    "pachaas": 50, "pachas": 50, "pachchaas": 50, "sau": 100, "hazaar": 1000,
    "hazar": 1000, "hajaar": 1000, "lakh": 100000,
}
_CAPABILITY_WORDS = {
    "pay_bill": ("bijli", "bill", "electricity", "paani", "water", "बिजली", "बिल"),
    "book_gas_cylinder": ("gas", "cylinder", "सिलेंडर", "गैस"),
    "refill_medicine": ("dawai", "dawa", "medicine", "दवाई", "दवा"),
    "message_child": ("message", "bata", "baat"),
}
_CAP_LABELS = {
    "pay_bill": "bijli jaise bill",
    "book_gas_cylinder": "gas cylinder",
    "refill_medicine": "dawai",
    "message_child": "beta ko message",
}


def words_to_number(text: str) -> int | None:
    """Parse a simple Hindi/English number phrase such as 'pachaas hazaar'."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return None
    total = 0
    current = 0
    found = False
    for word in words:
        if word in {"rupaye", "rupees", "rupee", "tak", "mahine", "month", "ke", "liye", "par", "se"}:
            continue
        if word in _UNITS:
            value = _UNITS[word]
            if value >= 1000:
                current = (current or 1) * value
                total += current
                current = 0
            elif value == 100:
                current = (current or 1) * 100
            else:
                current += value
            found = True
        elif word.isdigit():
            current += int(word)
            found = True
        else:
            break
    if not found:
        return None
    return total + current


def _amount_near_phrases(text: str) -> int | None:
    norm = text.lower().replace(",", "")
    digit = re.search(r"(\d{2,7})\s*(?:rupaye|rupees|rs|tak)?", norm)
    if digit:
        return int(digit.group(1))
    # Look for a window after 'mahine' / 'month' or before 'tak'.
    for pattern in (
        r"mahine\s*(?:mein|me|in)?\s*([a-zA-Z\s]+?)\s*(?:tak|rupaye|rupees)",
        r"([a-zA-Z\s]+?)\s*rupaye",
        r"([a-zA-Z\s]+?)\s*tak",
    ):
        match = re.search(pattern, norm)
        if match:
            value = words_to_number(match.group(1))
            if value:
                return value
    return None


@dataclass
class ParsedLimits:
    capabilities: list[str] = field(default_factory=list)
    monthly_rupees: int | None = None
    per_txn_rupees: int | None = None
    needs_clarification: bool = False
    clarification: str | None = None
    readback: str = ""
    confidence: float = 0.0
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "monthly_rupees": self.monthly_rupees,
            "per_txn_rupees": self.per_txn_rupees,
            "needs_clarification": self.needs_clarification,
            "clarification": self.clarification,
            "readback": self.readback,
            "confidence": self.confidence,
            "raw_text": self.raw_text,
        }


def parse_limits_note(text: str) -> ParsedLimits:
    norm = (text or "").lower()
    capabilities = [
        cap for cap, words in _CAPABILITY_WORDS.items() if any(w in norm for w in words)
    ]
    if "pay_bill" in capabilities and "book_gas_cylinder" in capabilities:
        # "bijli, gas aur dawai" means three capabilities, which is fine.
        pass

    monthly = _amount_near_phrases(norm)
    result = ParsedLimits(capabilities=capabilities, monthly_rupees=monthly, raw_text=text)

    if not capabilities:
        result.needs_clarification = True
        result.clarification = "Kaun kaun se kaam chalu karne hain — bijli bill, gas, dawai?"
        result.confidence = 0.3
        result.readback = result.clarification
        return result

    if monthly is None:
        result.needs_clarification = True
        result.clarification = "Mahine mein kitna tak kharch ho sakta hai? Jaise 'paanch hazaar tak'."
        result.confidence = 0.4
        result.readback = result.clarification
        return result

    if monthly < 100:
        result.needs_clarification = True
        result.clarification = "Kitne rupaye? Kam se kam sau rupaye boliye."
        result.confidence = 0.3
        result.readback = result.clarification
        return result

    result.per_txn_rupees = monthly
    per_txn_digits = re.search(
        r"(?:ek baar|ek payment|har payment|per transaction)[^0-9]{0,30}(\d{2,7})", norm
    )
    candidate: int | None = None
    if per_txn_digits:
        candidate = int(per_txn_digits.group(1))
    else:
        per_txn_words = re.search(
            r"(?:ek baar|ek payment|har payment|per transaction)([a-zA-Z\s]{0,40})", norm
        )
        if per_txn_words:
            tail = re.sub(r"\b(mein|me|tak|rupaye|rupees|lekin|par|aur|ka|ki|ke|se)\b", " ", per_txn_words.group(1))
            candidate = words_to_number(tail)
    if candidate:
        result.per_txn_rupees = candidate

    if result.per_txn_rupees is not None and result.per_txn_rupees > monthly:
        result.needs_clarification = True
        result.clarification = (
            f"Ek payment {format_indian(result.per_txn_rupees)} rupaye, par mahine ka limit "
            f"{format_indian(monthly)} rupaye hai. Kaunsa sahi hai?"
        )
        result.confidence = 0.35
        result.readback = result.clarification
        return result

    caps_text = ", ".join(_CAP_LABELS[c] for c in capabilities)
    result.confidence = 0.9
    result.readback = (
        f"Samajh gayi: {caps_text}. Mahine mein {format_indian(monthly)} rupaye tak. "
        f"Har payment {format_indian(result.per_txn_rupees or monthly)} rupaye tak. "
        "Theek hai?"
    )
    return result
