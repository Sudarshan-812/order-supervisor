"""Lightweight wake-up policy.

Runs on every incoming event before the main agent is disturbed. Order of checks:

  1. terminal event: not classified here, the workflow ends itself.
  2. known important type: wake now (no model call).
  3. agent wake-up guidance: substring match against the event, wake now.
  4. known routine type: stay asleep, unless aggressiveness is "aggressive".
  5. unknown type: one cheap LLM call, then the aggressiveness knob decides the
     borderline cases. The default is to wake, since over-waking is safer.
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


def _guidance_hit(event: dict, guidance: str) -> bool:
    """True if any word from the agent's wake-up guidance appears in the event
    type or payload. Deliberately crude; it is a hint, not a parser."""
    if not guidance:
        return False
    hay = f"{event.get('type', '')} {event.get('payload', '')}".lower()
    tokens = {w.strip(".,:;!?\"'()") for w in guidance.lower().split() if len(w) > 3}
    return any(tok and tok in hay for tok in tokens)


async def classify(
    event: dict,
    *,
    wakeup_guidance: str = "",
    aggressiveness: str = "balanced",
) -> ClassifierDecision:
    etype = str(event.get("type", "")).strip()

    if etype in _IMPORTANT:
        return ClassifierDecision(
            wake_now=True, importance="high",
            reason=f"'{etype}' is a known important event",
        )

    if _guidance_hit(event, wakeup_guidance):
        return ClassifierDecision(
            wake_now=True, importance="medium",
            reason=f"'{etype}' matches the agent's wake-up guidance",
        )

    if etype in _ROUTINE:
        if aggressiveness == "aggressive":
            return ClassifierDecision(
                wake_now=True, importance="low",
                reason=f"'{etype}' is routine but aggressiveness is aggressive",
            )
        return ClassifierDecision(
            wake_now=False, importance="low",
            reason=f"'{etype}' is routine; handle it on the next scheduled wake",
        )

    # Unknown event type: ask the cheap model, then apply the knob.
    try:
        raw = await llm.generate_json(
            system=prompts.CLASSIFIER_SYSTEM,
            prompt=prompts.build_classifier_prompt(event),
            kind="classifier",
        )
        verdict = ClassifierDecision.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - deliberate fail-safe
        return ClassifierDecision(
            wake_now=True, importance="medium",
            reason=f"unknown event '{etype}', classifier errored ({exc!r}); waking to be safe",
        )

    if aggressiveness == "aggressive":
        verdict = verdict.model_copy(update={"wake_now": True})
    elif aggressiveness == "passive" and verdict.importance != "high":
        verdict = verdict.model_copy(update={
            "wake_now": False,
            "reason": verdict.reason + " (held: aggressiveness is passive)",
        })
    return verdict
