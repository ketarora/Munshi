"""Capability plugins. Adding a Round 2 task means adding a capability, not a rewrite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..db import Database
from ..domain import ExecutionResult, Mode, ResolvedAction
from ..ports import BillerPort, NotifierPort, PaymentsPort


class UnknownCapability(KeyError):
    pass


@dataclass
class CapabilityContext:
    family_id: str
    family_name: str
    db: Database
    biller: BillerPort
    payments: PaymentsPort
    notifier: NotifierPort
    language: str = "hi"
    now: str = ""


class Capability(Protocol):
    name: str
    requires_money: bool
    mode: Mode
    supported_languages: tuple[str, ...]
    slots_schema: dict[str, Any]

    def resolve(self, slots: dict[str, Any], ctx: CapabilityContext) -> ResolvedAction: ...

    def execute(self, resolved: ResolvedAction, *, ctx: CapabilityContext, idempotency_key: str) -> ExecutionResult: ...

    def describe_for_speech(self, resolved: ResolvedAction, lang: str = "hi") -> str: ...


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._items[capability.name] = capability

    def get(self, name: str) -> Capability:
        if name not in self._items:
            raise UnknownCapability(name)
        return self._items[name]

    def has(self, name: str) -> bool:
        return name in self._items

    def names(self) -> list[str]:
        return sorted(self._items)

    def __iter__(self):
        return iter(self._items.values())
