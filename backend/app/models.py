"""Domain enums + Pydantic models shared by the API, the Temporal workflow, and
the agent layer.

Three groups:
  * DB / API models        - mutable, mirror the 3 tables (supervisors, runs,
                             activity_log) and the HTTP surface.
  * Signal payloads        - what the API sends into a live workflow.
  * Frozen LLM contracts   - `ClassifierDecision`, `AgentDecision`, `FinalOutput`.
                             These are `frozen=True`: once parsed from model
                             output they never mutate.

Everything here is JSON-serialisable so it can cross the Temporal boundary.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Enums (values match the CHECK constraints in schema.sql)
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    ACTIVE = "active"
    SLEEPING = "sleeping"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ActivityType(str, Enum):
    INCOMING_EVENT = "incoming_event"
    WAKE_DECISION = "wake_decision"
    AGENT_ACTION = "agent_action"
    MANUAL_INSTRUCTION = "manual_instruction"
    FINAL_OUTPUT = "final_output"


# Order lifecycle events the generator / control panel can emit.
EVENT_TYPES = [
    "order_created",
    "payment_confirmed",
    "payment_failed",
    "shipment_created",
    "shipment_delayed",
    "delivered",
    "refund_requested",
    "customer_message_received",
    "no_update_for_n_hours",
]

# Events that put the order into a terminal state -> workflow-owned completion.
TERMINAL_EVENT_TYPES = {"delivered", "order_cancelled"}

# The 5 required business actions. Each is "executed" by writing an
# activity_log row (type = agent_action). No external APIs.
BUSINESS_ACTIONS = [
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
]
ActionName = Literal[
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
]

# How eagerly the classifier wakes the main agent for borderline / unknown events.
WakeAggressiveness = Literal["passive", "balanced", "aggressive"]


# --------------------------------------------------------------------------- #
# Supervisor templates
# --------------------------------------------------------------------------- #
class SupervisorCreate(BaseModel):
    name: str
    base_instruction: str
    # First-class config knobs (assignment: available actions, default wake
    # behaviour, wake aggressiveness). Persisted inside the `model_config` JSONB
    # column together with `extra`.
    allowed_actions: list[ActionName] = Field(default_factory=list)  # [] == all 5
    default_wake_minutes: int = 60
    wake_aggressiveness: WakeAggressiveness = "balanced"
    # Free-form escape hatch (model name, temperature, ...). Named `extra` here
    # because `model_config` is reserved by pydantic v2.
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_model_config(self) -> dict[str, Any]:
        return {
            "allowed_actions": self.allowed_actions,
            "default_wake_minutes": self.default_wake_minutes,
            "wake_aggressiveness": self.wake_aggressiveness,
            **self.extra,
        }


class Supervisor(BaseModel):
    id: str
    name: str
    base_instruction: str
    model_settings: dict[str, Any]  # raw `model_config` JSONB
    created_at: datetime

    @property
    def allowed_actions(self) -> list[str]:
        return list(self.model_settings.get("allowed_actions", []))

    @property
    def default_wake_minutes(self) -> int:
        return int(self.model_settings.get("default_wake_minutes", 60))

    @property
    def wake_aggressiveness(self) -> str:
        return str(self.model_settings.get("wake_aggressiveness", "balanced"))


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
class RunCreate(BaseModel):
    supervisor_id: str
    order_id: str
    # Not persisted as columns - passed to the workflow as start input and
    # written to activity_log so the agent has them from wake #1.
    order_context: dict[str, Any] = Field(default_factory=dict)
    run_instructions: list[str] = Field(default_factory=list)


class Run(BaseModel):
    id: str
    order_id: str
    supervisor_id: str
    status: RunStatus
    memory_summary: str
    workflow_id: str | None = None
    next_wake_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ActivityLogRow(BaseModel):
    id: int
    run_id: str
    type: ActivityType
    payload: dict[str, Any]
    created_at: datetime


class RunDetail(BaseModel):
    run: Run
    timeline: list[ActivityLogRow]
    # Best-effort live snapshot from the workflow's `status` query (queued
    # events, standing instructions, next wake). None if the workflow can't be
    # reached (completed, or worker down).
    live: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Signal payloads (API -> workflow)
# --------------------------------------------------------------------------- #
class IncomingEvent(BaseModel):
    """An order lifecycle event delivered into the workflow as a signal."""

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class ManualInstruction(BaseModel):
    text: str


# --------------------------------------------------------------------------- #
# Frozen LLM contracts
# --------------------------------------------------------------------------- #
class ClassifierDecision(BaseModel):
    """Output of the lightweight wake-up classifier."""

    model_config = ConfigDict(frozen=True)

    wake_now: bool
    importance: Literal["low", "medium", "high"]
    reason: str


class AgentAction(BaseModel):
    """One business action the agent decided to take this wake."""

    model_config = ConfigDict(frozen=True)

    tool: ActionName
    message: str


class AgentDecision(BaseModel):
    """The main agent's structured response for a single wake."""

    model_config = ConfigDict(frozen=True)

    reasoning: str
    actions: list[AgentAction] = Field(default_factory=list)
    new_memory_summary: str
    next_sleep_seconds: int = Field(ge=1)
    # Optional: agent-authored hints the lightweight classifier uses on future
    # events ("wake immediately on refund_requested", ...). "" == keep current.
    wakeup_guidance: str = ""
    recommend_completion: bool = False
    completion_reason: str | None = None


class FinalOutput(BaseModel):
    """End-of-run report produced when the workflow completes."""

    model_config = ConfigDict(frozen=True)

    summary: str
    important_actions: list[str] = Field(default_factory=list)
    key_learnings: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
