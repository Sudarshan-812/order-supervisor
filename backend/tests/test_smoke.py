"""Smoke tests - wiring imports, schema shapes, and the mock LLM path.

These run without a database, a Temporal server, or a Gemini key.
"""
from __future__ import annotations

import asyncio
import importlib

import pytest


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


def test_tool_registry_is_the_five_actions():
    from app.agent.tools import tool_specs
    from app.models import BUSINESS_ACTIONS

    names = {s["name"] for s in tool_specs([])}
    assert names == set(BUSINESS_ACTIONS)
    assert len(BUSINESS_ACTIONS) == 5


def test_frozen_contracts_are_frozen():
    from app.models import AgentDecision

    d = AgentDecision(reasoning="x", new_memory_summary="m", next_sleep_seconds=60)
    with pytest.raises(Exception):
        d.next_sleep_seconds = 1


def test_activity_types_match_schema():
    from app.models import ActivityType

    assert {t.value for t in ActivityType} == {
        "incoming_event",
        "wake_decision",
        "agent_action",
        "manual_instruction",
        "final_output",
    }


def test_mock_llm_runs_without_key(monkeypatch):
    from app.agent import llm

    monkeypatch.setattr(llm.settings, "gemini_api_key", "", raising=False)

    cls = asyncio.run(
        llm.generate_json(system="s", prompt="event payment_failed", kind="classifier")
    )
    assert cls["wake_now"] is True

    agent = asyncio.run(
        llm.generate_json(system="s", prompt="wake reason: start", kind="agent")
    )
    assert {"reasoning", "actions", "new_memory_summary", "next_sleep_seconds"} <= set(agent)

    final = asyncio.run(llm.generate_json(system="s", prompt="end", kind="final"))
    assert {"summary", "key_learnings", "feedback"} <= set(final)


def test_classifier_rules(monkeypatch):
    from app.agent import classifier

    v = asyncio.run(classifier.classify({"type": "payment_failed"}))
    assert v.wake_now is True

    v = asyncio.run(classifier.classify({"type": "payment_confirmed"}))
    assert v.wake_now is False


def test_classifier_unknown_event_fails_safe(monkeypatch):
    from app.agent import classifier, llm

    monkeypatch.setattr(llm.settings, "gemini_api_key", "", raising=False)
    v = asyncio.run(classifier.classify({"type": "warehouse_fire"}))
    # mock classifier sees "unknown"? no - fails safe to waking on unknown types
    assert v.wake_now is True
