"""Event generator / simulator.

Two ways to use it:
  * CLI:   python -m app.event_generator <run_id> --scenario happy_path
  * import: `SCENARIOS` is also reused by an optional API route.

It sends events into a run by calling the FastAPI endpoint
POST /api/runs/{run_id}/events (which forwards them as `order_event` signals),
so it exercises the real path.
"""
from __future__ import annotations

import argparse

SCENARIOS: dict[str, list[dict]] = {
    "happy_path": [
        {"type": "order_created"},
        {"type": "payment_confirmed"},
        {"type": "shipment_created"},
        {"type": "delivered"},
    ],
    "payment_trouble": [
        {"type": "order_created"},
        {"type": "payment_failed", "payload": {"reason": "card_declined"}},
        {"type": "customer_message_received", "payload": {"text": "why did my payment fail?"}},
        {"type": "payment_confirmed"},
        {"type": "shipment_created"},
        {"type": "delivered"},
    ],
    "delayed_shipment": [
        {"type": "order_created"},
        {"type": "payment_confirmed"},
        {"type": "shipment_created"},
        {"type": "shipment_delayed", "payload": {"eta_days": 5}},
        {"type": "no_update_for_n_hours", "payload": {"hours": 48}},
        {"type": "refund_requested"},
    ],
    "unknown_event": [
        {"type": "order_created"},
        {"type": "warehouse_fire", "payload": {"severity": "high"}},  # escalation path
    ],
}


async def send_scenario(run_id: str, scenario: str, *, base_url: str = "http://localhost:8000", delay_s: float = 1.0) -> None:
    """TODO(scaffold): httpx.AsyncClient loop posting each event with `delay_s`
    between them so you can watch the agent wake / sleep."""
    raise NotImplementedError("scaffold: send_scenario")


def _cli() -> None:
    p = argparse.ArgumentParser(description="Send a canned event scenario into a run")
    p.add_argument("run_id")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="happy_path")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    import asyncio

    asyncio.run(send_scenario(args.run_id, args.scenario, base_url=args.base_url, delay_s=args.delay))


if __name__ == "__main__":
    _cli()
