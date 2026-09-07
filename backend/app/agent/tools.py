"""Tool registry for the main agent.

Two kinds:
  * business actions  - the 5 required actions. Mocked: each just writes an
    activity record (kind="agent_action") on the run. No external calls.
  * runtime capabilities - sleep / update_memory / record_reasoning /
    set_wakeup_guidance / recommend_completion. These are handled by the
    workflow, not executed here; they are declared so the agent can request
    them in its AgentDecision.

The agent runtime (app.agent.runtime) receives a tool-call list from the LLM,
dispatches business actions through the matching Temporal tool activity, and
folds the runtime capabilities into the returned AgentDecision.
"""
from __future__ import annotations

from typing import Any, Callable, Awaitable

from app.models import BUSINESS_ACTIONS, RUNTIME_CAPABILITIES


def tool_specs(allowed: list[str]) -> list[dict[str, Any]]:
    """JSON-schema-ish specs handed to the LLM. Filtered by the supervisor's
    ``available_actions`` (runtime capabilities are always available)."""
    specs: list[dict[str, Any]] = []
    for name in allowed:
        if name in _BUSINESS_SPECS:
            specs.append(_BUSINESS_SPECS[name])
    specs.extend(_CAPABILITY_SPECS)
    return specs


_BUSINESS_SPECS: dict[str, dict[str, Any]] = {
    "message_fulfillment_team": {
        "name": "message_fulfillment_team",
        "description": "Send a message to the fulfillment team (mocked).",
        "parameters": {"message": "string"},
    },
    "message_payments_team": {
        "name": "message_payments_team",
        "description": "Send a message to the payments team (mocked).",
        "parameters": {"message": "string"},
    },
    "message_logistics_team": {
        "name": "message_logistics_team",
        "description": "Send a message to the logistics team (mocked).",
        "parameters": {"message": "string"},
    },
    "message_customer": {
        "name": "message_customer",
        "description": "Send a message to the customer (mocked).",
        "parameters": {"message": "string"},
    },
    "create_internal_note": {
        "name": "create_internal_note",
        "description": "Record an internal note on the run (mocked).",
        "parameters": {"note": "string"},
    },
}

_CAPABILITY_SPECS: list[dict[str, Any]] = [
    {"name": "sleep", "description": "Sleep for N seconds or until an ISO timestamp.",
     "parameters": {"seconds": "int?", "until": "iso-8601?"}},
    {"name": "update_memory", "description": "Replace the compact rolling memory summary.",
     "parameters": {"summary": "string"}},
    {"name": "record_reasoning", "description": "Persist this wake's reasoning outcome.",
     "parameters": {"reasoning": "string"}},
    {"name": "set_wakeup_guidance", "description": "Author hints for the lightweight classifier.",
     "parameters": {"guidance": "string"}},
    {"name": "recommend_completion", "description": "Advise (not force) workflow completion.",
     "parameters": {"reason": "string"}},
]

# name -> Temporal activity callable, filled by runtime to avoid import cycles.
BusinessDispatch = Callable[[str, dict], Awaitable[dict]]

assert set(_BUSINESS_SPECS) == set(BUSINESS_ACTIONS)
assert {c["name"] for c in _CAPABILITY_SPECS} == set(RUNTIME_CAPABILITIES)
