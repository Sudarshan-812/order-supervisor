"""HTTP API surface.

Every handler is a scaffold stub. The intended behaviour is described in each
docstring; wiring is:

    supervisors  -> DB only
    runs (POST)  -> DB row + start Temporal workflow (one per order)
    events       -> Temporal signal `order_event`
    instructions -> Temporal signal `add_instruction`
    interrupt    -> Temporal signal `pause`
    resume       -> Temporal signal `resume`
    terminate    -> Temporal signal `terminate` (workflow-owned completion)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import (
    Activity,
    InstructionIn,
    OrderEvent,
    Run,
    RunCreate,
    RunDetail,
    Supervisor,
    SupervisorCreate,
)

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Supervisor templates
# --------------------------------------------------------------------------- #
@router.post("/supervisors", response_model=Supervisor, status_code=201)
async def create_supervisor(body: SupervisorCreate) -> Supervisor:
    """Insert a supervisor template row and return it."""
    raise HTTPException(501, "scaffold: not implemented")


@router.get("/supervisors", response_model=list[Supervisor])
async def list_supervisors() -> list[Supervisor]:
    raise HTTPException(501, "scaffold: not implemented")


@router.get("/supervisors/{supervisor_id}", response_model=Supervisor)
async def get_supervisor(supervisor_id: str) -> Supervisor:
    raise HTTPException(501, "scaffold: not implemented")


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
@router.post("/runs", response_model=Run, status_code=201)
async def create_run(body: RunCreate) -> Run:
    """Create a run row and start exactly one Temporal workflow for the order
    (workflow id = ``order-supervisor::{order_id}``, reject-duplicate policy)."""
    raise HTTPException(501, "scaffold: not implemented")


@router.get("/runs", response_model=list[Run])
async def list_runs(status: str | None = None) -> list[Run]:
    """List active + completed runs (optionally filtered by status)."""
    raise HTTPException(501, "scaffold: not implemented")


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str) -> RunDetail:
    """Return the run record + full activity timeline + memory summary."""
    raise HTTPException(501, "scaffold: not implemented")


@router.get("/runs/{run_id}/activities", response_model=list[Activity])
async def get_run_activities(run_id: str, kind: str | None = None) -> list[Activity]:
    raise HTTPException(501, "scaffold: not implemented")


# --------------------------------------------------------------------------- #
# Signals into a live run
# --------------------------------------------------------------------------- #
@router.post("/runs/{run_id}/events", status_code=202)
async def inject_event(run_id: str, event: OrderEvent) -> dict:
    """Deliver an order event into the workflow via the ``order_event`` signal."""
    raise HTTPException(501, "scaffold: not implemented")


@router.post("/runs/{run_id}/instructions", status_code=202)
async def add_instruction(run_id: str, body: InstructionIn) -> dict:
    """Append a run-specific instruction (``add_instruction`` signal)."""
    raise HTTPException(501, "scaffold: not implemented")


@router.post("/runs/{run_id}/interrupt", status_code=202)
async def interrupt_run(run_id: str) -> dict:
    """Pause agent inference (``pause`` signal). Events still queue."""
    raise HTTPException(501, "scaffold: not implemented")


@router.post("/runs/{run_id}/resume", status_code=202)
async def resume_run(run_id: str) -> dict:
    raise HTTPException(501, "scaffold: not implemented")


@router.post("/runs/{run_id}/terminate", status_code=202)
async def terminate_run(run_id: str) -> dict:
    """Request workflow-owned completion (``terminate`` signal): the workflow
    runs the agent's final-output step, then exits."""
    raise HTTPException(501, "scaffold: not implemented")
