"""Deterministic Policy Engine.

Pure function. No clock, no I/O, no LLM. The LLM proposes; this disposes.

Rule order is fixed and documented in ``RULE_ORDER``. The first matching rule
wins, and every result carries the rule code that fired so the UI can explain
the decision to a judge.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Decision

RULE_ORDER = (
    "P-CALLER-UNVERIFIED",
    "P-SYSTEM-PAUSED",
    "P-DUPLICATE",
    "P-CAPABILITY-DISABLED",
    "P-AMOUNT-INVALID",
    "P-CONFIDENCE-LOW",
    "P-CONFIDENCE-EXHAUSTED",
    "P-HARD-CEILING",
    "P-NEW-PAYEE",
    "P-PER-TXN-CAP",
    "P-DAILY-CAP",
    "P-MONTHLY-CAP",
    "P-OK",
)


@dataclass(frozen=True)
class PolicyRequest:
    caller_verified: bool
    paused: bool
    capability: str
    capability_enabled: bool
    intent_confidence: float
    confidence_threshold: float
    clarification_count: int
    max_clarifications: int
    amount_paise: int
    payee: str | None
    allowlisted_payees: tuple[str, ...]
    per_txn_cap: int
    hard_ceiling: int
    daily_cap: int
    monthly_cap: int
    spent_today: int
    spent_this_month: int
    duplicate: bool = False
    requires_money: bool = True


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    rule: str
    reason: str

    @property
    def executed(self) -> bool:
        return self.decision is Decision.AUTO_EXECUTE


def _result(decision: Decision, rule: str, reason: str) -> PolicyResult:
    if rule not in RULE_ORDER:  # guard against typos in the oracle table
        raise AssertionError(f"unknown rule code {rule}")
    return PolicyResult(decision=decision, rule=rule, reason=reason)


def evaluate(req: PolicyRequest) -> PolicyResult:
    """Evaluate one request against the fixed rule order."""

    # 1. Identity before anything else.
    if not req.caller_verified:
        return _result(
            Decision.REJECT,
            "P-CALLER-UNVERIFIED",
            "The caller number is not registered to a family; no action is allowed and the child is alerted.",
        )

    # 2. The family kill switch beats every capability.
    if req.paused:
        return _result(
            Decision.REJECT,
            "P-SYSTEM-PAUSED",
            "The family has paused Munshi; nothing may execute until the child resumes it.",
        )

    # 3. Replays return the prior result and never spend twice.
    if req.duplicate:
        return _result(
            Decision.NO_OP,
            "P-DUPLICATE",
            "This exact request was already processed; the earlier result is returned.",
        )

    # 4. Capability switches are per family.
    if not req.capability_enabled:
        return _result(
            Decision.REJECT,
            "P-CAPABILITY-DISABLED",
            f"The capability '{req.capability}' is disabled for this family.",
        )

    # 5. Money must be sane before any amount comparison.
    if req.requires_money:
        if not isinstance(req.amount_paise, int) or isinstance(req.amount_paise, bool) or req.amount_paise < 0:
            return _result(
                Decision.REJECT,
                "P-AMOUNT-INVALID",
                "The resolved amount is not a non-negative integer in paise.",
            )

    # 6. Low confidence clarifies, then escalates. It never guesses.
    if req.intent_confidence < req.confidence_threshold:
        if req.clarification_count < req.max_clarifications:
            return _result(
                Decision.CLARIFY,
                "P-CONFIDENCE-LOW",
                "Understanding confidence is below the configured threshold; ask one clarifying question.",
            )
        return _result(
            Decision.ESCALATE_TO_CHILD,
            "P-CONFIDENCE-EXHAUSTED",
            "Too many unclear attempts; escalate to the child rather than guess.",
        )

    if not req.requires_money:
        return _result(Decision.AUTO_EXECUTE, "P-OK", "All checks passed for a non-money action.")

    # 7. Hard ceiling is a refusal, not an approval request.
    if req.amount_paise > req.hard_ceiling:
        return _result(
            Decision.REJECT,
            "P-HARD-CEILING",
            "The amount exceeds the family's hard ceiling and can never be auto-approved.",
        )

    # 8. Unknown payee -> child approval, whatever the amount.
    if req.payee is not None and req.payee not in req.allowlisted_payees:
        return _result(
            Decision.REQUIRE_CHILD_APPROVAL,
            "P-NEW-PAYEE",
            f"'{req.payee}' is not on the family allowlist; the child must approve.",
        )

    # 9. Per-transaction cap.
    if req.amount_paise > req.per_txn_cap:
        return _result(
            Decision.REQUIRE_CHILD_APPROVAL,
            "P-PER-TXN-CAP",
            "The amount is above the per-transaction cap; the child must approve.",
        )

    # 10. Daily cap (spend already committed today + this amount).
    if req.spent_today + req.amount_paise > req.daily_cap:
        return _result(
            Decision.REQUIRE_CHILD_APPROVAL,
            "P-DAILY-CAP",
            "This payment would exceed today's cap; the child must approve.",
        )

    # 11. Monthly cap.
    if req.spent_this_month + req.amount_paise > req.monthly_cap:
        return _result(
            Decision.REQUIRE_CHILD_APPROVAL,
            "P-MONTHLY-CAP",
            "This payment would exceed this month's cap; the child must approve.",
        )

    # 12. Everything passed. Execution still waits for a spoken read-back.
    return _result(
        Decision.AUTO_EXECUTE,
        "P-OK",
        "Caller verified, payee allowlisted and every cap respected.",
    )
