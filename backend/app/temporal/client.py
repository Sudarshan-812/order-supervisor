"""Shared Temporal client factory plus the start/signal helpers the API uses.

One workflow per order: the workflow id is derived from the order id and started
with a reject-duplicate policy, so a second POST /api/runs for the same order
fails instead of spawning a parallel supervisor.
"""
from __future__ import annotations

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.config import settings
from app.temporal.workflows import OrderSupervisorInput, OrderSupervisorWorkflow

_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.temporal_host, namespace=settings.temporal_namespace
        )
    return _client


def workflow_id_for_order(order_id: str) -> str:
    """One workflow per order; a deterministic id enables reject-duplicate."""
    return f"order-supervisor::{order_id}"


class OrderAlreadySupervised(RuntimeError):
    """A workflow for this order id already exists."""


async def start_order_workflow(inp: OrderSupervisorInput) -> str:
    """Start the one workflow for this order. Returns its workflow id, or raises
    OrderAlreadySupervised if one already exists."""
    client = await get_client()
    wf_id = workflow_id_for_order(inp.order_id)
    try:
        await client.start_workflow(
            OrderSupervisorWorkflow.run,
            inp,
            id=wf_id,
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError as exc:
        raise OrderAlreadySupervised(wf_id) from exc
    return wf_id


def _handle(workflow_id: str) -> WorkflowHandle:
    assert _client is not None, "Temporal client not connected"
    return _client.get_workflow_handle(workflow_id)


async def signal_incoming_event(workflow_id: str, event: dict) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.incoming_event, event)


async def signal_manual_instruction(workflow_id: str, text: str) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.manual_instruction, text)


async def signal_interrupt(workflow_id: str, reason: str) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.interrupt, reason)


async def signal_pause(workflow_id: str) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.pause)


async def signal_resume(workflow_id: str) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.resume)


async def signal_terminate(workflow_id: str, reason: str) -> None:
    await get_client()
    await _handle(workflow_id).signal(OrderSupervisorWorkflow.terminate, reason)


async def query_status(workflow_id: str) -> dict | None:
    """Live snapshot from the workflow's `status` query, or None if it can't be
    reached (closed, not found, worker down). Best effort; the UI still has the
    DB row."""
    try:
        await get_client()
        return await _handle(workflow_id).query(OrderSupervisorWorkflow.status)
    except Exception:  # noqa: BLE001
        return None
