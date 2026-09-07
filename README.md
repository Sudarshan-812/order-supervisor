# Order Supervisor

A POC for a **long-running AI supervisor** that oversees a single order from
creation to completion. One [Temporal](https://temporal.io) workflow runs per
order; order events arrive as signals; an LLM agent decides when to act, when to
sleep, and when to wake up again.

> **Status: complete.** FastAPI → Temporal → `OrderSupervisorWorkflow` →
> activities → Neon, driven by a Next.js UI. One workflow per order; events as
> signals; a lightweight classifier gates wake/sleep; the agent reasons, runs
> the 5 business actions, refreshes memory, authors wake-up guidance, and picks
> its next sleep; completion is workflow-owned. Controls: inject events, add
> instructions, pause / resume / interrupt / terminate, and a scenario-based
> event generator. See `WALKTHROUGH.md` for a scripted demo.

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
`.env.example`), then create the tables — paste `backend/schema.sql` into the
Neon SQL editor, or `psql "$DATABASE_URL" -f schema.sql`. (The backend also runs
the idempotent `schema.sql` on startup.)

Leave `GEMINI_API_KEY` blank to run in deterministic **mock mode**; set it (and
`GEMINI_MODEL`) for real reasoning.

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

From the run-detail page's **Event generator** panel, or:

```bash
cd backend
python -m app.event_generator <run_id> --scenario payment_trouble
# scenarios: happy_path | payment_trouble | delayed_shipment | unknown_event
```

or hit the API: `POST /api/runs/<run_id>/simulate?scenario=payment_trouble`.

## Tests

```bash
cd backend
pytest
```

## API

| Method & path | Purpose |
| --- | --- |
| `POST /api/supervisors` · `GET /api/supervisors[/{id}]` | supervisor templates (name, base instruction, allowed actions, default wake minutes, wake aggressiveness) |
| `POST /api/runs` | start one workflow per order (reject-duplicate → `409`) |
| `GET /api/runs?status=` · `GET /api/runs/{id}` | run list / run + `activity_log` timeline + live `status` snapshot |
| `GET /api/runs/{id}/activities?type=` | filtered timeline |
| `POST /api/runs/{id}/events` | `incoming_event` signal |
| `POST /api/runs/{id}/instructions` | `manual_instruction` signal |
| `POST /api/runs/{id}/pause` · `/resume` | halt / restart agent inference |
| `POST /api/runs/{id}/interrupt` | force an immediate wake (non-terminal) |
| `POST /api/runs/{id}/terminate` | workflow-owned completion |
| `POST /api/runs/{id}/simulate?scenario=` · `GET /api/scenarios` | event generator |

## Acceptance criteria — where each is met

| Criterion | Where |
| --- | --- |
| one Temporal workflow per order | `temporal/client.py` `start_order_workflow` (reject-duplicate) |
| events as signals | `workflows.py` `incoming_event` |
| wake on start / signal / scheduled | `run()` initial wake · classifier · `wait_condition` timeout |
| sleep & wake later | `AgentDecision.next_sleep_seconds` → `wait_condition(timeout=…)` |
| execute the 5 business actions, stored as activity records | `activities.py` `run_agent` → `activity_log` rows (`type=agent_action`) |
| event + action history in the UI | `/runs/[runId]` timeline |
| timeline + compact memory | `activity_log` + `runs.memory_summary` (+ `agent/memory.py` compaction) |
| inject events + extra instructions from the UI | run-detail control panel |
| final summary + learnings + feedback | `produce_final_output` → `final_output` row + workflow return |
| pause / resume / interrupt / terminate | `pause`/`resume`/`interrupt`/`terminate` signals + endpoints + UI |

## Deliverables

- **Source code** — this repo.
- **README** — this file. **Architecture note** — `ARCHITECTURE.md`.
- **Walkthrough** — `WALKTHROUGH.md` is a scripted run-through (create supervisor →
  start run → events → sleep/wake → actions → instruction → interrupt/terminate →
  final output). Record a screen capture following it.
