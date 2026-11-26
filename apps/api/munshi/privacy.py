"""Hashing, masking and log scrubbing. No raw phone numbers in logs."""

from __future__ import annotations

import hashlib
import re

_PHONE_RE = re.compile(r"(?<!\d)(?:\+91[-\s]?)?(\d{10})(?!\d)")
_TOKEN_RE = re.compile(r"(?i)(token|secret|api[_-]?key|otp)\s*[=:]\s*\S+")


def normalise_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits


def hash_phone(phone: str) -> str:
    digits = normalise_phone(phone)
    return hashlib.sha256(f"munshi-phone:{digits}".encode("utf-8")).hexdigest()


def mask_phone(phone: str) -> str:
    digits = normalise_phone(phone)
    if len(digits) < 4:
        return "••••"
    return f"••••••{digits[-4:]}"


def scrub(text: str) -> str:
    """Best-effort PII scrubber for logs and audit payloads."""
    scrubbed = _PHONE_RE.sub(lambda m: f"••••••{m.group(1)[-4:]}", text or "")
    scrubbed = _TOKEN_RE.sub(lambda m: f"{m.group(1)}=[redacted]", scrubbed)
    return scrubbed
