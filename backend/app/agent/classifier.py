"""Lightweight wake-up policy.

Cheap, mostly deterministic gate that runs on every incoming event before the
main agent is disturbed. Order of checks:

  1. terminal events            -> handled by workflow lifecycle (not here)
  2. hard-coded important set    -> wake now
  3. hard-coded routine set      -> stay asleep
  4. agent-authored guidance     -> keyword / intent match
  5. unknown event type          -> escalate (wake now) - safer default
  6. aggressiveness knob         -> passive/balanced/aggressive shifts the line
"""
from __future__ import annotations

from dataclasses import dataclass

_IMPORTANT = {
    "payment_failed",
    "shipment_delayed",
    "refund_requested",
    "customer_message_received",
}
_ROUTINE = {
    "order_created",
    "payment_confirmed",
    "shipment_created",
    "no_update_for_n_hours",
}


@dataclass
class Verdict:
    wake_now: bool
    importance: str          # low | medium | high
    reason: str


async def classify(
    *,
    event_type: str,
    event_payload: dict,
    wakeup_guidance: str,
    aggressiveness: str = "balanced",
) -> Verdict:
    """TODO(scaffold): implement steps 2-6; call llm.generate_json only for
    genuinely unknown events when a key is configured."""
    raise NotImplementedError("scaffold: classifier.classify")
