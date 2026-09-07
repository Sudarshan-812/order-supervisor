"""Temporal activities - the only place side effects happen (DB writes, LLM
calls, "sending" messages). The workflow stays deterministic and calls these.

Grouped:
  * persistence  - write runs/activities rows
  * agent        - classifier + main agent runtime + final output
  * tools        - the 5 business actions (each writes an activity record)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from temporalio import activity


# --------------------------------------------------------------------------- #
# DTOs across the workflow <-> activity boundary
# --------------------------------------------------------------------------- #
@dataclass
class ClassifyRequest:
    run_id: str
    event: dict
    wakeup_guidance: str
    wake_aggressiveness: str


@dataclass
class ClassifyResult:
    wake_now: bool
    importance: str          # low | medium | high
    reason: str


@dataclass
class AgentInvocation:
    run_id: str
    reason: str              # "start" | "event" | "scheduled_wake" | "instruction" | "terminate"
    base_instruction: str
    instructions: list[str]
    memory_summary: str
    wakeup_guidance: str
    pending_events: list[dict]
    order_context: dict[str, Any]
    allowed_actions: list[str]


@dataclass
class AgentDecision:
    acted: bool
    actions: list[dict]                 # [{tool, args, result}] - already recorded
    reasoning: str
    memory_summary: str                 # refreshed rolling summary
    wakeup_guidance: str                # refreshed classifier hints
    next_sleep_seconds: int             # workflow clamps to [floor, ceiling]
    recommend_completion: bool
    completion_reason: str | None = None


# --------------------------------------------------------------------------- #
# Persistence activities
# --------------------------------------------------------------------------- #
@activity.defn
async def persist_run_state(run_id: str, patch: dict) -> None:
    """UPDATE order_supervisor.runs SET ... WHERE id = run_id."""
    raise NotImplementedError("scaffold: persist_run_state")


@activity.defn
async def append_activity(run_id: str, kind: str, title: str, payload: dict, important: bool = False) -> int:
    """INSERT INTO order_supervisor.activities ... RETURNING id."""
    raise NotImplementedError("scaffold: append_activity")


# --------------------------------------------------------------------------- #
# Agent activities
# --------------------------------------------------------------------------- #
@activity.defn
async def classify_event(req: ClassifyRequest) -> ClassifyResult:
    """Lightweight wake-up policy (see app.agent.classifier). Rule-based first,
    optional cheap LLM check for unknown events."""
    raise NotImplementedError("scaffold: classify_event")


@activity.defn
async def run_agent(inv: AgentInvocation) -> AgentDecision:
    """Main agent runtime (see app.agent.runtime): reason -> tool calls ->
    memory refresh -> next-sleep decision."""
    raise NotImplementedError("scaffold: run_agent")


@activity.defn
async def produce_final_output(run_id: str, reason: str) -> dict:
    """End-of-run step: summary, important actions, key learnings, feedback.
    Persists to runs.final_output and returns it."""
    raise NotImplementedError("scaffold: produce_final_output")


# --------------------------------------------------------------------------- #
# Tool activities (business actions) - all mocked, all write an activity record
# --------------------------------------------------------------------------- #
@activity.defn
async def tool_message_fulfillment_team(run_id: str, message: str) -> dict:
    raise NotImplementedError("scaffold: tool_message_fulfillment_team")


@activity.defn
async def tool_message_payments_team(run_id: str, message: str) -> dict:
    raise NotImplementedError("scaffold: tool_message_payments_team")


@activity.defn
async def tool_message_logistics_team(run_id: str, message: str) -> dict:
    raise NotImplementedError("scaffold: tool_message_logistics_team")


@activity.defn
async def tool_message_customer(run_id: str, message: str) -> dict:
    raise NotImplementedError("scaffold: tool_message_customer")


@activity.defn
async def tool_create_internal_note(run_id: str, note: str) -> dict:
    raise NotImplementedError("scaffold: tool_create_internal_note")


ALL_ACTIVITIES = [
    persist_run_state,
    append_activity,
    classify_event,
    run_agent,
    produce_final_output,
    tool_message_fulfillment_team,
    tool_message_payments_team,
    tool_message_logistics_team,
    tool_message_customer,
    tool_create_internal_note,
]
