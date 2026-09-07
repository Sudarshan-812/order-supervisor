# Order Supervisor

A POC for a **long-running AI supervisor** that oversees a single order from
creation to completion. One [Temporal](https://temporal.io) workflow runs per
order; order events arrive as signals; an LLM agent decides when to act, when to
sleep, and when to wake up again — it is **not** a tight loop.

> **Status: working end to end.** FastAPI → Temporal → `OrderSupervisorWorkflow`
> → activities → Postgres, driven by a Next.js UI. One workflow per order;
> events as signals; a lightweight classifier gates wake/sleep; the agent
> reasons, runs the 5 business actions, refreshes a compact memory, authors its
> own wake-up guidance, and picks its next sleep. Completion is **workflow-owned**
> (terminal event / manual terminate / max age), never agent-owned.

## What a run looks like

Feeding the `payment_trouble` scenario into a live run (real Gemini):

```
event: run_created
agent wake (start)          → message_customer ("order received…"), create_internal_note, sleep 3600s
event: order_created        → classifier: stay asleep (routine)
event: payment_failed       → classifier: WAKE (high)   → agent wakes
                              message_customer ("card was declined, please update…"), create_internal_note, sleep
event: customer_message      → classifier: WAKE (high)
event: payment_confirmed     → classifier: WAKE (medium) — "matches the agent's wake-up guidance"
event: shipment_created      → classifier: stay asleep (routine)
event: delivered             → TERMINAL → workflow runs produce_final_output → status "completed"

Final output: summary · important actions · key learnings · feedback
```

The classifier's `WAKE (medium) — matches the agent's wake-up guidance` line is
the agent steering its own future wake-ups: on an earlier wake it wrote
*"Wake immediately on payment, fulfillment, logistics, customer message, or
cancellation status events."* into workflow state, and the classifier now honours it.

## Stack

| Layer         | Choice                                    |
| ------------- | ----------------------------------------- |
| Frontend      | Next.js (App Router) + Tailwind CSS       |
| Backend       | Python + FastAPI                          |
| Orchestration | Temporal Python SDK (`temporalio`)        |
| Persistence   | PostgreSQL (developed against Neon)       |
| LLM           | Google Gemini (`google-genai`) — or a deterministic built-in mock |

No LangChain / LlamaIndex — raw API calls, frozen Pydantic schemas for the
agent/classifier contracts.

## Data model — 3 tables (`backend/schema.sql`)

| Table          | Holds |
| -------------- | ----- |
| `supervisors`  | reusable templates: `name`, `base_instruction`, `model_config` (allowed actions, default wake minutes, wake aggressiveness, model overrides) |
| `runs`         | one per order: `order_id`, `status` (`active`/`sleeping`/`completed`/`terminated`), `memory_summary`, `workflow_id`, `next_wake_at` |
| `activity_log` | one append-only log per run — `type` ∈ `incoming_event` · `wake_decision` (classifier verdicts *and* agent wake outcomes incl. chosen sleep) · `agent_action` · `manual_instruction` · `final_output`; `payload` JSONB |

Agent-authored wake-up guidance and last reasoning live in **workflow state**
(exposed via the `status` query, carried across `continue_as_new`).

## Layout

```
backend/app/
  main.py · config.py · db.py · models.py · event_generator.py
  api/routes.py                 HTTP surface
  temporal/
    client.py                   client + start/signal helpers
    worker.py                   worker entrypoint
    workflows.py                OrderSupervisorWorkflow (deterministic)
    activities.py               append_activity · persist_run_state · classify_event · run_agent · produce_final_output
  agent/
    runtime.py                  main agent — one model round-trip per wake
    classifier.py               lightweight wake-up policy
    memory.py                   working context + tail compaction
    prompts.py · llm.py         prompt builders · Gemini wrapper + mock
  scripts/dev_stack.py          one-process API + worker + in-proc Temporal
backend/schema.sql              the 3 tables
backend/tests/                  test_smoke.py (unit) · test_e2e.py (RUN_E2E=1)
frontend/src/app/               / (runs) · /supervisors · /runs/[runId]
frontend/src/lib/api.ts         typed backend client
```

## Quick start

### Prerequisites

- Python 3.11+ (tested on 3.13), Node.js 20+
- A Postgres URL in `backend/.env` (`DATABASE_URL`). The backend runs the
  idempotent `schema.sql` on startup, or paste it into your SQL editor.
- `GEMINI_API_KEY` in `backend/.env` for real reasoning — **leave blank for
  deterministic mock mode** (instant, offline, fully exercises the system).

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # PowerShell: .venv\Scripts\Activate.ps1 · bash/mac: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # bash/mac: cp .env.example .env   — then set DATABASE_URL (+ GEMINI_API_KEY)
```

**Fastest — one process** (in-process Temporal + worker + API, no Temporal CLI needed):

```bash
python -m scripts.dev_stack                       # API on http://localhost:8000  (docs: /docs)
```

**Or the real setup — three terminals** (persistent Temporal + its web UI on :8233):

```bash
temporal server start-dev                         # 1 · needs the CLI: `winget install Temporal.CLI` / `scoop install temporal`
uvicorn app.main:app --reload --port 8000         # 2 · API
python -m app.temporal.worker                     # 3 · Temporal worker
```

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local                # bash/mac: cp …
npm run dev                                        # http://localhost:3000
```

Open http://localhost:3000 → **Supervisors** (create a template) → **Runs**
(start a run for an order) → open the run → use the control panel.

## Using it

**In the UI** (`/runs/[runId]` control panel):

- **Event generator** — replay a scenario (`happy_path`, `payment_trouble`,
  `delayed_shipment`, `unknown_event`) into the run
- **Inject event** — one event with a JSON payload (try a custom type like
  `warehouse_fire` → unknown-event escalation)
- **Add instruction** — run-specific instruction added to a live run's context
- **Lifecycle** — Pause / Resume · Interrupt (force an immediate wake, non-terminal)
  · Terminate (workflow-owned completion)

**From the CLI / API:**

```bash
python -m app.event_generator <run_id> --scenario payment_trouble
# or:  POST /api/runs/<run_id>/simulate?scenario=payment_trouble
```

## API

| Method & path | Purpose |
| --- | --- |
| `POST /api/supervisors` · `GET /api/supervisors[/{id}]` | supervisor templates (name, base instruction, allowed actions, default wake minutes, wake aggressiveness) |
| `POST /api/runs` | start one workflow per order (reject-duplicate → `409`) |
| `GET /api/runs?status=` · `GET /api/runs/{id}` | run list · run + `activity_log` timeline + live `status` snapshot |
| `GET /api/runs/{id}/activities?type=` | filtered timeline |
| `POST /api/runs/{id}/events` | `incoming_event` signal |
| `POST /api/runs/{id}/instructions` | `manual_instruction` signal |
| `POST /api/runs/{id}/pause` · `/resume` | halt / restart agent inference |
| `POST /api/runs/{id}/interrupt` | force an immediate wake (non-terminal) |
| `POST /api/runs/{id}/terminate` | workflow-owned completion |
| `POST /api/runs/{id}/simulate?scenario=` · `GET /api/scenarios` | event generator |

## How the agent behaves

- **Three inference triggers**: workflow start, an `incoming_event` the
  classifier deems important, and the scheduled wake-up timer. The main loop is a
  single `workflow.wait_condition(..., timeout = next_wake - now)` — no polling.
- **Classifier** (`agent/classifier.py`, cheap / mostly rule-based): known
  important types wake now; agent-authored guidance can promote an otherwise
  routine event; known routine types stay asleep; unknown types get one cheap LLM
  check, then the supervisor's **wake aggressiveness** (`passive` / `balanced` /
  `aggressive`) decides the borderline cases. Unknown events fail safe to waking.
- **Agent** (`agent/runtime.py`): one model round-trip per wake → a frozen
  `AgentDecision` — actions to take, refreshed memory summary, refreshed wake-up
  guidance, next sleep seconds (workflow clamps to `[1 min, 24 h]`), optional
  completion recommendation.
- **5 business actions**: `message_fulfillment_team`, `message_payments_team`,
  `message_logistics_team`, `message_customer`, `create_internal_note`. Mocked —
  each writes an `activity_log` row (`type = agent_action`).
- **Memory**: the agent rewrites `runs.memory_summary` every wake; when
  `activity_log` grows past a threshold the old tail is summarised into it.
  Very long histories → `continue_as_new` carrying the compact state.

See `ARCHITECTURE.md` for the full design.

## Tests

```bash
cd backend

pytest                              # unit / smoke — no servers, no network

RUN_E2E=1 pytest tests/test_e2e.py -s
#   full integration: spins up an in-process Temporal + worker, drives the real
#   FastAPI app over ASGI against your Postgres, and exercises one workflow per
#   order, wake/sleep, the 5 actions, pause/resume/interrupt/terminate, the event
#   generator, and workflow-owned completion. Creates rows and deletes them. ~1 min.
```

## Notes & limitations

- **Mock vs real LLM**: mock mode (`GEMINI_API_KEY` blank) is deterministic and
  instant. With a real key the agent's text is richer; if Gemini returns
  transient `503`s the built-in retry/backoff makes a wake take ~20–30 s.
- `paused` is workflow state, not a `runs.status` value (that enum is fixed to
  the four spec values) — it shows on the run-detail page, not the dashboard list.
- Out of scope by design: auth, multi-tenant hardening, real integrations, visual polish.

## Deliverables

- **Source code** — this repo.
- **README** — this file · **Architecture note** — `ARCHITECTURE.md`.
- **Walkthrough** — `WALKTHROUGH.md`, a scripted run-through (create supervisor →
  start run → events → sleep/wake → actions → instruction → pause/resume →
  interrupt/terminate → final output). Record a screen capture from it.

### Acceptance criteria → where each is met

| Criterion | Where |
| --- | --- |
| one Temporal workflow per order | `temporal/client.py` `start_order_workflow` (reject-duplicate id policy) |
| order events as signals | `workflows.py` `incoming_event` |
| wake on start / signal / scheduled | `run()` initial wake · `classify_event` · `wait_condition` timeout |
| sleep & wake later | `AgentDecision.next_sleep_seconds` → `wait_condition(timeout=…)` |
| execute the 5 business actions, stored as activity records | `activities.py` `run_agent` → `activity_log` (`type=agent_action`) |
| event + action history in the UI | `/runs/[runId]` timeline |
| timeline + compact memory + status + next wake | `activity_log` + `runs` (`memory_summary`, `status`, `next_wake_at`) + `agent/memory.py` |
| inject events + extra instructions from the UI | run-detail control panel |
| final summary + learnings + feedback | `produce_final_output` → `final_output` row + workflow return value |
| pause / resume / interrupt / terminate | signals + endpoints + UI Lifecycle card |
| workflow-owned completion | `workflows.py` — terminal event / `terminate` signal / `MAX_WORKFLOW_AGE_HOURS` |
| context compaction | `agent/memory.py` `maybe_compact` + `continue_as_new` |
| (extra) agent-generated wake-up guidance · unknown-event escalation · wake aggressiveness | `agent/classifier.py`, `AgentDecision.wakeup_guidance` |
