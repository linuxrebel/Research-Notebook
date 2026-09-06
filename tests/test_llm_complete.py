"""Mocked tests for complete() — no network, no real clients.

Patches the lazy client factories in agents.llm with fakes that record the
kwargs they receive and return canned responses in each provider's shape.
"""

import asyncio
from types import SimpleNamespace

import pytest

import agents.llm as llm


class FakeAnthropic:
    def __init__(self):
        self.calls = []
        parent = self

        class Messages:
            async def create(self, **kwargs):
                parent.calls.append(kwargs)
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(type="text", text="A1"),
                        SimpleNamespace(type="tool_use", text="ignored"),
                        SimpleNamespace(type="text", text="A2"),
                    ]
                )

        self.messages = Messages()


class FakeOpenAI:
    def __init__(self, content="OUT"):
        self.calls = []
        parent = self

        class Completions:
            async def create(self, **kwargs):
                parent.calls.append(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                )

        self.chat = SimpleNamespace(completions=Completions())


def _run(coro):
    return asyncio.run(coro)


def test_anthropic_joins_text_and_passes_args(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL", "claude-x")
    fake = FakeAnthropic()
    monkeypatch.setattr(llm, "_anthropic_client", lambda: fake)

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=123,
            system="sys",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
    )

    assert out == "A1\nA2"
    kw = fake.calls[0]
    assert kw["model"] == "claude-x"
    assert kw["max_tokens"] == 123
    assert kw["system"] == "sys"
    assert kw["tools"][0]["name"] == "web_search"
    assert kw["messages"] == [{"role": "user", "content": "hi"}]


def test_anthropic_omits_optional_args(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL", "claude-x")
    fake = FakeAnthropic()
    monkeypatch.setattr(llm, "_anthropic_client", lambda: fake)

    _run(llm.complete(messages=[{"role": "user", "content": "hi"}], max_tokens=10))

    kw = fake.calls[0]
    assert "system" not in kw
    assert "tools" not in kw


def test_ollama_returns_content_and_prepends_system(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    monkeypatch.delenv("OLLAMA_REASONING_EFFORT", raising=False)
    fake = FakeOpenAI(content="hello")
    monkeypatch.setattr(llm, "_ollama_client", lambda: fake)

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            system="be brief",
        )
    )

    assert out == "hello"
    kw = fake.calls[0]
    assert kw["model"] == "ornith-1.5:9b"
    assert kw["messages"][0] == {"role": "system", "content": "be brief"}
    assert kw["messages"][1] == {"role": "user", "content": "hi"}
    assert kw["reasoning_effort"] == "none"


def test_ollama_ignores_tools_but_still_completes(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    fake = FakeOpenAI(content="ok")
    monkeypatch.setattr(llm, "_ollama_client", lambda: fake)

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
    )

    assert out == "ok"
    assert "tools" not in fake.calls[0]  # tools not forwarded to ollama


def test_ollama_per_call_reasoning_override(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "none")
    fake = FakeOpenAI(content="ok")
    monkeypatch.setattr(llm, "_ollama_client", lambda: fake)

    _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1200,
            reasoning_effort="medium",
        )
    )
    assert fake.calls[0]["reasoning_effort"] == "medium"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "bogus")
    monkeypatch.setenv("MODEL", "x")
    with pytest.raises(ValueError):
        _run(llm.complete(messages=[{"role": "user", "content": "hi"}], max_tokens=10))
