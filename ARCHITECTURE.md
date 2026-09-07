# Architecture note

## One workflow per order

`POST /api/runs` inserts a `runs` row (id generated client-side) and starts one
`OrderSupervisorWorkflow` with workflow id `order-supervisor::{order_id}` and a
**reject-duplicate** id-reuse policy, guaranteeing exactly one long-running
workflow per order. A duplicate `POST` returns `409`. The workflow is
initialised with the order context, the supervisor's base instruction, the
run's initial instructions, and the supervisor config knobs (allowed actions,
default wake minutes, wake aggressiveness).

## Three inference triggers

| Trigger              | Mechanism                                                        |
| -------------------- | --------------------------------------------------------------- |
| workflow start       | agent runs once immediately in `run()` (`reason="start"`)        |
| incoming event       | `incoming_event` signal → `classify_event` activity → maybe set `_agent_should_run` |
| scheduled wake-up    | `workflow.wait_condition(..., timeout = next_wake_at - now)`     |

The main loop is a single `wait_condition` that blocks on
`_agent_should_run or _terminate_requested`, with a timeout equal to the next
scheduled wake. No tight polling. Each agent run is a Temporal **activity**
(`run_agent`), so all LLM/DB side effects stay outside the deterministic
workflow. While **paused**, the loop parks on a second `wait_condition` and
never runs the agent (events still queue).

## Signals & lifecycle

| Signal                    | Effect                                                      |
| ------------------------- | ---------------------------------------------------------- |
| `incoming_event(event)`   | log it, classify it, maybe wake; terminal events → complete |
| `manual_instruction(text)`| appended to run context, wakes the agent                   |
| `pause()` / `resume()`    | halt / restart agent inference                             |
| `interrupt(reason)`       | force an immediate wake to re-assess (**non-terminal**)    |
| `terminate(reason)`       | workflow-owned completion → final output → exit            |

`status` query exposes: status, paused, next wake, queued events, standing
instructions, memory summary, **agent wake-up guidance**, **last reasoning**,
processed wakes.

## Wake / sleep

Every `incoming_event` is first passed to a **lightweight classifier**
(`agent/classifier.py`, activity `classify_event`):

1. known important type (`payment_failed`, `shipment_delayed`, `refund_requested`,
   `customer_message_received`, `order_cancelled`) → wake now
2. **agent-authored wake-up guidance**: crude token match against the event, wake now
3. known routine type → stay asleep (unless `wake_aggressiveness == "aggressive"`)
4. unknown type → one cheap LLM call, then the `wake_aggressiveness` knob
   (`passive` / `balanced` / `aggressive`) decides the borderline cases; the
   default is to wake, since over-waking is safer.

Only a wake-now verdict interrupts sleep; otherwise the event waits for the next
scheduled wake. The agent chooses its next sleep duration; the workflow clamps
it to `[1 min, 24 h]`.

## Memory & timeline

Three tables (`schema.sql`): `supervisors`, `runs`, `activity_log`. The single
`activity_log` stores every kind of record via its `type` column:
`incoming_event`, `wake_decision` (classifier verdicts *and* agent wake outcomes,
including the chosen sleep), `agent_action`, `manual_instruction`, `final_output`.

`runs` keeps the compact rolling `memory_summary`, `status`
(`active|sleeping|completed|terminated`), and `next_wake_at`. Agent-authored
wake-up guidance and last reasoning live in **workflow state** (surfaced via the
`status` query, carried across `continue_as_new`).

Compaction (`agent/memory.py`): the agent rewrites `memory_summary` every wake;
when `activity_log` grows past a threshold the old tail is summarised by the LLM
and folded into the summary so the prompt stays bounded. Very long histories
trigger `continue_as_new` carrying the compact state forward.

## Actions & runtime capabilities

Five mocked business actions (`message_{fulfillment,payments,logistics}_team`,
`message_customer`, `create_internal_note`). They are **not** separate Temporal
activities; `run_agent` performs each by writing an `activity_log` row
(`type = agent_action`). Runtime capabilities (choose next sleep, refresh memory
summary, author wake-up guidance, record reasoning, recommend completion) are
fields on the frozen `AgentDecision` and applied by the workflow.

## Workflow-owned completion

The agent can only *recommend* completion. The workflow ends when: a terminal
order event arrives (`delivered`, `order_cancelled`) → `completed`; the UI sends
`terminate` → `terminated`; or `MAX_WORKFLOW_AGE_HOURS` is exceeded →
`completed`. On completion the workflow runs `produce_final_output` (summary,
important actions, key learnings, feedback), writes it as a `final_output` row,
and returns it.

## Event generator

`app/event_generator.py` holds the canned `SCENARIOS`
(`happy_path`, `payment_trouble`, `delayed_shipment`, `unknown_event`). Two ways
to fire them:
* CLI: `python -m app.event_generator <run_id> --scenario payment_trouble`
* API: `POST /api/runs/{run_id}/simulate?scenario=...` (FastAPI background task
  to `incoming_event` signals, `delay_s` apart); also wired into the run-detail
  UI's control panel.

## Components

```
Next.js UI ──HTTP──▶ FastAPI ──┬── asyncpg ──▶ Postgres (Neon: supervisors/runs/activity_log)
                               └── Temporal client ──▶ Temporal server
                                                          │
                                        Worker ◀──────────┘
                                        ├─ OrderSupervisorWorkflow (deterministic)
                                        └─ activities: append_activity · persist_run_state ·
                                           classify_event · run_agent · produce_final_output
                                                          │
                                                    Gemini (google-genai) or deterministic mock
```
