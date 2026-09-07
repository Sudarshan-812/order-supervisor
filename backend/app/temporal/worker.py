"""Temporal worker entrypoint.

Run:  python -m app.temporal.worker
Requires a Temporal server:  temporal server start-dev
"""
from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app import db
from app.config import settings
from app.temporal.activities import ALL_ACTIVITIES
from app.temporal.client import get_client
from app.temporal.workflows import OrderSupervisorWorkflow

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await db.connect()  # activities need the pool
    client = await get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[OrderSupervisorWorkflow],
        activities=ALL_ACTIVITIES,
    )
    logging.info("worker up on task queue %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
