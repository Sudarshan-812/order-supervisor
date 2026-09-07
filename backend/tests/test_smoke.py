"""Scaffold smoke tests - assert the wiring imports and the shapes line up.
Replace / extend as modules get implemented.
"""
from __future__ import annotations

import importlib


def test_all_modules_import():
    for mod in [
        "app.config",
        "app.main",
        "app.models",
        "app.db",
        "app.api.routes",
        "app.temporal.client",
        "app.temporal.workflows",
        "app.temporal.activities",
        "app.temporal.worker",
        "app.agent.llm",
        "app.agent.prompts",
        "app.agent.tools",
        "app.agent.classifier",
        "app.agent.memory",
        "app.agent.runtime",
        "app.event_generator",
    ]:
        importlib.import_module(mod)


def test_tool_registry_matches_spec():
    from app.models import BUSINESS_ACTIONS, RUNTIME_CAPABILITIES
    from app.agent.tools import tool_specs

    specs = {s["name"] for s in tool_specs(list(BUSINESS_ACTIONS))}
    assert set(BUSINESS_ACTIONS) <= specs
    assert set(RUNTIME_CAPABILITIES) <= specs


def test_mock_llm_runs_without_key(monkeypatch):
    import asyncio
    from app.agent import llm

    # Force mock mode regardless of whether a real key is in .env.
    monkeypatch.setattr(llm.settings, "gemini_api_key", "", raising=False)

    out = asyncio.run(llm.generate_json(system="s", prompt="classify this event"))
    assert "wake_now" in out

    final = asyncio.run(llm.generate_json(system="s", prompt="final end-of-run report"))
    assert {"summary", "key_learnings", "feedback"} <= set(final)
