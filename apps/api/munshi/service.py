"""FastAPI surface: call gateway, family console, judge trace, webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .clock import Clock, SystemClock, iso
from .config import Settings
from .db import Database
from .domain import TxnState
from .errors import MunshiError
from .orchestrator import Orchestrator


class StartCallIn(BaseModel):
    caller_number: str | None = Field(default=None, max_length=20)


class TurnIn(BaseModel):
    text: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(default=0.9, ge=0, le=1)
    silence: bool = False
    interrupt: bool = False


class DtmfIn(BaseModel):
    key: str = Field(min_length=1, max_length=2)


class ApprovalIn(BaseModel):
    decision: str = Field(pattern="^(approve|deny)$")


class VoiceIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class PauseIn(BaseModel):
    paused: bool


class LimitsIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ConfirmLimitsIn(BaseModel):
    token: str = Field(min_length=4, max_length=80)
    confirmed: bool = True
    second_factor: str | None = Field(default=None, max_length=20)


def _verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


def create_app(
    *,
    db: Database | None = None,
    clock: Clock | None = None,
    settings: Settings | None = None,
    orchestrator: Orchestrator | None = None,
) -> FastAPI:
    clock = clock or SystemClock()
    db = db or Database(clock=clock)
    settings = settings or Settings()
    orchestrator = orchestrator or Orchestrator(db, clock=clock, settings=settings)

    app = FastAPI(title="Munshi API", version="0.1.0")
    app.state.db = db
    app.state.clock = clock
    app.state.settings = settings
    app.state.orchestrator = orchestrator

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(MunshiError)
    async def munshi_error(_: Request, exc: MunshiError) -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content={"error": type(exc).__name__, "detail": str(exc)})

    def family_or_401(token: str | None) -> dict[str, Any]:
        if not token:
            raise HTTPException(status_code=401, detail="Missing X-Munshi-Token")
        family = db.family_by_token(token)
        if not family:
            raise HTTPException(status_code=401, detail="Unknown console token")
        return family

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "munshi-api",
            "payments_adapter": orchestrator.payments.name,
            "payments_mode": orchestrator.payments.mode.value,
            "understanding": getattr(orchestrator.understanding, "name", "rule-based"),
            "audit_ok": db.verify_audit().ok,
        }

    @app.post("/api/calls/start")
    def start_call(payload: StartCallIn) -> dict[str, Any]:
        return orchestrator.start_call(payload.caller_number)

    @app.post("/api/calls/{call_id}/turn")
    def turn(call_id: str, payload: TurnIn) -> dict[str, Any]:
        outcome = orchestrator.handle_turn(
            call_id, payload.text, asr_confidence=payload.confidence,
            silence=payload.silence, interrupt=payload.interrupt,
        )
        return {
            "call_id": call_id,
            "reply": outcome.reply,
            "lang": outcome.lang,
            "decision": outcome.decision,
            "trace": outcome.trace,
            "txn": orchestrator._txn_public(outcome.txn) if outcome.txn else None,
            "approval": outcome.approval,
            "done": outcome.done,
        }

    @app.post("/api/calls/{call_id}/dtmf")
    def dtmf(call_id: str, payload: DtmfIn) -> dict[str, Any]:
        mapping = {"1": "haan", "2": "nahi", "*": "phir bolo"}
        text = mapping.get(payload.key)
        if text is None:
            raise HTTPException(status_code=422, detail="Unsupported key")
        outcome = orchestrator.handle_turn(call_id, text)
        return {
            "call_id": call_id, "reply": outcome.reply, "lang": outcome.lang,
            "decision": outcome.decision, "trace": outcome.trace,
            "txn": orchestrator._txn_public(outcome.txn) if outcome.txn else None,
            "approval": outcome.approval, "done": outcome.done,
        }

    @app.post("/api/calls/{call_id}/end")
    def end_call(call_id: str) -> dict[str, Any]:
        return orchestrator.end_call(call_id)

    @app.get("/api/console/bootstrap")
    def bootstrap(request: Request, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        snapshot = orchestrator.console_snapshot(family["id"])
        snapshot["modes"]["asr"] = "browser-live"
        snapshot["modes"]["tts"] = "browser-live"
        return snapshot

    @app.post("/api/console/approvals/{approval_id}")
    def decide(
        approval_id: str, payload: ApprovalIn,
        x_munshi_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        result = orchestrator.decide_approval(
            approval_id, payload.decision, family_id=family["id"], by="child", channel="console",
        )
        result["txn"] = orchestrator._txn_public(result["txn"]) if result.get("txn") else None
        return result

    @app.post("/api/console/approvals/{approval_id}/voice")
    def decide_voice(
        approval_id: str, payload: VoiceIn,
        x_munshi_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        proposal = orchestrator.understanding.understand(payload.text, context={"channel": "child"})
        if proposal.intent == "affirm":
            decision = "approve"
        elif proposal.intent in {"deny", "pause"}:
            decision = "deny"
        else:
            raise HTTPException(status_code=422, detail="Samajh nahi aaya: haan ya na boliye")
        result = orchestrator.decide_approval(
            approval_id, decision, family_id=family["id"], by="child", channel="voice",
        )
        result["txn"] = orchestrator._txn_public(result["txn"]) if result.get("txn") else None
        return result

    @app.post("/api/console/pause")
    def pause(payload: PauseIn, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        return orchestrator.set_paused(family["id"], payload.paused)

    @app.post("/api/console/pause/voice")
    def pause_voice(payload: VoiceIn, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        return orchestrator.child_voice_command(family["id"], payload.text)

    @app.post("/api/console/limits/parse")
    def limits_parse(payload: LimitsIn, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        return orchestrator.parse_limits(family["id"], payload.text)

    @app.post("/api/console/limits/confirm")
    def limits_confirm(payload: ConfirmLimitsIn, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        return orchestrator.confirm_limits(
            family["id"], payload.token, confirmed=payload.confirmed, second_factor=payload.second_factor,
        )

    @app.get("/api/calls")
    def list_calls(x_munshi_token: str | None = Header(default=None), limit: int = 12) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        calls = db.list_calls(family["id"], limit=max(1, min(limit, 50)))
        for call in calls:
            call["turns"] = db.turns(call["id"])
        return {"calls": calls}

    @app.get("/api/calls/{call_id}/trace")
    def trace(call_id: str, x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family = family_or_401(x_munshi_token)
        call = db.call(call_id)
        if not call or call["family_id"] != family["id"]:
            raise HTTPException(status_code=404, detail="Call not found")
        audit = db.verify_audit()
        return {
            "call": call,
            "turns": db.turns(call_id),
            "audit": {"ok": audit.ok, "entries": audit.entries, "first_bad_seq": audit.first_bad_seq},
            "audit_rows": db.audit_rows()[-40:],
        }

    @app.get("/api/audit")
    def audit(x_munshi_token: str | None = Header(default=None)) -> dict[str, Any]:
        family_or_401(x_munshi_token)
        status = db.verify_audit()
        return {
            "ok": status.ok, "entries": status.entries, "first_bad_seq": status.first_bad_seq,
            "rows": db.audit_rows()[-80:],
        }

    @app.post("/api/webhooks/payments")
    async def payments_webhook(
        request: Request,
        x_munshi_signature: str | None = Header(default=None),
    ) -> dict[str, Any]:
        raw = await request.body()
        if not _verify_signature(settings.webhook_secret, raw, x_munshi_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        try:
            payload = json.loads(raw.decode("utf-8"))
            event_id = str(payload["event_id"])
            txn_id = str(payload.get("txn_id", ""))
            event = str(payload.get("event", ""))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(status_code=422, detail="Malformed webhook payload") from None

        fresh = db.record_webhook_event(event_id, iso(clock.now()))
        db.audit("webhook", "webhook.received", {"event_id": event_id, "event": event, "fresh": fresh})
        if not fresh:
            return {"status": "duplicate", "event_id": event_id}

        txn = db.transaction(txn_id) if txn_id else None
        if txn and event == "payment.settled" and txn["state"] == TxnState.EXECUTING.value:
            db.set_transaction_state(txn_id, TxnState.SUCCEEDED, reason="webhook_settled")
        return {"status": "accepted", "event_id": event_id}

    @app.post("/api/demo/reset")
    def demo_reset() -> dict[str, Any]:
        started = time.perf_counter()
        db.reset()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"ok": True, "reset_ms": elapsed_ms}

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("munshi.service:app", host="127.0.0.1", port=8000, reload=False)
