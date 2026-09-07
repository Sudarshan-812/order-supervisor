"""Domain enums + Pydantic request/response models shared by the API and the
Temporal workflow. Keep these JSON-serialisable - the workflow passes them
across the Temporal boundary.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    SLEEPING = "sleeping"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class SleepState(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class ActivityKind(str, Enum):
    EVENT = "event"
    WAKE_DECISION = "wake_decision"
    SLEEP_DECISION = "sleep_decision"
    AGENT_ACTION = "agent_action"
    AGENT_REASONING = "agent_reasoning"
    INSTRUCTION = "instruction"
    FINAL_OUTPUT = "final_output"
    SYSTEM = "system"


# Order lifecycle events the generator can emit.
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
TERMINAL_EVENT_TYPES = {"delivered"}

# The 5 required business actions + 3 runtime capabilities.
BUSINESS_ACTIONS = [
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
]
RUNTIME_CAPABILITIES = [
    "sleep",                 # sleep for a duration / until a timestamp
    "update_memory",         # refresh the compact rolling summary
    "record_reasoning",      # persist the agent's reasoning outcome
    "set_wakeup_guidance",   # author hints for the lightweight classifier
    "recommend_completion",  # advise (not force) workflow completion
]
ALL_TOOLS = BUSINESS_ACTIONS + RUNTIME_CAPABILITIES

WakeAggressiveness = Literal["passive", "balanced", "aggressive"]


# --------------------------------------------------------------------------- #
# Supervisor templates
# --------------------------------------------------------------------------- #
class SupervisorCreate(BaseModel):
    name: str
    base_instruction: str
    available_actions: list[str] = Field(default_factory=lambda: list(BUSINESS_ACTIONS))
    default_wake_minutes: int = 60
    wake_aggressiveness: WakeAggressiveness = "balanced"
    model_config_overrides: dict[str, Any] = Field(default_factory=dict)


class Supervisor(SupervisorCreate):
    id: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
class RunCreate(BaseModel):
    supervisor_id: str
    order_id: str
    order_context: dict[str, Any] = Field(default_factory=dict)
    run_instructions: list[str] = Field(default_factory=list)


class Run(BaseModel):
    id: str
    supervisor_id: str
    order_id: str
    workflow_id: str
    status: RunStatus
    sleep_state: SleepState
    next_wake_at: datetime | None = None
    order_context: dict[str, Any]
    run_instructions: list[str]
    memory_summary: str
    wakeup_guidance: str
    final_output: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class Activity(BaseModel):
    id: int
    run_id: str
    kind: ActivityKind
    title: str
    payload: dict[str, Any]
    important: bool
    created_at: datetime


class RunDetail(BaseModel):
    run: Run
    timeline: list[Activity]


# --------------------------------------------------------------------------- #
# Signals into the workflow
# --------------------------------------------------------------------------- #
class OrderEvent(BaseModel):
    """An order lifecycle event delivered into the workflow as a signal."""
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class InstructionIn(BaseModel):
    text: str


# --------------------------------------------------------------------------- #
# End-of-run output produced by the agent
# --------------------------------------------------------------------------- #
class FinalOutput(BaseModel):
    summary: str
    important_actions: list[str]
    key_learnings: list[str]
    feedback: list[str]
