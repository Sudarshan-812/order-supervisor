# Walkthrough

A scripted run-through that exercises every acceptance criterion. Follow it as-is
to record the demo video. Times assume **mock mode** (no `GEMINI_API_KEY`);
with a real key the agent's text is richer but the flow is identical.

## 0. Start the stack

```bash
temporal server start-dev                                   # :7233, UI :8233
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && python -m app.temporal.worker
cd frontend && npm run dev                                  # http://localhost:3000
```

Open <http://localhost:3000>.

## 1. Create a supervisor config  → `/supervisors`

- **Name**: `Standard order supervisor`
- **Base instruction**: keep the default (or: "Supervise this order to delivery.
  Keep the customer informed, escalate payment problems to the payments team and
  shipping problems to logistics, and don't spam the customer.")
- **Available actions**: leave all 5 checked (= all allowed)
- **Default wake (minutes)**: `60`
- **Wake aggressiveness**: `balanced`
- **Create** → the template appears with its `model_config` JSON.

## 2. Start a run  → `/` (dashboard)

In **Start a run**:
- **Supervisor template**: the one you just made
- **Order ID**: `order-1001`
- **order_context**: `{ "sku": "WIDGET-1", "value": 149, "customer": "Priya" }`
- **run_instructions**: `keep Priya updated at every step`
- **Start run** → a row appears; click it to open `/runs/<id>`.

On the detail page you should immediately see (it may take ~1s, the page polls
every 3s):
- **status** `sleeping`, a **next wake** ~1h out
- **agent wakes** `1` (the start wake)
- **agent wake-up guidance**: a line the agent authored for the classifier
- **Timeline**: `run_created` → `agent wake (start) → sleep ...s`

## 3. Send events, watch classify then wake then act then sleep

Use the **Event generator** panel → scenario **`payment_trouble`** → **Run
scenario**. It fires, 2s apart:
`order_created → payment_failed → customer_message_received → payment_confirmed
→ shipment_created → delivered`.

Watch the timeline:
- `order_created` → classifier row **stay asleep** (routine)
- `payment_failed` → classifier row **WAKE (high)** → `agent wake (event)` →
  **`agent_action: message_payments_team`**
- `customer_message_received` → **WAKE** → `agent_action: message_customer`
- routine events → classifier keeps it asleep
- `delivered` → **workflow-owned completion**: `final_output` row, **status
  `completed`**, and the **Final output** card renders summary / important
  actions / key learnings / feedback.

(Manual single events: the **Inject event** panel sends one event with a JSON
payload. Try a custom type like `warehouse_fire` to see the unknown-event
escalation path.)

## 4. Add an instruction to a live run

Start a second run (`order-1002`). While it's `sleeping`, use **Add instruction**:
> If shipment is delayed, escalate to logistics immediately and offer a credit.

Timeline shows a `manual_instruction` row and an immediate `agent wake
(instruction)`. The instruction now shows under **standing instructions** and is
part of every future prompt. Fire the **`delayed_shipment`** scenario and watch
the agent act on `shipment_delayed` per the new instruction.

## 5. Pause / resume

On a live run, **Lifecycle → Pause**. The header shows a **paused** badge and
`paused = true`. Send an event: it shows in the timeline and **queued events**
increments, but **agent wakes** does *not*. **Resume** → the agent wakes once and
drains the queue.

## 6. Interrupt vs terminate

- **Interrupt (wake now)**: forces an immediate agent wake to re-assess; the run
  stays alive (status returns to `sleeping` afterwards).
- **Terminate**: confirm the dialog; the workflow runs the final-output step and
  exits with status **`terminated`**; the **Final output** card renders.

## 7. Persistence check (optional)

Every row above is in Neon:

```sql
select type, count(*) from activity_log group by 1 order by 2 desc;
select id, order_id, status, memory_summary from runs;
```

## What this demonstrates

one workflow per order · events as signals · wake on start/signal/schedule ·
sleep & wake later · the 5 business actions stored as activity records · timeline
+ compact memory + status + next-wake · inject events & instructions from the UI ·
pause / resume / interrupt / terminate · workflow-owned completion with a final
summary, learnings and feedback · (extras) agent-authored wake-up guidance,
unknown-event escalation, wake-aggressiveness knob, `continue_as_new`.
