"""One-process dev stack: in-process Temporal server + worker + FastAPI on :8000.

Use this when you don't want to install the Temporal CLI. It downloads a small
Temporal test-server binary on first run (cached afterwards).

    cd backend
    .venv/Scripts/python.exe -m scripts.dev_stack        # or: python scripts/dev_stack.py

Then the API is at http://localhost:8000 (docs at /docs) and the Next.js UI
(`npm run dev` in ../frontend) talks to it unchanged.

For the real setup (persistent Temporal + its web UI at :8233) install the CLI
and run the three processes separately - see README "Setup".
"""
from __future__ import annotations

import asyncio

import uvicorn
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app import db
from app.config import settings
from app.main import app
from app.temporal import client as tc
from app.temporal.activities import ALL_ACTIVITIES
from app.temporal.workflows import OrderSupervisorWorkflow

TASK_QUEUE = "order-supervisor-dev"


async def main() -> None:
    env = await WorkflowEnvironment.start_local()
    tc._client = env.client
    settings.temporal_task_queue = TASK_QUEUE
    await db.connect()

    worker = Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=ALL_ACTIVITIES,
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=settings.api_port, log_level="info")
    )

    async with env, worker:
        print(
            f"\n  dev stack up\n"
            f"  API   : http://127.0.0.1:{settings.api_port}  (docs: /docs)\n"
            f"  LLM   : {'gemini' if settings.llm_enabled else 'mock (no GEMINI_API_KEY)'}\n"
            f"  DB    : {settings.database_url.split('@')[-1].split('/')[0]}\n"
            f"  Ctrl-C to stop\n"
        )
        await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
