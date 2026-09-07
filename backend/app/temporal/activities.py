"""Temporal activities - the ONLY place side effects happen (DB writes, LLM
calls, "sending" messages). The workflow stays deterministic and calls these.

Groups:
  * persistence  - append_activity, persist_run_state
  * agent        - classify_event, run_agent, produce_final_output

The 5 business actions are not separate activities: `run_agent` performs them by
writing activity_log rows (type = agent_action) directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from temporalio import activity

from app import db
from app.agent import classifier, runtime
from app.models import ActivityType


# --------------------------------------------------------------------------- #
# DTOs across the workflow <-> activity boundary (dataclasses: temporalio 1.9
# has no pydantic converter, and these need no validation).
# --------------------------------------------------------------------------- #
@dataclass
class ClassifyRequest:
    run_id: str
    event: dict


@dataclass
class AgentInvocation:
    run_id: str
    reason: str  # start | scheduled_wake | event | instruction | terminate
    base_instruction: str
    run_instructions: list[str] = field(default_factory=list)
    order_context: dict[str, Any] = field(default_factory=dict)
    pending_events: list[dict] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
@activity.defn
async def append_activity(run_id: str, type_: str, payload: dict) -> dict:
    """Append one activity_log row. Returns {id, created_at}."""
    rec = await db.insert_activity(run_id, type_, payload)
    return {"id": rec["id"], "created_at": rec["created_at"].isoformat()}


@activity.defn
async def persist_run_state(run_id: str, patch: dict) -> None:
    """UPDATE runs SET <patch> WHERE id = run_id (whitelisted columns only).
    `next_wake_at` crosses the workflow boundary as an ISO string - coerce it
    back to a datetime for the timestamptz column."""
    patch = dict(patch)
    nwa = patch.get("next_wake_at")
    if isinstance(nwa, str):
        patch["next_wake_at"] = datetime.fromisoformat(nwa)
    await db.patch_run(run_id, **patch)


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
@activity.defn
async def classify_event(req: ClassifyRequest) -> dict:
    """Lightweight wake-up policy. Logs its own wake_decision row and returns
    {wake_now, importance, reason}."""
    verdict = await classifier.classify(req.event)
    await db.insert_activity(
        req.run_id,
        ActivityType.WAKE_DECISION.value,
        {
            "stage": "classifier",
            "event_type": req.event.get("type"),
            **verdict.model_dump(),
        },
    )
    return verdict.model_dump()


@activity.defn
async def run_agent(inv: AgentInvocation) -> dict:
    """Run one agent wake. Persists each action + a wake_decision row, then
    returns the AgentDecision as a dict for the workflow to apply."""
    decision = await runtime.run_agent(
        run_id=inv.run_id,
        reason=inv.reason,
        base_instruction=inv.base_instruction,
        run_instructions=inv.run_instructions,
        order_context=inv.order_context,
        pending_events=inv.pending_events,
        allowed_actions=inv.allowed_actions,
    )

    for action in decision.actions:
        await db.insert_activity(
            inv.run_id,
            ActivityType.AGENT_ACTION.value,
            {"tool": action.tool, "message": action.message, "result": "recorded"},
        )

    await db.insert_activity(
        inv.run_id,
        ActivityType.WAKE_DECISION.value,
        {
            "stage": "agent",
            "reason": inv.reason,
            "reasoning": decision.reasoning,
            "action_count": len(decision.actions),
            "next_sleep_seconds": decision.next_sleep_seconds,
            "recommend_completion": decision.recommend_completion,
            "completion_reason": decision.completion_reason,
        },
    )
    return decision.model_dump()


@activity.defn
async def produce_final_output(run_id: str, reason: str, memory_summary: str) -> dict:
    """End-of-run report. Logs a final_output row and returns it."""
    final = await runtime.produce_final_output(
        run_id=run_id, reason=reason, memory_summary=memory_summary
    )
    await db.insert_activity(
        run_id, ActivityType.FINAL_OUTPUT.value, {"reason": reason, **final.model_dump()}
    )
    return final.model_dump()


ALL_ACTIVITIES = [
    append_activity,
    persist_run_state,
    classify_event,
    run_agent,
    produce_final_output,
]
