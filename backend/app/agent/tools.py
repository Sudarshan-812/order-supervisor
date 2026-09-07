"""Tool registry for the main agent.

The 5 required business actions. Each is mocked: "executing" it means writing one
activity_log row (type = agent_action) on the run, with no external calls. The
agent runtime does that write directly; there is no per-tool Temporal activity.

Runtime concerns (how long to sleep, memory refresh, completion recommendation)
are not tools; they are fields on AgentDecision.
"""
from __future__ import annotations

from typing import Any

from app.models import BUSINESS_ACTIONS

_PARAM = {"message": "string, the message or note body"}

_BUSINESS_SPECS: dict[str, dict[str, Any]] = {
    "message_fulfillment_team": {
        "name": "message_fulfillment_team",
        "description": "Send a message to the fulfillment / warehouse team.",
        "parameters": _PARAM,
    },
    "message_payments_team": {
        "name": "message_payments_team",
        "description": "Send a message to the payments team (billing, refunds, chargebacks).",
        "parameters": _PARAM,
    },
    "message_logistics_team": {
        "name": "message_logistics_team",
        "description": "Send a message to the logistics / carrier team (shipping, delays).",
        "parameters": _PARAM,
    },
    "message_customer": {
        "name": "message_customer",
        "description": "Send a message directly to the customer.",
        "parameters": _PARAM,
    },
    "create_internal_note": {
        "name": "create_internal_note",
        "description": "Record an internal note on the run for later context.",
        "parameters": _PARAM,
    },
}

assert set(_BUSINESS_SPECS) == set(BUSINESS_ACTIONS)


def tool_specs(allowed: list[str]) -> list[dict[str, Any]]:
    """Specs handed to the LLM, filtered by the supervisor's allowed actions.
    Unknown names are ignored; an empty or missing list means all 5."""
    names = [a for a in allowed if a in _BUSINESS_SPECS] or list(BUSINESS_ACTIONS)
    return [_BUSINESS_SPECS[n] for n in names]
