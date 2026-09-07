"""asyncpg connection pool + schema bootstrap + typed query helpers.

Thin data-access layer. The pool is process-global and created once; the
activities and (later) the API routes call the helpers below.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"

# Columns callers are allowed to patch on `runs`.
_RUN_PATCHABLE = {"status", "memory_summary", "workflow_id", "next_wake_at"}


# --------------------------------------------------------------------------- #
# Pool lifecycle
# --------------------------------------------------------------------------- #
async def _init_conn(conn: asyncpg.Connection) -> None:
    """Make JSON/JSONB columns marshal to/from python dicts automatically."""
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(
            typename, encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )


async def connect() -> asyncpg.Pool:
    """Create the global pool (idempotent) and ensure the schema exists."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            init=_init_conn,
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
    """Run schema.sql. It is fully idempotent (CREATE ... IF NOT EXISTS /
    CREATE OR REPLACE), so this is safe on every boot."""
    ddl = _SCHEMA_FILE.read_text(encoding="utf-8")
    async with p.acquire() as conn:
        await conn.execute(ddl)


# --------------------------------------------------------------------------- #
# activity_log
# --------------------------------------------------------------------------- #
async def insert_activity(
    run_id: str, type_: str, payload: dict[str, Any]
) -> asyncpg.Record:
    """Append one row to activity_log. Returns id + created_at."""
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO activity_log (run_id, type, payload)
            VALUES ($1, $2, $3)
            RETURNING id, created_at
            """,
            run_id,
            type_,
            payload,
        )


async def fetch_activities(
    run_id: str,
    *,
    limit: int | None = None,
    types: list[str] | None = None,
    newest_first: bool = False,
) -> list[asyncpg.Record]:
    """Read a run's activity_log, oldest-first by default."""
    where = ["run_id = $1"]
    args: list[Any] = [run_id]
    if types:
        args.append(types)
        where.append(f"type = ANY(${len(args)})")
    order = "DESC" if newest_first else "ASC"
    sql = f"SELECT id, run_id, type, payload, created_at FROM activity_log " \
          f"WHERE {' AND '.join(where)} ORDER BY id {order}"
    if limit is not None:
        args.append(limit)
        sql += f" LIMIT ${len(args)}"
    async with pool().acquire() as conn:
        return await conn.fetch(sql, *args)


async def count_activities(run_id: str) -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM activity_log WHERE run_id = $1", run_id
        )


# --------------------------------------------------------------------------- #
# runs
# --------------------------------------------------------------------------- #
_RUN_COLS = (
    "id, order_id, supervisor_id, status, memory_summary, "
    "workflow_id, next_wake_at, created_at, updated_at"
)


async def create_run(run_id: str, order_id: str, supervisor_id: str) -> asyncpg.Record:
    """Insert a run row (status 'active', empty memory). id is supplied by the
    caller so the workflow input can carry it before the workflow starts."""
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            f"""
            INSERT INTO runs (id, order_id, supervisor_id, status, memory_summary)
            VALUES ($1, $2, $3, 'active', '')
            RETURNING {_RUN_COLS}
            """,
            run_id,
            order_id,
            supervisor_id,
        )


async def delete_run(run_id: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute("DELETE FROM runs WHERE id = $1", run_id)


async def list_runs(status: str | None = None) -> list[asyncpg.Record]:
    args: list[Any] = []
    where = ""
    if status:
        args.append(status)
        where = "WHERE status = $1"
    async with pool().acquire() as conn:
        return await conn.fetch(
            f"SELECT {_RUN_COLS} FROM runs {where} ORDER BY created_at DESC", *args
        )


async def fetch_run(run_id: str) -> asyncpg.Record | None:
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            f"SELECT {_RUN_COLS} FROM runs WHERE id = $1", run_id
        )


async def patch_run(run_id: str, **fields: Any) -> None:
    """UPDATE runs SET <fields> WHERE id = run_id. Only whitelisted columns."""
    bad = set(fields) - _RUN_PATCHABLE
    if bad:
        raise ValueError(f"not patchable on runs: {sorted(bad)}")
    if not fields:
        return
    cols = list(fields)
    assignments = ", ".join(f"{c} = ${i + 2}" for i, c in enumerate(cols))
    async with pool().acquire() as conn:
        await conn.execute(
            f"UPDATE runs SET {assignments} WHERE id = $1",
            run_id,
            *(fields[c] for c in cols),
        )


# --------------------------------------------------------------------------- #
# supervisors
# --------------------------------------------------------------------------- #
_SUPERVISOR_COLS = "id, name, base_instruction, model_config, created_at"


async def create_supervisor(
    name: str, base_instruction: str, model_settings: dict[str, Any]
) -> asyncpg.Record:
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            f"""
            INSERT INTO supervisors (name, base_instruction, model_config)
            VALUES ($1, $2, $3)
            RETURNING {_SUPERVISOR_COLS}
            """,
            name,
            base_instruction,
            model_settings,
        )


async def list_supervisors() -> list[asyncpg.Record]:
    async with pool().acquire() as conn:
        return await conn.fetch(
            f"SELECT {_SUPERVISOR_COLS} FROM supervisors ORDER BY created_at DESC"
        )


async def fetch_supervisor(supervisor_id: str) -> asyncpg.Record | None:
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            f"SELECT {_SUPERVISOR_COLS} FROM supervisors WHERE id = $1",
            supervisor_id,
        )
