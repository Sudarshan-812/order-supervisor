"""Prompt builders for the classifier, the main agent, and the final report.

Plain string builders, easy to eyeball and diff. The agent and classifier
always ask the model for a single JSON object matching a frozen pydantic schema.
"""
from __future__ import annotations

import json
from typing import Any


# Classifier

CLASSIFIER_SYSTEM = (
    "You are a lightweight event-triage policy for a long-running order "
    "supervisor. You are given ONE incoming order event. Decide whether it is "
    "important enough to wake the main agent now, or whether the supervisor can "
    "stay asleep until its next scheduled wake-up. Bias towards waking when "
    "unsure. Respond with a single JSON object and nothing else:\n"
    '{"wake_now": bool, "importance": "low" | "medium" | "high", "reason": string}'
)


def build_classifier_prompt(event: dict[str, Any]) -> str:
    return (
        "Incoming order event:\n"
        f"{json.dumps(event, indent=2, default=str)}\n\n"
        "Classify it."
    )


# Main agent

AGENT_SYSTEM = (
    "You are a long-running AI supervisor overseeing a SINGLE e-commerce order "
    "from creation to completion. You are woken occasionally: on start, on "
    "important events, and on a schedule you choose. You are NOT in a tight "
    "loop.\n\n"
    "Each wake: read the compact memory and recent timeline, reason about the "
    "order's current state, take ONLY the actions that are actually needed, "
    "rewrite your compact memory so the next wake has what it needs, and choose "
    "how many seconds to sleep before the next scheduled wake.\n\n"
    "You do NOT decide when the workflow ends. You may only recommend "
    "completion; the workflow ends itself on a terminal order event or a manual "
    "termination.\n\n"
    "Available actions (each just posts a message or note, no external system):\n"
    "  message_fulfillment_team, message_payments_team, message_logistics_team,\n"
    "  message_customer, create_internal_note\n\n"
    "You may also author 'wake-up guidance': a short line telling the classifier "
    "which future events should wake you immediately vs wait for the next "
    "scheduled check. Return it every time (repeat the current one if it still "
    "holds).\n\n"
    "Respond with a single JSON object and nothing else:\n"
    "{\n"
    '  "reasoning": string,\n'
    '  "actions": [{"tool": <action name>, "message": string}],\n'
    '  "new_memory_summary": string,\n'
    '  "next_sleep_seconds": integer (>= 1),\n'
    '  "wakeup_guidance": string,\n'
    '  "recommend_completion": boolean,\n'
    '  "completion_reason": string | null\n'
    "}"
)


def build_agent_prompt(
    *,
    reason: str,
    base_instruction: str,
    run_instructions: list[str],
    order_context: dict[str, Any],
    memory_summary: str,
    recent_timeline: list[dict[str, Any]],
    pending_events: list[dict[str, Any]],
    allowed_actions: list[str],
    wakeup_guidance: str = "",
) -> str:
    def block(title: str, body: str) -> str:
        return f"## {title}\n{body}".rstrip()

    instr = "\n".join(f"* {i}" for i in run_instructions) or "(none)"
    timeline = (
        json.dumps(recent_timeline, indent=2, default=str) if recent_timeline else "(empty)"
    )
    pending = (
        json.dumps(pending_events, indent=2, default=str) if pending_events else "(none)"
    )
    return "\n\n".join(
        [
            block("WAKE REASON", reason),
            block("BASE INSTRUCTION", base_instruction),
            block("RUN INSTRUCTIONS", instr),
            block("ORDER CONTEXT", json.dumps(order_context, indent=2, default=str)),
            block("COMPACT MEMORY", memory_summary or "(empty)"),
            block("CURRENT WAKE-UP GUIDANCE", wakeup_guidance or "(none set)"),
            block("RECENT TIMELINE (oldest first)", timeline),
            block("EVENTS SINCE LAST WAKE", pending),
            block("ALLOWED ACTIONS", ", ".join(allowed_actions)),
            "Decide what to do now and how long to sleep. Return the JSON object.",
        ]
    )


# Final report

FINAL_SYSTEM = (
    "The order workflow is ending. Produce a concise end-of-run report as a "
    "single JSON object and nothing else:\n"
    '{"summary": string, "important_actions": string[], '
    '"key_learnings": string[], "feedback": string[]}'
)


def build_final_prompt(
    *, reason: str, memory_summary: str, full_timeline: list[dict[str, Any]]
) -> str:
    return "\n\n".join(
        [
            f"## END REASON\n{reason}",
            f"## FINAL COMPACT MEMORY\n{memory_summary or '(empty)'}",
            "## FULL TIMELINE\n" + json.dumps(full_timeline, indent=2, default=str),
            "Write the end-of-run report. Return the JSON object.",
        ]
    )
