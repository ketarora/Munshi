"""Typed configuration. Thresholds are config, never constants scattered in code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime tuning. All money values are integer paise."""

    confidence_threshold: float = 0.60
    max_clarifications: int = 2
    max_turns_per_call: int = 20
    approval_ttl_seconds: int = 900
    monthly_timezone: str = "Asia/Kolkata"
    unknown_caller_alert_limit: int = 3
    unknown_caller_window_seconds: int = 3600
    demo_second_factor: str = "246810"
    webhook_secret: str = "whsec_demo_munshi_sandbox"
    ledger_currency: str = "INR"
    default_per_txn_cap: int = 200000
    default_daily_cap: int = 300000
    default_monthly_cap: int = 500000
    default_hard_ceiling: int = 500000
    record_calls_disclosure: bool = True
    environment: str = field(default_factory=lambda: os.environ.get("MUNSHI_ENV", "demo"))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            confidence_threshold=_env_float("MUNSHI_CONFIDENCE_THRESHOLD", 0.60),
            max_clarifications=_env_int("MUNSHI_MAX_CLARIFICATIONS", 2),
            max_turns_per_call=_env_int("MUNSHI_MAX_TURNS", 20),
            approval_ttl_seconds=_env_int("MUNSHI_APPROVAL_TTL", 900),
            demo_second_factor=os.environ.get("MUNSHI_DEMO_SECOND_FACTOR", "246810"),
            webhook_secret=os.environ.get("MUNSHI_WEBHOOK_SECRET", "whsec_demo_munshi_sandbox"),
        )

    def with_overrides(self, **kwargs: object) -> "Settings":
        return replace(self, **kwargs)  # type: ignore[arg-type]
