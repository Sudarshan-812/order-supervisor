"""HTTP API surface.

Wiring:
    supervisors        -> DB only
    POST /runs         -> DB row + start ONE Temporal workflow for the order
    GET  /runs[/{id}]  -> DB row(s) + activity_log timeline + live status query
    /events            -> `incoming_event`     signal
    /instructions      -> `manual_instruction` signal
    /interrupt         -> `interrupt`          signal (workflow-owned completion)
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import db
from app.models import (
    ActivityLogRow,
    IncomingEvent,
    ManualInstruction,
    Run,
    RunCreate,
    RunDetail,
    Supervisor,
    SupervisorCreate,
)
from app.temporal import client as tc
from app.temporal.workflows import OrderSupervisorInput

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Row -> model mappers
# --------------------------------------------------------------------------- #
def _supervisor(row: Any) -> Supervisor:
    return Supervisor(
        id=str(row["id"]),
        name=row["name"],
        base_instruction=row["base_instruction"],
        model_settings=row["model_config"] or {},
        created_at=row["created_at"],
    )


def _run(row: Any) -> Run:
    return Run(
        id=str(row["id"]),
        order_id=row["order_id"],
        supervisor_id=str(row["supervisor_id"]),
        status=row["status"],
        memory_summary=row["memory_summary"],
        workflow_id=row["workflow_id"],
        next_wake_at=row["next_wake_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _activity(row: Any) -> ActivityLogRow:
    return ActivityLogRow(
        id=row["id"],
        run_id=str(row["run_id"]),
        type=row["type"],
        payload=row["payload"] or {},
        created_at=row["created_at"],
    )


async def _load_run_or_404(run_id: str) -> Any:
    try:
        row = await db.fetch_run(run_id)
    except Exception as exc:  # bad uuid etc.
        raise HTTPException(400, f"bad run id: {exc}") from exc
    if row is None:
        raise HTTPException(404, "run not found")
    return row


async def _load_supervisor_or_404(supervisor_id: str) -> Any:
    try:
        row = await db.fetch_supervisor(supervisor_id)
    except Exception as exc:  # bad uuid etc.
        raise HTTPException(400, f"bad supervisor id: {exc}") from exc
    if row is None:
        raise HTTPException(404, "supervisor not found")
    return row


# --------------------------------------------------------------------------- #
# Supervisor templates
# --------------------------------------------------------------------------- #
@router.post("/supervisors", response_model=Supervisor, status_code=201)
async def create_supervisor(body: SupervisorCreate) -> Supervisor:
    row = await db.create_supervisor(
        body.name, body.base_instruction, body.model_settings
    )
    return _supervisor(row)


@router.get("/supervisors", response_model=list[Supervisor])
async def list_supervisors() -> list[Supervisor]:
    return [_supervisor(r) for r in await db.list_supervisors()]


@router.get("/supervisors/{supervisor_id}", response_model=Supervisor)
async def get_supervisor(supervisor_id: str) -> Supervisor:
    return _supervisor(await _load_supervisor_or_404(supervisor_id))


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
@router.post("/runs", response_model=Run, status_code=201)
async def create_run(body: RunCreate) -> Run:
    """Create a run row and start exactly one Temporal workflow for the order
    (id = ``order-supervisor::{order_id}``, reject-duplicate)."""
    sup = await _load_supervisor_or_404(body.supervisor_id)
    cfg = sup["model_config"] or {}
    run_id = str(uuid.uuid4())
    await db.create_run(run_id, body.order_id, body.supervisor_id)

    inp = OrderSupervisorInput(
        run_id=run_id,
        supervisor_id=str(sup["id"]),
        order_id=body.order_id,
        base_instruction=sup["base_instruction"],
        order_context=body.order_context,
        run_instructions=body.run_instructions,
        allowed_actions=list(cfg.get("allowed_actions", [])),
        default_wake_minutes=int(cfg.get("default_wake_minutes", 60)),
    )
    try:
        wf_id = await tc.start_order_workflow(inp)
    except tc.OrderAlreadySupervised:
        await db.delete_run(run_id)
        raise HTTPException(409, f"order '{body.order_id}' is already being supervised")
    except Exception as exc:
        await db.delete_run(run_id)
        raise HTTPException(502, f"could not start workflow: {exc}") from exc

    await db.patch_run(run_id, workflow_id=wf_id)
    run_row = await db.fetch_run(run_id)
    return _run(run_row)


@router.get("/runs", response_model=list[Run])
async def list_runs(status: str | None = None) -> list[Run]:
    return [_run(r) for r in await db.list_runs(status)]


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str) -> RunDetail:
    row = await _load_run_or_404(run_id)
    timeline = [_activity(a) for a in await db.fetch_activities(run_id)]
    live = None
    if row["workflow_id"]:
        live = await tc.query_status(row["workflow_id"])
    return RunDetail(run=_run(row), timeline=timeline, live=live)


@router.get("/runs/{run_id}/activities", response_model=list[ActivityLogRow])
async def get_run_activities(run_id: str, type: str | None = None) -> list[ActivityLogRow]:
    await _load_run_or_404(run_id)
    types = [type] if type else None
    return [_activity(a) for a in await db.fetch_activities(run_id, types=types)]


# --------------------------------------------------------------------------- #
# Signals into a live run
# --------------------------------------------------------------------------- #
async def _signal_or_409(run_id: str, coro_factory) -> None:
    row = await _load_run_or_404(run_id)
    if not row["workflow_id"]:
        raise HTTPException(409, "run has no workflow (start failed?)")
    try:
        await coro_factory(row["workflow_id"])
    except Exception as exc:  # workflow closed / worker down / not found
        raise HTTPException(409, f"could not signal workflow: {exc}") from exc


@router.post("/runs/{run_id}/events", status_code=202)
async def inject_event(run_id: str, event: IncomingEvent) -> dict:
    """Deliver an order event into the workflow (`incoming_event` signal)."""
    payload = event.model_dump(mode="json")
    await _signal_or_409(run_id, lambda wf: tc.signal_incoming_event(wf, payload))
    return {"ok": True, "delivered": event.type}


@router.post("/runs/{run_id}/instructions", status_code=202)
async def add_instruction(run_id: str, body: ManualInstruction) -> dict:
    """Append a run-specific instruction (`manual_instruction` signal)."""
    await _signal_or_409(run_id, lambda wf: tc.signal_manual_instruction(wf, body.text))
    return {"ok": True}


@router.post("/runs/{run_id}/interrupt", status_code=202)
async def interrupt_run(run_id: str, reason: str = "manual interrupt") -> dict:
    """Request workflow-owned completion (`interrupt` signal): the workflow runs
    the agent's final-output step, then exits."""
    await _signal_or_409(run_id, lambda wf: tc.signal_interrupt(wf, reason))
    return {"ok": True}
