"""Integer-paise money helpers and Indian-format read-back.

Money is never a float. A spoken amount never enters this module's payment path;
it is used only for onboarding limits, where a read-back is mandatory.
"""

from __future__ import annotations


class MoneyError(ValueError):
    """Raised for non-integer or negative money input."""


def rupees_to_paise(rupees: int) -> int:
    if isinstance(rupees, bool) or not isinstance(rupees, int):
        raise MoneyError("rupees must be an int (no floats, no bools)")
    if rupees < 0:
        raise MoneyError("rupees must not be negative")
    return rupees * 100


def validate_paise(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MoneyError("paise must be an int (no floats, no bools)")
    if value < 0:
        raise MoneyError("paise must not be negative")
    return value


def format_indian(number: int) -> str:
    """Group digits the Indian way: 100000 -> 1,00,000."""
    if not isinstance(number, int):
        raise MoneyError("number must be an int")
    negative = number < 0
    digits = str(abs(number))
    if len(digits) <= 3:
        out = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        out = ",".join(groups) + "," + last3
    return ("-" if negative else "") + out


def format_inr(paise: int, lang: str = "hi") -> str:
    validate_paise(paise)
    rupees = paise // 100
    paise_part = paise % 100
    amount = format_indian(rupees)
    if paise_part:
        amount = f"{amount}.{paise_part:02d}"
    if lang.lower().startswith("en"):
        return f"INR {amount}"
    return f"{amount} rupaye"


_ONES_HI = [
    "shunya", "ek", "do", "teen", "chaar", "paanch", "chhah", "saat", "aath", "nau",
    "das", "gyarah", "baarah", "terah", "chaudah", "pandrah", "solah", "satrah",
    "atharah", "unnees",
]
_TENS_HI = {
    20: "bees", 30: "tees", 40: "chalees", 50: "pachaas",
    60: "saath", 70: "sattar", 80: "assi", 90: "nabbe",
}
_ONES_EN = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS_EN = {
    20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
    60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
}


def _two_digit_hi(n: int) -> str:
    if n < 20:
        return _ONES_HI[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS_HI[tens * 10]
    return f"{_TENS_HI[tens * 10]} {_ONES_HI[ones]}"


def _two_digit_en(n: int) -> str:
    if n < 20:
        return _ONES_EN[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS_EN[tens * 10]
    return f"{_TENS_EN[tens * 10]}-{_ONES_EN[ones]}"


def _words_hi_below_crore(n: int) -> str:
    if n == 0:
        return "shunya"
    parts: list[str] = []
    lakh, rest = divmod(n, 100000)
    thousand, rest = divmod(rest, 1000)
    hundred, rest = divmod(rest, 100)
    if lakh:
        parts.append(f"{_words_hi_below_crore(lakh)} lakh")
    if thousand:
        parts.append(f"{_words_hi_below_crore(thousand)} hazaar")
    if hundred:
        parts.append(f"{_ONES_HI[hundred]} sau")
    if rest:
        parts.append(_two_digit_hi(rest))
    return " ".join(parts)


def _words_en_below_crore(n: int) -> str:
    if n == 0:
        return "zero"
    parts: list[str] = []
    lakh, rest = divmod(n, 100000)
    thousand, rest = divmod(rest, 1000)
    hundred, rest = divmod(rest, 100)
    if lakh:
        parts.append(f"{_words_en_below_crore(lakh)} lakh")
    if thousand:
        parts.append(f"{_words_en_below_crore(thousand)} thousand")
    if hundred:
        parts.append(f"{_ONES_EN[hundred]} hundred")
    if rest:
        parts.append(_two_digit_en(rest))
    return " ".join(parts)


def amount_words(paise: int, lang: str = "hi") -> str:
    """Spoken form, useful for TTS and for asserting grouping edge cases."""
    validate_paise(paise)
    rupees, paise_part = divmod(paise, 100)
    words = _words_en_below_crore(rupees) if lang.lower().startswith("en") else _words_hi_below_crore(rupees)
    unit = "rupees" if lang.lower().startswith("en") else "rupaye"
    if paise_part:
        small = _two_digit_en(paise_part) if lang.lower().startswith("en") else _two_digit_hi(paise_part)
        return f"{words} {unit} aur {small} paise"
    return f"{words} {unit}"


def speak_amount(paise: int, lang: str = "hi") -> str:
    """Read-back used on the phone: grouped digits, never an ASR guess."""
    validate_paise(paise)
    if lang.lower().startswith("en"):
        return f"{format_indian(paise // 100)} rupees"
    return f"{format_indian(paise // 100)} rupaye"
