"""Event generator / simulator.

Two ways to use it:
  * CLI:  python -m app.event_generator <run_id> --scenario payment_trouble
  * API:  POST /api/runs/{run_id}/simulate?scenario=payment_trouble
          (app.api.routes imports SCENARIOS from here)

The CLI posts each event to POST /api/runs/{run_id}/events, which forwards it as
an incoming_event signal, so it exercises the real path end to end.
"""
from __future__ import annotations

import argparse
import asyncio

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
        {"type": "delivered"},
    ],
}


async def send_scenario(
    run_id: str,
    scenario: str,
    *,
    base_url: str = "http://localhost:8000",
    delay_s: float = 2.0,
) -> None:
    """POST each event of `scenario` to the run's /events endpoint, `delay_s`
    apart. Stops early if the run has already completed (409)."""
    import httpx

    events = SCENARIOS[scenario]
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        for i, ev in enumerate(events):
            if i:
                await asyncio.sleep(delay_s)
            body = {"payload": {}, **ev}
            resp = await client.post(f"/api/runs/{run_id}/events", json=body)
            print(f"  {ev['type']:<26} {resp.status_code} {resp.text.strip()[:80]}")
            if resp.status_code == 409:
                print("  run is no longer accepting events; stopping.")
                return
    print("scenario complete.")


def _cli() -> None:
    p = argparse.ArgumentParser(description="Send a canned event scenario into a run")
    p.add_argument("run_id")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="happy_path")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--delay", type=float, default=2.0)
    args = p.parse_args()
    print(f"sending '{args.scenario}' to run {args.run_id} via {args.base_url}")
    asyncio.run(
        send_scenario(args.run_id, args.scenario, base_url=args.base_url, delay_s=args.delay)
    )


if __name__ == "__main__":
    _cli()
