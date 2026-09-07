"""Main agent runtime - invoked by the `run_agent` Temporal activity.

One invocation = one "wake". It does NOT loop internally beyond a small
bounded tool-call round-trip.

    async def run_agent(inv: AgentInvocation) -> AgentDecision:
        ctx      = await memory.build_working_context(inv.run_id)
        prompt   = prompts.build_agent_prompt(..., tool_specs(inv.allowed_actions))
        plan     = await llm.generate_json(system=AGENT_SYSTEM, prompt=prompt)
        actions  = []
        for call in plan["tool_calls"]:
            if call.name in BUSINESS_ACTIONS:
                result = await dispatch_business_action(inv.run_id, call)  # -> activity
                actions.append({...})
            # runtime capabilities are folded into the decision below
        await memory.maybe_compact(inv.run_id)
        return AgentDecision(
            acted=bool(actions),
            actions=actions,
            reasoning=plan["reasoning"],
            memory_summary=plan.get("memory_summary", ctx["memory_summary"]),
            wakeup_guidance=plan.get("wakeup_guidance", inv.wakeup_guidance),
            next_sleep_seconds=plan.get("next_sleep_seconds", DEFAULT),
            recommend_completion=plan.get("recommend_completion", False),
            completion_reason=plan.get("completion_reason"),
        )
"""
from __future__ import annotations

from app.temporal.activities import AgentDecision, AgentInvocation


async def run_agent(inv: AgentInvocation) -> AgentDecision:
    """TODO(scaffold): implement the flow in the module docstring."""
    raise NotImplementedError("scaffold: agent.runtime.run_agent")


async def produce_final_output(run_id: str, reason: str) -> dict:
    """End-of-run report via the LLM (FINAL_SYSTEM prompt). Persist + return
    {summary, important_actions, key_learnings, feedback}. TODO(scaffold)."""
    raise NotImplementedError("scaffold: agent.runtime.produce_final_output")
