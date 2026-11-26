"""Real-adapter stubs.

No vendor API shape is assumed here. These exist so the interface is real and a
credentialed adapter can be dropped in without touching the core. Until a
verified credential and documented request contract exist, they refuse to run
rather than silently mock real money.
"""

from __future__ import annotations

from ..domain import ExecutionResult, Mode
from ..ports import Bill, NotConfigured, Transcript


class CashfreePayments:
    name = "cashfree-sandbox"
    mode = Mode.SANDBOX
    doc_url = "https://docs.cashfree.com/"

    def charge(self, **_: object) -> ExecutionResult:
        raise NotConfigured(
            "Cashfree adapter is not configured. Access terms and the current MCP/wallet "
            "contract must be verified from Cashfree docs before use; the demo uses MockLedger."
        )


class TelegramNotifier:
    name = "telegram"
    doc_url = "https://core.telegram.org/bots/api"

    def notify_child(self, **_: object) -> str:
        raise NotConfigured("Telegram bot token is not configured; using the simulator inbox.")

    def notify_callback(self, **_: object) -> str:
        raise NotConfigured("Telegram bot token is not configured; using the simulator inbox.")


class SarvamASR:
    name = "sarvam-asr"

    def transcribe(self, audio_ref: str, language: str = "hi") -> Transcript:
        raise NotConfigured("ASR provider is not configured; the browser handles ASR in the demo.")


class SarvamTTS:
    name = "sarvam-tts"

    def speak(self, text: str, language: str = "hi") -> str:
        raise NotConfigured("TTS provider is not configured; the browser handles TTS in the demo.")


class CashfreeBiller:
    """Placeholder so nobody mistakes the fake biller for a live biller API."""

    name = "cashfree-biller"

    def fetch_due(self, family_id: str, biller: str) -> Bill:
        raise NotConfigured("No verified biller API is configured; bills come from synthetic fixtures.")

    def mark_paid(self, family_id: str, biller: str) -> None:
        raise NotConfigured("No verified biller API is configured; bills come from synthetic fixtures.")
