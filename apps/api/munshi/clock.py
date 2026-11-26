"""Injectable clock so money windows and approval expiry are deterministic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:  # pragma: no cover - protocol
        ...


@dataclass
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class FixedClock:
    """Test clock. ``advance`` keeps tests readable."""

    current: datetime = field(
        default_factory=lambda: datetime(2026, 11, 25, 4, 30, tzinfo=timezone.utc)
    )

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
