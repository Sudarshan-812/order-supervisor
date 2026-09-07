"""Prompt templates for the classifier, the main agent, and the final step.
Kept as plain string builders so they are easy to eyeball and tweak.
"""
from __future__ import annotations

from typing import Any

CLASSIFIER_SYSTEM = (
    "You are a lightweight event triage policy for an order supervisor. "
    "Given one incoming order event, decide whether it is important enough to "
    "wake the main agent now, or whether the workflow can stay asleep until its "
    "next scheduled wake-up. Respond with a single JSON object: "
    '{"wake_now": bool, "importance": "low|medium|high", "reason": str}.'
)

AGENT_SYSTEM = (
    "You are a long-running AI supervisor for a single e-commerce order. "
    "You are woken occasionally (on start, on important events, on a schedule). "
    "You are NOT in a tight loop: reason about the current situation, take only "
    "the actions that are needed, refresh your compact memory, then choose how "
    "long to sleep. You do not decide when the workflow ends - you may only "
    "recommend completion. Always respond with a single JSON object matching the "
    "AgentDecision schema."
)

FINAL_SYSTEM = (
    "The order workflow is ending. Produce a concise end-of-run report as a "
    "single JSON object: {summary, important_actions[], key_learnings[], "
    "feedback[]}."
)


def build_agent_prompt(
    *,
    base_instruction: str,
    run_instructions: list[str],
    memory_summary: str,
    wakeup_guidance: str,
    pending_events: list[dict],
    order_context: dict[str, Any],
    allowed_actions: list[str],
    reason: str,
) -> str:
    # TODO(scaffold): flesh out formatting / truncation rules.
    return "\n\n".join(
        [
            f"WAKE REASON: {reason}",
            f"BASE INSTRUCTION:\n{base_instruction}",
            f"RUN INSTRUCTIONS:\n" + "\n".join(f"- {i}" for i in run_instructions),
            f"ORDER CONTEXT:\n{order_context}",
            f"COMPACT MEMORY:\n{memory_summary or '(empty)'}",
            f"CURRENT WAKE-UP GUIDANCE:\n{wakeup_guidance or '(none)'}",
            f"PENDING EVENTS:\n{pending_events or '(none)'}",
            f"ALLOWED ACTIONS: {allowed_actions}",
        ]
    )
