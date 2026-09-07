"""OrderSupervisorWorkflow - one long-running workflow per order.

Triggers for agent inference
----------------------------
1. workflow start            -> run the agent once ("start")
2. incoming_event signal     -> classifier activity decides wake-now vs stay-asleep
3. manual_instruction signal -> always wakes the agent
4. interrupt signal          -> force an immediate wake to re-assess
5. resume signal             -> wake after a pause
6. scheduled wake-up         -> wait_condition timeout fires -> run the agent

Main loop (no tight polling)
----------------------------
A single `workflow.wait_condition(..., timeout=<until next scheduled wake>)`.
It returns early when the agent should run or a lifecycle flag flips; otherwise
it times out and we do a scheduled wake. While paused, the loop parks on a
second wait_condition and does not run the agent (events still queue).

Signals & lifecycle
-------------------
  incoming_event(event)      order lifecycle event -> classify -> maybe wake
  manual_instruction(text)   run-specific instruction -> wake
  pause()  / resume()        halt / restart agent inference
  interrupt(reason)          force an immediate wake now (NON-terminal)
  terminate(reason)          workflow-owned completion -> final output -> exit

Completion is WORKFLOW-owned, never agent-owned:
  * terminal order event (models.TERMINAL_EVENT_TYPES)   -> status "completed"
  * terminate signal (manual)                            -> status "terminated"
  * MAX_WORKFLOW_AGE_HOURS exceeded                       -> status "completed"
The agent may only *recommend* completion.

Long histories -> `continue_as_new`, carrying the compact memory summary and the
agent-authored wake-up guidance.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.config import settings
    from app.models import TERMINAL_EVENT_TYPES, FinalOutput
    from app.temporal.activities import (
        AgentInvocation,
        ClassifyRequest,
        append_activity,
        classify_event,
        persist_run_state,
        produce_final_output,
        run_agent,
    )

_WAKE_FLOOR = timedelta(minutes=1)
_WAKE_CEILING = timedelta(hours=24)
_CONTINUE_AS_NEW_AFTER = 200

_FAST_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1))
_AGENT_RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=2))


@dataclass
class OrderSupervisorInput:
    run_id: str
    supervisor_id: str
    order_id: str
    base_instruction: str
    order_context: dict[str, Any] = field(default_factory=dict)
    run_instructions: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    default_wake_minutes: int = 60
    wake_aggressiveness: str = "balanced"
    # carried across continue_as_new
    memory_summary: str = ""
    wakeup_guidance: str = ""
    processed_wakes: int = 0
    is_continuation: bool = False


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self) -> None:
        self._inp: OrderSupervisorInput | None = None
        self._pending_events: list[dict] = []
        self._instructions: list[str] = []
        self._agent_should_run = False
        self._wake_reason = "scheduled_wake"
        self._paused = False
        self._terminate_requested = False
        self._terminate_reason: str | None = None
        self._end_status = "completed"
        self._done = False
        self._status = "active"
        self._memory_summary = ""
        self._wakeup_guidance = ""
        self._last_reasoning = ""
        self._next_wake_dt = None  # type: ignore[assignment]
        self._processed_wakes = 0

    # ------------------------------ run -------------------------------- #
    @workflow.run
    async def run(self, inp: OrderSupervisorInput) -> FinalOutput:
        self._inp = inp
        self._memory_summary = inp.memory_summary
        self._wakeup_guidance = inp.wakeup_guidance
        self._instructions = list(inp.run_instructions)
        self._processed_wakes = inp.processed_wakes
        deadline = workflow.now() + timedelta(hours=settings.max_workflow_age_hours)

        if not inp.is_continuation:
            await self._log(
                "incoming_event",
                {
                    "type": "run_created",
                    "order_id": inp.order_id,
                    "order_context": inp.order_context,
                    "run_instructions": inp.run_instructions,
                },
            )
            await self._wake_agent("start")

        while not self._terminate_requested:
            if workflow.now() >= deadline:
                self._terminate_reason = "max workflow age exceeded"
                self._end_status = "completed"
                break

            if self._paused:
                self._status = "paused"
                await workflow.wait_condition(
                    lambda: not self._paused or self._terminate_requested
                )
                continue

            try:
                await workflow.wait_condition(
                    lambda: (self._agent_should_run and not self._paused)
                    or self._terminate_requested,
                    timeout=self._time_until_next_wake(),
                )
            except asyncio.TimeoutError:
                self._agent_should_run = True
                self._wake_reason = "scheduled_wake"

            if self._terminate_requested:
                break
            if self._paused:
                continue

            await self._wake_agent(self._wake_reason)

            if (
                self._processed_wakes >= _CONTINUE_AS_NEW_AFTER
                and not self._pending_events
                and not self._agent_should_run
                and not self._terminate_requested
            ):
                workflow.continue_as_new(args=[self._continuation_input()])

        final = await self._finalize(self._terminate_reason or "completed")
        return FinalOutput.model_validate(final)

    # ---------------------------- signals ----------------------------- #
    @workflow.signal
    async def incoming_event(self, event: dict) -> None:
        """Order lifecycle event: log it, classify it, maybe wake the agent.
        A terminal event moves the workflow towards completion. While paused the
        event is logged + classified but the agent is not woken (it queues)."""
        assert self._inp is not None
        self._pending_events.append(event)
        await self._log("incoming_event", event)

        if str(event.get("type")) in TERMINAL_EVENT_TYPES:
            self._terminate_requested = True
            self._terminate_reason = f"terminal order event: {event.get('type')}"
            self._end_status = "completed"
            return

        verdict = await workflow.execute_activity(
            classify_event,
            ClassifyRequest(
                run_id=self._inp.run_id,
                event=event,
                wakeup_guidance=self._wakeup_guidance,
                wake_aggressiveness=self._inp.wake_aggressiveness,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_FAST_RETRY,
        )
        if verdict.get("wake_now") and not self._paused:
            self._agent_should_run = True
            self._wake_reason = "event"

    @workflow.signal
    async def manual_instruction(self, text: str) -> None:
        """Operator instruction added to a live run -> part of run context."""
        assert self._inp is not None
        self._instructions.append(text)
        await self._log("manual_instruction", {"text": text})
        if not self._paused:
            self._agent_should_run = True
            self._wake_reason = "instruction"

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True

    @workflow.signal
    async def resume(self) -> None:
        if self._paused:
            self._paused = False
            self._agent_should_run = True
            self._wake_reason = "resume"

    @workflow.signal
    async def interrupt(self, reason: str = "operator interrupt") -> None:
        """Force an immediate agent wake to re-assess. NON-terminal."""
        self._paused = False
        self._agent_should_run = True
        self._wake_reason = "interrupt"

    @workflow.signal
    async def terminate(self, reason: str = "manual termination") -> None:
        """Operator-requested completion. The workflow still owns the exit and
        runs the final-output step before returning."""
        self._terminate_requested = True
        self._terminate_reason = reason or "manual termination"
        self._end_status = "terminated"

    # ---------------------------- queries ---------------------------- #
    @workflow.query
    def status(self) -> dict:
        return {
            "status": self._status,
            "paused": self._paused,
            "next_wake_at": self._next_wake_dt.isoformat() if self._next_wake_dt else None,
            "queued_events": len(self._pending_events),
            "standing_instructions": list(self._instructions),
            "memory_summary": self._memory_summary,
            "wakeup_guidance": self._wakeup_guidance,
            "last_reasoning": self._last_reasoning,
            "processed_wakes": self._processed_wakes,
            "terminating": self._terminate_requested,
        }

    # --------------------------- internals -------------------------- #
    async def _log(self, type_: str, payload: dict) -> None:
        assert self._inp is not None
        await workflow.execute_activity(
            append_activity,
            args=[self._inp.run_id, type_, payload],
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=_FAST_RETRY,
        )

    def _time_until_next_wake(self) -> timedelta:
        if self._next_wake_dt is None:
            return _WAKE_CEILING
        delta = self._next_wake_dt - workflow.now()
        return delta if delta > timedelta(0) else timedelta(seconds=1)

    async def _wake_agent(self, reason: str) -> None:
        assert self._inp is not None
        inp = self._inp
        self._status = "active"

        pending = list(self._pending_events)
        self._pending_events.clear()
        self._agent_should_run = False

        decision = await workflow.execute_activity(
            run_agent,
            AgentInvocation(
                run_id=inp.run_id,
                reason=reason,
                base_instruction=inp.base_instruction,
                run_instructions=list(self._instructions),
                order_context=inp.order_context,
                pending_events=pending,
                allowed_actions=inp.allowed_actions,
                wakeup_guidance=self._wakeup_guidance,
            ),
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=_AGENT_RETRY,
        )

        self._memory_summary = decision.get("new_memory_summary", self._memory_summary)
        self._last_reasoning = decision.get("reasoning", "")
        if decision.get("wakeup_guidance"):
            self._wakeup_guidance = decision["wakeup_guidance"]
        self._processed_wakes += 1

        sleep_s = int(decision.get("next_sleep_seconds") or inp.default_wake_minutes * 60)
        sleep_s = max(
            int(_WAKE_FLOOR.total_seconds()),
            min(sleep_s, int(_WAKE_CEILING.total_seconds())),
        )
        self._next_wake_dt = workflow.now() + timedelta(seconds=sleep_s)
        self._status = "sleeping"

        await workflow.execute_activity(
            persist_run_state,
            args=[
                inp.run_id,
                {
                    "status": "sleeping",
                    "memory_summary": self._memory_summary,
                    "next_wake_at": self._next_wake_dt.isoformat(),
                },
            ],
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=_FAST_RETRY,
        )

    async def _finalize(self, reason: str) -> dict:
        assert self._inp is not None
        inp = self._inp
        self._done = True
        self._status = self._end_status

        final = await workflow.execute_activity(
            produce_final_output,
            args=[inp.run_id, reason, self._memory_summary],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=_AGENT_RETRY,
        )
        await workflow.execute_activity(
            persist_run_state,
            args=[inp.run_id, {"status": self._end_status, "memory_summary": self._memory_summary}],
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=_FAST_RETRY,
        )
        return final

    def _continuation_input(self) -> OrderSupervisorInput:
        assert self._inp is not None
        base = self._inp
        return OrderSupervisorInput(
            run_id=base.run_id,
            supervisor_id=base.supervisor_id,
            order_id=base.order_id,
            base_instruction=base.base_instruction,
            order_context=base.order_context,
            run_instructions=list(self._instructions),
            allowed_actions=base.allowed_actions,
            default_wake_minutes=base.default_wake_minutes,
            wake_aggressiveness=base.wake_aggressiveness,
            memory_summary=self._memory_summary,
            wakeup_guidance=self._wakeup_guidance,
            processed_wakes=0,
            is_continuation=True,
        )
