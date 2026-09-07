"""Gemini client wrapper with a deterministic mock fallback.

If ``settings.gemini_api_key`` is empty, ``generate_json`` returns a canned,
schema-shaped response so the whole system runs offline (tests, CI, demos
without a key).
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings


class LLMUnavailable(RuntimeError):
    pass


async def generate_json(
    *,
    system: str,
    prompt: str,
    schema_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask the model for a single JSON object. Returns a parsed dict.

    Real impl: call google-genai with response_mime_type="application/json",
    model = settings.gemini_model. Retry once on parse failure.
    """
    if not settings.llm_enabled:
        return _mock_response(prompt)

    # TODO(scaffold): real Gemini call.
    #   from google import genai
    #   client = genai.Client(api_key=settings.gemini_api_key)
    #   resp = await asyncio.to_thread(client.models.generate_content, ...)
    #   return json.loads(resp.text)
    raise NotImplementedError("scaffold: generate_json (Gemini path)")


def _mock_response(prompt: str) -> dict[str, Any]:
    """Cheap, deterministic stand-in used when no API key is configured."""
    low = prompt.lower()
    if "classify" in low:
        important = any(k in low for k in ("failed", "delayed", "refund", "unknown"))
        return {
            "wake_now": important,
            "importance": "high" if important else "low",
            "reason": "mock classifier: keyword match" if important else "mock: routine event",
        }
    if "final" in low or "end-of-run" in low:
        return {
            "summary": "mock final summary",
            "important_actions": [],
            "key_learnings": ["mock learning"],
            "feedback": ["mock feedback"],
        }
    return {
        "acted": False,
        "actions": [],
        "reasoning": "mock agent: nothing to do, going back to sleep",
        "memory_summary": "mock rolling summary",
        "wakeup_guidance": "wake on payment_failed, shipment_delayed, refund_requested, unknown events",
        "next_sleep_seconds": settings.default_wake_interval_minutes * 60,
        "recommend_completion": False,
    }


def _loads(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - scaffold
        raise LLMUnavailable(f"model did not return valid JSON: {exc}") from exc
