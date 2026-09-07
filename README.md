# Order Supervisor

A POC for a **long-running AI supervisor** that oversees a single order from
creation to completion. One [Temporal](https://temporal.io) workflow runs per
order; order events arrive as signals; an LLM agent decides when to act, when to
sleep, and when to wake up again.

> **Status: scaffold.** Project structure, config, and dependencies are in
> place. Business logic modules are stubbed with `NotImplementedError` /
> `TODO(scaffold)` and a docstring describing the intended behaviour.

## Stack

| Layer            | Choice                                  |
| ---------------- | --------------------------------------- |
| Frontend         | Next.js (App Router) + Tailwind CSS     |
| Backend          | Python + FastAPI                        |
| Orchestration    | Temporal Python SDK (`temporalio`)      |
| Persistence      | PostgreSQL (Supabase), isolated schema  |
| LLM              | Google Gemini (`google-genai`), mockable |

## Layout

```
order-supervisor/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app
│   │   ├── config.py            env-backed settings
│   │   ├── db.py                asyncpg pool + schema bootstrap
│   │   ├── models.py            enums + Pydantic models
│   │   ├── event_generator.py   CLI / scenario simulator
│   │   ├── api/routes.py        HTTP endpoints
│   │   ├── temporal/
│   │   │   ├── client.py        client factory
│   │   │   ├── worker.py        worker entrypoint
│   │   │   ├── workflows.py     OrderSupervisorWorkflow
│   │   │   └── activities.py    all side-effecting activities
│   │   └── agent/
│   │       ├── runtime.py       main agent (one run per wake)
│   │       ├── classifier.py    lightweight wake-up policy
│   │       ├── tools.py         tool registry
│   │       ├── memory.py        context compaction
│   │       ├── prompts.py       prompt templates
│   │       └── llm.py           Gemini wrapper + mock
│   ├── schema.sql              order_supervisor schema DDL
│   ├── requirements.txt
│   └── tests/
├── frontend/                   Next.js UI (runs, supervisors, run detail)
├── ARCHITECTURE.md
└── README.md
```

## Setup

### 0. Prerequisites

- Python 3.11+ (repo tested on 3.13)
- Node.js 20+
- A Temporal dev server. Install the CLI, then:
  ```
  temporal server start-dev
  ```
  Windows install options: `winget install Temporal.CLI` or
  `scoop install temporal` or see <https://docs.temporal.io/cli#install>.
  Temporal UI: <http://localhost:8233>.

### 1. Backend

```bash
cd backend
py -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # then fill in values
```

`.env` already points at the shared Supabase database with
`DB_SCHEMA=order_supervisor`, so tables are created in an isolated schema on
first boot. Leave `GEMINI_API_KEY` blank to run in deterministic **mock mode**.

Run (three terminals):

```bash
uvicorn app.main:app --reload --port 8000        # API
python -m app.temporal.worker                    # Temporal worker
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                                       # http://localhost:3000
```

### 3. Send events

```bash
cd backend
python -m app.event_generator <run_id> --scenario payment_trouble
```

## Tests

```bash
cd backend
pytest
```

## What still needs implementing

See `TODO(scaffold)` / `NotImplementedError` markers. High level:

1. `db.py` query helpers + `api/routes.py` handlers.
2. `temporal/workflows.py` main loop (wait_condition + timer, signal handling,
   workflow-owned completion, `continue_as_new`).
3. `temporal/activities.py` bodies (persistence, classifier, agent, tools).
4. `agent/*` runtime, classifier, memory compaction, real Gemini call in `llm.py`.
5. Frontend: wire pages to `lib/api.ts`, add polling.
