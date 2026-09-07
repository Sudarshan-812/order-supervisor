"""Shared Temporal client factory (used by the API to start workflows / send
signals, and by scripts)."""
from __future__ import annotations

from temporalio.client import Client

from app.config import settings

_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
    return _client


def workflow_id_for_order(order_id: str) -> str:
    """One workflow per order - deterministic id enables reject-duplicate."""
    return f"order-supervisor::{order_id}"
