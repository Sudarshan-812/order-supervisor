"""Gemini client wrapper with a deterministic mock fallback.

`generate_json` asks the model for exactly one JSON object and returns it parsed.
If ``settings.gemini_api_key`` is empty it returns a canned, schema-shaped
response so the whole system runs offline (tests, CI, demos without a key).

Raw API only - no LangChain / no LlamaIndex.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal

from app.config import settings

Kind = Literal["classifier", "agent", "final"]

# HTTP statuses worth retrying (rate limit / transient server issues).
_TRANSIENT = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


async def generate_json(*, system: str, prompt: str, kind: Kind) -> dict[str, Any]:
    """Return a single parsed JSON object from the model (or the mock)."""
    if not settings.llm_enabled:
        return _mock_response(kind, prompt)
    return await _gemini_json(system=system, prompt=prompt)


# --------------------------------------------------------------------------- #
# Real Gemini path
# --------------------------------------------------------------------------- #
async def _gemini_json(*, system: str, prompt: str) -> dict[str, Any]:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0.2,
    )

    last_err: Exception | None = None
    for attempt in range(4):
        contents = prompt if last_err is None else (
            prompt + "\n\nYour previous reply was not valid JSON. "
            "Return ONLY the JSON object, no prose, no code fences."
        )
        try:
            resp = await client.aio.models.generate_content(
                model=settings.gemini_model, contents=contents, config=cfg
            )
            return _loads(resp.text or "")
        except genai_errors.APIError as exc:
            if getattr(exc, "code", None) not in _TRANSIENT or attempt == 3:
                raise LLMError(f"Gemini API error: {exc}") from exc
            last_err = None  # transient - retry the same prompt
            await asyncio.sleep(2 * (attempt + 1))
        except LLMError as exc:
            last_err = exc
            if attempt == 3:
                raise LLMError(f"Gemini returned invalid JSON: {exc}") from exc
    raise LLMError(f"Gemini call failed after retries: {last_err}")


def _loads(text: str) -> dict[str, Any]:
    text = text.strip()
    # Tolerate ```json ... ``` fences some models still emit.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(str(exc)) from exc
    if not isinstance(obj, dict):
        raise LLMError(f"expected a JSON object, got {type(obj).__name__}")
    return obj


# --------------------------------------------------------------------------- #
# Deterministic mock (no API key configured)
# --------------------------------------------------------------------------- #
def _mock_response(kind: Kind, prompt: str) -> dict[str, Any]:
    low = prompt.lower()
    default_sleep = settings.default_wake_interval_minutes * 60

    if kind == "classifier":
        # The classifier LLM path is only hit for events the rule table did NOT
        # recognise. Unknown == potentially important, so the mock biases to wake.
        routine = any(h in low for h in ("routine", "no_update", "heartbeat"))
        return {
            "wake_now": not routine,
            "importance": "low" if routine else "medium",
            "reason": (
                "mock: unrecognised event that looks routine"
                if routine
                else "mock: unrecognised event - waking the agent to be safe"
            ),
        }

    if kind == "final":
        return {
            "summary": "mock end-of-run summary: the order was supervised to completion.",
            "important_actions": _mock_scan_actions(low),
            "key_learnings": ["mock: no real model configured (GEMINI_API_KEY empty)"],
            "feedback": ["mock: set GEMINI_API_KEY to get real reasoning"],
        }

    # kind == "agent"
    actions: list[dict[str, str]] = []
    if "payment_failed" in low:
        actions.append(
            {
                "tool": "message_payments_team",
                "message": "mock: payment failed on this order - please investigate and advise.",
            }
        )
    elif "shipment_delayed" in low:
        actions.append(
            {
                "tool": "message_customer",
                "message": "mock: your shipment is delayed; we are on it and will update you.",
            }
        )
    return {
        "reasoning": "mock agent: acted on obvious signals, otherwise nothing to do.",
        "actions": actions,
        "new_memory_summary": "mock rolling memory: supervising order; "
        + ("handled an exception; " if actions else "")
        + "waiting for next event.",
        "next_sleep_seconds": default_sleep,
        "wakeup_guidance": "wake immediately on payment_failed, shipment_delayed, "
        "refund_requested, cancellations, or angry customer messages",
        "recommend_completion": "delivered" in low,
        "completion_reason": "mock: saw a delivered event" if "delivered" in low else None,
    }


def _mock_scan_actions(low: str) -> list[str]:
    found = []
    for name in ("message_payments_team", "message_customer", "message_logistics_team",
                 "message_fulfillment_team", "create_internal_note"):
        if name in low:
            found.append(name)
    return found
