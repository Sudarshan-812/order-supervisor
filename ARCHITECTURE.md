# Architecture note

## One workflow per order

`POST /api/runs` creates a `runs` row and starts one
`OrderSupervisorWorkflow` with workflow id `order-supervisor::{order_id}` and a
reject-duplicate policy, guaranteeing exactly one long-running workflow per
order. The workflow is initialised with the order context, the supervisor's
base instruction, and any initial run instructions.

## Three inference triggers

| Trigger              | Mechanism                                                        |
| -------------------- | --------------------------------------------------------------- |
| workflow start       | agent runs once immediately in `run()`                         |
| incoming event       | `order_event` signal → classifier → maybe set `agent_should_run` |
| scheduled wake-up    | `workflow.wait_condition(..., timeout=next_wake_at - now)`       |

The main loop is a single `wait_condition` that blocks on
`agent_should_run or done`, with a timeout equal to the next scheduled wake.
No tight polling. Each agent run is a Temporal **activity** (`run_agent`), so
all LLM/DB side effects stay outside the deterministic workflow.

## Wake / sleep

Every `order_event` is first passed to a **lightweight classifier**
(`agent/classifier.py`, activity `classify_event`): rule table first
(important set / routine set), then agent-authored `wakeup_guidance`, then an
"unknown event → escalate" default, modulated by the supervisor's
`wake_aggressiveness`. Only a wake-now verdict interrupts sleep; otherwise the
event is left in the queue for the next scheduled wake. The agent chooses its
next sleep duration; the workflow clamps it to `[1 min, 24 h]`.

## Memory & timeline

Single `activities` table per run stores events, wake/sleep decisions, agent
actions, reasoning, instructions, and final output. The run row keeps a compact
rolling `memory_summary` plus `status`, `sleep_state`, `next_wake_at`.
Compaction (`agent/memory.py`) summarises activities older than a recent window
into the rolling summary once the count crosses a threshold. Very long
histories trigger `continue_as_new` carrying the compact state forward.

## Tools

Five mocked business actions (`message_{fulfillment,payments,logistics}_team`,
`message_customer`, `create_internal_note`) — each is a Temporal activity that
only writes an `activities` row. Runtime capabilities (`sleep`,
`update_memory`, `record_reasoning`, `set_wakeup_guidance`,
`recommend_completion`) are folded into the `AgentDecision` and applied by the
workflow.

## Workflow-owned completion

The agent can only *recommend* completion. The workflow ends when: a terminal
order event arrives (`delivered`), the UI sends `terminate`, or
`MAX_WORKFLOW_AGE_HOURS` is exceeded. On completion the workflow runs
`produce_final_output` (summary, important actions, key learnings, feedback),
persists it to `runs.final_output`, and returns it.

## Components

```
Next.js UI ──HTTP──▶ FastAPI ──┬── asyncpg ──▶ Postgres (order_supervisor schema)
                               └── Temporal client ──▶ Temporal server
                                                          │
                                        Worker ◀──────────┘
                                        ├─ OrderSupervisorWorkflow (deterministic)
                                        └─ activities: persistence · classifier ·
                                           agent runtime · final output · tools
                                                          │
                                                    Gemini (or mock)
```
