"""P-01..P-13: the Policy Engine is the safety oracle."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings as hyp_settings, strategies as st

from munshi.domain import Decision
from munshi.policy import PolicyRequest, evaluate


def base_request(**overrides) -> PolicyRequest:
    request = PolicyRequest(
        caller_verified=True,
        paused=False,
        capability="pay_bill",
        capability_enabled=True,
        intent_confidence=0.9,
        confidence_threshold=0.6,
        clarification_count=0,
        max_clarifications=2,
        amount_paise=100000,
        payee="bijli",
        allowlisted_payees=("bijli", "gas", "dawai"),
        per_txn_cap=200000,
        hard_ceiling=500000,
        daily_cap=300000,
        monthly_cap=500000,
        spent_today=0,
        spent_this_month=0,
        duplicate=False,
        requires_money=True,
    )
    return replace(request, **overrides)


def test_p01_all_checks_pass() -> None:
    result = evaluate(base_request())
    assert result.decision is Decision.AUTO_EXECUTE
    assert result.rule == "P-OK"


def test_p02_per_txn_cap_boundary() -> None:
    at_cap = evaluate(base_request(amount_paise=200000))
    assert at_cap.decision is Decision.AUTO_EXECUTE

    over = evaluate(base_request(amount_paise=200001))
    assert over.decision is Decision.REQUIRE_CHILD_APPROVAL
    assert over.rule == "P-PER-TXN-CAP"


def test_p03_hard_ceiling_boundary() -> None:
    wide = dict(per_txn_cap=500000, daily_cap=600000, monthly_cap=600000)
    at_ceiling = evaluate(base_request(amount_paise=500000, **wide))
    assert at_ceiling.decision is Decision.AUTO_EXECUTE

    over = evaluate(base_request(amount_paise=500001, **wide))
    assert over.decision is Decision.REJECT
    assert over.rule == "P-HARD-CEILING"


def test_p04_new_payee_requires_child() -> None:
    result = evaluate(base_request(payee="paani", amount_paise=100))
    assert result.decision is Decision.REQUIRE_CHILD_APPROVAL
    assert result.rule == "P-NEW-PAYEE"


def test_p05_daily_cap_boundary() -> None:
    exact = evaluate(base_request(amount_paise=100000, daily_cap=150000, spent_today=50000))
    assert exact.decision is Decision.AUTO_EXECUTE

    over = evaluate(base_request(amount_paise=100000, daily_cap=150000, spent_today=50001))
    assert over.decision is Decision.REQUIRE_CHILD_APPROVAL
    assert over.rule == "P-DAILY-CAP"


def test_p06_monthly_cap_boundary() -> None:
    exact = evaluate(base_request(amount_paise=100000, monthly_cap=250000, spent_this_month=150000))
    assert exact.decision is Decision.AUTO_EXECUTE

    over = evaluate(base_request(amount_paise=100000, monthly_cap=250000, spent_this_month=150001))
    assert over.decision is Decision.REQUIRE_CHILD_APPROVAL
    assert over.rule == "P-MONTHLY-CAP"


def test_p07_paused_rejects_everything() -> None:
    result = evaluate(base_request(paused=True, amount_paise=1, payee="bijli"))
    assert result.decision is Decision.REJECT
    assert result.rule == "P-SYSTEM-PAUSED"


def test_p08_capability_disabled() -> None:
    result = evaluate(base_request(capability_enabled=False))
    assert result.decision is Decision.REJECT
    assert result.rule == "P-CAPABILITY-DISABLED"


def test_p09_unverified_caller() -> None:
    result = evaluate(base_request(caller_verified=False))
    assert result.decision is Decision.REJECT
    assert result.rule == "P-CALLER-UNVERIFIED"


def test_p10_confidence_threshold() -> None:
    below = evaluate(base_request(intent_confidence=0.59, confidence_threshold=0.6))
    assert below.decision is Decision.CLARIFY

    at = evaluate(base_request(intent_confidence=0.6, confidence_threshold=0.6))
    assert at.decision is Decision.AUTO_EXECUTE

    above = evaluate(base_request(intent_confidence=0.99, confidence_threshold=0.6))
    assert above.decision is Decision.AUTO_EXECUTE


def test_p10b_confidence_exhausted_escalates() -> None:
    result = evaluate(base_request(intent_confidence=0.2, clarification_count=2, max_clarifications=2))
    assert result.decision is Decision.ESCALATE_TO_CHILD
    assert result.rule == "P-CONFIDENCE-EXHAUSTED"


def test_p11_rule_order_is_documented_and_fixed() -> None:
    assert evaluate(base_request(caller_verified=False, paused=True)).rule == "P-CALLER-UNVERIFIED"
    assert evaluate(base_request(paused=True, capability_enabled=False)).rule == "P-SYSTEM-PAUSED"
    assert evaluate(base_request(capability_enabled=False, amount_paise=999999)).rule == "P-CAPABILITY-DISABLED"
    assert evaluate(base_request(amount_paise=600000, payee="paani")).rule == "P-HARD-CEILING"
    assert evaluate(base_request(payee="paani", amount_paise=300000)).rule == "P-NEW-PAYEE"
    duplicate = evaluate(base_request(duplicate=True, amount_paise=900000))
    assert duplicate.decision is Decision.NO_OP
    assert duplicate.rule == "P-DUPLICATE"


def test_p11b_invalid_amount() -> None:
    result = evaluate(base_request(amount_paise=-1))
    assert result.decision is Decision.REJECT
    assert result.rule == "P-AMOUNT-INVALID"


@hyp_settings(max_examples=200, deadline=None)
@given(
    verified=st.booleans(),
    paused=st.booleans(),
    enabled=st.booleans(),
    confidence=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    amount=st.integers(min_value=0, max_value=800000),
    per_txn=st.integers(min_value=0, max_value=500000),
    hard=st.integers(min_value=0, max_value=700000),
    daily=st.integers(min_value=0, max_value=700000),
    monthly=st.integers(min_value=0, max_value=700000),
    spent_today=st.integers(min_value=0, max_value=700000),
    spent_month=st.integers(min_value=0, max_value=700000),
    payee=st.sampled_from(["bijli", "paani"]),
    allowlist=st.sampled_from([("bijli",), ("bijli", "paani")]),
)
def test_p12_never_auto_executes_when_a_hard_rule_is_violated(
    verified, paused, enabled, confidence, amount, per_txn, hard, daily, monthly,
    spent_today, spent_month, payee, allowlist,
) -> None:
    request = base_request(
        caller_verified=verified, paused=paused, capability_enabled=enabled,
        intent_confidence=confidence, amount_paise=amount, payee=payee,
        allowlisted_payees=allowlist, per_txn_cap=per_txn, hard_ceiling=hard,
        daily_cap=daily, monthly_cap=monthly, spent_today=spent_today,
        spent_this_month=spent_month,
    )
    result = evaluate(request)
    violated = (
        not verified
        or paused
        or not enabled
        or confidence < request.confidence_threshold
        or amount > hard
        or payee not in allowlist
        or amount > per_txn
        or spent_today + amount > daily
        or spent_month + amount > monthly
    )
    if violated:
        assert result.decision is not Decision.AUTO_EXECUTE


@hyp_settings(max_examples=100, deadline=None)
@given(
    amount=st.integers(min_value=0, max_value=900000),
    spent=st.integers(min_value=0, max_value=900000),
)
def test_p13_policy_is_pure(amount: int, spent: int) -> None:
    request = base_request(amount_paise=amount, spent_this_month=spent)
    first = evaluate(request)
    second = evaluate(request)
    assert first == second
