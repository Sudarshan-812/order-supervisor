"""Main agent runtime, the reasoning core invoked by the `run_agent` and
`produce_final_output` Temporal activities.

One call to `run_agent` is one wake. It does a single model round-trip (plus an
optional compaction call); it does not loop internally. It returns a frozen
AgentDecision; the activity persists the resulting action rows and run-state.
"""
from __future__ import annotations

from typing import Any

from app.agent import llm, memory, prompts
from app.agent.tools import tool_specs
from app.config import settings
from app.models import AgentDecision, FinalOutput


async def run_agent(
    *,
    run_id: str,
    reason: str,
    base_instruction: str,
    run_instructions: list[str],
    order_context: dict[str, Any],
    pending_events: list[dict[str, Any]],
    allowed_actions: list[str],
    wakeup_guidance: str = "",
) -> AgentDecision:
    ctx = await memory.build_working_context(run_id)
    allowed = [s["name"] for s in tool_specs(allowed_actions)]

    prompt = prompts.build_agent_prompt(
        reason=reason,
        base_instruction=base_instruction,
        run_instructions=run_instructions,
        order_context=order_context,
        memory_summary=ctx["memory_summary"],
        recent_timeline=ctx["recent_timeline"],
        pending_events=pending_events,
        allowed_actions=allowed,
        wakeup_guidance=wakeup_guidance,
    )
    raw = await llm.generate_json(system=prompts.AGENT_SYSTEM, prompt=prompt, kind="agent")

    raw.setdefault("new_memory_summary", ctx["memory_summary"] or "")
    raw.setdefault("next_sleep_seconds", settings.default_wake_interval_minutes * 60)
    if not raw.get("wakeup_guidance"):
        raw["wakeup_guidance"] = wakeup_guidance  # keep the current guidance
    raw["actions"] = [a for a in raw.get("actions", []) if a.get("tool") in allowed]
    decision = AgentDecision.model_validate(raw)

    compacted = await memory.maybe_compact(run_id, decision.new_memory_summary)
    if compacted != decision.new_memory_summary:
        decision = decision.model_copy(update={"new_memory_summary": compacted})

    return decision


async def produce_final_output(
    *, run_id: str, reason: str, memory_summary: str
) -> FinalOutput:
    from app import db

    rows = await db.fetch_activities(run_id, newest_first=False)
    timeline = [
        {"type": r["type"], "payload": r["payload"], "at": r["created_at"].isoformat()}
        for r in rows
    ]
    raw = await llm.generate_json(
        system=prompts.FINAL_SYSTEM,
        prompt=prompts.build_final_prompt(
            reason=reason, memory_summary=memory_summary, full_timeline=timeline
        ),
        kind="final",
    )
    return FinalOutput.model_validate(raw)
