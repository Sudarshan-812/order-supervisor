"""OrderSupervisorWorkflow - one long-running run per order.

Design (scaffold - method bodies are TODO):

  Triggers for agent inference
  ----------------------------
  1. workflow start            -> run agent once with the base instruction
  2. incoming event / signal   -> classifier decides wake-now vs stay-asleep
  3. scheduled wake-up         -> timer fires -> run agent

  Main loop (no tight polling)
  ----------------------------
  while not done:
      timeout = next_wake_at - now                 (scheduled wake-up)
      await workflow.wait_condition(
          lambda: self._agent_should_run or self._done,
          timeout=timeout,
      )
      if self._done: break
      await self._run_agent(reason=...)             (activity: agent.runtime)
      # agent returns: actions taken, new memory, next sleep duration,
      # optional wake-up guidance, optional completion recommendation
      self._agent_should_run = False

  Wake / sleep
  ------------
  * `order_event` signal -> append to queue -> classify (activity) ->
    if important OR aggressiveness says so -> set self._agent_should_run
    else -> stay asleep until the scheduled timer.
  * Agent picks the next wake time; workflow enforces a floor/ceiling.

  Workflow-owned completion (NOT agent-owned)
  -------------------------------------------
  Completes when ANY of:
    * a terminal order event arrives  (models.TERMINAL_EVENT_TYPES)
    * `terminate` signal from the UI
    * workflow age exceeds MAX_WORKFLOW_AGE_HOURS
  On completion: run the agent's final-output step, persist, return FinalOutput.

  Long histories
  --------------
  After N processed signals, `continue_as_new` with a carried-over compact
  state (memory summary + open threads + wake-up guidance).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.models import FinalOutput


@dataclass
class OrderSupervisorInput:
    run_id: str
    supervisor_id: str
    order_id: str
    base_instruction: str
    order_context: dict[str, Any] = field(default_factory=dict)
    run_instructions: list[str] = field(default_factory=list)
    default_wake_minutes: int = 60
    wake_aggressiveness: str = "balanced"
    # carried across continue_as_new
    memory_summary: str = ""
    wakeup_guidance: str = ""
    processed_signals: int = 0


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self) -> None:
        self._input: OrderSupervisorInput | None = None
        self._event_queue: list[dict] = []
        self._instructions: list[str] = []
        self._agent_should_run: bool = False
        self._paused: bool = False
        self._terminate_requested: bool = False
        self._done: bool = False
        self._status: str = "starting"
        self._sleep_state: str = "awake"
        self._next_wake_iso: str | None = None
        self._memory_summary: str = ""
        self._wakeup_guidance: str = ""

    # ----------------------------- run ------------------------------------ #
    @workflow.run
    async def run(self, inp: OrderSupervisorInput) -> FinalOutput:
        """Main loop. See module docstring. TODO(scaffold): implement."""
        self._input = inp
        self._memory_summary = inp.memory_summary
        self._wakeup_guidance = inp.wakeup_guidance
        self._instructions = list(inp.run_instructions)
        # TODO: initial agent run, then the wait_condition loop described above,
        #       then _finalize() -> FinalOutput.
        raise NotImplementedError("scaffold: OrderSupervisorWorkflow.run")

    # --------------------------- signals -------------------------------- #
    @workflow.signal
    async def order_event(self, event: dict) -> None:
        """Order lifecycle event. Enqueue, then let the classifier decide
        whether to wake the main agent now. Terminal events flip _done."""
        # TODO(scaffold): append; if terminal -> self._terminate via lifecycle;
        #                 else -> classify (activity) and maybe set
        #                 self._agent_should_run.
        self._event_queue.append(event)

    @workflow.signal
    async def add_instruction(self, text: str) -> None:
        """Run-specific instruction added after start - becomes run context."""
        self._instructions.append(text)
        self._agent_should_run = True

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self._agent_should_run = True

    @workflow.signal
    async def terminate(self) -> None:
        """UI-requested completion. Workflow still owns the exit + final step."""
        self._terminate_requested = True
        self._agent_should_run = True

    # --------------------------- queries ------------------------------- #
    @workflow.query
    def status(self) -> dict:
        return {
            "status": self._status,
            "sleep_state": self._sleep_state,
            "next_wake_at": self._next_wake_iso,
            "paused": self._paused,
            "queued_events": len(self._event_queue),
            "instructions": list(self._instructions),
            "memory_summary": self._memory_summary,
            "wakeup_guidance": self._wakeup_guidance,
        }

    # --------------------------- internals ---------------------------- #
    async def _run_agent(self, reason: str) -> None:
        """Invoke the agent runtime as an activity and apply its decision.

        activity: agent_runtime_activity(AgentInvocation) -> AgentDecision
          - reads: memory, timeline, instructions, queued events, guidance
          - does : tool calls (each -> activity record), memory refresh,
                   reasoning record, next-sleep choice, optional guidance,
                   optional completion recommendation
        """
        raise NotImplementedError("scaffold: _run_agent")

    async def _finalize(self, reason: str) -> FinalOutput:
        """Run the agent's end-of-run step; persist final_output; mark done."""
        raise NotImplementedError("scaffold: _finalize")

    def _should_continue_as_new(self) -> bool:
        assert self._input is not None
        return self._input.processed_signals >= 500  # tune later

    _WAKE_TIMER_FLOOR = timedelta(minutes=1)
    _WAKE_TIMER_CEILING = timedelta(hours=24)
