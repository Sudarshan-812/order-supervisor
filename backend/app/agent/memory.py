"""Simple context compaction.

Strategy (deliberately not sophisticated):
  * keep a rolling text summary on the run (runs.memory_summary)
  * mark only "important" activities so the timeline view can filter
  * when the recent-activity window exceeds a threshold, summarise the older
    slice via the LLM and fold it into the rolling summary
"""
from __future__ import annotations

RECENT_WINDOW = 30          # activities kept verbatim in the agent prompt
COMPACT_TRIGGER = 60        # total activities before we compact the tail


async def build_working_context(run_id: str) -> dict:
    """Return {memory_summary, recent_activities} for the agent prompt.
    TODO(scaffold): read rolling summary + last RECENT_WINDOW activities."""
    raise NotImplementedError("scaffold: build_working_context")


async def maybe_compact(run_id: str) -> str | None:
    """If activity count > COMPACT_TRIGGER, summarise activities older than the
    recent window into the rolling summary and return the new summary.
    TODO(scaffold)."""
    raise NotImplementedError("scaffold: maybe_compact")
