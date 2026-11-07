"""Optional-mode registration warns when auxiliary/title traffic is unguarded."""
import logging
import sys
import types

import pytest

import nebula
from nebula import register


class Context:
    def __init__(self):
        self.hooks = []
        self.middleware = []
        self.skills = []
        self.prompt_sections = []

    def register_hook(self, name, callback, *, hold_stream=False):
        self.hooks.append((name, callback, hold_stream))

    def register_middleware(self, name, callback):
        self.middleware.append((name, callback))

    def register_skill(self, *args):
        self.skills.append(args)

    def register_system_prompt_section(self, name, text, max_chars=0):
        self.prompt_sections.append((name, text, max_chars))


@pytest.fixture(autouse=True)
def reset_warning_flag():
    nebula._stock_warned = False
    yield
    nebula._stock_warned = False


def fake_agent(monkeypatch, required_value):
    agent = types.ModuleType("agent")
    guard = types.ModuleType("agent.privacy_guard")
    guard.required = lambda: required_value
    agent.privacy_guard = guard
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.privacy_guard", guard)


def test_register_warns_aux_unguarded_without_core(monkeypatch, caplog):
    monkeypatch.delitem(sys.modules, "agent", raising=False)
    monkeypatch.delitem(sys.modules, "agent.privacy_guard", raising=False)
    with caplog.at_level(logging.WARNING, logger="nebula"):
        register(Context())
    assert "auxiliary/title" in caplog.text
    assert "NOT guarded" in caplog.text


def test_register_warns_when_required_false(monkeypatch, caplog):
    fake_agent(monkeypatch, False)
    with caplog.at_level(logging.WARNING, logger="nebula"):
        register(Context())
    assert "auxiliary/title" in caplog.text


def test_register_silent_when_required_core_active(monkeypatch, caplog):
    fake_agent(monkeypatch, True)
    with caplog.at_level(logging.WARNING, logger="nebula"):
        register(Context())
    assert "auxiliary/title" not in caplog.text


def test_prompt_note_names_auxiliary_gap():
    ctx = Context()
    register(ctx)
    note = " ".join(text for _, text, _ in ctx.prompt_sections)
    assert "auxiliary/title" in note
