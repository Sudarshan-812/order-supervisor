"""Lightweight wake-up policy.

Runs on every incoming event BEFORE the main agent is disturbed. Order of checks:

  1. terminal event        -> not classified here; the workflow ends itself
  2. known important type   -> wake now (no model call)
  3. known routine type     -> stay asleep (no model call)
  4. unknown type           -> one cheap LLM call (mock-friendly); default to
                               waking if that fails - safer to over-wake
"""
from __future__ import annotations

from app.agent import llm, prompts
from app.models import ClassifierDecision

_IMPORTANT = {
    "payment_failed",
    "shipment_delayed",
    "refund_requested",
    "customer_message_received",
    "order_cancelled",
}
_ROUTINE = {
    "order_created",
    "payment_confirmed",
    "shipment_created",
    "no_update_for_n_hours",
}


async def classify(event: dict) -> ClassifierDecision:
    etype = str(event.get("type", "")).strip()

    if etype in _IMPORTANT:
        return ClassifierDecision(
            wake_now=True, importance="high",
            reason=f"'{etype}' is a known important event",
        )
    if etype in _ROUTINE:
        return ClassifierDecision(
            wake_now=False, importance="low",
            reason=f"'{etype}' is routine; handle it on the next scheduled wake",
        )

    # Unknown event type -> ask the cheap model, but fail safe to waking.
    try:
        raw = await llm.generate_json(
            system=prompts.CLASSIFIER_SYSTEM,
            prompt=prompts.build_classifier_prompt(event),
            kind="classifier",
        )
        return ClassifierDecision.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - deliberate fail-safe
        return ClassifierDecision(
            wake_now=True, importance="medium",
            reason=f"unknown event '{etype}', classifier failed ({exc!r}); waking to be safe",
        )
