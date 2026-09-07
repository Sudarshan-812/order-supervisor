"""Full integration test: FastAPI -> Temporal -> Neon.

Spins up an in-process Temporal server + worker, drives the real FastAPI app
over ASGI, and writes/reads the real database in DATABASE_URL. It creates rows
and deletes them again at the end.

Skipped unless RUN_E2E=1 (it needs network: your Neon DB, plus a one-time
download of the Temporal test-server binary).

    cd backend
    RUN_E2E=1 .venv/Scripts/python.exe -m pytest tests/test_e2e.py -s
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1",
    reason="integration test - set RUN_E2E=1 (needs Neon + Temporal test server)",
)

TQ = "order-supervisor-e2e"


async def _wait_for(fn, desc, tries=80, delay=0.25):
    for _ in range(tries):
        if await fn():
            return
        await asyncio.sleep(delay)
    raise AssertionError(f"timeout waiting for: {desc}")


@pytest.mark.asyncio
async def test_full_order_lifecycle():
    os.environ.setdefault("GEMINI_API_KEY", "")  # force mock LLM for determinism

    import httpx
    from httpx import ASGITransport
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Worker

    from app import db
    from app.config import settings
    from app.main import app
    from app.temporal import client as tc
    from app.temporal.activities import ALL_ACTIVITIES
    from app.temporal.workflows import OrderSupervisorWorkflow

    env = await WorkflowEnvironment.start_local()
    async with env:
        tc._client = env.client
        settings.temporal_task_queue = TQ
        await db.connect()
        worker = Worker(
            env.client, task_queue=TQ,
            workflows=[OrderSupervisorWorkflow], activities=ALL_ACTIVITIES,
        )
        sup_ids: list[str] = []
        run_ids: list[str] = []
        try:
            async with worker, httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://t"
            ) as h:
                # ---- supervisor with explicit config knobs ----
                r = await h.post("/api/supervisors", json={
                    "name": "e2e", "base_instruction": "Supervise the order.",
                    "allowed_actions": ["message_payments_team", "message_customer"],
                    "default_wake_minutes": 720, "wake_aggressiveness": "aggressive",
                })
                assert r.status_code == 201, r.text
                sup = r.json(); sup_ids.append(sup["id"])
                assert sup["model_settings"]["wake_aggressiveness"] == "aggressive"

                # ---- start ONE workflow per order ----
                oid = f"e2e-{uuid.uuid4().hex[:8]}"
                r = await h.post("/api/runs", json={
                    "supervisor_id": sup["id"], "order_id": oid,
                    "order_context": {"sku": "X"}, "run_instructions": ["keep the customer posted"],
                })
                assert r.status_code == 201, r.text
                run = r.json(); rid = run["id"]; wf = run["workflow_id"]; run_ids.append(rid)
                assert wf == f"order-supervisor::{oid}"

                # duplicate order -> 409
                r = await h.post("/api/runs", json={"supervisor_id": sup["id"], "order_id": oid})
                assert r.status_code == 409

                async def detail():
                    return (await h.get(f"/api/runs/{rid}")).json()

                async def has_agent_wake():
                    return any(
                        a["type"] == "wake_decision" and a["payload"].get("stage") == "agent"
                        for a in (await detail())["timeline"]
                    )

                # ---- wake on start; reasoning + guidance in workflow state ----
                await _wait_for(has_agent_wake, "initial agent wake")
                live = (await detail())["live"]
                assert live["processed_wakes"] >= 1
                assert live["last_reasoning"] and live["wakeup_guidance"]

                # ---- pause: event queues, no wake ----
                assert (await h.post(f"/api/runs/{rid}/pause")).status_code == 202
                await _wait_for(lambda: _flag(detail, "paused", True), "paused")
                held = (await detail())["live"]["processed_wakes"]
                await h.post(f"/api/runs/{rid}/events", json={"type": "customer_message_received"})
                await asyncio.sleep(2)
                lv = (await detail())["live"]
                assert lv["processed_wakes"] == held and lv["queued_events"] >= 1

                # ---- resume: drains + wakes ----
                assert (await h.post(f"/api/runs/{rid}/resume")).status_code == 202
                await _wait_for(lambda: _gt(detail, "processed_wakes", held), "resume wake")

                # ---- interrupt: immediate wake, non-terminal ----
                w = (await detail())["live"]["processed_wakes"]
                assert (await h.post(f"/api/runs/{rid}/interrupt")).status_code == 202
                await _wait_for(lambda: _gt(detail, "processed_wakes", w), "interrupt wake")
                assert (await detail())["run"]["status"] != "terminated"

                # ---- event generator: scenario ends with a terminal event ----
                r = await h.post(f"/api/runs/{rid}/simulate?scenario=payment_trouble&delay_s=0.4")
                assert r.status_code == 202
                await _wait_for(
                    lambda: _has_action(detail, "message_payments_team"),
                    "agent messaged payments team",
                )
                handle = env.client.get_workflow_handle(wf)
                final = await asyncio.wait_for(handle.result(), timeout=30)
                assert set(final) >= {"summary", "important_actions", "key_learnings", "feedback"}

                d = await detail()
                assert d["run"]["status"] == "completed"
                assert any(a["type"] == "final_output" for a in d["timeline"])

                # ---- a second run, manually terminated ----
                r = await h.post("/api/runs", json={"supervisor_id": sup["id"], "order_id": oid + "-b"})
                run2 = r.json(); run_ids.append(run2["id"])
                await asyncio.sleep(1)
                assert (await h.post(f"/api/runs/{run2['id']}/terminate")).status_code == 202
                await asyncio.wait_for(
                    env.client.get_workflow_handle(run2["workflow_id"]).result(), timeout=30
                )
                assert (await h.get(f"/api/runs/{run2['id']}")).json()["run"]["status"] == "terminated"
        finally:
            async with db.pool().acquire() as c:
                for x in run_ids:
                    await c.execute("DELETE FROM runs WHERE id = $1", x)
                for x in sup_ids:
                    await c.execute("DELETE FROM supervisors WHERE id = $1", x)
            await db.disconnect()


async def _flag(detail_fn, key, val):
    lv = (await detail_fn())["live"]
    return lv and lv.get(key) == val


async def _gt(detail_fn, key, n):
    lv = (await detail_fn())["live"]
    return lv and lv[key] > n


async def _has_action(detail_fn, tool):
    return any(
        a["type"] == "agent_action" and a["payload"].get("tool") == tool
        for a in (await detail_fn())["timeline"]
    )
