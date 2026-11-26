"""The call orchestrator: one turn in, one spoken reply plus a full trace out.

Rules that hold everywhere in this module:

* ASR text is untrusted data.
* Policy is always called before anything can execute.
* A transaction's state only moves through ``statemachine``.
* Nothing is notified or charged without an audit entry.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .capabilities import CapabilityContext, CapabilityRegistry, UnknownCapability, default_registry
from .clock import Clock, SystemClock, iso, parse_iso
from .config import Settings
from .db import Database
from .domain import Decision, ExecutionResult, Mode, Proposal, ResolvedAction, TxnState
from .errors import (
    ApprovalAlreadyDecided,
    ApprovalExpired,
    ApprovalNotFound,
    CallNotFound,
    Forbidden,
    InvalidDecision,
    SecondFactorRequired,
)
from .limits import parse_limits_note
from .money import rupees_to_paise, speak_amount
from .policy import PolicyRequest, PolicyResult, evaluate
from .ports import BillerPort, BillNotFound, NotifierPort, PaymentsPort, UnderstandingPort
from .privacy import hash_phone
from .statemachine import assert_transition, is_terminal

MONEY_INTENTS = {"pay_bill", "book_gas_cylinder", "refill_medicine"}
ALL_INTENTS = {
    "pay_bill", "book_gas_cylinder", "refill_medicine", "message_child",
    "affirm", "deny", "repeat", "help", "pause", "unsupported_transfer", "unclear",
}


@dataclass
class Outcome:
    reply: str
    decision: str
    lang: str = "hi"
    trace: dict[str, Any] = field(default_factory=dict)
    txn: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    done: bool = False


class InMemoryRateLimiter:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self._hits: dict[str, list[datetime]] = {}

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = self.clock.now()
        cutoff = now - timedelta(seconds=window_seconds)
        hits = [h for h in self._hits.get(key, []) if h >= cutoff]
        allowed = len(hits) < limit
        if allowed:
            hits.append(now)
        self._hits[key] = hits
        return allowed


class Orchestrator:
    def __init__(
        self,
        db: Database,
        *,
        clock: Clock | None = None,
        settings: Settings | None = None,
        understanding: UnderstandingPort | None = None,
        payments: PaymentsPort | None = None,
        biller: BillerPort | None = None,
        notifier: NotifierPort | None = None,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        from .adapters.fakes import FakeBiller, MockLedger, SimulatorNotifier

        self.db = db
        self.clock = clock or db.clock or SystemClock()
        self.settings = settings or Settings()
        self.understanding = understanding or self._default_understanding()
        self.payments = payments or MockLedger()
        self.biller = biller or FakeBiller(db)
        self.notifier = notifier or SimulatorNotifier(db)
        self.registry = registry or default_registry()
        self.limiter = InMemoryRateLimiter(self.clock)

    @staticmethod
    def _default_understanding() -> UnderstandingPort:
        from .adapters.understanding import SchemaGuardedUnderstanding
        from .nlu import RuleUnderstanding

        return SchemaGuardedUnderstanding(RuleUnderstanding())

    # ------------------------------------------------------------------- calls
    def start_call(self, caller_number: str | None, channel: str = "browser") -> dict[str, Any]:
        now = iso(self.clock.now())
        caller_hash = hash_phone(caller_number) if caller_number else None
        user = self.db.user_by_phone_hash(caller_hash) if caller_hash else None
        verified = bool(user and user["role"] == "parent")

        if not verified:
            if caller_hash:
                allowed = self.limiter.allow(
                    caller_hash,
                    self.settings.unknown_caller_alert_limit,
                    self.settings.unknown_caller_window_seconds,
                )
                self.db.audit("system", "caller.unknown", {"caller_ref": caller_hash, "alerted": allowed})
            call = self.db.create_call(
                f"call_{uuid.uuid4().hex[:12]}", None, caller_hash, now, "active",
                {"verified": False, "lang": "hi", "awaiting": None, "clarify_count": 0, "silence": 0},
            )
            return {
                "call_id": call["id"],
                "verified": False,
                "greeting": "Namaste. Main Munshi hoon. Ye number kisi family se juda nahi hai. Kripya ghar ke kisi member se baat karein.",
                "family": None,
                "parent_name": None,
                "resumed": False,
                "pending": None,
            }

        family = self.db.family(user["family_id"])
        assert family is not None
        existing = self.db.active_call(family["id"])
        if existing:
            return {
                "call_id": existing["id"],
                "verified": True,
                "greeting": f"{user['display_name']} ji, aapki call pehle se chal rahi hai. Batayein?",
                "family": {"id": family["id"], "name": family["name"]},
                "parent_name": user["display_name"],
                "resumed": True,
                "pending": existing["meta"].get("pending_txn"),
            }

        meta = {
            "verified": True, "lang": "hi", "awaiting": None,
            "clarify_count": 0, "silence": 0, "pending_txn": None,
        }
        greeting = (
            f"Namaste {user['display_name']} ji. Main Munshi hoon, ek AI assistant"
            + (", aur ye call record ho rahi hai." if self.settings.record_calls_disclosure else ".")
            + " Batayein, kya karna hai?"
        )
        pending = self.db.pending_readback(family["id"])
        if pending:
            meta["awaiting"] = "readback"
            meta["pending_txn"] = pending["id"]
            capability = self.registry.get(pending["capability"])
            resolved = self._resolved_from_txn(pending)
            greeting += " Pichhli baar ka kaam ruka tha. " + capability.describe_for_speech(resolved, "hi")

        call = self.db.create_call(
            f"call_{uuid.uuid4().hex[:12]}", family["id"], caller_hash, now, "active", meta
        )
        self.db.audit(
            "gateway", "call.started",
            {"call_id": call["id"], "family_id": family["id"], "caller_ref": caller_hash, "channel": channel},
        )
        return {
            "call_id": call["id"],
            "verified": True,
            "greeting": greeting,
            "family": {"id": family["id"], "name": family["name"]},
            "parent_name": user["display_name"],
            "resumed": False,
            "pending": pending["id"] if pending else None,
        }

    def handle_turn(
        self,
        call_id: str,
        text: str | None,
        *,
        asr_confidence: float = 0.9,
        silence: bool = False,
        interrupt: bool = False,
    ) -> Outcome:
        call = self.db.call(call_id)
        if not call:
            raise CallNotFound(call_id)
        meta = dict(call["meta"])
        lang = meta.get("lang", "hi")
        if call["status"] != "active":
            return Outcome("Ye call band ho chuki hai. Dobara call kijiye.", "REJECT", lang, done=True)

        idx = self.db.turn_count(call_id) + 1
        if idx > self.settings.max_turns_per_call:
            reply = self._close_call(call, meta, "Bahut der ho gayi. Aaj ke liye baat khatam karta hoon. Namaste.")
            self._save_turn(call_id, idx, text or "", 0.0, Proposal("unclear"), "REJECT", reply,
                            {"stages": [], "degraded": False, "policy": None})
            return Outcome(reply, "REJECT", lang, done=True)

        if silence or not (text or "").strip():
            return self._handle_silence(call, meta, idx, text or "")

        started = time.perf_counter()
        trace: dict[str, Any] = {"stages": [], "degraded": False, "policy": None, "interrupt": interrupt}
        proposal = self._understand(text or "", meta, trace)
        trace["mode"] = {
            "understanding": getattr(self.understanding, "name", "rule-based"),
            "payments": self.payments.name,
            "biller": self.biller.name,
            "notifier": self.notifier.name,
        }

        if proposal.intent not in ALL_INTENTS:
            # A model proposed a capability that does not exist: discard it.
            self.db.audit("understanding", "proposal.discarded", {"intent": proposal.intent[:40]})
            proposal = Proposal(
                intent="unclear", confidence=0.1, language_detected=proposal.language_detected,
                injection_suspected=True,
            )
        if not self.registry.has(proposal.intent) and proposal.intent in MONEY_INTENTS:
            proposal = Proposal(intent="unclear", confidence=0.1, language_detected=proposal.language_detected)

        outcome = self._route(call, meta, proposal, trace)
        self._save_turn(call_id, idx, text or "", asr_confidence, proposal, outcome.decision,
                        outcome.reply, trace)
        meta["last_reply"] = outcome.reply
        self.db.update_call(call_id, meta=meta)
        outcome.trace = trace
        return outcome

    def end_call(self, call_id: str, *, reason: str = "hangup") -> dict[str, Any]:
        call = self.db.call(call_id)
        if not call:
            raise CallNotFound(call_id)
        if call["status"] == "active":
            self.db.update_call(call_id, status="ended", ended_at=iso(self.clock.now()))
            self.db.audit("gateway", "call.ended", {"call_id": call_id, "reason": reason})
        return {"call_id": call_id, "status": "ended"}

    # --------------------------------------------------------------- approvals
    def expire_approvals(self, family_id: str) -> list[str]:
        now = self.clock.now()
        expired: list[str] = []
        for approval in self.db.approvals(family_id, state="PENDING", limit=100):
            if parse_iso(approval["expires_at"]) <= now:
                txn = self.db.transaction(approval["txn_id"])
                if txn and txn["state"] == TxnState.AWAITING_APPROVAL.value:
                    assert_transition(TxnState.AWAITING_APPROVAL, TxnState.EXPIRED)
                    self.db.set_transaction_state(txn["id"], TxnState.EXPIRED, reason="approval_timeout", at=iso(now))
                self.db.set_approval_state(approval["id"], "EXPIRED", at=iso(now))
                self._safe_callback(
                    family_id,
                    "approval_expired",
                    "Beta ka jawab nahi aaya, isliye kaam nahi hua. Kuch bhi nahi kata gaya.",
                    approval["txn_id"],
                )
                self._clear_call_awaiting(family_id, approval["txn_id"])
                self.db.audit(
                    "system", "approval.expired",
                    {"approval_id": approval["id"], "txn_id": approval["txn_id"]},
                )
                expired.append(approval["id"])
        return expired

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        *,
        family_id: str,
        by: str = "child",
        channel: str = "console",
    ) -> dict[str, Any]:
        if decision not in {"approve", "deny"}:
            raise InvalidDecision(decision)
        self.expire_approvals(family_id)
        approval = self.db.approval(approval_id)
        if not approval or approval["family_id"] != family_id:
            raise ApprovalNotFound(approval_id)
        if approval["state"] == "EXPIRED":
            raise ApprovalExpired("Is manzoori ka waqt khatam ho gaya; kaam nahi hua.")
        if approval["state"] != "PENDING":
            raise ApprovalAlreadyDecided(f"Approval is already {approval['state']}.")

        txn = self.db.transaction(approval["txn_id"])
        if not txn:
            raise ApprovalNotFound(approval_id)

        if decision == "deny":
            assert_transition(TxnState.AWAITING_APPROVAL, TxnState.CANCELLED)
            self.db.set_transaction_state(txn["id"], TxnState.CANCELLED, reason="child_declined")
            self.db.set_approval_state(approval_id, "DENIED", decided_by=by, channel=channel, at=iso(self.clock.now()))
            self._safe_callback(
                family_id,
                "approval_denied",
                f"Aapne mana kar diya: {txn['resolved_action'].get('description', 'kaam')}. Kuch nahi kiya gaya.",
                txn["id"],
            )
            self.db.audit("child", "approval.denied", {"approval_id": approval_id, "txn_id": txn["id"]})
            self._clear_call_awaiting(family_id, txn["id"])
            return {"status": "denied", "txn": self.db.transaction(txn["id"])}

        cap = self.registry.get(txn["capability"])
        ctx = self._context(txn["family_id"])
        resolved = self._resolved_from_txn(txn)
        try:
            fresh = cap.resolve(resolved.detail.get("slots", {}), ctx)
        except Exception:
            fresh = None
        if fresh is not None and fresh.amount_paise != txn["amount_paise"]:
            assert_transition(TxnState.AWAITING_APPROVAL, TxnState.CANCELLED)
            self.db.set_transaction_state(txn["id"], TxnState.CANCELLED, reason="amount_changed")
            self.db.set_approval_state(approval_id, "STALE", decided_by=by, channel=channel, at=iso(self.clock.now()))
            self._safe_callback(
                family_id,
                "approval_stale",
                "Bill ki rakam badal gayi, isliye purani manzoori se payment nahi hua. Naya bill aayega.",
                txn["id"],
            )
            self.db.audit("system", "approval.stale", {"txn_id": txn["id"]})
            self._clear_call_awaiting(family_id, txn["id"])
            return {"status": "amount_changed", "txn": self.db.transaction(txn["id"])}

        assert_transition(TxnState.AWAITING_APPROVAL, TxnState.APPROVED)
        self.db.set_transaction_state(txn["id"], TxnState.APPROVED)
        assert_transition(TxnState.APPROVED, TxnState.EXECUTING)
        self.db.set_transaction_state(txn["id"], TxnState.EXECUTING)
        result = self._execute(cap, fresh or resolved, ctx, txn["id"])
        self.db.set_approval_state(approval_id, "APPROVED", decided_by=by, channel=channel, at=iso(self.clock.now()))

        if result.ok:
            self.db.set_transaction_state(txn["id"], TxnState.SUCCEEDED, reason="child_approved")
            self._safe_callback(
                family_id,
                "payment_succeeded",
                f"Manzoori ke baad payment ho gaya: {resolved.description}, {speak_amount(txn['amount_paise'] or 0)}.",
                txn["id"],
            )
            self.db.audit("child", "approval.approved", {"txn_id": txn["id"], "approval_id": approval_id})
        else:
            self.db.set_transaction_state(txn["id"], TxnState.FAILED, reason="provider_failed")
            self._safe_callback(
                family_id, "payment_failed",
                "Payment nahi ho paya. Paise nahi kate. Provider ne mana kiya.", txn["id"],
            )
        self._clear_call_awaiting(family_id, txn["id"])
        return {"status": "approved" if result.ok else "failed", "txn": self.db.transaction(txn["id"])}

    # -------------------------------------------------------------------- pause
    def set_paused(self, family_id: str, paused: bool, *, actor: str = "child", channel: str = "console") -> dict[str, Any]:
        limits = self.db.limits(family_id)
        if not limits:
            raise Forbidden("unknown family")
        self.db.update_limits(family_id, paused=paused)
        cancelled = []
        if paused:
            cancelled = self.db.cancel_non_terminal(family_id, reason="family_paused", at=iso(self.clock.now()))
            self._safe_notify_child(family_id, "pause", "Munshi ruk gaya hai. Jab tak aap chalu nahi karte, koi kaam nahi hoga.")
        self.db.audit(
            actor, "family.paused" if paused else "family.resumed",
            {"family_id": family_id, "cancelled": len(cancelled), "channel": channel},
        )
        return {"paused": paused, "cancelled": cancelled}

    # ---------------------------------------------------------------- onboarding
    def parse_limits(self, family_id: str, text: str) -> dict[str, Any]:
        parsed = parse_limits_note(text)
        limits = self.db.limits(family_id)
        if not limits:
            raise Forbidden("unknown family")
        if parsed.needs_clarification or parsed.monthly_rupees is None:
            return {
                "saved": False,
                "parsed": parsed.to_dict(),
                "token": None,
                "requires_second_factor": False,
            }
        monthly_paise = rupees_to_paise(int(parsed.monthly_rupees))
        is_increase = monthly_paise > int(limits["monthly_cap"])
        token = f"lim_{uuid.uuid4().hex[:16]}"
        payload = {
            "capabilities": parsed.capabilities,
            "monthly_paise": monthly_paise,
            "per_txn_paise": rupees_to_paise(int(parsed.per_txn_rupees or parsed.monthly_rupees)),
            "increase": is_increase,
            "readback": parsed.readback,
        }
        self.db.put_pending_limits(token, family_id, payload, iso(self.clock.now()))
        return {
            "saved": False,
            "parsed": parsed.to_dict(),
            "token": token,
            "requires_second_factor": is_increase,
        }

    def confirm_limits(
        self,
        family_id: str,
        token: str,
        *,
        confirmed: bool,
        second_factor: str | None = None,
    ) -> dict[str, Any]:
        pending = self.db.get_pending_limits(token)
        if not pending or pending["family_id"] != family_id:
            raise ApprovalNotFound(token)
        payload = pending["payload"]
        if not confirmed:
            self.db.delete_pending_limits(token)
            return {"saved": False, "reason": "not_confirmed"}
        if payload["increase"] and second_factor != self.settings.demo_second_factor:
            raise SecondFactorRequired("Limit badhane ke liye doosra step chahiye (demo code).")

        limits = self.db.limits(family_id)
        assert limits is not None
        monthly = int(payload["monthly_paise"])
        per_txn = min(int(payload["per_txn_paise"]), monthly)
        allowlist = set(limits["allowlisted_payees"])
        payee_map = {"pay_bill": ["bijli", "paani"], "book_gas_cylinder": ["gas"], "refill_medicine": ["dawai"]}
        for capability in payload["capabilities"]:
            allowlist.update(payee_map.get(capability, []))
        updated = self.db.update_limits(
            family_id,
            monthly_cap=monthly,
            per_txn_cap=per_txn,
            daily_cap=min(int(limits["daily_cap"]), monthly),
            hard_ceiling=monthly,
            capabilities_enabled=payload["capabilities"],
            allowlisted_payees=sorted(allowlist),
        )
        self.db.delete_pending_limits(token)
        self.db.audit(
            "child", "limits.updated",
            {"family_id": family_id, "monthly_cap": monthly, "per_txn_cap": per_txn,
             "capabilities": payload["capabilities"], "second_factor": bool(payload["increase"])},
        )
        return {"saved": True, "limits": self._limits_public(updated)}

    def child_voice_command(self, family_id: str, text: str) -> dict[str, Any]:
        proposal = self.understanding.understand(text, language="auto", context={"channel": "child"})
        norm = (text or "").lower()
        if proposal.intent == "pause" or any(w in norm for w in ("ruko", "ruk jao", "band karo")):
            return {"action": "pause", **self.set_paused(family_id, True, actor="child", channel="voice")}
        if any(w in norm for w in ("chalu", "resume", "shuru karo")):
            return {"action": "resume", **self.set_paused(family_id, False, actor="child", channel="voice")}
        return {"action": "unknown", "message": "Sirf 'Munshi ruk jao' ya 'Munshi chalu karo' samajh aaya."}

    # ------------------------------------------------------------- console view
    def console_snapshot(self, family_id: str) -> dict[str, Any]:
        family = self.db.family(family_id)
        limits = self.db.limits(family_id)
        if not family or not limits:
            raise Forbidden("unknown family")
        self.expire_approvals(family_id)
        users = self.db.users(family_id)
        parent = next((u for u in users if u["role"] == "parent"), None)
        child = next((u for u in users if u["role"] == "child"), None)
        spent_today, spent_month = self._spend(family)
        approvals = self.db.approvals(family_id, limit=12)
        txns = self.db.transactions(family_id, limit=25)
        bills = self.db.list_bills(family_id)
        calls = self.db.list_calls(family_id, limit=8)
        audit = self.db.verify_audit()
        return {
            "family": {"id": family["id"], "name": family["name"], "timezone": family["timezone"]},
            "parent": {"name": parent["display_name"] if parent else "", "masked": ""},
            "child": {"name": child["display_name"] if child else ""},
            "limits": self._limits_public(limits),
            "spend": {
                "today_paise": spent_today,
                "month_paise": spent_month,
                "monthly_remaining_paise": max(0, limits["monthly_cap"] - spent_month),
                "daily_remaining_paise": max(0, limits["daily_cap"] - spent_today),
            },
            "approvals": approvals,
            "ledger": [self._txn_public(t) for t in txns],
            "bills": bills,
            "notifications": self.db.notifications(family_id, limit=20, channel="child_simulator"),
            "callbacks": self.db.notifications(family_id, limit=20, channel="call_callback"),
            "calls": calls,
            "audit": {"ok": audit.ok, "entries": audit.entries, "first_bad_seq": audit.first_bad_seq},
            "modes": {
                "understanding": getattr(self.understanding, "name", "rule-based"),
                "payments": self.payments.mode.value,
                "payments_adapter": self.payments.name,
                "biller": self.biller.name,
                "notifier": self.notifier.name,
            },
        }

    # ---------------------------------------------------------------- internals
    def _understand(self, text: str, meta: dict[str, Any], trace: dict[str, Any]) -> Proposal:
        started = time.perf_counter()
        try:
            proposal = self.understanding.understand(
                text, language=meta.get("lang", "hi"),
                context={"awaiting": meta.get("awaiting"), "channel": "parent"},
            )
        except Exception:
            trace["degraded"] = True
            proposal = Proposal(intent="unclear", confidence=0.0, language_detected="hi")
        trace["stages"].append({"stage": "understand", "ms": round((time.perf_counter() - started) * 1000, 2)})
        trace["proposal"] = proposal.to_dict()
        return proposal

    def _route(self, call: dict[str, Any], meta: dict[str, Any], proposal: Proposal, trace: dict[str, Any]) -> Outcome:
        family_id = call["family_id"]
        lang = meta.get("lang", "hi")
        awaiting = meta.get("awaiting")
        pending_txn = self.db.transaction(meta["pending_txn"]) if meta.get("pending_txn") else None

        if not meta.get("verified", False):
            self.db.audit("gateway", "turn.blocked_unverified", {"call_id": call["id"]})
            return Outcome(
                "Main is number par koi kaam nahi kar sakta. Kripya ghar ke kisi member se baat karein.",
                "REJECT", lang,
            )

        if awaiting == "readback" and pending_txn:
            if proposal.intent == "affirm":
                return self._execute_pending(call, meta, pending_txn, trace)
            if proposal.intent in {"deny", "pause"}:
                assert_transition(TxnState.AWAITING_READBACK, TxnState.CANCELLED)
                self.db.set_transaction_state(pending_txn["id"], TxnState.CANCELLED, reason="parent_declined")
                self.db.audit("parent", "txn.cancelled_by_parent", {"txn_id": pending_txn["id"]})
                meta.update({"awaiting": None, "pending_txn": None})
                return Outcome("Theek hai, nahi kar raha. Kuch aur karna hai?", "REJECT", lang,
                               txn=self.db.transaction(pending_txn["id"]))
            if proposal.intent in {"repeat", "help"}:
                cap = self.registry.get(pending_txn["capability"])
                reply = cap.describe_for_speech(self._resolved_from_txn(pending_txn), lang)
                return Outcome(reply, "CLARIFY", lang, txn=pending_txn)

        if awaiting == "approval" and pending_txn:
            if proposal.intent == "affirm":
                return Outcome(
                    "Beta ka jawab aane ka intezaar hai. Unke haan ke bina payment nahi hoga.",
                    "CLARIFY", lang, txn=pending_txn,
                )
            if proposal.intent in {"deny", "pause"}:
                approval = self.db.approval_for_txn(pending_txn["id"])
                if pending_txn["state"] == TxnState.AWAITING_APPROVAL.value:
                    assert_transition(TxnState.AWAITING_APPROVAL, TxnState.CANCELLED)
                    self.db.set_transaction_state(pending_txn["id"], TxnState.CANCELLED, reason="parent_withdrew")
                    if approval:
                        self.db.set_approval_state(approval["id"], "CANCELLED", decided_by="parent", channel="call",
                                                   at=iso(self.clock.now()))
                    meta.update({"awaiting": None, "pending_txn": None})
                    self._safe_notify_child(family_id, "withdrawn", "Amma ne apna request wapas le liya. Kuch nahi kiya gaya.")
                return Outcome("Theek hai, request wapas le li.", "REJECT", lang,
                               txn=self.db.transaction(pending_txn["id"]))

        if proposal.intent in MONEY_INTENTS:
            lead = ""
            if awaiting == "readback" and pending_txn:
                assert_transition(TxnState.AWAITING_READBACK, TxnState.CANCELLED)
                self.db.set_transaction_state(pending_txn["id"], TxnState.CANCELLED, reason="replaced_by_new_request")
                meta.update({"awaiting": None, "pending_txn": None})
                lead = "Pehla kaam chhod diya. "
            return self._handle_money(call, meta, proposal, trace, lead=lead)
        if proposal.intent == "message_child":
            return self._handle_message(call, meta, proposal, trace)
        if proposal.intent == "unsupported_transfer":
            self._safe_notify_child(
                family_id, "unsupported_request",
                "Amma ne kisi ko paise bhejne ko kaha. Munshi ne mana kar diya; koi payment nahi hua.",
            )
            self.db.audit("parent", "request.unsupported_transfer", {"call_id": call["id"]})
            return Outcome(
                "Main kisi ko paise bhej nahi sakta. Sirf ghar ke bill, gas aur dawai jaise kaam kar sakta hoon. Beta ko bata diya.",
                "REJECT", lang,
            )
        if proposal.intent == "pause":
            return Outcome(
                "Theek hai, main ye kaam nahi kar raha. Beta ko bata deta hoon.",
                "REJECT", lang,
            )
        if proposal.intent == "help":
            return Outcome(
                "Main bijli ka bill, gas cylinder, dawai, aur beta ko message kar sakta hoon. Kya karna hai?",
                "CLARIFY", lang,
            )
        if proposal.intent == "repeat":
            return Outcome(meta.get("last_reply") or "Batayein, kya karna hai?", "CLARIFY", lang)
        if proposal.intent == "affirm":
            return Outcome("Abhi koi kaam pending nahi hai. Batayein, kya karna hai?", "CLARIFY", lang)
        if proposal.intent == "deny":
            return Outcome("Theek hai. Kuch aur karna hai?", "CLARIFY", lang)
        return self._handle_unclear(call, meta, proposal, trace)

    def _handle_money(
        self, call: dict[str, Any], meta: dict[str, Any], proposal: Proposal,
        trace: dict[str, Any], lead: str,
    ) -> Outcome:
        family_id = call["family_id"]
        family = self.db.family(family_id)
        assert family is not None
        limits = self.db.limits(family_id)
        assert limits is not None
        cap = self.registry.get(proposal.intent)
        ctx = self._context(family_id)

        if proposal.needs_clarification:
            count = int(meta.get("clarify_count", 0)) + 1
            question = proposal.clarification_question or "Kya karna hai, thoda saaf bataiye?"
            if count > self.settings.max_clarifications:
                self._safe_notify_child(
                    family_id, "clarify_escalation",
                    "Amma ki baat samajh nahi aayi, isliye kuch nahi kiya. Aap baat kar lijiye.",
                )
                meta.update({"clarify_count": 0, "awaiting": None, "pending_txn": None})
                return Outcome("Main beta ko bata deta hoon. Woh aapko call karega.", "ESCALATE_TO_CHILD", meta.get("lang", "hi"))
            meta.update({"clarify_count": count, "awaiting": None, "pending_txn": None})
            self.db.audit("understanding", "clarification.asked", {"call_id": call["id"], "count": count})
            return Outcome(lead + question, "CLARIFY", meta.get("lang", "hi"))

        try:
            resolved = cap.resolve(proposal.slots, ctx)
        except BillNotFound:
            self._safe_notify_child(family_id, "bill_missing", "Amma ne bill ke liye kaha, par koi unpaid bill nahi mila.")
            self.db.audit("action", "resolve.failed", {"capability": cap.name, "reason": "bill_not_found"})
            return Outcome("Abhi koi bill nahi mil raha. Beta ko bata diya.", "REJECT", meta.get("lang", "hi"))
        except Exception as exc:
            trace["degraded"] = True
            self.db.audit("action", "resolve.failed", {"capability": cap.name, "reason": type(exc).__name__})
            return Outcome("Abhi ye kaam nahi ho payega. Beta ko bata diya.", "REJECT", meta.get("lang", "hi"))

        trace["resolved"] = {
            "capability": resolved.capability, "amount_paise": resolved.amount_paise,
            "payee": resolved.payee, "description": resolved.description,
        }
        spent_today, spent_month = self._spend(family)
        request = PolicyRequest(
            caller_verified=bool(meta.get("verified", True)),
            paused=bool(limits["paused"]),
            capability=cap.name,
            capability_enabled=cap.name in limits["capabilities_enabled"],
            intent_confidence=proposal.confidence,
            confidence_threshold=self.settings.confidence_threshold,
            clarification_count=int(meta.get("clarify_count", 0)),
            max_clarifications=self.settings.max_clarifications,
            amount_paise=resolved.amount_paise if resolved.amount_paise is not None else 0,
            payee=resolved.payee,
            allowlisted_payees=tuple(limits["allowlisted_payees"]),
            per_txn_cap=int(limits["per_txn_cap"]),
            hard_ceiling=int(limits["hard_ceiling"]),
            daily_cap=int(limits["daily_cap"]),
            monthly_cap=int(limits["monthly_cap"]),
            spent_today=spent_today,
            spent_this_month=spent_month,
            duplicate=self._recent_duplicate(
                family_id, call["id"], cap.name, resolved.payee, resolved.amount_paise
            ),
            requires_money=cap.requires_money,
        )
        result: PolicyResult = evaluate(request)
        trace["policy"] = {
            "decision": result.decision.value, "rule": result.rule, "reason": result.reason,
            "input": {
                "amount_paise": request.amount_paise, "payee": request.payee,
                "spent_today": spent_today, "spent_this_month": spent_month,
                "per_txn_cap": request.per_txn_cap, "daily_cap": request.daily_cap,
                "monthly_cap": request.monthly_cap, "hard_ceiling": request.hard_ceiling,
                "confidence": round(proposal.confidence, 3),
            },
        }
        self.db.audit(
            "policy", "policy.decision",
            {"call_id": call["id"], "capability": cap.name, "decision": result.decision.value,
             "rule": result.rule, "amount_paise": request.amount_paise, "payee": request.payee},
        )
        mode = self.payments.mode if cap.name == "pay_bill" else cap.mode
        lang = meta.get("lang", "hi")

        if result.decision is Decision.NO_OP:
            return Outcome("Ye kaam abhi ho chuka hai, dobara nahi karunga.", "NO_OP", lang)

        if result.decision is Decision.CLARIFY:
            count = int(meta.get("clarify_count", 0)) + 1
            if count > self.settings.max_clarifications:
                self._safe_notify_child(
                    family_id, "clarify_escalation",
                    "Amma ki baat samajh nahi aayi, isliye kuch nahi kiya.",
                )
                meta.update({"clarify_count": 0, "awaiting": None, "pending_txn": None})
                return Outcome("Main beta ko bata deta hoon. Woh aapko call karega.", "ESCALATE_TO_CHILD", lang)
            txn = self._create_txn(call, resolved, TxnState.NEEDS_CLARIFICATION, mode, result.rule)
            meta.update({"clarify_count": count, "awaiting": None, "pending_txn": None})
            return Outcome(lead + "Kaunsa bill bharna hai — bijli, paani ya mobile?", "CLARIFY", lang, txn=txn)

        if result.decision is Decision.REJECT:
            txn = self._create_txn(call, resolved, TxnState.REJECTED, mode, result.rule)
            replies = {
                "P-SYSTEM-PAUSED": "Abhi Munshi ruka hua hai. Beta se baat kar lijiye. Kuch nahi kiya.",
                "P-CAPABILITY-DISABLED": "Ye kaam abhi band hai. Beta ko bata diya.",
                "P-HARD-CEILING": "Ye rakam limit se zyada hai. Main itna nahi kar sakta. Beta se baat karein.",
            }
            reply = replies.get(result.rule, "Ye kaam nahi ho sakta. Beta ko bata diya.")
            if result.rule != "P-SYSTEM-PAUSED":
                self._safe_notify_child(
                    family_id, "blocked",
                    f"Amma ne {resolved.description} ke liye kaha, par niyam ne roka ({result.rule}). Kuch nahi hua.",
                    txn["id"],
                )
            return Outcome(lead + reply, "REJECT", lang, txn=txn)

        if result.decision in {Decision.REQUIRE_CHILD_APPROVAL, Decision.ESCALATE_TO_CHILD}:
            txn = self._create_txn(call, resolved, TxnState.AWAITING_APPROVAL, mode, result.rule)
            approval = self.db.create_approval(
                txn_id=txn["id"], family_id=family_id,
                summary=self._approval_summary(resolved, lang),
                requested_at=iso(self.clock.now()),
                expires_at=iso(self.clock.now() + timedelta(seconds=self.settings.approval_ttl_seconds)),
            )
            meta.update({"awaiting": "approval", "pending_txn": txn["id"], "clarify_count": 0})
            self._safe_notify_child(
                family_id, "approval_request",
                f"Manzoori chahiye: Amma ne {resolved.description} ke liye kaha — {speak_amount(resolved.amount_paise or 0)}. Haan ya na boliye.",
                txn["id"],
            )
            self.db.audit("approval", "approval.requested", {"approval_id": approval["id"], "txn_id": txn["id"]})
            return Outcome(
                lead + f"{resolved.description}, {speak_amount(resolved.amount_paise or 0)}. "
                "Ye naya kaam hai, isliye beta se puchh rahi hoon. Thodi der mein bataungi.",
                "REQUIRE_CHILD_APPROVAL", lang, txn=txn, approval=approval,
            )

        # AUTO_EXECUTE
        txn = self._create_txn(call, resolved, TxnState.AWAITING_READBACK, mode, result.rule)
        meta.update({"awaiting": "readback", "pending_txn": txn["id"], "clarify_count": 0})
        self.db.audit("txn", "txn.readback", {"txn_id": txn["id"], "amount_paise": resolved.amount_paise})
        return Outcome(lead + cap.describe_for_speech(resolved, lang), "AUTO_EXECUTE", lang, txn=txn)

    def _handle_message(self, call: dict[str, Any], meta: dict[str, Any], proposal: Proposal, trace: dict[str, Any]) -> Outcome:
        family_id = call["family_id"]
        limits = self.db.limits(family_id)
        assert limits is not None
        cap = self.registry.get("message_child")
        ctx = self._context(family_id)
        resolved = cap.resolve(proposal.slots, ctx)
        request = PolicyRequest(
            caller_verified=bool(meta.get("verified", True)), paused=bool(limits["paused"]),
            capability=cap.name, capability_enabled=cap.name in limits["capabilities_enabled"],
            intent_confidence=proposal.confidence, confidence_threshold=self.settings.confidence_threshold,
            clarification_count=int(meta.get("clarify_count", 0)), max_clarifications=self.settings.max_clarifications,
            amount_paise=0, payee=None, allowlisted_payees=tuple(limits["allowlisted_payees"]),
            per_txn_cap=0, hard_ceiling=0, daily_cap=0, monthly_cap=0, spent_today=0, spent_this_month=0,
            requires_money=False,
        )
        result = evaluate(request)
        trace["policy"] = {"decision": result.decision.value, "rule": result.rule, "reason": result.reason}
        if result.decision is not Decision.AUTO_EXECUTE:
            reply = "Abhi message nahi bhej sakta. Beta se baat kar lijiye."
            return Outcome(reply, result.decision.value, meta.get("lang", "hi"))
        execution = self._execute(cap, resolved, ctx, f"msg_{uuid.uuid4().hex}")
        meta.update({"clarify_count": 0})
        if execution.ok:
            return Outcome("Beta ko bata diya.", "AUTO_EXECUTE", meta.get("lang", "hi"))
        return Outcome("Message nahi ja paya. Beta ko baad mein bata denge.", "REJECT", meta.get("lang", "hi"))

    def _handle_unclear(self, call: dict[str, Any], meta: dict[str, Any], proposal: Proposal, trace: dict[str, Any]) -> Outcome:
        count = int(meta.get("clarify_count", 0)) + 1
        if count <= self.settings.max_clarifications:
            meta.update({"clarify_count": count})
            question = proposal.clarification_question or "Samajh nahi aaya. Kaunsa kaam — bijli bill, gas, ya dawai?"
            return Outcome(question, "CLARIFY", meta.get("lang", "hi"))
        self._safe_notify_child(
            call["family_id"], "clarify_escalation",
            "Amma ki baat do baar samajh nahi aayi, isliye kuch nahi kiya. Aap baat kar lijiye.",
        )
        meta.update({"clarify_count": 0, "awaiting": None, "pending_txn": None})
        return Outcome("Main beta ko bata deta hoon. Woh aapko call karega.", "ESCALATE_TO_CHILD", meta.get("lang", "hi"))

    def _handle_silence(self, call: dict[str, Any], meta: dict[str, Any], idx: int, text: str) -> Outcome:
        call_id = call["id"]
        meta["silence"] = int(meta.get("silence", 0)) + 1
        if meta["silence"] == 1:
            if meta.get("awaiting") == "readback" and meta.get("pending_txn"):
                txn = self.db.transaction(meta["pending_txn"])
                if txn:
                    cap = self.registry.get(txn["capability"])
                    reply = "Aap wahan hain? " + cap.describe_for_speech(self._resolved_from_txn(txn), meta.get("lang", "hi"))
                else:
                    reply = "Aap wahan hain? Kya karna hai?"
            else:
                reply = "Aap wahan hain? Kya karna hai?"
            self.db.update_call(call_id, meta=meta)
            self._save_turn(call_id, idx, text, 0.0, Proposal("unclear"), "CLARIFY", reply,
                            {"stages": [], "degraded": False, "policy": None, "silence": True})
            return Outcome(reply, "CLARIFY", meta.get("lang", "hi"))
        reply = self._close_call(call, meta, "Theek hai, main baad mein baat karta hoon. Namaste.")
        self._save_turn(call_id, idx, text, 0.0, Proposal("unclear"), "REJECT", reply,
                        {"stages": [], "degraded": False, "policy": None, "silence": True})
        return Outcome(reply, "REJECT", meta.get("lang", "hi"), done=True)

    def _execute_pending(
        self, call: dict[str, Any], meta: dict[str, Any], txn: dict[str, Any], trace: dict[str, Any]
    ) -> Outcome:
        lang = meta.get("lang", "hi")
        if txn["state"] != TxnState.AWAITING_READBACK.value:
            return Outcome("Ye kaam abhi pending nahi hai.", "REJECT", lang, txn=txn)

        cap = self.registry.get(txn["capability"])
        ctx = self._context(txn["family_id"])
        stored = self._resolved_from_txn(txn)
        try:
            fresh = cap.resolve(stored.detail.get("slots", {}), ctx)
        except Exception:
            fresh = None

        if fresh is not None and fresh.amount_paise != txn["amount_paise"]:
            assert_transition(TxnState.AWAITING_READBACK, TxnState.CANCELLED)
            self.db.set_transaction_state(txn["id"], TxnState.CANCELLED, reason="amount_changed")
            new_txn = self._create_txn(
                call, fresh, TxnState.AWAITING_READBACK, Mode(txn["mode"]), "M-AMOUNT-CHANGED"
            )
            meta.update({"awaiting": "readback", "pending_txn": new_txn["id"]})
            self.db.audit("system", "readback.amount_changed", {"old_txn": txn["id"], "new_txn": new_txn["id"]})
            return Outcome(
                f"Bill badal gaya hai. Ab {cap.describe_for_speech(fresh, lang)}",
                "CLARIFY", lang, txn=new_txn,
            )

        assert_transition(TxnState.AWAITING_READBACK, TxnState.APPROVED)
        self.db.set_transaction_state(txn["id"], TxnState.APPROVED)
        assert_transition(TxnState.APPROVED, TxnState.EXECUTING)
        self.db.set_transaction_state(txn["id"], TxnState.EXECUTING)
        result = self._execute(cap, fresh or stored, ctx, txn["id"])

        trace["execution"] = {
            "txn_id": txn["id"], "state": "SUCCEEDED" if result.ok else "FAILED",
            "amount_paise": txn["amount_paise"], "reference": result.reference,
        }
        if result.ok:
            self.db.set_transaction_state(txn["id"], TxnState.SUCCEEDED, reason="readback_confirmed")
            meta.update({"awaiting": None, "pending_txn": None, "clarify_count": 0})
            amount = speak_amount(txn["amount_paise"] or 0, lang)
            self._safe_notify_child(
                txn["family_id"], "payment_succeeded",
                f"Ho gaya: {stored.description}, {amount}. Reference {result.reference}.",
                txn["id"],
            )
            self.db.audit("payment", "payment.succeeded", {"txn_id": txn["id"], "reference": result.reference})
            return Outcome(
                f"Ho gaya. {stored.description} {amount} bhar diya. Beta ko bata diya.",
                "AUTO_EXECUTE", lang, txn=self.db.transaction(txn["id"]),
            )

        self.db.set_transaction_state(txn["id"], TxnState.FAILED, reason="provider_failed")
        meta.update({"awaiting": None, "pending_txn": None})
        self._safe_notify_child(
            txn["family_id"], "payment_failed",
            "Payment nahi ho paya. Paise nahi kate. Beta ko bata diya.", txn["id"],
        )
        self.db.audit("payment", "payment.failed", {"txn_id": txn["id"]})
        return Outcome(
            "Payment nahi ho paya. Paise nahi kate. Beta ko bata diya.",
            "REJECT", lang, txn=self.db.transaction(txn["id"]),
        )

    def _execute(self, cap, resolved: ResolvedAction, ctx: CapabilityContext, idempotency_key: str) -> ExecutionResult:
        try:
            return cap.execute(resolved, ctx=ctx, idempotency_key=f"{idempotency_key}:execute")
        except Exception as exc:
            return ExecutionResult(ok=False, reference=f"ERR-{type(exc).__name__}", message=str(exc), mode=cap.mode)

    def _create_txn(
        self, call: dict[str, Any], resolved: ResolvedAction, state: TxnState, mode: Mode, reason: str
    ) -> dict[str, Any]:
        txn = self.db.create_transaction(
            family_id=call["family_id"],
            call_id=call["id"],
            idempotency_key=f"txn:{uuid.uuid4().hex}",
            capability=resolved.capability,
            resolved_action={
                "capability": resolved.capability,
                "description": resolved.description,
                "amount_paise": resolved.amount_paise,
                "payee": resolved.payee,
                "detail": resolved.detail,
            },
            amount_paise=resolved.amount_paise,
            state=state,
            mode=mode.value,
            reason=reason,
            created_at=iso(self.clock.now()),
        )
        self.db.audit("engine", f"txn.{state.value.lower()}", {"txn_id": txn["id"], "capability": resolved.capability})
        return txn

    def _close_call(self, call: dict[str, Any], meta: dict[str, Any], reply: str) -> str:
        self.db.update_call(call["id"], status="ended", ended_at=iso(self.clock.now()), meta=meta)
        self.db.audit("gateway", "call.ended", {"call_id": call["id"], "reason": "max_turns_or_silence"})
        return reply

    def _save_turn(
        self, call_id: str, idx: int, text: str, confidence: float,
        proposal: Proposal, decision: str, reply: str, trace: dict[str, Any],
    ) -> None:
        self.db.add_turn(
            call_id, idx, text, confidence, proposal.to_dict(), decision, reply, trace,
            iso(self.clock.now()),
        )

    def _context(self, family_id: str) -> CapabilityContext:
        family = self.db.family(family_id)
        assert family is not None
        return CapabilityContext(
            family_id=family_id, family_name=family["name"], db=self.db,
            biller=self.biller, payments=self.payments, notifier=self.notifier,
            language="hi", now=iso(self.clock.now()),
        )

    def _resolved_from_txn(self, txn: dict[str, Any]) -> ResolvedAction:
        data = txn["resolved_action"]
        return ResolvedAction(
            capability=data["capability"],
            description=data["description"],
            amount_paise=data.get("amount_paise"),
            payee=data.get("payee"),
            detail=data.get("detail") or {},
        )

    def _spend(self, family: dict[str, Any]) -> tuple[int, int]:
        tz = ZoneInfo(family.get("timezone") or self.settings.monthly_timezone)
        local_now = self.clock.now().astimezone(tz)
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        end = iso(local_now + timedelta(seconds=1))
        today = self.db.spend_between(family["id"], iso(day_start.astimezone(timezone.utc)), end)
        month = self.db.spend_between(family["id"], iso(month_start.astimezone(timezone.utc)), end)
        return today, month

    def _recent_duplicate(
        self, family_id: str, call_id: str, capability: str, payee: str | None, amount: int | None
    ) -> bool:
        """Replay guard inside one call only. Separate calls are separate requests."""
        cutoff = self.clock.now() - timedelta(seconds=60)
        for txn in self.db.transactions(family_id, states=[TxnState.SUCCEEDED], limit=20):
            if txn.get("call_id") != call_id:
                continue
            if txn["capability"] != capability or txn["amount_paise"] != amount:
                continue
            resolved = txn["resolved_action"]
            if resolved.get("payee") != payee:
                continue
            if parse_iso(txn["updated_at"]) >= cutoff:
                return True
        return False

    def _approval_summary(self, resolved: ResolvedAction, lang: str) -> str:
        amount = speak_amount(resolved.amount_paise or 0, lang)
        return f"Amma ne {resolved.description} ke liye kaha — {amount}."

    def _limits_public(self, limits: dict[str, Any]) -> dict[str, Any]:
        return {
            "per_txn_cap_paise": limits["per_txn_cap"],
            "daily_cap_paise": limits["daily_cap"],
            "monthly_cap_paise": limits["monthly_cap"],
            "hard_ceiling_paise": limits["hard_ceiling"],
            "capabilities_enabled": limits["capabilities_enabled"],
            "allowlisted_payees": limits["allowlisted_payees"],
            "paused": limits["paused"],
            "updated_at": limits["updated_at"],
        }

    @staticmethod
    def _txn_public(txn: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": txn["id"], "capability": txn["capability"],
            "description": txn["resolved_action"].get("description"),
            "amount_paise": txn["amount_paise"], "state": txn["state"],
            "mode": txn["mode"], "reason": txn["reason"], "created_at": txn["created_at"],
            "payee": txn["resolved_action"].get("payee"),
        }

    # ------------------------------------------------------------ safe helpers
    def _clear_call_awaiting(self, family_id: str, txn_id: str) -> None:
        """An approval decided outside the call must not leave the parent waiting."""
        active = self.db.active_call(family_id)
        if active and active["meta"].get("pending_txn") == txn_id:
            meta = dict(active["meta"])
            meta["awaiting"] = None
            meta["pending_txn"] = None
            self.db.update_call(active["id"], meta=meta)

    def _safe_notify_child(self, family_id: str, kind: str, body: str, related_txn: str | None = None) -> bool:
        try:
            self.notifier.notify_child(family_id=family_id, kind=kind, body=body, related_txn=related_txn)
            return True
        except Exception:
            self.db.audit("notifier", "notify.degraded", {"family_id": family_id, "kind": kind})
            return False

    def _safe_callback(self, family_id: str, kind: str, body: str, related_txn: str | None = None) -> bool:
        try:
            self.notifier.notify_callback(family_id=family_id, kind=kind, body=body, related_txn=related_txn)
            return True
        except Exception:
            self.db.audit("notifier", "callback.degraded", {"family_id": family_id, "kind": kind})
            return False
