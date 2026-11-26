"""Transaction state machine. Illegal transitions are errors, not warnings."""

from __future__ import annotations

from .domain import TxnState


class IllegalTransition(RuntimeError):
    def __init__(self, current: TxnState, target: TxnState) -> None:
        super().__init__(f"illegal transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


TERMINAL = frozenset(
    {
        TxnState.REJECTED,
        TxnState.SUCCEEDED,
        TxnState.FAILED,
        TxnState.CANCELLED,
        TxnState.EXPIRED,
    }
)

TRANSITIONS: dict[TxnState, frozenset[TxnState]] = {
    TxnState.PROPOSED: frozenset(
        {
            TxnState.REJECTED,
            TxnState.NEEDS_CLARIFICATION,
            TxnState.AWAITING_READBACK,
            TxnState.AWAITING_APPROVAL,
            TxnState.APPROVED,
        }
    ),
    TxnState.NEEDS_CLARIFICATION: frozenset({TxnState.PROPOSED, TxnState.CANCELLED}),
    TxnState.AWAITING_READBACK: frozenset(
        {TxnState.APPROVED, TxnState.CANCELLED, TxnState.EXPIRED}
    ),
    TxnState.AWAITING_APPROVAL: frozenset(
        {TxnState.APPROVED, TxnState.CANCELLED, TxnState.EXPIRED}
    ),
    TxnState.APPROVED: frozenset({TxnState.EXECUTING}),
    TxnState.EXECUTING: frozenset({TxnState.SUCCEEDED, TxnState.FAILED}),
}

# Every terminal state intentionally has no outgoing edges.
for _terminal in TERMINAL:
    TRANSITIONS.setdefault(_terminal, frozenset())


def assert_transition(current: TxnState, target: TxnState) -> TxnState:
    if current in TERMINAL:
        raise IllegalTransition(current, target)
    if target not in TRANSITIONS[current]:
        raise IllegalTransition(current, target)
    return target


def is_terminal(state: TxnState) -> bool:
    return state in TERMINAL
