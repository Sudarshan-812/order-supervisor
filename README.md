# Order Supervisor

A POC for a **long-running AI supervisor** that oversees a single order from
creation to completion. One [Temporal](https://temporal.io) workflow runs per
order; order events arrive as signals; an LLM agent decides when to act, when to
sleep, and when to wake up again.

> **Status: POC complete (Steps 1-4).** FastAPI -> Temporal client ->
> `OrderSupervisorWorkflow` -> activities -> Neon, driven by a Next.js UI
> (supervisor templates, runs dashboard + start-run, run detail with timeline /
> memory / final output, and a control panel to inject events + instructions +
> interrupt).

## Stack

| Layer            | Choice                                  |
| ---------------- | --------------------------------------- |
| Frontend         | Next.js (App Router) + Tailwind CSS     |
| Backend          | Python + FastAPI                        |
| Orchestration    | Temporal Python SDK (`temporalio`)      |
| Persistence      | PostgreSQL (Neon free tier)             |
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
│   ├── schema.sql              3-table DDL (run in any Postgres)
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

Set `DATABASE_URL` to your Neon **direct** connection string (see
`.env.example`), then create the tables:

```bash
psql "$DATABASE_URL" -f schema.sql
```

Leave `GEMINI_API_KEY` blank to run in deterministic **mock mode**.

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

## Build progress

- [x] **Step 1** - monorepo scaffold + `schema.sql` (3 tables on Neon).
- [x] **Step 2** - `OrderSupervisorWorkflow` (wait_condition loop, `incoming_event`
      / `manual_instruction` / `interrupt` signals, workflow-owned completion,
      `continue_as_new`) + activities (`classify_event`, `run_agent`,
      `produce_final_output`, persistence) + agent layer (`classifier`, `runtime`,
      `memory` compaction, real Gemini call + deterministic mock in `llm.py`).
- [x] **Step 3** - FastAPI routes wired to the Temporal client: `POST /api/runs`
      starts one workflow per order (reject-duplicate -> 409), `/events`,
      `/instructions`, `/interrupt` send signals, `GET /api/runs/{id}` returns
      the run + activity_log timeline + a live `status` query snapshot. Verified
      end-to-end against an in-process Temporal server + Neon.
- [x] **Step 4** - Next.js UI wired to the API: `/` runs dashboard + start-run
      panel, `/supervisors` template CRUD, `/runs/[runId]` timeline + memory +
      final output + control panel (inject event / add instruction / interrupt).
      3s polling; `npm run build` clean; verified through the dev proxy against
      a live backend.
