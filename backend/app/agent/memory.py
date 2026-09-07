"""Context compaction - deliberately simple.

  * The rolling summary lives on `runs.memory_summary` (a single text blob the
    agent rewrites every wake).
  * The agent prompt also gets the last RECENT_WINDOW activity_log rows verbatim.
  * When the log grows past COMPACT_TRIGGER rows, the tail (everything older
    than the recent window) is folded into the rolling summary by the LLM so the
    prompt stays bounded.
"""
from __future__ import annotations

from typing import Any

from app import db
from app.agent import llm

RECENT_WINDOW = 30          # activity_log rows kept verbatim in the agent prompt
COMPACT_TRIGGER = 80        # total rows before we summarise the tail


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "payload": row["payload"],
        "at": row["created_at"].isoformat(),
    }


async def build_working_context(run_id: str) -> dict[str, Any]:
    """Return {memory_summary, recent_timeline} for the agent prompt."""
    run = await db.fetch_run(run_id)
    memory_summary = run["memory_summary"] if run else ""
    rows = await db.fetch_activities(run_id, limit=RECENT_WINDOW, newest_first=True)
    recent = [_row_to_dict(r) for r in reversed(rows)]  # back to oldest-first
    return {"memory_summary": memory_summary, "recent_timeline": recent}


async def maybe_compact(run_id: str, current_summary: str) -> str:
    """If the log is long, fold the old tail into `current_summary` and return
    the new summary. Otherwise return `current_summary` unchanged."""
    total = await db.count_activities(run_id)
    if total <= COMPACT_TRIGGER:
        return current_summary

    tail = await db.fetch_activities(run_id, newest_first=False)
    tail = tail[:-RECENT_WINDOW] if len(tail) > RECENT_WINDOW else []
    if not tail:
        return current_summary

    out = await llm.generate_json(
        system=(
            "Compress an order-supervisor activity log tail into a compact "
            "running summary. Merge it with the existing summary. Keep every "
            "fact that affects future decisions (open issues, promises made, "
            "team hand-offs). Respond as a single JSON object: "
            '{"new_memory_summary": string}'
        ),
        prompt=(
            f"EXISTING SUMMARY:\n{current_summary or '(empty)'}\n\n"
            f"OLD ACTIVITY TAIL ({len(tail)} rows):\n"
            + "\n".join(str(_row_to_dict(r)) for r in tail)
        ),
        kind="final",
    )
    return out.get("new_memory_summary") or out.get("summary") or current_summary
