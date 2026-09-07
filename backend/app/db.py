"""asyncpg connection pool + schema bootstrap.

Thin data-access layer. Query helpers live next to the routes/activities that
use them; this module only owns the pool lifecycle and schema creation.
"""
from __future__ import annotations

from pathlib import Path

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"


async def connect() -> asyncpg.Pool:
    """Create the global pool (idempotent) and ensure the schema exists."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            # Always resolve unqualified names inside our isolated schema.
            server_settings={"search_path": f"{settings.db_schema},public"},
        )
        await _ensure_schema(_pool)
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised - call db.connect() first")
    return _pool


async def _ensure_schema(p: asyncpg.Pool) -> None:
    ddl = _SCHEMA_FILE.read_text(encoding="utf-8").format(schema=settings.db_schema)
    async with p.acquire() as conn:
        await conn.execute(ddl)


# TODO(scaffold): add typed query helpers as the API/activities are implemented,
# e.g. create_run(), get_run(), append_activity(), update_run_state(), etc.
