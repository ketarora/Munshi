"""Understanding adapters: schema guard plus an optional LLM adapter.

The schema guard is the contract: any adapter output that does not validate is
downgraded to ``unclear``. The LLM never decides, it only proposes.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import jsonschema

from ..domain import Proposal
from ..ports import NotConfigured

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "proposal.schema.json"
)


def load_schema() -> dict[str, Any]:
    if _SCHEMA_PATH.exists():
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    # Fallback used only if the monorepo contract is missing.
    return {
        "type": "object",
        "required": ["intent", "slots", "confidence", "language_detected"],
        "properties": {
            "intent": {"type": "string"},
            "slots": {"type": "object"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "language_detected": {"type": "string"},
        },
        "additionalProperties": False,
    }


class SchemaGuardedUnderstanding:
    name = "schema-guarded"

    def __init__(self, inner: Any, schema: dict[str, Any] | None = None) -> None:
        self.inner = inner
        self.schema = schema or load_schema()
        self.validator = jsonschema.Draft202012Validator(self.schema)

    def understand(
        self, text: str, language: str = "auto", context: dict[str, Any] | None = None
    ) -> Proposal:
        try:
            raw = self.inner.understand(text, language=language, context=context)
        except NotConfigured:
            raise
        except Exception:
            return Proposal(intent="unclear", confidence=0.0, language_detected="hi")

        data = raw.to_dict() if isinstance(raw, Proposal) else raw
        try:
            self.validator.validate(data)
        except jsonschema.ValidationError:
            return Proposal(intent="unclear", confidence=0.0, language_detected="hi")
        return Proposal(**data)


class AnthropicUnderstanding:
    """Optional LLM adapter.

    Disabled by default: it requires ``ANTHROPIC_API_KEY`` and ``MUNSHI_LLM_MODEL``.
    The request shape below follows the public Messages API; verify it against
    current docs before enabling in production. Any failure is downgraded to
    ``unclear`` by the schema guard.
    """

    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("MUNSHI_LLM_MODEL")

    def understand(
        self, text: str, language: str = "auto", context: dict[str, Any] | None = None
    ) -> Proposal:
        if not self.api_key or not self.model:
            raise NotConfigured("ANTHROPIC_API_KEY and MUNSHI_LLM_MODEL are required for the LLM adapter.")

        prompt = (
            "Extract a Munshi voice-command proposal. Return ONLY JSON with keys intent, slots, "
            "confidence, language_detected. Allowed intents: pay_bill, book_gas_cylinder, "
            "refill_medicine, message_child, affirm, deny, repeat, help, pause, "
            "unsupported_transfer, unclear. Never invent amounts for money intents.\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=False)}\n"
            f"Utterance: {text}"
        )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310 - fixed host
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["content"][0]["text"]
        start, end = content.find("{"), content.rfind("}")
        data = json.loads(content[start : end + 1])
        return Proposal(
            intent=data.get("intent", "unclear"),
            slots=data.get("slots") or {},
            confidence=float(data.get("confidence", 0)),
            language_detected=data.get("language_detected", "hi"),
        )
